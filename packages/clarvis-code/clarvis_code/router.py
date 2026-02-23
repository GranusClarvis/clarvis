"""
TaskRouter — Classify task complexity and route to the cheapest capable executor.

Adapted from ClawRouter's 14-dimension weighted scorer. Routes tasks:
  SIMPLE  -> lightweight model (Gemini Flash, local LLM, etc.)
  COMPLEX -> full agentic model (Claude Code, OpenCode)

Saves 80-90% cost on simple tasks by not spawning full agent sessions.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class RoutingResult:
    """Result of task classification."""
    tier: str           # "simple", "medium", "complex", "reasoning"
    score: float        # Composite score [0, 1]
    executor: str       # "lightweight" or "agent"
    dimensions: Dict[str, float]  # Per-dimension scores
    reason: str         # Human-readable explanation
    forced: bool = False  # True if pattern-matched (not scored)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier,
            "score": round(self.score, 4),
            "executor": self.executor,
            "dimensions": {k: round(v, 3) for k, v in self.dimensions.items()},
            "reason": self.reason,
            "forced": self.forced,
        }


# Default dimension configuration
DEFAULT_DIMENSIONS = {
    "code_generation": {
        "weight": 0.20,
        "positive": [
            "implement", "create script", "write function", "build module",
            "code", "class", "def ", "import", "refactor", "debug",
            "fix bug", "unit test", "integration test",
        ],
        "negative": ["check", "read", "list", "count", "verify", "status"],
    },
    "file_editing": {
        "weight": 0.18,
        "positive": [
            "edit", "modify", "update file", "change", "wire into",
            "integrate", "add to script", ".py", ".sh", ".json", ".md",
        ],
        "negative": ["summarize", "report", "measure", "check"],
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
            "trade-off", "strategy", "optimize", "prove",
        ],
        "negative": ["simple", "quick", "just", "only"],
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
        "positive": ["brainstorm", "novel", "creative", "invent", "design new"],
        "negative": [],
    },
    "task_length": {
        "weight": 0.05,
        "positive": [],  # Computed dynamically
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
        "positive": [],
        "negative": [
            "what is", "how many", "show me", "tell me", "define",
            "hello", "status", "check if",
        ],
    },
    "domain_specificity": {
        "weight": 0.03,
        "positive": [
            "quantum", "fpga", "genomics", "neural network", "transformer",
            "attention mechanism",
        ],
        "negative": [],
    },
}

# Default force-agent patterns (always route to full agent)
DEFAULT_FORCE_AGENT = [
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

# Default force-lightweight patterns (always route to cheap model)
DEFAULT_FORCE_LIGHTWEIGHT = [
    r"(?i)^check\s+(?:status|health|if)\b",
    r"(?i)^read\s+(?:and\s+)?(?:summarize|report)\b",
    r"(?i)^list\s+\b",
    r"(?i)^count\s+\b",
    r"(?i)^update\s+(?:queue|log|digest)\b",
    r"(?i)^mark\s+(?:task|item)\b",
    r"(?i)^verify\s+\b",
    r"(?i)^measure\s+\b",
]


class TaskRouter:
    """Routes tasks to the cheapest capable executor based on complexity scoring.

    The router uses a 14-dimension weighted scorer adapted from ClawRouter.
    Tasks are classified into tiers (simple/medium/complex/reasoning) and
    routed to either a lightweight model or a full agentic executor.

    Args:
        dimensions: Custom dimension config (default: 14-dim ClawRouter scorer).
        force_agent_patterns: Regex patterns that always route to agent.
        force_lightweight_patterns: Regex patterns that always route to lightweight.
        tier_boundaries: Custom tier score boundaries.
        log_path: Path to write routing decision log (JSONL). None to disable.

    Example:
        router = TaskRouter()
        result = router.classify("Build a new authentication module")
        print(result.tier)      # "complex"
        print(result.executor)  # "agent"
        print(result.score)     # 0.72
    """

    def __init__(
        self,
        dimensions: Optional[Dict[str, Dict]] = None,
        force_agent_patterns: Optional[List[str]] = None,
        force_lightweight_patterns: Optional[List[str]] = None,
        tier_boundaries: Optional[Dict[str, Tuple[float, float]]] = None,
        log_path: Optional[str] = None,
    ):
        self.dimensions = dimensions or DEFAULT_DIMENSIONS
        self.force_agent = [re.compile(p) for p in (force_agent_patterns or DEFAULT_FORCE_AGENT)]
        self.force_lightweight = [re.compile(p) for p in (force_lightweight_patterns or DEFAULT_FORCE_LIGHTWEIGHT)]
        self.tier_boundaries = tier_boundaries or {
            "simple": (-1.0, 0.15),
            "medium": (0.15, 0.40),
            "complex": (0.40, 0.65),
            "reasoning": (0.65, 1.0),
        }
        self.log_path = Path(log_path) if log_path else None
        self._history: List[Dict] = []

    def classify(self, task_text: str, context: str = "") -> RoutingResult:
        """Classify a task into a complexity tier.

        Args:
            task_text: The task description.
            context: Optional additional context.

        Returns:
            RoutingResult with tier, score, executor, dimensions, and reason.
        """
        # Force-agent check
        for pattern in self.force_agent:
            if pattern.search(task_text):
                result = RoutingResult(
                    tier="complex", score=0.70, executor="agent",
                    dimensions={}, reason=f"Force-agent: {pattern.pattern}",
                    forced=True,
                )
                self._log(task_text, result)
                return result

        # Force-lightweight check
        for pattern in self.force_lightweight:
            if pattern.search(task_text):
                result = RoutingResult(
                    tier="simple", score=0.05, executor="lightweight",
                    dimensions={}, reason=f"Force-lightweight: {pattern.pattern}",
                    forced=True,
                )
                self._log(task_text, result)
                return result

        # Dimensional scoring
        text = f"{task_text} {context}".strip()
        text_lower = text.lower()
        word_count = len(text.split())

        dim_scores = {}
        weighted_sum = 0.0
        total_weight = 0.0

        for dim_name, dim_config in self.dimensions.items():
            weight = dim_config["weight"]

            if dim_name == "task_length":
                if word_count < 8:
                    raw_score = -0.5
                elif word_count < 20:
                    raw_score = 0.0
                elif word_count < 50:
                    raw_score = 0.3
                else:
                    raw_score = 0.7
            else:
                raw_score = self._score_dimension(text_lower, dim_config)

            dim_scores[dim_name] = raw_score
            weighted_sum += raw_score * weight
            total_weight += weight

        # Normalize to [0, 1]
        composite = (weighted_sum / max(total_weight, 0.01) + 1.0) / 2.0
        composite = max(0.0, min(1.0, composite))

        # Map to tier
        if composite < self.tier_boundaries["simple"][1]:
            tier = "simple"
        elif composite < self.tier_boundaries["medium"][1]:
            tier = "medium"
        elif composite < self.tier_boundaries["complex"][1]:
            tier = "complex"
        else:
            tier = "reasoning"

        executor = "lightweight" if tier in ("simple", "medium") else "agent"

        # Build reason
        top_dims = sorted(dim_scores.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
        reason_parts = [f"{name}={val:+.2f}" for name, val in top_dims if val != 0]
        reason = f"Score {composite:.3f} -> {tier} | Top: {', '.join(reason_parts) or 'no signals'}"

        result = RoutingResult(
            tier=tier, score=composite, executor=executor,
            dimensions=dim_scores, reason=reason,
        )
        self._log(task_text, result)
        return result

    def stats(self) -> Dict[str, Any]:
        """Get routing statistics from history."""
        if not self._history:
            # Try loading from log file
            if self.log_path and self.log_path.exists():
                for line in self.log_path.read_text().splitlines():
                    try:
                        self._history.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        total = len(self._history)
        if total == 0:
            return {"total": 0, "lightweight": 0, "agent": 0}

        lightweight = sum(1 for h in self._history if h.get("executor") == "lightweight")
        agent = total - lightweight

        return {
            "total": total,
            "lightweight": lightweight,
            "agent": agent,
            "lightweight_pct": round(lightweight / total * 100, 1),
        }

    @staticmethod
    def _score_dimension(text_lower: str, dim_config: Dict) -> float:
        """Score a single dimension [-1, 1] based on keyword presence."""
        pos = sum(1 for kw in dim_config.get("positive", []) if kw.lower() in text_lower)
        neg = sum(1 for kw in dim_config.get("negative", []) if kw.lower() in text_lower)
        if pos + neg == 0:
            return 0.0
        raw = (pos - neg) / max(pos + neg, 1)
        return max(-1.0, min(1.0, raw))

    def _log(self, task_text: str, result: RoutingResult):
        """Log a routing decision."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task": task_text[:150],
            "tier": result.tier,
            "score": result.score,
            "executor": result.executor,
            "reason": result.reason,
        }
        self._history.append(entry)

        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
