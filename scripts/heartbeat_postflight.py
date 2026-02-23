#!/usr/bin/env python3
"""
Heartbeat Post-flight — Batched outcome recording in ONE Python process.

Replaces ~10-12 separate subprocess invocations in cron_autonomous.sh's
outcome-handling paths with a single process.

SAVINGS: ~10 Python cold-starts × ~300ms each = ~3s saved per heartbeat.

Reads task context from JSON (piped from preflight or passed as arg),
plus the exit code and output file from the executor.

Usage:
    python3 heartbeat_postflight.py <exit_code> <output_file> <preflight_json_file>
    # or pipe preflight JSON via stdin:
    cat preflight.json | python3 heartbeat_postflight.py <exit_code> <output_file> -
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

# === SINGLE IMPORT BLOCK ===
start_import = time.monotonic()

from attention import attention

try:
    from clarvis_confidence import outcome as conf_outcome
except ImportError:
    conf_outcome = None

try:
    from reasoning_chain_hook import close_chain
except ImportError:
    close_chain = None

try:
    from procedural_memory import record_use, learn_from_task
except ImportError:
    record_use = None
    learn_from_task = None

try:
    from episodic_memory import EpisodicMemory
except ImportError:
    EpisodicMemory = None

try:
    from digest_writer import write_digest
except ImportError:
    write_digest = None

try:
    from task_router import log_decision, classify_task
except ImportError:
    log_decision = None
    classify_task = None

try:
    from evolution_loop import EvolutionLoop
except ImportError:
    EvolutionLoop = None

try:
    from extract_steps import extract_steps
except ImportError:
    extract_steps = None

# Cost tracking
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'packages', 'clarvis-cost'))
try:
    from clarvis_cost.core import CostTracker, estimate_tokens
    COST_LOG = os.path.join(os.path.dirname(__file__), '..', 'data', 'costs.jsonl')
    cost_tracker = CostTracker(COST_LOG)
except ImportError:
    cost_tracker = None

import_time = time.monotonic() - start_import
log = lambda msg: print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')}] POSTFLIGHT: {msg}", file=sys.stderr)
log(f"All modules imported in {import_time:.2f}s (single process)")


def run_postflight(exit_code, output_file, preflight_data, task_duration=0):
    """Run all post-execution outcome recording in a single process.

    Args:
        exit_code: int, the exit code from the executor (0=success, 124=timeout, else=failure)
        output_file: str, path to the task output file
        preflight_data: dict, the JSON output from heartbeat_preflight.py
        task_duration: int, seconds the task took
    """
    t0 = time.monotonic()
    timings = {}

    task = preflight_data.get("task", "unknown")
    task_section = preflight_data.get("task_section", "P1")
    best_salience = preflight_data.get("task_salience", 0.5)
    chain_id = preflight_data.get("chain_id")
    proc_id = preflight_data.get("procedure_id")
    task_event = preflight_data.get("prediction_event", "")
    route_executor = preflight_data.get("route_executor", "claude")

    # Read output for evidence
    output_text = ""
    try:
        if output_file and os.path.exists(output_file):
            with open(output_file, 'r', errors='replace') as f:
                output_text = f.read()
    except Exception:
        pass

    # Determine outcome
    if exit_code == 0:
        task_status = "success"
    elif exit_code == 124:
        task_status = "timeout"
    else:
        task_status = "failure"

    log(f"Recording outcome: {task_status} (exit={exit_code}, duration={task_duration}s)")

    # === 1. CONFIDENCE OUTCOME ===
    t1 = time.monotonic()
    if conf_outcome and task_event:
        try:
            actual = "success" if exit_code == 0 else "failure"
            conf_outcome(task_event, actual)
        except Exception as e:
            log(f"Confidence outcome failed: {e}")
    timings["confidence"] = round(time.monotonic() - t1, 3)

    # === 2. REASONING CHAIN: Close ===
    t2 = time.monotonic()
    if close_chain and chain_id:
        try:
            # Extract evidence from output tail
            evidence = output_text[-300:].encode('ascii', 'replace').decode()
            evidence = re.sub(r'[^a-zA-Z0-9 _.,:;=+\-/()@#%]', '', evidence)[:280]
            close_chain(chain_id, task_status, task, str(exit_code), evidence)
            log(f"Reasoning chain {chain_id} closed ({task_status})")
        except Exception as e:
            log(f"Reasoning chain close failed: {e}")
    timings["reasoning_close"] = round(time.monotonic() - t2, 3)

    # === 3. ATTENTION: Record outcome ===
    t3 = time.monotonic()
    try:
        importance = 0.8 if task_status == "success" else 0.9
        attention.submit(
            f"OUTCOME: {task_status.upper()} (exit {exit_code}) — {task[:80]}",
            source="heartbeat", importance=importance, relevance=0.8
        )
    except Exception:
        pass
    timings["attention_outcome"] = round(time.monotonic() - t3, 3)

    # === 4. PROCEDURAL MEMORY ===
    t4 = time.monotonic()
    if exit_code == 0:
        if proc_id and record_use:
            try:
                record_use(proc_id, True)
                log(f"Recorded successful use of procedure {proc_id}")
            except Exception as e:
                log(f"Procedural record_use failed: {e}")
        elif learn_from_task:
            # Try to extract steps and learn a new procedure
            try:
                steps = None
                if extract_steps:
                    steps = extract_steps(output_text)
                if steps:
                    learn_from_task(task, steps)
                    log(f"Learned new procedure from task output ({len(steps)} steps)")
                else:
                    log("Skipped procedure learning — no concrete steps extracted")
            except Exception as e:
                log(f"Procedural learning failed: {e}")
    else:
        # Record failure against procedure if used
        if proc_id and record_use:
            try:
                record_use(proc_id, False)
                log(f"Recorded failed use of procedure {proc_id}")
            except Exception as e:
                log(f"Procedural failure record failed: {e}")
    timings["procedural"] = round(time.monotonic() - t4, 3)

    # === 5. EPISODIC MEMORY: Encode episode ===
    t5 = time.monotonic()
    if EpisodicMemory:
        try:
            em = EpisodicMemory()
            error_msg = output_text[-200:] if task_status != "success" else None
            em.encode(task, task_section, best_salience, task_status,
                     duration_s=task_duration, error_msg=error_msg)
            log(f"Encoded episode ({task_status}, {task_duration}s)")
        except Exception as e:
            log(f"Episodic encoding failed: {e}")
    timings["episodic"] = round(time.monotonic() - t5, 3)

    # === 6. ATTENTION BROADCAST ===
    t6 = time.monotonic()
    try:
        attention.submit(
            f"Heartbeat task {task_status}: {task[:100]}",
            source="heartbeat",
            importance=0.7 if task_status == "success" else 0.9,
            relevance=0.8
        )
    except Exception:
        pass
    timings["attention_broadcast"] = round(time.monotonic() - t6, 3)

    # === 7. ROUTING LOG ===
    t7 = time.monotonic()
    if log_decision and classify_task:
        try:
            cl = classify_task(task)
            log_decision(task, cl, route_executor,
                        "success" if exit_code == 0 else "failure")
        except Exception as e:
            log(f"Routing log failed: {e}")
    timings["routing_log"] = round(time.monotonic() - t7, 3)

    # === 7.5 COST TRACKING ===
    t75 = time.monotonic()
    if cost_tracker:
        try:
            # Check if real cost data was passed from the executor
            real_cost = preflight_data.get("real_cost_usd")
            real_gen_id = preflight_data.get("generation_id", "")
            real_model = preflight_data.get("actual_model", "")
            real_in_tokens = preflight_data.get("actual_input_tokens")
            real_out_tokens = preflight_data.get("actual_output_tokens")

            # Determine model used
            executor = preflight_data.get("route_executor", "claude")
            if real_model:
                model = real_model
            elif executor == "gemini":
                model = "gemini-2.0-flash"
            elif executor == "openrouter":
                model = preflight_data.get("route_model", "minimax/minimax-m2.5")
            else:
                model = "claude-code"

            if real_cost is not None and real_in_tokens is not None:
                # Use REAL cost data from API response
                entry = cost_tracker.log_real(
                    model=model,
                    input_tokens=real_in_tokens,
                    output_tokens=real_out_tokens or 0,
                    cost_usd=real_cost,
                    source="cron_autonomous",
                    task=task,
                    duration_s=task_duration,
                    generation_id=real_gen_id,
                )
                log(f"Cost logged (REAL): ${entry.cost_usd:.6f} ({model}, in={real_in_tokens}, out={real_out_tokens})")
            else:
                # Fall back to estimation for Claude Code CLI calls
                context_brief = preflight_data.get("context_brief", "")
                episodic_hints = preflight_data.get("episodic_hints", "")
                input_text = f"{task} {context_brief} {episodic_hints}"
                est_input = estimate_tokens(input_text, model) + 500
                est_output = estimate_tokens(output_text[:4000], model) if output_text else 300

                entry = cost_tracker.log(
                    model=model,
                    input_tokens=est_input,
                    output_tokens=est_output,
                    source="cron_autonomous",
                    task=task,
                    duration_s=task_duration,
                )
                log(f"Cost logged (est): ${entry.cost_usd:.6f} ({model}, in={est_input}, out={est_output})")
        except Exception as e:
            log(f"Cost tracking failed: {e}")
    timings["cost_tracking"] = round(time.monotonic() - t75, 3)

    # === 7.6 BUDGET ALERT CHECK ===
    t76 = time.monotonic()
    try:
        import subprocess
        subprocess.run(
            ["python3", os.path.join(os.path.dirname(__file__), "budget_alert.py")],
            timeout=15, capture_output=True
        )
    except Exception as e:
        log(f"Budget alert check failed: {e}")
    timings["budget_alert"] = round(time.monotonic() - t76, 3)

    # === 8. EVOLUTION LOOP (failures only) ===
    t8 = time.monotonic()
    if exit_code != 0 and exit_code != 124 and EvolutionLoop:
        try:
            evo = EvolutionLoop()
            failure_id = evo.capture_failure(
                "cron_autonomous",
                f"Exit code {exit_code} running task",
                context=task,
                exit_code=exit_code,
                stderr=output_text[-2000:]
            )
            log(f"Evolution: captured failure {failure_id}")
            # Evolve
            evo.evolve(failure_id)
            log(f"Evolution: fix generated for {failure_id}")
        except Exception as e:
            log(f"Evolution loop failed: {e}")
    elif exit_code == 124 and EvolutionLoop:
        # Timeout: light capture only
        try:
            evo = EvolutionLoop()
            evo.capture_failure(
                "cron_autonomous",
                "Timeout (exit 124) — task exceeded 600s",
                context=task,
                exit_code=124
            )
            log("Evolution: timeout captured (no evolve)")
        except Exception as e:
            log(f"Evolution timeout capture failed: {e}")
    timings["evolution"] = round(time.monotonic() - t8, 3)

    # === 9. DIGEST WRITER ===
    t9 = time.monotonic()
    if write_digest:
        try:
            snippet = output_text[-200:].encode('ascii', 'replace').decode()
            snippet = re.sub(r'[^a-zA-Z0-9 _.,:;=+\-/()@#%]', '', snippet)[:180]
            write_digest("autonomous",
                        f'I executed evolution task: "{task[:120]}". '
                        f'Result: {task_status} (exit {exit_code}, {task_duration}s). '
                        f'Output: {snippet}')
            log("Digest written")
        except Exception as e:
            log(f"Digest write failed: {e}")
    timings["digest"] = round(time.monotonic() - t9, 3)

    # === 10. MARK TASK COMPLETE IN QUEUE.MD ===
    t10 = time.monotonic()
    QUEUE_FILE = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md"
    RETRY_FILE = "/home/agent/.openclaw/workspace/data/task_retries.json"
    MAX_TASK_RETRIES = 3

    def _mark_task_in_queue(task_text, annotation):
        """Mark a task as [x] in QUEUE.md with an annotation."""
        with open(QUEUE_FILE, 'r') as f:
            lines = f.readlines()
        task_prefix = task_text[:60]
        for i, line in enumerate(lines):
            if line.strip().startswith("- [ ] ") and task_prefix in line:
                lines[i] = line.replace("- [ ] ", "- [x] ", 1).rstrip() + f" ({annotation})\n"
                with open(QUEUE_FILE, 'w') as f:
                    f.writelines(lines)
                return True
        return False

    if task and task != "unknown":
        try:
            if exit_code == 0:
                # Success — mark complete
                timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                if _mark_task_in_queue(task, timestamp):
                    log("Marked task complete in QUEUE.md")
                else:
                    log(f"Task not found in QUEUE.md for completion: {task[:60]}...")
            elif exit_code == 124:
                # Timeout — track retries, mark as skipped after MAX_TASK_RETRIES
                retries = {}
                if os.path.exists(RETRY_FILE):
                    with open(RETRY_FILE) as f:
                        retries = json.load(f)
                task_key = task[:80]
                retries[task_key] = retries.get(task_key, 0) + 1
                count = retries[task_key]
                log(f"Timeout retry {count}/{MAX_TASK_RETRIES} for: {task_key}")
                if count >= MAX_TASK_RETRIES:
                    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                    if _mark_task_in_queue(task, f"{timestamp} — skipped after {count} timeouts"):
                        log(f"Auto-skipped task after {count} timeouts")
                    del retries[task_key]
                os.makedirs(os.path.dirname(RETRY_FILE), exist_ok=True)
                with open(RETRY_FILE, 'w') as f:
                    json.dump(retries, f)
        except Exception as e:
            log(f"Queue completion marking failed: {e}")
    timings["queue_update"] = round(time.monotonic() - t10, 3)

    # === 11. SAVE ATTENTION STATE ===
    try:
        attention.save()
    except Exception:
        pass

    timings["total"] = round(time.monotonic() - t0, 3)
    log(f"Post-flight complete in {timings['total']:.2f}s")

    return {"status": "ok", "task_status": task_status, "timings": timings}


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: heartbeat_postflight.py <exit_code> <output_file> <preflight_json_file>",
              file=sys.stderr)
        sys.exit(1)

    exit_code = int(sys.argv[1])
    output_file = sys.argv[2]
    preflight_file = sys.argv[3]

    # Load preflight data
    if preflight_file == "-":
        preflight_data = json.load(sys.stdin)
    else:
        with open(preflight_file) as f:
            preflight_data = json.load(f)

    # Duration passed as optional 4th arg
    task_duration = int(sys.argv[4]) if len(sys.argv) > 4 else 0

    result = run_postflight(exit_code, output_file, preflight_data, task_duration)
    print(json.dumps(result))
