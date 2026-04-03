#!/usr/bin/env python3
"""
Meta-Learning System — Learn HOW to learn better from experience.

Instead of just learning task-specific knowledge, this system analyzes
the learning process itself and optimizes learning strategies.

Core idea: Analyze episodic history, capability trajectories, and procedural
memory to discover which learning strategies work best in which contexts,
then adjust future learning behavior accordingly.

5 Meta-Learning Strategies:
  1. Strategy Effectiveness — which task approaches (build, fix, wire, research)
     have the best success rates? Bias future task selection toward high-success
     strategies and flag struggling ones for improvement.
  2. Learning Speed — for each capability domain, how quickly do scores improve
     after focused effort? Identify which domains respond best to investment.
  3. Failure Pattern Mining — cluster recurring failure signatures across episodes
     and generate "anti-patterns" (things to avoid). Store as negative procedures.
  4. Retrieval Effectiveness — analyze which memory retrieval patterns (collections,
     query styles, contexts) yield the most useful results. Tune retrieval params.
  5. Consolidation Timing — analyze when knowledge consolidation is most effective
     (immediately, daily, weekly) based on retention of learned insights.

Usage:
    python3 meta_learning.py analyze    # Run full meta-learning analysis
    python3 meta_learning.py strategies # Show strategy effectiveness rankings
    python3 meta_learning.py speed      # Show learning speed by domain
    python3 meta_learning.py failures   # Show clustered failure anti-patterns
    python3 meta_learning.py recommend  # Get meta-learning recommendations
    python3 meta_learning.py stats      # Show meta-learning statistics
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brain import brain, AUTONOMOUS_LEARNING

DATA_DIR = Path("/home/agent/.openclaw/workspace/data/meta_learning")
DATA_DIR.mkdir(parents=True, exist_ok=True)

ANALYSIS_FILE = DATA_DIR / "analysis.json"
HISTORY_FILE = DATA_DIR / "history.jsonl"
RECOMMENDATIONS_FILE = DATA_DIR / "recommendations.json"
INJECTION_HISTORY_FILE = DATA_DIR / "injection_history.json"
MAX_INJECTIONS_PER_CYCLE = 2

# Paths to data sources
EPISODES_FILE = Path("/home/agent/.openclaw/workspace/data/episodes.json")
CAPABILITY_HISTORY_FILE = Path("/home/agent/.openclaw/workspace/data/capability_history.json")
HEBBIAN_ACCESS_LOG = Path("/home/agent/.openclaw/workspace/data/hebbian/access_log.jsonl")
AUTONOMOUS_LOG = Path("/home/agent/.openclaw/workspace/memory/cron/autonomous.log")
REASONING_CHAINS_DIR = Path("/home/agent/.openclaw/workspace/data/reasoning_chains")


class MetaLearner:
    """Learns about the learning process itself."""

    def __init__(self):
        self._analysis = self._load_analysis()

    def _load_analysis(self):
        if ANALYSIS_FILE.exists():
            try:
                with open(ANALYSIS_FILE) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {"last_run": None, "strategies": {}, "learning_speeds": {},
                "failure_clusters": {}, "retrieval_patterns": {},
                "recommendations": [], "run_count": 0}

    def _save_analysis(self):
        with open(ANALYSIS_FILE, "w") as f:
            json.dump(self._analysis, f, indent=2)

    def _log_run(self, result):
        with open(HISTORY_FILE, "a") as f:
            f.write(json.dumps(result) + "\n")

    # =================================================================
    # 1. STRATEGY EFFECTIVENESS
    # =================================================================

    def analyze_strategy_effectiveness(self):
        """Analyze which task strategies (action verbs/approaches) work best.

        Mines episodes for action verbs (build, fix, wire, research, implement)
        and computes success rate, avg duration, and trend for each.

        Returns:
            Dict mapping strategy -> {success_rate, count, avg_duration, trend}
        """
        episodes = self._load_episodes()
        if not episodes:
            return {}

        # Classify each episode by its primary strategy (first verb)
        strategy_stats = defaultdict(lambda: {
            "successes": 0, "failures": 0, "total": 0,
            "durations": [], "recent_outcomes": []
        })

        # Strategy verb extraction
        STRATEGY_VERBS = {
            "build": ["build", "create", "implement", "add", "design"],
            "fix": ["fix", "repair", "debug", "resolve", "patch"],
            "wire": ["wire", "connect", "integrate", "hook", "link"],
            "improve": ["improve", "boost", "enhance", "optimize", "strengthen"],
            "research": ["research", "analyze", "study", "investigate", "audit"],
            "refactor": ["refactor", "clean", "consolidate", "reorganize", "restructure"],
        }

        for ep in episodes:
            task_lower = (ep.get("task") or "").lower()
            words = task_lower.split()
            first_verb = words[0].strip("[]()") if words else ""

            # Map to strategy category
            strategy = "other"
            for cat, verbs in STRATEGY_VERBS.items():
                if first_verb in verbs or any(v in task_lower[:60] for v in verbs):
                    strategy = cat
                    break

            stats = strategy_stats[strategy]
            stats["total"] += 1
            outcome = ep.get("outcome", "")
            if outcome == "success":
                stats["successes"] += 1
            else:
                stats["failures"] += 1

            dur = ep.get("duration_s", 0)
            if dur > 0:
                stats["durations"].append(dur)

            # Track recent outcomes for trend (last 10 per strategy)
            stats["recent_outcomes"].append(1 if outcome == "success" else 0)
            stats["recent_outcomes"] = stats["recent_outcomes"][-10:]

        # Compute final strategy scores
        strategies = {}
        for name, stats in strategy_stats.items():
            if stats["total"] < 1:
                continue
            success_rate = stats["successes"] / stats["total"]
            avg_duration = (sum(stats["durations"]) / len(stats["durations"])
                           if stats["durations"] else 0)

            # Trend: compare recent 5 vs earlier 5 outcomes
            recent = stats["recent_outcomes"]
            if len(recent) >= 6:
                early_rate = sum(recent[:len(recent)//2]) / max(1, len(recent)//2)
                late_rate = sum(recent[len(recent)//2:]) / max(1, len(recent) - len(recent)//2)
                trend = late_rate - early_rate  # positive = improving
            else:
                trend = 0.0

            strategies[name] = {
                "success_rate": round(success_rate, 3),
                "count": stats["total"],
                "avg_duration_s": round(avg_duration, 1),
                "trend": round(trend, 3),
                "efficiency": round(success_rate / max(1, avg_duration / 300), 3),
            }

        return strategies

    # =================================================================
    # 2. LEARNING SPEED BY DOMAIN
    # =================================================================

    def analyze_learning_speed(self):
        """Analyze how quickly each capability domain improves after investment.

        Correlates task completion (from episodes) with capability score changes
        (from capability_history) to find which domains learn fastest.

        Returns:
            Dict mapping domain -> {improvement_rate, responsiveness, plateau}
        """
        history = self._load_capability_history()
        if not history or len(history) < 2:
            return {}

        episodes = self._load_episodes()

        # Build domain -> list of (date, score) pairs
        domain_series = defaultdict(list)
        for snap in history:
            date = snap.get("date", "")
            scores = snap.get("scores", {})
            for domain, score in scores.items():
                domain_series[domain].append((date, score))

        # Count episodes per domain per day
        DOMAIN_KEYWORDS = {
            "memory_system": ["memory", "brain", "recall", "store", "retrieval", "smart_recall"],
            "autonomous_execution": ["cron", "autonomous", "task_selector", "heartbeat"],
            "code_generation": ["code", "script", "fix", "build", "implement", "create"],
            "self_reflection": ["reflect", "meta", "phi", "self", "awareness", "calibrat"],
            "reasoning_chains": ["reason", "chain", "think"],
            "learning_feedback": ["learn", "predict", "procedure", "feedback", "evolution"],
            "consciousness_metrics": ["consciousness", "phi", "attention", "spotlight", "gwt"],
        }

        domain_effort = defaultdict(lambda: defaultdict(int))
        for ep in episodes:
            task_lower = (ep.get("task") or "").lower()
            date = ep.get("timestamp", "")[:10]
            for domain, keywords in DOMAIN_KEYWORDS.items():
                if any(kw in task_lower for kw in keywords):
                    domain_effort[domain][date] += 1

        # Compute learning metrics per domain
        learning_speeds = {}
        for domain, series in domain_series.items():
            if len(series) < 2:
                continue

            # Sort by date
            series.sort(key=lambda x: x[0])
            scores = [s[1] for s in series]

            # Improvement rate: average daily delta
            deltas = [scores[i] - scores[i-1] for i in range(1, len(scores))]
            avg_delta = sum(deltas) / len(deltas) if deltas else 0

            # Responsiveness: correlation between effort and improvement
            # (higher = domain responds well to focused work)
            effort_dates = domain_effort.get(domain, {})
            responsive_days = 0
            total_effort_days = 0
            for i in range(1, len(series)):
                date = series[i][0]
                if effort_dates.get(date, 0) > 0:
                    total_effort_days += 1
                    if scores[i] > scores[i-1]:
                        responsive_days += 1

            responsiveness = (responsive_days / total_effort_days
                              if total_effort_days > 0 else 0.0)

            # Plateau detection: has recent improvement stalled?
            recent_scores = scores[-3:] if len(scores) >= 3 else scores
            score_range = max(recent_scores) - min(recent_scores)
            is_plateaued = score_range < 0.05 and len(recent_scores) >= 3

            # Current score for context
            current_score = scores[-1] if scores else 0

            learning_speeds[domain] = {
                "improvement_rate": round(avg_delta, 4),
                "responsiveness": round(responsiveness, 3),
                "plateaued": is_plateaued,
                "current_score": round(current_score, 3),
                "total_effort_days": total_effort_days,
                "data_points": len(series),
            }

        return learning_speeds

    # =================================================================
    # 3. FAILURE PATTERN MINING
    # =================================================================

    def mine_failure_patterns(self):
        """Cluster recurring failure patterns into anti-patterns.

        Groups failures by error type, task context, and timing to find
        systematic weaknesses that can be proactively avoided.

        Returns:
            Dict of anti-pattern clusters with descriptions and avoidance hints.
        """
        episodes = self._load_episodes()
        failures = [e for e in episodes
                    if e.get("outcome") in ("failure", "soft_failure", "timeout")]

        if not failures:
            return {}

        # Cluster by error signature
        error_clusters = defaultdict(list)
        for ep in failures:
            error = ep.get("error", "") or ""
            # Extract error class
            error_class = "unknown"
            if "ImportError" in error or "ModuleNotFoundError" in error:
                error_class = "import_error"
            elif "timeout" in error.lower() or ep.get("outcome") == "timeout":
                error_class = "timeout"
            elif "SyntaxError" in error:
                error_class = "syntax_error"
            elif "AttributeError" in error:
                error_class = "attribute_error"
            elif "KeyError" in error or "IndexError" in error:
                error_class = "data_access_error"
            elif "long_duration" in error.lower():
                error_class = "long_duration"
            elif "FileNotFoundError" in error:
                error_class = "file_not_found"
            elif error:
                error_class = "runtime_error"
            else:
                error_class = "soft_failure"

            error_clusters[error_class].append({
                "task": ep.get("task", "")[:100],
                "timestamp": ep.get("timestamp", "")[:10],
                "duration_s": ep.get("duration_s", 0),
                "section": ep.get("section", ""),
            })

        # Generate anti-patterns from clusters
        AVOIDANCE_HINTS = {
            "import_error": "Always verify imports exist before running. Use try/except ImportError with fallback.",
            "timeout": "Break large tasks into smaller sub-tasks. Set realistic timeouts. Check for infinite loops.",
            "syntax_error": "Run py_compile on new code before committing. Use AST validation.",
            "attribute_error": "Verify object types and available attributes. Check API docs for correct method names.",
            "data_access_error": "Validate data structures before accessing nested keys. Use .get() with defaults.",
            "long_duration": "Add progress checkpoints. Consider decomposing into parallel sub-tasks.",
            "file_not_found": "Check file existence before operations. Use absolute paths.",
            "runtime_error": "Add defensive error handling. Log intermediate state for debugging.",
            "soft_failure": "Review success criteria. Some soft failures may indicate unrealistic expectations.",
        }

        anti_patterns = {}
        for error_class, episodes_in_cluster in error_clusters.items():
            if len(episodes_in_cluster) < 1:
                continue

            # Find common task context words
            task_words = defaultdict(int)
            for ep in episodes_in_cluster:
                for word in (ep.get("task") or "").lower().split():
                    if len(word) > 3:
                        task_words[word] += 1
            common_context = sorted(task_words.items(), key=lambda x: x[1], reverse=True)[:5]

            anti_patterns[error_class] = {
                "count": len(episodes_in_cluster),
                "common_context": [w for w, c in common_context if c > 1],
                "avoidance_hint": AVOIDANCE_HINTS.get(error_class, "Investigate root cause."),
                "recent_examples": [e["task"] for e in episodes_in_cluster[-3:]],
                "avg_duration_s": round(
                    sum(e["duration_s"] for e in episodes_in_cluster) / len(episodes_in_cluster), 1
                ),
            }

        return anti_patterns

    # =================================================================
    # 4. RETRIEVAL EFFECTIVENESS
    # =================================================================

    def analyze_retrieval_effectiveness(self):
        """Analyze which retrieval patterns yield the most useful results.

        Examines Hebbian access logs and retrieval quality data to find
        optimal retrieval strategies (which callers, collections, query styles).

        Returns:
            Dict with retrieval pattern analysis.
        """
        patterns = {
            "caller_effectiveness": {},
            "collection_hotspots": defaultdict(int),
            "access_concentration": 0.0,
            "total_accesses": 0,
        }

        # Analyze Hebbian access log for caller effectiveness
        if HEBBIAN_ACCESS_LOG.exists():
            caller_stats = defaultdict(lambda: {"count": 0, "unique_memories": set()})
            total = 0

            try:
                with open(HEBBIAN_ACCESS_LOG) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            event = json.loads(line)
                            caller = event.get("caller", "unknown")
                            mem_id = event.get("memory_id", "")
                            collection = event.get("collection", "")

                            caller_stats[caller]["count"] += 1
                            caller_stats[caller]["unique_memories"].add(mem_id)
                            patterns["collection_hotspots"][collection] += 1
                            total += 1
                        except json.JSONDecodeError:
                            continue
            except OSError:
                pass

            patterns["total_accesses"] = total

            # Convert sets to counts and compute diversity ratio
            for caller, stats in caller_stats.items():
                count = stats["count"]
                unique = len(stats["unique_memories"])
                patterns["caller_effectiveness"][caller] = {
                    "total_accesses": count,
                    "unique_memories_accessed": unique,
                    "diversity_ratio": round(unique / max(1, count), 3),
                    # Higher diversity = exploring more memory space
                    # Lower diversity = repeatedly accessing same memories
                }

            # Access concentration: Gini coefficient of memory access
            if total > 0:
                access_counts = [s["count"] for s in caller_stats.values()]
                patterns["access_concentration"] = round(
                    self._gini_coefficient(access_counts), 3
                )

        # Analyze retrieval quality data if available
        rq_dir = Path("/home/agent/.openclaw/workspace/data/retrieval_quality")
        if rq_dir.exists():
            try:
                events_file = rq_dir / "events.jsonl"
                if events_file.exists():
                    useful = 0
                    not_useful = 0
                    with open(events_file) as f:
                        for line in f:
                            try:
                                event = json.loads(line.strip())
                                if event.get("useful") is True:
                                    useful += 1
                                elif event.get("useful") is False:
                                    not_useful += 1
                            except (json.JSONDecodeError, KeyError):
                                continue
                    total_rated = useful + not_useful
                    if total_rated > 0:
                        patterns["retrieval_usefulness_rate"] = round(
                            useful / total_rated, 3
                        )
                        patterns["total_rated_retrievals"] = total_rated
            except OSError:
                pass

        patterns["collection_hotspots"] = dict(patterns["collection_hotspots"])
        return patterns

    # =================================================================
    # 5. CONSOLIDATION TIMING
    # =================================================================

    def analyze_consolidation_timing(self):
        """Analyze when knowledge consolidation is most effective.

        Looks at the correlation between consolidation events and
        subsequent capability improvements to find optimal timing.

        Returns:
            Dict with consolidation timing analysis.
        """
        # Load capability history to see improvement patterns
        history = self._load_capability_history()
        if not history or len(history) < 3:
            return {"data_points": len(history) if history else 0,
                    "status": "insufficient_data"}

        # Compute day-over-day improvements
        improvements = []
        for i in range(1, len(history)):
            prev = history[i-1].get("scores", {})
            curr = history[i].get("scores", {})
            date = history[i].get("date", "")

            total_delta = 0
            domains_improved = 0
            for domain in curr:
                if domain in prev:
                    delta = curr[domain] - prev[domain]
                    total_delta += delta
                    if delta > 0.02:
                        domains_improved += 1

            improvements.append({
                "date": date,
                "total_delta": round(total_delta, 4),
                "domains_improved": domains_improved,
            })

        # Find the best improvement days
        if improvements:
            best_days = sorted(improvements, key=lambda x: x["total_delta"], reverse=True)[:3]
            worst_days = sorted(improvements, key=lambda x: x["total_delta"])[:3]
        else:
            best_days = []
            worst_days = []

        # Average improvement rate
        avg_improvement = (sum(i["total_delta"] for i in improvements) / len(improvements)
                           if improvements else 0)

        return {
            "data_points": len(history),
            "avg_daily_improvement": round(avg_improvement, 4),
            "best_improvement_days": best_days,
            "worst_improvement_days": worst_days,
            "total_improvements_analyzed": len(improvements),
            "status": "analyzed",
        }

    # =================================================================
    # RECOMMENDATION ENGINE
    # =================================================================

    def generate_recommendations(self, strategies, learning_speeds,
                                  failure_patterns, retrieval_patterns,
                                  consolidation):
        """Synthesize all meta-learning analyses into actionable recommendations.

        Returns:
            List of recommendation dicts with priority, category, and action.
        """
        recommendations = []

        # 1. Strategy recommendations
        if strategies:
            # Recommend doubling down on high-success strategies
            sorted_strats = sorted(strategies.items(),
                                    key=lambda x: x[1]["success_rate"], reverse=True)
            if sorted_strats:
                best = sorted_strats[0]
                if best[1]["success_rate"] >= 0.8 and best[1]["count"] >= 3:
                    recommendations.append({
                        "priority": "high",
                        "category": "strategy",
                        "action": f"Prefer '{best[0]}' strategy — {best[1]['success_rate']:.0%} success rate across {best[1]['count']} tasks",
                        "detail": f"Average duration: {best[1]['avg_duration_s']:.0f}s. Trend: {'+' if best[1]['trend'] > 0 else ''}{best[1]['trend']:.2f}",
                    })

            # Flag struggling strategies
            for name, stats in strategies.items():
                if stats["success_rate"] < 0.5 and stats["count"] >= 2:
                    recommendations.append({
                        "priority": "high",
                        "category": "strategy",
                        "action": f"Investigate '{name}' strategy — only {stats['success_rate']:.0%} success rate ({stats['count']} tasks)",
                        "detail": "Consider breaking these tasks into smaller steps or changing approach.",
                    })

            # Flag declining strategies
            for name, stats in strategies.items():
                if stats["trend"] < -0.2 and stats["count"] >= 4:
                    recommendations.append({
                        "priority": "medium",
                        "category": "strategy",
                        "action": f"'{name}' strategy declining — trend {stats['trend']:+.2f}. Recent tasks doing worse.",
                        "detail": "May indicate increasing task complexity or environmental changes.",
                    })

        # 2. Learning speed recommendations
        if learning_speeds:
            # Recommend investing in responsive domains that aren't plateaued
            for domain, data in learning_speeds.items():
                if data["responsiveness"] > 0.5 and not data["plateaued"] and data["current_score"] < 0.8:
                    recommendations.append({
                        "priority": "medium",
                        "category": "learning_speed",
                        "action": f"Invest in {domain} — high responsiveness ({data['responsiveness']:.0%}) and room to grow (current: {data['current_score']:.2f})",
                        "detail": f"This domain responds well to focused effort. {data['total_effort_days']} effort days tracked.",
                    })

            # Flag plateaued domains that need a different approach
            for domain, data in learning_speeds.items():
                if data["plateaued"] and data["current_score"] < 0.7:
                    recommendations.append({
                        "priority": "high",
                        "category": "learning_speed",
                        "action": f"{domain} plateaued at {data['current_score']:.2f} — needs a different learning approach",
                        "detail": "Current strategy isn't producing improvement. Try a fundamentally different approach.",
                    })

        # 3. Failure pattern recommendations
        if failure_patterns:
            for error_class, pattern in failure_patterns.items():
                if pattern["count"] >= 3:
                    recommendations.append({
                        "priority": "high",
                        "category": "failure_avoidance",
                        "action": f"Recurring {error_class} failures ({pattern['count']}x). {pattern['avoidance_hint']}",
                        "detail": f"Common context: {', '.join(pattern['common_context'][:3])}",
                    })
                elif pattern["count"] >= 2:
                    recommendations.append({
                        "priority": "medium",
                        "category": "failure_avoidance",
                        "action": f"Watch for {error_class} pattern ({pattern['count']}x). {pattern['avoidance_hint']}",
                        "detail": f"Recent: {pattern['recent_examples'][-1][:60] if pattern['recent_examples'] else 'N/A'}",
                    })

        # 4. Retrieval recommendations
        if retrieval_patterns:
            # Flag low-diversity callers (repeatedly accessing same memories)
            for caller, stats in retrieval_patterns.get("caller_effectiveness", {}).items():
                if stats["diversity_ratio"] < 0.3 and stats["total_accesses"] >= 5:
                    recommendations.append({
                        "priority": "low",
                        "category": "retrieval",
                        "action": f"Caller '{caller}' has low memory diversity ({stats['diversity_ratio']:.0%}) — may be stuck in retrieval loop",
                        "detail": f"{stats['total_accesses']} accesses but only {stats['unique_memories_accessed']} unique memories.",
                    })

            # Overall retrieval usefulness
            usefulness = retrieval_patterns.get("retrieval_usefulness_rate")
            if usefulness is not None and usefulness < 0.5:
                recommendations.append({
                    "priority": "high",
                    "category": "retrieval",
                    "action": f"Retrieval usefulness only {usefulness:.0%} — consider tuning query routing or distance thresholds",
                    "detail": "More than half of retrievals are not useful. Smart_recall parameters may need adjustment.",
                })

        # 5. Consolidation timing recommendations
        if consolidation.get("status") == "analyzed":
            avg_imp = consolidation.get("avg_daily_improvement", 0)
            if avg_imp < 0:
                recommendations.append({
                    "priority": "high",
                    "category": "consolidation",
                    "action": f"Average daily improvement is negative ({avg_imp:+.4f}) — learning is regressing",
                    "detail": "Consolidation may be pruning useful memories, or tasks are degrading capabilities.",
                })

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda r: priority_order.get(r["priority"], 3))

        return recommendations

    # =================================================================
    # FULL ANALYSIS
    # =================================================================

    def analyze(self):
        """Run full meta-learning analysis cycle.

        Returns:
            Complete analysis dict with all strategies, patterns, and recommendations.
        """
        now = datetime.now(timezone.utc)

        # Run all analyses
        strategies = self.analyze_strategy_effectiveness()
        learning_speeds = self.analyze_learning_speed()
        failure_patterns = self.mine_failure_patterns()
        retrieval_patterns = self.analyze_retrieval_effectiveness()
        consolidation = self.analyze_consolidation_timing()

        # Generate recommendations
        recommendations = self.generate_recommendations(
            strategies, learning_speeds, failure_patterns,
            retrieval_patterns, consolidation
        )

        # Build full analysis result
        result = {
            "timestamp": now.isoformat(),
            "strategies": strategies,
            "learning_speeds": learning_speeds,
            "failure_patterns": failure_patterns,
            "retrieval_patterns": retrieval_patterns,
            "consolidation": consolidation,
            "recommendations": recommendations,
            "summary": {
                "strategy_count": len(strategies),
                "domains_analyzed": len(learning_speeds),
                "failure_clusters": len(failure_patterns),
                "total_recommendations": len(recommendations),
                "high_priority_recs": sum(1 for r in recommendations if r["priority"] == "high"),
            },
        }

        # Update persistent state
        self._analysis = {
            "last_run": now.isoformat(),
            "strategies": strategies,
            "learning_speeds": learning_speeds,
            "failure_clusters": failure_patterns,
            "retrieval_patterns": retrieval_patterns,
            "recommendations": recommendations,
            "run_count": self._analysis.get("run_count", 0) + 1,
        }
        self._save_analysis()

        # Save recommendations separately for easy consumption
        with open(RECOMMENDATIONS_FILE, "w") as f:
            json.dump(recommendations, f, indent=2)

        # Log to history
        self._log_run({
            "timestamp": now.isoformat(),
            "strategy_count": len(strategies),
            "recommendation_count": len(recommendations),
            "high_priority_count": result["summary"]["high_priority_recs"],
        })

        # Store top insights in brain for retrieval by other systems
        self._store_insights(strategies, learning_speeds, recommendations)

        # Inject high-priority recommendations into QUEUE.md
        tasks_injected = self._inject_to_queue(recommendations)
        result["summary"]["tasks_injected"] = tasks_injected

        return result

    def _store_insights(self, strategies, learning_speeds, recommendations):
        """Store meta-learning insights in brain for other systems to use."""
        now = datetime.now(timezone.utc).isoformat()

        # Store top strategy insight
        if strategies:
            sorted_strats = sorted(strategies.items(),
                                    key=lambda x: x[1]["success_rate"], reverse=True)
            top_strategies = sorted_strats[:3]
            strategy_summary = "; ".join(
                f"{name}: {s['success_rate']:.0%} success ({s['count']} tasks)"
                for name, s in top_strategies
            )
            brain.store(
                f"Meta-learning insight [{now[:10]}]: Best strategies: {strategy_summary}",
                collection=AUTONOMOUS_LEARNING,
                importance=0.7,
                tags=["meta-learning", "strategy"],
                source="meta_learning",
                memory_id=f"meta_strategy_{now[:10]}",
            )

        # Store high-priority recommendations
        high_recs = [r for r in recommendations if r["priority"] == "high"]
        if high_recs:
            rec_summary = "; ".join(r["action"][:100] for r in high_recs[:3])
            brain.store(
                f"Meta-learning alert [{now[:10]}]: {rec_summary}",
                collection=AUTONOMOUS_LEARNING,
                importance=0.8,
                tags=["meta-learning", "recommendation", "alert"],
                source="meta_learning",
                memory_id=f"meta_alert_{now[:10]}",
            )

        # Store learning speed insights
        if learning_speeds:
            responsive = {d: s for d, s in learning_speeds.items()
                          if s["responsiveness"] > 0.4}
            plateaued = {d: s for d, s in learning_speeds.items()
                         if s["plateaued"]}
            if responsive or plateaued:
                parts = []
                if responsive:
                    parts.append("Responsive domains: " + ", ".join(
                        f"{d} ({s['responsiveness']:.0%})" for d, s in responsive.items()
                    ))
                if plateaued:
                    parts.append("Plateaued domains: " + ", ".join(
                        f"{d} ({s['current_score']:.2f})" for d, s in plateaued.items()
                    ))
                brain.store(
                    f"Meta-learning insight [{now[:10]}]: {' | '.join(parts)}",
                    collection=AUTONOMOUS_LEARNING,
                    importance=0.6,
                    tags=["meta-learning", "learning-speed"],
                    source="meta_learning",
                    memory_id=f"meta_speed_{now[:10]}",
                )

    # =================================================================
    # QUEUE INJECTION — Turn recommendations into tasks
    # =================================================================

    def _load_injection_history(self):
        """Load injection history for dedup."""
        if INJECTION_HISTORY_FILE.exists():
            try:
                with open(INJECTION_HISTORY_FILE) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {"injected": []}

    def _save_injection_history(self, history):
        """Save injection history, keeping last 50 entries."""
        history["injected"] = history["injected"][-50:]
        with open(INJECTION_HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)

    def _inject_to_queue(self, recommendations):
        """Inject HIGH priority recommendations into QUEUE.md as tasks.

        Filters to high-priority only, deduplicates against injection history,
        caps at MAX_INJECTIONS_PER_CYCLE per cycle.

        Args:
            recommendations: List of recommendation dicts from generate_recommendations()

        Returns:
            Number of tasks injected.
        """
        try:
            from queue_writer import add_tasks
        except ImportError:
            return 0

        try:
            # Filter to HIGH priority only
            high_recs = [r for r in recommendations if r.get("priority") == "high"]
            if not high_recs:
                return 0

            # Load injection history for dedup
            history = self._load_injection_history()
            injected_keys = {entry["key"] for entry in history["injected"]}

            # Build task strings, skipping already-injected
            tasks = []
            for rec in high_recs:
                action = rec.get("action", "")
                category = rec.get("category", "unknown")
                detail = rec.get("detail", "")

                # Dedup key: first 80 chars of action
                dedup_key = action[:80].strip()
                if dedup_key in injected_keys:
                    continue

                task_text = f"[Meta-learning/{category}] {action}"
                if detail:
                    task_text += f" — {detail[:100]}"

                tasks.append(task_text)
                injected_keys.add(dedup_key)

                # Record in history
                history["injected"].append({
                    "key": dedup_key,
                    "category": category,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

                if len(tasks) >= MAX_INJECTIONS_PER_CYCLE:
                    break

            if not tasks:
                return 0

            # Inject to QUEUE.md
            added = add_tasks(tasks, priority="P1", source="meta_learning")

            # Only save history if at least one task was actually added
            if added:
                self._save_injection_history(history)

            return len(added)

        except Exception:
            return 0  # Never let injection break analysis

    # =================================================================
    # GET RECOMMENDATIONS FOR TASK SELECTION
    # =================================================================

    def get_task_advice(self, task_text):
        """Get meta-learning advice for a specific task before execution.

        Used by task_selector.py or cron_autonomous.sh to make better decisions.

        Args:
            task_text: The task about to be executed

        Returns:
            Dict with advice: strategy_score, warnings, suggested_approach
        """
        advice = {
            "strategy_score": 0.5,  # neutral default
            "warnings": [],
            "suggested_approach": None,
        }

        task_lower = (task_text or "").lower()

        # Check strategy effectiveness
        strategies = self._analysis.get("strategies", {})
        for strategy_name, stats in strategies.items():
            # Check if this task matches a known strategy
            STRATEGY_VERBS = {
                "build": ["build", "create", "implement", "add"],
                "fix": ["fix", "repair", "debug", "resolve"],
                "wire": ["wire", "connect", "integrate", "hook"],
                "improve": ["improve", "boost", "enhance", "optimize"],
                "research": ["research", "analyze", "study", "investigate"],
                "refactor": ["refactor", "clean", "consolidate"],
            }
            verbs = STRATEGY_VERBS.get(strategy_name, [])
            if any(v in task_lower[:60] for v in verbs):
                advice["strategy_score"] = stats.get("success_rate", 0.5)
                if stats.get("success_rate", 1.0) < 0.5:
                    advice["warnings"].append(
                        f"'{strategy_name}' strategy has low success rate "
                        f"({stats['success_rate']:.0%}). Consider different approach."
                    )
                break

        # Check failure patterns
        failure_clusters = self._analysis.get("failure_clusters", {})
        for error_class, pattern in failure_clusters.items():
            context_words = pattern.get("common_context", [])
            if any(w in task_lower for w in context_words):
                advice["warnings"].append(
                    f"Task matches {error_class} failure pattern "
                    f"({pattern['count']}x). {pattern.get('avoidance_hint', '')}"
                )

        return advice

    # =================================================================
    # HELPERS
    # =================================================================

    def _load_episodes(self):
        if EPISODES_FILE.exists():
            try:
                with open(EPISODES_FILE) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return []

    def _load_capability_history(self):
        if CAPABILITY_HISTORY_FILE.exists():
            try:
                with open(CAPABILITY_HISTORY_FILE) as f:
                    data = json.load(f)
                return data.get("snapshots", [])
            except (json.JSONDecodeError, OSError):
                pass
        return []

    @staticmethod
    def _gini_coefficient(values):
        """Compute Gini coefficient (0 = equal, 1 = concentrated)."""
        if not values or len(values) < 2:
            return 0.0
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        total = sum(sorted_vals)
        if total == 0:
            return 0.0
        numerator = sum((2 * i - n + 1) * val for i, val in enumerate(sorted_vals))
        return numerator / (n * total)


# Singleton (lazy — no I/O until first access)
_meta_learner = None

def get_meta_learner():
    global _meta_learner
    if _meta_learner is None:
        _meta_learner = MetaLearner()
    return _meta_learner

class _LazyMetaLearner:
    def __getattr__(self, name):
        real = get_meta_learner()
        global meta_learner
        meta_learner = real
        return getattr(real, name)
    def __repr__(self):
        return "<LazyMetaLearner (not yet initialized)>"

meta_learner = _LazyMetaLearner()


# =================================================================
# CLI
# =================================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: meta_learning.py <analyze|strategies|speed|failures|recommend|stats|advise>")
        print()
        print("Commands:")
        print("  analyze     Run full meta-learning analysis cycle")
        print("  strategies  Show strategy effectiveness rankings")
        print("  speed       Show learning speed by domain")
        print("  failures    Show clustered failure anti-patterns")
        print("  recommend   Get meta-learning recommendations")
        print("  stats       Show meta-learning run statistics")
        print("  advise      Get advice for a task: advise <task_text>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "analyze":
        print("Running full meta-learning analysis...")
        result = meta_learner.analyze()

        print(f"\n{'='*60}")
        print("META-LEARNING ANALYSIS REPORT")
        print(f"{'='*60}")

        # Strategies
        print(f"\n--- Strategy Effectiveness ({len(result['strategies'])}) ---")
        for name, stats in sorted(result["strategies"].items(),
                                    key=lambda x: x[1]["success_rate"], reverse=True):
            trend_str = f" trend={stats['trend']:+.2f}" if stats["trend"] != 0 else ""
            print(f"  {name:12s}  {stats['success_rate']:.0%} success  "
                  f"({stats['count']} tasks, avg {stats['avg_duration_s']:.0f}s){trend_str}")

        # Learning speeds
        print(f"\n--- Learning Speed by Domain ({len(result['learning_speeds'])}) ---")
        for domain, data in sorted(result["learning_speeds"].items(),
                                     key=lambda x: x[1]["responsiveness"], reverse=True):
            plateau_str = " [PLATEAUED]" if data["plateaued"] else ""
            print(f"  {domain:25s}  resp={data['responsiveness']:.0%}  "
                  f"score={data['current_score']:.2f}  "
                  f"rate={data['improvement_rate']:+.4f}{plateau_str}")

        # Failure patterns
        print(f"\n--- Failure Anti-Patterns ({len(result['failure_patterns'])}) ---")
        for error_class, pattern in sorted(result["failure_patterns"].items(),
                                            key=lambda x: x[1]["count"], reverse=True):
            print(f"  {error_class:20s}  {pattern['count']}x  "
                  f"context: {', '.join(pattern['common_context'][:3])}")
            print(f"    -> {pattern['avoidance_hint']}")

        # Retrieval
        rp = result["retrieval_patterns"]
        print("\n--- Retrieval Effectiveness ---")
        print(f"  Total accesses: {rp.get('total_accesses', 0)}")
        if rp.get("retrieval_usefulness_rate") is not None:
            print(f"  Usefulness rate: {rp['retrieval_usefulness_rate']:.0%}")
        print(f"  Access concentration (Gini): {rp.get('access_concentration', 0):.3f}")
        callers = rp.get("caller_effectiveness", {})
        if callers:
            print("  Top callers:")
            for caller, stats in sorted(callers.items(),
                                         key=lambda x: x[1]["total_accesses"], reverse=True)[:5]:
                print(f"    {caller:25s}  {stats['total_accesses']} accesses  "
                      f"diversity={stats['diversity_ratio']:.0%}")

        # Recommendations
        recs = result["recommendations"]
        print(f"\n--- Recommendations ({len(recs)}) ---")
        for r in recs:
            icon = {"high": "!!!", "medium": " ! ", "low": "   "}.get(r["priority"], "   ")
            print(f"  [{icon}] [{r['category']}] {r['action']}")
            if r.get("detail"):
                print(f"         {r['detail']}")

        # Summary
        s = result["summary"]
        print("\n--- Summary ---")
        print(f"  Strategies analyzed: {s['strategy_count']}")
        print(f"  Domains analyzed: {s['domains_analyzed']}")
        print(f"  Failure clusters: {s['failure_clusters']}")
        print(f"  Recommendations: {s['total_recommendations']} "
              f"({s['high_priority_recs']} high-priority)")

    elif cmd == "strategies":
        strategies = meta_learner.analyze_strategy_effectiveness()
        if not strategies:
            print("No strategies found. Run 'analyze' first or wait for more episodes.")
        else:
            print("Strategy Effectiveness Rankings:")
            for name, stats in sorted(strategies.items(),
                                        key=lambda x: x[1]["success_rate"], reverse=True):
                bar = "█" * int(stats["success_rate"] * 10) + "░" * (10 - int(stats["success_rate"] * 10))
                print(f"  {name:12s}  {bar}  {stats['success_rate']:.0%}  ({stats['count']} tasks)")

    elif cmd == "speed":
        speeds = meta_learner.analyze_learning_speed()
        if not speeds:
            print("Insufficient data for learning speed analysis.")
        else:
            print("Learning Speed by Domain:")
            for domain, data in sorted(speeds.items(),
                                         key=lambda x: x[1]["responsiveness"], reverse=True):
                plateau_str = " [PLATEAUED]" if data["plateaued"] else ""
                print(f"  {domain:25s}  responsiveness={data['responsiveness']:.0%}  "
                      f"score={data['current_score']:.2f}{plateau_str}")

    elif cmd == "failures":
        patterns = meta_learner.mine_failure_patterns()
        if not patterns:
            print("No failure patterns found.")
        else:
            print("Failure Anti-Patterns:")
            for error_class, pattern in sorted(patterns.items(),
                                                key=lambda x: x[1]["count"], reverse=True):
                print(f"\n  {error_class} ({pattern['count']}x):")
                print(f"    Avoidance: {pattern['avoidance_hint']}")
                if pattern["recent_examples"]:
                    print(f"    Recent: {pattern['recent_examples'][-1][:80]}")

    elif cmd == "recommend":
        # Load from saved analysis or run fresh
        if RECOMMENDATIONS_FILE.exists():
            try:
                with open(RECOMMENDATIONS_FILE) as f:
                    recs = json.load(f)
            except (json.JSONDecodeError, OSError):
                recs = []
        else:
            result = meta_learner.analyze()
            recs = result["recommendations"]

        if not recs:
            print("No recommendations. System is operating well.")
        else:
            print(f"Meta-Learning Recommendations ({len(recs)}):")
            for r in recs:
                icon = {"high": "!!!", "medium": " ! ", "low": "   "}.get(r["priority"], "   ")
                print(f"  [{icon}] [{r['category']}] {r['action']}")

    elif cmd == "stats":
        analysis = meta_learner._analysis
        print("Meta-Learning Statistics:")
        print(f"  Last run: {analysis.get('last_run', 'never')}")
        print(f"  Total runs: {analysis.get('run_count', 0)}")
        print(f"  Strategies tracked: {len(analysis.get('strategies', {}))}")
        print(f"  Failure clusters: {len(analysis.get('failure_clusters', {}))}")
        print(f"  Active recommendations: {len(analysis.get('recommendations', []))}")

    elif cmd == "advise":
        task_text = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        if not task_text:
            print("Usage: meta_learning.py advise <task_text>")
            sys.exit(1)
        advice = meta_learner.get_task_advice(task_text)
        print(json.dumps(advice, indent=2))

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
