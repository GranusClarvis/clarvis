#!/usr/bin/env python3
"""
Context Compressor — Orchestration layer over clarvis.context.compressor

Architecture:
  Spine (clarvis.context.compressor) — canonical, stateless compression primitives
      (TF-IDF, MMR, graduated compaction, basic queue/episode compression)
  This file (scripts/) — orchestration layer that imports spine primitives and adds:
      - Section-level MD5 caching with TTL (saves ~30-40% brief generation time)
      - Health data compression (multi-line → compact key=value)
      - Decision context building (success criteria, failure patterns, wire guidance)
      - Quality-optimized brief assembly (primacy/recency positioning, tiered budgets)
      - Queue archival and log rotation (GC)
  This layering is intentional — scripts/ orchestrators are NOT migration candidates.
  See QUEUE.md [CONTEXT_COMPRESSOR_FULL_MIGRATION] for the architectural decision.

Public API:
  compress_queue()          — strips completed tasks, keeps pending + last N completions
  compress_health()         — summarizes health data into compact format
  compress_episodes()       — trims episodic recall to essentials
  generate_tiered_brief()   — quality-optimized context brief for Claude Code prompts
  archive_completed()       — move old completed tasks to archive
  gc()                      — full garbage collection (archive + log rotation)

Usage:
    from context_compressor import compress_queue, compress_health, generate_tiered_brief

    # CLI
    python3 context_compressor.py queue          # compressed queue
    python3 context_compressor.py health         # compressed health summary
    python3 context_compressor.py brief          # full context brief for prompts
    python3 context_compressor.py brief --file   # write to data/context_brief.txt
"""

import gzip
import glob
import json
import math
import os
import re
import shutil
import sys
import hashlib
import time as _time
from collections import Counter
from datetime import datetime, timezone, timedelta


QUEUE_FILE = os.path.join(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")), "memory/evolution/QUEUE.md")
QUEUE_ARCHIVE = os.path.join(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")), "memory/evolution/QUEUE_ARCHIVE.md")
BRIEF_FILE = os.path.join(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")), "data/context_brief.txt")
CAPABILITY_HISTORY = os.path.join(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")), "data/capability_history.json")
PHI_HISTORY = os.path.join(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")), "data/phi_history.json")
MEMORY_DIR = os.path.join(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")), "memory")
CRON_LOG_DIR = os.path.join(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")), "memory/cron")
LOG_MAX_BYTES = 100_000  # 100KB cap per cron log


# === SECTION-LEVEL CACHING ===
#
# Inspired by Claude Code harness `systemPromptSections.ts` and its
# `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` concept: the system prompt is split into
# stable sections (identity, capabilities, goals, scores) that change rarely
# and dynamic sections (working memory, episodes, attention spotlight) that
# change every heartbeat.
#
# Stable sections are memoized with a content-hash of their source data.
# When the source hasn't changed, the cached result is returned instantly,
# saving both compute and ~200-400ms of file I/O + parsing per heartbeat.
#
# Cache invalidation: hash-based (content change) + TTL (max 300s staleness).
#
# Estimated savings: ~30-40% of brief generation time (scores + queue + brain
# stats are the most expensive stable sections at ~150ms combined).

_SECTION_CACHE = {}  # {section_name: {"hash": str, "result": Any, "ts": float}}
_SECTION_CACHE_TTL = 300  # seconds — max staleness for stable sections


def _section_cache_key(section_name, *source_data):
    """Compute a fast content hash for cache invalidation."""
    h = hashlib.md5(section_name.encode(), usedforsecurity=False)
    for item in source_data:
        if item is None:
            h.update(b"\x00")
        elif isinstance(item, str):
            h.update(item.encode("utf-8", errors="replace"))
        else:
            h.update(str(item).encode())
    return h.hexdigest()


def _section_cache_get(section_name, *source_data):
    """Return cached result if source data hasn't changed and TTL hasn't expired."""
    entry = _SECTION_CACHE.get(section_name)
    if entry is None:
        return None
    if _time.monotonic() - entry["ts"] > _SECTION_CACHE_TTL:
        return None  # expired
    key = _section_cache_key(section_name, *source_data)
    if entry["hash"] != key:
        return None  # source changed
    return entry["result"]


def _section_cache_put(section_name, result, *source_data):
    """Store a section result in cache."""
    key = _section_cache_key(section_name, *source_data)
    _SECTION_CACHE[section_name] = {
        "hash": key,
        "result": result,
        "ts": _time.monotonic(),
    }
    return result


def section_cache_stats():
    """Return cache hit/miss stats for monitoring. CLI: `context_compressor.py cache-stats`."""
    now = _time.monotonic()
    entries = []
    for name, entry in _SECTION_CACHE.items():
        age = round(now - entry["ts"], 1)
        expired = age > _SECTION_CACHE_TTL
        entries.append({"section": name, "age_s": age, "expired": expired})
    return {"entries": len(entries), "sections": entries}


def section_cache_clear():
    """Clear all cached sections."""
    _SECTION_CACHE.clear()


# --- Shared primitives from canonical spine module ---
# Constants and helpers are defined once in clarvis.context.compressor;
# this file adds caching, health compression, and advanced brief features.
from clarvis.context.compressor import (
    _STOPWORDS, _CATEGORY_RATIOS, _CATEGORY_PATTERNS,
    _classify_task_category, _extract_task_keywords,
    _tokenize, _jaccard_similarity, _split_sentences,
    mmr_rerank, tfidf_extract,
)


def compress_text(text, ratio=0.25, task_context=None):
    # NOTE: default ratio=0.25 here vs 0.30 in clarvis.context.compressor —
    # scripts callers expect the tighter default, so this wrapper is kept.
    """Public API: compress arbitrary text via extractive TF-IDF + MMR + dedup.

    Stage 1: TF-IDF sentence selection (with keyword-pinning if task_context given)
    Stage 2: MMR reranking to reduce semantic redundancy
    Stage 3: core-string dedup to catch residual near-duplicates

    Args:
        text: Input text to compress.
        ratio: Base extraction ratio (overridden by category ratio if task_context given).
        task_context: Optional task description string. When provided, enables:
            - Per-category ratio (code=0.35, maintenance=0.30, research=0.30)
            - Keyword-pinning: task-critical terms boost sentence selection scores

    Returns (compressed_text, compression_stats) tuple.
    """
    if not text or len(text) < 150:
        return text, {"input_chars": len(text or ""), "output_chars": len(text or ""), "ratio": 1.0}

    input_chars = len(text)

    # Determine ratio and pinned keywords from task context
    pinned_keywords = set()
    effective_ratio = ratio
    category = "default"
    if task_context:
        category = _classify_task_category(task_context)
        effective_ratio = _CATEGORY_RATIOS.get(category, ratio)
        pinned_keywords = _extract_task_keywords(task_context)

    # Stage 1: Extractive — select key sentences (with keyword pinning)
    extracted = tfidf_extract(text, ratio=effective_ratio, pinned_keywords=pinned_keywords or None)

    # Stage 2: MMR post-pass over extracted sentences to reduce redundancy
    lines = [line.strip() for line in extracted.split('\n') if line.strip()]
    if len(lines) > 1:
        mmr_items = [{"document": line, "distance": 0.0} for line in lines]
        lines = [item["document"] for item in mmr_rerank(mmr_items, text, lambda_param=0.35, n=len(lines))]

    # Stage 3: Light abstractive — deduplicate near-identical lines
    seen_cores = set()
    deduped = []
    for line in lines:
        core = re.sub(r'[^a-z0-9 ]', '', line.lower().strip())[:50]
        if core in seen_cores:
            continue
        seen_cores.add(core)
        deduped.append(line)

    compressed = '\n'.join(deduped)
    output_chars = len(compressed)
    actual_ratio = output_chars / max(1, input_chars)

    return compressed, {
        "input_chars": input_chars,
        "output_chars": output_chars,
        "ratio": round(actual_ratio, 3),
        "sentences_in": len(_split_sentences(text)),
        "sentences_out": len(deduped),
        "mmr_applied": len(lines) > 1,
        "task_category": category,
        "pinned_keywords_count": len(pinned_keywords),
    }


def _parse_queue_items(lines):
    """Parse QUEUE.md lines into pending and completed task lists."""
    pending_tasks = []
    recent_completed = []
    current_section = ""

    for line in lines:
        stripped = line.strip()

        if stripped.startswith('## '):
            current_section = stripped
            continue
        if '## Completed' in current_section:
            continue

        match_pending = re.match(r'^- \[ \] (.+)$', stripped)
        if match_pending:
            task_text = match_pending.group(1)
            core = re.split(r'\s*[\(—]', task_text, 1)[0].strip()
            if len(core) < 20:
                core = task_text[:150]
            pending_tasks.append({"section": current_section, "task": core})
            continue

        match_done = re.match(r'^- \[x\] (.+)$', stripped)
        if match_done:
            task_text = match_done.group(1)
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', task_text)
            date_str = date_match.group(1) if date_match else "unknown"
            core = re.split(r'\s*[\(—]', task_text, 1)[0].strip()
            if len(core) < 15:
                core = task_text[:100]
            recent_completed.append({"section": current_section, "task": core, "date": date_str})

    return pending_tasks, recent_completed


def _format_compressed_queue(pending_tasks, recent_completed):
    """Format parsed queue items into compressed output string."""
    output = ["=== EVOLUTION QUEUE (compressed) ===\n"]

    pending_by_section = {}
    for t in pending_tasks:
        pending_by_section.setdefault(t["section"], []).append(t["task"])

    if pending_by_section:
        output.append(f"PENDING ({len(pending_tasks)} tasks):")
        for section, tasks in pending_by_section.items():
            output.append(f"\n{section}")
            for task in tasks:
                output.append(f"  - [ ] {task}")
    else:
        output.append("PENDING: 0 tasks (queue empty)")

    if recent_completed:
        output.append(f"\nRECENT COMPLETIONS (last {len(recent_completed)}):")
        for t in recent_completed:
            output.append(f"  [x] ({t['date']}) {t['task'][:80]}")

    output.append(f"\nTOTAL: {len(pending_tasks)} pending, {len(recent_completed)} recently completed shown (older history stripped for token efficiency)")
    return "\n".join(output)


def compress_queue(queue_file=QUEUE_FILE, max_recent_completed=5):
    """Compress QUEUE.md: pending tasks in full, last N completed as 1-liners, rest stripped.

    Returns a string suitable for injection into Claude Code prompts.
    Typical reduction: 48KB → 3-5KB (85-90% token savings).

    Cached: invalidated when QUEUE.md mtime changes.
    """
    if not os.path.exists(queue_file):
        return "No evolution queue found."

    q_mtime = str(os.path.getmtime(queue_file))
    cached = _section_cache_get("queue", q_mtime, str(max_recent_completed))
    if cached is not None:
        return cached

    with open(queue_file, 'r') as f:
        lines = f.readlines()

    pending_tasks, recent_completed = _parse_queue_items(lines)

    recent_completed.sort(
        key=lambda x: x["date"] if x["date"] != "unknown" else "0000", reverse=True)
    recent_completed = recent_completed[:max_recent_completed]

    result = _format_compressed_queue(pending_tasks, recent_completed)
    return _section_cache_put("queue", result, q_mtime, str(max_recent_completed))


def _extract_calibration(calibration_output):
    """Extract Brier score and accuracy from calibration output."""
    brier_match = re.search(r'[Bb]rier[:\s=]*([0-9.]+)', calibration_output)
    accuracy_match = re.search(r'(\d+)/(\d+)\s*correct|accuracy[:\s=]*([0-9.]+)', calibration_output)
    brier = brier_match.group(1) if brier_match else "?"
    if accuracy_match:
        accuracy = f"{accuracy_match.group(1)}/{accuracy_match.group(2)}" if accuracy_match.group(1) else accuracy_match.group(3)
    else:
        accuracy = "?"
    return f"Calibration: Brier={brier}, accuracy={accuracy}"


def _extract_capabilities(capability_output):
    """Extract capability scores into summary lines."""
    scores = re.findall(r'(\w[\w_]+)[:=]\s*([0-9.]+)', capability_output)
    if not scores:
        return []
    score_pairs = [(name, float(val)) for name, val in scores if 0 <= float(val) <= 1.0]
    if not score_pairs:
        return []
    score_pairs.sort(key=lambda x: x[1])
    worst = score_pairs[0]
    avg = sum(v for _, v in score_pairs) / len(score_pairs)
    scores_str = ", ".join(f"{n}={v:.2f}" for n, v in score_pairs)
    return [
        f"Capabilities: avg={avg:.2f}, worst={worst[0]}={worst[1]:.2f}, n={len(score_pairs)}",
        f"  Scores: {scores_str}",
    ]


def compress_health(
    calibration_output="",
    phi_output="",
    capability_output="",
    retrieval_output="",
    episode_output="",
    goal_output="",
    param_output="",
    domain_output="",
):
    """Compress multi-line health data into compact key=value summary.

    Typical reduction: 8KB → 1KB (87% token savings).
    """
    summary = ["=== SYSTEM HEALTH (compressed) ==="]

    if calibration_output:
        summary.append(_extract_calibration(calibration_output))

    if phi_output:
        phi_match = re.search(r'[Pp]hi[:\s=]*([0-9.]+)', phi_output)
        trend_match = re.search(r'trend[:\s=]*([a-z_]+|[↑↓→]+)', phi_output, re.IGNORECASE)
        summary.append(f"Phi={phi_match.group(1) if phi_match else '?'} (trend: {trend_match.group(1) if trend_match else 'stable'})")

    if capability_output:
        summary.extend(_extract_capabilities(capability_output))

    if retrieval_output:
        hit_match = re.search(r'hit[_ ]rate[:\s=]*([0-9.]+)%?', retrieval_output, re.IGNORECASE)
        health_match = re.search(r'(HEALTHY|DEGRADED|CRITICAL)', retrieval_output)
        summary.append(f"Retrieval: hit_rate={hit_match.group(1) if hit_match else '?'}%, status={health_match.group(1) if health_match else '?'}")

    if episode_output:
        count_match = re.search(r'(\d+)\s*episodes?', episode_output)
        success_match = re.search(r'success[:\s=]*([0-9.]+)%?', episode_output, re.IGNORECASE)
        summary.append(f"Episodes: n={count_match.group(1) if count_match else '?'}, success_rate={success_match.group(1) if success_match else '?'}%")

    if goal_output:
        stalled_match = re.search(r'(\d+)\s*stalled', goal_output, re.IGNORECASE)
        tasks_match = re.search(r'(\d+)\s*tasks?\s*(generated|added)', goal_output, re.IGNORECASE)
        summary.append(f"Goals: {stalled_match.group(1) if stalled_match else '0'} stalled, {tasks_match.group(1) if tasks_match else '0'} remediation tasks generated")

    if not any(line for line in summary if not line.startswith("===")):
        summary.append("No health data available this cycle.")

    return "\n".join(summary)


def compress_episodes(similar_episodes_text, failure_episodes_text):
    """Compress episodic memory hints for task prompts.

    Strips verbose episode details, keeps only outcome + key lesson.
    """
    lines = []
    if similar_episodes_text:
        # Each episode line typically has format: [outcome] (act=X.XX) Task: ...
        for line in similar_episodes_text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            # Extract outcome and task name, skip activation details
            outcome_match = re.match(r'\[(\w+)\]\s*\(act=[0-9.]+\)\s*(?:Task:\s*)?(.+)', line)
            if outcome_match:
                outcome = outcome_match.group(1)
                task = outcome_match.group(2)[:80]
                lines.append(f"  [{outcome}] {task}")
            else:
                lines.append(f"  {line[:100]}")

    if failure_episodes_text:
        for line in failure_episodes_text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            # Extract just the error pattern, not full text
            error_match = re.search(r'Error:\s*\[?(\w+)\]?\s*(.+)', line)
            if error_match:
                lines.append(f"  AVOID: [{error_match.group(1)}] {error_match.group(2)[:80]}")
            elif len(line) > 10:
                lines.append(f"  AVOID: {line[:100]}")

    if lines:
        return "EPISODIC HINTS:\n" + "\n".join(lines)
    return ""


def get_latest_scores():
    """Read latest capability scores and Phi from history files.

    Returns compact dict for embedding in prompts without needing
    to re-run assessment scripts.

    Cached: invalidated when capability_history.json or phi_history.json change (by mtime).
    """
    # Cache key: mtimes of source files (stable between heartbeats)
    cap_mtime = os.path.getmtime(CAPABILITY_HISTORY) if os.path.exists(CAPABILITY_HISTORY) else 0
    phi_mtime = os.path.getmtime(PHI_HISTORY) if os.path.exists(PHI_HISTORY) else 0
    cached = _section_cache_get("scores", str(cap_mtime), str(phi_mtime))
    if cached is not None:
        return cached

    scores = {}

    # Capability scores
    if os.path.exists(CAPABILITY_HISTORY):
        try:
            with open(CAPABILITY_HISTORY, 'r') as f:
                history = json.load(f)
            if history:
                latest = history[-1]
                scores["capabilities"] = {
                    k: round(v, 2) for k, v in latest.get("scores", {}).items()
                    if isinstance(v, (int, float))
                }
                scores["capability_avg"] = round(
                    sum(scores["capabilities"].values()) / max(1, len(scores["capabilities"])),
                    2
                )
        except Exception:
            pass

    # Phi
    if os.path.exists(PHI_HISTORY):
        try:
            with open(PHI_HISTORY, 'r') as f:
                phi_hist = json.load(f)
            if phi_hist:
                scores["phi"] = round(phi_hist[-1].get("phi", 0), 3)
        except Exception:
            pass

    return _section_cache_put("scores", scores, str(cap_mtime), str(phi_mtime))


def generate_context_brief(queue_file=QUEUE_FILE):
    """Generate a full compressed context brief for Claude Code prompts.

    Combines compressed queue + latest scores into a single compact payload.
    Designed to replace "Read memory/evolution/QUEUE.md for full context."

    Returns string (~1-3KB instead of ~50KB).
    """
    brief_parts = []

    # Compressed queue
    brief_parts.append(compress_queue(queue_file))

    # Latest scores (from files, no subprocess needed)
    scores = get_latest_scores()
    if scores:
        brief_parts.append("\n=== LATEST METRICS ===")
        if "capabilities" in scores:
            caps = scores["capabilities"]
            worst_k = min(caps, key=caps.get) if caps else "?"
            worst_v = caps.get(worst_k, "?") if caps else "?"
            brief_parts.append(f"Capability avg={scores.get('capability_avg', '?')}, worst={worst_k}={worst_v}")
            brief_parts.append(f"  All: {', '.join(f'{k}={v}' for k, v in sorted(caps.items(), key=lambda x: x[1]))}")
        if "phi" in scores:
            brief_parts.append(f"Phi={scores['phi']}")

    # Current brain stats (lightweight)
    try:
        from brain import brain
        stats = brain.stats()
        brief_parts.append(f"Brain: {stats['total_memories']} memories, {stats['graph_edges']} edges")
    except Exception:
        pass

    return "\n".join(brief_parts)


# === TIERED CONTEXT BRIEF (v2 — quality-optimized) ===
#
# Designed around LLM attention research, not just token budgets.
#
# Key insights applied:
#   1. "Lost in the Middle" (Liu et al. 2023) — LLMs attend most to the
#      BEGINNING and END of context. Critical info must go at those positions.
#   2. Reasoning scaffolding — explicit "think before doing" instructions
#      improve output quality significantly (CoT research).
#   3. Decision context > raw data — Claude Code needs to know WHY and
#      WHAT GOOD LOOKS LIKE, not just metrics.
#   4. Failure patterns > success patterns — knowing what to AVOID
#      prevents the most common quality failures.
#
# Section ordering follows the primacy/recency principle:
#   BEGINNING (high attention): Decision context, failure avoidance, constraints
#   MIDDLE (lower attention):   Metrics, related tasks, completions
#   END (high attention):       Episodic lessons, reasoning instructions
#
# Tiers:
#   minimal  (~200 tokens) — cheap models: task + 1-line context only
#   standard (~600 tokens) — Claude Code: decision context + spotlight + metrics
#   full     (~1000 tokens) — complex reasoning: everything, optimally ordered

# Budget limits per section (approximate token counts)
TIER_BUDGETS = {
    "minimal": {
        "total": 200,
        "decision_context": 0,   # skip
        "spotlight": 0,          # skip
        "related_tasks": 0,      # skip
        "metrics": 0,            # skip
        "completions": 0,        # skip
        "episodes": 0,           # skip
        "reasoning_scaffold": 0, # skip
    },
    "standard": {
        "total": 600,
        "decision_context": 100, # success criteria + constraints
        "spotlight": 80,         # top 3 attention items
        "related_tasks": 60,     # 1-2 related pending tasks
        "metrics": 40,           # phi + worst capability only
        "completions": 40,       # last 2 completions
        "episodes": 60,          # failure patterns (was 0 — quality loss)
        "reasoning_scaffold": 40,# think-then-do instruction
    },
    "full": {
        "total": 1000,
        "decision_context": 150, # full success criteria + failure avoidance
        "spotlight": 120,        # top 5 attention items
        "related_tasks": 100,    # 2-3 related pending tasks
        "metrics": 80,           # all capabilities + phi
        "completions": 60,       # last 3 completions
        "episodes": 120,         # full episodic lessons with root causes
        "reasoning_scaffold": 60,# detailed reasoning instructions
    },
}


def _build_decision_context(current_task, tier="standard"):
    """Build a decision-context block that tells the executor what GOOD looks like.

    Extracts:
      - Inferred success criteria from the task text
      - Relevant failure patterns from recent episodes
      - Key constraints (coding standards, system patterns)

    This is the highest-value context for quality: it shapes HOW Claude Code
    approaches the task, not just WHAT the task is.
    """
    parts = []

    # --- Success criteria: parse actionable targets from task text ---
    targets = []
    # Look for explicit targets like "Target: 0.55+", "> 60%", "above 70%"
    for m in re.finditer(r'(?:target|goal|above|>|improve.*to)\s*[:=]?\s*([0-9.]+[%+]?)', current_task, re.IGNORECASE):
        targets.append(m.group(0).strip())
    # Look for explicit action verbs that define "done"
    done_verbs = re.findall(r'(?:verify|ensure|confirm|test|check|wire|implement|fix|build|add|create)\s+[^,.]+', current_task, re.IGNORECASE)
    if done_verbs:
        targets.extend(v.strip()[:60] for v in done_verbs[:3])

    if targets:
        parts.append("SUCCESS CRITERIA:")
        for t in targets[:4]:
            parts.append(f"  - {t}")

    # --- Wire task guidance (wire strategy has 30% success rate) ---
    wire_guidance = _build_wire_guidance(current_task)
    if wire_guidance:
        parts.append(wire_guidance)

    # --- Failure patterns from recent episodes ---
    failure_patterns = _get_failure_patterns(current_task, n=3 if tier == "full" else 2)
    if failure_patterns:
        parts.append("AVOID THESE FAILURE PATTERNS:")
        parts.extend(failure_patterns)

    # --- Meta-gradient RL recommendations ---
    try:
        from meta_gradient_rl import load_meta_params
        mg_params = load_meta_params()
        explore = mg_params.get("exploration_rate", 0.3)
        weights = mg_params.get("strategy_weights", {})
        best_strategy = max(weights, key=weights.get) if weights else None
        if best_strategy and weights[best_strategy] > 1.2:
            parts.append(f"META-GRADIENT: Prefer '{best_strategy}' strategy (weight={weights[best_strategy]:.2f}), explore={explore:.0%}")
    except Exception:
        pass

    # --- Constraints: common quality issues from code_quality scores ---
    scores = get_latest_scores()
    if scores:
        caps = scores.get("capabilities", {})
        # Flag capabilities below 0.5 that are relevant to this task
        weak_caps = [(k, v) for k, v in caps.items() if v < 0.5]
        if weak_caps:
            weak_names = ", ".join(f"{k}={v}" for k, v in sorted(weak_caps, key=lambda x: x[1]))
            parts.append(f"WEAK AREAS (be extra careful): {weak_names}")

    return "\n".join(parts)


def _get_failure_patterns(current_task, n=3):
    """Extract failure root causes from episodic memory, not just outcomes.

    Returns list of actionable avoidance strings like:
      '  - AVOID: Nested Claude Code calls cause timeout (seen 2x)'
    """
    patterns = []
    try:
        from clarvis.memory.episodic_memory import EpisodicMemory
        em = EpisodicMemory()

        # Get failures relevant to this task type
        failures = em.recall_failures(n=n * 2)
        if not failures:
            return []

        seen = set()

        for ep in failures:
            task_text = ep.get("task", "")
            outcome = ep.get("outcome", "failure")
            # Extract the error/lesson if stored
            error = ep.get("error", "") or ep.get("lesson", "") or ""
            core = error[:60] if error else task_text[:60]

            # Dedup by core
            dedup_key = core[:30].lower()
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            if error:
                patterns.append(f"  - AVOID: {error[:80]}")
            elif task_text:
                patterns.append(f"  - [{outcome}] {task_text[:60]}")

            if len(patterns) >= n:
                break

    except Exception:
        pass

    return patterns


def _detect_wire_task(task_text):
    """Detect if a task is a 'wire' strategy task (integration/hooking).

    Wire tasks have ~42% success rate (vs 55% for build tasks) because they
    require multi-file integration across bash/Python boundaries. Returns
    (is_wire, source_script, target_script) tuple.
    """
    task_lower = task_text.lower()
    wire_verbs = ["wire", "connect", "integrate", "hook", "link", "plug", "add.*to cron", "add.*to heartbeat"]
    if not any(re.search(v, task_lower) for v in wire_verbs):
        return False, None, None

    # Extract source (what to wire) and target (where to wire it)
    source = None
    target = None
    # Pattern 1: "Wire script.py into target.sh"
    m = re.search(r'(?:wire|integrate|hook|connect|link|plug)\s+(\S+\.(?:py|sh))\s+(?:into|to|with|in)\s+(\S+\.(?:py|sh))', task_lower)
    if m:
        source = m.group(1)
        target = m.group(2)
    else:
        # Pattern 2: "Add script.py to cron_evening.sh" / "Add X to heartbeat"
        m = re.search(r'add\s+(\S+\.(?:py|sh))\s+(?:into|to|in)\s+(\S+\.(?:py|sh))', task_lower)
        if m:
            source = m.group(1)
            target = m.group(2)
        else:
            # Pattern 3: "Wire X into Y" where X/Y are descriptive names
            m = re.search(r'(?:wire|integrate|hook|connect|link|plug)\s+(.+?)\s+(?:into|to|with|in)\s+(.+?)(?:\s*[-—,.]|$)', task_lower)
            if m:
                source = m.group(1).strip()
                target = m.group(2).strip()

    return True, source, target


_WIRE_SCRIPTS = os.path.join(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")), "scripts")

_WIRE_KNOWN_TARGETS = {
    "cron_reflection.sh": {
        "path": f"{_WIRE_SCRIPTS}/cron_reflection.sh",
        "structure": "Steps 0.5-7, each runs a python3 script. Add new steps between existing ones.",
        "pattern": '# Step N: Description\necho "[$(date)] Step N: ..." >> "$LOGFILE"\npython3 {}/script.py >> "$LOGFILE" 2>&1 || true'.format(_WIRE_SCRIPTS),
        "insert_hint": "Add between the last numbered step and the digest/cleanup section.",
    },
    "cron_autonomous.sh": {
        "path": f"{_WIRE_SCRIPTS}/cron_autonomous.sh",
        "structure": "3 phases: preflight → execution → postflight. Do NOT edit this bash script directly.",
        "pattern": "Modify heartbeat_preflight.py (add import + call) or heartbeat_postflight.py instead.",
        "insert_hint": "Wire into preflight (before task) or postflight (after task), not the bash orchestrator.",
    },
    "cron_evening.sh": {
        "path": f"{_WIRE_SCRIPTS}/cron_evening.sh",
        "structure": "Sequential sections: PHI_METRIC → CODE_QUALITY → CAPABILITY_ASSESSMENT → RETRIEVAL → SELF_REPORT → DASHBOARD → Claude Code audit → DIGEST.",
        "pattern": '# === SECTION_NAME ===\necho "[$(date)] Section ..." >> "$LOGFILE"\nOUTPUT=$(python3 {}/script.py 2>&1) || true\necho "$OUTPUT" >> "$LOGFILE"'.format(_WIRE_SCRIPTS),
        "insert_hint": "Add new section BEFORE the '# === DIGEST' section (last step).",
    },
    "cron_morning.sh": {
        "path": f"{_WIRE_SCRIPTS}/cron_morning.sh",
        "structure": "Spawns Claude Code with day planning prompt. Pre-run metrics, then Claude Code execution.",
        "pattern": "Add metric collection BEFORE the Claude Code spawn, or post-processing AFTER.",
        "insert_hint": "New metric calls go between 'Morning routine started' and the Claude Code prompt.",
    },
    "cron_evolution.sh": {
        "path": f"{_WIRE_SCRIPTS}/cron_evolution.sh",
        "structure": "Batched preflight (evolution_preflight.py) → Claude Code deep analysis → digest.",
        "pattern": "For new metrics: add to evolution_preflight.py, NOT to this bash script.",
        "insert_hint": "Prefer editing evolution_preflight.py over this orchestrator.",
    },
    "heartbeat_preflight.py": {
        "path": f"{_WIRE_SCRIPTS}/heartbeat_preflight.py",
        "structure": "Sections 1-10 in run_preflight(). Each section has timing + try/except.",
        "pattern": "try:\n    from module import func\nexcept ImportError:\n    func = None\n# In run_preflight(): if func: try: result = func(...) except: pass",
        "insert_hint": "Import at file top with try/except. Call in run_preflight() inside try/except with timing.",
    },
    "heartbeat_postflight.py": {
        "path": f"{_WIRE_SCRIPTS}/heartbeat_postflight.py",
        "structure": "Post-execution steps in run_postflight(). Same pattern as preflight.",
        "pattern": "try:\n    from module import func\nexcept ImportError:\n    func = None\n# In run_postflight(): if func: try: result = func(...) except: pass",
        "insert_hint": "Import at top with try/except. Call in run_postflight() with timing.",
    },
    "cron_strategic_audit.sh": {
        "path": f"{_WIRE_SCRIPTS}/cron_strategic_audit.sh",
        "structure": "Runs Wed+Sat at 15:00. Spawns Claude Code for strategic analysis.",
        "pattern": "Add metric collection before or post-processing after the Claude Code spawn.",
        "insert_hint": "New analysis steps go before the main Claude Code invocation.",
    },
}

_WIRE_SUB_STEPS = [
    "  REQUIRED SUB-STEPS (do each one explicitly, ~3min per step):",
    "    1. READ the target file — find the exact insertion point (line number). Output: 'Inserting at line N, after <context>'",
    "    2. READ the source script — find the exact function/class to import and its call signature. Output: 'Will import <func> from <module>, signature: <sig>'",
    "    3. ADD the import at the top of target (with try/except fallback for resilience)",
    "    4. ADD the call at the identified insertion point (with try/except + timing if target uses timing)",
    "    5. TEST: run `python3 -c 'import <module>'` or `bash -n <script>.sh` to verify no syntax errors",
    "    6. VERIFY: run the target script in test mode (or grep for your added lines) to confirm integration",
    "  AVOID: Do NOT explore the codebase broadly. The target and source are given — read only those two files.",
    "  AVOID: Do NOT refactor or improve the source script. Only wire it in.",
]


def _resolve_wire_target(target):
    """Resolve target name to path and guidance. Returns (path, guidance_lines)."""
    if not target:
        return None, []
    for known_name, info in _WIRE_KNOWN_TARGETS.items():
        if known_name in target:
            return info["path"], [
                f"  TARGET: {info['path']}",
                f"  STRUCTURE: {info['structure']}",
                f"  PATTERN: {info['pattern']}",
                f"  INSERT_HINT: {info['insert_hint']}",
            ]
    # Auto-detect from filesystem
    import glob as _glob
    candidates = _glob.glob(f"{_WIRE_SCRIPTS}/{target}") + _glob.glob(f"{_WIRE_SCRIPTS}/*{target}*")
    if candidates:
        return candidates[0], [f"  TARGET: {candidates[0]} (auto-detected, read carefully before editing)"]
    return None, []


def _build_target_preview(target_path):
    """Build a file preview snippet for wire guidance. Returns lines or []."""
    if not target_path or not os.path.isfile(target_path):
        return []
    try:
        with open(target_path) as f:
            lines = f.readlines()
        snippet_lines = lines[:10] + ["    ...\n"] + lines[-10:] if len(lines) > 30 else lines
        snippet = "".join(f"    {l.rstrip()}\n" for l in snippet_lines[:25])
        return [f"  TARGET PREVIEW ({len(lines)} lines total):", snippet.rstrip()]
    except Exception:
        return []


def _build_wire_guidance(task_text):
    """Generate explicit integration sub-steps for wire tasks."""
    is_wire, source, target = _detect_wire_task(task_text)
    if not is_wire:
        return ""

    parts = ["WIRE TASK GUIDANCE (wire tasks have ~42% success — follow these steps carefully):"]
    target_path, target_lines = _resolve_wire_target(target)
    parts.extend(target_lines)
    parts.extend(_build_target_preview(target_path))
    parts.extend(_WIRE_SUB_STEPS)
    return "\n".join(parts)


def _build_reasoning_scaffold(tier="standard", task_text=""):
    """Generate task-type-specific reasoning scaffolding.

    Delegates to canonical implementation in clarvis.context.assembly.
    Falls back to generic scaffold if import fails.
    """
    try:
        from clarvis.context.assembly import build_reasoning_scaffold
        return build_reasoning_scaffold(tier=tier, task_text=task_text)
    except ImportError:
        pass
    if tier == "full":
        return (
            "APPROACH: Before writing code, briefly analyze:\n"
            "  1. What files need to change and why\n"
            "  2. What could go wrong (check failure patterns above)\n"
            "  3. How to verify success (check criteria above)\n"
            "Then implement, test, and report what you accomplished."
        )
    else:
        return (
            "APPROACH: Analyze before implementing. Check the failure patterns above. "
            "Test your changes. Report what you accomplished."
        )


def _get_workspace_context(current_task, tier="standard"):
    """Get hierarchical context from the cognitive workspace.

    Returns structured context string with active/working/dormant buffers,
    or empty string if workspace is empty (triggering spotlight fallback).
    """
    try:
        from clarvis.memory.cognitive_workspace import workspace
        stats = workspace.stats()
        if stats["total_items"] == 0:
            return ""
        budget = 300 if tier == "full" else 180
        return workspace.get_context(budget=budget, task_query=current_task)
    except Exception:
        return ""


def _get_spotlight_items(n=5, exclude_task=""):
    """Get top-N attention spotlight items as compact strings.

    Deduplicates similar items and strips TASK: prefixes.
    Excludes items that closely match `exclude_task` to avoid echoing the current task.
    """
    try:
        from clarvis.cognition.attention import attention
        attention._load()
        focused = attention.focus()
        items = []
        seen_cores = set()
        exclude_words = set(re.findall(r'[a-z]{3,}', exclude_task.lower())) if exclude_task else set()

        for item in focused[:n * 3]:  # scan wider to fill after dedup
            content = item.get("content", "")
            sal = item.get("salience", 0)

            # Strip common prefixes
            for prefix in ("CURRENT TASK: ", "TASK: ", "OUTCOME: ", "PROCEDURE HIT "):
                if content.startswith(prefix):
                    content = content[len(prefix):]
                    break

            # Deduplicate by core content (first 40 chars)
            core = content[:40].lower()
            if core in seen_cores:
                continue
            seen_cores.add(core)

            # Skip if this item is basically the current task
            if exclude_words:
                item_words = set(re.findall(r'[a-z]{3,}', content.lower()))
                if item_words and len(exclude_words & item_words) / max(1, len(exclude_words)) > 0.5:
                    continue

            items.append(f"  ({sal:.2f}) {content[:80]}")
            if len(items) >= n:
                break

        return items
    except Exception:
        return []


def _find_related_tasks(current_task, queue_file=QUEUE_FILE, max_tasks=3):
    """Find pending tasks related to the current task by word overlap.

    Returns list of task strings, excluding the current task itself.
    """
    if not current_task or not os.path.exists(queue_file):
        return []

    # Tokenize current task into keywords
    task_words = set(re.findall(r'[a-z]{3,}', current_task.lower()))
    if not task_words:
        return []

    with open(queue_file, 'r') as f:
        lines = f.readlines()

    candidates = []
    for line in lines:
        stripped = line.strip()
        match = re.match(r'^- \[ \] (.+)$', stripped)
        if not match:
            continue
        task_text = match.group(1)
        # Skip if this IS the current task (fuzzy match: >60% overlap)
        candidate_words = set(re.findall(r'[a-z]{3,}', task_text.lower()))
        if not candidate_words:
            continue
        overlap = len(task_words & candidate_words) / max(1, len(task_words | candidate_words))
        if overlap > 0.6:
            continue  # too similar — this is probably the current task
        relevance = len(task_words & candidate_words) / max(1, len(candidate_words))
        if relevance > 0.1:
            # Extract core task name
            core = re.split(r'\s*[\(—]', task_text, 1)[0].strip()
            if len(core) < 15:
                core = task_text[:100]
            candidates.append((relevance, core[:80]))

    candidates.sort(reverse=True)
    return [text for _, text in candidates[:max_tasks]]


def _get_recent_completions(queue_file=QUEUE_FILE, n=3):
    """Get the N most recent completed tasks as compact 1-liners."""
    if not os.path.exists(queue_file):
        return []

    with open(queue_file, 'r') as f:
        lines = f.readlines()

    completions = []
    for line in lines:
        stripped = line.strip()
        match = re.match(r'^- \[x\] (.+)$', stripped)
        if not match:
            continue
        task_text = match.group(1)
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', task_text)
        date_str = date_match.group(1) if date_match else ""
        core = re.split(r'\s*[\(—]', task_text, 1)[0].strip()
        if len(core) < 15:
            core = task_text[:80]
        completions.append(f"  [{date_str}] {core[:60]}")

    # Return last N (most recent are usually at the top of the section)
    return completions[:n]


def _prune_knowledge_hints(knowledge_hints, current_task, max_hints=None):
    """Prune low-salience brain hits from knowledge_hints before compression.

    Filters by:
      1. Distance threshold — adaptive cutoff tightens with brain size
      2. Task-relevance — keep hints with word overlap to task
      3. Max count — cap total hints to prevent unbounded growth
      4. Character budget — hard cap on total output bytes

    Returns pruned knowledge_hints string.
    """
    if not knowledge_hints or not knowledge_hints.strip():
        return knowledge_hints

    lines = [l for l in knowledge_hints.split('\n') if l.strip()]
    if len(lines) <= 2:
        return knowledge_hints  # too few to prune

    # Scale max_hints with brain size: larger brain → stricter selection
    if max_hints is None:
        brain_size = _get_brain_size()
        if brain_size > 3000:
            max_hints = min(5, len(lines))
        elif brain_size > 2500:
            max_hints = min(6, len(lines))
        else:
            max_hints = min(8, len(lines))

    task_tokens = set(re.findall(r'[a-z]{3,}', current_task.lower())) - _STOPWORDS

    scored = []
    for line in lines:
        # Parse distance from "d=1.15" pattern
        dm = re.search(r'd=(\d+\.?\d*)', line)
        dist = float(dm.group(1)) if dm else 0.5  # default mid-range

        # Word overlap with task (relevance signal)
        line_tokens = set(re.findall(r'[a-z]{3,}', line.lower())) - _STOPWORDS
        overlap = len(task_tokens & line_tokens) / max(len(task_tokens), 1) if task_tokens else 0

        # Composite score: lower distance + higher overlap = better
        # Distance typically 0.8-1.5; overlap 0-1
        score = (1.5 - min(dist, 1.5)) + overlap * 0.5

        scored.append((score, line))

    # Sort by score descending, keep top max_hints
    scored.sort(key=lambda x: x[0], reverse=True)

    # Adaptive distance cutoff: tightens with brain size to counteract
    # more medium-distance hits from larger collections
    distances = [float(re.search(r'd=(\d+\.?\d*)', l).group(1))
                 for _, l in scored if re.search(r'd=(\d+\.?\d*)', l)]
    if distances:
        median_dist = sorted(distances)[len(distances) // 2]
        brain_size = _get_brain_size()
        # Tighter cutoff for larger brains: 0.3 → 0.2 as brain grows past 2500
        margin = 0.3 if brain_size < 2500 else 0.2
        cutoff = median_dist + margin
    else:
        cutoff = 1.3  # fallback

    kept = []
    total_chars = 0
    char_budget = 800  # hard cap: ~200 tokens of knowledge
    for score, line in scored[:max_hints]:
        dm = re.search(r'd=(\d+\.?\d*)', line)
        dist = float(dm.group(1)) if dm else 0.5
        if dist <= cutoff or len(kept) < 3:  # always keep top 3
            if total_chars + len(line) > char_budget and len(kept) >= 3:
                break
            kept.append(line)
            total_chars += len(line)

    return '\n'.join(kept)


def _get_brain_size():
    """Get total brain memory count (cached per process)."""
    if not hasattr(_get_brain_size, '_cached'):
        try:
            from brain import brain
            stats = brain.stats()
            _get_brain_size._cached = stats.get('total_memories', 2000)
        except Exception:
            _get_brain_size._cached = 2000
    return _get_brain_size._cached


def _build_brief_beginning(current_task, tier, budget, knowledge_hints):
    """Build the high-attention beginning sections of the brief."""
    parts = []

    # Task echo — ensures task-critical keywords appear in the brief
    if current_task:
        # Extract [TAG] if present
        tag_match = re.search(r'\[([A-Z][A-Z0-9_]+)\]', current_task)
        if tag_match:
            parts.append(f"CURRENT TASK: [{tag_match.group(1)}] {current_task[:120]}")
        else:
            parts.append(f"CURRENT TASK: {current_task[:120]}")

    # Decision Context (success criteria + failure avoidance)
    if budget.get("decision_context", 0) > 0:
        decision_ctx = _build_decision_context(current_task, tier=tier)
        if decision_ctx:
            parts.append(decision_ctx)

    # Brain Knowledge (research, dreams, synthesis) — reranked by task relevance
    if knowledge_hints and tier != "minimal":
        # Prune low-salience brain hits before compression (adaptive to brain growth)
        knowledge_hints = _prune_knowledge_hints(knowledge_hints, current_task,
                                                  max_hints=5 if tier == "standard" else 8)
        try:
            from clarvis.context.assembly import rerank_knowledge_hints
            knowledge_hints = rerank_knowledge_hints(knowledge_hints, current_task)
        except ImportError:
            pass
        if knowledge_hints and knowledge_hints.strip():
            parts.append("RELEVANT KNOWLEDGE:")
            if tier == "full":
                max_chars = 600
            else:
                # Adaptive: simple tasks get tighter knowledge budgets
                try:
                    from clarvis.context.assembly import _estimate_task_complexity
                    complexity = _estimate_task_complexity(current_task)
                    max_chars = {"simple": 200, "complex": 280, "medium": 240}[complexity]
                except Exception:
                    max_chars = 280
            if len(knowledge_hints) > max_chars * 1.5:
                compressed_knowledge, _ = compress_text(knowledge_hints, ratio=0.25, task_context=current_task)
                parts.append(compressed_knowledge[:max_chars])
            else:
                parts.append(knowledge_hints[:max_chars])

    # Working Memory (Cognitive Workspace + Spotlight fallback)
    if budget["spotlight"] > 0:
        workspace_ctx = _get_workspace_context(current_task, tier=tier)
        if workspace_ctx:
            ws_budget = 500 if tier == "full" else 300
            if len(workspace_ctx) > ws_budget * 1.5:
                workspace_ctx, _ = compress_text(workspace_ctx, ratio=0.25, task_context=current_task)
            parts.append(workspace_ctx[:ws_budget])
        else:
            n_items = 5 if tier == "full" else 3
            spotlight = _get_spotlight_items(n=n_items, exclude_task=current_task)
            if spotlight:
                parts.append("WORKING MEMORY:")
                parts.extend(spotlight[:n_items])
    return parts


def _build_brief_middle(current_task, tier, budget, queue_file):
    """Build the lower-attention middle sections (reference data).

    Metrics section is stable (cached via get_latest_scores).
    Related tasks and completions are stable per-queue-mtime + task combo.
    """
    parts = []
    q_mtime = str(os.path.getmtime(queue_file)) if os.path.exists(queue_file) else "0"

    # Related Pending Tasks (cached per task + queue mtime)
    if budget["related_tasks"] > 0:
        n_related = 3 if tier == "full" else 2
        cache_key_related = f"related:{current_task[:60]}:{n_related}"
        related = _section_cache_get(cache_key_related, q_mtime)
        if related is None:
            related = _find_related_tasks(current_task, queue_file, max_tasks=n_related)
            _section_cache_put(cache_key_related, related, q_mtime)
        if related:
            parts.append("RELATED TASKS:")
            for t in related:
                parts.append(f"  - {t}")

    # Metrics (get_latest_scores is itself cached)
    if budget["metrics"] > 0:
        scores = get_latest_scores()
        if scores:
            caps = scores.get("capabilities", {})
            phi = scores.get("phi", "?")
            if caps:
                worst_k = min(caps, key=caps.get)
                worst_v = caps[worst_k]
                if tier == "full":
                    parts.append(f"METRICS: Phi={phi}, cap_avg={scores.get('capability_avg', '?')}, worst={worst_k}={worst_v}")
                    parts.append(f"  {', '.join(f'{k}={v}' for k, v in sorted(caps.items(), key=lambda x: x[1]))}")
                else:
                    parts.append(f"METRICS: Phi={phi}, worst_cap={worst_k}={worst_v}")
            else:
                parts.append(f"METRICS: Phi={phi}")

    # Recent Completions (cached per queue mtime)
    if budget["completions"] > 0:
        n_comp = 3 if tier == "full" else 2
        cache_key_comp = f"completions:{n_comp}"
        completions = _section_cache_get(cache_key_comp, q_mtime)
        if completions is None:
            completions = _get_recent_completions(queue_file, n=n_comp)
            _section_cache_put(cache_key_comp, completions, q_mtime)
        if completions:
            parts.append("RECENT:")
            parts.extend(completions)
    return parts


def _build_brief_end(tier, budget, episodic_hints, current_task=None):
    """Build the high-attention end sections (episodes + reasoning scaffold)."""
    parts = []
    if budget["episodes"] > 0 and episodic_hints:
        max_chars = budget["episodes"] * 4
        if len(episodic_hints) > max_chars * 1.5:
            compressed_episodes, _ = compress_text(episodic_hints, ratio=0.25, task_context=current_task)
            parts.append(compressed_episodes[:max_chars])
        else:
            parts.append(episodic_hints[:max_chars])
    if budget.get("reasoning_scaffold", 0) > 0:
        parts.append(_build_reasoning_scaffold(tier=tier))
    return parts


def generate_tiered_brief(
    current_task,
    tier="standard",
    episodic_hints="",
    knowledge_hints="",
    queue_file=QUEUE_FILE,
):
    """Generate a quality-optimized context brief using primacy/recency positioning.

    Ordering follows LLM attention research (Liu et al. "Lost in the Middle"):
      BEGINNING (highest attention): decision context, knowledge, working memory.
      MIDDLE (lower attention): related tasks, metrics, completions.
      END (high attention): episodic lessons, reasoning scaffold.
    """
    budget = TIER_BUDGETS.get(tier, TIER_BUDGETS["standard"])
    beginning = _build_brief_beginning(current_task, tier, budget, knowledge_hints)
    middle = _build_brief_middle(current_task, tier, budget, queue_file)
    end = _build_brief_end(tier, budget, episodic_hints, current_task=current_task)

    parts = beginning
    if middle:
        parts.append("---")
        parts.extend(middle)
    if end:
        parts.append("---")
        parts.extend(end)
    result = "\n".join(parts)
    # Apply cross-section dedup to remove near-duplicate lines across sections
    try:
        from clarvis.context.dycp import _cross_section_dedup
        result = _cross_section_dedup(result)
    except ImportError:
        pass
    # Record per-section token counts for utilization benchmarking
    _record_brief_token_stats(result, tier, current_task)
    return result


def _record_brief_token_stats(brief_text, tier, task):
    """Record per-section token counts to sidecar JSONL for benchmarking.

    Non-blocking: silently skips on any error.
    """
    try:
        from clarvis.cognition.context_relevance import parse_brief_sections
        sections = parse_brief_sections(brief_text)
        if not sections:
            return
        stats = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "tier": tier,
            "task": task[:120],
            "total_tokens": 0,
            "sections": {},
        }
        for name, content in sections.items():
            word_count = len(content.split())
            tokens = int(word_count * 1.3)
            stats["sections"][name] = {"tokens": tokens, "chars": len(content)}
            stats["total_tokens"] += tokens
        brief_stats_file = os.path.join(
            os.path.dirname(BRIEF_FILE), "brief_token_stats.jsonl")
        os.makedirs(os.path.dirname(brief_stats_file), exist_ok=True)
        with open(brief_stats_file, "a") as f:
            f.write(json.dumps(stats) + "\n")
    except Exception:
        pass


def _classify_queue_lines(lines, cutoff_str):
    """Classify queue lines into kept vs archived based on completion date cutoff.

    Returns (kept_lines, archived_lines, stats_dict).
    """
    kept_lines = []
    archived_lines = []
    stats = {"archived": 0, "kept_completed": 0, "pending": 0}

    for line in lines:
        stripped = line.strip()
        match_done = re.match(r'^- \[x\] (.+)$', stripped)
        if match_done:
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', match_done.group(1))
            if date_match and date_match.group(1) < cutoff_str:
                archived_lines.append(line)
                stats["archived"] += 1
                continue
            stats["kept_completed"] += 1
            kept_lines.append(line)
            continue
        if re.match(r'^- \[ \] ', stripped):
            stats["pending"] += 1
        kept_lines.append(line)
    return kept_lines, archived_lines, stats


def _write_archive(archived_lines, archive_file, stats, keep_days):
    """Write archived lines to archive file and store summary in brain."""
    header = f"\n## Archived {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n"
    with open(archive_file, 'a') as f:
        f.write(header)
        f.writelines(archived_lines)
    try:
        from brain import brain
        brain.store(
            f"Archived {stats['archived']} completed tasks from QUEUE.md "
            f"(older than {keep_days} days). Saved {stats['bytes_saved']} bytes.",
            collection="context",
            metadata={"type": "archive_event", "date": datetime.now(timezone.utc).isoformat()},
            importance=0.3
        )
    except Exception:
        pass


def archive_completed(queue_file=QUEUE_FILE, archive_file=QUEUE_ARCHIVE,
                      keep_days=7, dry_run=False):
    """Move old completed tasks from QUEUE.md to archive file.

    Returns dict with stats: {archived: N, kept: N, pending: N, bytes_saved: N}.
    """
    if not os.path.exists(queue_file):
        return {"error": "QUEUE.md not found"}

    with open(queue_file, 'r') as f:
        content = f.read()
        lines = content.splitlines(keepends=True)

    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    kept_lines, archived_lines, stats = _classify_queue_lines(lines, cutoff.strftime("%Y-%m-%d"))
    stats["bytes_before"] = len(content)
    new_content = "".join(kept_lines)
    stats["bytes_after"] = len(new_content)
    stats["bytes_saved"] = stats["bytes_before"] - stats["bytes_after"]

    if dry_run:
        return stats

    if archived_lines:
        _write_archive(archived_lines, archive_file, stats, keep_days)
        with open(queue_file, 'w') as f:
            f.write(new_content)

    return stats


def rotate_logs(log_dir=CRON_LOG_DIR, max_bytes=LOG_MAX_BYTES, dry_run=False):
    """Rotate oversized cron logs and gzip old daily memory files.

    For cron logs > max_bytes:
      - Keep last max_bytes of content, discard older lines
      - Append a "[TRUNCATED]" marker

    For daily memory files > 7 days old:
      - Gzip them (memory/2026-02-15.md -> memory/2026-02-15.md.gz)

    Returns dict with stats.
    """
    stats = {"logs_truncated": 0, "logs_bytes_saved": 0, "files_gzipped": 0}

    # 1. Truncate oversized cron logs
    if os.path.isdir(log_dir):
        for logfile in glob.glob(os.path.join(log_dir, "*.log")):
            size = os.path.getsize(logfile)
            if size > max_bytes:
                if dry_run:
                    stats["logs_truncated"] += 1
                    stats["logs_bytes_saved"] += size - max_bytes
                    continue

                with open(logfile, 'rb') as f:
                    f.seek(size - max_bytes)
                    tail = f.read()

                # Find first newline to avoid partial line
                nl = tail.find(b'\n')
                if nl >= 0:
                    tail = tail[nl + 1:]

                marker = f"[TRUNCATED {datetime.now(timezone.utc).strftime('%Y-%m-%d')}] Older entries archived to save context window space\n".encode()
                with open(logfile, 'wb') as f:
                    f.write(marker)
                    f.write(tail)

                saved = size - os.path.getsize(logfile)
                stats["logs_truncated"] += 1
                stats["logs_bytes_saved"] += saved

    # 2. Gzip old daily memory files
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    for md_file in glob.glob(os.path.join(MEMORY_DIR, "2026-*.md")):
        basename = os.path.basename(md_file)
        # Extract date from filename (2026-02-15.md)
        date_match = re.match(r'(\d{4}-\d{2}-\d{2})\.md$', basename)
        if not date_match:
            continue
        file_date = date_match.group(1)
        if file_date >= cutoff_str:
            continue  # recent — keep uncompressed

        gz_path = md_file + ".gz"
        if os.path.exists(gz_path):
            continue  # already gzipped

        if dry_run:
            stats["files_gzipped"] += 1
            continue

        with open(md_file, 'rb') as f_in:
            with gzip.open(gz_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(md_file)
        stats["files_gzipped"] += 1

    return stats


def gc(dry_run=False):
    """Run full garbage collection: archive old tasks + rotate logs.

    Designed to run nightly in cron_reflection.sh.
    Returns combined stats dict.
    """
    results = {}
    results["archive"] = archive_completed(dry_run=dry_run)
    results["logs"] = rotate_logs(dry_run=dry_run)

    total_saved = (
        results["archive"].get("bytes_saved", 0)
        + results["logs"].get("logs_bytes_saved", 0)
    )
    results["total_bytes_saved"] = total_saved
    results["total_tokens_saved_est"] = total_saved // 4  # rough estimate

    return results


if __name__ == "__main__":
    print("DEPRECATION: Core functions available via 'from clarvis.context import tfidf_extract, mmr_rerank, compress_text, compress_queue'.", file=sys.stderr)
    if len(sys.argv) < 2:
        print("Usage: context_compressor.py <queue|health|brief|tiered|episodes|compress|gc|savings|cache-stats>")
        print("  queue        — compressed evolution queue")
        print("  health       — compressed health summary (reads from stdin or args)")
        print("  brief        — full context brief for prompts (legacy)")
        print("  brief --file — write brief to data/context_brief.txt")
        print("  tiered TASK [minimal|standard|full] — budget-aware brief adapted to task")
        print("  episodes     — compress episode text from stdin")
        print("  compress     — TF-IDF extractive compression (pipe text to stdin)")
        print("  savings      — estimate token savings")
        print("  gc           — archive old completed tasks + rotate logs")
        print("  gc --dry-run — show what gc would do without doing it")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "queue":
        print(compress_queue())

    elif cmd == "health":
        # Read from stdin if piped, else show empty
        if not sys.stdin.isatty():
            data = sys.stdin.read()
            print(compress_health(capability_output=data))
        else:
            print(compress_health())

    elif cmd == "brief":
        brief = generate_context_brief()
        if "--file" in sys.argv:
            os.makedirs(os.path.dirname(BRIEF_FILE), exist_ok=True)
            with open(BRIEF_FILE, 'w') as f:
                f.write(brief)
            print(f"Written to {BRIEF_FILE} ({len(brief)} bytes)")
        else:
            print(brief)

    elif cmd == "tiered":
        # Usage: context_compressor.py tiered "task text" [minimal|standard|full]
        task = sys.argv[2] if len(sys.argv) > 2 else "unknown task"
        tier = sys.argv[3] if len(sys.argv) > 3 else "standard"
        brief = generate_tiered_brief(task, tier=tier)
        print(brief)
        print(f"\n--- {tier} tier: {len(brief)} bytes (~{len(brief)//4} tokens) ---")

    elif cmd == "episodes":
        if not sys.stdin.isatty():
            data = sys.stdin.read()
            print(compress_episodes(data, ""))
        else:
            print("Pipe episode text to stdin")

    elif cmd == "compress":
        if not sys.stdin.isatty():
            data = sys.stdin.read()
            ratio = float(sys.argv[2]) if len(sys.argv) > 2 else 0.3
            compressed, stats = compress_text(data, ratio=ratio)
            print(compressed)
            print(f"\n--- Compression stats: {stats} ---")
        else:
            print("Pipe text to stdin. Usage: echo 'text' | context_compressor.py compress [ratio]")

    elif cmd == "gc":
        dry = "--dry-run" in sys.argv
        results = gc(dry_run=dry)
        prefix = "[DRY RUN] " if dry else ""
        arc = results["archive"]
        logs = results["logs"]
        print(f"{prefix}=== Context Window GC ===")
        print(f"{prefix}Archive: {arc.get('archived', 0)} completed tasks moved to QUEUE_ARCHIVE.md "
              f"({arc.get('bytes_saved', 0)} bytes saved), "
              f"{arc.get('kept_completed', 0)} recent kept, {arc.get('pending', 0)} pending")
        print(f"{prefix}Logs: {logs.get('logs_truncated', 0)} logs truncated "
              f"({logs.get('logs_bytes_saved', 0)} bytes saved), "
              f"{logs.get('files_gzipped', 0)} daily files gzipped")
        print(f"{prefix}Total: ~{results['total_tokens_saved_est']} tokens saved")

    elif cmd == "cache-stats":
        stats = section_cache_stats()
        print(f"Section cache: {stats['entries']} entries")
        for s in stats["sections"]:
            print(f"  {s['section']}: age={s['age_s']}s expired={s['expired']}")
        if not stats["sections"]:
            print("  (empty — cache populates on first brief generation)")

    elif cmd == "savings":
        # Estimate token savings
        if os.path.exists(QUEUE_FILE):
            with open(QUEUE_FILE, 'r') as f:
                raw = f.read()
            compressed = compress_queue()
            raw_tokens = len(raw) // 4  # rough estimate: 4 chars/token
            comp_tokens = len(compressed) // 4
            savings = raw_tokens - comp_tokens
            pct = (1 - comp_tokens / max(1, raw_tokens)) * 100
            print("QUEUE.md token estimate:")
            print(f"  Raw: ~{raw_tokens} tokens ({len(raw)} bytes)")
            print(f"  Compressed: ~{comp_tokens} tokens ({len(compressed)} bytes)")
            print(f"  Savings: ~{savings} tokens/heartbeat ({pct:.0f}% reduction)")
            print(f"  At 48 heartbeats/day: ~{savings * 48} tokens/day saved")
        else:
            print("QUEUE.md not found")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
