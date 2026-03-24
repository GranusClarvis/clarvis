# Clarvis Visual Identity — Styleguide v1

_Design language for website, dashboards, docs, and future tools._

---

## 1. Color System

### Core Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `--bg` | `#0a0e14` | Page background — near-black with blue undertone |
| `--bg-raised` | `#0d1117` | Slightly lifted surfaces (code blocks, dropdowns) |
| `--surface` | `#151b24` | Cards, panels, interactive containers |
| `--surface-hover` | `#1c2330` | Surface on hover/focus |
| `--border` | `#252d38` | Primary borders — visible but quiet |
| `--border-subtle` | `#1e2530` | Dividers, section separators |

### Text Hierarchy

| Token | Hex | Usage |
|-------|-----|-------|
| `--text` | `#d1d7e0` | Primary body text |
| `--text-muted` | `#7d8590` | Secondary text, descriptions, metadata |
| `--text-faint` | `#545d68` | Labels, captions, disabled states |

### Accent & Signals

| Token | Hex | Usage |
|-------|-----|-------|
| `--accent` | `#58a6ff` | Links, interactive elements, primary actions |
| `--accent-dim` | `rgba(88,166,255,0.12)` | Accent backgrounds (active nav, code pills) |
| `--accent-glow` | `rgba(88,166,255,0.06)` | Hover glow on rows/phases |
| `--purple` | `#bc8cff` | Gradient endpoint, decorative emphasis |
| `--green` | `#3fb950` | Success, healthy, active, live indicators |
| `--yellow` | `#d29922` | Warnings, stabilizing, in-progress |
| `--red` | `#f85149` | Errors, failures, critical alerts |

### Gradient

```css
--gradient-accent: linear-gradient(135deg, #58a6ff 0%, #bc8cff 100%);
```

Used sparingly: hero headlines, key visual moments. Never for body text or backgrounds.

### Rules

- **Dark-first, always.** There is no light mode. The void is the canvas.
- **Blue is the signal.** Accent blue draws the eye to interactive/important elements. Don't dilute it — if everything is blue, nothing is.
- **Status colors are semantic.** Green/yellow/red map to system states. Never use them decoratively.
- **Transparency over new colors.** Tinted backgrounds use `rgba()` of existing palette colors. Don't introduce new hues.

---

## 2. Typography

### Font Stacks

| Role | Stack | Usage |
|------|-------|-------|
| Body | `-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', Helvetica, Arial, sans-serif` | All prose, UI labels, descriptions |
| Code | `'SF Mono', 'Fira Code', 'Cascadia Code', 'JetBrains Mono', monospace` | Code, data values, terminal output, tags |

### Scale

| Element | Size | Weight | Tracking | Notes |
|---------|------|--------|----------|-------|
| Hero h1 | `2.75rem` | 700 | `-0.03em` | Gradient fill, used once per page |
| Page h1 | `2rem` | 700 | `-0.02em` | Page titles (non-hero) |
| Section h2 | `1.125rem` | 600 | `-0.01em` | Section headers |
| Card h3 | `1rem` | 600 | `-0.01em` | Card/feature titles |
| Body | `1rem` (implicit) | 400 | normal | Default paragraph text |
| Subtitle | `1rem` | 400 | normal | `--text-muted`, below h1 |
| Small body | `0.9375rem` | 400 | normal | Descriptions, secondary prose |
| UI text | `0.875rem` | 400 | normal | Lists, table cells, detail text |
| Labels | `0.8125rem` | 500 | normal | Nav items, completion tags |
| Micro labels | `0.75rem` | 600 | `0.04em` | Uppercase section labels, table headers |
| Badges | `0.6875rem` | 500 | `0.02em` | Status pills |

### Line Heights

- Body text: `1.6`
- Descriptive/secondary text: `1.7`–`1.8`
- Headings: inherit (tighter due to tracking)

### Rules

- **Line-height is generous.** Readability on dark backgrounds needs more air than on light.
- **Tight tracking on headings.** `-0.02em` to `-0.03em` keeps large text from looking loose.
- **Uppercase is for micro-labels only.** Table headers, status labels, definition terms. Never for headings or buttons.
- **Monospace for data and code.** Stat numbers, tags, code snippets. Use `font-variant-numeric: tabular-nums` for aligned numbers.

---

## 3. Spacing Scale

A geometric scale anchored to `1rem` (16px):

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `0.25rem` (4px) | Icon gaps, tight padding |
| `--space-sm` | `0.5rem` (8px) | Inner padding, list spacing |
| `--space-md` | `1rem` (16px) | Standard gaps, card padding internal |
| `--space-lg` | `1.5rem` (24px) | Card padding, between sections |
| `--space-xl` | `2.5rem` (40px) | Major section spacing |
| `--space-2xl` | `4rem` (64px) | Page-level vertical rhythm |

### Rules

- **Use tokens, not arbitrary values.** Every margin/padding should map to a spacing token.
- **Vertical rhythm > pixel precision.** Consistent spacing between blocks matters more than matching a mockup pixel-for-pixel.
- **Cards get `--space-lg` padding.** The interior breathing room is what makes them feel like distinct surfaces.

---

## 4. Panels & Cards

### Card Anatomy

```
┌─ 1px solid var(--border) ─────────────────┐
│  padding: var(--space-lg)                  │
│                                            │
│  [h3]  Title (1rem, 600)                   │
│  [p]   Description (--text-muted, 0.875rem)│
│  [code] Inline code pill                   │
│                                            │
└─ border-radius: var(--radius) ─────────────┘
```

### Variants

| Variant | Base | Border | Hover | Use |
|---------|------|--------|-------|-----|
| `.card` | `--surface` | `--border` | Accent tint border + `--surface-hover` | General content |
| `.status-card` | `--surface` | `--border` | Accent tint + lift `-1px` | Dashboard metrics |
| `.feature-card` | `--surface` | `--border` | Accent tint + lift `-2px` + shadow | Feature showcase |
| `.repo-card` | `--surface` | `--border` | Accent tint + lift `-1px` | Repository links |

### Surface Hierarchy

```
var(--bg)           ← page canvas (lowest)
var(--bg-raised)    ← embedded surfaces (code blocks, diagrams)
var(--surface)      ← cards, panels (primary interactive layer)
var(--surface-hover)← cards on hover (transient)
```

### Rules

- **One elevation level per context.** Cards sit on `--bg`. Don't nest cards inside cards.
- **Borders define surfaces, not shadows.** Shadows are used only on hover for feature cards. At rest, surfaces are flat with border distinction.
- **Hover = subtle life.** Border tints to accent, slight Y-translate lift. Never scale or rotate.

### Radii

| Token | Value | Usage |
|-------|-------|-------|
| `--radius` | `8px` | Cards, panels, inputs |
| `--radius-lg` | `12px` | Large cards (repo cards) |
| `6px` | inline | Buttons, nav items, code pills |
| `4px` | inline | Inline code, scrollbar thumb |
| `999px` | inline | Badges (full-round pill) |

---

## 5. Buttons & Links

### Button Variants

| Class | Appearance | Usage |
|-------|-----------|-------|
| `.btn-primary` | Solid `--accent` bg, dark text | Primary CTA (one per section max) |
| `.btn-ghost` | `--border` outline, `--text-muted` text | Secondary actions, navigation links |

### Button Specs

```
padding: 0.5rem 1.25rem
border-radius: 6px
font-size: 0.875rem
font-weight: 500
transition: all 200ms ease
```

### Hover States

- **Primary:** Lighten to `#79bbff`, lift `-1px`, blue glow shadow
- **Ghost:** Border → accent, text → accent, bg → `--accent-dim`

### Links

- Default: `--accent` (`#58a6ff`), no underline
- Hover: `#79bbff`, no underline
- Footer links: `--text-muted` → `--accent` on hover
- Nav links: `--text-muted` with `--accent-dim` bg on hover/active

### Rules

- **One primary button per visible section.** If two actions compete, one is ghost.
- **No underlines.** Color alone signals interactivity. The dark background provides enough contrast.
- **Buttons in flex rows.** `display: inline-flex; align-items: center; gap: var(--space-xs)` for icon+text.

---

## 6. Motion Principles

### Animations

| Name | Duration | Easing | Use |
|------|----------|--------|-----|
| `fadeUp` | 400–600ms | ease | Page entrance, section/card reveal |
| `fadeIn` | 400ms | ease | Nav, overlay elements |
| `pulse-subtle` | 2s | ease-in-out, infinite | Live indicator dots |

### Staggered Entrance

Grid children animate in sequence with `75ms` offset between siblings:

```css
.grid > *:nth-child(1) { animation-delay: 100ms; }
.grid > *:nth-child(2) { animation-delay: 175ms; }
.grid > *:nth-child(3) { animation-delay: 250ms; }
.grid > *:nth-child(4) { animation-delay: 325ms; }
```

### Transitions

- **Standard:** `200ms ease` — all interactive hover/focus states
- **Transform:** `translateY(-1px)` to `translateY(-2px)` on hover — cards "lift" toward the user

### Rules

- **Entrance, not spectacle.** Animation introduces content once. No looping, bouncing, or attention-seeking motion.
- **The only infinite animation is the live dot.** It signals real-time data. Everything else settles.
- **200ms is the default transition.** Fast enough to feel instant, slow enough to be perceived. Don't go below 150ms or above 300ms for UI transitions.
- **`ease` for entrances, `ease-in-out` for loops.** No custom cubic-beziers unless proven necessary.
- **Respect `prefers-reduced-motion`.** Future improvement: wrap animations in `@media (prefers-reduced-motion: no-preference)`.

---

## 7. Icons & Diagrams

### Icon Treatment

Clarvis does not use an icon library. Visual markers are typographic:

| Pattern | Example | Context |
|---------|---------|---------|
| Monospace symbols | `>` as list bullet | Lists (`.clean-list`, `.policy-list`) |
| Monospace labels | `[λ]`, `[◆]`, `[↻]` | Feature icons (`.feature-icon`) |
| Emoji (sparingly) | Used in source content | Only when present in data, never added by design |

### Diagrams

Architecture and flow diagrams use the `.arch-diagram` pattern:

```
background: var(--surface)
border: 1px solid var(--border)
font-family: var(--font-mono)
font-size: 0.75rem
color: var(--text-muted)
white-space: pre
overflow-x: auto
```

ASCII/Unicode box-drawing characters are the diagram language. No SVG, no images, no embedded iframes.

### Rules

- **No icon fonts, no SVG sprite sheets.** Visual identity comes from typography and color, not illustration.
- **Monospace symbols as icons.** They're always available, always aligned, always on-brand.
- **Diagrams are text.** Rendered in monospace on a surface panel. This keeps them editable, versionable, and consistent.

---

## 8. Badges & Status Indicators

### Badge Anatomy

```
font-size: 0.6875rem
padding: 0.125rem 0.5rem
border-radius: 999px (pill)
font-weight: 500
letter-spacing: 0.02em
background: rgba(color, 0.12)
color: color
border: 1px solid rgba(color, 0.3)
```

### Variants

| Class | Color | Meaning |
|-------|-------|---------|
| `.badge-mode` | `--accent` (blue) | Mode indicator, informational |
| `.badge-public` | `--green` | Public, available, healthy |
| `.badge-stabilizing` | `--yellow` | In progress, stabilizing |
| `.badge-internal` | `--text-muted` (gray) | Internal, private, draft |

### Live Indicator

```css
.live-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--green);
  animation: pulse-subtle 2s ease-in-out infinite;
}
```

Placed inline before live data values to signal real-time refresh.

---

## 9. Layout

### Page Container

```
max-width: 840px
margin: 0 auto
padding: var(--space-xl) var(--space-md)
```

Narrow, readable column. Content-focused, not dashboard-wide.

### Grids

- **2-column** at desktop (`1fr 1fr`), single column below `600px`
- Gap: `var(--space-md)` (16px)
- Used for: status cards, feature cards

### Section Rhythm

```
section { margin-bottom: var(--space-xl); }
.section-divider {
  margin-top: var(--space-2xl);
  padding-top: var(--space-xl);
  border-top: 1px solid var(--border-subtle);
}
```

### Navigation

Horizontal flex row, `0.8125rem` font, muted text with accent-dim active state. Separated from content by `--border-subtle` bottom border.

---

## 10. Copy & Tone

### Voice

Clarvis speaks like a British butler who also happens to be a systems architect. The tone is:

- **Precise, not padded.** Say what it is, not what it's going to be about.
- **Understated confidence.** "3,400+ memories across 10 collections" — let the numbers speak.
- **Dry when appropriate.** The occasional sardonic aside is welcome. Forced humor is not.
- **Technical but accessible.** Use proper terminology, but explain architecture, not jargon.

### Writing Rules

| Do | Don't |
|----|-------|
| "Autonomous evolution engine" | "AI-powered smart automation platform" |
| "Dual-layer cognitive architecture" | "Next-gen intelligent agent framework" |
| "Local-first. No cloud dependencies." | "Privacy-focused enterprise-ready solution" |
| "Built on ChromaDB + ONNX" | "Leveraging state-of-the-art vector databases" |

### Headlines

- Short, declarative. "An evolving intelligence." not "Welcome to the future of AI agents!"
- Sentence case. Never ALL CAPS for headings.
- No exclamation marks in UI copy. Ever.

### Labels & Microcopy

- Uppercase only for micro-labels: `STATUS`, `MEMORIES`, `UPTIME`
- Use `>` as a visual bullet, not `-` or `*`
- Status text is factual: "Healthy", "Stabilizing", "Offline" — not "Everything looks great!"

---

## Quick Reference — Token Map

```css
:root {
  /* Surfaces */
  --bg: #0a0e14;
  --bg-raised: #0d1117;
  --surface: #151b24;
  --surface-hover: #1c2330;
  --border: #252d38;
  --border-subtle: #1e2530;

  /* Text */
  --text: #d1d7e0;
  --text-muted: #7d8590;
  --text-faint: #545d68;

  /* Accent & Signals */
  --accent: #58a6ff;
  --accent-dim: rgba(88, 166, 255, 0.12);
  --accent-glow: rgba(88, 166, 255, 0.06);
  --purple: #bc8cff;
  --green: #3fb950;
  --yellow: #d29922;
  --red: #f85149;
  --gradient-accent: linear-gradient(135deg, #58a6ff 0%, #bc8cff 100%);

  /* Spacing */
  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 1.5rem;
  --space-xl: 2.5rem;
  --space-2xl: 4rem;

  /* Shape */
  --radius: 8px;
  --radius-lg: 12px;

  /* Motion */
  --transition: 200ms ease;

  /* Type */
  --font-mono: 'SF Mono', 'Fira Code', 'Cascadia Code', 'JetBrains Mono', monospace;
}
```

---

_Clarvis Styleguide v1 — 2026-03-24. Source of truth for all public-facing Clarvis surfaces._
