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

# Token budgets per tier (attention-optimal allocation)
TIER_BUDGETS = {
    "minimal": {
        "total": 200,
        "decision_context": 0,
        "spotlight": 0,
        "related_tasks": 0,
        "metrics": 0,
        "completions": 0,
        "episodes": 0,
        "reasoning_scaffold": 0,
    },
    "standard": {
        "total": 600,
        "decision_context": 100,
        "spotlight": 80,
        "related_tasks": 60,
        "metrics": 40,
        "completions": 40,
        "episodes": 60,
        "reasoning_scaffold": 40,
    },
    "full": {
        "total": 1000,
        "decision_context": 150,
        "spotlight": 120,
        "related_tasks": 100,
        "metrics": 80,
        "completions": 60,
        "episodes": 120,
        "reasoning_scaffold": 60,
    },
}

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
    if targets:
        parts.append("SUCCESS CRITERIA:")
        for t in targets[:4]:
            parts.append(f"  - {t}")

    # Wire guidance
    wire_guidance = build_wire_guidance(current_task)
    if wire_guidance:
        parts.append(wire_guidance)

    # Failure patterns
    failure_patterns = get_failure_patterns(
        current_task, n=3 if tier == "full" else 2
    )
    if failure_patterns:
        parts.append("AVOID THESE FAILURE PATTERNS:")
        parts.extend(failure_patterns)

    # Meta-gradient RL
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


def find_related_tasks(current_task, queue_file=None, max_tasks=3):
    """Find pending tasks related to the current task by word overlap."""
    queue_file = queue_file or QUEUE_FILE
    if not current_task or not os.path.exists(queue_file):
        return []

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
        candidate_words = set(re.findall(r'[a-z]{3,}', task_text.lower()))
        if not candidate_words:
            continue
        overlap = len(task_words & candidate_words) / max(1, len(task_words | candidate_words))
        if overlap > 0.6:
            continue
        relevance = len(task_words & candidate_words) / max(1, len(candidate_words))
        if relevance > 0.1:
            core = re.split(r'\s*[\(—]', task_text, 1)[0].strip()
            if len(core) < 15:
                core = task_text[:100]
            candidates.append((relevance, core[:80]))

    candidates.sort(reverse=True)
    return [text for _, text in candidates[:max_tasks]]


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
    budget = TIER_BUDGETS.get(tier, TIER_BUDGETS["standard"])
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

    # Metrics
    if budget["metrics"] > 0:
        scores = get_latest_scores()
        if scores:
            if tier == "full" and "capabilities" in scores:
                caps = scores["capabilities"]
                worst_k = min(caps, key=caps.get) if caps else "?"
                worst_v = caps.get(worst_k, "?") if caps else "?"
                middle.append(
                    f"METRICS: Phi={scores.get('phi', '?')}, "
                    f"cap_avg={scores.get('capability_avg', '?')}, "
                    f"worst={worst_k}={worst_v}"
                )
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

    # Recent Completions
    if budget["completions"] > 0:
        n_comp = 3 if tier == "full" else 2
        completions = get_recent_completions(queue_file, n=n_comp)
        if completions:
            middle.append("RECENT:")
            middle.extend(completions)

    # === END — High attention zone ===

    # Episodic Lessons
    if budget["episodes"] > 0 and episodic_hints:
        max_chars = budget["episodes"] * 4
        if len(episodic_hints) > max_chars * 1.5:
            compressed_episodes, _ = compress_text(episodic_hints, ratio=0.3)
            end.append(compressed_episodes[:max_chars])
        else:
            end.append(episodic_hints[:max_chars])

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

    return "\n".join(parts)
