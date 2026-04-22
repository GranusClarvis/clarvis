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

## Sanctuary V2 — World-First Rebuild (reorganized 2026-04-22)

_Full plan: `docs/SANCTUARY_V2_PLAN.md`. Queue tasks: `memory/evolution/QUEUE.md` §Star Sanctuary V2._
_Direction: lobby-first, social, game-like. Tamagotchi + Club Penguin + Habbo vibes. Operator feedback: V1 too dashboard-like, needs game feel._

**Core change:** Replace React panel-based dashboard with Phaser 3 game canvas world. Players walk a pixel-art map with their animated Skrumpey companion, see other players, chat with bubbles, discover quests via NPCs, shop at The Bazaar. Backend/API layer unchanged — V2 is a frontend revolution.

**Stack:** Phaser 3 (`phaserjs/template-nextjs`) + Tiled (maps) + Colyseus (multiplayer, Phase 3) + React overlays (contextual UI) + EventBus (bridge) + easystar.js (pathfinding) + Howler.js (audio)

**Phases (25 PRs, ~30 dev-days) — reorganized 2026-04-22:**

| Phase | PRs | Summary | Priority | Gate |
|-------|-----|---------|----------|------|
| 0. API Lock & Security | 2 | E2E tests + security hardening | P0 | All 15 routes tested, no open HIGH findings |
| 1. Canvas Foundation | 4 | Phaser scaffold, Tiled world, walking, zones+HUD | P0 | Player walks 8-zone world, HUD shows stats |
| 2. Companion Alive | 2 | Animated sprites, in-world interactions | P1 | Companion follows, animates, reacts |
| 3. Multiplayer Lobby | 3 | Colyseus server, other players, chat bubbles | P1 | 2+ players visible, chat works |
| 4. Diegetic Content | 4 | Quest NPCs, tracker, journal+traits overlays | P1 | Quests in-world, all V1 panels migrated |
| 5. LLM Companion | 4 | LLM chat, persistence, bond stages, overlay | P1 | AI chat with memory + personality |
| 6. Economy | 3 | Cosmetic layers, shop backend+UI | P2 | Buy/equip cosmetics, STAR balance |
| 7. Personal Rooms | 2 | Room scene, decorations | P2 | Customizable rooms, visiting |
| 8. Polish | 3 | Mobile, onboarding, sound | P2 | Mobile-ready, guided, audio |

**Changes from original V2 plan (2026-04-22 reorg):**
- Added Phase 0 security hardening (was implicit)
- Moved cosmetic sprite layers from Phase 2 → Phase 6 (not needed until shop)
- Merged overlay migrations (journal, traits) into Phase 4 with quests (migrate all panels together)
- Created Phase 5 for LLM companion (was scattered across carried-V1 items)
- Merged CHAT_HISTORY + CHAT_MEMORY into single CHAT_PERSISTENCE task
- Absorbed TYPING_SIM, RESPONSIVE, SOUND_DESIGN V1, COSMETICS_SHOP V1 into V2 equivalents
- Explicit quality gates after every phase

**Key decisions:**
- Top-down view (not isometric) — simpler, cuter, better for pixel art
- Phaser 3 over PixiJS (framework vs renderer — we need the framework)
- Feature flag (`NEXT_PUBLIC_SANCTUARY_V2`) for gradual rollout
- All V1 data carries forward (same DB, same tables, same API routes)
- LLM companion at Phase 5 (after world + quests proven, before economy)

**Open-source resources:**
- **Adopt:** Phaser 3, Tiled, Colyseus, easystar.js, Howler.js
- **Borrow:** rexrainbow/phaser3-rex-notes (virtual joystick), Kenney (placeholder assets)
- **Adapt:** Dungeon Crawl + Evil Dungeon pixel art (recolor per doctrine palette)
- **Inspirational:** Kinkly chat patterns, Club Penguin/Habbo/Tamagotchi feel, Stardew Valley art mood

**V1 reuse:**
- **Reuse as-is:** All API routes, DB schema, wallet auth, bond/XP logic, quest data, security fixes
- **Adapt to overlays:** Journal, traits, chat data fetching
- **Leave behind:** SanctuaryContent.tsx (1,656 lines), panel layout, tab navigation, button grids

## Notes

- Fork workflow: GranusClarvis has pull-only on InverseAltruism repo. Push to fork, PR targets upstream.
- Agent root: `/opt/clarvis-agents/star-world-order/` or `/home/agent/agents/star-world-order/`
- SWO repo: `GranusClarvis/Star-World-Order` (fork of `InverseAltruism/Star-World-Order`)
