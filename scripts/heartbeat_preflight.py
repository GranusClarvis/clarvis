#!/usr/bin/env python3
"""
Heartbeat Pre-flight — Batched pre-execution checks in ONE Python process.

Replaces ~15 separate subprocess invocations in cron_autonomous.sh with a single
process that imports all modules once and runs all checks sequentially.

SAVINGS: ~15 Python cold-starts × ~300ms each = ~4.5s saved per heartbeat.
Plus reduced disk I/O from fewer import scans.

Outputs JSON to stdout with all pre-flight results.
Logs to stderr for cron log capture.

Usage:
    python3 heartbeat_preflight.py              # full pre-flight
    python3 heartbeat_preflight.py --dry-run    # just print what would happen
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

# === SINGLE IMPORT BLOCK (one-time cost) ===
start_import = time.monotonic()

from attention import attention

try:
    from task_selector import parse_tasks, score_tasks
except ImportError:
    parse_tasks = None
    score_tasks = None

try:
    from cognitive_load import should_defer_task
except ImportError:
    should_defer_task = None

try:
    from procedural_memory import find_procedure
except ImportError:
    find_procedure = None

try:
    from reasoning_chain_hook import open_chain
except ImportError:
    open_chain = None

try:
    from clarvis_confidence import predict as conf_predict, dynamic_confidence
except ImportError:
    conf_predict = None
    dynamic_confidence = None

try:
    from episodic_memory import EpisodicMemory
except ImportError:
    EpisodicMemory = None

try:
    from context_compressor import generate_context_brief, generate_tiered_brief, compress_episodes
except ImportError:
    generate_context_brief = None
    generate_tiered_brief = None
    compress_episodes = None

try:
    from task_router import classify_task
except ImportError:
    classify_task = None

import_time = time.monotonic() - start_import
log = lambda msg: print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')}] PREFLIGHT: {msg}", file=sys.stderr)
log(f"All modules imported in {import_time:.2f}s (single process)")


QUEUE_FILE = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md"


def run_preflight(dry_run=False):
    """Run all pre-execution checks in a single process.

    Returns a dict with all results needed by cron_autonomous.sh.
    """
    t0 = time.monotonic()
    result = {
        "status": "ok",
        "task": None,
        "task_section": None,
        "task_salience": 0.0,
        "cognitive_load": {},
        "should_defer": False,
        "procedure": None,
        "procedure_id": None,
        "chain_id": None,
        "prediction_event": None,
        "prediction_confidence": 0.7,
        "episodic_hints": "",
        "context_brief": "",
        "route_tier": "complex",
        "route_executor": "claude",
        "route_score": 0.5,
        "route_reason": "unknown",
        "timings": {},
    }

    # === 1. ATTENTION: Load + Tick ===
    t1 = time.monotonic()
    try:
        attention._load()
        attention.tick()
        log("Attention load+tick done")
    except Exception as e:
        log(f"Attention load+tick failed: {e}")
    result["timings"]["attention_tick"] = round(time.monotonic() - t1, 3)

    # === 2. TASK SELECTION ===
    t2 = time.monotonic()
    next_task = None
    task_section = "P1"
    best_salience = 0.0

    if parse_tasks and score_tasks:
        try:
            tasks = parse_tasks()
            if not tasks:
                result["status"] = "queue_empty"
                log("Queue empty — no tasks to execute")
                result["timings"]["total"] = round(time.monotonic() - t0, 3)
                return result

            # Score all tasks using attention salience (returns list sorted by salience)
            scored = score_tasks(tasks)

            best_task = scored[0]
            best_salience = best_task.get("salience", 0.0)
            next_task = best_task.get("text", "")
            task_section = best_task.get("section", "P1")
            log(f"Selected task (salience={best_salience:.3f}): {next_task[:80]}...")
        except Exception as e:
            log(f"Task selector failed: {e}")

    # Fallback: grep first unchecked task
    if not next_task:
        try:
            import re
            with open(QUEUE_FILE) as f:
                for line in f:
                    m = re.match(r'^- \[ \] (.+)$', line.strip())
                    if m:
                        next_task = m.group(1)
                        log(f"Fallback task: {next_task[:80]}...")
                        break
        except Exception as e:
            log(f"Fallback task search failed: {e}")

    if not next_task:
        result["status"] = "no_tasks"
        result["timings"]["total"] = round(time.monotonic() - t0, 3)
        return result

    result["task"] = next_task
    result["task_section"] = task_section
    result["task_salience"] = round(best_salience, 4)
    result["timings"]["task_selection"] = round(time.monotonic() - t2, 3)

    if dry_run:
        result["timings"]["total"] = round(time.monotonic() - t0, 3)
        return result

    # === 3. ATTENTION: Add task context ===
    try:
        attention.submit(f"CURRENT TASK: {next_task}", source="heartbeat",
                        importance=0.9, relevance=0.8)
    except Exception:
        pass

    # === 4. COGNITIVE LOAD CHECK ===
    t4 = time.monotonic()
    if should_defer_task:
        try:
            defer, load_info = should_defer_task(task_section)
            result["should_defer"] = defer
            result["cognitive_load"] = load_info if isinstance(load_info, dict) else {"raw": str(load_info)}
            if defer:
                log(f"Cognitive load: DEFER — {load_info}")
                try:
                    attention.submit(f"DEFERRED due to cognitive load: {next_task[:80]}",
                                   source="heartbeat", importance=0.6)
                except Exception:
                    pass
                result["timings"]["total"] = round(time.monotonic() - t0, 3)
                return result
            else:
                log(f"Cognitive load: OK — {load_info}")
        except Exception as e:
            log(f"Cognitive load check failed: {e}")
    result["timings"]["cognitive_load"] = round(time.monotonic() - t4, 3)

    # === 5. PROCEDURAL MEMORY: Check for matching procedure ===
    t5 = time.monotonic()
    if find_procedure:
        try:
            proc = find_procedure(next_task)
            if proc:
                result["procedure"] = proc
                result["procedure_id"] = proc.get("id", "")
                log(f"Procedure hit: {proc.get('id', '?')} (success rate: {proc.get('success_rate', 0):.0%})")
                try:
                    attention.submit(
                        f"PROCEDURE HIT ({proc.get('id', '?')}, {proc.get('success_rate', 0):.0%} success)",
                        source="heartbeat", importance=0.7)
                except Exception:
                    pass
        except Exception as e:
            log(f"Procedural memory check failed: {e}")
    result["timings"]["procedural"] = round(time.monotonic() - t5, 3)

    # === 6. REASONING CHAIN: Open ===
    t6 = time.monotonic()
    if open_chain:
        try:
            chain_id = open_chain(next_task, task_section, str(best_salience))
            result["chain_id"] = chain_id
            log(f"Reasoning chain opened: {chain_id}")
            try:
                attention.submit(f"REASONING CHAIN: {chain_id} tracking current task",
                               source="heartbeat", importance=0.4)
            except Exception:
                pass
        except Exception as e:
            log(f"Reasoning chain open failed: {e}")
    result["timings"]["reasoning_open"] = round(time.monotonic() - t6, 3)

    # === 7. CONFIDENCE PREDICTION ===
    t7 = time.monotonic()
    import re as _re
    task_event = _re.sub(r'[^a-zA-Z0-9]', '_', next_task[:60])
    result["prediction_event"] = task_event

    if dynamic_confidence:
        try:
            dyn_conf = dynamic_confidence()
            result["prediction_confidence"] = dyn_conf
        except Exception:
            dyn_conf = 0.7
    else:
        dyn_conf = 0.7

    if conf_predict:
        try:
            conf_predict(task_event, "success", dyn_conf)
            log(f"Prediction logged: {task_event} @ {dyn_conf:.0%}")
        except Exception as e:
            log(f"Prediction logging failed: {e}")
    result["timings"]["confidence"] = round(time.monotonic() - t7, 3)

    # === 8. EPISODIC MEMORY: Recall similar episodes ===
    t8 = time.monotonic()
    similar_episodes = ""
    failure_episodes = ""

    if EpisodicMemory:
        try:
            em = EpisodicMemory()
            similar = em.recall_similar(next_task, n=5)
            if similar:
                similar_episodes = "\n".join(
                    f"  [{e.get('outcome', '?')}] {e.get('task', '')[:80]}"
                    for e in (similar if isinstance(similar, list) else [similar])
                )[:500]

            failures = em.recall_failures(n=3)
            if failures:
                failure_episodes = "\n".join(
                    f"  [{e.get('outcome', '?')}] {e.get('task', '')[:80]}"
                    for e in (failures if isinstance(failures, list) else [failures])
                )[:300]
        except Exception as e:
            log(f"Episodic recall failed: {e}")
    result["timings"]["episodic"] = round(time.monotonic() - t8, 3)

    # === 9. TASK ROUTING (moved before context compression to inform tier) ===
    t9 = time.monotonic()
    if classify_task:
        try:
            cl = classify_task(next_task)
            result["route_tier"] = cl.get("tier", "complex")
            result["route_executor"] = cl.get("executor", "claude")
            result["route_score"] = cl.get("score", 0.5)
            result["route_reason"] = cl.get("reason", "unknown")
            log(f"Route: tier={result['route_tier']} executor={result['route_executor']} score={result['route_score']}")
        except Exception as e:
            log(f"Task classification failed: {e}")
    result["timings"]["routing"] = round(time.monotonic() - t9, 3)

    # === 10. CONTEXT COMPRESSION (uses routing tier for budget) ===
    t10 = time.monotonic()

    # Compress episodic hints first (needed by tiered brief)
    compressed_episodes = ""
    if (similar_episodes or failure_episodes) and compress_episodes:
        try:
            compressed_episodes = compress_episodes(similar_episodes, failure_episodes)
            if not compressed_episodes:
                compressed_episodes = f"{similar_episodes}\n---\n{failure_episodes}"
        except Exception:
            compressed_episodes = f"{similar_episodes}\n---\n{failure_episodes}"
    elif similar_episodes or failure_episodes:
        compressed_episodes = f"{similar_episodes}\n---\n{failure_episodes}"

    # Generate tiered brief (adapts to executor)
    context_brief = ""
    executor = result["route_executor"]
    if generate_tiered_brief:
        try:
            # Map executor to brief tier
            brief_tier = {
                "openrouter": "minimal",
                "gemini": "minimal",
                "claude": "full" if result["route_tier"] in ("complex", "reasoning") else "standard",
            }.get(executor, "standard")

            context_brief = generate_tiered_brief(
                current_task=next_task,
                tier=brief_tier,
                episodic_hints=compressed_episodes,
            )
            log(f"Tiered brief ({brief_tier}): {len(context_brief)} bytes")
        except Exception as e:
            log(f"Tiered brief failed, falling back to legacy: {e}")
            # Fallback to legacy brief
            if generate_context_brief:
                try:
                    context_brief = generate_context_brief()
                except Exception:
                    pass
    elif generate_context_brief:
        try:
            context_brief = generate_context_brief()
            log(f"Context brief (legacy): {len(context_brief)} bytes")
        except Exception as e:
            log(f"Context compression failed: {e}")

    result["episodic_hints"] = compressed_episodes
    result["context_brief"] = context_brief
    result["timings"]["context"] = round(time.monotonic() - t10, 3)

    # === SAVE ATTENTION STATE ===
    try:
        attention.save()
    except Exception:
        pass

    result["timings"]["total"] = round(time.monotonic() - t0, 3)
    log(f"Pre-flight complete in {result['timings']['total']:.2f}s")
    return result


def format_proc_hint(proc):
    """Format a procedure match into the hint string expected by the prompt."""
    if not proc:
        return ""
    steps = proc.get("steps", [])
    if not steps:
        return ""
    steps_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(steps))
    rate = f"{proc.get('success_rate', 0):.0%}"
    return f"""
    PROCEDURAL MEMORY HIT: A similar task was done before (success rate: {rate}). Suggested steps:
{steps_text}
    Use these steps as a starting guide, adapt as needed."""


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    result = run_preflight(dry_run=dry_run)
    # JSON to stdout for bash to capture
    print(json.dumps(result))
