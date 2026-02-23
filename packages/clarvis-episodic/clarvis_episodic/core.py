"""
EpisodicStore — the main episodic memory store.

Self-contained JSON-backed episodic memory with ACT-R activation dynamics.
No external dependencies beyond the standard library.

Optional integration points:
- ChromaDB for semantic recall (falls back to keyword matching)
- Custom callbacks for encoding/recall events
"""

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from clarvis_episodic.actr import compute_activation, compute_valence


class EpisodicStore:
    """ACT-R episodic memory store.

    Episodes are stored as JSON with activation dynamics. Each episode
    tracks access times for power-law decay computation.

    Args:
        data_dir: Directory for episode storage (created if missing).
        max_episodes: Maximum episodes to retain (FIFO eviction).
        chroma_collection: Optional ChromaDB collection for semantic search.
        on_encode: Optional callback(episode) fired after encoding.
        on_recall: Optional callback(query, results) fired after recall.
    """

    def __init__(
        self,
        data_dir: str = "./data",
        max_episodes: int = 500,
        chroma_collection=None,
        on_encode: Optional[Callable] = None,
        on_recall: Optional[Callable] = None,
    ):
        self.data_dir = Path(data_dir)
        self.max_episodes = max_episodes
        self.episodes_file = self.data_dir / "episodes.json"
        self.chroma = chroma_collection
        self.on_encode = on_encode
        self.on_recall = on_recall
        self.episodes: List[Dict[str, Any]] = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        if self.episodes_file.exists():
            with open(self.episodes_file) as f:
                return json.load(f)
        return []

    def _save(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with open(self.episodes_file, "w") as f:
            json.dump(self.episodes[-self.max_episodes :], f, indent=2)

    # === CORE API ===

    def encode(
        self,
        task: str,
        section: str = "general",
        salience: float = 0.5,
        outcome: str = "success",
        duration_s: float = 0,
        error_msg: Optional[str] = None,
        steps: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Encode a new episode.

        Args:
            task: Description of what happened.
            section: Category/section (e.g., "P0", "bugs", "evolution").
            salience: Task importance (0.0-1.0).
            outcome: "success", "failure", "soft_failure", or "timeout".
            duration_s: How long the task took (seconds).
            error_msg: Error message if applicable (truncated to 200 chars).
            steps: List of steps taken.
            metadata: Arbitrary extra metadata.

        Returns:
            The encoded episode dict.
        """
        now = datetime.now(timezone.utc)

        # Detect novel errors (not seen in last 20 episodes)
        is_novel_error = False
        if error_msg:
            is_novel_error = not any(
                e.get("error") and e["error"][:50] == error_msg[:50]
                for e in self.episodes[-20:]
            )

        valence = compute_valence(outcome, salience, duration_s, is_novel_error)

        episode = {
            "id": f"ep_{now.strftime('%Y%m%d_%H%M%S')}",
            "timestamp": now.isoformat(),
            "task": task,
            "section": section,
            "salience": float(salience),
            "outcome": outcome,
            "valence": valence,
            "duration_s": duration_s,
            "error": error_msg[:200] if error_msg else None,
            "steps": steps,
            "access_times": [now.timestamp()],
            "activation": 1.0,
        }
        if metadata:
            episode["metadata"] = metadata

        self.episodes.append(episode)
        self._save()

        # Index in ChromaDB if available
        if self.chroma:
            try:
                summary = f"Episode: {task[:100]} -> {outcome}"
                if error_msg:
                    summary += f" (error: {error_msg[:80]})"
                self.chroma.upsert(
                    ids=[episode["id"]],
                    documents=[summary],
                    metadatas=[{"outcome": outcome, "section": section, "valence": valence}],
                )
            except Exception:
                pass  # Semantic index is optional

        if self.on_encode:
            try:
                self.on_encode(episode)
            except Exception:
                pass

        return episode

    def recall(self, query: str, n: int = 5) -> List[Dict[str, Any]]:
        """Recall episodes similar to the query.

        Uses ChromaDB for semantic search if available, otherwise falls
        back to keyword matching. Results are re-ranked by ACT-R activation.

        Args:
            query: Search query.
            n: Max episodes to return.

        Returns:
            List of episodes sorted by activation (highest first).
        """
        self._decay_all()

        if self.chroma and query:
            return self._recall_semantic(query, n)
        return self._recall_keyword(query, n)

    def failures(self, n: int = 5) -> List[Dict[str, Any]]:
        """Recall recent failure episodes (high learning value).

        Returns failures sorted by activation — most accessible first.
        """
        self._decay_all()
        fails = [
            e for e in self.episodes
            if e["outcome"] in ("failure", "soft_failure", "timeout")
        ]
        fails.sort(key=lambda e: e["activation"], reverse=True)
        return fails[:n]

    def stats(self) -> Dict[str, Any]:
        """Compute episodic memory statistics."""
        if not self.episodes:
            return {"total": 0}

        self._decay_all()

        outcomes: Dict[str, int] = {}
        for ep in self.episodes:
            outcomes[ep["outcome"]] = outcomes.get(ep["outcome"], 0) + 1

        activations = [e.get("activation", 0.0) for e in self.episodes]
        avg_valence = sum(e["valence"] for e in self.episodes) / len(self.episodes)
        avg_activation = sum(activations) / len(activations)

        forgotten = sum(1 for a in activations if a < -4.0)
        strong = sum(1 for a in activations if a > -1.0)

        return {
            "total": len(self.episodes),
            "outcomes": outcomes,
            "avg_valence": round(avg_valence, 3),
            "avg_activation": round(avg_activation, 3),
            "activation_min": round(min(activations), 3),
            "activation_max": round(max(activations), 3),
            "strong_memories": strong,
            "forgotten_memories": forgotten,
            "decay_model": "power-law (Pavlik & Anderson 2005, c=0.5, gamma=1.6)",
            "oldest": self.episodes[0]["timestamp"][:10],
            "newest": self.episodes[-1]["timestamp"][:10],
        }

    def synthesize(self) -> Dict[str, Any]:
        """Analyze episodes for recurring patterns.

        Examines outcomes, action verbs, error types, and domain clusters.
        Returns actionable insights about what's working and what's failing.
        """
        if not self.episodes:
            return {"error": "No episodes to analyze", "recommendations": []}

        total = len(self.episodes)

        # Outcome counts
        outcomes: Dict[str, int] = {}
        for ep in self.episodes:
            outcomes[ep["outcome"]] = outcomes.get(ep["outcome"], 0) + 1

        success_count = outcomes.get("success", 0)
        success_rate = success_count / total

        # Action verb analysis
        success_verbs: Dict[str, int] = {}
        failure_verbs: Dict[str, int] = {}
        for ep in self.episodes:
            words = ep["task"].split()
            verb = words[0].lower().strip("[]()") if words else ""
            if not verb:
                continue
            if ep["outcome"] == "success":
                success_verbs[verb] = success_verbs.get(verb, 0) + 1
            else:
                failure_verbs[verb] = failure_verbs.get(verb, 0) + 1

        # Section analysis
        section_outcomes: Dict[str, Dict[str, int]] = {}
        for ep in self.episodes:
            sec = ep.get("section", "unknown")
            if sec not in section_outcomes:
                section_outcomes[sec] = {}
            o = ep["outcome"]
            section_outcomes[sec][o] = section_outcomes[sec].get(o, 0) + 1

        # Error classification
        error_types: Dict[str, int] = {}
        for ep in self.episodes:
            if ep.get("error"):
                err = ep["error"].lower()
                if "importerror" in err or "modulenotfounderror" in err:
                    error_types["module_import"] = error_types.get("module_import", 0) + 1
                elif "attributeerror" in err:
                    error_types["attribute"] = error_types.get("attribute", 0) + 1
                elif "timeout" in err:
                    error_types["timeout"] = error_types.get("timeout", 0) + 1
                else:
                    error_types["other"] = error_types.get("other", 0) + 1

        # Generate recommendations
        recommendations = []
        if success_rate < 0.8 and total >= 3:
            recommendations.append(
                f"Success rate is {success_rate:.0%} — below 80% target. "
                "Review failure patterns and add pre-flight checks."
            )
        for sec, counts in section_outcomes.items():
            s = counts.get("success", 0)
            f = sum(v for k, v in counts.items() if k != "success")
            if f > 0 and s + f > 0 and f / (s + f) > 0.3:
                recommendations.append(
                    f"Section '{sec}' has {f/(s+f):.0%} failure rate ({f}/{s+f}). Investigate."
                )
        if error_types.get("module_import", 0) > 1:
            recommendations.append(
                f"Module import errors appeared {error_types['module_import']} times. "
                "Audit dependencies and sys.path."
            )

        top_success = sorted(success_verbs.items(), key=lambda x: x[1], reverse=True)[:5]
        top_failure = sorted(failure_verbs.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "total_episodes": total,
            "outcomes": outcomes,
            "success_rate": round(success_rate, 2),
            "top_success_actions": top_success,
            "top_failure_actions": top_failure,
            "section_outcomes": section_outcomes,
            "error_types": error_types,
            "recommendations": recommendations,
        }

    # === INTERNAL ===

    def _decay_all(self):
        """Recompute activations for all episodes."""
        for ep in self.episodes:
            ep["activation"] = compute_activation(ep.get("access_times", []))

    def _recall_semantic(self, query: str, n: int) -> List[Dict[str, Any]]:
        """Semantic recall via ChromaDB."""
        results = self.chroma.query(query_texts=[query], n_results=n * 2)
        matched = []
        seen_ids = set()

        for r_ids in results.get("ids", [[]]):
            for rid in r_ids:
                for ep in self.episodes:
                    if ep["id"] in seen_ids:
                        continue
                    if ep["id"] == rid:
                        ep["access_times"].append(datetime.now(timezone.utc).timestamp())
                        ep["activation"] = compute_activation(ep["access_times"])
                        matched.append(ep)
                        seen_ids.add(ep["id"])
                        break

        self._save()
        matched.sort(key=lambda e: e["activation"], reverse=True)
        result = matched[:n]

        if self.on_recall:
            try:
                self.on_recall(query, result)
            except Exception:
                pass

        return result

    def _recall_keyword(self, query: str, n: int) -> List[Dict[str, Any]]:
        """Keyword-based fallback recall (no ChromaDB needed)."""
        if not query:
            # No query = return most active episodes
            scored = sorted(self.episodes, key=lambda e: e["activation"], reverse=True)
            return scored[:n]

        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored = []
        for ep in self.episodes:
            task_lower = ep["task"].lower()
            # Word overlap scoring
            task_words = set(task_lower.split())
            overlap = len(query_words & task_words)
            if overlap == 0 and query_lower not in task_lower:
                continue

            # Substring match bonus
            substr_bonus = 0.5 if query_lower in task_lower else 0.0

            # Combined score: keyword relevance + activation
            relevance = (overlap / max(1, len(query_words))) + substr_bonus
            combined = relevance * 0.6 + (ep["activation"] + 5.0) / 10.0 * 0.4

            # Record access
            ep["access_times"].append(datetime.now(timezone.utc).timestamp())
            ep["activation"] = compute_activation(ep["access_times"])

            scored.append((combined, ep))

        self._save()
        scored.sort(key=lambda x: x[0], reverse=True)
        result = [ep for _, ep in scored[:n]]

        if self.on_recall:
            try:
                self.on_recall(query, result)
            except Exception:
                pass

        return result

    def get_episode(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific episode by ID."""
        for ep in self.episodes:
            if ep["id"] == episode_id:
                return ep
        return None

    def forget(self, episode_id: str) -> bool:
        """Explicitly remove an episode."""
        for i, ep in enumerate(self.episodes):
            if ep["id"] == episode_id:
                self.episodes.pop(i)
                self._save()
                if self.chroma:
                    try:
                        self.chroma.delete(ids=[episode_id])
                    except Exception:
                        pass
                return True
        return False

    def export(self, path: Optional[str] = None) -> str:
        """Export all episodes to JSON.

        Args:
            path: File path to write to (default: return JSON string).

        Returns:
            JSON string of all episodes.
        """
        data = json.dumps(self.episodes, indent=2)
        if path:
            Path(path).write_text(data)
        return data

    def import_episodes(self, path: str, merge: bool = True) -> int:
        """Import episodes from a JSON file.

        Args:
            path: Path to JSON file.
            merge: If True, merge with existing (skip duplicates by ID).
                   If False, replace all episodes.

        Returns:
            Number of episodes imported.
        """
        with open(path) as f:
            incoming = json.load(f)

        if not merge:
            self.episodes = incoming
            self._save()
            return len(incoming)

        existing_ids = {e["id"] for e in self.episodes}
        imported = 0
        for ep in incoming:
            if ep["id"] not in existing_ids:
                self.episodes.append(ep)
                imported += 1

        self._save()
        return imported
