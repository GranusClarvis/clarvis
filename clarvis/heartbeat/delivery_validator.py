"""Project-task delivery validation — enforces PR-based completion for project-lane tasks.

SWO/project tasks must produce a mergeable GitHub PR to count as "success".
Without a PR URL in the output, the task is downgraded to partial_success
(status: "partial_delivery") so it re-enters the queue for completion.

Wired into heartbeat_postflight after worker_validation (§0.6).
"""

import os
import re

# Detect project-lane tasks by tag patterns in task text
_PROJECT_TAG_RE = re.compile(
    r"\[PROJECT:[A-Z][A-Za-z0-9_-]+\]"
    r"|\(SWO\)|\[SWO\]"
    r"|\[PROJECT\b",
    re.IGNORECASE,
)

# Also match if CLARVIS_PROJECT_LANE is set and the task contains the lane name
_PROJECT_LANE = os.environ.get("CLARVIS_PROJECT_LANE", "").strip().upper()

# PR URL patterns — GitHub PR URLs, gh pr create output, or PR references
_PR_URL_RE = re.compile(
    r"https://github\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+/pull/\d+",
)
_PR_REF_RE = re.compile(
    r"(?:PR|pull\s+request)\s*#\d+",
    re.IGNORECASE,
)
_GH_PR_CREATED_RE = re.compile(
    r"gh\s+pr\s+create|created\s+pull\s+request|Creating pull request",
    re.IGNORECASE,
)
_GIT_PUSH_RE = re.compile(
    r"git\s+push\b|pushed\s+to\s+(remote|origin|upstream|fork)",
    re.IGNORECASE,
)


def is_project_task(task_text: str, task_tag: str = "") -> bool:
    """Return True if the task is a project-lane task requiring PR delivery."""
    combined = f"{task_text} {task_tag}"
    if _PROJECT_TAG_RE.search(combined):
        return True
    if _PROJECT_LANE and _PROJECT_LANE in combined.upper():
        return True
    return False


def extract_pr_urls(text: str) -> list[str]:
    """Extract GitHub PR URLs from output text."""
    if not text:
        return []
    return _PR_URL_RE.findall(text)


def has_pr_evidence(output_text: str) -> dict:
    """Check output text for evidence of PR delivery.

    Returns a dict with check results:
        has_pr_url: bool — found a github.com/.../pull/N URL
        has_pr_ref: bool — found "PR #N" or "pull request #N"
        has_pr_creation: bool — found gh pr create or similar
        has_git_push: bool — found git push evidence
        pr_urls: list[str] — extracted PR URLs
        evidence_level: str — "strong" (URL), "moderate" (ref+push), "weak" (push only), "none"
    """
    if not output_text:
        return {
            "has_pr_url": False,
            "has_pr_ref": False,
            "has_pr_creation": False,
            "has_git_push": False,
            "pr_urls": [],
            "evidence_level": "none",
        }

    pr_urls = extract_pr_urls(output_text)
    has_url = len(pr_urls) > 0
    has_ref = bool(_PR_REF_RE.search(output_text))
    has_creation = bool(_GH_PR_CREATED_RE.search(output_text))
    has_push = bool(_GIT_PUSH_RE.search(output_text))

    if has_url:
        level = "strong"
    elif has_ref or has_creation:
        level = "moderate"
    elif has_push:
        level = "weak"
    else:
        level = "none"

    return {
        "has_pr_url": has_url,
        "has_pr_ref": has_ref,
        "has_pr_creation": has_creation,
        "has_git_push": has_push,
        "pr_urls": pr_urls,
        "evidence_level": level,
    }


def validate_project_delivery(task_text: str, output_text: str, task_status: str,
                               task_tag: str = "") -> dict:
    """Validate that a project task produced PR delivery evidence.

    Only runs for project-lane tasks with task_status == "success".
    Non-project tasks or non-success statuses pass through unchanged.

    Returns:
        dict with:
            is_project: bool
            validated: bool — True if delivery evidence is sufficient
            downgrade: bool — True if status should become partial_success
            downgrade_reason: str — "no_pr_delivery" or ""
            evidence: dict from has_pr_evidence()
            reasons: list[str]
    """
    result = {
        "is_project": False,
        "validated": True,
        "downgrade": False,
        "downgrade_reason": "",
        "evidence": {},
        "reasons": [],
    }

    if not is_project_task(task_text, task_tag):
        return result

    result["is_project"] = True

    if task_status != "success":
        return result

    evidence = has_pr_evidence(output_text)
    result["evidence"] = evidence

    if evidence["evidence_level"] in ("strong", "moderate"):
        result["reasons"].append(
            f"PR delivery confirmed ({evidence['evidence_level']}): "
            f"{', '.join(evidence['pr_urls']) if evidence['pr_urls'] else 'PR reference found'}"
        )
        return result

    # Weak or no evidence → downgrade
    result["validated"] = False
    result["downgrade"] = True
    result["downgrade_reason"] = "no_pr_delivery"

    if evidence["evidence_level"] == "weak":
        result["reasons"].append(
            "project task has git push but no PR URL — partial delivery "
            "(branch pushed but PR not created)"
        )
    else:
        result["reasons"].append(
            "project task completed without PR evidence — downgraded to partial_success "
            "(no git push, no PR URL, no PR reference found in output)"
        )

    return result
