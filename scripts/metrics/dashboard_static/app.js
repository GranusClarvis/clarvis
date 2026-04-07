/**
 * Clarvis Ops Dashboard — PixiJS 8 pixel-art live dashboard.
 *
 * Visual-only (no controls). All commands via TG/Discord.
 * SSE-driven state updates from dashboard_server.py.
 */

// ── Constants ──────────────────────────────────────────────────────────

const COLORS = {
  floor1: 0x1a1a2e,
  floor2: 0x16213e,
  wall: 0x0f3460,
  wallAccent: 0x533483,
  desk: 0x2c3e50,
  deskTop: 0x34495e,
  deskShadow: 0x1a252f,
  textPrimary: 0xe0e0e0,
  textDim: 0x888899,
  success: 0x00ff88,
  fail: 0xff4444,
  pending: 0xffaa00,
  working: 0x55aaff,
  idle: 0xaaaacc,
  offline: 0x555566,
};

const TILE_SIZE = 20;
const PARTICLE_COLORS = [0x55aaff, 0x55ff88, 0xffaa33];

// ── State ──────────────────────────────────────────────────────────────

let state = {
  queue: [],
  agents: [],
  locks: [],
  recent_events: [],
  prs: [],
  digest_lines: [],
  scoreboard: [],
  metrics: {},
};

let app = null;
let sceneContainer = null;
let particles = [];
let tickCount = 0;

// ── Helpers ────────────────────────────────────────────────────────────

function hashStr(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

function truncate(s, n) {
  return s && s.length > n ? s.slice(0, n - 1) + '\u2026' : (s || '');
}

function showModal(title, bodyObj) {
  const modal = document.getElementById('modal');
  const card = document.getElementById('modal-card');
  const titleEl = document.getElementById('modal-title');
  const bodyEl = document.getElementById('modal-body');
  const closeBtn = document.getElementById('modal-close');

  if (!modal || !card || !titleEl || !bodyEl || !closeBtn) return;

  titleEl.textContent = title || 'Details';
  bodyEl.textContent = typeof bodyObj === 'string' ? bodyObj : JSON.stringify(bodyObj, null, 2);
  modal.style.display = 'block';

  const close = () => { modal.style.display = 'none'; };
  closeBtn.onclick = close;
  modal.onclick = (e) => { if (e.target === modal) close(); };
}

// ── Drawing primitives ─────────────────────────────────────────────────

function drawTiledFloor(g, w, h) {
  const cols = Math.ceil(w / TILE_SIZE);
  const rows = Math.ceil(h / TILE_SIZE);
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const color = (r + c) % 2 === 0 ? COLORS.floor1 : COLORS.floor2;
      g.rect(c * TILE_SIZE, r * TILE_SIZE, TILE_SIZE, TILE_SIZE).fill(color);
    }
  }
}

function drawWalls(g, w) {
  // Top wall with gradient bands
  const wallH = 40;
  const bands = [COLORS.wall, COLORS.wallAccent, COLORS.wall, 0x0a0a1a];
  const bandH = wallH / bands.length;
  for (let i = 0; i < bands.length; i++) {
    g.rect(0, i * bandH, w, bandH).fill(bands[i]);
  }
  // Title text
  const title = new PIXI.Text({
    text: 'CLARVIS OPS CENTER',
    style: { fontFamily: 'Courier New', fontSize: 14, fill: COLORS.textPrimary, letterSpacing: 2 },
  });
  title.x = w / 2 - title.width / 2;
  title.y = 12;
  return { wallH, title };
}

function drawDesk(container, x, y, label, statusColor) {
  const g = new PIXI.Graphics();
  // Shadow
  g.roundRect(x + 2, y + 2, 64, 28, 3).fill(COLORS.deskShadow);
  // Desk body
  g.roundRect(x, y, 64, 28, 3).fill(COLORS.desk);
  // Desk top surface
  g.roundRect(x + 2, y + 1, 60, 12, 2).fill(COLORS.deskTop);
  // Status LED
  g.circle(x + 56, y + 6, 3).fill(statusColor);
  container.addChild(g);

  // Label
  const text = new PIXI.Text({
    text: truncate(label, 10),
    style: { fontFamily: 'Courier New', fontSize: 9, fill: COLORS.textDim },
  });
  text.x = x + 4;
  text.y = y + 16;
  container.addChild(text);
}

// ── Agent rendering ────────────────────────────────────────────────────

const STATUS_EMOJI = {
  running: '\uD83D\uDD25',   // fire
  idle: '\uD83E\uDDD1\u200D\uD83D\uDCBB',  // technologist
  unknown: '\uD83E\uDD16',   // robot
  error: '\u26A0\uFE0F',     // warning
};

function drawAgent(container, agent, x, y) {
  const isWorking = agent.status === 'running';
  const isOffline = !agent.status || agent.status === 'error';

  // Emoji avatar
  const emoji = new PIXI.Text({
    text: STATUS_EMOJI[agent.status] || STATUS_EMOJI.unknown,
    style: { fontSize: 22 },
  });
  emoji.x = x;
  emoji.y = y - 28;
  emoji.alpha = isOffline ? 0.3 : 1.0;
  container.addChild(emoji);

  // Name label
  const name = new PIXI.Text({
    text: truncate(agent.name, 12),
    style: { fontFamily: 'Courier New', fontSize: 9, fill: isWorking ? COLORS.working : COLORS.textDim },
  });
  name.x = x - 4;
  name.y = y + 2;
  container.addChild(name);

  // Trust score bar
  const trustW = 40;
  const trustH = 3;
  const bg = new PIXI.Graphics();
  bg.rect(x, y + 14, trustW, trustH).fill(0x333344);
  const trustFill = agent.trust_score || 0.5;
  const trustColor = trustFill >= 0.8 ? COLORS.success : trustFill >= 0.5 ? COLORS.pending : COLORS.fail;
  bg.rect(x, y + 14, trustW * trustFill, trustH).fill(trustColor);
  container.addChild(bg);

  // Task label (if running)
  if (isWorking && agent.last_task) {
    const taskLabel = new PIXI.Text({
      text: truncate(agent.last_task, 20),
      style: { fontFamily: 'Courier New', fontSize: 8, fill: COLORS.working },
    });
    taskLabel.x = x - 4;
    taskLabel.y = y + 20;
    container.addChild(taskLabel);
  }

  // Spark particles for working agents
  if (isWorking && tickCount % 10 === 0) {
    spawnParticle(container, x + 10, y - 20);
  }
}

// ── Particle system ────────────────────────────────────────────────────

function spawnParticle(container, x, y) {
  const g = new PIXI.Graphics();
  const color = PARTICLE_COLORS[Math.floor(Math.random() * PARTICLE_COLORS.length)];
  g.circle(0, 0, 2).fill(color);
  g.x = x + (Math.random() - 0.5) * 10;
  g.y = y;
  g._vy = -(1 + Math.random() * 2);
  g._vx = (Math.random() - 0.5) * 1.5;
  g._life = 30 + Math.random() * 20;
  container.addChild(g);
  particles.push(g);
}

function tickParticles() {
  const dead = [];
  for (const p of particles) {
    p.x += p._vx;
    p.y += p._vy;
    p._life--;
    p.alpha = Math.max(0, p._life / 50);
    if (p._life <= 0) dead.push(p);
  }
  for (const p of dead) {
    p.destroy();
    particles.splice(particles.indexOf(p), 1);
  }
}

// ── Queue panel ────────────────────────────────────────────────────────

function drawQueuePanel(container, x, y, w, h) {
  // Background
  const bg = new PIXI.Graphics();
  bg.roundRect(x, y, w, h, 4).fill({ color: 0x111122, alpha: 0.85 });
  bg.roundRect(x, y, w, 16, 4).fill(COLORS.wall);
  container.addChild(bg);

  const header = new PIXI.Text({
    text: 'QUEUE',
    style: { fontFamily: 'Courier New', fontSize: 10, fill: COLORS.textPrimary, fontWeight: 'bold' },
  });
  header.x = x + 6;
  header.y = y + 2;
  container.addChild(header);

  // Task list
  const tasks = state.queue.filter(t => t.status !== 'done').slice(0, 12);
  let ty = y + 20;
  for (const t of tasks) {
    const icon = t.status === 'in_progress' ? '\u25B6' : '\u25CB';
    const color = t.status === 'in_progress' ? COLORS.working : COLORS.textDim;
    const ownerBadge = t.owner_name && t.owner_name !== 'unknown' ? ` ${truncate(t.owner_name, 8)}` : '';
    const line = new PIXI.Text({
      text: `${icon} [${t.tag}]${ownerBadge}`,
      style: { fontFamily: 'Courier New', fontSize: 8, fill: color },
    });
    line.x = x + 6;
    line.y = ty;

    // Clickable inspect — fetch full QUEUE.md block
    line.eventMode = 'static';
    line.cursor = 'pointer';
    line.on('pointertap', () => {
      showModal(`QUEUE [${t.tag}] (${t.status})`, 'Loading\u2026');
      fetch(`/queue-block/${encodeURIComponent(t.tag)}`)
        .then(r => r.json())
        .then(data => {
          if (data.block) {
            showModal(`QUEUE [${t.tag}] (${t.status})`, data.block);
          } else {
            showModal(`QUEUE [${t.tag}] (${t.status})`, data.error || 'Block not found');
          }
        })
        .catch(() => {
          showModal(`QUEUE [${t.tag}] (${t.status})`, {
            tag: t.tag, status: t.status, section: t.section,
            owner_type: t.owner_type || 'unknown',
            owner_name: t.owner_name || 'unknown',
            description: t.description,
          });
        });
    });

    container.addChild(line);
    ty += 12;
    if (ty > y + h - 4) break;
  }

  // Counts
  const pending = state.queue.filter(t => t.status === 'pending').length;
  const inProg = state.queue.filter(t => t.status === 'in_progress').length;
  const countText = new PIXI.Text({
    text: `${pending}p ${inProg}a`,
    style: { fontFamily: 'Courier New', fontSize: 8, fill: COLORS.textDim },
  });
  countText.x = x + w - 40;
  countText.y = y + 3;
  container.addChild(countText);
}

// ── Completed panel ───────────────────────────────────────────────────

function drawCompletedPanel(container, x, y, w, h) {
  const bg = new PIXI.Graphics();
  bg.roundRect(x, y, w, h, 4).fill({ color: 0x111122, alpha: 0.85 });
  bg.roundRect(x, y, w, 16, 4).fill(0x264653);
  container.addChild(bg);

  const header = new PIXI.Text({
    text: 'COMPLETED',
    style: { fontFamily: 'Courier New', fontSize: 10, fill: COLORS.textPrimary, fontWeight: 'bold' },
  });
  header.x = x + 6;
  header.y = y + 2;
  container.addChild(header);

  const completed = (state.recent_events || []).filter(ev => ev.type === 'task_completed').slice(-12);
  let cy = y + 20;
  for (const ev of completed.slice(-10)) {
    const ts = (ev.ts || '').slice(11, 19);
    const ok = (ev.status || '').toLowerCase() === 'success' || (ev.exit_code === '0');
    const color = ok ? COLORS.success : COLORS.fail;
    const ownerType = ev.owner_type || 'system';
    const ownerName = ev.owner_name || ev.agent || ev.executor || ev.section || '';
    const ownerPrefix = ownerType === 'cron' ? 'C' : ownerType === 'subagent' ? 'A' : 'S';
    const label = truncate(ev.task_name || ev.task || ownerName, 18);

    const line = new PIXI.Text({
      text: `${ts} ${ok ? 'ok' : '!!'}  ${ownerPrefix}:${truncate(ownerName, 6)} ${label}`,
      style: { fontFamily: 'Courier New', fontSize: 8, fill: color },
    });
    line.x = x + 6;
    line.y = cy;

    line.eventMode = 'static';
    line.cursor = 'pointer';
    line.on('pointertap', () => {
      showModal(`COMPLETED ${ok ? 'ok' : 'fail'} [${ownerType}/${ownerName}]`, ev);
    });

    container.addChild(line);
    cy += 12;
    if (cy > y + h - 4) break;
  }

  if (completed.length === 0) {
    const none = new PIXI.Text({
      text: 'No completed tasks yet',
      style: { fontFamily: 'Courier New', fontSize: 8, fill: COLORS.textDim },
    });
    none.x = x + 6;
    none.y = y + 20;
    container.addChild(none);
  }
}

// ── Events panel ───────────────────────────────────────────────────────

function drawEventsPanel(container, x, y, w, h) {
  const bg = new PIXI.Graphics();
  bg.roundRect(x, y, w, h, 4).fill({ color: 0x111122, alpha: 0.85 });
  bg.roundRect(x, y, w, 16, 4).fill(COLORS.wallAccent);
  container.addChild(bg);

  const header = new PIXI.Text({
    text: 'RECENT EVENTS',
    style: { fontFamily: 'Courier New', fontSize: 10, fill: COLORS.textPrimary, fontWeight: 'bold' },
  });
  header.x = x + 6;
  header.y = y + 2;
  container.addChild(header);

  const events = state.recent_events.slice(-8);
  let ey = y + 20;
  for (const ev of events) {
    const ts = (ev.ts || '').slice(11, 19);
    const typeColor =
      ev.type === 'task_completed' ? COLORS.success :
      ev.type === 'error' ? COLORS.fail :
      ev.type === 'agent_spawned' ? COLORS.working : COLORS.textDim;
    const evOwner = ev.owner_name || ev.agent || '';
    const evLabel = truncate(ev.task_name || evOwner || '', 16);
    const line = new PIXI.Text({
      text: `${ts} ${(ev.type || '').slice(0, 14)} ${evOwner ? truncate(evOwner, 6) + ' ' : ''}${evLabel}`,
      style: { fontFamily: 'Courier New', fontSize: 8, fill: typeColor },
    });
    line.x = x + 6;
    line.y = ey;
    container.addChild(line);
    ey += 12;
    if (ey > y + h - 4) break;
  }
}

// ── PR panel ───────────────────────────────────────────────────────────

function drawPRPanel(container, x, y, w, h) {
  const bg = new PIXI.Graphics();
  bg.roundRect(x, y, w, h, 4).fill({ color: 0x111122, alpha: 0.85 });
  bg.roundRect(x, y, w, 16, 4).fill(0x2d6a4f);
  container.addChild(bg);

  const header = new PIXI.Text({
    text: 'PULL REQUESTS',
    style: { fontFamily: 'Courier New', fontSize: 10, fill: COLORS.textPrimary, fontWeight: 'bold' },
  });
  header.x = x + 6;
  header.y = y + 2;
  container.addChild(header);

  const prs = (state.prs || []).slice(0, 5);
  let py = y + 20;
  for (const pr of prs) {
    const line = new PIXI.Text({
      text: `#${pr.number} ${truncate(pr.title, 30)}`,
      style: { fontFamily: 'Courier New', fontSize: 8, fill: COLORS.success },
    });
    line.x = x + 6;
    line.y = py;
    container.addChild(line);
    py += 12;
  }
  if (prs.length === 0) {
    const none = new PIXI.Text({
      text: 'No open PRs',
      style: { fontFamily: 'Courier New', fontSize: 8, fill: COLORS.textDim },
    });
    none.x = x + 6;
    none.y = py;
    container.addChild(none);
  }
}

// ── Metrics panel ─────────────────────────────────────────────────────

function drawMetricsPanel(container, x, y, w, h) {
  const bg = new PIXI.Graphics();
  bg.roundRect(x, y, w, h, 4).fill({ color: 0x111122, alpha: 0.85 });
  bg.roundRect(x, y, w, 16, 4).fill(0x6b21a8);
  container.addChild(bg);

  const header = new PIXI.Text({
    text: 'SYSTEM METRICS',
    style: { fontFamily: 'Courier New', fontSize: 10, fill: COLORS.textPrimary, fontWeight: 'bold' },
  });
  header.x = x + 6;
  header.y = y + 2;
  container.addChild(header);

  const m = state.metrics || {};
  let my = y + 22;

  // Gauge helper — draws a labeled bar
  function drawGauge(label, value, maxVal, thresholdGood, thresholdWarn) {
    if (value == null) return;
    const barW = w - 60;
    const barH = 6;
    const pct = Math.min(value / maxVal, 1.0);
    const color = pct >= thresholdGood ? COLORS.success :
                  pct >= thresholdWarn ? COLORS.pending : COLORS.fail;

    const lbl = new PIXI.Text({
      text: label,
      style: { fontFamily: 'Courier New', fontSize: 8, fill: COLORS.textDim },
    });
    lbl.x = x + 6;
    lbl.y = my;
    container.addChild(lbl);

    const valText = new PIXI.Text({
      text: typeof value === 'number' ? value.toFixed(3) : String(value),
      style: { fontFamily: 'Courier New', fontSize: 8, fill: color },
    });
    valText.x = x + 46;
    valText.y = my;
    container.addChild(valText);

    // Bar background
    const barG = new PIXI.Graphics();
    barG.rect(x + 6, my + 11, barW, barH).fill(0x333344);
    barG.rect(x + 6, my + 11, barW * pct, barH).fill(color);
    container.addChild(barG);

    my += 22;
  }

  drawGauge('PI', m.pi, 1.0, 0.8, 0.5);
  drawGauge('CLR', m.clr, 1.0, 0.7, 0.4);
  drawGauge('Phi', m.phi, 1.0, 0.6, 0.3);

  // Brain memory count
  if (m.brain_total != null) {
    const brainLine = new PIXI.Text({
      text: `Brain: ${m.brain_total} memories`,
      style: { fontFamily: 'Courier New', fontSize: 8, fill: COLORS.textPrimary },
    });
    brainLine.x = x + 6;
    brainLine.y = my;
    container.addChild(brainLine);
    my += 14;
  }

  // Mode indicator
  if (m.mode) {
    const modeLine = new PIXI.Text({
      text: `Mode: ${m.mode}`,
      style: { fontFamily: 'Courier New', fontSize: 8, fill: COLORS.working },
    });
    modeLine.x = x + 6;
    modeLine.y = my;
    container.addChild(modeLine);
    my += 14;
  }

  // CLR dimensions as mini bars
  const dims = m.clr_dimensions || {};
  const dimNames = Object.keys(dims);
  if (dimNames.length > 0 && my < y + h - 16) {
    const dimHeader = new PIXI.Text({
      text: 'CLR Dimensions:',
      style: { fontFamily: 'Courier New', fontSize: 7, fill: COLORS.textDim },
    });
    dimHeader.x = x + 6;
    dimHeader.y = my;
    container.addChild(dimHeader);
    my += 12;

    for (const dn of dimNames) {
      if (my > y + h - 10) break;
      const dv = dims[dn];
      const shortName = dn.replace(/_/g, ' ').slice(0, 12);
      const dColor = dv >= 0.8 ? COLORS.success : dv >= 0.5 ? COLORS.pending : COLORS.fail;
      const dimLine = new PIXI.Text({
        text: `  ${shortName.padEnd(13)} ${(dv * 100).toFixed(0)}%`,
        style: { fontFamily: 'Courier New', fontSize: 7, fill: dColor },
      });
      dimLine.x = x + 6;
      dimLine.y = my;
      container.addChild(dimLine);
      my += 10;
    }
  }
}

// ── Digest panel ──────────────────────────────────────────────────────

function drawDigestPanel(container, x, y, w, h) {
  const bg = new PIXI.Graphics();
  bg.roundRect(x, y, w, h, 4).fill({ color: 0x111122, alpha: 0.85 });
  bg.roundRect(x, y, w, 16, 4).fill(0x4a5568);
  container.addChild(bg);

  const header = new PIXI.Text({
    text: 'CRON DIGEST',
    style: { fontFamily: 'Courier New', fontSize: 10, fill: COLORS.textPrimary, fontWeight: 'bold' },
  });
  header.x = x + 6;
  header.y = y + 2;
  container.addChild(header);

  const lines = state.digest_lines || [];
  let dy = y + 20;
  for (const line of lines.slice(-Math.floor((h - 24) / 11))) {
    if (dy > y + h - 8) break;
    // Color based on content
    const isHeader = line.startsWith('#') || line.startsWith('##');
    const isResult = line.includes('✓') || line.includes('success') || line.includes('ok');
    const isError = line.includes('✗') || line.includes('fail') || line.includes('error');
    const color = isHeader ? COLORS.textPrimary :
                  isResult ? COLORS.success :
                  isError ? COLORS.fail : COLORS.textDim;
    const text = new PIXI.Text({
      text: truncate(line.replace(/^#+\s*/, ''), Math.floor(w / 5.5)),
      style: { fontFamily: 'Courier New', fontSize: 8, fill: color },
    });
    text.x = x + 6;
    text.y = dy;
    container.addChild(text);
    dy += 11;
  }

  if (lines.length === 0) {
    const none = new PIXI.Text({
      text: 'No digest available',
      style: { fontFamily: 'Courier New', fontSize: 8, fill: COLORS.textDim },
    });
    none.x = x + 6;
    none.y = y + 20;
    container.addChild(none);
  }
}

// ── Scene builder ──────────────────────────────────────────────────────

function buildScene() {
  if (sceneContainer) {
    sceneContainer.destroy({ children: true });
    particles = [];
  }

  sceneContainer = new PIXI.Container();
  app.stage.addChild(sceneContainer);

  const W = app.screen.width;
  const H = app.screen.height;

  // Floor
  const floorG = new PIXI.Graphics();
  drawTiledFloor(floorG, W, H);
  sceneContainer.addChild(floorG);

  // Walls
  const wallG = new PIXI.Graphics();
  const { wallH, title } = drawWalls(wallG, W);
  sceneContainer.addChild(wallG);
  sceneContainer.addChild(title);

  // Agent area — draw desks + agents
  const agents = state.agents || [];
  const agentStartX = 30;
  const agentStartY = wallH + 30;
  const agentSpacing = 110;

  for (let i = 0; i < agents.length; i++) {
    const ax = agentStartX + (i % 5) * agentSpacing;
    const ay = agentStartY + Math.floor(i / 5) * 80;
    const statusColor = agents[i].status === 'running' ? COLORS.working :
                        agents[i].status === 'idle' ? COLORS.idle : COLORS.offline;
    drawDesk(sceneContainer, ax, ay + 30, agents[i].name, statusColor);
    drawAgent(sceneContainer, agents[i], ax + 18, ay + 28);
  }

  // If no agents, show Clarvis
  if (agents.length === 0) {
    const clarvis = new PIXI.Text({
      text: '\uD83E\uDDE0',  // brain emoji
      style: { fontSize: 32 },
    });
    clarvis.x = W / 2 - 16;
    clarvis.y = wallH + 40;
    sceneContainer.addChild(clarvis);

    const label = new PIXI.Text({
      text: 'CLARVIS',
      style: { fontFamily: 'Courier New', fontSize: 12, fill: COLORS.textPrimary, letterSpacing: 3 },
    });
    label.x = W / 2 - label.width / 2;
    label.y = wallH + 78;
    sceneContainer.addChild(label);
  }

  // Panels — 3-column × 2-row grid
  const panelY = Math.max(wallH + 30 + Math.ceil(agents.length / 5) * 80 + 20, H * 0.35);
  const panelGap = 8;
  const panelCols = 3;
  const panelW = Math.min(340, (W - 20 - panelGap * (panelCols - 1)) / panelCols);
  const availH = H - panelY - 40;
  const panelH = Math.floor((availH - panelGap) / 2);

  // Row 1: Queue, Completed, Metrics
  drawQueuePanel(sceneContainer, 10, panelY, panelW, panelH);
  drawCompletedPanel(sceneContainer, 10 + (panelW + panelGap), panelY, panelW, panelH);
  drawMetricsPanel(sceneContainer, 10 + (panelW + panelGap) * 2, panelY, panelW, panelH);

  // Row 2: Events, PRs, Digest
  const row2Y = panelY + panelH + panelGap;
  drawEventsPanel(sceneContainer, 10, row2Y, panelW, panelH);
  drawPRPanel(sceneContainer, 10 + (panelW + panelGap), row2Y, panelW, panelH);
  drawDigestPanel(sceneContainer, 10 + (panelW + panelGap) * 2, row2Y, panelW, panelH);

  // Active locks indicator
  const activeLocks = (state.locks || []).filter(l => l.alive);
  if (activeLocks.length > 0) {
    const lockG = new PIXI.Graphics();
    lockG.roundRect(W - 120, wallH + 8, 110, 18, 3).fill({ color: COLORS.working, alpha: 0.2 });
    sceneContainer.addChild(lockG);
    const lockText = new PIXI.Text({
      text: `\uD83D\uDD12 ${activeLocks.length} active`,
      style: { fontFamily: 'Courier New', fontSize: 9, fill: COLORS.working },
    });
    lockText.x = W - 114;
    lockText.y = wallH + 11;
    sceneContainer.addChild(lockText);
  }
}

// ── Status bar updates ─────────────────────────────────────────────────

function updateStatusBar() {
  const pending = state.queue.filter(t => t.status === 'pending').length;
  const inProg = state.queue.filter(t => t.status === 'in_progress').length;
  const done = state.queue.filter(t => t.status === 'done').length;
  document.getElementById('pending-count').textContent =
    `Queue: ${pending} pending, ${inProg} active, ${done} done`;

  const activeTask = state.queue.find(t => t.status === 'in_progress');
  document.getElementById('active-task').textContent =
    activeTask ? `\u25B6 [${activeTask.tag}]` : 'No active task';

  const lastEv = state.recent_events.slice(-1)[0];
  if (lastEv) {
    const ts = (lastEv.ts || '').slice(11, 19);
    document.getElementById('last-event').textContent =
      `Last: ${lastEv.type} @ ${ts}`;
  }

  // Metrics summary in status bar
  const m = state.metrics || {};
  const metricParts = [];
  if (m.pi != null) metricParts.push(`PI:${m.pi.toFixed(2)}`);
  if (m.clr != null) metricParts.push(`CLR:${m.clr.toFixed(2)}`);
  if (m.phi != null) metricParts.push(`\u03A6:${m.phi.toFixed(2)}`);
  const metricsEl = document.getElementById('metrics-summary');
  if (metricsEl) metricsEl.textContent = metricParts.join(' | ') || '';

  document.getElementById('clock').textContent =
    new Date().toLocaleTimeString('en-GB', { hour12: false });
}

// ── SSE Client ─────────────────────────────────────────────────────────

let evtSource = null;

function connectSSE() {
  if (evtSource) {
    evtSource.close();
  }

  evtSource = new EventSource('/sse');

  evtSource.addEventListener('state', (e) => {
    try {
      state = JSON.parse(e.data);
      buildScene();
      updateStatusBar();
    } catch (err) { console.error('state parse error:', err); }
  });

  evtSource.addEventListener('queue_update', (e) => {
    try {
      const d = JSON.parse(e.data);
      state.queue = d.queue;
      buildScene();
      updateStatusBar();
    } catch (err) {}
  });

  evtSource.addEventListener('agent_status', (e) => {
    try {
      const d = JSON.parse(e.data);
      state.agents = d.agents;
      buildScene();
    } catch (err) {}
  });

  evtSource.addEventListener('cron_activity', (e) => {
    try {
      const d = JSON.parse(e.data);
      state.locks = d.locks;
      buildScene();
    } catch (err) {}
  });

  evtSource.addEventListener('events_update', (e) => {
    try {
      const d = JSON.parse(e.data);
      // Append new events
      for (const ev of d.events) {
        state.recent_events.push(ev);
      }
      // Keep last 30
      state.recent_events = state.recent_events.slice(-30);
      buildScene();
      updateStatusBar();
    } catch (err) {}
  });

  evtSource.addEventListener('pr_update', (e) => {
    try {
      const d = JSON.parse(e.data);
      state.prs = d.prs;
      buildScene();
    } catch (err) {}
  });

  evtSource.onopen = () => {
    document.getElementById('conn-dot').className = 'dot dot-green';
    document.getElementById('conn-label').textContent = 'LIVE';
  };

  evtSource.onerror = () => {
    document.getElementById('conn-dot').className = 'dot dot-red';
    document.getElementById('conn-label').textContent = 'OFFLINE';
    // Auto-reconnect handled by EventSource
  };
}

// ── Visibility-aware connection ────────────────────────────────────────

document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    if (evtSource) {
      evtSource.close();
      evtSource = null;
      document.getElementById('conn-dot').className = 'dot dot-yellow';
      document.getElementById('conn-label').textContent = 'PAUSED';
    }
  } else {
    connectSSE();
  }
});

// ── Init ───────────────────────────────────────────────────────────────

(async () => {
  app = new PIXI.Application();
  await app.init({
    resizeTo: document.getElementById('pixi-container'),
    antialias: false,
    backgroundColor: COLORS.floor1,
    resolution: 1,
  });

  document.getElementById('pixi-container').appendChild(app.canvas);

  // Animation ticker
  app.ticker.add(() => {
    tickCount++;
    tickParticles();
    // Rebuild scene every 5s for particle freshness
    if (tickCount % 300 === 0) {
      buildScene();
    }
    // Update clock every second (~60 ticks)
    if (tickCount % 60 === 0) {
      updateStatusBar();
    }
  });

  // Initial state fetch then connect SSE
  try {
    const resp = await fetch('/state');
    state = await resp.json();
  } catch (err) {
    console.warn('Initial fetch failed, waiting for SSE');
  }

  buildScene();
  updateStatusBar();
  connectSSE();
})();
