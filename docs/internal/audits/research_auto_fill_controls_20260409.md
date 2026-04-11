# Research Auto-Fill Controls — Implementation Report (2026-04-09)

## Problem

For 2+ weeks the operator has explicitly wanted research replenishment OFF, yet research tasks could still be surfaced through multiple uncoordinated paths. The prior control was a single ephemeral environment variable (`RESEARCH_AUTO_REPLENISH`) that only gated one of several injection paths.

## Solution: Durable Config File

**Config file:** `data/research_config.json`
**Module:** `clarvis/research_config.py`

### Control Keys

| Key | Controls | Default |
|-----|----------|---------|
| `research_auto_fill` | **Master switch** — gates ALL sub-keys | `false` |
| `research_discovery_fallback` | `cron_research.sh` auto-discovery when queue empty | `false` |
| `research_inject_from_papers` | `research_to_queue.py inject` command | `false` |
| `research_bridge_monthly` | `cron_reflection.sh` monthly bridge (1st of month) | `false` |

The master switch (`research_auto_fill`) gates everything: even if a sub-key is `true`, it has no effect when the master is `false`.

### CLI

```bash
# Check status
python3 -m clarvis.research_config status

# Enable everything
python3 -m clarvis.research_config enable --who operator --reason "research wanted again"

# Disable everything
python3 -m clarvis.research_config disable --who operator --reason "no more research"

# Enable/disable a single path
python3 -m clarvis.research_config enable --path research_discovery_fallback
python3 -m clarvis.research_config disable --path research_bridge_monthly
```

### Python API

```python
from clarvis.research_config import is_enabled, enable, disable, status

if is_enabled("research_auto_fill"):
    # research is allowed
    pass

enable("research_auto_fill", reason="operator said so", who="operator")
disable("research_auto_fill")
```

## Injection Paths Gated (5 total)

### 1. cron_research.sh — Discovery Fallback (lines 57-75)
- **What:** When no research tasks in QUEUE.md, auto-discovers new topics via Claude Code
- **Gate:** Reads `research_discovery_fallback` from config; falls back to `RESEARCH_AUTO_REPLENISH` env var for backward compat
- **Runs:** 2x/day (10:00, 16:00)

### 2. research_to_queue.py — Paper-to-Queue Inject (line 551)
- **What:** Scans ingested research papers, extracts actionable proposals, injects into QUEUE.md
- **Gate:** Reads `research_inject_from_papers` before injecting; prints message and returns if OFF

### 3. cron_reflection.sh — Monthly Research Bridge (line 108-112)
- **What:** On 1st of month, runs `research_to_queue.py inject --max 3`
- **Gate:** Reads `research_bridge_monthly` before executing; skips with log message if OFF

### 4. clarvis/queue/writer.py — Research Source Gate (line 268)
- **What:** Blocks any `add_tasks()` call with source in `{research_bridge, research_discovery, research}` when master switch is OFF
- **Gate:** Catches any code path that bypasses the script-level gates

### 5. clarvis/runtime/mode.py — mode_policies() (line 176)
- **What:** `allow_research_bursts` policy now reflects durable config, not just mode
- **Gate:** Even in `ge` mode, research bursts are OFF if config says so

## Current State

- **All research injection: OFF** (set 2026-04-09)
- QUEUE.md has no pending research tasks (one completed item in Research Sessions section)
- The config file persists across reboots, cron runs, and mode switches

## How to Re-Enable Research

When the operator explicitly wants research back:

```bash
python3 -m clarvis.research_config enable --who operator --reason "research wanted again"
```

This enables all four paths. To enable only specific paths, use `--path`:

```bash
python3 -m clarvis.research_config enable --path research_discovery_fallback --who operator
```

## Tests

`tests/test_research_config.py` — 11 tests covering:
- Default OFF state
- Master switch gating sub-keys
- Enable/disable master and individual keys
- Missing config file defaults to OFF
- Queue writer blocks research-source injections when OFF
- Non-research sources are NOT affected

## Files Changed

| File | Change |
|------|--------|
| `data/research_config.json` | NEW — durable config (all OFF) |
| `clarvis/research_config.py` | NEW — config reader/writer + CLI |
| `scripts/cron/cron_research.sh` | Reads config before discovery fallback |
| `scripts/evolution/research_to_queue.py` | Reads config before inject |
| `scripts/cron/cron_reflection.sh` | Reads config before monthly bridge |
| `clarvis/queue/writer.py` | Blocks research-source injections when OFF |
| `clarvis/runtime/mode.py` | `allow_research_bursts` reflects config |
| `tests/test_research_config.py` | NEW — 11 tests |
