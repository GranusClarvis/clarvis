# BunnyBagz Phase 2 — End-to-End Audit (2026-05-05)

> Verdict: **Phase 2 is ~85% real-complete, NOT closed.** All 9 wiring gaps
> from the 2026-05-04 truth audit (A,B,C,D,E,H,I,J) are closed. **Three
> ROADMAP exit-criteria lines remain open**: USDm bet path is not in any
> game UI, recent-bets surface is not in WalletSheet (and Dice/HiLo have no
> outcomes strip), and Playwright e2e has never been observed green in CI.
> A fourth blocker (testnet deploy of Dice + HiLo) is operator-gated on
> Phase 1 deployer funding.

Repo: `GranusClarvis/bunnybagz` · branch `feature/mvp-planning-and-rebrand`
Local workspace: `/home/agent/agents/mega-house/workspace`
Last commit on disk: `5a5e93e` (test(web,contracts): wallet-mocked e2e + HiLo fuzz commit guard)

## ROADMAP Phase 2 exit criteria (verbatim)

> all 3 games playable in ETH and USDm on testnet; recent bets in wallet
> sheet; e2e green; light + dark themes look intentional, not mechanical.

## What I verified live (2026-05-05)

Test suites, all run on-disk:

| Suite | Result |
|---|---|
| `pnpm --filter @bunnybagz/web test` | **283/283** ✓ |
| `pnpm --filter @bunnybagz/api test` | **75/75** ✓ |
| `pnpm --filter @bunnybagz/indexer test` | **37/37** ✓ |
| `pnpm --filter @bunnybagz/verify test` | **40/40** ✓ |
| `forge test --no-match-test Fuzz` | **119/119** ✓ |
| **Total non-fuzz** | **554/554** ✓ |

## Resolution of the 2026-05-04 truth-audit gaps

| Gap | Verdict | Evidence on disk |
|---|---|---|
| **A.** Dice + HiLo never deployed | ✅ Closed | `Deploy.s.sol:125,134` deploys both via CREATE3; `deployments/6343.json` includes `dice`/`hilo` keys; `addresses.generated.ts` exposes them for chain 6343. |
| **B.** Lobby still locks Dice + HiLo | ✅ Closed | `app/play/page.tsx:74` flips `status: addr[g.addressKey] ? "live" : "phase2"` — both unlock once their address resolves. |
| **C.** HiLo `playStep` has no backend | ✅ Closed | `apps/api/hilo/step.ts` (5.5KB edge handler) + `apps/web/src/app/api/hilo/step/route.ts` (Next App-Router proxy) + `step.test.ts` (10 cases) + extended `settler.ts` with `realPlayStepSettler`. |
| **D.** Verify API + page hard-code coinflip | ✅ Closed | `apps/api/verify/[betId].ts` + `apps/api/verify/session/` + `apps/web/src/app/verify/session/[sessionId]/` ship; tests cover `dice`/`hilo`/`coinflip` payloads. |
| **E.** Indexer covers only Coinflip | ✅ Closed | `apps/indexer/src/{dice,hilo}-handlers.ts` + ABIs + `recent-bets.ts` cross-game aggregator + 37 tests. |
| **F.** USDM completely missing | ⚠ **Partial** | `PermitForwarder.sol` + `apps/web/src/lib/permit.ts` ship + WalletSheet "Approved" pill — but **no `/play/*` page invokes the permit strategy**, so the bet flow remains ETH-only. The QUEUE archive entry says explicitly: "UI toggle on `/play/*` pages tracked as a follow-up." |
| **G.** Playwright e2e missing | ⚠ **Partial** | `apps/web/playwright.config.ts` + 6 specs (3 unconnected + 3 wallet-mocked connected) + `e2e:` CI job in `.github/workflows/ci.yml` ship; **CI has never been observed green** end-to-end (local box lacks `libatk` etc., never verified on `ubuntu-latest`). |
| **H.** Mobile/UI audits don't cover Phase 2 surfaces | ✅ Closed | `thumb-zone-audit.test.tsx` imports `DicePage` + `HiloPage`; `tabular-figures-audit.test.tsx` extends 11 dice+hilo entries; `contrast-audit.ts` covers `/play/dice`+`/play/hilo`. |
| **I.** UI quality below standard | ✅ Closed | `HiloCard.tsx` ships rank+suit (♠♥♦♣) + 600ms-capped flip; `DiceSlider.tsx` ships role=slider + 44px thumb + keyboard contract; `TrustFooter.tsx` mounted in `layout.tsx` exposes audit/bounty/verify. |
| **J.** `forge build` warnings | ✅ Closed | 5 `forge-lint: disable-next-line(unsafe-typecast)` annotations land in `BunnyBagzDice.sol` + `BunnyBagzHiLo.sol`; build is warning-free. |

## ROADMAP-line gaps (independent of truth-audit gaps)

The truth audit covered the wiring, but **two ROADMAP exit lines were not
on the truth-audit list** and are still open:

1. **"recent bets in wallet sheet"** — `WalletSheet.tsx` surfaces address +
   ETH balance + USDm balance + Approved pill + Fluffle placeholder + theme
   toggle. **No recent-bets section.** `RecentOutcomesStrip.tsx` exists but
   is hardcoded `&game=coinflip` and only mounted on `/play/coinflip`. The
   indexer-side `recent-bets.ts` aggregator is built but **not wired to any
   UI surface**.

2. **"e2e green"** — specs ship and CI job is wired, but there is no
   recorded green run for either the unconnected or the wallet-mocked specs.
   ROADMAP says `green`, not `wired` — the gate is a passing CI run.

3. **Operator-blocking — testnet deploy of Dice + HiLo.** `addresses.generated.ts`
   shows the deterministic addresses, but the bytecode is not on chain
   because the deployer wallet is unfunded (Phase 1 closeout blocker carried
   forward). Dice + HiLo are not actually playable on testnet today.

## Genuinely done

- All 9 wiring gaps from `bb_phase2_truth_audit_2026-05-04.md` (A,B,C,D,E,H,I,J).
- Permit strategy library + PermitForwarder contract + Approved pill (gap F partial).
- Playwright e2e scaffolding + wallet-mock harness + CI job (gap G partial).
- Forge build clean.
- 554/554 non-fuzz tests green.
- Light/dark theme parity (token diff covers it).
- Light + dark themes look intentional (not mechanical) — UX_PLAN tokens land.

## Still needed for Phase 2 closure

Six tasks added to `memory/evolution/QUEUE.md` (P1, project-lane BUNNYBAGZ):

1. `[BB_PHASE2_USDM_PERMIT_UI_PLAY_PAGES]` — wire `lib/permit.ts` into
   `/play/coinflip`, `/play/dice`, `/play/hilo`. Token toggle + per-bet
   permit + legacy fallback + ≥6 vitest cases per game.
2. `[BB_PHASE2_RECENT_BETS_WALLET_SHEET]` — new `/api/history/wallet`
   endpoint + `RecentBetsList.tsx` mounted in WalletSheet + `/wallet`.
3. `[BB_PHASE2_RECENT_OUTCOMES_DICE_HILO]` — generalize
   `RecentOutcomesStrip` over `game` prop and mount on Dice + HiLo.
4. `[BB_PHASE2_E2E_GREEN_IN_CI]` — drive one full green run on
   `ubuntu-latest`, capture run URL, pin Playwright + Chromium versions.
5. `[BB_PHASE2_TESTNET_DEPLOY_DICE_HILO_LIVE]` — operator-gated funding,
   then `deploy-testnet.sh --apply`, then a real round-trip bet on each
   game.
6. `[BB_PHASE2_TRUTH_AUDIT_FOLLOWUP_2]` — fresh end-to-end audit after
   the five above ship; archive Phase 2 only if every ROADMAP exit bullet
   holds.

## Phase 3 seeded into queue

Source: `docs/ROADMAP.md` Phase 3 + `docs/BUILD_PLAN.md` Phase 3. All
filed P2 today, will promote to P1 once `[BB_PHASE2_TRUTH_AUDIT_FOLLOWUP_2]`
archives Phase 2.

| Task | Operator-gated? | Surface |
|---|---|---|
| `[BB_PHASE3_ANIMATION_PASS]` | No | coin spin + dice slider + hi-lo flip + reduced-motion |
| `[BB_PHASE3_MASCOT_ART]` | No | idle/win/loss-streak + supporting character SVGs |
| `[BB_PHASE3_BANKROLL_CIRCUIT_BREAKER]` | No | contract + tests + symbolic proof |
| `[BB_PHASE3_PNL_MONITOR_CRON]` | Partial (provisioning) | 4th Defender monitor + Telegram alert |
| `[BB_PHASE3_GEO_ENFORCE_MODE]` | Partial (counsel review) | log → enforce flip + UI block screen |
| `[BB_PHASE3_BUG_BOUNTY_PAGE]` | Partial (Immunefi vs in-house decision) | real `/bounty` content + BUG_BOUNTY.md |
| `[BB_PHASE3_LEGAL_PAGES]` | Partial (counsel signoff) | privacy + terms + responsible-gaming |
| `[BB_PHASE3_STATUS_PAGE_ONCALL]` | No | `/status` + `/api/status` + ONCALL.md |
| `[BB_PHASE3_INTERNAL_BETA_TESTNET_7D]` | Yes (operator invites) | beta plan + daily summary cron |
| `[BB_PHASE3_TREASURY_MULTISIG_3OF5]` | Yes (signer set) | Safe + runbook + ownership transfer |
| `[BB_PHASE3_AUDIT_FIRM_ENGAGEMENT]` | Yes (firm selection) | scope doc + freeze tag + remediation tracker |
| `[BB_PHASE3_AUDIT_FIX_TRACKER_BOOT]` | No | template + cron diff job |
| `[BB_PHASE3_TESTNET_7D_INVARIANT_LOG]` | No | daily on-chain assertion sweep |
| `[BB_PHASE3_MAINNET_ALLOWLIST_SOFT_LAUNCH]` | Yes (mainnet deploy) | allowlist contract + UX gate + deploy artifact |

## Why this audit matters

The 2026-05-04 truth audit successfully drove the wiring layer to closure
(8 of 9 gaps fully closed in <24h), but two **product-level** ROADMAP
exit criteria — recent bets surface and USDm bet path — were never on the
truth-audit list and consequently never grew tasks. That is the same
"archive items pass their own gate but the user-facing product does not"
pattern `bunnybagz_realignment_2026-05-01.md` was filed to prevent. The
six new Phase 2 tasks above close that loop directly.
