# Claw-Empire Visual Dashboard — Deep Dive Notes

_Extracted from [GreenSheep01201/claw-empire](https://github.com/GreenSheep01201/claw-empire) on 2026-03-06._
_Purpose: inform Clarvis ORCH_VISUAL_DASHBOARD implementation._

---

## 1. Frontend Directory Structure

```
src/
├── components/
│   ├── office-view/          # ★ Core visual renderer (20 files, ~150KB)
│   │   ├── model.ts                    # Constants, types, particle emitter configs
│   │   ├── buildScene-types.ts         # TypeScript interfaces for build context
│   │   ├── buildScene.ts              # Main scene orchestrator — calls sub-builders
│   │   ├── buildScene-ceo-hallway.ts  # CEO office + hallways rendering
│   │   ├── buildScene-departments.ts  # Department rooms with agents
│   │   ├── buildScene-department-agent.ts  # Agent desk/avatar + sub-clones
│   │   ├── buildScene-break-room.ts   # Break room with furniture + chat bubbles
│   │   ├── buildScene-final-layers.ts # CEO sprite, delivery layer, highlight overlay
│   │   ├── drawing-core.ts            # Low-level drawing primitives (floor, walls, clock)
│   │   ├── drawing-furniture-a.ts     # Desk, chair, plant, whiteboard
│   │   ├── drawing-furniture-b.ts     # Bookshelf, coffee machine, sofa, vending
│   │   ├── officeTicker.ts            # Main animation loop/ticker
│   │   ├── officeTickerRoomAndDelivery.ts  # Break room & delivery sub-animations
│   │   ├── useOfficePixiRuntime.ts    # React hook: Pixi init, asset loading, keyboard
│   │   ├── useOfficeDeliveryEffects.ts # Meeting presence, deliveries, CEO calls
│   │   ├── themes-locale.ts           # Color themes (light/dark), i18n, locale helpers
│   │   ├── CliUsagePanel.tsx          # HTML/CSS CLI usage bar charts (not Pixi)
│   │   ├── useCliUsage.ts             # React hook for CLI usage polling
│   │   └── VirtualPadOverlay.tsx      # Mobile D-pad (HTML/CSS)
│   ├── dashboard/             # HTML/CSS stats dashboard (React + Tailwind)
│   ├── agent-detail/          # Agent info panel
│   ├── agent-manager/         # CRUD for agents + departments
│   ├── taskboard/             # Kanban-style task board
│   └── ...
├── hooks/
│   ├── useWebSocket.ts        # WS connection + reconnection
│   └── usePolling.ts          # Visibility-aware HTTP polling fallback
├── app/
│   ├── useRealtimeSync.ts     # WS event → state update dispatcher
│   ├── useLiveSyncScheduler.ts # Debounced full-state HTTP fetcher
│   └── useAppBootstrapData.ts  # Initial REST data fetch
├── types/
│   └── index.ts               # Agent, Task, WSEventType, etc.
├── api/
│   └── ...                    # REST API client wrappers
└── styles/
    └── ...                    # Tailwind CSS

server/
├── ws/
│   └── hub.ts                 # ★ WS broadcast hub with batching
├── modules/
│   ├── lifecycle.ts           # HTTP + WS server creation, graceful shutdown
│   └── workflow/
│       ├── core.ts            # Active processes map, worktree lifecycle
│       ├── orchestration/     # Task execution, completion, review finalization
│       └── agents/            # Subtask routing, seeding, CLI runtime

public/
└── sprites/                   # Character PNGs (1-14, 5 frames each + CEO)
```

## 2. Rendering Engine — PixiJS 8 Procedural Graphics

### Stack
- **PixiJS 8** (`pixi.js ^8.6.6`) — WebGL 2D renderer
- **No sprite sheets for environment** — all rooms/furniture/decorations drawn with `Graphics` primitives
- **Character sprites only**: 14 designs × 5 frames (3 down-walk + left + right) = 71 PNGs
- **React 19** wraps Pixi via `useOfficePixiRuntime` hook (Pixi state in refs, not React state)
- **Tailwind v4** for non-Pixi UI panels (CliUsagePanel, VirtualPad, Dashboard)

### Canvas Init
```typescript
// useOfficePixiRuntime.ts:78-97
const app = new Application();
await app.init({
  width: containerWidth,
  height: 600,
  backgroundAlpha: 0,
  antialias: false,                    // pixel art
  resolution: Math.min(devicePixelRatio, 2),
  autoDensity: true,
});
TextureStyle.defaultOptions.scaleMode = "nearest";  // crisp pixels
canvas.style.imageRendering = "pixelated";
```

### Room Layout (Vertical Stack)
```
┌─────────────────────────────────┐
│ CEO Office (110px)              │  buildScene-ceo-hallway.ts
├─────────────────────────────────┤
│ Hallway (32px)                  │
├────────┬────────┬───────────────┤
│ Dept 1 │ Dept 2 │ Dept 3        │  buildScene-departments.ts
│ 3 cols │        │               │  (grid: COLS_PER_ROW=3, SLOT_W=100, SLOT_H=120)
│ /row   │        │               │
├────────┴────────┴───────────────┤
│ Hallway (32px)                  │
├─────────────────────────────────┤
│ Break Room (110px)              │  buildScene-break-room.ts
└─────────────────────────────────┘
```

Constants from `model.ts`:
- `TILE = 20` (floor tile size), `CEO_ZONE_H = 110`, `HALLWAY_H = 32`
- `SLOT_W = 100`, `SLOT_H = 120`, `COLS_PER_ROW = 3`
- `TARGET_CHAR_H = 52` (agent sprite height)

### Procedural Drawing Pattern (Key Reusable Technique)
All furniture is multi-layered `Graphics` — shadow ellipse → base fill → inset highlight → detail:
```typescript
// drawing-furniture-a.ts — desk example (simplified)
function drawDesk(parent, dx, dy, working) {
  const g = new Graphics();
  // Shadow layers for depth
  g.ellipse(dx + DESK_W/2, dy + DESK_H + 4, DESK_W/2 + 6, 6)
   .fill({color: 0x000000, alpha: 0.06});
  // Base wood
  g.roundRect(dx, dy, DESK_W, DESK_H, 3).fill(0xbe9860);
  g.roundRect(dx+1, dy+1, DESK_W-2, DESK_H-2, 2).fill(0xd4b478);
  // Monitor: active vs idle
  g.roundRect(mx+1.5, my+1, 17, 10, 1)
   .fill(working ? 0x89c8b9 : 0x1e2836);
  parent.addChild(g);
}
```

### Color Utilities
```typescript
// drawing-core.ts:11-39
function blendColor(from, to, t) { /* RGB channel lerp */ }
function contrastTextColor(bg)   { /* YIQ luminance threshold at 150 */ }
function hashStr(s)              { /* deterministic hash for visual variety */ }
```

### Dark Mode
Module-level mutable palette, swapped on theme change:
```typescript
// themes-locale.ts
let OFFICE_PASTEL = OFFICE_PASTEL_LIGHT;
function applyOfficeThemeMode(isDark) {
  OFFICE_PASTEL = isDark ? OFFICE_PASTEL_DARK : OFFICE_PASTEL_LIGHT;
}
// Department themes: { floor1, floor2, wall, accent }
```

## 3. Agent Visual States — Status → Rendering Map

| Status / Condition | Tint | Alpha | Rotation | Particles | Extra Visuals |
|---|---|---|---|---|---|
| `working` (normal) | 0xffffff | 1.0 | 0 | Star sparks q10 ticks | Task speech bubble, monitor=code |
| `working` (util≥60%) | 0xffffff | 1.0 | 0 | Sweat drops q55 ticks | — |
| `working` (util≥80%) | 0xff9999 | 1.0 | 0 | Sweat drops q40 ticks | — |
| `working` (util≥100%) | 0xff6666 | 0.85 | -π/2 (lying) | Dizzy stars + "z" text | Bed+blanket, desk hidden |
| `offline` | 0x888899 | 0.3 | 0 | None | "💤" emoji overlay |
| `break` | — | — | — | — | Agent moves to break room; "away" tag at desk |
| `in meeting` | hidden at desk | — | — | — | Walking sprite at CEO meeting table |

**Sub-clones** (parallel sub-agents): 76%-scale sprites near parent, shadow aura, wave-motion drift, firework bursts on spawn/despawn. Max 3 visible + "+N" badge for overflow.

### Particle System (No Library)
Particles are plain `Graphics` nodes with custom props via `as any`:
```typescript
// Emit star particle
const p = new Graphics();
p.star(0, 0, 4, 2, 1, 0).fill(color);
(p as any)._vy = -0.4 - Math.random() * 0.3;
(p as any)._life = 0;
particles.addChild(p);

// Update in ticker
p._life++;
p.y += p._vy;
p.alpha = Math.max(0, 1 - p._life * 0.03);
if (p._life > 35) { particles.removeChild(p); p.destroy(); }
```

### Sprite Loading
```typescript
// useOfficePixiRuntime.ts:101-141
// Preloads all 13 sprites × 5 frames + CEO in parallel
for (const spriteNum of spriteNums) {
  for (const frame of [1, 2, 3]) {           // down-walk animation
    loads.push(Assets.load(`/sprites/${spriteNum}-D-${frame}.png`));
  }
  for (const dir of ["L", "R"]) {            // left/right facing
    loads.push(Assets.load(`/sprites/${spriteNum}-${dir}-1.png`));
  }
}
loads.push(Assets.load("/sprites/ceo-lobster.png"));
await Promise.all(loads);  // errors silently caught → emoji fallback
```

## 4. Animation Loop / Ticker

Driven by PixiJS's built-in `app.ticker` (RAF-based). `runOfficeTickerStep(ctx)` runs every frame:

1. **Wall clocks**: Hour/minute/second hand rotation via trigonometry (q1s)
2. **CEO movement**: Arrow/WASD at `CEO_SPEED=7` px/frame, clamped to bounds. Crown bounce: `Math.sin(tick * 0.06) * 2`
3. **Room highlight**: Pulsing border when CEO overlaps room rect (`alpha: 0.5 + Math.sin(tick * 0.08) * 0.2`)
4. **Agent particles**: Per-agent status-based particle spawning (stars, sweat, dizzy)
5. **Sub-clone drift**: Sine/cosine wave motion (`SUB_CLONE_WAVE_SPEED = 0.04`), periodic firework bursts
6. **Break room**: Agent sway, coffee steam, chat bubble pulse
7. **Deliveries**: Eased interpolation — `throw` uses parabolic arc, `walk` uses bounce

### Easing Functions
```typescript
// Quadratic ease-in-out
const ease = t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
// Walk bounce
const walkBounce = Math.abs(Math.sin(t * Math.PI * 12)) * 3;
```

### Scene Rebuild Strategy
Scene is destroyed and rebuilt from scratch when data changes:
```typescript
// buildScene.ts:69-73
const oldChildren = app.stage.removeChildren();
for (const child of oldChildren) {
  if (preservedDeliverySprites.has(child)) continue;  // preserve in-flight
  if (!child.destroyed) child.destroy({ children: true });
}
```

## 5. WebSocket Event Transport Layer

### Server Setup
- **Library**: `ws` (Node.js)
- **Port**: Same as HTTP (default 8790), path `/ws`
- **Auth**: Checks `isIncomingMessageOriginTrusted()` + `isIncomingMessageAuthenticated()` on connect; 1008 close = unauthorized

### Hub Broadcasting (`server/ws/hub.ts`)
```typescript
// Wire format
{ "type": "<WSEventType>", "payload": <any>, "ts": <number_ms> }
```

**Batched event types** (high-frequency → cooldown window):
- `cli_output`: **250ms** cooldown, max queue 60
- `subtask_update`: **150ms** cooldown, max queue 60

**Non-batched** (immediate):
- `task_update`, `agent_status`, `agent_created`, `agent_deleted`, `departments_changed`
- `new_message`, `announcement`, `cli_usage_update`
- `cross_dept_delivery`, `ceo_office_call`, `chat_stream`, `task_report`

**First-event-immediate pattern**: First event in a batch window fires immediately; subsequent queue up and flush when timer fires. Overflow: FIFO shed (shift oldest, push newest).

### Event Types + Payload Schemas

| Event Type | Payload | Notes |
|---|---|---|
| `connected` | `{ version, app }` | Sent once on WS connect |
| `task_update` | Full `Task` object | Triggers debounced live sync |
| `agent_status` | `Agent` + optional `subAgents[]` | Direct state patch (NOT batched) |
| `agent_created` | — | Triggers live sync |
| `agent_deleted` | — | Triggers live sync |
| `departments_changed` | — | Triggers live sync |
| `new_message` | `Message` object | Direct append (cap 600) |
| `announcement` | `Message` object | Direct append |
| `cli_output` | `{ task_id, stream?, data }` | **Batched 250ms** |
| `cli_usage_update` | usage data | Direct |
| `subtask_update` | `SubTask` object | **Batched 150ms** |
| `cross_dept_delivery` | `{ from_agent_id, to_agent_id }` | Animation trigger |
| `ceo_office_call` | `{ from_agent_id, seat_index?, phase?, action?, decision?, ... }` | Animation trigger |
| `chat_stream` | `{ phase: start|delta|end, message_id, agent_id, text?, ... }` | Streaming LLM output |
| `task_report` | `{ task?: { id? } }` | Report popup trigger |

### Client-Side Connection (`src/hooks/useWebSocket.ts`)
- Protocol: `wss:` for HTTPS, `ws:` for HTTP
- Pre-connect: `bootstrapSession()` (HTTP auth)
- Reconnect on close: **2000ms** delay
- 1008 close: forces session re-bootstrap
- Listeners: `Map<WSEventType, Set<Listener>>`, returns unsubscribe function

### Two-Tier Real-Time Sync
1. **Tier 1 (WS events)**: Instant patches for latency-sensitive data (agent_status, messages, streaming)
2. **Tier 2 (HTTP polling)**: Debounced full-state fetch (`getTasks + getAgents + getStats + getDecisionInbox`), 5s periodic + event-triggered (60-160ms delay)
3. **Fallback**: `usePolling` hook — generic visibility-aware HTTP polling at 3s intervals

## 6. Entity Models

### Agent
```typescript
interface Agent {
  id: string;
  name: string;
  department_id: string | null;
  role: "team_leader" | "senior" | "junior" | "intern";
  cli_provider: "claude" | "codex" | "gemini" | "opencode" | "copilot" | "antigravity" | "api";
  avatar_emoji: string;
  sprite_number?: number | null;
  status: "idle" | "working" | "break" | "offline";
  current_task_id: string | null;
  stats_tasks_done: number;
  stats_xp: number;
}
```

### Task
```typescript
interface Task {
  id: string;
  title: string;
  description: string | null;
  assigned_agent_id: string | null;
  status: "inbox" | "planned" | "collaborating" | "in_progress" | "review" | "done" | "pending" | "cancelled";
  priority: number;
  task_type: "general" | "development" | "design" | "analysis" | "presentation" | "documentation";
  result: string | null;
  started_at: number | null;
  completed_at: number | null;
}
```

### SubAgent (Ephemeral)
```typescript
interface SubAgent {
  id: string;
  parentAgentId: string;
  task: string;
  status: "working" | "done";
}
```

## 7. Key Patterns to Steal for Clarvis

### P1: Procedural Graphics (No Asset Pipeline)
All rooms/furniture drawn with `Graphics` primitives. Zero asset build step. Theme swap = repaint with different color constants. **Directly applicable** — Clarvis dashboard can be a single `.js` file with `drawRoom()`, `drawDesk()`, `drawAgent()` functions.

### P2: First-Event-Immediate Batching
```
Event 1 → send immediately, start 250ms timer
Event 2 (within 250ms) → queue
Event 3 (within 250ms) → queue
Timer fires → flush queue as batch
```
Overflow cap (60 items) prevents memory leak. **Adapt for SSE**: same pattern, serialize batch as multi-event SSE payload.

### P3: Custom Particle System (No Library)
Plain `Graphics` nodes with `_vy`, `_life` custom props. Update in ticker. Destroy when life > max. Under 20 LOC. **Copy verbatim** for Clarvis working/idle/error sparkles.

### P4: Scene Rebuild on Data Change
Don't try to diff the scene graph. Destroy all children, rebuild from data. Preserve only in-flight animations. Simple, correct, fast enough for our scale.

### P5: Hash-Based Deterministic Randomness
```typescript
function hashStr(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}
```
Use for: agent desk position jitter, chat message selection, sprite assignment.

### P6: Auto-Commit File Safety
Extension allowlist + blocked patterns. **Already queued** as [ORCH_AUTOCOMMIT_SAFETY].

### P7: Visibility-Aware Polling
Stop fetching when tab hidden, resume + immediate fetch on visibility change. Critical for LAN dashboard left open all day.

### P8: Two-Tier Sync (Events + Periodic Full Refresh)
WS/SSE for instant updates; periodic HTTP full-state fetch as safety net. Avoids complex server-side diff logic.

## 8. Clarvis Implementation Blueprint

### Recommended Stack

| Layer | Choice | Rationale |
|---|---|---|
| Event hub | **Starlette SSE** (Python, port 18791) | Already in our stack; SSE = simpler than WS for read-only dashboard; no npm server needed |
| Renderer | **PixiJS 8** (vanilla JS, no React) | Same as claw-empire; procedural Graphics for rooms; character sprites optional (emoji fallback) |
| HTTP | **Starlette** (same process) | `GET /state` for full snapshot, `GET /sse` for EventSource stream |
| Serving | **Starlette `StaticFiles`** | Serve `index.html` + `app.js` from same server |

**Why not React?** Our dashboard is view-only (no forms, no CRUD). Vanilla JS + PixiJS is ~300 LOC frontend vs ~2000 LOC with React. claw-empire uses React because they have interactive panels (task creation, agent management, settings).

**Why SSE over WebSocket?** Read-only dashboard. SSE is simpler (no handshake upgrade, auto-reconnect built into `EventSource`), works through proxies, and Starlette has native SSE support. claw-empire uses WS because they need bidirectional (chat, commands).

### Minimal P0 Implementation (1 room + 5 agents + live updates)

**Backend: `scripts/dashboard_server.py`** (~200 LOC)
```python
# Starlette app
# GET /         → serves static/index.html
# GET /state    → JSON snapshot (queue tasks, agent statuses, recent cron activity)
# GET /sse      → SSE stream (event types below)
# Data sources: QUEUE.md, digest.md, lockfiles, scoreboard JSONL, gh pr list

# SSE event types:
# task_started   → { agent, task_tag, started_at }
# task_completed → { agent, task_tag, status, duration }
# agent_status   → { agent, status: idle|working|offline, current_task }
# queue_update   → { pending_count, in_progress_count }
# cron_activity  → { script, started_at, status }
# pr_update      → { repo, pr_number, title, status, url }
```

**Frontend: `scripts/dashboard_static/index.html`** + **`app.js`** (~400 LOC)
```
┌──────────────────────────────────────┐
│  Clarvis Ops Dashboard        [LIVE] │
├──────────────────────────────────────┤
│                                      │
│  ┌──────┐ ┌──────┐ ┌──────┐        │
│  │Agent1│ │Agent2│ │Agent3│  Room   │
│  │ ★★★  │ │ 💤   │ │ ⚡   │        │
│  │ task  │ │ idle │ │ task │        │
│  └──────┘ └──────┘ └──────┘        │
│                                      │
│  ┌──────┐ ┌──────┐                  │
│  │Agent4│ │Agent5│                  │
│  │ 🔧   │ │ ⛔   │                  │
│  └──────┘ └──────┘                  │
│                                      │
├──────────────────────────────────────┤
│ Queue: 37 pending │ 1 active        │
│ Last: SEMANTIC_BRIDGE ✓ (3m ago)    │
│ PRs: #175 ✓ merged                  │
└──────────────────────────────────────┘
```

### Mapping to QUEUE Subtasks

| Task | Scope | LOC Est |
|---|---|---|
| `ORCH_VISUAL_DASHBOARD_2` | SSE event hub (`dashboard_server.py`): Starlette app, `/state`, `/sse`, data readers for QUEUE.md/digest/scoreboard/lockfiles. Batched broadcasting (250ms cooldown for `cron_activity`, immediate for `agent_status`). | ~200 |
| `ORCH_VISUAL_DASHBOARD_3` | PixiJS 8 renderer (`dashboard_static/app.js`): procedural room (1 room, tiled floor, walls, desks), agent sprites (emoji-based, status particles), status bar. Vanilla JS, `antialias:false`, `scaleMode:"nearest"`. | ~350 |
| `ORCH_VISUAL_DASHBOARD_4` *(new)* | SSE client + state sync (`dashboard_static/app.js`): `EventSource` connection, `onmessage` dispatch, scene rebuild on data change, visibility-aware reconnection. | ~50 (part of app.js) |
| `ORCH_VISUAL_DASHBOARD_5` | Hardening: bind `127.0.0.1` or LAN only, no command endpoints, rate limit SSE connections (max 5), serve static with `Cache-Control`. | ~30 |

### File Targets

```
scripts/
├── dashboard_server.py          # SSE hub + static serving (ORCH_VISUAL_DASHBOARD_2)
├── dashboard_events.py          # Event generation from data sources (ORCH_VISUAL_DASHBOARD_2)
└── dashboard_static/
    ├── index.html               # Single-page shell (ORCH_VISUAL_DASHBOARD_3)
    └── app.js                   # PixiJS renderer + SSE client (ORCH_VISUAL_DASHBOARD_3/4)
```

### Code Skeleton: SSE Event Hub

```python
# dashboard_server.py (skeleton)
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
import asyncio, json

clients: list[asyncio.Queue] = []

async def state_snapshot(request):
    """GET /state — full dashboard state."""
    return JSONResponse(build_state())

async def sse_stream(request):
    """GET /sse — SSE event stream."""
    queue = asyncio.Queue()
    clients.append(queue)
    try:
        async def event_generator():
            yield {"event": "state", "data": json.dumps(build_state())}
            while True:
                event = await queue.get()
                yield event
        return EventSourceResponse(event_generator())
    finally:
        clients.remove(queue)

async def broadcast(event_type: str, payload: dict):
    """Send event to all connected SSE clients."""
    msg = {"event": event_type, "data": json.dumps(payload)}
    for q in clients:
        await q.put(msg)

app = Starlette(routes=[
    Route("/state", state_snapshot),
    Route("/sse", sse_stream),
    Mount("/", StaticFiles(directory="dashboard_static", html=True)),
])
```

### Code Skeleton: PixiJS Renderer

```javascript
// app.js (skeleton)
import { Application, Graphics, Text, TextStyle } from "pixi.js";

const TILE = 20, SLOT_W = 90, SLOT_H = 100, COLS = 3;

async function init() {
  const app = new Application();
  await app.init({
    width: 600, height: 500,
    backgroundAlpha: 0, antialias: false,
    resolution: Math.min(devicePixelRatio, 2),
  });
  document.getElementById("canvas").appendChild(app.canvas);
  app.canvas.style.imageRendering = "pixelated";

  let state = await fetch("/state").then(r => r.json());
  buildScene(app, state);

  // SSE connection
  const es = new EventSource("/sse");
  es.addEventListener("agent_status", e => {
    const d = JSON.parse(e.data);
    updateAgentInState(state, d);
    rebuildScene(app, state);
  });
  // ... other event listeners

  // Ticker for particles
  app.ticker.add(() => updateParticles(app));
}

function buildScene(app, state) {
  app.stage.removeChildren().forEach(c => c.destroy({children:true}));
  drawRoom(app.stage, state);
  state.agents.forEach((a, i) => drawAgent(app.stage, a, i));
  drawStatusBar(app.stage, state);
}

function drawRoom(parent, state) {
  const g = new Graphics();
  // Tiled floor (checkerboard)
  for (let y = 0; y < 300; y += TILE)
    for (let x = 0; x < 600; x += TILE)
      g.rect(x, y, TILE, TILE)
       .fill((x/TILE + y/TILE) % 2 ? 0xd4c8a0 : 0xc8bc94);
  // Walls
  g.rect(0, 0, 600, 30).fill(0x8899aa);
  parent.addChild(g);
}

function drawAgent(parent, agent, idx) {
  const col = idx % COLS, row = Math.floor(idx / COLS);
  const x = 30 + col * (SLOT_W + 10), y = 50 + row * (SLOT_H + 10);
  // Desk
  const desk = new Graphics();
  desk.roundRect(x, y + 60, SLOT_W - 10, 25, 3).fill(0xd4b478);
  parent.addChild(desk);
  // Agent emoji
  const label = new Text({ text: agent.emoji || "🤖",
    style: new TextStyle({ fontSize: agent.status === "offline" ? 20 : 28 }) });
  label.position.set(x + 30, y + 20);
  label.alpha = agent.status === "offline" ? 0.3 : 1.0;
  parent.addChild(label);
  // Name + task
  const name = new Text({ text: agent.name,
    style: new TextStyle({ fontSize: 10, fill: 0x333333 }) });
  name.position.set(x + 5, y + 88);
  parent.addChild(name);
}

init();
```

---

## 9. What NOT to Copy

| Feature | Reason |
|---|---|
| React 19 + Tailwind for dashboard | Overkill for view-only; vanilla JS suffices |
| WebSocket bidirectional transport | We need read-only SSE, not WS |
| CEO movement + keyboard controls | Our dashboard has no interactive CEO avatar |
| Meeting presence + cross-dept delivery animations | We don't have cross-agent meetings |
| Sub-clone spawn/despawn with fireworks | Impressive but unnecessary for our agent count |
| Express 5 + SQLite backend | We already have our own data sources |
| i18n (ko/en/ja/zh) | English-only |
| XP / rank tier / leaderboard | Not relevant to our ops dashboard |
