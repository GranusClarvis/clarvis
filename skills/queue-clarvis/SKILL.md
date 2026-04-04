---
name: queue-clarvis
description: "Summarize Clarvis evolution queue. Usage: /queue_clarvis. Returns counts, P0/P1 sections, and 5 most recent completed items with minimal token usage (runs a local script; no brain/context load)."
whenToUse: |
  When the user asks about the task queue, backlog, evolution progress, or what's
  next on the roadmap. Lightweight — runs a local script with no brain/context load.
metadata: {"clawdbot":{"emoji":"📋"}}
user-invocable: true
---

# /queue_clarvis — Queue Summary

When the user sends `/queue_clarvis`, run the local summarizer script and return its output.

## Command

```bash
python3 $CLARVIS_WORKSPACE/skills/queue-clarvis/scripts/queue_clarvis.py
```

## Notes
- Keep the reply concise.
- The script reads only `memory/evolution/QUEUE.md` and prints a compact summary.
