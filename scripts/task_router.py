#!/usr/bin/env python3
"""
Task Router — Selective reasoning for Clarvis heartbeat loop.

Classifies task complexity and routes to the appropriate executor:
  SIMPLE/MEDIUM → OpenRouter cheap model (MiniMax M2.5)
  COMPLEX       → Claude Code CLI (full agentic, file editing, code gen)

Saves ~80-90% cost on simple tasks (queue management, config edits,
memory lookups, status checks) by not spawning a full Claude Code session.

Adapted from ClawRouter's 14-dimension weighted scorer.

Usage:
    python3 task_router.py classify "Build a new cron script for X"
    python3 task_router.py execute-openrouter "Task text" [model]
    python3 task_router.py stats
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

# === CONFIGURATION ===

DATA_DIR = "/home/agent/.openclaw/workspace/data"
ROUTER_LOG = os.path.join(DATA_DIR, "router_decisions.jsonl")

# Tier boundaries (from ClawRouter research, tuned for Clarvis tasks)
TIER_BOUNDARIES = {
    "simple": (-1.0, 0.15),   # score < 0.15 → SIMPLE
    "medium": (0.15, 0.40),   # 0.15 ≤ score < 0.40 → MEDIUM (still simple executor)
    "complex": (0.40, 0.65),  # 0.40 ≤ score < 0.65 → COMPLEX
    "reasoning": (0.65, 1.0), # score ≥ 0.65 → REASONING (always Claude Code)
}

# Tasks matching these patterns ALWAYS go to Claude Code (regardless of score)
FORCE_CLAUDE_PATTERNS = [
    r"(?i)write\s+code",
    r"(?i)create\s+(?:script|file|module)",
    r"(?i)implement\b",
    r"(?i)build\s+(?:a|the|new)\b",
    r"(?i)refactor\b",
    r"(?i)fix\s+(?:bug|error|crash|failure)",
    r"(?i)debug\b",
    r"(?i)test\s+(?:the|and|it)\b",
    r"(?i)wire\s+(?:in|into|up)\b",
    r"(?i)integrate\b",
    r"(?i)modify\b.*\.py\b",
    r"(?i)edit\s+(?:script|file|code)",
    r"(?i)add\s+(?:to|new)\s+(?:script|cron|code)",
    r"(?i)upgrade\b",
    r"(?i)deploy\b",
]

# Tasks matching these are always SIMPLE (quick operations)
FORCE_SIMPLE_PATTERNS = [
    r"(?i)^check\s+(?:status|health|if)\b",
    r"(?i)^read\s+(?:and\s+)?(?:summarize|report)\b",
    r"(?i)^list\s+\b",
    r"(?i)^count\s+\b",
    r"(?i)^update\s+(?:QUEUE|queue|log|digest)\b",
    r"(?i)^mark\s+(?:task|item)\b",
    r"(?i)^verify\s+\b",
    r"(?i)^measure\s+\b",
]


# === 14-DIMENSION SCORER ===
# Adapted from ClawRouter's rules.ts — scores [-1, 1] per dimension

DIMENSIONS = {
    "code_generation": {
        "weight": 0.20,
        "positive": [
            "implement", "create script", "write function", "build module",
            "code", "class", "def ", "import", "refactor", "debug",
            "fix bug", "unit test", "integration test",
        ],
        "negative": [
            "check", "read", "list", "count", "verify", "status",
        ],
    },
    "file_editing": {
        "weight": 0.18,
        "positive": [
            "edit", "modify", "update file", "change", "wire into",
            "integrate", "add to script", ".py", ".sh", ".json", ".md",
            "cron_", "scripts/",
        ],
        "negative": [
            "summarize", "report", "measure", "check",
        ],
    },
    "multi_step": {
        "weight": 0.15,
        "positive": [
            "first", "then", "step 1", "step 2", "and then",
            "pipeline", "workflow", "sequence", "chain",
            "build.*and.*wire", "create.*and.*test",
        ],
        "negative": [],
    },
    "reasoning_depth": {
        "weight": 0.12,
        "positive": [
            "analyze", "evaluate", "compare", "design", "architect",
            "trade-off", "strategy", "optimize", "prove", "theorem",
            "consciousness", "phi", "meta-cognition", "agi",
        ],
        "negative": [
            "simple", "quick", "just", "only",
        ],
    },
    "system_modification": {
        "weight": 0.10,
        "positive": [
            "deploy", "install", "configure", "cron", "systemd",
            "permission", "upgrade", "migrate",
        ],
        "negative": [],
    },
    "creative_generation": {
        "weight": 0.05,
        "positive": [
            "brainstorm", "novel", "creative", "invent", "design new",
        ],
        "negative": [],
    },
    "task_length": {
        "weight": 0.05,
        # Computed dynamically based on word count
        "positive": [],
        "negative": [],
    },
    "agentic_markers": {
        "weight": 0.08,
        "positive": [
            "run", "execute", "spawn", "invoke", "call",
            "fetch", "download", "upload", "push", "pull",
        ],
        "negative": [],
    },
    "query_simplicity": {
        "weight": 0.04,
        "positive": [],  # Computed: presence of simple patterns reduces score
        "negative": [
            "what is", "how many", "show me", "tell me", "define",
            "hello", "status", "check if",
        ],
    },
    "domain_specificity": {
        "weight": 0.03,
        "positive": [
            "quantum", "fpga", "genomics", "neural network", "transformer",
            "attention mechanism", "STDP", "hebbian",
        ],
        "negative": [],
    },
}


def score_dimension(text_lower, dim_config):
    """Score a single dimension [-1, 1] based on keyword presence."""
    pos_count = sum(1 for kw in dim_config["positive"] if kw.lower() in text_lower)
    neg_count = sum(1 for kw in dim_config["negative"] if kw.lower() in text_lower)

    if pos_count + neg_count == 0:
        return 0.0

    # Normalize: more keywords → stronger signal, capped at [-1, 1]
    raw = (pos_count - neg_count) / max(pos_count + neg_count, 1)
    return max(-1.0, min(1.0, raw))


def classify_task(task_text, context=""):
    """
    Classify a task into a complexity tier.

    Returns:
        dict: {
            "tier": "simple"|"medium"|"complex"|"reasoning",
            "score": float,  # weighted composite score [0, 1]
            "executor": "gemini"|"claude",
            "dimensions": dict,  # per-dimension scores
            "reason": str,
        }
    """
    text = f"{task_text} {context}".strip()
    text_lower = text.lower()
    word_count = len(text.split())

    # === OVERRIDE CHECKS ===

    # Vision tasks → Kimi K2.5
    for pattern in VISION_PATTERNS:
        if re.search(pattern, task_text):
            return {
                "tier": "vision",
                "score": 0.30,
                "executor": "openrouter",
                "dimensions": {},
                "reason": f"Vision task pattern: {pattern}",
                "model": OPENROUTER_MODELS["vision"],
            }

    # Web search tasks → Gemini 3 Flash
    for pattern in WEB_SEARCH_PATTERNS:
        if re.search(pattern, task_text):
            return {
                "tier": "web_search",
                "score": 0.25,
                "executor": "openrouter",
                "dimensions": {},
                "reason": f"Web search pattern: {pattern}",
                "model": OPENROUTER_MODELS["web_search"],
            }

    # Force Claude Code for code-heavy tasks
    for pattern in FORCE_CLAUDE_PATTERNS:
        if re.search(pattern, task_text):
            return {
                "tier": "complex",
                "score": 0.70,
                "executor": "claude",
                "dimensions": {},
                "reason": f"Force-Claude pattern match: {pattern}",
            }

    # Force simple for trivial tasks
    for pattern in FORCE_SIMPLE_PATTERNS:
        if re.search(pattern, task_text):
            return {
                "tier": "simple",
                "score": 0.05,
                "executor": "gemini",
                "dimensions": {},
                "reason": f"Force-simple pattern match: {pattern}",
            }

    # === DIMENSIONAL SCORING ===
    dim_scores = {}
    weighted_sum = 0.0
    total_weight = 0.0

    for dim_name, dim_config in DIMENSIONS.items():
        weight = dim_config["weight"]

        if dim_name == "task_length":
            # Dynamic: short tasks are simpler
            if word_count < 8:
                raw_score = -0.5
            elif word_count < 20:
                raw_score = 0.0
            elif word_count < 50:
                raw_score = 0.3
            else:
                raw_score = 0.7
        else:
            raw_score = score_dimension(text_lower, dim_config)

        dim_scores[dim_name] = round(raw_score, 3)
        weighted_sum += raw_score * weight
        total_weight += weight

    # Normalize to [0, 1] range (from [-1, 1] weighted sum)
    composite = (weighted_sum / max(total_weight, 0.01) + 1.0) / 2.0
    composite = max(0.0, min(1.0, composite))

    # === TIER MAPPING ===
    if composite < TIER_BOUNDARIES["simple"][1]:
        tier = "simple"
    elif composite < TIER_BOUNDARIES["medium"][1]:
        tier = "medium"
    elif composite < TIER_BOUNDARIES["complex"][1]:
        tier = "complex"
    else:
        tier = "reasoning"

    # Executor: simple + medium → gemini, complex + reasoning → claude
    executor = "gemini" if tier in ("simple", "medium") else "claude"

    # Build reason
    top_dims = sorted(dim_scores.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
    reason_parts = [f"{name}={val:+.2f}" for name, val in top_dims if val != 0]
    reason = f"Score {composite:.3f} → {tier} | Top: {', '.join(reason_parts) or 'no signals'}"

    return {
        "tier": tier,
        "score": round(composite, 4),
        "executor": executor,
        "dimensions": dim_scores,
        "reason": reason,
    }


# === OPENROUTER DIRECT EXECUTOR ===

# Model selection by tier and task type
OPENROUTER_MODELS = {
    "simple": "minimax/minimax-m2.5",    # $0.42/1M — fastest, cheapest
    "medium": "minimax/minimax-m2.5",    # same model, good enough for medium
    "complex": "z-ai/glm-5",             # $1.32/1M — better reasoning
    "vision": "moonshotai/kimi-k2.5",    # $0.90/1M — vision tasks
    "web_search": "google/gemini-3-flash-preview",  # $0.80/1M — web search
}

# Patterns that trigger specialized model selection (checked before tier routing)
VISION_PATTERNS = [
    r"(?i)image", r"(?i)photo", r"(?i)picture", r"(?i)screenshot",
    r"(?i)visual", r"(?i)diagram", r"(?i)chart",
    r"(?i)look\s+at", r"(?i)what.*see", r"(?i)describe.*(?:image|photo)",
    r"(?i)ocr\b", r"(?i)scan\b",
]

WEB_SEARCH_PATTERNS = [
    r"(?i)search\s+(?:the\s+)?(?:web|internet|online)",
    r"(?i)look\s+up\b", r"(?i)find\s+(?:out|info|information)",
    r"(?i)what\s+is\s+the\s+latest", r"(?i)current\s+(?:price|news|status)",
    r"(?i)google\b", r"(?i)research\s+(?:online|web)",
    r"(?i)fetch\s+(?:from|url|page|website)", r"(?i)browse\b",
]

def execute_openrouter(task_text, model=None, context="", proc_hint="", episode_hint=""):
    """
    Execute a task via direct OpenRouter API call (bypasses gateway).

    Returns:
        dict: {
            "output": str,
            "exit_code": int,
            "model": str,
            "usage": {"prompt_tokens", "completion_tokens", "cost", "generation_id"},
            "fallback": bool,  # True if task needs Claude Code escalation
        }
    """
    import urllib.request
    import urllib.error

    # Get API key
    try:
        from cost_api import get_api_key
        api_key = get_api_key()
    except Exception as e:
        return {
            "output": f"ERROR: Cannot get OpenRouter API key: {e}",
            "exit_code": 1,
            "model": "none",
            "usage": {},
            "fallback": True,
        }

    if not model:
        # Check for specialized task types first
        for pattern in VISION_PATTERNS:
            if re.search(pattern, task_text):
                model = OPENROUTER_MODELS["vision"]
                break
        if not model:
            for pattern in WEB_SEARCH_PATTERNS:
                if re.search(pattern, task_text):
                    model = OPENROUTER_MODELS["web_search"]
                    break
        if not model:
            # Fall back to tier-based selection
            cl = classify_task(task_text, context)
            model = OPENROUTER_MODELS.get(cl["tier"], OPENROUTER_MODELS["simple"])

    # Build prompt
    prompt = f"""You are Clarvis's executive function. Execute this evolution task:

TASK: {task_text}
{f'PROCEDURAL HINT: {proc_hint}' if proc_hint else ''}
{f'EPISODIC HINTS: {episode_hint}' if episode_hint else ''}
CONTEXT: {context}

IMPORTANT: You are running in lightweight mode (no file editing tools).
If this task requires writing or modifying code files, output exactly:
NEEDS_CLAUDE_CODE: true
and explain what needs to be done.

Otherwise, do the work. Be concrete. When done, output a 1-line summary."""

    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2048,
        "temperature": 0.3,
    }).encode()

    req = urllib.request.Request(url, data=payload, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://clarvis.openclaw.local",
        "X-Title": "Clarvis Task Router",
    })

    try:
        start = time.monotonic()
        resp = urllib.request.urlopen(req, timeout=60)
        elapsed = time.monotonic() - start
        data = json.loads(resp.read())

        # Extract response
        choices = data.get("choices", [])
        text = choices[0]["message"]["content"] if choices else ""

        # Sanitize: some models hallucinate tool-call XML (e.g. <minimax:tool_call>)
        text = re.sub(r'<[a-zA-Z_]+:tool_call>.*?</[a-zA-Z_]+:tool_call>', '', text, flags=re.DOTALL).strip()
        text = re.sub(r'<[a-zA-Z_]+:tool_call>.*', '', text, flags=re.DOTALL).strip()

        # Extract usage with real cost
        raw_usage = data.get("usage", {})
        gen_id = data.get("id", "")
        actual_model = data.get("model", model)

        usage = {
            "prompt_tokens": raw_usage.get("prompt_tokens", 0),
            "completion_tokens": raw_usage.get("completion_tokens", 0),
            "cost": raw_usage.get("cost", 0),
            "generation_id": gen_id,
            "actual_model": actual_model,
            "latency_ms": round(elapsed * 1000),
        }

        # Check if task needs escalation
        fallback = "NEEDS_CLAUDE_CODE: true" in text

        return {
            "output": text,
            "exit_code": 0,
            "model": actual_model,
            "usage": usage,
            "fallback": fallback,
        }

    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200] if e.fp else ""
        return {
            "output": f"OpenRouter API error {e.code}: {body}",
            "exit_code": 1,
            "model": model,
            "usage": {},
            "fallback": True,
        }
    except Exception as e:
        return {
            "output": f"OpenRouter API error: {e}",
            "exit_code": 1,
            "model": model,
            "usage": {},
            "fallback": True,
        }


# === DECISION LOGGING ===

def log_decision(task_text, classification, executor_used, outcome="pending"):
    """Log routing decision for analysis and learning."""
    os.makedirs(os.path.dirname(ROUTER_LOG), exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task": task_text[:150],
        "tier": classification["tier"],
        "score": classification["score"],
        "executor": executor_used,
        "reason": classification["reason"],
        "outcome": outcome,
    }

    with open(ROUTER_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def get_stats():
    """Get routing statistics."""
    if not os.path.exists(ROUTER_LOG):
        return {"total": 0, "gemini": 0, "claude": 0, "fallbacks": 0}

    total = gemini = claude = fallbacks = 0
    with open(ROUTER_LOG) as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                total += 1
                if entry.get("executor") == "gemini":
                    gemini += 1
                else:
                    claude += 1
                if "fallback" in entry.get("reason", "").lower():
                    fallbacks += 1
            except json.JSONDecodeError:
                continue

    return {
        "total": total,
        "gemini": gemini,
        "claude": claude,
        "fallbacks": fallbacks,
        "gemini_pct": round(gemini / max(total, 1) * 100, 1),
    }


# === CLI ===

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  task_router.py classify <task_text>     # Classify complexity")
        print("  task_router.py route <task_text>         # Classify + output JSON for bash")
        print("  task_router.py execute-openrouter <task> # Execute via OpenRouter")
        print("  task_router.py stats                     # Show routing statistics")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "classify":
        task = " ".join(sys.argv[2:])
        result = classify_task(task)
        print(json.dumps(result, indent=2))

    elif cmd == "route":
        # Machine-readable output for cron_autonomous.sh
        task = " ".join(sys.argv[2:])
        result = classify_task(task)
        # Output as single-line JSON for bash parsing
        print(json.dumps(result))

    elif cmd == "execute-openrouter":
        task = " ".join(sys.argv[2:])
        # Optional model override
        model = os.environ.get("OPENROUTER_MODEL")
        context = os.environ.get("TASK_CONTEXT", "")
        proc_hint = os.environ.get("TASK_PROC_HINT", "")
        episode_hint = os.environ.get("TASK_EPISODE_HINT", "")
        result = execute_openrouter(task, model, context, proc_hint, episode_hint)
        # Output response
        print(result["output"])
        # Output usage info to stderr for the caller to parse
        if result.get("usage"):
            usage_json = json.dumps(result["usage"])
            print(f"OPENROUTER_USAGE: {usage_json}", file=sys.stderr)
        if result.get("fallback"):
            print("NEEDS_CLAUDE_CODE: true", file=sys.stderr)
        sys.exit(result["exit_code"])

    elif cmd == "stats":
        stats = get_stats()
        print("Routing Stats:")
        print(f"  Total decisions: {stats['total']}")
        print(f"  Gemini (simple): {stats['gemini']} ({stats['gemini_pct']}%)")
        print(f"  Claude (complex): {stats['claude']}")
        print(f"  Fallbacks: {stats['fallbacks']}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
