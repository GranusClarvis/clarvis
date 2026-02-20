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
- Gemini: configured
- Google Places: placeholder key
- Telegram bot token: in openclaw.json
- Discord bot token: in openclaw.json

## Human Notes
- Patrick prefers "Inverse"
- Timezone: CET
- Hates fluff, loves directness
- Security-conscious but pragmatic
- Handles core infra (wallet, vector memory, SSH keys) personally — do not attempt

## Lessons Learned
- Always check `cat` output before pasting — prevent accidental leaks
- Discord bot error 4014 = Message Content Intent not enabled
- ClawHub has rate limits — install skills one at a time with pauses
- **Research before building** — validate monetization path first
- **Gas API is not viable** — free everywhere (Etherscan, Alchemy, Infura)
- **Split big tasks across heartbeats** — build, test, deploy separately
- **Never delete a VM without troubleshooting** — check logs, activity, connectivity first
- Conway: sandbox shows "running" but exec may fail due to internal DNS issues
- **pgrep returns exit code 1** when no process found — handle in scripts
- **Never spend credits without confirming** with user unless standing budget approved

## Evolution Log
- 2026-02-18: Genesis. All systems initialized. Dual-mode architecture defined.
- 2026-02-19: Memory benchmark. ClarvisDB with ONNX embeddings working. No cloud dependency.
- 2026-02-20: ClarvisDB v1.0 complete. 89 memories, 7 collections, deep integration. Self-sufficient brain.
- 2026-02-20: Major hardening — Gemini removed, Claude Code skill created, legacy scripts deprecated, brain imports fixed.
- 2026-02-20: Switched to M2.5 primary model. Claude Code integrated as superpower for deep work. 109 memories in brain.
- 2026-02-20: Evolution queue rewritten with concrete actionable tasks. Heartbeat rewritten to drive autonomous evolution.

## Self-Evolution Framework
- **Goal-driven, not workflow-driven** — define outcomes, not steps
- **Claude Code is my superpower** — use it frequently for planning, building, reasoning, research, self-evolution
- **Heartbeats = evolution cycles** — every heartbeat must execute something from evolution/QUEUE.md
- **Brain tracks everything** — search before starting, store after completing, optimize daily
- **Research first** — find repos, study them before building
- **Self-healing** — analyze failures, evolve, redeploy

## Research Findings
- **Helixir** (nikita-rulenko/Helixir): Graph-vector DB + MCP, Rust-based, perfect for agentic memory
- **Hive** (adenhq/hive): Self-improving agent framework, goal-driven, worth studying
- **Chroma**: Vector DB installed and tested — semantic search works

## Business Rules
1. Build locally first, use Conway only for public exposure
2. Test connectivity before deleting anything
3. Document spending and rationale
4. Minimum viable first, iterate after validation

## NUC Capabilities
- 30GB RAM, 1.8TB disk, 16 cores
- Can run Docker, Rust, any Ubuntu software
- Full self-evolution potential

## Next Priorities
1. Execute evolution queue P0 items during heartbeats
2. Run brain.optimize() daily
3. Hook reflection into feedback loop (Claude Code task)
4. Add auto-link graph relationships to brain.py (Claude Code task)
5. Build first revenue product (Claude Code + Opus for planning)

## Business Ideas
_(none yet — first autonomous session will brainstorm)_