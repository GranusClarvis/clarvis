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
- 2026-02-19: Memory benchmark. Semantic search (gemini-embedding-001) working. Chroma installed.

## Self-Evolution Framework
- **Goal-driven, not workflow-driven** — define outcomes, not steps
- **Research first** — find repos, study them before building
- **Heartbeat batching** — big tasks split, small tasks done together
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
1. First autonomous evolution cycle
2. First business ideation session (after crypto alert pivot)
3. Helixir integration research

## Business Ideas
_(none yet — first autonomous session will brainstorm)_