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

from attention import attention, get_codelet_competition

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

            # Score all tasks using attention salience + codelet bias (sorted by salience)
            scored = score_tasks(tasks, codelet_result=codelet_result)

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

    # === 8.5 BRAIN BRIDGE: Full brain context (goals + context + knowledge + working memory) ===
    t85 = time.monotonic()
    knowledge_hints = ""
    brain_goals = ""
    brain_context = ""
    brain_working_memory = ""
    if brain_preflight_context:
        try:
            brain_ctx = brain_preflight_context(next_task, n_knowledge=5, n_goals=5)
            knowledge_hints = brain_ctx.get("knowledge_hints", "")
            brain_goals = brain_ctx.get("goals_text", "")
            brain_context = brain_ctx.get("context", "")
            brain_working_memory = brain_ctx.get("working_memory", "")
            brain_timings = brain_ctx.get("brain_timings", {})
            log(f"Brain bridge: knowledge={len(knowledge_hints)}B goals={len(brain_goals)}B "
                f"context={len(brain_context)}B wm={len(brain_working_memory)}B "
                f"timings={brain_timings}")
        except Exception as e:
            log(f"Brain bridge preflight failed: {e}")
    else:
        # Fallback: ad-hoc brain recall (legacy)
        try:
            from brain import get_brain, LEARNINGS
            b = get_brain()
            learnings = b.recall(next_task, collections=[LEARNINGS], n=5, min_importance=0.3)
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
                log(f"Brain knowledge (legacy): {len(learnings)} relevant learnings found")
        except Exception as e:
            log(f"Brain knowledge recall failed: {e}")
    result["knowledge_hints"] = knowledge_hints
    result["brain_goals"] = brain_goals
    result["brain_context"] = brain_context
    result["brain_working_memory"] = brain_working_memory
    result["timings"]["knowledge"] = round(time.monotonic() - t85, 3)

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
    if brain_goals:
        context_brief += f"\nBRAIN GOALS (active objectives):\n{brain_goals[:500]}\n"
    if brain_context:
        context_brief += f"\nBRAIN CONTEXT: {brain_context[:200]}\n"

    # Append brain working memory (what recent heartbeats were doing)
    if brain_working_memory:
        context_brief += f"\nWORKING MEMORY (recent activity):\n{brain_working_memory[:300]}\n"

    # Append world model prediction (success probability + novelty signal)
    wm_p = result.get("wm_p_success")
    wm_curiosity = result.get("wm_curiosity")
    if wm_p is not None:
        wm_hint = f"WORLD MODEL: P(success)={wm_p:.0%}"
        if wm_curiosity and wm_curiosity > 0.6:
            wm_hint += f", novelty={wm_curiosity:.2f} (explore broadly)"
        elif wm_p < 0.4:
            wm_hint += " (low — tread carefully, check prior failures)"
        context_brief += f"\n{wm_hint}\n"

    # Append failure avoidance signals (somatic markers + causal chains)
    if failure_avoidance:
        context_brief += f"\n{failure_avoidance}\n"

    # Append synaptic associations (neural co-activation patterns)
    if synaptic_associations:
        context_brief += f"\n{synaptic_associations}\n"

    # Append codelet competition results (LIDA domain focus)
    if codelet_result:
        winner = codelet_result.get("winner", "?")
        coalition = codelet_result.get("coalition", [])
        activations = codelet_result.get("activations", {})
        act_str = ", ".join(f"{d}={a:.2f}" for d, a in
                           sorted(activations.items(), key=lambda x: x[1], reverse=True))
        context_brief += (f"\nATTENTION CODELETS (LIDA): "
                         f"winner={winner} coalition={','.join(coalition)} [{act_str}]\n")

    # Append GWT broadcast to context brief (makes broadcast visible to task executor)
    if gwt_broadcast_text:
        context_brief += f"\nGWT BROADCAST (conscious workspace):\n{gwt_broadcast_text[:400]}\n"

    # Append brain introspection (self-awareness context — raised from 600 to 1200 chars)
    if introspection_text:
        context_brief += f"\n{introspection_text[:1200]}\n"

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
