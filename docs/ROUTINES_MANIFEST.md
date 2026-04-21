# Routines Manifest Specification

_Version 1.0 — 2026-04-21. Defines the `.clarvis/routines.yaml` format for per-project Claude Code Routine declarations._

_Parent strategy: `docs/CLAUDE_DESIGN_ROUTINES_STRATEGY.md`._

---

## Overview

Each project that Clarvis manages declares its Routines in a `.clarvis/routines.yaml` file at the repo root. This manifest tells Clarvis (or a future `routine_manager.py` provisioner) which Routines to create, what triggers them, and what they should do.

The manifest is **declarative** — it describes desired state, not imperative steps. A provisioner reads the manifest, diffs against live Routines, and creates/updates/deletes to converge.

---

## Schema

```yaml
# .clarvis/routines.yaml
version: "1"

project: <string>          # required — project identifier (e.g., "star-world-order", "clarvis")
repo: <string>             # optional — GitHub repo in owner/name format (inferred from git remote if absent)
budget:
  max_daily_runs: <int>    # optional — cap on total Routine runs/day for this project (default: 5)

routines:
  <routine-id>:            # kebab-case identifier, unique within the manifest
    description: <string>  # required — one-line human summary
    enabled: <bool>        # optional — default true. Set false to suspend without deleting config.

    trigger: <trigger>     # required — one of: github_webhook, schedule, api
    events: [<string>]     # required for github_webhook — GitHub event types (e.g., pull_request.opened)
    cron: <string>         # required for schedule — cron expression (min interval: 1h)
    # api trigger has no extra fields — fires on POST to the Routine's endpoint

    filter:                # optional — conditions that must match for the Routine to execute
      base_branch: [<string>]     # PR target branch(es)
      head_branch_pattern: <str>  # regex for source branch name
      merged: <bool>              # for pull_request.closed — only fire if PR was merged
      paths: [<string>]           # glob patterns — only fire if changed files match
      labels: [<string>]          # only fire if PR/issue has one of these labels
      author_association: [<str>] # GitHub author associations (MEMBER, CONTRIBUTOR, etc.)

    prompt: |              # required — the instruction given to Claude Code when the Routine fires
      Multi-line prompt text. Supports variable interpolation (see below).

    connectors: [<string>] # optional — MCP connectors the Routine needs (github, slack, linear, etc.)

    model: <string>        # optional — Claude model override (default: routine platform default)
    timeout: <int>         # optional — max execution time in seconds (default: 600)
    permissions:           # optional — tool permission overrides
      allow: [<string>]   # tool patterns to auto-allow (e.g., "Bash(npm run *)")
      deny: [<string>]    # tool patterns to block
```

---

## Trigger Types

### `github_webhook`

Fires when a matching GitHub event occurs on the repo.

| Field | Required | Description |
|---|---|---|
| `events` | yes | List of `<event>.<action>` strings per GitHub webhook spec |
| `filter` | no | Additional conditions (branch, paths, labels, merged) |

Supported events: `pull_request.opened`, `pull_request.ready_for_review`, `pull_request.closed`, `pull_request.synchronize`, `issues.opened`, `issues.labeled`, `push`, `release.created`, `release.published`.

### `schedule`

Fires on a cron schedule. Minimum interval: 1 hour.

| Field | Required | Description |
|---|---|---|
| `cron` | yes | Standard 5-field cron expression. Timezone is UTC. |

### `api`

Fires when a POST request hits the Routine's API endpoint. No extra fields needed — the endpoint URL is assigned at provisioning time.

---

## Variable Interpolation

Prompts support these variables, injected at runtime:

| Variable | Available On | Value |
|---|---|---|
| `{{pr.number}}` | github_webhook (PR) | Pull request number |
| `{{pr.title}}` | github_webhook (PR) | Pull request title |
| `{{pr.author}}` | github_webhook (PR) | PR author username |
| `{{pr.base_branch}}` | github_webhook (PR) | Target branch |
| `{{pr.head_branch}}` | github_webhook (PR) | Source branch |
| `{{issue.number}}` | github_webhook (issue) | Issue number |
| `{{issue.title}}` | github_webhook (issue) | Issue title |
| `{{release.tag}}` | github_webhook (release) | Release tag name |
| `{{repo.full_name}}` | all | owner/repo |
| `{{run.date}}` | all | ISO-8601 date of the run |

---

## Validation Rules

1. `version` must be `"1"`.
2. `project` is required and must match `[a-z0-9-]+`.
3. Each `<routine-id>` must match `[a-z0-9-]+` and be unique within the file.
4. `trigger` must be one of `github_webhook`, `schedule`, `api`.
5. `events` is required when `trigger: github_webhook`.
6. `cron` is required when `trigger: schedule`. Must be a valid 5-field cron expression with interval >= 1h.
7. `prompt` is required and must be non-empty.
8. `budget.max_daily_runs` if set must be >= 1 and <= 25 (platform hard cap).
9. `filter` fields are only meaningful for `github_webhook` triggers; ignored on other trigger types.
10. `connectors` values must be known MCP connector names.

---

## File Location

The manifest lives at `.clarvis/routines.yaml` in the project repo root. This path is chosen to:
- Namespace Clarvis config under `.clarvis/` (future: design profiles, agent config)
- Keep it out of `.github/` to avoid confusion with GitHub Actions
- Be discoverable by `routine_manager.py` via convention

---

## Provisioning Lifecycle

1. **Read**: Provisioner reads `.clarvis/routines.yaml` from the target repo (local clone or GitHub API).
2. **Diff**: Compare declared routines against live Routines on the platform.
3. **Converge**: Create missing, update changed, disable removed (soft delete — never hard delete without operator approval).
4. **Report**: Log what changed to `memory/cron/routine_sync.log`.

Routines with `enabled: false` are suspended on the platform but not deleted — preserving history and allowing quick re-enable.

---

## Relationship to Local Cron

The manifest only governs **cloud Routines** (Anthropic platform). Local cron jobs (`scripts/cron/`) are managed by the existing `clarvis cron` CLI and system crontab. The two systems are complementary:

- **Cloud Routines**: GitHub-event reactions, scheduled tasks on remote repos, MCP connector integrations.
- **Local Cron**: Brain-dependent tasks, ChromaDB access, local filesystem state, high-frequency jobs.

A task should never exist in both systems. The decision framework in `docs/CLAUDE_DESIGN_ROUTINES_STRATEGY.md` §3 governs placement.
