# Browser Automation Tools Research (2026-02-28)

## Executive Summary

Researched 8 browser automation tools for Clarvis integration. Three are recommended for action.

## Priority Recommendations

### 1. Agent-Browser (Vercel Labs) — INSTALL NOW
- **What**: CLI browser tool with Rust performance, 93% context reduction via accessibility tree snapshots
- **Why**: When Claude Code runs cron/heartbeat tasks, it can call `agent-browser --cdp 18800 snapshot` directly — zero additional LLM cost (no Gemini Flash needed)
- **Integration**: `npm install -g agent-browser && agent-browser connect 18800`. Zero code changes to existing scripts. Complementary to browser-use.
- **Key metric**: 5.7x less tokens per browser operation vs browser-use
- **Stars**: 16.6k | **License**: Apache 2.0 | **Cost**: Free

### 2. Browser-Use Upgrade — UPDATE EXISTING
- **What**: Already on v0.12 (current). Recent patches add CAPTCHA solver watchdog, message compaction, planning system, action loop detection
- **Why**: Free improvements, already integrated
- **Action**: `pip install --upgrade browser-use`
- **Stars**: 79.2k | **License**: MIT | **Cost**: Free

### 3. Browserbase — OPTIONAL CLOUD BACKEND
- **What**: Cloud browser-as-a-service with CAPTCHA solving, residential proxies, stealth fingerprinting
- **Why**: Solves the DuckDuckGo/CAPTCHA problem. 15-20 line code change in `browser_agent.py` to add as optional backend
- **Integration**: Add `CLARVIS_BROWSER_BACKEND=local|browserbase` env var, use `cdp_url=session.connect_url` for Browserbase sessions
- **Pricing**: $20/mo Developer (100 browser-hours), $99/mo Startup (500 hours)
- **Risk**: Vendor lock-in for anti-detection features, ~50% reliability in benchmarks, data passes through cloud
- **License**: Proprietary SaaS (SDK is open source)

## Not Recommended

### Nanobrowser — SKIP (architecture mismatch)
- Chrome extension only, no headless mode, no CLI/API
- Built on browser-use (which we already use directly)
- **Steal this**: Planner/Navigator/Validator multi-agent pattern — implement in Python on browser-use

### Stagehand — SKIP (TypeScript, coupled to Browserbase)
- **Steal this**: Self-healing cache pattern (cache action sequences, replay until they fail, then re-engage LLM). Could save significant cost on recurring browser tasks.

### Liminal — IRRELEVANT
- Enterprise AI governance SaaS, not browser automation

### Skyvern — MONITOR ONLY
- Vision-based browser agent, strong on forms (85.85% WebVoyager)
- AGPL-3.0 license (copyleft concern)
- Good for: canvas-heavy sites, image-based UIs where DOM is unreliable

### BrowserOS — SKIP (too heavy)
- Full Chromium fork, massive dependency

## Comparison Matrix

| Tool | Stars | License | Self-Host | LLM Cost | Integration | Anti-Bot |
|------|-------|---------|-----------|----------|-------------|----------|
| browser-use | 79.2k | MIT | Yes | ~$0.02-0.08/task | Already done | No |
| Agent Browser | 16.6k | Apache 2.0 | Yes | $0 (uses Claude) | 5 min install | No |
| Browserbase | - | Proprietary | No | Same | 15-20 lines | Yes |
| Stagehand | 21.3k | MIT | Partial | ~$0.01-0.05/task | High | Via Browserbase |
| Nanobrowser | 12.3k | Apache 2.0 | No (extension) | User pays | N/A (no headless) | No |
| Skyvern | 20.6k | AGPL-3.0 | Yes | ~$0.02-0.08/task | Medium | No |

## Architectural Ideas to Steal

1. **Agent-Browser's accessibility tree snapshots** — Playwright's `page.accessibility.snapshot()` gives semantic page representation. Could add as alternative to DOM distillation in browser-use.

2. **Stagehand's self-healing cache** — Hash (URL pattern + task), record action sequence on first run, replay deterministically. Fall back to LLM on failure. Perfect for recurring research scraping.

3. **Nanobrowser's multi-agent pattern** — Planner (heavy model) decomposes task, Navigator (cheap model) executes, Validator (medium model) cross-checks results. Could implement in ~200-300 lines of Python atop browser-use.

## Implementation Plan

### Phase 1 (This Week)
- [ ] Install agent-browser: `npm install -g agent-browser && agent-browser connect 18800`
- [ ] Test: `agent-browser --cdp 18800 snapshot` on a few pages
- [ ] Upgrade browser-use: `pip install --upgrade browser-use`

### Phase 2 (Next Week)
- [ ] Add agent-browser as tool option in cron heartbeats (Claude Code uses CLI directly)
- [ ] Evaluate Browserbase free tier for CAPTCHA-heavy tasks

### Phase 3 (When Needed)
- [ ] Implement self-healing cache pattern for recurring browser tasks
- [ ] Consider Browserbase Developer plan ($20/mo) if CAPTCHA solving proves valuable
