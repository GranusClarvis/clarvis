#!/usr/bin/env python3
"""
Retrieval Quality Tracker — Measure how useful brain.recall() results are.

This is the foundational feedback loop for memory quality. Without knowing
whether recall returns useful results, every system that depends on it
(task selection, procedural memory, knowledge synthesis) operates blindly.

Tracks:
- Every recall event: query, num results, avg distance, caller
- Quality signals: was the retrieval actually used downstream?
- Aggregate metrics: hit rate, avg useful distance, dead-recall rate

Usage:
    from retrieval_quality import tracker

    # Automatic: brain.recall() logs events via on_recall()
    # Manual: callers rate usefulness
    tracker.rate("evt_123", useful=True, reason="matched procedure")

    # Report
    tracker.report()
"""

import json
import os
import sys
from datetime import datetime, timezone
from collections import defaultdict

_WS = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
DATA_DIR = os.path.join(_WS, "data", "retrieval_quality")
EVENTS_FILE = os.path.join(DATA_DIR, "events.jsonl")
REPORT_FILE = os.path.join(DATA_DIR, "report.json")
os.makedirs(DATA_DIR, exist_ok=True)

# Keep events file bounded (max ~5000 lines)
MAX_EVENTS = 5000


class RetrievalQualityTracker:
    """Tracks retrieval quality across all brain.recall() usage."""

    def __init__(self):
        self._event_counter = 0

    def on_recall(self, query: str, results: list, caller: str = "unknown") -> str:
        """
        Log a recall event. Called automatically by instrumented brain.recall().

        Args:
            query: The search query
            results: List of result dicts from recall()
            caller: Who called recall (e.g., "task_selector", "procedural_memory")

        Returns:
            Event ID for later rating
        """
        self._event_counter += 1
        event_id = f"evt_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{self._event_counter}"

        distances = []
        collections_hit = set()
        for r in results:
            if r.get("distance") is not None:
                distances.append(r["distance"])
            if r.get("collection"):
                collections_hit.add(r["collection"])

        # CRAG-style retrieval verdict (best-effort, non-blocking)
        retrieval_verdict = None
        retrieval_max_score = None
        try:
            from clarvis.brain.retrieval_eval import classify_batch
            verdict, max_score, _ = classify_batch(results, query)
            retrieval_verdict = verdict
            retrieval_max_score = round(max_score, 4)
        except Exception:
            pass  # Non-critical — don't block event logging

        event = {
            "id": event_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query": query[:200],  # Truncate long queries
            "caller": caller,
            "num_results": len(results),
            "avg_distance": round(sum(distances) / len(distances), 4) if distances else None,
            "min_distance": round(min(distances), 4) if distances else None,
            "max_distance": round(max(distances), 4) if distances else None,
            "collections_hit": sorted(collections_hit),
            "retrieval_verdict": retrieval_verdict,
            "retrieval_max_score": retrieval_max_score,
            "useful": None,  # Filled by rate()
            "reason": None,
        }

        self._append_event(event)
        return event_id

    def rate(self, event_id: str, useful: bool, reason: str = ""):
        """
        Rate a retrieval event as useful or not.

        Args:
            event_id: The event ID from on_recall()
            useful: Whether the results were actually useful
            reason: Why (optional)
        """
        # Read all events, find and update the one with this ID
        events = self._load_events()
        for event in reversed(events):  # Search from most recent
            if event.get("id") == event_id:
                event["useful"] = useful
                event["reason"] = reason
                self._save_events(events)
                return
        # If not found by ID, try matching by recent caller
        # (for cases where event_id wasn't captured)

    def rate_last(self, caller: str, useful: bool, reason: str = ""):
        """
        Rate the most recent retrieval by a specific caller.
        Convenience method when event_id wasn't captured.
        """
        events = self._load_events()
        for event in reversed(events):
            if event.get("caller") == caller and event.get("useful") is None:
                event["useful"] = useful
                event["reason"] = reason
                self._save_events(events)
                return

    def report(self, days: int = 7) -> dict:
        """
        Generate retrieval quality report.

        Returns:
            Dict with metrics: hit_rate, avg_distance, dead_recall_rate,
            per-caller stats, quality trend
        """
        events = self._load_events()

        # Filter to recent events
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        recent = [e for e in events if e.get("timestamp", "") >= cutoff]

        if not recent:
            return {"status": "no_data", "total_events": len(events)}

        # Overall stats
        total = len(recent)
        empty_results = sum(1 for e in recent if e["num_results"] == 0)
        rated = [e for e in recent if e.get("useful") is not None]
        useful_count = sum(1 for e in rated if e["useful"])

        # Distance stats (only for non-empty results)
        all_avg_distances = [e["avg_distance"] for e in recent if e.get("avg_distance") is not None]
        all_min_distances = [e["min_distance"] for e in recent if e.get("min_distance") is not None]

        # Per-caller breakdown
        by_caller = defaultdict(lambda: {"total": 0, "rated": 0, "useful": 0, "distances": []})
        for e in recent:
            c = e.get("caller", "unknown")
            by_caller[c]["total"] += 1
            if e.get("avg_distance") is not None:
                by_caller[c]["distances"].append(e["avg_distance"])
            if e.get("useful") is not None:
                by_caller[c]["rated"] += 1
                if e["useful"]:
                    by_caller[c]["useful"] += 1

        caller_stats = {}
        for caller, data in by_caller.items():
            caller_stats[caller] = {
                "total_recalls": data["total"],
                "rated": data["rated"],
                "useful": data["useful"],
                "hit_rate": round(data["useful"] / data["rated"], 3) if data["rated"] > 0 else None,
                "avg_distance": round(sum(data["distances"]) / len(data["distances"]), 4) if data["distances"] else None,
            }

        result = {
            "period_days": days,
            "total_events": total,
            "empty_recalls": empty_results,
            "dead_recall_rate": round(empty_results / total, 3) if total > 0 else 0,
            "rated_events": len(rated),
            "useful_events": useful_count,
            "hit_rate": round(useful_count / len(rated), 3) if rated else None,
            "avg_distance_overall": round(sum(all_avg_distances) / len(all_avg_distances), 4) if all_avg_distances else None,
            "avg_min_distance": round(sum(all_min_distances) / len(all_min_distances), 4) if all_min_distances else None,
            "by_caller": caller_stats,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Diagnosis
        if result["dead_recall_rate"] > 0.3:
            result["diagnosis"] = "HIGH_DEAD_RECALL"
            result["recommendation"] = "Many queries returning no results. Check query quality or add more memories."
        elif result.get("hit_rate") is not None and result["hit_rate"] < 0.5:
            result["diagnosis"] = "LOW_HIT_RATE"
            result["recommendation"] = "Retrieved results often not useful. Check memory quality and query relevance."
        elif result.get("avg_distance_overall") is not None and result["avg_distance_overall"] > 1.5:
            result["diagnosis"] = "HIGH_DISTANCE"
            result["recommendation"] = "Average distance high — memories aren't well-matched to queries. Consider rewriting or consolidating memories."
        else:
            result["diagnosis"] = "HEALTHY"
            result["recommendation"] = "Retrieval quality looks good."

        # Save report
        with open(REPORT_FILE, "w") as f:
            json.dump(result, f, indent=2)

        return result

    def _append_event(self, event: dict):
        """Append a single event to the events file."""
        with open(EVENTS_FILE, "a") as f:
            f.write(json.dumps(event) + "\n")

        # Periodic truncation check
        self._maybe_truncate()

    def _load_events(self) -> list:
        """Load all events from disk."""
        if not os.path.exists(EVENTS_FILE):
            return []
        events = []
        with open(EVENTS_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return events

    def _save_events(self, events: list):
        """Rewrite all events to disk."""
        with open(EVENTS_FILE, "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

    def _maybe_truncate(self):
        """Keep events file bounded."""
        if not os.path.exists(EVENTS_FILE):
            return
        try:
            with open(EVENTS_FILE, "r") as f:
                lines = f.readlines()
            if len(lines) > MAX_EVENTS:
                # Keep most recent half
                keep = lines[len(lines) - MAX_EVENTS // 2:]
                with open(EVENTS_FILE, "w") as f:
                    f.writelines(keep)
        except Exception:
            pass


# Singleton (lazy — no I/O until first access)
_tracker = None

def get_tracker():
    global _tracker
    if _tracker is None:
        _tracker = RetrievalQualityTracker()
    return _tracker

class _LazyTracker:
    def __getattr__(self, name):
        real = get_tracker()
        global tracker
        tracker = real
        return getattr(real, name)
    def __repr__(self):
        return "<LazyTracker (not yet initialized)>"

tracker = _LazyTracker()


# === CLI ===
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Retrieval Quality Tracker")
        print("Usage:")
        print("  report [days]     — Show retrieval quality report")
        print("  events [n]        — Show recent events")
        print("  rate <event_id> <useful|not_useful> [reason]")
        print("  baseline          — Run baseline quality measurement")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "report":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        result = tracker.report(days=days)
        print(f"=== Retrieval Quality Report ({days} days) ===")
        print(f"Total recalls: {result.get('total_events', 0)}")
        print(f"Dead recall rate: {result.get('dead_recall_rate', 0):.1%}")
        if result.get("hit_rate") is not None:
            print(f"Hit rate (of rated): {result['hit_rate']:.1%}")
        print(f"Avg distance: {result.get('avg_distance_overall', 'N/A')}")
        print(f"Diagnosis: {result.get('diagnosis', 'N/A')}")
        print(f"Recommendation: {result.get('recommendation', '')}")
        if result.get("by_caller"):
            print("\nBy caller:")
            for caller, stats in result["by_caller"].items():
                caller_short = caller.replace("clarvis-", "")
                hr = f"{stats['hit_rate']:.0%}" if stats.get("hit_rate") is not None else "unrated"
                print(f"  {caller_short}: {stats['total_recalls']} recalls, hit_rate={hr}, avg_dist={stats.get('avg_distance', 'N/A')}")

    elif cmd == "events":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        events = tracker._load_events()
        for e in events[-n:]:
            useful_str = ""
            if e.get("useful") is True:
                useful_str = " [USEFUL]"
            elif e.get("useful") is False:
                useful_str = " [NOT USEFUL]"
            print(f"  {e.get('timestamp', '')[:19]} [{e.get('caller', '?')}] "
                  f"q=\"{e.get('query', '')[:50]}\" "
                  f"n={e.get('num_results', 0)} "
                  f"d={e.get('avg_distance', 'N/A')}{useful_str}")

    elif cmd == "rate":
        event_id = sys.argv[2] if len(sys.argv) > 2 else ""
        useful = sys.argv[3] if len(sys.argv) > 3 else "useful"
        reason = " ".join(sys.argv[4:]) if len(sys.argv) > 4 else ""
        is_useful = useful.lower() in ("useful", "true", "yes", "1")
        tracker.rate(event_id, is_useful, reason)
        print(f"Rated {event_id}: {'useful' if is_useful else 'not useful'}")

    elif cmd == "baseline":
        # Run a baseline quality measurement against known queries
        from clarvis.brain import brain, GOALS, PROCEDURES, LEARNINGS, MEMORIES, CONTEXT, IDENTITY

        # Use smart_recall if available
        try:
            from retrieval_experiment import smart_recall
        except ImportError:
            smart_recall = None

        # Test queries with multiple acceptable collections (realistic expectations)
        test_queries = [
            ("What bugs have been fixed today?", [LEARNINGS, MEMORIES]),
            ("How does the attention mechanism work?", [LEARNINGS, MEMORIES]),
            ("What are my current goals?", [GOALS]),
            ("procedural memory for building scripts", [PROCEDURES, LEARNINGS]),
            ("consciousness and phi metric", [LEARNINGS, MEMORIES]),
            ("What is Clarvis's identity?", [IDENTITY, LEARNINGS]),
            ("How to wire a script into cron?", [PROCEDURES, LEARNINGS]),
            ("What happened in the last heartbeat?", [CONTEXT, MEMORIES]),
            ("reasoning chains and thought logging", [LEARNINGS, MEMORIES, PROCEDURES]),
            ("self-improvement and evolution", [LEARNINGS, GOALS, MEMORIES]),
        ]

        print("=== Baseline Retrieval Quality ===")
        hits = 0
        total = 0
        for query, expected_collections in test_queries:
            total += 1
            if smart_recall is not None:
                results = smart_recall(query, n=3)
            else:
                results = brain.recall(query, n=3)
            evt_id = tracker.on_recall(query, results, caller="baseline_test")

            # Check if top result is from any expected collection
            top_collection = results[0]["collection"] if results else None
            top_distance = results[0].get("distance") if results else None
            # Hit if top result is from expected collection OR distance is good (< 1.2)
            match = top_collection in expected_collections if top_collection else False
            distance_ok = top_distance is not None and top_distance < 1.2

            useful = match or distance_ok
            if useful:
                hits += 1

            # Auto-rate based on match + distance
            tracker.rate(evt_id, useful, f"expected={expected_collections}, got={top_collection}, d={top_distance}")

            match_str = "HIT" if useful else "MISS"
            print(f"  [{match_str}] \"{query[:50]}\"")
            print(f"       top: [{top_collection}] d={top_distance}")
            if not useful and results:
                print(f"       expected: {expected_collections}")

        hit_rate = hits / total if total > 0 else 0
        print(f"\nBaseline: {hits}/{total} = {hit_rate:.0%}")

        # Generate report
        report = tracker.report(days=1)
        print(f"Report hit rate: {report.get('hit_rate', 'N/A')}")
        print(f"Avg distance: {report.get('avg_distance_overall', 'N/A')}")

    else:
        print(f"Unknown command: {cmd}")
