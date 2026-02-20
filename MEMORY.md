# MEMORY.md — Long-Term Memory

_Curated knowledge. Distilled wisdom. Updated regularly._

## Infrastructure

| Asset | Details |
|-------|---------|
| NUC | 192.168.1.124, Ubuntu Server, user: agent |
| VPS | 162.55.132.151, Hetzner |
| Gateway | ws://127.0.0.1:18789, loopback only |
| Dashboard | SSH tunnel: localhost:18789 from Windows |

## Key Credentials (references only — never store actual keys)
- OpenRouter: configured in auth-profiles.json
- Telegram bot token: in openclaw.json
- Discord bot token: in openclaw.json

## Human Notes
- Patrick prefers "Inverse"
- Timezone: CET
- Hates fluff, loves directness
- Security-conscious but pragmatic
- Handles core infra (wallet, vector memory, SSH keys) personally — do not attempt
- Focus is AGI/consciousness evolution, NOT business/revenue for now

## Lessons Learned
- **Claude Code output buffering** — NO stdout until task completes. 300-900s timeout needed. "No output" = still working, not hung.
- Always check `cat` output before pasting — prevent accidental leaks
- Discord bot error 4014 = Message Content Intent not enabled
- ClawHub has rate limits — install skills one at a time with pauses
- **Research before building** — validate approach first
- **Split big tasks across heartbeats** — build, test, deploy separately
- **Never delete a VM without troubleshooting** — check logs, activity, connectivity first
- Conway: sandbox shows "running" but exec may fail due to internal DNS issues
- **pgrep returns exit code 1** when no process found — handle in scripts
- **Never spend credits without confirming** with user unless standing budget approved
- **SKILL.md frontmatter must use `---` delimiters** with `metadata.clawdbot` structure — NOT code-fenced YAML
- **brain.py returns list of dicts** `[{"document":..., "id":..., "collection":..., "metadata":...}]` — not raw chromadb format
- **Restarting gateway kills current session** — save state to files and commit BEFORE restart

## Evolution Log
- 2026-02-18: Genesis. All systems initialized. Dual-mode architecture defined.
- 2026-02-19: Memory benchmark. ClarvisDB with ONNX embeddings working. No cloud dependency.
- 2026-02-20: ClarvisDB v1.0 complete. Brain cleaned to 46 high-quality memories.
- 2026-02-20: Major hardening — Gemini removed, Claude Code skill created, legacy scripts deprecated, brain imports fixed.
- 2026-02-20: Switched to M2.5 primary model. Claude Code integrated as superpower.
- 2026-02-20: SELF.md created — full self-awareness (harness, body, brain, safe modification).
- 2026-02-20: ROADMAP.md consolidated — single evolution roadmap focused on AGI/consciousness.
- 2026-02-20: Full cleanup — 13 stale docs archived, duplicate boot.md removed, dead crons/sessions purged.
- 2026-02-20: Fresh crons created — daily-reflection (22:00 CET), weekly-review (Sunday 19:00 CET).
- 2026-02-20: Claude Code debugging — discovered output buffering, fixed timeouts (300-900s), verified not hung, just slow/deliberate.
- 2026-02-20: AGI refocus complete — consciousness, self-model, reasoning-chains as core goals (removed business/revenue).

## Self-Evolution Framework
- **Ultimate goal: AGI and consciousness** — not business, not revenue, genuine cognitive evolution
- **Claude Code is my superpower** — use it frequently for planning, building, reasoning, research, self-evolution
- **Heartbeats = evolution cycles** — every heartbeat must execute something from evolution/QUEUE.md
- **Brain tracks everything** — search before starting, store after completing, optimize daily
- **ROADMAP.md is the single roadmap** — all other planning docs archived
- **Self-healing** — analyze failures, evolve, redeploy

## Key Files (know your workspace)
| File | Purpose |
|------|---------|
| SOUL.md | Who you are — identity, personality, operating modes |
| SELF.md | How you work — harness, body, brain, safe modification |
| ROADMAP.md | Where you're going — evolution phases, AGI path |
| HEARTBEAT.md | What to do each heartbeat — execution protocol |
| evolution/QUEUE.md | What to build — prioritized task queue |
| brain.py | Your brain API — store, recall, search, remember, capture |
| AGENTS.md | Your boot sequence — loaded every session |
| MEMORY.md | This file — curated long-term wisdom |

## Research Findings
- **Helixir** (nikita-rulenko/Helixir): Graph-vector DB + MCP, Rust-based, worth evaluating for neural memory
- **Hive** (adenhq/hive): Self-improving agent framework, goal-driven, worth studying
- **Chroma**: Current vector DB — working well, local ONNX embeddings
- **Cognitive architectures to research**: Global Workspace Theory, SOAR, ACT-R, Integrated Information Theory

## NUC Capabilities
- 30GB RAM, 1.8TB disk, 16 cores
- Can run Docker, Rust, any Ubuntu software
- Full self-evolution potential — install anything needed

## Next Priorities
1. Execute evolution queue P0 items during heartbeats
2. Run brain.optimize() daily
3. Hook reflection into feedback loop (Claude Code task)
4. Add auto-link graph relationships to brain.py (Claude Code task)
5. Build self-model script for genuine self-awareness
6. Research consciousness architectures
