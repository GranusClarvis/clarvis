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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# === LIFECYCLE HOOKS: explicit registration replaces import-time wiring ===
try:
    from clarvis.heartbeat.hooks import registry as hook_registry, HookPhase
    from clarvis.heartbeat.adapters import register_all as _register_hooks
    _register_hooks()
    _hooks_available = True
except ImportError:
    hook_registry = None
    HookPhase = None
    _hooks_available = False

# === SINGLE IMPORT BLOCK ===
start_import = time.monotonic()

from attention import attention, get_attention_schema

try:
    from clarvis_confidence import outcome as conf_outcome, auto_resolve as conf_auto_resolve
except ImportError:
    conf_outcome = None
    conf_auto_resolve = None

try:
    from prediction_resolver import resolve_with_episodes as pred_resolve_enhanced
except ImportError:
    pred_resolve_enhanced = None

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
    from clarvis.orch.router import log_decision, classify_task
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
    from performance_gate import run_gate as perf_gate_run
except ImportError:
    perf_gate_run = None

try:
    from latency_budget import quick_check as latency_quick_check
except ImportError:
    latency_quick_check = None

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

try:
    from cognitive_workspace import workspace as cog_workspace
except ImportError:
    cog_workspace = None

try:
    from tool_maker import postflight_extract as tool_maker_extract
except ImportError:
    tool_maker_extract = None

try:
    from import_health import build_import_graph, full_report as import_health_report, SCRIPTS_DIR as IH_SCRIPTS_DIR
except ImportError:
    build_import_graph = None
    import_health_report = None
    IH_SCRIPTS_DIR = None

try:
    from retrieval_quality import tracker as rq_tracker
except ImportError:
    rq_tracker = None

try:
    from clarvis.brain.retrieval_feedback import record_feedback as retrieval_record_feedback
except ImportError:
    retrieval_record_feedback = None

try:
    from clarvis.brain.memory_evolution import record_recall_success as mem_evo_recall_success
    from clarvis.brain.memory_evolution import find_contradictions as mem_evo_find_contradictions
    from clarvis.brain.memory_evolution import evolve_memory as mem_evo_evolve
except ImportError:
    mem_evo_recall_success = None
    mem_evo_find_contradictions = None
    mem_evo_evolve = None

try:
    from prompt_optimizer import record_outcome as po_record_outcome
except ImportError:
    po_record_outcome = None

try:
    from clarvis.cognition.context_relevance import score_section_relevance, record_relevance as cr_record
except ImportError:
    score_section_relevance = None
    cr_record = None

try:
    from clarvis.context.adaptive_mmr import classify_mmr_category, update_lambdas as mmr_update_lambdas
except ImportError:
    classify_mmr_category = None
    mmr_update_lambdas = None

try:
    from clarvis.metrics.code_validation import validate_python_file as cv_validate_file, validate_output as cv_validate_output
except ImportError:
    cv_validate_file = None
    cv_validate_output = None

# Cost tracking
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'packages', 'clarvis-cost'))
try:
    from clarvis_cost.core import CostTracker, estimate_tokens
    COST_LOG = os.path.join(os.path.dirname(__file__), '..', 'data', 'costs.jsonl')
    cost_tracker = CostTracker(COST_LOG)
except ImportError:
    cost_tracker = None

_import_time = time.monotonic() - start_import
log = lambda msg: print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')}] POSTFLIGHT: {msg}", file=sys.stderr)


def _classify_error(exit_code, output_text):
    """Classify error into one of 5 categories using keyword matching on output.

    Categories:
      - timeout: exit code 124 or timeout-related keywords
      - memory: ChromaDB, embedding, brain, recall failures
      - planning: task selection, queue, routing, preflight failures
      - system: OS, network, permissions, disk, import errors
      - action: everything else (code errors, assertion failures, etc.)

    Returns: (error_type: str, evidence: str)
    """
    if exit_code == 124:
        return "timeout", "exit code 124"

    text_lower = (output_text or "")[-3000:].lower()

    # Memory-related keywords
    memory_kw = [
        "chromadb", "chroma", "embedding", "brain.store", "brain.recall",
        "collection", "vector", "onnx", "recall failed", "store failed",
        "memory_consolidation", "hebbian", "graph edge", "relationships.json",
    ]
    memory_hits = sum(1 for kw in memory_kw if kw in text_lower)
    if memory_hits >= 2:
        return "memory", f"{memory_hits} memory keywords matched"

    # Planning-related keywords
    planning_kw = [
        "task_selector", "queue.md", "preflight", "routing", "attention",
        "salience", "task selection", "no tasks", "queue empty",
        "codelet", "spotlight", "score_tasks",
    ]
    planning_hits = sum(1 for kw in planning_kw if kw in text_lower)
    if planning_hits >= 2:
        return "planning", f"{planning_hits} planning keywords matched"

    # System-related keywords
    system_kw = [
        "permission denied", "no such file", "filenotfounderror", "oserror",
        "connectionerror", "timeout", "disk", "importerror", "modulenotfounderror",
        "killed", "oom", "memory error", "segfault", "errno",
        "subprocess", "command not found", "systemctl",
    ]
    system_hits = sum(1 for kw in system_kw if kw in text_lower)
    if system_hits >= 2:
        return "system", f"{system_hits} system keywords matched"

    # Default: action error (code bug, assertion, logic error)
    return "action", "default classification"


def run_postflight(exit_code, output_file, preflight_data, task_duration=0):
    """Run all post-execution outcome recording in a single process.

    Args:
        exit_code: int, the exit code from the executor (0=success, 124=timeout, else=failure)
        output_file: str, path to the task output file
        preflight_data: dict, the JSON output from heartbeat_preflight.py
        task_duration: int, seconds the task took
    """
    log(f"All modules imported in {_import_time:.2f}s (single process)")
    t0 = time.monotonic()
    timings = {}
    _pf_errors = []  # Track stage failures for completeness scoring

    # Shared constants used by multiple sections
    QUEUE_FILE = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md"
    QUEUE_ARCHIVE = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE_ARCHIVE.md"
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

    # Classify error type for failure taxonomy
    error_type = None
    if task_status != "success":
        error_type, error_evidence = _classify_error(exit_code, output_text)
        log(f"Error taxonomy: {error_type} ({error_evidence})")

    # === 1. CONFIDENCE OUTCOME ===
    t1 = time.monotonic()
    if conf_outcome and task_event:
        try:
            actual = "success" if exit_code == 0 else "failure"
            conf_outcome(task_event, actual)
        except Exception as e:
            log(f"Confidence outcome failed: {e}")
            _pf_errors.append("confidence")
    timings["confidence"] = round(time.monotonic() - t1, 3)

    # === 1.5 AST: Evaluate attention schema prediction ===
    t15 = time.monotonic()
    try:
        schema = get_attention_schema()
        # Determine actual domain from codelet data
        actual_domain = preflight_data.get("codelet_winner", "unknown")
        eval_result = schema.evaluate_prediction(actual_domain, task)
        if "error" not in eval_result:
            log(f"AST eval: accuracy={eval_result['accuracy']:.3f} "
                f"domain_correct={eval_result['domain_correct']} "
                f"confidence={eval_result['confidence']:.3f}")
        else:
            log(f"AST eval: {eval_result['error']}")
    except Exception as e:
        log(f"AST evaluation failed (non-fatal): {e}")
        _pf_errors.append("ast_eval")
    timings["ast_eval"] = round(time.monotonic() - t15, 3)

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
            _pf_errors.append("reasoning_close")
    timings["reasoning_close"] = round(time.monotonic() - t2, 3)

    # === 2.5 FAILURE LESSONS: Store in brain + generate follow-up task ===
    t25 = time.monotonic()
    if task_status == "failure" and exit_code != 0 and exit_code != 124:
        try:
            # Store a concise lesson in brain
            error_snippet = output_text[-300:] if output_text else "no output"
            error_snippet = re.sub(r'[^a-zA-Z0-9 _.,:;=+\-/()@#%\n]', '', error_snippet)[:250]
            lesson = f"FAILURE LESSON [{error_type}]: Attempted '{task[:100]}' — exit {exit_code}. Error: {error_snippet}"
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
                    tags=["failure", "lesson", f"error_type:{error_type}"],
                    source="postflight_failure"
                )
                log("Stored failure lesson in brain")

                # Contradiction check: if the failure lesson contradicts existing learnings, evolve them
                if mem_evo_find_contradictions and mem_evo_evolve:
                    try:
                        contras = mem_evo_find_contradictions(brain_mod, lesson, "clarvis-learnings",
                                                              threshold=0.4, top_n=3)
                        for c in contras[:2]:  # Limit to 2 evolutions per cycle
                            evo = mem_evo_evolve(brain_mod, c["id"], c["collection"],
                                                 lesson, reason="contradiction")
                            if evo.get("evolved"):
                                log(f"MEMORY EVOLUTION: Evolved {c['id']} → {evo['new_id']} (contradiction: {c['contradiction_signal'][:3]})")
                    except Exception as e:
                        log(f"Contradiction check failed (non-fatal): {e}")

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
            _pf_errors.append("failure_lessons")
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
            _pf_errors.append("brain_bridge")
    if brain_update_context:
        try:
            brain_update_context(task, task_status)
            log("Brain bridge: context updated")
        except Exception as e:
            log(f"Brain bridge context update failed: {e}")
            _pf_errors.append("brain_bridge_ctx")
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

    # === 4. PROCEDURAL MEMORY (via lifecycle hooks) ===
    t4 = time.monotonic()
    _hook_results = {}  # collected from single registry.run() below
    if _hooks_available:
        # Build context for all postflight hooks (runs procedural + consolidation + metrics in one pass)
        hook_ctx = {
            "exit_code": exit_code, "task": task, "output_text": output_text,
            "procedure_id": proc_id, "task_status": task_status,
            "task_duration": task_duration,
            "procedure_injected": preflight_data.get("procedure_injected", False),
            "procedures_for_injection": preflight_data.get("procedures_for_injection", []),
        }
        _hook_results = hook_registry.run(HookPhase.POSTFLIGHT, hook_ctx)
        for hname, hr in _hook_results.items():
            if "error" in hr:
                log(f"Hook {hname} failed: {hr['error']}")
            timings[f"hook_{hname}"] = hr.get("elapsed_s", 0)
        hook_summary = ", ".join(
            f"{n}={r.get('elapsed_s', 0):.3f}s" for n, r in _hook_results.items()
        )
        log(f"Lifecycle hooks: {len(_hook_results)} hooks ran ({hook_summary})")
    else:
        # Legacy fallback — import-time wired procedural memory
        if exit_code == 0:
            if proc_id and record_use:
                try:
                    record_use(proc_id, True)
                    log(f"Recorded successful use of procedure {proc_id}")
                except Exception as e:
                    log(f"Procedural record_use failed: {e}")
            elif learn_from_task:
                try:
                    steps = None
                    if extract_steps:
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
            if proc_id and record_use:
                try:
                    record_use(proc_id, False)
                    log(f"Recorded failed use of procedure {proc_id}")
                except Exception as e:
                    log(f"Procedural failure record failed: {e}")
    timings["procedural"] = round(time.monotonic() - t4, 3)

    # === 4.5 TOOL MAKER: Extract reusable tools (LATM pattern) ===
    t45 = time.monotonic()
    if tool_maker_extract and exit_code == 0:
        try:
            tm_result = tool_maker_extract(output_text, task, task_status)
            extracted = tm_result.get("extracted", 0)
            if extracted > 0:
                log(f"Tool maker: extracted {extracted} tools from task output")
            elif tm_result.get("skipped"):
                pass  # silent skip — not every task produces reusable tools
        except Exception as e:
            log(f"Tool maker extraction failed (non-fatal): {e}")
    timings["tool_maker"] = round(time.monotonic() - t45, 3)

    # === 5. EPISODIC MEMORY: Encode episode ===
    t5 = time.monotonic()
    if EpisodicMemory:
        try:
            em = EpisodicMemory()
            error_msg = output_text[-200:] if task_status != "success" else None
            em.encode(task, task_section, best_salience, task_status,
                     duration_s=task_duration, error_msg=error_msg)
            # Tag episode with error_type for failure pattern analysis
            if error_type and em.episodes:
                latest = em.episodes[-1]
                if latest.get("task", "")[:60] == task[:60]:
                    latest.setdefault("tags", []).append(f"error_type:{error_type}")
                    em._save()
            log(f"Encoded episode ({task_status}, {task_duration}s{', type=' + error_type if error_type else ''})")
        except Exception as e:
            log(f"Episodic encoding failed: {e}")
            _pf_errors.append("episodic")
    timings["episodic"] = round(time.monotonic() - t5, 3)

    # === 5.05 PROMPT OPTIMIZATION: Record prompt→outcome pair (APE/SPO loop) ===
    t505 = time.monotonic()
    variant_id = preflight_data.get("prompt_variant_id", "")
    variant_task_type = preflight_data.get("prompt_variant_task_type", "")
    if po_record_outcome and variant_id:
        try:
            # Compute quality score (0.0-1.0) from output signals
            quality_score = None
            if task_status == "success" and output_text:
                q = 0.5  # base for success
                out_len = len(output_text)
                if out_len > 500:
                    q += 0.1  # substantive output
                if out_len > 2000:
                    q += 0.1  # detailed output
                # Check for test/verification signals
                out_lower = output_text[-3000:].lower() if out_len > 3000 else output_text.lower()
                if "pass" in out_lower or "✓" in out_lower or "success" in out_lower:
                    q += 0.1
                if "test" in out_lower and ("pass" in out_lower or "ok" in out_lower):
                    q += 0.1
                # Penalty for error signals in successful tasks
                if "error" in out_lower or "traceback" in out_lower:
                    q -= 0.1
                quality_score = max(0.0, min(1.0, q))
            elif task_status == "timeout":
                quality_score = 0.1
            elif task_status == "failure":
                quality_score = 0.0
            po_record_outcome(variant_id, variant_task_type, task_status,
                              task_duration, task, quality_score=quality_score)
            log(f"Prompt optimization: recorded {task_status} q={quality_score} for variant "
                f"{variant_id[:50]}")
        except Exception as e:
            log(f"Prompt optimization recording failed (non-fatal): {e}")
    timings["prompt_optimization"] = round(time.monotonic() - t505, 3)

    # === 5.1 PREDICTION AUTO-RESOLVER: String match + embedding fallback ===
    t51 = time.monotonic()
    actual = "success" if exit_code == 0 else "failure"
    if pred_resolve_enhanced:
        try:
            ar = pred_resolve_enhanced(task, actual)
            parts = [f"string={ar['matched']}"]
            if ar.get("embedding_matched", 0) > 0:
                parts.append(f"embed={ar['embedding_matched']}")
            if ar["stale_expired"] > 0:
                parts.append(f"stale={ar['stale_expired']}")
            parts.append(f"remaining={ar['remaining_open']}")
            log(f"Prediction resolve: {', '.join(parts)}")
        except Exception as e:
            log(f"Prediction resolve (enhanced) failed: {e}")
            # Fallback to string-only resolver
            if conf_auto_resolve:
                try:
                    ar = conf_auto_resolve(task, actual)
                    log(f"Prediction resolve (fallback): matched={ar['matched']}, remaining={ar['remaining_open']}")
                except Exception as e2:
                    log(f"Prediction resolve (fallback) also failed: {e2}")
    elif conf_auto_resolve:
        try:
            ar = conf_auto_resolve(task, actual)
            if ar["matched"] > 0 or ar["stale_expired"] > 0:
                log(f"Prediction auto-resolve: matched={ar['matched']}, "
                    f"stale_expired={ar['stale_expired']}, remaining={ar['remaining_open']}")
            else:
                log(f"Prediction auto-resolve: no matches, remaining={ar['remaining_open']}")
        except Exception as e:
            log(f"Prediction auto-resolve failed: {e}")
    timings["prediction_auto_resolve"] = round(time.monotonic() - t51, 3)

    # === 5.5 WORLD MODEL: Record outcome for prediction accuracy ===
    t55 = time.monotonic()
    if HierarchicalWorldModel:
        try:
            wm = HierarchicalWorldModel()
            wm.record_outcome(task, task_status)
            log(f"World model: recorded outcome '{task_status}' for prediction calibration")
        except Exception as e:
            log(f"World model outcome recording failed: {e}")
            _pf_errors.append("world_model")
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

    # === 7.3-7.35 PERFORMANCE METRICS (via lifecycle hooks if available) ===
    t73 = time.monotonic()
    if not _hooks_available:
        # Legacy fallback — hooks already ran metrics in §4 when available
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

        t735 = time.monotonic()
        if latency_quick_check:
            try:
                lat_result = latency_quick_check()
                if lat_result.get("critical"):
                    log(f"LATENCY CRITICAL: brain.recall p95={lat_result['p95_ms']:.0f}ms exceeds critical threshold")
                elif not lat_result.get("p50_ok") or not lat_result.get("p95_ok"):
                    log(f"LATENCY WARN: brain.recall p50={lat_result['p50_ms']:.0f}ms p95={lat_result['p95_ms']:.0f}ms "
                        f"(budget p50={lat_result['budget_p50_ms']}ms p95={lat_result['budget_p95_ms']}ms)")
                else:
                    log(f"LATENCY: brain.recall p50={lat_result['p50_ms']:.0f}ms p95={lat_result['p95_ms']:.0f}ms [OK]")
            except Exception as e:
                log(f"Latency budget check failed: {e}")
        timings["latency_budget"] = round(time.monotonic() - t735, 3)

    # === 7.4 SELF-TEST HARNESS: Auto-run tests after code-modifying heartbeats ===
    t74 = time.monotonic()
    selftest_result = {"ran": False}
    try:
        # Detect code modifications in output (Edit/Write tool usage, file writes, etc.)
        code_modified = False
        if output_text:
            code_indicators = [
                "Edit(",  "Write(",  "Edit tool",  "Write tool",
                "wrote to ",  "edited ",  "modified ",  "created ",
                ".py\n",  "def ",  "class ",  "import ",
                "scripts/",  "packages/",
            ]
            output_lower = output_text.lower()
            hits = sum(1 for ind in code_indicators if ind.lower() in output_lower)
            code_modified = hits >= 2  # Need at least 2 indicators

        if code_modified and exit_code == 0:
            import subprocess
            selftest_result["ran"] = True
            selftest_result["code_modified"] = True

            # 1. Run pytest on clarvis-db
            pytest_proc = subprocess.run(
                ["python3", "-m", "pytest", "packages/clarvis-db/tests/", "-q", "--tb=short"],
                cwd="/home/agent/.openclaw/workspace",
                capture_output=True, text=True, timeout=60
            )
            selftest_result["pytest_exit"] = pytest_proc.returncode
            selftest_result["pytest_summary"] = pytest_proc.stdout.strip().split('\n')[-1] if pytest_proc.stdout.strip() else ""

            # 2. Run brain.health_check()
            try:
                from brain import brain as brain_instance
                hc = brain_instance.health_check()
                selftest_result["brain_healthy"] = hc.get("status") == "healthy"
                selftest_result["brain_memories"] = hc.get("total_memories", 0)
            except Exception as e:
                selftest_result["brain_healthy"] = False
                selftest_result["brain_error"] = str(e)

            # Determine overall pass/fail
            tests_passed = selftest_result.get("pytest_exit", 1) == 0
            brain_ok = selftest_result.get("brain_healthy", False)
            selftest_result["all_passed"] = tests_passed and brain_ok

            if selftest_result["all_passed"]:
                log(f"SELF-TEST PASSED: pytest={selftest_result['pytest_summary']}, brain=healthy ({selftest_result.get('brain_memories', '?')} memories)")
            else:
                log(f"SELF-TEST FAILED: pytest_exit={selftest_result.get('pytest_exit')}, brain_ok={brain_ok}")
                # Store regression alert in brain
                try:
                    from brain import brain as brain_instance
                    alert = (
                        f"REGRESSION ALERT: Self-test failed after task '{task[:80]}'. "
                        f"pytest_exit={selftest_result.get('pytest_exit')}, brain_ok={brain_ok}. "
                        f"pytest: {selftest_result.get('pytest_summary', 'N/A')}"
                    )
                    brain_instance.store(alert, collection="clarvis-learnings",
                                        importance=0.95, tags=["regression", "self-test"],
                                        source="self_test_harness")
                    log("Stored regression alert in brain")
                except Exception:
                    pass
                # Push P0 fix task to QUEUE.md
                try:
                    from queue_writer import add_task
                    fix_task = f"FIX REGRESSION: Self-test failed after '{task[:60]}'. Review and fix immediately."
                    add_task(fix_task, priority="P0", source="self_test_harness")
                    log("Pushed P0 regression fix task to QUEUE.md")
                except Exception:
                    pass
        else:
            selftest_result["code_modified"] = code_modified
            if not code_modified:
                log("Self-test: skipped (no code modifications detected)")
    except Exception as e:
        log(f"Self-test harness failed: {e}")
        selftest_result["error"] = str(e)
        _pf_errors.append("self_test")
    timings["self_test"] = round(time.monotonic() - t74, 3)

    # === 7.42 CODE_GEN OUTCOME: Record actual code quality metrics for self_model ===
    t742 = time.monotonic()
    try:
        import subprocess
        # Detect changed .py files via git diff (staged + unstaged from this heartbeat)
        diff_proc = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD~1", "HEAD", "--", "*.py"],
            capture_output=True, text=True, timeout=10,
            cwd="/home/agent/.openclaw/workspace"
        )
        # Also check unstaged changes (task may not have committed)
        diff_proc2 = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", "--", "*.py"],
            capture_output=True, text=True, timeout=10,
            cwd="/home/agent/.openclaw/workspace"
        )
        changed_py = set()
        for line in (diff_proc.stdout + "\n" + diff_proc2.stdout).strip().split("\n"):
            line = line.strip()
            if line.endswith(".py"):
                changed_py.add(line)

        if changed_py:
            # Syntax-check each changed .py file
            syntax_ok = 0
            syntax_fail = 0
            syntax_errors = []
            ws = "/home/agent/.openclaw/workspace"
            for relpath in changed_py:
                fpath = os.path.join(ws, relpath)
                if os.path.exists(fpath):
                    try:
                        with open(fpath, "r") as cf:
                            compile(cf.read(), fpath, "exec")
                        syntax_ok += 1
                    except SyntaxError as se:
                        syntax_fail += 1
                        syntax_errors.append(f"{relpath}:{se.lineno}: {se.msg}")

            total_files = syntax_ok + syntax_fail
            syntax_ratio = syntax_ok / total_files if total_files > 0 else 1.0

            # === Quality score: 0.0-1.0 composite beyond binary success/fail ===
            # Weights: completion 0.30, syntax 0.25, output_cleanliness 0.25, efficiency 0.20
            q_completion = 1.0 if exit_code == 0 else (0.3 if exit_code == 124 else 0.0)
            q_syntax = syntax_ratio
            # Output cleanliness: penalize tracebacks, errors, warnings in output
            _out_lower = output_text.lower() if output_text else ""
            _traceback_count = _out_lower.count("traceback (most recent")
            _error_count = _out_lower.count("error:") + _out_lower.count("error ")
            q_output = max(0.0, 1.0 - (_traceback_count * 0.3) - (min(_error_count, 5) * 0.1))
            # Efficiency: reasonable duration (penalize >900s, bonus for <300s)
            # Progress-aware: if checkpoints show steady progress, reduce duration penalty
            progress_data = {}
            try:
                _progress_file = output_file + ".progress.json"
                if os.path.exists(_progress_file):
                    with open(_progress_file) as _pf:
                        progress_data = json.load(_pf)
            except (OSError, json.JSONDecodeError):
                pass

            if task_duration <= 0:
                q_efficiency = 0.5
            elif task_duration < 300:
                q_efficiency = 1.0
            elif task_duration < 900:
                q_efficiency = 0.8
            else:
                q_efficiency = max(0.2, 1.0 - (task_duration - 900) / 1800)
                # Checkpoint bonus: steady progress mitigates duration penalty
                cp_score = progress_data.get("progress_score", 0.0)
                if cp_score > 0.4:
                    q_efficiency = min(0.8, q_efficiency + cp_score * 0.3)
            quality_score = round(
                0.30 * q_completion + 0.25 * q_syntax + 0.25 * q_output + 0.20 * q_efficiency, 3
            )

            outcome_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "task": task[:200],
                "task_status": task_status,
                "files_touched": len(changed_py),
                "files_list": sorted(changed_py)[:20],
                "syntax_ok": syntax_ok,
                "syntax_fail": syntax_fail,
                "syntax_errors": syntax_errors[:5],
                "syntax_ratio": syntax_ratio,
                "exit_code": exit_code,
                "duration_s": task_duration,
                "quality_score": quality_score,
                "quality_breakdown": {
                    "completion": round(q_completion, 2),
                    "syntax": round(q_syntax, 2),
                    "output_cleanliness": round(q_output, 2),
                    "efficiency": round(q_efficiency, 2),
                },
            }
            if progress_data:
                outcome_entry["progress_checkpoints"] = progress_data.get("checkpoints", 0)
                outcome_entry["progress_score"] = progress_data.get("progress_score", 0.0)

            # Append to outcomes JSONL
            outcomes_file = os.path.join(ws, "data", "code_gen_outcomes.jsonl")
            os.makedirs(os.path.dirname(outcomes_file), exist_ok=True)
            with open(outcomes_file, "a") as of:
                of.write(json.dumps(outcome_entry) + "\n")

            log(f"Code-gen outcome: {len(changed_py)} files, "
                f"syntax={syntax_ok}/{total_files} clean, "
                f"quality={quality_score:.2f}, task={task_status}")
        else:
            log("Code-gen outcome: no .py changes detected")
    except Exception as e:
        log(f"Code-gen outcome recording failed: {e}")
        _pf_errors.append("code_gen_outcome")
    timings["code_gen_outcome"] = round(time.monotonic() - t742, 3)

    # === 7.43 CODE VALIDATION GATE: Self-repair feedback loop (Self-Refine pattern) ===
    t743 = time.monotonic()
    if cv_validate_output or cv_validate_file:
        try:
            cv_file_errors = []
            cv_output_result = None

            # 1. Validate execution output for runtime/test errors
            if cv_validate_output and output_text:
                cv_output_result = cv_validate_output(output_text, task)

            # 2. Validate changed Python files for syntax/structural issues
            if cv_validate_file:
                import subprocess
                ws = "/home/agent/.openclaw/workspace"
                _cvd1 = subprocess.run(
                    ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD~1", "HEAD", "--", "*.py"],
                    capture_output=True, text=True, timeout=10, cwd=ws
                )
                _cvd2 = subprocess.run(
                    ["git", "diff", "--name-only", "--diff-filter=ACMR", "--", "*.py"],
                    capture_output=True, text=True, timeout=10, cwd=ws
                )
                _cv_changed = set()
                for _cvline in (_cvd1.stdout + "\n" + _cvd2.stdout).strip().split("\n"):
                    _cvline = _cvline.strip()
                    if _cvline.endswith(".py"):
                        _cv_changed.add(_cvline)

                for relpath in sorted(_cv_changed)[:10]:
                    fpath = os.path.join(ws, relpath)
                    if os.path.exists(fpath):
                        fv = cv_validate_file(fpath)
                        if not fv["valid"]:
                            cv_file_errors.append({
                                "file": relpath,
                                "errors": fv["errors"][:3],
                                "refinement": fv["refinement"],
                            })

            has_output_errs = cv_output_result and cv_output_result.get("has_errors", False)
            has_file_errs = len(cv_file_errors) > 0

            if has_output_errs or has_file_errs:
                # Build refinement prompt (Self-Refine pattern from research)
                refinement_parts = []
                if has_output_errs:
                    refinement_parts.append(cv_output_result["refinement"])
                for fe in cv_file_errors[:3]:
                    refinement_parts.append(f"File {fe['file']}: {fe['refinement']}")
                refinement_prompt = "CODE VALIDATION ERRORS:\n" + "\n".join(refinement_parts)

                log(f"CODE VALIDATION: {len(cv_file_errors)} file(s) with issues, "
                    f"output_errors={has_output_errs}")

                # Record validation failure in episode
                if EpisodicMemory:
                    try:
                        em_cv = EpisodicMemory()
                        if em_cv.episodes:
                            latest = em_cv.episodes[-1]
                            if latest.get("task", "")[:60] == task[:60]:
                                latest.setdefault("tags", []).append("code_validation:fail")
                                latest["code_validation"] = {
                                    "passed": False,
                                    "file_errors": len(cv_file_errors),
                                    "output_errors": has_output_errs,
                                    "refinement": refinement_prompt[:300],
                                }
                                em_cv._save()
                    except Exception:
                        pass

                # Persist validation outcome
                cv_entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "task": task[:200],
                    "validation_passed": False,
                    "file_errors": len(cv_file_errors),
                    "output_errors": has_output_errs,
                    "refinement_prompt": refinement_prompt[:500],
                }
                cv_outcomes_file = os.path.join(
                    "/home/agent/.openclaw/workspace", "data", "code_validation_outcomes.jsonl"
                )
                os.makedirs(os.path.dirname(cv_outcomes_file), exist_ok=True)
                with open(cv_outcomes_file, "a") as cvf:
                    cvf.write(json.dumps(cv_entry) + "\n")

                # === FEEDBACK LOOP: Auto-inject P1 fix task when >3 validation errors ===
                total_cv_errors = sum(len(fe["errors"]) for fe in cv_file_errors)
                if has_output_errs and cv_output_result:
                    total_cv_errors += len(cv_output_result.get("errors", []))
                if total_cv_errors > 3:
                    try:
                        from queue_writer import add_task as _cv_add_task
                        affected_files = ", ".join(fe["file"] for fe in cv_file_errors[:3])
                        fix_desc = (
                            f"[CODE_QUALITY_FIX] Fix {total_cv_errors} code validation errors "
                            f"in: {affected_files or 'output'} — task: {task[:80]}"
                        )
                        _cv_added = _cv_add_task(fix_desc, priority="P1", source="code_validation")
                        if _cv_added:
                            log(f"CODE VALIDATION FEEDBACK: injected P1 fix task ({total_cv_errors} errors)")
                    except Exception as e:
                        log(f"CODE VALIDATION FEEDBACK: queue injection failed: {e}")
            else:
                log("CODE VALIDATION: all checks passed")
                # Record pass in episode
                if EpisodicMemory:
                    try:
                        em_cv = EpisodicMemory()
                        if em_cv.episodes:
                            latest = em_cv.episodes[-1]
                            if latest.get("task", "")[:60] == task[:60]:
                                latest.setdefault("tags", []).append("code_validation:pass")
                                em_cv._save()
                    except Exception:
                        pass
        except Exception as e:
            log(f"Code validation gate failed (non-fatal): {e}")
            _pf_errors.append("code_validation")
    timings["code_validation"] = round(time.monotonic() - t743, 3)

    # === 7.45 PERFORMANCE GATE: Run after code-modifying heartbeats ===
    t745 = time.monotonic()
    _code_mod = selftest_result.get("code_modified", False) or selftest_result.get("ran", False)
    if perf_gate_run and _code_mod and exit_code == 0:
        try:
            gate_report = perf_gate_run(skip_browser=True, verbose=False)
            if gate_report.get("all_passed"):
                log(f"PERF GATE: PASS ({gate_report['passed']}/{gate_report['total']} gates, {gate_report['elapsed_s']}s)")
            else:
                failed_gates = [g["gate"] for g in gate_report.get("gates", []) if not g["passed"]]
                log(f"PERF GATE: FAIL — {', '.join(failed_gates)} ({gate_report['elapsed_s']}s)")
        except Exception as e:
            log(f"Performance gate failed: {e}")
    timings["perf_gate"] = round(time.monotonic() - t745, 3)

    # === 7.46 MEMORY QUALITY GATES: Hard gate on retrieval quality ===
    t746 = time.monotonic()
    QUALITY_GATE_FILE = "/home/agent/.openclaw/workspace/data/memory_quality_gate.json"
    QUALITY_BASELINE_FILE = "/home/agent/.openclaw/workspace/data/memory_quality_baseline.json"
    try:
        if rq_tracker:
            rq_report = rq_tracker.report(days=1)
            if rq_report.get("status") != "no_data" and rq_report.get("total_events", 0) >= 5:
                # Load or initialize baseline
                baseline = None
                if os.path.exists(QUALITY_BASELINE_FILE):
                    with open(QUALITY_BASELINE_FILE) as bf:
                        baseline = json.load(bf)

                current_hit_rate = rq_report.get("hit_rate")
                current_dead_rate = rq_report.get("dead_recall_rate", 0)
                current_avg_dist = rq_report.get("avg_distance_overall")

                if baseline is None:
                    # First run — establish baseline from current data
                    baseline = {
                        "hit_rate": current_hit_rate,
                        "dead_recall_rate": current_dead_rate,
                        "avg_distance": current_avg_dist,
                        "established_at": datetime.now(timezone.utc).isoformat(),
                        "sample_size": rq_report.get("total_events", 0),
                    }
                    os.makedirs(os.path.dirname(QUALITY_BASELINE_FILE), exist_ok=True)
                    with open(QUALITY_BASELINE_FILE, "w") as bf:
                        json.dump(baseline, bf, indent=2)
                    log(f"QUALITY GATE: baseline established (hit_rate={current_hit_rate}, "
                        f"dead_rate={current_dead_rate:.3f}, avg_dist={current_avg_dist})")
                else:
                    # Compare against baseline — check for degradation
                    violations = []
                    bl_hit = baseline.get("hit_rate")
                    bl_dead = baseline.get("dead_recall_rate", 0)
                    bl_dist = baseline.get("avg_distance")

                    # Gate 1: Hit rate dropped >15% from baseline (or absolute <40%)
                    if current_hit_rate is not None and bl_hit is not None:
                        if current_hit_rate < bl_hit - 0.15 or current_hit_rate < 0.40:
                            violations.append(f"hit_rate={current_hit_rate:.3f} (baseline={bl_hit:.3f})")

                    # Gate 2: Dead recall rate increased >10% from baseline (or absolute >35%)
                    if current_dead_rate > bl_dead + 0.10 or current_dead_rate > 0.35:
                        violations.append(f"dead_recall_rate={current_dead_rate:.3f} (baseline={bl_dead:.3f})")

                    # Gate 3: Average distance increased >0.2 from baseline (or absolute >1.6)
                    if current_avg_dist is not None and bl_dist is not None:
                        if current_avg_dist > bl_dist + 0.20 or current_avg_dist > 1.6:
                            violations.append(f"avg_distance={current_avg_dist:.4f} (baseline={bl_dist:.4f})")

                    if violations:
                        log(f"QUALITY GATE VIOLATION: {'; '.join(violations)}")

                        # Write gate file — task_selector reads this to pause new features
                        gate_data = {
                            "status": "DEGRADED",
                            "violations": violations,
                            "current": {
                                "hit_rate": current_hit_rate,
                                "dead_recall_rate": current_dead_rate,
                                "avg_distance": current_avg_dist,
                            },
                            "baseline": baseline,
                            "triggered_at": datetime.now(timezone.utc).isoformat(),
                            "triggered_by_task": task[:120],
                        }
                        os.makedirs(os.path.dirname(QUALITY_GATE_FILE), exist_ok=True)
                        with open(QUALITY_GATE_FILE, "w") as gf:
                            json.dump(gate_data, gf, indent=2)

                        # Push P0 repair task
                        try:
                            from queue_writer import add_task
                            repair_desc = (
                                f"[MEMORY_REPAIR] Memory quality degraded — {'; '.join(violations)}. "
                                f"Run retrieval_quality.py baseline, check recent brain changes, "
                                f"fix retrieval before resuming new features."
                            )
                            added = add_task(repair_desc, priority="P0", source="memory_quality_gate")
                            if added:
                                log("QUALITY GATE: pushed P0 repair task to QUEUE.md")
                        except Exception as qe:
                            log(f"QUALITY GATE: failed to push repair task: {qe}")
                    else:
                        # Quality is fine — clear any existing gate
                        if os.path.exists(QUALITY_GATE_FILE):
                            os.remove(QUALITY_GATE_FILE)
                        log(f"QUALITY GATE: PASS (hit_rate={current_hit_rate}, "
                            f"dead_rate={current_dead_rate:.3f}, avg_dist={current_avg_dist})")

                        # Update baseline if current is better (rolling improvement)
                        updated = False
                        if current_hit_rate is not None and bl_hit is not None and current_hit_rate > bl_hit + 0.05:
                            baseline["hit_rate"] = current_hit_rate
                            updated = True
                        if current_dead_rate < bl_dead - 0.05:
                            baseline["dead_recall_rate"] = current_dead_rate
                            updated = True
                        if updated:
                            baseline["updated_at"] = datetime.now(timezone.utc).isoformat()
                            with open(QUALITY_BASELINE_FILE, "w") as bf:
                                json.dump(baseline, bf, indent=2)
                            log("QUALITY GATE: baseline improved, updated")
            else:
                log(f"QUALITY GATE: insufficient data ({rq_report.get('total_events', 0)} events, need >=5)")
    except Exception as e:
        log(f"Memory quality gate failed (non-fatal): {e}")
    timings["memory_quality_gate"] = round(time.monotonic() - t746, 3)

    # === 7.47 STRUCTURAL HEALTH: Import graph metrics (via hook when available) ===
    t747 = time.monotonic()
    if not _hooks_available:
        # Legacy fallback — hooks already ran structural_health in §4 when available
        if build_import_graph and import_health_report and IH_SCRIPTS_DIR:
            try:
                ih_graph = build_import_graph(IH_SCRIPTS_DIR)
                ih_report = import_health_report(ih_graph, use_current_thresholds=True)
                ih_metrics = {
                    "scc_count": ih_report["circular_imports"]["scc_count"],
                    "max_scc_size": ih_report["circular_imports"]["max_scc_size"],
                    "max_depth": ih_report["dependency_depth"]["max"],
                    "max_fan_in": ih_report["fan_in"]["max"],
                    "max_fan_out": ih_report["fan_out"]["max"],
                    "side_effects": ih_report["side_effects"]["count"],
                    "total_modules": ih_report["total_modules"],
                    "violations": ih_report["violations"],
                    "healthy": ih_report["healthy"],
                }
                struct_hist_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'structural_health_history.jsonl')
                ih_entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": "structural_health",
                    "metrics": ih_metrics,
                }
                with open(struct_hist_file, "a") as hf:
                    hf.write(json.dumps(ih_entry) + "\n")
                status_str = "HEALTHY" if ih_metrics["healthy"] else f"DEGRADED ({', '.join(ih_metrics['violations'])})"
                log(f"STRUCTURAL: {status_str} — SCCs={ih_metrics['scc_count']}, "
                    f"depth={ih_metrics['max_depth']}, fan_in={ih_metrics['max_fan_in']}, "
                    f"fan_out={ih_metrics['max_fan_out']}, modules={ih_metrics['total_modules']}")
            except Exception as e:
                log(f"Structural health check failed: {e}")
        timings["structural_health"] = round(time.monotonic() - t747, 3)

    # === 7.48 RETRIEVAL FEEDBACK: RL-lite reward signal from verdict × outcome ===
    t748 = time.monotonic()
    if retrieval_record_feedback:
        try:
            rv = preflight_data.get("retrieval_verdict", "SKIPPED")
            max_score = preflight_data.get("retrieval_max_score")
            if max_score is None:
                # Try from nested retrieval data
                ret_data = preflight_data.get("retrieval_data", {})
                max_score = ret_data.get("max_score") if isinstance(ret_data, dict) else None
            fb_result = retrieval_record_feedback(
                verdict=rv,
                outcome=task_status,
                max_score=max_score,
                task=task[:200],
            )
            log(f"RETRIEVAL FEEDBACK: {rv}×{task_status} → reward={fb_result['reward']:.2f}, "
                f"EMA={fb_result['ema_success_rate']:.3f}, total={fb_result['total_episodes']}"
                + (", suggestions generated!" if fb_result.get("suggestions_generated") else ""))

            # --- Context relevance: section-level content matching ---
            brief_text = preflight_data.get("context_brief", "")
            if brief_text and output_text and score_section_relevance:
                cr_result = score_section_relevance(
                    brief_text, output_text, task=task, outcome=task_status,
                )
                # Tag with MMR category for adaptive lambda feedback loop
                if classify_mmr_category:
                    cr_result["mmr_category"] = classify_mmr_category(task)
                log(f"CONTEXT RELEVANCE: {cr_result['sections_referenced']}/{cr_result['sections_total']} "
                    f"sections referenced ({cr_result['overall']:.1%})"
                    + (f" [{cr_result.get('mmr_category', '?')}]" if classify_mmr_category else ""))
                if cr_record:
                    cr_record(cr_result)
                # Periodically update adaptive MMR lambdas from accumulated data
                # Rate-limit: skip when no useful signal or insufficient new episodes
                if mmr_update_lambdas:
                    _mmr_skip_reason = None
                    if rv in ("NO_RETRIEVAL", "SKIPPED"):
                        _mmr_skip_reason = f"verdict={rv}"
                    else:
                        try:
                            import json as _json
                            _mmr_state_path = os.path.join(
                                os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"),
                                "data", "retrieval_quality", "adaptive_mmr_state.json",
                            )
                            if os.path.exists(_mmr_state_path):
                                with open(_mmr_state_path) as _f:
                                    _mmr_st = _json.load(_f)
                                _total_eps = sum(v.get("episodes", 0) for v in _mmr_st.values() if isinstance(v, dict))
                                if _total_eps < 10:
                                    _mmr_skip_reason = f"episodes={_total_eps}<10"
                        except Exception:
                            pass  # read failure → run update anyway
                    if _mmr_skip_reason:
                        log(f"ADAPTIVE MMR: skipped update ({_mmr_skip_reason})")
                    else:
                        try:
                            updated = mmr_update_lambdas()
                            log(f"ADAPTIVE MMR: lambdas updated — {updated}")
                        except Exception:
                            pass  # non-critical
        except Exception as e:
            log(f"Retrieval feedback recording failed (non-fatal): {e}")
            _pf_errors.append("retrieval_feedback")
    timings["retrieval_feedback"] = round(time.monotonic() - t748, 3)

    # === 7.49 MEMORY EVOLUTION: Increment recall_success for memories used in successful tasks ===
    t749 = time.monotonic()
    if mem_evo_recall_success and task_status == "success":
        try:
            recalled_ids = preflight_data.get("recalled_memory_ids", [])
            if recalled_ids:
                from clarvis.brain import get_brain as _get_brain_evo
                _brain_evo = _get_brain_evo()
                evo_result = mem_evo_recall_success(_brain_evo, recalled_ids)
                log(f"MEMORY EVOLUTION: recall_success updated for {evo_result['updated']}/{len(recalled_ids)} memories"
                    + (f", errors: {evo_result['errors'][:2]}" if evo_result['errors'] else ""))
        except Exception as e:
            log(f"Memory evolution tracking failed (non-fatal): {e}")
            _pf_errors.append("memory_evolution")
    timings["memory_evolution"] = round(time.monotonic() - t749, 3)

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
            _pf_errors.append("cost_tracking")
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
            _pf_errors.append("evolution")
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

    # === 8.5 PERIODIC SYNTHESIS (via lifecycle hook when available) ===
    t85_synth = time.monotonic()
    if not _hooks_available:
        # Legacy fallback — hooks already ran periodic_synthesis in §4 when available
        if EpisodicMemory:
            try:
                em_synth = EpisodicMemory()
                if len(em_synth.episodes) % 10 == 0 and len(em_synth.episodes) > 0:
                    synth = em_synth.synthesize()
                    log(f"Periodic synthesis: {synth.get('goals_count', 0)} goals, "
                        f"success_rate={synth.get('success_rate', '?')}")
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
            _pf_errors.append("digest")
    timings["digest"] = round(time.monotonic() - t9, 3)

    # === 10. MARK TASK COMPLETE IN QUEUE.MD ===
    t10 = time.monotonic()

    def _mark_task_in_queue(task_text, annotation):
        """Mark a task as [x] in QUEUE.md with an annotation.
        Returns: 'marked' if found and marked, 'archived' if already in archive, False if not found.

        Matching strategy:
        1) Prefer exact tag match when task_text contains [TAG]
        2) Fallback to prefix substring match (legacy)
        """
        import re

        with open(QUEUE_FILE, 'r') as f:
            lines = f.readlines()

        task_prefix = task_text[:60]
        m = re.match(r"\[([^\]]+)\]", task_text.strip())
        tag = m.group(1) if m else None

        # Strategy A: tag-based match (robust against description drift)
        if tag:
            tag_re = re.compile(rf"^\- \[ \] \[{re.escape(tag)}\](?=\s|$)")
            for i, line in enumerate(lines):
                if tag_re.search(line):
                    lines[i] = line.replace("- [ ] ", "- [x] ", 1).rstrip() + f" ({annotation})\n"
                    with open(QUEUE_FILE, 'w') as f:
                        f.writelines(lines)
                    return "marked"

        # Strategy B: legacy prefix substring match
        for i, line in enumerate(lines):
            if line.strip().startswith("- [ ] ") and task_prefix in line:
                lines[i] = line.replace("- [ ] ", "- [x] ", 1).rstrip() + f" ({annotation})\n"
                with open(QUEUE_FILE, 'w') as f:
                    f.writelines(lines)
                return "marked"

        # Check if already archived (race: preflight archived before postflight ran)
        if os.path.exists(QUEUE_ARCHIVE):
            with open(QUEUE_ARCHIVE, 'r') as f:
                archive = f.read()
            if task_prefix in archive:
                return "archived"
        return False

    if task and task != "unknown":
        try:
            if exit_code == 0:
                # Success — mark complete
                timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                # Prefer canonical tag emitted by preflight when available
                task_for_marking = task
                try:
                    if isinstance(preflight_data, dict) and preflight_data.get("task_tag"):
                        task_for_marking = f"[{preflight_data['task_tag']}]"
                except Exception:
                    pass
                result_mark = _mark_task_in_queue(task_for_marking, timestamp)
                if result_mark == "marked":
                    log("Marked task complete in QUEUE.md")
                elif result_mark == "archived":
                    log(f"Task already in QUEUE_ARCHIVE.md (archived by preflight): {task[:60]}")
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
            _pf_errors.append("queue_update")
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

    # === 13. COGNITIVE WORKSPACE: Close task, archive active→dormant ===
    if cog_workspace:
        try:
            lesson = ""
            if task_status == "success":
                lesson = f"Completed successfully"
            elif task_status == "failure":
                lesson = f"Failed — check episode for details"
            cw_result = cog_workspace.close_task(outcome=task_status, lesson=lesson)
            reuse = cw_result.get("reuse_rate", 0)
            log(f"Cognitive workspace: closed task, reuse_rate={reuse:.1%}, buffers={cw_result.get('buffers', {})}")
        except Exception as e:
            log(f"Cognitive workspace close failed: {e}")

    timings["total"] = round(time.monotonic() - t0, 3)

    # === COMPLETENESS SCORING ===
    # Count stages that ran (from timings, excluding 'total') vs stages that errored
    stages_attempted = len([k for k in timings if k != "total"])
    stages_failed = len(_pf_errors)
    stages_ok = stages_attempted - stages_failed
    completeness = stages_ok / stages_attempted if stages_attempted > 0 else 1.0

    if completeness < 0.80:
        log(f"COMPLETENESS WARNING: {stages_ok}/{stages_attempted} stages succeeded "
            f"({completeness:.0%}) — failed: {', '.join(_pf_errors)}")
    else:
        log(f"Post-flight complete in {timings['total']:.2f}s — "
            f"{stages_ok}/{stages_attempted} stages OK ({completeness:.0%})")

    # Persist completeness data
    try:
        completeness_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'postflight_completeness.jsonl')
        os.makedirs(os.path.dirname(completeness_file), exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task": task[:120],
            "task_status": task_status,
            "stages_attempted": stages_attempted,
            "stages_ok": stages_ok,
            "stages_failed": stages_failed,
            "completeness": round(completeness, 4),
            "errors": _pf_errors,
            "error_type": error_type,
            "total_time_s": timings["total"],
        }
        with open(completeness_file, "a") as cf:
            cf.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # Don't fail postflight over completeness logging

    return {"status": "ok", "task_status": task_status, "timings": timings,
            "completeness": round(completeness, 4), "errors": _pf_errors,
            "error_type": error_type}


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
