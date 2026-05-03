# BunnyBagz Phase 1 — End-to-End Status (2026-05-02 evening)

Single source of truth for Phase 1 completion. Supersedes the morning's
verification pass (`bb_phase1_verification_2026-05-01.md`) by adding the
afternoon's commits and a concrete remaining-gap list.

Repo: `GranusClarvis/bunnybagz` · branch `feature/mvp-planning-and-rebrand`
Local workspace: `/home/agent/agents/mega-house/workspace`
Test inventory (this session): web **132/132**, api **36/36**, verify **22/22**.

## Phase status snapshot

- **Phase 0 — Repo & rails: ✅ DONE.** Monorepo, CI green, brand locked.
- **Phase 1 — Coinflip end-to-end on testnet: ⚠ ~92%** (up from ~80% on
  2026-05-01 morning after today's three commits closed all known
  autonomous-doable Phase-1 gaps except the indexer/KV/wagmi-codegen trio).
- **Phase 2 — Dice + HiLo + USDM: ⚠ ~25%.** Dice contract drafted; HiLo,
  USDM, and Playwright still missing.
- **Phase 3+ — operator-blocked.** Audit, multisig, mainnet.

## Verified completed (commit + on-disk evidence)

| Item | Commit | Evidence |
|---|---|---|
| BB_TAILWIND_TOKENS_REAL | `de58447` + `e5aa23c` | `apps/web/src/app/globals.css` token system; `theme-tokens.test.ts` green |
| BB_LIGHT_THEME_PARITY_REAL | `d875f17` | `layout-bootstrap.ts` + 6 behavioural bootstrap tests |
| BB_MASCOT_PLACEHOLDER_REAL | `de58447` | `apps/web/public/mascot/{idle,win,loss-streak}.svg` + `mascot-assets.test.ts` |
| BB_MASCOT_WIN_CELEBRATE_WIRE | `12c3f03` | `MascotCelebrate.tsx` + 5-test suite |
| BB_RECENT_OUTCOMES_STRIP | `f513618` | `RecentOutcomesStrip.tsx` (loading/empty/populated/errored) + 7-test suite |
| BB_THEME_CONTRAST_AUDIT | `a017122` | `lib/contrast-audit.ts` + 49 vitest cases; `axe-baseline.json` artefact |
| BB_KEYBOARD_FLOW_AUDIT | `1473631` | `play/coinflip/page.tsx` `onKeyDown` + `aria-live`; 7 keyboard tests |
| BB_KEEPER_BOT_SETTLE | `c5276aa` | `apps/api/lib/settler.ts`; 36 api tests cover happy + 502 retry |
| BB_FRAMER_MOTION_COIN_SPIN | `08dca08` | `framer-motion ^12.38.0`; `CoinSpin.tsx` 1.2s + reduced-motion crossfade |
| BB_PLAY_LOBBY_ROUTE | `72168e5` | `apps/web/src/app/play/page.tsx` + render test |
| BB_DICE_CONTRACT_PHASE2 | `005b12a` | `BunnyBagzDice.sol` + `BunnyBagzDice.t.sol` + JS↔Sol parity |
| BB_PHASE1_VERIFICATION_PASS | (no code) | `memory/cron/bb_phase1_verification_2026-05-01.md` |
| BB_THEME_CONTRAST_AUDIT supersedes BB_A11Y_KEYBOARD_SCREEN_READER drift | `1473631` + `a017122` | aria-live + axe-baseline — closes the original A11Y drift |

## Drift confirmed (still open as of 2026-05-02 evening)

| Item | Gap | Action |
|---|---|---|
| BB_INDEXER_PHASE1_PONDER | `apps/indexer/` is `README.md` only — no `ponder.config.ts`, no schema, no `/api/history` handler | Re-open as `[BB_INDEXER_PHASE1_PONDER_REAL]` |
| BB_WAGMI_CLI_ABI_GEN | `apps/web/src/lib/abis.ts` still hand-rolled with the literal `"Phase 1 deploy will replace this"` comment | Re-open as `[BB_WAGMI_CLI_ABI_GEN_REAL]` |
| BB_PERSISTENT_KV_ADAPTER | `seedStore.ts` ships `MemorySeedKV` only; `getKV()` ignores `BUNNYBAGZ_KV_BINDING`; only string referencing the env is a comment | Re-open as `[BB_PERSISTENT_KV_ADAPTER_REAL]` |
| BB_PLAYWRIGHT_E2E_SETUP | `apps/web/package.json` has zero playwright deps; no `playwright.config.*`; no spec | Re-open as `[BB_PLAYWRIGHT_E2E_SETUP_REAL]` (Phase 2 exit gate) |
| BB_HILO_CONTRACT_PHASE2 | `packages/contracts/src/` has Bankroll/Coinflip/Dice/Randomness/Version only — no HiLo | Re-open as `[BB_HILO_CONTRACT_PHASE2_REAL]` (Phase 2) |

## Operator-gated (deferred-by-design — NOT drift)

- `BB_PHASE1_TESTNET_DEPLOY` — needs funded testnet deployer key. `packages/contracts/deployments/` correctly empty.

## Phase 1 closeout — what's left

Three autonomous-doable items remain to call Phase 1 truly closed:

1. **Indexer** — Ponder project that resolves `/api/history?address=…` (the
   `RecentOutcomesStrip` already handles 404 gracefully, so this is a quality
   improvement not a blocker for Phase 1 demo).
2. **Wagmi CLI ABI codegen** — replace hand-rolled ABI; mirrors the
   `chain-addresses` CI sync check shipped 2026-04-30.
3. **Persistent KV adapter** — Cloudflare KV / Upstash class behind
   `SeedKV`, runtime-selected on `BUNNYBAGZ_KV_BINDING`.

After those three, Phase 1 is `⚠ ~98%` with only the operator-gated testnet
deploy remaining.

## What "looks smooth" still needs (UI/polish for operator test)

The mobile 30-second flow is wired (UX_PLAN §2). The remaining polish that
matters for an "operator presses 'play' and is impressed" gate:

- **Mobile thumb-zone audit** — confirm primary CTA stays in bottom 30% of
  the viewport on common devices (iPhone SE / Pixel 7). No automated test
  for this yet.
- **Reduced-motion review** — confirm crossfade fallback is tasteful, not
  abrupt; coin viewport doesn't lose visual hierarchy when spin is disabled.
- **First-bet hint** — UX_PLAN §2 mentions a "Tap **HEADS** or **TAILS** to
  play" hint on `/play`. Not yet wired (the lobby card alone counts as the
  hint today; operator may want a literal floating hint).
- **Win confetti** — UX_PLAN §5 prescribes "confetti pulse capped at 600ms"
  on win. Not implemented; only the mascot celebrate is wired.
- **Tabular figures everywhere balances/odds appear** — UX_PLAN §6
  prescribes; not enforced via CSS audit.

These are the items that bridge "Phase 1 functional" to "Phase 1 looks
intentional under an operator demo".

## Phase 2 readiness

Blocking items for Phase 2 work to begin:
1. HiLo contract + Foundry tests + parity vectors (mirrors Dice scaffold).
2. USDM (`permit()` happy path + one-time-approval fallback).
3. Playwright e2e (Phase 2 exit criterion).

`BunnyBagzDice.sol` is shipped and tested; the front-end `/play/dice` route
is not yet started.
