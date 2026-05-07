# Star World Order — Project Tracker

_Dedicated tracker for SWO/Sanctuary project work. Separated from main QUEUE.md per PROJECT_LANES.md governance._
_Project lane: SWO | Status: ACTIVE | Operator-directed._

> **2026-04-26 RESET — V3 DEFERRED, V2 IS THE ACTIVE SURFACE, COMPANION-FIRST CORE LOOP.**
>
> All new feature work, polish, and visual fixes target **V2** (`?v=2` route, page `app/sanctuary/SanctuaryV2.tsx`, Phaser mount `components/sanctuary/PhaserGame.tsx`, game code under `game/{scenes,sprites,systems,config}/`, assets in `public/sanctuary/`). Tag commits/branches `[SWO_V2_*]` (or `[SWO_SHARED_*]` for engine-agnostic React/overlay/EventBus work).
>
> **Center of gravity: the Companion (selected Skrumpey).** A tamagotchi-style care + interaction loop is the new core loop. Quests, minigames, and economy stay as supporting structure; new feature work files under `[SWO_V2_COMPANION_*]` first. Direction note: `memory/evolution/swo_sanctuary_companion_first_2026-04-26.md`.
>
> **V3 is frozen.** Stop touching `game/v3/`, `public/sanctuary-v3/`, `scripts/v3/`, `docs/SANCTUARY_V3.md`. The `?v=3` route remains for archival access only. **No new PRs tagged `[SWO_V3_*]`.** **No further RD credit spend on V3** (~5 generation passes already burned without V2 parity; remaining RD balance is held for V2 polish only after explicit operator approval).
>
> **V1 (`SanctuaryContent.tsx` React panel) is archival.** It stays mounted as the no-flag fallback for backwards-compat only. No new V1 features. Anything still useful in V1 ports into V2 surfaces, not V1.
>
> Why V3 stopped: pixel-art-from-scratch parallel rebuild that never reached V2's painted-hub parity, and the FM aesthetic does not compose with V2's painted assets. Full inventory: SWO repo `docs/SANCTUARY_V3_DEFERRED.md`. The V3 doctrine doc (`docs/SANCTUARY_V3.md`) carries a deferred banner at the top.
>
> Primary V2 goals: **(a) reduce AI-slop** (palette quantize / dither shader, fix sprite aliasing, downsize NPCs, standardize painted-room palettes — without regenerating the painted backgrounds); **(b) build out the Companion core loop** (stats schema → mood-from-stats → companion screen → need alerts → chat-knows-stats). Direction note for (b): `memory/evolution/swo_sanctuary_companion_first_2026-04-26.md`.

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
| 60 | #277 | feat(sanctuary v2.7): cozy/tamagotchi polish on the Companion screen [SWO_V2_COMPANION_COZY_POLISH] | 2026-05-07 |

## Branch Cleanup Log

| Date | Action | Count |
|------|--------|-------|
| 2026-04-21 | Deleted merged local branches | 30 |
| 2026-04-21 | Force-deleted stale not-merged local branches | 8 |
| 2026-04-21 | Deleted merged remote branches (fork) | 16 |
| 2026-04-21 | Deleted stale remote branches (fork + copilot) | 10 |
| 2026-04-21 | Auto-cleanup wired into project_agent.py cmd_spawn | — |

## Pending PRs — MERGE PRIORITY ORDER

_Revalidated 2026-04-27 against upstream/dev HEAD. No pending pre-built PRs awaiting merge — deslop shader confirmed merged via #264._

| # | Branch / PR | Title | Status |
|---|-------------|-------|--------|
| 1 | `clarvis/star-world-order/swo-v2-companion-cozy-polish` / [#277](https://github.com/InverseAltruism/Star-World-Order/pull/277) | feat(sanctuary v2.7): cozy/tamagotchi polish on the Companion screen [SWO_V2_COMPANION_COZY_POLISH] | Open 2026-05-07 |

**Resolved:**
- ~~#264~~ — MERGED on dev 2026-04-26 (deslop post-FX shader, palette quantize + Bayer dither — `SWO_V2_DESLOP_SHADER`). Verified 2026-04-27.
- ~~#177~~ — MERGED on dev (governance votingPower server-side verification)
- ~~#180~~ — MERGED on dev (admin nonce persistence in SQLite)
- ~~#181~~ — MERGED on dev (contract archive housekeeping)
- ~~#179~~ — CLOSED (not merged). Wallet signature on chat/messages/presence. Findings H-1/H-4 remain unaddressed and need a new PR.
- ~~#204~~ — MERGED on dev (wallet auth for sanctuary companion interact). Confirmed 2026-04-26 evening; was incorrectly listed as "open."
- ~~#250~~ — MERGED on dev (operator playtest brief — `SWO_OPERATOR_PLAYTEST_BRIEF`)
- ~~#251~~ — MERGED on dev (shared companion VFX event contract — `SWO_SHARED_VFX_TRIGGER_API`)
- ~~#252~~ — MERGED on dev (overworld map enrichment — `SWO_V3_OVERWORLD_MAP_DETAIL`)
- ~~#253~~ — MERGED on dev (Pixelify Sans font swap — `SWO_V3_FONT_SWAP`)
- ~~#254~~ — MERGED on dev (V3 parity audit + overlay mounts — `SWO_V3_FEATURE_PARITY_AUDIT`)
- ~~#255~~ — MERGED on dev (companion sprite in WorldSceneV3 — `SWO_V3_COMPANION_SPRITE`)
- ~~#256~~ — MERGED on dev (7 minigames wired into V3 — `SWO_V3_MINIGAMES`)
- ~~#257~~ — MERGED on dev (shared VFX InteractAction→VfxKind mapping)
- ~~#258~~ — MERGED on dev (V3 location-entered/exited events — `SWO_V3_LOCATION_EVENTS`). V3 deferred post-merge; do not extend.
- ~~#259~~ — MERGED on dev (V3 radial CompanionMenu overlay mount — `SWO_V3_RADIAL_MENU`). V3 deferred post-merge.
- ~~#260~~ — MERGED on dev (V3 EasyStar click-to-move pathfinding — `SWO_V3_PLAYER_PATHFINDING`). V3 deferred post-merge.

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

## Sanctuary — V2-Only, Companion-First Operating Model (reset 2026-04-26)

_V2 (`?v=2`) is the **active surface** — all new feature work, polish, and visual fixes ship here. V3 (`?v=3`) is **DEFERRED** — archival access only, no new PRs, no RD spend. V1 (no flag) is **archival fallback only**. See banner at top of file. Direction note for the companion-first refinement: `memory/evolution/swo_sanctuary_companion_first_2026-04-26.md`._

**Routing** (`app/sanctuary/SanctuaryRouter.tsx`): `?v=2 or NEXT_PUBLIC_SANCTUARY_V2=true → SanctuaryV2`; else `SanctuaryContent` (V1). `?v=3 → SanctuaryV3 → PhaserGameV3` still wired for archival/reference; do not iterate on it.

**Local testing (verified 2026-04-25, branch `clarvis/star-world-order/t0425200011-0a6c`):**
- `npm run dev` (Next.js, port 3000) + `npm run colyseus:dev` (Colyseus multiplayer)
- Visit `localhost:3000/sanctuary?v=2`
- `npm run type-check` ✅ passes
- Pre-PR gate: `npm run type-check && npm run lint && npm run build`
- **No RD pipeline runs** without explicit operator approval.

### V2 — Active Surface Status

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
| 7+ (de-slop) | `[SWO_V2_*]` priority queue below | ⏳ ACTIVE — six items (2026-04-26) |

### V2 — Companion-First Core Loop (operator-set 2026-04-26 evening)

_Direction note: `memory/evolution/swo_sanctuary_companion_first_2026-04-26.md`. The Companion (selected Skrumpey) is the new center of gravity; quests/minigames stay as supporting structure. This section ranks **above** the de-slop polish queue for sequencing. The deslop shader has shipped (PR #264, merged 2026-04-26) — Companion stack is now the active focus._

| # | Task | Acceptance summary | Lane | Priority | Status |
|---|------|--------------------|------|----------|--------|
| 1 | `[SWO_V2_COMPANION_STATS_SCHEMA]` | Add hunger / energy / happiness stats (0–100) + per-hour decay rate + `stats_updated_at` to `SanctuaryCompanion`. Pure `decayStats(companion, now)` helper (unit-tested). New GET `/api/sanctuary/companion/stats` returns projected values + active needs. | V2 | P0 | ✅ DONE (commit `270bce1`, on dev) |
| 2 | `[SWO_V2_COMPANION_INTERACT_AFFECTS_STATS]` | Wire `feed`/`pet`/`talk` to stats; add `sleep` + `play`. Caps + reactions/VFX preserved. Daily interaction cap unchanged. | V2 | P0 | ✅ DONE (folded into stats schema PR + follow-up; on dev) |
| 3 | `[SWO_V2_COMPANION_MOOD_FROM_STATS]` | Derive mood from current stats (lowest-stat → matching mood; sleeping → `sleeping`); trait mood fallback when stats not populated. | V2 | P0 | ✅ DONE (`lib/sanctuary/mood.ts`, on dev) |
| 4 | `[SWO_V2_COMPANION_SCREEN_SURFACE]` | New `/sanctuary/companion` (default landing for owners with an active Skrumpey). Renders sprite + 3 stat bars + need callout + bond/level + last-3 journal + quick actions + Chat + Enter Sanctuary CTA. | V2 | P0 | ✅ DONE (commit `941ff11`, on dev) |
| 5 | `[SWO_V2_COMPANION_NEED_ALERTS]` | In-page soft alert in `CompanionHUD.tsx` when any stat drops below 30; click jumps to companion screen. Never blocks gameplay. | V2 | P1 | ✅ DONE (commit `a241cac`, on dev) |
| 6 | `[SWO_V2_COMPANION_CHAT_KNOWS_STATS]` | Inject current stats + active needs + last 3 actions into the LLM chat system prompt. Replies voice-y, not stat-readouts; ≤200-token blob. | V2 | P1 | ✅ DONE (commit `fc95324`, on dev) |
| 7 | `[SWO_V1_ARCHIVE_FORMALIZE]` | Banner inside V1 (`SanctuaryContent.tsx`); tracker note confirming V1 is fallback-only. No code removal. | V2 | P1 | ✅ DONE (commit `cdda233`, on dev) |
| 8 | `[SWO_V2_COMPANION_COZY_POLISH]` | Cozy/tamagotchi voice on the Companion screen: mood-aware greeting, last-visit anchor, sprite reactions per quick action, stat-bar +N + glow pulse, sleep-state warmth ("shhh — they're dreaming" + muted buttons), journal-line variety pool. New pure helper `companionGreeting.ts` + 25 vitest cases. | V2 | P1 | 🟡 PR #277 open (2026-05-07) |

**Companion track exclusions (out-of-scope unless operator re-opens):** new minigame scenes, new world zones, new quest content, mobile-app shell, push notifications, voice chat, multiplayer companion features, on-chain companion state.

**Cozy polish follow-ups (filed in `QUEUE.md` 2026-05-07, all P1/P2):**
- `[SWO_V2_COMPANION_BOND_MILESTONE_CELEBRATE]` (P1) — fire confetti/heart burst when `bond_score` crosses 25/50/75/100 thresholds; idempotent per threshold per companion.
- `[SWO_V2_COMPANION_LOCAL_VISIT_MARKER]` (P1) — persist per-token "screen opened at" in `localStorage` so the cozy last-visit line refreshes even without an interaction (today it reads `stats_updated_at`, so the phrase goes stale on a no-action open).
- `[SWO_V2_COMPANION_CHAT_REMEMBERS_RECENT_ACTIONS]` (P2) — extend chat system-prompt to inject last 1–3 interaction journal lines (≤80 tokens) for temporally-anchored replies.
- `[SWO_V2_COMPANION_TIME_OF_DAY_GREETING]` (P2) — prefix the cozy greeting with "Good morning." / "Up late?" using the operator's local hour.

**Quest track posture:** quest authoring shipped (`[SWO_SHARED_QUEST_DIALOG_CONTENT]` → PR #245). New quest features and new quest content are **demoted to P2 or retired** — see Retired/Deferred Items in `QUEUE.md`.

### V2 — De-Slop Priority Queue (2026-04-26, operator-set)

Six priorities ordered as in the operator brief. Items 1–3 are de-slop visual fixes; 4 standardises existing painted assets; 5 closes one half-wired feature; 6 is a UX gate. **No RD credits for any of these.**

| # | Task | Acceptance summary | Lane | Priority |
|---|------|--------------------|------|----------|
| 1 | ~~`[SWO_V2_DESLOP_SHADER]`~~ | ~~Phaser post-FX pipeline (built-in `PostFXPipeline` API) palette-quantizes (+ optional Bayer dither) the canvas to a fixed N-color SWO palette. Dev-flag toggle (`?v=2&deslop=1` + `localStorage`). Ship enabled only after operator A/B inspection.~~ **DONE — PR #264 merged 2026-04-26 (commit `47d9b08`).** Shipped opt-in (`DESLOP_DEFAULT_ON=false`); operator A/B inspection still pending before flipping default. | V2 | ✓ |
| 2 | `[SWO_V2_PLAYER_SPRITE_ALIASING]` | Fix `public/sanctuary/player.png` aliasing. No non-integer scaling: redraw at display size or lock integer scale (1×/2×/3×) + `setScaleMode(NEAREST)` + `roundPixels: true`. **No RD.** | V2 | P0 |
| 3 | `[SWO_V2_NPC_DISPLAY_SIZE]` | Reduce NPC display size 64 → 48 px in `game/sprites/NPCSprite.ts`; update collider/hit region/nameplate offsets accordingly. | V2 | P0 |
| 4 | `[SWO_V2_ROOM_PALETTE_STANDARDIZE]` | Standardize palette across the 8 painted room backgrounds via batch color-adjust script (Pillow / ImageMagick). Lives at `scripts/v2/standardize_room_palette.{mjs,py}`. **No regeneration.** | V2 | P1 |
| 5 | `[SWO_V2_HALFWIRED_FEATURE_FINISH]` | Pick one of {DevMapEditor (no UI), MultiplayerBridge (incomplete), click-to-move (stub)}; either ship the minimum end-to-end or remove the mount. Document the other two as deliberate stubs. Recommended pick: DevMapEditor (low risk, dev-only). | V2 | P1 |
| 6 | `[SWO_V2_NPC_SELECT_SKRUMPEY_GATE]` | NPC click → if no active Skrumpey: auto-select if exactly one owned, else show guidance overlay with jump-to-picker button, else show "no Skrumpey" CTA. Wire through `SanctuaryContent.tsx` + `NPCSprite.ts`. | V2 | P1 |

V2 polish, secondary (P2): ~~`[SWO_V2_STATUS_VERIFY]`~~ — both child tasks already shipped on dev HEAD (verified 2026-04-27): `[SWO_V2_STAR_GARDEN_DOOR]` fixed in commit `3d8e4cc` (DOORS array now has 8 entries for 8 rooms); `[SWO_V2_NPC_REAL_SPRITES]` shipped in commit `e0900f6` (real PNG textures wired through BootScene + NPCSprite).
Retired 2026-04-26: `[SWO_V2_COMPANION_BG_MATTE]` (verified no-op), `[SWO_V2_DEPRECATION_GATE]` (moot — V3 is now the deprecated lane).
Retired 2026-04-27: `[SWO_V2_STATUS_VERIFY]`, `[SWO_V2_STAR_GARDEN_DOOR]`, `[SWO_V2_NPC_REAL_SPRITES]` (all verified shipped).

### V3 — DEFERRED 2026-04-26 (frozen, do not iterate)

All `[SWO_V3_*]` items are frozen. The `?v=3` route stays for archival access. Remaining V3 weak-points and partial work are intentionally not scheduled. Reference inventory: SWO repo `docs/SANCTUARY_V3_DEFERRED.md`.

| Item | Pre-defer status | Disposition |
|------|------------------|-------------|
| `[SWO_V3_PIPELINE_HARDENING]` | Not started; would have gated all RD spend | DEFERRED — moot without RD spend |
| `[SWO_V3_HUD_ICONS]` | Blocked on `RD_API_KEY` | DEFERRED |
| `[SWO_V3_FONT_SWAP]` | PR #253 merged | Closed |
| `[SWO_V3_OVERWORLD_MAP_DETAIL]` | PR #252 merged | Closed |
| `[SWO_V3_ROOM_INTERIOR_MAPS]` | Not started | DEFERRED |
| `[SWO_V3_FEATURE_PARITY_AUDIT]` | PR #254 open with audit doc | DEFERRED — close PR or re-tag if any V2-applicable findings remain |
| `[SWO_V3_LOCATION_EVENTS]` | PR #258 open | DEFERRED — close or reframe to V2 if needed |
| `[SWO_V3_RADIAL_MENU]` | PR #259 open | DEFERRED — overlay logic is shared; if needed, refile as `[SWO_SHARED_RADIAL_MENU_MOUNT]` |
| `[SWO_V3_PLAYER_PATHFINDING]` | PR #260 open | DEFERRED — close or reframe to V2 |
| `[SWO_V3_COMPANION_SPRITE]` | PR #255 merged | Closed |
| `[SWO_V3_MINIGAMES]` | PR #256 merged | Closed |
| `[SWO_V3_SHOP_CHROME]`, `[SWO_V3_VFX_SPRITES]`, `[SWO_V3_COSMETIC_HATS_V1]`, `[SWO_V3_UI_RESTYLE]`, `[SWO_V3_PARTICLES_AMBIENT]`, `[SWO_V3_MOBILE_CANVAS]` | Not started | DEFERRED |

### Shared — engine-agnostic logic that V2 mounts
- Companion chat (LLM, history pagination, memory) — DONE (#236–#240)
- Shop backend + STAR currency + cosmetic equip API — DONE (`fd9924c`/`72d6202`/`5aa2965`)
- Quest system + Quest Board + Quest Tracker — DONE
- Minigame framework + 7 minigames — DONE (#232–#235 + earlier)
- Multiplayer (Colyseus), EventBus, React overlays — DONE
- **Outstanding SHARED**: `[SWO_SHARED_SHOP_DIALOG]`, `[SWO_SHARED_QUEST_DIALOG_CONTENT]`, `[SWO_SHARED_ONBOARDING]`, `[SWO_SHARED_SOUND_DESIGN]`, `[SWO_SHARED_VFX_TRIGGER_API]`, `[SWO_SHARED_MOBILE_OVERLAYS]`, `[SWO_SHARED_EXPEDITIONS]`, `[SWO_SHARED_CHAT_MEMORY_CONSOLIDATION]`, `[SWO_SHARED_COSMETIC_ITEM_DESIGN]`.

### Recommended next-task order (revalidated 2026-04-27, post companion-first reset)

Two tracks are live in parallel: **(A) Companion core loop** (this is the new center of gravity, primary focus); **(B) V2 visual polish** in slots when no Companion P0 is ready. Deslop shader (was item 1) shipped via PR #264 — companion stack is the active head of A.

1. **`[SWO_V2_COMPANION_STATS_SCHEMA]`** (P0, A) — foundation for the new core loop; nothing else in the companion track moves without it.
2. **`[SWO_V2_COMPANION_INTERACT_AFFECTS_STATS]`** (P0, A) — wires existing `feed`/`pet`/`talk` to stats; adds `sleep`/`play`.
3. **`[SWO_V2_COMPANION_MOOD_FROM_STATS]`** (P0, A) — closes the loop visually using existing mood sprite animations.
4. **`[SWO_V2_COMPANION_SCREEN_SURFACE]`** (P0, A) — the daily-return surface; companion becomes default landing.
5. **`[SWO_V2_PLAYER_SPRITE_ALIASING]`** (P0, B) — fold in once a Companion P0 isn't ready to ship.
6. **`[SWO_V2_NPC_DISPLAY_SIZE]`** (P0, B) — one-line constant + hit region.
7. **`[SWO_V2_COMPANION_NEED_ALERTS]`** (P1, A) — soft HUD alert when any stat crosses threshold.
8. **Deslop A/B verification** (operational, A) — operator-driven inspection of `?deslop=1` against off; once accepted, flip `DESLOP_DEFAULT_ON=true`.
9. **`[SWO_V2_COMPANION_CHAT_KNOWS_STATS]`** (P1, A) — chat prompt knows current stats / recent actions.
10. **`[SWO_V2_ROOM_PALETTE_STANDARDIZE]`** (P1, B) — batch palette-snap over 8 painted rooms.
11. **`[SWO_V2_HALFWIRED_FEATURE_FINISH]`** (P1, B) — pick DevMapEditor; ship or remove.
12. **`[SWO_V2_NPC_SELECT_SKRUMPEY_GATE]`** (P1, B) — UX gate on NPC interaction; still relevant from companion screen.
13. **`[SWO_V1_ARCHIVE_FORMALIZE]`** (P1) — V1 banner + tracker note; no code removal.

### Naming convention (binding, updated 2026-04-26)

| Prefix | Lane | Touches |
|--------|------|---------|
| `[SWO_V2_*]` | **V2 active surface** | `app/sanctuary/SanctuaryV2.tsx`, `SanctuaryContent.tsx`, `components/sanctuary/PhaserGame.tsx`, `game/{config,scenes,sprites,systems}/`, `public/sanctuary/`. |
| `[SWO_SHARED_*]` | Engine-agnostic | DB, API, overlays, EventBus, Colyseus, quest data, minigame rules, content. React-only or backend-only — V2 mounts these. |
| `[SWO_V3_*]` | **FROZEN — do not file new items** | `app/sanctuary/SanctuaryV3.tsx`, `components/sanctuary-v3/PhaserGameV3.tsx`, `game/v3/`, `public/sanctuary-v3/`, `scripts/v3/`, `docs/SANCTUARY_V3.md`. |

If an item touches more than one lane, split it. The V2 item is usually the trunk now (was SHARED under the previous V2/V3 model).

## Notes

- Fork workflow: GranusClarvis has pull-only on InverseAltruism repo. Push to fork, PR targets upstream.
- Agent root: `/opt/clarvis-agents/star-world-order/` or `/home/agent/agents/star-world-order/`
- SWO repo: `GranusClarvis/Star-World-Order` (fork of `InverseAltruism/Star-World-Order`)
