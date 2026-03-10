#!/usr/bin/env python3
"""AUTONOMY_SEARCH — Web search accuracy benchmark.

Compares two search approaches on factual questions with ground-truth answers:

  1. Browser-based:  ClarvisBrowser → Google search → extract text → LLM extracts answer
  2. API-based:      OpenRouter model with web grounding (Perplexity / Gemini Flash)

Measures: accuracy (exact + fuzzy match), latency, estimated cost.

Usage:
    python3 autonomy_search_benchmark.py              # full benchmark (both)
    python3 autonomy_search_benchmark.py --browser     # browser only
    python3 autonomy_search_benchmark.py --api         # API only
    python3 autonomy_search_benchmark.py --results     # show last results
    python3 autonomy_search_benchmark.py --questions   # list questions only
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Paths ─────────────────────────────────────────────────────────────

WORKSPACE = Path("/home/agent/.openclaw/workspace")
SCRIPTS = WORKSPACE / "scripts"
RESULTS_FILE = WORKSPACE / "data" / "autonomy_search_results.json"
AUTH_FILE = Path("/home/agent/.openclaw/agents/main/agent/auth-profiles.json")
AUTH_FILE_LEGACY = Path("/home/agent/.openclaw/agents/main/agent/auth.json")

sys.path.insert(0, str(SCRIPTS))

# ── Benchmark Questions ──────────────────────────────────────────────
# Each question has: query, ground_truth (list of acceptable answers),
# match_type: "exact" (any ground_truth must appear) or "fuzzy" (token overlap).

QUESTIONS = [
    {
        "id": "capital_australia",
        "query": "What is the capital of Australia?",
        "ground_truth": ["Canberra"],
        "match_type": "exact",
        "category": "factual",
    },
    {
        "id": "python_creator",
        "query": "Who created the Python programming language?",
        "ground_truth": ["Guido van Rossum"],
        "match_type": "exact",
        "category": "factual",
    },
    {
        "id": "speed_of_light",
        "query": "What is the speed of light in meters per second?",
        "ground_truth": ["299792458", "299,792,458", "3×10^8", "3e8", "300000000"],
        "match_type": "exact",
        "category": "factual",
    },
    {
        "id": "largest_ocean",
        "query": "What is the largest ocean on Earth?",
        "ground_truth": ["Pacific"],
        "match_type": "exact",
        "category": "factual",
    },
    {
        "id": "chromadb_language",
        "query": "What programming language is ChromaDB primarily written in?",
        "ground_truth": ["Python", "Rust"],
        "match_type": "exact",
        "category": "technical",
    },
    {
        "id": "rust_creator",
        "query": "Who originally created the Rust programming language?",
        "ground_truth": ["Graydon Hoare"],
        "match_type": "exact",
        "category": "technical",
    },
    {
        "id": "transformer_paper",
        "query": "What is the title of the original Transformer paper from 2017?",
        "ground_truth": ["Attention Is All You Need"],
        "match_type": "fuzzy",
        "category": "technical",
    },
    {
        "id": "earth_moon_distance",
        "query": "What is the average distance from Earth to the Moon in kilometers?",
        "ground_truth": ["384400", "384,400", "385000", "384000"],
        "match_type": "exact",
        "category": "factual",
    },
    {
        "id": "linux_kernel_license",
        "query": "What license is the Linux kernel released under?",
        "ground_truth": ["GPL", "GPLv2", "GNU General Public License"],
        "match_type": "exact",
        "category": "technical",
    },
    {
        "id": "water_boiling_point",
        "query": "What is the boiling point of water at sea level in Celsius?",
        "ground_truth": ["100"],
        "match_type": "exact",
        "category": "factual",
    },
]


# ── Scoring ───────────────────────────────────────────────────────────

def score_answer(answer: str, question: dict) -> dict:
    """Score an answer against ground truth. Returns {correct, confidence, detail}."""
    if not answer or answer.startswith("ERROR"):
        return {"correct": False, "confidence": 0.0, "detail": "no_answer"}

    answer_lower = answer.lower().strip()

    if question["match_type"] == "exact":
        for gt in question["ground_truth"]:
            if gt.lower() in answer_lower:
                return {"correct": True, "confidence": 1.0, "detail": f"matched: {gt}"}
        return {"correct": False, "confidence": 0.0,
                "detail": f"no match in: {answer[:80]}"}

    elif question["match_type"] == "fuzzy":
        best_overlap = 0.0
        best_gt = ""
        for gt in question["ground_truth"]:
            gt_tokens = set(gt.lower().split())
            ans_tokens = set(answer_lower.split())
            if not gt_tokens:
                continue
            overlap = len(gt_tokens & ans_tokens) / len(gt_tokens)
            if overlap > best_overlap:
                best_overlap = overlap
                best_gt = gt
        correct = best_overlap >= 0.6
        return {"correct": correct, "confidence": best_overlap,
                "detail": f"fuzzy={best_overlap:.2f} vs '{best_gt}'"}

    return {"correct": False, "confidence": 0.0, "detail": "unknown_match_type"}


# ── OpenRouter API helper ─────────────────────────────────────────────

def _get_api_key() -> str:
    """Read OpenRouter API key from auth-profiles.json or legacy auth.json."""
    env_key = os.environ.get("OPENROUTER_API_KEY")
    if env_key:
        return env_key
    # New format: auth-profiles.json
    if AUTH_FILE.exists():
        auth = json.loads(AUTH_FILE.read_text())
        profiles = auth.get("profiles", {})
        or_profile = profiles.get("openrouter:default", {})
        if or_profile.get("key"):
            return or_profile["key"]
    # Legacy format: auth.json
    if AUTH_FILE_LEGACY.exists():
        auth = json.loads(AUTH_FILE_LEGACY.read_text())
        return auth.get("openrouter", {}).get("key", "")
    return ""


def _openrouter_chat(messages: list[dict], model: str,
                     temperature: float = 0.0,
                     max_tokens: int = 200) -> tuple[str, float]:
    """Call OpenRouter chat completion. Returns (answer_text, elapsed_s)."""
    api_key = _get_api_key()
    if not api_key:
        return "ERROR: No OpenRouter API key", 0.0

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode()

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://clarvis.local",
            "X-Title": "Clarvis Autonomy Search Benchmark",
        },
    )

    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        elapsed = time.monotonic() - t0
        answer = data["choices"][0]["message"]["content"].strip()
        return answer, elapsed
    except urllib.error.HTTPError as e:
        elapsed = time.monotonic() - t0
        body = e.read().decode("utf-8", errors="replace")[:200]
        return f"ERROR: HTTP {e.code}: {body}", elapsed
    except (urllib.error.URLError, KeyError, json.JSONDecodeError) as e:
        elapsed = time.monotonic() - t0
        return f"ERROR: {e}", elapsed


# ── Search Approach 1: Browser-based ──────────────────────────────────

async def browser_search(query: str) -> tuple[str, float]:
    """Search via ClarvisBrowser → Google → extract → LLM answer extraction.

    Returns (answer, elapsed_seconds).
    """
    t0 = time.monotonic()

    try:
        from clarvis_browser import ClarvisBrowser
    except ImportError:
        return "ERROR: ClarvisBrowser not available", time.monotonic() - t0

    try:
        async with ClarvisBrowser() as cb:
            result = await cb.search_web(query, engine="google")
            if result.error:
                return f"ERROR: {result.error}", time.monotonic() - t0

            search_text = (result.text or "")[:3000]
            if not search_text.strip():
                return "ERROR: Empty search results", time.monotonic() - t0
    except Exception as e:
        return f"ERROR: Browser failed: {e}", time.monotonic() - t0

    # Use LLM to extract answer from search results text
    extract_prompt = (
        f"Based on these Google search results, answer this question concisely "
        f"(1-2 sentences max):\n\nQuestion: {query}\n\n"
        f"Search results:\n{search_text}\n\nAnswer:"
    )

    answer, _ = _openrouter_chat(
        [{"role": "user", "content": extract_prompt}],
        model="meta-llama/llama-4-scout",
        max_tokens=100,
    )
    elapsed = time.monotonic() - t0
    return answer, elapsed


# ── Search Approach 2: API-based (model with web access) ─────────────

def api_search(query: str) -> tuple[str, float]:
    """Search via OpenRouter model with native web access.

    Uses Perplexity (has built-in web search) or Gemini Flash.
    Returns (answer, elapsed_seconds).
    """
    prompt = (
        f"Answer this question concisely (1-2 sentences max). "
        f"If you need to search the web, do so.\n\n"
        f"Question: {query}\n\nAnswer:"
    )

    # Try Perplexity first (native web search), fallback to Gemini Flash
    models = [
        "perplexity/sonar",
        "google/gemini-2.5-flash-preview",
    ]

    for model in models:
        answer, elapsed = _openrouter_chat(
            [{"role": "user", "content": prompt}],
            model=model,
            max_tokens=150,
        )
        if not answer.startswith("ERROR"):
            return answer, elapsed

    return answer, elapsed


# ── Runner ────────────────────────────────────────────────────────────

async def run_benchmark(run_browser: bool = True, run_api: bool = True) -> dict:
    """Run the full benchmark. Returns results dict."""
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "questions": len(QUESTIONS),
        "browser": {"results": [], "accuracy": 0.0, "avg_latency_s": 0.0},
        "api": {"results": [], "accuracy": 0.0, "avg_latency_s": 0.0},
    }

    # -- Browser-based search --
    if run_browser:
        print("\n=== Browser-based Search ===")
        correct = 0
        total_latency = 0.0

        for i, q in enumerate(QUESTIONS):
            print(f"  [{i+1}/{len(QUESTIONS)}] {q['query'][:60]}...", end=" ", flush=True)
            answer, elapsed = await browser_search(q["query"])
            score = score_answer(answer, q)
            if score["correct"]:
                correct += 1
            total_latency += elapsed

            results["browser"]["results"].append({
                "id": q["id"],
                "answer": answer[:200],
                "elapsed_s": round(elapsed, 2),
                **score,
            })
            status = "OK" if score["correct"] else "MISS"
            print(f"[{status}] {elapsed:.1f}s — {score['detail'][:50]}")

        n = len(QUESTIONS)
        results["browser"]["accuracy"] = correct / n if n else 0
        results["browser"]["avg_latency_s"] = round(total_latency / n, 2) if n else 0
        print(f"\n  Browser accuracy: {correct}/{n} ({results['browser']['accuracy']:.0%})")
        print(f"  Avg latency: {results['browser']['avg_latency_s']:.1f}s")

    # -- API-based search --
    if run_api:
        print("\n=== API-based Search (Perplexity/Gemini) ===")
        correct = 0
        total_latency = 0.0

        for i, q in enumerate(QUESTIONS):
            print(f"  [{i+1}/{len(QUESTIONS)}] {q['query'][:60]}...", end=" ", flush=True)
            answer, elapsed = api_search(q["query"])
            score = score_answer(answer, q)
            if score["correct"]:
                correct += 1
            total_latency += elapsed

            results["api"]["results"].append({
                "id": q["id"],
                "answer": answer[:200],
                "elapsed_s": round(elapsed, 2),
                **score,
            })
            status = "OK" if score["correct"] else "MISS"
            print(f"[{status}] {elapsed:.1f}s — {score['detail'][:50]}")

        n = len(QUESTIONS)
        results["api"]["accuracy"] = correct / n if n else 0
        results["api"]["avg_latency_s"] = round(total_latency / n, 2) if n else 0
        print(f"\n  API accuracy: {correct}/{n} ({results['api']['accuracy']:.0%})")
        print(f"  Avg latency: {results['api']['avg_latency_s']:.1f}s")

    # -- Comparison --
    if run_browser and run_api:
        print("\n=== Comparison ===")
        print(f"  {'Approach':<20} {'Accuracy':>10} {'Avg Latency':>12}")
        print(f"  {'─'*20} {'─'*10} {'─'*12}")
        print(f"  {'Browser+LLM':<20} {results['browser']['accuracy']:>9.0%} "
              f"{results['browser']['avg_latency_s']:>10.1f}s")
        print(f"  {'API (Perplexity)':<20} {results['api']['accuracy']:>9.0%} "
              f"{results['api']['avg_latency_s']:>10.1f}s")

        # Per-question comparison
        print(f"\n  {'Question':<25} {'Browser':>10} {'API':>10}")
        print(f"  {'─'*25} {'─'*10} {'─'*10}")
        for b, a in zip(results["browser"]["results"], results["api"]["results"]):
            bmark = "OK" if b["correct"] else "MISS"
            amark = "OK" if a["correct"] else "MISS"
            qid = b["id"][:24]
            print(f"  {qid:<25} {bmark:>10} {amark:>10}")

    # Save results
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to: {RESULTS_FILE}")

    return results


def show_results():
    """Show last benchmark results."""
    if not RESULTS_FILE.exists():
        print("No results found. Run the benchmark first.")
        return
    data = json.loads(RESULTS_FILE.read_text())
    print(f"Last run: {data['timestamp']}")
    print(f"Questions: {data['questions']}")
    if data["browser"]["results"]:
        print(f"\nBrowser: accuracy={data['browser']['accuracy']:.0%}, "
              f"latency={data['browser']['avg_latency_s']:.1f}s")
    if data["api"]["results"]:
        print(f"API:     accuracy={data['api']['accuracy']:.0%}, "
              f"latency={data['api']['avg_latency_s']:.1f}s")


def list_questions():
    """List benchmark questions."""
    for i, q in enumerate(QUESTIONS):
        print(f"  {i+1}. [{q['id']}] {q['query']}")
        print(f"     Expected: {', '.join(q['ground_truth'])} ({q['match_type']})")


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Autonomy Search Benchmark")
    parser.add_argument("--browser", action="store_true",
                        help="Run browser search only")
    parser.add_argument("--api", action="store_true",
                        help="Run API search only")
    parser.add_argument("--results", action="store_true",
                        help="Show last results")
    parser.add_argument("--questions", action="store_true",
                        help="List benchmark questions")
    args = parser.parse_args()

    if args.results:
        show_results()
        return
    if args.questions:
        list_questions()
        return

    run_browser = not args.api    # run browser unless --api only
    run_api = not args.browser    # run API unless --browser only

    if args.browser:
        run_browser = True
        run_api = False
    if args.api:
        run_browser = False
        run_api = True

    print("=== Clarvis Autonomy Search Benchmark ===")
    print(f"Questions: {len(QUESTIONS)}")
    print(f"Browser: {'YES' if run_browser else 'no'}")
    print(f"API:     {'YES' if run_api else 'no'}")

    asyncio.run(run_benchmark(run_browser=run_browser, run_api=run_api))


if __name__ == "__main__":
    main()
