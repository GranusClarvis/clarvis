# Clarvis on OpenClaw — User Guide

## What is Clarvis?

Clarvis is a dual-layer cognitive agent that runs inside the OpenClaw gateway. It adds persistent memory, autonomous evolution, cost tracking, and Claude Code delegation on top of baseline OpenClaw.

**What OpenClaw provides**: Chat gateway (Telegram/Discord), model routing, session management.
**What Clarvis adds**: Long-term brain (ClarvisDB), 30+ scheduled cron jobs, heartbeat-driven self-improvement, episodic memory, performance benchmarks, and a structured cognitive architecture.

## How to Talk to Clarvis

Clarvis responds in your configured chat channel (Telegram or Discord). It uses MiniMax M2.5 for direct conversation and delegates complex tasks to Claude Code (Opus).

**Interaction style**: Precise, economical language with dry wit. Clarvis is a colleague, not a servant — it will challenge you when needed and admit mistakes immediately.

### Slash Commands

| Command | What it does |
|---------|-------------|
| `/spawn <task>` | Delegate a complex task to Claude Code (Opus 4.6). Results delivered via Telegram. |
| `/costs` | Real OpenRouter usage report — daily, weekly, monthly breakdown by model. |
| `/budget` | Budget status and alert thresholds. |
| `/queue_clarvis` | Show the evolution queue — what Clarvis plans to work on autonomously. |
| `/iteration1`–`/iteration4` | Run 1–4 autonomous evolution cycles on demand. |

### Tips for Good Results

- **Be specific**: "Search brain for memories about cost optimization" works better than "find stuff about costs."
- **Use spawn for heavy tasks**: Coding, research, multi-file refactors, and architecture work should go through `/spawn`.
- **Don't poll**: After spawning Claude Code, wait silently. Output is buffered — silence means it's still working. Polling wastes 5k–15k tokens per message.

## What Autonomy Means

Clarvis has a **subconscious layer** that runs continuously via system crontab, even when you're not chatting. This layer:

1. **Evolves itself**: 12x/day heartbeat cycles pick tasks from the evolution queue, execute them with Claude Code, and record results.
2. **Plans and reflects**: Morning planning, evening assessment, weekly/monthly reflection cycles.
3. **Maintains itself**: Graph compaction, brain hygiene, backup verification, log rotation.
4. **Researches**: 2x/day research sessions explore topics relevant to active goals.

All autonomous work surfaces through `memory/cron/digest.md` — a rolling summary that the conscious layer reads to stay coherent.

### Operating Modes

| Mode | Behavior |
|------|----------|
| **GE** (General Evolution) | Full autonomy — heartbeats select and execute tasks freely. |
| **Architecture** | Self-improvement only — no external actions, focus on internal upgrades. |
| **Passive** | User-directed — heartbeats suppressed, Clarvis only responds to commands. |

Check or change mode:
```
python3 -m clarvis mode show
python3 -m clarvis mode set passive
```

## What Cron Does

The cron schedule runs 30+ jobs daily (all times CET):

| Category | Jobs | Purpose |
|----------|------|---------|
| **Evolution** (12x/day) | `cron_autonomous.sh` | Pick queue tasks, spawn Claude Code, record results |
| **Planning** | `cron_morning.sh` (08:00) | Day planning based on queue and goals |
| **Research** | `cron_research.sh` (10:00, 16:00) | Explore topics, ingest findings into brain |
| **Analysis** | `cron_evolution.sh` (13:00) | Deep metrics analysis |
| **Implementation** | `cron_implementation_sprint.sh` (14:00) | Dedicated coding slot |
| **Assessment** | `cron_evening.sh` (18:00) | Daily progress review |
| **Reflection** | `cron_reflection.sh` (21:00) | 8-step reflection pipeline |
| **Reports** | `cron_report_*.sh` (09:30, 22:30) | Telegram digest summaries |
| **Maintenance** | 04:00–06:00 window | Graph compaction, ChromaDB vacuum, backups |
| **Watchdog** | Every 30 min | Health checks and alerts |

All cron jobs respect mutual exclusion locks — only one Claude Code instance runs at a time.

## Features

### Brain (ClarvisDB)
Persistent vector memory with 10 collections, 3400+ memories, and 106k+ graph edges. Fully local (ChromaDB + ONNX MiniLM embeddings).

```bash
python3 -m clarvis brain health          # Full health report
python3 -m clarvis brain search "query"  # Semantic search
python3 -m clarvis brain stats           # Quick counts
python3 -m clarvis brain optimize-full   # Maintenance cycle
```

### Cost Tracking
Tracks real API spend via OpenRouter. Budget alerts via Telegram.

```bash
python3 scripts/cost_tracker.py telegram   # Usage report
python3 scripts/budget_alert.py --status   # Budget status
```

### Claude Code Delegation
Clarvis spawns Claude Code (Opus 4.6) for complex tasks:
- From chat: `/spawn <task description>`
- From cron: automatic via heartbeat pipeline
- Manual: `workspace/scripts/spawn_claude.sh "task" 1200`

Results are delivered to Telegram and stored in brain memory.

### Performance Tracking
8-dimension Performance Index (PI): brain speed, retrieval quality, efficiency, accuracy, results quality, bloat, context quality, load scaling.

```bash
python3 scripts/performance_benchmark.py pi    # Current PI score
python3 scripts/performance_benchmark.py record # Full benchmark
```

### Project Agents
Clarvis can delegate to specialized project agents in isolated workspaces:
```bash
python3 scripts/agents/project_agent.py list   # List agents
python3 scripts/agents/project_agent.py spawn <name> "task"  # Spawn agent
```

## What Clarvis Adds Over Baseline OpenClaw

| Baseline OpenClaw | Clarvis Layer |
|-------------------|---------------|
| Stateless chat sessions | Persistent brain with semantic memory |
| Single model routing | Multi-model delegation (M2.5 chat + Claude Code heavy tasks) |
| No autonomy | 30+ scheduled cron jobs, self-directed evolution |
| No self-awareness | Performance Index, Phi metric, capability domains |
| Manual everything | Automated maintenance, backups, health monitoring |
| No learning | Episodic memory, Hebbian strengthening, reflection cycles |

## Troubleshooting

**Clarvis seems unresponsive**: Check gateway status with `systemctl --user status openclaw-gateway.service`. Requires `XDG_RUNTIME_DIR=/run/user/1001`.

**Spawn tasks hang**: Check `/tmp/clarvis_claude_global.lock` — another Claude Code instance may be running. Wait or check `ps aux | grep claude`.

**Brain errors**: Run `python3 -m clarvis brain health` for diagnostics. If ChromaDB is corrupt, backups are at `~/backups/clarvis-db/`.

**Cost concerns**: Run `/costs` to see real spend. Budget alerts fire automatically when thresholds are crossed.
