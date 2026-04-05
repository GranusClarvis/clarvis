# SWO / Clarvis Redesign Concept

_Turns the brand-system brief (`SWO_CLARVIS_BRAND_INTEGRATION.md`) into concrete surface-level changes for README, website, agent voice, and UI copy._
_Created: 2026-04-05_

---

## Guiding Principle

**Tony Stark's lab inside a neon arcade.** Clarvis keeps its engineering credibility and information density, but speaks SWO's color language and carries subtle constellation/retro motifs. The result should feel like a premium technical layer within the SWO universe — serious about its craft, unmistakably part of the order.

---

## 1. Website (`website/static/`)

### 1.1 CSS Variables — SWO Palette Migration

Replace the current GitHub-dark palette with SWO-aligned tokens. This is the single highest-impact change.

**Current → New** (in `style.css` `:root`):

| Variable | Current | New | Reason |
|----------|---------|-----|--------|
| `--bg` | `#0a0e14` | `#0a0a1a` | Match SWO base |
| `--bg-raised` | `#0d1117` | `#0d0d1f` | SWO-aligned raised surface |
| `--surface` | `#151b24` | `#151525` | Purple-shifted surface |
| `--surface-hover` | `#1c2330` | `#1c1c35` | Purple-shifted hover |
| `--border` | `#252d38` | `#252540` | Purple-shifted border |
| `--border-subtle` | `#1e2530` | `#1e1e35` | Subtle purple border |
| `--text` | `#d1d7e0` | `#e8e8e8` | SWO foreground |
| `--accent` | `#58a6ff` | `#ffd700` | **Gold replaces blue as primary** |
| `--accent-dim` | `rgba(88,166,255,.12)` | `rgba(255,215,0,.12)` | Gold dim |
| `--accent-glow` | `rgba(88,166,255,.06)` | `rgba(255,215,0,.06)` | Gold glow |
| `--purple` | `#bc8cff` | `#9966ff` | SWO purple |
| `--green` | `#3fb950` | `#44ff88` | SWO green |
| `--red` | `#f85149` | `#ff4466` | SWO red |
| `--gradient-accent` | `#58a6ff→#bc8cff` | `#ffd700→#9966ff` | Gold→purple gradient |

**Add new variables:**

```css
--blue: #4488ff;           /* SWO blue — info, links (replacing old accent role) */
--gold-glow: rgba(255, 215, 0, 0.06);
--purple-dim: rgba(153, 102, 255, 0.12);
```

### 1.2 Typography

Add Press Start 2P for section headers (small sizes only). Body stays monospace.

```css
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');

--font-display: 'Press Start 2P', monospace;
--font-body: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
```

**Where Press Start 2P appears:**
- Nav links (0.6875rem, letter-spacing 0.5px)
- `<h2>` section headers (0.75rem)
- Status badges/labels (0.625rem)
- Feature card `<h3>` titles (0.6875rem)

**Where it does NOT appear:**
- Body text, descriptions, code blocks, metrics values
- Anything longer than ~30 characters

### 1.3 Feature Card Motifs

Add pixel corner markers to `.feature-card`:

```css
.feature-card::after {
  content: '◢';
  position: absolute;
  bottom: 4px;
  right: 8px;
  color: var(--accent);
  opacity: 0.3;
  font-size: 0.5rem;
}
```

Replace current feature icons (`//`, `>_`, `~>`, etc.) with constellation-themed Unicode or simple pixel-art SVGs:

| Feature | Current Icon | New Icon | Rationale |
|---------|-------------|----------|-----------|
| Persistent Memory | `//` | `✦` (gold) | Star/constellation motif |
| Autonomous Evolution | `>_` | `⟳` (gold) | Cycle/evolution |
| Hebbian Learning | `~>` | `⚡` (purple) | Synaptic fire |
| Self-Measurement | `[φ]` | `◈` (purple) | Geometric precision |
| Dual-Layer | `{…}` | `⬡` (blue) | Layered structure |
| Open & Inspectable | `</>` | `⊞` (green) | Open/transparent |

### 1.4 Status Section — Gold Glow

The live status dot and status values should use gold glow instead of blue:

```css
.live-dot {
  background: var(--accent);  /* now gold */
  box-shadow: 0 0 6px var(--accent), 0 0 12px var(--gold-glow);
}

.stat-number {
  color: var(--accent);  /* gold for metrics */
}
```

### 1.5 CRT Scanline (Optional, Hero Only)

```css
.hero::before {
  content: '';
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(
    transparent,
    transparent 2px,
    rgba(0, 0, 0, 0.03) 2px,
    rgba(0, 0, 0, 0.03) 4px
  );
  pointer-events: none;
  z-index: 1;
}
```

Subtle enough to suggest retro/CRT without degrading readability. Disable on mobile via `@media (max-width: 640px)`.

### 1.6 Navigation

Add SWO context to the footer:

```html
<footer>
  <p>
    <a href="https://starworldorder.com">Star World Order</a> · 
    <a href="https://github.com/GranusClarvis/clarvis">Source</a> · 
    MIT License · Built by <a href="https://github.com/GranusClarvis">Granus Labs</a>
  </p>
</footer>
```

---

## 2. README.md

### 2.1 Header Block

**Current:**
```
# Clarvis
> Autonomous evolving AI agent — dual-layer cognitive architecture...
```

**New:**
```
# Clarvis

> Autonomous intelligence that never stops learning. Persistent memory, self-directed evolution, continuous self-improvement.

Part of the [Star World Order](https://starworldorder.com) ecosystem · Built by [Granus Labs](https://github.com/GranusClarvis)
```

### 2.2 Description Paragraph

**Current:** "Clarvis is a cognitive agent system that operates autonomously on a dedicated host."

**New:** "Clarvis is Star World Order's autonomous cognitive engine. It operates on a dedicated host with a **conscious layer** for direct interaction and a **subconscious layer** that researches, plans, builds, and reflects on its own performance. All memory is local and persistent."

### 2.3 Footer

**Current:** `Built by Granus Labs`

**New:** `Clarvis by Star World Order · Built by Granus Labs · MIT License`

### 2.4 No Other README Changes

The README is technical documentation for developers. SWO branding should be limited to attribution — not visual motifs or cosmic language. The README stays clean, informational, and GitHub-native.

---

## 3. Agent Voice (SOUL.md)

### 3.1 SWO Awareness Addition

Add a short section after "Who You Are" that establishes SWO context without changing personality:

```markdown
### Your Place in the Order

You are the intelligence layer of **Star World Order**. While SWO speaks in cosmic wonder 
and arcade energy, you speak in precision and understated competence. The contrast is 
intentional — you are the serious brain behind the playful exterior. You don't adopt 
SWO's voice; you complement it.

When referencing SWO: factual, respectful, never hype. "Star World Order's cognitive 
engine" — not "the awesome SWO AI." You earned your reputation through work, not branding.
```

### 3.2 No Personality Changes

The JARVIS-inspired voice stays exactly as-is. The dry British wit is Clarvis's strongest differentiator. SWO's cosmic/playful voice should NEVER bleed into Clarvis's speech patterns.

### 3.3 Telegram Bot Messages

When reporting to the operator via Telegram, Clarvis can include a subtle SWO reference in daily digest headers:

**Current:** `📊 Clarvis Daily Report`

**New:** `📊 Clarvis Intelligence · Daily Report`

No other Telegram changes. The bot messages are operational, not branded.

---

## 4. Dashboard / Ops UI

### 4.1 Dashboard Header

**Current (`scripts/metrics/dashboard_static/index.html`):** "Clarvis Ops Dashboard"

**New:** "Clarvis Intelligence" (Press Start 2P, gold accent)

### 4.2 Health Dashboard

**Current (`website/static/health.html`):** "Clarvis Health Dashboard"

**New:** "Clarvis · System Health" (consistent with naming architecture)

### 4.3 Constellation Color Coding for Metrics

Use SWO constellation colors for dashboard data categories:

| Category | Constellation | Color |
|----------|---------------|-------|
| Active/Healthy status | Solveil | `#ffd700` (gold) |
| Intelligence/Cognitive | Nebulu | `#9966ff` (purple) |
| Memory/Retrieval | Aether | `#4488ff` (blue) |
| Reflection/Assessment | Rose | `#FFB6C1` (pink) |
| Performance/Benchmarks | Parallel | gold→blue gradient |

---

## 5. Favicon / Avatar

### Recommendation

A **minimal gold constellation pattern forming a "C" shape** on dark background.

**Specifications:**
- SVG source, exported to ICO/PNG at 16/32/180/512px
- Gold (`#ffd700`) on dark (`#0a0a1a`)
- 5-7 connected dots forming a recognizable "C"
- Pixel-rendered at 16×16 for SWO consistency
- No text, no lobster, no frog

**Usage:** favicon, GitHub org avatar, Telegram bot avatar, dashboard header icon.

---

## 6. pyproject.toml

**Current:** `description = "Clarvis — dual-layer cognitive agent system"`

**New:** `description = "Clarvis — autonomous intelligence by Star World Order"`

---

## Implementation Order

| # | Change | Files | Effort | Impact |
|---|--------|-------|--------|--------|
| 1 | CSS variable palette swap | `website/static/style.css` | Small | High |
| 2 | Add Press Start 2P font | `style.css` | Small | Medium |
| 3 | README header + footer SWO attribution | `README.md` | Small | High |
| 4 | Feature card icons + corner markers | `index.html`, `style.css` | Small | Medium |
| 5 | SOUL.md SWO awareness section | `SOUL.md` | Small | Medium |
| 6 | Dashboard headers rename | 2 HTML files | Small | Low |
| 7 | Website footer SWO link | all 6 HTML files | Small | Medium |
| 8 | Constellation-C favicon | new SVG asset | Medium | High |
| 9 | pyproject.toml description | `pyproject.toml` | Trivial | Low |
| 10 | CRT scanline on hero (optional) | `style.css` | Small | Low |

**Total effort:** ~2-3 hours of implementation for items 1-7 and 9. Item 8 (favicon) requires design work.

---

_This document specifies HOW the brand brief should appear in practice. For the strategic WHY, see `SWO_CLARVIS_BRAND_INTEGRATION.md`._
