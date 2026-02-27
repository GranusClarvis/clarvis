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

try:
    from benchmark_brief import record as benchmark_record
except ImportError:
    benchmark_record = None

try:
    from performance_benchmark import run_heartbeat_check as perf_heartbeat_check
except ImportError:
    perf_heartbeat_check = None

try:
    from world_models import HierarchicalWorldModel
except ImportError:
    HierarchicalWorldModel = None

try:
    from meta_gradient_rl import adapt as meta_gradient_adapt
except ImportError:
    meta_gradient_adapt = None

try:
    from self_representation import postflight_update as self_rep_update
except ImportError:
    self_rep_update = None

try:
    from self_model import think_about_thinking
except ImportError:
    think_about_thinking = None

try:
    from soar_engine import get_soar as get_soar_engine
except ImportError:
    get_soar_engine = None

try:
    from hyperon_atomspace import get_atomspace
except ImportError:
    get_atomspace = None

try:
    from workspace_broadcast import WorkspaceBroadcast
except ImportError:
    WorkspaceBroadcast = None

try:
    from brain_bridge import brain_record_outcome, brain_update_context
except ImportError:
    brain_record_outcome = None
    brain_update_context = None

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

    # Shared constants used by multiple sections
    QUEUE_FILE = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md"
    RETRY_FILE = "/home/agent/.openclaw/workspace/data/task_retries.json"
    MAX_TASK_RETRIES = 3

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

    # === 2.5 FAILURE LESSONS: Store in brain + generate follow-up task ===
    t25 = time.monotonic()
    if task_status == "failure" and exit_code != 0 and exit_code != 124:
        try:
            # Store a concise lesson in brain
            error_snippet = output_text[-300:] if output_text else "no output"
            error_snippet = re.sub(r'[^a-zA-Z0-9 _.,:;=+\-/()@#%\n]', '', error_snippet)[:250]
            lesson = f"FAILURE LESSON: Attempted '{task[:100]}' — exit {exit_code}. Error: {error_snippet}"
            brain_mod = None
            try:
                from brain import brain as brain_mod
            except ImportError:
                pass
            if brain_mod:
                brain_mod.store(
                    lesson,
                    collection="clarvis-learnings",
                    importance=0.8,
                    tags=["failure", "lesson"],
                    source="postflight_failure"
                )
                log("Stored failure lesson in brain")

            # Generate a follow-up investigation task (max 1 per cycle)
            # Check retry count to avoid infinite failure loops
            retry_data = {}
            if os.path.exists(RETRY_FILE):
                try:
                    with open(RETRY_FILE) as rf:
                        retry_data = json.load(rf)
                except Exception:
                    pass
            task_key = task[:80]
            failure_count = retry_data.get(task_key, 0)

            if failure_count < 2:  # Only generate follow-up if <2 prior failures
                try:
                    from queue_writer import add_task
                    followup = f"Investigate failure: '{task[:80]}' failed with exit {exit_code}. Check logs and fix root cause."
                    added = add_task(followup, priority="P1", source="reasoning_failure")
                    if added:
                        log("Generated follow-up investigation task")
                except ImportError:
                    pass
            else:
                log(f"Skipped follow-up task — {task_key[:40]}... failed {failure_count}+ times")
        except Exception as e:
            log(f"Failure lesson recording failed: {e}")
    timings["failure_lessons"] = round(time.monotonic() - t25, 3)

    # === 2.7 BRAIN BRIDGE: Record ALL outcomes + update context ===
    t27 = time.monotonic()
    if brain_record_outcome:
        try:
            mem_id = brain_record_outcome(task, task_status, output_text, task_duration)
            if mem_id:
                log(f"Brain bridge: recorded {task_status} outcome → {mem_id}")
        except Exception as e:
            log(f"Brain bridge outcome recording failed: {e}")
    if brain_update_context:
        try:
            brain_update_context(task, task_status)
            log("Brain bridge: context updated")
        except Exception as e:
            log(f"Brain bridge context update failed: {e}")
    timings["brain_bridge"] = round(time.monotonic() - t27, 3)

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
                    # Truncate to last 2000 chars — extract_steps looks at the
                    # summary line near the end; a huge blob confuses the splitter
                    extraction_text = output_text[-2000:] if len(output_text) > 2000 else output_text
                    steps = extract_steps(extraction_text)
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

    # === 5.5 WORLD MODEL: Record outcome for prediction accuracy ===
    t55 = time.monotonic()
    if HierarchicalWorldModel:
        try:
            wm = HierarchicalWorldModel()
            wm.record_outcome(task, task_status)
            log(f"World model: recorded outcome '{task_status}' for prediction calibration")
        except Exception as e:
            log(f"World model outcome recording failed: {e}")
    timings["world_model"] = round(time.monotonic() - t55, 3)

    # === 5.6 META-GRADIENT RL: Adapt hyperparameters online ===
    t56 = time.monotonic()
    if meta_gradient_adapt:
        try:
            mg_result = meta_gradient_adapt()
            mg_status = mg_result.get("status", "unknown")
            if mg_status == "complete":
                adapt_info = mg_result.get("adapt_info", {})
                J = adapt_info.get("J_validation", 0)
                log(f"Meta-gradient: adapted (J={J:.3f})")
            else:
                log(f"Meta-gradient: {mg_status}")
        except Exception as e:
            log(f"Meta-gradient adaptation failed: {e}")
    timings["meta_gradient_rl"] = round(time.monotonic() - t56, 3)

    # === 5.7 SELF-REPRESENTATION: Update latent self-state + anticipatory predictions ===
    t57 = time.monotonic()
    if self_rep_update:
        try:
            sr_result = self_rep_update(task_status, task_text=task, duration_s=task_duration)
            sr_pred = sr_result.get("anticipation", {}).get("p_next_success")
            log(f"Self-representation: updated (p_next={sr_pred})")
        except Exception as e:
            log(f"Self-representation update failed: {e}")
    timings["self_representation"] = round(time.monotonic() - t57, 3)

    # === 5.75 META-THOUGHT: Generate self-reflective thought about this task ===
    t575 = time.monotonic()
    if think_about_thinking:
        try:
            if task_status == "success":
                thought = (
                    f"Completed '{task[:80]}' successfully in {task_duration}s. "
                    f"Executor: {route_executor}."
                )
            elif task_status == "timeout":
                thought = (
                    f"Task '{task[:80]}' timed out after {task_duration}s — "
                    f"may need decomposition or longer budget."
                )
            else:
                thought = (
                    f"Task '{task[:80]}' failed (exit {exit_code}). "
                    f"Need to investigate root cause."
                )
            think_about_thinking(thought)
            log(f"Meta-thought recorded: {task_status}")
        except Exception as e:
            log(f"Meta-thought generation failed: {e}")
    timings["meta_thought"] = round(time.monotonic() - t575, 3)

    # === 5.8 SOAR ENGINE: Update goal stack with task outcome ===
    t58 = time.monotonic()
    if get_soar_engine:
        try:
            soar = get_soar_engine()
            current = soar.current_goal()
            if current:
                alignment = soar.align_task(task)
                if alignment.get("aligned"):
                    # Task aligned with current goal — record outcome
                    ops = current.get("operators_proposed", [])
                    if ops:
                        soar.apply_outcome(ops[0].get("id", ""), task_status,
                                          details=f"exit={exit_code}, duration={task_duration}s")
                    log(f"SOAR: outcome recorded for goal '{current['name'][:40]}' ({task_status})")
                else:
                    log("SOAR: task not aligned with current goal")
            else:
                log("SOAR: no active goal")
        except Exception as e:
            log(f"SOAR engine update failed: {e}")
    timings["soar_engine"] = round(time.monotonic() - t58, 3)

    # === 5.9 ATOMSPACE: Register task as context + link outcome ===
    t59 = time.monotonic()
    if get_atomspace:
        try:
            atoms = get_atomspace()
            task_node = atoms.add_node("ConceptNode", task[:100],
                                       tv={"strength": 0.8, "confidence": 0.6},
                                       av={"sti": 3.0, "lti": 1.0})
            outcome_node = atoms.add_node("ConceptNode", f"outcome:{task_status}",
                                          tv={"strength": 1.0, "confidence": 0.9})
            atoms.add_link("EvaluationLink", [task_node, outcome_node],
                          tv={"strength": 1.0 if task_status == "success" else 0.2,
                              "confidence": 0.8})
            atoms.decay_attention(0.97)
            log(f"AtomSpace: registered task outcome ({atoms.stats()['total_atoms']} atoms)")
        except Exception as e:
            log(f"AtomSpace update failed: {e}")
    timings["atomspace"] = round(time.monotonic() - t59, 3)

    # === 5.95 GWT WORKSPACE: Submit outcome as codelet for next cycle ===
    t595 = time.monotonic()
    if WorkspaceBroadcast:
        try:
            # Submit outcome as high-salience codelet — will be picked up by next cycle's collect()
            from attention import attention as attn_module
            outcome_importance = 0.85 if task_status == "success" else 0.95
            attn_module.submit(
                f"OUTCOME [{task_status}]: {task[:100]} (exit={exit_code}, {task_duration}s)",
                source="gwt_outcome",
                importance=outcome_importance,
                relevance=0.9,
            )
            log("GWT: outcome codelet submitted for next broadcast cycle")
        except Exception as e:
            log(f"GWT outcome submission failed: {e}")
    timings["gwt_outcome"] = round(time.monotonic() - t595, 3)

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

    # === 7.25 BENCHMARK: Brief v2 quality tracking ===
    t725 = time.monotonic()
    if benchmark_record:
        try:
            benchmark_record(preflight_data, exit_code, task_duration)
            log("Benchmark: brief v2 entry recorded")
        except Exception as e:
            log(f"Benchmark recording failed: {e}")
    timings["benchmark"] = round(time.monotonic() - t725, 3)

    # === 7.3 PERFORMANCE BENCHMARK: Quick health check ===
    t73 = time.monotonic()
    if perf_heartbeat_check:
        try:
            perf_result = perf_heartbeat_check()
            if not perf_result.get("speed_ok", True):
                log(f"PERF WARNING: brain query avg {perf_result.get('brain_query_avg_ms', '?')}ms exceeds critical threshold")
            else:
                log(f"PERF: query={perf_result.get('brain_query_avg_ms', '?')}ms, "
                    f"memories={perf_result.get('brain_memories', '?')}, "
                    f"density={perf_result.get('graph_density', '?')}, "
                    f"prev_pi={perf_result.get('prev_pi', 'N/A')}")
        except Exception as e:
            log(f"Performance heartbeat check failed: {e}")
    timings["perf_benchmark"] = round(time.monotonic() - t73, 3)

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
            elif executor in ("gemini", "openrouter"):
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
                f"Timeout (exit 124) — task exceeded {task_duration}s",
                context=task,
                exit_code=124
            )
            log("Evolution: timeout captured (no evolve)")
        except Exception as e:
            log(f"Evolution timeout capture failed: {e}")
    timings["evolution"] = round(time.monotonic() - t8, 3)

    # === 8.5 PERIODIC SYNTHESIS: Re-analyze episode patterns every 10th run ===
    t85_synth = time.monotonic()
    if EpisodicMemory:
        try:
            em_synth = EpisodicMemory()
            # Run synthesis every 10 episodes (cheap, keeps insights fresh)
            if len(em_synth.episodes) % 10 == 0 and len(em_synth.episodes) > 0:
                synth = em_synth.synthesize()
                log(f"Periodic synthesis: {synth.get('goals_count', 0)} goals, "
                    f"success_rate={synth.get('success_rate', '?')}")
                # Also backfill causal links
                backfilled = em_synth.backfill_causal_links()
                if backfilled:
                    log(f"Causal backfill: +{backfilled} links")
        except Exception as e:
            log(f"Periodic synthesis failed: {e}")
    timings["periodic_synthesis"] = round(time.monotonic() - t85_synth, 3)

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

    # === 12. QUEUE HYGIENE: Archive completed items ===
    try:
        from queue_writer import archive_completed
        archived = archive_completed()
        if archived > 0:
            log(f"Queue hygiene: archived {archived} completed items")
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
