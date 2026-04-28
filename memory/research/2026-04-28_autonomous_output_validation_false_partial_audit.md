# Autonomous Output Validation — False-Partial Audit (2026-04-28)

**Trigger:** [AUTONOMOUS_OUTPUT_VALIDATION_FALSE_PARTIAL_AUDIT].
**Scope:** the last 20 autonomous heartbeat tasks downgraded from `success` →
`partial_success` by `clarvis/heartbeat/worker_validation.py`.
**Source data:** `data/audit/traces/2026-04-25..28/*.json` (postflight section).

## TL;DR

- 18 of 20 downgrades (90%) were **false partials** — real file changes and a
  task-specific commit landed, but the validator only inspected `output_text`
  for tool-call markers (`edit(`, `write(`, `pytest`, …) and saw none, because
  Claude Code's tail summary doesn't echo tool calls.
- 2 of 20 (10%) were **true partials / ambiguous** — research tasks whose
  output lacked findings/structure/brain-storage markers.
- **Root cause:** `_check_implementation_output()` and `_check_maintenance_output()`
  used a text-only heuristic. The postflight already captured `git_diff_stat`
  via `_capture_git_outcome()` but never fed it to the validator.
- **Fix landed (this PR):** capture pre-task HEAD SHA in preflight, diff against
  post-task HEAD in postflight, pass that diff into `validate_worker_output()`.
  Real filesystem evidence overrides the text heuristic — but a diff that
  touches *only* bookkeeping files (`QUEUE.md`, `SWO_TRACKER.md`,
  `status.json`, `digest.md`) does **not** count as delivery.

## Classification table (last 20 partials)

| Date | Tag | Worker | Validator reasons | Diff (cleaned) | Verdict |
|---|---|---|---|---|---|
| 2026-04-25 | SWO_V2_MINIGAME_PLUMBING | impl | no file changes | `scripts/cron/cron_doctor.py` + QUEUE | **FALSE** (project work likely in mirror; main also touched) |
| 2026-04-25 | SWO_V2_ROOM_MINIGAMES | impl | no file changes / no code | QUEUE + status.json | true (no code in main; project lane via mirror — delivery_validator covers PR check) |
| 2026-04-25 | SWO_SANCTUARY_CHAT_PERSISTENCE | impl | no file changes | QUEUE + status.json | true (project lane) |
| 2026-04-25 | SWO_SANCTUARY_BOND_STAGES | impl | no file changes / no code | QUEUE + status.json | true (project lane) |
| 2026-04-25 | SWO_V2_COSMETIC_SPRITE_LAYERS | research | no findings / no brain / no structure | QUEUE + status.json | true (research output didn't structure findings) |
| 2026-04-25 | CRON_DOCTOR_SOFT_HEALTH_SEMANTICS | impl | no file changes / no code | `clarvis/heartbeat/adapters.py` + commit `4ee4da1 fix(heartbeat):…` | **FALSE** |
| 2026-04-25 | SWO_SHARED_SHOP_DIALOG | research | no findings / no structure | QUEUE + SWO_TRACKER | true (project lane) |
| 2026-04-26 | CRON_SYNC_STASH_RECOVERY_REF | general | (n/a) | `scripts/cron/cron_env.sh` + commit `cb197e6 fix(cron-sync):…` | n/a (general type already exempt — listed for context) |
| 2026-04-26 | SWO_V2_DESLOP_SHADER | impl | no file changes | `ROADMAP.md` + QUEUE | true-ish (no shader code in main; project lane) |
| 2026-04-27 | SWO_V2_COMPANION_STATS_SCHEMA | impl | no file changes / no code | QUEUE + SWO_TRACKER | true (project lane) |
| 2026-04-27 | P0_PROJECT_AGENT_MIRROR_RESET_FAILURE_HANDLING | impl | no file changes / no code | `scripts/agents/project_agent.py` + `tests/scripts/…` + commit `55baf40 fix(project-agent):…` | **FALSE** |
| 2026-04-27 | SWO_V2_COMPANION_SCREEN_SURFACE | impl | no file changes / no code | QUEUE + status.json | true (project lane) |
| 2026-04-27 | SWO_V1_ARCHIVE_FORMALIZE | impl | no file changes / no code | QUEUE + status.json | true (project lane) |
| 2026-04-27 | SWO_V2_PLAYER_SPRITE_ALIASING | impl | no file changes / no tests / no code | QUEUE + SWO_TRACKER | true (project lane) |
| 2026-04-27 | SWO_V2_HALFWIRED_FEATURE_FINISH | research | no findings / no brain / no structure | QUEUE + SWO_TRACKER | true (no findings emitted) |
| 2026-04-27 | SWO_V2_NPC_SELECT_SKRUMPEY_GATE | impl | no file changes / no code | QUEUE + SWO_TRACKER | true (project lane) |
| 2026-04-27 | ABSOLUTE_ZERO_ERROR_FALLBACK_COMMIT | impl | no file changes / no code | QUEUE + SWO_TRACKER + `tests/test_*` + commit `3604bb3 test(absolute_zero):…` | **FALSE** |
| 2026-04-27 | SANCTUARY_STAR_CURRENCY_DECISION | research | no findings / no brain / no structure | QUEUE + SWO_TRACKER | true (decision research without structured output) |
| 2026-04-28 | SEMANTIC_OVERLAP_BOOST | impl | no file changes / no tests / no code | QUEUE + commit `22ae399 chore(phi): record SEMANTIC_OVERLAP_BOOST…` | **FALSE** (commit body confirms; bridging memories were stored) |
| 2026-04-28 | PHI_SEMANTIC_SAMPLING_FIX | impl | no file changes / no tests | `clarvis/metrics/phi.py` + `data/phi_regression_baseline.json` + commit `0f033cf fix(phi):…` | **FALSE** |

(`AUTONOMOUS_EXECUTION_CAPABILITY_LIFT` partial-success at 07:00 was a same-day
followup discovered during this audit; it ALSO falls into the false-partial
class — code change in `clarvis/metrics/self_model.py` plus a test edit, commit
`580094b fix(self_model):…`.)

### Counts

- **False partials (Clarvis-internal, real file change in main repo, real commit):** 6
  - CRON_DOCTOR_SOFT_HEALTH_SEMANTICS, P0_PROJECT_AGENT_MIRROR_RESET_FAILURE_HANDLING,
    ABSOLUTE_ZERO_ERROR_FALLBACK_COMMIT, SEMANTIC_OVERLAP_BOOST,
    PHI_SEMANTIC_SAMPLING_FIX, AUTONOMOUS_EXECUTION_CAPABILITY_LIFT.
- **True partials (project lane, no mainline diff — delivery validator owns this):** 11
  - These are all `[SWO_*]` tasks where the work happens in the project mirror,
    not the main Clarvis repo. The PR-evidence check in `delivery_validator.py`
    is the right gate for these; worker_validation should not double-downgrade.
- **True partials (research, missing structured findings):** 3
  - SWO_V2_COSMETIC_SPRITE_LAYERS, SWO_V2_HALFWIRED_FEATURE_FINISH,
    SANCTUARY_STAR_CURRENCY_DECISION. These genuinely failed to emit findings.

## Root cause

`_check_implementation_output()` and `_check_maintenance_output()` looked only
at `output_text`. Two factors collide there:

1. Claude Code's tail summary is human-readable English, not a tool-call
   transcript. Markers like `edit(`, `Write(file_path=…)`, `pytest`, `0 failed`
   rarely appear in the final reply.
2. `output_text` for autonomous heartbeats is captured from the
   `claude -p ... > /tmp/claude_output.txt` tail — which is intentionally a
   short summary, not the full streaming session.

So the validator was effectively asking "did Claude verbatim narrate its tool
use?" — and the answer is usually no, regardless of whether real work shipped.

The postflight ALREADY computed `git_diff_stat` for cost-per-commit tracking
(see `_capture_git_outcome()` at scripts/pipeline/heartbeat_postflight.py:466).
That diff was ignored by the validator.

## Fix (this PR)

1. **`scripts/pipeline/heartbeat_preflight.py`** — new `_capture_pre_task_git_state()`
   captures HEAD SHA + porcelain at preflight start; serialized into
   `preflight_data["pre_task_commit_sha"]` and `pre_task_porcelain`.
2. **`scripts/pipeline/heartbeat_postflight.py`** — `_capture_git_outcome(pre_task_sha)`
   now also computes `git diff --stat <pre_sha>..HEAD` (the *actual* changes
   produced by this task) and `task_porcelain` (uncommitted edits).
3. **`clarvis/heartbeat/worker_validation.py`** —
   `_check_implementation_output()` and `_check_maintenance_output()` accept a
   `git_diff_stat` arg. Real diffs override the text heuristic.
   Bookkeeping-only diffs (`memory/evolution/QUEUE.md`, `SWO_TRACKER.md`,
   `website/static/status.json`, `memory/cron/digest.md`,
   `memory/evolution/QUEUE_ARCHIVE.md`) do NOT count — those are journaling.
   Test files (`tests/`, `test_*.py`, `*_test.py`, `*.test.[tj]sx?`,
   `*.spec.[tj]sx?`) are credited for `has_tests`.
   Code-extension files (`.py`, `.ts`, `.tsx`, `.js`, `.sh`, `.sql`, `.go`,
   `.rs`, `.json`, `.yaml`, …) are credited for `has_code`.
4. **Research validator unchanged.** Research tasks legitimately need
   structured findings / brain storage / headings; a code diff doesn't
   substitute for those.

## Narrower downgrade policy (codified)

For implementation/maintenance tasks, downgrade ONLY when **both**:
- output_text has no tool-call/test/code markers, **and**
- the diff between pre-task SHA and post-task HEAD is empty OR touches only
  bookkeeping paths (QUEUE.md, SWO_TRACKER.md, status.json, digest.md,
  QUEUE_ARCHIVE.md).

For project-lane tasks (`[PROJECT:*]`, `[SWO_*]`, …), the **delivery_validator**
PR-evidence gate (postflight §0.6) remains authoritative. Worker validation
no longer double-downgrades a project task that has no mainline diff — the
delivery validator catches the missing PR.

## Test coverage added

`tests/test_heartbeat_worker_validation.py::TestGitEvidenceOverridesTextHeuristic`
(7 cases): summary-only output with real diff passes; test files in diff credit
`has_tests`; bookkeeping-only diff still downgrades; no-diff-no-text downgrades;
maintenance real diff credits actions; research unaffected; back-compat with
older callers (no git args).

All 68 worker-validation tests pass.

## Backfill not done

The 18 already-recorded `partial_success` outcomes are not retroactively
re-classified — outcome history stays immutable. The fix applies prospectively
from this commit forward.

## Followups (not done in this PR)

- Consider extending the same git-evidence signal to `delivery_validator.py`
  so internal Clarvis tasks that aren't project-lane but still produced a real
  Clarvis commit get an extra positive signal (current implementation already
  exempts non-project tasks, so this is just defensive).
- Audit `clarvis/queue/engine.py::end_run` to ensure `partial_success` outcomes
  re-enter the queue with sensible retry policy (out of scope here).
