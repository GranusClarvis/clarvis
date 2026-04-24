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

- [ ] **[SWO_P0_CHAT_LOCAL_ECHO]** Chat messages vanish silently if Colyseus server isn't running (no room joined). No local echo — message must roundtrip through server before appearing. Fix: in `useMultiplayer.ts:handleSendChat`, emit `'chat-message'` locally immediately with `isLocal: true` before sending to Colyseus. Deduplicate server echo by matching text+sessionId within 2s. If no room connected, still show local echo. File: `lib/colyseus/useMultiplayer.ts:172-176`. ~30 min. (PROJECT:SWO)
- [ ] **[SWO_P0_COMPANION_BG_MATTE]** Companion mood PNGs under `public/sanctuary/companions/<constellation>/<mood>.png` have non-transparent backgrounds. Create `scripts/matte_companion_sprites.mjs`: detect dominant corner color per PNG, replace matching pixels with alpha (tolerance ~15). Or provide a batch script for operator to re-export. Verify all 60 PNGs render clean in-game. ~1h. (PROJECT:SWO)
- [ ] **[SWO_P0_ROOM_GAMEPLAY]** RoomScene is a static image viewer (bg + title + exit button). No player spawning, no movement, no collision, no companion. Fix: spawn PlayerSprite at southern entrance (x=ROOM_W/2, y=ROOM_H-60), add WASD+click-to-move inside room, camera follow with bounds 1448×1086, companion follows. Per-room collision: paint red masks on room PNG copies → run `extract_sanctuary_layout.mjs` variant → store in `game/config/roomLayouts.ts` keyed by `RoomKey`. Exit trigger zone at bottom center. File: `game/scenes/RoomScene.ts` (currently 79 lines). ~3-4h. (PROJECT:SWO)
- **GATE:** Overworld collision works ✅. All 8 rooms enterable via doors (including Star Garden). NPCs show real sprite art. Chat works offline (local echo). Companion sprites render without background artifacts. Rooms are playable spaces with movement and collision.

#### Phase 4: Diegetic Content & Overlay Migrations (P1 — partially done)

_Quest NPCs with click-to-dialog and quest board shipped (PR #219). Remaining: 3 overlay migrations + 3 new content tasks from operator brief._

**Overlay migrations (carry-forward):**
- [ ] **[SWO_V2_QUEST_TRACKER_HUD]** Active quest tracker overlay (top-right). 1-3 quests with progress bars. Click to expand. Uses existing quest API. Auto-updates on interaction events. (PROJECT:SWO)
- [ ] **[SWO_V2_JOURNAL_OVERLAY]** Journal as overlay. Hotkey (J) or HUD icon. Same data from existing `/api/sanctuary/companion/journal`. Scrollable, type filters, pagination. Pixel-art "book" styling per doctrine. Remove old JournalPanel. (PROJECT:SWO)
- [ ] **[SWO_V2_TRAITS_LIBRARY]** Traits at Cosmic Library zone. Auto-opens on zone entry + hotkey (T). Personality traits, progress bars, constellation info. Uses existing `/api/sanctuary/traits`. Remove old TraitsPanel. (PROJECT:SWO)

**New diegetic content (from operator split brief 2026-04-23):**
- [ ] **[SWO_V2_SPAWN_FOX_INTRO]** Place Spawn Fox NPC near spawn point (724, 700) using `Spawn_Fox_Sprite.png`. First-time-per-wallet welcome dialog: explains WASD/click-to-move, [E] to enter rooms, companion radial menu. Track intro state in `sanctuary_companions` (add `intro_completed INTEGER DEFAULT 0` column) or new `sanctuary_player_state` table keyed by wallet. On return visits Fox stays as help NPC with shorter repeat dialog. Depends on `[SWO_P0_NPC_REAL_SPRITES]` for sprite loading pipeline. Add Spawn Fox to `npcDefinitions.ts` with zone "Town Square". ~1-2h. (PROJECT:SWO)
- [ ] **[SWO_V2_ROOM_NPCS]** Place one themed NPC inside each room using matching sprite sheets. NPC↔room mapping: Springs Duck → Hot Springs, Observatory Owl → Observatory, Training Wolf → Training Grounds, Kitchen Bunny → Nebula Kitchen, Garden Ent → Star Garden, Hollow Moth → Cosmic Library, Dream Sheep → Dream Hollow, Aura Golem → Aura Forge. Load sprites in `BootScene.ts`, render via `NPCSprite` inside `RoomScene.ts`. Each NPC is interactive (click for dialog, hooks for future quest/minigame triggers). Extend `npcDefinitions.ts` with `roomPlacement` field. Depends on `[SWO_P0_ROOM_GAMEPLAY]` (rooms need player movement first) + `[SWO_P0_NPC_REAL_SPRITES]`. ~2h. (PROJECT:SWO)
- [ ] **[SWO_V2_QUEST_HUB]** Enhance Quest Board NPC in Town Square as central quest aggregator. Quest Board overlay shows all available quests grouped by source room/NPC. Category tabs: All / Room / Daily / Weekly. Each entry shows NPC name, room location, rewards. "Go" button highlights target door on overworld. Builds on existing `QuestBoard.tsx` overlay + `sanctuary_quests` table (already has 12 seeded quests). ~2h. (PROJECT:SWO)
- **GATE:** Quests discovered in-world via NPCs. All V1 panels (journal, traits, quests) migrated to contextual overlays. No panel layout remnants in V2. Spawn Fox greets first-time visitors. Each room has its themed NPC. Quest Board aggregates all quests.

#### Phase 4B: Room Activities & Minigames (P1 — from operator split brief, 4-5 PRs)

_Operator requirement: rooms must have gameplay, not just scenery. Training Grounds for leveling, timed quests with away-state, shared minigame plumbing, 8 room-specific minigames. All depend on `[SWO_P0_ROOM_GAMEPLAY]` + `[SWO_V2_ROOM_NPCS]`._

- [ ] **[SWO_V2_TIMED_QUESTS]** Send Skrumpey on timed quests from room NPC dialogs. Timer stored in existing `activity_ends_at` column (`sanctuary_companions` table). Away-state HUD in `CompanionHUD.tsx`: quest name, countdown timer, "Claim" button on completion. Companion sprite shows sleeping/away animation during quest. Claim flow calls existing `/api/sanctuary/companion/complete-activity` route, grants XP + bond + STAR. Quest durations: 5min / 15min / 1h / 4h / 8h. Companion unavailable for interactions while on quest. ~3h. 1 PR. (PROJECT:SWO)
- [ ] **[SWO_V2_TRAINING_GROUNDS_XP]** Training Grounds room as Skrumpey leveling zone. Per-token XP persistence: extend `sanctuary_companions` with `xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1`. Training activities via Training Wolf NPC dialog: choose training type (Endurance/Agility/Wisdom) → short timer → XP awarded. Level-up thresholds: 100/300/600/1000/1500 XP. Level-up celebration animation. Level displayed in CompanionHUD. Higher levels unlock harder training + better rewards. Depends on `[SWO_V2_ROOM_NPCS]`. ~3-4h. 1 PR. (PROJECT:SWO)
- [ ] **[SWO_V2_MINIGAME_PLUMBING]** Shared minigame framework. Abstract `MinigameScene` base class (extends `Phaser.Scene`): score tracking, 60-90s timer, pause/resume, pixel-art result screen (score + STAR earned + personal best), exit-to-room flow. Score API: `POST /api/sanctuary/minigame/score` (wallet, game_id, score, token_id). New `sanctuary_minigame_scores` table (wallet_address, token_id, game_id, score, played_at). Leaderboard: `GET /api/sanctuary/minigame/leaderboard?game_id=X` (top 20). Entry from room NPC → minigame scene → result → back to room. STAR rewards: first play bonus (25) + score-based (1-10). ~4h. 1 PR. (PROJECT:SWO)
- [ ] **[SWO_V2_ROOM_MINIGAMES]** 8 room-specific minigames using shared framework. Implement 2-3 per PR. Each: 200-400 lines, Phaser arcade physics, 60-90s rounds, awards STAR + XP. NPC in each room triggers its minigame. Proposed games: (1) Hot Springs — Memory match (flip tiles to match Skrumpey moods), (2) Observatory — Star connect (draw lines between stars to form constellations), (3) Training Grounds — Obstacle course (side-scroll dodge, complements XP leveling), (4) Nebula Kitchen — Cooking rhythm (time button presses to recipe steps), (5) Star Garden — Plant & grow (water/tend for fastest bloom), (6) Cosmic Library — Lore trivia (multiple-choice Sanctuary knowledge), (7) Dream Hollow — Dream catcher (catch falling dream orbs, avoid nightmares), (8) Aura Forge — Forge hammer (timing/anvil beat game). ~2-4h each, 3-4 PRs total. (PROJECT:SWO)
- **GATE:** Every room has interactive gameplay beyond scenery. Timed quests show away-state in HUD with countdown. Training Grounds grant XP that persists and levels up companions. At least 4/8 minigames playable with score tracking. Leaderboards display.

#### Phase 5: LLM Companion (P1 — AI chat, emotional bond, 4 PRs)

_Companion chat confirmed valid for V2. Positioned after world + quests are working. Design ref: `docs/KINKLY_REFERENCE_ANALYSIS.md`._

- [ ] **[SWO_SANCTUARY_CHAT_LLM]** Upgrade chat from templates to LLM (per ADR-002). OpenRouter → Gemini Flash, 15/day rate limit, personality + bond + journal context injection. Create `lib/sanctuary/chatPersonality.ts` (trait→prompt builder), `app/api/sanctuary/companion/chat/route.ts`, `sanctuary_chat_usage` table. `SANCTUARY_CHAT_DRY_RUN` env flag for cost-safe testing. ~$0.05/day at 100 users. (PROJECT:SWO)
- [ ] **[SWO_SANCTUARY_CHAT_PERSISTENCE]** Server-side chat history + companion memory in one PR. (a) `sanctuary_chat_history` table — persist messages, load last 20 on reconnect, send last 10 to LLM. GET endpoint for paginated history. (b) `sanctuary_chat_memories` table (5 categories: owner_identity, preferences, shared_experiences, companion_feelings, recurring_topics). Extract facts via piggyback on chat LLM call (zero extra cost). Inject top 5 memories into system prompt (150 token budget). Depends on `[SWO_SANCTUARY_CHAT_LLM]`. (PROJECT:SWO)
- [ ] **[SWO_SANCTUARY_BOND_STAGES]** Map `bond_score` 0-100 to 4 behavioral stages (Shy/Friendly/Bonded/Devoted). Create `lib/sanctuary/bondStages.ts` with thresholds + prompt context. Inject stage tone guidance into chat system prompt. No schema changes. Depends on `[SWO_SANCTUARY_CHAT_LLM]`. (PROJECT:SWO)
- [ ] **[SWO_V2_COMPANION_CHAT_OVERLAY]** Chat as in-world conversation. "Talk" from radial menu or hotkey (C) opens compact chat near companion. LLM responses as speech bubble above companion + in overlay. Rate limit display (X/15 remaining). Typing simulation (delay by word count, ~45 WPM, 800ms-4000ms, CSS indicator dots). Depends on `[SWO_SANCTUARY_CHAT_LLM]`. (PROJECT:SWO)
- **GATE:** Companion talks via LLM with personality. Remembers facts across sessions. Bond stages change tone. Chat overlay works in-world with typing simulation.

#### Phase 6: Economy (P2 — STAR currency, shop, cosmetics, 4 PRs)

_Operator requirement: STAR currency storage + ShopDialog/API. All economy is off-chain for V2 (on-chain decision deferred per `SANCTUARY_STAR_CURRENCY_DECISION` in Post-V2)._

- [ ] **[SWO_V2_STAR_CURRENCY]** STAR currency storage and economy foundation. New `sanctuary_star_balance` table (`wallet_address TEXT PRIMARY KEY, balance INTEGER DEFAULT 0, lifetime_earned INTEGER DEFAULT 0, updated_at DATETIME`). Internal earn endpoint: `POST /api/sanctuary/star/earn` (called by quest/activity/minigame completion — server-side only, not public). Spend endpoint: `POST /api/sanctuary/star/spend` (called by shop buy). Balance query: `GET /api/sanctuary/star/balance?wallet=X`. STAR displayed in CompanionHUD (star icon + balance, top bar). Earn rates: quest completion 10-50, minigame first-play 25, daily login 5, activity completion 5-20, level-up bonus 50. Prerequisite for `[SWO_V2_SHOP_BACKEND]`. ~2h. 1 PR. (PROJECT:SWO)
- [ ] **[SWO_V2_COSMETIC_SPRITE_LAYERS]** Layered cosmetic rendering. Extend `CompanionSprite.ts` with Phaser Container (base + hat + accessory layers, same animation frame). Load cosmetic sheets separately. Read `equipped_cosmetics` from API. `game/systems/CosmeticSystem.ts` for layer composition. Equip/unequip via EventBus. (PROJECT:SWO)
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
