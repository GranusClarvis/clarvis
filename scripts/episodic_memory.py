#!/usr/bin/env python3
"""
Episodic Memory System — ACT-R inspired episode encoding and retrieval.

Each heartbeat task becomes an "episode" with:
- context (what was happening)
- actions (what was done)
- outcome (success/failure)
- valence (emotional weight: surprise, pain, satisfaction)
- activation (strengthens on retrieval, decays over time)

Episodes are stored in brain's EPISODES collection.
Activation follows ACT-R: A(i) = ln(sum(t_j^(-d))) + spreading
"""

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brain import brain

EPISODES_FILE = Path("/home/agent/.openclaw/workspace/data/episodes.json")


class EpisodicMemory:
    def __init__(self):
        self.episodes = self._load()

    def _load(self):
        if EPISODES_FILE.exists():
            with open(EPISODES_FILE) as f:
                return json.load(f)
        return []

    def _save(self):
        EPISODES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(EPISODES_FILE, 'w') as f:
            json.dump(self.episodes[-500:], f, indent=2)  # cap at 500

    def encode(self, task_text, section, salience, outcome,
               duration_s=0, error_msg=None, steps_taken=None):
        """Encode a new episode from a heartbeat task."""
        now = datetime.now(timezone.utc)

        # Calculate emotional valence
        valence = self._compute_valence(outcome, salience, duration_s, error_msg)

        episode = {
            "id": f"ep_{now.strftime('%Y%m%d_%H%M%S')}",
            "timestamp": now.isoformat(),
            "task": task_text,
            "section": section,
            "salience": float(salience),
            "outcome": outcome,  # "success" | "failure" | "timeout"
            "valence": valence,
            "duration_s": duration_s,
            "error": error_msg[:200] if error_msg else None,
            "steps": steps_taken,
            "access_times": [now.timestamp()],  # ACT-R: track retrievals
            "activation": 1.0  # initial activation
        }

        self.episodes.append(episode)
        self._save()

        # Store searchable version in brain
        importance = min(1.0, 0.5 + valence * 0.3)
        tags = ["episode", outcome, section]
        summary = f"Episode: {task_text[:100]} -> {outcome}"
        if error_msg:
            summary += f" (error: {error_msg[:80]})"

        brain.store(
            summary,
            collection="clarvis-episodes",
            importance=importance,
            tags=tags,
            source="episodic_memory"
        )

        return episode

    def recall_similar(self, query, n=5):
        """Recall episodes similar to the current situation.
        Returns episodes sorted by activation (ACT-R style)."""
        # Semantic search in brain
        results = brain.recall(query, n=n * 2, collections=["clarvis-episodes"])

        # Recompute all activations (ACT-R decay)
        self._decay_activations()

        # Boost retrieved episodes' activation (retrieval strengthens memory)
        matched_episodes = []
        seen_ids = set()
        for r in results:
            doc = r.get("document", "")
            # Find matching local episode
            for ep in self.episodes:
                if ep["id"] in seen_ids:
                    continue
                if ep["task"][:50] in doc or doc[:50] in f"Episode: {ep['task']}":
                    ep["access_times"].append(datetime.now(timezone.utc).timestamp())
                    ep["activation"] = self._compute_activation(ep)
                    matched_episodes.append(ep)
                    seen_ids.add(ep["id"])
                    break

        self._save()
        # Sort by activation (highest first)
        matched_episodes.sort(key=lambda e: e["activation"], reverse=True)
        return matched_episodes[:n]

    def recall_failures(self, n=5):
        """Recall recent failure episodes (high learning value)."""
        failures = [e for e in self.episodes if e["outcome"] == "failure"]
        self._decay_activations()
        failures.sort(key=lambda e: e["activation"], reverse=True)
        return failures[:n]

    def get_stats(self):
        """Get episodic memory statistics."""
        if not self.episodes:
            return {"total": 0}

        outcomes = {}
        for ep in self.episodes:
            outcomes[ep["outcome"]] = outcomes.get(ep["outcome"], 0) + 1

        avg_valence = sum(e["valence"] for e in self.episodes) / len(self.episodes)
        avg_activation = sum(e.get("activation", 0.5) for e in self.episodes) / len(self.episodes)

        return {
            "total": len(self.episodes),
            "outcomes": outcomes,
            "avg_valence": round(avg_valence, 3),
            "avg_activation": round(avg_activation, 3),
            "oldest": self.episodes[0]["timestamp"][:10],
            "newest": self.episodes[-1]["timestamp"][:10]
        }

    def _compute_valence(self, outcome, salience, duration_s, error_msg):
        """Compute emotional valence of an episode.
        Higher = more emotionally significant (worth remembering).
        Range: 0.0 to 1.0"""
        valence = 0.3  # baseline

        # Failures are more memorable (negativity bias)
        if outcome == "failure":
            valence += 0.3
        elif outcome == "timeout":
            valence += 0.2

        # High-salience tasks are more memorable
        valence += float(salience) * 0.2

        # Long tasks are more memorable
        if duration_s > 300:
            valence += 0.1

        # Novel errors are more memorable
        if error_msg and not any(
            e.get("error") and e["error"][:50] == error_msg[:50]
            for e in self.episodes[-20:]
        ):
            valence += 0.1

        return min(1.0, valence)

    def _compute_activation(self, episode):
        """ACT-R base-level activation.
        A(i) = ln(sum(t_j^(-d))) where t_j = seconds since j-th access
        d = 0.5 (decay parameter)"""
        access_times = episode.get("access_times", [])
        if not access_times:
            return 0.0

        d = 0.5  # ACT-R default decay
        now = datetime.now(timezone.utc).timestamp()

        total = 0.0
        for t in access_times:
            age = max(1.0, now - t)  # avoid log(0)
            total += age ** (-d)

        return math.log(max(1e-10, total))

    def _decay_activations(self):
        """Recompute all activations (ACT-R decay)."""
        for ep in self.episodes:
            ep["activation"] = self._compute_activation(ep)


# Singleton
episodic = EpisodicMemory()

# CLI interface
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: episodic_memory.py <encode|recall|failures|stats>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "encode":
        # encode <task> <section> <salience> <outcome> [duration_s] [error]
        if len(sys.argv) < 6:
            print("Usage: encode <task> <section> <salience> <outcome> [duration] [error]")
            sys.exit(1)
        ep = episodic.encode(
            task_text=sys.argv[2],
            section=sys.argv[3],
            salience=sys.argv[4],
            outcome=sys.argv[5],
            duration_s=int(sys.argv[6]) if len(sys.argv) > 6 else 0,
            error_msg=sys.argv[7] if len(sys.argv) > 7 else None
        )
        print(json.dumps(ep, indent=2))

    elif cmd == "recall":
        query = sys.argv[2] if len(sys.argv) > 2 else ""
        episodes = episodic.recall_similar(query)
        for ep in episodes:
            print(f"  [{ep['outcome']}] (act={ep['activation']:.2f}) {ep['task'][:80]}")

    elif cmd == "failures":
        failures = episodic.recall_failures()
        for ep in failures:
            print(f"  (act={ep['activation']:.2f}, val={ep['valence']:.2f}) {ep['task'][:70]}")
            if ep.get("error"):
                print(f"    Error: {ep['error'][:100]}")

    elif cmd == "stats":
        stats = episodic.get_stats()
        print(json.dumps(stats, indent=2))

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
