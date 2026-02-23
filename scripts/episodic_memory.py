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
"""

import json
import math
import sys
import time
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

        # Create somatic markers (emotional tags for decision biasing)
        try:
            from somatic_markers import somatic
            somatic.tag_episode(episode)
        except Exception:
            pass  # Don't let somatic tagging break episode encoding

        return episode

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
                from attention import attention
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

        activations = [e.get("activation", 0.0) for e in self.episodes]
        avg_valence = sum(e["valence"] for e in self.episodes) / len(self.episodes)
        avg_activation = sum(activations) / len(activations)

        # Decay diagnostics: how many episodes are effectively forgotten?
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
            "decay_model": "power-law (d=c*lag^(-1/gamma), c=0.5, gamma=1.6)",
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

    def synthesize(self):
        """Analyze all episodes for recurring patterns, generate goal entries.

        Examines outcomes, action verbs, error types, and domain clusters to
        produce actionable goal items stored in the clarvis-goals collection.

        Returns a summary dict with patterns found and goals generated.
        """
        if not self.episodes:
            return {"error": "No episodes to analyze", "goals_generated": []}

        # 1. Count outcomes
        outcome_counts: dict = {}
        for ep in self.episodes:
            o = ep["outcome"]
            outcome_counts[o] = outcome_counts.get(o, 0) + 1

        total = len(self.episodes)
        success_count = outcome_counts.get("success", 0)
        failure_count = (outcome_counts.get("failure", 0) +
                         outcome_counts.get("timeout", 0) +
                         outcome_counts.get("soft_failure", 0))
        success_rate = success_count / total if total else 0.0

        # 2. Extract first-word action verbs (typically the imperative verb)
        success_actions: dict = {}
        failure_actions: dict = {}
        for ep in self.episodes:
            words = ep["task"].split()
            verb = words[0].lower().strip("[]()") if words else ""
            if not verb:
                continue
            if ep["outcome"] == "success":
                success_actions[verb] = success_actions.get(verb, 0) + 1
            else:
                failure_actions[verb] = failure_actions.get(verb, 0) + 1

        # 3. Domain classification via keyword matching
        DOMAIN_KEYWORDS = {
            "memory_retrieval": ["retrieval", "recall", "search", "benchmark", "hit rate", "precision"],
            "memory_system":    ["brain", "episodic", "procedural", "working_memory", "smart_recall"],
            "automation":       ["cron", "task_selector", "scheduler", "autonomous", "cron_autonomous"],
            "goal_tracking":    ["goal", "tracker", "progress", "goal-tracker"],
            "consciousness":    ["consciousness", "phi", "awareness", "consciousness_metrics"],
            "attention":        ["attention", "spotlight", "salience", "gwt"],
            "infrastructure":   ["wire", "wiring", "import", "module", "cross-collection", "cross_link"],
        }

        domain_outcomes: dict = {}
        for ep in self.episodes:
            task_lower = ep["task"].lower()
            matched = [d for d, kws in DOMAIN_KEYWORDS.items() if any(kw in task_lower for kw in kws)]
            if not matched:
                matched = ["general"]
            for domain in matched:
                if domain not in domain_outcomes:
                    domain_outcomes[domain] = {"success": 0, "failure": 0, "timeout": 0, "soft_failure": 0}
                outcome = ep["outcome"]
                bucket = outcome if outcome in domain_outcomes[domain] else "failure"
                domain_outcomes[domain][bucket] += 1

        # 4. Classify error types across failures
        error_types: dict = {}
        for ep in self.episodes:
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

        # 5. Generate goals based on findings
        now = datetime.now(timezone.utc)
        goals_generated: list = []

        # Goal: fix domains with >30% failure rate
        for domain, counts in domain_outcomes.items():
            d_total = sum(counts.values())
            d_failures = counts.get("failure", 0) + counts.get("timeout", 0) + counts.get("soft_failure", 0)
            if d_failures > 0 and d_total > 0:
                fail_rate = d_failures / d_total
                if fail_rate > 0.3:
                    goal_name = f"Reduce {domain.replace('_', ' ')} failure rate"
                    brain.set_goal(goal_name, 0, subtasks={
                        "source": "episodic_synthesis",
                        "domain": domain,
                        "fail_rate": round(fail_rate, 2),
                        "episode_count": d_total,
                        "description": (
                            f"Failure rate {fail_rate:.0%} detected in {domain.replace('_', ' ')} tasks "
                            f"({d_failures}/{d_total} episodes). Investigate and fix root causes."
                        ),
                        "generated_at": now.isoformat(),
                    })
                    goals_generated.append(goal_name)

        # Goal: fix module import errors if any
        if error_types.get("module_import", 0) > 0:
            goal_name = "Fix module import reliability"
            brain.set_goal(goal_name, 0, subtasks={
                "source": "episodic_synthesis",
                "description": (
                    f"ImportError/ModuleNotFoundError appeared in {error_types['module_import']} episode(s). "
                    "Audit sys.path, __init__.py files, and missing dependencies."
                ),
                "occurrences": error_types["module_import"],
                "generated_at": now.isoformat(),
            })
            goals_generated.append(goal_name)

        # Goal: strengthen dominant success domains
        high_success_domains = {
            d: c["success"] for d, c in domain_outcomes.items() if c.get("success", 0) >= 2
        }
        if high_success_domains:
            best = max(high_success_domains, key=lambda d: high_success_domains[d])
            goal_name = f"Deepen {best.replace('_', ' ')} capabilities"
            brain.set_goal(goal_name, 25, subtasks={
                "source": "episodic_synthesis",
                "description": (
                    f"Strong track record in {best.replace('_', ' ')} "
                    f"({high_success_domains[best]} successes). "
                    "Continue building depth: add tests, metrics, and stress cases."
                ),
                "success_count": high_success_domains[best],
                "generated_at": now.isoformat(),
            })
            goals_generated.append(goal_name)

        # Goal: improve overall success rate if below 80%
        if success_rate < 0.8 and total >= 3:
            goal_name = "Improve task success rate above 80%"
            brain.set_goal(goal_name, int(success_rate * 100), subtasks={
                "source": "episodic_synthesis",
                "description": (
                    f"Current success rate is {success_rate:.0%} ({success_count}/{total} episodes). "
                    "Review failure patterns and add pre-flight checks."
                ),
                "current_rate": round(success_rate, 2),
                "generated_at": now.isoformat(),
            })
            goals_generated.append(goal_name)

        top_success = sorted(success_actions.items(), key=lambda x: x[1], reverse=True)[:5]
        top_failure = sorted(failure_actions.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "total_episodes": total,
            "outcome_counts": outcome_counts,
            "success_rate": round(success_rate, 2),
            "top_success_actions": top_success,
            "top_failure_actions": top_failure,
            "domain_outcomes": domain_outcomes,
            "error_types": error_types,
            "goals_generated": goals_generated,
            "goals_count": len(goals_generated),
        }


# Singleton
episodic = EpisodicMemory()

# CLI interface
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: episodic_memory.py <encode|recall|failures|stats|synthesize>")
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

    elif cmd == "synthesize":
        result = episodic.synthesize()

        if "error" in result:
            print(f"Error: {result['error']}")
            sys.exit(1)

        print("=" * 60)
        print("EPISODIC MEMORY SYNTHESIS REPORT")
        print("=" * 60)
        print(f"\nEpisodes analyzed : {result['total_episodes']}")
        print(f"Outcome breakdown :")
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

        print("\nDomain outcomes:")
        for domain, counts in sorted(result["domain_outcomes"].items()):
            s = counts.get("success", 0)
            f = counts.get("failure", 0) + counts.get("timeout", 0) + counts.get("soft_failure", 0)
            bar = "█" * s + "░" * f
            print(f"  {domain:22s}  {bar}  ({s}✓ {f}✗)")

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

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
