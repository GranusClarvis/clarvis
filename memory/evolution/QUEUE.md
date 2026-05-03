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

_**Status doc (sole source of truth):** `memory/cron/bb_phase1_status_2026-05-02.md`._
_**Realignment background:** `memory/evolution/bunnybagz_realignment_2026-05-01.md` (root cause of the 2026-04-30 queue-degradation incident)._
_**Latest verification pass:** `memory/cron/bb_phase1_verification_2026-05-01.md` (14 items audited; 6 silently-archived drift, now re-opened below as `[BB_*_REAL]`)._

_**Phase status (2026-05-02 evening, after commits `f513618` `a017122` `1473631`):**_
- _**Phase 0 — Repo & rails: ✅ DONE.**_
- _**Phase 1 — Coinflip end-to-end on testnet: ⚠ ~92%.** Contracts + edge fns + `/play/coinflip` + `/verify/[betId]` + parity + GEO flag + keeper-bot settle + framer-motion spin + token system + dark/light parity + mascots + `/play` + `/wallet` + recent-outcomes strip + keyboard/aria-live + WCAG-AA contrast audit ALL DONE. **Remaining (autonomous-doable):** indexer (Ponder) real impl, wagmi-CLI ABI codegen, persistent KV adapter (Cloudflare/Upstash). **Remaining (operator-gated):** funded testnet deploy run._
- _**Phase 2 — Dice + HiLo + USDM: ⚠ ~25%.** `BunnyBagzDice.sol` shipped + tested (commit `005b12a`); HiLo contract MISSING; USDM integration not started; Playwright e2e MISSING; `/play/dice` route not started._
- _**Phase 3+ — operator-blocked.** Audit firm, multisig, counsel, mainnet._

_**Test inventory (verified live 2026-05-02 evening):** `@bunnybagz/verify` **22/22**, `@bunnybagz/api` **36/36**, `@bunnybagz/web` **132/132**. Foundry suite covers Bankroll/Coinflip/Dice/Randomness/Version. `pnpm -r typecheck` clean._

_**Operator-blocking — DO NOT attempt autonomously:** funded testnet deployer key + first deploy, KV/Redis production binding (impl is autonomous-doable; the **binding** is operator-gated), indexer Fly.io machine + Neon Postgres (impl is autonomous-doable; the **hosting** is operator-gated), audit firm engagement, multisig signer set, X/TG/Discord handle squat, real-money mainnet seed._

#### Phase 1 closeout — drift re-opens (P1, autonomous-doable)

_Items the 2026-05-01 verification pass found silently archived as `[x] [UNVERIFIED]` but with no on-disk artifact. Mirroring the `[BB_TAILWIND_TOKENS_REAL]` pattern, each has a real acceptance contract that requires the test/file to exist before it can be archived._


#### Phase 1 closeout — UI polish for operator demo (P1, autonomous-doable)

_The 30-second flow works (UX_PLAN §2) but `bb_phase1_status_2026-05-02.md` flags four polish items that bridge "Phase 1 functional" to "Phase 1 looks intentional under an operator demo". Each ships as one PR with concrete tests._

- [ ] **[BB_WIN_CONFETTI_PULSE]** UX_PLAN §5 prescribes "confetti pulse capped at 600ms" on win-state; today only the `MascotCelebrate.tsx` 2-frame keyframe ships. Add `apps/web/src/components/WinConfetti.tsx` that renders a CSS-only confetti burst (no canvas-confetti dep — keep bundle small) for 600ms on a winning settle; respect `useReducedMotionPreference` (no animation, no DOM mount when reduced-motion). **Acceptance:** new component + 4-test vitest suite covering (a) mounts on win + matching pick, (b) does NOT mount on loss, (c) does NOT mount under reduced-motion, (d) auto-unmounts after 600ms via `vi.useFakeTimers`; web suite 132 → ≥136. (PROJECT:BUNNYBAGZ)
- [ ] **[BB_FIRST_BET_HINT]** UX_PLAN §2 prescribes a "Tap **HEADS** or **TAILS** to play" first-bet hint on `/play`. Today the lobby shows the Coinflip card with no instructional copy for first-time visitors. Add a small dismissible hint pill above the card (state stored in `localStorage` under `bunnybagz:first-bet-hint-dismissed`); auto-hides after the first connected wallet places a bet (read from indexer when wired, otherwise stay until manually dismissed). **Acceptance:** new component + 3 vitest cases (renders by default, dismissible, stays dismissed across re-mounts via localStorage); does NOT render in test setups where `localStorage["bunnybagz:first-bet-hint-dismissed"]` is set; web suite +3. (PROJECT:BUNNYBAGZ)
- [ ] **[BB_TABULAR_FIGURES_AUDIT]** UX_PLAN §6 prescribes "Tabular figures everywhere balances and odds appear. No exceptions." Audit `apps/web/src/` for every site that renders an ETH balance, USDM balance, payout multiplier, edge percentage, or odds string and confirm a `font-feature-settings: "tnum"` (or Tailwind `tabular-nums`) is applied. Add a vitest helper that snapshots the computed style on the relevant elements. **Acceptance:** audit doc at `apps/web/src/lib/tabular-figures-audit.ts` enumerates the surfaces; vitest test asserts each site has the tabular numerals class/style; ≥1 fix landed in the same PR for any site found missing. (PROJECT:BUNNYBAGZ)
- [ ] **[BB_MOBILE_THUMB_ZONE_AUDIT]** UX_PLAN §3 prescribes "Primary action **always lives in the bottom 30% of the viewport**. Thumb-zone law." Today there's no test enforcing this. Add a token-level audit at `apps/web/src/lib/thumb-zone-audit.ts` that, given a route's primary CTA selector + a viewport size, computes (in the JSDOM render tree) the CTA's `getBoundingClientRect().top / viewport.height` ratio and asserts it lies in the bottom 30% on iPhone-SE (375×667) + Pixel-7 (412×915) viewports. Cover `/`, `/play`, `/play/coinflip`. **Acceptance:** new audit + vitest suite (≥6 cases — 3 routes × 2 viewports); web suite +6; CI step runs the audit. (PROJECT:BUNNYBAGZ)

#### Phase 2 — re-open + new (P1 once Phase 1 closes; staged P2 today)

_Re-opens of items the 2026-05-01 audit found drifted. Filed under P1-once-Phase-1-closes since they are real product work, but sit at the Phase-2 boundary today._

- [ ] **[BB_HILO_CONTRACT_PHASE2_REAL]** ([REOPENED] from `[BB_HILO_CONTRACT_PHASE2]`, drift confirmed 2026-05-01). `packages/contracts/src/` has Bankroll/Coinflip/Dice/Randomness/Version only — no `BunnyBagzHiLo.sol`. Ship: `BunnyBagzHiLo.sol` with session struct (`bet`, `currentMultiplier`, `currentCard`, `nonce`), `openSession`/`playStep`/`cashOut` lifecycle; step multiplier `(12 / (13-c)) * 0.99`, ties → house. Mirror Coinflip/Dice patterns: per-game allowance via Bankroll, commit-reveal randomness, expiration → refund. Foundry tests: settlement math 100%, fuzz on session length, invariant on bankroll solvency mirroring Coinflip's. JS-side `hiloCard()` parity vectors in `packages/verify` (helpers already exist per yesterday's audit). **Acceptance:** `BunnyBagzHiLo.sol` + `BunnyBagzHiLo.t.sol` shipped; `forge test` 100% in CI; verify suite extended with HiLo parity vectors (22→≥30). (PROJECT:BUNNYBAGZ)
- [ ] **[BB_PLAYWRIGHT_E2E_SETUP_REAL]** ([REOPENED] from `[BB_PLAYWRIGHT_E2E_SETUP]`, drift confirmed 2026-05-01 + 2026-05-02). `apps/web/package.json` has zero playwright deps; no `playwright.config.*`; no spec. Phase 2 exit criterion per `docs/ROADMAP.md`. Install `@playwright/test`; ship `apps/web/playwright.config.ts` (Chromium + Mobile Safari emulation, 30s timeout, retries=1 in CI) and `apps/web/e2e/coinflip.spec.ts` walking: load `/`, click connect (mocked wallet via `playwright`'s `page.addInitScript` + a wagmi mock), navigate to `/play`, click Coinflip card, set stake, tap Heads, see settled outcome (mocked api/seed). Add CI job that runs `pnpm --filter @bunnybagz/web exec playwright test` on Linux headless. **Acceptance:** spec runs green locally + in CI; deps lockfile updated; new CI job in `.github/workflows/ci.yml`. (PROJECT:BUNNYBAGZ)

#### BunnyBagz — process + verification (P1, autonomous-doable)

- [ ] **[BB_PHASE1_VERIFICATION_PASS_RECURRING]** Make the BB phase verification pass a weekly cadence so silent drift is impossible. Add `clarvis cron` entry running `python3 scripts/audit/bb_phase_verification.py` every Sunday 04:30 CET (sits in the maintenance window; uses `/tmp/clarvis_maintenance.lock`). The script: walks `memory/evolution/QUEUE_ARCHIVE.md` for `[x] [BB_*]` items archived in the last 7 days, asserts each cited commit exists in `mega-house/workspace`'s git log, asserts each cited file path exists, asserts each cited test count matches a fresh `pnpm --filter` run. Output: `memory/cron/bb_phase_verification_<YYYY-MM-DD>.md` mirroring the 2026-05-01 schema; on any drift, append a `[BB_<TAG>_REAL]` reopen task to `QUEUE.md` automatically (using `clarvis.queue.writer.append_task`). **Acceptance:** script + cron entry + first weekly run produces a verification doc; planted-drift test (manually flip one `[x]` item to a fake commit hash) confirms the auto-reopen path. (PROJECT:BUNNYBAGZ)
- [ ] **[BB_END_TO_END_UI_REVIEW]** Single-shot UI review pass over the live BB web surface — does the 30-second flow per UX_PLAN §2 actually feel right? Use the existing `clarvis_browser.py` (Playwright CDP path) to: visit `localhost:3000/`, screenshot LCP at 1.0s, navigate `/play`, screenshot, tap Coinflip card, screenshot, simulate keyboard-only (Tab → Enter), screenshot, take a screenshot under both dark and light themes, take a screenshot at 375px-wide viewport. Save under `memory/cron/bb_ui_review_<YYYY-MM-DD>/`. Then write a 10-line review verdict scoring each surface 1-5 against UX_PLAN §3 layout primitives + §6 visual system + §7 accessibility. **Acceptance:** review folder exists with ≥6 screenshots; verdict file at `memory/cron/bb_ui_review_<YYYY-MM-DD>.md` lists ≥3 concrete issues with file:line references where the fix should land; if any issue is `severity: high`, auto-append a `[BB_UI_<TAG>_FIX]` task to QUEUE.md. (PROJECT:BUNNYBAGZ)

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

- [ ] **[CONFIG_MULTI_LANE_ACTIVATION]** Wire BUNNYBAGZ as a co-active project lane alongside SWO. Edit `scripts/cron/cron_env.sh` to set `CLARVIS_ACTIVE_PROJECT_LANES="SWO,BUNNYBAGZ"` (read by `clarvis/queue/runnable.py` for lane-health monitoring). Edit the same file to flip `CLARVIS_QUEUE_UNVERIFIED_GUARD="block"` (writer.py reads this; default `log` is opt-in observability, `block` is the actual prevention). Both env vars only take effect for cron + spawn; interactive use unaffected. **Acceptance:** `grep CLARVIS_ACTIVE_PROJECT_LANES scripts/cron/cron_env.sh` returns the new line; next cron_morning report shows `🛤 LANE HEALTH` for both SWO and BUNNYBAGZ; planted-test (mark a fake `[BB_TEST_UNVERIFIED]` item `[x] [UNVERIFIED]` with no sidecar verification record + run `archive_completed`) is HELD not archived. (PROJECT:CLARVIS)
- [ ] **[TASK_SELECTOR_MULTI_LANE_BOOST]** `clarvis/orch/task_selector.py:60` reads a single `_PROJECT_LANE` env var at import time (line 60: `_PROJECT_LANE = os.environ.get("CLARVIS_PROJECT_LANE", "").strip()`); `_project_lane_boost()` only matches that one lane. After `[CONFIG_MULTI_LANE_ACTIVATION]` lands, BB tasks get the lane-health surface but NOT the +0.3 selector boost. Extend `_project_lane_boost()` to ALSO match any lane in `CLARVIS_ACTIVE_PROJECT_LANES` (comma-split, upper-case). Boost stays at +0.3 (do not multiply). Read both env vars at function-call time, not import time, so cron-set env applies. **Acceptance:** new test `tests/test_task_selector.py::test_multi_lane_boost` covers (a) `CLARVIS_PROJECT_LANE=SWO` only — only SWO tasks boosted, (b) `CLARVIS_ACTIVE_PROJECT_LANES=SWO,BUNNYBAGZ` only — both boosted, (c) both env vars set — both boosted (no double-counting). (PROJECT:CLARVIS)
- [ ] **[QUEUE_LANE_MINIMUM_AUTOFILL]** When `lane_health` reports `in_queue == 0` for an active project lane (BB went 24h with zero actionable items today even though Phase-1 work remained), do not just warn — also auto-spawn a `[<LANE>_LANE_REFILL]` task that asks Claude Code to: (a) read the lane's status doc (`memory/cron/<lane_lower>_phase*_status_*.md`, latest), (b) read the lane's section header in QUEUE.md, (c) propose 2–3 concrete next-step items with acceptance contracts, (d) write them to QUEUE.md. Wire this into `scripts/pipeline/heartbeat_postflight.py` (or `cron_report_morning.sh` — pick whichever already runs `lane_health`). **Acceptance:** when both lanes are saturated, no autofill task spawns; when one is empty, exactly one `[<LANE>_LANE_REFILL]` task lands in QUEUE.md per scan; idempotent (does not stack if the previous refill task is still pending). (PROJECT:CLARVIS)
- [ ] **[PROJECT_VERIFICATION_CADENCE_GENERIC]** `[BB_PHASE1_VERIFICATION_PASS_RECURRING]` (filed under BB above) bakes in a per-project weekly verification. Generalize: `scripts/audit/project_verification_pass.py <lane>` — reads QUEUE_ARCHIVE.md for `[x] [<LANE>_*]` items in the last N days, asserts cited commit/file/test claims hold, writes `memory/cron/<lane_lower>_verification_<YYYY-MM-DD>.md`, auto-reopens drift as `[<LANE>_<TAG>_REAL]`. Cron entry runs per active lane (read `CLARVIS_ACTIVE_PROJECT_LANES`). **Acceptance:** running `project_verification_pass.py SWO` produces a SWO doc; running `project_verification_pass.py BUNNYBAGZ` produces a BB doc; cron entry installed via `clarvis cron`; first weekly run produces both docs. Replaces `[BB_PHASE1_VERIFICATION_PASS_RECURRING]` once shipped (mark BB item DONE then). (PROJECT:CLARVIS)
- [ ] **[QUEUE_LANE_DROP_AUDIT]** Diagnose why the BB lane went silent for 36+ hours after the 2026-05-01 realignment despite the lane-minimum guard shipping mid-window. Read `monitoring/queue_unverified_archive.log` + `data/audit/queue_verifications/` + cron run logs from 2026-05-01 18:00 → 2026-05-02 18:00 CET. Write `docs/internal/audits/QUEUE_LANE_DROP_AUDIT_2026-05-02.md` enumerating: (a) when lane-health was first surfaced in a morning brief, (b) whether `archive_completed()` was actually called in `block` mode (it wasn't — env var unset), (c) which heartbeats picked Clarvis-self instead of BB and why (selector logged scores), (d) one concrete recommendation per finding. **Acceptance:** doc exists with ≥3 findings + ≥3 recommendations; recommendations either map to existing queued items above OR file new ones inline. (PROJECT:CLARVIS)

#### Capability building — UI quality (2026-05-02 evening)

_Source: operator concern that Clarvis cannot reliably create or review beautiful UI / page quality. The 2026-05-02 BB review confirmed that token-level audits (contrast, mascot SVG presence) ship but visual review is operator-eyeballed only. These tasks build the missing capability._

- [ ] **[UI_QUALITY_PLAYWRIGHT_VISUAL_REGRESSION_HARNESS]** Today Clarvis can run vitest on UI components but cannot assert "the page looks intentional" — it relies on token-level proxies (contrast ratios, font feature settings). Build a generic harness: `scripts/ui_review/playwright_visual.py <repo> <route> <viewport>` that (a) launches `clarvis_browser.py` against a local dev server, (b) screenshots the named route at 3 viewports (mobile/tablet/desktop), (c) saves under `data/ui_review/<repo>/<route>/<viewport>.png`, (d) computes a perceptual diff vs the prior snapshot using `pixelmatch`-style algorithm (or `imagehash` from PyPI — install if needed), (e) flags >5% pixel-change or >10% phash distance as `regressed`. Wire into a per-project cron job. **Acceptance:** baseline snapshots exist for `/`, `/play`, `/play/coinflip` × 3 viewports for BB; second run shows zero regressions; planted-change (CSS color tweak) triggers `regressed` flag. (PROJECT:CLARVIS)
- [ ] **[UI_QUALITY_REVIEW_RUBRIC]** Establish a 7-axis UI review rubric Claude Code can apply consistently across projects. Create `clarvis/cognition/ui_review.py` exposing `review_ui_artifact(screenshot_path, ux_plan_path) -> dict` that scores: (1) visual hierarchy (LCP element clarity), (2) thumb-zone CTA placement, (3) color contrast (delegates to existing `contrast-audit.ts` per-repo), (4) type rhythm (heading vs body size ratio), (5) whitespace/breathing room, (6) brand consistency (palette adherence), (7) accessibility surface (visible focus rings, sufficient touch targets). Each axis scored 1-5 with one-line evidence. **Acceptance:** module + tests + first review of BB `/play/coinflip` produces a scored card at `memory/cron/bb_ui_review_2026-05-XX.md`; rubric is documented at `docs/UI_REVIEW_RUBRIC.md` so per-project agents can reuse. (PROJECT:CLARVIS)
- [ ] **[PROJECT_AGENT_UI_LITE_BRAIN_SEED]** The mega-house lite-brain (project-agent.py path) does not currently include UX_PLAN.md or BRAND.md as seeded knowledge. Result: when a BB-targeted spawn asks "is this design choice on-brand?", the agent has no grounding doc. For each active project agent (BB, SWO), seed the lite brain with the project's UX_PLAN.md + BRAND.md + ROADMAP.md as searchable memories on creation. Update `project_agent.py seed` to detect these docs and ingest them under `project-procedures` (operator-set design constraints) and `project-context` (current phase). **Acceptance:** `python3 scripts/project_agent.py info bunnybagz` shows ≥3 seeded UX/brand entries; spawned agent's lite-brain `search("primary CTA placement rule")` returns the UX_PLAN §3 thumb-zone rule. (PROJECT:CLARVIS)



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
- [ ] **[QUEUE_ELIGIBILITY_PROBE_PAGING_WIRE]** Non-Python bash. `[QUEUE_ELIGIBILITY_ZERO_PROBE]` shipped `scripts/audit/queue_eligibility_probe.sh` this morning but the watchdog paging hookup needs verification. Check `scripts/cron/cron_watchdog.sh` (or spine equivalent) — if it does not already invoke the probe, wire it in: on each watchdog run, call the probe; if the probe shows `eligible=0 && pending>0` for ≥30 min (track via `monitoring/queue_eligibility_drift.log` last-success timestamp), fire a Telegram alert via `scripts/infra/budget_alert.py`'s alert helper or the existing `cron_watchdog.sh` alert hook. Acceptance: `grep queue_eligibility_probe scripts/cron/cron_watchdog.sh` returns ≥1 line; manual smoke test (touch a marker file simulating sustained eligibility=0) produces one Telegram alert; resolution clears the marker so alerts don't repeat. (PROJECT:CLARVIS)


---

## Partial Items (tracked, not actively worked)

### External Challenges


---

## Research Sessions
