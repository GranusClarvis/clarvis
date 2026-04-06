# What Is Clarvis?

Clarvis is a dual-layer cognitive agent system that adds persistent memory, autonomous evolution, and self-awareness on top of existing AI agent harnesses.

## The Problem

Running an AI agent (OpenClaw, Hermes, plain Claude Code) gives you a stateless tool: it answers questions, executes tasks, and forgets everything between sessions. There is no continuity, no learning, no self-improvement.

## What Clarvis Adds

| Capability | Plain harness | Clarvis |
|---|---|---|
| **Persistent memory** | None (or basic chat history) | ChromaDB vector brain with 10 collections, graph edges, Hebbian learning. Memories survive across sessions and are searchable. |
| **Autonomous background work** | Only runs when you ask | Cron-driven subconscious layer: evolution, reflection, research, maintenance — runs on a schedule you control. |
| **Self-awareness** | None | Self-model tracking 7 capability domains, Phi (integrated information) metric, Performance Index across 8 dimensions. |
| **Calibrated confidence** | Model says "I think..." | Brier-scored predictions, per-domain confidence bands, calibration tracking over time. |
| **Episodic memory** | None | Episodes encoded after each task with context, outcome, and reasoning chain — used for future decision-making. |
| **Cognitive architecture** | Prompt in, response out | Global Workspace Theory (GWT) attention, working memory buffers, reasoning chains with meta-cognitive monitoring. |
| **Cost awareness** | You check your bill | Real-time cost tracking, budget alerts, model routing by task complexity to minimize spend. |
| **Evolution queue** | Manual task management | Priority queue with heartbeat-driven task selection, automatic archival, and progress tracking. |

## When to Use Clarvis vs Alternatives

**Use Clarvis when you want:**
- An agent that learns from its own experience and improves over time
- Autonomous background processing (research, reflection, maintenance)
- Persistent memory that survives across sessions and conversations
- Self-monitoring with quantitative metrics (PI, Phi, Brier score)
- A cognitive layer on top of any chat model (M2.5, Claude, Hermes)

**Use plain OpenClaw when you want:**
- A simple chat gateway to one or more LLM models
- No autonomous behavior, no background tasks
- Minimal setup, no Python dependencies
- Stateless operation (no brain, no cron)

**Use plain Claude Code when you want:**
- A one-shot coding agent for a specific task
- No persistent state between invocations
- Direct terminal interaction without a gateway

**Use Hermes when you want:**
- NousResearch's agent framework with tool-use focus
- Different model ecosystem (Hermes-compatible models)
- Clarvis can wrap Hermes too (hermes profile in installer)

## Architecture at a Glance

```
You (Telegram/Discord/CLI)
  |
  v
Conscious Layer (OpenClaw gateway + MiniMax M2.5)
  |-- Direct conversation
  |-- Reads daily digest from subconscious work
  |-- Spawns Claude Code for complex tasks
  |
Subconscious Layer (Claude Code Opus via system crontab)
  |-- Autonomous evolution (configurable: 4-12x/day)
  |-- Morning planning, evening assessment
  |-- Research ingestion, dream engine
  |-- Reflection pipeline, strategic audits
  |
ClarvisDB Brain (ChromaDB + ONNX, fully local)
  |-- 10 memory collections
  |-- Graph backend (SQLite)
  |-- Hebbian learning (connection strengthening)
  |-- Sub-300ms query latency
```

## Installation Profiles

Clarvis installs in layers — pick what fits your needs:

| Profile | What you get |
|---|---|
| **minimal** | CLI only. No brain, no services, no API keys. |
| **standalone** | CLI + brain (ChromaDB + ONNX). Recommended starting point. |
| **openclaw** | Standalone + OpenClaw gateway + chat channels. |
| **fullstack** | OpenClaw + cron schedule + systemd. Reference deployment. |
| **hermes** | Standalone + Hermes agent harness. |
| **local** | Standalone + Ollama local models. Zero API keys needed. |
| **docker** | Containerized dev/test setup. |

Start minimal, upgrade any time: `bash scripts/install.sh --profile <name>`

## Quick Start

```bash
# Install (interactive — picks profile, optional cron)
bash scripts/install.sh

# Verify
clarvis doctor

# Explore
clarvis welcome          # Full onboarding briefing
clarvis demo             # Self-contained demo
clarvis brain health     # Brain status
```

## Key Principle

Clarvis is designed so that **all data stays local**. The brain, episodic memory, reasoning chains, and metrics are stored on your machine. External API calls only happen when you configure them (OpenRouter for model access, Telegram for notifications). You control what runs and when through the cron schedule presets.
