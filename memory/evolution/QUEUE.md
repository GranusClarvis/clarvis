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

- [ ] **[CRON_SYNC_STASH_RECOVERY_REF]** `scripts/cron/cron_env.sh::sync_workspace()` captures `_stash_ref` via `git stash list -1 --format="%H"`, which yields an opaque commit hash, while the recovery instructions reference stash workflows. Store/log a usable stash selector (`stash@{n}`) or both selector+hash so operators can recover stranded work without guesswork.

## P1 — This Week

### Claude Design & Routines Integration (cross-project, added 2026-04-20)

_Source: `docs/CLAUDE_DESIGN_ROUTINES_STRATEGY.md`. Cross-project operating model for Claude Design + Claude Code Routines._


### Star Sanctuary — V2/V3 Operating Model (PROJECT:SWO, reconciled 2026-04-25)

_Source: `memory/evolution/swo_sanctuary_v2_v3_replan_2026-04-25.md` + execution `memory/evolution/swo_sanctuary_v3_alignment_execution_2026-04-25.md`. Sanctuary now runs as two parallel tracks sharing all game logic. V2 = gameplay testbed (`?v=2`). V3 = production tile-based pixel-art rebuild (`?v=3`)._

_**Canonical V3 doc:** `docs/SANCTUARY_V3.md` (in SWO repo). Locked palette: `public/sanctuary-v3/palettes/forgotten-memories.png`. Pipeline: `scripts/v3/{generate,normalize,rd-client}.mjs`._

_**Shipped V3 reality (commits `7149ed2 → c2efa0c` on dev):** canonical plan + locked FM palette + custom RD style → 11 NPC walking sheets → 15 themed props → 8 building exteriors → tilemap-driven `overworld.json` with animated water → door transitions + procedural room interiors → walkable test scene at `?v=3`._

_**Local testing (verified 2026-04-25):** `npm run dev` (Next.js) + `npm run colyseus:dev` in SWO workspace; visit `localhost:3000/sanctuary?v=3` for V3 (or `?v=2` for V2). Pre-PR: `npm run type-check && npm run lint && npm run build` (all green at branch `clarvis/star-world-order/t0425200011-0a6c`). RD pipeline gate: `RD_API_KEY=... node scripts/v3/generate.mjs --check-cost`._

_**Lane discipline:** default new feature work to SHARED. Only fork into V2 or V3 when the work touches Phaser scenes or assets specifically. Naming: `[SWO_SHARED_*]` / `[SWO_V2_*]` / `[SWO_V3_*]`._

#### SHARED — both V2 + V3 benefit (default lane)

- [ ] **[SWO_SHARED_SHOP_DIALOG]** ShopDialog React overlay (`components/sanctuary/overlays/ShopDialog.tsx`). Backend shipped (`5aa2965` cosmetic shop + inventory + equip API). Triggered by NPC interaction (Shop Keeper or Quest Board area) + hotkey (B). Grid layout with category tabs (Hats / Accessories / Backgrounds / Animations). Live companion preview via EventBus. Buy button with STAR price/balance/owned/level-req. Inventory tab (hotkey I) with equip/unequip. Mounts in BOTH SanctuaryV2.tsx and SanctuaryV3.tsx. (PROJECT:SWO, P1)
- [ ] **[SWO_SHARED_QUEST_DIALOG_CONTENT]** Write quest dialog JSON for 5 daily errands + 3 weekly adventures. Map to `sanctuary_quests` table format. JSON seed file. NPC names/zones/locations defined in both `npcDefinitions.ts` (V2) and `game/v3/config/npcDefinitionsV3.ts` (V3). Same dialog data drives both renderers via QuestDialog overlay. (PROJECT:SWO, CONTENT, P1)
- [ ] **[SWO_SHARED_COSMETIC_ITEM_DESIGN]** 20-30 cosmetic items: 8 hats, 6 accessories, 5 backgrounds, 5 floors, 4 animations, 2 seasonal. Each: name, category, rarity (common/uncommon/rare/epic), STAR price (10-50), level req (0-15), pixel-art spec. Seed JSON for `sanctuary_cosmetic_items`. **Sprite generation forks: V2 cosmic palette under `public/sanctuary/cosmetics/`; V3 FM palette under `public/sanctuary-v3/cosmetics/`. This item owns the shared data spec only.** (PROJECT:SWO, CONTENT, P2)
- [ ] **[SWO_SHARED_ONBOARDING]** Full guided tutorial extending Spawn Fox intro. Detect new player. Fox walks player through: select companion → walk to first room → interact with NPC → open quest board → try first minigame. Tooltip arrows + highlight zones. Skip button. State in `sanctuary_player_state`. Engine-agnostic (overlays + EventBus events); mounts on V2 and V3. (PROJECT:SWO, P2)
- [ ] **[SWO_SHARED_SOUND_DESIGN]** Howler.js-based ambient + SFX service (`lib/sanctuary/audio.ts` + EventBus listener). Per-zone ambient loops (crossfade on zone-change event), interaction SFX (pet sparkle, feed munch, level-up chime). Muted by default, volume slider in WelcomeDialog/settings overlay. Both Phaser scenes emit `zone:enter` / `zone:leave` / `companion:react` events; service consumes them. ~8 ambient loops + ~10 SFX. Audio asset folder shared at `public/audio/sanctuary/`. (PROJECT:SWO, P2)
- [ ] **[SWO_SHARED_VFX_TRIGGER_API]** Shared EventBus contract for companion reactions: `companion:vfx:sparkle`, `companion:vfx:heart`, etc. V2 RadialMenu + V3 RadialMenu both publish these events. Sprite sheets differ per track — V2 stays on emoji/cosmic palette; V3 uses FM palette via `[SWO_V3_VFX_SPRITES]`. This task is the trigger contract only. (PROJECT:SWO, P2)
- [ ] **[SWO_SHARED_MOBILE_OVERLAYS]** Responsive React overlay sweep: min 44 px hit targets, fluid layout under 768 px, touch-friendly chat input + radial menu. Excludes Phaser canvas joystick (handled per-track in `[SWO_V3_MOBILE_CANVAS]`). (PROJECT:SWO, P2)
- [ ] **[SWO_SHARED_EXPEDITIONS]** Multi-step expedition adventures with narrative choices. Quest data model extension; UI is overlay-only. Benefits both V2 and V3 automatically. (PROJECT:SWO, P2)
- [ ] **[SWO_SHARED_CHAT_MEMORY_CONSOLIDATION]** Weekly batch: merge duplicate companion memories, decay old emotions, summarize recurring topics. Backend job; depends on chat persistence shipped in `1d44697`. (PROJECT:SWO, P2)

#### V3 — Production Rebuild (`?v=3`, FM palette, locked)

_**Phase status (per `docs/SANCTUARY_V3.md` §14, commits `7149ed2 → c2efa0c`):** 0 plan ✅ | 1 FM tileset ✅ | 2 RD pipeline ✅ | 3 first-NPC sign-off ✅ | 4 bulk NPC+prop ✅ | 5 buildings + walkable test scene ✅ | 6 tilemap+water ✅ | 7 door transitions + procedural rooms ✅ | 8 polish (HUD/UI/font/particles) ⏳ | 9 hand-authored room interiors + parity audit ⏳._

- [ ] **[SWO_V3_PIPELINE_HARDENING]** Harden `scripts/v3/` against credit waste before next batch. Add: (a) `scripts/v3/asset-manifest-status.json`-style record with prompt_hash dedup before any RD call (refuse if `status=approved` & hash matches); (b) per-batch + per-day cost ceilings via env (`RD_BATCH_CAP_USD=0.50`, `RD_DAILY_CAP_USD=5.00`), abort with override flag; (c) `flock /tmp/rd_v3_generate.lock` around all writes; (d) append-only `scripts/v3/requested.jsonl` log of every POST (success + error); (e) reconciliation script `scripts/v3/rd-reconcile.mjs` that sums jsonl vs `GET /credits`. Acceptance: `RD_DRY_RUN=1 node scripts/v3/generate.mjs --only spawn-fox` produces stub PNG; second run with same hash refuses. (PROJECT:SWO, P1)
- [ ] **[SWO_V3_HUD_ICONS]** Generate 12 × 16×16 HUD icons (pet/feed/talk/send/sleep + bond/xp/energy/hunger/level + quest/journal) via the V3 pipeline + custom RD style (`scripts/v3/style-id.txt = user__swo_forgotten_sanctuary_0dbd7f09`), `bypass_prompt_expansion: true`, `remove_bg: true`. Use FM palette (no neon `#ffd700` — antique gold `#d4a445` per V3 §4.2). Replace emoji in `CompanionHUD.tsx` and `QuestBoard.tsx` (shared overlays — both V2 and V3 benefit). Cost cap $0.50. Single PR. Depends on `[SWO_V3_PIPELINE_HARDENING]`. (PROJECT:SWO, P1)
- [ ] **[SWO_V3_FONT_SWAP]** Replace `Press Start 2P` globally with a SNES-mood bitmap font that matches the FM palette mood (V3 doc §14 phase 1, currently used for nameTags + HUD in `WorldSceneV3` / `RoomSceneV3` / `NPCSpriteV3`). Affects both V2 and V3 chrome — choice is driven by V3 doctrine. ~1h. (PROJECT:SWO, P1)
- [ ] **[SWO_V3_OVERWORLD_MAP_DETAIL]** Currently `public/sanctuary-v3/maps/overworld.json` is 60×40 tiles with **only 4 unique tile gids** (gid=2 grass fills 79% of the map; gid=3 ≈10%; gid=66/67 trace). The walkable test scene reads as a flat green carpet around 8 building anchors with one water rectangle. Author a richer ground composition: stone/dirt path threading buildings, grass tufts/decoration variation, fence segments, terrain transitions, layered tree clusters, additional water bodies. Use existing FM tileset (2048×2048, 4096 tiles available). Tools: Tiled or Sprite Fusion. Out of scope: new RD generation. Acceptance: ground+ground_decoration layers use ≥30 unique tile gids; visual diff at `?v=3` shows readable RPG-route composition not tactical-map flatness. (PROJECT:SWO, P1)
- [ ] **[SWO_V3_ROOM_INTERIOR_MAPS]** Hand-author Tiled JSON maps for the 8 room interiors (Hot Springs, Observatory, Training Grounds, Star Garden, Cosmic Library, Nebula Kitchen, Dream Hollow, Aura Forge) replacing the procedural floor/wall renderer in `RoomSceneV3.renderInterior()`. Layers per V3 §12: `ground` → `ground_decoration` → `objects` → `collision` → `npcs` → `doors`. 30×20 tiles each. Use FM tileset + already-generated themed props. NPC placement matches `npcDefinitionsV3.ts`. Wire `RoomSceneV3` to `load.tilemapTiledJSON` per door target. Operator-authored or Sprite Fusion procedural-then-refine. (PROJECT:SWO, P1)
- [ ] **[SWO_V3_SHOP_CHROME]** Generate 4 shop-chrome assets in FM palette via `scripts/v3/`: STAR coin icon (16×16 + 32×32), Shop Keeper NPC walking sheet (48×48 4-direction `rd_animation__four_angle_walking`), Shop panel 9-slice (256×192). Promote to `public/sanctuary-v3/{npcs,props,ui}/`. Cost cap $0.50. Pairs with `[SWO_SHARED_SHOP_DIALOG]`. Depends on `[SWO_V3_PIPELINE_HARDENING]`. (PROJECT:SWO, P1)
- [ ] **[SWO_V3_VFX_SPRITES]** Generate 6 VFX spritesheets in FM palette via `rd_animation__vfx`: sparkle 32×32×4f, heart 32×32×4f, food crumb 32×32×3f, level-up 64×64×6f, glow ring 32×32×4f, dust trail 16×16×3f. Frame counts in {3,4,6,8,10,12,16}. Promote to `public/sanctuary-v3/vfx/`. Wire to `[SWO_SHARED_VFX_TRIGGER_API]` events. Cost cap $0.50. (PROJECT:SWO, P2)
- [ ] **[SWO_V3_COSMETIC_HATS_V1]** Generate 8 × 32×32 cosmetic hats in FM palette (wizard, crown, halo, party, beanie, top, bow, antlers). Img2img on the V3 `player-wanderer.png` sprite (NOT V2's `purple_skrumpey.png`). `strength: 0.55`, `remove_bg: true`. Promote to `public/sanctuary-v3/cosmetics/hats/`. Add 8 rows to `sanctuary_cosmetic_items` seed JSON. Cost cap $0.50. Pairs with `[SWO_SHARED_COSMETIC_ITEM_DESIGN]`. (PROJECT:SWO, P2)
- [ ] **[SWO_V3_UI_RESTYLE]** Restyle V3 UI chrome to FM tones (V3 §14 phase 8). Buttons, panels, dialog frames use FM stone/wood/parchment colors. 9-slice frames cropped from FM tileset where possible; minimal RD only for hero panels. V2 keeps cosmic chrome to remain the "obvious testbed" visually. (PROJECT:SWO, P2)
- [ ] **[SWO_V3_PARTICLES_AMBIENT]** Add ambient particle system within accent budget (≤2% pixels): firefly drift in Star Garden, steam in Hot Springs, rune sparkle in Aura Forge. Reuses `[SWO_SHARED_VFX_TRIGGER_API]` style. (PROJECT:SWO, P2)
- [ ] **[SWO_V3_MOBILE_CANVAS]** V3 Phaser touch joystick (rex-rainbow plugin or custom). Tap-to-move on tilemap. Responsive zoom (1× / 2× selection by viewport). Pairs with `[SWO_SHARED_MOBILE_OVERLAYS]`. (PROJECT:SWO, P2)
- [ ] **[SWO_V3_FEATURE_PARITY_AUDIT]** Walk every V2 feature (minigames, quest board, companion chat, shop, multiplayer, journal, traits) and verify it works at `?v=3`. Gap list → individual follow-up tasks. Operator decides whether to drop V2 entirely after this audit. (PROJECT:SWO, P2)

#### V2 — Testbed (`?v=2`, gameplay-feature host, visuals are placeholder by design)

_All Phase 0–6 backbone shipped (PRs #205–#219, #232–#240, plus `5aa2965`/`fd9924c`/`72d6202`). V2 stays as iteration host for game logic. Visual fixes only matter where they unblock testing._

- [ ] **[SWO_V2_COMPANION_BG_MATTE]** Run shipped `0f80a91 matte_companion_sprites.mjs` against the 60 mood PNGs in `public/sanctuary/companions/` and commit the cleaned outputs. Visual QA at `localhost:3000/sanctuary?v=2`. ~30 min, 1 PR. V3 unaffected (V3 keeps existing constellation PNGs per `docs/SANCTUARY_V3.md` §13). (PROJECT:SWO, P2)
- [ ] **[SWO_V2_STATUS_VERIFY]** Verify status of `[SWO_V2_STAR_GARDEN_DOOR]` and `[SWO_V2_NPC_REAL_SPRITES]` against dev HEAD. If still broken, scope a single fix PR; otherwise close them in SWO_TRACKER.md. Operator direction is "keep V2 as testbed for game logic" — door + NPC fixes only matter if operator still iterates on V2 worldmap. (PROJECT:SWO, P2)
- [ ] **[SWO_V2_DEPRECATION_GATE]** Define the explicit gate at which V2 stops getting visual fixes. V3 doc §0 says "V2 stays until V3 reaches feature parity." Add an operational checklist (which V2-only assets are no longer maintained) so we don't burn cycles on V2 polish that V3 will replace. (PROJECT:SWO, P2)

#### Sanctuary — Post-V3 / strategic

- [ ] **[SANCTUARY_STAR_CURRENCY_DECISION]** STAR on Monad (soulbound vs transferable vs hybrid). Blocks on-chain cosmetic minting. Off-chain backend already shipped (`fd9924c`). Not needed for V2/V3 MVPs. See STAR_SANCTUARY_PLAN.md §3.3. (PROJECT:SWO, P2)

#### Retired Items (superseded by V2/V3 split or shipped)

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


### Sanctuary Asset Batches — RETIRED 2026-04-25

_Source: `memory/evolution/swo_sanctuary_v2_v3_replan_2026-04-25.md` §B.2. The cosmic-palette V2 RD pipeline never shipped; V3 has its own working pipeline at `scripts/v3/{generate,normalize,rd-client}.mjs` with the FM palette anchor and the custom RD style ID `user__swo_forgotten_sanctuary_0dbd7f09`. The V2 batches are RETIRED and their scope mapped to V3-lane equivalents:_

- ~~[SWO_RD_BATCH_2_CURRENCY]~~ → `[SWO_V3_SHOP_CHROME]` (FM palette, V3 pipeline)
- ~~[SWO_RD_BATCH_3_VFX]~~ → `[SWO_SHARED_VFX_TRIGGER_API]` (overlay contract) + `[SWO_V3_VFX_SPRITES]` (FM-palette sheets)
- ~~[SWO_RD_BATCH_4_HATS]~~ → `[SWO_V3_COSMETIC_HATS_V1]` (img2img on V3 player, not `purple_skrumpey.png`)
- ~~[SWO_RD_BATCH_5_VIGNETTES]~~ → DROPPED (V2-polish-only; revisit if operator wants V3 empty states)


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
