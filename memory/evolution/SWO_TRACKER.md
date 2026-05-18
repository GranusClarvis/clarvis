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

## Sanctuary Engagement V2 — 7 PRs (added 2026-05-18, operator brief)

> **Center of gravity for V2 after the cozy-polish track shipped.** Infrastructure is solid (stats, mood, decay, bond, chat personality, expeditions engine, STAR ledger) but the **design layer is flat**: actions all bump similar stats, no preferences, no risk, no reason to sleep. The Expeditions engine has no DB/API/UI yet. These 7 PRs close the gap.
>
> **Binding plan:** `docs/SANCTUARY_ENGAGEMENT_PLAN.md` — PR-quality rules, design doctrine, anti-patterns, the 7-PR order.

| PR | Tag | Order | Track | Status |
|----|-----|-------|-------|--------|
| 1 | `[SWO_V2_SANCTUARY_PREFERENCE_PROFILE]` | first | A — Loop depth | ⏳ |
| 2 | `[SWO_V2_SANCTUARY_EXPEDITIONS_DB_API]` | second | A — Loop depth | ⏳ |
| 3 | `[SWO_V2_SANCTUARY_EXPEDITIONS_UI]` | after PR2 | A — Loop depth | ⏳ |
| 4 | `[SWO_V2_SANCTUARY_SLEEP_DYNAMICS]` | parallel w/ PR2/3 | B — Care depth | ⏳ |
| 5 | `[SWO_V2_SANCTUARY_STREAKS]` | after PR4 | B — Care depth | ⏳ |
| 6 | `[SWO_V2_SANCTUARY_STAR_ECONOMY_SINKS]` | after PR3 | C — Economy | ⏳ |
| 7 | `[SWO_V2_SANCTUARY_VARIABLE_REWARDS]` | last | C — Economy | ⏳ |

**Design doctrine (must hold for every PR):**
- Action choice must be meaningful (hidden preference per-Skrumpey × need-state × mood).
- Sleep must matter (24h+ no sleep → Tired halves bond gains; full cycle → dream reward with floor; early-wake → −2 bond + journal).
- Risk/reward deterministic; RNG only on aesthetic prizes.
- Variable rewards always have a floor.
- Compassionate streaks (1 miss pauses, 2 misses reset).
- Identity over power (bond milestones reveal personality, never raw stat lifts).

**Anti-patterns (auto-reject):** notification spam, pay-to-not-lose, full-reset streaks on one miss, variable rewards with zero floor, forced social/share gates.

**PR-quality rules (every PR):**
1. Pre-flight: `git log --oneline origin/dev -50` + `gh -R InverseAltruism/Star-World-Order pr list --state open` — no competing PRs.
2. 300–800 lines per PR including tests.
3. Rebase on `origin/dev`, never merge.
4. Vitest unit/component for all new logic + 1 Playwright happy-path + 1 negative-path for player-facing flows. CI all-green.
5. PR description: design rationale + acceptance checklist + actual local test counts pasted.
6. Commit prefix: `feat(sanctuary): …` / `fix(sanctuary): …` / `docs(sanctuary): …`.

**Per-PR acceptance summaries** (full detail in `docs/SANCTUARY_ENGAGEMENT_PLAN.md §5`):

| PR | Files (primary) | Acceptance highlights | E2E |
|----|-----------------|----------------------|-----|
| PR1 | `lib/sanctuary/preferences.ts` + test; extend `companionAction.ts` | Two Skrumpey on one wallet → different profiles; loved=4×, hated subtracts; clue after N=3 matched | Feed two companions, assert differing bond; hated action negative outcome |
| PR2 | `sanctuary_expeditions` + `sanctuary_expedition_progress` migrations; `app/api/sanctuary/expeditions/{list,start,choose,abandon}`; `data/sanctuary/expeditions/{easy,medium,hard}.json` | start deducts STAR; failure costs; outcomes deterministic against `(seed, choices)` | Walk easy → success; walk hard risky branch → failure |
| PR3 | `components/sanctuary/overlays/ExpeditionDialog.tsx`; hook into `QuestBoard.tsx` | Renders current step; choice POSTs; abandon POSTs; resume from DB on reload | Full walkthrough + reload mid-flight resumes |
| PR4 | `lib/sanctuary/sleepDynamics.ts` + test; wire into `companionAction.ts` + sleep endpoint | Tired gate after 24h; full cycle clears + grants ≥ floor; early-wake −2 + journal | All three cases via time-skip helper |
| PR5 | `sanctuary_companion_streaks` migration; `lib/sanctuary/streaks.ts`; HUD chip in `CompanionHUD.tsx` | 1-miss pauses, 2-misses reset, milestone fires once | 9-day timeline w/ 1 miss; streak still active; 7-day journal entry |
| PR6 | Gacha pull in `components/sanctuary/overlays/ShopDialog.tsx` | Every pull yields ≥1 cosmetic; 1000-pull distribution within tolerance | 5 pulls all yield; rare badge fires on rare |
| PR7 | `lib/sanctuary/variableRewards.ts` + test; wire into `companionAction.ts` after preference + need-state | 1000-sim distribution within ±0.5%; bonus badge fires; floor always present | 50 interactions w/ fixed seed; bonus badge ≥1; floor in journal every time |

## Cosmic Casino — BB merge-in (2026-05-15, **Phase A done; B–F structured**)

Operator-bound: MegaETH is treated as a failed experiment. The BunnyBagz
contract stack (`mega-house` repo) was absorbed into SWO as the casino
layer on Monad. Full migration plan and branding rationale:
`memory/evolution/bb_swo_monad_repositioning_2026-05-15.md`. Implementation
log (Phase A): `memory/evolution/cosmic_casino_monad_testnet_live_2026-05-15.md`.
**End-to-end delivery plan (Phases B–F)**: `memory/evolution/cosmic_casino_delivery_plan_2026-05-15.md`
— authoritative for QA / E2E / rollout / contract verification / monitoring /
launch checklist / post-launch hardening.

**Branding locked in (autonomous decision 2026-05-15):**
- Sub-brand: **Cosmic Casino** (matches `app/casino/page.tsx` `<title>`; aligns with SWO's "Cosmic Mandate" + "cosmic realm" copy).
- `CosmicFlip` (UI: **Cosmic Flip**) — heads/tails, 1.98× payout.
- `GravityDice` (UI: **Gravity Dice**) — roll-under 2..98, `99/(R-1)` multiplier.
- `ConstellationClimb` (UI: **Constellation Climb**) — Hi-Lo session, multi-step compounding.
- `CasinoBankroll`, `CasinoAllowlist`, `CommitRevealRandomness` (internal/library names).
- Header placement: `CASINO` link added between `RAFFLE` and dev-only `STARFORGE`.

**Monad testnet deploy — LIVE on chain 10143 (2026-05-15):**
- `CasinoBankroll`: `0x33C5B6a95e71611F5dC821A74DDAD0F746fF2dFf`
- `CosmicFlip`: `0x064b8bfc03b23D2b525deD9d3969090347A21983`
- `GravityDice`: `0xAC023542A8168465EE4A1b3e8Ae0f58F36A6d84B`
- `ConstellationClimb`: `0xd9B9b6c37ad4f3D5b07ae76dE261c5C865600d6e`
- Deployer (1/1 owner): `0xb29e6735629539cEd64F0d6f0c476Fe92539fD7B` (carried from BB; ~19 MON remaining).
- Bankroll seed: 0.02 MON; drawdown breaker armed at 0.01 MON/24h.

| # | Phase | Task | Lane tag | Status |
|---|------|------|----------|--------|
| C1 | A | Operator: claim ≥0.5 MON from `faucet.monad.xyz` to deployer | `[SWO_CASINO_FAUCET]` | ✅ already funded (20 MON pre-existing) |
| C2 | B | Port BB Solidity stack into SWO `contracts/casino/src/*.sol` (mechanical rename) | `[SWO_CASINO_CONTRACTS_PORT]` | ✅ shipped 2026-05-15 |
| C3 | B | Port BB Foundry tests into `contracts/casino/test/` + integration suite | `[SWO_CASINO_TEST_PORT]` | ✅ 6/6 passing (smoke) — full BB suite port TODO |
| C4 | C | Verify CreateX (`0xba5Ed099...ba5Ed`) on Monad testnet | `[SWO_CASINO_CREATEX_VERIFY]` | ✅ already present, verified |
| C5 | C | Deploy CasinoBankroll + 3 games to Monad testnet 10143 via CREATE3 | `[SWO_CASINO_TESTNET_DEPLOY]` | ✅ shipped 2026-05-15 |
| C6 | C | Register games on bankroll, seed bankroll, write `lib/casino/addresses.ts` | `[SWO_CASINO_TESTNET_WIRE]` | ✅ shipped (address book exported) |
| C7 | D | Port Coinflip betting page from BB `apps/web` → `app/casino/coinflip/page.tsx` | `[SWO_CASINO_COINFLIP_UI]` | ✅ PR #306 (`1725354`, 2026-05-17) |
| C8 | D | Port Dice betting page → `app/casino/dice/page.tsx` | `[SWO_CASINO_DICE_UI]` | ✅ PR #309 (`b501115`, 2026-05-17) |
| C9 | D | Port HiLo betting page → `app/casino/constellation-climb/page.tsx` | `[SWO_CASINO_HILO_UI]` | ⏳ open — only D10 not yet shipped in Phase D |
| C10 | D | Add `CASINO` link to `components/Header.tsx` (desktop + mobile) | `[SWO_CASINO_NAV]` | ✅ shipped 2026-05-15 |
| C11 | D | Replace BB mascot art with Star Skrumpey art across casino surfaces | `[SWO_CASINO_MASCOT_SWAP]` | ⏳ depends on C7–C9 |
| C12 | D | Update `CasinoContent.tsx` card statuses to `'testnet'` / `'live'` | `[SWO_CASINO_STATUS_FLIP]` | ✅ shipped — `testnet` badge surfaced |
| C13 | — | Cancel BB Phase 3/4/5 queue items (`[BB_PHASE3_*]` etc.) — explicitly killed | `[SWO_CASINO_BB_CANCEL]` | ⏳ separate sweep task |
| C14 | E | (Operator gate) Audit, multisig migration, mainnet 143 deploy via CREATE3 same salts | `[SWO_CASINO_MAINNET]` | ⏸ blocked on audit + operator |

### Phase B — Foundry test suite full port (P0, autonomous)

| # | Phase | Tag | Description | Status |
|---|---|---|---|--------|
| B1 | B | `[SWO_CASINO_TEST_PORT_BANKROLL]` | Port Bankroll unit + breaker + invariant | ✅ PR #287 (`4b31b96`) |
| B2 | B | `[SWO_CASINO_TEST_PORT_COINFLIP]` | Port Coinflip unit + commit-replay + Halmos | ✅ PR #288 (`f340b14`) |
| B3 | B | `[SWO_CASINO_TEST_PORT_DICE]` | Port Dice unit | ✅ PR #289 (`f625b83`) |
| B4 | B | `[SWO_CASINO_TEST_PORT_HILO]` | Port HiLo→ConstellationClimb unit | ✅ PR #290 (`1c02775`) |
| B5 | B | `[SWO_CASINO_TEST_PORT_RANDOMNESS]` | Port randomness lib unit | ✅ PR #291 (`18dccd8`) |
| B6 | B | `[SWO_CASINO_TEST_PORT_ALLOWLIST]` | Port allowlist unit | ✅ PR #292 (`52b8805`) |
| B7 | B | `[SWO_CASINO_TEST_PORT_DEPLOY_DETERMINISTIC]` | CREATE3 prediction = actual on local anvil + Monad dry-run | ✅ (`70396fc`) |
| B8 | B | `[SWO_CASINO_TEST_PORT_MEDUSA]` | Port Medusa invariant harness | ✅ PR #293 (`7045981`) |
| B9 | B | `[SWO_CASINO_TEST_COVERAGE_BAR]` | `forge coverage` ≥ 90% on `contracts/casino/src/` | ⏳ verify — `docs/casino/coverage_<date>.md` claim flagged in `[SWO_CASINO_FORGE_COVERAGE_VERIFY_2026-05-16]` |

### Phase C — CI integration (P0, autonomous)

| # | Phase | Tag | Description | Status |
|---|---|---|---|--------|
| C-CI1 | C | `[SWO_CASINO_CI_FORGE_TEST]` | `.github/workflows/casino-forge.yml` runs `forge test` on PRs | ✅ PR #295 (`4954ef0`) |
| C-CI2 | C | `[SWO_CASINO_CI_FORGE_COVERAGE]` | `forge coverage` ≥ 90% line gate | ✅ PR #295 (`e7cb5a6`) |
| C-CI3 | C | `[SWO_CASINO_CI_FOUNDRY_FMT]` | `forge fmt --check` job | ✅ PR #296 (`12cb6a8`) |
| C-CI4 | C | `[SWO_CASINO_CI_VITEST]` | Vitest casino project on casino path changes | ✅ PR #299 (`97de879`) |
| C-CI5 | C | `[SWO_CASINO_CI_E2E]` | Playwright connected suite on anvil-forked Monad | ✅ PR #300 (`c88bc2d`) |

### Phase D — UI port (P0, autonomous, ~3–4 sessions)

| # | Phase | Tag | Description | Status |
|---|---|---|---|--------|
| D1 | D | `[SWO_CASINO_LIB_CHAIN_CLIENT]` | Port `packages/chain` adapter → `lib/casino/{chain,abi,bets}.ts` | ✅ (`efdd113`) |
| D2 | D | `[SWO_CASINO_LIB_VERIFY]` | Port `packages/verify` → `lib/casino/verify.ts` | ✅ (`efdd113`) |
| D3 | D | `[SWO_CASINO_COMPONENT_BET_PANEL]` | Port BetPanel + CTA dwell ≥600ms (BB QA lesson F3) | ✅ PR #300 (`2b0c073`) |
| D4 | D | `[SWO_CASINO_COMPONENT_TRUST_STRIP]` | Port TrustStrip + mobile-44 hit floor | ✅ PR #301 (`7b358ab`) |
| D5 | D | `[SWO_CASINO_COMPONENT_WALLET_SHEET]` | Port WalletSheet + focus trap | ✅ PR #302 (`db51227`) |
| D6 | D | `[SWO_CASINO_COMPONENT_RECENT_BETS]` | Port RecentBets (empty until indexer) | ✅ PRs #303/#304 (`91cdc3e`, `800a89d`) |
| D7 | D | `[SWO_CASINO_COMPONENT_FAIRNESS_PROOF]` | Port FairnessProof commit/reveal display | ✅ PR #305 (`efdd113`) |
| D8 | D | `[SWO_CASINO_COINFLIP_UI]` | `/casino/coinflip/page.tsx` end-to-end bet flow | ✅ PR #306 (`1725354`) |
| D9 | D | `[SWO_CASINO_DICE_UI]` | `/casino/dice/page.tsx` with rollUnder slider | ✅ PR #309 (`b501115`) |
| D10 | D | `[SWO_CASINO_HILO_UI]` | `/casino/constellation-climb/page.tsx` open/step/cashOut | ⏳ **NEXT** — all deps shipped (D1–D7, D11). Pick today. |
| D11 | D | `[SWO_CASINO_UI_CHAIN_GATE]` | "Switch to Monad" CTA for wrong-chain users | ✅ PR #310 (`74f90d1`) |
| D12 | D | `[SWO_CASINO_TESTNET_OPEN_ACCESS]` | `AccessGate` bypass on chain 10143 for QA | ⏳ unblocks operator smoke gate T5 |
| D13 | D | `[SWO_CASINO_MASCOT_SWAP]` | Star Skrumpey dealer art (reuse SWO IP, no RD spend) | ⏳ runnable for D8/D9 surfaces now (D10 added after PR) |
| D14 | D | `[SWO_CASINO_NATSPEC_BLOCK_TIME_FIX]` | Sweep "≈25s on MegaETH" → "≈2 min on Monad" in code+docs+UI copy | ⏳ |
| D15 | D | `[SWO_CASINO_ALLOWLIST_UI_GATE]` | UI reads `game.allowlist()` and pre-checks before signing | ⏳ runnable for D8/D9 now |

### Phase E — Off-chain infra (P1, autonomous)

| # | Phase | Tag | Description | Status |
|---|---|---|---|--------|
| E1 | E | `[SWO_CASINO_KEEPER_PORT]` | Port seed-manager keeper to daemon / Vercel cron / Defender Autotask | ⏳ |
| E2 | E | `[SWO_CASINO_KEEPER_DOCTOR]` | Port `keeper/doctor.ts` + `/api/casino/health` route | ⏳ |
| E3 | E | `[SWO_CASINO_KEEPER_HEALTH_MONITOR]` | Cron-driven liveness alert (Telegram if offline >5 min) | ⏳ |
| E4 | E | `[SWO_CASINO_INDEXER_PORT]` | Ponder config → Monad 10143; hosting target operator-decided | ⏳ |
| E5 | E | `[SWO_CASINO_DEFENDER_MONITORS_PORT]` | Port 4 Defender monitors retargeted at monad-testnet network | ⏳ |
| E6 | E | `[SWO_CASINO_DEFENDER_ACTION_TELEGRAM]` | Telegram forwarder → SWO ops chat | ⏳ |
| E7 | E | `[SWO_CASINO_BANKROLL_TOP_UP_RUNBOOK]` | `docs/runbooks/CASINO_BANKROLL_TOPUP.md` + alert <0.05 MON | ⏳ |
| E8 | E | `[SWO_CASINO_BREAKER_STRESS_TEST]` | Synthetic bot load fires breaker on testnet; `stress_breaker.sh` | ⏳ |

### Phase F — QA, E2E, verification, runbooks, checklist (P1, autonomous)

| # | Phase | Tag | Description | Status |
|---|---|---|---|--------|
| F1 | F | `[SWO_CASINO_QA_HARNESS_PORT]` | Port `apps/web/scripts/qa/{run,audits,report}.mjs` for `/casino/*` | ⏳ |
| F2 | F | `[SWO_CASINO_QA_DEFECT_TAXONOMY]` | Adopt 8 BB defect classes for casino harness | ⏳ |
| F3 | F | `[SWO_CASINO_PLAYWRIGHT_CONNECTED]` | `e2e/casino/{coinflip,dice,climb}.connected.spec.ts` | ⏳ |
| F4 | F | `[SWO_CASINO_PLAYWRIGHT_FOCUS_RING]` | `e2e/casino/focus-ring.spec.ts` | ⏳ |
| F5 | F | `[SWO_CASINO_PLAYWRIGHT_VISUAL_BASELINE]` | Snapshot 375×812 + 1280×800 baselines | ⏳ |
| F6 | F | `[SWO_CASINO_VITEST_BET_PANEL]` | BetPanel component tests (44px hit floor, 600ms dwell, 12px floor) | ⏳ |
| F7 | F | `[SWO_CASINO_MONADSCAN_VERIFY]` | `forge verify-contract` 4 contracts on Monadscan testnet | ⏳ |
| F8 | F | `[SWO_CASINO_MAINNET_ADDRESS_PREDICTION]` | Publish predicted mainnet 143 addresses in `DEPLOYED.md` | ⏳ |
| F9 | F | `[SWO_CASINO_OPERATOR_SMOKE_RUNBOOK]` | `docs/runbooks/CASINO_TESTNET_SMOKE.md` (operator-driven) | ⏳ |
| F10 | F | `[SWO_CASINO_LAUNCH_CHECKLIST]` | `docs/runbooks/CASINO_LAUNCH_CHECKLIST.md` — T1–T14 + M1–M14 | ⏳ |
| F11 | F | `[SWO_CASINO_POST_LAUNCH_HARDENING]` | `docs/runbooks/CASINO_POST_LAUNCH.md` — first-30-days cadence | ⏳ |
| F12 | F | `[SWO_CASINO_TESTNET_EXIT_DOC]` | `cosmic_casino_testnet_exit_<date>.md` mirroring `bb_phase2_testnet_live` shape | ⏳ |

### Phase G — Mainnet (P2, OPERATOR-GATED, no autonomous execution)

| # | Phase | Tag | Description | Status |
|---|---|---|---|--------|
| G1 | G | `[SWO_CASINO_AUDIT_PICK]` | Operator picks audit firm (Spearbit / ToB / Cyfrin / ChainSecurity) | ⏸ operator |
| G2 | G | `[SWO_CASINO_MULTISIG_MIGRATION]` | Ownership: EOA → SWO governance multisig (Safe on chain 143) | ⏸ operator |
| G3 | G | `[SWO_CASINO_GEO_BLOCKLIST]` | OFAC + 9-country block (carry over from BB) at route layer + WAF | ⏸ operator |
| G4 | G | `[SWO_CASINO_RESPONSIBLE_GAMING_PAGE]` | Port `/responsible-gaming` page + legal review | ⏸ operator |
| G5 | G | `[SWO_CASINO_MAINNET_DEPLOY]` | `bash script/deploy-mainnet.sh` (same salts ⇒ same addresses) | ⏸ operator |
| G6 | G | `[SWO_CASINO_MAINNET_SEED]` | Initial bankroll seed (operator-sized; suggested 10–50 MON) | ⏸ operator |
| G7 | G | `[SWO_CASINO_MAINNET_OWNERSHIP_HANDOVER]` | `transferOwnership` to multisig; revoke deployer | ⏸ operator |
| G8 | G | `[SWO_CASINO_MAINNET_SMOKE]` | Operator smoke on chain 143 (min stakes, 3 games) | ⏸ operator |
| G9 | G | `[SWO_CASINO_STATUS_FLIP_MAINNET]` | UI status `'live'` on chain 143 in `CasinoContent.tsx` | ⏸ operator |

### Testnet exit gates (must all green before mainnet ceremony)

| # | Gate | Owner phase | Status |
|---|---|---|--------|
| T1 | Foundry coverage ≥ 90% | B | ⏳ |
| T2 | CI `forge test` green on PRs | C | ⏳ |
| T3 | All 3 game UIs live on `/casino/<game>` | D | ⏳ |
| T4 | Chain-gate works for wrong-chain users | D | ⏳ |
| T5 | Operator smoke: 3 bets settled on chain 10143 | F | ⏳ |
| T6 | Defender monitors firing on testnet | E | ⏳ |
| T7 | Keeper online ≥ 24h with clean health log | E | ⏳ |
| T8 | Breaker stress test fires + resets cleanly | E | ⏳ |
| T9 | Bankroll never <0.05 MON for >5 min | E | ⏳ |
| T10 | Monadscan verified for all 4 contracts | F | ⏳ |
| T11 | Mainnet addresses predicted and published | F | ⏳ |
| T12 | QA harness: zero HIGH findings across 48 variants | F | ⏳ |
| T13 | NatSpec/UI copy block-time sweep done | D | ⏳ |
| T14 | `[SWO_CASINO_BB_CANCEL]` BB phase 3/4/5 sweep done | Clarvis | ⏳ |

Resolved operator decisions (autonomous, 2026-05-15):
- Deployer key: **reuse** BB deployer (it's funded, owns the salts). Same address on every chain via CREATE3.
- Sub-brand & game names: **ratified** — Cosmic Casino / Cosmic Flip / Gravity Dice / Constellation Climb.
- Header slot: `CASINO` in main nav (not nested under STARFORGE).
- Geo blocklist: carry forward at mainnet time (defer until C14).

## Notes

- Fork workflow: GranusClarvis has pull-only on InverseAltruism repo. Push to fork, PR targets upstream.
- Agent root: `/opt/clarvis-agents/star-world-order/` or `/home/agent/agents/star-world-order/`
- SWO repo: `GranusClarvis/Star-World-Order` (fork of `InverseAltruism/Star-World-Order`)
