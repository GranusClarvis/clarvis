"""
Context Assembly — attention-optimal context brief generation.

Migrated from scripts/context_compressor.py (the advanced assembly functions).
Provides decision context, failure patterns, wire guidance, reasoning scaffold,
workspace/spotlight integration, and the full tiered brief generator.

Usage:
    from clarvis.context.assembly import generate_tiered_brief
    brief = generate_tiered_brief("my task", tier="standard")
"""

import logging
import os
import re
from .compressor import compress_text, get_latest_scores
from .budgets import (  # noqa: F401 — re-exported for backward compat
    BUDGET_TO_SECTIONS as _BUDGET_TO_SECTIONS,
    TIER_BUDGETS, RECENCY_BOOST_EPISODES,
    MIN_EPISODES_FOR_ADJUSTMENT,
    load_relevance_weights, get_adjusted_budgets,
    load_section_relevance_weights,
)
from .dycp import (  # noqa: F401 — re-exported for backward compat
    DYCP_PROTECTED_SECTIONS, DYCP_MIN_CONTAINMENT, DYCP_HISTORICAL_FLOOR,
    DYCP_ZERO_OVERLAP_CEILING, HARD_SUPPRESS, DYCP_DEFAULT_SUPPRESS,
    DYCP_DEFAULT_SUPPRESS_CONTAINMENT_OVERRIDE,
    DYNAMIC_SUPPRESS_THRESHOLD, DYNAMIC_SOFT_SUPPRESS_CEILING,
    should_suppress_section, dycp_prune_brief,
    rerank_knowledge_hints, _extract_task_keywords,
)
try:
    from .knowledge_synthesis import synthesize_knowledge
except ImportError:
    synthesize_knowledge = None

try:
    from clarvis.cognition.conceptual_framework import get_relevant_frameworks
except ImportError:
    get_relevant_frameworks = None

logger = logging.getLogger(__name__)

WORKSPACE = os.environ.get(
    "CLARVIS_WORKSPACE", os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
)
SCRIPTS = os.path.join(WORKSPACE, "scripts")
QUEUE_FILE = os.path.join(WORKSPACE, "memory/evolution/QUEUE.md")


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
            logger.debug("Failed to read target preview", exc_info=True)

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
        logger.debug("Failed to load failure patterns", exc_info=True)
    return patterns


def _extract_success_criteria(task_text):
    """Extract success criteria from task text: numeric targets + action verbs."""
    targets = []
    for m in re.finditer(
        r'(?:target|goal|above|>|improve.*to)\s*[:=]?\s*([0-9.]+[%+]?)',
        task_text, re.IGNORECASE
    ):
        targets.append(m.group(0).strip())
    done_verbs = re.findall(
        r'(?:verify|ensure|confirm|test|check|wire|implement|fix|build|add|create)\s+[^,.]+',
        task_text, re.IGNORECASE
    )
    if done_verbs:
        targets.extend(v.strip()[:60] for v in done_verbs[:3])
    sc_match = re.search(
        r'[Ss]uccess\s+criteria[:\s]+(.+?)(?:\.\s*\*\*|$)',
        task_text, re.DOTALL
    )
    if sc_match:
        sc_text = sc_match.group(1).strip()[:120]
        if sc_text and sc_text not in targets:
            targets.insert(0, sc_text)
    return targets


def _get_supplementary_hints(current_task, tier):
    """Get meta-gradient hint + weak capabilities warning."""
    hints = []
    # Meta-gradient RL (default-suppressed — mean=0.056 historically)
    if not should_suppress_section("meta_gradient", current_task):
        try:
            from meta_gradient_rl import load_meta_params
            mg_params = load_meta_params()
            explore = mg_params.get("exploration_rate", 0.3)
            weights = mg_params.get("strategy_weights", {})
            best_strategy = max(weights, key=weights.get) if weights else None
            if best_strategy and weights[best_strategy] > 1.2:
                hints.append(
                    f"META-GRADIENT: Prefer '{best_strategy}' strategy "
                    f"(weight={weights[best_strategy]:.2f}), explore={explore:.0%}"
                )
        except Exception:
            logger.debug("Failed to load meta-gradient params", exc_info=True)

    scores = get_latest_scores()
    if scores:
        caps = scores.get("capabilities", {})
        weak_caps = [(k, v) for k, v in caps.items() if v < 0.5]
        if weak_caps:
            weak_names = ", ".join(
                f"{k}={v}" for k, v in sorted(weak_caps, key=lambda x: x[1])
            )
            hints.append(f"WEAK AREAS (be extra careful): {weak_names}")
    return hints


_DOMAIN_STOP = {
    "this", "that", "with", "from", "have", "been", "will", "each",
    "make", "like", "into", "than", "also", "when", "what", "which",
    "their", "them", "then", "there", "these", "those", "they", "were",
    "would", "could", "should", "about", "after", "before", "above",
    "below", "between", "through", "during", "within", "without",
    "does", "done", "doing", "only", "just", "more", "most", "some",
    "such", "very", "much", "many", "here", "where", "over", "under",
    "file", "task", "current", "added", "based", "using", "currently",
}


def _extract_output_vocabulary(task_text, task_tag=None):
    """Extract output-vocabulary keywords for context_relevance containment scoring.

    Extracts file paths, function names, numeric targets, domain vocabulary,
    and tag words from the task text.
    """
    vocab_tokens = []
    vocab_tokens.extend(re.findall(r'`([^`]+)`', task_text))
    vocab_tokens.extend(
        re.findall(r'\b[\w/.-]+\.(?:py|sh|js|ts|json|md|yaml)\b', task_text)
    )
    vocab_tokens.extend(
        t for t in re.findall(r'\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b', task_text)
        if len(t) > 5
    )
    vocab_tokens.extend(re.findall(r'[≥≤><]?\s*\d+\.\d+', task_text))
    vocab_tokens.extend(re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-zA-Z]*)+\b', task_text))
    vocab_tokens.extend(re.findall(r'\b[A-Z]{2,6}\b', task_text))
    domain_words = re.findall(r'\b[a-z]{4,}\b', task_text.lower())
    vocab_tokens.extend(w for w in domain_words if w not in _DOMAIN_STOP)
    if task_tag:
        tag_name = re.sub(r'\s+\d{4}-\d{2}-\d{2}$', '', task_tag)
        tag_words = [w.lower() for w in tag_name.split("_") if len(w) >= 4]
        vocab_tokens.extend(tag_words)
    vocab_tokens.extend(re.findall(r'\b[a-z]+-[a-z]+\b', task_text.lower()))
    # Deduplicate while preserving order
    seen_vocab = set()
    unique_vocab = []
    for t in vocab_tokens:
        t = t.strip()
        if t and t not in seen_vocab and len(t) > 2:
            seen_vocab.add(t)
            unique_vocab.append(t)
    return unique_vocab


def build_decision_context(current_task, tier="standard"):
    """Build decision-context block: success criteria, failure avoidance, constraints.

    Highest-value context — shapes HOW Claude Code approaches the task.
    """
    parts = []

    # Task description — prominent placement for LLM grounding
    tag_match = re.match(r'\[([A-Z0-9_]+(?:\s+\d{4}-\d{2}-\d{2})?)\]\s*', current_task)
    task_tag = tag_match.group(1) if tag_match else None
    task_body = current_task[tag_match.end():] if tag_match else current_task
    task_summary = task_body[:200].strip()
    if task_tag:
        parts.append(f"CURRENT TASK: [{task_tag}] {task_summary}")
    else:
        parts.append(f"CURRENT TASK: {task_summary}")

    targets = _extract_success_criteria(current_task)
    if targets:
        parts.append("SUCCESS CRITERIA:")
        for t in targets[:5]:
            parts.append(f"  - {t}")

    wire_guidance = build_wire_guidance(current_task)
    if wire_guidance:
        parts.append(wire_guidance)

    if not should_suppress_section("failure_avoidance", current_task):
        failure_patterns = get_failure_patterns(
            current_task, n=3 if tier == "full" else 2
        )
        if failure_patterns:
            parts.append("AVOID THESE FAILURE PATTERNS:")
            parts.extend(failure_patterns)

    parts.extend(_get_supplementary_hints(current_task, tier))

    vocab = _extract_output_vocabulary(current_task, task_tag)
    if vocab:
        parts.append("KEY TERMS: " + ", ".join(vocab[:15]))

    return "\n".join(parts)


def _classify_task_type(task_text):
    """Classify a task into a type for scaffold selection.

    Returns one of: 'code', 'research', 'maintenance', 'generic'.
    """
    t = task_text.lower()

    # Code indicators: file references, programming verbs, code artifacts
    code_signals = (
        re.search(r'\.(py|sh|js|ts|json|yaml|toml)\b', t)
        or re.search(r'\b(implement|refactor|wire|add.*section|fix.*bug|edit|write.*code|function|class|import|module)\b', t)
        or re.search(r'\b(assembly\.py|postflight|preflight|cron_|brain\.py)\b', t)
    )
    # Research indicators
    research_signals = re.search(
        r'\b(research|survey|read.*paper|literature|arxiv|compare.*approaches|'
        r'evaluate.*options|investigate|explore.*alternatives|state.of.the.art)\b', t
    )
    # Maintenance indicators
    maint_signals = re.search(
        r'\b(audit|cleanup|prune|compact|vacuum|backup|verify|health|migrate|'
        r'dedup|archive|rotate|benchmark|validate|check.*integrity)\b', t
    )

    if code_signals:
        return "code"
    if research_signals:
        return "research"
    if maint_signals:
        return "maintenance"
    return "generic"


# Task-type-specific reasoning scaffolds.
# Each scaffold primes the agent with steps relevant to that task type,
# increasing the token overlap between the scaffold and the agent's output.
_SCAFFOLDS = {
    "code": {
        "full": (
            "APPROACH: Before writing code, briefly analyze:\n"
            "  1. What files need to change and why\n"
            "  2. What could go wrong (check failure patterns above)\n"
            "  3. How to verify success (check criteria above)\n"
            "Then implement, test, and report what you accomplished."
        ),
        "standard": (
            "APPROACH: Break this into the smallest possible steps. "
            "Complete and verify each step before moving to the next. "
            "If time is short, deliver the most impactful step fully done."
        ),
    },
    "research": {
        "full": (
            "APPROACH: Research systematically:\n"
            "  1. Define what you need to learn and why\n"
            "  2. Search existing brain/memory first (avoid redundant research)\n"
            "  3. Gather evidence from multiple sources, note contradictions\n"
            "  4. Synthesize findings into actionable recommendations\n"
            "  5. Store key learnings in brain for future retrieval\n"
            "Prioritize depth over breadth. Cite sources."
        ),
        "standard": (
            "APPROACH: Search existing knowledge first. "
            "Gather evidence, note contradictions, synthesize into actionable findings. "
            "Store key learnings in brain."
        ),
    },
    "maintenance": {
        "full": (
            "APPROACH: Maintenance protocol:\n"
            "  1. Assess current state — measure before changing\n"
            "  2. Identify what needs fixing (check health, stats, logs)\n"
            "  3. Apply fixes incrementally — verify each step\n"
            "  4. Measure after — confirm improvement vs baseline\n"
            "  5. Document what changed and why\n"
            "Do not over-optimize. Fix what is broken, leave what works."
        ),
        "standard": (
            "APPROACH: Measure before changing. Fix incrementally, verify each step. "
            "Measure after to confirm improvement. Don't over-optimize."
        ),
    },
    "generic": {
        "full": (
            "APPROACH: Before writing code, briefly analyze:\n"
            "  1. What files need to change and why\n"
            "  2. What could go wrong (check failure patterns above)\n"
            "  3. How to verify success (check criteria above)\n"
            "Then implement, test, and report what you accomplished."
        ),
        "standard": (
            "APPROACH: Analyze before implementing. Check the failure patterns above. "
            "Test your changes. Report what you accomplished."
        ),
    },
}


def build_reasoning_scaffold(tier="standard", task_text=""):
    """Generate task-type-specific reasoning scaffolding.

    Classifies the task as code/research/maintenance/generic and returns
    a scaffold tuned for that task type, improving reasoning section relevance.
    """
    task_type = _classify_task_type(task_text) if task_text else "generic"
    scaffold_tier = "full" if tier == "full" else "standard"
    return _SCAFFOLDS[task_type][scaffold_tier]


def get_workspace_context(current_task, tier="standard"):
    """Get hierarchical context from the cognitive workspace.

    Returns structured context string, or empty string if workspace is empty.
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
    """Parse pending and in-progress tasks from QUEUE.md with priority + milestone.

    Returns list of (priority_weight, core_text, full_text, milestone, status) tuples.
    Priority weights: P0=1.0, P1=0.7, P2=0.4, unknown=0.5.
    Status: 'pending' for [ ], 'in-progress' for [~].
    """
    priority_weight = 0.5  # default for tasks before any section header
    milestone = ""
    results = []

    for line in content.splitlines():
        stripped = line.strip()

        # Track priority and milestone from section headers
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
                priority_weight = 0.7
            # Extract milestone name (e.g., "Milestone B — Brain / Context Quality")
            ms_match = re.search(r'(Milestone\s+\w(?:\s*[-—]\s*[^(]+)?)', header)
            if ms_match:
                milestone = ms_match.group(1).strip()[:40]
            elif re.search(r'\bP[012]\b', header):
                milestone = header.strip()[:40]
            continue

        # Extract pending [ ] and in-progress [~] tasks
        task_match = re.match(r'^- \[( |~)\] (.+)$', stripped)
        if not task_match:
            continue
        status = "in-progress" if task_match.group(1) == "~" else "pending"
        task_text = task_match.group(2)
        core = re.split(r'\s*[\(—]', task_text, 1)[0].strip()
        if len(core) < 15:
            core = task_text[:100]
        results.append((priority_weight, core[:80], task_text, milestone, status))

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


def _extract_shared_artifacts(current_task, related_task):
    """Find file paths, functions, and identifiers shared between two tasks."""
    def _extract_ids(text):
        ids = set()
        # Backtick items
        ids.update(re.findall(r'`([^`]+)`', text))
        # File-like tokens
        ids.update(re.findall(r'\b[\w/.-]+\.(?:py|sh|js|ts|json|md)\b', text))
        # underscore_identifiers
        ids.update(i for i in re.findall(r'\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b', text)
                   if len(i) > 5)
        return ids

    current_ids = _extract_ids(current_task)
    related_ids = _extract_ids(related_task)
    return current_ids & related_ids


def _format_related_task(core, full_text, milestone, status, shared, max_len=200):
    """Format a related task with relationship context for high token overlap."""
    # Extract task tag from full_text
    tag_match = re.search(r'\[([A-Z_]+)\]', full_text)
    tag_str = tag_match.group(1) if tag_match else ""

    # Strip tag from core if already present (avoid duplication)
    if tag_str and f"[{tag_str}]" in core:
        core = core.replace(f"[{tag_str}]", "").strip()

    # Status prefix
    status_prefix = "[~] " if status == "in-progress" else ""

    # Build relationship annotation
    parts = []
    if shared:
        parts.append("shares: " + ", ".join(sorted(shared)[:3]))
    if milestone:
        parts.append(milestone)
    annotation = " (" + "; ".join(parts) + ")" if parts else ""

    # Enrich with actionable context from full text
    context = _extract_actionable_context(full_text)

    tag_prefix = f"[{tag_str}] " if tag_str else ""
    result = f"{status_prefix}{tag_prefix}{core}{context}{annotation}"
    return result[:max_len]


def _semantic_rank(current_task, parsed_tasks, embed_fn):
    """Rank tasks by semantic similarity using embeddings + priority weight."""
    texts = [current_task] + [t[2] for t in parsed_tasks]
    embeddings = embed_fn(texts)
    query_emb = embeddings[0]

    scored = []
    for i, (priority_w, core, _full, milestone, status) in enumerate(parsed_tasks):
        sim = _cosine_similarity(query_emb, embeddings[i + 1])
        # Skip near-duplicates (same task)
        if sim > 0.9:
            continue
        # Skip distant matches — only include tasks with meaningful similarity
        if sim < 0.3:
            continue
        # Combined score: semantic similarity * priority weight
        # Boost in-progress tasks (more likely to be referenced)
        weight = priority_w * (1.2 if status == "in-progress" else 1.0)
        score = sim * weight
        if score > 0.05:
            shared = _extract_shared_artifacts(current_task, _full)
            # Boost score if tasks share concrete artifacts
            if shared:
                score *= 1.15
            formatted = _format_related_task(core, _full, milestone, status, shared)
            scored.append((score, formatted))

    scored.sort(reverse=True)
    return scored


def _word_overlap_rank(current_task, parsed_tasks):
    """Fallback: rank tasks by word overlap (original Jaccard approach)."""
    task_words = set(re.findall(r'[a-z]{3,}', current_task.lower()))
    if not task_words:
        return []

    scored = []
    for priority_w, core, full_text, milestone, status in parsed_tasks:
        candidate_words = set(re.findall(r'[a-z]{3,}', full_text.lower()))
        if not candidate_words:
            continue
        jaccard = len(task_words & candidate_words) / max(1, len(task_words | candidate_words))
        if jaccard > 0.6:
            continue  # skip near-duplicates
        relevance = len(task_words & candidate_words) / max(1, len(candidate_words))
        if relevance > 0.1:
            weight = priority_w * (1.2 if status == "in-progress" else 1.0)
            shared = _extract_shared_artifacts(current_task, full_text)
            formatted = _format_related_task(core, full_text, milestone, status, shared)
            scored.append((relevance * weight, formatted))

    scored.sort(reverse=True)
    return scored


def _extract_task_dependencies(content, current_task):
    """Extract dependency/blocker relationships from QUEUE.md for current task.

    Looks for patterns like:
      - "Blocked on X", "depends on X", "after X", "requires X"
      - "blocks Y", "needed by Y"
    Returns dict with 'blockers' and 'blocks' lists.
    """
    blockers = []
    blocks = []

    # Extract current task tag for matching
    tag_match = re.search(r'\[([A-Z_]+)\]', current_task)
    current_tag = tag_match.group(1) if tag_match else None
    if not current_tag:
        return {"blockers": blockers, "blocks": blocks}

    for line in content.splitlines():
        stripped = line.strip()
        # Find lines mentioning our task tag in dependency context
        if current_tag in stripped:
            # "Blocked on [CURRENT_TAG]" means something else is blocked on us
            blocker_match = re.search(
                r'\[([A-Z_]+)\].*(?:blocked\s+on|depends\s+on|after|requires)\s+.*'
                + re.escape(current_tag),
                stripped, re.IGNORECASE,
            )
            if blocker_match and blocker_match.group(1) != current_tag:
                blocks.append(blocker_match.group(1))

        # Find our task blocked on something else
        if current_tag in stripped:
            dep_match = re.search(
                re.escape(current_tag)
                + r'.*(?:blocked\s+on|depends\s+on|after|requires)\s+.*\[([A-Z_]+)\]',
                stripped, re.IGNORECASE,
            )
            if dep_match and dep_match.group(1) != current_tag:
                blockers.append(dep_match.group(1))

    # Also scan for "Blocked on:" lines near our task
    in_task_block = False
    for line in content.splitlines():
        stripped = line.strip()
        if current_tag and current_tag in stripped and stripped.startswith("- ["):
            in_task_block = True
            # Check inline blockers: "Blocked on [TAG]" within the task line
            inline_tags = re.findall(
                r'(?:[Bb]locked\s+on|[Dd]epends\s+on|[Rr]equires)\s+.*?\[([A-Z_]+)\]',
                stripped,
            )
            blockers.extend(t for t in inline_tags if t != current_tag)
            continue
        if in_task_block:
            if stripped.startswith("- ") or stripped.startswith("##"):
                in_task_block = False
            elif re.match(r'(?:blocked|depends|requires)', stripped, re.IGNORECASE):
                inline_tags = re.findall(r'\[([A-Z_]+)\]', stripped)
                blockers.extend(t for t in inline_tags if t != current_tag)

    return {
        "blockers": list(dict.fromkeys(blockers))[:3],
        "blocks": list(dict.fromkeys(blocks))[:3],
    }


def find_related_tasks(current_task, queue_file=None, max_tasks=3):
    """Find pending tasks related to the current task using semantic similarity.

    Uses ONNX MiniLM embeddings for semantic matching with priority weighting.
    Falls back to word-overlap Jaccard if embeddings are unavailable.
    Includes dependency/blocker annotations when found.
    """
    queue_file = queue_file or QUEUE_FILE
    if not current_task or not os.path.exists(queue_file):
        return []

    with open(queue_file, 'r') as f:
        content = f.read()

    parsed = _parse_queue_tasks(content)
    if not parsed:
        return []

    # Extract current task tag for self-exclusion
    current_tag_match = re.search(r'\[([A-Z0-9_]+)\]', current_task)
    current_tag = current_tag_match.group(1) if current_tag_match else None
    if current_tag:
        parsed = [(pw, c, ft, ms, st) for pw, c, ft, ms, st in parsed
                  if f"[{current_tag}]" not in ft]

    # Try semantic ranking with brain embeddings
    related = None
    try:
        from clarvis.brain.factory import get_embedding_function
        embed_fn = get_embedding_function(use_onnx=True)
        if embed_fn is not None:
            scored = _semantic_rank(current_task, parsed, embed_fn)
            related = [text for _, text in scored[:max_tasks]]
    except Exception:
        logger.debug("Semantic ranking failed, falling back to word overlap", exc_info=True)

    if related is None:
        # Fallback to word overlap
        scored = _word_overlap_rank(current_task, parsed)
        related = [text for _, text in scored[:max_tasks]]

    # Enrich with dependency/blocker annotations
    deps = _extract_task_dependencies(content, current_task)
    annotations = []
    if deps["blockers"]:
        annotations.append(
            "BLOCKED BY: " + ", ".join(deps["blockers"])
        )
    if deps["blocks"]:
        annotations.append(
            "BLOCKS: " + ", ".join(deps["blocks"])
        )
    return annotations + related


def _get_similar_failure_lessons(current_task, max_lessons=2):
    """Get failure lessons from episodes similar to the current task.

    Returns compact avoidance strings for inline insertion in the episodes section.
    These are distinct from the top-level failure_patterns (which are generic);
    these are task-specific based on semantic similarity.
    """
    lessons = []
    try:
        from clarvis.memory.episodic_memory import EpisodicMemory
        em = EpisodicMemory()
        failures = em.recall_failures(n=10)
        if not failures:
            return []

        task_tokens = set(re.findall(r'[a-z][a-z0-9_]{2,}', current_task.lower()))
        _sw = {"the", "and", "for", "are", "but", "not", "you", "all", "can",
               "had", "was", "one", "our", "out", "has", "have", "from",
               "with", "this", "that", "they", "been", "will", "each", "make",
               "like", "into", "than", "its", "also", "use", "two", "how"}
        task_tokens -= _sw

        seen = set()
        for ep in failures:
            ep_task = ep.get("task", "")
            ep_tokens = set(re.findall(r'[a-z][a-z0-9_]{2,}', ep_task.lower())) - _sw
            if not task_tokens or not ep_tokens:
                continue
            overlap = len(task_tokens & ep_tokens) / max(1, len(task_tokens))
            if overlap < 0.15:
                continue  # not similar enough

            error = ep.get("error", "") or ep.get("lesson", "") or ""
            tag = re.search(r'\[([A-Z_]+)\]', ep_task)
            tag_str = f"[{tag.group(1)}] " if tag else ""
            dedup_key = (error or ep_task)[:30].lower()
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            if error:
                lessons.append(
                    f" - AVOID: SIMILAR TASK FAILED BEFORE: '{ep_task[:80]}' (error: {error[:40]})"
                )
            else:
                outcome = ep.get("outcome", "failure")
                lessons.append(
                    f" - AVOID: SIMILAR TASK FAILED BEFORE: '{tag_str}{ep_task[:80]}' ({outcome})"
                )
            if len(lessons) >= max_lessons:
                break
    except Exception:
        logger.debug("Failed to load similar failure lessons", exc_info=True)
    return lessons


_EPISODE_DOMAIN_PATTERNS = {
    "brain": r"brain|chroma|memory|retrieval|search|recall|embed",
    "metrics": r"metric|phi|benchmark|score|brier|confidence|calibrat",
    "context": r"context|assembly|compress|brief|relevance|episode",
    "infra": r"cron|gateway|health|backup|monitor|watchdog|graph",
    "code": r"implement|refactor|migrate|fix|build|wire|test|create",
    "research": r"research|paper|arxiv|ingest|literature|survey",
}

# Shared stopwords for episode token overlap calculations
_EPISODE_STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "can",
    "had", "was", "one", "our", "out", "has", "have", "from",
    "with", "this", "that", "they", "been", "will", "each", "make",
    "like", "into", "than", "its", "also", "use", "two", "how",
}


def _classify_episode_domain(task_text: str) -> str:
    """Classify an episode's task text into a domain category."""
    task_lower = task_text.lower()
    for domain, pattern in _EPISODE_DOMAIN_PATTERNS.items():
        if re.search(pattern, task_lower):
            return domain
    return "general"


def _ep_tokens(text):
    """Extract meaningful tokens from text, minus stopwords."""
    return set(re.findall(r'[a-z][a-z0-9_]{2,}', text.lower())) - _EPISODE_STOPWORDS


def _find_recovery_pairs(failure_eps, success_eps, max_pairs=2):
    """Find failure→success recovery pairs on similar tasks."""
    pairs = []
    for fail_ep in failure_eps[:5]:
        fail_tokens = _ep_tokens(fail_ep.get("task", ""))
        if not fail_tokens:
            continue
        for succ_ep in success_eps:
            succ_tokens = _ep_tokens(succ_ep.get("task", ""))
            overlap = len(fail_tokens & succ_tokens) / max(1, len(fail_tokens))
            if overlap >= 0.3:
                pairs.append((fail_ep, succ_ep))
                break
        if len(pairs) >= max_pairs:
            break
    return pairs


def _score_domain_groups(domain_groups, current_task):
    """Score episode domain groups by token relevance to current task."""
    task_tokens = _ep_tokens(current_task)
    domain_scores = []
    for domain, eps in domain_groups.items():
        overlaps = []
        for ep in eps:
            ep_tok = _ep_tokens(ep.get("task", ""))
            if task_tokens and ep_tok:
                overlaps.append(len(task_tokens & ep_tok) / max(1, len(task_tokens)))
        avg_overlap = sum(overlaps) / max(1, len(overlaps)) if overlaps else 0
        domain_scores.append((avg_overlap, domain, eps))
    domain_scores.sort(key=lambda x: x[0], reverse=True)
    return domain_scores


def _format_episode_patterns(domain_scores, max_patterns):
    """Format success patterns as abstract→concrete lines."""
    lines = []
    pattern_count = 0
    for _, domain, eps in domain_scores:
        if pattern_count >= max_patterns:
            break
        best_ep = eps[0]
        task_str = best_ep.get("task", "")[:80]

        lesson_str = ""
        for ep in eps:
            lesson = ep.get("lesson", "")
            if lesson and lesson.lower() not in ("success", "failure", ""):
                lesson_str = lesson[:60]
                break
        if not lesson_str:
            ids = _extract_actionable_context(task_str)
            duration = best_ep.get("duration_s")
            dur_str = f" ({int(duration)}s)" if duration else ""
            lesson_str = f"{best_ep.get('outcome', 'success')}{dur_str}{ids}"

        tag = re.search(r'\[([A-Z_]+)\]', task_str)
        tag_str = f"[{tag.group(1)}]" if tag else f"[{domain}]"
        lines.append(f"  {tag_str} {lesson_str}")
        lines.append(f"    eg: {task_str}")
        pattern_count += 1
    return lines


def _format_recovery_lines(recovery_pairs):
    """Format failure→recovery pairs with concrete identifiers."""
    if not recovery_pairs:
        return []
    lines = ["  RECOVERY:"]
    for fail_ep, succ_ep in recovery_pairs[:2]:
        fail_task = (fail_ep.get("task") or "")[:70]
        fail_err = (fail_ep.get("error") or "")[:40] or "failed"
        succ_lesson = succ_ep.get("lesson") or ""
        if succ_lesson and succ_lesson.lower() not in ("success", ""):
            fix_str = succ_lesson[:60]
        else:
            fix_str = (succ_ep.get("task") or "")[:60]
        lines.append(f"    fail: {fail_task} ({fail_err})")
        if fix_str.strip():
            lines.append(f"    fix: {fix_str}")
    return lines


def build_hierarchical_episodes(current_task: str, episodic_hints: str = "",
                                max_patterns: int = 3, max_chars: int = 400) -> str:
    """Build multi-level episode summaries: abstract pattern → concrete example.

    Returns formatted string for the EPISODIC LESSONS section.
    """
    if not current_task:
        return episodic_hints[:max_chars] if episodic_hints else ""

    episodes = []
    try:
        from clarvis.memory.episodic_memory import EpisodicMemory
        em = EpisodicMemory()
        episodes = em.recall_similar(current_task, n=12, use_spreading_activation=True)
    except Exception:
        logger.debug("Failed to recall episodes for hierarchical build", exc_info=True)

    if not episodes:
        if episodic_hints:
            return rerank_episodes_by_task(episodic_hints, current_task)[:max_chars]
        return ""

    # Classify episodes by outcome
    success_eps = [ep for ep in episodes if ep.get("outcome") == "success"]
    failure_eps = [ep for ep in episodes
                   if ep.get("outcome") in ("failure", "soft_failure", "timeout")]

    recovery_pairs = _find_recovery_pairs(failure_eps, success_eps)

    # Group successes by domain, score by relevance
    domain_groups: dict = {}
    for ep in success_eps:
        domain = _classify_episode_domain(ep.get("task", ""))
        domain_groups.setdefault(domain, []).append(ep)
    domain_scores = _score_domain_groups(domain_groups, current_task)

    # Format output
    lines = _format_episode_patterns(domain_scores, max_patterns)
    lines.extend(_format_recovery_lines(recovery_pairs))

    avoidance = _get_similar_failure_lessons(current_task, max_lessons=2)
    if avoidance:
        lines.extend(avoidance)

    result = "\n".join(lines)
    if len(result) < 80 and episodic_hints:
        fallback = rerank_episodes_by_task(episodic_hints, current_task)
        result = result + "\n" + fallback if result else fallback

    return result[:max_chars]


def _split_episode_lines(lines):
    """Separate header/separator lines from episode content lines."""
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
    return episode_lines, other_lines


def _enrich_top_episodes(scored, task_tokens):
    """Annotate top episodes with task-relevant terms for containment boost."""
    enriched = []
    for idx, (score, line) in enumerate(scored):
        if idx < 3 and task_tokens:
            shared = task_tokens & _ep_tokens(line)
            if shared:
                tag = " [rel: " + ", ".join(sorted(shared)[:4]) + "]"
                enriched.append(line.rstrip() + tag)
            else:
                enriched.append(line)
        else:
            enriched.append(line)
    return enriched


def rerank_episodes_by_task(episodic_hints: str, current_task: str) -> str:
    """Re-rank episode lines by combined recency + task similarity.

    Scores each line by task-token overlap + position (recency proxy),
    returns sorted by combined score with failure-avoidance lessons injected.
    """
    if not episodic_hints or not current_task:
        return episodic_hints

    lines = [l for l in episodic_hints.strip().split('\n') if l.strip()]
    if len(lines) <= 1:
        return episodic_hints

    episode_lines, other_lines = _split_episode_lines(lines)
    if len(episode_lines) <= 1:
        return episodic_hints

    task_tokens = _ep_tokens(current_task)

    scored = []
    n_eps = len(episode_lines)
    for i, line in enumerate(episode_lines):
        ep_tok = _ep_tokens(line)
        overlap = len(task_tokens & ep_tok) / max(1, len(task_tokens)) if task_tokens and ep_tok else 0.0
        recency = (i + 1) / n_eps
        scored.append((0.6 * overlap + 0.4 * recency, line))
    scored.sort(key=lambda x: x[0], reverse=True)

    failure_lessons = _get_similar_failure_lessons(current_task, max_lessons=2)
    enriched = _enrich_top_episodes(scored, task_tokens)

    result = other_lines + enriched
    if failure_lessons:
        result.append("AVOID THESE FAILURE PATTERNS:")
        result.extend(failure_lessons)
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


def get_recommended_procedures(current_task, max_procs=2):
    """Query clarvis-procedures for task-similar procedures.

    Returns a formatted "RECOMMENDED PROCEDURES" section, or empty string
    if no relevant procedures are found.
    """
    try:
        from clarvis.memory.procedural_memory import find_procedure, find_code_templates
    except ImportError:
        return ""

    parts = []

    # 1. Check for a matching procedure (step-by-step)
    try:
        proc = find_procedure(current_task, threshold=0.6)
        if proc:
            name = proc.get("name", "unnamed")
            steps = proc.get("steps", [])
            rate = proc.get("success_rate", 1.0)
            rate_pct = int(rate * 100)
            parts.append(f"  [{name}] (success: {rate_pct}%)")
            for i, step in enumerate(steps[:6], 1):
                step_text = step if isinstance(step, str) else str(step)
                parts.append(f"    {i}. {step_text[:80]}")
    except Exception:
        logger.debug("Failed to load recommended procedures", exc_info=True)

    # 2. Check for code generation templates
    try:
        templates = find_code_templates(current_task, top_n=max_procs)
        for tmpl in templates:
            name = tmpl.get("name", "template")
            scaffold = tmpl.get("scaffold", [])
            if not scaffold:
                continue
            parts.append(f"  [{name}]")
            for i, step in enumerate(scaffold[:6], 1):
                parts.append(f"    {i}. {step[:80]}")
            pre = tmpl.get("preconditions", [])
            if pre:
                parts.append(f"    PRE: {', '.join(pre[:3])}")
            verify = tmpl.get("termination_criteria", [])
            if verify:
                parts.append(f"    VERIFY: {', '.join(verify[:2])}")
    except Exception:
        logger.debug("Failed to load code generation templates", exc_info=True)

    if not parts:
        return ""

    return "CODE GENERATION TEMPLATES (matched scaffolds from top patterns):\n" + "\n".join(parts[:20])




def _classify_task_class(task_text):
    """Classify a task into a budget-policy task class.

    Returns one of the keys from data/prompt_eval/context_budget_policy.json.
    Rules are ordered most-specific-first to avoid false matches.
    """
    if not task_text:
        return "code_implementation"
    t = task_text.lower()
    # --- specific classes first (avoid false matches) ---
    if any(kw in t for kw in ("benchmark", "clr benchmark", "pi benchmark", "performance benchmark")):
        return "benchmarking"
    if any(kw in t for kw in ("spawn", "agent task", "orchestrat", "project agent")):
        return "agent_orchestration"
    if any(kw in t for kw in ("brand", "redesign", "visual identity", "copy audit", "naming treatment")):
        return "brand_creative"
    if any(kw in t for kw in ("evening assessment", "morning planning", "self-report", "review today", "velocity review", "reflection pipeline", "reflection —")):
        return "reflection"
    if any(kw in t for kw in ("brier", "calibration", "self-aware", "capability score", "phi metric", "confidence sweep")):
        return "self_awareness"
    # --- broader classes ---
    if any(kw in t for kw in ("research", "investigate", "paper", "compare", "survey")):
        return "research_synthesis"
    if any(kw in t for kw in ("remove dead", "cleanup", "prune dead", "delete unused", "remove 5 dead", "dead scripts")):
        return "repo_cleanup"
    if any(kw in t for kw in ("migrate", "move to", "refactor", "rename across", "replace proxy")):
        return "migration_refactor"
    if any(kw in t for kw in ("fix", "bug", "crash", "error", "broken", "fails")):
        return "bugfix_debug"
    if any(kw in t for kw in ("doc", "readme", "claude.md", "update table", "schedule table")):
        return "documentation"
    if any(kw in t for kw in ("cron", "logrotate", "systemd", "monitoring", "shell")):
        return "infra_cron"
    if any(kw in t for kw in ("brain", "dedup", "retrieval", "chromadb", "memory")):
        return "memory_brain"
    if any(kw in t for kw in ("evolution", "strategic", "queue analysis", "gap", "roadmap")):
        return "strategic_evolution"
    return "code_implementation"


_BUDGET_POLICY_CACHE = {}
_BUDGET_POLICY_MTIME = 0


def _load_budget_policy():
    """Load task-class context budget policy from data file."""
    global _BUDGET_POLICY_CACHE, _BUDGET_POLICY_MTIME
    import json
    policy_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "data", "prompt_eval", "context_budget_policy.json")
    policy_path = os.path.normpath(policy_path)
    try:
        mtime = os.path.getmtime(policy_path)
        if mtime == _BUDGET_POLICY_MTIME and _BUDGET_POLICY_CACHE:
            return _BUDGET_POLICY_CACHE
        with open(policy_path) as f:
            data = json.load(f)
        _BUDGET_POLICY_CACHE = data.get("task_classes", {})
        _BUDGET_POLICY_MTIME = mtime
        return _BUDGET_POLICY_CACHE
    except Exception:
        return {}


def _get_policy_section_weights(task_text):
    """Get section priority weights from budget policy based on task class.

    Merges policy weights with empirical section relevance weights.
    Policy weights act as priors; empirical data adjusts within the range.
    """
    policy = _load_budget_policy()
    if not policy:
        return {}
    task_class = _classify_task_class(task_text)
    class_config = policy.get(task_class, {})
    return class_config.get("section_priorities", {})


def _estimate_task_complexity(task_text):
    """Estimate task complexity from text: 'simple', 'medium', or 'complex'.

    Heuristics: word count, presence of multi-step indicators, research keywords.
    """
    if not task_text:
        return "medium"
    words = task_text.split()
    wc = len(words)
    text_lower = task_text.lower()
    complex_signals = sum(1 for kw in (
        "research", "investigate", "analyze", "design", "architect",
        "refactor", "migrate", "benchmark", "audit", "strategy",
        "multi-step", "comprehensive", "deep",
    ) if kw in text_lower)
    simple_signals = sum(1 for kw in (
        "fix", "update", "bump", "rename", "typo", "pin",
        "toggle", "enable", "disable", "set",
    ) if kw in text_lower)
    if wc < 20 and simple_signals > 0 and complex_signals == 0:
        return "simple"
    if wc > 60 or complex_signals >= 2:
        return "complex"
    return "medium"


def _scale_chars(base_chars, section_name, section_weights):
    """Scale a char budget by the section's relevance weight."""
    if not section_weights:
        return base_chars
    w = section_weights.get(section_name, 1.0)
    return max(50, round(base_chars * w))


def _build_brief_beginning(current_task, tier, budget, knowledge_hints, section_weights=None):
    """Build the BEGINNING (high-attention) zone of the tiered brief."""
    parts = []

    if budget.get("decision_context", 0) > 0:
        decision_ctx = build_decision_context(current_task, tier=tier)
        if decision_ctx:
            # Scale decision context by its relevance weight
            dc_max = _scale_chars(
                len(decision_ctx), "decision_context", section_weights)
            parts.append(decision_ctx[:dc_max])

    if knowledge_hints and tier != "minimal":
        reranked = rerank_knowledge_hints(knowledge_hints, current_task)
        if reranked and reranked.strip():
            parts.append("RELEVANT KNOWLEDGE:")
            # Adaptive budget: simple tasks get tighter knowledge budgets
            complexity = _estimate_task_complexity(current_task)
            if tier == "full":
                base_chars = 600
            elif complexity == "simple":
                base_chars = 200
            elif complexity == "complex":
                base_chars = 350
            else:
                base_chars = 280
            max_chars = _scale_chars(base_chars, "knowledge", section_weights)
            if len(reranked) > max_chars * 1.5:
                compressed_knowledge, _ = compress_text(reranked, ratio=0.25, task_context=current_task)
                parts.append(compressed_knowledge[:max_chars])
            else:
                parts.append(reranked[:max_chars])

    if budget["spotlight"] > 0:
        workspace_ctx = get_workspace_context(current_task, tier=tier)
        if workspace_ctx:
            base_ws = 500 if tier == "full" else 300
            ws_budget = _scale_chars(base_ws, "working_memory", section_weights)
            if len(workspace_ctx) > ws_budget * 1.5:
                workspace_ctx, _ = compress_text(workspace_ctx, ratio=0.25, task_context=current_task)
            parts.append(workspace_ctx[:ws_budget])
        else:
            n_items = 5 if tier == "full" else 3
            spotlight = get_spotlight_items(n=n_items, exclude_task=current_task)
            if spotlight:
                parts.append("WORKING MEMORY:")
                parts.extend(spotlight[:n_items])

    # Metrics one-liner — scaled down when metrics relevance is low
    if not should_suppress_section("metrics", current_task):
        metrics_w = section_weights.get("metrics", 1.0) if section_weights else 1.0
        if metrics_w > 0.2:  # skip entirely if relevance is very low
            scores = get_latest_scores()
            if scores:
                phi = scores.get("phi", "?")
                if "capabilities" in scores:
                    caps = scores["capabilities"]
                    worst_k = min(caps, key=caps.get) if caps else "?"
                    worst_v = caps.get(worst_k, "?") if caps else "?"
                    parts.append(f"METRICS: Phi={phi}, worst={worst_k}={worst_v}")
                else:
                    parts.append(f"METRICS: Phi={phi}")

    return parts


def _build_brief_middle(current_task, tier, budget, queue_file, section_weights=None):
    """Build the MIDDLE (lower-attention) zone of the tiered brief."""
    parts = []

    if budget["related_tasks"] > 0:
        # Scale number of related tasks by relevance weight
        rt_w = section_weights.get("related_tasks", 1.0) if section_weights else 1.0
        base_n = 3 if tier == "full" else 2
        n_related = max(1, round(base_n * rt_w))
        related = find_related_tasks(current_task, queue_file, max_tasks=n_related)
        if related:
            parts.append("RELATED TASKS:")
            for t in related:
                parts.append(f"  - {t}")

    if budget["completions"] > 0:
        comp_w = section_weights.get("completions", 1.0) if section_weights else 1.0
        base_n = 3 if tier == "full" else 2
        n_comp = max(1, round(base_n * comp_w))
        completions = get_recent_completions(queue_file, n=n_comp)
        if completions:
            parts.append("RECENT:")
            parts.extend(completions)

    return parts


def _build_brief_end(current_task, tier, budget, episodic_hints, section_weights=None):
    """Build the END (high-attention) zone of the tiered brief."""
    parts = []

    if tier != "minimal":
        procedures_text = get_recommended_procedures(current_task, max_procs=2)
        if procedures_text:
            parts.append(procedures_text)

    if budget["episodes"] > 0:
        # Episodes are high-value — scale char budget up when relevant
        base_chars = budget["episodes"] * 4
        max_chars = _scale_chars(base_chars, "episodes", section_weights)
        base_patterns = 3 if tier == "full" else 2
        ep_w = section_weights.get("episodes", 1.0) if section_weights else 1.0
        max_patterns = max(1, round(base_patterns * ep_w))
        hierarchical = build_hierarchical_episodes(
            current_task, episodic_hints=episodic_hints or "",
            max_patterns=max_patterns,
            max_chars=max_chars,
        )
        if hierarchical and hierarchical.strip():
            parts.append("EPISODIC LESSONS:\n" + hierarchical)

    if synthesize_knowledge and tier != "minimal":
        try:
            base_chars = 500 if tier == "full" else 350
            max_chars = _scale_chars(base_chars, "knowledge", section_weights)
            knowledge_section = synthesize_knowledge(
                current_task, tier=tier, max_chars=max_chars)
            if knowledge_section and knowledge_section.strip():
                parts.append("KNOWLEDGE SYNTHESIS:\n" + knowledge_section)
        except Exception:
            logger.debug("Failed to synthesize knowledge", exc_info=True)

    if get_relevant_frameworks and tier != "minimal":
        try:
            frameworks_text = get_relevant_frameworks(current_task, max_frameworks=3)
            if frameworks_text and frameworks_text.strip():
                parts.append("CONCEPTUAL FRAMEWORKS:\n" + frameworks_text)
        except Exception:
            logger.debug("Failed to get conceptual frameworks", exc_info=True)

    if budget.get("reasoning_scaffold", 0) > 0:
        scaffold = build_reasoning_scaffold(tier=tier, task_text=current_task)
        parts.append(scaffold)

    return parts


def generate_tiered_brief(
    current_task,
    tier="standard",
    episodic_hints="",
    knowledge_hints="",
    queue_file=None,
):
    """Generate a quality-optimized context brief using primacy/recency positioning.

    Ordering follows LLM attention research (Liu et al. "Lost in the Middle"):
      BEGINNING (highest attention): Decision context, knowledge, working memory.
      MIDDLE (lower attention): Related tasks, completions.
      END (high attention): Episodic lessons, knowledge synthesis, reasoning scaffold.

    Per-section relevance weights scale individual char budgets within each zone,
    so high-value sections (episodes, reasoning, knowledge) expand while low-value
    sections (metrics, completions) compress.  This improves brief compression
    ratio by allocating tokens where they contribute most to task success.
    """
    queue_file = queue_file or QUEUE_FILE
    budget = get_adjusted_budgets(tier)
    empirical_weights = load_section_relevance_weights()
    policy_weights = _get_policy_section_weights(current_task)
    # Merge: policy weights are priors, empirical data adjusts.
    # If both exist for a section, geometric mean preserves both signals.
    section_weights = {}
    all_sections = set(list(empirical_weights.keys()) + list(policy_weights.keys()))
    for sec in all_sections:
        emp = empirical_weights.get(sec)
        pol = policy_weights.get(sec)
        if emp is not None and pol is not None:
            section_weights[sec] = round((emp * pol) ** 0.5, 3)  # geometric mean
        elif pol is not None:
            section_weights[sec] = round(pol, 3)
        elif emp is not None:
            section_weights[sec] = round(emp, 3)

    beginning = _build_brief_beginning(current_task, tier, budget, knowledge_hints, section_weights)
    middle = _build_brief_middle(current_task, tier, budget, queue_file, section_weights)
    end = _build_brief_end(current_task, tier, budget, episodic_hints, section_weights)

    parts = beginning
    if middle:
        parts.append("---")
        parts.extend(middle)
    if end:
        parts.append("---")
        parts.extend(end)

    assembled = "\n".join(parts)

    if tier != "minimal":
        assembled = dycp_prune_brief(assembled, current_task)

    return assembled
