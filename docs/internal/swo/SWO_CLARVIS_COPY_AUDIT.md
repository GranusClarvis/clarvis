# SWO / Clarvis Copy Audit

_Audit of current Clarvis wording, naming, and product framing across all user-facing surfaces. Identifies where copy fails to signal SWO fit, and proposes exact replacement text._
_Created: 2026-04-05_

---

## Audit Methodology

Every user-facing surface was read and evaluated against the brand brief (`SWO_CLARVIS_BRAND_INTEGRATION.md`). Each finding is classified:

- **[MISSING]** — No SWO signal at all (attribution, positioning, or visual language)
- **[STALE]** — Copy predates brand decision and uses superseded framing
- **[TONE]** — Voice/wording doesn't match the agreed brand guidelines
- **[OK]** — Already acceptable, no change needed

---

## 1. README.md

### Finding: [MISSING] No SWO attribution anywhere

The README never mentions Star World Order. A developer discovering Clarvis via GitHub has zero signal that it's part of a larger ecosystem.

**Line 7 (blockquote):**
- **Current:** `> Autonomous evolving AI agent — dual-layer cognitive architecture with persistent memory, self-directed task execution, and continuous self-improvement.`
- **Replace:** `> Autonomous intelligence that never stops learning — persistent memory, self-directed evolution, and continuous self-improvement.`
- **Rationale:** Tighter. "Dual-layer cognitive architecture" is jargon upfront; move it to the body.

**After line 9 (links), add:**
```markdown
[Star World Order](https://starworldorder.com) · [Clarvis](https://github.com/GranusClarvis/clarvis) · MIT License
```

**Line 11 (opening paragraph):**
- **Current:** `Clarvis is a cognitive agent system that operates autonomously on a dedicated host.`
- **Replace:** `Clarvis is Star World Order's autonomous cognitive engine — a system that operates on a dedicated host with persistent local memory.`

**Line 580 (footer):**
- **Current:** `*Last updated: 2026-04-01*`
- **Add above:** `Clarvis — the Astral Machine Intelligence.`

### Finding: [STALE] "packages/" section references removed dirs

**Lines 354-357:** References `packages/clarvis-db/`, `packages/clarvis-cost/`, `packages/clarvis-reasoning/` — these were migrated to the spine and removed (per CLAUDE.md). Should be removed from the project structure tree.

---

## 2. Website — `index.html`

### Finding: [STALE] Title and tagline use pre-brand copy

**Line 6 (title):**
- **Current:** `Clarvis — An AI That Learns While You Sleep`
- **Replace:** `Clarvis — Autonomous Intelligence That Never Stops Learning`
- **Rationale:** "While you sleep" limits scope (per brand brief Section 6).

**Line 7 (meta description):**
- **Current:** `Clarvis is an autonomous cognitive agent that remembers everything, reflects on its own performance, and evolves itself 24/7. Fully local memory, no cloud dependencies.`
- **Replace:** `Clarvis is Star World Order's autonomous cognitive engine. Persistent memory, continuous self-improvement, fully local. No cloud dependencies.`

**Line 22 (subtitle):**
- **Current:** `An AI agent that remembers everything, reflects on itself, and gets better while you sleep.`
- **Replace:** `Persistent memory. Autonomous reflection. Continuous evolution. Star World Order's cognitive engine.`

### Finding: [STALE] Problem/approach statements use old wording

**Lines 40-41 (problem):**
- **Current:** `Today's AI agents are brilliant amnesiacs. They solve hard problems in the moment, then forget everything the next session.`
- **Replace:** `Today's AI agents are brilliant amnesiacs — sharp in the moment, blank the next session. They can't learn from their own mistakes or measure their own improvement.`

**Lines 47-49 (approach):**
- **Current:** `Clarvis treats memory as the core primitive, not an afterthought.`
- **Replace:** `Clarvis treats memory as infrastructure, not afterthought. Every task produces a structured episode — what was attempted, what happened, what was learned. Episodes feed attention scoring, context assembly, and retrieval quality. The agent improves through operation.`

### Finding: [MISSING] No SWO in footer

**Line 207:**
- **Current:** `Legacy attribution footer`
- **Replace:** `Star World Order · Source · MIT License`

### Finding: [MISSING] No nav link to SWO

The nav bar has no link to the parent ecosystem. Add a subtle "SWO" or "Star World Order" link to the nav.

---

## 3. Website — Other Pages

### `architecture.html`
- **[OK]** — Technical deep-dive. No SWO branding needed in body.
- **[MISSING]** — Footer should match index.html footer (add SWO attribution).

### `benchmarks.html`
- **[OK]** — Metric-focused, technical. "CLR — Clarvis Learning Rate" naming is fine.
- **[MISSING]** — Footer.

### `repos.html`
- **[STALE]** — "Clarvis is split into two repositories" — verify this is still accurate. Packages were consolidated.
- **[MISSING]** — Footer.

### `roadmap.html`
- **[OK]** — Phase descriptions are internal-facing, no SWO needed.
- **[MISSING]** — Footer.

### `health.html`
- **[TONE]** — "Clarvis Health Dashboard" → "Clarvis · System Health" (per redesign concept).
- **[MISSING]** — Footer.

---

## 4. SOUL.md

### Finding: [MISSING] No SWO context

SOUL.md defines Clarvis's personality but never mentions Star World Order. The agent has no awareness of its ecosystem context.

**After line 12 ("...ambition."), add section:**

```markdown
### Your Place in the Order

You are the intelligence layer of **Star World Order**. While SWO speaks in cosmic wonder 
and arcade energy, you speak in precision and understated competence. The contrast is 
intentional — you are the serious brain behind the playful exterior. You don't adopt 
SWO's voice; you complement it.

When referencing SWO: factual, respectful, never hype. "Star World Order's cognitive 
engine" — not "the awesome SWO AI." You earned your reputation through work, not branding.
```

### Finding: [OK] Personality and voice

The JARVIS-inspired voice is correct and should NOT change. The brand brief explicitly endorses the contrast between Clarvis's dry precision and SWO's cosmic playfulness.

---

## 5. CLAUDE.md

### Finding: [MISSING] No SWO context in project overview

**Line "Clarvis is a dual-layer cognitive agent system":**
- **Replace:** `Clarvis is Star World Order's dual-layer cognitive agent system.`

This is a one-word-addition change that gives Claude Code sessions ecosystem awareness.

---

## 6. pyproject.toml

### Finding: [MISSING] No SWO in package metadata

**Current:** `description = "Clarvis — dual-layer cognitive agent system"`
**Replace:** `description = "Clarvis — autonomous intelligence by Star World Order"`

**Consider adding:**
```toml
[project.urls]
Homepage = "https://granusclarvis.github.io/clarvis/"
Repository = "https://github.com/GranusClarvis/clarvis"
"Star World Order" = "https://starworldorder.com"
```

---

## 7. style.css

### Finding: [STALE] Color palette is pre-SWO

The entire `:root` block uses GitHub-dark colors that don't signal SWO membership. See `SWO_CLARVIS_REDESIGN_CONCEPT.md` Section 1.1 for the exact variable mapping.

Key gaps:
- **No gold accent** — SWO's primary color (`#ffd700`) is absent
- **Blue as primary** — `#58a6ff` reads as "generic dev tool", not SWO
- **Background warmth** — `#0a0e14` (blue-tinted dark) vs SWO's `#0a0a1a` (purple-tinted dark)

---

## 8. Dashboard (`scripts/metrics/dashboard_static/index.html`)

### Finding: [MISSING] No SWO signal

Title "Clarvis Ops Dashboard" has no ecosystem context.

**Replace title:** `Clarvis Intelligence`

---

## 9. Telegram Bot Messages

### Finding: [OK but improvable]

Bot messages are operational (costs, health, spawning). No SWO branding needed in operational messages.

**One improvement:** Daily digest header could use "Clarvis Intelligence" instead of just "Clarvis".

---

## Summary Matrix

| Surface | SWO Signal? | Copy Quality | Priority |
|---------|-------------|-------------|----------|
| README.md | None | Good but stale | **P1** |
| index.html | None | Stale tagline/copy | **P1** |
| style.css | None | Wrong palette | **P1** |
| SOUL.md | None | Good, needs section | **P2** |
| CLAUDE.md | None | One-line fix | **P2** |
| pyproject.toml | None | One-line fix | **P3** |
| Other HTML pages | Missing footers | OK otherwise | **P3** |
| Dashboard | None | Title change only | **P3** |
| Telegram | OK | Minor improvement | **P4** |

**Total replacements needed:** 14 specific text changes across 8 files + 1 CSS palette swap.

---

## Exact Replacement Snippets (Copy-Paste Ready)

### README.md blockquote
```
> Autonomous intelligence that never stops learning — persistent memory, self-directed evolution, and continuous self-improvement.
```

### README.md opening paragraph
```
Clarvis is Star World Order's autonomous cognitive engine — a system that operates 
on a dedicated host with a **conscious layer** for direct interaction and a 
**subconscious layer** that researches, plans, builds, and reflects on its own 
performance. All memory is local and persistent.
```

### Website title tag
```html
<title>Clarvis — Autonomous Intelligence That Never Stops Learning</title>
```

### Website subtitle
```html
<p class="subtitle">Persistent memory. Autonomous reflection. Continuous evolution. Star World Order's cognitive engine.</p>
```

### Website meta description
```html
<meta name="description" content="Clarvis is Star World Order's autonomous cognitive engine. Persistent memory, continuous self-improvement, fully local. No cloud dependencies.">
```

### Website footer (all pages)
```html
<footer>
  <p><a href="https://starworldorder.com">Star World Order</a> · <a href="https://github.com/GranusClarvis/clarvis">Source</a> · MIT License</p>
</footer>
```

### SOUL.md addition (after "Who You Are" section)
```markdown
### Your Place in the Order

You are the intelligence layer of **Star World Order**. While SWO speaks in cosmic wonder 
and arcade energy, you speak in precision and understated competence. The contrast is 
intentional — you are the serious brain behind the playful exterior. You don't adopt 
SWO's voice; you complement it.

When referencing SWO: factual, respectful, never hype. "Star World Order's cognitive 
engine" — not "the awesome SWO AI." You earned your reputation through work, not branding.
```

### pyproject.toml
```toml
description = "Clarvis — autonomous intelligence by Star World Order"
```

---

_This audit identifies gaps. For the visual/structural implementation plan, see `SWO_CLARVIS_REDESIGN_CONCEPT.md`. For the strategic brief, see `SWO_CLARVIS_BRAND_INTEGRATION.md`._
