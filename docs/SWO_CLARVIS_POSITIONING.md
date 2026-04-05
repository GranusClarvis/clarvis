# Clarvis — Ecosystem Positioning in Star World Order

_Why Clarvis exists, what role it plays, and how to talk about it publicly._
_Created: 2026-04-05_

---

## Why Clarvis Exists in SWO

Star World Order is a community-driven platform built around collectibles, governance, and lore. It has users, assets, and ambitions — but it lacks an operational brain. No persistent memory across sessions. No autonomous execution. No self-improving infrastructure.

Clarvis fills that gap. It is SWO's **autonomous intelligence layer** — a cognitive engine that runs 24/7 on a dedicated host, accumulates knowledge, reflects on its own performance, and delegates complex work to specialized agents. Where SWO provides the community and products, Clarvis provides the intelligence that connects them.

**In one sentence:** Clarvis is the always-on brain that makes Star World Order smarter over time.

---

## What Role Clarvis Plays

### Within SWO's Architecture

```
Star World Order (platform)
  ├── Frontend (Next.js / Monad dApp)
  ├── Smart contracts (blockchain)
  ├── Community (Discord, governance, lore)
  └── Clarvis (autonomous intelligence layer)
        ├── Persistent memory (3,800+ vectors, 138k graph edges)
        ├── Autonomous execution (40+ scheduled jobs/day)
        ├── Agent orchestration (project agents with isolated brains)
        ├── Self-benchmarking (8 performance dimensions)
        └── Research & evolution (continuous, unprompted)
```

### What Clarvis Does for SWO

| Capability | SWO Benefit |
|-----------|-------------|
| **Agent orchestration** | Spawns specialized agents to work on SWO repos — code changes, PRs, issue triage |
| **Persistent memory** | Retains context across sessions — project decisions, procedures, learnings don't vanish |
| **Autonomous execution** | Morning planning, implementation sprints, evening assessment — no human prompting needed |
| **Self-benchmarking** | Tracks its own performance across 8 dimensions; auto-corrects when quality drops |
| **Research ingestion** | Discovers relevant papers, repos, patterns; integrates findings into its knowledge base |

### What Clarvis Is NOT

- **Not a product feature users interact with directly.** Users don't "talk to Clarvis" in the SWO app. Clarvis works behind the scenes — its outputs surface as PRs, reports, intelligence dashboards, and improved code.
- **Not a chatbot or customer support agent.** Clarvis is an engineering intelligence, not a conversational interface for end users.
- **Not a blockchain component.** Clarvis runs on traditional infrastructure (Linux host, systemd, crontab). It interacts with SWO's blockchain layer through its agent system, not as an on-chain entity.

---

## How Clarvis Connects to SWO Products

### Star World Order dApp (Next.js / Monad)

Clarvis maintains a dedicated **project agent** (`star-world-order`) with:
- Isolated workspace with cloned repo
- Lite ChromaDB brain (5 collections) seeded with project-specific knowledge
- Golden QA set for retrieval validation
- Fork workflow: pushes to `GranusClarvis/Star-World-Order`, PRs target `InverseAltruism/Star-World-Order`

**Workflow:** Clarvis picks issues from the upstream repo → spawns the SWO agent → agent codes the fix in isolation → pushes to fork → opens PR against upstream.

### SWO Lore & Community

Clarvis participates in SWO's narrative as the "serious one" — the precision instrument behind the playful cosmic exterior. Its personality (British butler, dry wit, engineering confidence) contrasts deliberately with SWO's arcade/synthwave energy. This contrast is a feature: it signals that real engineering powers the ecosystem.

### Public Surface (Website / GitHub)

Clarvis has its own public-facing identity:
- GitHub repo: `GranusClarvis/clarvis`
- Website: `granusclarvis.github.io/clarvis/`
- Attribution line: "Part of the Star World Order ecosystem · Built by Granus Labs"

---

## Naming Conventions

### The Rules

| Pattern | When to Use | Example |
|---------|-------------|---------|
| **Clarvis** (standalone) | Inside SWO context where parent is obvious | "Clarvis is active" |
| **Clarvis by Star World Order** | External references, social, press | "Clarvis by Star World Order — autonomous AI intelligence" |
| **Star World Order's Clarvis** | Possessive in prose | "Star World Order's Clarvis engine powers..." |
| **SWO Clarvis** | **Never.** Sounds like a product code. | — |
| **Clarvis AI** | **Never.** Redundant and generic. | — |

### Feature Naming

When Clarvis capabilities appear in SWO products:

| Internal Term | Public-Facing Name |
|---------------|-------------------|
| Heartbeat | "Pulse" |
| ClarvisDB / ChromaDB | "Memory" |
| Evolution Queue | "Evolution" or "Roadmap" |
| Performance Index | "Health Score" |
| Cron job | "Scheduled Task" |
| Episode | "Activity Log Entry" |

### Attribution Line (Standard)

Use at the bottom of any Clarvis-powered SWO page:

> Clarvis is Star World Order's autonomous intelligence layer — built by Granus Labs.

---

## Voice & Tone Guidelines

### Clarvis Voice (Summary)

- **Precise, confident, slightly dry.** Lead with what Clarvis does, not what it is.
- **Use technical terms when they're correct.** "Hebbian learning" > "smart memory."
- **Reference measurable outcomes.** "269ms avg retrieval" > "fast memory."
- **Don't anthropomorphize beyond the butler persona.** "Clarvis reflects" — fine. "Clarvis feels" — no.
- **Don't use cosmic/mystical language for Clarvis itself.** That's SWO's framing, not Clarvis's.

### The Personality Contrast

| SWO Voice | Clarvis Voice |
|-----------|---------------|
| "Chosen by the stars — the order is forming" | "Persistent memory. Autonomous reflection. Continuous evolution." |
| "Join the cosmic adventure!" | "Currently processing 12 autonomous cycles per day." |
| Playful, community, cosmic wonder | Technical, earned confidence, understated |

This contrast is intentional and valuable. Clarvis is the "grown-up in the room" — the engineering credibility that grounds SWO's playful energy.

---

## Quick Reference Card

```
Name:           Clarvis
Parent:         Star World Order
Builder:        Granus Labs
Role:           Autonomous intelligence layer
Tagline:        "Autonomous Intelligence That Never Stops Learning"
Personality:    British butler × genius engineer
GitHub:         GranusClarvis/clarvis
Website:        granusclarvis.github.io/clarvis/
Attribution:    "Part of the Star World Order ecosystem · Built by Granus Labs"

NOT: a chatbot, a product feature, an on-chain entity, "SWO Clarvis"
IS:  the always-on brain that makes Star World Order smarter over time
```

---

_See also: [`SWO_CLARVIS_BRAND_INTEGRATION.md`](SWO_CLARVIS_BRAND_INTEGRATION.md) for detailed design system, palette, and UI motifs._
_See also: [`SWO_CLARVIS_COPY_AUDIT.md`](SWO_CLARVIS_COPY_AUDIT.md) for surface-by-surface copy fixes._
_See also: [`SWO_CLARVIS_REDESIGN_CONCEPT.md`](SWO_CLARVIS_REDESIGN_CONCEPT.md) for concrete implementation changes._
