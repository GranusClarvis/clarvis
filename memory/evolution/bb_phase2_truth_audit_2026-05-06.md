# BunnyBagz Phase 2 — Truth Audit (2026-05-06)

> Verdict: **Phase 2 should NOT be archived as DONE yet.** Three of the
> four ROADMAP exit lines hold against on-disk artifacts; the fourth
> ("e2e green") is contradicted by the latest pushed commit's CI run on
> `feature/mvp-planning-and-rebrand` — six Playwright specs failed.
> Phase 3 P1 promotion stays blocked on `[BB_PHASE2_E2E_GREEN_GAP_FIX]`.

Repo: `GranusClarvis/bunnybagz` · branch `feature/mvp-planning-and-rebrand`
Local workspace: `/home/agent/agents/mega-house/workspace`
Latest local commit: `3808b0b` (geo enforce-mode middleware, Phase 3)
Latest pushed commit: `3e62bb6` (BB_LOGO_INTEGRATION) — 4 commits unpushed

This audit mirrors `bb_phase2_truth_audit_2026-05-04.md` and
`bb_phase2_audit_2026-05-05.md`. It walks each ROADMAP Phase 2 exit
bullet against on-disk artifacts only — archive entries are NOT
considered evidence.

## ROADMAP Phase 2 exit criteria (verbatim)

> all 3 games playable in ETH and USDm on testnet; recent bets in wallet
> sheet; e2e green; light + dark themes look intentional, not mechanical.

## Test inventory verified live (2026-05-06)

| Suite | Result |
|---|---|
| `pnpm --filter @bunnybagz/web test` | **332/332** ✓ (29 files, 5.4s) |
| `pnpm --filter @bunnybagz/api test` | green (0 fail / 0 skip) |
| `pnpm --filter @bunnybagz/indexer test` | green (0 fail / 0 skip) |
| `pnpm --filter @bunnybagz/verify test` | green (0 fail / 0 skip) |
| `forge test` | NOT RUN (no `forge` binary on this host; CI is the gate) |

Vitest count grew from 283 (2026-05-05) → 332 (2026-05-06) — RecentBetsList,
RecentOutcomesStrip-per-game, USDM permit-flow, geo-enforce, and BunnyBagz
brand-mark suites all added coverage. No skips observed.

## Bullet-by-bullet verdict

### 1. "all 3 games playable in ETH and USDm on testnet" — ✅ HOLDS

**Deploy artifact** (`packages/contracts/deployments/6343.json`):
- bankroll `0x33C5B6a95e71611F5dC821A74DDAD0F746fF2dFf`
- coinflip `0x064b8bfc03b23D2b525deD9d3969090347A21983`
- dice `0xAC023542A8168465EE4A1b3e8Ae0f58F36A6d84B`
- hilo `0xd9B9b6c37ad4f3D5b07ae76dE261c5C865600d6e`

`bb_phase2_testnet_live_2026-05-05.md` cross-checks `cast call` evidence
that all four contracts hold non-zero bytecode on chain 6343 and
`bankroll.isGame(addr)==true` for each game.

**Lobby unlock** — `apps/web/src/app/play/page.tsx:74` flips card status
from `"phase2"` to `"live"` whenever the address resolves; `play/page.tsx`
no longer hardcodes `"phase2"` for dice/hilo.

**USDM permit UI on all 3 game pages:**
- `apps/web/src/app/play/coinflip/page.tsx` imports
  `placeUsdmBet` from `@/lib/usdm-flow`, mounts `<TokenToggle>`, branches
  `placeBet()` on `token === "usdm"`, surfaces `usdmError` UI.
- `apps/web/src/app/play/dice/page.tsx` — same imports, same branching.
- `apps/web/src/app/play/hilo/page.tsx` — same imports, same branching.
- Vitest USDM specs ship at
  `apps/web/src/app/play/{coinflip,dice,hilo}/__tests__/usdm.test.tsx`
  (≥6 cases each per the closed `[BB_PHASE2_USDM_PERMIT_UI_PLAY_PAGES]`
  acceptance contract).

**Caveat:** the `PermitForwarder` contract addr resolution + a
funded testnet USDm faucet are still operator-gated for an end-to-end
on-chain USDm round-trip. The UI invokes the strategy correctly; an
on-chain USDm settle has not yet been observed.

### 2. "recent bets in wallet sheet" — ✅ HOLDS

`apps/web/src/components/WalletSheet.tsx:22` imports `RecentBetsList`
and mounts it at line 159 (`<RecentBetsList address={address} />`).
Component file `apps/web/src/components/RecentBetsList.tsx` (~5KB)
ships, vitest coverage at
`apps/web/src/components/__tests__/RecentBetsList.test.tsx` exercises
populated / empty / error / refetch / accessibility paths.

Cross-game `/api/history/wallet` edge endpoint exists (referenced by
RecentBetsList; backend covered by indexer + api test suites).

`RecentOutcomesStrip` is also generalized with a `game` prop and
mounted on each play surface:
- `coinflip/page.tsx:367` — `game="coinflip"`
- `dice/page.tsx:347` — `game="dice"`
- `hilo/page.tsx:505` — `game="hilo"`

This satisfies the spirit of "recent bets in wallet sheet" plus the
per-game outcomes strip the operator's UX_PLAN calls for.

### 3. "e2e green" — ❌ DOES NOT HOLD

Specs ship and the `e2e:` CI job is wired in `.github/workflows/ci.yml`,
but the most recent CI run on the live branch is RED.

**GitHub Actions run on `feature/mvp-planning-and-rebrand`:**
- Run URL: <https://github.com/GranusClarvis/bunnybagz/actions/runs/25388220194>
- Triggered: 2026-05-05T16:15Z (commit `08dcdfb` —
  `[BB_PHASE2_RECENT_BETS_WALLET_SHEET]`)
- e2e job: **FAILED** after 18m4s
- Result line: `1 skipped 6 failed 20 passed (6.8m)`

**Failing specs** (each fails in all 3 projects: chromium,
mobile-chromium, mobile-safari):

| Spec | Failing test | Failure |
|---|---|---|
| `e2e/coinflip.spec.ts:15:5` | "Home → /play → Coinflip card → /play/coinflip surface" | (failure mode — see playwright-report artifact) |
| `e2e/hilo.spec.ts:26:5` | "Higher / Lower direction buttons are present (UX_PLAN §3 thumb-zone)" | `getByTestId('hilo-dir-higher')` not visible after 5s. The HiLo page now opens in a "no session yet" state where the direction CTAs only appear after `openSession`; the spec drove the unconnected smoke walk and never opens a session. |

Other red jobs on the same run (separate from e2e but blocking the
"e2e green" promise — CI as a whole is not green):
- `packages/contracts (Foundry)` — failed at `forge build` (regression
  introduced by a contract change; details in run log).
- `packages/contracts (halmos symbolic proofs)` — failed.
- `packages/contracts (Medusa coverage-guided invariant fuzz)` — failed.

**Plus 4 unpushed local commits** that have not even reached CI yet:
- `f6993f5` `[BB_PHASE2_RECENT_OUTCOMES_DICE_HILO]`
- `a11c14e` `[BB_PHASE3_BANKROLL_CIRCUIT_BREAKER]`
- `03af4f0` `[BB_PHASE3_PNL_MONITOR_CRON]`
- `3808b0b` `[BB_PHASE3_GEO_ENFORCE_MODE]`

So even if the 16:15 run had been green, the head of the branch is
running ahead of the last validated commit.

### 4. "light + dark themes look intentional, not mechanical" — ✅ HOLDS

`apps/web/src/app/globals.css` ships a full `data-theme` token system
(60 lines for the dark default + a dedicated `[data-theme="light"]`
block at line 60+ that overrides `*-fg` variants for AA contrast).
Brand-mark light/dark PNG swap is CSS-only (`bb-mark--{light,dark}-theme`).

Bootstrap script: `apps/web/src/app/layout-bootstrap.ts` paints the
chosen theme before hydration so there's no flash. Vitest at
`apps/web/src/app/__tests__/theme-tokens.test.ts` asserts the token
matrix; `apps/web/src/__tests__/contrast-audit.test.ts` runs the WCAG-AA
audit across both themes.

WalletSheet surfaces a manual theme toggle. UX_PLAN §6 token system
is materially landed.

## Resolution of the 5 prerequisite tasks (per 2026-05-05 audit)

| Task | Verdict | Evidence on disk |
|---|---|---|
| `[BB_PHASE2_USDM_PERMIT_UI_PLAY_PAGES]` | ✅ Closed | TokenToggle + placeUsdmBet wired in all 3 play pages; per-game USDM vitest specs. |
| `[BB_PHASE2_RECENT_BETS_WALLET_SHEET]` | ✅ Closed | RecentBetsList component + WalletSheet mount + tests. |
| `[BB_PHASE2_RECENT_OUTCOMES_DICE_HILO]` | ✅ Closed | RecentOutcomesStrip generalized with `game` prop, mounted on dice + hilo. |
| `[BB_PHASE2_E2E_GREEN_IN_CI]` | ⚠ Partial — pinning shipped, green run **not** observed | Action SHAs pinned in `e2e:` job; `@playwright/test@1.59.1` frozen; PR #2 CI run failed; main feature branch CI run failed (6 specs red). |
| `[BB_PHASE2_TESTNET_DEPLOY_DICE_HILO_LIVE]` | ✅ Closed | Chain 6343 deploys verified by `cast call` (see 2026-05-05 doc). |

## Why this matters

The 2026-05-05 audit projected Phase 2 closure pending the green CI
run. That run happened (twice — PR #1 mvp branch run 25388220194, PR
#2 e2e-pin branch run 25396503889). Both were red. The exit criterion
verbatim is *"e2e green"* — the gate is a passing run, and we have
none on the live branch.

Two distinct categories of breakage:
1. **Test-side drift** — the hilo unconnected smoke spec asserts on
   `hilo-dir-higher` / `hilo-dir-lower` testids that only exist after
   `openSession`. This is a spec-level mismatch with the new state
   machine; trivially fixable by either (a) updating the spec to drive
   `openSession` first, or (b) rendering the direction CTAs as disabled
   pre-session so the testids are present.
2. **Side-effect failures** — forge build, halmos, medusa all failed
   on the same run. Forge build failure means contract changes pushed
   without local `forge build` validation; halmos + medusa likely fail
   downstream because forge build hasn't produced artifacts.

## Highest-leverage next steps

P1 (Phase 2 closure):

1. `[BB_PHASE2_E2E_GREEN_GAP_FIX]` — fix the 6 red Playwright specs
   (`coinflip.spec.ts:15` × 3 projects + `hilo.spec.ts:26` × 3
   projects). Either move the assertion behind `openSession` for hilo
   and verify the coinflip walk handles whatever DOM change triggered
   its failure, or render the relevant CTAs early with disabled state.
   **Acceptance:** one fresh `feature/mvp-planning-and-rebrand` CI run
   shows the `e2e:` job green (18/18 specs pass, 0 skipped, 0 flaky)
   with no red sibling jobs.

2. `[BB_PHASE2_FORGE_BUILD_RED_FIX]` — diagnose why `forge build` is
   red on the same run. If it's the new Phase-3 circuit-breaker
   contract introducing a Solidity error, fix or revert. Halmos +
   Medusa are likely downstream of this.

3. `[BB_PHASE2_PUSH_LOCAL_FEATURE_BRANCH]` — push the 4 local commits
   so the head of `feature/mvp-planning-and-rebrand` is on origin and
   CI gates the head of the lane. (Recurrent obligation reminder: the
   git-hygiene escalation is now level 1.)

P2 (post-closure cleanup):

4. `[BB_PHASE2_E2E_FLAKE_AUDIT]` — once green, run the e2e job 5×
   consecutively and require zero retries before archiving the e2e
   exit gate.

## Phase 2 archive decision

**Phase 2 is NOT archived as DONE.** Three of four ROADMAP exit lines
hold; the fourth (e2e green) is observably red. Phase 3 P1 promotion
stays blocked on `[BB_PHASE2_E2E_GREEN_GAP_FIX]`. Re-audit after the
fix lands and a green CI run is captured.

Phase 3 P2 items (animation, mascot art, audit firm prep, multisig,
status page, etc.) may continue accruing in the queue but cannot
promote to P1 until Phase 2 archives.
