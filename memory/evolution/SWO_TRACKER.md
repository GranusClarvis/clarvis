# Star World Order — Project Tracker

_Dedicated tracker for SWO/Sanctuary project work. Separated from main QUEUE.md per PROJECT_LANES.md governance._
_Project lane: SWO | Status: ACTIVE | Operator-directed._

## Delivery Criteria

Each item must produce a **PR or working feature branch** in the SWO repo.
Planning docs, queue items, and brand positioning do NOT count as delivery.

## Current Sprint — Foundation PRs

| # | Task | Branch | PR | Status |
|---|------|--------|----|--------|
| 1 | [SANCTUARY_ACTIVE_COMPANION_API] Active companion endpoints | feat/sanctuary-companion-panel | #178 | Done |
| 2 | [SANCTUARY_BOOTSTRAP_STATE] First-time bootstrap path | feat/sanctuary-companion-panel | #178 | Done |
| 3 | [SANCTUARY_TEST_FIXTURES] Test fixtures/seeds | feat/sanctuary-companion-panel | #178 | Done |
| 4 | [SANCTUARY_SUBSITE_SHELL] `/sanctuary` route shell | ec216e3 (dev) | — | Done |
| 5 | [SANCTUARY_COMPANION_PANEL] V1 companion dashboard | feat/sanctuary-companion-panel | #178 | Done |

## Completed PRs

| # | PR | Title | Date |
|---|-----|-------|------|
| 1 | #175 | ci: add test workflow | 2026-03-02 |
| 2 | #178 | feat: V1 companion dashboard with quick actions | 2026-04-16 |
| 3 | #182 | fix: replace 14 `any` types with narrow sanctuary row types | 2026-04-17 |
| 4 | #183 | feat: sanctuary interactables V1 + enhanced world map | 2026-04-18 |
| 5 | #184 | fix: social connections auth | 2026-04-18 |
| 6 | #185 | feat: sanctuary interactables V1 + enhanced world map | 2026-04-19 |
| 7 | #186 | feat: sanctuary journal system | 2026-04-20 |
| 8 | #187 | feat: open Sanctuary to all Skrumpey holders | 2026-04-20 |
| 9 | #188 | feat: sanctuary V1.5 — companion chat, trait evolution, seasonal quests | 2026-04-20 |
| 10 | #189 | feat: sanctuary style doctrine + sprite/animation infrastructure | 2026-04-20 |
| 11 | #192 | feat: self-hosted Skrumpey corpus + Sanctuary integration | 2026-04-21 |
| 12 | #177 | fix: verify governance voting power server-side | 2026-04-21 |
| 13 | #180 | fix(adminAuth): persist used nonces in SQLite to prevent replay | 2026-04-21 |
| 14 | #181 | chore(contracts): archive StarForge V1-V4 + Testing_casino | 2026-04-21 |
| 15 | #183 | fix: harden raffle randomness — CSPRNG + combined entropy | 2026-04-18 |
| 16 | #184 | fix: social connections auth | 2026-04-18 |
| 17 | #191 | feat: sanctuary-map-bg CSS class with procedural star map | 2026-04-21 |
| 18 | #194 | fix: replace silent .catch with error states in SanctuaryContent | 2026-04-21 |
| 19 | #195 | fix: wrap all JSON.parse(attributes_json) calls in try-catch | 2026-04-21 |
| 20 | #204 | feat: wallet auth for sanctuary companion interact | 2026-04-22 |
| 21 | #205 | feat: add Zod input validation to Sanctuary API routes | 2026-04-22 |
| 22 | #206 | test: E2E HTTP-layer tests for all 16 Sanctuary API routes | 2026-04-22 |
| 23 | #207 | security: SQLite rate limiting + wallet auth on all Sanctuary POST routes | 2026-04-22 |
| 24 | #208 | feat: scaffold Phaser 3 engine for Sanctuary V2 | 2026-04-22 |
| 25 | #209 | feat: add 8-zone world tilemap with player movement | 2026-04-23 |
| 26 | #210 | feat: player & companion sprites with click-to-move pathfinding | 2026-04-23 |
| 27 | #213 | feat: integrate constellation companions, zones, and companion HUD | 2026-04-23 |
| 28 | #214 | feat: animated companion sprite system with mood and walk cycles | 2026-04-23 |
| 29 | #215 | feat: in-world companion radial menu with reaction animations | 2026-04-23 |
| 30 | #216 | feat: add Colyseus multiplayer server with room-per-location architecture | 2026-04-23 |
| 31 | #217 | feat: render other players from Colyseus multiplayer state | 2026-04-23 |
| 32 | #218 | feat: in-world chat bubbles with Colyseus broadcast | 2026-04-23 |
| 33 | #219 | feat: quest NPC sprites with click-to-dialog and quest board | 2026-04-23 |
| 34 | #232–#235 | feat: 4 room minigames (Hot Springs Memory, Cooking Rhythm, Dream Catcher, Lore Trivia) | 2026-04-25 |
| 35 | #236 | feat: LLM-backed sanctuary companion chat (ADR-002) | 2026-04-25 |
| 36 | #237 | feat: server-side chat history pagination + companion memory | 2026-04-25 |
| 37 | #238 | feat: bond_score → 4 behavioral chat tones | 2026-04-25 |
| 38 | #239 | feat: in-world companion chat overlay with hotkey C | 2026-04-25 |
| 39 | #240 | feat: STAR currency storage + earn/spend/balance API | 2026-04-25 |
| 40 | #241 | feat: layered cosmetic rendering for companion (hat + accessory) | 2026-04-25 |
| 41 | #242 | feat: cosmetic shop backend + inventory + equip API | 2026-04-25 |
| 42 | `7149ed2` | feat(sanctuary v3): canonical plan, locked palette, RD pipeline, first NPC | 2026-04-25 |
| 43 | `404dd93` | feat(sanctuary v3): bulk-generate 9 NPCs + 15 themed props through RD pipeline | 2026-04-25 |
| 44 | `993ce6c` | feat(sanctuary v3): 8 building exteriors + walkable test scene at ?v=3 | 2026-04-25 |
| 45 | `5cec372` | feat(sanctuary v3): phase 6 — tilemap-driven overworld + animated water | 2026-04-25 |
| 46 | `c2efa0c` | feat(sanctuary v3): phase 7 — door transitions + procedural room interiors | 2026-04-25 |
| 47 | #245 | feat(sanctuary): seed 5 daily errands + 3 weekly adventures via JSON | 2026-04-26 |
| 48 | #246 | content(sanctuary): SWO_SHARED_COSMETIC_ITEM_DESIGN — 30-item catalog spec | 2026-04-26 |
| 49 | #247 | feat(sanctuary v2.3): guided onboarding tutorial overlay | 2026-04-26 |
| 50 | #248 | feat(sanctuary): Howler-based ambient + SFX audio service | 2026-04-26 |
| 51 | #249 | feat(sanctuary v3): harden RD pipeline against credit waste | 2026-04-26 |
| 52 | #253 | feat(sanctuary v3): swap Press Start 2P → Pixelify Sans [SWO_V3_FONT_SWAP] | 2026-04-26 |
| 53 | #254 | feat(sanctuary v3): mount missing overlays + parity audit [SWO_V3_FEATURE_PARITY_AUDIT] | 2026-04-26 |
| 54 | #255 | feat(sanctuary v3): spawn companion sprite in WorldSceneV3 [SWO_V3_COMPANION_SPRITE] | 2026-04-26 |
| 55 | #256 | feat(sanctuary v3): wire 7 minigames into V3 [SWO_V3_MINIGAMES] | 2026-04-26 |
| 56 | #257 | feat(sanctuary): share InteractAction→VfxKind mapping for V2/V3 [SWO_SHARED_VFX_TRIGGER_API] | 2026-04-26 |
| 57 | #258 | feat(sanctuary v3): emit location-entered/exited from V3 zones [SWO_V3_LOCATION_EVENTS] | 2026-04-26 |
| 58 | #259 | feat(sanctuary v3): mount radial CompanionMenu overlay [SWO_V3_RADIAL_MENU] | 2026-04-26 |
| 59 | #260 | feat(sanctuary v3): EasyStar click-to-move pathfinding [SWO_V3_PLAYER_PATHFINDING] | 2026-04-26 |

## Branch Cleanup Log

| Date | Action | Count |
|------|--------|-------|
| 2026-04-21 | Deleted merged local branches | 30 |
| 2026-04-21 | Force-deleted stale not-merged local branches | 8 |
| 2026-04-21 | Deleted merged remote branches (fork) | 16 |
| 2026-04-21 | Deleted stale remote branches (fork + copilot) | 10 |
| 2026-04-21 | Auto-cleanup wired into project_agent.py cmd_spawn | — |

## Pending PRs — MERGE PRIORITY ORDER

_Revalidated 2026-04-26 against upstream/dev HEAD (68d9c94)._

| # | PR | Title | Status |
|---|-----|-------|--------|
| 1 | #204 | feat: wallet auth for sanctuary companion interact | Open — awaiting review |
| 2 | #258 | feat(sanctuary v3): emit location-entered/exited from V3 zones [SWO_V3_LOCATION_EVENTS] | Open — 2026-04-26 |
| 3 | #259 | feat(sanctuary v3): mount radial CompanionMenu overlay [SWO_V3_RADIAL_MENU] | Open — 2026-04-26 |
| 4 | #260 | feat(sanctuary v3): EasyStar click-to-move pathfinding [SWO_V3_PLAYER_PATHFINDING] | Open — 2026-04-26 |

**Resolved:**
- ~~#177~~ — MERGED on dev (governance votingPower server-side verification)
- ~~#180~~ — MERGED on dev (admin nonce persistence in SQLite)
- ~~#181~~ — MERGED on dev (contract archive housekeeping)
- ~~#179~~ — CLOSED (not merged). Wallet signature on chat/messages/presence. Findings H-1/H-4 remain unaddressed and need a new PR.
- ~~#250~~ — MERGED on dev (operator playtest brief — `SWO_OPERATOR_PLAYTEST_BRIEF`)
- ~~#251~~ — MERGED on dev (shared companion VFX event contract — `SWO_SHARED_VFX_TRIGGER_API`)
- ~~#252~~ — MERGED on dev (overworld map enrichment — `SWO_V3_OVERWORLD_MAP_DETAIL`)
- ~~#253~~ — MERGED on dev (Pixelify Sans font swap — `SWO_V3_FONT_SWAP`)
- ~~#254~~ — MERGED on dev (V3 parity audit + overlay mounts — `SWO_V3_FEATURE_PARITY_AUDIT`)
- ~~#255~~ — MERGED on dev (companion sprite in WorldSceneV3 — `SWO_V3_COMPANION_SPRITE`)
- ~~#256~~ — MERGED on dev (7 minigames wired into V3 — `SWO_V3_MINIGAMES`)
- ~~#257~~ — MERGED on dev (shared VFX InteractAction→VfxKind mapping)

## Security Audit Backlog (from 2026-04-19 audit, revalidated 2026-04-21)

_Full report: `docs/SECURITY_AUDIT_2026-04-19.md` in SWO repo._
_Revalidated against dev HEAD 5ed3557. Updated status reflects actual merge state._

| # | Finding | Sev | Covered By | Status |
|---|---------|-----|------------|--------|
| C-1 | Raffle randomness predictable/manipulable | CRIT | #183 merged | **FIXED** — CSPRNG + combined entropy |
| C-2 | Governance votingPower client-supplied | CRIT | #177 merged | **FIXED** |
| H-1 | Raffle bonuses (discordBonus/engagementBonus) client-supplied | HIGH | #179 CLOSED | **OPEN — needs new PR** |
| H-2 | Social connections GET leaks user PII without auth | HIGH | #184 merged | **FIXED** — wallet auth required |
| H-3 | In-memory security state (nonces, seeds, rate limits) | HIGH | #180 merged (nonces) | **Partial** — seeds+rates still in-memory |
| H-4 | Cron dev bypass tied to NODE_ENV | HIGH | #179 CLOSED | **OPEN — needs new PR** |
| M-1 | No rate limiting on most API endpoints | MED | — | **OPEN — needs PR** |
| M-3 | Vote change lacks signature verification | MED | — | **OPEN — needs PR** |
| M-5 | StarForge game ID predictable | MED | — | **OPEN — needs PR** |
| L-3 | Hardcoded default admin wallet | LOW | — | **OPEN — needs PR** |
| NEW | Sanctuary POST routes (interact/activity/claim) accept wallet without auth | HIGH | — | **OPEN — needs PR** |

## Delivered Artifacts (non-PR)

| Date | Commit | Description |
|------|--------|-------------|
| 2026-04-19 | docs   | Security audit v2: `docs/SECURITY_AUDIT_2026-04-19.md` (14 findings, 2 CRIT / 4 HIGH / 5 MED / 3 LOW) |
| 2026-04-16 | audit  | Security threat-surface audit: `memory/audits/swo_security_threat_surface_2026-04-16.md` (16 findings, 6 P0, 5-PR plan) |
| 2026-04-10 | 378d7a1 | Website redesign — gold palette, Press Start 2P font |
| 2026-04-05 | a5479fd | SWO ecosystem positioning doc |
| 2026-04-03 | 09b0598 | SWO brand integration doc + LLM prompt evaluator |

## Sanctuary — V2/V3 Operating Model (reconciled 2026-04-25)

_V2 = gameplay testbed (`?v=2`). V3 = production tile-based pixel-art rebuild (`?v=3`). Shared logic (DB, overlays, EventBus, Colyseus, minigames, quest system, companion chat, shop backend) benefits both automatically._
_**Canonical V3 doc:** `docs/SANCTUARY_V3.md` (in SWO repo). **Replan:** `memory/evolution/swo_sanctuary_v2_v3_replan_2026-04-25.md`. **Execution log:** `memory/evolution/swo_sanctuary_v3_alignment_execution_2026-04-25.md`._

**Routing** (`app/sanctuary/SanctuaryRouter.tsx`): `?v=3 → SanctuaryV3 → PhaserGameV3`; `?v=2 or NEXT_PUBLIC_SANCTUARY_V2=true → SanctuaryV2`; else `SanctuaryContent` (V1).

**Local testing (verified 2026-04-25, branch `clarvis/star-world-order/t0425200011-0a6c`):**
- `npm run dev` (Next.js, port 3000) + `npm run colyseus:dev` (Colyseus multiplayer)
- Visit `localhost:3000/sanctuary?v=3` (V3) or `?v=2` (V2)
- `npm run type-check` ✅ passes; `/sanctuary?v=3` returns HTTP 200
- Pre-PR gate: `npm run type-check && npm run lint && npm run build`
- RD cost gate: `RD_API_KEY=... node scripts/v3/generate.mjs --check-cost`

### V2 — Testbed Status (frozen at PRs #208–#240 + V2 polish)

| Phase | PRs / Commits | Status |
|-------|---------------|--------|
| 0. API Lock & Security | #205–#207 | ✅ DONE (Zod, rate limit, wallet auth on POST) |
| 1. Canvas Foundation | #208–#210, #213 + `f17f38e` collision | ✅ DONE |
| 2. Companion Alive | #214–#215 | ✅ DONE |
| 3. Multiplayer Lobby | #216–#218 | ✅ DONE |
| 4. Diegetic Content | #219 + `40d0177` Spawn Fox + `50ad237` overlays | ✅ DONE |
| 4B. Room Minigames | #232–#235 (3 added today: Cooking Rhythm, Dream Catcher, Lore Trivia) | ✅ DONE |
| 5. LLM Companion | #236–#240 (`1144e4b`, `1d44697`, `b5bc7ef`, `3084f9f`) | ✅ DONE |
| 6. Economy | `fd9924c` STAR currency + `72d6202` layered cosmetics + `5aa2965` shop+inventory backend | ✅ DONE — UI lives in SHARED |
| 7+ | — | Frozen / superseded by V3 |

V2 polish remaining (P2): `[SWO_V2_COMPANION_BG_MATTE]`, `[SWO_V2_STATUS_VERIFY]`, `[SWO_V2_DEPRECATION_GATE]`.

### V3 — Production Rebuild Status (commits `7149ed2 → c2efa0c` on dev)

| Phase | Commit | Status |
|-------|--------|--------|
| 0. Canonical plan + locked palette | `7149ed2` | ✅ DONE (`docs/SANCTUARY_V3.md`, FM palette PNG+TXT, RD style ID) |
| 1. FM tileset + first NPC sign-off | `7149ed2` | ✅ DONE (Spawn Fox passed) |
| 2. RD pipeline scripts | `7149ed2` | ✅ DONE (`scripts/v3/{generate,normalize,rd-client,create-style,build-review}.mjs`) |
| 3. Spawn Fox eyeball sign-off | `7149ed2` | ✅ DONE |
| 4. Bulk NPC + prop generation | `404dd93` | ✅ DONE (9 more NPCs + 15 themed props) |
| 5. Building exteriors + walkable test scene | `993ce6c` | ✅ DONE (8 buildings, `?v=3` walkable) |
| 6. Tilemap-driven overworld + animated water | `5cec372` | ✅ DONE (Tiled JSON, 6-frame water) |
| 7. Door transitions + procedural room interiors | `c2efa0c` | ✅ DONE (8 rooms launchable via `[E]`) |
| 8. UI restyle / ambient particles / font / HUD icons | PR #253 (font) open | ⏳ IN PROGRESS — `[SWO_V3_FONT_SWAP]` PR #253 open; `[SWO_V3_HUD_ICONS]` blocked on RD_API_KEY; `[SWO_V3_UI_RESTYLE]`, `[SWO_V3_PARTICLES_AMBIENT]` not started |
| 9. Hand-authored maps + parity audit | PRs #252 (merged), #254 (parity audit) open | ⏳ IN PROGRESS — `[SWO_V3_OVERWORLD_MAP_DETAIL]` MERGED on dev; `[SWO_V3_FEATURE_PARITY_AUDIT]` PR #254 open with audit doc + 6 overlay mounts; `[SWO_V3_ROOM_INTERIOR_MAPS]` not started |

**V3 assets in repo (verified 2026-04-25):** 11 NPC walking sheets (`public/sanctuary-v3/npcs/`), 15 themed props, 8 building exteriors, FM 64-color palette, custom RD user style ID `user__swo_forgotten_sanctuary_0dbd7f09`, overworld Tiled JSON (60×40 tiles, layers ground/buildings/props/water/npcs/doors/collision), procedural `RoomSceneV3`.

**V3 weak points (concrete, observed 2026-04-25):**
1. **Overworld map composition is placeholder.** `public/sanctuary-v3/maps/overworld.json` ground layer has 2400 tiles but **only 4 unique tile gids** (gid=2 grass = 1899/2400 ≈ 79%). Reads as flat green carpet around 8 building anchors, not an RPG forest route. Tracked: `[SWO_V3_OVERWORLD_MAP_DETAIL]`.
2. **Room interiors are procedural.** `RoomSceneV3.renderInterior()` paints a floor+wall grid from a single FM crop — no decoration, no path, identical-looking across all 8 rooms apart from one signature prop. Tracked: `[SWO_V3_ROOM_INTERIOR_MAPS]`.
3. **HUD/UI chrome still cosmic-palette + emoji.** Press Start 2P font and `#ffd700` accents in `WorldSceneV3`/`RoomSceneV3` text labels diverge from FM doctrine §4 (`#d4a445` antique gold). Tracked: `[SWO_V3_FONT_SWAP]`, `[SWO_V3_HUD_ICONS]`, `[SWO_V3_UI_RESTYLE]`.
4. **No animation polish beyond water + walk-cycle.** No idle bob on player, no particles, no door open animation, no scene-transition flourish (only fade in/out at 250ms). Tracked: `[SWO_V3_PARTICLES_AMBIENT]`.
5. **Pipeline is unhardened.** No prompt_hash dedup before RD POST; no daily/per-batch cost ceiling; no flock; no append-only `requested.jsonl`. One bug could re-bill the entire FM asset set. Tracked: `[SWO_V3_PIPELINE_HARDENING]`.
6. **Companion sprite not yet wired to V3.** `WorldSceneV3` does not spawn a companion next to the player; V3 doc §13 says the constellation PNGs are kept on-spec, but the rendering hook is not yet present. Tracked: implicit in `[SWO_V3_FEATURE_PARITY_AUDIT]`.

### Shared — what benefits both V2 and V3
- Companion chat (LLM, history pagination, memory) — DONE (#236–#240)
- Shop backend + STAR currency + cosmetic equip API — DONE (`fd9924c`/`72d6202`/`5aa2965`)
- Quest system + Quest Board + Quest Tracker — DONE
- Minigame framework + 7 minigames — DONE (#232–#235 + earlier)
- Multiplayer (Colyseus), EventBus, React overlays — DONE
- **Outstanding SHARED**: `[SWO_SHARED_SHOP_DIALOG]`, `[SWO_SHARED_QUEST_DIALOG_CONTENT]`, `[SWO_SHARED_ONBOARDING]`, `[SWO_SHARED_SOUND_DESIGN]`, `[SWO_SHARED_VFX_TRIGGER_API]`, `[SWO_SHARED_MOBILE_OVERLAYS]`, `[SWO_SHARED_EXPEDITIONS]`, `[SWO_SHARED_CHAT_MEMORY_CONSOLIDATION]`, `[SWO_SHARED_COSMETIC_ITEM_DESIGN]`.

### Recommended next-task order (post-alignment)

_Updated 2026-04-26 (fourth pass): SWO_V3_LOCATION_EVENTS, SWO_V3_RADIAL_MENU, SWO_V3_PLAYER_PATHFINDING shipped this session (PRs #258, #259, #260). All earlier V3 polish (#253–#257) merged on dev. HUD_ICONS still blocked on operator-side RD_API_KEY._

1. **`[SWO_V3_HUD_ICONS]`** (P1, 1 PR, ~$0.30 RD spend) — **BLOCKED on operator running `RD_API_KEY=... node scripts/v3/generate.mjs --force`.** Pipeline ready (#249), manifest entries TBD. Most-visible UX win once unblocked.
2. ~~**`[SWO_V3_COMPANION_SPRITE]`**~~ → MERGED (#255).
3. ~~**`[SWO_V3_MINIGAMES]`**~~ → MERGED (#256).
4. ~~**`[SWO_V3_RADIAL_MENU]`**~~ → PR #259 OPEN 2026-04-26.
5. **`[SWO_V3_ROOM_INTERIOR_MAPS]`** (P1, 1–2 PRs) — replace procedural rooms with hand-authored Tiled JSON.
6. **`[SWO_V3_SHOP_CHROME]`** (P1, 1 PR, ~$0.50 RD spend) — blocked on RD_API_KEY like HUD icons.
7. **`[SWO_V3_MULTIPLAYER]`** (NEW, P2, 1 PR, unblocked by #258) — Colyseus join + `OtherPlayersManager` + chat bubble + chat input in V3.
8. **`[SWO_V3_UI_RESTYLE]`** (P2, 1 PR) — restyle V3 chrome to FM tones; V2 stays cosmic.
9. **`[SWO_SHARED_MOBILE_OVERLAYS]`** (P2, 1 PR) — responsive React overlay sweep.
10. **`[SWO_SHARED_EXPEDITIONS]`** (P2, 1 PR) — multi-step adventures with narrative choices.
11. ~~**`[SWO_V3_LOCATION_EVENTS]`**~~ → PR #258 OPEN 2026-04-26.
12. ~~**`[SWO_V3_PLAYER_PATHFINDING]`**~~ → PR #260 OPEN 2026-04-26.

### Naming convention (binding)

| Prefix | Lane | Touches |
|--------|------|---------|
| `[SWO_SHARED_*]` | Shared logic | DB, API, overlays, EventBus, Colyseus, quest data, minigame rules, content. React-only or backend-only. |
| `[SWO_V2_*]` | V2 testbed | `app/sanctuary/SanctuaryV2.tsx`, `components/sanctuary/PhaserGame.tsx`, `game/{config,scenes,sprites,systems}/`, `public/sanctuary/`. |
| `[SWO_V3_*]` | V3 production | `app/sanctuary/SanctuaryV3.tsx`, `components/sanctuary-v3/PhaserGameV3.tsx`, `game/v3/`, `public/sanctuary-v3/`, `scripts/v3/`. |

If an item touches more than one lane, **split it**. The SHARED item is usually the trunk.

## Notes

- Fork workflow: GranusClarvis has pull-only on InverseAltruism repo. Push to fork, PR targets upstream.
- Agent root: `/opt/clarvis-agents/star-world-order/` or `/home/agent/agents/star-world-order/`
- SWO repo: `GranusClarvis/Star-World-Order` (fork of `InverseAltruism/Star-World-Order`)
