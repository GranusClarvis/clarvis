"""Worker-type classification and output validation for heartbeat postflight.

Classifies tasks into worker types (research, implementation, maintenance)
and validates that the output meets minimum expectations for that type.
Failed validation downgrades task_status to partial_success.

Canonical module for COORDINATOR_POSTFLIGHT_VALIDATION.
"""

import re

# Worker type constants
RESEARCH = "research"
IMPLEMENTATION = "implementation"
MAINTENANCE = "maintenance"
GENERAL = "general"

# Classification patterns — checked in order, first match wins
_WORKER_PATTERNS = {
    RESEARCH: [
        r"\[RESEARCH\b",
        r"\bresearch\b.*\b(paper|survey|study|analyze|review|compare|investigate)\b",
        r"\bstudy\b.*\b(module|system|pattern|architecture)\b",
        r"\bdeep.?dive\b",
        r"\blit(erature)?\s+review\b",
    ],
    IMPLEMENTATION: [
        r"\[IMPL\b",
        r"\bimplement\b",
        r"\b(add|create|build|wire)\b.*\b(function|class|module|script|endpoint)\b",
        r"\bfix\b.*\b(bug|error|broken|failing|crash)\b",
        r"\brefactor\b",
        r"\bmigrat(e|ion)\b",
    ],
    MAINTENANCE: [
        r"\[MAINT(ENANCE)?\b",
        r"\b(cleanup|clean.up|rotate|prune|archive|vacuum|compact|purge)\b",
        r"\bhealth\s+(check|monitor|status)\b",
        r"\b(backup|restore|verify)\b.*\b(data|db|database|brain)\b",
        r"\bbloat\b.*\b(reduc|audit|score)\b",
        r"\bdead.?(code|script)\b.*\b(audit|remove|purge)\b",
    ],
}

# Compiled patterns (lazy init)
_compiled = {}


def _get_compiled():
    if not _compiled:
        for wtype, patterns in _WORKER_PATTERNS.items():
            _compiled[wtype] = [re.compile(p, re.IGNORECASE) for p in patterns]
    return _compiled


def classify_worker_type(task_text, task_tag=None, prompt_variant_task_type=None):
    """Classify a task into a worker type.

    Uses three signals in priority order:
    1. Explicit task_tag from QUEUE.md brackets (e.g. [RESEARCH], [IMPL])
    2. prompt_variant_task_type from prompt optimizer
    3. Regex pattern matching on task text

    Args:
        task_text: The full task description string.
        task_tag: First bracket tag from QUEUE.md (e.g. "RESEARCH 2026-04-02").
        prompt_variant_task_type: Task type from prompt optimizer.

    Returns:
        str: One of "research", "implementation", "maintenance", "general".
    """
    # Signal 1: explicit tag
    if task_tag:
        tag_upper = task_tag.upper()
        if "RESEARCH" in tag_upper:
            return RESEARCH
        if "IMPL" in tag_upper:
            return IMPLEMENTATION
        if "MAINT" in tag_upper:
            return MAINTENANCE

    # Signal 2: prompt optimizer classification
    if prompt_variant_task_type:
        pvt = prompt_variant_task_type.lower()
        if pvt == "research":
            return RESEARCH
        if pvt in ("implementation", "bugfix"):
            return IMPLEMENTATION
        if pvt in ("refactoring", "optimization"):
            # Refactoring/optimization is closer to implementation
            return IMPLEMENTATION

    # Signal 3: regex pattern matching
    compiled = _get_compiled()
    for wtype, patterns in compiled.items():
        for pattern in patterns:
            if pattern.search(task_text or ""):
                return wtype

    return GENERAL


# --- Output validation rules per worker type ---

def _check_research_output(output_text):
    """Research must have structured findings.

    Checks for: brain memory storage, research notes, findings/insights,
    or RESEARCH_RESULT block.
    """
    checks = {
        "has_findings": False,
        "has_brain_storage": False,
        "has_structure": False,
    }
    reasons = []

    if not output_text:
        return False, ["no output text"], checks

    text_lower = output_text.lower()

    # Check for structured findings
    if any(marker in text_lower for marker in [
        "research_result:", "findings:", "## findings",
        "key insight", "key finding", "learned that",
        "## summary", "## ideas", "## application",
    ]):
        checks["has_findings"] = True

    # Check for brain storage
    if any(marker in text_lower for marker in [
        "brain.py remember", "remember(", "stored", "brain memories",
        "importance=", "clarvis-learnings",
    ]):
        checks["has_brain_storage"] = True

    # Check for any structural markers (headings, bullet lists, numbered lists)
    if re.search(r"^#{1,3}\s+\w", output_text, re.MULTILINE):
        checks["has_structure"] = True
    elif re.search(r"^[\-\*]\s+\w", output_text, re.MULTILINE):
        checks["has_structure"] = True

    passed = sum(checks.values()) >= 2  # At least 2 of 3

    if not checks["has_findings"]:
        reasons.append("no structured findings detected")
    if not checks["has_brain_storage"]:
        reasons.append("no brain memory storage detected")
    if not checks["has_structure"]:
        reasons.append("output lacks structural markers")

    return passed, reasons, checks


_TEST_PATH_RE = re.compile(
    r"(^|[\s/])"  # word boundary or path sep
    r"(?:tests?/|test_[A-Za-z0-9_]+\.py|[A-Za-z0-9_]+_test\.py"
    r"|[A-Za-z0-9_.-]+\.test\.[tj]sx?|[A-Za-z0-9_.-]+\.spec\.[tj]sx?)",
)
_CODE_PATH_RE = re.compile(
    r"\.(?:py|ts|tsx|js|jsx|mjs|cjs|sh|sql|go|rs|java|rb|c|h|cpp|hpp"
    r"|tf|yaml|yml|toml|json)\b",
)


_BOOKKEEPING_ONLY_PATHS = (
    "memory/evolution/QUEUE.md",
    "memory/evolution/QUEUE_ARCHIVE.md",
    "memory/evolution/SWO_TRACKER.md",
    "website/static/status.json",
    "memory/cron/digest.md",
)


def _git_evidence_from_diff(diff_stat):
    """Extract has_file_changes / has_tests / has_code signals from a git diff stat.

    diff_stat is the output of ``git diff --stat`` (or empty/None).
    Bookkeeping-only diffs (just QUEUE.md / SWO_TRACKER.md / status.json /
    digest.md) do NOT count as code/test changes — those are journaling, not work.
    """
    sig = {"has_file_changes": False, "has_tests": False, "has_code": False}
    if not diff_stat:
        return sig
    real_change_lines = []
    for line in diff_stat.splitlines():
        s = line.strip()
        if not s or s.startswith("|") or "files changed" in s or "file changed" in s:
            continue
        # Lines look like "path/to/file.py | 4 +++-"; isolate the path
        path = s.split("|", 1)[0].strip()
        if not path:
            continue
        if path in _BOOKKEEPING_ONLY_PATHS:
            continue
        real_change_lines.append(path)

    if real_change_lines:
        sig["has_file_changes"] = True
        for p in real_change_lines:
            if _TEST_PATH_RE.search(p):
                sig["has_tests"] = True
            if _CODE_PATH_RE.search(p):
                sig["has_code"] = True
    return sig


def _parse_porcelain_paths(porcelain_text):
    """Parse `git status --porcelain` output into a set of file paths.

    Handles renames ("R  old -> new") by taking the destination path, and
    strips quoting that git uses for paths with special characters.
    """
    paths = set()
    for line in (porcelain_text or "").splitlines():
        if len(line) < 4:
            continue
        rest = line[3:]
        if " -> " in rest:
            rest = rest.split(" -> ", 1)[1]
        rest = rest.strip()
        if rest.startswith('"') and rest.endswith('"'):
            rest = rest[1:-1]
        if rest:
            paths.add(rest)
    return paths


def porcelain_delta_paths(pre_porcelain, post_porcelain):
    """Return file paths newly dirty/untracked in post that weren't in pre.

    These are paths the task touched in the working tree but possibly didn't
    commit (e.g. a new test file written but never staged). Crediting them
    fixes the false-partial pattern where uncommitted real edits were ignored.
    """
    pre_set = _parse_porcelain_paths(pre_porcelain)
    post_set = _parse_porcelain_paths(post_porcelain)
    return sorted(post_set - pre_set)


def _git_evidence_from_paths(paths):
    """Same shape as ``_git_evidence_from_diff`` but takes a list of paths.

    Bookkeeping-only paths are filtered the same way diff stats are.
    """
    sig = {"has_file_changes": False, "has_tests": False, "has_code": False}
    real = [p for p in (paths or []) if p and p not in _BOOKKEEPING_ONLY_PATHS]
    if real:
        sig["has_file_changes"] = True
        for p in real:
            if _TEST_PATH_RE.search(p):
                sig["has_tests"] = True
            if _CODE_PATH_RE.search(p):
                sig["has_code"] = True
    return sig


def _merge_signals(*sigs):
    out = {"has_file_changes": False, "has_tests": False, "has_code": False}
    for s in sigs:
        if not s:
            continue
        for k in out:
            if s.get(k):
                out[k] = True
    return out


def _check_implementation_output(output_text, git_diff_stat="", task_made_commit=False,
                                 porcelain_delta=None):
    """Implementation must have file changes and ideally tests.

    Checks for: file edits/writes, test execution, code artifacts. When
    ``git_diff_stat`` is provided (the diff produced *during* this task — see
    `_capture_git_outcome` with `pre_task_sha`), filesystem evidence overrides
    the output_text heuristic. ``porcelain_delta`` carries paths newly
    dirty/untracked since the task started — this credits work that edited or
    created files without committing. This catches the false-partial pattern
    where a summary-style Claude Code output omits tool-call markers even
    though real files changed.
    """
    checks = {
        "has_file_changes": False,
        "has_tests": False,
        "has_code": False,
    }
    reasons = []

    if not output_text and not git_diff_stat and not porcelain_delta:
        return False, ["no output text"], checks

    text_lower = (output_text or "").lower()

    # Check for file changes (tool use patterns from Claude Code output)
    if any(marker in text_lower for marker in [
        "edit(", "write(", "edited", "created", "modified",
        "file_path", "old_string", "new_string",
        "writing to", "wrote to", "updated file",
    ]):
        checks["has_file_changes"] = True

    # Check for test execution
    if any(marker in text_lower for marker in [
        "pytest", "test_", "tests passed", "tests failed",
        "assert", "testing", "test run", "ran tests",
        "passed", "0 failed",
    ]):
        checks["has_tests"] = True

    # Check for code artifacts (function defs, imports, etc.)
    if output_text and re.search(r"(def |class |import |from .+ import)", output_text):
        checks["has_code"] = True

    # Filesystem evidence: real diffs and uncommitted-edit deltas win over
    # text heuristics. Committed diff + working-tree porcelain delta together
    # give credit for both committed and uncommitted edits.
    git_sig = _merge_signals(
        _git_evidence_from_diff(git_diff_stat),
        _git_evidence_from_paths(porcelain_delta),
    )
    if git_sig["has_file_changes"]:
        checks["has_file_changes"] = True
    if git_sig["has_tests"]:
        checks["has_tests"] = True
    if git_sig["has_code"]:
        checks["has_code"] = True

    passed = checks["has_file_changes"]  # File changes are required

    if not checks["has_file_changes"]:
        reasons.append("no file changes detected")
    if not checks["has_tests"]:
        reasons.append("no test execution detected")
    if not checks["has_code"]:
        reasons.append("no code artifacts detected")

    return passed, reasons, checks


def _check_maintenance_output(output_text, git_diff_stat="", task_made_commit=False,
                              porcelain_delta=None):
    """Maintenance must have health status or actions taken.

    Checks for: health/status reporting, cleanup actions, metrics.
    Real filesystem changes (diff stat or porcelain delta) count as
    actions taken — including uncommitted edits.
    """
    checks = {
        "has_status": False,
        "has_actions": False,
    }
    reasons = []

    if not output_text and not git_diff_stat and not porcelain_delta:
        return False, ["no output text"], checks

    text_lower = (output_text or "").lower()

    # Check for health/status reporting
    if any(marker in text_lower for marker in [
        "health", "status", "ok", "pass", "fail",
        "checked", "verified", "report", "metrics",
        "disk", "memory", "cpu", "size", "count",
    ]):
        checks["has_status"] = True

    # Check for actions taken
    if any(marker in text_lower for marker in [
        "cleaned", "rotated", "pruned", "archived",
        "removed", "deleted", "compressed", "vacuumed",
        "compacted", "backed up", "fixed", "repaired",
        "no action needed", "all healthy", "nothing to clean",
    ]):
        checks["has_actions"] = True

    # Filesystem evidence: any non-bookkeeping diff or porcelain delta counts
    # as actions (covers both committed and uncommitted maintenance edits).
    git_sig = _merge_signals(
        _git_evidence_from_diff(git_diff_stat),
        _git_evidence_from_paths(porcelain_delta),
    )
    if git_sig["has_file_changes"]:
        checks["has_actions"] = True

    passed = checks["has_status"] or checks["has_actions"]

    if not checks["has_status"]:
        reasons.append("no health/status reporting detected")
    if not checks["has_actions"]:
        reasons.append("no maintenance actions detected")

    return passed, reasons, checks


_VALIDATORS = {
    RESEARCH: _check_research_output,
    IMPLEMENTATION: _check_implementation_output,
    MAINTENANCE: _check_maintenance_output,
}


def validate_worker_output(worker_type, output_text, task_status,
                           git_diff_stat="", task_made_commit=False,
                           porcelain_delta=None):
    """Validate worker output against type-specific expectations.

    Only validates successful tasks — failed/timeout/crash tasks are not
    downgraded further.

    Args:
        worker_type: str from classify_worker_type().
        output_text: Raw output text from the executor.
        task_status: Current task status ("success", "failure", etc.).
        git_diff_stat: ``git diff --stat`` of changes produced during the task
            (post-task minus pre-task). When supplied, real filesystem changes
            count as positive evidence and prevent false-partial downgrades on
            summary-style outputs that omit tool-call markers.
        task_made_commit: True if a new commit landed during the task.
        porcelain_delta: Optional list of file paths newly dirty/untracked
            since the task started (computed from pre/post
            ``git status --porcelain``). Credits uncommitted edits so that
            tasks which changed files without committing are not falsely
            downgraded. See :func:`porcelain_delta_paths`.

    Returns:
        dict: {
            "validated": bool — True if output meets expectations,
            "worker_type": str,
            "downgrade": bool — True if task_status should become partial_success,
            "reasons": list[str] — why validation failed,
            "checks": dict — per-check results,
        }
    """
    result = {
        "validated": True,
        "worker_type": worker_type,
        "downgrade": False,
        "reasons": [],
        "checks": {},
    }

    # Only validate successful tasks
    if task_status != "success":
        return result

    # General tasks skip validation
    validator = _VALIDATORS.get(worker_type)
    if validator is None:
        return result

    if worker_type in (IMPLEMENTATION, MAINTENANCE):
        passed, reasons, checks = validator(
            output_text, git_diff_stat, task_made_commit,
            porcelain_delta=porcelain_delta,
        )
    else:
        passed, reasons, checks = validator(output_text)
    result["checks"] = checks
    result["reasons"] = reasons

    if not passed:
        result["validated"] = False
        result["downgrade"] = True

    return result
