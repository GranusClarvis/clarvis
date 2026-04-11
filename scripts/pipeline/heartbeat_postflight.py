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
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone

from clarvis._script_loader import load as _load_script

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

from clarvis.cognition.attention import attention, get_attention_schema

try:
    from clarvis.cognition.confidence import outcome as conf_outcome, auto_resolve as conf_auto_resolve
except ImportError:
    conf_outcome = None
    conf_auto_resolve = None

try:
    pred_resolve_enhanced = _load_script("prediction_resolver", "cognition").resolve_with_episodes
except ImportError:
    pred_resolve_enhanced = None

try:
    close_chain = _load_script("reasoning_chain_hook", "cognition").close_chain
except ImportError:
    close_chain = None

try:
    from clarvis.memory.procedural_memory import record_use, learn_from_task
except ImportError:
    record_use = None
    learn_from_task = None

try:
    from clarvis.memory.episodic_memory import EpisodicMemory
except ImportError:
    EpisodicMemory = None

try:
    from clarvis._script_loader import load as _load_script
    _dw = _load_script("digest_writer", "tools")
    write_digest = _dw.write_digest
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
    from clarvis.metrics.self_model import think_about_thinking
except ImportError:
    think_about_thinking = None

try:
    from clarvis.memory.soar import get_soar as get_soar_engine
except ImportError:
    get_soar_engine = None

try:
    from hyperon_atomspace import get_atomspace
except ImportError:
    get_atomspace = None

try:
    from clarvis.cognition.workspace_broadcast import WorkspaceBroadcast
except ImportError:
    WorkspaceBroadcast = None

try:
    from clarvis.heartbeat.brain_bridge import brain_record_outcome, brain_update_context
except ImportError:
    brain_record_outcome = None
    brain_update_context = None

try:
    from clarvis.memory.cognitive_workspace import workspace as cog_workspace
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
    from wiki_hooks import postflight_wiki_ingest
except ImportError:
    postflight_wiki_ingest = None

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
    from clarvis.context.prompt_optimizer import record_outcome as po_record_outcome
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

try:
    from clarvis.metrics.trajectory import record_trajectory_event
except ImportError:
    record_trajectory_event = None

try:
    from clarvis.metrics.cot_evaluator import score_episode_cot, record_cot_score
except ImportError:
    score_episode_cot = None
    record_cot_score = None

try:
    from clarvis.cognition.obligations import ObligationTracker as OT_Postflight
except ImportError:
    OT_Postflight = None

try:
    from directive_engine import DirectiveEngine as DE_Postflight
except ImportError:
    DE_Postflight = None

# Cost tracking — spine module
try:
    from clarvis.orch.cost_tracker import CostTracker, estimate_tokens
    COST_LOG = os.path.join(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")), 'data', 'costs.jsonl')
    cost_tracker = CostTracker(COST_LOG)
except ImportError:
    cost_tracker = None

# Queue engine v2 — sidecar state + run records
try:
    from clarvis.queue.engine import engine as queue_engine
except ImportError:
    queue_engine = None

_import_time = time.monotonic() - start_import
log = lambda msg: print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')}] POSTFLIGHT: {msg}", file=sys.stderr)


# Error classification — canonical implementation in clarvis.heartbeat.error_classifier
from clarvis.heartbeat.error_classifier import (  # noqa: F401
    ERROR_RULES as _ERROR_RULES,
    classify_error as _classify_error,
    _match_keywords,
)

# Episode encoding — canonical implementation in clarvis.heartbeat.episode_encoder
from clarvis.heartbeat.episode_encoder import episode_encode as _episode_encode_canonical

# Worker-type classification and output validation
from clarvis.heartbeat.worker_validation import classify_worker_type, validate_worker_output

# Brain storage — canonical implementation in clarvis.heartbeat.brain_store
from clarvis.heartbeat.brain_store import (
    brain_store as _brain_store_canonical,
    store_failure_lesson as _store_failure_lesson_canonical,
)


def _mark_task_in_queue(task_text, annotation, queue_file, archive_file=None):
    """Back-compat shim; use queue_writer.mark_task_complete as canonical path."""
    try:
        from clarvis.queue.writer import mark_task_complete
        return mark_task_complete(task_text, annotation, queue_file=queue_file, archive_file=archive_file)
    except Exception as e:
        log(f"_mark_task_in_queue failed for '{task_text[:60]}': {e}")
        return False


def _compute_completeness(timings, pf_errors):
    """Compute postflight completeness score from timings and errors.

    Returns: (stages_attempted, stages_ok, stages_failed, completeness)
    """
    stages_attempted = len([k for k in timings if k != "total"])
    stages_failed = len(pf_errors)
    stages_ok = stages_attempted - stages_failed
    completeness = stages_ok / stages_attempted if stages_attempted > 0 else 1.0
    return stages_attempted, stages_ok, stages_failed, completeness


def _episode_encode(task, task_section, best_salience, task_status, task_duration,
                    error_type, output_text, preflight_data, _pf_errors):
    """§5 Episode encoding + §5.01 Trajectory scoring. Delegates to canonical module."""
    return _episode_encode_canonical(
        task, task_section, best_salience, task_status, task_duration,
        error_type, output_text, preflight_data, _pf_errors,
        EpisodicMemory=EpisodicMemory,
        record_trajectory_event=record_trajectory_event,
        log=log,
    )


def _cot_score(chain_id, _pf_errors):
    """§5.02 Chain-of-thought self-evaluation for episode quality."""
    timings = {}
    t502 = time.monotonic()
    if score_episode_cot and chain_id:
        try:
            result = score_episode_cot(chain_id=chain_id)
            if result and result.get("num_steps", 0) > 0:
                record_cot_score(result)
                issues_str = ", ".join(result.get("issues", [])) or "none"
                log(f"COT: score={result['cot_score']:.3f} grade={result['cot_grade']} "
                    f"steps={result['num_steps']} "
                    f"bt={result['backtracking_detail']['count']} "
                    f"issues=[{issues_str}]")
            else:
                log("COT: no reasoning steps found, skipping")
        except Exception as e:
            log(f"CoT scoring failed (non-fatal): {e}")
    timings["cot_eval"] = round(time.monotonic() - t502, 3)
    return timings


def _confidence_record(task_event, exit_code, task, preflight_data, _pf_errors):
    """§1 Confidence outcome + §1.5 AST evaluation."""
    timings = {}

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

    return timings


def _reasoning_close(chain_id, task_status, task, exit_code, output_text, _pf_errors):
    """§2 Reasoning chain close."""
    timings = {}

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

    return timings


def _store_failure_lesson(task, exit_code, output_text, error_type):
    """Store a failure lesson in brain. Delegates to canonical module."""
    _store_failure_lesson_canonical(
        task, exit_code, output_text, error_type,
        mem_evo_find_contradictions=mem_evo_find_contradictions,
        mem_evo_evolve=mem_evo_evolve, log=log,
    )


def _brain_store(task, task_status, exit_code, output_text, error_type,
                 task_duration, _pf_errors, RETRY_FILE):
    """§2.5 Failure lessons + §2.7 Brain bridge outcome recording. Delegates to canonical module."""
    return _brain_store_canonical(
        task, task_status, exit_code, output_text, error_type,
        task_duration, _pf_errors, RETRY_FILE,
        brain_record_outcome=brain_record_outcome,
        brain_update_context=brain_update_context,
        mem_evo_find_contradictions=mem_evo_find_contradictions,
        mem_evo_evolve=mem_evo_evolve, log=log,
    )


def _digest_write_fn(task, task_status, exit_code, task_duration, output_text, _pf_errors):
    """§9 Digest write."""
    timings = {}

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

    return timings


def _transcript_log(ctx, _pf_errors):
    """§9.5 Session transcript persistence (JSONL + raw output)."""
    timings = {}
    t = time.monotonic()
    try:
        from session_transcript_logger import log_transcript
        log_transcript(
            task=ctx["task"],
            task_status=ctx["task_status"],
            exit_code=ctx["exit_code"],
            task_duration=ctx["task_duration"],
            output_text=ctx["output_text"],
            error_type=ctx.get("error_type"),
            worker_type=ctx.get("worker_type", "general"),
            task_section=ctx.get("task_section", "P1"),
            chain_id=ctx.get("chain_id"),
        )
    except Exception as e:
        logging.debug("Transcript log failed (non-fatal): %s", e)
        _pf_errors.append("transcript_log")
    timings["transcript_log"] = round(time.monotonic() - t, 3)
    return timings


def _build_postflight_ctx(exit_code, output_file, preflight_data, task_duration):
    """Build shared context dict for postflight helpers."""
    WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
    task = preflight_data.get("task", "unknown")
    output_text = ""
    try:
        if output_file and os.path.exists(output_file):
            with open(output_file, 'r', errors='replace') as f:
                output_text = f.read()
    except Exception as e:
        logging.debug("Reading task output file failed: %s", e)

    # Crash guard: instant-fail episodes (< 10s, non-zero exit) are infrastructure
    # crashes, not real task failures. Don't penalize episode success rate.
    is_crash = preflight_data.get("crash_guard", False)

    if exit_code == 0:
        task_status = "success"
    elif exit_code == 124:
        task_status = "timeout"
    elif is_crash:
        task_status = "crash"
    else:
        task_status = "failure"

    error_type = error_evidence = None
    if task_status not in ("success",):
        error_type, error_evidence = _classify_error(exit_code, output_text)
        if is_crash:
            error_type = "crash"
            error_evidence = f"instant-fail ({preflight_data.get('crash_duration', '?')}s), original: {error_evidence}"
        log(f"Error taxonomy: {error_type} ({error_evidence})")

    return {
        "task": task,
        "task_section": preflight_data.get("task_section", "P1"),
        "best_salience": preflight_data.get("task_salience", 0.5),
        "chain_id": preflight_data.get("chain_id"),
        "proc_id": preflight_data.get("procedure_id"),
        "task_event": preflight_data.get("prediction_event", ""),
        "route_executor": preflight_data.get("route_executor", "claude"),
        "queue_run_id": preflight_data.get("queue_run_id"),
        "output_text": output_text,
        "task_status": task_status,
        "error_type": error_type,
        "error_evidence": error_evidence,
        "exit_code": exit_code,
        "task_duration": task_duration,
        "preflight_data": preflight_data,
        "WORKSPACE": WORKSPACE,
        "QUEUE_FILE": os.path.join(WORKSPACE, "memory/evolution/QUEUE.md"),
        "QUEUE_ARCHIVE": os.path.join(WORKSPACE, "memory/evolution/QUEUE_ARCHIVE.md"),
        "RETRY_FILE": os.path.join(WORKSPACE, "data/task_retries.json"),
        "selftest_result": {"ran": False},
    }


def _pf_attention_hooks_procedural(ctx, _pf_errors):
    """§3 Attention outcome, §4 Hooks/procedural memory, §4.5 Tool maker."""
    timings = {}
    task = ctx["task"]
    task_status = ctx["task_status"]
    exit_code = ctx["exit_code"]
    output_text = ctx["output_text"]
    preflight_data = ctx["preflight_data"]

    # §3 Attention outcome
    t3 = time.monotonic()
    try:
        importance = 0.8 if task_status == "success" else 0.9
        attention.submit(
            f"OUTCOME: {task_status.upper()} (exit {exit_code}) — {task[:80]}",
            source="heartbeat", importance=importance, relevance=0.8)
    except Exception as e:
        logging.debug("Attention outcome submit failed: %s", e)
    timings["attention_outcome"] = round(time.monotonic() - t3, 3)

    # §4 Hooks / procedural memory
    t4 = time.monotonic()
    if _hooks_available:
        hook_ctx = {
            "exit_code": exit_code, "task": task, "output_text": output_text,
            "procedure_id": ctx["proc_id"], "task_status": task_status,
            "task_duration": ctx["task_duration"],
            "procedure_injected": preflight_data.get("procedure_injected", False),
            "procedures_for_injection": preflight_data.get("procedures_for_injection", []),
        }
        _hook_results = hook_registry.run(HookPhase.POSTFLIGHT, hook_ctx)
        for hname, hr in _hook_results.items():
            if "error" in hr:
                log(f"Hook {hname} failed: {hr['error']}")
            timings[f"hook_{hname}"] = hr.get("elapsed_s", 0)
        hook_summary = ", ".join(f"{n}={r.get('elapsed_s', 0):.3f}s" for n, r in _hook_results.items())
        log(f"Lifecycle hooks: {len(_hook_results)} hooks ran ({hook_summary})")
    else:
        if exit_code == 0:
            if ctx["proc_id"] and record_use:
                try:
                    record_use(ctx["proc_id"], True)
                    log(f"Recorded successful use of procedure {ctx['proc_id']}")
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
                except Exception as e:
                    log(f"Procedural learning failed: {e}")
        elif ctx["proc_id"] and record_use:
            try:
                record_use(ctx["proc_id"], False)
            except Exception as e:
                logging.debug("Procedural record_use (failure path) failed: %s", e)
    timings["procedural"] = round(time.monotonic() - t4, 3)

    # §4.5 Tool maker
    t45 = time.monotonic()
    if tool_maker_extract and exit_code == 0:
        try:
            tm_result = tool_maker_extract(output_text, task, task_status)
            extracted = tm_result.get("extracted", 0)
            if extracted > 0:
                log(f"Tool maker: extracted {extracted} tools from task output")
        except Exception as e:
            log(f"Tool maker extraction failed (non-fatal): {e}")
    timings["tool_maker"] = round(time.monotonic() - t45, 3)

    return timings


def _pf_prompt_and_prediction(ctx):
    """§5.05 Prompt optimization + §5.1 Prediction auto-resolver."""
    # --- §5.05 Prompt optimization outcome recording ---
    preflight_data = ctx["preflight_data"]
    variant_id = preflight_data.get("prompt_variant_id", "")
    variant_task_type = preflight_data.get("prompt_variant_task_type", "")
    if po_record_outcome and variant_id:
        try:
            quality_score = _compute_prompt_quality(ctx["task_status"], ctx["output_text"], ctx["task_duration"])
            po_record_outcome(variant_id, variant_task_type, ctx["task_status"],
                              ctx["task_duration"], ctx["task"], quality_score=quality_score)
            log(f"Prompt optimization: recorded {ctx['task_status']} q={quality_score} for variant {variant_id[:50]}")
        except Exception as e:
            log(f"Prompt optimization recording failed (non-fatal): {e}")

    # --- §5.1 Prediction auto-resolver ---
    task = ctx["task"]
    actual = "success" if ctx["exit_code"] == 0 else "failure"
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
            if conf_auto_resolve:
                try:
                    ar = conf_auto_resolve(task, actual)
                    log(f"Prediction resolve (fallback): matched={ar['matched']}, remaining={ar['remaining_open']}")
                except Exception as e:
                    logging.debug("Prediction resolve fallback (conf_auto_resolve) failed: %s", e)
    elif conf_auto_resolve:
        try:
            ar = conf_auto_resolve(task, actual)
            if ar["matched"] > 0 or ar["stale_expired"] > 0:
                log(f"Prediction auto-resolve: matched={ar['matched']}, stale_expired={ar['stale_expired']}, remaining={ar['remaining_open']}")
            else:
                log(f"Prediction auto-resolve: no matches, remaining={ar['remaining_open']}")
        except Exception as e:
            log(f"Prediction auto-resolve failed: {e}")


def _pf_world_model_and_metagradient(ctx, _pf_errors):
    """§5.5 World model + §5.6 Meta-gradient RL."""
    timings = {}
    task = ctx["task"]
    task_status = ctx["task_status"]

    # §5.5 World model
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

    # §5.6 Meta-gradient RL
    t56 = time.monotonic()
    if meta_gradient_adapt:
        try:
            mg_result = meta_gradient_adapt()
            mg_status = mg_result.get("status", "unknown")
            if mg_status == "complete":
                J = mg_result.get("adapt_info", {}).get("J_validation", 0)
                log(f"Meta-gradient: adapted (J={J:.3f})")
            else:
                log(f"Meta-gradient: {mg_status}")
        except Exception as e:
            log(f"Meta-gradient adaptation failed: {e}")
    timings["meta_gradient_rl"] = round(time.monotonic() - t56, 3)

    return timings


def _pf_self_awareness(ctx):
    """§5.7 Self-representation + §5.75 Meta-thought."""
    timings = {}
    task = ctx["task"]
    task_status = ctx["task_status"]
    exit_code = ctx["exit_code"]
    task_duration = ctx["task_duration"]
    route_executor = ctx["route_executor"]

    # §5.7 Self-representation
    t57 = time.monotonic()
    if self_rep_update:
        try:
            sr_result = self_rep_update(task_status, task_text=task, duration_s=task_duration)
            sr_pred = sr_result.get("anticipation", {}).get("p_next_success")
            log(f"Self-representation: updated (p_next={sr_pred})")
        except Exception as e:
            log(f"Self-representation update failed: {e}")
    timings["self_representation"] = round(time.monotonic() - t57, 3)

    # §5.75 Meta-thought
    t575 = time.monotonic()
    if think_about_thinking:
        try:
            if task_status == "success":
                thought = f"Completed '{task[:80]}' successfully in {task_duration}s. Executor: {route_executor}."
            elif task_status == "timeout":
                thought = f"Task '{task[:80]}' timed out after {task_duration}s — may need decomposition or longer budget."
            else:
                thought = f"Task '{task[:80]}' failed (exit {exit_code}). Need to investigate root cause."
            think_about_thinking(thought)
            log(f"Meta-thought recorded: {task_status}")
        except Exception as e:
            log(f"Meta-thought generation failed: {e}")
    timings["meta_thought"] = round(time.monotonic() - t575, 3)

    return timings


def _pf_goal_engines(ctx):
    """§5.8 SOAR engine, §5.9 AtomSpace, §5.95 GWT workspace."""
    timings = {}
    task = ctx["task"]
    task_status = ctx["task_status"]
    exit_code = ctx["exit_code"]
    task_duration = ctx["task_duration"]

    # §5.8 SOAR engine
    t58 = time.monotonic()
    if get_soar_engine:
        try:
            soar = get_soar_engine()
            current = soar.current_goal()
            if current:
                alignment = soar.align_task(task)
                if alignment.get("aligned"):
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

    # §5.9 AtomSpace
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
                          tv={"strength": 1.0 if task_status == "success" else 0.2, "confidence": 0.8})
            atoms.decay_attention(0.97)
            log(f"AtomSpace: registered task outcome ({atoms.stats()['total_atoms']} atoms)")
        except Exception as e:
            log(f"AtomSpace update failed: {e}")
    timings["atomspace"] = round(time.monotonic() - t59, 3)

    # §5.95 GWT workspace
    t595 = time.monotonic()
    if WorkspaceBroadcast:
        try:
            outcome_importance = 0.85 if task_status == "success" else 0.95
            attention.submit(
                f"OUTCOME [{task_status}]: {task[:100]} (exit={exit_code}, {task_duration}s)",
                source="gwt_outcome", importance=outcome_importance, relevance=0.9)
            log("GWT: outcome codelet submitted for next broadcast cycle")
        except Exception as e:
            log(f"GWT outcome submission failed: {e}")
    timings["gwt_outcome"] = round(time.monotonic() - t595, 3)

    return timings


def _pf_prompt_predict_cognitive(ctx, _pf_errors):
    """§5.05 Prompt opt, §5.1 Prediction resolve, §5.5-5.95 Cognitive subsystems."""
    timings = {}

    # §5.05 Prompt optimization + §5.1 Prediction auto-resolver
    t505 = time.monotonic()
    _pf_prompt_and_prediction(ctx)
    timings["prompt_and_prediction"] = round(time.monotonic() - t505, 3)

    # §5.5-5.6 World model + Meta-gradient
    timings.update(_pf_world_model_and_metagradient(ctx, _pf_errors))

    # §5.7-5.75 Self-awareness
    timings.update(_pf_self_awareness(ctx))

    # §5.8-5.95 Goal engines (SOAR, AtomSpace, GWT)
    timings.update(_pf_goal_engines(ctx))

    return timings


def _compute_prompt_quality(task_status, output_text, task_duration):
    """Compute quality score for prompt optimization recording."""
    if task_status == "success" and output_text:
        q = 0.5
        out_len = len(output_text)
        if out_len > 500:
            q += 0.1
        if out_len > 2000:
            q += 0.1
        out_lower = output_text[-3000:].lower() if out_len > 3000 else output_text.lower()
        if "pass" in out_lower or "✓" in out_lower or "success" in out_lower:
            q += 0.1
        if "test" in out_lower and ("pass" in out_lower or "ok" in out_lower):
            q += 0.1
        if "error" in out_lower or "traceback" in out_lower:
            q -= 0.1
        return max(0.0, min(1.0, q))
    elif task_status == "timeout":
        return 0.1
    elif task_status == "failure":
        return 0.0
    return None


def _pf_broadcast_routing(ctx):
    """§6 Attention broadcast, §7 Routing log, §7.25 Benchmark, §7.3-7.35 Perf/latency."""
    timings = {}
    task = ctx["task"]
    task_status = ctx["task_status"]
    exit_code = ctx["exit_code"]
    preflight_data = ctx["preflight_data"]
    task_duration = ctx["task_duration"]

    # §6 Attention broadcast
    t6 = time.monotonic()
    try:
        attention.submit(f"Heartbeat task {task_status}: {task[:100]}", source="heartbeat",
                        importance=0.7 if task_status == "success" else 0.9, relevance=0.8)
    except Exception as e:
        logging.debug("Attention broadcast submit failed: %s", e)
    timings["attention_broadcast"] = round(time.monotonic() - t6, 3)

    # §7 Routing log
    t7 = time.monotonic()
    if log_decision and classify_task:
        try:
            cl = classify_task(task)
            log_decision(task, cl, ctx["route_executor"], "success" if exit_code == 0 else "failure")
        except Exception as e:
            log(f"Routing log failed: {e}")
    timings["routing_log"] = round(time.monotonic() - t7, 3)

    # §7.25 Benchmark
    t725 = time.monotonic()
    if benchmark_record:
        try:
            benchmark_record(preflight_data, exit_code, task_duration)
            log("Benchmark: brief v2 entry recorded")
        except Exception as e:
            log(f"Benchmark recording failed: {e}")
    timings["benchmark"] = round(time.monotonic() - t725, 3)

    # §7.3-7.35 Performance + latency (legacy path)
    if not _hooks_available:
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

    return timings


def _pf_self_test(ctx, _pf_errors):
    """§7.4 Self-test harness + §7.41 Pytest results capture."""
    timings = {}
    task = ctx["task"]
    exit_code = ctx["exit_code"]
    output_text = ctx["output_text"]
    WORKSPACE = ctx["WORKSPACE"]
    selftest_result = ctx["selftest_result"]

    t74 = time.monotonic()
    try:
        code_modified = False
        if output_text:
            code_indicators = [
                "Edit(", "Write(", "Edit tool", "Write tool", "wrote to ", "edited ",
                "modified ", "created ", ".py\n", "def ", "class ", "import ", "scripts/", "packages/",
            ]
            output_lower = output_text.lower()
            hits = sum(1 for ind in code_indicators if ind.lower() in output_lower)
            code_modified = hits >= 2

        if code_modified and exit_code == 0:
            import subprocess
            selftest_result["ran"] = True
            selftest_result["code_modified"] = True

            pytest_proc = subprocess.run(
                ["python3", "-m", "pytest", "tests/", "-q", "--tb=short", "-m", "not slow"],
                cwd=WORKSPACE, capture_output=True, text=True, timeout=60)
            selftest_result["pytest_exit"] = pytest_proc.returncode
            selftest_result["pytest_summary"] = pytest_proc.stdout.strip().split('\n')[-1] if pytest_proc.stdout.strip() else ""

            try:
                from clarvis.brain import brain as brain_instance
                hc = brain_instance.health_check()
                selftest_result["brain_healthy"] = hc.get("status") == "healthy"
                selftest_result["brain_memories"] = hc.get("total_memories", 0)
            except Exception as e:
                selftest_result["brain_healthy"] = False
                selftest_result["brain_error"] = str(e)

            tests_passed = selftest_result.get("pytest_exit", 1) == 0
            brain_ok = selftest_result.get("brain_healthy", False)
            selftest_result["all_passed"] = tests_passed and brain_ok

            if selftest_result["all_passed"]:
                log(f"SELF-TEST PASSED: pytest={selftest_result['pytest_summary']}, brain=healthy ({selftest_result.get('brain_memories', '?')} memories)")
            else:
                log(f"SELF-TEST FAILED: pytest_exit={selftest_result.get('pytest_exit')}, brain_ok={brain_ok}")
                _store_regression_alert(task, selftest_result, brain_ok)
        else:
            selftest_result["code_modified"] = code_modified
            if not code_modified:
                log("Self-test: skipped (no code modifications detected)")
    except Exception as e:
        log(f"Self-test harness failed: {e}")
        selftest_result["error"] = str(e)
        _pf_errors.append("self_test")
    timings["self_test"] = round(time.monotonic() - t74, 3)

    # §7.41 Pytest results capture
    try:
        if selftest_result.get("ran") and "pytest_exit" in selftest_result:
            _capture_pytest_results(selftest_result, WORKSPACE)
        else:
            _refresh_stale_test_results(WORKSPACE)
    except Exception as e:
        log(f"Test results capture failed (non-fatal): {e}")

    return timings


def _store_regression_alert(task, selftest_result, brain_ok):
    """Store regression alert in brain and push P0 fix task."""
    try:
        from clarvis.brain import brain as brain_instance
        alert = (f"REGRESSION ALERT: Self-test failed after task '{task[:80]}'. "
                 f"pytest_exit={selftest_result.get('pytest_exit')}, brain_ok={brain_ok}. "
                 f"pytest: {selftest_result.get('pytest_summary', 'N/A')}")
        brain_instance.store(alert, collection="clarvis-learnings", importance=0.95,
                            tags=["regression", "self-test"], source="self_test_harness")
    except Exception as e:
        logging.debug("Storing regression alert in brain failed: %s", e)
    try:
        from clarvis.queue.writer import add_task
        fix_task = f"FIX REGRESSION: Self-test failed after '{task[:60]}'. Review and fix immediately."
        add_task(fix_task, priority="P0", source="self_test_harness")
        log("Pushed P0 regression fix task to QUEUE.md")
    except Exception as e:
        logging.debug("Pushing P0 regression fix task to QUEUE.md failed: %s", e)


def _capture_pytest_results(selftest_result, WORKSPACE):
    """Write test results JSON from selftest data."""
    import re as _re74
    summary_line = selftest_result.get("pytest_summary", "")
    _passed = _failed = 0
    _m = _re74.search(r'(\d+) passed', summary_line)
    if _m:
        _passed = int(_m.group(1))
    _m = _re74.search(r'(\d+) failed', summary_line)
    if _m:
        _failed = int(_m.group(1))
    _test_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "passed": _passed, "failed": _failed, "errors": 0, "total": _passed + _failed,
        "pytest_exit_code": selftest_result.get("pytest_exit", -1),
        "test_suites": ["tests/"], "source": "postflight_self_test",
    }
    _test_results_path = os.path.join(WORKSPACE, "data", "test_results.json")
    with open(_test_results_path, 'w') as _tf:
        json.dump(_test_data, _tf, indent=2)
    log(f"Captured test results: {_passed} passed, {_failed} failed → data/test_results.json")


def _refresh_stale_test_results(WORKSPACE):
    """Refresh test_results.json if stale (>24h)."""
    _test_results_path = os.path.join(WORKSPACE, "data", "test_results.json")
    _stale = True
    if os.path.exists(_test_results_path):
        _age = time.time() - os.path.getmtime(_test_results_path)
        _stale = _age > 86400
    if not _stale:
        return
    import subprocess as _sp74
    _pr = _sp74.run(
        ["python3", "-m", "pytest", "tests/", "-q", "--tb=no", "-m", "not slow"],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=60)
    import re as _re74b
    _m = _re74b.search(r'(\d+) passed', _pr.stdout)
    _p = int(_m.group(1)) if _m else 0
    _m = _re74b.search(r'(\d+) failed', _pr.stdout)
    _f = int(_m.group(1)) if _m else 0
    with open(_test_results_path, 'w') as _tf:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "passed": _p, "failed": _f, "errors": 0, "total": _p + _f,
            "pytest_exit_code": _pr.returncode,
            "test_suites": ["tests/"], "source": "postflight_stale_refresh",
        }, _tf, indent=2)
    log(f"Refreshed stale test results: {_p} passed, {_f} failed")


def _compute_code_quality(exit_code, output_text, task_duration, output_file):
    """Compute composite code quality score (0-1)."""
    q_completion = 1.0 if exit_code == 0 else (0.3 if exit_code == 124 else 0.0)

    _out_lower = output_text.lower() if output_text else ""
    _traceback_count = _out_lower.count("traceback (most recent")
    _error_count = _out_lower.count("error:") + _out_lower.count("error ")
    q_output = max(0.0, 1.0 - (_traceback_count * 0.3) - (min(_error_count, 5) * 0.1))

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
        cp_score = progress_data.get("progress_score", 0.0)
        if cp_score > 0.4:
            q_efficiency = min(0.8, q_efficiency + cp_score * 0.3)

    return q_completion, q_output, q_efficiency, progress_data


def _pf_code_gen_outcome(ctx, output_file, _pf_errors):
    """§7.42 Code-gen outcome recording."""
    timings = {}
    t742 = time.monotonic()
    try:
        import subprocess
        ws = ctx["WORKSPACE"]
        diff_proc = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD~1", "HEAD", "--", "*.py"],
            capture_output=True, text=True, timeout=10, cwd=ws)
        diff_proc2 = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", "--", "*.py"],
            capture_output=True, text=True, timeout=10, cwd=ws)
        changed_py = set()
        for line in (diff_proc.stdout + "\n" + diff_proc2.stdout).strip().split("\n"):
            line = line.strip()
            if line.endswith(".py"):
                changed_py.add(line)
        ctx["changed_py"] = changed_py

        if changed_py:
            syntax_ok, syntax_fail, syntax_errors = _syntax_check_files(changed_py, ws)
            total_files = syntax_ok + syntax_fail
            syntax_ratio = syntax_ok / total_files if total_files > 0 else 1.0

            q_completion, q_output, q_efficiency, progress_data = _compute_code_quality(
                ctx["exit_code"], ctx["output_text"], ctx["task_duration"], output_file)
            quality_score = round(0.30 * q_completion + 0.25 * syntax_ratio + 0.25 * q_output + 0.20 * q_efficiency, 3)

            outcome_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "task": ctx["task"][:200], "task_status": ctx["task_status"],
                "files_touched": len(changed_py), "files_list": sorted(changed_py)[:20],
                "syntax_ok": syntax_ok, "syntax_fail": syntax_fail,
                "syntax_errors": syntax_errors[:5], "syntax_ratio": syntax_ratio,
                "exit_code": ctx["exit_code"], "duration_s": ctx["task_duration"],
                "quality_score": quality_score,
                "quality_breakdown": {
                    "completion": round(q_completion, 2), "syntax": round(syntax_ratio, 2),
                    "output_cleanliness": round(q_output, 2), "efficiency": round(q_efficiency, 2),
                },
            }
            if progress_data:
                outcome_entry["progress_checkpoints"] = progress_data.get("checkpoints", 0)
                outcome_entry["progress_score"] = progress_data.get("progress_score", 0.0)

            outcomes_file = os.path.join(ws, "data", "code_gen_outcomes.jsonl")
            os.makedirs(os.path.dirname(outcomes_file), exist_ok=True)
            with open(outcomes_file, "a") as of:
                of.write(json.dumps(outcome_entry) + "\n")
            log(f"Code-gen outcome: {len(changed_py)} files, syntax={syntax_ok}/{total_files} clean, "
                f"quality={quality_score:.2f}, task={ctx['task_status']}")
        else:
            log("Code-gen outcome: no .py changes detected")
    except Exception as e:
        log(f"Code-gen outcome recording failed: {e}")
        _pf_errors.append("code_gen_outcome")
    timings["code_gen_outcome"] = round(time.monotonic() - t742, 3)
    return timings


def _syntax_check_files(changed_py, ws):
    """Syntax-check each changed .py file. Returns (ok, fail, errors)."""
    syntax_ok = syntax_fail = 0
    syntax_errors = []
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
    return syntax_ok, syntax_fail, syntax_errors


def _pf_complexity_gate(ctx):
    """§7.421 Structural review: advisory report on changed files (report-only).

    Replaces the old line-count gate. Uses structural_complexity_risk() for
    role-aware, multi-signal analysis. Emits findings to data/structural_review.json.
    NEVER auto-creates queue tasks from structural findings.
    """
    timings = {}
    t7421 = time.monotonic()
    try:
        import subprocess
        _cg_changed = ctx.get("changed_py", set())
        if not _cg_changed:
            _ws = ctx["WORKSPACE"]
            for _cmd in [
                ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD~1", "HEAD", "--", "*.py"],
                ["git", "diff", "--name-only", "--diff-filter=ACMR", "--", "*.py"],
            ]:
                _p = subprocess.run(_cmd, capture_output=True, text=True, timeout=10, cwd=_ws)
                for _l in _p.stdout.strip().split("\n"):
                    _l = _l.strip()
                    if _l.endswith(".py"):
                        _cg_changed.add(_l)

        if _cg_changed:
            try:
                from clarvis.metrics.quality import structural_complexity_risk
            except ImportError:
                structural_complexity_risk = None

            _ws = ctx["WORKSPACE"]
            reviews = []
            for relpath in sorted(_cg_changed)[:15]:
                fpath = os.path.join(_ws, relpath)
                if not os.path.exists(fpath):
                    continue
                if structural_complexity_risk:
                    review = structural_complexity_risk(fpath)
                    review["file"] = relpath  # use relative path
                    if review["candidates"]:
                        reviews.append(review)

            # Determine overall recommendation level
            has_high = any(r["risk"] == "high" for r in reviews)
            has_medium = any(r["risk"] == "medium" for r in reviews)
            if has_high:
                recommendation = "REVIEW_SOON"
            elif has_medium:
                recommendation = "REVIEW_LATER"
            else:
                recommendation = "OK"

            # Emit artifact (report-only, never feeds queue)
            artifact = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "recommendation": recommendation,
                "files_analyzed": len(_cg_changed),
                "flagged_files": reviews,
            }
            artifact_path = os.path.join(_ws, "data", "structural_review.json")
            try:
                import json as _json
                os.makedirs(os.path.dirname(artifact_path), exist_ok=True)
                with open(artifact_path, "w") as _f:
                    _json.dump(artifact, _f, indent=2)
            except Exception:
                pass

            total_candidates = sum(len(r["candidates"]) for r in reviews)
            if total_candidates:
                log(f"Structural review: {total_candidates} candidate(s) across {len(reviews)} file(s), "
                    f"recommendation={recommendation} (report-only)")
            else:
                log("Structural review: no concerns in changed files")
        else:
            log("Structural review: no changed Python files")
    except Exception as e:
        log(f"Structural review failed (non-fatal): {e}")
    timings["complexity_gate"] = round(time.monotonic() - t7421, 3)
    return timings


def _pf_code_validation(ctx, _pf_errors):
    """§7.43 Code validation gate (Self-Refine pattern)."""
    timings = {}
    t743 = time.monotonic()
    if cv_validate_output or cv_validate_file:
        try:
            cv_file_errors = []
            cv_output_result = None

            if cv_validate_output and ctx["output_text"]:
                cv_output_result = cv_validate_output(ctx["output_text"], ctx["task"])

            if cv_validate_file:
                import subprocess
                ws = ctx["WORKSPACE"]
                _cvd1 = subprocess.run(
                    ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD~1", "HEAD", "--", "*.py"],
                    capture_output=True, text=True, timeout=10, cwd=ws)
                _cvd2 = subprocess.run(
                    ["git", "diff", "--name-only", "--diff-filter=ACMR", "--", "*.py"],
                    capture_output=True, text=True, timeout=10, cwd=ws)
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
                            cv_file_errors.append({"file": relpath, "errors": fv["errors"][:3], "refinement": fv["refinement"]})

            has_output_errs = cv_output_result and cv_output_result.get("has_errors", False)
            has_file_errs = len(cv_file_errors) > 0

            if has_output_errs or has_file_errs:
                _handle_cv_failures(ctx, cv_output_result, cv_file_errors, has_output_errs)
            else:
                log("CODE VALIDATION: all checks passed")
                _tag_cv_pass(ctx["task"])
        except Exception as e:
            log(f"Code validation gate failed (non-fatal): {e}")
            _pf_errors.append("code_validation")
    timings["code_validation"] = round(time.monotonic() - t743, 3)
    return timings


def _handle_cv_failures(ctx, cv_output_result, cv_file_errors, has_output_errs):
    """Handle code validation failures: persist, tag episode, auto-queue fix."""
    refinement_parts = []
    if has_output_errs:
        refinement_parts.append(cv_output_result["refinement"])
    for fe in cv_file_errors[:3]:
        refinement_parts.append(f"File {fe['file']}: {fe['refinement']}")
    refinement_prompt = "CODE VALIDATION ERRORS:\n" + "\n".join(refinement_parts)
    log(f"CODE VALIDATION: {len(cv_file_errors)} file(s) with issues, output_errors={has_output_errs}")

    # Tag episode
    if EpisodicMemory:
        try:
            em_cv = EpisodicMemory()
            if em_cv.episodes:
                latest = em_cv.episodes[-1]
                if latest.get("task", "")[:60] == ctx["task"][:60]:
                    latest.setdefault("tags", []).append("code_validation:fail")
                    latest["code_validation"] = {
                        "passed": False, "file_errors": len(cv_file_errors),
                        "output_errors": has_output_errs, "refinement": refinement_prompt[:300],
                    }
                    em_cv._save()
        except Exception as e:
            logging.debug("Tagging episode with code_validation:fail failed: %s", e)

    # Persist
    cv_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(), "task": ctx["task"][:200],
        "validation_passed": False, "file_errors": len(cv_file_errors),
        "output_errors": has_output_errs, "refinement_prompt": refinement_prompt[:500],
    }
    cv_outcomes_file = os.path.join(ctx["WORKSPACE"], "data", "code_validation_outcomes.jsonl")
    os.makedirs(os.path.dirname(cv_outcomes_file), exist_ok=True)
    with open(cv_outcomes_file, "a") as cvf:
        cvf.write(json.dumps(cv_entry) + "\n")

    # Auto-queue fix if many errors
    total_cv_errors = sum(len(fe["errors"]) for fe in cv_file_errors)
    if has_output_errs and cv_output_result:
        total_cv_errors += len(cv_output_result.get("errors", []))
    if total_cv_errors > 3:
        try:
            from clarvis.queue.writer import add_task as _cv_add_task
            affected_files = ", ".join(fe["file"] for fe in cv_file_errors[:3])
            fix_desc = (f"[CODE_QUALITY_FIX] Fix {total_cv_errors} code validation errors "
                        f"in: {affected_files or 'output'} — task: {ctx['task'][:80]}")
            if _cv_add_task(fix_desc, priority="P1", source="code_validation"):
                log(f"CODE VALIDATION FEEDBACK: injected P1 fix task ({total_cv_errors} errors)")
        except Exception as e:
            log(f"CODE VALIDATION FEEDBACK: queue injection failed: {e}")


def _tag_cv_pass(task):
    """Tag latest episode with code_validation:pass."""
    if EpisodicMemory:
        try:
            em_cv = EpisodicMemory()
            if em_cv.episodes:
                latest = em_cv.episodes[-1]
                if latest.get("task", "")[:60] == task[:60]:
                    latest.setdefault("tags", []).append("code_validation:pass")
                    em_cv._save()
        except Exception as e:
            logging.debug("Tagging episode with code_validation:pass failed: %s", e)


def _pf_gates(ctx, _pf_errors):
    """§7.45 Perf gate, §7.46 Memory quality gate, §7.47 Structural health."""
    timings = {}
    selftest_result = ctx["selftest_result"]

    # §7.45 Performance gate
    t745 = time.monotonic()
    _code_mod = selftest_result.get("code_modified", False) or selftest_result.get("ran", False)
    if perf_gate_run and _code_mod and ctx["exit_code"] == 0:
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

    # §7.46 Memory quality gate
    timings.update(_pf_memory_quality_gate(ctx, _pf_errors))

    # §7.47 Structural health (legacy path)
    if not _hooks_available:
        t747 = time.monotonic()
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
                    "violations": ih_report["violations"], "healthy": ih_report["healthy"],
                }
                struct_hist_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'structural_health_history.jsonl')
                ih_entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "type": "structural_health", "metrics": ih_metrics}
                with open(struct_hist_file, "a") as hf:
                    hf.write(json.dumps(ih_entry) + "\n")
                status_str = "HEALTHY" if ih_metrics["healthy"] else f"DEGRADED ({', '.join(ih_metrics['violations'])})"
                log(f"STRUCTURAL: {status_str} — SCCs={ih_metrics['scc_count']}, depth={ih_metrics['max_depth']}, "
                    f"fan_in={ih_metrics['max_fan_in']}, fan_out={ih_metrics['max_fan_out']}, modules={ih_metrics['total_modules']}")
            except Exception as e:
                log(f"Structural health check failed: {e}")
        timings["structural_health"] = round(time.monotonic() - t747, 3)

    return timings


def _pf_memory_quality_gate(ctx, _pf_errors):
    """§7.46 Memory quality gates."""
    timings = {}
    t746 = time.monotonic()
    QUALITY_GATE_FILE = os.path.join(ctx["WORKSPACE"], "data", "memory_quality_gate.json")
    QUALITY_BASELINE_FILE = os.path.join(ctx["WORKSPACE"], "data", "memory_quality_baseline.json")
    try:
        if rq_tracker:
            rq_report = rq_tracker.report(days=1)
            if rq_report.get("status") != "no_data" and rq_report.get("total_events", 0) >= 5:
                baseline = None
                if os.path.exists(QUALITY_BASELINE_FILE):
                    with open(QUALITY_BASELINE_FILE) as bf:
                        baseline = json.load(bf)
                current_hit_rate = rq_report.get("hit_rate")
                current_dead_rate = rq_report.get("dead_recall_rate", 0)
                current_avg_dist = rq_report.get("avg_distance_overall")

                if baseline is None:
                    baseline = {
                        "hit_rate": current_hit_rate, "dead_recall_rate": current_dead_rate,
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
                    _evaluate_quality_gate(current_hit_rate, current_dead_rate, current_avg_dist,
                                           baseline, ctx["task"], QUALITY_GATE_FILE, QUALITY_BASELINE_FILE)
            else:
                log(f"QUALITY GATE: insufficient data ({rq_report.get('total_events', 0)} events, need >=5)")
    except Exception as e:
        log(f"Memory quality gate failed (non-fatal): {e}")
    timings["memory_quality_gate"] = round(time.monotonic() - t746, 3)
    return timings


def _evaluate_quality_gate(current_hit_rate, current_dead_rate, current_avg_dist,
                           baseline, task, QUALITY_GATE_FILE, QUALITY_BASELINE_FILE):
    """Compare quality metrics against baseline and act on violations."""
    violations = []
    bl_hit = baseline.get("hit_rate")
    bl_dead = baseline.get("dead_recall_rate", 0)
    bl_dist = baseline.get("avg_distance")

    if current_hit_rate is not None and bl_hit is not None:
        if current_hit_rate < bl_hit - 0.15 or current_hit_rate < 0.40:
            violations.append(f"hit_rate={current_hit_rate:.3f} (baseline={bl_hit:.3f})")
    if current_dead_rate > bl_dead + 0.10 or current_dead_rate > 0.35:
        violations.append(f"dead_recall_rate={current_dead_rate:.3f} (baseline={bl_dead:.3f})")
    if current_avg_dist is not None and bl_dist is not None:
        if current_avg_dist > bl_dist + 0.20 or current_avg_dist > 1.6:
            violations.append(f"avg_distance={current_avg_dist:.4f} (baseline={bl_dist:.4f})")

    if violations:
        log(f"QUALITY GATE VIOLATION: {'; '.join(violations)}")
        gate_data = {
            "status": "DEGRADED", "violations": violations,
            "current": {"hit_rate": current_hit_rate, "dead_recall_rate": current_dead_rate, "avg_distance": current_avg_dist},
            "baseline": baseline, "triggered_at": datetime.now(timezone.utc).isoformat(),
            "triggered_by_task": task[:120],
        }
        os.makedirs(os.path.dirname(QUALITY_GATE_FILE), exist_ok=True)
        with open(QUALITY_GATE_FILE, "w") as gf:
            json.dump(gate_data, gf, indent=2)
        try:
            from clarvis.queue.writer import add_task
            repair_desc = (f"[MEMORY_REPAIR] Memory quality degraded — {'; '.join(violations)}. "
                           f"Run retrieval_quality.py baseline, check recent brain changes, fix retrieval before resuming new features.")
            if add_task(repair_desc, priority="P0", source="memory_quality_gate"):
                log("QUALITY GATE: pushed P0 repair task to QUEUE.md")
        except Exception as qe:
            log(f"QUALITY GATE: failed to push repair task: {qe}")
    else:
        if os.path.exists(QUALITY_GATE_FILE):
            os.remove(QUALITY_GATE_FILE)
        log(f"QUALITY GATE: PASS (hit_rate={current_hit_rate}, dead_rate={current_dead_rate:.3f}, avg_dist={current_avg_dist})")
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


def _pf_retrieval_feedback(ctx, _pf_errors):
    """§7.48 Retrieval feedback, §7.49 Memory evolution, §7.495 Action accuracy."""
    timings = {}
    task = ctx["task"]
    task_status = ctx["task_status"]
    preflight_data = ctx["preflight_data"]
    output_text = ctx["output_text"]

    # §7.48 Retrieval feedback
    t748 = time.monotonic()
    if retrieval_record_feedback:
        try:
            rv = preflight_data.get("retrieval_verdict", "SKIPPED")
            max_score = preflight_data.get("retrieval_max_score")
            if max_score is None:
                ret_data = preflight_data.get("retrieval_data", {})
                max_score = ret_data.get("max_score") if isinstance(ret_data, dict) else None
            fb_result = retrieval_record_feedback(verdict=rv, outcome=task_status, max_score=max_score, task=task[:200])
            log(f"RETRIEVAL FEEDBACK: {rv}×{task_status} → reward={fb_result['reward']:.2f}, "
                f"EMA={fb_result['ema_success_rate']:.3f}, total={fb_result['total_episodes']}"
                + (", suggestions generated!" if fb_result.get("suggestions_generated") else ""))

            _pf_context_relevance(ctx, rv, preflight_data, output_text)
        except Exception as e:
            log(f"Retrieval feedback recording failed (non-fatal): {e}")
            _pf_errors.append("retrieval_feedback")
    timings["retrieval_feedback"] = round(time.monotonic() - t748, 3)

    # §7.49 Memory evolution
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

    # §7.495 Action accuracy guard
    t7495 = time.monotonic()
    try:
        if EpisodicMemory:
            _em_aa = EpisodicMemory()
            _recent_eps = _em_aa.episodes[-20:] if len(_em_aa.episodes) >= 20 else _em_aa.episodes
            if len(_recent_eps) >= 10:
                _aa_successes = sum(1 for e in _recent_eps if e.get("outcome") == "success")
                _aa_soft = sum(1 for e in _recent_eps if e.get("outcome") == "soft_failure")
                _aa_timeouts = sum(1 for e in _recent_eps if e.get("outcome") == "timeout")
                _aa_crashes = sum(1 for e in _recent_eps if e.get("outcome") == "crash")
                _aa_denom = len(_recent_eps) - _aa_soft - _aa_timeouts - _aa_crashes
                if _aa_denom > 0:
                    _aa_score = round(_aa_successes / _aa_denom, 3)
                    log(f"ACTION ACCURACY: trailing-{len(_recent_eps)} = {_aa_score:.3f} "
                        f"({_aa_successes}/{_aa_denom} excl {_aa_soft} soft_fail, {_aa_timeouts} timeout, {_aa_crashes} crash)")
                    if _aa_score < 0.95:
                        _failing_ids = [e.get("id", e.get("task", "?")[:40]) for e in _recent_eps if e.get("outcome") == "failure"]
                        _diag_task = (f"[ACTION_ACCURACY_DIAGNOSTIC] Action accuracy dropped to {_aa_score:.3f} "
                                      f"(threshold: 0.95). Failing episodes: {', '.join(_failing_ids[:5])}. Investigate root causes and fix.")
                        try:
                            from clarvis.queue.writer import add_task
                            if add_task(_diag_task, priority="P1", source="action_accuracy_guard"):
                                log(f"ACTION ACCURACY GUARD: pushed P1 diagnostic (score={_aa_score})")
                        except Exception as e:
                            logging.debug("Action accuracy guard: pushing P1 diagnostic task failed: %s", e)
                else:
                    log(f"ACTION ACCURACY: insufficient non-timeout/non-soft episodes in trailing-{len(_recent_eps)}")
    except Exception as e:
        log(f"Action accuracy guard failed (non-fatal): {e}")
    timings["action_accuracy_guard"] = round(time.monotonic() - t7495, 3)

    return timings


def _pf_context_relevance(ctx, rv, preflight_data, output_text):
    """Score section-level context relevance and update adaptive MMR."""
    task = ctx["task"]
    task_status = ctx["task_status"]
    brief_text = preflight_data.get("context_brief", "")
    if not (brief_text and output_text and score_section_relevance):
        return
    cr_result = score_section_relevance(brief_text, output_text, task=task, outcome=task_status)
    if classify_mmr_category:
        cr_result["mmr_category"] = classify_mmr_category(task)
    noise_ratio = round(1.0 - cr_result["overall"], 4)
    cr_result["noise_ratio"] = noise_ratio
    log(f"CONTEXT RELEVANCE: {cr_result['sections_referenced']}/{cr_result['sections_total']} "
        f"sections referenced ({cr_result['overall']:.1%}), noise={noise_ratio:.1%}"
        + (f" [{cr_result.get('mmr_category', '?')}]" if classify_mmr_category else ""))
    if cr_record:
        cr_record(cr_result)
    if EpisodicMemory:
        try:
            em_nr = EpisodicMemory()
            if em_nr.episodes:
                latest_ep = em_nr.episodes[-1]
                if latest_ep.get("task", "")[:60] == task[:60]:
                    latest_ep["noise_ratio"] = noise_ratio
                    latest_ep["context_relevance"] = cr_result["overall"]
                    em_nr._save()
                    log(f"NOISE RATIO: {noise_ratio:.1%} tagged on episode {latest_ep.get('id', '?')}")
        except Exception as e:
            log(f"Noise ratio tagging failed (non-fatal): {e}")

    if mmr_update_lambdas:
        _mmr_skip_reason = None
        if rv in ("NO_RETRIEVAL", "SKIPPED"):
            _mmr_skip_reason = f"verdict={rv}"
        else:
            try:
                _mmr_state_path = os.path.join(ctx["WORKSPACE"], "data", "retrieval_quality", "adaptive_mmr_state.json")
                if os.path.exists(_mmr_state_path):
                    with open(_mmr_state_path) as _f:
                        _mmr_st = json.load(_f)
                    _total_eps = sum(v.get("episodes", 0) for v in _mmr_st.values() if isinstance(v, dict))
                    if _total_eps < 10:
                        _mmr_skip_reason = f"episodes={_total_eps}<10"
            except Exception as e:
                logging.debug("Reading adaptive MMR state file failed: %s", e)
        if _mmr_skip_reason:
            log(f"ADAPTIVE MMR: skipped update ({_mmr_skip_reason})")
        else:
            try:
                updated = mmr_update_lambdas()
                log(f"ADAPTIVE MMR: lambdas updated — {updated}")
            except Exception as e:
                logging.debug("Adaptive MMR lambda update failed: %s", e)


def _pf_cost_and_budget(ctx, _pf_errors):
    """§7.5 Cost tracking, §7.6 Budget alert."""
    timings = {}
    task = ctx["task"]
    preflight_data = ctx["preflight_data"]
    output_text = ctx["output_text"]
    task_duration = ctx["task_duration"]

    t75 = time.monotonic()
    if cost_tracker:
        try:
            real_cost = preflight_data.get("real_cost_usd")
            real_in_tokens = preflight_data.get("actual_input_tokens")
            real_out_tokens = preflight_data.get("actual_output_tokens")
            real_gen_id = preflight_data.get("generation_id", "")
            real_model = preflight_data.get("actual_model", "")
            executor = preflight_data.get("route_executor", "claude")
            if real_model:
                model = real_model
            elif executor in ("gemini", "openrouter"):
                model = preflight_data.get("route_model", "minimax/minimax-m2.5")
            else:
                model = "claude-code"

            if real_cost is not None and real_in_tokens is not None:
                entry = cost_tracker.log_real(model=model, input_tokens=real_in_tokens,
                    output_tokens=real_out_tokens or 0, cost_usd=real_cost, source="cron_autonomous",
                    task=task, duration_s=task_duration, generation_id=real_gen_id)
                log(f"Cost logged (REAL): ${entry.cost_usd:.6f} ({model}, in={real_in_tokens}, out={real_out_tokens})")
            else:
                context_brief = preflight_data.get("context_brief", "")
                episodic_hints = preflight_data.get("episodic_hints", "")
                input_text = f"{task} {context_brief} {episodic_hints}"
                est_input = estimate_tokens(input_text, model) + 500
                est_output = estimate_tokens(output_text[:4000], model) if output_text else 300
                entry = cost_tracker.log(model=model, input_tokens=est_input, output_tokens=est_output,
                    source="cron_autonomous", task=task, duration_s=task_duration)
                log(f"Cost logged (est): ${entry.cost_usd:.6f} ({model}, in={est_input}, out={est_output})")
        except Exception as e:
            log(f"Cost tracking failed: {e}")
            _pf_errors.append("cost_tracking")
    timings["cost_tracking"] = round(time.monotonic() - t75, 3)

    t76 = time.monotonic()
    try:
        import subprocess
        subprocess.run(["python3", os.path.join(os.path.dirname(__file__), "budget_alert.py")],
                      timeout=15, capture_output=True)
    except Exception as e:
        log(f"Budget alert check failed: {e}")
    timings["budget_alert"] = round(time.monotonic() - t76, 3)

    return timings


def _pf_evolution_synthesis(ctx, _pf_errors):
    """§8 Evolution loop, §8.5 Periodic synthesis."""
    timings = {}
    task = ctx["task"]
    task_status = ctx["task_status"]
    exit_code = ctx["exit_code"]
    output_text = ctx["output_text"]
    task_duration = ctx["task_duration"]

    t8 = time.monotonic()
    is_crash = ctx.get("preflight_data", {}).get("crash_guard", False)
    if exit_code != 0 and exit_code != 124 and not is_crash and EvolutionLoop:
        try:
            evo = EvolutionLoop()
            failure_id = evo.capture_failure("cron_autonomous", f"Exit code {exit_code} running task",
                context=task, exit_code=exit_code, stderr=output_text[-2000:])
            log(f"Evolution: captured failure {failure_id}")
            evo.evolve(failure_id)
            log(f"Evolution: fix generated for {failure_id}")
        except Exception as e:
            log(f"Evolution loop failed: {e}")
            _pf_errors.append("evolution")
    elif exit_code == 124 and EvolutionLoop:
        try:
            evo = EvolutionLoop()
            evo.capture_failure("cron_autonomous", f"Timeout (exit 124) — task exceeded {task_duration}s",
                context=task, exit_code=124)
            log("Evolution: timeout captured (no evolve)")
        except Exception as e:
            log(f"Evolution timeout capture failed: {e}")
    timings["evolution"] = round(time.monotonic() - t8, 3)

    if not _hooks_available:
        t85_synth = time.monotonic()
        if EpisodicMemory:
            try:
                em_synth = EpisodicMemory()
                if len(em_synth.episodes) % 10 == 0 and len(em_synth.episodes) > 0:
                    synth = em_synth.synthesize()
                    log(f"Periodic synthesis: {synth.get('goals_count', 0)} goals, success_rate={synth.get('success_rate', '?')}")
                    backfilled = em_synth.backfill_causal_links()
                    if backfilled:
                        log(f"Causal backfill: +{backfilled} links")
            except Exception as e:
                log(f"Periodic synthesis failed: {e}")
        timings["periodic_synthesis"] = round(time.monotonic() - t85_synth, 3)

    return timings


def _pf_queue_update(ctx, _pf_errors):
    """§10 Queue update — mark task complete or handle timeout retry.

    Dual-path: legacy queue_writer (marks [x] in QUEUE.md) + queue engine v2
    (sidecar state + run records for observability).
    """
    task = ctx["task"]
    exit_code = ctx["exit_code"]
    preflight_data = ctx["preflight_data"]
    task_status = ctx["task_status"]

    if not task or task == "unknown":
        return

    # --- Queue Engine v2: end run record + sidecar state ---
    task_tag = None
    if isinstance(preflight_data, dict):
        task_tag = preflight_data.get("task_tag")
    run_id = ctx.get("queue_run_id")

    if queue_engine and task_tag:
        try:
            if run_id:
                queue_engine.end_run(
                    run_id=run_id,
                    outcome=task_status,
                    exit_code=exit_code,
                    error=ctx.get("error_evidence", ""),
                    duration_s=ctx.get("task_duration"),
                )
                log(f"Queue engine: ended run {run_id} ({task_status})")
            else:
                # No run_id from preflight — just update sidecar state directly
                if task_status == "success":
                    queue_engine.mark_succeeded(task_tag, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
                else:
                    queue_engine.mark_failed(task_tag, ctx.get("error_evidence", task_status))
                log(f"Queue engine: marked [{task_tag}] {task_status} (no run_id)")
        except Exception as e:
            log(f"Queue engine update failed (non-fatal): {e}")

    # --- Legacy path: queue_writer marks [x] in QUEUE.md ---
    try:
        if exit_code == 0:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            task_for_marking = task
            if task_tag:
                task_for_marking = f"[{task_tag}]"
            result_mark = _mark_task_in_queue(task_for_marking, timestamp, ctx["QUEUE_FILE"], ctx["QUEUE_ARCHIVE"])
            if result_mark == "marked":
                log("Marked task complete in QUEUE.md")
            elif result_mark == "archived":
                log(f"Task already in QUEUE_ARCHIVE.md: {task[:60]}")
            else:
                log(f"Task not found in QUEUE.md for completion: {task[:60]}...")
        elif exit_code == 124:
            _handle_timeout_retry(task, ctx["RETRY_FILE"], ctx["QUEUE_FILE"], ctx["QUEUE_ARCHIVE"])
    except Exception as e:
        log(f"Queue completion marking failed: {e}")
        _pf_errors.append("queue_update")


def _pf_finalize(ctx, _pf_errors):
    """§10-13: Queue update, attention save, queue hygiene, cognitive workspace, obligations, directives."""
    timings = {}
    task = ctx["task"]
    task_status = ctx["task_status"]

    # §10 Queue update
    t10 = time.monotonic()
    _pf_queue_update(ctx, _pf_errors)
    timings["queue_update"] = round(time.monotonic() - t10, 3)

    # §11 Attention save
    try:
        attention.save()
    except Exception as e:
        logging.debug("Attention save failed: %s", e)

    # §12 Queue hygiene
    try:
        from clarvis.queue.writer import archive_completed
        archived = archive_completed()
        if archived > 0:
            log(f"Queue hygiene: archived {archived} completed items")
    except Exception as e:
        logging.debug("Queue hygiene archive_completed failed: %s", e)

    # §13 Cognitive workspace
    if cog_workspace:
        try:
            lesson = "Completed successfully" if task_status == "success" else "Failed — check episode for details"
            cw_result = cog_workspace.close_task(outcome=task_status, lesson=lesson)
            reuse = cw_result.get("reuse_rate", 0)
            log(f"Cognitive workspace: closed task, reuse_rate={reuse:.1%}, buffers={cw_result.get('buffers', {})}")
        except Exception as e:
            log(f"Cognitive workspace close failed: {e}")

    # Obligation postflight
    t_ob = time.monotonic()
    if OT_Postflight:
        try:
            ob_tracker = OT_Postflight()
            ob_tracker.postflight_record(task, task_status, ctx["output_text"])
            log(f"Obligation postflight recorded ({task_status})")
        except Exception as e:
            log(f"Obligation postflight failed (non-fatal): {e}")
            _pf_errors.append("obligation_postflight")
    timings["obligation_postflight"] = round(time.monotonic() - t_ob, 3)

    # Directive postflight
    t_dir = time.monotonic()
    if DE_Postflight:
        try:
            deng = DE_Postflight()
            deng._sweep_expiry()
            for d in deng.list_active():
                if d["scope"] == "one_shot" and deng._is_relevant(d, task):
                    d["times_enforced"] = d.get("times_enforced", 0) + 1
                    deng._save()
            log(f"Directive postflight: {len(deng.list_active())} active directives")
        except Exception as e:
            log(f"Directive postflight failed (non-fatal): {e}")
            _pf_errors.append("directive_postflight")
    timings["directive_postflight"] = round(time.monotonic() - t_dir, 3)

    return timings


def _handle_timeout_retry(task, RETRY_FILE, QUEUE_FILE, QUEUE_ARCHIVE):
    """Handle timeout retry tracking and auto-skip after max retries."""
    MAX_TASK_RETRIES = 3
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
        if _mark_task_in_queue(task, f"{timestamp} — skipped after {count} timeouts", QUEUE_FILE, QUEUE_ARCHIVE):
            log(f"Auto-skipped task after {count} timeouts")
        del retries[task_key]
    os.makedirs(os.path.dirname(RETRY_FILE), exist_ok=True)
    with open(RETRY_FILE, 'w') as f:
        json.dump(retries, f)


def _persist_completeness(ctx, timings, _pf_errors, completeness, stages_attempted, stages_ok, stages_failed):
    """Log and persist completeness data."""
    if completeness < 0.80:
        log(f"COMPLETENESS WARNING: {stages_ok}/{stages_attempted} stages succeeded "
            f"({completeness:.0%}) — failed: {', '.join(_pf_errors)}")
    else:
        log(f"Post-flight complete in {timings['total']:.2f}s — "
            f"{stages_ok}/{stages_attempted} stages OK ({completeness:.0%})")
    try:
        completeness_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'postflight_completeness.jsonl')
        os.makedirs(os.path.dirname(completeness_file), exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task": ctx["task"][:120], "task_status": ctx["task_status"],
            "stages_attempted": stages_attempted, "stages_ok": stages_ok,
            "stages_failed": stages_failed, "completeness": round(completeness, 4),
            "errors": _pf_errors, "error_type": ctx["error_type"],
            "error_evidence": ctx.get("error_evidence"),
            "total_time_s": timings["total"],
        }
        with open(completeness_file, "a") as cf:
            cf.write(json.dumps(entry) + "\n")
    except Exception as e:
        logging.debug("Persisting postflight completeness entry failed: %s", e)


def run_postflight(exit_code, output_file, preflight_data, task_duration=0):
    """Run all post-execution outcome recording in a single process."""
    log(f"All modules imported in {_import_time:.2f}s (single process)")
    t0 = time.monotonic()
    timings = {}
    _pf_errors = []
    ctx = _build_postflight_ctx(exit_code, output_file, preflight_data, task_duration)
    log(f"Recording outcome: {ctx['task_status']} (exit={exit_code}, duration={task_duration}s)")

    # §0.5: Worker-type classification and output validation
    t_wv = time.monotonic()
    try:
        worker_type = classify_worker_type(
            ctx["task"],
            task_tag=preflight_data.get("task_tag"),
            prompt_variant_task_type=preflight_data.get("prompt_variant_task_type", ""),
        )
        ctx["worker_type"] = worker_type
        wv_result = validate_worker_output(worker_type, ctx["output_text"], ctx["task_status"])
        ctx["worker_validation"] = wv_result
        if wv_result["downgrade"]:
            ctx["task_status"] = "partial_success"
            ctx["error_type"] = ctx.get("error_type") or "output_validation"
            log(f"Worker validation DOWNGRADE: {worker_type} → partial_success "
                f"(reasons: {', '.join(wv_result['reasons'])})")
        else:
            log(f"Worker type: {worker_type}, validation: {'PASS' if wv_result['validated'] else 'SKIP'}")
    except Exception as e:
        log(f"Worker validation failed (non-fatal): {e}")
        ctx["worker_type"] = "general"
        ctx["worker_validation"] = {"validated": True, "downgrade": False}
        _pf_errors.append("worker_validation")
    timings["worker_validation"] = round(time.monotonic() - t_wv, 3)

    # §1-2.7: Confidence, reasoning chain, failure lessons, brain bridge
    timings.update(_confidence_record(ctx["task_event"], exit_code, ctx["task"], preflight_data, _pf_errors))
    timings.update(_reasoning_close(ctx["chain_id"], ctx["task_status"], ctx["task"], exit_code, ctx["output_text"], _pf_errors))
    timings.update(_brain_store(ctx["task"], ctx["task_status"], exit_code, ctx["output_text"],
                                ctx["error_type"], task_duration, _pf_errors, ctx["RETRY_FILE"]))
    # §3-4.5: Attention, hooks/procedural, tool maker
    timings.update(_pf_attention_hooks_procedural(ctx, _pf_errors))
    # §5: Episode encoding + trajectory
    timings.update(_episode_encode(ctx["task"], ctx["task_section"], ctx["best_salience"], ctx["task_status"],
                                   task_duration, ctx["error_type"], ctx["output_text"], preflight_data, _pf_errors))
    # §5.02: Chain-of-thought self-evaluation
    timings.update(_cot_score(ctx["chain_id"], _pf_errors))
    # §5.05-5.95: Cognitive subsystems
    timings.update(_pf_prompt_predict_cognitive(ctx, _pf_errors))
    # §6-7.35: Broadcast, routing, benchmark, perf
    timings.update(_pf_broadcast_routing(ctx))
    # §7.4-7.43: Quality gates
    timings.update(_pf_self_test(ctx, _pf_errors))
    timings.update(_pf_code_gen_outcome(ctx, output_file, _pf_errors))
    timings.update(_pf_complexity_gate(ctx))
    timings.update(_pf_code_validation(ctx, _pf_errors))
    # §7.45-7.47: Perf, memory, structural gates
    timings.update(_pf_gates(ctx, _pf_errors))
    # §7.48-7.495: Feedback loops
    timings.update(_pf_retrieval_feedback(ctx, _pf_errors))
    # §7.5-8.5: Cost, evolution, synthesis
    timings.update(_pf_cost_and_budget(ctx, _pf_errors))
    timings.update(_pf_evolution_synthesis(ctx, _pf_errors))
    # §8.7: Wiki auto-ingest (promotion-gated)
    t_wiki = time.monotonic()
    if postflight_wiki_ingest:
        try:
            wiki_result = postflight_wiki_ingest(
                task=ctx["task"],
                task_tag=ctx.get("preflight_data", {}).get("task_tag", ""),
                task_status=ctx["task_status"],
                output_text=ctx["output_text"],
                exit_code=exit_code,
            )
            if wiki_result.get("ingested"):
                log(f"Wiki: ingested {wiki_result['source_id']} (gate={wiki_result['reason']})")
            else:
                log(f"Wiki: skip ({wiki_result.get('reason', 'unknown')})")
        except Exception as e:
            log(f"Wiki ingest failed (non-fatal): {e}")
            _pf_errors.append("wiki_ingest")
    timings["wiki_ingest"] = round(time.monotonic() - t_wiki, 3)

    # §9-13: Digest, transcript, queue, cleanup, finalize
    timings.update(_digest_write_fn(ctx["task"], ctx["task_status"], exit_code, task_duration, ctx["output_text"], _pf_errors))
    timings.update(_transcript_log(ctx, _pf_errors))
    timings.update(_pf_finalize(ctx, _pf_errors))

    timings["total"] = round(time.monotonic() - t0, 3)
    stages_attempted, stages_ok, stages_failed, completeness = _compute_completeness(timings, _pf_errors)
    _persist_completeness(ctx, timings, _pf_errors, completeness, stages_attempted, stages_ok, stages_failed)

    return {"status": "ok", "task_status": ctx["task_status"], "timings": timings,
            "completeness": round(completeness, 4), "errors": _pf_errors,
            "error_type": ctx["error_type"],
            "worker_type": ctx.get("worker_type", "general"),
            "worker_validation": ctx.get("worker_validation", {})}



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
