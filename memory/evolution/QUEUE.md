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

### BunnyBagz — MegaETH Casino (full state audit 2026-04-30)

_Repo: `GranusClarvis/bunnybagz` (renamed from `mega-house` 2026-04-29). Active branch: `feature/mvp-planning-and-rebrand`. Local workspace: `/home/agent/agents/mega-house/workspace`._
_**Workflow:** BunnyBagz is managed and tested **directly in its own repo**. Do NOT route through the SWO PR workflow (no `gh pr create --repo InverseAltruism/...`). Standard flow: pull → branch → edit → `pnpm test` (verify+api+web) + `forge test` (CI) → commit + push to working branch. PRs only when the operator explicitly asks._
_**Phase status (2026-04-30 audit):**_
- _**Phase 0 — Repo & rails: ✅ DONE.** Monorepo scaffolded; CI green (verify, web typecheck, contracts forge build+test, lint stub); domain `bunnybagz.xyz` locked; repo renamed._
- _**Phase 1 — Coinflip end-to-end on testnet: ⚠ ~70%.** Contracts (`Bankroll/Randomness/Coinflip` + `Deploy.s.sol`), Foundry tests (settlement math + fuzz + invariant + Bankroll unit), edge fns (`apps/api/{seed,verify,geo}`), `/play/coinflip` + `/verify/[betId]` pages, JS↔Solidity parity vectors (3), and `GEO_ENFORCE` flag ALL DONE. **Remaining:** testnet deploy run, indexer wiring (`apps/indexer` is README only), keeper-bot on-chain settle call, address-book population, persistent KV._
- _**Phase 2 — Dice + HiLo + USDM: ❌ NOT STARTED.** No `BunnyBagzDice/HiLo.sol`, no USDM integration, no Ponder indexer code, no wallet sheet, no light theme, no Playwright. `verify` package already has `diceRoll()` + `hiloCard()` helpers ready._
- _**Phase 3+ — operator-blocked.** Audit firm, multisig signers, counsel review, mainnet deploy._

_**Test inventory (all green as of 2026-04-30 audit run):** `@bunnybagz/verify` 19/19, `@bunnybagz/api` 30/30 (was 7; +23 new for seedStore + rotate/commit/reveal lifecycle + `/api/verify/[betId]` handler), `@bunnybagz/web` 16/16 (was 8; +8 new for `/play/coinflip` CTA state machine). Foundry suite extends with `BunnyBagzBankroll.t.sol` (22 standalone unit tests for register/setAllowance/revoke/deposit/withdraw/payout/settle/pause). All TS typechecks pass._

_**Open testing gaps (post-audit):** Playwright e2e (Phase 2 exit), local anvil deploy smoke, USDM behavior tests, animation/reduced-motion regression test, accessibility audit (contrast + keyboard + screen-reader), no `/play` lobby or `/wallet` route exists yet, no mascot art assets, no Tailwind/Framer Motion installed (the polish stack lives in `BUILD_PLAN.md` but isn't wired)._

_**Operator-blocking — DO NOT attempt autonomously:** funded testnet deployer key + first deploy, KV/Redis production binding, indexer Fly.io machine + Neon Postgres, audit firm engagement, multisig signer set, X/TG/Discord handle squat, real-money mainnet seed._

#### Phase 1 closeout (P1)


#### Pre-operator-test polish (P1, blocks "looks smooth" gate)


_Phase 2 prep + tooling hygiene (`[BB_WAGMI_CLI_ABI_GEN]`, `[BB_ADDRESS_BOOK_CODEGEN]`, `[BB_PERSISTENT_KV_ADAPTER]`, `[BB_PLAYWRIGHT_E2E_SETUP]`, `[BB_DICE_CONTRACT_PHASE2]`, `[BB_HILO_CONTRACT_PHASE2]`) is filed under `## P2 — When Idle § BunnyBagz — Phase 2 prep` below — they ship after the 11 P1 closeout items above land._




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

- [x] **[BB_ADDRESS_BOOK_CODEGEN]** (2026-04-30) Codegen `packages/chain/scripts/codegen-addresses.mjs` reads `packages/contracts/deployments/*.json` → writes `packages/chain/src/addresses.generated.ts`. `index.ts` overlays `ADDRESSES_GENERATED` onto the static base map; verified `ADDRESSES[6342].coinflip` resolves to the JSON value. New `chain-addresses` CI job runs `pnpm --filter @bunnybagz/chain check:addresses` (drift = exit 1). Deploy.s.sol docstring updated with codegen step. Web typecheck + verify (19) + api (36) + web (31) all green. (PROJECT:BUNNYBAGZ)
- [ ] [UNVERIFIED] **[BB_PERSISTENT_KV_ADAPTER]** `apps/api/lib/seedStore.ts` ships only `MemorySeedKV` today. Add a Cloudflare KV (or Upstash Redis, behind the same `SeedKV` interface) adapter selected when `BUNNYBAGZ_KV_BINDING` is set. Acceptance: `getKV()` returns the right adapter per env; the seed-lifecycle suite passes against an in-memory mock of the new adapter. **Operator-gated** for production binding setup. (PROJECT:BUNNYBAGZ)
- [ ] [UNVERIFIED] **[BB_PLAYWRIGHT_E2E_SETUP]** Phase 2 exit criterion (`docs/ROADMAP.md`). Install Playwright in `apps/web`, add a single `coinflip.spec.ts` walking: load `/`, click connect (mocked wallet), click Coinflip card, set stake, tap Heads, see settled outcome (against a local anvil + dev seed). Acceptance: `pnpm --filter @bunnybagz/web exec playwright test` runs green in CI (Linux + headless Chromium). Land before Phase 2 game contracts. (PROJECT:BUNNYBAGZ)
- [ ] [UNVERIFIED] **[BB_DICE_CONTRACT_PHASE2]** Phase 2 first game: `BunnyBagzDice.sol` (rollUnder, multiplier `99 / (R-1)`, same lifecycle as Coinflip). Reuse `BunnyBagzRandomness` + per-game allowance. Foundry: settlement math 100%, fuzz on rollUnder ∈ [2, 98]. JS layer already has `diceRoll()` in `packages/verify`. Acceptance: `forge test` 100%, parity vector added to JS↔Solidity test pairs. (PROJECT:BUNNYBAGZ)
- [ ] [UNVERIFIED] **[BB_HILO_CONTRACT_PHASE2]** Phase 2 third game: `BunnyBagzHiLo.sol` with session struct (`bet`, `currentMultiplier`, `currentCard`, `nonce`), `openSession`/`playStep`/`cashOut` lifecycle. Step multiplier `(12 / (13-c)) * 0.99`, ties → house. Foundry: settlement math 100%, fuzz on session length, invariant on bankroll solvency mirroring Coinflip's. Acceptance: same gates as Dice. (PROJECT:BUNNYBAGZ)

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
  - [ ] [UNVERIFIED_1] Analyze: read relevant source files, identify change boundary (added: 2026-04-30, source: auto_split)
  - [ ] [UNVERIFIED_2] Implement: core logic change in one focused increment (added: 2026-04-30, source: auto_split)
  - [ ] [UNVERIFIED_3] Test: add/update test(s) covering the new behavior (added: 2026-04-30, source: auto_split)
  - [ ] [UNVERIFIED_4] Verify: run existing tests, confirm no regressions (added: 2026-04-30, source: auto_split)
- ~~[SWO_V2_COMPANION_BG_MATTE]~~ (2026-04-24 entry) → VERIFIED NO-OP 2026-04-26 (Claude Code session). See first occurrence under §V2 — Testbed for full verification details.
- [~] [UNVERIFIED] **[DIGEST_ARCHIVE_IMPLEMENTATION]** Phase 12 ruled REVISE on digest actionability (56.5% vs 60% gate) with "Digest archive missing" as one root cause. Implement rolling archive: each write of `memory/cron/digest.md` snapshots prior content to `memory/cron/digest_archive/YYYY-MM-DD_HHMM.md` before overwrite. Retention: 30 days. Update `tools/digest_writer.py` + add `cron_cleanup.sh` pruning for archive dir. Enables digest trend analysis (what subconscious work was done last week?) and recovery from garbled writes. Acceptance: new digest write produces archive entry; older-than-30d entries auto-pruned; Phase 12 re-scoring can use archive as corpus. (PROJECT:CLARVIS)
  - [ ] [UNVERIFIED_1] Analyze: read relevant source files, identify change boundary (added: 2026-04-30, source: auto_split)
  - [ ] [UNVERIFIED_2] Implement: core logic change in one focused increment (added: 2026-04-30, source: auto_split)
  - [ ] [UNVERIFIED_3] Test: add/update test(s) covering the new behavior (added: 2026-04-30, source: auto_split)
  - [ ] [UNVERIFIED_4] Verify: run existing tests, confirm no regressions (added: 2026-04-30, source: auto_split)

### 2026-04-26 weekly review


### 2026-04-28 evolution scan

_Note: queue at 11 pending (under cap, but the recent saturation pattern argues for triage-first additions). Phi item continues operator-set de-emphasis (retires a stale ACTIVE GOAL that still names Phi≥0.65 as a target, contradicting `[PHI_DEEMPHASIS_AUDIT]`). Genuine weakest capability is `code_generation: 0.69` (not Phi); adding a concrete capability lift. Non-Python item is a bash digest lint that complements `[DIGEST_GARBLE_FIX]` with a regression guard._




### 2026-04-27 evolution scan

_Note: queue still saturated (20 pending, P1 at cap). Adding 4 items only — none speculative. Phi item continues the operator-set de-emphasis direction (passive observability signal only). Non-Python item is a bash/crontab health probe._

- [ ] [UNVERIFIED] **[PHI_HEARTBEAT_ATTENTION_DEBIAS]** Second execution slice of `[PHI_DEEMPHASIS_AUDIT]` after `[PHI_AUTO_INJECTION_REMOVAL]`. Remove Phi-score multipliers/boosts from the heartbeat attention scoring path so episodic recall ranking and task selection are no longer biased toward Phi-coded items. Touch: `clarvis/cognition/attention.py` (GWT salience scorer), `scripts/heartbeat_preflight.py` (task selection), and any spine `clarvis.cognition.*` callers that read `phi`/`integration` keys for attention weighting. Keep Phi readable as metadata, but stop letting it modify selection scores. Acceptance: grep of `attention.py` + `heartbeat_preflight.py` shows zero arithmetic on a Phi or Integration field; running heartbeat preflight on a corpus where Phi is shuffled yields identical task ranks (deterministic test); existing PI dashboard still shows Phi value. (PROJECT:CLARVIS)
- [ ] [UNVERIFIED] **[HEALTH_METRIC_CAPTURE_AUDIT]** Today's evolution scan context shows `Calibration: Brier=?, accuracy=?`, `Phi=? (trend: stable)`, `Retrieval: hit_rate=?%`, `Episodes: n=?, success_rate=?%` — the literal `?` placeholders mean the strategic-evolution prompt builder cannot read these telemetry sources. Locate the context-builder for cron_evolution / `scripts/strategic_evolution.py` and identify whether the breakage is (a) a stale/missing `data/performance_metrics.json` write, (b) an incorrect dict key lookup, or (c) a path that moved during the spine consolidation. Fix the readers so the next scan reports real numbers. Acceptance: next strategic-evolution prompt has zero `?` placeholders in the SYSTEM HEALTH section; a regression test validates the readers against a canned metrics fixture. (PROJECT:CLARVIS)
- [ ] [UNVERIFIED] **[GATEWAY_HEALTH_PROBE_CRON]** Non-Python: add a cron-based gateway watchdog so a silently-down OpenClaw gateway gets caught before the operator notices. Create `workspace/scripts/infra/gateway_probe.sh` that runs `systemctl --user status openclaw-gateway.service` + a TCP probe of `127.0.0.1:18789`, appends a one-line status to `monitoring/gateway_health.log`, and on three consecutive failures fires the existing Telegram alert helper. Wire it via `clarvis cron` preset at `*/15` (alongside `health_monitor.sh`). Acceptance: bash script exists and is executable, cron entry installed, simulated systemctl-stop produces a log entry within 15 min and a Telegram alert within 45 min. (PROJECT:CLARVIS)

### 2026-04-30 evolution scan

_Note: queue at 22 pending. Two items target the documented execution-shape warnings (no-task rate 46%, sidecar/QUEUE checkbox drift on 8 succeeded tasks). One targets the operator-stated weakest metric (Action Accuracy=0.875, target 0.9). One non-Python bash triage item complements the existing gateway probe. Skipping speculative additions to honour cap pressure._

- [ ] [UNVERIFIED] **[ACTION_ACCURACY_PRECHECK_GUARD]** Targets the weakest metric (Action Accuracy=0.875, target 0.9). Add a pre-execution sanity guard in `clarvis/cognition/preflight` (or `scripts/heartbeat_preflight.py`) that, before spawning Claude Code on a queue item, validates the named primitives in the task body actually exist: file paths via `Path.exists()`, module symbols via `importlib`-based introspection, CLI commands via `shutil.which`. On any miss, the heartbeat skips the task with a `precheck_fail` reason logged to the sidecar so the queue writer can re-evaluate (without burning a Claude Code spawn). Acceptance: new `precheck.py` module + tests covering hit/miss for each primitive type; sidecar entries gain a `precheck_fail` state; one-week measurement of episode `action_accuracy` shows ≥+0.015 lift attributable to the guard (compare to prior 14-day baseline). (PROJECT:CLARVIS)
- [ ] [UNVERIFIED] **[QUEUE_ARCHIVE_DRIFT_REPAIR]** Execution-shape warning surfaced: "8 task(s) succeeded but checkbox still [ ] — sidecar/QUEUE.md drift; archive_completed may be stalled." Diagnose `clarvis.queue.writer.archive_completed()` (and any cron caller) for why successful sidecar entries are not flipping the QUEUE.md checkboxes. Likely candidates: (a) ID match relies on a key the writer no longer stamps, (b) lockfile contention with the maintenance lock, (c) the cron entry that calls it stopped firing. Acceptance: a one-shot reconciliation script catches up the 8 stuck tasks; the underlying cause is fixed (not just the symptom); a regression test simulates a succeeded sidecar entry → verifies the checkbox flips on the next archiver run. (PROJECT:CLARVIS)
- [ ] [UNVERIFIED] **[QUEUE_AUTO_SPLIT_BOILERPLATE_PRUNE]** The compressed evolution-scan view is polluted with 8 boilerplate `[UNVERIFIED_1..4] Analyze/Implement/Test/Verify` sub-items spawned by `auto_split` from generic parent task descriptions. They consume queue cap, dilute the cap-ceiling signal, and add zero information beyond their parent. Audit `clarvis.queue.writer` (or wherever `source: auto_split` lives) and either (a) gate auto-split behind a per-task flag instead of running on every parent, or (b) collapse the four sub-items into a single rendered checklist inside the parent. One-shot cleanup: remove existing auto_split sub-items where the parent is already actionable (e.g., `[PHI_AUTO_INJECTION_REMOVAL]`, `[DIGEST_ARCHIVE_IMPLEMENTATION]`). Acceptance: queue compressed-view shows zero generic `Analyze/Implement/Test/Verify` lines; a regression test asserts auto_split does not fire on tasks already containing an Acceptance clause. (PROJECT:CLARVIS)

---

## Partial Items (tracked, not actively worked)

### External Challenges


---

## Research Sessions
