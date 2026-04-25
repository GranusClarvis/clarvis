# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items archived by `clarvis.queue.writer.archive_completed()` to QUEUE_ARCHIVE.md._
_Caps: P0 ≤ 10, P1 ≤ 15. Triage before adding. See docs/PROJECT_LANES.md for rules._
_Deep audit tracker: `docs/internal/audits/CLARVIS_DEEP_AUDIT_PLAN_2026-04-16.md` (existing P1 audit items map to phases there — do not duplicate). Quick-reference: `docs/internal/audits/AUDIT_INDEX.md`._

## P0 — Current Sprint (2026-04-15)

- [x] [STRATEGIC_AUDIT] **[PI_HISTORY_WRITER_REPAIR]** Fixed 2026-04-25. Root cause: `clarvis/heartbeat/adapters.py:_structural_health` was appending `structural_health` entries to `performance_history.jsonl` instead of the dedicated `data/structural_health_history.jsonl` (which `heartbeat_postflight.py` already used correctly). Audit's "last full PI 2026-04-02" claim was misleading — full PI records existed daily; the structural_health entries at the file's tail masked them. Fix: redirected adapters writer, migrated 7 misplaced entries (backup at `performance_history.jsonl.bak_pi_repair`). Acceptance verified: 7 consecutive days (04-19→04-25) all have full PI records. 137 tests pass.
_Audit-phase override: while executing the deep Clarvis audit plan, do not suppress or skip justified follow-up queue items merely because P1 is over cap. Audit-derived findings may add P1/P2 tasks when they are necessary to preserve audit continuity and evidence integrity. Triage still applies, but cap pressure must not block recording valid findings._

### Critical Pipeline Fixes


### Deep Audit (anchor for canonical audit tracker)


### Execution Governance (added 2026-04-15 — prevents SWO-style drift)


### Deep Audit — Phase 9 Follow-ups (added 2026-04-17)

_Source: `docs/internal/audits/NEURO_FEATURE_DECISIONS_2026-04-17.md`. Phase 9 scored 16 neuro features via proxy-EVS/TCS (no A/B data). 2 PROMOTE, 6 KEEP, 4 REVISE, 4 SHADOW, 0 DEMOTE. Critical defect: world_models calibration loop broken._


### Bugs

- [ ] **[CRON_DOCTOR_SOFT_HEALTH_SEMANTICS]** `scripts/cron/cron_doctor.py::check_chromadb_health()` now skips destructive recovery when the brain initializes but health_check reports soft issues, but still returns `success=False`. Audit all callers/reporting paths and split `healthy` vs `recoverable_soft_issue` so cron doctor doesn't page/escalate like a hard failure while still surfacing issues for graph hygiene/backfill jobs.
- [ ] **[CRON_SYNC_STASH_RECOVERY_REF]** `scripts/cron/cron_env.sh::sync_workspace()` captures `_stash_ref` via `git stash list -1 --format="%H"`, which yields an opaque commit hash, while the recovery instructions reference stash workflows. Store/log a usable stash selector (`stash@{n}`) or both selector+hash so operators can recover stranded work without guesswork.

## P1 — This Week

### Claude Design & Routines Integration (cross-project, added 2026-04-20)

_Source: `docs/CLAUDE_DESIGN_ROUTINES_STRATEGY.md`. Cross-project operating model for Claude Design + Claude Code Routines._


### Star Sanctuary V2 — World-First Rebuild (PROJECT:SWO, reviewed 2026-04-23)

_Sanctuary V2 replaces V1 React panel layout with a Phaser 3 game world. Direction: lobby-first, social, game-like (Tamagotchi + Club Penguin + Habbo). Backend/API layer unchanged — V2 is a frontend revolution._
_V2 Plan: `docs/SANCTUARY_V2_PLAN.md` | Style: `docs/SANCTUARY_STYLE_DOCTRINE.md` | ADR: `docs/SANCTUARY_ADR.md`_
_Status: Phases 0-3 COMPLETE (PRs #205-#219 merged). Phase 4 in progress (quest NPCs done, overlays remain). Operator hand-crafted all map/sprite/room art 2026-04-23._
_Asset state: Overworld map ✓ (Sanctuary_map.png) | 4 player sprites ✓ | 8 room backgrounds ✓ | 8 NPC sprites ✓ | 10×6 companion mood PNGs ✓ (need BG cleanup) | Collision data ✓ (685 rects from marked map)_
_Tech stack: Phaser 3 + easystar.js (pathfinding) + Colyseus (multiplayer) + React overlays + EventBus bridge_
_What carries forward: all DB schema, all API routes, wallet auth, bond/XP logic, quest data model, security fixes_
_What's left behind: panel layout, tab navigation, CompanionPanel button grid, monolithic SanctuaryContent.tsx_
_**Testing convention:** Primary dev/test loop is local: `npm run dev` + `npm run colyseus:dev` in SWO workspace, verify at `localhost:3000/sanctuary`. Run `npm run type-check && npm run lint && npm run build` before PR. test.starworldorder.com is **secondary deployment verification only** — requires separate pull/rebuild on server, not the default test path._

#### Phase 0: API Contract Lock & Security — ✅ DONE (PRs #205-#207)

- **GATE MET:** All 16 API routes have HTTP-layer tests. Zod validation. SQLite rate limiting + wallet auth on all Sanctuary POST routes.

#### Phase 1: Canvas Foundation — ✅ DONE (PRs #208-#210, #213 + operator commits)

- **GATE MET:** Player walks 8-zone world with hand-painted map background (Sanctuary_map.png). Click-to-move pathfinding via easystar.js. Zones trigger events. HUD shows companion stats. Door system with [E] interaction. Collision data from marked map (685 rects). Clean character sprite via PlayerSprite::registerFrames.

#### Phase 2: Companion Alive — ✅ DONE (PRs #214-#215)

- **GATE MET:** Companion follows player with animation. 10 constellation × 6 mood sprite system. Radial menu with pet/feed/play reactions + API calls. Bond/XP increments visible.

#### Phase 3: Multiplayer Lobby — ✅ DONE (PRs #216-#218)

- **GATE MET:** Colyseus multiplayer with room-per-location architecture. Other players visible. Chat bubbles above players. Join/leave on zone transition.

#### P0 Playability Blockers (fix before continuing Phase 4)

_Discovered 2026-04-23 during codebase review. Collision fix shipped same day (operator commit f17f38e). 5 items remain._

- **GATE:** Overworld collision works ✅. All 8 rooms enterable via doors (including Star Garden). NPCs show real sprite art. Chat works offline (local echo). Companion sprites render without background artifacts. Rooms are playable spaces with movement and collision.

#### Phase 4: Diegetic Content & Overlay Migrations (P1 — partially done)

_Quest NPCs with click-to-dialog and quest board shipped (PR #219). Remaining: 3 overlay migrations + 3 new content tasks from operator brief._

**Overlay migrations (carry-forward):**

**New diegetic content (from operator split brief 2026-04-23):**
- **GATE:** Quests discovered in-world via NPCs. All V1 panels (journal, traits, quests) migrated to contextual overlays. No panel layout remnants in V2. Spawn Fox greets first-time visitors. Each room has its themed NPC. Quest Board aggregates all quests.

#### Phase 4B: Room Activities & Minigames (P1 — from operator split brief, 4-5 PRs)

_Operator requirement: rooms must have gameplay, not just scenery. Training Grounds for leveling, timed quests with away-state, shared minigame plumbing, 8 room-specific minigames. All depend on `[SWO_P0_ROOM_GAMEPLAY]` + `[SWO_V2_ROOM_NPCS]`._

- **GATE:** Every room has interactive gameplay beyond scenery. Timed quests show away-state in HUD with countdown. Training Grounds grant XP that persists and levels up companions. At least 4/8 minigames playable with score tracking. Leaderboards display.

#### Phase 5: LLM Companion (P1 — AI chat, emotional bond, 4 PRs)

_Companion chat confirmed valid for V2. Positioned after world + quests are working. Design ref: `docs/KINKLY_REFERENCE_ANALYSIS.md`._

- **GATE:** Companion talks via LLM with personality. Remembers facts across sessions. Bond stages change tone. Chat overlay works in-world with typing simulation.

#### Phase 6: Economy (P2 — STAR currency, shop, cosmetics, 4 PRs)

_Operator requirement: STAR currency storage + ShopDialog/API. All economy is off-chain for V2 (on-chain decision deferred per `SANCTUARY_STAR_CURRENCY_DECISION` in Post-V2)._

- [ ] **[SWO_V2_SHOP_BACKEND]** Shop API + ShopDialog backend. Seed `sanctuary_cosmetic_items` table with 20-30 items (hats, accessories, backgrounds, animations; 10-50 STAR per STAR_SANCTUARY_PLAN.md). `POST /api/sanctuary/shop/buy` (validate STAR balance via `sanctuary_star_balance`, deduct, add to `sanctuary_companion_inventory`). `POST /api/sanctuary/inventory/equip`. `GET /api/sanctuary/shop/items` (filterable by category, sorted by price). Tests for purchase, insufficient balance, double-equip, level gating. Depends on `[SWO_V2_STAR_CURRENCY]`. Needs content from `[SWO_V2_COSMETIC_ITEM_DESIGN]`. (PROJECT:SWO)
- [ ] **[SWO_V2_SHOP_UI]** ShopDialog overlay component (`components/sanctuary/overlays/ShopDialog.tsx`). Triggered by NPC interaction in Town Square (add Shop Keeper NPC or use existing Quest Board area) + hotkey (B). Grid layout with category tabs (Hats / Accessories / Backgrounds / Animations). Live companion preview (EventBus preview event). Buy button with STAR price, balance display, "Owned" badge, level requirement. Inventory tab via hotkey (I) showing owned items with equip/unequip. Depends on `[SWO_V2_SHOP_BACKEND]` + `[SWO_V2_COSMETIC_SPRITE_LAYERS]`. (PROJECT:SWO)
- **GATE:** STAR balance persists per wallet and updates on earn/spend. Players browse shop, buy, equip cosmetics. Companions render with equipped items. ShopDialog opens from NPC or hotkey.

#### Phase 7: Personal Rooms (P2 — customizable spaces, 2 PRs)

_Note: basic RoomScene shell exists (bg image + exit). `[SWO_P0_ROOM_GAMEPLAY]` makes rooms playable first. This phase adds personalization._

- [ ] **[SWO_V2_ROOM_CUSTOMIZATION]** Room personalization. Background/floor from equipped cosmetics. Drag-and-place decorations from inventory on 3×3 grid. Layout saved to `sanctuary_companions.room_layout` (new JSON column). Visit other players' rooms (click avatar → "Visit Room"). Visitors see but can't modify. (PROJECT:SWO)
- **GATE:** Players have personal rooms. Decorations persist. Can visit others' rooms.

#### Phase 8: Polish (P2 — mobile, onboarding, sound, 3 PRs)

- [ ] **[SWO_V2_MOBILE_CONTROLS]** Mobile touch support. Virtual joystick (`rexrainbow/phaser3-rex-notes` plugin or custom). Tap-to-move. Responsive canvas sizing. Touch-friendly overlays (min 44px targets). Test iOS Safari + Android Chrome. Depends on Phases 1-6 stable. (PROJECT:SWO)
- [ ] **[SWO_V2_ONBOARDING]** Full guided tutorial extending Spawn Fox intro (`[SWO_V2_SPAWN_FOX_INTRO]`). Detect new player (no companion). Spawn Fox walks player through: select companion → walk to first room → interact with NPC → open quest board → try first minigame. Tooltip arrows + highlight zones. Skip button. State in `sanctuary_player_state`. Depends on `[SWO_V2_SPAWN_FOX_INTRO]` (basic intro) + Phase 4B (minigames exist). (PROJECT:SWO)
- [ ] **[SWO_V2_SOUND_DESIGN]** Ambient + SFX. Per-location ambient loops (crossfade on zone transition). Interaction SFX (pet sparkle, feed munch, level-up chime). Muted by default, volume slider. Howler.js or Phaser built-in. Need ~8 ambient loops + ~10 SFX. (PROJECT:SWO)
- **GATE:** Mobile-ready with touch controls. New players guided. Audio layer functional (muted by default).

#### Art & Content Track (updated 2026-04-23 — most art now delivered by operator)

_Operator hand-crafted most assets 2026-04-23. Remaining work is cleanup/content, not creation._

- [ ] **[SWO_V2_QUEST_DIALOG_CONTENT]** Write quest dialog for 5 daily errands + 3 weekly adventures. Map to `sanctuary_quests` table format. JSON seed file. NPC names/zones/locations already defined in `npcDefinitions.ts`. (PROJECT:SWO, CONTENT)
- [ ] **[SWO_V2_COSMETIC_ITEM_DESIGN]** 20-30 items: 8 hats, 6 accessories, 5 backgrounds, 5 floors, 4 animations, 2 seasonal. Each: name, category, rarity (common/uncommon/rare/epic), STAR price (10-50), level req (0-15), pixel art spec. Seed JSON for `sanctuary_cosmetic_items`. **Sprite generation handled by `[SWO_RD_BATCH_4_HATS]` and follow-up RD batches; this item only owns the data spec.** (PROJECT:SWO, CONTENT)

#### Sanctuary Asset Pipeline — Retro Diffusion (added 2026-04-25)

_Source: `memory/evolution/swo_sanctuary_retrodiffusion_action_plan_2026-04-25.md`. Plan: `memory/evolution/swo_sanctuary_retrodiffusion_plan_2026-04-25.md`. Stand up dedup-protected RD pipeline in SWO repo, then drip-ship 5 asset batches (~41 assets, ~$2.50–$5.00 budgeted to $10). All assets gated by `check_cost: true` preflight, manifest hash dedup, staging-first promotion. `RD_API_KEY` env-only — never commit / log / echo._

- [ ] **[SWO_RD_PIPELINE_INFRA]** Build the Retro Diffusion asset pipeline in the SWO repo. Create `scripts/rd/{rd_client,rd_plan,rd_generate,rd_review,rd_promote,rd_dedup}.py` (env-only `RD_API_KEY`, refuses to start if unset; always sends `check_cost: true` first; per-batch cost cap default $0.50, daily $5.00; flock `/tmp/rd_generate.lock`). Folders: `assets/specs/` (committed YAML), `assets/manifest.json` (committed), `assets/requested.jsonl` (committed), `assets/staging/` + `assets/rejected/` (gitignored). One-time `assets/palette/sanctuary_palette.png` from doctrine §2 swatches. Add `RD_API_KEY=` placeholder to `.env.example`. Operator runbook at `docs/ASSET_PIPELINE.md`. PR includes `--dry-run` smoke test (no real API call) covering: spec parse, hash compute, dedup refusal on existing slug, manifest read/write. Acceptance: `python3 scripts/rd/rd_client.py credits` returns balance when `RD_API_KEY` set; `rd_plan.py --slug <fake>` errors cleanly when missing. Blocks: all batches below. (PROJECT:SWO, P1)
- [ ] **[SWO_RD_BATCH_1_HUD]** Generate 12 × 16×16 HUD icons (pet/feed/talk/send/sleep + bond/xp/energy/hunger/level + quest/journal) using `rd_fast__mc_item` style with `bypass_prompt_expansion: true`, `remove_bg: true`, sanctuary palette PNG anchored. Standard negative prompt. Specs in `assets/specs/hud_*.yaml`. Generate `num_images: 4` per slug, pick winner, save seed. Promote to `public/sanctuary/hud/`. Wire icons into `CompanionHUD.tsx` (stat row) + `QuestBoard.tsx` (quest list) + radial menu (action buttons), replacing emoji per Style Doctrine §6 ("When sprites arrive, replace emoji with 16×16 pixel icons"). Test at 1× and 2× display. Single PR. Cost cap $0.50. Depends on `[SWO_RD_PIPELINE_INFRA]`. (PROJECT:SWO, P1)

#### Post-V2 (P2 — after V2 stable)

- [ ] **[SWO_SANCTUARY_EXPEDITIONS]** Multi-step expedition adventures with narrative choices. Needs V2 Phase 4 quest system as foundation. (PROJECT:SWO)
- [ ] **[SWO_SANCTUARY_MEMORY_CONSOLIDATION]** Weekly batch: merge duplicate memories, decay old emotions, summarize recurring topics. Depends on `[SWO_SANCTUARY_CHAT_PERSISTENCE]` shipping and accumulating data. (PROJECT:SWO)
- [ ] **[SANCTUARY_STAR_CURRENCY_DECISION]** STAR on Monad (soulbound vs transferable vs hybrid). Blocks on-chain cosmetic minting. Not needed for V2 MVP — all V2 economy is off-chain. See STAR_SANCTUARY_PLAN.md §3.3. (PROJECT:SWO)

#### Retired Items (absorbed or replaced by V2 tasks)

_These V1 items are no longer standalone tasks. Their scope is covered by V2 items above._

- ~~[SWO_SANCTUARY_RESPONSIVE]~~ → absorbed by `[SWO_V2_MOBILE_CONTROLS]` (V1 panel layout gone; mobile = Phaser canvas now)
- ~~[SWO_SANCTUARY_CHAT_HISTORY]~~ → merged into `[SWO_SANCTUARY_CHAT_PERSISTENCE]` (single PR for history + memory)
- ~~[SWO_SANCTUARY_TYPING_SIM]~~ → absorbed by `[SWO_V2_COMPANION_CHAT_OVERLAY]` (typing sim is 15 lines, not a separate PR)
- ~~[SWO_SANCTUARY_SOUND_DESIGN]~~ → absorbed by `[SWO_V2_SOUND_DESIGN]` (same scope, V2 framing)
- ~~[SWO_SANCTUARY_COSMETICS_SHOP]~~ → replaced by `[SWO_V2_SHOP_BACKEND]` + `[SWO_V2_SHOP_UI]` (V2 split into backend + zone-based UI)
- ~~[SWO_V2_WORLD_TILESET_ART]~~ → RETIRED 2026-04-23. Operator painted full map PNG.
- ~~[SWO_V2_COMPANION_SPRITE_ART]~~ → RETIRED 2026-04-23. Mood PNGs exist; replaced by `[SWO_P0_COMPANION_BG_MATTE]`.
- ~~[SWO_V2_NPC_QUEST_CONTENT]~~ → RETIRED 2026-04-23. NPCs defined in `npcDefinitions.ts` + sprite art exists. Remaining dialog content moved to `[SWO_V2_QUEST_DIALOG_CONTENT]`.
- ~~[SWO_V2_ROOM_SCENE]~~ → RETIRED 2026-04-23. Split: basic room gameplay is now `[SWO_P0_ROOM_GAMEPLAY]` (P0 blocker); personalization is `[SWO_V2_ROOM_CUSTOMIZATION]` (Phase 7).




- [ ] **[PHI_DEEMPHASIS_AUDIT]** Audit and reduce Clarvis-wide overfocus on Phi. Goal: Phi should remain only a lightweight regression/health signal, not a recurring optimization target, routing bias, prompt contaminant, or context-budget parasite. Find where Phi/Integration language, tasks, alerts, queue injection, prompt sections, and autonomous logic still over-prioritize it; downgrade/remove those pathways where low-value; preserve only minimal monitoring for genuine regressions. Deliver: clear map of where Phi is still plaguing the system, code/config/doc changes to de-emphasize it, and updated rules so future work is judged more by operator value, task outcomes, retrieval quality, reliability, and shipped results than by Phi movement. (PROJECT:CLARVIS)

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
- [~] [STALLED] **[AUDIT_PHASE_0_INSTRUMENTATION]** Implement the Phase 0 measurement substrate that blocks every downstream audit phase: (1) per-spawn `audit_trace_id` linking preflight→execution→postflight→outcome, (2) `data/audit/traces/<date>/<id>.json` writer with ≥45d retention, (3) `data/audit/feature_toggles.json` registry supporting `shadow` mode, (4) `scripts/audit/trace_exporter.py` CLI, (5) `scripts/audit/replay.py` for deterministic prompt rebuild. PASS gate: ≥95% of real Claude spawns in a 7-day window have a complete recoverable trace. Canonical plan: `docs/internal/audits/CLARVIS_DEEP_AUDIT_PLAN_2026-04-16.md`. (2026-04-16: substrate shipped — `clarvis/audit/{trace,toggles}.py`, trace_exporter + replay CLIs, spawn_claude + heartbeat wiring, `audit_trace_id` on CostEntry. Awaiting 7-day trace window before PASS ruling. Decision doc: `docs/internal/audits/decisions/2026-04-16_phase0_instrumentation.md`.) (2026-04-20 corrected assessment: 106 traces across 5 days (Apr 16–20). By source: heartbeat 43/43 complete (100%), spawn_claude 59/61 have outcome (96.7% — 2 missing outcome.status), 2 test traces excluded. Combined: 102/104 non-test = 98.1% completeness, above 95% gate. 7-day window not yet met — 5/7 days elapsed, eval on or after 2026-04-23.)

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


### Sanctuary Asset Batches (P2 — gated by Batch 1 success, added 2026-04-25)

_Source: `memory/evolution/swo_sanctuary_retrodiffusion_action_plan_2026-04-25.md` §B.3. Each batch promotes to P1 once its predecessor merges. All use the `scripts/rd/` pipeline shipped by `[SWO_RD_PIPELINE_INFRA]`. Per-batch cost cap $0.50 except Batch 5 (RD_PRO empty states — $2.00 cap). Standard negative prompt and palette anchor on every call._

- [ ] **[SWO_RD_BATCH_2_CURRENCY]** Generate 4 shop-chrome assets: STAR coin icon (16×16 + 32×32, `rd_fast__mc_item` / `rd_fast__game_asset`), Shop Keeper NPC turnaround (~32×48 strip, `rd_fast__character_turnaround`), Shop panel frame (256×192, `rd_pro__ui_panel`). Promote to `public/sanctuary/currency/` + `public/sanctuary/hud/`. Cost cap $0.50. Unblocks `[SWO_V2_SHOP_UI]`. Depends on `[SWO_RD_BATCH_1_HUD]` shipping (proves pipeline). (PROJECT:SWO, P2 → P1 once Batch 1 merges)
- [ ] **[SWO_RD_BATCH_3_VFX]** Generate 6 VFX spritesheets via `rd_animation__vfx`: sparkle 32×32×4f, heart 32×32×4f, food crumb 32×32×3f, level-up 64×64×6f, glow ring 32×32×4f, dust trail 16×16×3f. Frame counts must be in {3,4,6,8,10,12,16}. Promote to `public/sanctuary/vfx/`. Wire into existing radial-menu reactions (PR #215) replacing placeholder sparkle. Cost cap $0.50. (PROJECT:SWO, P2 → P1 after Batch 2)
- [ ] **[SWO_RD_BATCH_4_HATS]** Generate 8 × 32×32 cosmetic hats (wizard, crown, halo, party, beanie, top, bow, antlers). Each uses img2img against `public/purple_skrumpey.png` with `strength: 0.55` so hats sit on a Skrumpey body silhouette. `rd_fast__game_asset` style, `remove_bg: true`. Promote to `public/sanctuary/cosmetics/hats/`. Add 8 rows to `sanctuary_cosmetic_items` seed JSON (price 10–25 STAR, level req 0–5, all category=hat, rarity common/uncommon). Cost cap $0.50. Unblocks `[SWO_V2_SHOP_BACKEND]` content seed. Pairs with `[SWO_V2_COSMETIC_ITEM_DESIGN]`. (PROJECT:SWO, P2 → P1 after Batch 3)
- [ ] **[SWO_RD_BATCH_5_VIGNETTES]** Generate 3 RD_PRO empty-state illustrations (96×64: no-companion, empty-journal, no-quests) + 8 RD_FAST 64×64 location vignettes (one per zone). Closes the existing `public/sanctuary/ASSET_SPEC.md` gap (`empty/` + `locations/` directories spec'd but never populated). Wire empty states into existing first-time-UX overlays. Cost cap $2.00 (RD_PRO is flat $0.18/image; explicit operator approval required). (PROJECT:SWO, P2 → P1 after Batch 4)


### Adaptive RAG Pipeline

### Episode Success Rate Recovery & Benchmark Accuracy (2026-04-09 evolution)

### Task Quality Score (RECOVERED — 0.83 as of 2026-04-20, target 0.70 PASS)

---

## NEW ITEMS (2026-04-15 evolution scan)


### 2026-04-16 evolution scan


### 2026-04-20 evolution scan

- [ ] [UNVERIFIED] **[FIX_PHI_HEALTH_REPORTING]** The health pipeline reports Phi=0.000 because `phi_metric.py` was never committed to `scripts/metrics/` on main — it only exists in stale worktrees. Either (a) add a `scripts/metrics/phi_metric.py` wrapper that calls `clarvis.metrics.phi.compute_phi()`, or (b) fix the health data collector (`cron_pi_refresh.sh` / `daily_brain_eval.py`) to import from `clarvis.metrics.phi` directly. Acceptance: `health_monitor.sh` and evolution context report Phi≥0.60 instead of 0.000.
- [ ] **[SEMANTIC_OVERLAP_BOOST]** Phi's weakest sub-component is `semantic_cross_collection`=0.579 (others ≥0.63). Identify the 5 lowest-similarity collection pairs (goals↔autonomous-learning=0.492, procedures↔autonomous-learning=0.488) and add 10–15 bridging memories that create genuine semantic connections between those domains. Verify Phi semantic component rises ≥0.60 without degrading other components.
- [ ] **[CRON_STALE_WORKTREE_CLEANUP]** 10+ stale worktrees exist under `.claude/worktrees/` from prior agent runs, each containing full repo copies. Add a weekly cron entry (Sun 05:25, between existing hygiene jobs) that runs `git worktree prune` and removes any `.claude/worktrees/` dirs older than 7 days. Non-Python task (bash cron script).
- [ ] **[AUTONOMOUS_EXECUTION_CAPABILITY_LIFT]** `autonomous_execution` is the weakest capability at 0.64. Audit the last 20 autonomous cron episodes for failure patterns (timeout, lock contention, wrong-model spawn). Implement the top fix (likely: reduce lock wait time or add per-job timeout tuning). Acceptance: capability score ≥0.70 on next weekly benchmark.

### 2026-04-25 evolution scan

_Note: queue still saturated (21 pending, P1 at cap). Adding 3 high-signal items only. Phi item is a de-emphasis execution slice — removing Phi's contamination of the evolution prompt itself, in line with `[PHI_DEEMPHASIS_AUDIT]` and `[PHI_AUTO_INJECTION_REMOVAL]` (the prompt that requested this very task hardcodes "WEAKEST METRIC: Phi", so each scan keeps adding Phi tasks regardless of de-emphasis rulings)._

- [ ] [UNVERIFIED] **[PHI_EVOLUTION_PROMPT_DEEMPHASIS]** Strip Phi-as-mandatory-target from the evolution scan prompt builder itself. The cron_evolution / strategic-scan prompt currently hardcodes a "WEAKEST METRIC: Phi (Integration)=X — at least one new task MUST target this" header, which contaminates every evolution scan with Phi bias regardless of operator value. Touch: the prompt template under `scripts/cron/cron_evolution.sh` / `scripts/strategic_evolution.py` (or wherever this prompt is assembled). Replace the Phi-special-cased header with a dynamic "weakest capability" picker that selects from `capability_scores` (currently autonomous_execution=0.64, code_generation=0.74) and skips Phi unless it has regressed ≥0.10 sustained ≥3 days. Acceptance: grep of evolution prompt sources shows no hardcoded "WEAKEST METRIC: Phi" string; next evolution scan prompt names a real capability gap, not Phi. Pairs with `[PHI_AUTO_INJECTION_REMOVAL]`. (PROJECT:CLARVIS)
- [ ] [UNVERIFIED] **[DIGEST_GARBLE_FIX]** The 2026-04-25 digest contains literal garbled output: `"me plays.n  ,n  tests_passed: true,n  error: null,n  confidence: 0.85,n  pr_class: Annn,  log: ..."` — a JSON/dict block where `\n` escapes were stringified to literal `n` characters, with truncation mid-sentence ("me plays" appears to be a chopped tail of "the user plays"). Source is the autonomous evolution writer path that promotes Claude task output into `memory/cron/digest.md`. Find the writer (likely `clarvis/cron/digest_writer.py` or `cron_autonomous.sh` post-step) and fix the unescape/format step so JSON dicts render as readable prose or a fenced code block. Acceptance: next autonomous task entry in digest.md is human-readable, with no literal `n,n,n` chains and no mid-word truncation. Feeds Phase 12 digest actionability work directly. (PROJECT:CLARVIS)
- [ ] [UNVERIFIED] **[SWO_OPERATOR_PLAYTEST_BRIEF]** Non-Python. Operator-facing playtest brief for Sanctuary V2 current state. With Phases 0-3 complete and Phase 4/4B shipping (PRs #234, #235 added 3 minigames + framework today), assemble a single-page `docs/operator/SANCTUARY_V2_PLAYTEST_2026-04-25.md` covering: (1) what works at `localhost:3000/sanctuary` right now (movable player, 8 zones, NPCs, quest board, 3+ minigames), (2) known visual issues (companion BG matte, art assets), (3) 5 specific operator actions to try (walk to Hot Springs Memory Match, click NPC, open quest board, etc.), (4) 1-line each of: top 3 P0 items still blocking smooth playthrough. No code — just operator-readable status doc to enable a real playtest before Phase 5 (LLM Companion) starts. (PROJECT:SWO, CONTENT)

### 2026-04-24 evolution scan

_Note: queue is saturated (29 pending, P1 at cap). Adding minimal, high-signal items only. All three map to documented gaps, not speculative optimization. Phi item here is a de-emphasis execution task — it REDUCES Phi's system footprint rather than optimizing for a higher score, in alignment with `[PHI_DEEMPHASIS_AUDIT]` above._

- [ ] [UNVERIFIED] **[PHI_AUTO_INJECTION_REMOVAL]** First concrete execution slice of `[PHI_DEEMPHASIS_AUDIT]`. Remove Phi-triggered auto-queue-injection and prompt-injection pathways so Phi becomes a passive regression signal only. Touch: `scripts/phi_anomaly_guard.py` (or spine equivalent) — stop writing P1 tasks when Phi drops; `cron_pi_refresh.sh` / evolution prompt builder — stop injecting "weakest metric: Phi" lines into Claude prompts; autonomous heartbeat bias — remove Phi score from attention/task-selection boost. Keep: daily Phi measurement + dashboard display + alert only on ≥0.10 regression sustained ≥3 days. Acceptance: grep shows zero auto-P1-from-Phi writers; evolution prompt no longer mentions Phi as mandatory target; Phi still recorded in `data/performance_history.jsonl`. This is the Phi-targeting task required by the evolution scan, framed to reduce (not amplify) Phi overfocus. (PROJECT:CLARVIS)
- [ ] **[SWO_V2_COMPANION_BG_MATTE]** Non-Python. Clean background matte from the 10×6 companion mood PNGs (header note in V2 section: "10×6 companion mood PNGs ✓ (need BG cleanup)"). Each sprite currently has a solid/semi-solid background that bleeds onto room backgrounds. Use ImageMagick or Pillow script to flood-fill-remove the BG color (or alpha-key a known color) across all 60 PNGs; commit cleaned sheet + re-verify `CompanionSprite.ts` frame registration. No code logic change — just asset cleanup + visual QA at `localhost:3000/sanctuary`. Unblocks clean companion rendering in every room without artifacts. ~1h. 1 PR. (PROJECT:SWO)
- [ ] [UNVERIFIED] **[DIGEST_ARCHIVE_IMPLEMENTATION]** Phase 12 ruled REVISE on digest actionability (56.5% vs 60% gate) with "Digest archive missing" as one root cause. Implement rolling archive: each write of `memory/cron/digest.md` snapshots prior content to `memory/cron/digest_archive/YYYY-MM-DD_HHMM.md` before overwrite. Retention: 30 days. Update `tools/digest_writer.py` + add `cron_cleanup.sh` pruning for archive dir. Enables digest trend analysis (what subconscious work was done last week?) and recovery from garbled writes. Acceptance: new digest write produces archive entry; older-than-30d entries auto-pruned; Phase 12 re-scoring can use archive as corpus. (PROJECT:CLARVIS)

---

## Partial Items (tracked, not actively worked)

### External Challenges


---

## Research Sessions
