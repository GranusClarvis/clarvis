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
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _paths  # noqa: F401 — registers all script subdirs on sys.path

# === SINGLE IMPORT BLOCK (one-time cost) ===
start_import = time.monotonic()

from clarvis.cognition.attention import attention, get_codelet_competition, get_attention_schema

try:
    from clarvis.orch.task_selector import parse_tasks, score_tasks
except ImportError:
    parse_tasks = None
    score_tasks = None

try:
    from clarvis.cognition.cognitive_load import should_defer_task, estimate_task_complexity, log_sizing
except ImportError:
    should_defer_task = None
    estimate_task_complexity = None
    log_sizing = None

try:
    from clarvis.memory.procedural_memory import find_procedure, find_code_templates, format_code_templates
except ImportError:
    find_procedure = None
    find_code_templates = None
    format_code_templates = None

try:
    from reasoning_chain_hook import open_chain
except ImportError:
    open_chain = None

try:
    from clarvis.cognition.confidence import predict as conf_predict, dynamic_confidence
except ImportError:
    conf_predict = None
    dynamic_confidence = None

try:
    from clarvis.memory.episodic_memory import EpisodicMemory
except ImportError:
    EpisodicMemory = None

try:
    from clarvis.context.compressor import generate_context_brief, compress_episodes
    from clarvis.context.assembly import generate_tiered_brief
except ImportError:
    generate_context_brief = None
    generate_tiered_brief = None
    compress_episodes = None

try:
    from clarvis.context.assembly import dycp_prune_brief
except ImportError:
    dycp_prune_brief = None

try:
    from clarvis.orch.router import classify_task
except ImportError:
    classify_task = None

try:
    from clarvis.queue.engine import engine as queue_engine
except ImportError:
    queue_engine = None

try:
    from world_models import predict_task_outcome as wm_predict
except ImportError:
    wm_predict = None

try:
    from clarvis.cognition.workspace_broadcast import WorkspaceBroadcast
except ImportError:
    WorkspaceBroadcast = None

try:
    from clarvis.heartbeat.brain_bridge import brain_preflight_context
except ImportError:
    brain_preflight_context = None

try:
    from brain_introspect import introspect_for_task, format_introspection_for_prompt
except ImportError:
    introspect_for_task = None
    format_introspection_for_prompt = None

try:
    from automation_insights import format_insights_for_brief as get_automation_insights
except ImportError:
    get_automation_insights = None

try:
    from clarvis.memory.synaptic_memory import SynapticMemory
except ImportError:
    SynapticMemory = None

try:
    from somatic_markers import SomaticMarkerSystem
except ImportError:
    SomaticMarkerSystem = None

try:
    from clarvis.memory.cognitive_workspace import workspace as cog_workspace
except ImportError:
    cog_workspace = None

try:
    from clarvis.context.prompt_optimizer import select_variant as po_select_variant
except ImportError:
    po_select_variant = None

try:
    from clarvis.brain.retrieval_gate import classify_retrieval as gate_classify
except ImportError:
    gate_classify = None

try:
    from clarvis.brain.retrieval_eval import score_evidence
except ImportError:
    score_evidence = None

try:
    from clarvis.cognition.obligations import ObligationTracker
except ImportError:
    ObligationTracker = None

try:
    from directive_engine import DirectiveEngine
except ImportError:
    DirectiveEngine = None

_import_time = time.monotonic() - start_import
log = lambda msg: print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')}] PREFLIGHT: {msg}", file=sys.stderr)


QUEUE_FILE = os.path.join(os.path.dirname(__file__), "..", "memory", "evolution", "QUEUE.md")
WORKSPACE = os.path.join(os.path.dirname(__file__), "..")
LOCK_DIR = "/tmp"


def _check_lock_conflict():
    """Check if a conflicting clarvis/claude lock is held.

    Verifies via /proc/<pid>/cmdline that the lock holder is actually
    a clarvis/claude process (prevents false honors from PID recycling).
    Returns list of conflict descriptions (empty = no conflict).
    """
    conflicts = []
    _lock_markers = ("clarvis", "claude", "cron_", "project_agent")
    for lockfile in ("clarvis_claude_global.lock", "clarvis_maintenance.lock"):
        lock_path = os.path.join(LOCK_DIR, lockfile)
        if not os.path.exists(lock_path):
            continue
        try:
            with open(lock_path) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)  # alive?
            cmdline_file = f"/proc/{pid}/cmdline"
            if os.path.exists(cmdline_file):
                with open(cmdline_file, "rb") as cf:
                    cmdline = cf.read().replace(b"\x00", b" ").decode("utf-8", errors="replace")
                if not any(m in cmdline for m in _lock_markers):
                    continue  # PID recycled — not a clarvis process
            conflicts.append(f"lock held: {lockfile} (pid {pid})")
        except (ValueError, ProcessLookupError, PermissionError, OSError):
            pass  # stale lock or dead process
    return conflicts


def _verify_task_executable(task_text):
    """Pre-execution verification gate.

    Checks: (1) task format, (2) file references exist, (3) no lock conflict.
    Returns dict with passed, reason, hard_fail.
    """
    import re

    checks_passed = 0
    checks_total = 3
    reasons = []

    # 1. Format check
    tag_match = re.match(r"\[([^\]]+)\]\s*(.+)", task_text.strip())
    if tag_match:
        if len(tag_match.group(2)) >= 10:
            checks_passed += 1
        else:
            reasons.append(f"description too short ({len(tag_match.group(2))} chars)")
    elif len(task_text.strip()) >= 20:
        checks_passed += 1
    else:
        reasons.append("task too short/vague")

    # 2. File reference check
    file_refs = re.findall(
        r'(?:scripts/|clarvis/|packages/|data/|memory/)[\w/\-_.]+\.(?:py|sh|json|md|yaml)',
        task_text,
    )
    missing_files = [r for r in file_refs if not os.path.exists(os.path.join(WORKSPACE, r))]
    if missing_files:
        reasons.append(f"missing files: {', '.join(missing_files[:3])}")
    else:
        checks_passed += 1

    # 3. Lock check
    lock_conflicts = _check_lock_conflict()
    if lock_conflicts:
        reasons.extend(lock_conflicts)
    else:
        checks_passed += 1

    return {
        "passed": checks_passed == checks_total,
        "reason": "; ".join(reasons) if reasons else "all checks passed",
        "checks_passed": checks_passed,
        "checks_total": checks_total,
        "hard_fail": bool(missing_files) and len(missing_files) > 2,
        "missing_files": missing_files,
    }


_MAX_CANDIDATES = 20  # Wider scan to avoid burning a slot on one oversized cluster

# Confidence gate cache — dynamic_confidence() is global (not per-task), so compute once per heartbeat.
_confidence_gate_cache = None  # will be (tier, score) or ("DISABLED", None)
_FORCE_LOW_CONFIDENCE = os.environ.get("CLARVIS_FORCE_LOW_CONFIDENCE", "") == "1"


def _try_auto_split(cand_task):
    """Attempt to auto-split an oversized task into subtasks. Returns parent tag if split, else None."""
    import re as _re
    m = _re.match(r"\[([^\]]+)\]", cand_task.strip())
    parent_tag = m.group(1).strip() if m else ""
    if not parent_tag:
        return None
    try:
        from clarvis.queue.writer import ensure_subtasks_for_tag, mark_task_in_progress
        subtasks = [
            f"[{parent_tag}_1] Analyze: read relevant source files, identify change boundary",
            f"[{parent_tag}_2] Implement: core logic change in one focused increment",
            f"[{parent_tag}_3] Test: add/update test(s) covering the new behavior",
            f"[{parent_tag}_4] Verify: run existing tests, confirm no regressions",
        ]
        inserted = ensure_subtasks_for_tag(parent_tag, subtasks=subtasks, source="auto_split")
        if inserted:
            log(f"Auto-split: inserted subtasks for [{parent_tag}] into QUEUE.md")
            try:
                mark_task_in_progress(parent_tag)
                log(f"Auto-split: marked [{parent_tag}] as in-progress ([~])")
            except Exception as me:
                log(f"Auto-split: parent mark failed (non-fatal): {me}")
            return parent_tag
    except Exception as e:
        log(f"Auto-split failed (non-fatal): {e}")
    return None


def _check_candidate_gates(cand_task, cand_section):
    """Run gates 1-5 on a candidate. Returns (pass, defer_reason or None, autosplit_tag or None)."""
    # Gate 1: Cognitive load
    if should_defer_task:
        try:
            defer, load_info = should_defer_task(cand_section)
            if defer:
                return False, f"cognitive_load: {load_info}", None
        except Exception as e:
            log(f"Cognitive load check failed for candidate: {e}")

    # Gate 2: Task sizing — defer oversized, try auto-split
    if estimate_task_complexity:
        try:
            sizing = estimate_task_complexity(cand_task)
            if sizing["recommendation"] == "defer_to_sprint":
                if log_sizing:
                    log_sizing(cand_task, sizing)
                split_tag = _try_auto_split(cand_task)
                reason = f"oversized (score={sizing['score']:.2f}, signals={sizing['signals']})"
                return False, reason, split_tag
        except Exception as e:
            log(f"Task sizing failed for candidate: {e}")

    # Gate 3: Verification (hard failures only block)
    try:
        verification = _verify_task_executable(cand_task)
        if verification.get("hard_fail"):
            return False, f"verification: {verification['reason']}", None
    except Exception:
        pass

    # Gate 4: Mode compliance
    try:
        from clarvis.runtime.mode import is_task_allowed_for_mode
        allowed, mode_reason = is_task_allowed_for_mode(cand_task)
        if not allowed:
            return False, f"mode_gate: {mode_reason}", None
    except ImportError:
        pass
    except Exception as e:
        log(f"Mode gate check failed (non-fatal): {e}")

    # Gate 5: Confidence gate — skip LOW/UNKNOWN unless forced
    global _confidence_gate_cache
    if _confidence_gate_cache is None:
        if dynamic_confidence and not _FORCE_LOW_CONFIDENCE:
            try:
                _dyn_score = dynamic_confidence()
                if _dyn_score >= 0.5:
                    _confidence_gate_cache = ("PASS", _dyn_score)
                elif _dyn_score >= 0.3:
                    _confidence_gate_cache = ("LOW", _dyn_score)
                else:
                    _confidence_gate_cache = ("UNKNOWN", _dyn_score)
            except Exception as e:
                log(f"Confidence gate: dynamic_confidence() failed ({e}), allowing tasks")
                _confidence_gate_cache = ("PASS", 0.7)
        else:
            _confidence_gate_cache = ("PASS", None)

    gate_tier, gate_score = _confidence_gate_cache
    if gate_tier in ("LOW", "UNKNOWN"):
        log(f"CONFIDENCE_GATE: skipping task (tier={gate_tier}, score={gate_score:.2f}): {cand_task[:60]}")
        return False, f"confidence_gate: tier={gate_tier} score={gate_score:.2f}", None

    return True, None, None


def _evaluate_candidates(candidate_list, deferred_tasks, pass_name="primary"):
    """Try candidates until one passes all gates. Returns (task, section, salience, tag, autosplit_tags)."""
    import re as _re
    autosplit_tags = []

    for candidate in candidate_list[:_MAX_CANDIDATES]:
        cand_task = candidate.get("text") or ""
        cand_section = candidate.get("section", "P1")
        cand_salience = candidate.get("salience", 0.0)
        if not cand_task:
            continue

        passed, reason, split_tag = _check_candidate_gates(cand_task, cand_section)
        if split_tag:
            autosplit_tags.append(split_tag)
        if not passed:
            deferred_tasks.append({"task": cand_task[:80], "reason": reason})
            log(f"Skipping ({reason[:40]}): {cand_task[:60]}...")
            continue

        m = _re.match(r"\[([^\]]+)\]", cand_task.strip())
        tag = m.group(1).strip() if m else None
        return cand_task, cand_section, cand_salience, tag, autosplit_tags

    return None, None, 0.0, None, autosplit_tags


def _preflight_attention(result):
    """§1: Attention load + tick + codelet competition + AST prediction."""
    t1 = time.monotonic()
    codelet_result = None
    try:
        attention._load()
        attention.tick()
        log("Attention load+tick done")
    except Exception as e:
        log(f"Attention load+tick failed: {e}")

    try:
        competition = get_codelet_competition()
        codelet_result = competition.compete()
        activations = codelet_result.get("activations", {})
        log(f"Codelet competition: winner={codelet_result.get('winner', '?')} "
            f"coalition={','.join(codelet_result.get('coalition', []))} "
            f"score={codelet_result.get('coalition_score', 0):.3f} "
            f"activations={activations}")
        result["codelet_winner"] = codelet_result.get("winner", "?")
        result["codelet_coalition"] = codelet_result.get("coalition", [])
        result["codelet_activations"] = activations
        result["codelet_domain_bias"] = codelet_result.get("domain_bias", {})
    except Exception as e:
        log(f"Codelet competition failed (non-fatal): {e}")

    try:
        schema = get_attention_schema()
        prediction = schema.predict_next_focus(context="heartbeat preflight")
        result["ast_prediction"] = prediction.get("predicted_domain", "unknown")
        log(f"AST prediction: domain={prediction['predicted_domain']} "
            f"focus={prediction['predicted_focus_type']}")
    except Exception as e:
        log(f"AST prediction failed (non-fatal): {e}")

    result["timings"]["attention_tick"] = round(time.monotonic() - t1, 3)
    return codelet_result


def _gather_candidates(codelet_result):
    """Build ranked candidate list via Queue Engine V2 (primary) or legacy fallback.

    V2 path: queue_engine.ranked_eligible() reconciles QUEUE.md + sidecar,
    filters eligible tasks (pending/retryable, not in backoff/deferred/running),
    scores them, and returns them ranked.

    Legacy fallback: only used when queue_engine is unavailable (import failed).
    """
    # --- Primary path: Queue Engine V2 ---
    if queue_engine:
        try:
            eligible = queue_engine.ranked_eligible()
            if not eligible:
                # Distinguish empty queue from all-filtered
                from clarvis.queue.engine import parse_queue as _pq
                md_tasks = _pq()
                if not md_tasks:
                    return [], "queue_empty"
                return [], "all_filtered_by_v2"

            # Map to the format _evaluate_candidates expects
            candidates = []
            for task in eligible:
                candidates.append({
                    "text": task["text"],
                    "section": task["priority"],
                    "salience": task.get("score", 0.0),
                })
            log(f"Queue V2: {len(candidates)} eligible candidate(s) from {len(eligible)} ranked")
            return candidates, None
        except Exception as e:
            log(f"Queue V2 ranked_eligible failed, falling back to legacy: {e}")

    # --- Legacy fallback (only if queue_engine import failed) ---
    candidates = []
    if parse_tasks and score_tasks:
        try:
            tasks = parse_tasks()
            if not tasks:
                return candidates, "queue_empty"
            candidates = score_tasks(tasks, codelet_result=codelet_result)
        except Exception as e:
            log(f"Legacy task selector failed: {e}")
    if not candidates:
        try:
            import re
            with open(QUEUE_FILE) as f:
                for line in f:
                    m = re.match(r'^- \[ \] (.+)$', line)
                    if m:
                        candidates.append({"text": m.group(1), "section": "P1", "salience": 0.0})
                        if len(candidates) >= 10:
                            break
            if candidates:
                log(f"Legacy fallback: {len(candidates)} unchecked tasks found")
        except Exception as e:
            log(f"Legacy fallback task search failed: {e}")

    return candidates, None


def _preflight_select_task(result, codelet_result, t0):
    """§2: Task selection with fallback-on-defer loop + rescue pass.

    Returns (next_task, task_section, best_salience) or sets result status and returns None.
    """
    t2 = time.monotonic()
    candidates, early_status = _gather_candidates(codelet_result)

    if early_status:
        result["status"] = early_status
        log(f"Queue status: {early_status}")
        result["timings"]["total"] = round(time.monotonic() - t0, 3)
        return None

    if not candidates:
        result["status"] = "no_tasks"
        result["timings"]["total"] = round(time.monotonic() - t0, 3)
        return None

    deferred_tasks = []
    next_task, task_section, best_salience, selected_tag, autosplit_tags = _evaluate_candidates(candidates, deferred_tasks, "primary")

    # Rescue pass: freshly inserted subtasks can compete in the same heartbeat
    if not next_task and autosplit_tags:
        try:
            reparsed = parse_tasks(QUEUE_FILE) if parse_tasks else []
            rescored = score_tasks(reparsed) if (score_tasks and reparsed) else []
            deferred_prefixes = {d["task"] for d in deferred_tasks}
            rescue_candidates = [c for c in rescored if c.get("text") and c.get("text")[:80] not in deferred_prefixes]
            if rescue_candidates:
                log(f"Rescue pass: rescanning queue after auto-split ({len(autosplit_tags)} parent(s))")
                next_task, task_section, best_salience, selected_tag, more_autosplit = _evaluate_candidates(
                    rescue_candidates, deferred_tasks, "rescue")
                autosplit_tags.extend(more_autosplit)
        except Exception as e:
            log(f"Rescue pass failed (non-fatal): {e}")

    if not next_task:
        log(f"All {len(deferred_tasks)} candidates deferred — no executable task this heartbeat")
        result["should_defer"] = True
        result["defer_reason"] = "all_candidates_deferred"
        result["deferred_tasks"] = deferred_tasks
        try:
            attention.submit(f"ALL TASKS DEFERRED ({len(deferred_tasks)} candidates checked)",
                             source="heartbeat", importance=0.7)
        except Exception:
            pass
        result["timings"]["task_selection"] = round(time.monotonic() - t2, 3)
        result["timings"]["total"] = round(time.monotonic() - t0, 3)
        return None

    if deferred_tasks:
        log(f"Skipped {len(deferred_tasks)} deferred tasks, executing fallback: {next_task[:60]}...")
        result["deferred_tasks"] = deferred_tasks

    result["task"] = next_task
    try:
        import re
        m = re.match(r"\[([^\]]+)\]", next_task.strip())
        result["task_tag"] = m.group(1) if m else None
    except Exception:
        result["task_tag"] = None

    # Queue Engine v2: start a run record for this task
    result["queue_run_id"] = None
    if queue_engine and result["task_tag"]:
        try:
            result["queue_run_id"] = queue_engine.start_run(result["task_tag"])
            log(f"Queue engine: started run {result['queue_run_id']}")
        except Exception as e:
            log(f"Queue engine start_run failed (non-fatal): {e}")

    result["task_section"] = task_section
    result["task_salience"] = round(best_salience, 4)
    result["timings"]["task_selection"] = round(time.monotonic() - t2, 3)
    return next_task, task_section, best_salience


def _preflight_load_sizing(result, next_task, task_section):
    """§4+4.7: Re-run cognitive load, task sizing, and verification for result population."""
    t4 = time.monotonic()
    if should_defer_task:
        try:
            _defer, load_info = should_defer_task(task_section)
            result["cognitive_load"] = load_info if isinstance(load_info, dict) else {"raw": str(load_info)}
            log(f"Cognitive load: OK — {load_info}")
        except Exception as e:
            log(f"Cognitive load check failed: {e}")
    result["timings"]["cognitive_load"] = round(time.monotonic() - t4, 3)

    t45 = time.monotonic()
    if estimate_task_complexity:
        try:
            sizing = estimate_task_complexity(next_task)
            result["task_sizing"] = sizing
            log(f"Task sizing: {sizing['complexity']} (score={sizing['score']:.2f}, "
                f"signals={sizing['signals']}, rec={sizing['recommendation']})")
            if log_sizing:
                log_sizing(next_task, sizing)
        except Exception as e:
            log(f"Task sizing failed (non-fatal): {e}")
    result["timings"]["task_sizing"] = round(time.monotonic() - t45, 3)

    t47 = time.monotonic()
    try:
        verification = _verify_task_executable(next_task)
        result["verification"] = verification
        log(f"Verification {'OK' if verification['passed'] else 'note'}: {verification['reason']}")
    except Exception as e:
        log(f"Verification gate failed (non-fatal): {e}")
    result["timings"]["verification"] = round(time.monotonic() - t47, 3)


def _preflight_procedural(result, next_task):
    """§5+5.2+5.5: Procedural memory lookup, procedure injection, code templates."""
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

    # Collect top-2 procedures for prompt injection
    t52 = time.monotonic()
    procs_for_injection = []
    if result.get("procedure") and result["procedure"].get("steps"):
        procs_for_injection.append(result["procedure"])
    if len(procs_for_injection) < 2:
        procs_for_injection = _collect_extra_procedures(procs_for_injection, next_task)
    result["procedures_for_injection"] = [p.get("id", "") for p in procs_for_injection]
    result["timings"]["proc_injection_collect"] = round(time.monotonic() - t52, 3)

    # Code templates
    t55 = time.monotonic()
    code_templates_hint = ""
    if find_code_templates and format_code_templates:
        try:
            task_lower = next_task.lower()
            code_signals = any(kw in task_lower for kw in [
                "create script", "build module", "implement", "write function",
                "new module", "wire into", "add to", "create.*py", "code",
                "refactor", "test suite", "cron script",
            ])
            if code_signals:
                templates = find_code_templates(next_task, top_n=2)
                if templates:
                    code_templates_hint = format_code_templates(templates)
                    result["code_templates"] = [t["name"] for t in templates]
                    log(f"Code templates: {len(templates)} matched")
        except Exception as e:
            log(f"Code template lookup failed: {e}")
    result["code_templates_hint"] = code_templates_hint
    result["timings"]["code_templates"] = round(time.monotonic() - t55, 3)
    return procs_for_injection, code_templates_hint


def _collect_extra_procedures(procs_for_injection, next_task):
    """Find up to 2nd procedure match via brain query for injection."""
    try:
        from brain import brain as _brain_proc, PROCEDURES as _PROCEDURES
        extra = _brain_proc.recall(next_task, collections=[_PROCEDURES], n=3,
                                   caller="preflight_proc_inject")
        existing_ids = {p.get("id") for p in procs_for_injection}
        for r in extra:
            if r["id"] in existing_ids:
                continue
            meta = r.get("metadata", {})
            steps_raw = meta.get("steps", "[]")
            try:
                steps = json.loads(steps_raw) if isinstance(steps_raw, str) else steps_raw
            except (json.JSONDecodeError, TypeError):
                steps = []
            if not steps:
                continue
            dist = r.get("distance")
            if dist is not None and dist > 0.8:
                continue
            uc = int(meta.get("use_count", 0))
            sc = int(meta.get("success_count", 0))
            procs_for_injection.append({
                "id": r["id"], "name": meta.get("name", "unknown"),
                "steps": steps, "use_count": uc, "success_count": sc,
                "success_rate": sc / uc if uc > 0 else 1.0,
            })
            if len(procs_for_injection) >= 2:
                break
    except Exception as e:
        log(f"2nd procedure lookup failed (non-fatal): {e}")
    return procs_for_injection



def _preflight_confidence_world_model(result, next_task, task_section):
    """§7+7.5: Confidence prediction + world model. Returns dyn_conf."""
    t7 = time.monotonic()
    import re as _re
    task_event = _re.sub(r'[^a-zA-Z0-9]', '_', next_task[:60])
    result["prediction_event"] = task_event
    dyn_conf = 0.7
    if dynamic_confidence:
        try:
            dyn_conf = dynamic_confidence()
            result["prediction_confidence"] = dyn_conf
        except Exception:
            pass
    if conf_predict:
        try:
            conf_predict(task_event, "success", dyn_conf)
            log(f"Prediction logged: {task_event} @ {dyn_conf:.0%}")
        except Exception as e:
            log(f"Prediction logging failed: {e}")
    result["timings"]["confidence"] = round(time.monotonic() - t7, 3)

    t75 = time.monotonic()
    if wm_predict:
        try:
            wm_result = wm_predict(next_task, task_section)
            result["wm_prediction"] = wm_result.get("prediction", "unknown")
            result["wm_p_success"] = wm_result.get("p_success", 0.5)
            result["wm_curiosity"] = wm_result.get("curiosity", 0.5)
            log(f"World model: prediction={wm_result['prediction']}, "
                f"P(success)={wm_result['p_success']:.0%}, curiosity={wm_result['curiosity']:.2f}")
        except Exception as e:
            log(f"World model prediction failed: {e}")
    result["timings"]["world_model"] = round(time.monotonic() - t75, 3)
    return dyn_conf


def _preflight_confidence_tier(result, dyn_conf, next_task, t0):
    """§7.6: Compute confidence tier and gate execution. Returns dyn_conf or None if deferred."""
    confidence_for_tier = dyn_conf
    wm_p = result.get("wm_p_success")
    if wm_p is not None:
        confidence_for_tier = (dyn_conf + wm_p) / 2

    if confidence_for_tier >= 0.8:
        tier, action = "HIGH", "execute"
    elif confidence_for_tier >= 0.5:
        tier, action = "MEDIUM", "execute_with_validation"
    elif confidence_for_tier >= 0.3:
        tier, action = "LOW", "dry_run"
    else:
        tier, action = "UNKNOWN", "skip"

    result["confidence_tier"] = tier
    result["confidence_action"] = action
    result["confidence_for_tier"] = round(confidence_for_tier, 3)
    log(f"Confidence tier: {tier} (combined={confidence_for_tier:.2f}, "
        f"dyn={dyn_conf:.2f}, wm_p={wm_p if wm_p is not None else 'N/A'})")

    if tier in ("UNKNOWN", "LOW"):
        result["should_defer"] = True
        if tier == "UNKNOWN":
            result["defer_reason"] = f"unknown_confidence ({confidence_for_tier:.2f})"
            msg, imp = f"TASK DEFERRED (UNKNOWN confidence={confidence_for_tier:.2f})", 0.7
        else:
            result["defer_reason"] = f"low_confidence_dry_run ({confidence_for_tier:.2f})"
            result["dry_run"] = True
            msg, imp = f"TASK DRY-RUN (LOW confidence={confidence_for_tier:.2f})", 0.6
        log(f"{tier} confidence — {'deferring' if tier == 'UNKNOWN' else 'dry-run'}: {next_task[:60]}")
        try:
            attention.submit(f"{msg}: {next_task[:60]}", source="heartbeat", importance=imp)
        except Exception:
            pass
        result["timings"]["total"] = round(time.monotonic() - t0, 3)
        return None
    return dyn_conf


def _preflight_gwt_retrieval_gate(result, next_task):
    """§7.7+7.8: GWT broadcast + retrieval gate classification."""
    t77 = time.monotonic()
    gwt_broadcast_text = ""
    if WorkspaceBroadcast:
        try:
            ws = WorkspaceBroadcast()
            gwt_result = ws.run_cycle()
            gwt_broadcast_text = gwt_result.get("broadcast_text", "")
            result["gwt_winners"] = gwt_result.get("winners", 0)
            result["gwt_sources"] = gwt_result.get("sources", [])
            result["gwt_codelets"] = gwt_result.get("total_codelets", 0)
            log(f"GWT broadcast: {gwt_result['winners']} winners from "
                f"{gwt_result['total_codelets']} codelets "
                f"({', '.join(gwt_result.get('sources', []))})")
        except Exception as e:
            log(f"GWT broadcast cycle failed: {e}")
    result["gwt_broadcast"] = gwt_broadcast_text
    result["timings"]["gwt_broadcast"] = round(time.monotonic() - t77, 3)

    t78 = time.monotonic()
    retrieval_tier_info = None
    if gate_classify:
        try:
            retrieval_tier_info = gate_classify(next_task)
            result["retrieval_tier"] = retrieval_tier_info.tier
            result["retrieval_gate_reason"] = retrieval_tier_info.reason
            log(f"Retrieval gate: tier={retrieval_tier_info.tier} reason={retrieval_tier_info.reason}")
        except Exception as e:
            log(f"Retrieval gate failed (non-fatal, defaulting DEEP): {e}")
            result["retrieval_tier"] = "DEEP_RETRIEVAL"
    else:
        result["retrieval_tier"] = "DEEP_RETRIEVAL"
    result["timings"]["retrieval_gate"] = round(time.monotonic() - t78, 3)

    _rt = result.get("retrieval_tier", "DEEP_RETRIEVAL")
    return gwt_broadcast_text, retrieval_tier_info, _rt


def _preflight_episodic(result, next_task, _rt):
    """§8: Episodic memory recall (similar + failures)."""
    t8 = time.monotonic()
    similar_episodes = ""
    failure_episodes = ""
    if _rt == "NO_RETRIEVAL":
        log("Episodic recall SKIPPED — retrieval gate: NO_RETRIEVAL")
    elif EpisodicMemory:
        try:
            em = EpisodicMemory()
            _ep_n = 3 if _rt == "LIGHT_RETRIEVAL" else 5
            similar = em.recall_similar(next_task, n=_ep_n)
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
    return similar_episodes, failure_episodes


def _format_memory_hint(mem):
    """Format a single brain memory result into a tagged hint line."""
    doc = mem.get("document", "")[:120]
    src = mem.get("metadata", {}).get("source", "")
    tags = mem.get("metadata", {}).get("tags", "")
    col = mem.get("collection", "")
    if "dream" in str(tags):
        prefix = "[DREAM]"
    elif "research" in str(src) or "research" in str(tags):
        prefix = "[RESEARCH]"
    elif "synthesis" in str(src):
        prefix = "[SYNTHESIS]"
    elif "episode" in col:
        prefix = "[EPISODE]"
    elif "procedur" in col:
        prefix = "[PROCEDUR]"
    else:
        prefix = "[LEARNING]"
    return f"  {prefix} {doc}"


def _preflight_brain_bridge(result, next_task, _rt, retrieval_tier_info):
    """§8.5+8.6: Brain bridge context + retrieval eval with adaptive retry."""
    t85 = time.monotonic()
    knowledge_hints = ""
    brain_goals = ""
    brain_context = ""
    brain_working_memory = ""
    brain_ctx = {}

    if _rt == "NO_RETRIEVAL":
        log("Brain bridge SKIPPED — retrieval gate: NO_RETRIEVAL (saving ~7.5s)")
    elif brain_preflight_context:
        try:
            _graph_expand = False
            _tier_collections = None
            if _rt == "LIGHT_RETRIEVAL":
                _n_knowledge = 3
                if retrieval_tier_info and retrieval_tier_info.collections:
                    _tier_collections = retrieval_tier_info.collections[:2]
            else:
                _graph_expand = bool(retrieval_tier_info and retrieval_tier_info.graph_expand)
                _n_knowledge = 10 if _graph_expand else 5
            brain_ctx = brain_preflight_context(next_task, n_knowledge=_n_knowledge, n_goals=5,
                                                graph_expand=_graph_expand, collections=_tier_collections)
            knowledge_hints = brain_ctx.get("knowledge_hints", "")
            brain_goals = brain_ctx.get("goals_text", "")
            brain_context = brain_ctx.get("context", "")
            brain_working_memory = brain_ctx.get("working_memory", "")
            log(f"Brain bridge ({_rt}): knowledge={len(knowledge_hints)}B goals={len(brain_goals)}B "
                f"context={len(brain_context)}B wm={len(brain_working_memory)}B")
        except Exception as e:
            log(f"Brain bridge preflight failed: {e}")
    else:
        knowledge_hints = _brain_legacy_fallback(next_task, _rt)

    result["knowledge_hints"] = knowledge_hints
    result["brain_goals"] = brain_goals
    result["brain_context"] = brain_context
    result["brain_working_memory"] = brain_working_memory

    # Extract recalled memory IDs for postflight
    _recalled_ids = []
    _raw = brain_ctx.get("raw_results", []) if brain_preflight_context and brain_ctx else []
    for _mem in (_raw if isinstance(_raw, list) else []):
        _mid, _mcol = _mem.get("id"), _mem.get("collection")
        if _mid and _mcol:
            _recalled_ids.append({"id": _mid, "collection": _mcol})
    if _recalled_ids:
        result["recalled_memory_ids"] = _recalled_ids
    result["timings"]["knowledge"] = round(time.monotonic() - t85, 3)

    # §8.5.1: Evidence scoring gate — pre-filter by cosine similarity (threshold 0.3)
    if score_evidence and _raw and isinstance(_raw, list) and len(_raw) > 0:
        try:
            t_gate = time.monotonic()
            gate_out = score_evidence(next_task, _raw, threshold=0.3)
            n_discarded = gate_out["discarded"]
            if n_discarded > 0:
                log(f"Evidence gate: {n_discarded}/{len(_raw)} results discarded (sim < 0.3)")
                # Replace raw_results in brain_ctx so downstream eval uses filtered set
                if brain_ctx:
                    brain_ctx["raw_results"] = gate_out["kept"]
            result["evidence_gate_discarded"] = n_discarded
            result["evidence_gate_scores"] = gate_out["scores"]
            result["timings"]["evidence_gate"] = round(time.monotonic() - t_gate, 3)
        except Exception as e:
            log(f"Evidence gate failed (non-fatal): {e}")

    # §8.6: Retrieval eval + adaptive retry
    _preflight_retrieval_eval(result, next_task, _rt, brain_ctx)
    return knowledge_hints, brain_goals, brain_context, brain_working_memory, brain_ctx


def _brain_legacy_fallback(next_task, _rt):
    """Legacy brain recall fallback when brain_preflight_context unavailable."""
    try:
        from brain import get_brain, LEARNINGS
        b = get_brain()
        _n = 3 if _rt == "LIGHT_RETRIEVAL" else 5
        learnings = b.recall(next_task, collections=[LEARNINGS], n=_n, min_importance=0.3)
        if learnings:
            hints = [_format_memory_hint(mem) for mem in learnings]
            log(f"Brain knowledge (legacy, {_rt}): {len(learnings)} relevant learnings found")
            return "\n".join(hints)
    except Exception as e:
        log(f"Brain knowledge recall failed: {e}")
    return ""


def _preflight_retrieval_eval(result, next_task, _rt, brain_ctx):
    """§8.6: CRAG-style retrieval eval with corrective retry."""
    try:
        from clarvis.brain.retrieval_eval import adaptive_recall
        from brain import get_brain as _get_brain_for_retry
        eval_results = brain_ctx.get("raw_results", []) if brain_preflight_context and brain_ctx else []
        if eval_results and isinstance(eval_results, list) and len(eval_results) > 0:
            b_retry = _get_brain_for_retry()
            ar_out = adaptive_recall(b_retry, next_task, tier=_rt,
                                     original_results=eval_results, n=len(eval_results))
            verdict = ar_out["verdict"]
            result["retrieval_verdict"] = verdict
            result["retrieval_max_score"] = ar_out["max_score"]
            result["retrieval_retried"] = ar_out["retried"]
            result["retrieval_original_verdict"] = ar_out["original_verdict"]
            result["retrieval_n_filtered"] = ar_out.get("n_filtered_out", 0)
            if ar_out["retry_query"]:
                result["retrieval_retry_query"] = ar_out["retry_query"]
            log(f"Retrieval eval: {verdict} (max={ar_out['max_score']}, retried={ar_out['retried']})")
            if verdict == "INCORRECT":
                log("Retrieval INCORRECT — knowledge_hints omitted")
                result["knowledge_hints"] = ""
            elif ar_out["results"]:
                _rebuilt = [_format_memory_hint(m) for m in ar_out["results"]]
                if _rebuilt:
                    result["knowledge_hints"] = "\n".join(_rebuilt)
                    log(f"Knowledge hints rebuilt: {len(eval_results)}→{len(ar_out['results'])} results")
        else:
            result["retrieval_verdict"] = "NO_RESULTS"
    except Exception as e:
        log(f"Retrieval eval failed (non-fatal): {e}")
        result["retrieval_verdict"] = "ERROR"


def _preflight_introspection_synaptic(result, next_task, recalled_memory_ids=None):
    """§8.7+8.8+8.9: Brain introspection, synaptic spread, failure avoidance."""
    # §8.7: Brain introspection
    t87 = time.monotonic()
    introspection_text = ""
    if introspect_for_task and format_introspection_for_prompt:
        try:
            budget = "standard"
            if result.get("route_tier") in ("complex", "reasoning"):
                budget = "full"
            elif result.get("route_executor") in ("openrouter", "gemini"):
                budget = "minimal"
            introspection = introspect_for_task(next_task, budget=budget)
            introspection_text = format_introspection_for_prompt(introspection, budget)
            log(f"Brain introspection ({budget}): {len(introspection_text)}B")
        except Exception as e:
            log(f"Brain introspection failed: {e}")
    result["brain_introspection"] = introspection_text
    result["timings"]["brain_introspection"] = round(time.monotonic() - t87, 3)

    # §8.8: Synaptic spreading activation
    t88 = time.monotonic()
    synaptic_associations = ""
    if SynapticMemory:
        try:
            synaptic_associations = _run_synaptic_spread(next_task, introspection_text, recalled_memory_ids)
        except Exception as e:
            log(f"Synaptic spreading activation failed: {e}")
    result["synaptic_associations"] = synaptic_associations
    result["timings"]["synaptic_spread"] = round(time.monotonic() - t88, 3)

    # §8.9: Somatic markers + episodic causal chains
    t89 = time.monotonic()
    failure_avoidance = _build_failure_avoidance(next_task)
    result["failure_avoidance"] = failure_avoidance
    result["timings"]["failure_avoidance"] = round(time.monotonic() - t89, 3)

    return introspection_text, synaptic_associations, failure_avoidance


def _run_synaptic_spread(next_task, introspection_text, recalled_memory_ids=None):
    """Run synaptic spreading activation from recalled memory seeds.

    Uses pre-recalled IDs from brain_bridge when available, avoiding a
    duplicate brain.recall() call (CONTEXT_DUPLICATE_RECALL fix).
    """
    sm = SynapticMemory()
    recalled_ids = []
    # Prefer IDs already recalled by brain_bridge (§8.5) to avoid duplicate recall
    if recalled_memory_ids:
        recalled_ids = [mid["id"] for mid in recalled_memory_ids if mid.get("id")]
    elif introspect_for_task and introspection_text:
        try:
            from brain import get_brain, LEARNINGS
            b_syn = get_brain()
            syn_results = b_syn.recall(next_task, collections=[LEARNINGS], n=5, min_importance=0.3)
            if syn_results:
                recalled_ids = [m.get("id", "") for m in syn_results if m.get("id")]
        except Exception:
            pass
    if not recalled_ids:
        return ""
    spread_results = sm.spread(recalled_ids[:5], n=5, min_weight=0.1)
    if not spread_results:
        return ""
    lines = []
    try:
        from brain import get_brain
        b_syn = get_brain()
    except Exception:
        b_syn = None
    for mem_id, activation in spread_results[:5]:
        try:
            doc_results = b_syn.recall(mem_id[:30], n=1) if b_syn else []
            doc_text = doc_results[0].get("document", mem_id)[:80] if doc_results else mem_id[:40]
        except Exception:
            doc_text = mem_id[:40]
        lines.append(f"  [{activation:.2f}] {doc_text}")
    log(f"Synaptic spread: {len(spread_results)} associations from {len(recalled_ids)} seeds")
    return "SYNAPTIC ASSOCIATIONS (neural co-activation):\n" + "\n".join(lines)


def _build_failure_avoidance(next_task):
    """Build failure avoidance text from somatic markers + episodic causal chains."""
    avoidance_lines = []
    try:
        if SomaticMarkerSystem:
            try:
                somatic = SomaticMarkerSystem()
                bias = somatic.get_bias(next_task)
                if bias and bias.get("valence", 0) < -0.1:
                    for m in bias.get("markers", [])[:3]:
                        val = m.get("valence", 0)
                        if val < -0.1:
                            avoidance_lines.append(f"  AVOID [{val:.2f}]: {m.get('stimulus', '')[:60]}")
            except Exception:
                pass
        if EpisodicMemory:
            try:
                em_causal = EpisodicMemory()
                recent_failures = em_causal.recall_failures(n=3)
                if recent_failures:
                    for fail_ep in (recent_failures if isinstance(recent_failures, list) else [recent_failures]):
                        fail_id = fail_ep.get("id", "")
                        fail_task = fail_ep.get("task", "")[:60]
                        if fail_id:
                            causes = em_causal.causes_of(fail_id)
                            if causes:
                                avoidance_lines.append(f"  FAIL: {fail_task} <- caused by: {causes[0].get('task', causes[0].get('description', ''))[:60]}")
                            else:
                                lesson = fail_ep.get("lesson", fail_ep.get("error", ""))[:60]
                                if lesson:
                                    avoidance_lines.append(f"  FAIL: {fail_task} — {lesson}")
            except Exception:
                pass
    except Exception as e:
        log(f"Failure avoidance assembly failed: {e}")
    if avoidance_lines:
        log(f"Failure avoidance: {len(avoidance_lines)} signals")
        return "FAILURE AVOIDANCE (somatic markers + causal chains):\n" + "\n".join(avoidance_lines[:5])
    return ""



def _preflight_generate_brief(result, next_task, knowledge_hints, compressed_episodes):
    """Generate the tiered/legacy context brief."""
    executor = result["route_executor"]
    if generate_tiered_brief:
        try:
            brief_tier = {
                "openrouter": "minimal", "gemini": "minimal",
                "claude": "full" if result["route_tier"] in ("complex", "reasoning") else "standard",
            }.get(executor, "standard")
            brief = generate_tiered_brief(current_task=next_task, tier=brief_tier,
                                          episodic_hints=compressed_episodes,
                                          knowledge_hints=knowledge_hints)
            log(f"Tiered brief ({brief_tier}): {len(brief)} bytes")
            result["tiered_brief_used"] = True
            return brief
        except Exception as e:
            log(f"Tiered brief failed, falling back to legacy: {e}")
    if generate_context_brief:
        try:
            brief = generate_context_brief()
            log(f"Context brief (legacy): {len(brief)} bytes")
            return brief
        except Exception as e:
            log(f"Context compression failed: {e}")
    return ""


def _preflight_append_supplementary(context_brief, result, brain_goals, brain_context,
                                     brain_working_memory, failure_avoidance, procs_for_injection,
                                     synaptic_associations, codelet_result, gwt_broadcast_text,
                                     introspection_text, code_templates_hint, _suppressed_sections):
    """Append all supplementary sections to the context brief, gated by suppression."""
    if brain_goals and "brain_goals" not in _suppressed_sections:
        context_brief += f"\nBRAIN GOALS (active objectives):\n{brain_goals[:500]}\n"
    if brain_context and "brain_context" not in _suppressed_sections:
        context_brief += f"\nBRAIN CONTEXT: {brain_context[:200]}\n"
    # NOTE: working_memory is already included in the tiered brief (spotlight/workspace section).
    # Only append if tiered brief was NOT used (legacy fallback path).
    if brain_working_memory and "working_memory" not in _suppressed_sections and not result.get("tiered_brief_used"):
        context_brief += f"\nWORKING MEMORY (recent activity):\n{brain_working_memory[:300]}\n"

    wm_p = result.get("wm_p_success")
    wm_curiosity = result.get("wm_curiosity")
    if wm_p is not None and "world_model" not in _suppressed_sections:
        wm_hint = f"WORLD MODEL: P(success)={wm_p:.0%}"
        if wm_curiosity and wm_curiosity > 0.6:
            wm_hint += f", novelty={wm_curiosity:.2f} (explore broadly)"
        elif wm_p < 0.4:
            wm_hint += " (low — tread carefully, check prior failures)"
        context_brief += f"\n{wm_hint}\n"

    # NOTE: failure_avoidance is already included in the tiered brief (via build_decision_context).
    # Only append if tiered brief was NOT used (legacy fallback path).
    if failure_avoidance and "failure_avoidance" not in _suppressed_sections and not result.get("tiered_brief_used"):
        context_brief += f"\n{failure_avoidance}\n"

    # NOTE: procedures are already included in the tiered brief (via get_recommended_procedures).
    # Only append if tiered brief was NOT used (legacy fallback path).
    if procs_for_injection and not result.get("tiered_brief_used"):
        rec_lines = ["Recommended approach (from procedural memory):"]
        for idx, proc in enumerate(procs_for_injection[:2]):
            steps = proc.get("steps", [])
            rate = f"{proc.get('success_rate', 0):.0%}"
            name = proc.get("name", proc.get("id", "?"))
            rec_lines.append(f"  Procedure {idx+1}: {name} (success rate: {rate})")
            for si, step in enumerate(steps):
                rec_lines.append(f"    {si+1}. {step}")
        rec_lines.append("  Use these steps as a starting guide, adapt as needed.")
        context_brief += "\n" + "\n".join(rec_lines) + "\n"
        result["procedure_injected"] = True
        log(f"Procedure injection: {len(procs_for_injection)} procedure(s) injected into prompt")

    if synaptic_associations and "synaptic" not in _suppressed_sections:
        context_brief += f"\n{synaptic_associations}\n"
    if codelet_result and "attention" not in _suppressed_sections:
        activations = codelet_result.get("activations", {})
        act_str = ", ".join(f"{d}={a:.2f}" for d, a in
                            sorted(activations.items(), key=lambda x: x[1], reverse=True))
        context_brief += (f"\nATTENTION CODELETS (LIDA): "
                          f"winner={codelet_result.get('winner', '?')} "
                          f"coalition={','.join(codelet_result.get('coalition', []))} [{act_str}]\n")
    if gwt_broadcast_text and "gwt_broadcast" not in _suppressed_sections:
        context_brief += f"\nGWT BROADCAST (conscious workspace):\n{gwt_broadcast_text[:400]}\n"
    if introspection_text and "introspection" not in _suppressed_sections:
        context_brief += f"\n{introspection_text[:1200]}\n"
    if code_templates_hint:
        context_brief += f"\n{code_templates_hint}\n"
    return context_brief


def _preflight_insights_prompt_workspace(context_brief, result, next_task, compressed_episodes):
    """§10.5+10.52+10.55+10.6: Automation insights, confidence gate, prompt opt, cognitive workspace."""
    t105 = time.monotonic()
    if get_automation_insights:
        try:
            insights_text = get_automation_insights(next_task)
            if insights_text:
                context_brief += f"\n{insights_text[:400]}\n"
                log(f"Automation insights: {len(insights_text)}B")
        except Exception as e:
            log(f"Automation insights failed: {e}")
    result["timings"]["automation_insights"] = round(time.monotonic() - t105, 3)

    if result.get("confidence_tier") == "MEDIUM":
        conf_val = result.get("confidence_for_tier", 0)
        context_brief += (
            f"\nCONFIDENCE GATE (MEDIUM — extra validation required, confidence={conf_val:.0%}):\n"
            "Before committing changes, verify:\n"
            "1. Run existing tests to confirm no regressions\n"
            "2. If creating new code, add at least one smoke test\n"
            "3. Double-check file paths and imports before writing\n"
            "4. Prefer smaller, safer changes over ambitious rewrites\n")

    t1055 = time.monotonic()
    if po_select_variant:
        try:
            po_result = po_select_variant(next_task)
            result["prompt_variant_id"] = po_result["variant_id"]
            result["prompt_variant_task_type"] = po_result["task_type"]
            meta_instr = po_result.get("meta_instruction", "")
            if meta_instr:
                context_brief += f"\n{meta_instr}\n"
            log(f"Prompt variant: {po_result['variant_id'][:60]} (type={po_result['task_type']})")
        except Exception as e:
            log(f"Prompt optimizer failed (non-fatal): {e}")
    result["timings"]["prompt_optimizer"] = round(time.monotonic() - t1055, 3)

    t106 = time.monotonic()
    if cog_workspace:
        try:
            cw_result = cog_workspace.set_task(next_task)
            if cw_result.get("reactivated"):
                log(f"Cognitive workspace: reactivated {len(cw_result['reactivated'])} dormant items")
                cog_workspace.sync_from_spotlight()
        except Exception as e:
            log(f"Cognitive workspace failed: {e}")
    result["timings"]["cognitive_workspace"] = round(time.monotonic() - t106, 3)
    result["episodic_hints"] = compressed_episodes
    return context_brief


def _preflight_pruning_obligations_directives(context_brief, result, next_task):
    """DyCP pruning + obligation check + directive engine."""
    if dycp_prune_brief and next_task:
        try:
            pre_len = len(context_brief)
            context_brief = dycp_prune_brief(context_brief, next_task)
            pruned_bytes = pre_len - len(context_brief)
            if pruned_bytes > 0:
                log(f"DyCP pruning: removed {pruned_bytes}B of irrelevant context")
        except Exception as e:
            log(f"DyCP pruning failed (non-fatal): {e}")

    t_ob = time.monotonic()
    if ObligationTracker:
        try:
            tracker = ObligationTracker()
            obligation_result = tracker.preflight_check()
            ob_ctx = obligation_result.get("obligation_context", "")
            if ob_ctx:
                context_brief += f"\n{ob_ctx}\n"
                log(f"Obligation check: {obligation_result.get('checked', 0)} checked, "
                    f"{len(obligation_result.get('violations', []))} violations")
            result["obligation_violations"] = obligation_result.get("violations", [])
            result["obligation_git_hygiene"] = obligation_result.get("git_hygiene", {})
        except Exception as e:
            log(f"Obligation check failed (non-fatal): {e}")
    result["timings"]["obligation_check"] = round(time.monotonic() - t_ob, 3)

    t_dir = time.monotonic()
    if DirectiveEngine:
        try:
            deng = DirectiveEngine()
            deng._sweep_expiry()
            dir_context = deng.build_context(
                task_context=result.get("selected_task", {}).get("label", ""),
                max_tokens=300)
            if dir_context:
                context_brief += f"\n{dir_context}\n"
                log(f"Directive engine: {len(deng.list_active())} active directives injected")
            result["directive_count"] = len(deng.list_active())
        except Exception as e:
            log(f"Directive engine failed (non-fatal): {e}")
    result["timings"]["directive_engine"] = round(time.monotonic() - t_dir, 3)

    return context_brief


def _preflight_auth_check(result):
    """Quick API auth validation — catches expired tokens before they become episode failures.

    Returns True if auth is OK (or check is skipped), False if auth failed (result updated).
    This prevents system/infrastructure failures from polluting action accuracy.
    """
    try:
        import subprocess
        check = subprocess.run(
            [os.environ.get("CLAUDE_BIN", os.path.expanduser("~/.local/bin/claude")), "--version"],
            capture_output=True, text=True, timeout=10
        )
        # If claude CLI works, auth is likely fine (it validates on startup)
        if check.returncode != 0:
            stderr = check.stderr or ""
            if "401" in stderr or "auth" in stderr.lower() or "token" in stderr.lower():
                log("AUTH PRE-CHECK FAILED: API token appears expired/invalid — skipping heartbeat")
                result["status"] = "skip"
                result["skip_reason"] = "auth_preflight_failed"
                return False
        return True
    except Exception as e:
        log(f"Auth pre-check error (non-fatal, proceeding): {e}")
        return True  # fail-open: don't block heartbeat on check failure


def _make_preflight_result():
    """Create the initial result dict with default values."""
    return {
        "status": "ok", "task": None, "task_section": None, "task_salience": 0.0,
        "cognitive_load": {}, "should_defer": False, "procedure": None,
        "procedure_id": None, "procedure_injected": False, "procedures_for_injection": [],
        "chain_id": None, "prediction_event": None, "prediction_confidence": 0.7,
        "episodic_hints": "", "context_brief": "", "confidence_tier": "HIGH",
        "confidence_action": "execute", "confidence_for_tier": 0.7,
        "route_tier": "complex", "route_executor": "claude", "route_score": 0.5,
        "route_reason": "unknown", "prompt_variant_id": "", "prompt_variant_task_type": "",
        "context_relevance_score": None, "priority_override": None,
        "timings": {},
    }


def _preflight_assemble_context(result, next_task, ctx):
    """§10: Full context assembly pipeline (brief + supplements + enrichments + pruning).

    Args:
        result: The preflight result dict (mutated in place).
        next_task: Selected task string.
        ctx: Dict with keys: similar_episodes, failure_episodes, knowledge_hints,
             brain_goals, brain_context, brain_working_memory, failure_avoidance,
             procs_for_injection, synaptic_associations, codelet_result,
             gwt_broadcast_text, introspection_text, code_templates_hint,
             compressed_episodes.
    """
    t10 = time.monotonic()
    _suppressed_sections = set()
    try:
        from clarvis.cognition.context_relevance import get_suppressed_sections
        _suppressed_sections = get_suppressed_sections(threshold=0.15, min_episodes=10)
        if _suppressed_sections:
            log(f"Section gate: suppressing {_suppressed_sections}")
    except Exception:
        pass

    brief = _preflight_generate_brief(result, next_task, ctx["knowledge_hints"], ctx["compressed_episodes"])
    brief = _preflight_append_supplementary(
        brief, result, ctx["brain_goals"], ctx["brain_context"], ctx["brain_working_memory"],
        ctx["failure_avoidance"], ctx["procs_for_injection"], ctx["synaptic_associations"],
        ctx["codelet_result"], ctx["gwt_broadcast_text"], ctx["introspection_text"],
        ctx["code_templates_hint"], _suppressed_sections)
    brief = _preflight_insights_prompt_workspace(brief, result, next_task, ctx["compressed_episodes"])
    brief = _preflight_pruning_obligations_directives(brief, result, next_task)

    result["context_brief"] = brief
    result["timings"]["context"] = round(time.monotonic() - t10, 3)


def run_preflight(dry_run=False):
    """Run all pre-execution checks in a single process.

    Returns a dict with all results needed by cron_autonomous.sh.
    """
    log(f"All modules imported in {_import_time:.2f}s (single process)")
    t0 = time.monotonic()
    result = _make_preflight_result()

    # Populate context_relevance from gate/performance metrics (zero-LLM)
    try:
        from clarvis.heartbeat.gate import get_context_relevance, CONTEXT_RELEVANCE_THRESHOLD
        cr = get_context_relevance()
        result["context_relevance_score"] = cr
        if cr is not None and cr < CONTEXT_RELEVANCE_THRESHOLD:
            result["priority_override"] = "context_improvement"
            log(f"Context relevance {cr:.3f} < {CONTEXT_RELEVANCE_THRESHOLD} — prioritizing context improvement tasks")
    except Exception as e:
        log(f"Context relevance check failed (non-fatal): {e}")

    codelet_result = _preflight_attention(result)
    sel = _preflight_select_task(result, codelet_result, t0)
    if sel is None:
        return result
    next_task, task_section, best_salience = sel
    if dry_run:
        result["timings"]["total"] = round(time.monotonic() - t0, 3)
        return result

    # --- Auth pre-check: abort early if API token is invalid ---
    # Prevents "system" failures (expired OAuth) from polluting action accuracy
    if not _preflight_auth_check(result):
        return result

    try:
        attention.submit(f"CURRENT TASK: {next_task}", source="heartbeat",
                         importance=0.9, relevance=0.8)
    except Exception:
        pass

    _preflight_load_sizing(result, next_task, task_section)
    procs_for_injection, code_templates_hint = _preflight_procedural(result, next_task)
    # §6: Open reasoning chain for task tracking
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
    dyn_conf = _preflight_confidence_world_model(result, next_task, task_section)
    dyn_conf = _preflight_confidence_tier(result, dyn_conf, next_task, t0)
    if dyn_conf is None:
        return result

    gwt_broadcast_text, retrieval_tier_info, _rt = _preflight_gwt_retrieval_gate(result, next_task)

    # --- Parallel execution of 3 independent preflight stages ---
    # Inspired by Claude Code harness `isConcurrencySafe` / `toolOrchestration.ts`:
    # episodic recall, brain bridge, and introspection/synaptic are independent
    # once the retrieval tier is known. Running them in parallel via threads
    # saves ~30-50% of the total preflight I/O wait time.
    #
    # Each function mutates `result` (adding timings + data), which is safe because
    # they write to disjoint keys. Return values are collected via futures.
    _parallel_enabled = os.environ.get("CLARVIS_PREFLIGHT_PARALLEL", "1") != "0"

    if _parallel_enabled:
        t_par = time.monotonic()
        _ep_result = {}
        _bb_result = {}
        _is_result = {}

        def _par_episodic():
            return _preflight_episodic(result, next_task, _rt)

        def _par_brain_bridge():
            return _preflight_brain_bridge(result, next_task, _rt, retrieval_tier_info)

        def _par_introspection():
            return _preflight_introspection_synaptic(result, next_task)

        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="preflight") as executor:
            fut_ep = executor.submit(_par_episodic)
            fut_bb = executor.submit(_par_brain_bridge)
            fut_is = executor.submit(_par_introspection)

            similar_episodes, failure_episodes = fut_ep.result()
            knowledge_hints, brain_goals, brain_context, brain_working_memory, _ = fut_bb.result()
            introspection_text, synaptic_associations, failure_avoidance = fut_is.result()

        result["timings"]["parallel_wall"] = round(time.monotonic() - t_par, 3)
        _seq_time = (result["timings"].get("episodic", 0) +
                     result["timings"].get("knowledge", 0) +
                     result["timings"].get("brain_introspection", 0) +
                     result["timings"].get("synaptic_spread", 0) +
                     result["timings"].get("failure_avoidance", 0))
        _saved = max(0, _seq_time - result["timings"]["parallel_wall"])
        log(f"Parallel preflight: wall={result['timings']['parallel_wall']:.3f}s "
            f"seq_sum={_seq_time:.3f}s saved={_saved:.3f}s")
    else:
        similar_episodes, failure_episodes = _preflight_episodic(result, next_task, _rt)
        knowledge_hints, brain_goals, brain_context, brain_working_memory, _ = \
            _preflight_brain_bridge(result, next_task, _rt, retrieval_tier_info)
        # Pass recalled IDs to avoid duplicate brain.recall in synaptic spread
        introspection_text, synaptic_associations, failure_avoidance = \
            _preflight_introspection_synaptic(result, next_task,
                                              recalled_memory_ids=result.get("recalled_memory_ids"))
    # §9: Task routing / classification
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

    # Compress episodic hints for tiered brief
    if (similar_episodes or failure_episodes) and compress_episodes:
        try:
            compressed_episodes = compress_episodes(similar_episodes, failure_episodes)
            if not compressed_episodes:
                compressed_episodes = f"{similar_episodes}\n---\n{failure_episodes}" if (similar_episodes or failure_episodes) else ""
        except Exception:
            compressed_episodes = f"{similar_episodes}\n---\n{failure_episodes}" if (similar_episodes or failure_episodes) else ""
    elif similar_episodes or failure_episodes:
        compressed_episodes = f"{similar_episodes}\n---\n{failure_episodes}"
    else:
        compressed_episodes = ""
    _preflight_assemble_context(result, next_task, ctx={
        "similar_episodes": similar_episodes, "failure_episodes": failure_episodes,
        "knowledge_hints": knowledge_hints, "brain_goals": brain_goals,
        "brain_context": brain_context, "brain_working_memory": brain_working_memory,
        "failure_avoidance": failure_avoidance, "procs_for_injection": procs_for_injection,
        "synaptic_associations": synaptic_associations, "codelet_result": codelet_result,
        "gwt_broadcast_text": gwt_broadcast_text, "introspection_text": introspection_text,
        "code_templates_hint": code_templates_hint, "compressed_episodes": compressed_episodes,
    })

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
