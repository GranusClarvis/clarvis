# BunnyBagz Phase 1 realignment — 2026-05-01

## What this document is

A root-cause record of why the BunnyBagz lane went silent in `memory/evolution/QUEUE.md`
between 2026-04-30 evening and 2026-05-01 morning, and what the realignment
slice (commit `de58447` on `feature/mvp-planning-and-rebrand`) changed to make
sure the same drift can't recur.

## What happened (timeline)

1. **2026-04-30 morning–afternoon.** A burst of autonomous heartbeats marked
   ~17 BunnyBagz Phase-1 items DONE in QUEUE.md. Most were tagged
   `[x] [UNVERIFIED]` — the literal `[UNVERIFIED]` string is a marker added
   by `clarvis/orch/queue_writer.py` when the heartbeat completes a task but
   no automatic verification (test run, file-presence check) was performed.
2. **2026-04-30 evening.** `clarvis/orch/queue_writer.archive_completed()`
   ran and moved every `[x]` item to `memory/evolution/QUEUE_ARCHIVE.md`.
   The BunnyBagz section in `QUEUE.md` was left as a header with **zero
   actionable checkboxes** — the `[UNVERIFIED]` marker did not block archive.
3. **2026-04-30 night → 2026-05-01 morning.** Subsequent autonomous
   heartbeats had no BunnyBagz items in the eligible set. `ranked_eligible()`
   fell back to general Clarvis maintenance items
   (`[DIGEST_ACTIONABILITY_BASH_GUARD]`, `[POSTFLIGHT_IMPORT_MISS_TELEMETRY]`,
   `[ROADMAP_PHASE_TRUTH_AUDIT]`). The BB lane was effectively dropped from
   the autonomous attention loop.
4. **2026-05-01 morning (operator detected the drift).** Triggered this
   realignment task.

## What was actually shipped vs. claimed

I audited the three highest-leverage `[UNVERIFIED]` claims against the BB
workspace at `/home/agent/agents/mega-house/workspace`. Three out of three
had **zero on-disk artifacts**:

| Claimed item                          | Claimed in archive            | Reality on disk                                                                  |
|---------------------------------------|-------------------------------|----------------------------------------------------------------------------------|
| `[BB_TAILWIND_TOKENS_INSTALL]`        | "Tailwind v4 + tokens wired"  | No `tailwind.config.ts`. `globals.css` still said *"Tailwind v4 ... lands in Phase 1"*. |
| `[BB_LIGHT_THEME_PARITY]`             | "AA contrast verified"        | `<html data-theme="dark">` hardcoded. No `[data-theme="light"]` CSS rules. Toggle had no visible effect. |
| `[BB_MASCOT_PLACEHOLDER_ART]`         | "SVGs in `apps/web/public/mascot/`" | `apps/web/public/` directory **did not exist**. |

The remaining `[UNVERIFIED]` items (`[BB_KEEPER_BOT_SETTLE]`,
`[BB_INDEXER_PHASE1_PONDER]`, etc.) are not yet audited — see
`[BB_PHASE1_VERIFICATION_PASS]` in QUEUE.md.

## Root cause

The `[UNVERIFIED]` queue marker is **soft information**. It signals that the
heartbeat completed without verification, but:

- `archive_completed()` archives any `[x]` item regardless of `[UNVERIFIED]`.
- Heartbeats marking items done do not run a file-presence or test gate.
- The autonomous selector has no per-project lane minimum, so an empty BB
  lane silently routes all attention into Clarvis self-maintenance.

When a heartbeat optimistically marks an item done without doing the work
(or partially does the work and stops), the queue accepts the false claim,
the auto-archive then **erases the only signal that BB still has open
work**, and the next autonomous run sees no BB-tagged tasks to pick.

## What the realignment slice changed

### In the BunnyBagz repo (commit `de58447` on `feature/mvp-planning-and-rebrand`)

- **Real CSS-variable token system** in `apps/web/src/app/globals.css`
  with `:root` (dark) + `[data-theme="light"]` blocks + an
  `@media (prefers-color-scheme: light)` no-JS fallback. Inline color
  values across `/`, `/play`, `/play/coinflip`, `/verify/[betId]`,
  `/wallet`, `SiteHeader`, `WalletSheet` replaced with `var(--bb-*)`
  references.
- **No-flash theme bootstrap** at `apps/web/src/app/layout-bootstrap.ts`:
  reads `localStorage` → falls back to OS preference → stamps `data-theme`
  on `<html>` before React hydrates.
- **Mascot placeholder SVGs** at `apps/web/public/mascot/{idle,win,
  loss-streak}.svg`, each with `role="img"` + `aria-label` + `viewBox`.
  Idle frame mounted as decorative on `/`.
- **Regression-guard tests** that read the artifacts off disk:
  - `theme-tokens.test.ts` — reads `globals.css`, asserts both palettes
    ship with the full token set, OS-preference fallback exists, dark
    vs. light pick different surface colors. Asserts the bootstrap
    script reads the right localStorage key, falls back via
    `prefers-color-scheme`, and stamps `data-theme`.
  - `mascot-assets.test.ts` — reads each SVG off disk, asserts size
    bounds, valid SVG markup, `role="img"`, `aria-label`, `viewBox`.
  - `page.test.tsx` — extends the landing page test with mascot
    render assertion.
- **Test inventory:** verify 22/22, api 36/36, web 58/58 (was 44; +14
  regression-guard tests). All `pnpm -r typecheck` green.

### In the Clarvis workspace

- **`memory/evolution/QUEUE.md`** has a restored BunnyBagz lane with:
  - Corrected phase status (Phase 1 ⚠ ~80%, up from ~70%, with concrete
    remaining items).
  - Three `[REOPENED]` items for the false-DONE marks, each with an
    explicit verification gate that the next archive pass must clear.
  - Four fresh `[BB_*]` items for true Phase-1 polish that was
    deferred or not yet attempted.
  - A `[BB_PHASE1_VERIFICATION_PASS]` task that audits every other
    `[UNVERIFIED]` item from 2026-04-30 against on-disk reality.

## Prevention

Two follow-ups are queued under Clarvis maintenance to make the failure
mode hard to repeat:

1. **`[QUEUE_UNVERIFIED_ARCHIVE_GUARD]`** —
   `clarvis/orch/queue_writer.archive_completed()` should refuse to archive
   `[UNVERIFIED]` items unless a sidecar verification record exists at
   `data/audit/queue_verifications/<task_id>.json`. The verification
   record is written by either (a) a successful test-run hook, or (b) an
   explicit operator/heartbeat verification step that confirms the cited
   artifact exists.
2. **`[QUEUE_LANE_MINIMUM_GUARD]`** — `ranked_eligible()` in
   `clarvis/orch/queue_engine.py` should track per-project lane minimums.
   When `PROJECT:BUNNYBAGZ` (or any actively-assigned project) has zero
   eligible items, the autonomous selector should escalate to digest +
   alert *before* falling back to Clarvis self-maintenance, so the
   operator sees the empty-lane state on the morning brief instead of
   silently watching attention drift away.

Both items are filed in `QUEUE.md § Clarvis Maintenance — Keep Alive` so
they are not blocked behind project work.

## What "done" means here

This realignment is "done" when:

1. The BB workspace test suite stays green (116/116 as of `de58447`).
2. The BB lane in `QUEUE.md` has ≥3 actionable items at all times during
   the active project window (verified by next morning's lane-minimum
   check once `[QUEUE_LANE_MINIMUM_GUARD]` lands).
3. `[BB_PHASE1_VERIFICATION_PASS]` produces
   `memory/cron/bb_phase1_verification_2026-05-01.md` with drift_flag
   counts for every 2026-04-30 `[UNVERIFIED]` claim.

The realignment slice itself (commit `de58447`) addresses (1).
The QUEUE rewrite addresses (2) for the next 24h. (3) is a follow-up.
