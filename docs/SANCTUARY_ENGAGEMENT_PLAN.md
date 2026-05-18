# Star Sanctuary — Engagement Plan (2026-05-18)

**Status:** ACTIVE. Operator-set direction for the Companion / Sanctuary core
loop. Supersedes purely additive feature work in `SWO_TRACKER.md §V2 — Companion-First Core Loop` (those PRs shipped; the surface is now mechanically wired but **design-flat**). This doc is the binding plan for the next 7 PRs that turn the surface into a real engagement loop.

This plan governs **SWO sanctuary work only**. Casino work has its own plan
(`memory/evolution/cosmic_casino_delivery_plan_2026-05-15.md`).

## 1. Where we stand

Infrastructure (shipped on `origin/dev`, confirmed 2026-05-18):

| Surface | State |
|---|---|
| `lib/sanctuary/companionStats.ts` + decay + needs | ✅ |
| `lib/sanctuary/mood.ts` | ✅ |
| `lib/sanctuary/bondStages.ts` + 4-stage chat tone | ✅ |
| `lib/sanctuary/chatPersonality.ts` + chat memory | ✅ |
| `lib/sanctuary/expeditions.ts` (pure engine, types, reducer) | ✅ — **but no DB / API / UI** |
| STAR ledger (earn/spend/balance, soulbound on Monad) | ✅ |
| Companion screen + journal + cozy polish | ✅ |
| Companion `feed / pet / talk / sleep / play` actions | ✅ — but every action bumps similar stats |

The loop is mechanically correct and visually polished. The **design layer is
flat**:

- Action choice is not meaningful — all 5 actions push similar deltas.
- No hidden preference profile per Skrumpey.
- No need-state multiplier; no mood multiplier.
- No reason to sleep. Sleep is decorative.
- No daily action cap, so check-ins don't matter and grinding doesn't either.
- Expeditions exist in pure-engine form but a player cannot start one.

This plan ships **7 PRs in order** that close those gaps without enlarging
scope into V3, new minigames, new world zones, or any other deferred surface.

## 2. PR-quality rules (binding)

These rules apply to every PR in this plan and to any future sanctuary PR
unless the operator overrides in writing.

1. **No duplicate / in-flight work.** Before opening: run
   `git log --oneline origin/dev -50` and `gh -R InverseAltruism/Star-World-Order pr list --state open`.
   If the work already landed (full or partial) or is in flight under another
   branch, do not open a competing PR — extend or reuse.
2. **Size.** 300–800 lines per PR including tests. Larger features split along
   clean seams (Expeditions splits into 3: DB+API → overlay UI → polish).
3. **Branching.** Rebase on `origin/dev`. **Never merge.** Squash-or-rebase
   merge only, no merge commits in feature history.
4. **Tests required per PR:**
   - Vitest unit/component for **every** new logic file.
   - At least one Playwright happy-path **and** one failure / negative-path
     test for any player-facing flow.
   - CI gates green: type-check, vitest, eslint, playwright. PRs that skip
     any of these will be reverted.
5. **PR description must contain:**
   - Design rationale (which mechanic from §3 below).
   - Acceptance checklist (cross-referenced to this doc).
   - Actual local test results with **counts pasted** (e.g.
     `vitest 514/514 green`, `playwright 4/4 green`).
6. **Commit prefix:** `feat(sanctuary): …` / `fix(sanctuary): …` /
   `docs(sanctuary): …`. Pure-engine modules under `lib/sanctuary/` may use
   `feat(sanctuary-core): …` for clarity.

## 3. Design doctrine (binding)

Carve every mechanic against these rules. If a feature does not satisfy them,
it does not ship.

### 3.1 Action choice must be meaningful

- Each Skrumpey gets a deterministic, seeded **preference profile**:
  loved / liked / neutral / disliked / hated across the 5 actions
  (`feed, pet, talk, sleep, play`). Same wallet × different token_id → different profile.
- **Bond delta** = base × preference × need-state × mood:
  - preference: `4× loved · 2× liked · 1× neutral · 0× disliked · −1× hated`
  - need-state: `0.5× when need bar full · 1× nominal · 1.5× when need bar low · 2× when critical`
  - mood: derived from current stats per `mood.ts`; multiplier ∈ [0.5, 1.25].
- Discovery: the journal reveals **one preference clue** per N matched
  interactions (e.g. "Aurora seemed especially happy when you fed them today").

### 3.2 Sleep must matter

- 24h with no full sleep cycle → `Tired` mood gates in. While Tired, every
  bond delta on non-sleep actions is halved.
- A full sleep cycle clears the Tired gate and grants a dream-reward with a
  **non-zero floor** (always at least 1 STAR + 1 bond).
- Early-wake (interrupting an active sleep cycle) costs −2 bond and writes a
  short journal entry explaining the cost.

### 3.3 Risk / reward must be deterministic

- Expedition outcomes are deterministic against `(seed, choices)` — same
  seed × same choices → same outcome. Server records the seed at start.
- RNG is allowed only for **aesthetic prizes** (cosmetic skin tone, particle
  color, journal flourish) — never for whether the player won or lost.
- Failure paths cost STAR; success paths grant STAR + bond + trait.

### 3.4 Variable rewards always have a floor

- Every interaction that "rolls" for a bonus also guarantees a baseline:
  - 5–10% chance of bonus STAR (1–3) on a successful interaction.
  - 0.5–1% chance of rare trinket.
  - Always at least the baseline bond / stat delta from the interaction
    itself.

### 3.5 Compassionate streaks

- Daily streaks pause on **1 missed day**, do not reset.
- 2 consecutive missed days → reset.
- HUD chip surfaces the streak; 7 / 14 / 30 milestones unlock journal
  entries, not stat lifts (identity over power).

### 3.6 Identity over power

- Bond milestones reveal personality / preference / journal lore. They
  **must not** unlock raw stat multipliers, raw STAR drops, or any other
  power-creep.

## 4. Anti-patterns (explicit guard)

Reviewers must reject PRs that introduce any of these:

- Notification spam. Need callouts may surface once per session per stat;
  badges are passive.
- Pay-to-not-lose. No STAR sink whose only function is to prevent decay.
- Full-reset streaks on a single miss (§3.5 above).
- Variable rewards with a zero-outcome floor (§3.4 above).
- Forced social / share gates (Twitter share, Discord join) on any reward.

## 5. The 7 PRs, in order

Each PR is sized to fit the 300–800 line rule and ship with its own
test coverage. Tags are the binding lane labels — heartbeat scheduler
should treat them as `[SWO_V2_SANCTUARY_*]` and route to the project lane.

### PR1 — `[SWO_V2_SANCTUARY_PREFERENCE_PROFILE]`

**Goal.** Preference profile per token_id + need-state multiplier wired into bond math.

**Files.**
- `lib/sanctuary/preferences.ts` — pure module. Deterministic seeded profile
  derived from `(token_id, contract_address)` returning
  `{ feed, pet, talk, sleep, play } → 'loved'|'liked'|'neutral'|'disliked'|'hated'`.
- `lib/sanctuary/preferences.test.ts` — vitest unit.
- Hook into `interactWithCompanionV15` (current
  `lib/sanctuary/companionAction.ts`): bond delta multiplied by preference
  rank × need-state × mood.
- `lib/sanctuary/__tests__/companionAction.test.ts` — extend.
- Journal: one preference clue per N matched-preference interactions.

**Acceptance.**
- (a) Two Skrumpey on the same wallet have **different** profiles (assert via
  vitest fixture).
- (b) `loved` action bond delta = 4× `neutral` baseline.
- (c) `hated` action **subtracts** bond.
- (d) Journal-clue surfaces after N = 3 matched interactions (configurable
  constant; assert constant + test both N−1 and N triggers).

**E2E.** Playwright spec: feed two companions on one wallet; assert differing
bond deltas via API response. Attempt a hated action; verify negative
outcome surfaces in journal + bond bar.

### PR2 — `[SWO_V2_SANCTUARY_EXPEDITIONS_DB_API]`

**Goal.** Persistence + API for the existing pure-engine `expeditions.ts`.

**Files.**
- Migration: `sanctuary_expeditions` (id, token_id, expedition_id, started_at, ended_at, outcome) and `sanctuary_expedition_progress` (expedition_row_id, current_step_id, choices_jsonb).
- Routes: `app/api/sanctuary/expeditions/{list,start,choose,abandon}/route.ts`.
- Seeds: `data/sanctuary/expeditions/{easy,medium,hard}.json` — three starter
  expeditions, narratively distinct.
- Tests: route-level vitest for each endpoint + reducer round-trip test.

**Acceptance.**
- (a) `start` deducts STAR (cost in seed JSON).
- (b) Failure path costs STAR; success grants STAR + bond + trait.
- (c) Outcomes are deterministic against `(seed, choices)` (same input →
  same output across two runs).

**E2E.** Playwright spec drives `start → choose → choose → terminal` for the
easy expedition (happy path) and walks the hard expedition's risky branch to
a failure outcome (negative path).

### PR3 — `[SWO_V2_SANCTUARY_EXPEDITIONS_UI]`

**Goal.** Overlay UI that consumes PR2's API.

**Files.**
- `components/sanctuary/overlays/ExpeditionDialog.tsx` — overlay with
  narrative pane + choice buttons + resume support.
- Hook into `QuestBoard.tsx`: "Begin expedition" CTA when expedition unlocked
  by an NPC interaction.
- DB-backed resume: page reload mid-expedition restores current step.
- Tests: component vitest covers (a) renders current step, (b) choice click
  POSTs `/choose`, (c) abandon CTA POSTs `/abandon`, (d) resume reads
  current_step_id from DB on remount.

**E2E.** Full expedition walkthrough in a browser; reload mid-flight; verify
the dialog resumes at the correct step.

### PR4 — `[SWO_V2_SANCTUARY_SLEEP_DYNAMICS]`

**Goal.** Sleep that matters per §3.2.

**Files.**
- `lib/sanctuary/sleepDynamics.ts` — pure module.
  - `isTired(stats, now)` → boolean (24h+ since last full sleep).
  - `applyTiredMultiplier(bondDelta, isTired)` → halved when tired.
  - `dreamReward(stats, now)` → `{ star, bond, journalLine }` with non-zero floor.
  - `applyEarlyWake(stats, sleepStartedAt, now)` → bond −2 + journal line.
- Wire into `companionAction.ts` (multiplier) and the sleep endpoint
  (reward + early-wake penalty).
- Tests: unit cover 3 cases — Tired gate fires after 24h; full cycle clears
  Tired + grants ≥ floor; early-wake fires the −2 + journal.

**E2E.** Playwright: drive each case via test-only time-skip helper
(matches the pattern in `companionStats.test.ts` for `stats_updated_at`):
24h+ no sleep → assert bond delta halved on a `pet`; full cycle → assert
dream reward visible; early-wake within first 30s of sleep → assert −2 +
journal entry.

### PR5 — `[SWO_V2_SANCTUARY_STREAKS]`

**Goal.** Compassionate streak counter per §3.5.

**Files.**
- Migration: `sanctuary_companion_streaks` (token_id, current_streak, longest_streak, last_visit_at, paused_since_at).
- `lib/sanctuary/streaks.ts` — pure module with reducers.
- HUD: `CompanionHUD.tsx` adds a streak chip.
- Milestones: 7 / 14 / 30 → journal entry on cross-over (no stat lift).
- Tests: unit covers 1-miss-pauses, 2-misses-resets, milestone fires once.

**E2E.** Playwright simulates a 9-day timeline (test-only time-skip): day 1–4
interact, day 5 skip, day 6–9 interact. Assert streak still active on day 9
with one paused day in the history, and 7-day milestone journal entry
present.

### PR6 — `[SWO_V2_SANCTUARY_STAR_ECONOMY_SINKS]`

**Goal.** STAR sinks that respect §3.3 / §3.4.

**Files.**
- Cosmetic gacha pull added to the existing shop (`components/sanctuary/overlays/ShopDialog.tsx`):
  - Guaranteed cosmetic floor on every pull.
  - 1–2% rare-cosmetic chance.
  - No "premium pity" mechanic; floor is the only no-loss guarantee.
- Expedition entry cost confirmation lands with PR2 (no rework here, just a
  reference assertion in tests).
- Tests: shop spec covers (a) every pull yields at least 1 cosmetic,
  (b) distribution over 1000 simulated pulls is within tolerance of the
  configured table.

**E2E.** Playwright: 5 pulls all yield at least one cosmetic; visible
"Rare!" badge fires when the configured rare slot lands.

### PR7 — `[SWO_V2_SANCTUARY_VARIABLE_REWARDS]`

**Goal.** Variable rewards on the existing 5 actions per §3.4.

**Files.**
- `lib/sanctuary/variableRewards.ts` — pure module.
  - 5–10% chance of bonus STAR (1–3) on a successful interaction.
  - 0.5–1% chance of rare trinket.
  - **Always** a floor: base bond delta + base stat delta unchanged.
  - Bonus emits a visible badge event for `CompanionHUD`.
- Wire into `companionAction.ts` after preference + need-state multiplier
  (so bonus is on top of, never instead of, the base reward).
- Tests: unit covers (a) 1000-simulation distribution within ±0.5%,
  (b) bonus badge fires on bonus, (c) zero-bonus path still returns the floor.

**E2E.** Playwright drives 50 interactions with a fixed RNG seed; asserts
the bonus badge appears at least once (against the configured probability)
**and** that every interaction surfaces the floor reward in the journal.

## 6. Execution order + lane

| PR | Tag | Order | Track |
|---|---|---|---|
| 1 | `[SWO_V2_SANCTUARY_PREFERENCE_PROFILE]` | first | A — Loop depth |
| 2 | `[SWO_V2_SANCTUARY_EXPEDITIONS_DB_API]` | second | A — Loop depth |
| 3 | `[SWO_V2_SANCTUARY_EXPEDITIONS_UI]` | after PR2 | A — Loop depth |
| 4 | `[SWO_V2_SANCTUARY_SLEEP_DYNAMICS]` | parallel with PR2/3 | B — Care depth |
| 5 | `[SWO_V2_SANCTUARY_STREAKS]` | after PR4 | B — Care depth |
| 6 | `[SWO_V2_SANCTUARY_STAR_ECONOMY_SINKS]` | after PR3 | C — Economy |
| 7 | `[SWO_V2_SANCTUARY_VARIABLE_REWARDS]` | last | C — Economy |

PR1 is the foundation — everything else builds on the preference signal.
PR2 is the heaviest persistence piece. PR3 unlocks the existing engine. PR4
and PR5 land in parallel with the expedition track. PR6 and PR7 land last —
both depend on the upstream signals from PR1/PR4 to keep the economy
honest.

## 7. Out of scope (operator-set)

The following are **not** part of this plan; any PR that touches them must
be operator-approved first:

- V3 (`game/v3/`, `public/sanctuary-v3/`, `?v=3` route) — frozen per
  `swo_sanctuary_v3_deferred_2026-04-26.md`.
- New minigame scenes beyond the 7 shipped.
- New world zones / hub map.
- Replacing painted room backgrounds.
- New RD asset generation outside the V2 companion-surface allowance.
- Mobile-app shell, push notifications, voice chat.
- Multiplayer companion features.
- On-chain companion state (STAR is on-chain; companion stats are off-chain
  by design).

## 8. Definition of "done"

Each PR closes when, all of these are true:

1. PR is merged into `origin/dev`.
2. Vitest + Playwright counts pasted in PR description and matching the
   passing job in CI.
3. The matching row in `memory/evolution/SWO_TRACKER.md §Sanctuary Engagement V2`
   is flipped to ✅ with a commit SHA reference.
4. The matching `- [ ]` row in `memory/evolution/QUEUE.md §SWO Sanctuary Engagement`
   is flipped to `- [x]` with the PR number.

No row closes on `[UNVERIFIED]`. Every row carries a concrete artifact path
(file under `lib/sanctuary/`, a Playwright spec, or a migration).
