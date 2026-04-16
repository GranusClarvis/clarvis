#!/usr/bin/env python3
"""
Cognitive Stack A/B Test — full pipeline vs raw retrieval+LLM baseline.

Runs 5 tasks through:
  A) Full heartbeat preflight (17 cognitive stages)
  B) Raw baseline (brain.recall only + minimal prompt)

Measures: context size, latency, retrieval count, relevance scores.
Records results to data/benchmarks/cognitive_ab_test.json.
"""

import json
import os
import sys
import time

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE",
    os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(WORKSPACE, ".."))

TEST_TASKS = [
    {
        "id": "fix_graph_verify",
        "text": "Fix brain_hygiene.py crash when calling graph-verify",
        "section": "P1",
        "domain": "infrastructure",
    },
    {
        "id": "phi_cross_link",
        "text": "Run targeted bulk_cross_link on all 45 collection pairs to boost Phi integration",
        "section": "P2",
        "domain": "memory",
    },
    {
        "id": "dream_engine_fix",
        "text": "Fix dream_engine.py NoneType crash in compute_surprise()",
        "section": "P2",
        "domain": "code",
    },
    {
        "id": "reasoning_depth",
        "text": "Execute a multi-hop reasoning challenge requiring 3+ inference steps",
        "section": "P1",
        "domain": "research",
    },
    {
        "id": "context_relevance",
        "text": "Raise DYCP_DEFAULT_SUPPRESS_CONTAINMENT_OVERRIDE from 0.10 to 0.20 for gwt_broadcast",
        "section": "P1",
        "domain": "code",
    },
]


def run_baseline(task_text):
    """Raw retrieval + minimal prompt — no cognitive modules."""
    t0 = time.monotonic()
    from clarvis.brain import get_brain
    b = get_brain()

    results = b.recall(task_text, n=5)
    elapsed = time.monotonic() - t0

    knowledge_lines = []
    for mem in results:
        doc = mem.get("document", "")[:200]
        sim = mem.get("similarity", 0)
        knowledge_lines.append(f"  [{sim:.2f}] {doc}")

    brief = f"TASK: {task_text}\n\nRELEVANT KNOWLEDGE:\n" + "\n".join(knowledge_lines) + "\n\nExecute the task."

    return {
        "variant": "baseline",
        "brief_size_bytes": len(brief.encode()),
        "brief_lines": brief.count("\n") + 1,
        "retrieval_count": len(results),
        "avg_similarity": round(sum(m.get("similarity", 0) for m in results) / max(len(results), 1), 3),
        "top_similarity": round(max((m.get("similarity", 0) for m in results), default=0), 3),
        "latency_s": round(elapsed, 3),
        "modules_used": ["brain.recall"],
        "brief_preview": brief[:300],
    }


def run_full_stack(task_text, task_section="P1"):
    """Full cognitive stack via heartbeat_preflight."""
    t0 = time.monotonic()

    os.environ["CLARVIS_PREFLIGHT_TASK_OVERRIDE"] = task_text
    os.environ["CLARVIS_PREFLIGHT_SECTION_OVERRIDE"] = task_section

    try:
        sys.path.insert(0, os.path.join(WORKSPACE, "scripts", "pipeline"))
        from heartbeat_preflight import run_preflight
        result = run_preflight(dry_run=False)
    except Exception as e:
        elapsed = time.monotonic() - t0
        return {
            "variant": "full_stack",
            "error": str(e),
            "latency_s": round(elapsed, 3),
            "modules_used": ["error"],
        }
    finally:
        os.environ.pop("CLARVIS_PREFLIGHT_TASK_OVERRIDE", None)
        os.environ.pop("CLARVIS_PREFLIGHT_SECTION_OVERRIDE", None)

    elapsed = time.monotonic() - t0
    brief = result.get("context_brief", "")
    timings = result.get("timings", {})

    modules_used = []
    if timings.get("attention", 0) > 0:
        modules_used.append("attention")
    if timings.get("task_selection", 0) > 0:
        modules_used.append("task_selection")
    if timings.get("cognitive_load", 0) > 0:
        modules_used.append("cognitive_load")
    if timings.get("procedural", 0) > 0:
        modules_used.append("procedural_memory")
    if timings.get("reasoning_open", 0) > 0:
        modules_used.append("reasoning_chain")
    if timings.get("confidence", 0) > 0:
        modules_used.append("confidence")
    if timings.get("gwt_broadcast", 0) > 0:
        modules_used.append("gwt_broadcast")
    if timings.get("episodic", 0) > 0:
        modules_used.append("episodic_memory")
    if timings.get("brain_bridge", 0) > 0:
        modules_used.append("brain_bridge")
    if timings.get("synaptic", 0) > 0:
        modules_used.append("synaptic_memory")
    if timings.get("context_assembly", 0) > 0:
        modules_used.append("context_assembly")
    if timings.get("dycp", 0) > 0:
        modules_used.append("dycp")

    return {
        "variant": "full_stack",
        "brief_size_bytes": len(brief.encode()) if isinstance(brief, str) else 0,
        "brief_lines": brief.count("\n") + 1 if isinstance(brief, str) else 0,
        "retrieval_count": len(result.get("brain_results", [])),
        "avg_similarity": 0,
        "top_similarity": 0,
        "latency_s": round(elapsed, 3),
        "modules_used": modules_used,
        "confidence_tier": result.get("confidence_tier", "unknown"),
        "route_tier": result.get("route_tier", "unknown"),
        "timings": timings,
        "brief_preview": (brief[:300] if isinstance(brief, str) else ""),
    }


def main():
    print("=" * 60)
    print("COGNITIVE STACK A/B TEST")
    print(f"Tasks: {len(TEST_TASKS)} | Variants: baseline, full_stack")
    print("=" * 60)

    results = []

    for i, task in enumerate(TEST_TASKS, 1):
        print(f"\n--- Task {i}/{len(TEST_TASKS)}: {task['id']} ---")
        print(f"  Text: {task['text'][:80]}")

        print("  [B] Running baseline...")
        baseline = run_baseline(task["text"])
        print(f"      latency={baseline['latency_s']}s  brief={baseline['brief_size_bytes']}B  "
              f"retrievals={baseline['retrieval_count']}  avg_sim={baseline['avg_similarity']}")

        print("  [A] Running full stack...")
        full = run_full_stack(task["text"], task["section"])
        fs_lat = full.get("latency_s", "err")
        fs_size = full.get("brief_size_bytes", 0)
        fs_mods = len(full.get("modules_used", []))
        print(f"      latency={fs_lat}s  brief={fs_size}B  modules={fs_mods}")

        entry = {
            "task_id": task["id"],
            "task_text": task["text"],
            "domain": task["domain"],
            "baseline": baseline,
            "full_stack": full,
            "delta": {
                "brief_size_ratio": round(fs_size / max(baseline["brief_size_bytes"], 1), 2),
                "latency_ratio": round(full.get("latency_s", 0) / max(baseline["latency_s"], 0.001), 2),
                "extra_modules": fs_mods - 1,
            },
        }
        results.append(entry)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    avg_baseline_lat = sum(r["baseline"]["latency_s"] for r in results) / len(results)
    avg_full_lat = sum(r["full_stack"].get("latency_s", 0) for r in results) / len(results)
    avg_baseline_size = sum(r["baseline"]["brief_size_bytes"] for r in results) / len(results)
    avg_full_size = sum(r["full_stack"].get("brief_size_bytes", 0) for r in results) / len(results)
    avg_baseline_sim = sum(r["baseline"]["avg_similarity"] for r in results) / len(results)

    print(f"\nBaseline avg: {avg_baseline_lat:.2f}s latency, {avg_baseline_size:.0f}B brief, {avg_baseline_sim:.3f} avg sim")
    print(f"Full stack avg: {avg_full_lat:.2f}s latency, {avg_full_size:.0f}B brief")
    print(f"Overhead: {avg_full_lat - avg_baseline_lat:.2f}s ({avg_full_lat/max(avg_baseline_lat, 0.001):.1f}x)")
    print(f"Context enrichment: {avg_full_size/max(avg_baseline_size, 1):.1f}x more context")

    all_modules = set()
    for r in results:
        all_modules.update(r["full_stack"].get("modules_used", []))
    print(f"Modules activated: {sorted(all_modules)}")

    conclusion = {
        "question": "Does the 22-module architecture produce better reasoning than a simple pipeline?",
        "baseline_avg_latency_s": round(avg_baseline_lat, 3),
        "full_stack_avg_latency_s": round(avg_full_lat, 3),
        "latency_overhead_s": round(avg_full_lat - avg_baseline_lat, 3),
        "baseline_avg_brief_bytes": round(avg_baseline_size),
        "full_stack_avg_brief_bytes": round(avg_full_size),
        "context_enrichment_ratio": round(avg_full_size / max(avg_baseline_size, 1), 2),
        "modules_activated": sorted(all_modules),
        "verdict": "pending_execution_quality_check",
    }

    output = {
        "test_date": time.strftime("%Y-%m-%d %H:%M"),
        "task_count": len(TEST_TASKS),
        "results": results,
        "summary": conclusion,
    }

    out_path = os.path.join(WORKSPACE, "data", "benchmarks", "cognitive_ab_test.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")

    return output


if __name__ == "__main__":
    main()
