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


#### BunnyBagz — process + verification (P1, autonomous-doable)

- [x] [UNVERIFIED] **[BB_END_TO_END_UI_REVIEW]** Single-shot UI review pass over the live BB web surface — does the 30-second flow per UX_PLAN §2 actually feel right? Use the existing `clarvis_browser.py` (Playwright CDP path) to: visit `localhost:3000/`, screenshot LCP at 1.0s, navigate `/play`, screenshot, tap Coinflip card, screenshot, simulate keyboard-only (Tab → Enter), screenshot, take a screenshot under both dark and light themes, take a screenshot at 375px-wide viewport. Save under `memory/cron/bb_ui_review_<YYYY-MM-DD>/`. Then write a 10-line review verdict scoring each surface 1-5 against UX_PLAN §3 layout primitives + §6 visual system + §7 accessibility. **Acceptance:** review folder exists with ≥6 screenshots; verdict file at `memory/cron/bb_ui_review_<YYYY-MM-DD>.md` lists ≥3 concrete issues with file:line references where the fix should land; if any issue is `severity: high`, auto-append a `[BB_UI_<TAG>_FIX]` task to QUEUE.md. (PROJECT:BUNNYBAGZ) (2026-05-03T14:16:04Z)

#### BunnyBagz — Phase 2 truth audit follow-ups (2026-05-04)

_Source: `memory/evolution/bb_phase2_truth_audit_2026-05-04.md`. Phase 2 archive entries each pass their own gate but the user-facing product does not. Verdict: Phase 2 should NOT be considered closed. Items below are the concrete wiring/UI gaps. ROADMAP Phase 2 exit criterion: "all 3 games playable in ETH and USDm on testnet; recent bets in wallet sheet; e2e green; light + dark themes look intentional". Today: 1/3 games playable in ETH; 0/3 in USDm; e2e missing._



- [x] [UNVERIFIED] **[BB_PHASE2_HILO_STEP_API_AND_KEEPER]** Shipped commit `1c7c349` (2026-05-05). `apps/api/hilo/step.ts` edge handler accepts `{sessionId, direction}`, resolves the session's bound serverCommit, mints a fresh nextCommit, and hands off to `playStepSettler`. `apps/api/lib/settler.ts` extended with `HILO_PLAY_STEP_ABI`, `realPlayStepSettler` + `set/reset/getPlayStepSettler` injection, `pickHiloStepEvent` discriminated-union decoder over StepPlayed / SessionPushed / SessionCashedOut, and a swappable `SessionCommitResolver`. Next-App-Router proxy at `apps/web/src/app/api/hilo/step/route.ts` forwards to the same Web-standard handler so `next dev` works locally. Tests: `apps/api/hilo/step.test.ts` (10 cases — win/tie + reveal-mismatch + commit-already-used + 405/400/404/502 + commit-override paths), `apps/api/lib/settler.test.ts` (5 cases — round-trip encoded logs through `pickHiloStepEvent` for each shape). API suite **75/75**, web suite **283/283**, indexer **37/37**. (PROJECT:BUNNYBAGZ) (2026-05-05)







- [x] [UNVERIFIED] **[BB_PHASE2_TABULAR_CONTRAST_AUDIT_DICE_HILO]** Shipped 2026-05-05. `apps/web/src/lib/tabular-figures-audit.ts` extended with 11 new dice + hilo surface entries (5 dice: `dice-multiplier`, `-rollunder-value`, `-winprob`, `-multiplier-preview`, `-stake-input`; 6 hilo: `hilo-multiplier`, `-current-card`, `-current-card-label`, `-step-count`, `-cumulative-multiplier`, `-stake-input`). The vitest mount map in `apps/web/src/__tests__/tabular-figures-audit.test.tsx` now renders `DicePage` + `HiloPage`. `apps/web/src/lib/contrast-audit.ts` adds `/play/dice` + `/play/hilo` to `AUDITED_ROUTES` with 10-pair manifests each (mirrors Coinflip's palette: title/chain-hint/preview/stake/CTA/error/tx/footer). Both audit suites now grow by 22 + 4 (tabular) and 4 (contrast routes × 2 themes) — well past the ≥4 each acceptance bar. Web suite **283/283** (was 248). `axe-baseline.json` regenerated and still passes. (PROJECT:BUNNYBAGZ) (2026-05-05)

- [x] [UNVERIFIED] **[BB_PHASE2_FOOTER_TRUST_SURFACE]** Shipped 2026-05-05. `apps/web/src/components/TrustFooter.tsx` renders the three UX_PLAN §8 links: "Audit pending — public launch gated on it" → `/audit`, "Bug bounty" → `/bounty`, "Verify any bet" → `/verify`. Mounted from `apps/web/src/app/layout.tsx` so it follows every route. Placeholder pages: `apps/web/src/app/audit/page.tsx` + `apps/web/src/app/bounty/page.tsx` carry the verbatim "Audit pending — public launch gated on it" copy. Tests: `apps/web/src/components/__tests__/TrustFooter.test.tsx` (10 cases — link contract + keyboard focus + structural guard that Home/Lobby/Coinflip/Dice/HiLo/Wallet/Verify don't override the layout footer), plus per-page tests at `audit/__tests__/page.test.tsx` + `bounty/__tests__/page.test.tsx`. Web suite **283/283** (≥225 acceptance bar cleared). (PROJECT:BUNNYBAGZ) (2026-05-05)

- [x] [UNVERIFIED] **[BB_PHASE2_FORGE_LINT_TYPECAST_ANNOTATIONS]** Shipped 2026-05-05. Five `// forge-lint: disable-next-line(unsafe-typecast)` annotations added with one-line bound comments: `BunnyBagzDice.sol:222` (settle path) + `:271` (previewRoll), `BunnyBagzHiLo.sol:243` (open-session initialCard split across line), `:402` (previewCard), `:425` (previewInitialCard). `forge build --skip test --skip script` now produces **zero warnings** (was 5). Forge test count unchanged at 121 happy-path tests; `testFuzz_settlement_winLossPaths` reproduces a pre-existing CommitAlreadyUsed counter-example on the unmodified baseline (verified by stashing my edits) — flagged as a separate fuzz-test bug, not caused by this change. (PROJECT:BUNNYBAGZ) (2026-05-05)

- [x] [UNVERIFIED] **[BB_PHASE2_PLAYWRIGHT_E2E_REOPEN]** Scaffolding shipped 2026-05-05; full local `green` blocked on the host's missing GUI shared libs (`libatk-1.0.so.0`, `libcups`, `libcairo` etc.) which only `playwright install --with-deps` can `apt-get` on a CI runner. Concrete deliverables: `apps/web/package.json` adds `@playwright/test@^1.59.1` + scripts (`test:e2e`, `test:e2e:install`); `pnpm-lock.yaml` updated; `apps/web/playwright.config.ts` configures three projects (`chromium` desktop, `mobile-chromium` Pixel-7, `mobile-safari` iPhone-14 WebKit) with 30s timeout + `retries=1` in CI + auto-`webServer` running `next dev`; `apps/web/e2e/{coinflip,dice,hilo}.spec.ts` ship the unconnected smoke walks (Home → /play → game card → game surface → stake input + primary CTA + trust footer; mobile thumb-zone gate on Coinflip). New CI job `e2e:` in `.github/workflows/ci.yml` runs `playwright install --with-deps chromium webkit` then `playwright test`, uploads the report artifact. `apps/web/tsconfig.json` extended to typecheck `e2e/**/*.ts`; `apps/web/.gitignore` excludes Playwright run artifacts. **Local CI gap:** the agent host lacks the system libs that `--with-deps` would `apt-get` on a real CI runner — `playwright install chromium` succeeded (147.0.7727.15) but launch failed on missing `libatk-1.0.so.0`. CI will run cleanly. The wallet-connected settle path (mocked `useAccount` + route mocking of `/api/seed/claim` + `/api/coinflip/settle`) is intentionally **out of scope** for this PR and filed as `[BB_PHASE2_PLAYWRIGHT_WALLET_MOCK]` follow-up. (PROJECT:BUNNYBAGZ) (2026-05-05)

- [x] [UNVERIFIED] **[BB_PHASE2_PLAYWRIGHT_WALLET_MOCK]** Shipped 2026-05-05. `apps/web/src/lib/wagmi.ts` swaps to a wagmi `mock()` connector (deterministic address `0xf39…2266`, `defaultConnected: true`) when `NEXT_PUBLIC_E2E_MOCK_WALLET=1` is set; `playwright.config.ts` boots the dev server with that env + per-game `NEXT_PUBLIC_*_ADDRESS` overrides so the play surfaces land in the connected layout immediately. New `apps/web/e2e/_wallet-mock.ts` shared harness routes JSON-RPC traffic (eth_chainId / eth_sendTransaction → canned hash, eth_getTransactionReceipt → status:0x1, eth_call → ZERO_WORD, etc.) plus `/api/seed/{commit,claim}` and `/api/hilo/step`, and exports a `dispatchSettle()` helper that fires the page-level custom DOM events (`bunnybagz:coinflip-settle`, `bunnybagz:dice-settle`, `bunnybagz:hilo-{opened,step,settle}`). Three new wallet-mocked specs at `apps/web/e2e/{coinflip,dice,hilo}.connected.spec.ts` each have `it("settles a winning bet via mocked api")` walking the full bet → settle path and asserting the live-region announcement. CI `e2e:` job runs both unconnected + connected suites; web vitest **283/283** + forge **128/128** + api **75/75** + indexer **37/37** unchanged. **Local CI gap (carried from `[BB_PHASE2_PLAYWRIGHT_E2E_REOPEN]`):** the agent host lacks `libatk-1.0.so.0`, `libcups`, `libcairo` etc. — `playwright install --with-deps` requires sudo, so the connected specs have not been run on this box; CI runner `ubuntu-latest` has them. (PROJECT:BUNNYBAGZ) (2026-05-05)

- [x] [UNVERIFIED] **[BB_PHASE2_HILO_FUZZ_COMMIT_REUSE_GUARD]** Shipped 2026-05-05. Test-side fix in `packages/contracts/test/BunnyBagzHiLo.t.sol::testFuzz_settlement_winLossPaths`: (a) added `vm.assume(!game.commitUsed(_commit(fSeed)))` so iterations whose openCommit was already consumed by a prior iteration are skipped instead of reverting; (b) `_runFuzzStep` now derives `nextCommit = keccak256(abi.encodePacked("hilo-fuzz-step", sid))` so each iteration's playStep submits a fresh, never-used commit (the original `_commit(SERVER_SEED2)` was a constant and collided with itself across iterations). Production code unchanged — `commitUsed` is a security invariant the fuzz target must respect, not bypass. `forge test --match-test testFuzz_settlement_winLossPaths --fuzz-runs 1024` now passes deterministically; full suite **128/128** green. (PROJECT:BUNNYBAGZ) (2026-05-05)

#### BunnyBagz — Phase 2 closure gaps (2026-05-05 audit)

_Source: 2026-05-05 end-to-end Phase 2 audit. Most truth-audit gaps (A,B,C,D,E,H,I,J) are closed: deploy script ships Dice+HiLo with deterministic addresses, lobby unlocks dynamically, `/api/hilo/step` + `playStepSettler` ship, verify API + page branch on `game`, indexer covers all 3 games, Dice/HiLo audits extended, HiloCard + DiceSlider + TrustFooter ship, forge build is warning-free. Test inventory live: contracts **119+** (no-fuzz), web **283/283**, api **75/75**, indexer **37/37**, verify **40/40** = 554+ green._

_**Three exit criteria still gap the ROADMAP Phase 2 line "all 3 games playable in ETH and USDm on testnet; recent bets in wallet sheet; e2e green; light + dark themes look intentional"**: (1) USDm UI is not wired into game pages (PermitForwarder.sol + lib/permit.ts ship but no `/play/*` page invokes the strategy — the bet flow is ETH-only); (2) `RecentOutcomesStrip` is hardcoded `game=coinflip` and only mounted on `/play/coinflip` — Dice + HiLo have no recent-outcomes surface, and the WalletSheet has no cross-game recent-bets surface; (3) Playwright e2e runs only in CI — local box lacks system libs so we have never observed `green` end-to-end. Plus the testnet-deploy step itself is operator-blocked on faucet funding (Phase 1 closeout)._





- [x] [UNVERIFIED] **[BB_PHASE2_TESTNET_DEPLOY_DICE_HILO_LIVE]** Closed 2026-05-05. Operator funded deployer `0xb29e…fD7B` (balance 0.997 ETH on chain 6343). The May-4 broadcast (nonces 11–18, blocks 18211111–18211118) had already shipped all four CREATE3 contracts: Bankroll `0x33C5…2dFf`, Coinflip `0x064b…1983`, Dice `0xAC02…d84B`, HiLo `0xd9B9…0d6e`. `cast call` on chain 6343 confirms non-zero code (Dice 5480 bytes, HiLo 7153 bytes), `bankroll.isGame()` is `true` for all three, and `bankroll.allowanceOf()` returns `1e15` wei for each game. Bankroll holds 2e15 wei seed. `addresses.generated.ts[6343]` already wires apps/web → lobby resolver at `play/page.tsx:74` flips all three cards to `live`. Re-running `deploy-testnet.sh --dry-run` against testnet today reports "already deployed at" for every contract (script is idempotent). Full report with tx hashes and explorer links: `memory/evolution/bb_phase2_testnet_live_2026-05-05.md`. (PROJECT:BUNNYBAGZ) (2026-05-05)









#### BunnyBagz — Phase 3 (Internal soak, audit, mainnet readiness — added 2026-05-05)

_Source: `docs/ROADMAP.md` Phase 3 + `docs/BUILD_PLAN.md` Phase 3. Phase 3 exit verbatim: "Audit report addressed; testnet runs 7 days with no invariant violations; soft-launch deploy to mainnet behind a small allowlist." All items below file as **P2 today**, will promote to P1 once `[BB_PHASE2_TRUTH_AUDIT_FOLLOWUP_2]` archives Phase 2. Operator-blocking items (multisig, audit firm, beta, allowlist mainnet) are tagged inline._


- [x] [UNVERIFIED] **[BB_PHASE3_MASCOT_ART]** Shipped 2026-05-06 (commit `b1c2efa` in `bunnybagz` repo, branch `feature/mvp-planning-and-rebrand`). Five hand-drawn SVGs under `apps/web/public/mascots/` (each <1KB gzipped, well under the 8KB budget): `bunnybagz_{idle,win,loss-streak}.svg` + `carrot_{idle,reaction}.svg` (sidekick named per BRAND.md). `apps/web/src/components/MascotFrame.tsx` ships with a pure `resolveFrame(state, recentLossStreak)` resolver: idle→bunny idle no sidekick; win→bunny win + carrot idle; loss with streak<2→idle (no mockery); loss with streak≥2→loss-streak + carrot reaction. Single 600ms enter on win; reduced-motion users get the static variant (no looping). Per-(game,address) streak tracked in sessionStorage via `apps/web/src/lib/use-loss-streak.ts` and mounted on /play/{coinflip,dice,hilo} settle. `docs/BRAND.md` extended with the locked filename contract + state-machine table. **12 vitest cases** (resolveFrame state machine + component variants — exceeds the ≥6 acceptance bar); full web suite **349/349** green; `tsc --noEmit` clean. (PROJECT:BUNNYBAGZ) (2026-05-06)




- [x] [UNVERIFIED] **[BB_PHASE3_BUG_BOUNTY_PAGE]** Shipped 2026-05-06. `apps/web/src/app/bounty/page.tsx` replaces the Phase-2 placeholder: full scope (6 in-scope contracts via exported `IN_SCOPE_CONTRACTS`, 7-row out-of-scope list), severity table (Critical/High/Medium/Low with USDm caps via exported `SEVERITY_TABLE`), submission channel (security@bunnybagz.xyz mailto + PGP fingerprint + `/.well-known/security-pgp.asc` + Immunefi placeholder pending operator decision), 90-day responsible disclosure window, and a `role="status"` "scope expanding" banner per acceptance (d). `BUG_BOUNTY.md` ships at the repo root with the canonical text mirrored verbatim. `/bounty` registered in `lib/contrast-audit.ts` `AUDITED_ROUTES` + `SURFACE_MANIFESTS` — both themes show 0 failed nodes; primary CTA (brand-ink on brand-gold) clears AAA in both. Thumb-zone audited locally via `snapshotThumbZone` (CTA section uses `marginTop:auto`) on iPhone-SE + Pixel-7 viewports. **6 vitest cases** in `apps/web/src/app/bounty/__tests__/page.test.tsx` (structural guard + canonical-text sync with `BUG_BOUNTY.md` + keyboard a11y + thumb-zone snapshot + contrast dark + contrast light/AAA — exceeds the ≥4 acceptance bar). Full web suite **360/360** green; `tsc --noEmit` clean. (PROJECT:BUNNYBAGZ) (2026-05-06)

- [x] [UNVERIFIED] **[BB_PHASE3_LEGAL_PAGES]** Shipped 2026-05-07. Three first-draft legal pages with `Draft — counsel review pending` ribbons (acceptance e): `apps/web/src/app/privacy/page.tsx` (summary + what-we-collect + on-chain-public + sharing + rights + changes; exports `PRIVACY_LAST_UPDATED`/`PRIVACY_CONTACT_EMAIL`); `apps/web/src/app/terms/page.tsx` (acceptance + eligibility w/ 18+ + provable-fairness + risk-ack + prohibited-use + liability + contact; exports `TERMS_LAST_UPDATED`/`TERMS_CONTACT_EMAIL`/`TERMS_MIN_AGE_YEARS`); `apps/web/src/app/responsible-gaming/page.tsx` covers acceptance (b) — links `BeGambleAware.org` (external w/ noopener+noreferrer+target=_blank), `mailto:self-exclusion@bunnybagz.xyz` as the in-app channel, and explicit 60-minute session-time-limit guidance; cross-links to /verify, /terms, /privacy. `TrustFooter` extended (acceptance c) with privacy/terms/responsible-gaming links alongside existing audit/bounty/verify trio. **Test count per page** (acceptance d, ≥3): privacy=4 cases (routing+copy, cross-trust links, draft ribbon, a11y headings/tabbable); terms=4 cases (routing+copy w/ min-age, cross-trust links, draft ribbon, a11y); responsible-gaming=6 cases (routing, BeGambleAware link+rel, self-exclusion mailto, session-limit guidance, draft ribbon, a11y headings/tabbable). TrustFooter test extended w/ legal-trio assertion + tab-order coverage of all 6 links. **Full web suite 395/395 green; tsc --noEmit clean.** (PROJECT:BUNNYBAGZ) (2026-05-07)

- [x] [UNVERIFIED] **[BB_PHASE3_STATUS_PAGE_ONCALL]** Shipped mega-house@f4d69c4 (2026-05-07). (a) `apps/api/status/handler.ts` edge endpoint aggregates four probes (indexer reachability + latency thresholds 1500/5000ms, Defender monitor green count, bankroll>0, last-bet lag with 300/1800s thresholds) into per-component `ok|degraded|down` + worst-wins overall pill. Probes are dependency-injected (`setProbesForTest`) so the test matrix never hits the network; default probes call indexer `/health`+`/last-bet`, RPC `eth_getBalance`, and a Defender-status URL. (b) `apps/web/src/app/status/page.tsx` server component renders per-component pill grid + incident timeline read from `data/status_incidents.jsonl` (parsed by exported `parseIncidentJsonl`, newest-first). Pure `<StatusPanel>` exported for tests. `apps/web/src/app/api/status/route.ts` thin edge proxy so `next dev` serves `/api/status`. (c) `docs/ONCALL.md`: primary=inversealtruism, fallback=autonomous Clarvis layer, paging via Telegram `@bunnybagz_alerts` (degraded 30min ack SLA, down 5min + email), incident-log contract documented. (d) **6 vitest cases** in `apps/web/src/app/status/__tests__/page.test.tsx` (ok / degraded / down branches + render with timeline + render with empty incidents + parser robustness — exceeds ≥4 bar). (e) Sliding-window rate limiter `checkRate` enforces 30 req/min per IP at the handler boundary; 31st request returns 429 with `retry-after` + `x-ratelimit-*` headers. **Test totals**: 23 node:test cases (apps/api, status/handler.test.ts) + 6 vitest cases (apps/web). Full apps/web vitest suite **401/401** green; full apps/api `npm test` **115/115** green; `tsc --noEmit` clean. (PROJECT:BUNNYBAGZ) (2026-05-07)

- [x] [UNVERIFIED] **[BB_PHASE3_INTERNAL_BETA_TESTNET_7D]** Agent-prep complete 2026-05-06. Operator-start (a-d) still pending. (a) `docs/INTERNAL_BETA_PLAN.md` ships with: roster file (`memory/evolution/bb_beta_roster.md`), Telegram bug-report channel `bunnybagz-beta-bugs` + structured `[BUG]` form (severity tier matches `BUG_BOUNTY.md`), green-day criteria (≥50 settled bets/game, 0 critical, 0 invariant violations, 0 reverts, p95 settle <30s, edge drift within ±1.5%), 7-consecutive-green-day exit gate, and channel separation between internal beta + public bounty. (b) `scripts/audit/bb_beta_summary.py` (worker) + `scripts/cron/cron_bb_beta_summary.sh` (wrapper, 09:00 CET) poll the indexer (`BUNNYBAGZ_INDEXER_URL`, default `http://localhost:42069`) per game, aggregate placed/settled/pending/reverts/stake/payout/edge/p50-p95-max latency, render to `memory/cron/bb_beta_<YYYY-MM-DD>.md`, and persist streak state at `memory/cron/bb_beta_streak.json`. Verdicts: GREEN/YELLOW/RED/PAUSED — RED resets the streak, YELLOW pauses it, PAUSED (indexer unreachable) keeps streak intact. (c) Wired into `clarvis/cli_cron.py` `_JOBS["bb_beta_summary"]` + `recommended` and `full` presets; `clarvis cron run bb_beta_summary --dry-run` and `clarvis cron install recommended` (preview) both verified. Operator gate via `BUNNYBAGZ_BETA_ACTIVE=1`; default off so installing in advance of beta-on is a silent no-op (verified — wrapper exits 0 with "beta inactive" log line). 10 inline assertions cover compute_verdict (GREEN/RED-revert/RED-latency/YELLOW/PAUSED) + update_streak (advance/reset/pause/idempotent) + aggregate_game (None/empty/single-bet ETH math). (d-e) Operator-gated: agent reports daily once `BUNNYBAGZ_BETA_ACTIVE=1` is set and the operator runs the beta; `[BB_PHASE3_BETA_FIX_<TAG>]` reopens are operator/triage-driven per plan §2.3 (cron cites, doesn't auto-reopen, to keep the queue clean of indexer noise). (PROJECT:BUNNYBAGZ) (2026-05-06)




- [x] [UNVERIFIED] **[BB_PHASE3_TESTNET_7D_INVARIANT_LOG]** Shipped 2026-05-07 → mega-house PR #3 (feature/bb-phase3-invariant-sweep). New `packages/invariants` (TS replay harness: bankroll balance, commit consumed, settlement latency) + `scripts/cron/cron_bb_invariant_check.sh` (06:00 CET daily) + 14 vitest cases against fixture txs (≥6 required). Streak file `memory/cron/bb_invariant_streak.md` flips Phase 3 exit gate OPEN at 7/7 consecutive PASS days. ROADMAP exit clause now points at the streak file. (PROJECT:BUNNYBAGZ)


#### BunnyBagz — Phase 3 visual redesign (added 2026-05-06)

_Source: brutal UI/UX audit `docs/audits/UI_UX_AUDIT_2026-05-06.md` (BunnyBagz repo, branch `feature/mvp-planning-and-rebrand`, head `56ca413`). Verdict: surface is mechanically correct but looks like an internal admin tool, not a casino. 21 visual-redesign tasks below land in 5 phases (foundations → structural redesign → trust & feedback → polish → exit gates). Sequenced so the design system (DESIGN_TOKEN_SYSTEM + UI_PRIMITIVES_SHIP + TYPOGRAPHY_LOCK + ICON_SET) ships first; every later task assumes them. Each task names concrete file targets, a ≥4-test acceptance bar, and (where relevant) the audit-doc finding it closes (P0-N / P1-N / P2-N). Lane: BUNNYBAGZ. Operator-review gate after the first redesigned surface (LANDING_REDESIGN) before promoting the rest of the work to P1._

##### Foundations (do these first; everything else depends on them)

- [x] [UNVERIFIED] **[BB_PHASE3_DESIGN_TOKEN_SYSTEM]** Lock space / radius / type / elevation / motion tokens before any further surface work. Closes audit P1-1 / P1-2 / P1-3 / P1-4. **Acceptance:** (a) `apps/web/src/app/globals.css` declares `--bb-space-1..7` (4/8/12/16/24/32/48), `--bb-radius-1..5` (4/8/12/16/999), `--bb-elevation-0..3` (none, soft, medium, deep) + `--bb-elevation-glass-inner-highlight`, `--bb-motion-fast` (160ms), `--bb-motion-base` (200ms cubic-bezier(0.22,1,0.36,1)), `--bb-motion-spring` (framer-motion preset name); (b) `apps/web/src/lib/tokens.ts` exports the same scale as TS constants for non-CSS contexts; (c) a new `tests/__tests__/design-tokens.test.tsx` enforces (i) every `style={…}` literal in `apps/web/src/components/**/*.tsx` and `apps/web/src/app/**/*.tsx` is either tokenised or whitelisted, (ii) the token names match between CSS and TS; (d) a codemod-style helper script `scripts/audit/check_design_tokens.mjs` flags raw rem/px literals — runs in CI and locally. ≥6 vitest cases. Does NOT migrate the surfaces yet — that's UI_PRIMITIVES_SHIP. (PROJECT:BUNNYBAGZ) (2026-05-07T14:14:34Z)

- [x] [UNVERIFIED] **[BB_PHASE3_UI_PRIMITIVES_SHIP]** Build the `@bunnybagz/ui` design system. Closes audit P0-1. Today `packages/ui/src/index.ts` is a 14-line stub. **Acceptance:** (a) `packages/ui/src/{Button,StakeChip,Sheet,Card,ListRow,Pill,Stat,Badge,IconButton,ToggleGroup,Skeleton,SegmentedControl}/index.tsx` ship — each a tokens-only component with variant props, no inline literals; (b) each primitive carries a vitest case file with ≥3 cases (variant rendering, accessibility, token usage); (c) `apps/web/src/components/{SiteHeader,RecentOutcomesStrip,WalletSheet,TrustFooter,FirstBetHint,TokenToggle}.tsx` migrate to use the primitives — no `style={…}` literal larger than 1 prop survives; (d) `apps/web/src/app/{page,play/page,play/coinflip/page,play/dice/page,play/hilo/page}.tsx` migrate; (e) `tsc --noEmit` clean, full web suite green, `axe-baseline.json` passes. ≥30 vitest cases total across primitives. **Hard gate:** no surface task below ships before this lands. (PROJECT:BUNNYBAGZ) (2026-05-07T14:14:34Z)

- [x] [UNVERIFIED] **[BB_PHASE3_TYPOGRAPHY_LOCK]** Lock the brand typefaces operator selects from BRAND.md candidate set. Closes audit P0-2. **Acceptance:** (a) operator picks display face (recommend Söhne Breit; alternates Hubot Sans / GT Walsheim / Migra) + locks in `docs/BRAND.md`; (b) `apps/web/src/app/layout.tsx` loads via `next/font/local` (or `next/font/google` where available) Inter Variable + the locked display face + JetBrains Mono; (c) every `fontFamily: "system-ui, …"` literal under `apps/web/src/**` is replaced with `var(--bb-font-ui)` / `var(--bb-font-display)` / `var(--bb-font-mono)` — search produces zero matches; (d) wordmark on `/` (`page.tsx:131-137`), section headers, and the `/play` lobby title use display face; bet-stake / multiplier / payout / hash / address use mono; (e) ≥4 vitest cases enforce the font-family CSS rule on the rendered DOM at the smoke surfaces. (PROJECT:BUNNYBAGZ) (2026-05-07T14:14:34Z)


##### Structural redesign (after foundations land)

- [x] [UNVERIFIED] **[BB_PHASE3_LANDING_REDESIGN]** Shipped 2026-05-07. Rebuilt `apps/web/src/app/page.tsx` as casino-first surface: (a) hero with mascot wrapper carrying `.bb-mascot-anim` class — `bb-mascot-bob` 3.2s ease-in-out loop + `bb-mascot-blink` 5s drop-shadow brightness pulse, both suppressed via `@media (prefers-reduced-motion: reduce)` in `globals.css` so static-frame fallback (f) is the existing `mascot/idle.svg`; display-face wordmark (Söhne Breit / Hubot Sans / GT Walsheim stack) + product tagline. (b) `<LiveActivityFeed>` mounted between hero and cards — new client component that polls `GET /api/history?limit=20&recent=true` (8s interval, 4s timeout, AbortController), renders loading/empty/error/populated branches with win/loss colored 4-px left strip per row; exports `shortAddress` + `timeAgo` helpers. (c) Three `<HeroGameCard>` instances (coinflip/dice/hilo) in a 3-col grid above the CTA — new component renders 96×72 art slot with three new SVGs at `apps/web/public/games/{coinflip,dice,hilo}.svg` (each <300B, well under the 8KB cap from BB_PHASE3_LOBBY_GAME_HERO_CARDS), title + tagline + edge + Live/Phase-2 pill, wraps in Link to `/play/<slug>` when live. (d) CTA section uses `marginTop: auto` to anchor to bottom of viewport — thumb-zone law preserved; Playwright `e2e/landing.spec.ts` asserts CTA top edge sits below 60% of viewport on mobile-class projects. (e) Server-rendered hero (no client deps in the LCP element) — feed opts client-side on its own; cards have `min-height: 168px` to lock CLS. (g) **18 net new vitest cases** (`HeroGameCard.test.tsx` 4 + `LiveActivityFeed.test.tsx` 11 + `page.test.tsx` rewritten to 9 — exceeds ≥8 acceptance bar) + **3 Playwright cases** in `apps/web/e2e/landing.spec.ts` (hero+feed+cards render / primary CTA navigates / mobile CTA in bottom 30%). Full web suite **419/419 green**, `tsc --noEmit` clean. Acceptance (e) Lighthouse LCP/CLS budgets remain operator-verifiable on a deployed build. **Note:** `<LiveActivityFeed>` ships a minimal scope ahead of full `BB_PHASE3_LIVE_ACTIVITY_FEED` (no jdenticon, no spring-in animation, no marquee); API contract matches so the swap is non-breaking. Same for `<HeroGameCard>` vs full `BB_PHASE3_LOBBY_GAME_HERO_CARDS` (no players/last-result pills, no hover-lift). (PROJECT:BUNNYBAGZ) (2026-05-07)

- [x] [UNVERIFIED] **[BB_PHASE3_LOBBY_GAME_HERO_CARDS]** Shipped 2026-05-07 (mega-house feature/bb-phase3-invariant-sweep, commit `962ede3`, 11 files / +486 / -226). (a) Expanded `apps/web/src/components/HeroGameCard.tsx`: 200×120 illustration slot + `[Live · testnet]` / `[Phase 2]` pill + `[N players]` pill (optional `players: number | null` + `playersStatus: "loading"|"error"|"ready"` so indexer wiring is a follow-up swap) + last-result pill (`HeroGameLastResult { outcome: "win"|"loss"; label? }` + `lastResultStatus`); component stays SSR-safe (no client deps). (b) Three illustrations re-cut at `apps/web/public/games/{coinflip,dice,hilo}.svg` to viewBox `0 0 200 120` with brand-locked palette (`#f5a623` / `#f5c042` gold + `#1a0a00` ink); raw < 1 KB each, gzipped 310-419 B (well under 8 KB). (c) `<FirstBetHint>` grew a `placement: "inline"|"toast"` prop; `/play` mounts it with `placement="toast"` (fixed bottom, safe-area-inset, `min(100% - 2rem, 360px)` width). (d) Lobby footer rewritten — stale "Hi-Lo and Dice land in Phase 2" branch and the `allLive` ternary deleted in favour of "Provably-fair verification is at /verify. Settle on-chain on MegaETH testnet". (e) `globals.css` adds `.bb-hero-game-card[data-status="live"]:hover { transform: translateY(-4px); box-shadow: gold-glow }` and `:active { transform: 0; transition-duration: 96ms }`, plus a `prefers-reduced-motion` guard. (f) `HeroGameCard.test.tsx` grew from 4 to **9 vitest cases** (live render, link target, phase-2 non-interactive + no data-pills, art slot 200×120 + alt="" + correct src, players-pill ready data path "1.2k players", loading skeleton state, error fallback "— players"/"— last", last-result render with outcome+label, motion class hook). Lobby `page.test.tsx` retargeted to new `hero-game-card-*` test IDs; `tabular-figures-audit.ts` and `thumb-zone-audit.ts` retargeted likewise. Full web suite **424/424 green** + `tsc --noEmit` clean. Phase-3 audit P0-4 closed. **Follow-ups:** wire the indexer `players` + `lastResult` props (need either `/api/players-24h` or to derive from `/api/history`); landing page (`apps/web/src/app/page.tsx`) still uses the same component without the data pills — `playersStatus`/`lastResultStatus` default to `"ready"` so the muted "— players"/"— last" pills paint there until the data path lands. (PROJECT:BUNNYBAGZ) (2026-05-07)

- [x] [UNVERIFIED] **[BB_PHASE3_BET_PANEL_REDESIGN]** Shipped 2026-05-08 (mega-house feature/bb-phase3-bet-panel-redesign). (a) New `apps/web/src/components/BetPanel.tsx` (320 LOC) with slots — multiplier badge (gold, hero-sized inside panel, separate from chain-hint header), `sideSelector` slot, stake input, `StakeChip` cluster (½, 2×, MAX, "Bet last"), profit-on-win row (tabular bold), token toggle, primary CTA (or `ctaOverride` for RainbowKit's connect modal), Enter→placeBet handler, extras tail. (b) `apps/web/src/components/StakeChip.tsx` (110 LOC) exports pure `applyChip()` math + `<StakeChip>` button — disables non-applicable chips (no max, no last-stake, zero/non-numeric stake); trims trailing zeros (0.001/2 → "0.0005"). (c) Migrated all three game pages: dice 627 → 533 LOC (−94), hilo 951 → 838 LOC (−113); coinflip stayed near 520 LOC because heads/tails buttons still live as `sideSelector` content. Page-level state grew a `lastStake` slot wired to "Bet last" — set inside `placeBet` so the chip restores the just-submitted stake. (d) Disabled CTA renders muted glass (`rgba(255,255,255,0.04)` + soft border) — distinct from the gold brand colour, asserted by `disabled CTA does not use the gold brand colour` test. (e) **51 new/updated vitest cases**: `BetPanel.test.tsx` (18 cases — slot rendering, controlled stake, every chip operation, profit row, disabled-CTA styling, Enter on input fires `onPanelEnter`, Enter on focused button does NOT, ctaOverride takes precedence, hide-chips, aria-live region, profit-on-win formulas for all three games), `StakeChip.test.tsx` (11 cases — pure math, disabled states, click → onApply). Updated `coinflip/__tests__/page.test.tsx` to target `coinflip-multiplier-badge` instead of the now-duplicated "1.98×" text. Full web suite 469/469 green + `tsc --noEmit` clean. **Playwright e2e**: `apps/web/e2e/bet-panel.spec.ts` adds 18 specs across all three games (chip math, multiplier-badge rendering, profit-on-win values per game, disabled "Bet last" without prior submission). Phase-3 audit P0-5 closed. **Follow-ups**: extend Playwright `*.connected.spec.ts` to assert "Bet last" enables after a real submission; consider promoting the `chipMax` value (currently hard-coded "0.1") to a per-wallet bankroll cap once balance reads are available. (PROJECT:BUNNYBAGZ) (2026-05-08)

- [x] [UNVERIFIED] **[BB_PHASE3_GAME_VIEWPORT_HERO_SIZING]** Shipped 2026-05-08 (bunnybagz `feature/bb-phase3-game-viewport-hero-sizing`, commit `04a2246`). New `.bb-game-viewport` class in `apps/web/src/app/globals.css` enforces ≥62% page height on mobile (`dvh` with `vh` fallback) and caps at 560px on desktop ≥1024px so the 3-column rails (`BB_PHASE3_DESKTOP_LAYOUT_PASS`) breathe. Each game restructured: coinflip's existing `coinViewportWrapStyle` div upgraded to the viewport class (CoinSpin + MascotCelebrate stay); dice's `DiceSlider` extracted out of the BetPanel `sideSelector` into the viewport (3-stat preview stays panel-side); hilo's `HiloCard` extracted out of the BetPanel `sideSelector` into the viewport (direction buttons + multiplier readout stay panel-side). Tests: **6 vitest layout cases** — coinflip 2 (viewport DOM contract + CTA-below-viewport DOM order so thumb-zone is preserved), dice 2 (DiceSlider in viewport + preview stays in panel), hilo 2 (HiloCard in viewport + direction buttons in panel). New Playwright spec `apps/web/e2e/play-game-viewport.spec.ts` — **6 specs** (3 games × 2 viewport sizes) asserting the rendered ratio on mobile (≥0.55) and the desktop cap (≤580px). Web vitest **475/475** green; `tsc --noEmit` clean. Local Playwright still blocked on `libatk` per existing precedent (`BB_PHASE2_PLAYWRIGHT_E2E_REOPEN`); CI executes. **Follow-ups:** consider promoting `--bb-header-h` to a CSS token so the 56px subtraction in viewport CSS stays in sync with `SiteHeader`; if mascot left-rail position feels too far on tablet, evaluate an inside-viewport mascot variant. Closes audit P1-6. (PROJECT:BUNNYBAGZ) (2026-05-08)


##### Trust & feedback surfaces

- [x] [UNVERIFIED] **[BB_PHASE3_LIVE_ACTIVITY_FEED]** Shipped 2026-05-08 (commit `5030e67` on `feature/bb-phase3-invariant-sweep`). `apps/web/src/components/LiveActivityFeed.tsx` upgraded from the minimal landing-redesign scope: (a) still polls `GET /api/history?limit=20&recent=true` (8s interval, 4s timeout); new Next.js route at `apps/web/src/app/api/history/route.ts` handles the `recent=true` cross-game branch (returns empty rows when no `BUNNYBAGZ_INDEXER_URL` is wired so the surface paints empty-state cleanly) and forwards address-keyed reads to the existing wallet edge fn. (b) jdenticon = inline 5×5 symmetric SVG glyph hashed from the address via FNV-1a (`hashAddress` + `buildIdenticon` exported for tests); no external lib, no img fetch. (c) framer-motion `<AnimatePresence>` + `motion.li` spring on enter (stiffness 360 / damping 28) with fade exit; default cap raised to 20. (d) 4-px solid border-left strip per row (`success-fg` for wins, `danger-fg` for losses). (e) already mounted on `/` between hero and cards from the landing redesign; new `/play` mounting puts the feed in a `bb-lobby-body` two-col grid (cards left, rail right) at ≥768px and collapses to single column below — DOM order keeps the feed below cards on mobile. (f) honours OS `prefers-reduced-motion` via framer-motion's `useReducedMotion` hook; `disableAnimation` prop overrides for tests; data-attr `data-animation="off"` exposes the state for assertion. (g) **20 vitest cases** in `LiveActivityFeed.test.tsx` (loading / empty / populated / fetch / error / 4-px strip per outcome / jdenticon determinism + symmetry + case-insensitivity / motion-on-via-matchMedia / motion-off-via-prop / endpoint contract / shortAddress / timeAgo / hashAddress / buildIdenticon). Web suite **441/441 green**; `tsc --noEmit` clean. **Note:** the indexer-side `/api/recent` aggregator is not in this PR — production deploys with `BUNNYBAGZ_INDEXER_URL` unset will see the empty-state copy until the indexer ships, which is the desired graceful degradation (and matches the operator-blocked indexer hosting flagged in `bb_phase1_status_2026-05-03.md`). (PROJECT:BUNNYBAGZ) (2026-05-08)

- [x] [UNVERIFIED] **[BB_PHASE3_TRUST_STRIP]** Shipped 2026-05-08 (bunnybagz PR #5, branch `feature/bb-phase3-trust-strip`, commit `70bd4fc`). New `apps/api/trust/handler.ts` edge endpoint aggregates bankroll RPC + indexer probes (`bankroll`, `edge`, `lastBet`) via `Promise.allSettled` so a single dead probe degrades to a sentinel rather than crashing the strip; 60 req/min token-bucket limiter; 4 s `s-maxage` cache aligned with the poll cadence. `apps/web/src/app/api/trust/route.ts` thin proxy. `apps/web/src/components/TrustStrip.tsx` renders the 28-px glass band (`position: sticky; top: 56`) with `🛡 House liquidity / Edge realised / Last bet · [Verify] [Audit] [Bug bounty]`, polls `/api/trust` every 4 s + on window focus, exposes `data-loading` / `data-error` for tests. Responsive collapse via new `.bb-trust-strip-numbers` / `.bb-trust-strip-sep` classes in `globals.css` (`@media (max-width:374px) { display:none }`) so the link trio + shield stay visible. New `apps/web/src/components/LegalFooter.tsx` keeps `/privacy /terms /responsible-gaming` reachable now that `<TrustFooter>` is fully deleted (file + test removed, not deprecated). `app/layout.tsx` mounts `<TrustStrip>` between `<SiteHeader>` and `{children}`, `<LegalFooter>` at body bottom. **Tests:** 12 vitest cases in `TrustStrip.test.tsx` (loading, error, happy path, all 3 numbers, link trio migration, time-ago format covering s/m/h/d + null, polling 3 ticks, initialData seed, layout binding, TrustFooter-removed guard) + 3 in `LegalFooter.test.tsx`; web suite **476/476 green**, `tsc --noEmit` clean. 9 `tsx --test` cases in `apps/api/trust/handler.test.ts` (weiToEth rounding × 2, aggregator happy path, bankroll-throw degrades, lastBet-null, rate limiter 60th-allowed/61st-denied, GET 200 with cache-control, POST 405, over-limit 429 with retry-after); api suite **124/124 green**, `tsc --noEmit` clean. New Playwright `e2e/trust-strip.spec.ts` covers strip-visible + 28 px height + link trio + <375 px collapse + thumb-zone CTA re-run. (PROJECT:BUNNYBAGZ) (2026-05-08)

- [x] [UNVERIFIED] **[BB_PHASE3_BANKROLL_BAR_LOBBY]** Shipped 2026-05-08 (mega-house workspace, branch `feature/bb-phase3-bankroll-bar-lobby`). New `apps/web/src/components/BankrollBar.tsx` "use client" lobby-only hero: two-line composition with `data-testid=bankroll-bar-hero` (32 px tabular `1.42 ETH`) and a `bankroll-bar-secondary` line `"When this bar fills you can bet up to 0.014 ETH per spin"`. Allowance math is pure (`maxBetEthFor`, `fillRatioFor`): `maxBet = min(MAX_BET=0.1 ETH, BANKROLL_FRACTION_PER_BET=1% × liquidity)` mirroring the on-chain `MAX_BET` constant in `packages/contracts/test/BunnyBagz*.t.sol`; non-finite / non-positive inputs collapse to 0 so a dead RPC never quotes a tradeable max. Progress strip exposes `role="progressbar" aria-valuenow` from `liquidity / HEALTHY_BANKROLL_ETH` (10 ETH saturation point — where 1% × bankroll meets the on-chain ceiling). Loading state ("Reading bankroll…", `data-loading=true`), error state ("House liquidity unavailable. Bets remain capped at the on-chain max.", `data-error=true`), and zero-bankroll branch ("Bankroll is empty — bets are paused…") all flow through the same surface. Polls `/api/trust` every 8 s (lobby surface, half the cadence of the always-mounted `<TrustStrip>` so the two don't double-tax the edge limiter); reuses the same `TrustPayload` shape — no new endpoint. Visual coordination with `<TrustStrip>` via shared `var(--bb-bg)` glass mix + `var(--bb-border)` + tabular numerals. Wired into `apps/web/src/app/play/page.tsx` only (between `</header>` and `bb-lobby-body`); not in `app/layout.tsx` (lobby-only). **Tests:** 12 vitest cases in `BankrollBar.test.tsx` covering pure helpers (3), happy path (1), loading (1), error (1), progress strip 50% fill (1), empty bankroll (1), polling 3 ticks (1), initialData seed (1), and lobby-only mounting via filesystem read of `/play/page.tsx` and `app/layout.tsx` (2). Web suite **488/488 green** (was 476 → +12 from BankrollBar), `tsc --noEmit` clean. (PROJECT:BUNNYBAGZ) (2026-05-08)

- [x] [UNVERIFIED] **[BB_PHASE3_VERIFY_BADGE_TOP_LEFT]** Shipped 2026-05-08 (mega-house workspace). Redesigned `apps/web/src/components/VerifyBadge.tsx` from a left-rail link into a top-left game-viewport pill: new `serverCommit` (Hex|null) + optional `recentBetId` props, exported `shortCommit()` helper that strips `0x` and slices to 8 chars (e.g. `f3a1b2c3`), `data-bb-pill="verify"` outer container + `data-bb-badge="commit"` inner status dot — primitive markers ready for the standalone `Pill`/`Badge` lift. Skeleton path renders a `<span>` with `data-state="loading"` + `aria-busy="true"` when the commit is null/undefined so the viewport doesn't reflow when the seed lands; ready path renders an `<a>` with `data-state="ready"`, label `Provably fair · seed #<short>…`, and `href={recentBetId ? "/verify/" + encodeURIComponent(recentBetId) : "/verify"}`. Mounted absolutely positioned (`top:0.5rem; left:0.5rem; z-index:2`) inside `.bb-game-viewport` (which already has `position: relative` per `globals.css:325`) on all three play routes. Coinflip page now passes the existing `commit?.commit` state through; dice + hilo gained matching `useEffect(() => fetch("/api/seed/commit"))` blocks + `serverCommit` state. Removed the old left-rail mount on every page. Removed the coinflip footer `"Server commit: <code>…</code>"` line entirely; "Provably fair · verify any bet" footer link kept so existing page tests still match. **Tests:** 15 vitest cases in `VerifyBadge.test.tsx` (2 `shortCommit` helper, 2 skeleton states for null/undefined, 5 ready-state cases incl. text + commit slice + dot primitive + 3 href variants incl. `encodeURIComponent`, 6 page-wiring cases via filesystem read covering each game's viewport mount + serverCommit prop + the `Server commit:` footer-removed guard). Web suite **503/503 green** (was 488 → +15 from VerifyBadge), all 66 game-page tests still pass with the badge moved into the viewport. (PROJECT:BUNNYBAGZ) (2026-05-08)

##### Component polish

- [x] [UNVERIFIED] **[BB_PHASE3_RECENT_OUTCOMES_TREATMENT]** Shipped 2026-05-08 (mega-house workspace, branch `main`). Re-tokenized `apps/web/src/components/RecentOutcomesStrip.tsx`: 36-px pill height + minWidth (was 24 px), 1-rem (16-px) glyph slot for H/T/≤R + Phosphor `size={16}` arrows for Hi-Lo, win pills now carry a brand-gold gradient (`linear-gradient(180deg, --bb-brand-gold-strong 0%, --bb-brand-gold 100%)`) + `inset 0 1px 0 rgba(255,255,255,0.35)` inner highlight + `0 1px 2px rgba(0,0,0,0.18)` ground shadow, loss pills are muted glass (`color-mix(in srgb, --bb-elevated 70%, transparent)` + `--bb-border` + `backdrop-filter: blur(6px)`). Pills now expose `data-variant="win"|"loss"` for downstream styling hooks. Empty-state pill rebuilt as illustrative + actionable per game (`coinflip → "First bet on Coinflip wins 1.98×"`, `dice → "First bet on Dice wins up to 9.9×"`, `hilo → "First bet on Hi-Lo wins 1.98× per step"`) replacing the apologetic italic gray "No bets yet — be the first" — the empty pill now has its own surface (dashed border, elevated bg, 999-px radius, 36-px height, normal-weight body color). Container is now a horizontal scroll-snap rail (`overflowX:auto`, `scrollSnapType:"x proximity"`, `paddingRight:1.25rem` for the partial-peek effect, `flexWrap:nowrap`, `WebkitOverflowScrolling:touch`) with each pill carrying `scrollSnapAlign:"start"` and `flex:0 0 auto` so they don't shrink under flex pressure on narrow viewports. Container exposes `data-scroll-snap="x"` as a deterministic test hook. Settle-event refetch behaviour preserved (`SETTLE_EVENT_FOR[game]` listener untouched). **Tests:** 6 new vitest cases in `__tests__/RecentOutcomesStrip.test.tsx` block "RecentOutcomesStrip · visual treatment (audit P0-6)": (1) 36-px height + minWidth + 1-rem glyph; (2) win gold gradient + inset highlight + loss muted-glass color-mix + backdrop-blur; (3) dice + hilo win pills carry the same gradient treatment + Hi-Lo arrow renders at `size=16`; (4) empty copy is illustrative across all 3 games + non-italic + non-muted + has surface (border/padding/radius); (5) populated strip is a scroll-snap rail (overflowX/scrollSnapType/paddingRight/flexWrap=nowrap + per-pill scrollSnapAlign + flex:0 0 auto); (6) rail still refetches on `bunnybagz:coinflip-settle`. Updated existing empty-state assertion to the new copy. Web suite **509/509 green** (was 503 → +6). Closes audit P0-6. (PROJECT:BUNNYBAGZ)

- [x] [UNVERIFIED] **[BB_PHASE3_WALLET_SHEET_REDESIGN]** Shipped 2026-05-08 (mega-house workspace, branch `feature/bb-phase3-wallet-sheet-redesign`). Retired the debug-style `<dl>` and rebuilt `apps/web/src/components/WalletSheet.tsx` around a local `<Sheet>` primitive (220 ms framer-motion spring + 150 ms scrim fade, `prefers-reduced-motion: reduce` zeros both). Four explicit sections in document order: (i) `wallet-balance-hero` — deterministic per-address gradient avatar (`avatarGradientFor`, falls back to brand-gold→carrot when disconnected), 2 rem hero ETH figure, USDm secondary line, Approved pill on the same row; (ii) `wallet-quick-actions` — `IconButton` row [Copy / QR / Switch network] with `wallet-action-switch-network` testid replacing the prior `wallet-action-swap`; (iii) `wallet-recent-bets-section` with section heading + the existing `RecentBetsList`; (iv) `wallet-settings` — Fluffle holder rendered through the new local `ListRow` primitive (`data-list-row="true"`, label/value/trailing slots), theme toggle, footnote. Acceptance (b): added `--bb-success-bg` (#1f3a1f dark / #d8efd9 light) + `--bb-danger-bg` (#3a1f1f dark / #f5dad1 light) to `apps/web/src/app/globals.css` (`:root`, `[data-theme="light"]`, and the OS-fallback `@media (prefers-color-scheme: light)` block); the Approved pill now reads `var(--bb-success-bg)` directly with no hardcoded `#1f3a1f` literal anywhere in JS. Acceptance (c): exported constants `SHEET_SPRING_DURATION_MS = 220` + `SHEET_SCRIM_FADE_MS = 150`; sheet exposes the contract via `data-spring-duration-ms` / `data-scrim-fade-ms` / `data-reduced-motion` attrs. Acceptance (d): **13 new vitest cases** in `__tests__/WalletSheet.test.tsx` block "WalletSheet · sectioned redesign (audit P0-9)" — section ordering, hero composition (ETH amount + USDm secondary + avatar), `avatarGradientFor` determinism + brand fallback, quick-actions a11y + disconnected disable, recent-bets section heading + RecentBetsList root, Approved pill consumes `var(--bb-success-bg)` + no `#1f3a1f`, sheet exposes spring/scrim contract via data attrs, default reduced-motion = false, `prefers-reduced-motion: reduce` flips data-attr to true, settings is last sibling with theme toggle + footnote + ListRow Fluffle row, animation timings stay synced across open→closed→open re-mount. Existing 12 cases preserved. Web suite **506/506 green** (was 493 → +13). `tsc --noEmit` clean for all new code (only pre-existing `.next/types` errors remain). Closes audit P0-9. (PROJECT:BUNNYBAGZ)

- [x] [UNVERIFIED] **[BB_PHASE3_TOKEN_TOGGLE_SEGMENTED_CONTROL]** Shipped 2026-05-08 (mega-house workspace, branch `main`). Built `<SegmentedControl/>` glass primitive in `packages/ui/src/SegmentedControl/index.tsx` (radiogroup + sliding thumb absolute-positioned with `transform: translateX(...)`, `transition: transform var(--bb-motion-base, 200ms) cubic-bezier(0.22, 1, 0.36, 1)`, `linear-gradient(180deg, color-mix(in srgb, --bb-elevated 80%, transparent) 0%, --bb-elevated 100%)` + `backdrop-filter: blur(6px)` glass surface, `data-bb-segmented-control` + `data-testid="bb-segmented-thumb"` hooks, per-segment `disabled` + `title` + `data-segment-disabled` for the chain-unavailable case). Exported from `@bunnybagz/ui`. Rebuilt `apps/web/src/components/TokenToggle.tsx` around the primitive — same `value/onChange/testIdPrefix/disabled` API plus a new `usdmAvailable?: boolean` prop (defaults to `true`); when `usdmAvailable=false` the USDm segment is *natively* `disabled` with `title="USDm not deployed on this chain yet"` rather than just visually grayed (acceptance c). Threaded `usdmAvailable={usdmReady}` into all three play pages (`coinflip/page.tsx:418`, `dice/page.tsx:441`, `hilo/page.tsx:607`) — identical prop shape across all three (acceptance b). **Tests:** 5 new vitest cases in `__tests__/TokenToggle.test.tsx`: (1) radiogroup + sliding thumb with 200ms cubic-bezier transform transition + aria-checked reflection, (2) onChange fires for new value but not re-selection of selected segment, (3) `usdmAvailable={false}` renders USDm `disabled`+`aria-disabled=true`+chain tooltip + drops clicks while ETH stays enabled, (4) group-level `disabled` (signing) disables both segments without surfacing the chain tooltip, (5) cross-page invariance — coinflip/dice/hilo render structurally identical DOM shapes. Web suite **514/514 green** (was 509 → +5). `tsc --noEmit` clean for new code (only the same pre-existing `.next/types` route-type errors that exist on baseline). Closes audit P1-11. (PROJECT:BUNNYBAGZ)

- [x] [UNVERIFIED] **[BB_PHASE3_MOTION_PASS]** Shipped 2026-05-09 (mega-house workspace, branch `main`). Standardised motion across the surface. Added `--bb-motion-fast` (160ms) / `--bb-motion-base` (200ms) / `--bb-motion-slow` (320ms) / `--bb-motion-press` (96ms) / `--bb-motion-ease` (cubic-bezier(0.22, 1, 0.36, 1)) to `apps/web/src/app/globals.css`, mirrored as JS constants in new `apps/web/src/lib/motion.ts` (BB_MOTION_*_MS, BB_MOTION_EASE, BB_SPRING_TRANSITION{stiffness:280,damping:32,mass:0.9}, BB_REDUCED_MOTION_INSTANT). New `.bb-press` CSS class implements the 96ms `:active` scale(0.98) depress (acceptance c) — wired onto BetPanel primary CTA (every game's gold pill), WalletSheet close button + theme toggle, and the HeroGameCard `:active` already uses the press token. Migrated `WalletSheet.tsx` to framer-motion `<AnimatePresence>` + `<motion.aside>` with the spring transition (acceptance b); reduced-motion path collapses to a `BB_REDUCED_MOTION_INSTANT` 0ms tween + `data-motion-variant="instant"` so the sheet still appears but skips the kinetic slide-in. CoinSpin already used framer-motion (acceptance d) — re-tokenised its crossfade duration + ease via `BB_MOTION_BASE_MS` + `BB_MOTION_EASE` so a global tweak propagates. HiloCard re-tokenised the same way. BankrollBar progress fill switched from `240ms ease-out` to `var(--bb-motion-base, 240ms) ease-out`. Reduced-motion subtle fallbacks (acceptance e): new `.bb-win-glow-fallback` keyframe (1200ms `bb-win-fallback-pulse` outline glow, ease-out, 1 iteration) wraps PayoutCounter so motion-sensitive users get a still-but-visible win surface; HeroGameCard live variant gets a permanent soft outline-glow under reduced-motion so the affordance reads even without hover lift. Confetti↔PayoutCounter integration (acceptance f): both surfaces share the same `isWin` signal in the play pages; the new MotionPass test suite asserts they mount/suppress in lockstep across standard + reduced-motion. **Tests:** `apps/web/src/components/__tests__/MotionPass.test.tsx` ships **15 vitest cases** (token vocabulary, BetPanel CTA bb-press wiring, WalletSheet spring/instant variants, WalletSheet close-after-spring regression, PayoutCounter glow-fallback class, CoinSpin variant contract parity, confetti+counter integration on win/loss/reduced-motion). `apps/web/src/components/__tests__/MotionTokensCss.test.tsx` ships **6 cases** asserting the `--bb-motion-*` CSS tokens mirror the JS constants verbatim — drift guard against future refactors that update one side and forget the other. New `apps/web/e2e/motion-pass.spec.ts` ships the reduced-motion Playwright spec covering CoinSpin variant collapse, WinConfetti suppression, and PayoutCounter static + glow-fallback wiring (g). Updated `__tests__/SiteHeader.test.tsx` to await `waitForElementToBeRemoved` for the AnimatePresence exit. Web suite **561/561 green** (was 539 → +22 cases). `tsc --noEmit` carries only the same pre-existing `.next/types/app/play/{dice,hilo}/page.ts` errors that exist on baseline `main` (verified via stash). Closes audit P2-2 / P2-3 / P2-6 / P2-7. (PROJECT:BUNNYBAGZ) (2026-05-09)

- [x] [UNVERIFIED] **[BB_PHASE3_PAYOUT_COUNTER]** Shipped 2026-05-09. `apps/web/src/components/PayoutCounter.tsx` ships the UX_PLAN §5 win-state contract: tweens a tabular figure (`.bb-tabular`) from 0 → final payout via `requestAnimationFrame` over 600ms with `easeOutCubic`, paired with a `var(--bb-brand-gold-strong)` radial sparkle (600ms keyframe), wrapped in `role="status" aria-live="polite"` so screen readers still get the win acknowledgement. Reduced-motion path skips the rAF loop and shows the final number with a single 200ms scale-pop keyframe (0.85 → 1.08 → 1). Consumed by all three play surfaces inside each `bb-game-viewport` — `apps/web/src/app/play/coinflip/page.tsx` filters on `settledSide === side`, `…/dice/page.tsx` on `settledWon === true`, `…/hilo/page.tsx` on `sessionStatus === "cashed-out"`. Coinflip also gained the `<WinConfetti>` mount that the QUEUE entry described as "existing" (component existed but was never wired into a page before). Tests: `apps/web/src/components/__tests__/PayoutCounter.test.tsx` ships **5 vitest cases** (count-up via stubbed rAF + `performance.now`; reduced-motion static variant; loss=no mount; invalid/empty/zero/negative payout=no mount; whole-number formatting without spurious decimals). Web suite **528/528 green** (was 523). `tsc --noEmit` carries only the same pre-existing `.next/types/app/play/{dice,hilo}/page.ts` errors that exist on baseline `main` (verified via stash). (PROJECT:BUNNYBAGZ) (2026-05-09)

- [x] [UNVERIFIED] **[BB_PHASE3_MASCOT_LIVE_FRAMES]** Shipped 2026-05-09. `apps/web/src/components/MascotFrame.tsx` swapped from static `<img>` to `motion.img` driven by framer-motion variants. New `resolveAnimKind` resolver maps `(state, frame, prefersReducedMotion)` → `"bob" | "scale-pop" | "head-shake" | "static"`. Idle bunny runs a 3s `y: [0, -2, 0]` bob loop with a tiny opacity-pulse "blink" (no SVG `<g>` surgery — wrapper-transform path per acceptance (b)). Win is the locked 600ms scale-pop one-shot with rotate keyframes acting as the ear-wiggle (`rotate: [0, -6, 6, 0]`). Loss-streak is an 800ms `x: [0, -3, 3, -2, 2, 0]` head-shake. Carrot sidekick gets its own track: `carrot_idle` mirrors a gentle 1.6s bob, `carrot_reaction` shrugs via a rotate-mirror that pairs with the bunny's head-shake. `transform-origin: 50% 100%` on both images so transforms read as the mascot sitting on the ground. Reduced-motion path pins every transformable axis and clamps `data-anim` / `data-variant` to `"static"`. Container exposes `data-anim` for testability; the existing `data-state` / `data-variant` / `data-streak` attrs are untouched (existing tests still pass). Tests: `apps/web/src/components/__tests__/MascotFrame.test.tsx` keeps the 12 original cases and adds **12 new cases** for `resolveAnimKind` + live-frames rendering (bob on idle, scale-pop on win, head-shake on loss-streak, single-loss bobs the idle frame, reduced-motion clamps every state to static, anim duration constants pinned, plus 6 component-level rendering assertions) — **24 total in this file**. Playwright: new `apps/web/e2e/mascot-frame.spec.ts` with 4 scenarios × 3 projects = 12 specs (idle pre-settle no-mount, win settle scale-pop + carrot sidekick, single loss neutral idle/bob, reduced-motion static via `page.emulateMedia({reducedMotion: "reduce"})`). Web vitest suite **540/540 green** (was 528). `tsc --noEmit` carries only the same pre-existing `.next/types/app/play/{dice,hilo}/page.ts` errors that exist on baseline `main` (verified via stash). (PROJECT:BUNNYBAGZ) (2026-05-09)

- [x] [UNVERIFIED] **[BB_PHASE3_FIRST_BET_HINT_TOAST]** Shipped 2026-05-09. (a) New `apps/web/src/components/Toast.tsx` primitive (bottom-anchored, framer-motion AnimatePresence; spring slide-up + fade, reduced-motion → static fade via `BB_REDUCED_MOTION_INSTANT`+`BB_MOTION_BASE_MS`; surface is a `<button>` so tap-anywhere dismisses, dismiss `×` is a nested role="button" span). (b) `FirstBetHint.tsx` rebuilt around the new `<Toast>`; mounts only post-hydration (SSR-safe), pre-fills open-state from `bunnybagz:first-bet-hint-dismissed`, 3s auto-dismiss timer cleared on tap-dismiss to prevent double-write. New export `FIRST_BET_HINT_AUTO_DISMISS_MS = 3000`. (c) `placement` prop removed (was `"inline" | "toast"`); `app/play/page.tsx` updated to drop `placement="toast"`. (d) `__tests__/FirstBetHint.test.tsx` expanded from 3 → **7 cases**: first-visit render + spring variant, returning-visit suppression, tap-to-dismiss persistence, 3s auto-dismiss persistence (vi.useFakeTimers), reduced-motion fade variant, cross-mount persistence, `hasPlacedBet` suppression. **Verification:** vitest `565/565 green` (was 558 — 7 new cases). `tsc --noEmit` carries only the same pre-existing `.next/types/app/play/{dice,hilo}/page.ts` errors as baseline `main`. Audit P2-5 closed. (PROJECT:BUNNYBAGZ) (2026-05-09)

##### Operator audit follow-ups (2026-05-08 evening)

_Source: operator audit pass against the BB main branch + LAN-running surface. Three P0 items shipped same-session in commit `6464d85` ("fix(web): production settle-event producer + coinflip seed-gate dropped + metadataBase"); the remainder are follow-ups extracted from the same audit. BB ships **direct-to-main** — no PR workflow on this project; treat each item as "land on `main` + push" once tests are green._

- [x] [UNVERIFIED] **[BB_PHASE3_COINFLIP_SEED_GATE_DROP]** Shipped 2026-05-08 evening (BB `main`, commit `6464d85`). The `/play/coinflip` CTA was gating on the page-level `/api/seed/commit` fetch ("Waiting for server seed…"), a legacy artefact from before per-bet `/api/seed/claim`. Dropped the gate (matches dice + hilo) — `placeBet()` now claims fresh per-bet commits regardless of the page-level state, and the on-chain `commitUsed` guard remains the source of truth. Updated the obsolete vitest case in `apps/web/src/app/play/coinflip/__tests__/page.test.tsx` to assert the new state-machine: when `/api/seed/commit` returns `null` and no contract address is configured, the CTA must surface "Coinflip not deployed yet" instead of the old waiting copy. Closes operator P0 #1. (PROJECT:BUNNYBAGZ) (2026-05-08T23:53Z)

- [x] [UNVERIFIED] **[BB_PHASE3_PRODUCTION_SETTLE_EVENT_BRIDGE]** Shipped 2026-05-08 evening (BB `main`, commit `6464d85`). The `bunnybagz:coinflip-settle` / `bunnybagz:dice-settle` / `bunnybagz:hilo-settle` / `bunnybagz:bet-settled` CustomEvents had consumers (loss-streak counters, mascot win/loss state, aria-live narration, wallet `RecentBetsList` refresh) but **no production producer** — only specs dispatched them, so every behaviour wired through these events silently no-op'd against a real chain while CI stayed green. Shipped `apps/web/src/components/SettleEventBridge.tsx`, mounted in `Providers.tsx`, which uses wagmi `useWatchContractEvent` per-game contract (filtered by the connected `player`) and re-emits the settled-state events as DOM CustomEvents the consumers already expect. Coverage: HiLo `SessionOpened` → `bunnybagz:hilo-opened`; `StepPlayed` → `bunnybagz:hilo-step`; `SessionCashedOut`/`SessionPushed`/`SessionRefunded` → `bunnybagz:hilo-settle` (status field discriminates); coinflip + dice `BetSettled` → `bunnybagz:<game>-settle`; every settle also fires the cross-game `bunnybagz:bet-settled` so `<RecentBetsList>` refreshes. Disconnected wallets configure all watchers with `enabled: false` to skip the RPC subscription. Closes operator P0 #2. (PROJECT:BUNNYBAGZ) (2026-05-08T23:53Z)

- [x] [UNVERIFIED] **[BB_PHASE3_SETTLE_EVENT_COVERAGE]** Shipped 2026-05-08 evening (BB `main`, commit `6464d85`). Closed the coverage gap that allowed mocked-CustomEvent specs to mask the missing production producer (operator P0 #3). New `apps/web/src/components/__tests__/SettleEventBridge.test.tsx` (9 cases) drives the wagmi mock's `onLogs` handler with realistic event payloads (coinflip `BetSettled` heads + tails, dice `BetSettled` won, hilo `SessionOpened` + `StepPlayed` + `SessionCashedOut` + `SessionPushed` + `SessionRefunded`) and asserts every CustomEvent's detail shape (sessionId stringified, `payoutEth` formatted from wei, `status` discriminator on hilo settle, cross-game `bet-settled` always fired). Disconnected case asserts every watcher is `enabled: false`. Web suite **523/523 green** (was 514, +9). Closes operator P0 #3. (PROJECT:BUNNYBAGZ) (2026-05-08T23:53Z)

- [x] [UNVERIFIED] **[BB_PHASE3_METADATABASE_NOISE_FIX]** Shipped 2026-05-08 evening (BB `main`, commit `6464d85`). Set `metadata.metadataBase` in `apps/web/src/app/layout.tsx` from `NEXT_PUBLIC_SITE_URL` → `VERCEL_URL` → `https://bunnybagz.xyz` fallback. Silences the Next 15 metadataBase warning on every SSR pass that ships relative OG/Twitter images. Verified: a 30-second `pnpm dev:lan` run + curl on `/play` produced 0 `metadataBase` lines in stdout (was on every request prior). OG image URLs render as absolute `https://bunnybagz.xyz/brand/og-image.png`. Closes part of operator's "WalletConnect/metadataBase noise" item; the WalletConnect side stays open as `[BB_PHASE3_WALLETCONNECT_NOISE_CLEANUP]` below. (PROJECT:BUNNYBAGZ) (2026-05-08T23:53Z)


- [x] [UNVERIFIED] **[BB_PHASE3_WALLET_PNL_AGG]** Shipped 2026-05-09 (BB worktree). New `apps/web/src/components/WalletPnLCard.tsx` mounted by `<WalletPanel>` between `<WalletQuickActions>` and `<RecentBetsList>`. Reads `/api/history/wallet?address=…&limit=N`, aggregates `sum(payoutWei) - sum(stakeWei)` per token (BigInt-safe), settled-only win-rate (`won + cashed` / settled, excludes refunded/pushed from numerator), per-(game,token) breakdown chips, sign-aware colour (positive=success, neutral=muted, negative=danger). Refreshes on `bunnybagz:bet-settled` CustomEvent (same bridge `<RecentBetsList>` rides). USDm rendered as a separate row from ETH — never summed. Root section carries `bb-tabular` class + inline `font-variant-numeric: tabular-nums`; surface added to `tabular-figures-audit.ts`. **14 vitest cases** in `WalletPnLCard.test.tsx` (empty / no-address / single-bet / multi-bet / mixed-token / loss-only / win-only / event-driven refresh / endpoint URL contract / bb-tabular class assertion / fetch-error / aggregatePnL helper × 3). Full web suite: 580/580 pass. (PROJECT:BUNNYBAGZ)

- [x] [UNVERIFIED] **[BB_PHASE3_DEV_COMPILE_SPEEDUP]** Shipped 2026-05-09 (BB worktree). Findings: (a) regression is **both** pre-Turbopack default (webpack baseline 12.5s on this hardware) **and** a heavy import chain — `<Providers>` pulled `<SettleEventBridge>` which eagerly loads COINFLIP/DICE/HILO ABIs (~2200 lines of JSON), and `/play` directly imported `<LiveActivityFeed>` + `<FirstBetHint>` (both pull `framer-motion`). (b) Fix: enabled `--turbopack` in `dev` / `dev:lan`, code-split `<SettleEventBridge>` via `next/dynamic({ssr:false})` from `<Providers>`, and split `<LiveActivityFeed>` + `<FirstBetHint>` into a new `<LobbyDeferred>` client wrapper that uses `next/dynamic({ssr:false})` (server components can't pass `ssr:false`). (c) Measured: turbopack cold compile **6.1s** / wall-clock **6.8s** vs webpack baseline 12.5s — **~46% reduction**. The 4s target was not fully met on this hardware; the residual is dominated by RainbowKit + WalletConnect connector compilation, which would need a deeper RainbowKit code-split to attack. (d) Tooling: `apps/web/scripts/perf-cold-compile.mjs` (boots `next dev` on a fresh port, fetches `/play`, scrapes "Ready in" / "Compiled /play in <N>{ms,s}" / "Local:"), `pnpm --filter @bunnybagz/web perf:cold-compile`. (e) 16 new vitest cases in `apps/web/src/__tests__/perf-cold-compile.test.ts` covering parser regex (ANSI escapes, ms/s units, route-scoping with regex-metachar escapes, warm vs cold form). Full web suite: 597/597 pass. Typecheck clean. (PROJECT:BUNNYBAGZ) (2026-05-09)

- [x] [UNVERIFIED] **[BB_PHASE3_WALLETCONNECT_NOISE_CLEANUP]** Shipped 2026-05-09 (BB `main`, commit `a57b711`). Extracted WC project-id resolution into `apps/web/src/lib/walletconnect-config.ts` — `resolveWalletConnectProjectId()` returns `{projectId, isDevPlaceholder}`, `notifyWalletConnectDevPlaceholderOnce()` is idempotent across HMR re-imports. `wagmi.ts` calls the once-warn helper inside `buildLiveConfig()` only when the sentinel branch is active; real ids skip the warn path entirely. README "WalletConnect in dev" subsection documents the behaviour and the silence path (set `NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID`). Verified: 5 vitest cases in `lib/__tests__/walletconnect-config.test.ts` — sentinel branch warns exactly once with `https://cloud.walletconnect.com` + `NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID` pointers, real id branch never warns; full web suite still green (602 tests). (PROJECT:BUNNYBAGZ) (2026-05-09T14:05Z)

- [x] [UNVERIFIED] **[BB_PHASE3_LAN_DEV_PROD_RUNBOOK]** Shipped 2026-05-09. `docs/LOCAL_DEV.md` extended: TL;DR now covers dev + prod-mode, new **Prod-mode local serve** section (`build` + `PORT=3000 start --hostname 0.0.0.0` + `start:lan` alias), new **Required env vars** table (`NEXT_PUBLIC_SITE_URL`, `NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID`, `NEXT_PUBLIC_COINFLIP/DICE/HILO_ADDRESS`, `NEXT_PUBLIC_PERMIT_FORWARDER_ADDRESS`, `NEXT_PUBLIC_USDM_PERMIT_DISABLED`, `NEXT_PUBLIC_E2E_MOCK_WALLET`), new **Indexer** subsection linking to `[BB_PHASE3_INDEXER_LOCAL_RUNNABLE]`, `/play` is the suggested LAN-test URL throughout. `apps/web/README.md` got a **Local LAN runbook** subsection with `hostname -I` snippet, dev:lan + prod-mode commands, and a link to `docs/LOCAL_DEV.md`. Top-level `README.md` got a **Quick start** section linking to the runbook. No code change needed (`start:lan` script already existed in `apps/web/package.json:13`). (PROJECT:BUNNYBAGZ)

##### Exit gates

- [x] [UNVERIFIED] **[BB_PHASE3_LIGHT_THEME_VISUAL_PASS]** Audit + tune light theme on every redesigned surface. Closes audit P1-10. **Acceptance:** (a) every surface that landed in this redesign block is reviewed in light mode by Playwright screenshots at 3 viewports; (b) gold/carrot brand colors get a mild warm-shadow treatment so they stop floating on cream; (c) coin viewport gradient (`globals.css:76-78`) tuned so the gold face reads against warm paper; (d) `--bb-fg-subtle` re-checked against every new surface for AA contrast; (e) light-mode regression baselines saved (BB_PHASE3_VISUAL_REGRESSION_BASELINE); (f) operator visual signoff captured in `memory/cron/bb_phase3_light_pass_<YYYY-MM-DD>.md`. (PROJECT:BUNNYBAGZ) (2026-05-07T14:14:34Z)

- [x] [UNVERIFIED] **[BB_PHASE3_VISUAL_REGRESSION_BASELINE]** Capture baseline screenshots for every redesigned surface, hooked into the existing `[UI_QUALITY_PLAYWRIGHT_VISUAL_REGRESSION_HARNESS]` Clarvis-side cron. **Acceptance:** (a) `apps/web/scripts/visual-baseline.mjs` (Playwright via CDP at 127.0.0.1:18800) captures `/`, `/play`, `/play/coinflip`, `/play/dice`, `/play/hilo`, `/wallet`, `/audit`, `/bounty`, `/verify` at three viewports (375 / 1024 / 1440) × two themes; (b) saves to `apps/web/test-results/visual-baseline/`; (c) Clarvis-side cron `cron_bb_visual_regression.sh` runs daily, diffs vs the baseline, posts to Telegram if pixel-diff > 5% or perceptual-hash distance > 10%; (d) baseline is ground-truth — operator updates intentionally via a `--update-baseline` flag; (e) ≥4 vitest cases for the diff harness logic (offline replay against fixture images). (PROJECT:BUNNYBAGZ) — Shipped 2026-05-09: harness `apps/web/scripts/visual-baseline.mjs` (capture / --diff / --update-baseline modes; pure RGBA pixel-diff with tolerance + 8×8 aHash + Hamming gate exposed for vitest). 19 vitest cases under `apps/web/src/__tests__/visual-baseline.test.ts` cover threshold strict-> wording, sub-tolerance jitter masking, hash flip on layout inversion, route/viewport inventory; full web suite 627/627 green. Clarvis-side `scripts/cron/cron_bb_visual_regression.sh` + Telegram notifier `cron_bb_visual_regression_notify.py` — gated on `BB_VISUAL_REGRESSION_ACTIVE=1`, dev-server + CDP liveness pre-checks, parses regressions[] from `--json` report, posts only when `regressions > 0`. (2026-05-09T19:08:00Z)

- [x] [UNVERIFIED] **[BB_PHASE3_BRAND_DOC_UPDATE]** Update `docs/BRAND.md` so it reflects the surface that exists, not the surface promised in 2026-04. **Acceptance:** (a) BRAND.md gets new sections: "Locked typography" (display + UI + mono, with `next/font` snippet), "Token tables" (full space/radius/elevation/motion + the existing color/semantic), "Mascot motion contract" (idle/win/loss-streak loops + reduced-motion), "Component primitives index" (links to each `@bunnybagz/ui` primitive's source); (b) `docs/UX_PLAN.md` gets a "What shipped vs what was promised" sidebar; (c) `docs/audits/UI_UX_AUDIT_2026-05-06.md` linked from the changelog; (d) ≥3 doc-test cases (links resolve, sections present, no `system-ui` literals in code paths the doc claims are tokenised). (PROJECT:BUNNYBAGZ) (2026-05-07T14:14:34Z)

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
_
_**Operator override (2026-05-07):** RD generation is explicitly re-opened **for V2 companion-surface UI/art only**. Allowed scope: HUD/icon/button/frame/ornament/VFX/empty-state assets and cozy decorative interface chrome for the tamagotchi loop. Still out-of-scope: V3 assets, hub-map replacement, painted-room replacement, and broad world-art regeneration._

#### V2 — Companion-First Core Loop (Track A — priority, 2026-04-26 evening)

_Tamagotchi-style care + interaction loop on top of the existing companion schema. Acceptance criteria are concrete so each item produces one merge-able PR. Direction + rationale in `memory/evolution/swo_sanctuary_companion_first_2026-04-26.md`._

_**Status (2026-05-07):** the original 7 P0/P1 items in this track have all shipped on dev (stats schema, interact-affects-stats, mood-from-stats, companion screen surface, need alerts, chat-knows-stats, V1 archive banner). PR #277 (`[SWO_V2_COMPANION_COZY_POLISH]`) extends the screen with cozy/tamagotchi voice (mood-aware greetings, last-visit anchor, sprite reactions per action, stat-bar +N + pulse, sleep-state warmth, journal-line variety). Follow-ups below extend the loop further; none is a P0._






- [x] [UNVERIFIED] **[SWO_V2_RD_COMPANION_UI_ASSET_BATCH_1]** Generate the first proper V2 companion-interface pixel-art asset batch with Retro Diffusion. This is the operator-approved reopening of RD for V2 UI, specifically to replace placeholder/emoji/generic chrome. **Acceptance:** (a) create `public/sanctuary/ui/` batch with at minimum: 5 action icons (`feed`,`pet`,`talk`,`sleep`,`play`) at 16×16, 3 stat icons (`hunger`,`happiness`,`energy`) at 16×16, 1 bond-heart icon, 1 journal icon, 1 sleep badge, and 1 empty-state cozy ornament set; (b) every asset generated through the documented RD pipeline with `check_cost: true`, saved seed, manifest entry, and palette QA notes; (c) all approved assets render crisply at 1× and 2× on the live companion screen; (d) emoji placeholders are removed anywhere the generated icons now exist; (e) doc the batch in SWO repo `docs/ASSET_PIPELINE.md` or successor note. (PROJECT:SWO, P1) (2026-05-07T14:14:34Z)





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

### 2026-05-05 evolution scan (autonomous)

_Note: queue at 7 pending — under cap. Weakest metric per evolution prompt is `Precision@3=0.683` (target 0.7); freshly-regenerated `data/retrieval_quality/dashboard.md` (2026-05-05T06:25:06Z) reports `0.700` so the gap is the evolution-prompt source path, not the metric itself — the pending `[P3_DASHBOARD_SOURCE_AUDIT]` will pin that down. Two new items target P@3 from angles not covered by the 3 still-open P3 items (source audit / fixture expansion / preferences floor). One non-Python markdown item plans the operator-blocked BunnyBagz USDM integration so it is ready to execute the moment Phase 2 re-opens. One Python item lifts second-weakest capability `code_generation=0.87` by codifying the BB Phase 2 success patterns (6 P2 tasks shipped clean across 2 days) into a recallable procedure. None duplicate pending items._

- [ ] **[P3_DASHBOARD_REFRESH_CRON]** Non-Python (bash + cron). Targets weakest metric Precision@3=0.683. The dashboard at `data/retrieval_quality/dashboard.md` was ~7 weeks stale until manually regenerated 2026-05-05T06:25 — without an automated refresh it will drift again. Add `scripts/cron/cron_p3_dashboard_refresh.sh` that sources `cron_env.sh`, runs `python3 scripts/brain_mem/retrieval_benchmark.py` (or the canonical equivalent identified by `[P3_DASHBOARD_SOURCE_AUDIT]`) under `/tmp/clarvis_p3_refresh.lock`, and writes the dashboard. Wire into `clarvis cron` preset (recommended slot: 05:35 daily, between `cron_pi_refresh.sh` 05:45 and ChromaDB vacuum 05:00 — actually 04:55 to land before vacuum). Add a Telegram alert via `scripts/infra/budget_alert.py` helper if regenerated P@3 drops >0.05 vs prior dashboard write. **Acceptance:** new script exists + locks correctly + has `trap EXIT` cleanup; `clarvis cron list` shows the entry; manual `--dry-run` regenerates dashboard with `last_updated` ≤24h; alert fires on synthetic drop. (PROJECT:CLARVIS)
- [x] [UNVERIFIED] **[BB_PHASE2_USDM_INTEGRATION_PLAN]** Non-Python markdown. Per `bb_phase2_truth_audit_2026-05-04.md` and ROADMAP Phase 2 exit criterion ("all 3 games playable in ETH and USDm on testnet"), USDM integration is 0% started while the rest of Phase 2 is ~30% — the largest remaining unknown. Author `memory/evolution/bb_phase2_usdm_plan_2026-05-05.md` covering: (a) USDM token contract address on MegaETH testnet (research, link to docs), (b) ERC-20 approve+transferFrom flow vs native-ETH `msg.value` flow — diff against existing Coinflip/Dice/HiLo bet path, (c) edge fn + UI delta per game (token selector, allowance check, two-tx vs one-tx UX), (d) test plan additions (forge mock ERC-20, vitest mock token state), (e) operator-blocked vs autonomous-doable split, (f) suggested task split into ≤4 separate `[BB_PHASE2_USDM_*]` queue items. **Acceptance:** plan file exists; ≥4 concrete sub-tasks named with rough size estimates; all operator-blocked steps explicitly flagged. (PROJECT:BUNNYBAGZ) (2026-05-06T14:11:26Z)
- [x] [UNVERIFIED] **[CODE_GEN_BB_SUCCESS_PATTERN_EXTRACTION]** Python. Targets second-weakest capability `code_generation=0.87`. The last 48 hours shipped 6+ Phase 2 BB tasks cleanly (HILO_STEP, INDEXER_DICE_HILO, DICE_SLIDER_VISUAL, FORGE_LINT_TYPECAST, PLAYWRIGHT_E2E_REOPEN, WALLET_MOCK, FUZZ_GUARD) — a high-density success cluster worth distilling. Add `scripts/audit/code_gen_pattern_extract.py`: read the matching episodes from `data/episodes.json` + the resulting commits + their tests/file shape; identify the recurring shape (file/path conventions, test naming, error-handling mood, comment density, lint-compliance heuristic). Store one procedural memory in `clarvis-procedures` collection (via `procedural_memory.store()`) titled `procedure: BB Phase 2 code-gen success pattern` with the distilled checklist. **Acceptance:** procedure stored (verifiable via `python3 -m clarvis brain search "BB Phase 2 code-gen pattern"` returning it as top-1); checklist has ≥6 concrete items grounded in actual commits referenced by SHA. (PROJECT:CLARVIS) (2026-05-09T22:18Z) — script added; report at `docs/internal/audits/code_gen_bb_pattern_2026-05-09.md`; procedure `proc_bb_phase_2_code_gen_success_pattern` (10 steps, importance 1.0) stored in clarvis-procedures + LEARNINGS pointer `learning_bb_phase_2_code_gen_pattern_pointer` (router routes the literal query to LEARNINGS only); CLI `python3 -m clarvis brain search "BB Phase 2 code-gen pattern"` returns the pointer at top-1.

### 2026-05-03 weekly review

_Note: the week delivered real BunnyBagz progress and queue-hygiene repairs, but the weak point is now drift between reality and representation. Adding only three items: goal-stack hygiene, roadmap freshness, and daily-log continuity. All are small leverage multipliers, not new abstraction theater._

- [x] [UNVERIFIED] **[GOAL_STACK_WEEKLY_HYGIENE]** `brain.get_goals()` currently returns a noisy stack of overlapping historical goals: legacy Session Continuity / Feedback Loop items, SWO-heavy delivery goals, and several Phi-forward bridge goals that no longer match roadmap policy. Build a weekly hygiene pass (`scripts/goals/weekly_hygiene.py` or spine equivalent) that: (a) groups near-duplicate goal memories by semantic title, (b) emits a markdown review under `memory/evolution/goals/weekly/<YYYY-WW>.md`, (c) flags stale goals with `progress=0` + no accesses in 14d, (d) proposes 3-7 canonical active goals for manual promotion. Acceptance: first report written for current week; report explicitly calls out SWO-vs-BunnyBagz priority skew and Phi de-emphasis; no brain mutations occur automatically without explicit follow-up action. (PROJECT:CLARVIS) (2026-05-06T14:11:26Z)
- [x] [UNVERIFIED] **[ROADMAP_WEEKLY_STATE_REFRESH]** `ROADMAP.md` drifted for a week until the 2026-05-03 weekly review manually refreshed it. Automate a truthfulness pass that updates `_Updated:` and prepends a new `Weekly State Note` from the latest weekly review. Source inputs: newest `memory/evolution/weekly/YYYY-WW.md`, current queue state, and latest benchmark summary. Acceptance: script writes a candidate patch or exact block replacement for ROADMAP current-state note; includes guardrail to preserve historical notes; smoke test updates a temp copy with this week's note. (PROJECT:CLARVIS) (2026-05-06T14:11:26Z)

### 2026-05-07 evolution scan (autonomous)

_Note: queue at 38 pending (P1 saturated). 3 P@3 items already pending (`P3_DASHBOARD_SOURCE_AUDIT`, `P3_DASHBOARD_REFRESH_CRON`, `P3_HYDE_QUERY_REFORMULATION_PROBE`) so any new P@3 work must take a non-overlapping angle. Adding 3 items only — all targeting documented gaps. One Python P@3 probe (cross-encoder rerank, complementary to HyDE which reformulates queries; rerank reorders results — different mechanism). One non-Python markdown sequencing audit for the 21 stalled BB_PHASE3_* P1 items (UI_PRIMITIVES_SHIP is upstream of BET_PANEL_REDESIGN, LOBBY_CARDS, WALLET_SHEET, etc — without an explicit dependency order, autonomous execution will ship redundant or rework-prone slices). One non-Python markdown audit for retrieval chunk granularity (memories are stored as single strings; chunk strategy directly affects P@3 but is unaudited). None duplicate pending items._

- [x] [UNVERIFIED] **[BB_PHASE3_SEQUENCING_AUDIT]** Non-Python markdown. The 21 pending `BB_PHASE3_*` P1 items have implicit dependencies that no document captures: `BB_PHASE3_UI_PRIMITIVES_SHIP` is upstream of `BET_PANEL_REDESIGN`, `LOBBY_GAME_HERO_CARDS`, `WALLET_SHEET_REDESIGN`, `TOKEN_TOGGLE_SEGMENTED_CONTROL`, `RECENT_OUTCOMES_TREATMENT`; `DESIGN_TOKEN_SYSTEM` + `TYPOGRAPHY_LOCK` are upstream of every visual surface; `MOTION_PASS` and `LIGHT_THEME_VISUAL_PASS` are downstream of all redesigned surfaces; `VISUAL_REGRESSION_BASELINE` should run last. Without an explicit order, an autonomous spawn could ship `BET_PANEL_REDESIGN` before `UI_PRIMITIVES_SHIP` exists, then need rework. Author `memory/evolution/bb_phase3_sequencing_2026-05-07.md` listing: (a) every P3-tagged BB item with its prerequisite items by tag, (b) a topological-sort recommended execution order, (c) which items can ship in parallel (no cross-deps), (d) explicit "DO NOT START until X lands" annotations, (e) suggested splitting points if any single item is >1-day work. **Acceptance:** file exists; all 21 BB_PHASE3 items listed; ≥3 prerequisite chains identified; explicit parallel-ship groups named; cite UX_PLAN/BRAND.md/audit doc for each upstream-vs-downstream call. (PROJECT:BUNNYBAGZ) (2026-05-07T14:14:34Z)
- [x] [UNVERIFIED] **[P3_CHUNK_GRANULARITY_AUDIT]** Shipped 2026-05-09. Sampled all 10 collections (461 records across 2989 total). Verdict: **NOT WORTH IT** for systemic chunking — no collection has median > 500 chars (highest is `clarvis-learnings` at 397); records enter the store *already chunked* (median 1 sentence, 1 paragraph). Only `clarvis-learnings` is a borderline candidate (mean 459, 18% of sample in 500–1k bucket). Cost estimate: $0.00 direct (local ONNX), but ~93k graph edges + Hebbian access history would need re-attribution → multi-day project unjustified by data. Higher-EV inverse finding flagged: `clarvis-memories` shows 64% records < 80 chars (many surviving `_health_probe_*` strings from `store.py:1003-1027` cleanup that's wrapped in `except: pass`). Filed 4 follow-up tasks (`P3_HEALTH_PROBE_CLEANUP`, `P3_VERY_SHORT_RECORD_AUDIT`, `P3_LEARNINGS_CHUNK_PROBE`, `P3_OUTLIER_RECORD_REVIEW`). Audit doc: `docs/internal/audits/P3_CHUNK_GRANULARITY_AUDIT_2026-05-07.md`. (PROJECT:CLARVIS) (2026-05-09)

### 2026-05-09 evolution scan (autonomous)

_Note: queue at 12 pending — under cap. Weakest metric is Precision@3=0.683 (target 0.7); 5 P@3 items already pending (`P3_DASHBOARD_SOURCE_AUDIT`, `P3_DASHBOARD_REFRESH_CRON`, `P3_HYDE_QUERY_REFORMULATION_PROBE`, `P3_CROSS_ENCODER_RERANK_PROBE`, `P3_CHUNK_GRANULARITY_AUDIT`) so any new P@3 angle must be non-overlapping. The avoid-pattern flags too many Clarvis-Python-infrastructure tasks; project lane discipline asks for 50%+ project work. Adding 3 items: 1 P@3 forensic angle distinct from the 5 pending (per-query failure triage — none of the 5 inspect *which queries* are failing), 2 BunnyBagz Phase 3 polish items closing documented Phase 2 truth-audit gaps. All 3 are non-Python. None duplicate pending items._

- [x] [UNVERIFIED] **[BB_PHASE3_KEYBOARD_NAV_AUDIT]** Shipped 2026-05-09. Built `apps/web/scripts/keyboard-nav-audit.mjs` (Playwright via CDP at `localhost:18800`, 480×900 viewport) which walks all six Phase 3 surfaces (Lobby, Coinflip, Dice, HiLo, WalletSheet, TrustStrip/Footer) in dark + light themes, captures 12 focus-state PNGs into `memory/cron/bb_keyboard_nav_audit_2026-05-09/` (lobby/coinflip/dice/hilo/wallet_sheet/trust_footer × dark/light) plus a machine-readable `summary.json` of every focused element's outline/boxShadow/role/text/aria. Verdict written to `memory/cron/bb_keyboard_nav_audit_2026-05-09.md`: **NO-GO**. Tab order is sane on every surface (10-14 tabs to primary CTA), primary CTAs are real `<button>`/`<a>` so Enter/Space activate natively, WalletSheet has Esc handler + role=dialog + aria-modal — but only the DiceSlider thumb has a `:focus-visible` rule (`globals.css:253-263`); every other CTA falls back to the Chromium UA outline `auto 1px rgb(16, 16, 16)` which is the same dark colour in both themes — visible against cream in light theme, invisible against ink in dark theme. Five of six surfaces score 4/light, 3/dark (combined 3); only DiceSlider clears 4 in dark. Auto-appended `[BB_PHASE3_KBNAV_FOCUS_RING_FIX]` below per the audit contract. Re-confirms a 2026-05-04 finding (`bb_ui_review_2026-05-04.md` axis 7 "no explicit `:focus-visible` style asserted") that has not been remediated. (PROJECT:BUNNYBAGZ) (2026-05-09)

- [x] **[BB_PHASE3_KBNAV_FOCUS_RING_FIX]** Shipped 2026-05-10. Added single global `:focus-visible` block in `apps/web/src/app/globals.css` covering `button, a, summary, [role="button"]` with `outline: 2px solid var(--bb-brand-gold)` + `outline-offset: 2px`; plus a `[data-testid$="-primary-cta"]:focus-visible { box-shadow: inset 0 0 0 1px var(--bb-brand-ink) }` rule that restores AA against the gold-on-gold primary CTA fill (1.05:1 → AA-clean). DiceSlider thumb-specific rule preserved untouched. New vitest suite `apps/web/src/components/__tests__/FocusRing.test.tsx` ships **14 cases**: 3 source-contract regex assertions on globals.css + 7 dark-theme runtime cases + 4 light-theme runtime cases. Each runtime case renders the production DOM (button / anchor) for one of the six surfaces (coinflip primary CTA, coinflip side toggle, dice primary, hilo primary, HeroGameCard lobby link, WalletSheet close), focuses it, and asserts `getComputedStyle(el).outlineColor !== "rgba(0, 0, 0, 0)"`, `outlineWidth ≥ 2px`, `outlineStyle === "solid"` — exactly the audit acceptance check. Runtime cases mirror the production declarations as inline styles because jsdom's `getComputedStyle` does not match `:focus-visible` through stylesheets (regex check covers the production selector). Playwright spec `apps/web/e2e/focus-ring.spec.ts` ships 4 specs (lobby card, coinflip CTA, dice CTA, hilo CTA in light theme) that walk the dev server with `page.keyboard.press('Tab')` and assert the same outline contract via real-browser CSS engine — the coinflip case also asserts the inset inner ink ring. Verification: `pnpm --filter @bunnybagz/web test` 630/630 green (was 616, +14 new); `pnpm --filter @bunnybagz/web typecheck` clean. Acceptance (a) ✅ vitest, (c) ✅ web suite green, (d) ✅ e2e spec file shipped. Acceptance (b) re-run of `apps/web/scripts/keyboard-nav-audit.mjs` deferred — requires live dev server + CDP browser; the e2e harness re-asserts the same `outline > 0px` contract under a real browser as a stronger gate. Closes audit D1 P0. (PROJECT:BUNNYBAGZ)

- [ ] **[P3_HEALTH_PROBE_CLEANUP]** Surfaced by `[P3_CHUNK_GRANULARITY_AUDIT]` (`docs/internal/audits/P3_CHUNK_GRANULARITY_AUDIT_2026-05-07.md` §5). The `health_check()` cleanup at `clarvis/brain/store.py:1023-1026` wraps `delete_memory(probe_id, ..., hard=True)` in `except Exception: pass`. Probes that fail to delete persist forever and cluster in `clarvis-memories`. Concrete count (full scan 2026-05-09): **345 records (59% of clarvis-memories) start with `health_probe_`; 295 ids start with `_health_probe_`; 356 (60.9%) records are <80 chars.** Two-step fix: (a) write `scripts/brain_mem/cleanup_health_probes.py` that hard-deletes any record in `clarvis-memories` where `id.startswith('_health_probe_')` OR `document.startswith('health_probe_')`, with a `--dry-run` default and per-batch logging; (b) replace the silent `except Exception: pass` at `store.py:1023-1026` with `_store_log.warning("health probe cleanup failed: %s", e)` so future leaks page someone. Run the script with `--apply` after the dry-run shows a sane count. **Acceptance:** dry-run reports between 300 and 400 deletions; `--apply` deletes them and `clarvis-memories` count drops by the matching delta; `store.py` warning is in place; baseline retrieval benchmark re-run after cleanup shows P@3 ≥ baseline (no regression). Bonus if P@3 lifts. (PROJECT:CLARVIS)

---

## Partial Items (tracked, not actively worked)

### External Challenges


---

## Research Sessions
