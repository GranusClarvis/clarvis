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

### Claude Design & Routines Integration (cross-project, added 2026-04-20)

_Source: `docs/CLAUDE_DESIGN_ROUTINES_STRATEGY.md`. Cross-project operating model for Claude Design + Claude Code Routines._


### Star Sanctuary V2 — World-First Rebuild (PROJECT:SWO, reorganized 2026-04-22)

_Sanctuary V2 replaces V1 React panel layout with a Phaser 3 game world. Direction: lobby-first, social, game-like (Tamagotchi + Club Penguin + Habbo). Backend/API layer unchanged — V2 is a frontend revolution._
_V2 Plan: `docs/SANCTUARY_V2_PLAN.md` | Style: `docs/SANCTUARY_STYLE_DOCTRINE.md` | ADR: `docs/SANCTUARY_ADR.md`_
_Status: V1.5 shipped (20 PRs merged through #204). PR #204 open (wallet auth for companion interact). Security audit: 7 findings open (see SWO_TRACKER.md)._
_Asset state: NFT art self-hosted (333 tokens) ✓ | Companion sprites: NOT YET (falls back to NFT art) | Tileset: NOT YET (placeholder OK for Phase 1)_
_Tech stack: Phaser 3 (`phaserjs/template-nextjs`) + Tiled + Colyseus (Phase 3+) + React overlays + EventBus bridge_
_What carries forward: all DB schema, all API routes, wallet auth, bond/XP logic, quest data model, security fixes_
_What's left behind: panel layout, tab navigation, CompanionPanel button grid, monolithic SanctuaryContent.tsx_

#### Phase 0: API Contract Lock & Security (P0 — do before any canvas work)

- **GATE:** All 15 API routes have HTTP-layer tests. All Sanctuary POST routes require wallet auth. Rate limiting on write endpoints. No CRIT/HIGH Sanctuary security findings open.

#### Phase 1: Canvas Foundation (P0 — single-player walking world, 4 PRs)

- [ ] **[SWO_V2_PHASER_SCAFFOLD]** Install Phaser 3 and create the V2 entry point. Add `phaser` dependency. Create `components/sanctuary/PhaserGame.tsx` (dynamic import, ssr:false), `components/sanctuary/EventBus.ts` (React↔Phaser bridge), `game/scenes/BootScene.ts` (asset loader), `game/scenes/WorldScene.ts` (main scene with solid-color background placeholder), `game/config/GameConfig.ts`. Add `SanctuaryV2.tsx` with Phaser canvas + wallet auth bar. Feature flag `NEXT_PUBLIC_SANCTUARY_V2` toggles V1 vs V2. Scaffold from `phaserjs/template-nextjs`. PR renders an empty Phaser canvas at `/sanctuary?v=2`. (PROJECT:SWO)
- [ ] **[SWO_V2_TILED_WORLD_MAP]** Create the world tilemap. Design 8-zone map in Tiled (Town Square center hub, paths to all locations, collision layer, spawn at Town Square). Export as JSON + tileset PNG. Use Kenney free tiles for initial tileset — replaced with doctrine art later. Load in `WorldScene.ts` via `this.load.tilemapTiledJSON()`. Camera follows player. Map ~40×30 tiles at 16px. Depends on `[SWO_V2_PHASER_SCAFFOLD]`. (PROJECT:SWO)
- [ ] **[SWO_V2_PLAYER_COMPANION_MOVEMENT]** Player and companion walking. Create `game/sprites/PlayerSprite.ts` (placeholder 16×16 sprite, 4-direction walk, arrow/WASD input). Create `game/sprites/CompanionSprite.ts` (follows player with lerp 0.15, uses NFT art as static fallback). Click-to-move via `easystar.js`. Camera follows player. Depends on `[SWO_V2_TILED_WORLD_MAP]`. (PROJECT:SWO)
- [ ] **[SWO_V2_LOCATION_ZONES_HUD]** Zone detection and minimal HUD. Create `game/systems/ZoneSystem.ts` — rectangular zones per location, `location-entered`/`location-exited` events via EventBus. Create `components/sanctuary/overlays/CompanionHUD.tsx` — compact status bar (name, mood emoji, bond bar, XP bar from existing API). Location name indicator on zone entry. Depends on `[SWO_V2_PLAYER_COMPANION_MOVEMENT]`. (PROJECT:SWO)
- **GATE:** Player walks around 8-zone world. Zones trigger events. HUD shows companion stats from API. Feature flag toggles V1↔V2. Click-to-move works.

#### Phase 2: Companion Alive (P1 — animated sprites, in-world interactions, 2 PRs)

- [ ] **[SWO_V2_COMPANION_SPRITE_SYSTEM]** Animated companion sprites. Create `game/systems/AnimationSystem.ts` — sprite sheet loader, animation state machine (idle-bob, walk 4-dir, mood variants). Start with 1-2 constellation sheets (32×32px per style doctrine). Idle bob: 2-frame ±1px at 2s. Walk: 4-frame cycle. Mood from API (happy/calm/sleepy/excited/curious). Fallback to static NFT art for constellations without sheets. Depends on `[SWO_V2_LOCATION_ZONES_HUD]`. Needs at least 1 sprite sheet from `[SWO_V2_COMPANION_SPRITE_ART]`. (PROJECT:SWO)
- [ ] **[SWO_V2_IN_WORLD_INTERACTIONS]** Replace button panels with in-world interactions. Create `components/sanctuary/overlays/CompanionMenu.tsx` — radial menu on companion click/tap with Pet/Feed/Talk. On action: call existing `/api/sanctuary/companion/interact`, trigger reaction animation (sparkle on pet, bounce on feed, bubble on talk), floating "+2 Bond"/"+5 XP" text. Remove old CompanionPanel button grid from V2. Depends on `[SWO_V2_COMPANION_SPRITE_SYSTEM]`. (PROJECT:SWO)
- **GATE:** Companion follows player with animation. Mood-driven idle states. Interactions trigger visual reactions + API calls. Bond/XP increments visible.

#### Phase 3: Multiplayer Lobby (P1 — lobby-first social layer, 3 PRs)

- [ ] **[SWO_V2_COLYSEUS_SERVER]** Colyseus multiplayer server. `server/colyseus/` with room-per-location architecture. `PlayerState` schema (wallet, displayName, position, facing, isMoving, companionTokenId, constellation, mood, equippedCosmetics, currentLocation). `LocationRoom.ts` — one room type per location. Player joins on zone enter, leaves on zone exit. Add `colyseus` + `@colyseus/schema` + `colyseus.js` client. Standalone Node.js process (Railway/Fly.io). Depends on `[SWO_V2_LOCATION_ZONES_HUD]`. (PROJECT:SWO)
- [ ] **[SWO_V2_OTHER_PLAYERS_RENDER]** Render other players. Create `game/sprites/OtherPlayerSprite.ts` — spawned on `state.players.onAdd`, destroyed on `onRemove`. Position interpolated from Colyseus state. Name tag above sprite. Companion rendered alongside. Sprite pool for off-camera players. Depends on `[SWO_V2_COLYSEUS_SERVER]`. (PROJECT:SWO)
- [ ] **[SWO_V2_CHAT_BUBBLES]** In-world chat bubbles. Create `components/sanctuary/overlays/ChatInput.tsx` — input bar at bottom. Message → Colyseus room broadcast. `ChatBubble.tsx` — HTML div positioned via `Camera.worldToScreen()`, doctrine-styled (rounded, #0a0a1a bg, Press Start 2P, max 100 chars), fades after 8s. Depends on `[SWO_V2_COLYSEUS_SERVER]`. (PROJECT:SWO)
- **GATE:** 2+ players visible in same zone. Chat messages as bubbles above players. Join/leave works. Smooth interpolation.

#### Phase 4: Diegetic Content & Overlay Migrations (P1 — quests in-world, panels→overlays, 4 PRs)

- [ ] **[SWO_V2_QUEST_NPCS]** Quest givers as NPC sprites. Create `game/sprites/NPCSprite.ts` — static/2-frame idle at map locations. "!" indicator for available quests. Click NPC → `npc-clicked` via EventBus → `QuestDialog.tsx` overlay (description, requirements, rewards, accept/decline). Quest Board at Town Square aggregates all quests. Uses existing `/api/sanctuary/quests`. Remove old QuestsPanel. Depends on `[SWO_V2_LOCATION_ZONES_HUD]`. Needs NPC content from `[SWO_V2_NPC_QUEST_CONTENT]`. (PROJECT:SWO)
- [ ] **[SWO_V2_QUEST_TRACKER_HUD]** Active quest tracker overlay (top-right). 1-3 quests with progress bars. Click to expand. Uses existing quest API. Auto-updates on interaction events. Depends on `[SWO_V2_QUEST_NPCS]`. (PROJECT:SWO)
- [ ] **[SWO_V2_JOURNAL_OVERLAY]** Journal as overlay. Hotkey (J) or HUD icon. Same data from existing `/api/sanctuary/companion/journal`. Scrollable, type filters, pagination. Pixel-art "book" styling per doctrine. Remove old JournalPanel. (PROJECT:SWO)
- [ ] **[SWO_V2_TRAITS_LIBRARY]** Traits at Cosmic Library zone. Auto-opens on zone entry + hotkey (T). Personality traits, progress bars, constellation info. Uses existing `/api/sanctuary/traits`. Remove old TraitsPanel. (PROJECT:SWO)
- **GATE:** Quests discovered in-world via NPCs. All V1 panels (journal, traits, quests) migrated to contextual overlays. No panel layout remnants in V2.

#### Phase 5: LLM Companion (P1 — AI chat, emotional bond, 4 PRs)

_Companion chat confirmed valid for V2. Positioned after world + quests are working. Design ref: `docs/KINKLY_REFERENCE_ANALYSIS.md`._

- [ ] **[SWO_SANCTUARY_CHAT_LLM]** Upgrade chat from templates to LLM (per ADR-002). OpenRouter → Gemini Flash, 15/day rate limit, personality + bond + journal context injection. Create `lib/sanctuary/chatPersonality.ts` (trait→prompt builder), `app/api/sanctuary/companion/chat/route.ts`, `sanctuary_chat_usage` table. `SANCTUARY_CHAT_DRY_RUN` env flag for cost-safe testing. ~$0.05/day at 100 users. (PROJECT:SWO)
- [ ] **[SWO_SANCTUARY_CHAT_PERSISTENCE]** Server-side chat history + companion memory in one PR. (a) `sanctuary_chat_history` table — persist messages, load last 20 on reconnect, send last 10 to LLM. GET endpoint for paginated history. (b) `sanctuary_chat_memories` table (5 categories: owner_identity, preferences, shared_experiences, companion_feelings, recurring_topics). Extract facts via piggyback on chat LLM call (zero extra cost). Inject top 5 memories into system prompt (150 token budget). Depends on `[SWO_SANCTUARY_CHAT_LLM]`. (PROJECT:SWO)
- [ ] **[SWO_SANCTUARY_BOND_STAGES]** Map `bond_score` 0-100 to 4 behavioral stages (Shy/Friendly/Bonded/Devoted). Create `lib/sanctuary/bondStages.ts` with thresholds + prompt context. Inject stage tone guidance into chat system prompt. No schema changes. Depends on `[SWO_SANCTUARY_CHAT_LLM]`. (PROJECT:SWO)
- [ ] **[SWO_V2_COMPANION_CHAT_OVERLAY]** Chat as in-world conversation. "Talk" from radial menu or hotkey (C) opens compact chat near companion. LLM responses as speech bubble above companion + in overlay. Rate limit display (X/15 remaining). Typing simulation (delay by word count, ~45 WPM, 800ms-4000ms, CSS indicator dots). Depends on `[SWO_SANCTUARY_CHAT_LLM]` + `[SWO_V2_IN_WORLD_INTERACTIONS]`. (PROJECT:SWO)
- **GATE:** Companion talks via LLM with personality. Remembers facts across sessions. Bond stages change tone. Chat overlay works in-world with typing simulation.

#### Phase 6: Economy (P2 — cosmetics, shop, layered sprites, 3 PRs)

- [ ] **[SWO_V2_COSMETIC_SPRITE_LAYERS]** Layered cosmetic rendering. Extend `CompanionSprite.ts` with Phaser Container (base + hat + accessory layers, same animation frame). Load cosmetic sheets separately. Read `equipped_cosmetics` from API. `game/systems/CosmeticSystem.ts` for layer composition. Equip/unequip via EventBus. Depends on `[SWO_V2_COMPANION_SPRITE_SYSTEM]`. (PROJECT:SWO)
- [ ] **[SWO_V2_SHOP_BACKEND]** Shop API. Seed `sanctuary_cosmetic_items` with 20-30 items (hats, accessories, backgrounds, animations; 10-50 STAR per STAR_SANCTUARY_PLAN.md). `POST /api/sanctuary/shop/buy` (validate STAR, deduct, add to inventory). `POST /api/sanctuary/inventory/equip`. `GET /api/sanctuary/shop/items` (filterable). Tests for purchase, insufficient balance, double-equip, level gating. Needs content from `[SWO_V2_COSMETIC_ITEM_DESIGN]`. (PROJECT:SWO)
- [ ] **[SWO_V2_SHOP_UI]** Shop overlay at The Bazaar zone. Grid with category tabs. Preview on companion (EventBus preview event). Buy button, STAR balance, "Owned" badge. `InventoryOverlay.tsx` via hotkey (I). Depends on `[SWO_V2_SHOP_BACKEND]` + `[SWO_V2_COSMETIC_SPRITE_LAYERS]`. (PROJECT:SWO)
- **GATE:** Players browse, buy, equip cosmetics. Companions render with equipped items. STAR balance updates correctly.

#### Phase 7: Personal Rooms (P2 — customizable spaces, 2 PRs)

- [ ] **[SWO_V2_ROOM_SCENE]** Room as separate Phaser scene. `game/scenes/RoomScene.ts` — 3×3 grid room (expandable with level). Background/floor from equipped cosmetics. Companion idles in room. Enter via portal in Town Square or profile click. "Return to world" exit. Room data in `equipped_cosmetics` JSON (add room_bg, room_floor). (PROJECT:SWO)
- [ ] **[SWO_V2_ROOM_CUSTOMIZATION]** Decoration placement. Drag-and-place from inventory on 3×3 grid. Layout saved to `sanctuary_companions.room_layout` (new JSON column). Visit other players' rooms (click avatar → "Visit Room"). Visitors see but can't modify. Depends on `[SWO_V2_ROOM_SCENE]`. (PROJECT:SWO)
- **GATE:** Players have personal rooms. Decorations persist. Can visit others' rooms.

#### Phase 8: Polish (P2 — mobile, onboarding, sound, 3 PRs)

- [ ] **[SWO_V2_MOBILE_CONTROLS]** Mobile touch support. Virtual joystick (`rexrainbow/phaser3-rex-notes` plugin or custom). Tap-to-move. Responsive canvas sizing. Touch-friendly overlays (min 44px targets). Test iOS Safari + Android Chrome. Depends on Phases 1-6 stable. (PROJECT:SWO)
- [ ] **[SWO_V2_ONBOARDING]** First-visit tutorial. Detect new player (no companion). Guided: select companion → walk to location → interact → open quest board. Tooltip-style, skip button. State in localStorage. (PROJECT:SWO)
- [ ] **[SWO_V2_SOUND_DESIGN]** Ambient + SFX. Per-location ambient loops (crossfade on zone transition). Interaction SFX (pet sparkle, feed munch, level-up chime). Muted by default, volume slider. Howler.js or Phaser built-in. Need ~8 ambient loops + ~10 SFX. (PROJECT:SWO)
- **GATE:** Mobile-ready with touch controls. New players guided. Audio layer functional (muted by default).

#### Art & Content Track (parallel — start during Phases 1-3)

_These produce assets consumed by code phases. Can be done by humans, AI tools (Aseprite/PixelLab), or commissioned. Style doctrine is binding._

- [ ] **[SWO_V2_WORLD_TILESET_ART]** Doctrine-compliant tileset for world map. Dark cosmic base (#0a0a1a → #1a1a2e), luminous zones, scattered stars, 16×16px tiles. Replace Kenney placeholders from Phase 1. Deliver tileset PNG + updated Tiled map. Sources: Dungeon Crawl + Evil Dungeon (recolor per doctrine palette). (PROJECT:SWO, ART)
- [ ] **[SWO_V2_COMPANION_SPRITE_ART]** Sprite sheets for all 10 constellations. 32×32px: walk (4 dir × 4 frames), idle bob (2 frames), 5 moods (happy/excited/calm/sleepy/curious, 2-3 frames each), interaction reactions (pet/feed/play, 4 frames each). ~50 frames per constellation, 500 total. PNG sheets + JSON atlas. Per-constellation accent colors from style doctrine. (PROJECT:SWO, ART)
- [ ] **[SWO_V2_NPC_QUEST_CONTENT]** Design 3-5 NPCs (names, locations, personality, sprite spec). Write quest dialog for 5 daily errands + 3 weekly adventures. Map to `sanctuary_quests` table format. JSON seed file + NPC placement for Tiled map. (PROJECT:SWO, CONTENT)
- [ ] **[SWO_V2_COSMETIC_ITEM_DESIGN]** 20-30 items: 8 hats, 6 accessories, 5 backgrounds, 5 floors, 4 animations, 2 seasonal. Each: name, category, rarity (common/uncommon/rare/epic), STAR price (10-50), level req (0-15), pixel art spec. Seed JSON for `sanctuary_cosmetic_items`. (PROJECT:SWO, CONTENT)

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

---

## Partial Items (tracked, not actively worked)

### External Challenges


---

## Research Sessions
