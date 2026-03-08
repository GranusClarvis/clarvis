#!/usr/bin/env python3
"""
screenshot_analyzer.py — Screenshot any URL, analyze with local Qwen3-VL vision.

Extracts structured info: page type, main elements, interactive components.
Includes ground-truth benchmark mode for measuring extraction accuracy.

Usage:
    python3 screenshot_analyzer.py analyze <url>              # Analyze a URL
    python3 screenshot_analyzer.py analyze <url> --full-page  # Full-page screenshot
    python3 screenshot_analyzer.py benchmark                  # Run ground truth benchmark
    python3 screenshot_analyzer.py benchmark --update         # Update ground truth file

Requires: Ollama running with qwen3-vl:4b, Playwright/ClarvisBrowser for screenshots.
"""

import asyncio
import base64
import json
import os
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("Requires: pip install requests")
    sys.exit(1)

SCRIPTS_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("OLLAMA_VISION_MODEL", "qwen3-vl:4b")
SCREENSHOT_DIR = Path("/tmp/clarvis-screenshots")
GROUND_TRUTH_FILE = WORKSPACE / "data" / "screenshot_ground_truth.json"

# Structured extraction prompt — concise to maximize JSON output tokens
ANALYSIS_PROMPT = """/no_think
Analyze this webpage screenshot. Reply with ONLY this JSON (fill in real values):
{"page_type":"<landing|article|dashboard|form|search|e-commerce|social|docs|error|other>","title":"<actual page title>","main_elements":["<visible element 1>","<visible element 2>","<visible element 3>"],"interactive_components":["<clickable thing 1>","<clickable thing 2>"],"color_scheme":"<dominant colors>","layout":"<single-column|two-column|grid|sidebar|fullscreen>","has_navigation":<true or false>,"has_footer":<true or false>,"content_summary":"<one sentence describing page content>"}
Do NOT add any text before or after the JSON."""


def _ensure_ollama() -> bool:
    """Check if Ollama is running, try to start if not."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        pass

    # Try to start
    import subprocess
    try:
        subprocess.run(
            ["systemctl", "--user", "start", "ollama.service"],
            env={
                **os.environ,
                "XDG_RUNTIME_DIR": "/run/user/1001",
                "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1001/bus",
            },
            capture_output=True,
            timeout=15,
        )
        time.sleep(8)  # cold start ~51s but service should be ready faster
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def _ollama_vision(image_path: str, prompt: str, timeout: int = 180) -> dict:
    """Send image to Qwen3-VL via Ollama chat API, return parsed result."""
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    # Use /api/chat with JSON format mode
    # Qwen3-VL needs enough token budget for thinking + JSON response (~1024)
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a webpage analyzer. Output ONLY valid JSON. No explanation.",
            },
            {
                "role": "user",
                "content": prompt,
                "images": [img_b64],
            },
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1, "num_predict": 1024},
    }

    start = time.time()
    resp = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=timeout)
    elapsed = time.time() - start
    data = resp.json()

    msg = data.get("message", {})
    return {
        "thinking": msg.get("thinking", "") or data.get("thinking", ""),
        "response": msg.get("content", "") or data.get("response", ""),
        "time_s": round(elapsed, 1),
        "eval_count": data.get("eval_count", 0),
    }


def _parse_analysis(raw: dict) -> dict:
    """Extract structured JSON from Qwen3-VL response."""
    import re

    # Try response first, then thinking
    for text in [raw.get("response", ""), raw.get("thinking", "")]:
        if not text:
            continue
        # Try direct parse
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        # Try code-block extraction: ```json ... ```
        cb_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if cb_match:
            try:
                return json.loads(cb_match.group(1))
            except json.JSONDecodeError:
                pass
        # Try finding any JSON object (greedy, largest match)
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

    # Fallback: regex-extract key fields from CoT text
    combined = (raw.get("thinking", "") + "\n" + raw.get("response", "")).strip()
    if combined:
        return _extract_from_cot(combined)

    return _empty_result(raw)


def _extract_from_cot(text: str) -> dict:
    """Best-effort extraction of structured fields from chain-of-thought text."""
    import re

    result = {
        "page_type": "unknown",
        "title": "",
        "main_elements": [],
        "interactive_components": [],
        "color_scheme": "",
        "layout": "unknown",
        "has_navigation": False,
        "has_footer": False,
        "content_summary": "",
        "_extracted_from_cot": True,
    }

    tl = text.lower()

    # page_type
    types = ["landing", "article", "dashboard", "form", "search",
             "e-commerce", "social", "docs", "error"]
    for pt in types:
        if re.search(rf'page.?type["\s:]+{pt}', tl) or re.search(rf'"{pt}"', tl):
            result["page_type"] = pt
            break

    # title
    m = re.search(r'title["\s:]+["\']([^"\']+)["\']', text, re.IGNORECASE)
    if m:
        result["title"] = m.group(1)
    else:
        m = re.search(r'"([A-Z][^"]{2,40})"', text)
        if m:
            result["title"] = m.group(1)

    # navigation / footer
    result["has_navigation"] = bool(re.search(r'has.?navigation.*true|navigation.*bar|nav.*bar', tl))
    result["has_footer"] = bool(re.search(r'has.?footer.*true|footer.*visible', tl))

    # layout
    layouts = ["single-column", "two-column", "grid", "sidebar", "fullscreen"]
    for lay in layouts:
        if lay in tl:
            result["layout"] = lay
            break

    # elements — extract quoted strings, deduplicate
    elem_match = re.findall(r'"([^"]{2,50})"', text)
    if elem_match:
        noise = {"page_type", "title", "main_elements", "interactive_components",
                 "color_scheme", "layout", "has_navigation", "has_footer",
                 "content_summary", "true", "false", "colors", "unknown",
                 "one sentence"}
        seen = set()
        elems = []
        for e in elem_match:
            el = e.lower()
            if el not in noise and len(e) > 2 and el not in seen:
                seen.add(el)
                elems.append(e)
        if elems:
            result["main_elements"] = elems[:8]

    # interactive components — look for button/link/input mentions
    ic_patterns = re.findall(
        r'\b(button|link|input|dropdown|checkbox|radio|submit|search\s*bar|menu|toggle)\b',
        tl,
    )
    if ic_patterns:
        result["interactive_components"] = list(dict.fromkeys(ic_patterns))[:10]

    # content summary — find a descriptive sentence, skip CoT noise
    sentences = re.findall(r'[A-Z][^.!?]{10,150}[.!?]', text)
    cot_noise = {"wait", "hmm", "let me", "i think", "the user", "the problem",
                 "so the", "yes,", "now,", "ok,", "check"}
    for s in reversed(sentences):
        if not any(n in s.lower() for n in cot_noise):
            result["content_summary"] = s.strip()
            break

    return result


def _empty_result(raw: dict) -> dict:
    return {
        "page_type": "unknown",
        "title": "",
        "main_elements": [],
        "interactive_components": [],
        "color_scheme": "",
        "layout": "unknown",
        "has_navigation": False,
        "has_footer": False,
        "content_summary": raw.get("response", "")[:200] or raw.get("thinking", "")[:200],
        "_parse_failed": True,
    }


async def _take_screenshot(url: str, full_page: bool = False) -> str:
    """Take screenshot of URL using ClarvisBrowser."""
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    shot_path = str(SCREENSHOT_DIR / f"analyze_{int(time.time())}.png")

    try:
        from clarvis_browser import ClarvisBrowser
        async with ClarvisBrowser() as cb:
            await cb.goto(url)
            await asyncio.sleep(2)  # let page render
            path = await cb.screenshot(path=shot_path, full_page=full_page)
            return path
    except Exception as e:
        print(f"[WARN] ClarvisBrowser failed ({e}), trying direct Playwright...")

    # Fallback: direct Playwright
    try:
        from browser_agent import BrowserAgent
        async with BrowserAgent() as ba:
            await ba.goto(url)
            await asyncio.sleep(2)
            path = await ba.screenshot(path=shot_path, full_page=full_page)
            return path
    except Exception as e2:
        print(f"[WARN] BrowserAgent failed ({e2}), trying raw Playwright...")

    # Last resort: raw Playwright
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.screenshot(path=shot_path, full_page=full_page)
        await browser.close()
        return shot_path


def analyze_url(url: str, full_page: bool = False) -> dict:
    """Main entry: screenshot URL, analyze with Qwen3-VL, return structured data."""
    print(f"[1/3] Taking screenshot of {url}...")
    shot_path = asyncio.run(_take_screenshot(url, full_page))
    shot_size = os.path.getsize(shot_path)
    print(f"      Screenshot: {shot_path} ({shot_size // 1024}KB)")

    print(f"[2/3] Analyzing with {MODEL}...")
    raw = _ollama_vision(shot_path, ANALYSIS_PROMPT)
    print(f"      Vision took {raw['time_s']}s, {raw['eval_count']} tokens")

    print(f"[3/3] Parsing structured output...")
    analysis = _parse_analysis(raw)

    result = {
        "url": url,
        "screenshot_path": shot_path,
        "screenshot_kb": shot_size // 1024,
        "analysis": analysis,
        "vision_time_s": raw["time_s"],
        "vision_tokens": raw["eval_count"],
        "model": MODEL,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    return result


# --- Ground Truth Benchmark ---

DEFAULT_GROUND_TRUTH = [
    {
        "url": "https://example.com",
        "expected": {
            "page_type": "landing",
            "title": "Example Domain",
            "main_elements": ["heading", "paragraph", "link"],
            "interactive_components": ["link"],
            "has_navigation": False,
            "has_footer": False,
            "layout": "single-column",
        },
    },
    {
        "url": "https://httpbin.org/forms/post",
        "expected": {
            "page_type": "form",
            "main_elements": ["form", "input fields", "submit button"],
            "interactive_components": ["text input", "radio button", "submit button"],
            "has_navigation": False,
        },
    },
    {
        "url": "https://news.ycombinator.com",
        "expected": {
            "page_type": "social",
            "title": "Hacker News",
            "main_elements": ["story list", "navigation", "links"],
            "interactive_components": ["links", "login"],
            "has_navigation": True,
            "layout": "single-column",
        },
    },
]


def _score_field(expected, actual, field: str) -> float:
    """Score a single field: 1.0 = exact match, 0.5 = partial, 0.0 = miss."""
    ev = expected.get(field)
    av = actual.get(field)
    if ev is None:
        return 1.0  # field not in ground truth, skip

    if isinstance(ev, bool):
        return 1.0 if ev == av else 0.0

    if isinstance(ev, str):
        if ev == av:
            return 1.0
        if isinstance(av, str) and ev.lower() in av.lower():
            return 0.75
        return 0.0

    if isinstance(ev, list):
        if not isinstance(av, list):
            return 0.0
        # Fuzzy list match: what fraction of expected items appear in actual?
        ev_lower = [e.lower() for e in ev]
        av_str = " ".join(str(a).lower() for a in av)
        hits = sum(1 for e in ev_lower if e in av_str)
        return hits / len(ev_lower) if ev_lower else 1.0

    return 1.0 if ev == av else 0.0


SCORED_FIELDS = [
    "page_type", "title", "main_elements", "interactive_components",
    "has_navigation", "has_footer", "layout",
]


def benchmark(ground_truth_path: str = None) -> dict:
    """Run benchmark against ground truth, return per-URL and aggregate scores."""
    gt_path = Path(ground_truth_path) if ground_truth_path else GROUND_TRUTH_FILE
    if gt_path.exists():
        with open(gt_path) as f:
            ground_truth = json.load(f)
    else:
        ground_truth = DEFAULT_GROUND_TRUTH
        # Save default for future editing
        gt_path.parent.mkdir(parents=True, exist_ok=True)
        with open(gt_path, "w") as f:
            json.dump(ground_truth, f, indent=2)
        print(f"[INFO] Wrote default ground truth to {gt_path}")

    results = []
    total_score = 0.0

    for entry in ground_truth:
        url = entry["url"]
        expected = entry["expected"]
        print(f"\n{'='*60}")
        print(f"BENCHMARK: {url}")
        print(f"{'='*60}")

        try:
            result = analyze_url(url)
            actual = result["analysis"]

            field_scores = {}
            for field in SCORED_FIELDS:
                score = _score_field(expected, actual, field)
                field_scores[field] = score

            scored_fields = [f for f in SCORED_FIELDS if f in expected]
            url_score = (
                sum(field_scores[f] for f in scored_fields) / len(scored_fields)
                if scored_fields else 0.0
            )
            total_score += url_score

            results.append({
                "url": url,
                "score": round(url_score, 3),
                "field_scores": {k: round(v, 3) for k, v in field_scores.items()},
                "expected": expected,
                "actual": actual,
                "vision_time_s": result["vision_time_s"],
            })

            print(f"\nScore: {url_score:.1%}")
            for f in scored_fields:
                exp_v = expected.get(f, "n/a")
                act_v = actual.get(f, "n/a")
                mark = "✓" if field_scores[f] >= 0.75 else "✗"
                print(f"  {mark} {f}: expected={exp_v} got={act_v} ({field_scores[f]:.0%})")

        except Exception as e:
            print(f"[ERROR] {url}: {e}")
            results.append({"url": url, "score": 0.0, "error": str(e)})

    n = len(ground_truth)
    aggregate = round(total_score / n, 3) if n else 0.0

    summary = {
        "aggregate_score": aggregate,
        "n_urls": n,
        "results": results,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "model": MODEL,
    }

    # Save benchmark results
    bench_path = WORKSPACE / "data" / "screenshot_benchmark_results.json"
    bench_path.parent.mkdir(parents=True, exist_ok=True)
    with open(bench_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n{'='*60}")
    print(f"AGGREGATE SCORE: {aggregate:.1%} ({n} URLs)")
    print(f"Results saved to {bench_path}")

    return summary


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "analyze":
        if len(sys.argv) < 3:
            print("Usage: screenshot_analyzer.py analyze <url> [--full-page]")
            sys.exit(1)
        url = sys.argv[2]
        full_page = "--full-page" in sys.argv

        if not _ensure_ollama():
            print("[ERROR] Ollama not available. Start with: systemctl --user start ollama.service")
            sys.exit(1)

        result = analyze_url(url, full_page)
        print(f"\n{'='*60}")
        print(json.dumps(result["analysis"], indent=2))
        print(f"{'='*60}")
        print(f"Time: {result['vision_time_s']}s | Tokens: {result['vision_tokens']} | Screenshot: {result['screenshot_path']}")

    elif cmd == "benchmark":
        if not _ensure_ollama():
            print("[ERROR] Ollama not available. Start with: systemctl --user start ollama.service")
            sys.exit(1)

        gt_path = None
        if "--update" in sys.argv:
            # Write default ground truth for manual editing
            GROUND_TRUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(GROUND_TRUTH_FILE, "w") as f:
                json.dump(DEFAULT_GROUND_TRUTH, f, indent=2)
            print(f"Ground truth written to {GROUND_TRUTH_FILE}")
            print("Edit this file, then run: screenshot_analyzer.py benchmark")
            sys.exit(0)

        benchmark(gt_path)

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
