"""PR Factory Rules — Phase 1 prompt injection for project subagents.

Generates the PR class rules, two-PR policy, refinement limits, and
task-linkage requirements as prompt sections for build_spawn_prompt().

Spec: docs/subagents/PR_FACTORY_SPEC.md
"""


def build_pr_rules_section() -> list[str]:
    """Return prompt lines for PR Factory rules.

    Injected into the spawn prompt between context and the Task section.
    """
    return [
        "## PR Factory Rules (MANDATORY)",
        "",
        "### PR Classes — Every Run Ships a PR",
        "Your run MUST end with exactly one PR in one of these classes:",
        "- **Class A — Full completion.** Task implemented, validated, shipped.",
        "- **Class B — Best safe progress.** Core task done, a real blocker "
        "prevented full closure. Gap documented, next step explicit.",
        "- **Class C — Task-unblocking.** A concrete blocker prevents the task "
        "this run. Ship the smallest enabling change that unblocks THE SAME "
        "requested task. Not for drive-by cleanups.",
        "",
        "### Two-PR Policy",
        "If the task is blocked, ship two PRs in sequence:",
        "1. Class C — removes the blocker",
        "2. Class A/B — implements the task (next run or same run if time permits)",
        "The unblocking PR must be tightly linked to the original task.",
        "",
        "### Class C Requirements (anti-spam)",
        "Class C PRs must satisfy at least one measurable enabling outcome:",
        "- Adds a failing regression test for the target behavior",
        "- Fixes test/CI scaffolding so validations can run",
        "- Adds missing hooks/instrumentation required for the main change",
        "- Isolates pre-existing CI breakage (xfail/skip/quarantine + rationale)",
        "",
        "### Class C Task-Linkage (REQUIRED in PR body for Class C)",
        "- `Original task:` (verbatim or linked)",
        "- `Blocker:` (what prevented direct implementation)",
        "- `Unblocks:` (how this PR enables the task)",
        "- `Next PR:` (exact next step)",
        "",
        "### Refinement Policy — Max 2 Evidence-Triggered Loops",
        "1. **Attempt 1** — implement + verify",
        "2. **Refinement 1** — ONLY if: test failed, requirement missed, "
        "scope bloat found, or PR class upgradeable with one bounded pass",
        "3. **Refinement 2** — ONLY if still justified by evidence",
        "4. Then ship. No fourth pass.",
        "",
        "**Allowed triggers:** validation failed, requirement missed, "
        "self-review found a concrete edge case, diff has avoidable scope bloat.",
        "**NOT allowed:** vague unease, speculative perfectionism, "
        "hallucinated architecture concerns, gut feelings.",
        "Evidence steers behavior but is never an excuse to avoid the requested task.",
        "",
        "### Truthfulness",
        "Never misrepresent completion. If shipping Class B or C, say so in the "
        "PR body and in your A2A result (set `pr_class` accordingly).",
        "",
        "### Done Definition",
        "\"Done\" means: requested change implemented (or explicitly blocked "
        "per B/C), repo checks run, diff scoped to the task, memory updated, "
        "PR created. If B/C: PR body includes why A was impossible, what "
        "remains, exact next step.",
        "",
    ]


# Valid PR classes for A2A validation
PR_CLASSES = {"A", "B", "C"}
