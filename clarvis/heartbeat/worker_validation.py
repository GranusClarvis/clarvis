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


def _check_implementation_output(output_text):
    """Implementation must have file changes and ideally tests.

    Checks for: file edits/writes, test execution, code artifacts.
    """
    checks = {
        "has_file_changes": False,
        "has_tests": False,
        "has_code": False,
    }
    reasons = []

    if not output_text:
        return False, ["no output text"], checks

    text_lower = output_text.lower()

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
    if re.search(r"(def |class |import |from .+ import)", output_text):
        checks["has_code"] = True

    passed = checks["has_file_changes"]  # File changes are required

    if not checks["has_file_changes"]:
        reasons.append("no file changes detected")
    if not checks["has_tests"]:
        reasons.append("no test execution detected")
    if not checks["has_code"]:
        reasons.append("no code artifacts detected")

    return passed, reasons, checks


def _check_maintenance_output(output_text):
    """Maintenance must have health status or actions taken.

    Checks for: health/status reporting, cleanup actions, metrics.
    """
    checks = {
        "has_status": False,
        "has_actions": False,
    }
    reasons = []

    if not output_text:
        return False, ["no output text"], checks

    text_lower = output_text.lower()

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


def validate_worker_output(worker_type, output_text, task_status):
    """Validate worker output against type-specific expectations.

    Only validates successful tasks — failed/timeout/crash tasks are not
    downgraded further.

    Args:
        worker_type: str from classify_worker_type().
        output_text: Raw output text from the executor.
        task_status: Current task status ("success", "failure", etc.).

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

    passed, reasons, checks = validator(output_text)
    result["checks"] = checks
    result["reasons"] = reasons

    if not passed:
        result["validated"] = False
        result["downgrade"] = True

    return result
