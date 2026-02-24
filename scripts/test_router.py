#!/usr/bin/env python3
"""
Router Test Script — Validate direct OpenRouter API calls with cheap models.

Tests that we can call OpenRouter models directly (bypassing the gateway)
and get correct responses + real cost data back.

Usage:
    python3 test_router.py                           # Run all model tests
    python3 test_router.py "prompt" model/id         # Test specific model
    python3 test_router.py --models                  # List available models + pricing
    python3 test_router.py --benchmark "prompt"      # Compare all models on same prompt
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from typing import Dict, Optional, Tuple

sys.path.insert(0, os.path.dirname(__file__))
from cost_api import get_api_key

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Models to test — our target cheap models for routing
TEST_MODELS = {
    "minimax/minimax-m2.5": {"name": "MiniMax M2.5", "price": "$0.42/1M", "role": "simple/coding"},
    "z-ai/glm-5": {"name": "GLM-5", "price": "$1.32/1M", "role": "complex reasoning"},
    "moonshotai/kimi-k2.5": {"name": "Kimi K2.5", "price": "$0.90/1M", "role": "vision"},
    "google/gemini-3-flash-preview": {"name": "Gemini 3 Flash", "price": "$0.80/1M", "role": "web search"},
}

# Standard test prompts
TEST_PROMPTS = [
    ("simple", "What is 2 + 2? Reply with just the number."),
    ("coding", "Write a Python function that checks if a number is prime. Just the function, no explanation."),
    ("reasoning", "A farmer has 3 fields. Field A produces twice as much as Field B. Field C produces 50% more than Field A. If Field B produces 100kg, how much does Field C produce? Show your work briefly."),
]


def call_openrouter(
    prompt: str,
    model: str,
    max_tokens: int = 1024,
    temperature: float = 0.3,
    timeout: int = 30,
) -> Tuple[Optional[str], Optional[Dict], Optional[str]]:
    """Make a direct call to OpenRouter chat completions.

    Returns:
        (response_text, usage_dict, error_message)
        On success: (text, {prompt_tokens, completion_tokens, cost, ...}, None)
        On failure: (None, None, error_string)
    """
    api_key = get_api_key()

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode()

    req = urllib.request.Request(OPENROUTER_URL, data=payload, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://clarvis.openclaw.local",
        "X-Title": "Clarvis Router Test",
    })

    try:
        start = time.monotonic()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = time.monotonic() - start
            data = json.loads(resp.read().decode())

        # Extract response text
        choices = data.get("choices", [])
        text = choices[0]["message"]["content"] if choices else ""

        # Extract usage/cost
        usage = data.get("usage", {})
        gen_id = data.get("id", "")
        actual_model = data.get("model", model)

        usage_info = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "cost": usage.get("cost", 0),
            "generation_id": gen_id,
            "actual_model": actual_model,
            "latency_ms": round(elapsed * 1000),
        }

        return text, usage_info, None

    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return None, None, f"HTTP {e.code}: {body[:200]}"
    except urllib.error.URLError as e:
        return None, None, f"Network error: {e.reason}"
    except Exception as e:
        return None, None, f"Error: {str(e)}"


def test_model(model_id: str, prompt: str, label: str = "") -> Dict:
    """Test a single model and return results."""
    info = TEST_MODELS.get(model_id, {"name": model_id, "price": "?", "role": "?"})
    print(f"\n--- {info['name']} ({model_id}) ---")
    if label:
        print(f"  Prompt type: {label}")
    print(f"  Prompt: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")

    text, usage, error = call_openrouter(prompt, model_id)

    result = {
        "model": model_id,
        "label": label,
        "success": error is None,
    }

    if error:
        print(f"  ERROR: {error}")
        result["error"] = error
    else:
        print(f"  Response: {text[:200]}{'...' if len(text) > 200 else ''}")
        print(f"  Tokens: {usage['prompt_tokens']} in / {usage['completion_tokens']} out")
        print(f"  Cost: ${usage['cost']:.6f}")
        print(f"  Latency: {usage['latency_ms']}ms")
        print(f"  Model used: {usage['actual_model']}")
        result.update({
            "response": text[:500],
            "usage": usage,
        })

    return result


def run_all_tests():
    """Run test suite across all models and prompts."""
    print("=" * 60)
    print("OpenRouter Direct API — Model Validation Suite")
    print("=" * 60)

    results = []
    for model_id in TEST_MODELS:
        for label, prompt in TEST_PROMPTS:
            result = test_model(model_id, prompt, label)
            results.append(result)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    success = sum(1 for r in results if r["success"])
    total = len(results)
    print(f"Tests passed: {success}/{total}")

    if success == total:
        print("\nAll models responding correctly via direct API!")
        print("Safe to proceed with router integration.")
    else:
        failed = [r for r in results if not r["success"]]
        print("\nFailed tests:")
        for r in failed:
            print(f"  {r['model']} ({r['label']}): {r.get('error', 'unknown')}")

    # Cost summary
    total_cost = sum(r.get("usage", {}).get("cost", 0) for r in results if r["success"])
    print(f"\nTotal test cost: ${total_cost:.6f}")

    return results


def benchmark(prompt: str):
    """Compare all models on the same prompt."""
    print(f"Benchmarking: {prompt[:80]}")
    print("-" * 60)

    for model_id in TEST_MODELS:
        test_model(model_id, prompt, "benchmark")


def list_models():
    """List available test models with pricing."""
    print("Available cheap models for routing:")
    print("-" * 50)
    for model_id, info in TEST_MODELS.items():
        print(f"  {model_id}")
        print(f"    Name:  {info['name']}")
        print(f"    Price: {info['price']}")
        print(f"    Role:  {info['role']}")
        print()


def main():
    if "--models" in sys.argv:
        list_models()
        return

    if "--benchmark" in sys.argv:
        idx = sys.argv.index("--benchmark")
        prompt = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "What is the capital of France?"
        benchmark(prompt)
        return

    if len(sys.argv) >= 3 and not sys.argv[1].startswith("--"):
        # Single model test: test_router.py "prompt" model/id
        prompt = sys.argv[1]
        model = sys.argv[2]
        test_model(model, prompt, "manual")
        return

    # Default: run full test suite
    run_all_tests()


if __name__ == "__main__":
    main()
