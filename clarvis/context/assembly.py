"""
Context Assembly — attention-optimal context brief generation.

Migrated from scripts/context_compressor.py (the advanced assembly functions).
Provides decision context, failure patterns, wire guidance, reasoning scaffold,
workspace/spotlight integration, and the full tiered brief generator.

Usage:
    from clarvis.context.assembly import generate_tiered_brief
    brief = generate_tiered_brief("my task", tier="standard")
"""

import os
import re
from .compressor import compress_text, get_latest_scores

WORKSPACE = os.environ.get(
    "CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"
)
SCRIPTS = os.path.join(WORKSPACE, "scripts")
QUEUE_FILE = os.path.join(WORKSPACE, "memory/evolution/QUEUE.md")

# Mapping from budget keys to context_relevance section names.
# Each budget key controls a region of the brief; the section names are
# what context_relevance.py tracks at the per-section level.
# Note: brain_goals, metrics folded into decision_context; synaptic folded
# into spotlight (2026-03-18) — all had mean relevance < 0.12 as standalone.
_BUDGET_TO_SECTIONS = {
    "decision_context": ["decision_context", "failure_avoidance", "meta_gradient",
                         "brain_goals", "metrics"],
    "spotlight": ["working_memory", "attention", "gwt_broadcast", "brain_context",
                  "synaptic"],
    "related_tasks": ["related_tasks"],
    "completions": ["completions"],
    "episodes": ["episodes"],
    "reasoning_scaffold": ["reasoning"],
}

# Relevance-based budget adjustment parameters
MIN_EPISODES_FOR_ADJUSTMENT = 5  # need enough data before adjusting
BUDGET_FLOOR = 0.4   # minimum 40% of base budget (legacy, used as fallback)
BUDGET_CEILING = 1.4  # maximum 140% of base budget (legacy, used as fallback)

# Adaptive section cap thresholds — tiered budget allocation based on
# rolling 14-day mean relevance score per budget category.
# Replaces smooth linear interpolation with aggressive stepped scaling.
# Evidence: last 30 episodes show clear tier separation (2026-03-19).
ADAPTIVE_HIGH_THRESHOLD = 0.25   # mean ≥ 0.25 → 100% budget
ADAPTIVE_MID_THRESHOLD = 0.12    # mean 0.12-0.25 → 50% budget
# mean < 0.12 → 0% budget (hard-pruned)

# Token budgets per tier (attention-optimal allocation)
# Sections that are never pruned by DyCP (high-value regardless of task overlap)
DYCP_PROTECTED_SECTIONS = frozenset({
    "decision_context", "reasoning", "knowledge", "related_tasks",
    "episodes", "completions",
})

# Minimum containment (section∩task / section) to keep a prunable section.
# Calibrated from per-section data: sections with mean relevance < 0.10
# almost never contribute. Raised 0.04→0.08 on 2026-03-18 to prune more
# aggressively — the 5 weakest sections (mean < 0.12) were still leaking through.
DYCP_MIN_CONTAINMENT = 0.08

# Also consider historical mean relevance — sections historically below
# this AND below task-containment threshold get pruned.
# History: 0.13→0.16 (2026-03-15) → 0.20 (2026-03-18) → 0.15 (2026-03-19).
# Lowered back: 0.20 was too aggressive — pruned moderately useful sections
# (brain_context=0.163, confidence_gate=0.167) that agents do reference.
# Tier 0 (hardcoded < 0.15) still catches truly noisy sections.
DYCP_HISTORICAL_FLOOR = 0.15

# Sections with zero task overlap AND historical score below this
# stricter ceiling are also pruned (DyCP query-dependent tier 2).
# Lowered 0.20→0.15 on 2026-03-19: same rationale — borderline-useful
# sections (hist 0.15-0.20) shouldn't be pruned even with zero overlap.
DYCP_ZERO_OVERLAP_CEILING = 0.15

# Hard-suppressed: bottom-5 noise sections with 14-day mean < 0.12.
# These are ALWAYS suppressed — no task-containment override.  They waste
# ~800 tokens per brief for near-zero downstream signal (2026-03-18 analysis).
HARD_SUPPRESS = frozenset({
    "meta_gradient",      # mean=0.058
    "brain_goals",        # mean=0.089
    "failure_avoidance",  # mean=0.090
    "metrics",            # mean=0.097
    "synaptic",           # mean=0.112
})

# Soft-suppressed: borderline sections (mean 0.12-0.13) that ARE included
# when task-containment exceeds DYCP_DEFAULT_SUPPRESS_CONTAINMENT_OVERRIDE.
# This list is separate from DyCP pruning — DyCP prunes post-assembly,
# while default-suppress prevents generation in the first place (cheaper).
DYCP_DEFAULT_SUPPRESS = frozenset({
    "world_model",        # mean=0.122
    "gwt_broadcast",      # mean=0.128
    "introspection",      # mean=0.129
})
# Task-containment threshold to override default suppression — if the task
# tokens overlap significantly with a suppressed section, include it anyway.
DYCP_DEFAULT_SUPPRESS_CONTAINMENT_OVERRIDE = 0.10

# Cache of section name → content token sample from the last assembled brief.
# Populated by dycp_prune_brief(); used by _dycp_task_containment_fast() so
# that suppression decisions consider actual section content, not just the
# section name.  First run (empty cache) falls back to name-only matching.
_section_content_cache: dict = {}

# Maximum number of content tokens to sample per section for the cache.
# Kept small to make the containment check fast (O(n) set intersection).
_CONTENT_SAMPLE_SIZE = 40


TIER_BUDGETS = {
    "minimal": {
        "total": 200,
        "decision_context": 0,
        "spotlight": 0,
        "related_tasks": 0,
        "completions": 0,
        "episodes": 0,
        "reasoning_scaffold": 0,
    },
    "standard": {
        "total": 600,
        "decision_context": 140,   # +40 from merged metrics
        "spotlight": 80,
        "related_tasks": 60,
        "completions": 40,
        "episodes": 60,
        "reasoning_scaffold": 40,
    },
    "full": {
        "total": 1000,
        "decision_context": 230,   # +80 from merged metrics
        "spotlight": 120,
        "related_tasks": 100,
        "completions": 60,
        "episodes": 120,
        "reasoning_scaffold": 60,
    },
}

RECENCY_BOOST_EPISODES = 5  # last N episodes get up to 3x weight in budget adjustment

def load_relevance_weights(min_episodes=MIN_EPISODES_FOR_ADJUSTMENT, days=14):
    """Load per-section relevance scores and convert to adaptive budget scaling factors.

    Reads aggregated context_relevance data and maps per-section mean scores
    to budget category scaling factors using tiered thresholds:
      - mean ≥ ADAPTIVE_HIGH_THRESHOLD (0.25): scale=1.0 (full budget)
      - ADAPTIVE_MID_THRESHOLD ≤ mean < ADAPTIVE_HIGH_THRESHOLD: scale=0.5 (half budget)
      - mean < ADAPTIVE_MID_THRESHOLD (0.12): scale=0.0 (hard-pruned)

    Uses exponential recency weighting so the last 5 episodes have ~3x
    influence — budget adjustments respond within 1-2 heartbeat cycles
    instead of waiting for the full 14-day window to rotate.

    Returns:
        Dict mapping budget keys to scaling factors, or empty dict if
        insufficient episode data exists.
    """
    try:
        from clarvis.cognition.context_relevance import aggregate_relevance
        agg = aggregate_relevance(days=days, recency_boost=RECENCY_BOOST_EPISODES)
    except Exception:
        return {}

    if agg.get("episodes", 0) < min_episodes:
        return {}

    per_section = agg.get("per_section_mean", {})
    if not per_section:
        return {}

    weights = {}
    for budget_key, section_names in _BUDGET_TO_SECTIONS.items():
        # Exclude HARD_SUPPRESS sections from averaging — they're already
        # suppressed at generation time and shouldn't drag down the budget
        # of the category they were folded into (e.g., meta_gradient=0.058
        # shouldn't penalize decision_context=0.300).
        active_scores = [
            per_section[s] for s in section_names
            if s in per_section and s not in HARD_SUPPRESS
        ]
        if not active_scores:
            continue
        mean_score = sum(active_scores) / len(active_scores)
        # Tiered adaptive scaling (replaces linear interpolation 2026-03-19)
        if mean_score >= ADAPTIVE_HIGH_THRESHOLD:
            scale = 1.0
        elif mean_score >= ADAPTIVE_MID_THRESHOLD:
            scale = 0.5
        else:
            scale = 0.0
        weights[budget_key] = scale

    return weights


def get_adjusted_budgets(tier="standard"):
    """Get tier budgets adjusted by adaptive relevance-based caps.

    Uses tiered scaling from load_relevance_weights():
      - High relevance (≥0.25): full budget
      - Mid relevance (0.12-0.25): 50% budget
      - Low relevance (<0.12): 0 tokens (hard-pruned from brief)

    Tokens freed by pruned/halved sections are redistributed to full-budget
    sections proportionally, keeping total token budget constant.

    Falls back to static TIER_BUDGETS when no relevance data exists.
    """
    base = TIER_BUDGETS.get(tier, TIER_BUDGETS["standard"]).copy()
    weights = load_relevance_weights()

    if not weights:
        return base

    total_base = sum(v for k, v in base.items() if k != "total" and v > 0)
    if total_base == 0:
        return base

    adjusted = {"total": base["total"]}
    for key, value in base.items():
        if key == "total" or value == 0:
            adjusted[key] = value
            continue
        scale = weights.get(key, 1.0)  # default 1.0 = keep full if no data
        adjusted[key] = round(value * scale)

    # Redistribute freed tokens to full-budget sections (scale=1.0)
    total_adjusted = sum(v for k, v in adjusted.items() if k != "total")
    freed = total_base - total_adjusted
    if freed > 0:
        full_keys = [k for k in adjusted if k != "total" and weights.get(k, 1.0) >= 1.0 and adjusted[k] > 0]
        if full_keys:
            full_total = sum(adjusted[k] for k in full_keys)
            for k in full_keys:
                share = adjusted[k] / full_total if full_total > 0 else 1.0 / len(full_keys)
                adjusted[k] += round(freed * share)

    return adjusted


def should_suppress_section(section_name: str, task_text: str = "") -> bool:
    """Check if a section should be suppressed before generation.

    Hard-suppressed sections (bottom-5 noise, mean < 0.12) are ALWAYS
    suppressed — no task-containment override.

    Soft-suppressed sections (DYCP_DEFAULT_SUPPRESS) are suppressed only
    when their task-containment is below the override threshold.

    Protected sections are never suppressed.
    """
    if section_name in DYCP_PROTECTED_SECTIONS:
        return False
    # Hard suppress: unconditional — these sections are pure noise
    if section_name in HARD_SUPPRESS:
        return True
    # Soft suppress: can be overridden by task containment
    if section_name not in DYCP_DEFAULT_SUPPRESS:
        return False
    if not task_text:
        return True  # no task context → suppress by default
    containment = _dycp_task_containment_fast(section_name, task_text)
    return containment < DYCP_DEFAULT_SUPPRESS_CONTAINMENT_OVERRIDE


def _dycp_task_containment_fast(section_name: str, task_text: str) -> float:
    """Fast containment check using section name + cached content vs task tokens.

    Checks both the section *name* tokens AND a small sample of actual content
    tokens (cached from the previous brief assembly).  This prevents sections
    with relevant content but non-matching names from being wrongly suppressed.
    """
    task_lower = task_text.lower()
    task_words = set(re.findall(r"[a-z][a-z0-9_]{2,}", task_lower))
    if not task_words:
        return 0.0

    # Name-based score (original heuristic)
    name_words = set(section_name.replace("_", " ").split())
    name_score = (
        len(name_words & task_words) / len(name_words) if name_words else 0.0
    )

    # Content-based score from cache (populated by previous dycp_prune_brief)
    content_tokens = _section_content_cache.get(section_name)
    if content_tokens:
        overlap = len(content_tokens & task_words)
        content_score = overlap / max(1, len(content_tokens))
    else:
        content_score = 0.0

    # Return the higher of the two — either signal is enough to keep
    return max(name_score, content_score)


# Known integration targets for wire-task guidance
KNOWN_TARGETS = {
    "cron_reflection.sh": {
        "path": f"{SCRIPTS}/cron_reflection.sh",
        "structure": "Steps 0.5-7, each runs a python3 script. Add new steps between existing ones.",
        "pattern": '# Step N: Description\necho "[$(date)] Step N: ..." >> "$LOGFILE"\npython3 {}/script.py >> "$LOGFILE" 2>&1 || true'.format(SCRIPTS),
        "insert_hint": "Add between the last numbered step and the digest/cleanup section.",
    },
    "cron_autonomous.sh": {
        "path": f"{SCRIPTS}/cron_autonomous.sh",
        "structure": "3 phases: preflight → execution → postflight. Do NOT edit this bash script directly.",
        "pattern": "Modify heartbeat_preflight.py (add import + call) or heartbeat_postflight.py instead.",
        "insert_hint": "Wire into preflight (before task) or postflight (after task), not the bash orchestrator.",
    },
    "cron_evening.sh": {
        "path": f"{SCRIPTS}/cron_evening.sh",
        "structure": "Sequential sections: PHI_METRIC → CODE_QUALITY → CAPABILITY_ASSESSMENT → RETRIEVAL → SELF_REPORT → DASHBOARD → Claude Code audit → DIGEST.",
        "pattern": '# === SECTION_NAME ===\necho "[$(date)] Section ..." >> "$LOGFILE"\nOUTPUT=$(python3 {}/script.py 2>&1) || true\necho "$OUTPUT" >> "$LOGFILE"'.format(SCRIPTS),
        "insert_hint": "Add new section BEFORE the '# === DIGEST' section (last step).",
    },
    "cron_morning.sh": {
        "path": f"{SCRIPTS}/cron_morning.sh",
        "structure": "Spawns Claude Code with day planning prompt. Pre-run metrics, then Claude Code execution.",
        "pattern": "Add metric collection BEFORE the Claude Code spawn, or post-processing AFTER.",
        "insert_hint": "New metric calls go between 'Morning routine started' and the Claude Code prompt.",
    },
    "cron_evolution.sh": {
        "path": f"{SCRIPTS}/cron_evolution.sh",
        "structure": "Batched preflight (evolution_preflight.py) → Claude Code deep analysis → digest.",
        "pattern": "For new metrics: add to evolution_preflight.py, NOT to this bash script.",
        "insert_hint": "Prefer editing evolution_preflight.py over this orchestrator.",
    },
    "heartbeat_preflight.py": {
        "path": f"{SCRIPTS}/heartbeat_preflight.py",
        "structure": "Sections 1-10 in run_preflight(). Each section has timing + try/except.",
        "pattern": "try:\n    from module import func\nexcept ImportError:\n    func = None\n# In run_preflight(): if func: try: result = func(...) except: pass",
        "insert_hint": "Import at file top with try/except. Call in run_preflight() inside try/except with timing.",
    },
    "heartbeat_postflight.py": {
        "path": f"{SCRIPTS}/heartbeat_postflight.py",
        "structure": "Post-execution steps in run_postflight(). Same pattern as preflight.",
        "pattern": "try:\n    from module import func\nexcept ImportError:\n    func = None\n# In run_postflight(): if func: try: result = func(...) except: pass",
        "insert_hint": "Import at top with try/except. Call in run_postflight() with timing.",
    },
    "cron_strategic_audit.sh": {
        "path": f"{SCRIPTS}/cron_strategic_audit.sh",
        "structure": "Runs Wed+Sat at 15:00. Spawns Claude Code for strategic analysis.",
        "pattern": "Add metric collection before or post-processing after the Claude Code spawn.",
        "insert_hint": "New analysis steps go before the main Claude Code invocation.",
    },
}


def _detect_wire_task(task_text):
    """Detect if a task is a 'wire' strategy task (integration/hooking).

    Returns (is_wire, source_script, target_script) tuple.
    """
    task_lower = task_text.lower()
    wire_verbs = ["wire", "connect", "integrate", "hook", "link", "plug",
                  "add.*to cron", "add.*to heartbeat"]
    if not any(re.search(v, task_lower) for v in wire_verbs):
        return False, None, None

    source = target = None
    m = re.search(
        r'(?:wire|integrate|hook|connect|link|plug)\s+(\S+\.(?:py|sh))\s+'
        r'(?:into|to|with|in)\s+(\S+\.(?:py|sh))', task_lower)
    if m:
        source, target = m.group(1), m.group(2)
    else:
        m = re.search(
            r'add\s+(\S+\.(?:py|sh))\s+(?:into|to|in)\s+(\S+\.(?:py|sh))',
            task_lower)
        if m:
            source, target = m.group(1), m.group(2)
        else:
            m = re.search(
                r'(?:wire|integrate|hook|connect|link|plug)\s+(.+?)\s+'
                r'(?:into|to|with|in)\s+(.+?)(?:\s*[-—,.]|$)', task_lower)
            if m:
                source, target = m.group(1).strip(), m.group(2).strip()

    return True, source, target


def build_wire_guidance(task_text):
    """Generate explicit integration sub-steps for wire tasks.

    Wire tasks historically have ~42% success rate. This guidance provides
    target-specific structure, pre-reads, and time-budgeted sub-steps.
    """
    is_wire, source, target = _detect_wire_task(task_text)
    if not is_wire:
        return ""

    parts = ["WIRE TASK GUIDANCE (wire tasks have ~42% success — follow these steps carefully):"]

    target_found = False
    target_path = None
    if target:
        for known_name, info in KNOWN_TARGETS.items():
            if known_name in (target or ""):
                target_found = True
                target_path = info["path"]
                parts.append(f"  TARGET: {info['path']}")
                parts.append(f"  STRUCTURE: {info['structure']}")
                parts.append(f"  PATTERN: {info['pattern']}")
                parts.append(f"  INSERT_HINT: {info['insert_hint']}")
                break

    if not target_found and target:
        import glob as _glob
        candidates = (_glob.glob(f"{SCRIPTS}/{target}")
                      + _glob.glob(f"{SCRIPTS}/*{target}*"))
        if candidates:
            target_path = candidates[0]
            parts.append(f"  TARGET: {target_path} (auto-detected, read carefully before editing)")

    if target_path and os.path.isfile(target_path):
        try:
            with open(target_path) as f:
                lines = f.readlines()
            if len(lines) > 30:
                snippet_lines = lines[:10] + ["    ...\n"] + lines[-10:]
            else:
                snippet_lines = lines
            snippet = "".join(f"    {l.rstrip()}\n" for l in snippet_lines[:25])
            parts.append(f"  TARGET PREVIEW ({len(lines)} lines total):")
            parts.append(snippet.rstrip())
        except Exception:
            pass

    parts.append("  REQUIRED SUB-STEPS (do each one explicitly, ~3min per step):")
    parts.append("    1. READ the target file — find the exact insertion point (line number). Output: 'Inserting at line N, after <context>'")
    parts.append("    2. READ the source script — find the exact function/class to import and its call signature. Output: 'Will import <func> from <module>, signature: <sig>'")
    parts.append("    3. ADD the import at the top of target (with try/except fallback for resilience)")
    parts.append("    4. ADD the call at the identified insertion point (with try/except + timing if target uses timing)")
    parts.append("    5. TEST: run `python3 -c 'import <module>'` or `bash -n <script>.sh` to verify no syntax errors")
    parts.append("    6. VERIFY: run the target script in test mode (or grep for your added lines) to confirm integration")
    parts.append("  AVOID: Do NOT explore the codebase broadly. The target and source are given — read only those two files.")
    parts.append("  AVOID: Do NOT refactor or improve the source script. Only wire it in.")

    return "\n".join(parts)


def get_failure_patterns(current_task, n=3):
    """Extract failure root causes from episodic memory.

    Returns list of actionable avoidance strings.
    """
    patterns = []
    try:
        from clarvis.memory.episodic_memory import EpisodicMemory
        em = EpisodicMemory()
        failures = em.recall_failures(n=n * 2)
        if not failures:
            return []

        seen = set()
        for ep in failures:
            task_text = ep.get("task", "")
            outcome = ep.get("outcome", "failure")
            error = ep.get("error", "") or ep.get("lesson", "") or ""
            core = error[:60] if error else task_text[:60]
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


def build_decision_context(current_task, tier="standard"):
    """Build decision-context block: success criteria, failure avoidance, constraints.

    Highest-value context — shapes HOW Claude Code approaches the task.
    """
    parts = []

    # Task description — prominent placement for LLM grounding
    # Extract task tag if present (e.g., [SOME_TAG 2026-03-15])
    tag_match = re.match(r'\[([A-Z_]+(?:\s+\d{4}-\d{2}-\d{2})?)\]\s*', current_task)
    task_tag = tag_match.group(1) if tag_match else None
    task_body = current_task[tag_match.end():] if tag_match else current_task
    # Truncate to first 200 chars for the summary line
    task_summary = task_body[:200].strip()
    if task_tag:
        parts.append(f"CURRENT TASK: [{task_tag}] {task_summary}")
    else:
        parts.append(f"CURRENT TASK: {task_summary}")

    # Success criteria from task text
    targets = []
    for m in re.finditer(
        r'(?:target|goal|above|>|improve.*to)\s*[:=]?\s*([0-9.]+[%+]?)',
        current_task, re.IGNORECASE
    ):
        targets.append(m.group(0).strip())
    done_verbs = re.findall(
        r'(?:verify|ensure|confirm|test|check|wire|implement|fix|build|add|create)\s+[^,.]+',
        current_task, re.IGNORECASE
    )
    if done_verbs:
        targets.extend(v.strip()[:60] for v in done_verbs[:3])
    # Also extract "Success criteria:" lines if present
    sc_match = re.search(
        r'[Ss]uccess\s+criteria[:\s]+(.+?)(?:\.\s*\*\*|$)',
        current_task, re.DOTALL
    )
    if sc_match:
        sc_text = sc_match.group(1).strip()[:120]
        if sc_text and sc_text not in targets:
            targets.insert(0, sc_text)
    if targets:
        parts.append("SUCCESS CRITERIA:")
        for t in targets[:5]:
            parts.append(f"  - {t}")

    # Wire guidance
    wire_guidance = build_wire_guidance(current_task)
    if wire_guidance:
        parts.append(wire_guidance)

    # Failure patterns (default-suppressed unless task-relevant)
    if not should_suppress_section("failure_avoidance", current_task):
        failure_patterns = get_failure_patterns(
            current_task, n=3 if tier == "full" else 2
        )
        if failure_patterns:
            parts.append("AVOID THESE FAILURE PATTERNS:")
            parts.extend(failure_patterns)

    # Meta-gradient RL (default-suppressed — mean=0.056 historically)
    if not should_suppress_section("meta_gradient", current_task):
        try:
            from meta_gradient_rl import load_meta_params
            mg_params = load_meta_params()
            explore = mg_params.get("exploration_rate", 0.3)
            weights = mg_params.get("strategy_weights", {})
            best_strategy = max(weights, key=weights.get) if weights else None
            if best_strategy and weights[best_strategy] > 1.2:
                parts.append(
                    f"META-GRADIENT: Prefer '{best_strategy}' strategy "
                    f"(weight={weights[best_strategy]:.2f}), explore={explore:.0%}"
                )
        except Exception:
            pass

    # Weak capabilities warning
    scores = get_latest_scores()
    if scores:
        caps = scores.get("capabilities", {})
        weak_caps = [(k, v) for k, v in caps.items() if v < 0.5]
        if weak_caps:
            weak_names = ", ".join(
                f"{k}={v}" for k, v in sorted(weak_caps, key=lambda x: x[1])
            )
            parts.append(f"WEAK AREAS (be extra careful): {weak_names}")

    return "\n".join(parts)


def build_reasoning_scaffold(tier="standard"):
    """Generate reasoning scaffolding instructions appropriate to the tier."""
    if tier == "full":
        return (
            "APPROACH: Before writing code, briefly analyze:\n"
            "  1. What files need to change and why\n"
            "  2. What could go wrong (check failure patterns above)\n"
            "  3. How to verify success (check criteria above)\n"
            "Then implement, test, and report what you accomplished."
        )
    return (
        "APPROACH: Analyze before implementing. Check the failure patterns above. "
        "Test your changes. Report what you accomplished."
    )


def get_workspace_context(current_task, tier="standard"):
    """Get hierarchical context from the cognitive workspace.

    Returns structured context string, or empty string if workspace is empty.
    """
    try:
        from cognitive_workspace import workspace
        stats = workspace.stats()
        if stats["total_items"] == 0:
            return ""
        budget = 300 if tier == "full" else 180
        return workspace.get_context(budget=budget, task_query=current_task)
    except Exception:
        return ""


def get_spotlight_items(n=5, exclude_task=""):
    """Get top-N attention spotlight items as compact strings.

    Deduplicates similar items and excludes items matching `exclude_task`.
    """
    try:
        from clarvis.cognition.attention import attention
        attention._load()
        focused = attention.focus()
        items = []
        seen_cores = set()
        exclude_words = (
            set(re.findall(r'[a-z]{3,}', exclude_task.lower()))
            if exclude_task else set()
        )
        for item in focused[:n * 3]:
            content = item.get("content", "")
            sal = item.get("salience", 0)
            for prefix in ("CURRENT TASK: ", "TASK: ", "OUTCOME: ", "PROCEDURE HIT "):
                if content.startswith(prefix):
                    content = content[len(prefix):]
                    break
            core = content[:40].lower()
            if core in seen_cores:
                continue
            seen_cores.add(core)
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


def _parse_queue_tasks(content):
    """Parse pending tasks from QUEUE.md with their priority context.

    Returns list of (priority_weight, task_text) tuples.
    Priority weights: P0=1.0, P1=0.7, P2=0.4, unknown=0.5.
    """
    priority_weight = 0.5  # default for tasks before any section header
    results = []

    for line in content.splitlines():
        stripped = line.strip()

        # Track priority from section headers
        header_match = re.match(r'^#{1,3}\s+(.+)$', stripped)
        if header_match:
            header = header_match.group(1)
            if re.search(r'\bP0\b', header):
                priority_weight = 1.0
            elif re.search(r'\bP1\b', header):
                priority_weight = 0.7
            elif re.search(r'\bP2\b', header):
                priority_weight = 0.4
            elif re.match(r'Pillar', header):
                priority_weight = 0.7  # Pillar sections default to P1
            continue

        # Extract pending tasks
        task_match = re.match(r'^- \[ \] (.+)$', stripped)
        if not task_match:
            continue
        task_text = task_match.group(1)
        core = re.split(r'\s*[\(—]', task_text, 1)[0].strip()
        if len(core) < 15:
            core = task_text[:100]
        results.append((priority_weight, core[:80], task_text))

    return results


def _extract_actionable_context(full_text):
    """Extract file paths, function names, and code identifiers from task text.

    Pulls backtick-wrapped content (e.g., `assembly.py`, `run_postflight()`)
    which are the tokens most likely to appear in Claude Code output,
    improving containment scoring for the related_tasks section.

    When no backtick items are found, falls back to extracting technical
    keywords (file-like names, underscore_identifiers, domain terms) that
    Claude Code output is likely to contain.
    """
    items = []
    seen = set()

    # 1. Extract backtick-wrapped tokens (highest signal)
    backtick_items = re.findall(r'`([^`]+)`', full_text)
    for item in backtick_items:
        if item not in seen and len(item) > 2:
            seen.add(item)
            items.append(item)

    # 2. Extract file-like tokens (foo.py, bar.sh, baz.json, etc.)
    file_like = re.findall(r'\b[\w/.-]+\.(?:py|sh|js|ts|json|md|yaml|yml|toml)\b', full_text)
    for item in file_like:
        if item not in seen:
            seen.add(item)
            items.append(item)

    # 3. Extract underscore_identifiers (function/variable names: run_postflight, brain_health)
    underscore_ids = re.findall(r'\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b', full_text)
    for item in underscore_ids:
        if item not in seen and len(item) > 5:
            seen.add(item)
            items.append(item)

    # 4. Extract CamelCase identifiers (class names: ChromaDB, ClarvisDB, MiniLM)
    camel_ids = re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-zA-Z]*)+\b', full_text)
    for item in camel_ids:
        if item not in seen:
            seen.add(item)
            items.append(item)

    # 5. If no code identifiers found, extract domain keywords from full text
    #    that Claude Code output is likely to contain (4+ char words, no stopwords)
    if not items:
        _stop = {"the", "and", "for", "are", "but", "not", "you", "all", "can",
                 "had", "was", "one", "our", "out", "has", "have", "from",
                 "with", "this", "that", "they", "been", "will", "each", "make",
                 "like", "into", "than", "its", "also", "use", "how", "what",
                 "when", "where", "which", "there", "still", "just", "only",
                 "should", "would", "could", "very", "more", "most", "some",
                 "other", "about", "after", "before", "ensure", "implement",
                 "produce", "raise", "current", "today", "blocks", "public",
                 "hard", "list", "finish", "execute", "around"}
        words = re.findall(r'[a-z]{4,}', full_text.lower())
        domain = []
        seen_kw = set()
        for w in words:
            if w not in _stop and w not in seen_kw:
                seen_kw.add(w)
                domain.append(w)
        if domain:
            items = domain[:5]

    if not items:
        return ""
    return " [" + ", ".join(items[:5]) + "]"


def _enrich_task(core, full_text, max_len=200):
    """Return core enriched with actionable context from full_text."""
    context = _extract_actionable_context(full_text)
    enriched = core + context
    return enriched[:max_len]


def _cosine_similarity(a, b):
    """Compute cosine similarity between two vectors."""
    import numpy as np
    a, b = np.asarray(a), np.asarray(b)
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    return float(dot / norm) if norm > 0 else 0.0


def _semantic_rank(current_task, parsed_tasks, embed_fn):
    """Rank tasks by semantic similarity using embeddings + priority weight."""
    texts = [current_task] + [t[2] for t in parsed_tasks]
    embeddings = embed_fn(texts)
    query_emb = embeddings[0]

    scored = []
    for i, (priority_w, core, _full) in enumerate(parsed_tasks):
        sim = _cosine_similarity(query_emb, embeddings[i + 1])
        # Skip near-duplicates (same task)
        if sim > 0.9:
            continue
        # Skip distant matches — only include tasks with meaningful similarity
        if sim < 0.3:
            continue
        # Combined score: semantic similarity * priority weight
        score = sim * priority_w
        if score > 0.05:
            scored.append((score, _enrich_task(core, _full)))

    scored.sort(reverse=True)
    return scored


def _word_overlap_rank(current_task, parsed_tasks):
    """Fallback: rank tasks by word overlap (original Jaccard approach)."""
    task_words = set(re.findall(r'[a-z]{3,}', current_task.lower()))
    if not task_words:
        return []

    scored = []
    for priority_w, core, full_text in parsed_tasks:
        candidate_words = set(re.findall(r'[a-z]{3,}', full_text.lower()))
        if not candidate_words:
            continue
        jaccard = len(task_words & candidate_words) / max(1, len(task_words | candidate_words))
        if jaccard > 0.6:
            continue  # skip near-duplicates
        relevance = len(task_words & candidate_words) / max(1, len(candidate_words))
        if relevance > 0.1:
            scored.append((relevance * priority_w, _enrich_task(core, full_text)))

    scored.sort(reverse=True)
    return scored


def find_related_tasks(current_task, queue_file=None, max_tasks=3):
    """Find pending tasks related to the current task using semantic similarity.

    Uses ONNX MiniLM embeddings for semantic matching with priority weighting.
    Falls back to word-overlap Jaccard if embeddings are unavailable.
    """
    queue_file = queue_file or QUEUE_FILE
    if not current_task or not os.path.exists(queue_file):
        return []

    with open(queue_file, 'r') as f:
        content = f.read()

    parsed = _parse_queue_tasks(content)
    if not parsed:
        return []

    # Try semantic ranking with brain embeddings
    try:
        from clarvis.brain.factory import get_embedding_function
        embed_fn = get_embedding_function(use_onnx=True)
        if embed_fn is not None:
            scored = _semantic_rank(current_task, parsed, embed_fn)
            return [text for _, text in scored[:max_tasks]]
    except Exception:
        pass

    # Fallback to word overlap
    scored = _word_overlap_rank(current_task, parsed)
    return [text for _, text in scored[:max_tasks]]


def rerank_episodes_by_task(episodic_hints: str, current_task: str) -> str:
    """Re-rank episode lines by combined recency + task similarity.

    Episodes come as pre-compressed text lines. This function parses them,
    scores each by task-token overlap (content relevance) and position
    (recency proxy), then returns them sorted by combined score.

    Lines that share more tokens with the current task float to the top.
    This improves episodes section relevance from ~0.27 baseline.
    """
    if not episodic_hints or not current_task:
        return episodic_hints

    lines = [l for l in episodic_hints.strip().split('\n') if l.strip()]
    if len(lines) <= 1:
        return episodic_hints

    # Separate header/separator lines from episode content lines
    episode_lines = []
    other_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('[') or stripped.startswith('Episode:') or (
            len(stripped) > 20 and not stripped.startswith('---')
        ):
            episode_lines.append(line)
        else:
            other_lines.append(line)

    if len(episode_lines) <= 1:
        return episodic_hints

    # Score each episode line by task-token overlap + recency (position)
    task_tokens = set(re.findall(r'[a-z][a-z0-9_]{2,}', current_task.lower()))
    _sw = {"the", "and", "for", "are", "but", "not", "you", "all", "can",
           "had", "was", "one", "our", "out", "has", "have", "from",
           "with", "this", "that", "they", "been", "will", "each", "make",
           "like", "into", "than", "its", "also", "use", "two", "how"}
    task_tokens -= _sw

    scored = []
    n_eps = len(episode_lines)
    for i, line in enumerate(episode_lines):
        ep_tokens = set(re.findall(r'[a-z][a-z0-9_]{2,}', line.lower())) - _sw
        if task_tokens and ep_tokens:
            overlap = len(task_tokens & ep_tokens) / max(1, len(task_tokens))
        else:
            overlap = 0.0
        # Recency bonus: later episodes (higher index = more recent) get a boost
        recency = (i + 1) / n_eps  # 0..1
        # Combined: 60% task similarity, 40% recency
        combined = 0.6 * overlap + 0.4 * recency
        scored.append((combined, line))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Rebuild: other_lines first (headers), then sorted episodes
    result = other_lines + [line for _, line in scored]
    return '\n'.join(result)


def get_recent_completions(queue_file=None, n=3):
    """Get the N most recent completed tasks as compact 1-liners."""
    queue_file = queue_file or QUEUE_FILE
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

    return completions[:n]


def _dycp_task_containment(section_text: str, task_text: str) -> float:
    """Compute bidirectional containment between section and task tokens.

    Returns max(section_in_task, task_in_section) — captures relevance
    regardless of which text is larger.
    """
    sec_tokens = set(re.findall(r"[a-z][a-z0-9_]{2,}", section_text.lower()))
    task_tokens = set(re.findall(r"[a-z][a-z0-9_]{2,}", task_text.lower()))
    # Remove stopwords
    _sw = {"the", "and", "for", "are", "but", "not", "you", "all", "can",
           "had", "her", "was", "one", "our", "out", "has", "have", "from",
           "with", "this", "that", "they", "been", "will", "each", "make",
           "like", "into", "than", "its", "also", "use", "two", "how"}
    sec_tokens -= _sw
    task_tokens -= _sw
    if not sec_tokens or not task_tokens:
        return 0.0
    sec_in_task = len(sec_tokens & task_tokens) / len(sec_tokens)
    task_in_sec = len(sec_tokens & task_tokens) / len(task_tokens)
    return max(sec_in_task, task_in_sec)


def _load_historical_section_means() -> dict:
    """Load per-section historical mean relevance scores.

    Returns dict mapping section_name → mean_relevance, or empty dict on error.
    """
    try:
        from clarvis.cognition.context_relevance import aggregate_relevance
        agg = aggregate_relevance(days=14)
        if agg.get("episodes", 0) >= 5:
            return agg.get("per_section_mean", {})
    except Exception:
        pass
    return {}


def dycp_prune_brief(brief_text: str, task_text: str) -> str:
    """Dynamic Context Pruning — remove sections irrelevant to the current task.

    Inspired by DyCP (arXiv:2601.07994): query-dependent segment-level pruning.
    Each section is scored against the task query using token containment.
    Sections that are both historically low-relevance AND have low task-overlap
    are pruned to reduce noise in the context.

    Protected sections (decision_context, reasoning, knowledge, etc.) are
    never pruned — they carry critical task-shaping information.

    Args:
        brief_text: The assembled context brief (with section markers).
        task_text: The current task description.

    Returns:
        Pruned brief text with irrelevant sections removed.
    """
    if not brief_text or not task_text:
        return brief_text

    try:
        from clarvis.cognition.context_relevance import parse_brief_sections
    except ImportError:
        return brief_text

    sections = parse_brief_sections(brief_text)
    if len(sections) <= 3:
        return brief_text  # too few sections to prune

    # Update the content cache so future _dycp_task_containment_fast calls
    # (in should_suppress_section) consider actual section content.
    _sw = {"the", "and", "for", "are", "but", "not", "you", "all", "can",
           "had", "was", "one", "our", "out", "has", "have", "from",
           "with", "this", "that", "they", "been", "will", "each", "make",
           "like", "into", "than", "its", "also", "use", "two", "how"}
    global _section_content_cache
    new_cache = {}
    for sname, scontent in sections.items():
        tokens = set(re.findall(r"[a-z][a-z0-9_]{2,}", scontent.lower())) - _sw
        # Sample up to _CONTENT_SAMPLE_SIZE tokens (sorted for determinism)
        if len(tokens) > _CONTENT_SAMPLE_SIZE:
            tokens = set(sorted(tokens)[:_CONTENT_SAMPLE_SIZE])
        new_cache[sname] = tokens
    _section_content_cache = new_cache

    historical = _load_historical_section_means()
    pruned_names = set()

    for name, content in sections.items():
        if name in DYCP_PROTECTED_SECTIONS:
            continue
        # Compute task-relevance via containment.
        # Include section name in content so header keywords count
        # (parse_brief_sections strips the header line).
        enriched = f"{name.replace('_', ' ')} {content}"
        containment = _dycp_task_containment(enriched, task_text)
        if containment >= DYCP_MIN_CONTAINMENT:
            continue  # section has task-relevant content, keep it
        # Check historical performance
        hist_score = historical.get(name, 0.5)  # default=keep if no data
        # Tier 0 (aggressive): Historical mean < 0.15 → always stub-collapse
        # regardless of task containment. These sections are chronic noise;
        # even marginal containment hits don't justify full rendering.
        if hist_score < 0.15:
            pruned_names.add(name)
        # Tier 1: Historically weak sections with low task overlap → prune
        elif hist_score < DYCP_HISTORICAL_FLOOR:
            pruned_names.add(name)
        # Tier 2 (DyCP query-dependent): Zero overlap + borderline history → prune
        elif containment == 0.0 and hist_score < DYCP_ZERO_OVERLAP_CEILING:
            pruned_names.add(name)

    if not pruned_names:
        return brief_text

    # Rebuild brief: pruned sections become 1-line stubs (preserves signal,
    # removes noise). Stubs let the LLM know the section exists without
    # the token cost of full rendering.
    lines = brief_text.split("\n")
    from clarvis.cognition.context_relevance import _SECTION_MARKERS
    result_lines = []
    current_section = None
    skip_until_next = False

    for line in lines:
        # Check if this line starts a new section
        new_section = None
        for sname, pattern in _SECTION_MARKERS:
            if pattern.search(line):
                new_section = sname
                break

        if new_section is not None:
            current_section = new_section
            skip_until_next = current_section in pruned_names
            if skip_until_next:
                # Emit a 1-line stub instead of the full section
                hist_score = historical.get(current_section, 0.0)
                result_lines.append(
                    f"[{current_section}: pruned — hist_relevance={hist_score:.2f}]"
                )
                continue
        elif line.strip() == "---":
            # Separator — don't skip, but reset skip state
            skip_until_next = False

        if not skip_until_next:
            result_lines.append(line)

    # Clean up consecutive --- separators and trailing ---
    cleaned = []
    for line in result_lines:
        if line.strip() == "---" and cleaned and cleaned[-1].strip() == "---":
            continue
        cleaned.append(line)
    # Remove trailing ---
    while cleaned and cleaned[-1].strip() == "---":
        cleaned.pop()

    return "\n".join(cleaned)


def generate_tiered_brief(
    current_task,
    tier="standard",
    episodic_hints="",
    knowledge_hints="",
    queue_file=None,
):
    """Generate a quality-optimized context brief using primacy/recency positioning.

    Ordering follows LLM attention research (Liu et al. "Lost in the Middle"):
      BEGINNING (highest attention): Decision context — success criteria, failure
          avoidance, constraints.
      MIDDLE (lower attention): Metrics, related tasks, completions.
      END (high attention): Episodic lessons + reasoning scaffold.

    Args:
        current_task: The task being executed.
        tier: "minimal" | "standard" | "full" — controls depth.
        episodic_hints: Pre-compressed episode text.
        knowledge_hints: Brain knowledge text.
        queue_file: Path to QUEUE.md (default: auto-detected).

    Returns:
        Quality-optimized context string.
    """
    queue_file = queue_file or QUEUE_FILE
    budget = get_adjusted_budgets(tier)
    beginning = []
    middle = []
    end = []

    # === BEGINNING — High attention zone ===

    # Decision Context (success criteria + failure avoidance)
    if budget.get("decision_context", 0) > 0:
        decision_ctx = build_decision_context(current_task, tier=tier)
        if decision_ctx:
            beginning.append(decision_ctx)

    # Brain Knowledge
    if knowledge_hints and tier != "minimal":
        beginning.append("RELEVANT KNOWLEDGE:")
        max_chars = 600 if tier == "full" else 350
        if len(knowledge_hints) > max_chars * 1.5:
            compressed_knowledge, _ = compress_text(knowledge_hints, ratio=0.3)
            beginning.append(compressed_knowledge[:max_chars])
        else:
            beginning.append(knowledge_hints[:max_chars])

    # Working Memory (Cognitive Workspace + Spotlight fallback)
    if budget["spotlight"] > 0:
        workspace_ctx = get_workspace_context(current_task, tier=tier)
        if workspace_ctx:
            ws_budget = 500 if tier == "full" else 300
            if len(workspace_ctx) > ws_budget * 1.5:
                workspace_ctx, _ = compress_text(workspace_ctx, ratio=0.3)
            beginning.append(workspace_ctx[:ws_budget])
        else:
            n_items = 5 if tier == "full" else 3
            spotlight = get_spotlight_items(n=n_items, exclude_task=current_task)
            if spotlight:
                beginning.append("WORKING MEMORY:")
                beginning.extend(spotlight[:n_items])

    # === MIDDLE — Lower attention zone ===

    # Related Pending Tasks
    if budget["related_tasks"] > 0:
        n_related = 3 if tier == "full" else 2
        related = find_related_tasks(current_task, queue_file, max_tasks=n_related)
        if related:
            middle.append("RELATED TASKS:")
            for t in related:
                middle.append(f"  - {t}")

    # Metrics — folded into decision_context as a compact one-liner (2026-03-18).
    # Previously a standalone middle section; mean relevance=0.100 suggested it
    # was noise on its own but the Phi score is useful alongside decision context.
    if not should_suppress_section("metrics", current_task):
        scores = get_latest_scores()
        if scores:
            phi = scores.get("phi", "?")
            if "capabilities" in scores:
                caps = scores["capabilities"]
                worst_k = min(caps, key=caps.get) if caps else "?"
                worst_v = caps.get(worst_k, "?") if caps else "?"
                beginning.append(f"METRICS: Phi={phi}, worst={worst_k}={worst_v}")
            else:
                beginning.append(f"METRICS: Phi={phi}")

    # Recent Completions
    if budget["completions"] > 0:
        n_comp = 3 if tier == "full" else 2
        completions = get_recent_completions(queue_file, n=n_comp)
        if completions:
            middle.append("RECENT:")
            middle.extend(completions)

    # === END — High attention zone ===

    # Episodic Lessons — reranked by task similarity + recency
    if budget["episodes"] > 0 and episodic_hints:
        ranked_episodes = rerank_episodes_by_task(episodic_hints, current_task)
        max_chars = budget["episodes"] * 4
        if len(ranked_episodes) > max_chars * 1.5:
            compressed_episodes, _ = compress_text(ranked_episodes, ratio=0.3)
            end.append(compressed_episodes[:max_chars])
        else:
            end.append(ranked_episodes[:max_chars])

    # Reasoning Scaffold
    if budget.get("reasoning_scaffold", 0) > 0:
        scaffold = build_reasoning_scaffold(tier=tier)
        end.append(scaffold)

    # Assemble: beginning → middle → end
    parts = beginning
    if middle:
        parts.append("---")
        parts.extend(middle)
    if end:
        parts.append("---")
        parts.extend(end)

    assembled = "\n".join(parts)

    # DyCP: Query-dependent pruning — remove sections irrelevant to this task
    if tier != "minimal":
        assembled = dycp_prune_brief(assembled, current_task)

    return assembled
