#!/usr/bin/env python3
"""
Context Compressor — Summarize old context instead of full history

Reduces token consumption by:
1. compress_queue() — strips completed tasks from QUEUE.md, keeps only pending + last 5 completions
2. compress_health() — summarizes multi-line health data into compact key=value format
3. compress_episodes() — trims episodic recall to essentials (outcome, lesson, not full text)
4. generate_context_brief() — one-shot compressed context for Claude Code prompts

SAVINGS ESTIMATE:
  QUEUE.md: 48KB → ~4KB (85% reduction)
  Health data: ~8KB → ~1KB (87% reduction)
  Per heartbeat: ~15K tokens → ~2K tokens saved

Usage:
    from context_compressor import compress_queue, compress_health, generate_context_brief

    # CLI
    python3 context_compressor.py queue          # compressed queue
    python3 context_compressor.py health         # compressed health summary
    python3 context_compressor.py brief          # full context brief for prompts
    python3 context_compressor.py brief --file   # write to data/context_brief.txt
"""

import gzip
import glob
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(__file__))

QUEUE_FILE = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md"
QUEUE_ARCHIVE = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE_ARCHIVE.md"
BRIEF_FILE = "/home/agent/.openclaw/workspace/data/context_brief.txt"
CAPABILITY_HISTORY = "/home/agent/.openclaw/workspace/data/capability_history.json"
PHI_HISTORY = "/home/agent/.openclaw/workspace/data/phi_history.json"
MEMORY_DIR = "/home/agent/.openclaw/workspace/memory"
CRON_LOG_DIR = "/home/agent/.openclaw/workspace/memory/cron"
LOG_MAX_BYTES = 100_000  # 100KB cap per cron log


def compress_queue(queue_file=QUEUE_FILE, max_recent_completed=5):
    """Compress QUEUE.md: pending tasks in full, last N completed as 1-liners, rest stripped.

    Returns a string suitable for injection into Claude Code prompts.

    Typical reduction: 48KB → 3-5KB (85-90% token savings).
    """
    if not os.path.exists(queue_file):
        return "No evolution queue found."

    with open(queue_file, 'r') as f:
        lines = f.readlines()

    pending_tasks = []       # [ ] items — keep in full
    recent_completed = []    # [x] items — keep last N as summaries
    current_section = ""

    for line in lines:
        stripped = line.strip()

        # Track section headers
        if stripped.startswith('## '):
            current_section = stripped
            continue

        # Skip completed section entirely
        if '## Completed' in current_section:
            continue

        # Pending tasks — keep verbatim with section context
        match_pending = re.match(r'^- \[ \] (.+)$', stripped)
        if match_pending:
            task_text = match_pending.group(1)
            # Strip long parenthetical timestamps/details for compression
            # Keep up to first ( or — to get the core task
            core = re.split(r'\s*[\(—]', task_text, 1)[0].strip()
            if len(core) < 20:
                core = task_text[:150]  # fallback: keep more if core is too short
            pending_tasks.append({
                "section": current_section,
                "task": core,
            })
            continue

        # Completed tasks — collect for recency trimming
        match_done = re.match(r'^- \[x\] (.+)$', stripped)
        if match_done:
            task_text = match_done.group(1)
            # Try to extract date BEFORE splitting (it's often in the parenthetical)
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', task_text)
            date_str = date_match.group(1) if date_match else "unknown"
            # Extract just the core task name (before timestamp/details)
            core = re.split(r'\s*[\(—]', task_text, 1)[0].strip()
            if len(core) < 15:
                core = task_text[:100]
            recent_completed.append({
                "section": current_section,
                "task": core,
                "date": date_str,
            })

    # Sort completed by date (newest first), "unknown" goes last
    recent_completed.sort(key=lambda x: x["date"] if x["date"] != "unknown" else "0000", reverse=True)
    recent_completed = recent_completed[:max_recent_completed]

    # Build compressed output
    output = []
    output.append("=== EVOLUTION QUEUE (compressed) ===\n")

    # Group pending by section
    pending_by_section = {}
    for t in pending_tasks:
        sec = t["section"]
        if sec not in pending_by_section:
            pending_by_section[sec] = []
        pending_by_section[sec].append(t["task"])

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

    Takes raw stdout from various health scripts and extracts only the
    essential metrics, discarding verbose explanations.

    Typical reduction: 8KB → 1KB (87% token savings).
    """
    summary = []
    summary.append("=== SYSTEM HEALTH (compressed) ===")

    # Extract key numbers from calibration
    if calibration_output:
        brier_match = re.search(r'[Bb]rier[:\s=]*([0-9.]+)', calibration_output)
        accuracy_match = re.search(r'(\d+)/(\d+)\s*correct|accuracy[:\s=]*([0-9.]+)', calibration_output)
        brier = brier_match.group(1) if brier_match else "?"
        if accuracy_match:
            if accuracy_match.group(1):
                accuracy = f"{accuracy_match.group(1)}/{accuracy_match.group(2)}"
            else:
                accuracy = accuracy_match.group(3)
        else:
            accuracy = "?"
        summary.append(f"Calibration: Brier={brier}, accuracy={accuracy}")

    # Extract Phi value
    if phi_output:
        phi_match = re.search(r'[Pp]hi[:\s=]*([0-9.]+)', phi_output)
        trend_match = re.search(r'trend[:\s=]*([a-z_]+|[↑↓→]+)', phi_output, re.IGNORECASE)
        phi_val = phi_match.group(1) if phi_match else "?"
        trend = trend_match.group(1) if trend_match else "stable"
        summary.append(f"Phi={phi_val} (trend: {trend})")

    # Extract capability scores — just the numbers
    if capability_output:
        # Pattern: "domain_name: 0.XX" or "domain: X.XX"
        scores = re.findall(r'(\w[\w_]+)[:=]\s*([0-9.]+)', capability_output)
        if scores:
            # Find lowest
            score_pairs = [(name, float(val)) for name, val in scores if 0 <= float(val) <= 1.0]
            if score_pairs:
                score_pairs.sort(key=lambda x: x[1])
                worst = score_pairs[0]
                avg = sum(v for _, v in score_pairs) / len(score_pairs)
                summary.append(f"Capabilities: avg={avg:.2f}, worst={worst[0]}={worst[1]:.2f}, n={len(score_pairs)}")
                # List all briefly
                scores_str = ", ".join(f"{n}={v:.2f}" for n, v in score_pairs)
                summary.append(f"  Scores: {scores_str}")

    # Extract retrieval health
    if retrieval_output:
        hit_match = re.search(r'hit[_ ]rate[:\s=]*([0-9.]+)%?', retrieval_output, re.IGNORECASE)
        health_match = re.search(r'(HEALTHY|DEGRADED|CRITICAL)', retrieval_output)
        hit = hit_match.group(1) if hit_match else "?"
        health = health_match.group(1) if health_match else "?"
        summary.append(f"Retrieval: hit_rate={hit}%, status={health}")

    # Episode stats — just count and success rate
    if episode_output:
        count_match = re.search(r'(\d+)\s*episodes?', episode_output)
        success_match = re.search(r'success[:\s=]*([0-9.]+)%?', episode_output, re.IGNORECASE)
        count = count_match.group(1) if count_match else "?"
        success = success_match.group(1) if success_match else "?"
        summary.append(f"Episodes: n={count}, success_rate={success}%")

    # Goal tracker — just stalled count
    if goal_output:
        stalled_match = re.search(r'(\d+)\s*stalled', goal_output, re.IGNORECASE)
        tasks_match = re.search(r'(\d+)\s*tasks?\s*(generated|added)', goal_output, re.IGNORECASE)
        stalled = stalled_match.group(1) if stalled_match else "0"
        tasks_gen = tasks_match.group(1) if tasks_match else "0"
        summary.append(f"Goals: {stalled} stalled, {tasks_gen} remediation tasks generated")

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
    """
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

    return scores


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
        from episodic_memory import EpisodicMemory
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

    Wire tasks have a 30% success rate (vs 55% for build tasks) because they
    require multi-file integration across bash/Python boundaries. Returns
    (is_wire, source_script, target_script) tuple.
    """
    task_lower = task_text.lower()
    wire_verbs = ["wire", "connect", "integrate", "hook", "link"]
    if not any(v in task_lower for v in wire_verbs):
        return False, None, None

    # Extract source (what to wire) and target (where to wire it)
    source = None
    target = None
    # Pattern: "Wire X into Y", "Integrate X into Y", "Hook X into Y"
    m = re.search(r'(?:wire|integrate|hook|connect|link)\s+(\S+\.(?:py|sh))\s+(?:into|to|with)\s+(\S+\.(?:py|sh))', task_lower)
    if m:
        source = m.group(1)
        target = m.group(2)
    else:
        # Pattern: "Wire X into Y" where X/Y are descriptive names
        m = re.search(r'(?:wire|integrate|hook|connect|link)\s+(.+?)\s+(?:into|to|with)\s+(.+?)(?:\s*[-—]|$)', task_lower)
        if m:
            source = m.group(1).strip()
            target = m.group(2).strip()

    return True, source, target


def _build_wire_guidance(task_text):
    """Generate explicit integration sub-steps for wire tasks.

    Wire tasks fail 70% of the time due to:
      - shallow_reasoning (57%): vague "Wire X into Y" with no specifics
      - long_duration (29%): excessive exploration of unfamiliar architecture

    This function generates concrete steps that eliminate ambiguity.
    """
    is_wire, source, target = _detect_wire_task(task_text)
    if not is_wire:
        return ""

    # Known integration targets and their structure
    KNOWN_TARGETS = {
        "cron_reflection.sh": {
            "path": "/home/agent/.openclaw/workspace/scripts/cron_reflection.sh",
            "structure": "Steps 0.5-7, each runs a python3 script. Add new steps between existing ones.",
            "pattern": "# Step N: Description\necho ... >> \"$LOGFILE\"\npython3 /path/to/script.py >> \"$LOGFILE\" 2>&1 || true",
        },
        "cron_autonomous.sh": {
            "path": "/home/agent/.openclaw/workspace/scripts/cron_autonomous.sh",
            "structure": "3 phases: preflight (heartbeat_preflight.py) → execution → postflight (heartbeat_postflight.py).",
            "pattern": "Modify heartbeat_preflight.py (add import + call) or heartbeat_postflight.py, NOT the bash script directly.",
        },
        "heartbeat_preflight.py": {
            "path": "/home/agent/.openclaw/workspace/scripts/heartbeat_preflight.py",
            "structure": "Sections 1-10, each with timing. Import at top (try/except), call in run_preflight().",
            "pattern": "try:\n    from module import func\nexcept ImportError:\n    func = None\n# ... then in run_preflight(): if func: try: result = func(...)",
        },
        "heartbeat_postflight.py": {
            "path": "/home/agent/.openclaw/workspace/scripts/heartbeat_postflight.py",
            "structure": "Post-execution steps. Import at top, call in run_postflight().",
            "pattern": "Same pattern as preflight: try/except import at top, guarded call in main function.",
        },
    }

    parts = ["WIRE TASK GUIDANCE (wire tasks have 30% success — follow these steps carefully):"]

    # Add target-specific guidance if we recognize the target
    if target:
        for known_name, info in KNOWN_TARGETS.items():
            if known_name in (target or ""):
                parts.append(f"  TARGET: {info['path']}")
                parts.append(f"  STRUCTURE: {info['structure']}")
                parts.append(f"  PATTERN: {info['pattern']}")
                break

    # Always add the explicit sub-steps that successful wire tasks follow
    parts.append("  REQUIRED SUB-STEPS (do each one explicitly):")
    parts.append("    1. READ the target file first — find the exact insertion point (step number, function, line)")
    parts.append("    2. READ the source script — verify the function/class to import exists and its signature")
    parts.append("    3. ADD the import (with try/except fallback for resilience)")
    parts.append("    4. ADD the call at the correct location (with timing + logging + error handling)")
    parts.append("    5. TEST: run the target script (or python3 -c 'import ...') to verify no import/syntax errors")
    parts.append("    6. VERIFY: confirm the integration point is reached (check log output or return value)")

    return "\n".join(parts)


def _build_reasoning_scaffold(tier="standard"):
    """Generate reasoning scaffolding instructions appropriate to the tier.

    Research shows explicit step-by-step instructions improve LLM output quality
    significantly, especially for complex tasks.
    """
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


def _get_spotlight_items(n=5, exclude_task=""):
    """Get top-N attention spotlight items as compact strings.

    Deduplicates similar items and strips TASK: prefixes.
    Excludes items that closely match `exclude_task` to avoid echoing the current task.
    """
    try:
        from attention import attention
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


def generate_tiered_brief(
    current_task,
    tier="standard",
    episodic_hints="",
    knowledge_hints="",
    queue_file=QUEUE_FILE,
):
    """Generate a quality-optimized context brief using primacy/recency positioning.

    Ordering follows LLM attention research (Liu et al. "Lost in the Middle"):
      BEGINNING (highest attention): Decision context — success criteria, failure
          avoidance, constraints. This shapes HOW the model approaches the task.
      MIDDLE (lower attention): Metrics, related tasks, completions — useful but
          non-critical reference data.
      END (high attention): Episodic lessons + reasoning scaffold — the final
          instructions the model sees before generating output.

    Args:
        current_task: The task being executed (used for relevance filtering).
        tier: "minimal" | "standard" | "full" — controls depth, not just size.
        episodic_hints: Pre-compressed episode text (from compress_episodes).
        queue_file: Path to QUEUE.md.

    Returns:
        Quality-optimized context string. Size varies by tier:
          minimal:  ~200 tokens (task-focused, no extras)
          standard: ~600 tokens (decision context + spotlight + metrics + scaffold)
          full:     ~1000 tokens (everything, optimally ordered for attention)
    """
    budget = TIER_BUDGETS.get(tier, TIER_BUDGETS["standard"])
    # Build sections in attention-optimal order:
    #   beginning_parts → middle_parts → end_parts
    beginning = []
    middle = []
    end = []

    # =====================================================================
    # BEGINNING — High attention zone: shapes the model's approach
    # =====================================================================

    # === SECTION 1: Decision Context (success criteria + failure avoidance) ===
    if budget.get("decision_context", 0) > 0:
        decision_ctx = _build_decision_context(current_task, tier=tier)
        if decision_ctx:
            beginning.append(decision_ctx)

    # === SECTION 1.5: Brain Knowledge (research, dreams, synthesis) ===
    if knowledge_hints and tier != "minimal":
        beginning.append("RELEVANT KNOWLEDGE:")
        # Cap knowledge hints to stay within budget
        max_chars = 600 if tier == "full" else 350
        beginning.append(knowledge_hints[:max_chars])

    # === SECTION 2: Working Memory (Attention Spotlight) ===
    if budget["spotlight"] > 0:
        n_items = 5 if tier == "full" else 3
        spotlight = _get_spotlight_items(n=n_items, exclude_task=current_task)
        if spotlight:
            beginning.append("WORKING MEMORY:")
            beginning.extend(spotlight[:n_items])

    # =====================================================================
    # MIDDLE — Lower attention zone: reference data
    # =====================================================================

    # === SECTION 3: Related Pending Tasks ===
    if budget["related_tasks"] > 0:
        n_related = 3 if tier == "full" else 2
        related = _find_related_tasks(current_task, queue_file, max_tasks=n_related)
        if related:
            middle.append("RELATED TASKS:")
            for t in related:
                middle.append(f"  - {t}")

    # === SECTION 4: Metrics ===
    if budget["metrics"] > 0:
        scores = get_latest_scores()
        if scores:
            if tier == "full" and "capabilities" in scores:
                caps = scores["capabilities"]
                worst_k = min(caps, key=caps.get) if caps else "?"
                worst_v = caps.get(worst_k, "?") if caps else "?"
                middle.append(f"METRICS: Phi={scores.get('phi', '?')}, cap_avg={scores.get('capability_avg', '?')}, worst={worst_k}={worst_v}")
                middle.append(f"  {', '.join(f'{k}={v}' for k, v in sorted(caps.items(), key=lambda x: x[1]))}")
            else:
                phi = scores.get("phi", "?")
                if "capabilities" in scores:
                    caps = scores["capabilities"]
                    worst_k = min(caps, key=caps.get) if caps else "?"
                    worst_v = caps.get(worst_k, "?") if caps else "?"
                    middle.append(f"METRICS: Phi={phi}, worst_cap={worst_k}={worst_v}")
                else:
                    middle.append(f"METRICS: Phi={phi}")

    # === SECTION 5: Recent Completions ===
    if budget["completions"] > 0:
        n_comp = 3 if tier == "full" else 2
        completions = _get_recent_completions(queue_file, n=n_comp)
        if completions:
            middle.append("RECENT:")
            middle.extend(completions)

    # =====================================================================
    # END — High attention zone: last thing the model sees before output
    # =====================================================================

    # === SECTION 6: Episodic Lessons (specific to this task type) ===
    if budget["episodes"] > 0 and episodic_hints:
        max_chars = budget["episodes"] * 4  # ~4 chars per token
        end.append(episodic_hints[:max_chars])

    # === SECTION 7: Reasoning Scaffold (think-then-do instruction) ===
    if budget.get("reasoning_scaffold", 0) > 0:
        scaffold = _build_reasoning_scaffold(tier=tier)
        end.append(scaffold)

    # Assemble: beginning → middle → end
    parts = beginning
    if middle:
        parts.append("---")
        parts.extend(middle)
    if end:
        parts.append("---")
        parts.extend(end)

    return "\n".join(parts)


def archive_completed(queue_file=QUEUE_FILE, archive_file=QUEUE_ARCHIVE,
                      keep_days=7, dry_run=False):
    """Move old completed tasks from QUEUE.md to archive file.

    Keeps completed tasks from the last `keep_days` days in QUEUE.md.
    Older completed tasks are appended to QUEUE_ARCHIVE.md and removed
    from the main file.

    Returns dict with stats: {archived: N, kept: N, pending: N, bytes_saved: N}.
    """
    if not os.path.exists(queue_file):
        return {"error": "QUEUE.md not found"}

    with open(queue_file, 'r') as f:
        content = f.read()
        lines = content.splitlines(keepends=True)

    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    kept_lines = []
    archived_lines = []
    stats = {"archived": 0, "kept_completed": 0, "pending": 0, "bytes_before": len(content)}

    for line in lines:
        stripped = line.strip()

        # Check if this is a completed task
        match_done = re.match(r'^- \[x\] (.+)$', stripped)
        if match_done:
            task_text = match_done.group(1)
            # Extract date
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', task_text)
            if date_match:
                task_date = date_match.group(1)
                if task_date < cutoff_str:
                    # Old completed task — archive it
                    archived_lines.append(line)
                    stats["archived"] += 1
                    continue
            # No date or recent — keep
            stats["kept_completed"] += 1
            kept_lines.append(line)
            continue

        # Pending task — always keep
        if re.match(r'^- \[ \] ', stripped):
            stats["pending"] += 1

        kept_lines.append(line)

    new_content = "".join(kept_lines)
    stats["bytes_after"] = len(new_content)
    stats["bytes_saved"] = stats["bytes_before"] - stats["bytes_after"]

    if dry_run:
        return stats

    if archived_lines:
        # Append to archive file
        header = f"\n## Archived {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n"
        with open(archive_file, 'a') as f:
            f.write(header)
            f.writelines(archived_lines)

        # Store archive summary in brain (if available)
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

        # Rewrite QUEUE.md without archived tasks
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
    if len(sys.argv) < 2:
        print("Usage: context_compressor.py <queue|health|brief|tiered|episodes|gc|savings>")
        print("  queue        — compressed evolution queue")
        print("  health       — compressed health summary (reads from stdin or args)")
        print("  brief        — full context brief for prompts (legacy)")
        print("  brief --file — write brief to data/context_brief.txt")
        print("  tiered TASK [minimal|standard|full] — budget-aware brief adapted to task")
        print("  episodes     — compress episode text from stdin")
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
