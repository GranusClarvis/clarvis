"""
Token optimizer — concrete strategies for reducing API costs.

Migrated from packages/clarvis-cost/clarvis_cost/optimizer.py into the spine.
The canonical import is now: from clarvis.orch.cost_optimizer import PromptCache

Provides:
  - Prompt deduplication (detect repeated content across calls)
  - Caching layer for repeated queries
  - Context window budget planner
  - Compression ratio tracking
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple


@dataclass
class CacheEntry:
    """A cached prompt-response pair."""
    key: str
    response: str
    model: str
    tokens_saved: int
    created_at: float
    hits: int = 0


class PromptCache:
    """Simple file-backed cache for repeated prompts.

    Hashes prompts and stores responses. On cache hit, returns the stored
    response instead of making an API call — saving 100% of tokens.

    Best for: health checks, status queries, repeated analytics.
    """

    def __init__(self, cache_path: str, ttl_seconds: int = 1800):
        self.cache_path = cache_path
        self.ttl = ttl_seconds
        self._cache: Dict[str, CacheEntry] = {}
        self._load()

    def _hash(self, prompt: str, model: str) -> str:
        """Generate cache key from prompt + model."""
        content = f"{model}:{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _load(self):
        if not os.path.exists(self.cache_path):
            return
        try:
            with open(self.cache_path) as f:
                data = json.load(f)
            now = time.time()
            for key, entry in data.items():
                if now - entry["created_at"] < self.ttl:
                    self._cache[key] = CacheEntry(**entry)
        except (json.JSONDecodeError, KeyError):
            pass

    def _save(self):
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        now = time.time()
        # Prune expired entries on save
        valid = {k: asdict(v) for k, v in self._cache.items()
                 if now - v.created_at < self.ttl}
        with open(self.cache_path, "w") as f:
            json.dump(valid, f, indent=2)

    def get(self, prompt: str, model: str) -> Optional[str]:
        """Check cache. Returns response text or None."""
        key = self._hash(prompt, model)
        entry = self._cache.get(key)
        if entry and time.time() - entry.created_at < self.ttl:
            entry.hits += 1
            return entry.response
        return None

    def put(self, prompt: str, model: str, response: str, input_tokens: int):
        """Store a response in cache."""
        key = self._hash(prompt, model)
        self._cache[key] = CacheEntry(
            key=key,
            response=response,
            model=model,
            tokens_saved=input_tokens,
            created_at=time.time(),
        )
        self._save()

    def stats(self) -> Dict:
        """Cache performance stats."""
        total_hits = sum(e.hits for e in self._cache.values())
        total_saved = sum(e.tokens_saved * e.hits for e in self._cache.values())
        return {
            "entries": len(self._cache),
            "total_hits": total_hits,
            "tokens_saved_by_cache": total_saved,
            "ttl_seconds": self.ttl,
        }


class ContextBudgetPlanner:
    """Plan token allocation across context window components.

    Given a max context window, allocates budget to:
    - System prompt (fixed)
    - Retrieved context (variable)
    - User content (variable)
    - Reserved for output (fixed)

    Helps prevent context overflow and optimizes information density.
    """

    DEFAULT_BUDGETS = {
        "system_prompt": 2000,
        "episodic_hints": 500,
        "queue_context": 1500,
        "health_metrics": 300,
        "task_description": 1000,
        "output_reserved": 4000,
    }

    def __init__(self, max_context: int = 200_000):
        self.max_context = max_context
        self.budgets = dict(self.DEFAULT_BUDGETS)

    def allocate(self, components: Dict[str, str]) -> Dict[str, Dict]:
        """Allocate token budget across components.

        Args:
            components: {name: text_content} for each prompt component

        Returns:
            {name: {"tokens": int, "budget": int, "over_budget": bool, "action": str}}
        """
        from clarvis.orch.cost_tracker import estimate_tokens

        result = {}
        total_used = 0

        for name, text in components.items():
            tokens = estimate_tokens(text)
            budget = self.budgets.get(name, 2000)
            over = tokens > budget
            action = "ok"
            if over:
                ratio = tokens / budget
                if ratio > 3.0:
                    action = "compress_aggressively"
                elif ratio > 1.5:
                    action = "compress"
                else:
                    action = "trim"

            result[name] = {
                "tokens": tokens,
                "budget": budget,
                "over_budget": over,
                "action": action,
            }
            total_used += tokens

        result["_total"] = {
            "tokens": total_used,
            "budget": self.max_context,
            "over_budget": total_used > self.max_context,
            "utilization_pct": round(total_used / self.max_context * 100, 1),
        }
        return result


def detect_prompt_waste(prompt: str) -> Dict:
    """Analyze a prompt for token waste patterns.

    Detects:
    - Repeated instructions
    - Verbose preambles
    - Unnecessary formatting
    - Redundant context
    """
    issues = []
    tokens_wasted = 0

    lines = prompt.split("\n")

    # Check for repeated lines
    seen_lines = {}
    for i, line in enumerate(lines):
        stripped = line.strip()
        if len(stripped) < 10:
            continue
        if stripped in seen_lines:
            issues.append(f"Duplicate line at {i+1} (first at {seen_lines[stripped]+1}): {stripped[:60]}")
            tokens_wasted += len(stripped) // 4
        else:
            seen_lines[stripped] = i

    # Check for excessive whitespace
    blank_runs = 0
    max_blank_run = 0
    for line in lines:
        if not line.strip():
            blank_runs += 1
        else:
            max_blank_run = max(max_blank_run, blank_runs)
            blank_runs = 0
    if max_blank_run > 3:
        issues.append(f"Excessive blank lines (max run of {max_blank_run})")
        tokens_wasted += max_blank_run

    # Check for very long lines (might be uncompressed data)
    for i, line in enumerate(lines):
        if len(line) > 2000:
            issues.append(f"Very long line at {i+1} ({len(line)} chars) — may be uncompressed data")
            tokens_wasted += len(line) // 8  # Estimate waste as 12.5%

    return {
        "issues": issues,
        "estimated_waste_tokens": tokens_wasted,
        "total_tokens": len(prompt) // 4,
        "waste_pct": round(tokens_wasted / max(len(prompt) // 4, 1) * 100, 1),
    }


def compression_ratio_report(raw_text: str, compressed_text: str) -> Dict:
    """Measure compression effectiveness."""
    from clarvis.orch.cost_tracker import estimate_tokens

    raw_tokens = estimate_tokens(raw_text)
    comp_tokens = estimate_tokens(compressed_text)
    saved = raw_tokens - comp_tokens

    return {
        "raw_tokens": raw_tokens,
        "compressed_tokens": comp_tokens,
        "tokens_saved": saved,
        "compression_ratio": round(comp_tokens / max(raw_tokens, 1), 3),
        "reduction_pct": round(saved / max(raw_tokens, 1) * 100, 1),
    }
