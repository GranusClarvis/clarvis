# Skill Inventory Audit — 2026-03-10

Supersedes 2026-03-05 audit. Deeper inspection of tool binaries, API keys, and node_modules.

## Summary

- **Total skills:** 19 (includes `web-browse`, previously miscounted as 18)
- **With SKILL.md:** 19/19 (100%)
- **With _meta.json (ClawhHub origin):** 10/19
- **In gateway config (openclaw.json):** 5/19
- **Tool binary/deps available:** 12/19
- **Broken/missing deps:** 7/19

## Inventory

| # | Skill | SKILL.md | Type | Binary/Deps | Gateway | Status | Issue |
|---|-------|----------|------|-------------|---------|--------|-------|
| 1 | `brave-search` | Yes | Published | **BROKEN** | No | **Stale** | `node_modules/` missing, no `BRAVE_API_KEY` |
| 2 | `clarvis-brain` | Yes | Internal | OK | Yes (T3) | **Active** | Core memory system |
| 3 | `clarvis-cognition` | Yes | Internal | OK | Yes (T3/5/6) | **Active** | Cognitive state queries |
| 4 | `clarvis-model-router` | Yes | Internal | N/A (prompt) | No | **Active** | Prompt-only routing logic |
| 5 | `claude-code` | Yes | Internal | OK | Yes (T2/6) | **Active** | Core delegation |
| 6 | `ddg-web-search` | Yes | Published | OK | No | **Active** | Uses built-in `web_fetch`, no deps |
| 7 | `gog` | Yes | Published | **MISSING** | No | **Stale** | `gog` binary not installed, no OAuth |
| 8 | `himalaya` | Yes | Published | **MISSING** | No | **Stale** | `himalaya` binary not installed |
| 9 | `iteration` | Yes | Internal | OK | No | **Active** | Uses cron_autonomous.sh |
| 10 | `mcporter` | Yes | Published | OK | No | **Active** | Conway access via SOUL.md |
| 11 | `nano-pdf` | Yes | Published | **MISSING** | No | **Stale** | `nano-pdf` binary not installed |
| 12 | `notion` | Yes | Published | curl OK | No | **Stale** | No `NOTION_TOKEN` configured |
| 13 | `project-agent` | Yes | Internal | OK | No | **Active** | Fully wired, agents running |
| 14 | `queue-clarvis` | Yes | Internal | OK | No | **Active** | Local script, in AGENTS.md |
| 15 | `session-logs` | Yes | Published | OK | Yes (T5/6) | **Active** | jq/rg available |
| 16 | `spawn-claude` | Yes | Internal | OK | Yes (T2/6) | **Active** | Core spawning |
| 17 | `summarize` | Yes | Published | **MISSING** | No | **Stale** | `summarize` CLI not installed |
| 18 | `tavily-search` | Yes | Published | **BROKEN** | No | **Stale** | `node_modules/` missing, no `TAVILY_API_KEY` |
| 19 | `web-browse` | Yes | Internal | OK | No | **Active** | agent-browser + clarvis_browser.py |

## Classification

### Active (12)
clarvis-brain, clarvis-cognition, clarvis-model-router, claude-code, ddg-web-search, iteration, mcporter, project-agent, queue-clarvis, session-logs, spawn-claude, web-browse

### Stale (7)
| Skill | Problem | Fix |
|-------|---------|-----|
| `brave-search` | No `node_modules/`, no API key | `cd skills/brave-search && npm install` + set `BRAVE_API_KEY` |
| `gog` | Binary not installed | Install `gog` CLI + configure Google OAuth |
| `himalaya` | Binary not installed | Install `himalaya` CLI + configure IMAP/SMTP |
| `nano-pdf` | Binary not installed | `pip install nano-pdf` |
| `notion` | No API token | Set `NOTION_TOKEN` in environment |
| `summarize` | CLI not installed | Install `summarize` CLI (brew/pip) + set API keys |
| `tavily-search` | No `node_modules/`, no API key | `cd skills/tavily-search && npm install` + set `TAVILY_API_KEY` |

## Gateway Wiring (openclaw.json)

Only 5/19 skills explicitly routed via topic channels:

| Topic | Skills |
|-------|--------|
| Topic 2 (Claude Code) | spawn-claude, claude-code |
| Topic 3 (Brain) | clarvis-brain, clarvis-cognition |
| Topic 5 (Reports) | session-logs, clarvis-cognition |
| Topic 6 (Debug) | spawn-claude, claude-code, clarvis-cognition, session-logs |

The remaining 14 skills are available via SKILL.md prompt injection only (loaded into agent context when skill is in the agent's skill list).

## ClawhHub vs Internal

- **10 Published** (ClawhHub `_meta.json`): brave-search, ddg-web-search, gog, himalaya, mcporter, nano-pdf, notion, session-logs, summarize, tavily-search
- **9 Internal** (locally created): clarvis-brain, clarvis-cognition, clarvis-model-router, claude-code, iteration, project-agent, queue-clarvis, spawn-claude, web-browse

## Recommendations

1. **Fix CLAUDE.md count** — says "15 OpenClaw skills" but actual is 19
2. **Token savings** — 7 stale SKILL.md files load into agent context unnecessarily; consider disabling stale skills from agent skill lists until deps are installed
3. **Search consolidation** — 3 web search skills (brave, ddg, tavily) but only ddg works; either install deps for brave/tavily or remove them
4. **Wire more active skills** — only 5/19 in gateway topic routing; iteration, project-agent, queue-clarvis, web-browse, mcporter could benefit from topic routing
