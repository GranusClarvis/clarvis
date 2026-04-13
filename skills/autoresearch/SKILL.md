---
name: autoresearch
description: "Toggle automatic research task injection ON/OFF. Usage: /autoresearch, /autoresearch on, /autoresearch off. Controls whether research papers, discovery, and bridge inject tasks into QUEUE.md."
whenToUse: |
  When the user wants to enable or disable automatic research task replenishment.
  Controls research_to_queue.py, cron_research.sh discovery fallback, and
  monthly reflection bridge. Does not affect normal queue auto-fill (use
  /autoqueue for that).
metadata: {"clawdbot":{"emoji":"🔬"}}
user-invocable: true
---

# /autoresearch — Research Auto-Fill Toggle

When the user sends `/autoresearch`, run the script below and return the output.

## Command

```bash
python3 $CLARVIS_WORKSPACE/skills/autoresearch/scripts/autoresearch.py "$ARGS"
```

## What it controls

- **ON**: Research papers, discovery fallback, and monthly bridge can inject
  research tasks into QUEUE.md. Sub-paths:
  - `research_inject_from_papers` — research_to_queue.py inject
  - `research_discovery_fallback` — cron_research.sh generates topics when queue empty
  - `research_bridge_monthly` — monthly reflection injects paper findings
- **OFF**: All research injection stops. Normal queue auto-fill unaffected.

## Notes
- Independent from normal queue auto-fill (use `/autoqueue` for that)
- Master switch: turning ON enables all 3 sub-paths; turning OFF disables all 3
- Config stored in `data/research_config.json` (key: `research_auto_fill`)
