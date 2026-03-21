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

from attention import attention, get_codelet_competition, get_attention_schema

try:
    from clarvis.orch.task_selector import parse_tasks, score_tasks
except ImportError:
    parse_tasks = None
    score_tasks = None

try:
    from cognitive_load import should_defer_task, estimate_task_complexity, log_sizing
except ImportError:
    should_defer_task = None
    estimate_task_complexity = None
    log_sizing = None

try:
    from procedural_memory import find_procedure, find_code_templates, format_code_templates
except ImportError:
    find_procedure = None
    find_code_templates = None
    format_code_templates = None

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
    from clarvis.context.assembly import dycp_prune_brief
except ImportError:
    dycp_prune_brief = None

try:
    from clarvis.orch.router import classify_task
except ImportError:
    classify_task = None

try:
    from world_models import predict_task_outcome as wm_predict
except ImportError:
    wm_predict = None

try:
    from workspace_broadcast import WorkspaceBroadcast
except ImportError:
    WorkspaceBroadcast = None

try:
    from brain_bridge import brain_preflight_context
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
    from synaptic_memory import SynapticMemory
except ImportError:
    SynapticMemory = None

try:
    from somatic_markers import SomaticMarkerSystem
except ImportError:
    SomaticMarkerSystem = None

try:
    from cognitive_workspace import workspace as cog_workspace
except ImportError:
    cog_workspace = None

try:
    from prompt_optimizer import select_variant as po_select_variant
except ImportError:
    po_select_variant = None

try:
    from clarvis.brain.retrieval_gate import classify_retrieval as gate_classify
except ImportError:
    gate_classify = None

try:
    from obligation_tracker import ObligationTracker
except ImportError:
    ObligationTracker = None

_import_time = time.monotonic() - start_import
log = lambda msg: print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')}] PREFLIGHT: {msg}", file=sys.stderr)


QUEUE_FILE = os.path.join(os.path.dirname(__file__), "..", "memory", "evolution", "QUEUE.md")
WORKSPACE = os.path.join(os.path.dirname(__file__), "..")
LOCK_DIR = "/tmp"


def _verify_task_executable(task_text):
    """Pre-execution verification gate.

    Checks:
    1. Task description parses to concrete steps (not empty/vague)
    2. Referenced files/scripts exist
    3. No conflicting lock held

    Returns dict with passed, reason, hard_fail.
    """
    import re

    checks_passed = 0
    checks_total = 3
    reasons = []

    # 1. Format check: task has a tag and description
    tag_match = re.match(r"\[([^\]]+)\]\s*(.+)", task_text.strip())
    if tag_match:
        tag = tag_match.group(1)
        desc = tag_match.group(2)
        if len(desc) < 10:
            reasons.append(f"description too short ({len(desc)} chars)")
        else:
            checks_passed += 1
    else:
        # Untagged task — still valid if has substance
        if len(task_text.strip()) >= 20:
            checks_passed += 1
        else:
            reasons.append("task too short/vague")

    # 2. File reference check: find referenced scripts/files and verify they exist
    file_refs = re.findall(
        r'(?:scripts/|clarvis/|packages/|data/|memory/)[\w/\-_.]+\.(?:py|sh|json|md|yaml)',
        task_text,
    )
    missing_files = []
    for ref in file_refs:
        full_path = os.path.join(WORKSPACE, ref)
        if not os.path.exists(full_path):
            missing_files.append(ref)
    if missing_files:
        reasons.append(f"missing files: {', '.join(missing_files[:3])}")
    else:
        checks_passed += 1

    # 3. Lock check: ensure no conflicting lock held
    #    Uses /proc/<pid>/cmdline to verify the lock holder is actually
    #    a clarvis/claude process (prevents false honors from PID recycling).
    lock_conflict = False
    _lock_markers = ("clarvis", "claude", "cron_", "project_agent")
    for lockfile in ("clarvis_claude_global.lock", "clarvis_maintenance.lock"):
        lock_path = os.path.join(LOCK_DIR, lockfile)
        if os.path.exists(lock_path):
            try:
                with open(lock_path) as f:
                    pid_str = f.read().strip()
                pid = int(pid_str)
                os.kill(pid, 0)  # alive?
                # Verify via /proc/<pid>/cmdline
                cmdline_file = f"/proc/{pid}/cmdline"
                if os.path.exists(cmdline_file):
                    with open(cmdline_file, "rb") as cf:
                        cmdline = cf.read().replace(b"\x00", b" ").decode("utf-8", errors="replace")
                    if not any(m in cmdline for m in _lock_markers):
                        # PID recycled — not a clarvis process, ignore lock
                        continue
                reasons.append(f"lock held: {lockfile} (pid {pid})")
                lock_conflict = True
            except (ValueError, ProcessLookupError, PermissionError, OSError):
                pass  # stale lock or dead process — ignore
    if not lock_conflict:
        checks_passed += 1

    passed = checks_passed == checks_total
    hard_fail = bool(missing_files) and len(missing_files) > 2

    return {
        "passed": passed,
        "reason": "; ".join(reasons) if reasons else "all checks passed",
        "checks_passed": checks_passed,
        "checks_total": checks_total,
        "hard_fail": hard_fail,
        "missing_files": missing_files,
    }


def run_preflight(dry_run=False):
    """Run all pre-execution checks in a single process.

    Returns a dict with all results needed by cron_autonomous.sh.
    """
    log(f"All modules imported in {_import_time:.2f}s (single process)")
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
        "procedure_injected": False,
        "procedures_for_injection": [],
        "chain_id": None,
        "prediction_event": None,
        "prediction_confidence": 0.7,
        "episodic_hints": "",
        "context_brief": "",
        "confidence_tier": "HIGH",
        "confidence_action": "execute",
        "confidence_for_tier": 0.7,
        "route_tier": "complex",
        "route_executor": "claude",
        "route_score": 0.5,
        "route_reason": "unknown",
        "prompt_variant_id": "",
        "prompt_variant_task_type": "",
        "timings": {},
    }

    # === 1. ATTENTION: Load + Tick + Codelet Competition (LIDA) ===
    t1 = time.monotonic()
    codelet_result = None
    try:
        attention._load()
        attention.tick()
        log("Attention load+tick done")
    except Exception as e:
        log(f"Attention load+tick failed: {e}")

    # Run LIDA codelet competition — domain-specific codelets compete for broadcast
    try:
        competition = get_codelet_competition()
        codelet_result = competition.compete()
        winner = codelet_result.get("winner", "?")
        coalition = codelet_result.get("coalition", [])
        coalition_score = codelet_result.get("coalition_score", 0)
        activations = codelet_result.get("activations", {})
        log(f"Codelet competition: winner={winner} "
            f"coalition={','.join(coalition)} score={coalition_score:.3f} "
            f"activations={activations}")
        result["codelet_winner"] = winner
        result["codelet_coalition"] = coalition
        result["codelet_activations"] = activations
        result["codelet_domain_bias"] = codelet_result.get("domain_bias", {})
    except Exception as e:
        log(f"Codelet competition failed (non-fatal): {e}")

    # AST: Attention Schema prediction — predict what will capture attention next
    try:
        schema = get_attention_schema()
        prediction = schema.predict_next_focus(context="heartbeat preflight")
        result["ast_prediction"] = prediction.get("predicted_domain", "unknown")
        log(f"AST prediction: domain={prediction['predicted_domain']} "
            f"focus={prediction['predicted_focus_type']}")
    except Exception as e:
        log(f"AST prediction failed (non-fatal): {e}")

    result["timings"]["attention_tick"] = round(time.monotonic() - t1, 3)

    # === 2. TASK SELECTION (with fallback-on-defer loop) ===
    t2 = time.monotonic()
    next_task = None
    task_section = "P1"
    best_salience = 0.0

    # Build ranked candidate list
    candidates = []
    if parse_tasks and score_tasks:
        try:
            tasks = parse_tasks()
            if not tasks:
                result["status"] = "queue_empty"
                log("Queue empty — no tasks to execute")
                result["timings"]["total"] = round(time.monotonic() - t0, 3)
                return result

            # Score all tasks using attention salience + codelet bias (sorted by salience)
            scored = score_tasks(tasks, codelet_result=codelet_result)
            candidates = scored
        except Exception as e:
            log(f"Task selector failed: {e}")

    # Fallback: grep unchecked tasks (collect multiple for fallback rotation)
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
                log(f"Fallback: {len(candidates)} unchecked tasks found")
        except Exception as e:
            log(f"Fallback task search failed: {e}")

    if not candidates:
        result["status"] = "no_tasks"
        result["timings"]["total"] = round(time.monotonic() - t0, 3)
        return result

    # --- DEFER-FALLBACK LOOP: Try candidates until one passes all gates ---
    MAX_CANDIDATES = 20  # Wider scan to avoid burning a slot on one oversized cluster

    def _evaluate_candidates(candidate_list, deferred_tasks, pass_name="primary"):
        selected = None
        selected_section = None
        selected_salience = 0.0
        selected_tag = None
        autosplit_tags = []

        for candidate in candidate_list[:MAX_CANDIDATES]:
            cand_task = candidate.get("text", "")
            cand_section = candidate.get("section", "P1")
            cand_salience = candidate.get("salience", 0.0)

            if not cand_task:
                continue

            # Gate 1: Cognitive load check (section-dependent)
            if should_defer_task:
                try:
                    defer, load_info = should_defer_task(cand_section)
                    if defer:
                        deferred_tasks.append({"task": cand_task[:80], "reason": f"cognitive_load: {load_info}"})
                        log(f"Skipping (cognitive load, {cand_section}): {cand_task[:60]}...")
                        continue
                except Exception as e:
                    log(f"Cognitive load check failed for candidate: {e}")

            # Gate 2: Task sizing — defer oversized tasks, but try auto-split first
            if estimate_task_complexity:
                try:
                    sizing = estimate_task_complexity(cand_task)
                    if sizing["recommendation"] == "defer_to_sprint":
                        if log_sizing:
                            log_sizing(cand_task, sizing)
                        # Auto-split oversized tasks (non-blocking — inject meaningful subtasks + mark parent)
                        try:
                            import re as _re
                            m = _re.match(r"\[([^\]]+)\]", cand_task.strip())
                            parent_tag = m.group(1).strip() if m else ""
                            if parent_tag:
                                from queue_writer import ensure_subtasks_for_tag, mark_task_in_progress
                                subtasks = [
                                    f"[{parent_tag}_1] Analyze: read relevant source files, identify change boundary",
                                    f"[{parent_tag}_2] Implement: core logic change in one focused increment",
                                    f"[{parent_tag}_3] Test: add/update test(s) covering the new behavior",
                                    f"[{parent_tag}_4] Verify: run existing tests, confirm no regressions",
                                ]
                                inserted = ensure_subtasks_for_tag(
                                    parent_tag,
                                    subtasks=subtasks,
                                    source="auto_split",
                                )
                                if inserted:
                                    autosplit_tags.append(parent_tag)
                                    log(f"Auto-split: inserted subtasks for [{parent_tag}] into QUEUE.md")
                                    try:
                                        mark_task_in_progress(parent_tag)
                                        log(f"Auto-split: marked [{parent_tag}] as in-progress ([~])")
                                    except Exception as me:
                                        log(f"Auto-split: parent mark failed (non-fatal): {me}")
                        except Exception as e:
                            log(f"Auto-split failed (non-fatal): {e}")

                        deferred_tasks.append({
                            "task": cand_task[:80],
                            "reason": f"oversized (score={sizing['score']:.2f}, signals={sizing['signals']})",
                        })
                        log(f"Skipping (oversized, score={sizing['score']:.2f}): {cand_task[:60]}...")
                        continue
                except Exception as e:
                    log(f"Task sizing failed for candidate: {e}")

            # Gate 3: Verification (hard failures only block)
            try:
                verification = _verify_task_executable(cand_task)
                if verification.get("hard_fail"):
                    deferred_tasks.append({"task": cand_task[:80], "reason": f"verification: {verification['reason']}"})
                    log(f"Skipping (verification hard fail): {cand_task[:60]}...")
                    continue
            except Exception:
                pass

            # Gate 4: Mode compliance — skip tasks disallowed by operating mode
            try:
                from clarvis.runtime.mode import is_task_allowed_for_mode
                allowed, mode_reason = is_task_allowed_for_mode(cand_task)
                if not allowed:
                    deferred_tasks.append({"task": cand_task[:80], "reason": f"mode_gate: {mode_reason}"})
                    log(f"Skipping (mode gate): {cand_task[:60]}... ({mode_reason})")
                    continue
            except ImportError:
                pass  # Mode system not available — allow all
            except Exception as e:
                log(f"Mode gate check failed (non-fatal): {e}")

            selected = cand_task
            selected_section = cand_section
            selected_salience = cand_salience
            try:
                import re as _re
                m = _re.match(r"\[([^\]]+)\]", cand_task.strip())
                selected_tag = m.group(1).strip() if m else None
            except Exception:
                selected_tag = None
            break

        return selected, selected_section, selected_salience, selected_tag, autosplit_tags

    deferred_tasks = []
    next_task, task_section, best_salience, selected_tag, autosplit_tags = _evaluate_candidates(candidates, deferred_tasks, "primary")

    # Rescue pass: if the first pass only saw oversized parents, rescan the queue so the
    # freshly inserted subtasks can compete in the same heartbeat instead of wasting the slot.
    if not next_task and autosplit_tags:
        try:
            reparsed = parse_tasks(QUEUE_FILE) if parse_tasks else []
            rescored = score_tasks(reparsed) if (score_tasks and reparsed) else []
            deferred_prefixes = {d["task"] for d in deferred_tasks}
            rescue_candidates = [
                c for c in rescored
                if c.get("text") and c.get("text")[:80] not in deferred_prefixes
            ]
            if rescue_candidates:
                log(f"Rescue pass: rescanning queue after auto-split ({len(autosplit_tags)} parent(s))")
                next_task, task_section, best_salience, selected_tag, more_autosplit = _evaluate_candidates(
                    rescue_candidates, deferred_tasks, "rescue"
                )
                autosplit_tags.extend(more_autosplit)
        except Exception as e:
            log(f"Rescue pass failed (non-fatal): {e}")

    if not next_task:
        log(f"All {len(deferred_tasks)} candidates deferred — no executable task this heartbeat")
        result["should_defer"] = True
        result["defer_reason"] = "all_candidates_deferred"
        result["deferred_tasks"] = deferred_tasks
        try:
            attention.submit(
                f"ALL TASKS DEFERRED ({len(deferred_tasks)} candidates checked)",
                source="heartbeat", importance=0.7)
        except Exception:
            pass
        result["timings"]["task_selection"] = round(time.monotonic() - t2, 3)
        result["timings"]["total"] = round(time.monotonic() - t0, 3)
        return result

    if deferred_tasks:
        log(f"Skipped {len(deferred_tasks)} deferred tasks, executing fallback: {next_task[:60]}...")
        result["deferred_tasks"] = deferred_tasks

    result["task"] = next_task
    # Canonical tag for deterministic QUEUE completion marking
    try:
        import re
        m = re.match(r"\[([^\]]+)\]", next_task.strip())
        result["task_tag"] = m.group(1) if m else None
    except Exception:
        result["task_tag"] = None

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

    # === 4. COGNITIVE LOAD + TASK SIZING (already checked in defer-fallback loop above) ===
    # Re-run sizing for the selected task to populate result fields
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

    # === 4.7 ACTION VERIFY GATE: Re-run for result population ===
    t47 = time.monotonic()
    try:
        verification = _verify_task_executable(next_task)
        result["verification"] = verification
        if not verification["passed"]:
            log(f"Verification note: {verification['reason']}")
        else:
            log(f"Verification OK: {verification['reason']}")
    except Exception as e:
        log(f"Verification gate failed (non-fatal): {e}")
    result["timings"]["verification"] = round(time.monotonic() - t47, 3)

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

    # === 5.2 PROCEDURE INJECTION: Collect top-2 procedures for prompt injection ===
    t52 = time.monotonic()
    procs_for_injection = []
    if result.get("procedure") and result["procedure"].get("steps"):
        procs_for_injection.append(result["procedure"])
    # Try to find a 2nd procedure match via direct brain query
    if len(procs_for_injection) < 2:
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
                    "id": r["id"],
                    "name": meta.get("name", "unknown"),
                    "steps": steps,
                    "use_count": uc,
                    "success_count": sc,
                    "success_rate": sc / uc if uc > 0 else 1.0,
                })
                if len(procs_for_injection) >= 2:
                    break
        except Exception as e:
            log(f"2nd procedure lookup failed (non-fatal): {e}")
    result["procedures_for_injection"] = [p.get("id", "") for p in procs_for_injection]
    result["timings"]["proc_injection_collect"] = round(time.monotonic() - t52, 3)

    # === 5.5 CODE TEMPLATES: Inject scaffolds for CODE-type tasks ===
    t55 = time.monotonic()
    code_templates_hint = ""
    if find_code_templates and format_code_templates:
        try:
            # Check if task has code-generation signals (keyword heuristic)
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
                    log(f"Code templates: {len(templates)} matched "
                        f"({', '.join(t['name'] for t in templates)})")
        except Exception as e:
            log(f"Code template lookup failed: {e}")
    result["code_templates_hint"] = code_templates_hint
    result["timings"]["code_templates"] = round(time.monotonic() - t55, 3)

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

    # === 7.5 WORLD MODEL: Predict task outcome (Ha&Schmidhuber + JEPA) ===
    t75 = time.monotonic()
    if wm_predict:
        try:
            wm_result = wm_predict(next_task, task_section)
            result["wm_prediction"] = wm_result.get("prediction", "unknown")
            result["wm_p_success"] = wm_result.get("p_success", 0.5)
            result["wm_curiosity"] = wm_result.get("curiosity", 0.5)
            log(f"World model: prediction={wm_result['prediction']}, "
                f"P(success)={wm_result['p_success']:.0%}, "
                f"curiosity={wm_result['curiosity']:.2f}")
        except Exception as e:
            log(f"World model prediction failed: {e}")
    result["timings"]["world_model"] = round(time.monotonic() - t75, 3)

    # === 7.6 CONFIDENCE TIERED ACTIONS: Gate execution by confidence level ===
    # HIGH (≥0.8)     → execute autonomously
    # MEDIUM (0.5-0.8) → execute with extra validation gate injected into prompt
    # LOW (0.3-0.5)    → dry-run mode (log what would be done, skip execution)
    # UNKNOWN (<0.3)   → skip entirely (defer to next heartbeat)
    confidence_for_tier = dyn_conf
    # Factor in world model P(success) if available — average with dynamic confidence
    wm_p = result.get("wm_p_success")
    if wm_p is not None:
        confidence_for_tier = (dyn_conf + wm_p) / 2

    if confidence_for_tier >= 0.8:
        confidence_tier = "HIGH"
        confidence_action = "execute"
    elif confidence_for_tier >= 0.5:
        confidence_tier = "MEDIUM"
        confidence_action = "execute_with_validation"
    elif confidence_for_tier >= 0.3:
        confidence_tier = "LOW"
        confidence_action = "dry_run"
    else:
        confidence_tier = "UNKNOWN"
        confidence_action = "skip"

    result["confidence_tier"] = confidence_tier
    result["confidence_action"] = confidence_action
    result["confidence_for_tier"] = round(confidence_for_tier, 3)
    log(f"Confidence tier: {confidence_tier} (combined={confidence_for_tier:.2f}, "
        f"dyn={dyn_conf:.2f}, wm_p={wm_p if wm_p is not None else 'N/A'})")

    # UNKNOWN confidence → defer task entirely (no useful signal)
    if confidence_tier == "UNKNOWN":
        result["should_defer"] = True
        result["defer_reason"] = f"unknown_confidence ({confidence_for_tier:.2f})"
        log(f"UNKNOWN confidence — deferring task: {next_task[:60]}")
        try:
            attention.submit(
                f"TASK DEFERRED (UNKNOWN confidence={confidence_for_tier:.2f}): {next_task[:60]}",
                source="heartbeat", importance=0.7)
        except Exception:
            pass
        result["timings"]["total"] = round(time.monotonic() - t0, 3)
        return result

    # LOW confidence → dry-run mode (gather context but skip actual execution)
    if confidence_tier == "LOW":
        result["should_defer"] = True
        result["defer_reason"] = f"low_confidence_dry_run ({confidence_for_tier:.2f})"
        result["dry_run"] = True
        log(f"LOW confidence — dry-run mode for task: {next_task[:60]}")
        try:
            attention.submit(
                f"TASK DRY-RUN (LOW confidence={confidence_for_tier:.2f}): {next_task[:60]}",
                source="heartbeat", importance=0.6)
        except Exception:
            pass
        result["timings"]["total"] = round(time.monotonic() - t0, 3)
        return result

    # === 7.7 GWT BROADCAST: Run LIDA cognitive cycle ===
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

    # === 7.8 RETRIEVAL GATE: Classify retrieval need before brain recall ===
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
        result["retrieval_tier"] = "DEEP_RETRIEVAL"  # fallback: full recall
    result["timings"]["retrieval_gate"] = round(time.monotonic() - t78, 3)
    _rt = result.get("retrieval_tier", "DEEP_RETRIEVAL")

    # === 8. EPISODIC MEMORY: Recall similar episodes ===
    # Gated by retrieval_tier from §7.8 — NO_RETRIEVAL skips entirely
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

    # === 8.5 BRAIN BRIDGE: Full brain context (goals + context + knowledge + working memory) ===
    # Gated by retrieval_tier from §7.8
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
            # Adjust recall depth, collections, and graph expansion based on retrieval tier
            _graph_expand = False
            _tier_collections = None
            if _rt == "LIGHT_RETRIEVAL":
                _n_knowledge = 3
                # Use tier's collection list (capped to 2 for LIGHT)
                if retrieval_tier_info and retrieval_tier_info.collections:
                    _tier_collections = retrieval_tier_info.collections[:2]
            else:  # DEEP_RETRIEVAL
                _graph_expand = bool(retrieval_tier_info and retrieval_tier_info.graph_expand)
                _n_knowledge = 10 if _graph_expand else 5
            brain_ctx = brain_preflight_context(next_task, n_knowledge=_n_knowledge, n_goals=5,
                                                graph_expand=_graph_expand,
                                                collections=_tier_collections)
            knowledge_hints = brain_ctx.get("knowledge_hints", "")
            brain_goals = brain_ctx.get("goals_text", "")
            brain_context = brain_ctx.get("context", "")
            brain_working_memory = brain_ctx.get("working_memory", "")
            brain_timings = brain_ctx.get("brain_timings", {})
            log(f"Brain bridge ({_rt}): knowledge={len(knowledge_hints)}B goals={len(brain_goals)}B "
                f"context={len(brain_context)}B wm={len(brain_working_memory)}B "
                f"timings={brain_timings}")
        except Exception as e:
            log(f"Brain bridge preflight failed: {e}")
    else:
        # Fallback: ad-hoc brain recall (legacy) — only if not NO_RETRIEVAL
        try:
            from brain import get_brain, LEARNINGS
            b = get_brain()
            _n_fallback = 3 if _rt == "LIGHT_RETRIEVAL" else 5
            learnings = b.recall(next_task, collections=[LEARNINGS], n=_n_fallback, min_importance=0.3)
            if learnings:
                hints = []
                for mem in learnings:
                    doc = mem.get("document", "")[:120]
                    src = mem.get("metadata", {}).get("source", "")
                    tags = mem.get("metadata", {}).get("tags", "")
                    if "dream" in str(tags):
                        prefix = "[DREAM]"
                    elif "research" in str(src) or "research" in str(tags):
                        prefix = "[RESEARCH]"
                    elif "synthesis" in str(src):
                        prefix = "[SYNTHESIS]"
                    else:
                        prefix = "[LEARNING]"
                    hints.append(f"  {prefix} {doc}")
                knowledge_hints = "\n".join(hints)
                log(f"Brain knowledge (legacy, {_rt}): {len(learnings)} relevant learnings found")
        except Exception as e:
            log(f"Brain knowledge recall failed: {e}")
    result["knowledge_hints"] = knowledge_hints
    result["brain_goals"] = brain_goals
    result["brain_context"] = brain_context
    result["brain_working_memory"] = brain_working_memory
    # Extract recalled memory IDs for postflight recall_success tracking (memory evolution)
    _recalled_ids = []
    _raw = brain_ctx.get("raw_results", []) if brain_preflight_context and brain_ctx else []
    if not _raw:
        _raw = locals().get("learnings", []) or []
    for _mem in (_raw if isinstance(_raw, list) else []):
        _mid = _mem.get("id")
        _mcol = _mem.get("collection")
        if _mid and _mcol:
            _recalled_ids.append({"id": _mid, "collection": _mcol})
    if _recalled_ids:
        result["recalled_memory_ids"] = _recalled_ids
    result["timings"]["knowledge"] = round(time.monotonic() - t85, 3)

    # === 8.6 RETRIEVAL EVAL + ADAPTIVE RETRY: CRAG-style scoring with corrective retry ===
    retrieval_verdict = "SKIPPED"
    try:
        from clarvis.brain.retrieval_eval import adaptive_recall
        from brain import get_brain as _get_brain_for_retry
        # Gather raw results from brain bridge or legacy path
        eval_results = brain_ctx.get("raw_results", []) if brain_preflight_context and brain_ctx else []
        if not eval_results:
            eval_results = locals().get("learnings", [])
        if eval_results and isinstance(eval_results, list) and len(eval_results) > 0:
            b_retry = _get_brain_for_retry()
            ar_out = adaptive_recall(
                b_retry, next_task, tier=_rt,
                original_results=eval_results, n=len(eval_results),
            )
            retrieval_verdict = ar_out["verdict"]
            result["retrieval_verdict"] = retrieval_verdict
            result["retrieval_max_score"] = ar_out["max_score"]
            result["retrieval_retried"] = ar_out["retried"]
            result["retrieval_original_verdict"] = ar_out["original_verdict"]
            result["retrieval_n_filtered"] = ar_out.get("n_filtered_out", 0)
            if ar_out["retry_query"]:
                result["retrieval_retry_query"] = ar_out["retry_query"]
            log(f"Retrieval eval: {retrieval_verdict} "
                f"(max={ar_out['max_score']}, retried={ar_out['retried']}, "
                f"orig={ar_out['original_verdict']}, "
                f"filtered={ar_out.get('n_filtered_out', 0)})")
            # If INCORRECT after retry, omit knowledge_hints entirely
            if retrieval_verdict == "INCORRECT":
                log("Retrieval INCORRECT (even after retry) — knowledge_hints omitted")
                result["knowledge_hints"] = ""
            elif ar_out["results"]:
                # Rebuild knowledge_hints from filtered/refined results
                # This replaces noisy raw results with CRAG-evaluated content
                _filtered_results = ar_out["results"]
                _rebuilt_hints = []
                for _mem in _filtered_results:
                    doc = _mem.get("document", "")[:120]
                    src = _mem.get("metadata", {}).get("source", "")
                    tags = _mem.get("metadata", {}).get("tags", "")
                    col = _mem.get("collection", "")
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
                    _rebuilt_hints.append(f"  {prefix} {doc}")
                if _rebuilt_hints:
                    prev_len = len(result.get("knowledge_hints", ""))
                    result["knowledge_hints"] = "\n".join(_rebuilt_hints)
                    log(f"Knowledge hints rebuilt from eval: "
                        f"{len(eval_results)}→{len(_filtered_results)} results, "
                        f"{prev_len}→{len(result['knowledge_hints'])}B"
                        + (f" (retry improved {ar_out['original_verdict']}→{retrieval_verdict})"
                           if ar_out["retried"] else ""))
        else:
            result["retrieval_verdict"] = "NO_RESULTS"
    except Exception as e:
        log(f"Retrieval eval failed (non-fatal): {e}")
        result["retrieval_verdict"] = "ERROR"

    # === 8.7 BRAIN INTROSPECTION: Deep self-awareness for decision-making ===
    t87 = time.monotonic()
    introspection_text = ""
    if introspect_for_task and format_introspection_for_prompt:
        try:
            # Match budget to route tier (if routing already done, use it; else standard)
            introspect_budget = "standard"
            if result.get("route_tier") in ("complex", "reasoning"):
                introspect_budget = "full"
            elif result.get("route_executor") in ("openrouter", "gemini"):
                introspect_budget = "minimal"

            introspection = introspect_for_task(next_task, budget=introspect_budget)
            introspection_text = format_introspection_for_prompt(introspection, introspect_budget)
            brain_introsp_timings = introspection.get("timings", {})
            log(f"Brain introspection ({introspect_budget}): "
                f"{len(introspection_text)}B, "
                f"meta={introspection.get('meta_awareness', '')[:60]}, "
                f"timings={brain_introsp_timings}")
        except Exception as e:
            log(f"Brain introspection failed: {e}")
    result["brain_introspection"] = introspection_text
    result["timings"]["brain_introspection"] = round(time.monotonic() - t87, 3)

    # === 8.8 SYNAPTIC SPREADING ACTIVATION: Neural associations beyond vector search ===
    t88 = time.monotonic()
    synaptic_associations = ""
    if SynapticMemory:
        try:
            sm = SynapticMemory()
            # Collect memory IDs from brain introspection (which does vector recall with IDs)
            recalled_ids = []
            if introspect_for_task and introspection_text:
                try:
                    # Re-use the introspection result — it has recalled memory IDs
                    from brain import get_brain, LEARNINGS
                    b_syn = get_brain()
                    syn_results = b_syn.recall(next_task, collections=[LEARNINGS], n=5, min_importance=0.3)
                    if syn_results:
                        for mem in syn_results:
                            mid = mem.get("id", "")
                            if mid:
                                recalled_ids.append(mid)
                except Exception:
                    pass
            if recalled_ids:
                spread_results = sm.spread(recalled_ids[:5], n=5, min_weight=0.1)
                if spread_results:
                    # spread() returns list of (memory_id, activation) tuples
                    # Resolve IDs to documents for context
                    lines = []
                    for mem_id, activation in spread_results[:5]:
                        try:
                            doc_results = b_syn.recall(mem_id[:30], n=1)
                            doc_text = doc_results[0].get("document", mem_id)[:80] if doc_results else mem_id[:40]
                        except Exception:
                            doc_text = mem_id[:40]
                        lines.append(f"  [{activation:.2f}] {doc_text}")
                    synaptic_associations = "SYNAPTIC ASSOCIATIONS (neural co-activation):\n" + "\n".join(lines)
                    log(f"Synaptic spread: {len(spread_results)} associations from {len(recalled_ids)} seeds")
        except Exception as e:
            log(f"Synaptic spreading activation failed: {e}")
    result["synaptic_associations"] = synaptic_associations
    result["timings"]["synaptic_spread"] = round(time.monotonic() - t88, 3)

    # === 8.9 SOMATIC MARKERS + EPISODIC CAUSAL CHAINS: Failure avoidance signals ===
    t89 = time.monotonic()
    failure_avoidance = ""
    try:
        avoidance_lines = []

        # Somatic markers: emotional signals from past experiences
        if SomaticMarkerSystem:
            try:
                somatic = SomaticMarkerSystem()
                bias = somatic.get_bias(next_task)
                if bias and bias.get("valence", 0) < -0.1:
                    markers = bias.get("markers", [])
                    for m in markers[:3]:
                        stimulus = m.get("stimulus", "")[:60]
                        val = m.get("valence", 0)
                        if val < -0.1:
                            avoidance_lines.append(f"  AVOID [{val:.2f}]: {stimulus}")
            except Exception:
                pass

        # Episodic causal chains: root causes of recent failures
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
                                cause_text = causes[0].get("task", causes[0].get("description", ""))[:60]
                                avoidance_lines.append(f"  FAIL: {fail_task} <- caused by: {cause_text}")
                            else:
                                lesson = fail_ep.get("lesson", fail_ep.get("error", ""))[:60]
                                if lesson:
                                    avoidance_lines.append(f"  FAIL: {fail_task} — {lesson}")
            except Exception:
                pass

        if avoidance_lines:
            failure_avoidance = "FAILURE AVOIDANCE (somatic markers + causal chains):\n" + "\n".join(avoidance_lines[:5])
            log(f"Failure avoidance: {len(avoidance_lines)} signals")
    except Exception as e:
        log(f"Failure avoidance assembly failed: {e}")
    result["failure_avoidance"] = failure_avoidance
    result["timings"]["failure_avoidance"] = round(time.monotonic() - t89, 3)

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

    # Load suppressed sections (data-driven noise gate)
    _suppressed_sections = set()
    try:
        from clarvis.cognition.context_relevance import get_suppressed_sections
        _suppressed_sections = get_suppressed_sections(threshold=0.13, min_episodes=10)
        if _suppressed_sections:
            log(f"Section gate: suppressing {_suppressed_sections}")
    except Exception:
        pass

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
                knowledge_hints=knowledge_hints,
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

    # Append brain goals to context brief (direct brain → subconscious link)
    if brain_goals and "brain_goals" not in _suppressed_sections:
        context_brief += f"\nBRAIN GOALS (active objectives):\n{brain_goals[:500]}\n"
    if brain_context and "brain_context" not in _suppressed_sections:
        context_brief += f"\nBRAIN CONTEXT: {brain_context[:200]}\n"

    # Append brain working memory (what recent heartbeats were doing)
    if brain_working_memory and "working_memory" not in _suppressed_sections:
        context_brief += f"\nWORKING MEMORY (recent activity):\n{brain_working_memory[:300]}\n"

    # Append world model prediction (success probability + novelty signal)
    wm_p = result.get("wm_p_success")
    wm_curiosity = result.get("wm_curiosity")
    if wm_p is not None and "world_model" not in _suppressed_sections:
        wm_hint = f"WORLD MODEL: P(success)={wm_p:.0%}"
        if wm_curiosity and wm_curiosity > 0.6:
            wm_hint += f", novelty={wm_curiosity:.2f} (explore broadly)"
        elif wm_p < 0.4:
            wm_hint += " (low — tread carefully, check prior failures)"
        context_brief += f"\n{wm_hint}\n"

    # Append failure avoidance signals (somatic markers + causal chains)
    if failure_avoidance and "failure_avoidance" not in _suppressed_sections:
        context_brief += f"\n{failure_avoidance}\n"

    # Append recommended approach from procedural memory (top-2 procedures)
    if procs_for_injection:
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

    # Append synaptic associations (neural co-activation patterns)
    if synaptic_associations and "synaptic" not in _suppressed_sections:
        context_brief += f"\n{synaptic_associations}\n"

    # Append codelet competition results (LIDA domain focus)
    if codelet_result and "attention" not in _suppressed_sections:
        winner = codelet_result.get("winner", "?")
        coalition = codelet_result.get("coalition", [])
        activations = codelet_result.get("activations", {})
        act_str = ", ".join(f"{d}={a:.2f}" for d, a in
                           sorted(activations.items(), key=lambda x: x[1], reverse=True))
        context_brief += (f"\nATTENTION CODELETS (LIDA): "
                         f"winner={winner} coalition={','.join(coalition)} [{act_str}]\n")

    # Append GWT broadcast to context brief (makes broadcast visible to task executor)
    if gwt_broadcast_text and "gwt_broadcast" not in _suppressed_sections:
        context_brief += f"\nGWT BROADCAST (conscious workspace):\n{gwt_broadcast_text[:400]}\n"

    # Append brain introspection (self-awareness context — raised from 600 to 1200 chars)
    if introspection_text and "introspection" not in _suppressed_sections:
        context_brief += f"\n{introspection_text[:1200]}\n"

    # Append code generation templates (scaffolds for CODE-type tasks)
    if code_templates_hint:
        context_brief += f"\n{code_templates_hint}\n"

    # === 10.5 AUTOMATION INSIGHTS: Historical pattern warnings ===
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

    # === 10.52 CONFIDENCE GATE: Extra validation for MEDIUM confidence tasks ===
    if result.get("confidence_tier") == "MEDIUM":
        conf_val = result.get("confidence_for_tier", 0)
        context_brief += (
            f"\nCONFIDENCE GATE (MEDIUM — extra validation required, confidence={conf_val:.0%}):\n"
            "Before committing changes, verify:\n"
            "1. Run existing tests to confirm no regressions\n"
            "2. If creating new code, add at least one smoke test\n"
            "3. Double-check file paths and imports before writing\n"
            "4. Prefer smaller, safer changes over ambitious rewrites\n"
        )

    # === 10.55 PROMPT OPTIMIZATION: Select best variant combo (APE/SPO) ===
    t1055 = time.monotonic()
    if po_select_variant:
        try:
            po_result = po_select_variant(next_task)
            result["prompt_variant_id"] = po_result["variant_id"]
            result["prompt_variant_task_type"] = po_result["task_type"]
            meta_instr = po_result.get("meta_instruction", "")
            if meta_instr:
                context_brief += f"\n{meta_instr}\n"
            log(f"Prompt variant: {po_result['variant_id'][:60]} "
                f"(type={po_result['task_type']})")
        except Exception as e:
            log(f"Prompt optimizer failed (non-fatal): {e}")
    result["timings"]["prompt_optimizer"] = round(time.monotonic() - t1055, 3)

    # === 10.6 COGNITIVE WORKSPACE: Set task + reactivate dormant memory ===
    t106 = time.monotonic()
    if cog_workspace:
        try:
            cw_result = cog_workspace.set_task(next_task)
            reactivated = cw_result.get("reactivated", [])
            if reactivated:
                log(f"Cognitive workspace: reactivated {len(reactivated)} dormant items")
                # Sync spotlight → workspace for coherence
                cog_workspace.sync_from_spotlight()
        except Exception as e:
            log(f"Cognitive workspace failed: {e}")
    result["timings"]["cognitive_workspace"] = round(time.monotonic() - t106, 3)

    result["episodic_hints"] = compressed_episodes

    # DyCP: Final query-dependent pruning of supplementary sections
    # Removes sections that are both historically low-relevance AND irrelevant
    # to this specific task. Targets Context Relevance metric toward 0.75.
    if dycp_prune_brief and next_task:
        try:
            pre_len = len(context_brief)
            context_brief = dycp_prune_brief(context_brief, next_task)
            pruned_bytes = pre_len - len(context_brief)
            if pruned_bytes > 0:
                log(f"DyCP pruning: removed {pruned_bytes}B of irrelevant context")
        except Exception as e:
            log(f"DyCP pruning failed (non-fatal): {e}")

    # === OBLIGATION CHECK: inject violations/git-hygiene into context ===
    t_ob = time.monotonic()
    obligation_result = {}
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
