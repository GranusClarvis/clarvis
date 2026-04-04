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
Activation follows ACT-R power-law: A(i) = ln(sum(t_j^(-d_j)))
where d_j = c * lag_j^(-1/gamma) (Pavlik & Anderson 2005 spacing model)

Causal Graph:
Episodes are connected by directed causal links. Each link records a
relationship type (caused, enabled, blocked, fixed, retried) between
two episodes, forming a DAG that supports temporal reasoning queries
like "what caused this failure?" and "what chain of events led here?"
"""

import json
import math
import os
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from clarvis.brain import brain

_WS = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
_SCRIPTS_DIR = os.path.join(_WS, "scripts")

EPISODES_FILE = Path(_WS) / "data" / "episodes.json"
CAUSAL_LINKS_FILE = Path(_WS) / "data" / "causal_links.json"

# Valid causal relationship types
CAUSAL_RELATIONSHIPS = {
    "caused":  "A directly caused B to happen",
    "enabled": "A made B possible (necessary precondition)",
    "blocked": "A prevented B from succeeding",
    "fixed":   "B was a fix/resolution of A's failure",
    "retried": "B was a retry of the same task as A",
    "related": "A and B share topic/collection overlap (auto-inferred)",
}


class EpisodicMemory:
    def __init__(self):
        self.episodes = self._load()
        self.causal_links = self._load_causal()
        # Index for fast episode lookup by id
        self._id_index = {ep["id"]: ep for ep in self.episodes}

    def _load(self):
        if EPISODES_FILE.exists():
            with open(EPISODES_FILE) as f:
                return json.load(f)
        return []

    def _load_causal(self):
        if CAUSAL_LINKS_FILE.exists():
            with open(CAUSAL_LINKS_FILE) as f:
                return json.load(f)
        return []

    def _save(self):
        EPISODES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(EPISODES_FILE, 'w') as f:
            json.dump(self.episodes[-500:], f, indent=2)  # cap at 500

    def _save_causal(self):
        CAUSAL_LINKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CAUSAL_LINKS_FILE, 'w') as f:
            json.dump(self.causal_links[-2000:], f, indent=2)  # cap at 2000

    # ------------------------------------------------------------------
    # Causal graph: linking and querying
    # ------------------------------------------------------------------

    def causal_link(self, episode_a, episode_b, relationship, confidence=1.0):
        """Create a directed causal link: episode_a --[relationship]--> episode_b.

        Args:
            episode_a: episode id (str) or episode dict — the cause/source
            episode_b: episode id (str) or episode dict — the effect/target
            relationship: one of caused, enabled, blocked, fixed, retried
            confidence: 0.0-1.0, how certain we are about this link (default 1.0)

        Returns:
            The created link dict, or None if invalid.
        """
        id_a = episode_a["id"] if isinstance(episode_a, dict) else episode_a
        id_b = episode_b["id"] if isinstance(episode_b, dict) else episode_b

        if relationship not in CAUSAL_RELATIONSHIPS:
            print(f"Invalid relationship '{relationship}'. "
                  f"Valid: {list(CAUSAL_RELATIONSHIPS.keys())}")
            return None

        if id_a == id_b:
            return None  # no self-loops

        # Prevent exact duplicate links
        for link in self.causal_links:
            if (link["from"] == id_a and link["to"] == id_b
                    and link["relationship"] == relationship):
                return link  # already exists

        link = {
            "from": id_a,
            "to": id_b,
            "relationship": relationship,
            "confidence": round(min(1.0, max(0.0, confidence)), 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.causal_links.append(link)
        self._save_causal()
        return link

    def causes_of(self, episode_id, relationship=None):
        """Return all direct causes of an episode (incoming edges).

        Args:
            episode_id: str episode id
            relationship: optional filter (e.g. "blocked")

        Returns:
            List of (link, episode) tuples where episode caused this one.
        """
        eid = episode_id["id"] if isinstance(episode_id, dict) else episode_id
        results = []
        for link in self.causal_links:
            if link["to"] != eid:
                continue
            if relationship and link["relationship"] != relationship:
                continue
            ep = self._id_index.get(link["from"])
            results.append((link, ep))
        return results

    def effects_of(self, episode_id, relationship=None):
        """Return all direct effects of an episode (outgoing edges).

        Args:
            episode_id: str episode id
            relationship: optional filter

        Returns:
            List of (link, episode) tuples where this episode caused them.
        """
        eid = episode_id["id"] if isinstance(episode_id, dict) else episode_id
        results = []
        for link in self.causal_links:
            if link["from"] != eid:
                continue
            if relationship and link["relationship"] != relationship:
                continue
            ep = self._id_index.get(link["to"])
            results.append((link, ep))
        return results

    def causal_chain(self, episode_id, direction="backward", max_depth=10):
        """Walk the causal graph transitively.

        Args:
            episode_id: starting episode id
            direction: "backward" traces causes, "forward" traces effects
            max_depth: maximum traversal depth to prevent infinite loops

        Returns:
            List of (depth, link, episode) tuples in BFS order.
        """
        eid = episode_id["id"] if isinstance(episode_id, dict) else episode_id

        # Build adjacency for the chosen direction
        if direction == "backward":
            # link["to"] -> link["from"] (trace causes)
            adj = {}
            for link in self.causal_links:
                adj.setdefault(link["to"], []).append(link)
            get_next = lambda link: link["from"]
        else:
            # link["from"] -> link["to"] (trace effects)
            adj = {}
            for link in self.causal_links:
                adj.setdefault(link["from"], []).append(link)
            get_next = lambda link: link["to"]

        visited = {eid}
        queue = deque()
        # Seed with depth 0 neighbors
        for link in adj.get(eid, []):
            nxt = get_next(link)
            if nxt not in visited:
                queue.append((1, link, nxt))

        chain = []
        while queue:
            depth, link, node_id = queue.popleft()
            if node_id in visited or depth > max_depth:
                continue
            visited.add(node_id)
            ep = self._id_index.get(node_id)
            chain.append((depth, link, ep))
            # Continue traversal
            for next_link in adj.get(node_id, []):
                nxt = get_next(next_link)
                if nxt not in visited:
                    queue.append((depth + 1, next_link, nxt))

        return chain

    def root_causes(self, episode_id, max_depth=10):
        """Find root causes — episodes with no incoming causal links
        in the backward chain from the given episode."""
        chain = self.causal_chain(episode_id, direction="backward", max_depth=max_depth)
        if not chain:
            return []

        # Collect all "to" targets in the chain's links
        has_incoming = set()
        for _, link, _ in chain:
            has_incoming.add(link["to"])

        # Root causes are chain nodes that have no incoming link in the subgraph
        roots = []
        for depth, link, ep in chain:
            node_id = link["from"]
            if node_id not in has_incoming and ep is not None:
                roots.append(ep)
        return roots

    def causal_graph_stats(self):
        """Summary statistics for the causal graph."""
        if not self.causal_links:
            return {"total_links": 0}

        rel_counts = {}
        for link in self.causal_links:
            r = link["relationship"]
            rel_counts[r] = rel_counts.get(r, 0) + 1

        # Count unique nodes involved
        nodes = set()
        for link in self.causal_links:
            nodes.add(link["from"])
            nodes.add(link["to"])

        # Find episodes with most connections (hubs)
        in_degree = {}
        out_degree = {}
        for link in self.causal_links:
            out_degree[link["from"]] = out_degree.get(link["from"], 0) + 1
            in_degree[link["to"]] = in_degree.get(link["to"], 0) + 1

        top_causes = sorted(out_degree.items(), key=lambda x: x[1], reverse=True)[:5]
        top_effects = sorted(in_degree.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "total_links": len(self.causal_links),
            "unique_nodes": len(nodes),
            "relationship_counts": rel_counts,
            "top_causes": [(eid, deg, self._id_index.get(eid, {}).get("task", "?")[:60])
                           for eid, deg in top_causes],
            "top_effects": [(eid, deg, self._id_index.get(eid, {}).get("task", "?")[:60])
                            for eid, deg in top_effects],
        }

    def backfill_causal_links(self):
        """Retroactively detect causal links across ALL existing episodes.

        Walks through episodes chronologically, applying _auto_link_against()
        for each episode against its predecessors (window of 30).
        Returns count of links created.
        """
        created = 0
        for i, ep in enumerate(self.episodes):
            window_start = max(0, i - 30)
            window = self.episodes[window_start:i]
            if not window:
                continue
            before = len(self.causal_links)
            self._auto_link_against(ep, window)
            created += len(self.causal_links) - before
        if created:
            self._save_causal()
        return created

    @staticmethod
    def _keyword_overlap(text_a, text_b, min_len=4):
        """Compute overlap using meaningful keywords (ignoring short/stop words).

        More robust than raw word overlap for diverse task descriptions
        because it strips brackets, tags, and short words.
        """
        import re as _re
        def extract(t):
            return set(
                w.lower() for w in _re.split(r'[\s\-_/.,;:()[\]]+', t)
                if len(w) >= min_len and w.isalpha()
            )
        ka, kb = extract(text_a), extract(text_b)
        if not ka or not kb:
            return 0.0
        return len(ka & kb) / max(1, len(ka | kb))

    def _auto_link_against(self, new_episode, candidates, max_links=3):
        """Heuristically detect causal links between new_episode and candidates.

        Uses both raw word overlap and keyword overlap (ignoring tags/short words)
        to catch relationships between diverse task descriptions.
        Creates up to max_links links per episode (strongest relationships first).
        Returns number of links created.
        """
        if not candidates:
            return 0

        new_words = set((new_episode.get("task") or "").lower().split())
        new_section = new_episode.get("section")
        new_outcome = new_episode.get("outcome")
        links_created = 0
        linked_ids = set()

        for prior in reversed(candidates):
            if links_created >= max_links:
                break
            prior_id = prior.get("id", "")
            if prior_id in linked_ids:
                continue

            prior_words = set((prior.get("task") or "").lower().split())
            raw_overlap = len(new_words & prior_words) / max(1, len(new_words | prior_words))
            kw_overlap = self._keyword_overlap(new_episode["task"], prior["task"])
            overlap = max(raw_overlap, kw_overlap)

            # Strong causal: retry (same section + prior failed + high overlap)
            if (overlap > 0.35
                    and prior["outcome"] in ("failure", "timeout")
                    and prior["section"] == new_section):
                self.causal_link(prior, new_episode, "retried", confidence=round(overlap, 2))
                linked_ids.add(prior_id)
                links_created += 1
                continue

            # Fix: new success after prior failure with overlap
            if (new_outcome == "success"
                    and prior["outcome"] in ("failure", "timeout", "soft_failure")
                    and overlap > 0.20):
                self.causal_link(prior, new_episode, "fixed", confidence=round(overlap, 2))
                linked_ids.add(prior_id)
                links_created += 1
                continue

            # Enabled: prior success enables new success
            if (prior["outcome"] == "success"
                    and overlap > 0.12
                    and new_outcome == "success"):
                self.causal_link(prior, new_episode, "enabled", confidence=round(min(0.7, overlap), 2))
                linked_ids.add(prior_id)
                links_created += 1
                continue

            # Blocked: both failed with overlap
            if (prior["outcome"] in ("failure", "timeout")
                    and new_outcome in ("failure", "timeout")
                    and overlap > 0.20):
                self.causal_link(prior, new_episode, "blocked", confidence=round(overlap, 2))
                linked_ids.add(prior_id)
                links_created += 1
                continue

            # Related: moderate topic overlap regardless of outcome (new rule)
            if overlap > 0.15 and prior["section"] == new_section:
                self.causal_link(prior, new_episode, "related", confidence=round(overlap, 2))
                linked_ids.add(prior_id)
                links_created += 1
                continue

            # Related: higher overlap across sections
            if overlap > 0.25:
                self.causal_link(prior, new_episode, "related", confidence=round(overlap, 2))
                linked_ids.add(prior_id)
                links_created += 1
                continue

        return links_created

    def _auto_link(self, new_episode):
        """Heuristically detect causal links between new_episode and recent episodes.

        Detection rules:
        1. RETRY: same section + similar task text + prior was failure → retried
        2. FIX: new success that follows a failure with overlapping keywords → fixed
        3. ENABLED: prior success with topic overlap → enabled
        4. BLOCKED: prior failure in same section, new episode also fails → blocked
        5. RELATED: moderate topic/section overlap regardless of outcome → related

        Returns number of links created.
        """
        recent = self.episodes[-30:-1]  # last 30 episodes excluding new one
        return self._auto_link_against(new_episode, recent)

    # Valid failure types for structured categorization
    FAILURE_TYPES = {
        "timeout":      "Task exceeded time limit (exit 124 or similar)",
        "import_error": "ImportError/ModuleNotFoundError — missing dependency",
        "data_missing": "Missing file, broken JSON, empty data, missing config",
        "external_dep": "Network, API, auth, rate-limit, service failure",
        "memory":       "ChromaDB/embedding/brain subsystem failure",
        "planning":     "Task selection, queue, routing, preflight failure",
        "logic_bug":    "Assertion, type, value, index, attribute error",
        "system":       "OS, permissions, disk, OOM, segfault",
        "action":       "General code/execution error (unclassified)",
        "action.param_missing":  "Missing required argument or parameter",
        "action.api_error":      "API call failure (HTTP, OpenRouter, model error)",
        "action.race_condition": "Concurrency/lock/stale-state issue",
        "action.validation":     "Schema, format, or contract validation failure",
        "crash":        "Infrastructure crash (instant-fail, <10s duration)",
        "partial-success": "Task partially completed but did not fully succeed",
    }

    def encode(self, task_text, section, salience, outcome,
               duration_s=0, error_msg=None, steps_taken=None,
               failure_type=None):
        """Encode a new episode from a heartbeat task.

        Args:
            failure_type: Optional structured failure category. One of:
                timeout, memory, planning, system, action, partial-success.
                Only meaningful when outcome != 'success'.
        """
        now = datetime.now(timezone.utc)

        # Calculate emotional valence
        valence = self._compute_valence(outcome, salience, duration_s, error_msg)

        # Validate and normalize failure_type; auto-detect system failures from error
        ft = None
        if outcome != "success":
            if failure_type:
                ft = failure_type if failure_type in self.FAILURE_TYPES else "action"
            elif error_msg:
                # Auto-classify infrastructure failures to avoid polluting action accuracy
                err_lower = error_msg.lower()
                if any(sig in err_lower for sig in (
                    "401", "authentication_error", "oauth token",
                    "importerror", "modulenotfounderror",
                    "nested sessions", "cannot be launched inside",
                    "permission denied", "disk quota", "no space left",
                )):
                    ft = "system"
            # Always assign a failure_type for non-success outcomes;
            # "action" is the catch-all default when no specific type detected
            if ft is None:
                ft = "action"

        episode = {
            "id": f"ep_{now.strftime('%Y%m%d_%H%M%S')}",
            "timestamp": now.isoformat(),
            "task": task_text,
            "section": section,
            "salience": float(salience),
            "outcome": outcome,  # "success" | "failure" | "timeout"
            "failure_type": ft,  # structured failure category (None for success)
            "valence": valence,
            "duration_s": duration_s,
            "error": error_msg[:200] if error_msg else None,
            "steps": steps_taken,
            "access_times": [now.timestamp()],  # ACT-R: track retrievals
            "activation": 1.0  # initial activation
        }

        self.episodes.append(episode)
        self._id_index[episode["id"]] = episode
        self._save()

        # Auto-detect causal links with recent episodes
        causal_links_created = self._auto_link(episode)
        episode["causal_links_created"] = causal_links_created

        self._post_encode(episode, task_text, valence, ft, error_msg)
        return episode

    def _post_encode(self, episode, task_text, valence, ft, error_msg):
        """Auto-tag, store in brain, and create somatic markers for a new episode."""
        import re
        if re.search(r'code|implement|fix|create|add|write|refactor|migrate|wire|test|build',
                      task_text, re.I):
            episode["is_code_task"] = True

        importance = min(1.0, 0.5 + valence * 0.3)
        tags = ["episode", episode["outcome"], episode["section"]]
        if episode.get("is_code_task"):
            tags.append("code_task")
        if ft:
            tags.append(f"failure:{ft}")
        summary = f"Episode: {task_text[:100]} -> {episode['outcome']}"
        if ft:
            summary += f" [{ft}]"
        if error_msg:
            summary += f" (error: {error_msg[:80]})"

        brain.store(summary, collection="clarvis-episodes",
                    importance=importance, tags=tags, source="episodic_memory")

        try:
            from clarvis.cognition.somatic_markers import somatic
            somatic.tag_episode(episode)
        except Exception:
            pass

    def get_recent(self, limit=50):
        """Return the most recent episodes (newest first), up to `limit`."""
        return list(reversed(self.episodes[-limit:]))

    def recall_similar(self, query, n=5, use_spreading_activation=True):
        """Recall episodes similar to the current situation.
        Returns episodes sorted by activation (ACT-R style).

        If use_spreading_activation=True, also boosts attention items related
        to the query — closing the loop between episodic recall and GWT spotlight.
        """
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
        top_episodes = matched_episodes[:n]

        # === SPREADING ACTIVATION: Connect episodic recall to attention spotlight ===
        if use_spreading_activation and top_episodes:
            try:
                from clarvis.cognition.attention import attention
                # Build activation text from retrieved episodes
                activation_text = " ".join(ep["task"] for ep in top_episodes)
                # Boost spotlight items that overlap with recalled episodes
                boosted = attention.spreading_activation(activation_text, n=3)
                if boosted:
                    # Also submit the top recalled episode to attention
                    # (what we remember should influence what we attend to)
                    attention.submit(
                        f"Episodic recall: {top_episodes[0]['task'][:100]} ({top_episodes[0]['outcome']})",
                        source="episodic_recall",
                        importance=0.6,
                        relevance=0.7,
                        boost=0.1,
                    )
            except Exception:
                pass  # Attention module unavailable — degrade gracefully

        return top_episodes

    def conflict_resolution(self, candidates, goal_context=None):
        """ACT-R conflict resolution for competing production candidates.

        When multiple episodes/procedures could apply, ACT-R selects
        via expected utility: U(i) = P(i)*G - C(i) + noise
          P(i) = probability of success (from past outcomes)
          G = goal value (from context)
          C(i) = expected cost (from past duration)
          noise = stochastic for exploration

        Args:
            candidates: List of episode/procedure dicts with 'outcome', 'activation', 'duration_s'
            goal_context: Optional goal string for relevance scoring

        Returns:
            Ranked list of candidates with 'utility' field added
        """
        import random

        if not candidates:
            return []

        # Default goal value
        G = 1.0

        # Boost goal value if context provided and aligns
        if goal_context:
            try:
                from clarvis.memory.soar import soar
                alignment = soar.align_task(goal_context)
                if alignment.get("aligned"):
                    G = 1.0 + alignment.get("boost", 0)
            except Exception:
                pass

        for c in candidates:
            # P(i): probability of success based on outcome history
            if c.get("outcome") == "success":
                p_success = 0.8
            elif c.get("outcome") == "failure":
                p_success = 0.2
            else:
                p_success = 0.5

            # C(i): cost proportional to duration (normalized to [0, 1])
            duration = c.get("duration_s", 60)
            cost = min(1.0, duration / 600.0)  # 600s = max expected duration

            # Activation bonus from ACT-R base-level learning
            activation_bonus = max(0, c.get("activation", 0)) * 0.1

            # Stochastic noise for exploration (ACT-R uses logistic noise)
            noise = random.gauss(0, 0.05)

            # Expected utility
            utility = p_success * G - cost + activation_bonus + noise
            c["utility"] = round(utility, 4)

        # Sort by utility (highest first)
        candidates.sort(key=lambda c: c.get("utility", 0), reverse=True)
        return candidates

    def recall_failures(self, n=5):
        """Recall recent failure episodes (high learning value).
        Includes both hard failures and soft failures."""
        failures = [e for e in self.episodes if e["outcome"] in ("failure", "soft_failure", "timeout")]
        self._decay_activations()
        failures.sort(key=lambda e: e["activation"], reverse=True)
        return failures[:n]

    def get_stats(self):
        """Get episodic memory statistics."""
        if not self.episodes:
            return {"total": 0}

        self._decay_activations()

        outcomes = {}
        for ep in self.episodes:
            outcomes[ep["outcome"]] = outcomes.get(ep["outcome"], 0) + 1

        # Failure type distribution (first-class field + legacy tag fallback)
        failure_types = {}
        for ep in self.episodes:
            ft = self._get_failure_type(ep)
            if ft:
                failure_types[ft] = failure_types.get(ft, 0) + 1

        activations = [e.get("activation", 0.0) for e in self.episodes]
        avg_valence = sum(e["valence"] for e in self.episodes) / len(self.episodes)
        avg_activation = sum(activations) / len(activations)

        # Decay diagnostics: how many episodes are effectively forgotten?
        forgotten = sum(1 for a in activations if a < -4.0)
        strong = sum(1 for a in activations if a > -1.0)

        return {
            "total": len(self.episodes),
            "outcomes": outcomes,
            "failure_types": failure_types,
            "avg_valence": round(avg_valence, 3),
            "avg_activation": round(avg_activation, 3),
            "activation_min": round(min(activations), 3),
            "activation_max": round(max(activations), 3),
            "strong_memories": strong,
            "forgotten_memories": forgotten,
            "decay_model": "power-law (d=c*lag^(-1/gamma), c=0.5, gamma=1.6)",
            "oldest": self.episodes[0]["timestamp"][:10],
            "newest": self.episodes[-1]["timestamp"][:10]
        }

    @staticmethod
    def _get_failure_type(episode):
        """Extract failure type from episode (first-class field or legacy tag).

        Returns failure_type string or None for successful episodes.
        """
        # First-class field (new episodes)
        ft = episode.get("failure_type")
        if ft:
            return ft
        # Legacy: extract from tags list (e.g. "error_type:timeout")
        for tag in episode.get("tags", []):
            if isinstance(tag, str) and tag.startswith("error_type:"):
                return tag.split(":", 1)[1]
        # Infer from outcome and error message for old episodes without tags
        outcome = episode.get("outcome", "")
        if outcome == "timeout":
            return "timeout"
        if outcome in ("failure", "soft_failure"):
            # Auto-detect system/infrastructure failures from error message
            error = (episode.get("error") or "").lower()
            if any(sig in error for sig in (
                "401", "authentication_error", "oauth token",
                "importerror", "modulenotfounderror",
                "nested sessions", "cannot be launched inside",
                "permission denied", "disk quota", "no space left",
            )):
                return "system"
            return "action"  # default for untagged failures
        return None

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
        """ACT-R base-level activation with power-law decay.

        Standard ACT-R: A(i) = ln(sum(t_j^(-d))) with fixed d=0.5
        Power-law extension: d_j = c * lag_j^(-1/gamma)

        The decay rate d itself follows a power law of the lag between
        successive retrievals. This captures the spacing effect:
        - Spaced repetitions → lower d → slower forgetting
        - Massed repetitions → higher d → faster forgetting
        - gamma controls how strongly spacing affects decay (higher = stronger)

        Reference: Pavlik & Anderson (2005), "Practice and Forgetting Effects
        on Vocabulary Memory: An Activation-Based Model"
        """
        access_times = episode.get("access_times", [])
        if not access_times:
            return 0.0

        c = 0.5       # base decay scaling factor (calibrated for hour-scale lags)
        gamma = 1.6   # spacing effect strength (ACT-R typical: 1.0-2.0)
        d_min = 0.1    # floor to prevent infinite memory
        d_max = 0.9    # ceiling to prevent instant forgetting
        now = datetime.now(timezone.utc).timestamp()

        sorted_times = sorted(access_times)
        total = 0.0
        for j, t in enumerate(sorted_times):
            age = max(1.0, now - t)

            # Compute inter-retrieval lag in hours for stable power-law range
            if j == 0:
                lag_hours = age / 3600.0
            else:
                lag_hours = max(1.0 / 60.0, (t - sorted_times[j - 1]) / 3600.0)

            # Power-law decay: d = c * lag_hours^(-1/gamma)
            # Longer lags between retrievals → lower d → slower forgetting
            d_j = c * (lag_hours ** (-1.0 / gamma))
            d_j = max(d_min, min(d_max, d_j))

            total += age ** (-d_j)

        return math.log(max(1e-10, total))

    def _decay_activations(self):
        """Recompute all activations (ACT-R decay).

        Rate-limited to once per 60 seconds to avoid redundant O(N) recomputation
        when multiple callers (recall_similar, recall_failures, get_stats) invoke
        this in quick succession.
        """
        now = time.monotonic()
        if hasattr(self, '_last_decay_time') and (now - self._last_decay_time) < 60:
            return  # Already recomputed recently
        for ep in self.episodes:
            ep["activation"] = self._compute_activation(ep)
        self._last_decay_time = now

    # Domain keywords for synthesis classification
    _DOMAIN_KEYWORDS = {
        "memory_retrieval": ["retrieval", "recall", "search", "benchmark", "hit rate", "precision"],
        "memory_system":    ["brain", "episodic", "procedural", "working_memory", "smart_recall"],
        "automation":       ["cron", "task_selector", "scheduler", "autonomous", "cron_autonomous"],
        "goal_tracking":    ["goal", "tracker", "progress", "goal-tracker"],
        "consciousness":    ["consciousness", "phi", "awareness", "consciousness_metrics"],
        "attention":        ["attention", "spotlight", "salience", "gwt"],
        "infrastructure":   ["wire", "wiring", "import", "module", "cross-collection", "cross_link"],
    }

    def _synth_counts(self):
        """Compute outcome counts, action verbs, domain outcomes, error types."""
        outcome_counts: dict = {}
        success_actions: dict = {}
        failure_actions: dict = {}
        domain_outcomes: dict = {}
        error_types: dict = {}

        for ep in self.episodes:
            o = ep["outcome"]
            outcome_counts[o] = outcome_counts.get(o, 0) + 1

            # Action verb extraction
            _task = ep.get("task") or ""
            words = _task.split()
            verb = words[0].lower().strip("[]()") if words else ""
            if verb:
                bucket = success_actions if o == "success" else failure_actions
                bucket[verb] = bucket.get(verb, 0) + 1

            # Domain classification
            task_lower = _task.lower()
            matched = [d for d, kws in self._DOMAIN_KEYWORDS.items()
                       if any(kw in task_lower for kw in kws)]
            if not matched:
                matched = ["general"]
            for domain in matched:
                if domain not in domain_outcomes:
                    domain_outcomes[domain] = {"success": 0, "failure": 0, "timeout": 0, "soft_failure": 0}
                dom_bucket = o if o in domain_outcomes[domain] else "failure"
                domain_outcomes[domain][dom_bucket] += 1

            # Error classification
            if ep.get("error"):
                err = ep["error"].lower()
                if "importerror" in err or "modulenotfounderror" in err or "no module" in err:
                    error_types["module_import"] = error_types.get("module_import", 0) + 1
                elif "attributeerror" in err:
                    error_types["attribute"] = error_types.get("attribute", 0) + 1
                elif "timeout" in err:
                    error_types["timeout_error"] = error_types.get("timeout_error", 0) + 1
                else:
                    error_types["other"] = error_types.get("other", 0) + 1

        real_episodes = [ep for ep in self.episodes if ep["outcome"] != "soft_failure"]
        real_total = len(real_episodes)
        success_count = outcome_counts.get("success", 0)
        success_rate = success_count / real_total if real_total else 0.0

        return {
            "outcome_counts": outcome_counts,
            "success_actions": success_actions,
            "failure_actions": failure_actions,
            "domain_outcomes": domain_outcomes,
            "error_types": error_types,
            "real_total": real_total,
            "success_count": success_count,
            "success_rate": success_rate,
        }

    def _synth_goals(self, counts):
        """Generate goals from synthesis counts. Returns (goals_generated, tasks_injected, skip_reason)."""
        # GUARDRAIL: Check existing goal count
        try:
            existing_goals = brain.get_goals()
            existing_goal_count = len(existing_goals)
            existing_goal_names = {g.get("metadata", {}).get("goal", g.get("id", "")).lower() for g in existing_goals}
        except Exception:
            existing_goal_count = 0
            existing_goal_names = set()
            existing_goals = []

        if existing_goal_count >= 20:
            return [], [], f"goal_cap_reached ({existing_goal_count} goals exist)"

        goals = self._synth_create_goals(counts, existing_goals, existing_goal_names)
        tasks_injected = self._synth_inject_queue(goals)
        return goals, tasks_injected, None

    def _synth_create_goals(self, counts, existing_goals, existing_goal_names):
        """Create brain goals from synthesis pattern analysis."""
        now = datetime.now(timezone.utc)
        goals_generated: list = []
        domain_outcomes = counts["domain_outcomes"]

        # Goal: fix domains with >30% REAL failure rate
        for domain, dc in domain_outcomes.items():
            d_real_total = dc.get("success", 0) + dc.get("failure", 0) + dc.get("timeout", 0)
            d_hard_failures = dc.get("failure", 0) + dc.get("timeout", 0)
            d_soft_failures = dc.get("soft_failure", 0)
            if d_hard_failures > 0 and d_real_total > 0:
                fail_rate = d_hard_failures / d_real_total
                if fail_rate > 0.3:
                    goal_name = f"Reduce {domain.replace('_', ' ')} failure rate"
                    if goal_name.lower() in existing_goal_names:
                        matching = [g for g in existing_goals if g.get("metadata", {}).get("goal", "").lower() == goal_name.lower()]
                        if matching and matching[0].get("metadata", {}).get("progress", 0) > 0:
                            continue
                    brain.set_goal(goal_name, 0, subtasks={
                        "source": "episodic_synthesis", "domain": domain,
                        "fail_rate": round(fail_rate, 2), "episode_count": d_real_total,
                        "soft_failures_noted": d_soft_failures,
                        "description": (f"Failure rate {fail_rate:.0%} in {domain.replace('_', ' ')} "
                                        f"({d_hard_failures}/{d_real_total} real, +{d_soft_failures} soft)."),
                        "generated_at": now.isoformat(),
                    })
                    goals_generated.append(goal_name)

        # Goal: fix module import errors
        error_types = counts["error_types"]
        if error_types.get("module_import", 0) > 0:
            goal_name = "Fix module import reliability"
            brain.set_goal(goal_name, 0, subtasks={
                "source": "episodic_synthesis",
                "description": f"ImportError in {error_types['module_import']} episode(s).",
                "occurrences": error_types["module_import"],
                "generated_at": now.isoformat(),
            })
            goals_generated.append(goal_name)

        # Goal: strengthen dominant success domains
        high_success = {d: c["success"] for d, c in domain_outcomes.items() if c.get("success", 0) >= 2}
        if high_success:
            best = max(high_success, key=lambda d: high_success[d])
            goal_name = f"Deepen {best.replace('_', ' ')} capabilities"
            brain.set_goal(goal_name, 25, subtasks={
                "source": "episodic_synthesis",
                "description": f"Strong in {best.replace('_', ' ')} ({high_success[best]} successes).",
                "success_count": high_success[best], "generated_at": now.isoformat(),
            })
            goals_generated.append(goal_name)

        # Goal: improve success rate if below 80%
        success_rate, real_total = counts["success_rate"], counts["real_total"]
        if success_rate < 0.8 and real_total >= 3:
            goal_name = "Improve task success rate above 80%"
            brain.set_goal(goal_name, int(success_rate * 100), subtasks={
                "source": "episodic_synthesis",
                "description": f"Rate {success_rate:.0%} ({counts['success_count']}/{real_total}).",
                "current_rate": round(success_rate, 2), "generated_at": now.isoformat(),
            })
            goals_generated.append(goal_name)

        return goals_generated

    @staticmethod
    def _synth_inject_queue(goals_generated):
        """Inject top goals into QUEUE.md as actionable tasks."""
        if not goals_generated:
            return []
        try:
            from queue_writer import add_tasks
            actionable = [f"Investigate and fix: {g}" for g in goals_generated[:2]]
            return add_tasks(actionable, priority="P1", source="episodic_synthesis")
        except Exception as e:
            import sys as _sys
            print(f"[EPISODIC SYNTHESIZE] queue_writer injection failed: {e}", file=_sys.stderr)
            try:
                from brain import get_brain
                b = get_brain()
                for gn in goals_generated[:2]:
                    b.store(f"[SYNTHESIS GOAL] {gn}", collection="clarvis-learnings",
                            importance=0.75, tags=["synthesis", "goal"], source="episodic_synthesis")
            except Exception:
                pass
        return []

    def synthesize(self):
        """Analyze all episodes for recurring patterns, generate goal entries.

        Returns a summary dict with patterns found and goals generated.
        """
        if not self.episodes:
            return {"error": "No episodes to analyze", "goals_generated": []}

        counts = self._synth_counts()

        goals_generated, tasks_injected, skip_reason = self._synth_goals(counts)
        if skip_reason:
            return {
                "total_episodes": len(self.episodes),
                "real_episodes": counts["real_total"],
                "success_rate": round(counts["success_rate"], 2),
                "outcome_counts": counts["outcome_counts"],
                "goals_generated": [],
                "skipped_reason": skip_reason,
            }

        top_success = sorted(counts["success_actions"].items(), key=lambda x: x[1], reverse=True)[:5]
        top_failure = sorted(counts["failure_actions"].items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "total_episodes": len(self.episodes),
            "real_episodes": counts["real_total"],
            "soft_failure_episodes": counts["outcome_counts"].get("soft_failure", 0),
            "outcome_counts": counts["outcome_counts"],
            "success_rate": round(counts["success_rate"], 2),
            "top_success_actions": top_success,
            "top_failure_actions": top_failure,
            "domain_outcomes": counts["domain_outcomes"],
            "error_types": counts["error_types"],
            "goals_generated": goals_generated,
            "goals_count": len(goals_generated),
            "tasks_injected": tasks_injected,
        }


# Singleton
episodic = EpisodicMemory()

# CLI interface
def _cli_basic(cmd):
    """Handle basic CLI subcommands (encode, recall, failures, stats, failure-types)."""
    if cmd == "encode":
        if len(sys.argv) < 6:
            print("Usage: encode <task> <section> <salience> <outcome> [duration] [error]")
            sys.exit(1)
        ep = episodic.encode(
            task_text=sys.argv[2], section=sys.argv[3],
            salience=sys.argv[4], outcome=sys.argv[5],
            duration_s=int(sys.argv[6]) if len(sys.argv) > 6 else 0,
            error_msg=sys.argv[7] if len(sys.argv) > 7 else None
        )
        print(json.dumps(ep, indent=2))
        return True

    if cmd == "recall":
        query = sys.argv[2] if len(sys.argv) > 2 else ""
        for ep in episodic.recall_similar(query):
            print(f"  [{ep['outcome']}] (act={ep['activation']:.2f}) {ep['task'][:80]}")
        return True

    if cmd == "failures":
        for ep in episodic.recall_failures():
            print(f"  (act={ep['activation']:.2f}, val={ep['valence']:.2f}) {ep['task'][:70]}")
            if ep.get("error"):
                print(f"    Error: {ep['error'][:100]}")
        return True

    if cmd == "stats":
        print(json.dumps(episodic.get_stats(), indent=2))
        return True

    if cmd == "failure-types":
        ft = episodic.get_stats().get("failure_types", {})
        if not ft:
            print("No failure types recorded.")
        else:
            print("Failure type distribution:")
            total_failures = sum(ft.values())
            for ftype, count in sorted(ft.items(), key=lambda x: x[1], reverse=True):
                pct = count / total_failures * 100
                print(f"  {ftype:16s}  {count:3d}  ({pct:4.1f}%)  {'█' * int(pct / 5)}")
            print(f"\nTotal failures: {total_failures}")
            weakest = max(ft, key=ft.get)
            print(f"Weakest mode: {weakest} ({ft[weakest]} episodes)")
        return True

    return False


def _cli_synthesize():
    """Handle the synthesize CLI subcommand with formatted output."""
    result = episodic.synthesize()
    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)

    print("=" * 60)
    print("EPISODIC MEMORY SYNTHESIS REPORT")
    print("=" * 60)
    print(f"\nEpisodes analyzed : {result['total_episodes']}")
    print("Outcome breakdown :")
    for outcome, count in sorted(result["outcome_counts"].items()):
        print(f"  {outcome:10s} {count}")
    print(f"Success rate      : {result['success_rate']:.0%}")

    print("\nTop action verbs (successes):")
    for verb, count in result["top_success_actions"]:
        print(f"  {count:2d}x  {verb}")

    if result["top_failure_actions"]:
        print("\nTop action verbs (failures):")
        for verb, count in result["top_failure_actions"]:
            print(f"  {count:2d}x  {verb}")

    print("\nDomain outcomes (real | soft):")
    for domain, counts in sorted(result["domain_outcomes"].items()):
        s = counts.get("success", 0)
        f = counts.get("failure", 0) + counts.get("timeout", 0)
        sf = counts.get("soft_failure", 0)
        soft_note = f" +{sf}soft" if sf else ""
        print(f"  {domain:22s}  {'█' * s + '░' * f + '·' * sf}  ({s}✓ {f}✗{soft_note})")

    if result["error_types"]:
        print("\nError type breakdown:")
        for etype, count in result["error_types"].items():
            print(f"  {count:2d}x  {etype}")

    print(f"\nGoals generated ({result['goals_count']}):")
    if result["goals_generated"]:
        for goal in result["goals_generated"]:
            print(f"  → {goal}")
    else:
        print("  (none — all patterns already well-handled)")
    print("\n[Full JSON]")
    print(json.dumps(result, indent=2))


def _cli_causal_link(cmd):
    """Handle link/causes/effects CLI subcommands."""
    if cmd == "link":
        if len(sys.argv) < 5:
            print("Usage: link <from_id> <to_id> <relationship> [confidence]")
            print(f"  relationships: {list(CAUSAL_RELATIONSHIPS.keys())}")
            sys.exit(1)
        confidence = float(sys.argv[5]) if len(sys.argv) > 5 else 1.0
        result = episodic.causal_link(sys.argv[2], sys.argv[3], sys.argv[4], confidence)
        if result:
            print(f"Linked: {result['from']} --[{result['relationship']}]--> {result['to']} "
                  f"(conf={result['confidence']})")
        else:
            print("Link creation failed (invalid relationship or self-loop)")
        return True

    if cmd == "causes":
        if len(sys.argv) < 3:
            print("Usage: causes <episode_id> [relationship]")
            sys.exit(1)
        rel = sys.argv[3] if len(sys.argv) > 3 else None
        results = episodic.causes_of(sys.argv[2], relationship=rel)
        if not results:
            print(f"No causes found for {sys.argv[2]}")
        for link, ep in results:
            task = ep["task"][:60] if ep else "?"
            print(f"  {link['from']} --[{link['relationship']}]--> {sys.argv[2]}  "
                  f"(conf={link['confidence']})  {task}")
        return True

    if cmd == "effects":
        if len(sys.argv) < 3:
            print("Usage: effects <episode_id> [relationship]")
            sys.exit(1)
        rel = sys.argv[3] if len(sys.argv) > 3 else None
        results = episodic.effects_of(sys.argv[2], relationship=rel)
        if not results:
            print(f"No effects found for {sys.argv[2]}")
        for link, ep in results:
            task = ep["task"][:60] if ep else "?"
            print(f"  {sys.argv[2]} --[{link['relationship']}]--> {link['to']}  "
                  f"(conf={link['confidence']})  {task}")
        return True

    return False


def _cli_causal_graph(cmd):
    """Handle chain/roots/causal-stats/backfill CLI subcommands."""
    if cmd == "chain":
        if len(sys.argv) < 3:
            print("Usage: chain <episode_id> [backward|forward] [max_depth]")
            sys.exit(1)
        direction = sys.argv[3] if len(sys.argv) > 3 else "backward"
        max_depth = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        chain = episodic.causal_chain(sys.argv[2], direction=direction, max_depth=max_depth)
        if not chain:
            print(f"No causal chain found ({direction}) from {sys.argv[2]}")
        else:
            print(f"Causal chain ({direction}) from {sys.argv[2]}:")
            for depth, link, ep in chain:
                indent = "  " * depth
                task = ep["task"][:55] if ep else "?"
                outcome = ep["outcome"] if ep else "?"
                node = link["from"] if direction == "backward" else link["to"]
                print(f"  {indent}depth={depth} [{link['relationship']}] "
                      f"{node} [{outcome}] {task}")
        return True

    if cmd == "roots":
        if len(sys.argv) < 3:
            print("Usage: roots <episode_id>")
            sys.exit(1)
        roots = episodic.root_causes(sys.argv[2])
        if not roots:
            print(f"No root causes found for {sys.argv[2]}")
        else:
            print(f"Root causes of {sys.argv[2]}:")
            for ep in roots:
                print(f"  {ep['id']} [{ep['outcome']}] {ep['task'][:70]}")
        return True

    if cmd == "causal-stats":
        print(json.dumps(episodic.causal_graph_stats(), indent=2, default=str))
        return True

    if cmd == "backfill":
        count = episodic.backfill_causal_links()
        print(f"Backfilled {count} causal links across {len(episodic.episodes)} episodes")
        print(json.dumps(episodic.causal_graph_stats(), indent=2, default=str))
        return True

    return False


def main():
    if len(sys.argv) < 2:
        print("Usage: episodic_memory.py <encode|recall|failures|stats|failure-types"
              "|synthesize|link|causes|effects|chain|roots|causal-stats|backfill>")
        sys.exit(1)

    cmd = sys.argv[1]

    if _cli_basic(cmd):
        return
    if cmd == "synthesize":
        _cli_synthesize()
        return
    if _cli_causal_link(cmd):
        return
    if _cli_causal_graph(cmd):
        return

    print(f"Unknown command: {cmd}")
    sys.exit(1)


if __name__ == "__main__":
    main()
