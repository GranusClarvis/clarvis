# Cosmic Casino — End-to-End Delivery Plan (2026-05-15)

> **Status:** PLAN (binding for the active casino lane). Closes the QA / E2E /
> rollout gaps between the 2026-05-15 BB→SWO port (`bb_swo_monad_repositioning_2026-05-15.md`)
> and what shipped (`cosmic_casino_monad_testnet_live_2026-05-15.md`).
>
> **Audience:** the next 3–6 cron spawners working on the casino lane.
> **Rigor floor:** matches the former BB QA stack — Foundry+Halmos+Medusa,
> Playwright connected suites, QA harness, Defender monitors, indexer, keeper.

## 1. Where we stand (auditable snapshot)

### 1.1 What is verifiably live on Monad testnet 10143

| Component | Address / artifact | Evidence |
|---|---|---|
| `CasinoBankroll` | `0x33C5B6a95e71611F5dC821A74DDAD0F746fF2dFf` | `contracts/casino/deployments/10143.json`, `contracts/DEPLOYED.md` |
| `CosmicFlip` | `0x064b8bfc03b23D2b525deD9d3969090347A21983` | same |
| `GravityDice` | `0xAC023542A8168465EE4A1b3e8Ae0f58F36A6d84B` | same |
| `ConstellationClimb` | `0xd9B9b6c37ad4f3D5b07ae76dE261c5C865600d6e` | same |
| Deploy script | `contracts/casino/script/Deploy.s.sol` + `deploy-testnet.sh` | broadcast in `broadcast/Deploy.s.sol/10143/run-latest.json` |
| Smoke integration test | `contracts/casino/test/CasinoIntegration.t.sol` (6/6 PASS) | `forge test` clean |
| Address book | `lib/casino/addresses.ts` (export `getCasinoAddresses`, `casinoIsLive`) | type-check clean |
| UI cards | `app/casino/CasinoContent.tsx` testnet badge + explorer link | rendered, `tsc --noEmit` clean |
| Header nav | `components/Header.tsx` `CASINO` link (desktop+mobile) | shipped |
| Brand doc | `app/casino/page.tsx` title "Cosmic Casino" + tagline | shipped |
| Deployer balance | `0xb29e…fD7B`, ~19 MON remaining | reused from BB |
| `DEPLOYED.md` rows | Testnet table populated, Mainnet table "not yet deployed" | shipped |

### 1.2 What did NOT ship vs the BB stack (the rigor gap)

| Surface | BB has | Cosmic Casino has | Gap |
|---|---|---|---|
| Foundry tests | 14 `.t.sol` (Bankroll invariants, CircuitBreaker, CommitReplay, Halmos formal, Dice, HiLo, Allowlist, Randomness, Treasury, Version, PermitForwarder, DeployDeterministic, MedusaInvariants) | 1 (smoke `CasinoIntegration.t.sol`, 6/6 pass) | **13 missing** |
| Medusa fuzz harness | `MedusaInvariants.t.sol` + config | none | missing |
| Halmos formal | `BunnyBagzCoinflipHalmos.t.sol` | none | missing |
| `forge test` in CI | Yes (BB workflow) | **No** — `.github/workflows/copilot-setup-steps.yml` only | **acceptance gap in `[SWO_CASINO_CONTRACTS_PORT]`** |
| Defender monitors | 4 JSON monitors + 2 actions + deploy script | none | full port pending |
| Indexer (Ponder) | `apps/indexer/` with schema + ABIs | none | full port pending |
| Seed-manager keeper | `apps/api/keeper/keeper.ts` + tests + doctor | none | full port pending |
| Betting UI (Coinflip) | `apps/web/src/app/play/coinflip/page.tsx` + tests + Playwright | none (card only) | full port pending |
| Betting UI (Dice) | `apps/web/src/app/play/dice/page.tsx` + tests | none | full port pending |
| Betting UI (HiLo / Climb) | `apps/web/src/app/play/hilo/page.tsx` + tests | none | full port pending |
| Connected Playwright suites | `coinflip.connected.spec.ts` + dice + hilo (wallet-mock) | none | port pending |
| QA harness | `apps/web/scripts/qa/{run,audits,report}.mjs` | none | port pending |
| BetPanel component | `apps/web/src/components/BetPanel.tsx` | none | port pending |
| TrustStrip / WalletSheet / RecentBets / FairnessProof | shared components shipped | none | port pending |
| Vitest unit tests | dozens of `__tests__/` co-located | none for casino | gap |
| Contract verification | etherscan/blockscout verified on chain 6343 | **Not verified on Monadscan** | gap (Monadscan compatibility check needed) |
| Refund-path test | covered in `BunnyBagzCommitReplay.t.sol` + integration | not in smoke | gap |
| Drawdown-breaker tested live | armed at deploy | **never exercised** | gap |
| Region/geo gate | none (BB had `apps/web/src/app/region-not-supported/`) | none | TBD — SWO uses `AccessGate` differently |
| Responsible-gaming page | `/responsible-gaming` in BB | none in SWO | port pending |
| Terms / Privacy | BB pages exist | unknown — SWO has separate legal | reuse SWO's |
| Mainnet 143 CREATE3 dry-run | predicted addresses in `bb_phase2_*.md` | **not predicted/published** | gap |
| Operator smoke runbook | `bb_phase2_testnet_live_2026-05-05.md` §Appendix | none | this doc closes it |
| Post-launch monitoring | Defender + Telegram + dashboards | none | full port pending |
| Launch checklist | `bb_qa_closeout_burndown_2026-05-10.md` | none | this doc closes it |

### 1.3 What "fresh deploy" means in practice

The contracts work in `forge test`. They have **never been exercised by a
real wallet through the production UI**, because the production UI doesn't
have a betting surface yet. Until [§5 UI Port] lands we have no proof
that the wagmi config, ABI imports, address book, and chain detection all
agree end-to-end. The smoke is currently *Solidity-only*.

---

## 2. Risks & open questions (sorted by blast radius)

| Risk | Likelihood | Impact | Mitigation lane |
|---|---|---|---|
| **R1.** Mainnet redeploy yields a different address than testnet → live address book mismatch | Low (CREATE3 is deterministic per `(deployer, salt)`) | HIGH (lost session, wallet-side mismatch) | `[SWO_CASINO_MAINNET_ADDRESS_PREDICTION]` — publish predicted mainnet addresses in `DEPLOYED.md` before any deploy |
| **R2.** Drawdown circuit-breaker fires unexpectedly on testnet under bot load → games freeze | Medium | MED (testnet-only freeze; reset by `owner.resetCircuitBreaker()`) | `[SWO_CASINO_BREAKER_STRESS_TEST]` and add a `breaker_state` Defender monitor |
| **R3.** Seed-manager keeper offline → players' bets sit in `Pending` for 256 blocks, then they can `refundBet` (no loss, but trust-damaging) | High during early days | MED | `[SWO_CASINO_KEEPER_PORT]` + `[SWO_CASINO_KEEPER_HEALTH_MONITOR]` |
| **R4.** Wrong-chain user clicks bet → wagmi reverts but UX is opaque | High (Monad is niche; users on mainnet) | LOW (no funds at risk) | `[SWO_CASINO_UI_CHAIN_GATE]` |
| **R5.** `EXPIRY_BLOCKS = 256` constant says "≈25s on MegaETH" in NatSpec but Monad blocks are 500 ms → ~2 min → docs say "~25s" everywhere | Already shipped | LOW (docs only) | `[SWO_CASINO_NATSPEC_BLOCK_TIME_FIX]` — sweep `/casino/*` copy, NatSpec, README |
| **R6.** Allowlist not deployed on testnet but UI assumes optional → if mainnet flips `allowlistEnabled=true`, betting silently reverts for non-allowlisted users | Medium at mainnet ceremony | HIGH at mainnet launch | `[SWO_CASINO_ALLOWLIST_UI_GATE]` — UI must read `flip.allowlist()` and pre-check |
| **R7.** Bankroll seed too small (0.02 MON) → drawdown of one max bet (0.002 MON × 99 multiplier = 0.198 MON) drains the bankroll | Likely on first big GravityDice win | HIGH (game frozen until owner deposits) | `[SWO_CASINO_BANKROLL_TOP_UP_RUNBOOK]` + alert at <0.05 MON |
| **R8.** Monadscan API unstable / different schema → contract verification fails silently → users can't read source | Medium | LOW (users can read from GitHub) | `[SWO_CASINO_MONADSCAN_VERIFY]` — try, fall back to source-only listing |
| **R9.** No indexer → "Recent bets" feed in UI is empty | Inherited from BB design | LOW (cosmetic) | `[SWO_CASINO_INDEXER_PORT]` |
| **R10.** Geo blocklist gap: BB had explicit OFAC + 9-country block. SWO casino has none. If mainnet ships without one → legal exposure | Will surface at mainnet | HIGH (legal) | `[SWO_CASINO_GEO_BLOCKLIST]` — operator-gated for mainnet |
| **R11.** Operator key (0xb29e…) is 1/1 EOA on testnet **and** scheduled to own mainnet via CREATE3 → compromise of that key = total drain | Compromise: low; impact: catastrophic | CRITICAL at mainnet | `[SWO_CASINO_MULTISIG_MIGRATION]` (already operator-gated at Phase E) |
| **R12.** SWO `/casino` page is wrapped in `AccessGate` (Skrumpey-only). Testnet users without a Skrumpey can't even see the cards | Already shipped | MED (gates QA testing too) | `[SWO_CASINO_TESTNET_OPEN_ACCESS]` — `AccessGate` should pass through on testnet chain only |
| **R13.** Reusing BB deployer key reuses BB CREATE3 salts → if BB ever redeploys on a chain that collides, identical addresses might cause indexer chaos | Very low (MegaETH abandoned) | LOW | document; no action |
| **R14.** Smoke test deployment used `CASINO_INITIAL_DEPOSIT=2e16` (0.02 MON) but `MAX_BET=2e15` (0.002 MON) and Gravity Dice payout at `rollUnder=2` is `99×` — single max bet payout = 0.198 MON ≈ 10× bankroll | Live as we speak | HIGH on first big dice win | tighten on next deploy: lower `MAX_BET` to `bankroll / 200` and document in deploy script |

---

## 3. Phase plan (Phase A done; B–F structured here)

Reuses the BB Phase rubric so the rigor floor is comparable.

### Phase A — Funding & smoke (DONE)
- ✅ Deployer funded (~19 MON remaining)
- ✅ RPC verified
- ✅ Contracts deployed via CREATE3
- ✅ Games registered, bankroll seeded
- ✅ 6/6 Foundry smoke pass
- ✅ Address book + nav link + page metadata

### Phase B — Test suite full port (P0, autonomous, ~2 sessions)

**Goal:** match BB Foundry coverage so the Cosmic Casino smoke is not the
only line of defense.

Acceptance: every BB `.t.sol` has an equivalent under `contracts/casino/test/`
(renamed), all tests pass against `forge test`. `forge coverage` ≥ 90% on the
ported sources.

Subtasks:

| Tag | Description | Source | Target |
|---|---|---|---|
| `[SWO_CASINO_TEST_PORT_BANKROLL]` | Port `BunnyBagzBankroll.t.sol` + `BunnyBagzBankrollCircuitBreaker.t.sol` + `BunnyBagzBankrollInvariant.t.sol` | `mega-house/packages/contracts/test/BunnyBagzBankroll*.t.sol` | `contracts/casino/test/CasinoBankroll{Unit,Breaker,Invariant}.t.sol` |
| `[SWO_CASINO_TEST_PORT_COINFLIP]` | Port Coinflip unit + commit-replay + Halmos | `BunnyBagzCoinflip*.t.sol` | `CosmicFlip*.t.sol` |
| `[SWO_CASINO_TEST_PORT_DICE]` | Port Dice unit | `BunnyBagzDice.t.sol` | `GravityDice.t.sol` |
| `[SWO_CASINO_TEST_PORT_HILO]` | Port HiLo unit | `BunnyBagzHiLo.t.sol` | `ConstellationClimb.t.sol` |
| `[SWO_CASINO_TEST_PORT_RANDOMNESS]` | Port randomness lib unit | `BunnyBagzRandomness.t.sol` | `CommitRevealRandomness.t.sol` |
| `[SWO_CASINO_TEST_PORT_ALLOWLIST]` | Port allowlist unit | `BunnyBagzAllowlist.t.sol` | `CasinoAllowlist.t.sol` |
| `[SWO_CASINO_TEST_PORT_DEPLOY_DETERMINISTIC]` | Verify CREATE3 prediction = actual on local anvil + dry-run against Monad | `DeployDeterministic.t.sol` | `DeployDeterministic.t.sol` |
| `[SWO_CASINO_TEST_PORT_MEDUSA]` | Port Medusa invariants harness (separate `medusa.json`, not run in CI but doc'd in README) | `MedusaInvariants.t.sol` | same |
| `[SWO_CASINO_TEST_COVERAGE_BAR]` | `forge coverage` ≥ 90% on `contracts/casino/src/` ports; publish report under `docs/casino/coverage_<date>.md` | — | — |

### Phase C — CI integration (P0, autonomous, ~1 session)

Acceptance: pushing to a branch in SWO repo runs `forge test` on
`contracts/casino/`, fails the PR if any test reds, posts a coverage delta
comment. Add a parallel job for the connected Playwright suite once UI lands.

Subtasks:

| Tag | Description |
|---|---|
| `[SWO_CASINO_CI_FORGE_TEST]` | Add `.github/workflows/casino-forge.yml`: matrix Solidity 0.8.24, `forge install`, `forge build`, `forge test -vvv`, fail on red |
| `[SWO_CASINO_CI_FORGE_COVERAGE]` | `forge coverage --report lcov`, publish artifact, gate at 90% line coverage |
| `[SWO_CASINO_CI_FOUNDRY_FMT]` | `forge fmt --check` as a lint job |
| `[SWO_CASINO_CI_VITEST]` | When `lib/casino/**` or `app/casino/**` changes, run Vitest with a casino tag |
| `[SWO_CASINO_CI_E2E]` | When UI lands, Playwright connected suite runs against a `forge anvil` fork of Monad testnet (cheap, deterministic) |

### Phase D — UI port (P0, autonomous, ~3–4 sessions)

Acceptance: a Skrumpey-holding user can connect MetaMask, switch to Monad
testnet, click Cosmic Flip / Gravity Dice / Constellation Climb, place a
0.001 MON bet, and see it settle on-chain. Each game has its own URL,
shared `BetPanel` chrome, and Vitest unit tests + Playwright connected spec.

Subtasks:

| Tag | Description | Source (BB) | Target (SWO) |
|---|---|---|---|
| `[SWO_CASINO_LIB_CHAIN_CLIENT]` | Port `packages/chain` adapter — wagmi config helpers, ABI exports, address resolver | `mega-house/packages/chain/src/` | `lib/casino/{chain,abi,bets}.ts` |
| `[SWO_CASINO_LIB_VERIFY]` | Port `packages/verify` — local commit/reveal verifier for "provably fair" UI strip | `mega-house/packages/verify/src/` | `lib/casino/verify.ts` |
| `[SWO_CASINO_COMPONENT_BET_PANEL]` | Port BetPanel — stake input, side picker, "Confirm in wallet…" CTA, signing-overlay dwell ≥600ms (lesson from `[BB_QA_BET_CTA_INTERMEDIATE_STATE]`) | `apps/web/src/components/BetPanel.tsx` | `components/casino/BetPanel.tsx` |
| `[SWO_CASINO_COMPONENT_TRUST_STRIP]` | Port TrustStrip — mobile-44 hit floor (lesson from `[BB_QA_TRUST_STRIP_MOBILE_HIT_TARGET_FIX]`) | `apps/web/src/components/TrustStrip.tsx` | `components/casino/TrustStrip.tsx` |
| `[SWO_CASINO_COMPONENT_WALLET_SHEET]` | Port WalletSheet — mobile-44 hit floor + focus-trap | `apps/web/src/components/WalletSheet.tsx` | `components/casino/WalletSheet.tsx` |
| `[SWO_CASINO_COMPONENT_RECENT_BETS]` | Port RecentBets feed (gracefully empty until indexer ships) | `apps/web/src/components/RecentBets.tsx` | `components/casino/RecentBets.tsx` |
| `[SWO_CASINO_COMPONENT_FAIRNESS_PROOF]` | Port FairnessProof — commit + reveal display | `apps/web/src/components/FairnessProof.tsx` | `components/casino/FairnessProof.tsx` |
| `[SWO_CASINO_COINFLIP_UI]` | `/casino/coinflip/page.tsx` with full bet flow | `apps/web/src/app/play/coinflip/page.tsx` | `app/casino/coinflip/page.tsx` |
| `[SWO_CASINO_DICE_UI]` | `/casino/dice/page.tsx` with rollUnder slider | `apps/web/src/app/play/dice/page.tsx` | `app/casino/dice/page.tsx` |
| `[SWO_CASINO_HILO_UI]` | `/casino/constellation-climb/page.tsx` (renamed) — session open / step / cashOut | `apps/web/src/app/play/hilo/page.tsx` | `app/casino/constellation-climb/page.tsx` |
| `[SWO_CASINO_UI_CHAIN_GATE]` | When user not on chain 10143 (or 143 mainnet later), show "Switch to Monad testnet" CTA with `wallet_switchEthereumChain` call. Block all bet buttons. | new | `components/casino/ChainGate.tsx` |
| `[SWO_CASINO_TESTNET_OPEN_ACCESS]` | `AccessGate` for `/casino/*` routes: bypass Skrumpey check **when chainId === 10143** (testnet should be QA-friendly). Mainnet keeps Skrumpey-only. | `components/AccessGate.tsx` | edit |
| `[SWO_CASINO_MASCOT_SWAP]` | Replace BB rabbit assets with Star Skrumpey dealer art (reuse SWO Skrumpey pixel art; no RD spend) | new | `public/casino/skrumpey-dealer-*.png` |
| `[SWO_CASINO_STATUS_FLIP]` | Once a betting page is end-to-end, flip card status `'testnet' → 'live'` (still testnet chain, but UI is live there) | `app/casino/CasinoContent.tsx` | edit |
| `[SWO_CASINO_NATSPEC_BLOCK_TIME_FIX]` | Sweep code+docs+NatSpec for "≈25s on MegaETH" → "≈2 min on Monad (256 blocks × ~500ms)" | many | many |

### Phase E — Off-chain infra (P1, autonomous, ~2 sessions)

Acceptance: the seed-manager keeper publishes commits + settles bets within
1 block on Monad testnet; an indexer renders RecentBets; Defender alerts on
abnormal events.

Subtasks:

| Tag | Description |
|---|---|
| `[SWO_CASINO_KEEPER_PORT]` | Port `apps/api/keeper` from BB to a small daemonisable script (or Vercel cron / Defender Autotask). Reads `BetPlaced` / `SessionOpened` from RPC, signs `settleBet` / `settleSession` with the seed-manager key. Reuse the BB hot-key rotation logic. |
| `[SWO_CASINO_KEEPER_DOCTOR]` | Port `keeper/doctor.ts` health check + a `/api/casino/health` route. |
| `[SWO_CASINO_KEEPER_HEALTH_MONITOR]` | Cron-driven `monitoring/casino_keeper_health.log` plus Telegram alert if keeper offline >5 min. |
| `[SWO_CASINO_INDEXER_PORT]` | Port `apps/indexer/ponder.config.ts` to point at Monad testnet 10143 RPC + ABIs. Hosted target TBD (operator decision — Ponder Cloud, Goldsky, or self-host on Vercel cron). |
| `[SWO_CASINO_DEFENDER_MONITORS_PORT]` | Port the 4 Defender monitors: BetPlaced rate spike, owner-key actions, bankroll balance threshold, PnL monitor 24h. Re-target to Monad testnet network. |
| `[SWO_CASINO_DEFENDER_ACTION_TELEGRAM]` | Port `defender/actions/telegram-forwarder.ts` to forward alerts to the SWO ops Telegram chat (separate from BB's). |
| `[SWO_CASINO_BANKROLL_TOP_UP_RUNBOOK]` | `docs/runbooks/CASINO_BANKROLL_TOPUP.md` — when to top up, how, owner-key procedure. Alert at <0.05 MON via Defender. |
| `[SWO_CASINO_BREAKER_STRESS_TEST]` | Drive synthetic bot load (10 max-bet wins in 1h) on testnet, observe breaker fires correctly, reset it via `resetCircuitBreaker`. Capture the script under `scripts/casino/stress_breaker.sh`. |

### Phase F — QA harness, E2E, contract verification, launch checklist (P1, ~2 sessions)

Acceptance: a single command runs the full QA suite against `localhost:3000/casino` and produces a markdown report; Monadscan shows verified source; the launch checklist passes.

Subtasks:

| Tag | Description |
|---|---|
| `[SWO_CASINO_QA_HARNESS_PORT]` | Port `apps/web/scripts/qa/{run,audits,report}.mjs` and Playwright harness. Targets: 12 scenarios × 4 variants = 48 (Coinflip/Dice/Climb × {connected,mock} × {dark,light} × {mobile-375,desktop-1280}). |
| `[SWO_CASINO_QA_DEFECT_TAXONOMY]` | Adopt the 8 defect classes from `bb_qa_defect_taxonomy_2026-05-10.md` for the casino harness (`mobile-horizontal-overflow`, `touch-target-floor`, etc.). |
| `[SWO_CASINO_PLAYWRIGHT_CONNECTED]` | `e2e/casino/{coinflip,dice,climb}.connected.spec.ts` using wallet-mock against a forked-anvil Monad testnet. |
| `[SWO_CASINO_PLAYWRIGHT_FOCUS_RING]` | `e2e/casino/focus-ring.spec.ts` (lesson from BB H6/H7 defect classes). |
| `[SWO_CASINO_PLAYWRIGHT_VISUAL_BASELINE]` | Snapshot baseline at 375×812 + 1280×800 for all 3 game pages. |
| `[SWO_CASINO_VITEST_BET_PANEL]` | Component test that asserts (a) `getBoundingClientRect().height ≥ 44` for all interactive children; (b) `text-below-readable-floor` ≥ 12px; (c) CTA dwell ≥ 600ms. |
| `[SWO_CASINO_MONADSCAN_VERIFY]` | `forge verify-contract` for each of the 4 deployed contracts on `testnet.monadscan.com`. Fall back to publishing flattened source under `contracts/casino/flattened/` if API rejects. |
| `[SWO_CASINO_MAINNET_ADDRESS_PREDICTION]` | `forge script Deploy --rpc-url $MONAD_MAINNET_RPC --sender 0xb29e… --skip-simulation` to PREDICT (not deploy) the mainnet 143 addresses. Publish in `DEPLOYED.md` under "Mainnet (predicted)". |
| `[SWO_CASINO_OPERATOR_SMOKE_RUNBOOK]` | `docs/runbooks/CASINO_TESTNET_SMOKE.md` mirroring `bb_phase2_testnet_live_2026-05-05.md §Appendix` — MetaMask setup, faucet, 3-game bet round-trip, paste-tx-hash slots. |
| `[SWO_CASINO_LAUNCH_CHECKLIST]` | `docs/runbooks/CASINO_LAUNCH_CHECKLIST.md` — testnet exit gates + mainnet exit gates. See §6 below. |
| `[SWO_CASINO_POST_LAUNCH_HARDENING]` | `docs/runbooks/CASINO_POST_LAUNCH.md` — top-up cadence, breaker reset, keeper rotation, incident response, withdraw-by-owner path. |

### Phase G — Mainnet (P2, OPERATOR-GATED — no autonomous execution)

Acceptance: operator green-lights audit firm, multisig migration, geo
blocklist, initial bankroll seed. CREATE3 deploys with **same salts** ⇒
identical addresses on chain 143 vs 10143.

Subtasks (placeholders; do not execute):

| Tag | Description |
|---|---|
| `[SWO_CASINO_AUDIT_PICK]` | Operator picks Spearbit / ToB / Cyfrin / ChainSecurity. |
| `[SWO_CASINO_MULTISIG_MIGRATION]` | Transfer ownership of bankroll + games from EOA to SWO governance multisig before any mainnet seed. |
| `[SWO_CASINO_GEO_BLOCKLIST]` | OFAC + 9-country block (carry forward verbatim from BB) at the `/casino/*` route layer. |
| `[SWO_CASINO_MAINNET_DEPLOY]` | `bash script/deploy-mainnet.sh` once gates clear. |
| `[SWO_CASINO_MAINNET_SEED]` | Initial bankroll seed (operator-decided; suggested 10–50 MON sized by MON valuation). |
| `[SWO_CASINO_STATUS_FLIP_MAINNET]` | UI status `'live'` once mainnet bets settle. |

---

## 4. End-to-end test plan (replaces the BB QA closeout doc)

### 4.1 Test pyramid

1. **Unit (Foundry + Vitest)** — covered by Phase B + Vitest in Phase D/F.
2. **Integration (Foundry)** — `CasinoIntegration.t.sol` smoke + Phase B ports.
3. **Component (Vitest + jsdom)** — `BetPanel`, `TrustStrip`, `WalletSheet`, `ChainGate`, `FairnessProof`.
4. **E2E mocked (Playwright + wallet-mock)** — Phase F connected suites, no real RPC.
5. **E2E real (operator-driven)** — `CASINO_TESTNET_SMOKE.md` runbook (Phase F).
6. **Resilience / stress** — breaker stress test (Phase E), keeper-offline soak.
7. **Visual / accessibility** — QA harness (Phase F) — 48 variants × 8 defect classes.

### 4.2 Test matrix

| Surface | Foundry | Vitest | Playwright (mock) | Playwright (anvil-fork) | Operator smoke |
|---|:---:|:---:|:---:|:---:|:---:|
| Bankroll deposit/withdraw | ✅ Phase B | — | — | — | smoke |
| Bankroll allowance | ✅ Phase B | — | — | — | — |
| Bankroll drawdown breaker | ✅ Phase B | — | — | — | stress test |
| Cosmic Flip win/lose/refund | ✅ Phase B | — | ✅ Phase F | ✅ Phase F | ✅ smoke |
| Gravity Dice win/lose/refund | ✅ Phase B | — | ✅ Phase F | ✅ Phase F | ✅ smoke |
| Constellation Climb open/step/cashOut | ✅ Phase B | — | ✅ Phase F | ✅ Phase F | ✅ smoke |
| Allowlist gating | ✅ Phase B | — | — | — | — (mainnet only) |
| Commit-reveal randomness | ✅ Phase B (Halmos formal) | — | — | — | — |
| Refund-after-expiry | ✅ Phase B | — | — | — | optional |
| BetPanel UI invariants | — | ✅ Phase F | ✅ Phase F | — | — |
| Chain gate (wrong network) | — | ✅ Phase F | ✅ Phase F | — | ✅ smoke |
| Wallet sheet focus trap | — | ✅ Phase F | ✅ Phase F | — | — |
| QA harness (48 variants × 8 classes) | — | — | ✅ Phase F (deep) | — | — |

### 4.3 CI gates (PR-blocking)

| Gate | Lives at | Threshold |
|---|---|---|
| `forge build` on `contracts/casino/` | `.github/workflows/casino-forge.yml` | clean |
| `forge test` on `contracts/casino/` | same | green |
| `forge coverage` | same | ≥ 90% lines, ≥ 80% branches |
| `forge fmt --check` | same | clean |
| `pnpm vitest run --project casino` | `.github/workflows/web.yml` | green |
| `tsc --noEmit` | existing | clean |
| `pnpm playwright test --project casino-connected` | `.github/workflows/casino-e2e.yml` | green (once UI lands) |
| QA harness deep-profile | `.github/workflows/casino-qa.yml` | zero `HIGH`-severity findings |

### 4.4 Manual operator-driven smoke (the irreducible test)

Every mainnet ceremony, every breaker reset, every keeper rotation triggers
the operator smoke from `CASINO_TESTNET_SMOKE.md`:

1. Fresh MetaMask wallet (not the deployer key).
2. Faucet-drip to ≥ 0.005 MON.
3. Switch to chain 10143, navigate to `/casino`.
4. Place one bet on each game at min stake. Confirm `BetSettled` / `SessionCashedOut` on-chain.
5. Paste tx hashes into the runbook + commit.
6. Run `cast call bankroll() balance()` before+after, assert delta consistent with bet outcomes.

---

## 5. Contract verification plan (Monadscan)

Monadscan exposes an Etherscan-API-compatible endpoint at
`https://api.monadscan.com/api` (mainnet) and
`https://testnet-api.monadscan.com/api` (testnet) — already configured in
`contracts/casino/foundry.toml` `[etherscan]` section.

Steps (do for each of `CasinoBankroll`, `CosmicFlip`, `GravityDice`, `ConstellationClimb`):

```bash
cd contracts/casino
forge verify-contract \
  --chain monad_testnet \
  --etherscan-api-key "$MONAD_ETHERSCAN_KEY" \
  --watch \
  <ADDRESS> src/<Name>.sol:<Name> \
  --constructor-args $(cast abi-encode "constructor(address)" "$DEPLOYER")
```

Fallback if the API rejects (returns "Pending" indefinitely):

1. `forge flatten src/<Name>.sol > flattened/<Name>.flat.sol`.
2. Commit flattened sources.
3. Open a Monadscan issue / use their manual web-form verifier with the flat file.

Acceptance:

- ✅ All 4 contracts show "Source code verified" on `testnet.monadscan.com/address/<addr>`.
- ✅ Constructor args displayed.
- ✅ ABI auto-extracted.

---

## 6. Launch checklist (testnet exit → mainnet ceremony)

### 6.1 Testnet exit gates (must all green before mainnet)

| # | Gate | Owner | Evidence path |
|---|---|---|---|
| T1 | Foundry tests ≥ 90% coverage | Phase B | `docs/casino/coverage_<date>.md` |
| T2 | CI `forge test` green on PRs | Phase C | workflow run URL |
| T3 | All 3 game UIs live on `/casino/<game>` | Phase D | branch / PR URL |
| T4 | Chain-gate works for wrong-chain users | Phase D | Playwright spec |
| T5 | Operator smoke: 3 bets settled on chain 10143 | Phase F | `CASINO_TESTNET_SMOKE.md` filled |
| T6 | Defender monitors firing on testnet | Phase E | Telegram alert sample |
| T7 | Keeper online ≥ 24h with `keeper_health.log` clean | Phase E | log path |
| T8 | Breaker stress test: fires + resets cleanly | Phase E | `scripts/casino/stress_breaker.sh` log |
| T9 | Bankroll never < 0.05 MON for >5 min (auto top-up runbook tested) | Phase E | runbook |
| T10 | Monadscan verified for all 4 contracts | Phase F | URLs |
| T11 | Mainnet addresses **predicted** and published in `DEPLOYED.md` | Phase F | doc |
| T12 | QA harness: zero `HIGH` findings across 48 variants | Phase F | report path |
| T13 | NatSpec/UI copy block-time fix swept (≈2 min, not ≈25s) | Phase D | grep audit |
| T14 | `[SWO_CASINO_BB_CANCEL]` sweep done (BB phase 3/4/5 items strikethrough'd) | Clarvis | QUEUE.md |

### 6.2 Mainnet ceremony gates (OPERATOR ONLY — no autonomous)

| # | Gate | Notes |
|---|---|---|
| M1 | Audit firm engaged + report delivered | Spearbit / ToB / Cyfrin / ChainSecurity |
| M2 | All HIGH+ findings remediated | re-audit or sign-off |
| M3 | Multisig deployed (Safe on Monad mainnet 143) | 2/3 or 3/5 — operator's call |
| M4 | Geo blocklist live (OFAC + 9-country) | route-level + Cloudflare WAF |
| M5 | Responsible-gaming page live | port from BB |
| M6 | Terms / Privacy / KYC posture set | legal sign-off |
| M7 | Bankroll seed wallet topped to ≥10 MON | operator-funded |
| M8 | Allowlist enabled + seeded with soft-launch cohort | `CASINO_DEPLOY_ALLOWLIST=true CASINO_ALLOWLIST_ENABLED=true` |
| M9 | `forge script Deploy --broadcast --rpc-url monad_mainnet` | same salts as testnet ⇒ same addresses |
| M10 | Multisig accepts ownership; deployer key revoked | `transferOwnership` + accept |
| M11 | Defender monitors re-target mainnet network | re-config |
| M12 | Operator smoke on mainnet with min stake | 0.001 MON each game |
| M13 | Status flipped to `'live'` in UI on chain 143 | edit `CasinoContent.tsx` |
| M14 | Public announcement | Twitter / Discord |

### 6.3 Post-launch hardening (first 30 days)

| # | Action | Cadence |
|---|---|---|
| PL1 | Watch bankroll balance | every 5 min via Defender |
| PL2 | Watch breaker state | every block via Defender monitor |
| PL3 | Watch keeper liveness | every 1 min |
| PL4 | Daily PnL summary | Telegram at 00:00 UTC |
| PL5 | Rotate seed-manager key | day 7 (and quarterly thereafter) |
| PL6 | Lift allowlist if stable for 7 days | operator call |
| PL7 | Increase `MAX_BET` if bankroll grows | operator call, multisig tx |
| PL8 | Audit logs vs indexer for ≥1 sample/day | manual spot-check |

---

## 7. Acceptance criteria for "delivery-ready"

The casino lane reaches "ready for mainnet ceremony" when:

1. **All Phase B–F tags closed.** Every row in §3 either `[x]` in QUEUE.md or
   explicitly out-of-scope with a written rationale.
2. **Every testnet gate (T1–T14) green** with linked evidence.
3. **Operator has signed off on M1–M8** in writing (chat / commit message).
4. **`bb_phase2_testnet_live_*` analogue exists** for the casino —
   `cosmic_casino_testnet_exit_<date>.md` — capturing the same evidence shape
   as the BB phase-2 doc (bytes per contract, allowance, deposit, explorer
   links, broadcast tx hashes).
5. **Mainnet addresses are predicted and pinned.**

Any one of those missing = NOT ready. No "soft launch" without M3+M4+M5+M7+M8.

---

## 8. Estimate

| Phase | Sessions (~30 min Claude Code, parallel-spawnable) | Wall time | Blockers |
|---|---|---|---|
| B (test port) | 4–6 | 2 days | none — pure code |
| C (CI) | 1–2 | half day | depends on B |
| D (UI) | 6–8 | 3 days | parallel with B+C |
| E (off-chain) | 3–4 | 2 days | parallel with D |
| F (QA + verify + runbooks + checklist) | 4–5 | 2 days | depends on B,C,D,E |
| G (mainnet) | operator-only | weeks | audit + multisig |

Total autonomous: **~14–17 sessions** to reach testnet-exit. Most parallelisable.

---

## 9. References

- Migration plan: `memory/evolution/bb_swo_monad_repositioning_2026-05-15.md`
- Deploy log: `memory/evolution/cosmic_casino_monad_testnet_live_2026-05-15.md`
- BB QA rigor floor: `memory/evolution/bb_qa_defect_taxonomy_2026-05-10.md`,
  `memory/evolution/bb_qa_closeout_burndown_2026-05-10.md`
- BB phase-2 evidence shape: `memory/evolution/bb_phase2_testnet_live_2026-05-05.md`
- Tracker: `memory/evolution/SWO_TRACKER.md` §"Cosmic Casino — BB merge-in"
- SWO repo branch: `clarvis/star-world-order/t0515010014-1adb` (head: `4bde35c`)
- Monad testnet RPC: `https://testnet-rpc.monad.xyz` (chain 10143)
- Explorer base: `https://testnet.monadscan.com/address/`
- Deployer: `0xb29e6735629539cEd64F0d6f0c476Fe92539fD7B` (~19 MON remaining)
