# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items archived by `clarvis.queue.writer.archive_completed()` to QUEUE_ARCHIVE.md._
_Caps: P0 ≤ 10, P1 ≤ 15. Triage before adding. See docs/PROJECT_LANES.md for rules._
_Deep audit tracker: `docs/internal/audits/CLARVIS_DEEP_AUDIT_PLAN_2026-04-16.md` (existing P1 audit items map to phases there — do not duplicate). Quick-reference: `docs/internal/audits/AUDIT_INDEX.md`._

## P0 — Current Sprint (2026-04-15)

_Audit-phase override: while executing the deep Clarvis audit plan, do not suppress or skip justified follow-up queue items merely because P1 is over cap. Audit-derived findings may add P1/P2 tasks when they are necessary to preserve audit continuity and evidence integrity. Triage still applies, but cap pressure must not block recording valid findings._

### Critical Pipeline Fixes


### Deep Audit (anchor for canonical audit tracker)


### Execution Governance (added 2026-04-15 — prevents SWO-style drift)


### Deep Audit — Phase 9 Follow-ups (added 2026-04-17)

_Source: `docs/internal/audits/NEURO_FEATURE_DECISIONS_2026-04-17.md`. Phase 9 scored 16 neuro features via proxy-EVS/TCS (no A/B data). 2 PROMOTE, 6 KEEP, 4 REVISE, 4 SHADOW, 0 DEMOTE. Critical defect: world_models calibration loop broken._


### Bugs


## P1 — This Week

### BunnyBagz — MegaETH Casino (full state audit 2026-05-02 evening)

_Repo: `GranusClarvis/bunnybagz` (renamed from `mega-house` 2026-04-29). Active branch: `feature/mvp-planning-and-rebrand`. Local workspace: `/home/agent/agents/mega-house/workspace`._
_**Workflow:** BunnyBagz is managed and tested **directly in its own repo**. Do NOT route through the SWO PR workflow. Standard flow: pull → branch → edit → `pnpm --filter @bunnybagz/<pkg> test` (verify+api+web) + `forge test` (CI) → commit + push to working branch. PRs only when the operator explicitly asks._

_**Status doc (sole source of truth):** `memory/evolution/bb_phase1_status_2026-05-03.md` (supersedes `memory/cron/bb_phase1_status_2026-05-02.md`)._
_**Realignment background:** `memory/evolution/bunnybagz_realignment_2026-05-01.md` (root cause of the 2026-04-30 queue-degradation incident)._
_**Latest verification pass:** `memory/cron/bb_phase1_verification_2026-05-01.md` (14 items audited; 6 silently-archived drift, now re-opened below as `[BB_*_REAL]`)._

_**Phase status (2026-05-03 evening, after commits `ae1897f` `cdf105f`):**_
- _**Phase 0 — Repo & rails: ✅ DONE.**_
- _**Phase 1 — Coinflip end-to-end on testnet: ⚠ ~96%.** All software-side closeout done: contracts + edge fns + real Ponder indexer + persistent KV adapter + wagmi-CLI ABI codegen + every UI polish item. Today's session also fixed a Phase-0-era chain-id drift (`6342 → 6343`, the upstream MegaETH testnet id per `megaeth-labs/documentation` `vars.yaml`) and shipped `packages/contracts/script/deploy-testnet.sh` — a faucet-sized deploy runbook verified end-to-end against `https://carrot.megaeth.com/rpc` (every call simulates cleanly except the final `deposit{value:…}` which reverts on `OutOfFunds`, as expected with a 0-balance wallet). **Single remaining gap:** operator funds `0xb29e6735629539cEd64F0d6f0c476Fe92539fD7B` from `https://testnet.megaeth.com/` (Cloudflare Turnstile gates the API; agent cannot self-fund) and runs the deploy script._
- _**Phase 2 — Dice + HiLo + USDM: ⚠ ~30%.** `BunnyBagzDice.sol` (commit `005b12a`) and `BunnyBagzHiLo.sol` (commit `70b53c9`) shipped + tested; USDM integration not started; Playwright e2e MISSING; `/play/dice` and `/play/hi-lo` routes not started._
- _**Phase 3+ — operator-blocked.** Audit firm, multisig, counsel, mainnet._

_**Test inventory (verified live 2026-05-03 evening):** contracts **102/102**, web **157/157**, api **46/46**, indexer **21/21**, all green after the chain-id rename. `@bunnybagz/verify` baseline **22/22** unchanged._

_**Operator-blocking — DO NOT attempt autonomously:** funded testnet deployer key + first deploy, KV/Redis production binding (impl is autonomous-doable; the **binding** is operator-gated), indexer Fly.io machine + Neon Postgres (impl is autonomous-doable; the **hosting** is operator-gated), audit firm engagement, multisig signer set, X/TG/Discord handle squat, real-money mainnet seed._

#### Phase 1 closeout — drift re-opens (P1, autonomous-doable)

_Items the 2026-05-01 verification pass found silently archived as `[x] [UNVERIFIED]` but with no on-disk artifact. Mirroring the `[BB_TAILWIND_TOKENS_REAL]` pattern, each has a real acceptance contract that requires the test/file to exist before it can be archived._


#### Phase 1 closeout — operator action required (single blocker)

- [x] **[BB_PHASE2_DEFENDER_MONITOR]** [UNVERIFIED] Configs ready, provisioning operator-gated. Configured 2026-05-04: `packages/contracts/defender/` carries 3 monitor JSONs (BetPlaced rate spike, owner-key actions, bankroll <10% drawdown), one routing autotask (`actions/telegram-forwarder.ts`), an idempotent deploy script (`scripts/deploy-monitors.ts --dry-run|--apply`), and a synthetic Telegram test (`scripts/test-webhook.sh`). Runbook § 7.0 documents the operator setup checklist. Final 3 acceptance bullets (provision Defender team, run `--apply`, fire synthetic alert) require the operator's Defender org token — see `mega-house/workspace/packages/contracts/defender/README.md`. (PROJECT:BUNNYBAGZ) (2026-05-03)


#### Phase 1 closeout — UI polish for operator demo (P1, autonomous-doable)

_The 30-second flow works (UX_PLAN §2) but `bb_phase1_status_2026-05-02.md` flagged four polish items that bridge "Phase 1 functional" to "Phase 1 looks intentional under an operator demo". Each ships as one PR with concrete tests._


#### Phase 2 — re-open + new (P1 once Phase 1 closes; staged P2 today)

_Re-opens of items the 2026-05-01 audit found drifted. Filed under P1-once-Phase-1-closes since they are real product work, but sit at the Phase-2 boundary today._

- [x] [UNVERIFIED] **[BB_PLAYWRIGHT_E2E_SETUP_REAL]** ([REOPENED] from `[BB_PLAYWRIGHT_E2E_SETUP]`, drift confirmed 2026-05-01 + 2026-05-02). `apps/web/package.json` has zero playwright deps; no `playwright.config.*`; no spec. Phase 2 exit criterion per `docs/ROADMAP.md`. Install `@playwright/test`; ship `apps/web/playwright.config.ts` (Chromium + Mobile Safari emulation, 30s timeout, retries=1 in CI) and `apps/web/e2e/coinflip.spec.ts` walking: load `/`, click connect (mocked wallet via `playwright`'s `page.addInitScript` + a wagmi mock), navigate to `/play`, click Coinflip card, set stake, tap Heads, see settled outcome (mocked api/seed). Add CI job that runs `pnpm --filter @bunnybagz/web exec playwright test` on Linux headless. **Acceptance:** spec runs green locally + in CI; deps lockfile updated; new CI job in `.github/workflows/ci.yml`. (PROJECT:BUNNYBAGZ) (2026-05-03T14:16:04Z)

#### BunnyBagz — process + verification (P1, autonomous-doable)

- [x] [UNVERIFIED] **[BB_END_TO_END_UI_REVIEW]** Single-shot UI review pass over the live BB web surface — does the 30-second flow per UX_PLAN §2 actually feel right? Use the existing `clarvis_browser.py` (Playwright CDP path) to: visit `localhost:3000/`, screenshot LCP at 1.0s, navigate `/play`, screenshot, tap Coinflip card, screenshot, simulate keyboard-only (Tab → Enter), screenshot, take a screenshot under both dark and light themes, take a screenshot at 375px-wide viewport. Save under `memory/cron/bb_ui_review_<YYYY-MM-DD>/`. Then write a 10-line review verdict scoring each surface 1-5 against UX_PLAN §3 layout primitives + §6 visual system + §7 accessibility. **Acceptance:** review folder exists with ≥6 screenshots; verdict file at `memory/cron/bb_ui_review_<YYYY-MM-DD>.md` lists ≥3 concrete issues with file:line references where the fix should land; if any issue is `severity: high`, auto-append a `[BB_UI_<TAG>_FIX]` task to QUEUE.md. (PROJECT:BUNNYBAGZ) (2026-05-03T14:16:04Z)

#### BunnyBagz — Phase 2 truth audit follow-ups (2026-05-04)

_Source: `memory/evolution/bb_phase2_truth_audit_2026-05-04.md`. Phase 2 archive entries each pass their own gate but the user-facing product does not. Verdict: Phase 2 should NOT be considered closed. Items below are the concrete wiring/UI gaps. ROADMAP Phase 2 exit criterion: "all 3 games playable in ETH and USDm on testnet; recent bets in wallet sheet; e2e green; light + dark themes look intentional". Today: 1/3 games playable in ETH; 0/3 in USDm; e2e missing._



- [ ] ~~**[BB_PHASE2_HILO_STEP_API_AND_KEEPER]**~~ Phase 2 BLOCKER #3. `apps/web/src/app/play/hilo/page.tsx:285` POSTs `playStep` to `/api/hilo/step`. Endpoint does not exist (`apps/web/src/app/api/` directory absent; no edge route in `apps/api/`). The HiLo state machine will hang in `stepping` indefinitely on any live demo. Two-part fix: **(a)** add `apps/api/hilo/step.ts` (mirroring `apps/api/seed/reveal.ts` shape): accepts `{sessionId, direction}`, looks up the session's bound server seed in `seedStore`, calls a new `playStepSettler` that signs `BunnyBagzHiLo.playStep(sessionId, direction, serverReveal, nextCommit)` via `viem walletClient` and waits for `StepPlayed` / `SessionPushed` / `SessionCashedOut` log; **(b)** extend `apps/api/lib/settler.ts` with a `HILO_PLAY_STEP_ABI` + `playStepSettler: PlayStepSettler` + `pickHiloStepEvent(logs, gameAddress)` that decodes any of the three settle events and returns a discriminated union; same `setSettler` / `resetSettler` injection pattern. Page side: dispatch `bunnybagz:hilo-step` (or `bunnybagz:hilo-settle` on push/loss) custom DOM event with the decoded payload so the existing `useEffect` listener picks it up. Add a Next.js / Worker route handler under `apps/web/src/app/api/hilo/step/route.ts` (or wherever `/api/seed/claim` is served from — discover the existing pattern first via `grep -rn "/api/seed/claim" apps/web`). **Acceptance:** new `apps/api/hilo/step.test.ts` covers happy path (open session → playStep wins → step event dispatched) + reveal-mismatch + commit-already-used reverts; settler test in `apps/api/lib/settler.test.ts` (or sibling) verifies decoded `StepPlayed` / `SessionPushed` payloads; HiLo page test covers transition `open → stepping → open` (win) and `open → stepping → pushed` (tie); all api + web suites still green. (PROJECT:BUNNYBAGZ)


- [x] **[BB_PHASE2_INDEXER_DICE_HILO]** SHIPPED 2026-05-05 — `ponder.config.ts` now filters Coinflip + Dice + HiLo (BetPlaced/BetSettled/BetRefunded × 2 games + SessionOpened/StepPlayed/SessionCashedOut/SessionRefunded/SessionPushed). Schema extended with `DiceBet`, `HiLoSession`, `HiLoStep`. New handlers `dice-handlers.ts` + `hilo-handlers.ts` + stores `dice-store.ts` + `hilo-store.ts`. Cross-game aggregator `recent-bets.ts` (`recentBetsForPlayer`) merges newest-first across all 3 games. Test suite 21 → 37 (5 dice + 8 hilo + 3 recent-bets); typecheck clean; README.md updated. (PROJECT:BUNNYBAGZ)

- [ ] **[BB_PHASE2_USDM_PERMIT_FLOW]** Phase 2 ROADMAP exit verbatim: "USDm integration: `permit()` happy path + one-time-approval fallback." Repo grep currently finds zero implementation. Wallet copy at `apps/web/src/app/wallet/page.tsx:23` self-admits "Deposits, withdrawals, and USDM swap land in Phase 2." Wire it: **(a)** add USDM token contract address to `packages/chain` (testnet placeholder + real-mainnet env override), **(b)** extend each game contract's `placeBet` / `openSession` to accept an optional `(uint256 deadline, uint8 v, bytes32 r, bytes32 s)` permit tuple — or ship a thin `PermitForwarder` helper that does `IERC20Permit(token).permit(...)` + `transferFrom` + game call atomically (favour the helper to keep the game contracts unchanged for the audit), **(c)** frontend USDM toggle on each `/play/*` page that, on bet, requests a `permit()` signature via `useSignTypedData` and falls back to `approve(maxUint256)` once for legacy USDM, **(d)** `apps/web/src/components/WalletSheet` shows USDM balance + "Approved" pill, **(e)** wallet `/wallet` page replaces the "land in Phase 2" copy with the live deposit/withdraw flow. **Acceptance:** Foundry tests for the permit forwarder cover both happy path + invalid signature; vitest specs for permit signing on each `/play/*` page (≥2 cases per page); integration test that one-time-approval fallback only triggers when `permit()` is unavailable; web suite ≥220 tests; copy on `/wallet` no longer says "land in Phase 2"; ROADMAP can mark Phase 2 USDM checkbox closed. (PROJECT:BUNNYBAGZ)




- [ ] **[BB_PHASE2_TABULAR_CONTRAST_AUDIT_DICE_HILO]** Same gap as `[BB_PHASE2_THUMB_ZONE_DICE_HILO]` but for the other two existing audits. Confirm `apps/web/src/__tests__/tabular-figures-audit.test.tsx` and `apps/web/src/__tests__/contrast-audit.test.ts` only cover Coinflip + Lobby + Home; extend both to render `/play/dice` + `/play/hilo` and assert (a) every `data-testid` matching `*-stake-input`, `*-multiplier`, `*-current-card`, `*-step-count` carries `font-variant-numeric: tabular-nums`, (b) every text token (foreground × background pair) on the new pages clears WCAG-AA contrast under both themes. Fix any failures by token swap (do not lower the contrast bar). **Acceptance:** both audit suites grow by ≥4 cases each (2 pages × 2 themes for contrast; 2 pages for tabular); all pass; `axe-baseline.json` artifact upload still green. (PROJECT:BUNNYBAGZ)

- [ ] **[BB_PHASE2_FOOTER_TRUST_SURFACE]** UX_PLAN §8 verbatim: *"Audit & bounty links in the footer of every page."* Grep across `apps/web/src/app/{layout.tsx,page.tsx}` finds zero "audit"/"bounty" references. Add a shared `<TrustFooter />` component (`apps/web/src/components/TrustFooter.tsx`) rendering: "Audit pending — public launch gated on it" link to `/audit` (Phase 0–3 placeholder), "Bug bounty" link to `/bounty` (placeholder), "Verify any bet" link to `/verify`. Mount in `app/layout.tsx` so it appears on every route. Stub `app/audit/page.tsx` + `app/bounty/page.tsx` with the placeholder copy from UX_PLAN §8 ("Audit pending — public launch gated on it"). **Acceptance:** new vitest spec covers `<TrustFooter />` is rendered on Home, Lobby, Coinflip, Dice, HiLo, Wallet, Verify; placeholder pages render expected copy; footer links pass keyboard focus contract (visible focus ring per §7); web suite ≥225 tests after this + USDM + slider + card. (PROJECT:BUNNYBAGZ)

- [ ] **[BB_PHASE2_FORGE_LINT_TYPECAST_ANNOTATIONS]** Cosmetic but visible: `forge build` emits `unsafe-typecast` warnings on `BunnyBagzDice.sol:270` (`return uint8(raw + 1);` in `previewRoll`) and `BunnyBagzHiLo.sol:399` + `:421` (similar pattern). The casts are mathematically safe (`raw < ROLL_MOD` ⇒ < 100, `raw < CARD_MOD` ⇒ < 13, both fit `uint8`). Add the suppression annotation `// forge-lint: disable-next-line(unsafe-typecast)` immediately above each cast, with a one-line comment explaining the bound (e.g. `// raw < ROLL_MOD == 100, fits uint8`). Do NOT relax the `uint8` cast itself — keep the cast, just silence the lint. **Acceptance:** `forge build --skip test --skip script` produces zero warnings; full forge suite still 120/120; no behavioural change. (PROJECT:BUNNYBAGZ)

- [ ] **[BB_PHASE2_PLAYWRIGHT_E2E_REOPEN]** Reopen of `[BB_PLAYWRIGHT_E2E_SETUP_REAL]` (line 70 of QUEUE.md, still `[x] [UNVERIFIED]` with no on-disk artifact — `apps/web/package.json` has zero playwright deps; no `playwright.config.*`; no spec). ROADMAP Phase 2 exit verbatim: *"e2e green"*. With the dice + hilo surfaces now real, the e2e setup must cover all 3 games end-to-end, not just coinflip. Install `@playwright/test`; ship `apps/web/playwright.config.ts` (Chromium + Mobile Safari emulation, 30s timeout, retries=1 in CI); ship `apps/web/e2e/{coinflip,dice,hilo}.spec.ts` each walking: load `/`, mocked-wallet connect, navigate to `/play`, click the game card, set stake (or rollUnder for dice), tap primary CTA, see settled outcome (mocked api/seed). Add CI job that runs `pnpm --filter @bunnybagz/web exec playwright test` on Linux headless. **Acceptance:** all 3 specs run green locally + in CI; deps lockfile updated; new CI job in `.github/workflows/ci.yml`; old `[BB_PLAYWRIGHT_E2E_SETUP_REAL]` line edited to `[x] [DONE via BB_PHASE2_PLAYWRIGHT_E2E_REOPEN]`. (PROJECT:BUNNYBAGZ)

### Claude Design & Routines Integration (cross-project, added 2026-04-20)

_Source: `docs/CLAUDE_DESIGN_ROUTINES_STRATEGY.md`. Cross-project operating model for Claude Design + Claude Code Routines._


### Star Sanctuary — Companion-First Core Loop (PROJECT:SWO, reset 2026-04-26 evening)

> **Center of gravity: the Companion (selected Skrumpey).** A tamagotchi-style care + interaction loop is the new core loop. Quests, minigames, and economy stay as supporting structure; new feature work files under `[SWO_V2_COMPANION_*]` first. Direction note: `memory/evolution/swo_sanctuary_companion_first_2026-04-26.md`.
>
> **V3 is DEFERRED** (unchanged from morning brief). Stop touching `game/v3/`, `public/sanctuary-v3/`, `scripts/v3/`, `docs/SANCTUARY_V3.md`. The `?v=3` route stays for archival access only. **No new PRs tagged `[SWO_V3_*]`. No further RD credit spend on V3** (~5 generation passes burned without parity vs V2). Full inventory: SWO repo `docs/SANCTUARY_V3_DEFERRED.md`.
>
> **V1 is archival.** `SanctuaryContent.tsx` (V1 React panel) stays mounted as the no-flag fallback only. No new V1 features.

_**Active surface — V2:** page `app/sanctuary/SanctuaryV2.tsx` + `SanctuaryContent.tsx` (V1 fallback only); Phaser mount `components/sanctuary/PhaserGame.tsx`; game code under `game/scenes/`, `game/sprites/`, `game/systems/`, `game/config/`; assets in `public/sanctuary/`; routing `?v=2` (or no param + `NEXT_PUBLIC_SANCTUARY_V2=true`)._

_**Local testing (verified 2026-04-25 against branch `clarvis/star-world-order/t0425200011-0a6c`):** `npm run dev` (Next.js) + `npm run colyseus:dev`; visit `localhost:3000/sanctuary?v=2`. Pre-PR: `npm run type-check && npm run lint && npm run build`._

_**Primary V2 goals (2026-04-26 evening):** **(a) reduce AI-slop** — palette quantize / dither shader, fix sprite aliasing, downsize NPCs, standardize painted-room palettes, no regeneration; **(b) build out the Companion core loop** — stats schema → mood-from-stats → companion screen → need alerts → chat-knows-stats. Both ship in parallel. Track A items below ship before Track B items when both are ready._

_**Lane discipline:** all new feature work, polish, and visual fixes target V2. Tag commits/branches `[SWO_V2_*]` (or `[SWO_SHARED_*]` for engine-agnostic React/overlay/EventBus work that V2 mounts). `[SWO_V3_*]` is frozen — do not file new PRs under that prefix._

_**Hard out-of-scope (operator brief 2026-04-26 evening)** unless operator re-opens: replacing painted room backgrounds with new pixel art; replacing the hub map; touching V3; generating new RD assets; **new minigame scenes; new world zones; new quest content beyond what shipped in PR #245**; voice chat; mobile-app shell; push notifications; multiplayer companion features; multiplayer infra beyond what's already shipped._

#### V2 — Companion-First Core Loop (Track A — priority, 2026-04-26 evening)

_Tamagotchi-style care + interaction loop on top of the existing companion schema. Acceptance criteria are concrete so each item produces one merge-able PR. Direction + rationale in `memory/evolution/swo_sanctuary_companion_first_2026-04-26.md`._








#### V2 — De-Slop Polish (Track B — operator-set 2026-04-26 morning, still active)

_Six visual/structural polish items. Track B ships in parallel with Track A — these go in slots when no Companion P0 is ready. Items 1–3 are de-slop visual fixes; 4 standardises existing painted assets; 5 closes half-wired features; 6 is a UX gate. **No RD credits.**_


#### V2 polish — secondary (P2, do after the six priorities)

- ~~[SWO_V2_COMPANION_BG_MATTE]~~ → VERIFIED NO-OP 2026-04-26 (Claude Code session): ran `node scripts/matte_companion_sprites.mjs` (dry-run) against all 60 PNGs under `public/sanctuary/companions/`. Result: `0 file(s) would be modified, 60 already transparent, 0 no-match`. Sample alpha analysis (aether/idle.png, parallel/idle.png, prime/happy.png) confirms ~73% fully transparent + ~20% opaque + ~7% partial-alpha edges — clean sprite alpha as expected. The header note "10×6 companion mood PNGs ✓ (need BG cleanup)" predates the asset re-export; no further action needed.
- ~~[SWO_V2_DEPRECATION_GATE]~~ → RETIRED 2026-04-26: V3 is now the deprecated lane (deferred), not V2. The "V2 stops getting fixes when V3 hits parity" gate is moot. V2 is the active surface indefinitely.

#### Sanctuary — Post-V2 / strategic (P2)


#### Retired / Deferred Items

**Quest-centric items — DEMOTED 2026-04-26 evening (operator brief: companion-first).** Quest authoring has shipped (PR #245). New quest features, new quest content, and quest-centric polish are no longer the center of gravity. Quests stay in-world as supporting structure; they do not gate companion progression. New quest items should be filed P2 at most, and should be evaluated against "does this serve the companion core loop?" before adding.

- ~~[SWO_SHARED_QUEST_DIALOG_CONTENT]~~ → DONE (PR #245). No follow-up beyond bug-fixes.
- New quest authoring / new quest types / quest UI redesign → **NOT IN QUEUE** as of 2026-04-26 evening. File only as P2 with explicit operator approval.
- New minigame scenes (beyond the 7 shipped) → **NOT IN QUEUE** unless one becomes the obvious complement to a companion-care play action.

**V1 — ARCHIVAL 2026-04-26 evening (operator brief).** `SanctuaryContent.tsx` (V1 React panel) stays mounted as the no-flag fallback only. No new V1 features. Anything still useful in V1 ports into V2 surfaces, not V1. Formalization PR: `[SWO_V1_ARCHIVE_FORMALIZE]` (Track A, P1).

**V3 — DEFERRED 2026-04-26 (operator brief).** All `[SWO_V3_*]` items below are frozen. The `?v=3` route stays as archival/reference only; no new PRs target V3 paths. Reasoning, full inventory, and any future un-deferral conditions live in SWO repo `docs/SANCTUARY_V3_DEFERRED.md`. Workspace docs `swo_sanctuary_v2_v3_replan_2026-04-25.md` and `swo_sanctuary_v3_alignment_execution_2026-04-25.md` carry a SUPERSEDED banner pointing here.

- ~~[SWO_V3_PIPELINE_HARDENING]~~ → DEFERRED. No further RD spend on V3, so pipeline hardening is not actionable. If V3 is ever un-deferred, restore from git history.
- ~~[SWO_V3_HUD_ICONS]~~ → DEFERRED. (Was blocked on RD_API_KEY anyway.) HUD-icon work for V2 must use non-RD assets.
- ~~[SWO_V3_FONT_SWAP]~~ → DEFERRED on V3. PR #253 (Pixelify Sans swap) already merged on dev — covers the V3 surface. Any V2 font work files as `[SWO_V2_*]`.
- ~~[SWO_V3_OVERWORLD_MAP_DETAIL]~~ → DEFERRED. PR #252 already merged on dev; no further V3 map authoring.
- ~~[SWO_V3_ROOM_INTERIOR_MAPS]~~ → DEFERRED. V2 painted rooms remain canonical (out-of-scope to replace).
- ~~[SWO_V3_SHOP_CHROME]~~ → DEFERRED. Shop UI work files under `[SWO_SHARED_SHOP_DIALOG]` against V2.
- ~~[SWO_V3_VFX_SPRITES]~~ → DEFERRED. No new RD generation.
- ~~[SWO_V3_COSMETIC_HATS_V1]~~ → DEFERRED. No new RD generation.
- ~~[SWO_V3_UI_RESTYLE]~~ → DEFERRED.
- ~~[SWO_V3_PARTICLES_AMBIENT]~~ → DEFERRED. Any ambient FX work files under V2.
- ~~[SWO_V3_MOBILE_CANVAS]~~ → DEFERRED. Mobile work, if revived, files under `[SWO_V2_MOBILE_CANVAS]`.
- ~~[SWO_V3_FEATURE_PARITY_AUDIT]~~ → DEFERRED (moot — V3 is not the production target).

**Earlier retirements (V2/V3 split or shipped, kept for trace):**

- ~~[SWO_P0_CHAT_LOCAL_ECHO]~~ → DONE (commit `7a5c40e fix: show local chat echo immediately and dedup server roundtrip`)
- ~~[SWO_P0_ROOM_GAMEPLAY]~~ → DONE for V2 (commit `55f7cea`); V3 has its own `RoomSceneV3` (commit `c2efa0c`)
- ~~[SWO_V2_SHOP_BACKEND]~~ → DONE (commit `5aa2965 cosmetic shop backend + inventory + equip API`)
- ~~[SWO_V2_SHOP_UI]~~ → REPLACED by `[SWO_SHARED_SHOP_DIALOG]` (overlay is shared between V2 and V3)
- ~~[SWO_V2_ROOM_CUSTOMIZATION]~~ → deferred to post-V3-Phase-8 SHARED equivalent
- ~~[SWO_V2_MOBILE_CONTROLS]~~ → split into `[SWO_SHARED_MOBILE_OVERLAYS]` + `[SWO_V3_MOBILE_CANVAS]`
- ~~[SWO_V2_ONBOARDING]~~ → REPLACED by `[SWO_SHARED_ONBOARDING]`
- ~~[SWO_V2_SOUND_DESIGN]~~ → REPLACED by `[SWO_SHARED_SOUND_DESIGN]`
- ~~[SWO_V2_QUEST_DIALOG_CONTENT]~~ → REPLACED by `[SWO_SHARED_QUEST_DIALOG_CONTENT]`
- ~~[SWO_V2_COSMETIC_ITEM_DESIGN]~~ → REPLACED by `[SWO_SHARED_COSMETIC_ITEM_DESIGN]`
- ~~[SWO_RD_PIPELINE_INFRA]~~ → SUPERSEDED. V3 ships its own pipeline at `scripts/v3/` (FM palette anchor, custom user style ID); a parallel V2 cosmic-palette pipeline is no longer needed. Hardening tracked at `[SWO_V3_PIPELINE_HARDENING]`.
- ~~[SWO_RD_BATCH_1_HUD]~~ → REPLACED by `[SWO_V3_HUD_ICONS]` (FM palette, V3 pipeline)
- ~~[SWO_RD_BATCH_2_CURRENCY]~~ → REPLACED by `[SWO_V3_SHOP_CHROME]`
- ~~[SWO_RD_BATCH_3_VFX]~~ → REPLACED by `[SWO_SHARED_VFX_TRIGGER_API]` + `[SWO_V3_VFX_SPRITES]`
- ~~[SWO_RD_BATCH_4_HATS]~~ → REPLACED by `[SWO_V3_COSMETIC_HATS_V1]`
- ~~[SWO_RD_BATCH_5_VIGNETTES]~~ → DROPPED (V2 polish item; V3 empty states tracked separately if operator wants them)
- ~~[SWO_SANCTUARY_EXPEDITIONS]~~ → RENAMED `[SWO_SHARED_EXPEDITIONS]`
- ~~[SWO_SANCTUARY_MEMORY_CONSOLIDATION]~~ → RENAMED `[SWO_SHARED_CHAT_MEMORY_CONSOLIDATION]`
- ~~[SWO_SANCTUARY_RESPONSIVE]~~ → absorbed by `[SWO_SHARED_MOBILE_OVERLAYS]`
- ~~[SWO_SANCTUARY_CHAT_HISTORY]~~ → DONE (commit `1d44697 server-side chat history pagination + companion memory`)
- ~~[SWO_SANCTUARY_TYPING_SIM]~~ → absorbed by `[SWO_V2_COMPANION_CHAT_OVERLAY]`
- ~~[SWO_SANCTUARY_SOUND_DESIGN]~~ → absorbed by `[SWO_SHARED_SOUND_DESIGN]`
- ~~[SWO_SANCTUARY_COSMETICS_SHOP]~~ → backend DONE (`5aa2965`); UI is `[SWO_SHARED_SHOP_DIALOG]`
- ~~[SWO_V2_WORLD_TILESET_ART]~~ → V2 RETIRED 2026-04-23 (operator painted PNG); V3 uses Forgotten Memories tileset
- ~~[SWO_V2_COMPANION_SPRITE_ART]~~ → V2 mood PNGs exist; replaced by `[SWO_V2_COMPANION_BG_MATTE]`
- ~~[SWO_V2_NPC_QUEST_CONTENT]~~ → NPCs defined in `npcDefinitions.ts`; dialog content moved to `[SWO_SHARED_QUEST_DIALOG_CONTENT]`
- ~~[SWO_V2_ROOM_SCENE]~~ → RETIRED 2026-04-23. Split: basic room gameplay is now `[SWO_P0_ROOM_GAMEPLAY]` (P0 blocker); personalization is `[SWO_V2_ROOM_CUSTOMIZATION]` (Phase 7).





### Deep Audit — Phase 9 Follow-ups (P1, added 2026-04-17)


### Phase 8 Follow-ups (P1, added 2026-04-16)


### Deep Audit — Verification Program (added 2026-04-20)

_3-phase verification pass over the completed 16-phase deep audit + 100+ queue items. Confirms work quality, identifies regressions, flags fragile areas. Each phase covers ~6 audit areas. Source: operator-requested audit-of-the-audit._


### Project-Agent Orchestration Quality (added 2026-04-21)

_Source: deep analysis of why Clarvis self-work > project-agent work. Core issue: project-agent prompts lacked 8+ context layers that self-work enjoys. FIXED in this session: worker template, time budget, episodic recall, failure avoidance, lite brain query, episode writeback, procedures.md auto-refresh. Follow-up items below._


### Clarvis Maintenance — Keep Alive

#### BunnyBagz realignment follow-ups (2026-05-01)

_Filed after the BunnyBagz Phase-1 false-DONE incident. Detail in `memory/evolution/bunnybagz_realignment_2026-05-01.md`. Both items prevent the same drift pattern from recurring on any project lane (not just BB)._



#### Cross-project continuity + queue-persistence (2026-05-02 evening)

_Source: 2026-05-02 evening end-to-end audit (`memory/cron/bb_phase1_status_2026-05-02.md`). Even after `[QUEUE_LANE_MINIMUM_GUARD]` + `[QUEUE_UNVERIFIED_ARCHIVE_GUARD]` + `[QUEUE_VERIFICATION_RECORD_PRODUCER]` shipped, BunnyBagz still went silent in the queue: the BB lane is empty of actionable items, `CLARVIS_PROJECT_LANE` is single-valued (`SWO`), and `CLARVIS_QUEUE_UNVERIFIED_GUARD` defaults to `log` not `block`. The infra is built but not configured. These tasks close that gap._

- [x] **[CONFIG_MULTI_LANE_ACTIVATION]** Wire BUNNYBAGZ as a co-active project lane alongside SWO. Edit `scripts/cron/cron_env.sh` to set `CLARVIS_ACTIVE_PROJECT_LANES="SWO,BUNNYBAGZ"` (read by `clarvis/queue/runnable.py` for lane-health monitoring). Edit the same file to flip `CLARVIS_QUEUE_UNVERIFIED_GUARD="block"` (writer.py reads this; default `log` is opt-in observability, `block` is the actual prevention). Both env vars only take effect for cron + spawn; interactive use unaffected. **Acceptance:** `grep CLARVIS_ACTIVE_PROJECT_LANES scripts/cron/cron_env.sh` returns the new line; next cron_morning report shows `🛤 LANE HEALTH` for both SWO and BUNNYBAGZ; planted-test (mark a fake `[BB_TEST_UNVERIFIED]` item `[x] [UNVERIFIED]` with no sidecar verification record + run `archive_completed`) is HELD not archived. (PROJECT:CLARVIS) (2026-05-03 14:16 UTC)
- [x] [UNVERIFIED] **[PROJECT_VERIFICATION_CADENCE_GENERIC]** `[BB_PHASE1_VERIFICATION_PASS_RECURRING]` (filed under BB above) bakes in a per-project weekly verification. Generalize: `scripts/audit/project_verification_pass.py <lane>` — reads QUEUE_ARCHIVE.md for `[x] [<LANE>_*]` items in the last N days, asserts cited commit/file/test claims hold, writes `memory/cron/<lane_lower>_verification_<YYYY-MM-DD>.md`, auto-reopens drift as `[<LANE>_<TAG>_REAL]`. Cron entry runs per active lane (read `CLARVIS_ACTIVE_PROJECT_LANES`). **Acceptance:** running `project_verification_pass.py SWO` produces a SWO doc; running `project_verification_pass.py BUNNYBAGZ` produces a BB doc; cron entry installed via `clarvis cron`; first weekly run produces both docs. Replaces `[BB_PHASE1_VERIFICATION_PASS_RECURRING]` once shipped (mark BB item DONE then). (PROJECT:CLARVIS) (2026-05-03T14:16:04Z)

#### Capability building — UI quality (2026-05-02 evening)

_Source: operator concern that Clarvis cannot reliably create or review beautiful UI / page quality. The 2026-05-02 BB review confirmed that token-level audits (contrast, mascot SVG presence) ship but visual review is operator-eyeballed only. These tasks build the missing capability._

- [x] [UNVERIFIED] **[UI_QUALITY_PLAYWRIGHT_VISUAL_REGRESSION_HARNESS]** Today Clarvis can run vitest on UI components but cannot assert "the page looks intentional" — it relies on token-level proxies (contrast ratios, font feature settings). Build a generic harness: `scripts/ui_review/playwright_visual.py <repo> <route> <viewport>` that (a) launches `clarvis_browser.py` against a local dev server, (b) screenshots the named route at 3 viewports (mobile/tablet/desktop), (c) saves under `data/ui_review/<repo>/<route>/<viewport>.png`, (d) computes a perceptual diff vs the prior snapshot using `pixelmatch`-style algorithm (or `imagehash` from PyPI — install if needed), (e) flags >5% pixel-change or >10% phash distance as `regressed`. Wire into a per-project cron job. **Acceptance:** baseline snapshots exist for `/`, `/play`, `/play/coinflip` × 3 viewports for BB; second run shows zero regressions; planted-change (CSS color tweak) triggers `regressed` flag. (PROJECT:CLARVIS) (2026-05-03T14:16:04Z)
- [x] [UNVERIFIED] **[PROJECT_AGENT_UI_LITE_BRAIN_SEED]** The mega-house lite-brain (project-agent.py path) does not currently include UX_PLAN.md or BRAND.md as seeded knowledge. Result: when a BB-targeted spawn asks "is this design choice on-brand?", the agent has no grounding doc. For each active project agent (BB, SWO), seed the lite brain with the project's UX_PLAN.md + BRAND.md + ROADMAP.md as searchable memories on creation. Update `project_agent.py seed` to detect these docs and ingest them under `project-procedures` (operator-set design constraints) and `project-context` (current phase). **Acceptance:** `python3 scripts/project_agent.py info bunnybagz` shows ≥3 seeded UX/brand entries; spawned agent's lite-brain `search("primary CTA placement rule")` returns the UX_PLAN §3 thumb-zone rule. (PROJECT:CLARVIS) (2026-05-03T14:16:04Z)



### Deep Audit — Phase 0 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Recorded under the audit-cap override (§P0 banner). P1 is currently 19/15 in base terms but within the 25-ceiling for audit sources. These are justified Phase 0 follow-ups; closing them is a precondition for a valid Phase 0 PASS ruling and for downstream phases. See `docs/internal/audits/decisions/2026-04-16_phase0_instrumentation.md`._


### Deep Audit — Phase 2 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/SPINE_MODULE_SCORECARD_2026-04-16.md` + `docs/internal/audits/decisions/2026-04-16_phase2_spine_quality.md`. Phase 2 ruled 1 PASS, 13 REVISE, 0 DEMOTE/ARCHIVE on 14 spine modules — most of the REVISE work is small `__init__.py` surface trims and cheap coverage lifts. Only 1 P1 (the new `clarvis/audit/` module needs tests — substrate is live but untested)._


### Deep Audit — Phase 3 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/PROMPT_ASSEMBLY_SCORECARD_2026-04-16.md` + `docs/internal/audits/decisions/2026-04-16_phase3_prompt_assembly.md`. Phase 3 ruled 5×PASS across task types on 334 scored episodes; aggregate gate PASS. Open follow-ups address proxy limits (MISLEADING detection, trace-backed rescore) and one hand-label task. No assembly code paths were changed by this phase._


### Deep Audit — Phase 4 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/BRAIN_USEFULNESS_2026-04-16.md` + `docs/internal/audits/decisions/2026-04-16_phase4_brain_usefulness.md`. Phase 4 ruled INSUFFICIENT_DATA × 10 collections on the attribution gate — blocked by two Phase-0 capture gaps (listed below, the P0 item being the most severe). One independent REVISE flagged on routing. `scripts/audit/brain_attribution.py` + `data/audit/brain_attribution.jsonl` + `data/audit/brain_collection_scorecard.json` shipped. All items use `source="audit_phase_4"`._


### Deep Audit — Phase 6 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/decisions/2026-04-16_phase6_execution_routing_queue.md`. Phase 6 ruled REVISE overall: router PASS (98.9% accuracy, PROMOTE candidate), autofill PASS (2.4% stale), caps REVISE (21/30 days), spawn PASS, slot share FAIL (12.5% vs 50%). All items use `source="audit_phase_6"`._


### Deep Audit — Meta-Audit Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/decisions/2026-04-16_meta_audit_phases_0_4.md`. A sharpness-check on Phases 0–4 found the program well-executed but framed too narrowly toward removal. Corrections: add code-review axis to Phase 2, wire operator-in-the-loop EVS signal, content-quality spot check for Phase 4. Plan §0 principle 7 + PROMOTE gate already landed in the plan doc. All items use `source="audit_meta"`._


---

## P2 — When Idle

### BunnyBagz — Phase 2 prep + tooling hygiene (P2, added 2026-04-30)

_Filed under P2 because they ship **after** the 11 P1 BunnyBagz closeout items above. Phase 2 contracts (`Dice` + `HiLo`) gate on Phase 1 testnet deploy + indexer being live, so they sit here even though they're real product work._


### Claude Design & Routines — Medium-term (P2, added 2026-04-20)

_Source: `docs/CLAUDE_DESIGN_ROUTINES_STRATEGY.md` §6 Phase 2-3._


### Demoted from P1 (2026-04-16, cap triage)

_Demoted to P2 to bring P1 within 25-ceiling. All are review/sweep/benchmark tasks not blocking audit gates or project delivery._


### Phase 6 Follow-ups (P2, added 2026-04-16)


### Deep Audit — Meta-Audit Follow-ups (P2, added 2026-04-16 via AUDIT_CAP_OVERRIDE)


### Graph Integration (P2, added 2026-04-18)


### Phase 4.5 Follow-ups (P2, added 2026-04-16)


### Phase 8 Follow-ups (P2, added 2026-04-16)


### Deep Audit — Phase 9 Follow-ups (P2, added 2026-04-17)

- [~] [BLOCKED:2026-05-01] **[PHASE9_REEVAL_WITH_AB]** After `[PHASE9_AB_TOGGLE_WIRING]` completes and 14-day A/B windows are collected for the 4 SHADOW features, re-run Phase 9 EVS scoring with causal data instead of proxies. Update `data/audit/neuro_feature_scorecard.jsonl` and `NEURO_FEATURE_DECISIONS_2026-04-17.md`. Any SHADOW feature showing positive causal EVS/TCS ≥ 0.2 → upgrade to REVISE. Any showing zero or negative → proceed to DEMOTE (with operator signoff for consciousness-labelled). Source: Phase 9 Proxy Limitation §0. (2026-04-19: A/B window opened 2026-04-17, closes 2026-05-01 — only 2/14 days elapsed. No causal data available yet. Re-check on or after 2026-05-01.)

### Phase 10 Follow-ups (P2, added 2026-04-17)

_Source: `docs/internal/audits/decisions/2026-04-17_phase10_reliability_security.md`. Phase 10 ruled REVISE — restore drill FAIL blocks PASS. Items below were in the decision doc and AUDIT_INDEX but never added to QUEUE.md._


### Phase 5 Follow-ups (P2, added 2026-04-19 — recovered from decision doc)

_Source: `docs/internal/audits/decisions/2026-04-16_phase5_wiki_usefulness.md`. Phase 5 ruled REVISE. These items were mandated in the decision doc but never added to QUEUE.md. The 30-day re-evaluation window from 2026-04-16 is active._


### Phase 12 Follow-ups (P2, added 2026-04-19 — recovered from decision doc)

_Source: `docs/internal/audits/DUAL_LAYER_HANDOFF_2026-04-17.md`. Phase 12 ruled REVISE (digest actionability 56.5% vs 60% target). Only 1 of 4 follow-ups was in QUEUE.md._


### Test Suite Health (P2, added 2026-04-19)

_~~72/2921 tests failing (2.5% failure rate)~~ → 0/3031 failing (0.0%) as of 2026-04-20. Fixed: (1) `quality.py` AST walk consolidated 4→1 pass + 200-file cap to eliminate timeout; (2) `test_pi_anomaly_guard` missing `benchmark_phi` monkeypatch added; (3) phi tests still flaky under concurrent ChromaDB access — `_safe_compute_phi()` wrapper added to gracefully skip on transient ChromaDB errors instead of hard-failing. 2026-04-20: 1 phi test was failing again (ChromaDB "Error finding id") — fixed with skip-on-transient-error._



### Deep Audit — Phases 12–15 Anchors (P2, added 2026-04-16 per meta-meta audit)

_Activate when Sprint 6 artifacts merge. These are placeholder anchors — full queue items should be written when dependency phases land._


### Phase 15 Follow-ups (P2, added 2026-04-17)

_Source: `docs/internal/audits/decisions/2026-04-17_phase15_reaudit_protocol.md`. Phase 15 PASS: all 3 gates met. Trial run found 3 stale locks (actionable regression)._


### Phase 14 Follow-ups (P2, added 2026-04-17)

_Source: `docs/internal/audits/COST_VALUE_2026-04-17.md`. Phase 14 ruled REVISE: cost tracking structurally broken, system-adjusted cost/PR fails gate, but trend improving and cost-reduction targets identified._


### Phase 13 Follow-ups (P2, added 2026-04-17)

_Source: `docs/internal/audits/PROPOSAL_QUALITY_2026-04-17.md`. Phase 13 ruled REVISE: proposal quality analytically strong but tracking broken (sidecar 0/394 useful), hallucination rate at boundary (10%), self-work bias structural._

- [~] [BLOCKED:SIDECAR_OUTCOME_CAPTURE] **[PHASE13_RESCORE_AFTER_SIDECAR]** After sidecar carries outcome-quality metadata and 14 days of data accumulates, re-run Phase 13 survival and outcome measurements with real data instead of proxies. Update `data/audit/proposal_quality.jsonl` and scorecard. Acceptance: re-scored gates use sidecar data, not proxy estimates. Source: Phase 13 proxy limitation. (2026-04-20 corrected: Phase 6 source propagation landed 2026-04-18 — 106/434 sidecar entries now have `source`. However, 0/434 have `status` or `outcome` quality metadata. The sidecar tracks operational state (`state: succeeded/failed`) but not outcome quality (PR merged, value delivered). Real blocker: outcome-quality capture must be wired into sidecar before rescore is possible.)

### Phase 12 Follow-ups (P2, added 2026-04-17)

_Source: `docs/internal/audits/DUAL_LAYER_HANDOFF_2026-04-17.md`. Phase 12 found digest actionability at 56.5% (REVISE), spawn quality 85% (PASS). Digest archive missing, inconsistent writers, morning garble._


### Deep Audit Follow-ups (from Phase 1 — `docs/internal/audits/SCRIPT_WIRING_INVENTORY_2026-04-16.md`)


### Deep Audit — Phase 2.5 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/decisions/2026-04-16_phase2_5_code_design_review.md`. Phase 2.5 reviewed 3 spine modules (brain, orch, context) for design quality. All 3 ruled REVISE. Top finding: no prompt-generation telemetry in `clarvis.context`. All items use `source="audit_phase_2_5"`._


### Deep Audit Follow-ups (from Phase 2 — `docs/internal/audits/SPINE_MODULE_SCORECARD_2026-04-16.md`)

_All are surface trims or cheap coverage lifts. Bridge wrappers (18) and underlying submodule files are NOT being touched — only `__init__.py` re-exports. All new items use `source="audit_phase_2"` and benefit from the audit-cap override. Re-run `scripts/audit/spine_scorecard.py` after each PR to verify the `dead_exports` count drops._


### Deep Audit Follow-ups (from Phase 3 — `docs/internal/audits/PROMPT_ASSEMBLY_SCORECARD_2026-04-16.md`)

_Source: `source="audit_phase_3"`. P1 items are co-located in the Phase 3 Follow-ups section above; this is the P2 continuation._


### Deep Audit Follow-ups (from Phase 4 — `docs/internal/audits/BRAIN_USEFULNESS_2026-04-16.md`)

_Source: `source="audit_phase_4"`. P0+P1 items are co-located with their parent blocks above; these are the P2 continuation._


### Phi Monitoring / Validation (demoted to observability metric by Phase 11 synthesis — regression watch only, not a KPI or optimization target; overlaps Phase 9 REVISE ruling on phi_metric)


### Deep Cognition (pre-audit backlog; overlaps Phase 2/4.5/9 findings)


### Cron / Non-Python Maintenance (pre-audit backlog; several overlap Phase 1 wiring inventory + Phase 10 reliability findings)


### Calibration / Brier Score (RECOVERED — all-time Brier=0.094, 7-day=0.085 as of 2026-04-20; target 0.1 PASS)


### CLR Autonomy Dimension (recovered from 0.025 → 0.603 as of 2026-04-20; remaining drag: daily cost > $10 ceiling)

### Claude Spawn Observability (pre-audit backlog; related to Phase 0 instrumentation + Phase 10 reliability)


### Star Sanctuary — Later Phases (PROJECT:SWO)

_Consolidated into P1 §Star Sanctuary V2 queue (reorganized 2026-04-22). All remaining items now in V2 phased plan above. SANCTUARY_STAR_CURRENCY_DECISION moved to Post-V2 section._


### Sanctuary Asset Batches — RETIRED 2026-04-25, V3 mapping DEFERRED 2026-04-26

_Original V2 cosmic-palette batches were retired and re-mapped to V3-lane equivalents on 2026-04-25. As of 2026-04-26 V3 itself is **DEFERRED** (operator brief — no further RD spend, ?v=3 archival only), so the V3 mappings below are also frozen. Both rows of redirection are kept as breadcrumb only; **do not start any of these items**._

- ~~[SWO_RD_BATCH_2_CURRENCY]~~ → ~~[SWO_V3_SHOP_CHROME]~~ — DEFERRED
- ~~[SWO_RD_BATCH_3_VFX]~~ → ~~[SWO_V3_VFX_SPRITES]~~ — DEFERRED. (`[SWO_SHARED_VFX_TRIGGER_API]` overlay contract is still actionable as a SHARED item.)
- ~~[SWO_RD_BATCH_4_HATS]~~ → ~~[SWO_V3_COSMETIC_HATS_V1]~~ — DEFERRED
- ~~[SWO_RD_BATCH_5_VIGNETTES]~~ → DROPPED


### Adaptive RAG Pipeline

### Episode Success Rate Recovery & Benchmark Accuracy (2026-04-09 evolution)

### Task Quality Score (RECOVERED — 0.83 as of 2026-04-20, target 0.70 PASS)

---

## NEW ITEMS (2026-04-15 evolution scan)


### 2026-04-16 evolution scan


### 2026-04-20 evolution scan


### 2026-04-25 evolution scan

_Note: queue still saturated (21 pending, P1 at cap). Adding 3 high-signal items only. Phi item is a de-emphasis execution slice — removing Phi's contamination of the evolution prompt itself, in line with `[PHI_DEEMPHASIS_AUDIT]` and `[PHI_AUTO_INJECTION_REMOVAL]` (the prompt that requested this very task hardcodes "WEAKEST METRIC: Phi", so each scan keeps adding Phi tasks regardless of de-emphasis rulings)._

- ~~[SWO_OPERATOR_PLAYTEST_BRIEF]~~ → DONE (PR #250 merged 2026-04-26 per `SWO_TRACKER.md`).

### 2026-04-24 evolution scan

_Note: queue is saturated (29 pending, P1 at cap). Adding minimal, high-signal items only. All three map to documented gaps, not speculative optimization. Phi item here is a de-emphasis execution task — it REDUCES Phi's system footprint rather than optimizing for a higher score, in alignment with `[PHI_DEEMPHASIS_AUDIT]` above._

- [~] [UNVERIFIED] **[PHI_AUTO_INJECTION_REMOVAL]** First concrete execution slice of `[PHI_DEEMPHASIS_AUDIT]`. Remove Phi-triggered auto-queue-injection and prompt-injection pathways so Phi becomes a passive regression signal only. Touch: `scripts/phi_anomaly_guard.py` (or spine equivalent) — stop writing P1 tasks when Phi drops; `cron_pi_refresh.sh` / evolution prompt builder — stop injecting "weakest metric: Phi" lines into Claude prompts; autonomous heartbeat bias — remove Phi score from attention/task-selection boost. Keep: daily Phi measurement + dashboard display + alert only on ≥0.10 regression sustained ≥3 days. Acceptance: grep shows zero auto-P1-from-Phi writers; evolution prompt no longer mentions Phi as mandatory target; Phi still recorded in `data/performance_history.jsonl`. This is the Phi-targeting task required by the evolution scan, framed to reduce (not amplify) Phi overfocus. (PROJECT:CLARVIS)
- ~~[SWO_V2_COMPANION_BG_MATTE]~~ (2026-04-24 entry) → VERIFIED NO-OP 2026-04-26 (Claude Code session). See first occurrence under §V2 — Testbed for full verification details.
- [~] [UNVERIFIED] **[DIGEST_ARCHIVE_IMPLEMENTATION]** Phase 12 ruled REVISE on digest actionability (56.5% vs 60% gate) with "Digest archive missing" as one root cause. Implement rolling archive: each write of `memory/cron/digest.md` snapshots prior content to `memory/cron/digest_archive/YYYY-MM-DD_HHMM.md` before overwrite. Retention: 30 days. Update `tools/digest_writer.py` + add `cron_cleanup.sh` pruning for archive dir. Enables digest trend analysis (what subconscious work was done last week?) and recovery from garbled writes. Acceptance: new digest write produces archive entry; older-than-30d entries auto-pruned; Phase 12 re-scoring can use archive as corpus. (PROJECT:CLARVIS)

### 2026-04-26 weekly review


### 2026-04-28 evolution scan

_Note: queue at 11 pending (under cap, but the recent saturation pattern argues for triage-first additions). Phi item continues operator-set de-emphasis (retires a stale ACTIVE GOAL that still names Phi≥0.65 as a target, contradicting `[PHI_DEEMPHASIS_AUDIT]`). Genuine weakest capability is `code_generation: 0.69` (not Phi); adding a concrete capability lift. Non-Python item is a bash digest lint that complements `[DIGEST_GARBLE_FIX]` with a regression guard._




### 2026-04-27 evolution scan

_Note: queue still saturated (20 pending, P1 at cap). Adding 4 items only — none speculative. Phi item continues the operator-set de-emphasis direction (passive observability signal only). Non-Python item is a bash/crontab health probe._


### 2026-04-30 evolution scan

_Note: queue at 22 pending. Two items target the documented execution-shape warnings (no-task rate 46%, sidecar/QUEUE checkbox drift on 8 succeeded tasks). One targets the operator-stated weakest metric (Action Accuracy=0.875, target 0.9). One non-Python bash triage item complements the existing gateway probe. Skipping speculative additions to honour cap pressure._

- [~] [UNVERIFIED] **[ACTION_ACCURACY_PRECHECK_GUARD]** Targets the weakest metric (Action Accuracy=0.875, target 0.9). Add a pre-execution sanity guard in `clarvis/cognition/preflight` (or `scripts/heartbeat_preflight.py`) that, before spawning Claude Code on a queue item, validates the named primitives in the task body actually exist: file paths via `Path.exists()`, module symbols via `importlib`-based introspection, CLI commands via `shutil.which`. On any miss, the heartbeat skips the task with a `precheck_fail` reason logged to the sidecar so the queue writer can re-evaluate (without burning a Claude Code spawn). Acceptance: new `precheck.py` module + tests covering hit/miss for each primitive type; sidecar entries gain a `precheck_fail` state; one-week measurement of episode `action_accuracy` shows ≥+0.015 lift attributable to the guard (compare to prior 14-day baseline). (PROJECT:CLARVIS)

### 2026-04-30 evolution scan (autonomous, second pass)

_Note: queue marked empty by compressed scan, but the actionable signal is the failure-type histogram (`action: 54, timeout: 2, memory: 1`) — 95% of real failures collapse into a single bucket called "action", which is too coarse to act on. Two of the four items below sharpen that bucket to lift Action Accuracy=0.875 toward target 0.9. Two are non-Python: a bash crontab-vs-managed-schedule drift audit and a markdown root-cause report on the 46% no-task heartbeat rate. None duplicate `[ACTION_ACCURACY_PRECHECK_GUARD]` (which guards spawn-time primitive existence) — these address post-mortem classification and prompt-template refinement instead._


### 2026-05-01 evolution scan (autonomous)

_Note: queue empty per compressed scan; weakest metric is Episode Success Rate=0.868 (just above 0.85 gate, low headroom). Adding 4 high-signal items. One targets Episode Success Rate via calibration capture. One is non-Python (bash regression guard). None duplicate the still-pending `[ACTION_ACCURACY_PRECHECK_GUARD]`, `[DIGEST_ARCHIVE_IMPLEMENTATION]`, or `[PHI_AUTO_INJECTION_REMOVAL]` items above._


### 2026-05-01 evolution scan (autonomous, second pass)

_Note: queue is at 4 pending after first-pass additions. Weakest metric is Episode Success Rate=0.868 (target ≥0.85, ~0.018 headroom). Adding 4 items: 2 target Episode Success Rate via different mechanisms (denominator correction + transient-retry), 1 non-Python bash attribution log, 1 non-Python markdown roadmap-vs-truth audit. None duplicate the 2 pending items above; both Episode Success Rate items work together (denominator first, retry second) but each ships independently._

### 2026-05-02 evolution scan (autonomous)

_Note: compressed scan reports 0 pending and `queue runnable: 0/0 eligible` — the queue is functionally empty for the heartbeat selector even though many `[~] [UNVERIFIED]`/`[BLOCKED]` items remain on disk. That eligibility=0 signal is itself the most important finding; one of the items below is a diagnostic for it. Weakest reported metric is Episode Success Rate=0.860 (gate ≥0.85, 0.010 headroom — even lower headroom than yesterday's 0.018). Failure patterns include 401 auth errors and test-suite timeouts in recent episodes. Adding 4 items: 1 targets Episode Success Rate via auth-failure transient classification, 1 non-Python bash diagnoses the eligibility=0 selector gap, 1 non-Python markdown audits the new failure-type histogram against actual sidecar ground truth, 1 lifts the second-weakest capability (`code_generation`=0.88) via prompt-template tightening. None duplicate `[ACTION_ACCURACY_PRECHECK_GUARD]`, `[DIGEST_ARCHIVE_IMPLEMENTATION]`, or `[PHI_AUTO_INJECTION_REMOVAL]`._



### 2026-05-02 evolution scan (autonomous, second pass)

_Note: queue is empty per compressed scan; today's first-pass items mostly archived (CODE_GEN_PROMPT_TIGHTENING, FAILURE_HISTOGRAM_TRUTH_AUDIT, QUEUE_ELIGIBILITY_ZERO_PROBE all DONE). Weakest metric remains Episode Success Rate=0.860 (gate ≥0.85, 0.010 headroom). Critical signal: this morning's `FAILURE_HISTOGRAM_TRUTH_AUDIT` (`docs/internal/audits/FAILURE_HISTOGRAM_AUDIT_2026-05-02.md`) found 75% of failures collapse into two specific postflight bugs — `classifier_misclassified` (50%, agent reports success but postflight tags partial) and `lint_structure_fail` (25%, code_validation >100-line lint downgrades shipped work). Audit projected ESR lift ~0.07–0.10 from fixing both. The two ESR items below execute that recommendation directly. Two non-Python items complete verification + alerting. None duplicate `[ACTION_ACCURACY_PRECHECK_GUARD]` (spawn-time primitive guard) or `[ESR_AUTH_TRANSIENT_RECLASSIFY]` (transient auth-error retag, already shipped as [UNVERIFIED] this afternoon)._

- [ ] **[ESR_CLASSIFIER_MISCLASSIFIED_FIX]** Targets weakest metric Episode Success Rate=0.860 (gate ≥0.85). Per `docs/internal/audits/FAILURE_HISTOGRAM_AUDIT_2026-05-02.md` §recommendation, 50% of plain-`action` failures are `classifier_misclassified`: the spawned Claude Code agent reports success in its self-report but the postflight downgrades the episode to `partial` because of a brittle outcome classifier. Fix the classifier in `clarvis/cognition/metacognition.py` (locate via `grep -n "classifier_misclassified\|partial" clarvis/cognition/metacognition.py`): when (a) agent self-report contains explicit success markers AND (b) exit_code==0 AND (c) no test/lint failure in postflight, do NOT downgrade to `partial`. Add a new test in `tests/test_metacognition.py` covering the success-self-report-but-partial-tag case. Acceptance: rerun classification on prior 100 `data/episodes.json` entries shifts ≥10 from `partial`→`success`; 7-day post-merge ESR ≥0.89 (≥+0.03 lift). (PROJECT:CLARVIS)
- [ ] **[ESR_DENOMINATOR_FORMULA_AUDIT]** Non-Python markdown audit. Targets weakest metric Episode Success Rate=0.860 by verifying the metric itself is computed correctly before optimizing it. The displayed 0.860 may differ from canonical depending on whether `precheck_fail`, `no_task`, and `skipped` outcomes are in the denominator. Read `clarvis/cognition/metacognition.py` and `scripts/performance_benchmark.py` to find every site that computes ESR; enumerate each formula's denominator (raw count vs filtered). Recompute ESR from `data/episodes.json` using each variant. Write `docs/internal/audits/ESR_DENOMINATOR_AUDIT_2026-05-02.md` with: (a) every formula site + line numbers, (b) recomputed ESR per variant on the last 100 / 500 / all episodes, (c) recommendation on which is canonical and what to converge on. Acceptance: file exists, contains ≥3 formula sites, ≥1 concrete recommendation. (PROJECT:CLARVIS)
- [x] [UNVERIFIED] **[QUEUE_ELIGIBILITY_PROBE_PAGING_WIRE]** Non-Python bash. `[QUEUE_ELIGIBILITY_ZERO_PROBE]` shipped `scripts/audit/queue_eligibility_probe.sh` this morning but the watchdog paging hookup needs verification. Check `scripts/cron/cron_watchdog.sh` (or spine equivalent) — if it does not already invoke the probe, wire it in: on each watchdog run, call the probe; if the probe shows `eligible=0 && pending>0` for ≥30 min (track via `monitoring/queue_eligibility_drift.log` last-success timestamp), fire a Telegram alert via `scripts/infra/budget_alert.py`'s alert helper or the existing `cron_watchdog.sh` alert hook. Acceptance: `grep queue_eligibility_probe scripts/cron/cron_watchdog.sh` returns ≥1 line; manual smoke test (touch a marker file simulating sustained eligibility=0) produces one Telegram alert; resolution clears the marker so alerts don't repeat. (PROJECT:CLARVIS) (2026-05-03T14:16:04Z)


### 2026-05-03 evolution scan (autonomous)

_Note: queue at 15 pending (P1 saturated). Evolution prompt cites Precision@3=0.683 (target 0.7) but `data/retrieval_quality/dashboard.md` shows P@3=0.817 — that source mismatch is the first thing to nail down before optimizing the metric. Adding 3 high-signal items, all targeting P@3 from different angles (source audit → fixture expansion → per-collection floor lift). 2 of 3 are non-Python. None duplicate existing items: `[ESR_DENOMINATOR_FORMULA_AUDIT]` audits ESR formulas (different metric); no pending item touches retrieval precision._

- [ ] **[P3_DASHBOARD_SOURCE_AUDIT]** Non-Python markdown. Targets weakest metric Precision@3=0.683 by first verifying which source is canonical. The evolution prompt reports `Precision@3=0.683` while `data/retrieval_quality/dashboard.md` (last generated 2026-03-17 — ~7 weeks stale) reports 0.817, and `clarvis/cli_bench.py` / `scripts/brain_mem/retrieval_benchmark.py` each emit their own value. Enumerate every site that computes or reports P@3: file path, line number, fixture set used, denominator (per-query vs per-collection-mean), freshness of the underlying corpus. Run each computation now and record the live value. Write `docs/internal/audits/P3_SOURCE_AUDIT_2026-05-03.md` listing: (a) all sites + line numbers, (b) live values for each, (c) which the evolution prompt actually pulls from, (d) recommendation on canonical source + cadence to refresh it. Acceptance: file exists, ≥3 sites enumerated, ≥1 concrete recommendation, identifies the source feeding the evolution prompt's 0.683 figure. (PROJECT:CLARVIS)
- [x] [UNVERIFIED] **[P3_GOLDEN_QA_FIXTURE_EXPANSION]** Non-Python (JSON fixture + markdown). Targets weakest metric Precision@3=0.683 by widening the measurement base. Per `data/retrieval_quality/dashboard.md`, three collections have ≤3 queries each in the golden set: `preferences`=2, `context`=1, `meta`=2 — too few for a stable per-collection P@k signal, and the lowest-precision collection (`preferences`=0.500) is the one with the fewest queries. Locate the golden QA fixture (likely `data/retrieval_quality/golden_qa.json` or under `data/golden_qa/`). Author ≥5 additional realistic queries per under-sampled collection (preferences/context/meta), grounded in actual stored memories — for each, the expected `top_k` IDs must be verifiable against current ChromaDB content. Re-run the retrieval benchmark and record the new P@3. Acceptance: fixture file expanded by ≥15 queries (≥5 each for the 3 thin collections); `python3 scripts/brain_mem/retrieval_benchmark.py` runs green; new dashboard write under `data/retrieval_quality/dashboard.md` with `last_updated` ≤24h old; per-collection query counts ≥5 for every collection. (PROJECT:CLARVIS) (2026-05-03T14:16:04Z)
- [x] [UNVERIFIED] **[P3_PREFERENCES_COLLECTION_FLOOR_LIFT]** Targets weakest metric Precision@3=0.683 by attacking the lowest per-collection contributor. `data/retrieval_quality/dashboard.md` shows `clarvis-preferences` at P@k=0.500 (worst of all 8 collections) and `clarvis-identity` at 0.667 — both pull the global P@3 down. Diagnose: run `python3 -m clarvis brain search "<query>"` for each failing fixture query and inspect what gets returned vs expected. Likely root causes (test before fixing): (a) preference memories are short/keyword-poor so embeddings match weakly, (b) duplicate/near-duplicate preference records crowd top-3, (c) cross-collection bleed from `clarvis-memories` catch-all. Fix path: dedup preference collection via `python3 -m clarvis brain optimize-full --collection clarvis-preferences`; for any remaining miss, rewrite the preference record body to include retrieval-relevant terms (preserve original meaning); if cross-collection bleed dominates, raise the per-collection score floor in the routing weights. Acceptance: re-run benchmark shows `clarvis-preferences` P@k ≥0.75 (lift ≥+0.25) and global P@3 ≥0.72 (above 0.7 target); zero preference records lost (count before == count after, modulo dedup); diagnostic notes captured at `docs/internal/audits/P3_PREFERENCES_LIFT_2026-05-03.md`. (PROJECT:CLARVIS) (2026-05-03T14:16:04Z)

### 2026-05-04 evolution scan (autonomous)

_Note: queue at 7 pending — under cap, but recent saturation patterns argue for high-signal additions only. Weakest metric per evolution prompt is `Precision@3=0.683` (target 0.7). The 2026-05-03 scan already filed `[P3_DASHBOARD_SOURCE_AUDIT]` (pending) to identify the canonical source; complementing it with a freshness/refresh angle so the audit's canonical pick can stay live. Two non-Python items below (markdown audit + capability review). One Python item targets the second-weakest capability (`code_generation=0.85`) via failure-mode histogram, mirroring the successful `FAILURE_HISTOGRAM_TRUTH_AUDIT` pattern that produced concrete ESR fix candidates last week. None duplicate the 7 pending items: P3 refresh is the operations layer beneath the source audit; dashboard freshness is system-wide not P@3-specific; consciousness review is governance, not Phi-targeting; code-gen histogram covers a different capability than the existing classifier-misclassified ESR fix._

- [ ] **[CODE_GEN_FAILURE_MODE_HISTOGRAM]** Targets second-weakest capability (`code_generation=0.85`, vs the operator-de-emphasised `consciousness_metrics=0.79`). Mirrors the `FAILURE_HISTOGRAM_TRUTH_AUDIT` pattern that already produced two concrete ESR fixes in May. Add `scripts/audit/code_gen_failure_histogram.py`: load `data/episodes.json` (or sidecar archive), filter to last 30 days where task type involves code-gen (`code_generation`, `implementation_sprint`, lane-tagged BB/SWO with file edits in postflight), classify each failure into one of: `lint_fail`, `type_check_fail`, `test_fail`, `compile_fail`, `wrong_file_edited`, `incomplete_implementation`, `other`. Emit `data/audit/code_gen_failures_2026-05-04.json` and a markdown summary at `docs/internal/audits/CODE_GEN_FAILURE_HISTOGRAM_2026-05-04.md`. **Acceptance:** ≥50 code-gen episodes classified; top-3 failure modes named with ≥2 example episode IDs each; ≥1 concrete fix recommendation per top-3 mode (similar to how the ESR audit produced `[ESR_CLASSIFIER_MISCLASSIFIED_FIX]`). (PROJECT:CLARVIS)
- [ ] **[CONSCIOUSNESS_METRICS_CAPABILITY_REVIEW]** Non-Python markdown governance review. The capability scorecard still lists `consciousness_metrics: 0.79` as the lowest capability, but operator-set Phi de-emphasis (`[PHI_DEEMPHASIS_AUDIT]`, `[PHI_AUTO_INJECTION_REMOVAL]`) treats Phi as a passive observability signal only. The capability score still drives evolution-prompt weakest-capability targeting, contradicting that ruling. Audit `clarvis/cognition/self_model.py` (capability domains) and any callers that treat `consciousness_metrics` as an optimization target. Write `docs/internal/audits/CONSCIOUSNESS_CAPABILITY_REVIEW_2026-05-04.md` covering: (a) every site computing or reading `consciousness_metrics`, (b) what each site does with the value (display, alert, prompt-injection, queue-injection), (c) which usages survive Phi de-emphasis vs which should be removed, (d) one concrete follow-up task to retire the surviving contradictions. **Acceptance:** file exists, ≥3 sites enumerated, ≥1 retire-and-replace recommendation, no auto-mutation. (PROJECT:CLARVIS)

### 2026-05-03 weekly review

_Note: the week delivered real BunnyBagz progress and queue-hygiene repairs, but the weak point is now drift between reality and representation. Adding only three items: goal-stack hygiene, roadmap freshness, and daily-log continuity. All are small leverage multipliers, not new abstraction theater._

- [ ] [UNVERIFIED] **[GOAL_STACK_WEEKLY_HYGIENE]** `brain.get_goals()` currently returns a noisy stack of overlapping historical goals: legacy Session Continuity / Feedback Loop items, SWO-heavy delivery goals, and several Phi-forward bridge goals that no longer match roadmap policy. Build a weekly hygiene pass (`scripts/goals/weekly_hygiene.py` or spine equivalent) that: (a) groups near-duplicate goal memories by semantic title, (b) emits a markdown review under `memory/evolution/goals/weekly/<YYYY-WW>.md`, (c) flags stale goals with `progress=0` + no accesses in 14d, (d) proposes 3-7 canonical active goals for manual promotion. Acceptance: first report written for current week; report explicitly calls out SWO-vs-BunnyBagz priority skew and Phi de-emphasis; no brain mutations occur automatically without explicit follow-up action. (PROJECT:CLARVIS)
- [ ] [UNVERIFIED] **[ROADMAP_WEEKLY_STATE_REFRESH]** `ROADMAP.md` drifted for a week until the 2026-05-03 weekly review manually refreshed it. Automate a truthfulness pass that updates `_Updated:` and prepends a new `Weekly State Note` from the latest weekly review. Source inputs: newest `memory/evolution/weekly/YYYY-WW.md`, current queue state, and latest benchmark summary. Acceptance: script writes a candidate patch or exact block replacement for ROADMAP current-state note; includes guardrail to preserve historical notes; smoke test updates a temp copy with this week's note. (PROJECT:CLARVIS)
- [ ] [UNVERIFIED] **[MEMORY_DAILY_GAP_BACKFILL_AUDIT]** The rolling 7-day review for 2026-W18 found missing daily files for `2026-04-27`, `2026-04-28`, and `2026-04-29`, which weakens continuity and distorts weekly synthesis. Add an audit / backfill pass that scans the last 14 days for missing `memory/YYYY-MM-DD.md` files, creates stub files with `MISSING DAY — backfill required` headers, and writes `memory/evolution/daily_gap_audit_<YYYY-MM-DD>.md` summarizing gaps. Acceptance: missing dates in the last 14 days are surfaced explicitly; stub files are created only for absent dates; weekly review can distinguish real logs from backfills. (PROJECT:CLARVIS)

---

## Partial Items (tracked, not actively worked)

### External Challenges


---

## Research Sessions
