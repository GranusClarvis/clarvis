---
name: autoqueue
description: "Toggle automatic queue task injection ON/OFF. Usage: /autoqueue, /autoqueue on, /autoqueue off. Controls whether self-model, PI, meta-learning, obligations, and other systems auto-add tasks to QUEUE.md."
whenToUse: |
  When the user wants to enable or disable automatic task replenishment in the
  evolution queue. Does not affect research tasks (use /autoresearch for those)
  or user-directed tasks (manual, /spawn, CLI always work).
metadata: {"clawdbot":{"emoji":"🔄"}}
user-invocable: true
---

# /autoqueue — Queue Auto-Fill Toggle

When the user sends `/autoqueue`, run the script below and return the output.

## Command

```bash
python3 $CLARVIS_WORKSPACE/skills/autoqueue/scripts/autoqueue.py "$ARGS"
```

## What it controls

- **ON**: Self-model, PI benchmark, meta-learning, obligations, reasoning failures,
  episodic synthesis, LLM reviews, and other systems can auto-add tasks to QUEUE.md.
  `cron_evolution.sh` runs normally.
- **OFF**: All automatic injection stops. Existing queue tasks still execute.
  User-directed tasks (/spawn, CLI `clarvis queue add`) still work.
  Queue drains naturally. No state corruption.

## Notes
- Independent from research auto-fill (use `/autoresearch` for that)
- Turning back ON takes effect immediately on next heartbeat/cron cycle
- Config stored in `data/research_config.json` (key: `queue_auto_fill`)
