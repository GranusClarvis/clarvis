"""
Hook adapters for heartbeat subsystems.

Migrates 3 subsystems from import-time wiring to explicit hook registration:
  1. Procedural memory (priority 30-39)
  2. Consolidation / periodic synthesis (priority 50-59)
  3. Metrics: performance benchmark, latency budget, structural health (priority 60-69)

Each adapter lazily imports its dependency so the hook registry itself
has zero import-time side effects.

Usage:
    from clarvis.heartbeat.adapters import register_all
    register_all()   # call once at startup
"""

import os
import json
import sys
import time
from datetime import datetime, timezone

from .hooks import registry, HookPhase
from clarvis._script_loader import load as _load_script

_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")

_log = lambda msg: print(
    f"[{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')}] HOOK: {msg}",
    file=sys.stderr,
)


# ---------------------------------------------------------------------------
# 1. PROCEDURAL MEMORY hooks (postflight priority 30-39)
# ---------------------------------------------------------------------------

def _procedural_record(context):
    """Record procedure usage outcome (success/failure) and learn new procedures."""
    from clarvis.memory.procedural_memory import record_use, learn_from_task

    exit_code = context.get("exit_code", 1)
    proc_id = context.get("procedure_id")
    task = context.get("task", "")
    output_text = context.get("output_text", "")

    if exit_code == 0:
        if proc_id:
            record_use(proc_id, True)
            _log(f"Recorded successful use of procedure {proc_id}")
            return {"action": "record_success", "proc_id": proc_id}
        else:
            # Try to learn a new procedure from output
            try:
                _es_mod = _load_script("extract_steps", "tools")
                extract_steps = _es_mod.extract_steps
                extraction_text = output_text[-2000:] if len(output_text) > 2000 else output_text
                steps = extract_steps(extraction_text)
                if steps:
                    learn_from_task(task, steps)
                    _log(f"Learned new procedure from task output ({len(steps)} steps)")
                    return {"action": "learned", "steps": len(steps)}
                return {"action": "no_steps"}
            except ImportError:
                return {"action": "extract_steps_unavailable"}
    else:
        if proc_id:
            record_use(proc_id, False)
            _log(f"Recorded failed use of procedure {proc_id}")
            return {"action": "record_failure", "proc_id": proc_id}
    return {"action": "skip"}


def _procedural_injection_track(context):
    """Track procedure injection → outcome correlation."""
    proc_injected = context.get("procedure_injected", False)
    if not proc_injected:
        return {"action": "skip"}

    injection_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task": context.get("task", "")[:200],
        "procedure_id": context.get("procedure_id", ""),
        "procedures_injected": context.get("procedures_for_injection", []),
        "outcome": context.get("task_status", "unknown"),
        "exit_code": context.get("exit_code", -1),
        "duration_s": context.get("task_duration", 0),
    }
    injection_log = os.path.join(_SCRIPTS_DIR, "..", "data", "procedure_injection_log.jsonl")
    os.makedirs(os.path.dirname(injection_log), exist_ok=True)
    with open(injection_log, "a") as f:
        f.write(json.dumps(injection_entry) + "\n")
    _log(f"Procedure injection tracked: {injection_entry['procedure_id']} → {injection_entry['outcome']}")
    return {"action": "tracked"}


# ---------------------------------------------------------------------------
# 2. CONSOLIDATION hooks (postflight priority 50-59)
# ---------------------------------------------------------------------------

def _periodic_synthesis(context):
    """Run episodic memory synthesis every 10th episode."""
    from clarvis.memory.episodic_memory import EpisodicMemory

    em = EpisodicMemory()
    ep_count = len(em.episodes)
    if ep_count % 10 != 0 or ep_count == 0:
        return {"action": "skip", "episode_count": ep_count}

    synth = em.synthesize()
    result = {
        "action": "synthesized",
        "goals_count": synth.get("goals_count", 0),
        "success_rate": synth.get("success_rate", "?"),
    }
    _log(f"Periodic synthesis: {result['goals_count']} goals, success_rate={result['success_rate']}")

    # Backfill causal links
    backfilled = em.backfill_causal_links()
    if backfilled:
        result["causal_links_added"] = backfilled
        _log(f"Causal backfill: +{backfilled} links")

    return result


# ---------------------------------------------------------------------------
# 3. METRICS hooks (postflight priority 60-69)
# ---------------------------------------------------------------------------

def _perf_benchmark(context):
    """Quick performance health check (brain query speed, memory count)."""
    _pb = _load_script("performance_benchmark", "metrics")
    run_heartbeat_check = _pb.run_heartbeat_check

    result = run_heartbeat_check()
    if not result.get("speed_ok", True):
        _log(f"PERF WARNING: brain query avg {result.get('brain_query_avg_ms', '?')}ms exceeds critical threshold")
    else:
        _log(f"PERF: query={result.get('brain_query_avg_ms', '?')}ms, "
             f"memories={result.get('brain_memories', '?')}, "
             f"density={result.get('graph_density', '?')}, "
             f"prev_pi={result.get('prev_pi', 'N/A')}")
    return result


def _latency_budget(context):
    """Check p50/p95 brain.recall latency against budget."""
    _lb = _load_script("latency_budget", "metrics")
    quick_check = _lb.quick_check

    result = quick_check()
    if result.get("critical"):
        _log(f"LATENCY CRITICAL: brain.recall p95={result['p95_ms']:.0f}ms exceeds critical threshold")
    elif not result.get("p50_ok") or not result.get("p95_ok"):
        _log(f"LATENCY WARN: brain.recall p50={result['p50_ms']:.0f}ms p95={result['p95_ms']:.0f}ms "
             f"(budget p50={result['budget_p50_ms']}ms p95={result['budget_p95_ms']}ms)")
    else:
        _log(f"LATENCY: brain.recall p50={result['p50_ms']:.0f}ms p95={result['p95_ms']:.0f}ms [OK]")
    return result


def _structural_health(context):
    """Import graph metrics for trend tracking."""
    _ih = _load_script("import_health", "infra")
    build_import_graph, full_report, SCRIPTS_DIR = _ih.build_import_graph, _ih.full_report, _ih.SCRIPTS_DIR

    graph = build_import_graph(SCRIPTS_DIR)
    report = full_report(graph, use_current_thresholds=True)
    metrics = {
        "scc_count": report["circular_imports"]["scc_count"],
        "max_scc_size": report["circular_imports"]["max_scc_size"],
        "max_depth": report["dependency_depth"]["max"],
        "max_fan_in": report["fan_in"]["max"],
        "max_fan_out": report["fan_out"]["max"],
        "side_effects": report["side_effects"]["count"],
        "total_modules": report["total_modules"],
        "violations": report["violations"],
        "healthy": report["healthy"],
    }

    # Append to performance_history.jsonl
    hist_file = os.path.join(_SCRIPTS_DIR, "..", "data", "performance_history.jsonl")
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "structural_health",
        "metrics": metrics,
    }
    with open(hist_file, "a") as f:
        f.write(json.dumps(entry) + "\n")

    status = "HEALTHY" if metrics["healthy"] else f"DEGRADED ({', '.join(metrics['violations'])})"
    _log(f"STRUCTURAL: {status} — SCCs={metrics['scc_count']}, "
         f"depth={metrics['max_depth']}, fan_in={metrics['max_fan_in']}, "
         f"fan_out={metrics['max_fan_out']}, modules={metrics['total_modules']}")
    return metrics


# ---------------------------------------------------------------------------
# 4. META-LEARNING hook (postflight priority 90 — optional, daily max)
# ---------------------------------------------------------------------------

# Marker file for daily rate limiting
_META_LEARNING_MARKER = os.path.join(_SCRIPTS_DIR, "..", "data", "meta_learning", ".last_postflight_run")


def _meta_learning_analyze(context):
    """Run meta-learning analysis (at most once per day via postflight)."""
    # Daily rate limit check
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if os.path.exists(_META_LEARNING_MARKER):
        try:
            with open(_META_LEARNING_MARKER) as f:
                last_date = f.read().strip()
            if last_date == today:
                return {"action": "skip", "reason": "already_ran_today"}
        except (IOError, OSError):
            pass

    from clarvis.learning.meta_learning import MetaLearner

    ml = MetaLearner()
    result = ml.analyze()
    summary = result.get("summary", {})

    # Update marker
    os.makedirs(os.path.dirname(_META_LEARNING_MARKER), exist_ok=True)
    with open(_META_LEARNING_MARKER, "w") as f:
        f.write(today)

    _log(f"META-LEARNING: {summary.get('strategy_count', 0)} strategies, "
         f"{summary.get('total_recommendations', 0)} recommendations "
         f"({summary.get('high_priority_recs', 0)} high-pri)")

    return {
        "action": "analyzed",
        "strategies": summary.get("strategy_count", 0),
        "recommendations": summary.get("total_recommendations", 0),
        "high_priority": summary.get("high_priority_recs", 0),
    }


# ---------------------------------------------------------------------------
# 5. INTRINSIC SELF-ASSESSMENT hook (postflight priority 92 — daily, after meta-learning)
# ---------------------------------------------------------------------------

_ASSESSMENT_MARKER = os.path.join(_SCRIPTS_DIR, "..", "data", ".last_assessment_run")


def _intrinsic_assessment(context):
    """Run intrinsic self-assessment (at most once per day via postflight)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if os.path.exists(_ASSESSMENT_MARKER):
        try:
            with open(_ASSESSMENT_MARKER) as f:
                last_date = f.read().strip()
            if last_date == today:
                return {"action": "skip", "reason": "already_ran_today"}
        except (IOError, OSError):
            pass

    from clarvis.cognition.intrinsic_assessment import full_assessment

    result = full_assessment(days=7)
    assessment = result.get("assessment", {})
    curriculum = result.get("autocurriculum", [])

    # Update marker
    os.makedirs(os.path.dirname(_ASSESSMENT_MARKER), exist_ok=True)
    with open(_ASSESSMENT_MARKER, "w") as f:
        f.write(today)

    score = assessment.get("composite_score", 0)
    patterns = len(result.get("failure_patterns", []))
    _log(f"SELF-ASSESSMENT: composite={score:.0%}, "
         f"patterns={patterns}, autocurriculum={len(curriculum)} tasks")

    return {
        "action": "assessed",
        "composite_score": score,
        "failure_patterns": patterns,
        "autocurriculum_tasks": len(curriculum),
    }


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_procedural():
    """Register procedural memory hooks."""
    registry.register(HookPhase.POSTFLIGHT, "procedural_record", _procedural_record, priority=30)
    registry.register(HookPhase.POSTFLIGHT, "procedural_injection_track", _procedural_injection_track, priority=35)


def register_consolidation():
    """Register memory consolidation hooks."""
    registry.register(HookPhase.POSTFLIGHT, "periodic_synthesis", _periodic_synthesis, priority=50)


def register_metrics():
    """Register performance metrics hooks."""
    registry.register(HookPhase.POSTFLIGHT, "perf_benchmark", _perf_benchmark, priority=60)
    registry.register(HookPhase.POSTFLIGHT, "latency_budget", _latency_budget, priority=62)
    registry.register(HookPhase.POSTFLIGHT, "structural_health", _structural_health, priority=65)


def register_meta_learning():
    """Register meta-learning analysis hook (daily, priority 90)."""
    registry.register(HookPhase.POSTFLIGHT, "meta_learning", _meta_learning_analyze, priority=90)


def register_intrinsic_assessment():
    """Register intrinsic self-assessment hook (daily, priority 92)."""
    registry.register(HookPhase.POSTFLIGHT, "intrinsic_assessment", _intrinsic_assessment, priority=92)


def register_all():
    """Register all migrated subsystem hooks. Call once at startup."""
    register_procedural()
    register_consolidation()
    register_metrics()
    register_meta_learning()
    register_intrinsic_assessment()
