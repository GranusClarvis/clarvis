---
name: web-browse
description: "Browse the web — navigate, screenshot, extract text, fill forms, agent mode. Usage: /web-browse <command> <args>"
whenToUse: |
  When the user needs interactive web browsing — navigating pages, filling forms,
  taking screenshots, extracting text from rendered pages, or agent-mode web tasks.
  Prefer search skills for simple lookups; use this for interactive/visual tasks.
metadata: {"clawdbot":{"emoji":"🌐","requires":{"bins":["python3","chromium"]}}}
user-invocable: true
---

# /web-browse — Browser Automation

When the user sends `/web-browse <command>`, use Clarvis's browser modules to interact with web pages.

## What This Skill Does

Two browser engines are available, each with different strengths:

1. **ClarvisBrowser** (`clarvis_browser.py`) — Primary. Uses Agent-Browser (Rust, snapshot/refs) for fast, token-efficient browsing. Falls back to Playwright for uploads/JS eval. Best for multi-page navigation, data extraction, and general browsing.

2. **BrowserAgent** (`browser_agent.py`) — Single-session Playwright CDP. Best for auth-heavy flows (login, Twitter, Gmail) where cookies must persist across actions in one tab.

## Commands

### goto — Navigate to a URL
```bash
python3 /home/agent/.openclaw/workspace/scripts/clarvis_browser.py goto <url>
```

### screenshot — Capture a page screenshot
```bash
python3 /home/agent/.openclaw/workspace/scripts/clarvis_browser.py screenshot [url] [/tmp/screenshot.png]
# With element annotations:
python3 /home/agent/.openclaw/workspace/scripts/clarvis_browser.py screenshot <url> /tmp/s.png --annotate
```

### snapshot — Get page elements with clickable refs
```bash
python3 /home/agent/.openclaw/workspace/scripts/clarvis_browser.py snapshot
# Interactive mode:
python3 /home/agent/.openclaw/workspace/scripts/clarvis_browser.py snapshot -i
```
Returns elements like `@e1 [button] "Submit"` — use refs with click/fill commands.

### click — Click an element by ref
```bash
python3 /home/agent/.openclaw/workspace/scripts/clarvis_browser.py click @e2
```

### fill — Fill a form field by ref
```bash
python3 /home/agent/.openclaw/workspace/scripts/clarvis_browser.py fill @e3 "user@example.com"
```

### text — Extract text from an element
```bash
python3 /home/agent/.openclaw/workspace/scripts/clarvis_browser.py text @e1
```

### markdown — Extract page content as clean markdown
```bash
python3 /home/agent/.openclaw/workspace/scripts/clarvis_browser.py markdown [url]
```

### search — Web search via browser
```bash
python3 /home/agent/.openclaw/workspace/scripts/clarvis_browser.py search "query terms"
```

### agent — LLM-driven autonomous browsing
```bash
python3 /home/agent/.openclaw/workspace/scripts/clarvis_browser.py agent "Find the latest Python release date"
# Or with BrowserAgent for auth-heavy tasks:
python3 /home/agent/.openclaw/workspace/scripts/browser_agent.py agent "Log in and check notifications"
```

### upload — Upload a file
```bash
python3 /home/agent/.openclaw/workspace/scripts/browser_agent.py upload /path/to/file.png [css-selector]
```

### status — Check browser connection
```bash
python3 /home/agent/.openclaw/workspace/scripts/clarvis_browser.py status
```

### Session management
```bash
python3 /home/agent/.openclaw/workspace/scripts/browser_agent.py save-session [path]
python3 /home/agent/.openclaw/workspace/scripts/browser_agent.py session-info [path]
# Auto-save session on exit:
python3 /home/agent/.openclaw/workspace/scripts/browser_agent.py --persist navigate <url>
```

## Execution Steps

1. Parse the command after `/web-browse` — extract subcommand and arguments
2. Choose the right module:
   - **General browsing, extraction, screenshots**: use `clarvis_browser.py`
   - **Login flows, auth-heavy tasks, file uploads**: use `browser_agent.py` with `--persist`
3. Run the command and present results to the user
4. For screenshots: read the image file and show it to the user

## Rules

- **Always use full paths**: `python3 /home/agent/.openclaw/workspace/scripts/clarvis_browser.py`
- **CDP port is 18800** — Chromium must be running (snap-managed)
- **Session cookies**: stored in `data/browser_sessions/default_session.json`
- **For login flows**: use `BrowserAgent` directly (single tab, cookies persist within session)
- **ClarvisBrowser** opens new tabs per call — don't use for multi-step auth
- **Google sessions expire** — re-login needed periodically
- **Agent mode** uses Gemini Flash via OpenRouter (costs ~$0.01-0.05 per task)
- **go_back()** times out over CDP — use goto with the previous URL instead
- **Twitter** rate-limits headless browsers after rapid attempts

## Python Library Usage

```python
# General browsing
from clarvis_browser import ClarvisBrowser
async with ClarvisBrowser() as cb:
    await cb.goto("https://example.com")
    snap = await cb.snapshot()       # Elements with @e1, @e2... refs
    await cb.click("@e2")
    text = await cb.get_text("@e1")
    await cb.screenshot("/tmp/s.png")

# Auth-heavy flows (single persistent session)
from browser_agent import BrowserAgent
async with BrowserAgent(persist_session=True) as ba:
    await ba.goto("https://twitter.com")
    await ba.handle_modal()          # Dismiss cookie banners
    await ba.fill('input[name="text"]', "username")
    await ba.click_by_text("Next")
```

## Example

User: `/web-browse screenshot https://github.com/trending`

Response: "Taking a screenshot of GitHub Trending..."

```bash
python3 /home/agent/.openclaw/workspace/scripts/clarvis_browser.py screenshot https://github.com/trending /tmp/github_trending.png
```

Then show the screenshot to the user.
