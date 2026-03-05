# Skill Inventory Audit — 2026-03-05

18 skills total. All have `SKILL.md` documentation.

## Inventory

| Skill | SKILL.md | \_meta.json | Type | Referenced By | Status |
|---|---|---|---|---|---|
| `brave-search` | Yes | Yes (v1.0.1) | Published | Topic 1 (all skills) | **Active** — Brave Search API web search |
| `clarvis-brain` | Yes | No | Internal | Topic 3, openclaw.json | **Active** — Core memory system |
| `clarvis-cognition` | Yes | No | Internal | Topics 3/5/6, openclaw.json | **Active** — Cognitive state queries |
| `clarvis-model-router` | Yes | No | Internal | Topic 1 (all skills) | **Active** — Task→model routing |
| `claude-code` | Yes | No | Internal | Topics 2/6, AGENTS.md | **Active** — Claude Code delegation |
| `ddg-web-search` | Yes | Yes (v1.0.0) | Published | Topic 1 (all skills) | **Active** — DuckDuckGo search (API-free) |
| `gog` | Yes | Yes (v1.0.0) | Published | Topic 1 (all skills) | **Stale** — Google Workspace CLI (no active cron/agent use) |
| `himalaya` | Yes | Yes (v1.0.0) | Published | Topic 1 (all skills) | **Stale** — IMAP/SMTP email (no active cron/agent use) |
| `iteration` | Yes | No | Internal | AGENTS.md (/iteration1-4) | **Active** — Fast-track evolution cycles |
| `mcporter` | Yes | Yes (v1.0.0) | Published | Topic 1 (all skills) | **Stale** — MCP server management (no active use) |
| `nano-pdf` | Yes | Yes (v1.0.0) | Published | Topic 1 (all skills) | **Stale** — PDF editing (no active cron/agent use) |
| `notion` | Yes | Yes (v1.0.0) | Published | Topic 1 (all skills) | **Stale** — Notion API (no active cron/agent use) |
| `project-agent` | Yes | No | Internal | project_agent.py, AGENTS.md | **Active** — Multi-project agent management |
| `queue-clarvis` | Yes | No | Internal | AGENTS.md (/queue_clarvis) | **Active** — Evolution queue summary |
| `session-logs` | Yes | Yes (v1.0.0) | Published | Topics 5/6, openclaw.json | **Active** — Conversation history search |
| `spawn-claude` | Yes | No | Internal | Topics 2/6, AGENTS.md | **Active** — Claude Code spawning |
| `summarize` | Yes | Yes (v1.0.0) | Published | Topic 1 (all skills) | **Active** — URL/PDF/video summarization |
| `tavily-search` | Yes | Yes (v1.0.0) | Published | Topic 1 (all skills) | **Active** — AI-optimized web search |

## Summary

- **18 skills total**, all documented with SKILL.md
- **10 Published** (have `_meta.json`, published to ClawhubRegistry)
- **8 Internal** (Clarvis cognitive/orchestration, no registry)
- **13 Active** (referenced by agents, cron, or OpenClaw topics)
- **5 Stale** — `gog`, `himalaya`, `mcporter`, `nano-pdf`, `notion` (available in Topic 1 but no active cron/agent callers)
- **0 Undocumented** — all skills have SKILL.md
- **0 Broken** — no stale tool references detected

## Stale Skills Detail

These 5 published skills are available but have no active callers beyond Topic 1 (general chat):

| Skill | Last Relevant Use | Recommendation |
|---|---|---|
| `gog` | N/A (Google Workspace) | Keep — useful for future Google integration |
| `himalaya` | N/A (email CLI) | Keep — useful for email automation tasks |
| `mcporter` | N/A (MCP management) | Keep — needed if MCP servers are added |
| `nano-pdf` | N/A (PDF editing) | Keep — occasional manual use |
| `notion` | N/A (Notion API) | Keep — useful if Notion workspace is created |

No skills recommended for removal. All serve documented purposes.
