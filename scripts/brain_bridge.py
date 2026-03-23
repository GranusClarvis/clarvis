#!/usr/bin/env python3
# STATUS: production-wired via heartbeat_preflight + heartbeat_postflight (core pipeline)
# (Misclassified as "weakly wired" in SPINE_USAGE_AUDIT.md §3.3)
"""
Brain Bridge — Connects brain.py directly to the subconscious (heartbeat loop).

This module closes the architecture gap where brain (unified memory) was
only partially wired into the autonomous execution pipeline.

Functions are designed for use in heartbeat_preflight.py and heartbeat_postflight.py:

  PREFLIGHT (before task execution):
    - brain_preflight_context(task) → dict with goals, working_memory, relevant knowledge

  POSTFLIGHT (after task execution):
    - brain_record_outcome(task, status, output_text, duration_s) → stores in brain
    - brain_update_context(task, status) → updates brain's working context
"""

import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

try:
    __import__("actr_activation")
    _HAS_ACTR = True
except ImportError:
    _HAS_ACTR = False


def brain_preflight_context(task_text, n_knowledge=5, n_goals=5, graph_expand=False,
                            collections=None):
    """Gather brain context for a task before execution.

    Queries brain for:
      1. Active goals (with progress)
      2. Current working context
      3. Relevant knowledge from learnings, memories, episodes
      4. Working memory (recent context items)

    Args:
        graph_expand: If True, expand recall results with 1-hop graph neighbors.
        collections: Override which collections to query for knowledge recall.
                     If None, uses default [LEARNINGS, MEMORIES, EPISODES].

    Returns dict with keys: goals_text, context, knowledge_hints, working_memory
    All values are strings safe for prompt injection.
    """
    from brain import get_brain, LEARNINGS, CONTEXT, MEMORIES, EPISODES

    result = {
        "goals_text": "",
        "context": "",
        "knowledge_hints": "",
        "working_memory": "",
        "brain_timings": {},
    }

    try:
        b = get_brain()
    except Exception:
        return result

    t0 = time.monotonic()

    # 1. Goals
    try:
        goals = b.get_goals()
        if goals:
            lines = []
            for g in goals[:n_goals]:
                meta = g.get("metadata", {})
                name = meta.get("goal", g.get("document", "")[:60])
                progress = meta.get("progress", 0)
                lines.append(f"  ({progress}%) {name}")
            result["goals_text"] = "\n".join(lines)
    except Exception:
        pass
    result["brain_timings"]["goals"] = round(time.monotonic() - t0, 3)

    # 2. Current context
    t1 = time.monotonic()
    try:
        ctx = b.get_context()
        result["context"] = ctx if ctx != "idle" else ""
    except Exception:
        pass
    result["brain_timings"]["context"] = round(time.monotonic() - t1, 3)

    # 3. Relevant knowledge (multi-collection: learnings + memories + episodes)
    t2 = time.monotonic()
    try:
        _recall_collections = collections if collections else [LEARNINGS, MEMORIES, EPISODES]
        knowledge = b.recall(
            task_text,
            collections=_recall_collections,
            n=n_knowledge,
            min_importance=0.3,
            attention_boost=True,
            caller="brain_bridge_preflight",
            graph_expand=graph_expand,
        )
        # MMR reranking: balance relevance with diversity to reduce redundant context
        # Lambda adapts per task category: code=0.7, research=0.4, maintenance=0.6
        if knowledge and len(knowledge) > 1:
            try:
                from context_compressor import mmr_rerank
                try:
                    from clarvis.context.adaptive_mmr import get_adaptive_lambda
                    _lambda = get_adaptive_lambda(task_text)
                except ImportError:
                    _lambda = 0.5
                knowledge = mmr_rerank(knowledge, task_text, lambda_param=_lambda)
            except Exception:
                pass  # fall through to unranked results
        # Contextual enrichment: add collection + metadata prefix (pilot collections)
        if knowledge:
            try:
                from clarvis.brain.search import contextual_enrich
                knowledge = contextual_enrich(knowledge)
            except ImportError:
                pass  # graceful fallback — no enrichment
        result["raw_results"] = knowledge or []
        if knowledge:
            hints = []
            actr_scores = []
            for mem in knowledge:
                # Skip memories below ACT-R retrieval threshold
                score = mem.get("_actr_score")
                if _HAS_ACTR and score is not None:
                    actr_scores.append(score)

                # Use contextually-enriched document when available
                doc = mem.get("_contextual_document", mem.get("document", ""))[:160]
                src = mem.get("metadata", {}).get("source", "")
                tags = mem.get("metadata", {}).get("tags", "")
                col = mem.get("collection", "")
                # Prefix by source type
                if "episode" in col:
                    prefix = "[EPISODE]"
                elif "dream" in str(tags):
                    prefix = "[DREAM]"
                elif "research" in str(src) or "research" in str(tags):
                    prefix = "[RESEARCH]"
                elif "synthesis" in str(src):
                    prefix = "[SYNTHESIS]"
                elif "outcome" in str(src) or "postflight" in str(src):
                    prefix = "[OUTCOME]"
                else:
                    prefix = "[LEARNING]"
                # Append ACT-R score when available
                score_tag = f" a={score:.2f}" if score is not None else ""
                hints.append(f"  {prefix}{score_tag} {doc}")
            result["knowledge_hints"] = "\n".join(hints)
            # Surface ACT-R activation stats for diagnostics
            if actr_scores:
                result["brain_timings"]["actr_mean"] = round(sum(actr_scores) / len(actr_scores), 3)
                result["brain_timings"]["actr_max"] = round(max(actr_scores), 3)
    except Exception:
        pass
    result["brain_timings"]["knowledge"] = round(time.monotonic() - t2, 3)

    # 4. Working memory: recent context entries (last 3)
    t3 = time.monotonic()
    try:
        ctx_mems = b.get(CONTEXT, n=5)
        if ctx_mems:
            wm_lines = []
            for m in ctx_mems[:3]:
                doc = m.get("document", "")[:100]
                if doc and doc != "idle":
                    wm_lines.append(f"  {doc}")
            result["working_memory"] = "\n".join(wm_lines)
    except Exception:
        pass
    result["brain_timings"]["working_memory"] = round(time.monotonic() - t3, 3)

    return result


def brain_record_outcome(task_text, status, output_text="", duration_s=0):
    """Store task outcome in brain after execution.

    Stores a structured learning in clarvis-learnings so future tasks
    can benefit from past successes and failures.

    Args:
        task_text: The task that was executed
        status: "success", "failure", or "timeout"
        output_text: Executor output (will be truncated)
        duration_s: How long the task took
    """
    import re
    from brain import get_brain, LEARNINGS

    try:
        b = get_brain()
    except Exception:
        return None

    # Build a concise outcome record
    if status == "success":
        # Extract summary from output (last meaningful line)
        summary = ""
        if output_text:
            # Look for the summary line (often the last non-empty line)
            lines = [l.strip() for l in output_text.strip().split("\n") if l.strip()]
            if lines:
                summary = lines[-1][:150]
        text = f"SUCCESS ({duration_s}s): {task_text[:120]}"
        if summary:
            text += f" — {summary}"
        importance = 0.7
        tags = ["outcome", "success"]
    elif status == "timeout":
        text = f"TIMEOUT ({duration_s}s): {task_text[:120]} — exceeded time budget"
        importance = 0.75
        tags = ["outcome", "timeout"]
    else:
        # Failure — extract error
        error_snippet = ""
        if output_text:
            error_snippet = output_text[-200:]
            error_snippet = re.sub(r'[^a-zA-Z0-9 _.,:;=+\-/()@#%\n]', '', error_snippet)[:150]
        text = f"FAILURE: {task_text[:120]}"
        if error_snippet:
            text += f" — {error_snippet}"
        importance = 0.8
        tags = ["outcome", "failure"]

    mem_id = b.store(
        text,
        collection=LEARNINGS,
        importance=importance,
        tags=tags,
        source="brain_bridge_postflight",
    )
    return mem_id


def brain_update_context(task_text, status):
    """Update brain's working context after task execution.

    Sets the brain's context to reflect what just happened,
    so the next preflight can see what the last heartbeat did.
    """
    from brain import get_brain

    try:
        b = get_brain()
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        context = f"[{timestamp}] Last task ({status}): {task_text[:120]}"
        b.set_context(context)
    except Exception:
        pass


if __name__ == "__main__":
    """Quick self-test."""
    print("=== Brain Bridge Self-Test ===")

    # Test preflight
    t0 = time.monotonic()
    ctx = brain_preflight_context("Wire brain to subconscious")
    elapsed = time.monotonic() - t0
    print(f"\nPreflight context ({elapsed:.2f}s):")
    print(f"  Goals: {len(ctx['goals_text'])} bytes")
    print(f"  Context: {ctx['context'][:80] if ctx['context'] else '(idle)'}")
    print(f"  Knowledge: {len(ctx['knowledge_hints'])} bytes")
    print(f"  Working memory: {len(ctx['working_memory'])} bytes")
    print(f"  Timings: {ctx['brain_timings']}")

    # Test outcome recording
    mem_id = brain_record_outcome(
        "Self-test of brain_bridge.py",
        "success",
        "All tests passed",
        duration_s=1,
    )
    print(f"\nRecorded outcome: {mem_id}")

    # Test context update
    brain_update_context("Self-test of brain_bridge.py", "success")
    print("Context updated.")

    print("\n=== Brain Bridge OK ===")
