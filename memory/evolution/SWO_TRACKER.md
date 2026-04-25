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

## Branch Cleanup Log

| Date | Action | Count |
|------|--------|-------|
| 2026-04-21 | Deleted merged local branches | 30 |
| 2026-04-21 | Force-deleted stale not-merged local branches | 8 |
| 2026-04-21 | Deleted merged remote branches (fork) | 16 |
| 2026-04-21 | Deleted stale remote branches (fork + copilot) | 10 |
| 2026-04-21 | Auto-cleanup wired into project_agent.py cmd_spawn | — |

## Pending PRs — MERGE PRIORITY ORDER

_Revalidated 2026-04-21 against upstream/dev HEAD (36d0e20). Fork dev synced. All branches cleaned._

| # | PR | Title | Status |
|---|-----|-------|--------|
| 1 | #204 | feat: wallet auth for sanctuary companion interact | Open — awaiting review |

**Resolved:**
- ~~#177~~ — MERGED on dev (governance votingPower server-side verification)
- ~~#180~~ — MERGED on dev (admin nonce persistence in SQLite)
- ~~#181~~ — MERGED on dev (contract archive housekeeping)
- ~~#179~~ — CLOSED (not merged). Wallet signature on chat/messages/presence. Findings H-1/H-4 remain unaddressed and need a new PR.

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

## Sanctuary V2 — World-First Rebuild (reviewed 2026-04-23)

_Full plan: `docs/SANCTUARY_V2_PLAN.md`. Queue tasks: `memory/evolution/QUEUE.md` §Star Sanctuary V2._
_Direction: lobby-first, social, game-like. Tamagotchi + Club Penguin + Habbo vibes._

**Core change:** Replace React panel-based dashboard with Phaser 3 game canvas world. Players walk a pixel-art map with their animated Skrumpey companion, see other players, chat with bubbles, discover quests via NPCs, shop at The Bazaar. Backend/API layer unchanged — V2 is a frontend revolution.

**Stack:** Phaser 3 + Colyseus (multiplayer) + React overlays (contextual UI) + EventBus (bridge) + easystar.js (pathfinding) + Howler.js (audio)

**Phase Status (reviewed 2026-04-23, updated with operator split brief):**

| Phase | PRs | Status | Gate |
|-------|-----|--------|------|
| 0. API Lock & Security | #205-#207 | ✅ DONE | All routes tested, wallet auth, rate limiting |
| P0 Blockers | f17f38e (collision) | **1/6 done** | Collision ✅, 5 remain: door, NPC art, chat echo, companion BG, room gameplay |
| 1. Canvas Foundation | #208-#210, #213 | ✅ DONE | Player walks 8-zone world, real map art, click-to-move |
| 2. Companion Alive | #214-#215 | ✅ DONE | Companion follows, mood anims, radial menu |
| 3. Multiplayer Lobby | #216-#218 | ✅ DONE | Colyseus rooms, other players, chat bubbles |
| 4. Diegetic Content | #219 (partial) | **25%** | Quest NPCs done; 3 overlays + Spawn Fox intro + room NPCs + quest hub remain |
| 4B. Room Activities & Minigames | — | Not started | Timed quests, Training Grounds XP, minigame plumbing, 8 room minigames |
| 5. LLM Companion | — | Not started | — |
| 6. Economy | — | Not started | STAR currency + shop + cosmetics (4 PRs) |
| 7. Personal Rooms | — | Not started | — |
| 8. Polish | — | Not started | Mobile, onboarding (Spawn Fox guided), sound |
| RD Asset Pipeline | — | Planned (action plan 2026-04-25) | scripts/rd/ + manifest+dedup → 5 batches → ~41 assets unblock HUD/Shop/VFX/cosmetics/empty states |

**Operator manual work (2026-04-23):** Uploaded 4 player sprites, 8 room backgrounds, 8 NPC sprites, overworld map, marked collision map. Authored `extract_sanctuary_layout.mjs`, `analyze_sprite.mjs`, wired real collision data (685 rects), clean character sprite pipeline (`PlayerSprite::registerFrames`), room background loading in BootScene/RoomScene.

**P0 Playability Blockers (discovered 2026-04-23):**
1. ~~`[SWO_P0_COLLISION_FIX]`~~ — ✅ FIXED (commit f17f38e: `physics.add.collider` wired)
2. `[SWO_P0_STAR_GARDEN_DOOR]` — Star Garden has no door (7/8 doors defined)
3. `[SWO_P0_NPC_REAL_SPRITES]` — NPCs use placeholder circles despite real art existing
4. `[SWO_P0_CHAT_LOCAL_ECHO]` — Chat requires Colyseus roundtrip, no local echo
5. `[SWO_P0_COMPANION_BG_MATTE]` — Companion mood PNGs have non-transparent backgrounds
6. `[SWO_P0_ROOM_GAMEPLAY]` — Rooms are static image viewers (no player/movement/collision)

**Recommended execution order:** P0 blockers (2→3→4→5→6) → Phase 4 content → Phase 4B activities/minigames → Phase 5 LLM → Phase 6 economy

**Art track retired items (2026-04-23):** WORLD_TILESET_ART (operator painted map), COMPANION_SPRITE_ART (mood PNGs exist), NPC_QUEST_CONTENT (NPCs defined, only dialog content remains)

**Testing convention:** Primary dev/test loop is local (`npm run dev` + `npm run colyseus:dev`, verify at localhost:3000/sanctuary). test.starworldorder.com is secondary deployment verification only.

**NPC↔Sprite mapping (from operator sprite sheets):** Spawn Fox → Spawn_Fox_Sprite.png (Town Square intro), Springs Duck → Hot Springs, Observatory Owl → Observatory, Training Wolf → Training Grounds, Kitchen Bunny → Nebula Kitchen, Garden Ent → Star Garden, Hollow Moth → Cosmic Library, Dream Sheep → Dream Hollow, Aura Golem → Aura Forge.

## Notes

- Fork workflow: GranusClarvis has pull-only on InverseAltruism repo. Push to fork, PR targets upstream.
- Agent root: `/opt/clarvis-agents/star-world-order/` or `/home/agent/agents/star-world-order/`
- SWO repo: `GranusClarvis/Star-World-Order` (fork of `InverseAltruism/Star-World-Order`)
