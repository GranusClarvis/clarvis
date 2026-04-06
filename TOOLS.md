# Clarvis — Available Tools

## Browser Automation
- `scripts/browser_agent.py` — Playwright-based browser automation over CDP
- Connects to headless Chromium on `127.0.0.1:18800` (managed by `~/.openclaw/browser/start-chromium.sh`)
- **Backend**: Playwright async API via `connect_over_cdp()` — reliable, no WebSocket instability
- **Browser-Use 0.12**: Installed for LLM-driven agent mode (requires Ollama or OpenRouter)
- **12 integration tests**: `scripts/test_browser_integration.py` — all passing

### CLI Usage
```bash
# Activate venv first
source ~/.openclaw/venvs/chroma/bin/activate

python3 scripts/browser_agent.py status                          # Check connectivity
python3 scripts/browser_agent.py navigate https://example.com    # Navigate
python3 scripts/browser_agent.py extract https://example.com     # Extract text
python3 scripts/browser_agent.py markdown https://example.com    # Extract as markdown
python3 scripts/browser_agent.py screenshot https://example.com  # Screenshot
python3 scripts/browser_agent.py search "query here"             # Web search
python3 scripts/browser_agent.py browse https://example.com      # All-in-one
python3 scripts/browser_agent.py eval "document.title"           # Run JS
python3 scripts/browser_agent.py agent "Find latest Python version"  # LLM agent
```

### Library Usage
```python
from browser_agent import BrowserAgent, store_browse_result

async with BrowserAgent() as ba:
    result = await ba.browse("https://example.com", take_screenshot=True)
    text = await ba.extract_text()
    md = await ba.extract_markdown()
    store_browse_result(result)  # Save to ClarvisDB
```

### From spawn_claude.sh
```bash
workspace/scripts/agents/spawn_claude.sh "
source ~/.openclaw/venvs/chroma/bin/activate
python3 workspace/scripts/browser_agent.py browse https://target-url.com
" 600
```

### Architecture
```
start-chromium.sh  →  Chromium (headless, CDP port 18800)
                          ↑
browser_agent.py   →  Playwright (connect_over_cdp)
                          ↑
brain.py           ←  store_browse_result() → ClarvisDB
```

### Environment Variables
| Variable | Default | Purpose |
|----------|---------|---------|
| `CLARVIS_CDP_PORT` | `18800` | Chromium CDP port |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Optional: Ollama API (not required for agent mode) |
| `CLARVIS_OLLAMA_MODEL` | `qwen3-vl:4b` | Optional: Vision model (fallback only) |
| `OPENROUTER_API_KEY` | (none) | Primary LLM for agent mode (Gemini 2.5 Flash) |

## Architecture: Hybrid Autonomy

```
                    ┌─────────────────────────┐
                    │   Gemini 2.5 Flash      │
                    │   (OpenRouter)          │
                    │   → Agent reasoning     │
                    └───────────┬─────────────┘
                                │
                                ▼
┌─────────────┐    ┌─────────────────────────┐    ┌──────────────┐
│  Clarvis    │───▶│  browser_agent.py       │───▶│  Chromium    │
│  (spawn)    │    │  (Browser-Use + Play)   │    │  CDP :18800  │
└─────────────┘    └─────────────────────────┘    └──────────────┘
                                │
                                ▼ (optional)
                    ┌─────────────────────────┐
                    │  Ollama + Qwen3-VL 4B   │
                    │  → Local vision (zero   │
                    │    external deps)       │
                    └─────────────────────────┘
```

**Operating Modes:**
- **Default**: Agent mode uses OpenRouter (Gemini 2.5 Flash) - fast, cheap, browser-optimized
- **Zero-external**: Start Ollama, use Qwen3-VL for purely local vision
- **Hybrid**: Claude spawns for complex reasoning + local browser for execution

**Optimization:** Clarvis can evolve this by editing `scripts/browser_agent.py` to tweak prompts, add stealth features, optimize timeouts, or add new capabilities.

## ClarvisEyes — Visual Perception
- `scripts/clarvis_eyes.py` — CAPTCHA/visual challenge solver for web automation
- Supports: Image text recognition, reCAPTCHA v2, hCaptcha
- **Current**: Uses 2captcha.com external service
- **Long-term**: Replace with local vision (Ollama + Qwen3-VL)
- Usage:
  ```python
  from clarvis_eyes import ClarvisEyes, ChallengeType
  eyes = ClarvisEyes()  # Uses CLARVIS_EYES_API_KEY env var
  result = eyes.solve("path/to/image.png", ChallengeType.IMAGE_TEXT)
  print(result.solution)
  ```
- Setup: Set `CLARVIS_EYES_API_KEY` environment variable
