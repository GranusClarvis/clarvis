# Research: Open-Source Agent Browsers for Clarvis Autonomy

**Date:** 2026-02-26
**Purpose:** Evaluate open-source browser agent solutions for Clarvis's web browsing autonomy

---

## Current State Assessment

### What Clarvis Already Has

| Capability | Status | Technology |
|---|---|---|
| Headless browser (Playwright) | **Installed but NOT enabled** | Playwright 1.58.2 + Chromium 1208 (both installed via OpenClaw) |
| Browser tool API (30+ endpoints) | **Available, needs config** | OpenClaw built-in: navigate, screenshot, snapshot, act, cookies, etc. |
| CAPTCHA solving | Available | 2captcha.com API (`clarvis_eyes.py`) — external dependency |
| Web search (no JS rendering) | Active | Brave API / DDG Lite / Tavily |
| LLM vision (image analysis) | Active via routing | Kimi K2.5 via OpenRouter — external dependency |

**Key finding:** The OpenClaw gateway already has a full Playwright-backed browser tool with 30+ API endpoints (navigate, screenshot, act, click, type, scroll, etc.). It just needs `"browser": {"enabled": true}` in `openclaw.json` and a gateway restart. This is the **foundation** to build on.

---

## Top 10 Open-Source Browser Agent Projects

### Tier 1: Best Fit for Clarvis

#### 1. Browser-Use
- **URL:** https://github.com/browser-use/browser-use
- **Stars:** 78,000+
- **Language:** Python
- **License:** MIT
- **What it does:** Makes websites accessible to AI agents. Combines LLM reasoning with Playwright browser control. Agent sees page DOM + screenshots, decides actions, executes them.
- **Key strengths:**
  - Pure Python, Playwright-based (same as OpenClaw's browser)
  - Works with ANY LLM via LangChain (OpenAI, Anthropic, **Ollama local models**)
  - 89.1% success rate on WebVoyager benchmark
  - Multi-step workflow automation
  - Visual + DOM understanding (dual perception)
- **Self-hosted potential:** **Excellent** — works with Ollama + local vision models (Qwen2.5-VL, Llama 3.2 Vision)
- **Clarvis fit:** **Best candidate.** Python, Playwright, works with local LLMs. Can leverage OpenClaw's existing Chromium.

#### 2. Skyvern
- **URL:** https://github.com/Skyvern-AI/skyvern
- **Stars:** 18,000+
- **Language:** Python
- **License:** AGPL-3.0
- **What it does:** Visual-first browser automation. Takes screenshots, uses Vision-LLM to find elements, clicks them. No DOM parsing needed.
- **Key strengths:**
  - Works on never-before-seen websites
  - Resistant to layout changes (no XPath/CSS selectors)
  - Self-writes Playwright code (2.7x cheaper, 2.3x faster)
  - Built-in workflow recording and replay
- **Self-hosted potential:** **Good** — needs a vision-capable LLM but can use local models
- **Clarvis fit:** **Strong candidate.** Visual reasoning approach aligns with ClarvisEyes vision. AGPL license is more restrictive.

#### 3. Crawl4AI
- **URL:** https://github.com/unclecode/crawl4ai
- **Stars:** 58,000+
- **Language:** Python
- **License:** Apache 2.0
- **What it does:** LLM-friendly web crawler. Converts web pages to clean Markdown for RAG pipelines. Intelligent adaptive crawling.
- **Key strengths:**
  - Generates clean LLM-ready Markdown from any page
  - CSS/XPath/LLM-based structured extraction
  - Parallel crawling, session re-use, stealth modes
  - Crash recovery for long-running crawls
  - No forced API keys
- **Self-hosted potential:** **Excellent** — fully self-contained, no external APIs required
- **Clarvis fit:** **Excellent for research/information gathering.** Not interactive (can't fill forms/click buttons), but perfect for the research pipeline.

### Tier 2: Strong Options

#### 4. Stagehand
- **URL:** https://github.com/browserbase/stagehand
- **Stars:** 50,000+
- **Language:** TypeScript (Python SDK available)
- **License:** MIT
- **What it does:** AI browser automation framework. Hybrid approach: natural language for unknown pages, code for known patterns.
- **Key strengths:**
  - Auto-caching: remembers actions, runs without LLM on repeat visits
  - Self-healing: detects when websites change, re-engages AI
  - Multiple LLM providers including open-source models
  - Python SDK via `stagehand-python`
- **Self-hosted potential:** **Good** — TypeScript core but has Python bindings
- **Clarvis fit:** Moderate. TypeScript-first is a friction point, but auto-caching is brilliant for repeated tasks.

#### 5. LaVague
- **URL:** https://github.com/lavague-ai/LaVague
- **Stars:** 5,500+
- **Language:** Python
- **License:** Apache 2.0
- **What it does:** "Large Action Model" framework. World Model observes page state, Action Engine generates Selenium/Playwright code.
- **Key strengths:**
  - Built on open-source models (can use local or remote)
  - Dual driver support (Selenium + Playwright)
  - Test automation: Gherkin specs → automated tests
  - SaaS navigation automation
- **Self-hosted potential:** **Good** — designed to work with open-source models
- **Clarvis fit:** Moderate. Good architecture but smaller community than browser-use.

#### 6. Steel Browser
- **URL:** https://github.com/steel-dev/steel-browser
- **Stars:** 8,000+
- **Language:** TypeScript
- **License:** Apache 2.0
- **What it does:** Browser-as-a-service API for AI agents. Handles infrastructure (anti-bot, proxies, sessions).
- **Key strengths:**
  - Session management and persistence
  - Anti-detection / stealth browsing
  - REST API interface
- **Self-hosted potential:** **Excellent** — designed to be self-hosted
- **Clarvis fit:** Good infrastructure layer, but TypeScript-based.

#### 7. BrowserOS
- **URL:** https://github.com/browseros-ai/BrowserOS
- **Stars:** 4,000+
- **Language:** TypeScript/Chromium fork
- **License:** MIT
- **What it does:** Full Chromium fork with built-in AI agents. Privacy-first alternative to Perplexity Comet.
- **Self-hosted potential:** Heavy (entire browser fork)
- **Clarvis fit:** Low — we already have Chromium via Playwright.

### Tier 3: Complementary Tools

#### 8. AgentQL
- **URL:** https://github.com/tinyfish-io/agentql
- **Language:** Python
- **What it does:** AI-powered web element locator. Natural language queries to find DOM elements.
- **Clarvis fit:** Could complement browser-use as an element detection layer.

#### 9. Open Operator (by Browser-Use team)
- **URL:** Part of browser-use ecosystem
- **What it does:** Gives LLMs direct Chrome access via simplified DOM view. Autonomous or approval mode.
- **Clarvis fit:** Could be the autonomous browsing mode for Clarvis.

#### 10. Agentic Browser (TheAgenticAI)
- **URL:** https://github.com/TheAgenticAI/TheAgenticBrowser
- **Language:** Python (PydanticAI-based)
- **What it does:** Natural language browser interaction using PydanticAI framework.
- **Clarvis fit:** Interesting for structured output extraction.

---

## Self-Hosted Vision Solutions (No External APIs)

### Local Vision Language Models (for screenshot understanding)

| Model | Size | Capability | Self-Hosted? |
|---|---|---|---|
| **Qwen2.5-VL** | 7B-72B | Best open VLM. OCR, object localization, 29 languages | Yes (Ollama) |
| **Llama 3.2 Vision** | 11B-90B | Strong OCR, document VQA, 128k context | Yes (Ollama) |
| **Granite Vision 3.3** | 2B | Compact, document understanding focus | Yes (Ollama) |
| **dots.ocr** | 3B | Fine-tuned Qwen2.5-VL for OCR, 100+ languages | Yes |

### Local OCR (Traditional)

| Tool | Notes |
|---|---|
| **Tesseract** | Classic OCR engine, good for clean text, weak on complex layouts |
| **PaddleOCR** | Excellent accuracy, multi-language, runs locally |
| **EasyOCR** | Simple Python API, 80+ languages, GPU optional |
| **Surya** | Modern OCR, good on documents, tables, math |

### Recommended Stack for Zero-External-Dependencies Vision

```
Browser screenshot → Qwen2.5-VL 7B (via Ollama) → structured understanding
                  → PaddleOCR (fallback for pure text extraction)
```

This gives Clarvis visual understanding of any webpage without external API calls.

---

## Recommendation

### Primary: Browser-Use + Ollama + Qwen2.5-VL

**Why browser-use wins:**
1. **Python-native** — fits Clarvis's script ecosystem perfectly
2. **Playwright-based** — same engine OpenClaw already uses (Chromium installed)
3. **LLM-agnostic** — works with Ollama for fully local operation
4. **Proven** — 78K stars, 89% benchmark success, $17M funded team
5. **Dual perception** — DOM + visual understanding (covers all web patterns)
6. **Active development** — large community, rapid iteration

**Why not others:**
- Skyvern: AGPL license, heavier infrastructure
- Stagehand: TypeScript-first, Python SDK is secondary
- LaVague: Smaller community, less proven
- Crawl4AI: Complementary (for scraping) but not interactive

### Secondary: Crawl4AI for Research Pipeline

Crawl4AI should be added separately for the research/knowledge absorption pipeline. It's not an interactive browser agent but excels at converting web pages to clean Markdown — perfect for Clarvis's `cron_research.sh` pipeline.

---

## Implementation Plan

### Phase 1: Enable OpenClaw Browser (Week 1)
1. Add `"browser": {"enabled": true, "headless": true}` to `openclaw.json`
2. Restart gateway
3. Test basic navigation, screenshots, and DOM snapshots
4. This alone gives Clarvis basic browser control via the existing tool API

### Phase 2: Install Browser-Use (Week 2)
1. `pip install browser-use langchain-ollama`
2. Install Playwright browsers (already installed, verify)
3. Create `scripts/browser_agent.py` — wrapper around browser-use
4. Integration points:
   - Input: task description from heartbeat pipeline
   - Output: results stored in ClarvisDB
   - Connect to existing Playwright/Chromium installation

### Phase 3: Local Vision Model (Week 3)
1. Install Ollama: `curl -fsSL https://ollama.com/install.sh | sh`
2. Pull vision model: `ollama pull qwen2.5-vl:7b`
3. Configure browser-use to use Ollama endpoint
4. Replace external vision API calls (Kimi K2.5 via OpenRouter) with local model
5. Update `clarvis_eyes.py` to use local vision for screenshot understanding

### Phase 4: Crawl4AI for Research (Week 4)
1. `pip install crawl4ai`
2. Create `scripts/research_crawler.py` — integrates with research pipeline
3. Replace/supplement Brave/DDG/Tavily search with direct crawling
4. Feed crawled content into ClarvisDB brain

### Phase 5: Autonomous Web Workflows (Month 2)
1. Define reusable web workflows (form filling, data extraction, monitoring)
2. Build workflow library in ClarvisDB
3. Connect to heartbeat pipeline for autonomous task execution
4. Add Stagehand-style caching for repeated tasks

---

## Architecture: Zero External Dependencies Vision

```
┌─────────────────────────────────────────────────────────┐
│                    Clarvis Cognitive Layer                │
│                                                          │
│  Heartbeat Pipeline ──→ Task: "Browse X, extract Y"      │
│                              │                            │
│                              ▼                            │
│  ┌──────────────────────────────────────────────┐        │
│  │           Browser Agent (browser-use)          │        │
│  │                                                │        │
│  │  ┌──────────┐    ┌─────────────┐              │        │
│  │  │ Playwright│    │ Page State  │              │        │
│  │  │ (Chromium)│───▶│ DOM + Screenshot           │        │
│  │  └──────────┘    └──────┬──────┘              │        │
│  │                         │                      │        │
│  │                         ▼                      │        │
│  │  ┌──────────────────────────────────┐         │        │
│  │  │     Vision Understanding          │         │        │
│  │  │  Qwen2.5-VL 7B (via Ollama)      │         │        │
│  │  │  - Screenshot → structured data   │         │        │
│  │  │  - Element identification         │         │        │
│  │  │  - Text extraction (OCR)          │         │        │
│  │  └──────────────────────────────────┘         │        │
│  │                         │                      │        │
│  │                         ▼                      │        │
│  │  ┌──────────────────────────────────┐         │        │
│  │  │     Action Decision (LLM)         │         │        │
│  │  │  Local model via Ollama           │         │        │
│  │  │  - Decide next action             │         │        │
│  │  │  - Generate Playwright commands   │         │        │
│  │  └──────────────────────────────────┘         │        │
│  └──────────────────────────────────────────────┘        │
│                              │                            │
│                              ▼                            │
│  ┌──────────────────────────────────────────────┐        │
│  │           Results → ClarvisDB Brain            │        │
│  │           Episodes, learnings, procedures      │        │
│  └──────────────────────────────────────────────┘        │
│                                                          │
│  ┌──────────────────────────────────────────────┐        │
│  │    Research Crawler (Crawl4AI) — separate      │        │
│  │    Web → Clean Markdown → Brain ingestion      │        │
│  └──────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────┘

External Dependencies: NONE
  - Chromium: already installed locally
  - Playwright: already installed locally
  - Ollama + Qwen2.5-VL: runs locally
  - Browser-use: Python library, no cloud needed
  - Crawl4AI: Python library, no cloud needed
```

---

## Resource Requirements

| Component | RAM | Disk | GPU | Notes |
|---|---|---|---|---|
| Chromium (Playwright) | ~300MB | Already installed | No | Already available |
| Browser-use | ~50MB | ~100MB | No | Python library |
| Ollama | ~500MB | ~200MB | No | Runtime engine |
| Qwen2.5-VL 7B | ~5GB | ~4.5GB | Recommended | Can run CPU-only (slower) |
| Crawl4AI | ~100MB | ~200MB | No | Python library |
| **Total new** | **~6GB** | **~5GB** | **Optional** | Qwen2.5-VL dominates |

**Note:** If GPU is not available, use `qwen2.5-vl:3b` (1.8GB RAM) or `granite3.3-vision:2b` (1.2GB) as lighter alternatives. They trade accuracy for speed but still far exceed basic OCR.

---

## Risk Assessment

| Risk | Mitigation |
|---|---|
| Local VLM quality vs. cloud models | Start with cloud (current setup), gradually shift to local as models improve |
| RAM pressure from vision model | Use 3B model variant; only load when needed (Ollama unloads after timeout) |
| Browser-use breaking changes | Pin version; it's MIT licensed so can fork if needed |
| Complex sites (SPAs, heavy JS) | Playwright handles JS rendering; browser-use adds AI understanding |
| Anti-bot detection | Steel Browser or Crawl4AI stealth modes as fallback |

---

## Sources

- [Browser-Use GitHub](https://github.com/browser-use/browser-use)
- [Skyvern GitHub](https://github.com/Skyvern-AI/skyvern)
- [Crawl4AI GitHub](https://github.com/unclecode/crawl4ai)
- [Stagehand GitHub](https://github.com/browserbase/stagehand)
- [LaVague GitHub](https://github.com/lavague-ai/LaVague)
- [Steel Browser GitHub](https://github.com/steel-dev/steel-browser)
- [BrowserOS GitHub](https://github.com/browseros-ai/BrowserOS)
- [Best AI Browser Agents 2026 (Firecrawl)](https://www.firecrawl.dev/blog/best-browser-agents)
- [30+ Open Source Web Agents (AIM)](https://aimultiple.com/open-source-web-agents)
- [Agentic Browser Landscape 2026](https://www.nohackspod.com/blog/agentic-browser-landscape-2026)
- [Using Ollama with Browser-Use](https://medium.com/@tossy21/using-ollama-with-browser-use-to-leverage-local-llms-6e1fba532b58)
- [Best Open-Source VLMs 2026 (Labellerr)](https://www.labellerr.com/blog/top-open-source-vision-language-models/)
- [Open-Source OCR Models 2025 (E2E)](https://www.e2enetworks.com/blog/complete-guide-open-source-ocr-models-2025)
- [Local Vision-Language Models (Roboflow)](https://blog.roboflow.com/local-vision-language-models/)
