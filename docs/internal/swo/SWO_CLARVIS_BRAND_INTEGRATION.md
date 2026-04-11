# SWO / Clarvis Brand Integration

_Comprehensive brand strategy for positioning Clarvis within Star World Order._
_Covers: Brand Audit, Design Brief, Naming Architecture, Token Alignment, Landing Concept, Copy Pass._
_Created: 2026-04-03_

---

## 1. Brand Audit

### Current Clarvis Identity

| Attribute | Current State |
|-----------|---------------|
| **Name** | Clarvis (JARVIS homage) |
| **Tagline** | "An AI That Learns While You Sleep" |
| **Personality** | British butler meets genius engineer. Dry wit, precision, sardonic. |
| **Icon/Mascot** | Lobster emoji (informal), no formal logo |
| **Color palette** | Dev-tool dark: `#58a6ff` accent blue, `#bc8cff` purple, `#3fb950` green, `#0a0e14` bg |
| **Typography** | System sans-serif (body), SF Mono / Fira Code (code/metrics) |
| **Aesthetic** | Clean, minimal, GitHub-dark inspired. Information-dense, engineer-facing. |
| **Voice** | Technical, confident, economical. "Most AI agents are brilliant amnesiacs." |

### Current SWO Identity

| Attribute | SWO State |
|-----------|-----------|
| **Name** | Star World Order |
| **Tagline** | "chosen by the stars - the order is forming" |
| **Mascot** | Skrumpeys (pixel frog NFTs, 333 constellation variants) |
| **Color palette** | Synthwave neon: `#ffd700` gold, `#9966ff` purple, `#4488ff` blue, `#0a0a1a` bg |
| **Typography** | Press Start 2P (pixel font), monospace fallback |
| **Aesthetic** | Retro N64/synthwave, pixel art, CRT scanlines, cozy gaming station |
| **Voice** | Cosmic, playful, community-driven. Arcade meets blockchain. |

### Gap Analysis

| Dimension | Compatibility | Notes |
|-----------|--------------|-------|
| **Background darkness** | High | Both use deep dark bg (~`#0a0e14` vs `#0a0a1a`). Nearly identical. |
| **Accent purple** | High | Clarvis `#bc8cff` / SWO `#9966ff`. Same family, different weight. |
| **Gold accent** | Gap | SWO uses gold `#ffd700` heavily. Clarvis has no gold. Must adopt. |
| **Typography** | Gap | Press Start 2P (pixel) vs system sans. Incompatible for body text. |
| **Personality** | Complementary | Butler precision + cosmic wonder can coexist. Clarvis = the "serious brain" behind SWO's playful exterior. |
| **Information density** | Strength | Clarvis's data-rich style fits SWO's "command center" fantasy. |
| **Animation style** | Gap | SWO: heavy pixel animations, CRT effects. Clarvis: subtle fadeUp. Needs bridging. |

### Verdict

Clarvis should **not** fully adopt SWO's pixel-art aesthetic. The engineering credibility would dissolve. Instead, Clarvis operates as the **premium technical layer** within SWO — think Tony Stark's lab inside a neon arcade. The UI speaks SWO's color language but keeps Clarvis's typographic clarity and information density.

**What stays Clarvis-native:**
- Name "Clarvis" (strong, recognizable, earned)
- Butler personality and voice
- Monospace code typography for data/metrics
- Information-dense layout patterns
- Clean card-based component structure

**What adopts SWO language:**
- Gold (`#ffd700`) as primary accent (replacing blue `#58a6ff`)
- Purple (`#9966ff`) as secondary (aligning existing `#bc8cff`)
- Dark background harmonized to `#0a0a1a`
- Pixel-border decorative accents (corner markers, card borders)
- Constellation color coding for categorization
- CRT glow effects (subtle, on headers/status indicators only)

---

## 2. Design Brief

### Concept: "Clarvis as SWO Intelligence Layer"

Clarvis is Star World Order's autonomous cognitive engine — the brain behind the order. It surfaces within SWO as a premium, slightly mysterious technical interface. Users encounter Clarvis through status dashboards, intelligence reports, and the "AI that never sleeps" narrative.

### Palette

```
Primary:
  --clarvis-gold:      #ffd700    /* SWO gold — primary accent, CTAs, highlights */
  --clarvis-gold-dim:  rgba(255, 215, 0, 0.12)
  --clarvis-gold-glow: rgba(255, 215, 0, 0.06)

Secondary:
  --clarvis-purple:      #9966ff  /* SWO purple — secondary, links, interactive */
  --clarvis-purple-dim:  rgba(153, 102, 255, 0.12)
  --clarvis-purple-glow: rgba(153, 102, 255, 0.06)

Semantic:
  --clarvis-green:  #44ff88       /* SWO green — success, healthy, active */
  --clarvis-blue:   #4488ff       /* SWO blue — info, links, neutral */
  --clarvis-red:    #ff4466       /* SWO red — error, critical, alert */

Backgrounds:
  --clarvis-bg:          #0a0a1a  /* Matched to SWO base */
  --clarvis-bg-raised:   #0d0d1f
  --clarvis-surface:     #151525
  --clarvis-surface-hover: #1c1c35

Text:
  --clarvis-text:       #e8e8e8   /* SWO foreground */
  --clarvis-text-muted: #7d8590
  --clarvis-text-faint: #545d68

Borders:
  --clarvis-border:        #252540
  --clarvis-border-subtle: #1e1e35
```

### Typography

```
/* Headings: SWO pixel font for brand alignment — small sizes only */
--font-display: 'Press Start 2P', monospace;

/* Body: Clean monospace for readability — Clarvis-native */
--font-body: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;

/* Data/metrics: Same as body — already monospace */
--font-data: var(--font-body);
```

**Rules:**
- Press Start 2P: nav labels, section headers, status badges, card titles. Max 14px. Never for body text.
- JetBrains Mono: all body copy, metrics, code, descriptions. 13-15px.
- Never mix Press Start 2P into paragraphs. It's decoration, not content.

### UI Motifs

1. **Pixel corner markers** — SWO's `::after` corner decoration (`content: '◢'`) on cards. Use sparingly on primary cards only.
2. **Gold glow on status indicators** — Replace Clarvis's blue pulse with gold `text-shadow` glow.
3. **CRT scanline overlay** — Optional, extremely subtle (2% opacity), on hero sections only. Disable on mobile.
4. **Retro border** — 2px embossed border on primary action buttons (SWO's `retro-border` pattern, thinned from 4px).
5. **Pixel-float animation** — Gentle 3s vertical bounce on mascot/icon elements. Not on data.

### Icon/Avatar Direction

- **No pixel frog.** Clarvis is not a Skrumpey. Clarvis's visual identity should be abstract/geometric: a stylized eye, neural network node, or constellation pattern.
- **Recommended**: A minimal gold-on-dark constellation pattern forming a "C" shape — ties to SWO's star/constellation theme while staying distinct.
- **Badge format**: Gold circle with constellation-C, used as favicon and avatar. Pixel-rendered at small sizes for SWO consistency.

### Copy Tone

- **Clarvis within SWO**: Maintain the dry British wit. The contrast with SWO's playful cosmic voice is a feature, not a bug. Clarvis is the "serious one" in the group — the precision instrument.
- **Template**: "Star World Order's autonomous intelligence. Clarvis remembers, reflects, and evolves — 24 hours a day, no prompting required."
- **Avoid**: "AI buddy", "magical", "vibes", "to the moon". Clarvis doesn't hype. It delivers.

### Correct vs Incorrect Usage

| Context | Correct | Incorrect |
|---------|---------|-----------|
| SWO landing page | "Powered by Clarvis — autonomous intelligence that never sleeps." | "Meet our AI friend Clarvis! He's super smart!" |
| Dashboard header | "Clarvis Intelligence" in Press Start 2P, gold | "CLARVIS AI DASHBOARD" in rainbow gradient |
| Status indicator | Gold pulsing dot + "Clarvis: Active" | Pixel frog avatar with "Clarvis is thinking..." |
| Error message | "Clarvis: Retrieval degraded. Investigating." | "Oops! Clarvis had a brain fart!" |
| Feature description | "Persistent vector memory with Hebbian learning dynamics" | "Clarvis remembers stuff really well" |

---

## 3. Naming Architecture

### Core Principle

Clarvis is a **product name**, not a feature label. It retains standalone identity while being positioned as an SWO capability.

### Hierarchy

```
Star World Order                    ← Brand / Platform
  └── Clarvis                       ← Product / Intelligence Layer
        ├── Clarvis Intelligence     ← Dashboard / Status view
        ├── Clarvis Memory           ← Brain/memory subsystem
        ├── Clarvis Heartbeat        ← Autonomous execution cycle
        └── Clarvis Reports          ← Digest/analysis outputs
```

### Naming Rules

| Pattern | When to Use | Example |
|---------|-------------|---------|
| **"Clarvis"** alone | When context makes the parent clear (inside SWO UI) | "Clarvis is active" |
| **"Clarvis by Star World Order"** | External references, press, social | "Clarvis by Star World Order — autonomous AI intelligence" |
| **"SWO Clarvis"** | Never. Sounds like a product code, not a name. | — |
| **"Star World Order's Clarvis"** | Possessive context in prose | "Star World Order's Clarvis engine powers..." |
| **"Clarvis Intelligence"** | Dashboard/UI section header | Nav item: "Intelligence" (Clarvis implied by section) |

### Feature Naming Within SWO

| SWO Feature | Clarvis-Powered? | Display Name | Internal Reference |
|-------------|-------------------|--------------|-------------------|
| Member dashboard stats | Yes | "Intelligence" tab | `clarvis-intelligence` |
| Autonomous reports | Yes | "Clarvis Reports" | `clarvis-reports` |
| Brain search | Yes | "Memory Search" | `clarvis-memory` |
| NFT gallery | No | "Gallery" | `gallery` |
| DAO governance | No | "Governance" | `dao` |
| Raffle system | No | "Raffle" | `raffle` |

### Dashboard Terminology

| Internal Term | Public-Facing Name |
|---------------|-------------------|
| Heartbeat | "Pulse" (friendlier, cosmic metaphor) |
| Brain/ChromaDB | "Memory" |
| Evolution Queue | "Roadmap" or "Evolution" |
| Performance Index | "Health Score" |
| Cron job | "Scheduled Task" |
| Episode | "Activity Log Entry" |

---

## 4. Token Alignment

### SWO Tokens Available for Reuse

| SWO Token | CSS Variable | Clarvis Mapping |
|-----------|-------------|-----------------|
| `--pixel-gold` | `#ffd700` | `--clarvis-gold` (primary accent) |
| `--pixel-purple` | `#9966ff` | `--clarvis-purple` (secondary) |
| `--pixel-blue` | `#4488ff` | `--clarvis-blue` (info) |
| `--pixel-green` | `#44ff88` | `--clarvis-green` (success) |
| `--pixel-red` | `#ff4466` | `--clarvis-red` (error) |
| `--pixel-dark` | `#1a1a2e` | `--clarvis-surface` (adjusted) |
| `--pixel-darker` | `#0d0d1a` | `--clarvis-bg-raised` |
| `--background` | `#0a0a1a` | `--clarvis-bg` (direct match) |
| `--foreground` | `#e8e8e8` | `--clarvis-text` (direct match) |

### SWO Tokens NOT Reused (Clarvis diverges)

| SWO Token | Why Not |
|-----------|---------|
| `--neon-cyan` `#00ffff` | Too arcade. Clarvis needs restraint. |
| `--neon-magenta` `#ff00ff` | Same — pure neon breaks data readability. |
| `--neon-pink` `#ff6ec7` | No use case in Clarvis UI. |
| `--sunset-orange` `#ff7b00` | Conflicts with warning semantics. |
| `--crt-glow` | Clarvis uses gold glow instead. |

### Missing Tokens (Must Be Added)

These tokens exist in Clarvis's design system but have no SWO equivalent:

| Clarvis Token | Value | Purpose | Action |
|---------------|-------|---------|--------|
| `--clarvis-gold-dim` | `rgba(255,215,0,0.12)` | Card backgrounds, hover states | Add to SWO shared tokens |
| `--clarvis-purple-dim` | `rgba(153,102,255,0.12)` | Interactive element backgrounds | Add to SWO shared tokens |
| `--clarvis-border` | `#252540` | Card/section borders | Add to SWO shared tokens |
| `--clarvis-text-muted` | `#7d8590` | Secondary text | Add to SWO shared tokens |
| `--clarvis-text-faint` | `#545d68` | Tertiary text | Add to SWO shared tokens |

### Component Class Mapping

| SWO Class | Clarvis Equivalent | Compatibility |
|-----------|-------------------|---------------|
| `.pixel-card` | `.clarvis-card` | Adapt: use gold glow instead of purple, keep corner marker |
| `.pixel-btn` | `.clarvis-btn` | Adapt: use `--clarvis-purple` bg, retro-border at 2px |
| `.pixel-btn-gold` | `.clarvis-btn-primary` | Direct reuse for primary CTAs |
| `.pixel-glow-gold` | `.clarvis-glow` | Direct reuse for status text |
| `.animate-pixel-float` | `.clarvis-float` | Reuse for decorative elements only |
| `.animate-pixel-pulse` | `.clarvis-pulse` | Reuse for status indicators |

### Constellation Colors for Categorization

Leverage SWO's constellation system for Clarvis data categories:

| Constellation | Color | Clarvis Use |
|---------------|-------|-------------|
| Solveil (Gold) | `#ffd700` | Active/healthy status |
| Nebulu (Purple) | `#9966ff` | Intelligence/cognitive |
| Aether (Blue) | `#87CEEB` | Memory/retrieval |
| Rose (Pink) | `#FFB6C1` | Reflection/assessment |
| Parallel (Green-Blue) | gradient | Performance/benchmarks |

---

## 5. Landing Page Concept

### Page: `/intelligence` (Clarvis within SWO)

```
┌─────────────────────────────────────────────────┐
│  [SWO NAV BAR]  Home  Gallery  DAO  Intelligence│
├─────────────────────────────────────────────────┤
│                                                 │
│  ╔═══════════════════════════════════════════╗  │
│  ║  CLARVIS          [Gold constellation-C]  ║  │
│  ║  Autonomous Intelligence                  ║  │
│  ║                                           ║  │
│  ║  "An AI that remembers everything,        ║  │
│  ║   reflects on itself, and gets better     ║  │
│  ║   while you sleep."                       ║  │
│  ║                                           ║  │
│  ║  [View on GitHub]  [Architecture]         ║  │
│  ╚═══════════════════════════════════════════╝  │
│                                                 │
│  ┌─── STATUS ──────────────────────────────┐   │
│  │  ● Active   Pulse: 12/day   Memory: 3.4k│   │
│  │  Health: 0.87   Last Task: 4m ago        │   │
│  └──────────────────────────────────────────┘   │
│                                                 │
│  ┌─── WHAT IS CLARVIS ─────────────────────┐   │
│  │                                          │   │
│  │  Most AI agents forget between sessions. │   │
│  │  Clarvis doesn't.                        │   │
│  │                                          │   │
│  │  Persistent vector memory. Hebbian       │   │
│  │  learning. 20+ autonomous jobs daily.    │   │
│  │  Self-benchmarking across 8 dimensions.  │   │
│  │  All local — zero cloud for retrieval.   │   │
│  │                                          │   │
│  └──────────────────────────────────────────┘   │
│                                                 │
│  ┌─── CAPABILITIES ───────────────────────┐    │
│  │  [Memory]  [Evolution]  [Reflection]    │    │
│  │  [Hebbian] [Performance] [Orchestration]│    │
│  │  (6 pixel-cards with gold icons)        │    │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  ┌─── LIVE METRICS ───────────────────────┐    │
│  │  Brain Speed: 269ms avg                 │    │
│  │  Retrieval Quality: P@3 = 1.0           │    │
│  │  Performance Index: 0.87                │    │
│  │  Evolution Velocity: 4.2 tasks/day      │    │
│  │  (real-time from status.json API)       │    │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  ┌─── RECENT ACTIVITY ────────────────────┐    │
│  │  3m ago  Spine migration — 8 modules    │    │
│  │  1h ago  Queue cleanup + brand tasks    │    │
│  │  4h ago  Prompt quality pipeline        │    │
│  │  (from episodes, styled as pixel-cards) │    │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  ┌─── ARCHITECTURE ───────────────────────┐    │
│  │  Dual-layer diagram:                    │    │
│  │  Conscious (M2.5) ←→ Subconscious (CC) │    │
│  │  (simplified, SWO-styled)               │    │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  Powered by Clarvis · Star World Order         │
└─────────────────────────────────────────────────┘
```

### CTA Hierarchy

1. **Primary**: "View on GitHub" — gold pixel-btn, top hero
2. **Secondary**: "Architecture" — ghost btn, top hero
3. **Tertiary**: Capability cards — clickable, expand to detail

### Section Priorities

1. Hero + status (immediate credibility: "it's alive and working")
2. Problem/solution statement (why this matters)
3. Capability grid (what it does)
4. Live metrics (proof it works)
5. Recent activity (proof it's active)
6. Architecture (how it works — for the curious)

---

## 6. Copy Pass

### Hero

**Before:** "Clarvis — An AI That Learns While You Sleep"

**After:** "Clarvis — Autonomous Intelligence That Never Stops Learning"

_Rationale: "While you sleep" is cute but limits scope. Clarvis runs 24/7 regardless of operator state._

### Subtitle

**Before:** "An AI agent that remembers everything, reflects on itself, and gets better while you sleep."

**After:** "Persistent memory. Autonomous reflection. Continuous evolution. Star World Order's cognitive engine."

_Rationale: Adds SWO attribution naturally. Tighter structure. Removes second "while you sleep"._

### Problem Statement

**Before:** "Today's AI agents are brilliant amnesiacs. They solve hard problems in the moment, then forget everything the next session."

**After:** "Today's AI agents are brilliant amnesiacs — sharp in the moment, blank the next session. They can't learn from their own mistakes or measure their own improvement."

_Rationale: Punchier. Adds the self-measurement angle that differentiates Clarvis._

### Approach Statement

**Before:** "Clarvis treats memory as the core primitive, not an afterthought."

**After:** "Clarvis treats memory as infrastructure, not afterthought. Every task produces a structured episode — what was attempted, what happened, what was learned. Episodes feed attention scoring, context assembly, and retrieval quality. The agent improves through operation."

_Rationale: "Infrastructure" > "primitive" for non-technical audiences. Added the feedback loop explanation._

### Feature Card Copy (6 cards)

1. **Persistent Memory**: "3,400+ memories across 10 specialized collections. ChromaDB + ONNX embeddings, fully local. No API calls for recall — ever."
2. **Autonomous Evolution**: "12 heartbeats daily. Morning planning, afternoon sprints, evening reflection, nightly dreams. No prompting required."
3. **Hebbian Learning**: "Memories that fire together wire together. Synaptic dynamics strengthen useful connections through use, not retraining."
4. **Self-Benchmarking**: "8 performance dimensions measured continuously. Brain speed, retrieval quality, efficiency, accuracy — tracked, trended, and self-corrected."
5. **Cognitive Architecture**: "Global workspace theory, episodic memory, procedural learning, working memory buffers. Built on peer-reviewed cognitive science."
6. **Agent Orchestration**: "Clarvis delegates to specialized project agents in isolated workspaces. Each gets its own brain, benchmarks, and golden QA set."

### SWO-Specific Attribution Line

Use at page bottom or in SWO navigation:

> "Clarvis is the Astral Machine Intelligence. Star World Order is one of its primary public surfaces."

### Voice Guidelines for Future Copy

- **Do**: Be precise, confident, slightly dry. Lead with what Clarvis does, not what it is.
- **Do**: Use technical terms when they're the right terms. "Hebbian learning" is better than "smart memory."
- **Do**: Reference measurable outcomes. "269ms avg retrieval" > "fast memory."
- **Don't**: Use cosmic/mystical language for Clarvis itself (save that for SWO framing).
- **Don't**: Anthropomorphize beyond the butler persona. "Clarvis reflects" is fine. "Clarvis feels" is not.
- **Don't**: Over-explain. Trust the reader to click through for details.

---

## Implementation Priority

| Action | Effort | Impact | Order |
|--------|--------|--------|-------|
| Update website CSS variables to aligned palette | Small | High | 1 |
| Add Press Start 2P for headers in website | Small | Medium | 2 |
| Rewrite hero/feature copy per Section 6 | Small | High | 3 |
| Create constellation-C favicon/avatar | Medium | High | 4 |
| Build `/intelligence` page for SWO integration | Large | High | 5 |
| Export shared token JSON for cross-repo use | Small | Medium | 6 |

---

_This document is the single source of truth for Clarvis/SWO brand alignment decisions. Update here first, implement second._
