"""RL-lite feedback loop for retrieval quality.

Tracks retrieval_verdict × task_outcome to compute reward signals.
Maintains per-verdict success rate via EMA (alpha=0.1) and generates
threshold adjustment suggestions every N episodes.

Data stored in data/retrieval_quality/retrieval_params.json.
Suggestions written to data/retrieval_quality/param_suggestions.json.

Reference: Adaptive RAG pipeline — GATE → EVAL → RETRY → FEEDBACK (this module).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

EMA_ALPHA = 0.1             # Smoothing factor for success rate EMA
SUGGESTION_INTERVAL = 50     # Generate suggestions every N episodes
MIN_EPISODES_FOR_SUGGESTION = 20  # Need at least this many per verdict

# Reward signal: (retrieval_verdict, task_outcome) → reward
# Good retrieval + success → positive reward
# Bad retrieval + failure → neutral (retrieval correctly skipped)
# Good retrieval + failure → slight negative (retrieval didn't help)
# Bad retrieval + success → negative (retrieval was wrong)
REWARD_MAP = {
    ("CORRECT", "success"): 1.0,
    ("CORRECT", "failure"): -0.3,
    ("CORRECT", "timeout"): -0.2,
    ("AMBIGUOUS", "success"): 0.3,
    ("AMBIGUOUS", "failure"): -0.1,
    ("AMBIGUOUS", "timeout"): -0.1,
    ("INCORRECT", "success"): -0.5,   # retrieval said bad but task succeeded anyway
    ("INCORRECT", "failure"): 0.2,    # retrieval correctly identified bad context
    ("INCORRECT", "timeout"): 0.1,
    ("SKIPPED", "success"): 0.0,
    ("SKIPPED", "failure"): 0.0,
    ("SKIPPED", "timeout"): 0.0,
    ("NO_RESULTS", "success"): 0.0,
    ("NO_RESULTS", "failure"): 0.0,
    ("NO_RESULTS", "timeout"): 0.0,
    ("ERROR", "success"): 0.0,
    ("ERROR", "failure"): 0.0,
    ("ERROR", "timeout"): 0.0,
}

# Default data directory
_DEFAULT_DATA_DIR = Path(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")) / "data" / "retrieval_quality"


def _default_params() -> dict:
    """Return default params structure."""
    return {
        "version": 1,
        "total_episodes": 0,
        "last_updated": None,
        "last_suggestion_at": 0,
        "ema_success_rate": {
            "CORRECT": 0.5,
            "AMBIGUOUS": 0.5,
            "INCORRECT": 0.5,
            "SKIPPED": 0.5,
            "NO_RESULTS": 0.5,
            "ERROR": 0.5,
        },
        "verdict_counts": {
            "CORRECT": 0,
            "AMBIGUOUS": 0,
            "INCORRECT": 0,
            "SKIPPED": 0,
            "NO_RESULTS": 0,
            "ERROR": 0,
        },
        "reward_history": [],  # Last 100 rewards for trend analysis
    }


class RetrievalFeedback:
    """RL-lite feedback tracker for retrieval quality.

    Tracks retrieval_verdict × task_outcome to compute reward signals,
    maintains per-verdict success rate via EMA, and generates threshold
    adjustment suggestions.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else _DEFAULT_DATA_DIR
        self.params_file = self.data_dir / "retrieval_params.json"
        self.suggestions_file = self.data_dir / "param_suggestions.json"
        self.params = self._load_params()

    def _load_params(self) -> dict:
        """Load params from disk or return defaults."""
        if self.params_file.exists():
            try:
                with open(self.params_file) as f:
                    data = json.load(f)
                # Ensure all expected keys exist
                defaults = _default_params()
                for key in defaults:
                    if key not in data:
                        data[key] = defaults[key]
                # Ensure all verdict keys exist in sub-dicts
                for verdict in ("CORRECT", "AMBIGUOUS", "INCORRECT",
                                "SKIPPED", "NO_RESULTS", "ERROR"):
                    data["ema_success_rate"].setdefault(verdict, 0.5)
                    data["verdict_counts"].setdefault(verdict, 0)
                return data
            except (json.JSONDecodeError, IOError):
                return _default_params()
        return _default_params()

    def _save_params(self) -> None:
        """Persist params to disk."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.params["last_updated"] = datetime.now(timezone.utc).isoformat()
        # Trim reward history to last 100
        self.params["reward_history"] = self.params["reward_history"][-100:]
        tmp = self.params_file.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(self.params, f, indent=2)
        tmp.rename(self.params_file)

    def compute_reward(self, verdict: str, outcome: str) -> float:
        """Compute reward signal from verdict × outcome pair.

        Args:
            verdict: CORRECT/AMBIGUOUS/INCORRECT/SKIPPED/NO_RESULTS/ERROR
            outcome: success/failure/timeout

        Returns:
            Reward in [-1.0, 1.0] range
        """
        return REWARD_MAP.get((verdict, outcome), 0.0)

    def record(self, verdict: str, outcome: str,
               max_score: Optional[float] = None,
               task: str = "") -> dict:
        """Record a retrieval feedback episode.

        Updates EMA success rate, appends to reward history, and checks
        if threshold suggestions should be generated.

        Args:
            verdict: Retrieval verdict from eval
            outcome: Task outcome (success/failure/timeout)
            max_score: Max retrieval score (optional)
            task: Task description (optional, for logging)

        Returns:
            Dict with reward, updated EMA, and whether suggestions were generated.
        """
        reward = self.compute_reward(verdict, outcome)
        is_success = 1.0 if outcome == "success" else 0.0

        # Update EMA for this verdict
        old_ema = self.params["ema_success_rate"].get(verdict, 0.5)
        new_ema = EMA_ALPHA * is_success + (1 - EMA_ALPHA) * old_ema
        self.params["ema_success_rate"][verdict] = round(new_ema, 4)

        # Update counts
        self.params["verdict_counts"][verdict] = \
            self.params["verdict_counts"].get(verdict, 0) + 1
        self.params["total_episodes"] += 1

        # Append to reward history
        self.params["reward_history"].append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "verdict": verdict,
            "outcome": outcome,
            "reward": reward,
            "max_score": max_score,
        })

        # Check if we should generate suggestions
        suggestions_generated = False
        episodes_since = self.params["total_episodes"] - \
            self.params["last_suggestion_at"]
        if episodes_since >= SUGGESTION_INTERVAL:
            suggestions_generated = self._generate_suggestions()

        self._save_params()

        return {
            "reward": reward,
            "ema_success_rate": new_ema,
            "verdict": verdict,
            "outcome": outcome,
            "total_episodes": self.params["total_episodes"],
            "suggestions_generated": suggestions_generated,
        }

    def _generate_suggestions(self) -> bool:
        """Generate threshold adjustment suggestions based on accumulated data.

        Analyzes EMA success rates per verdict and suggests adjustments
        to CORRECT_THRESHOLD and AMBIGUOUS_THRESHOLD in retrieval_eval.py.

        Returns:
            True if suggestions were written, False otherwise.
        """
        counts = self.params["verdict_counts"]
        ema = self.params["ema_success_rate"]

        suggestions = []

        # If CORRECT verdicts have low success rate, threshold may be too loose
        correct_count = counts.get("CORRECT", 0)
        if correct_count >= MIN_EPISODES_FOR_SUGGESTION:
            correct_success = ema.get("CORRECT", 0.5)
            if correct_success < 0.6:
                suggestions.append({
                    "parameter": "CORRECT_THRESHOLD",
                    "current": 0.55,
                    "suggested": 0.60,
                    "reason": f"CORRECT verdict success rate is low ({correct_success:.2f}). "
                              f"Raise threshold to be more selective.",
                    "confidence": min(correct_count / 50, 1.0),
                })
            elif correct_success > 0.85:
                suggestions.append({
                    "parameter": "CORRECT_THRESHOLD",
                    "current": 0.55,
                    "suggested": 0.50,
                    "reason": f"CORRECT verdict success rate is high ({correct_success:.2f}). "
                              f"Lower threshold to include more results.",
                    "confidence": min(correct_count / 50, 1.0),
                })

        # If INCORRECT verdicts often lead to success, threshold may be too strict
        incorrect_count = counts.get("INCORRECT", 0)
        if incorrect_count >= MIN_EPISODES_FOR_SUGGESTION:
            incorrect_success = ema.get("INCORRECT", 0.5)
            if incorrect_success > 0.5:
                suggestions.append({
                    "parameter": "AMBIGUOUS_THRESHOLD",
                    "current": 0.35,
                    "suggested": 0.30,
                    "reason": f"INCORRECT verdict has {incorrect_success:.2f} success rate. "
                              f"Many 'bad' retrievals lead to good outcomes — "
                              f"lower AMBIGUOUS threshold to salvage more context.",
                    "confidence": min(incorrect_count / 50, 1.0),
                })

        # If AMBIGUOUS verdicts rarely succeed, tighten
        ambiguous_count = counts.get("AMBIGUOUS", 0)
        if ambiguous_count >= MIN_EPISODES_FOR_SUGGESTION:
            ambiguous_success = ema.get("AMBIGUOUS", 0.5)
            if ambiguous_success < 0.4:
                suggestions.append({
                    "parameter": "AMBIGUOUS_THRESHOLD",
                    "current": 0.35,
                    "suggested": 0.40,
                    "reason": f"AMBIGUOUS verdict success rate is low ({ambiguous_success:.2f}). "
                              f"Raise threshold — treat more borderline results as INCORRECT.",
                    "confidence": min(ambiguous_count / 50, 1.0),
                })

        if not suggestions:
            suggestions.append({
                "parameter": "none",
                "reason": "No threshold adjustments needed. Current parameters performing well.",
                "confidence": 1.0,
            })

        result = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_episodes": self.params["total_episodes"],
            "ema_success_rates": dict(ema),
            "verdict_counts": dict(counts),
            "suggestions": suggestions,
            "note": "HUMAN REVIEW REQUIRED — do not auto-apply.",
        }

        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            tmp = self.suggestions_file.with_suffix(".tmp")
            with open(tmp, "w") as f:
                json.dump(result, f, indent=2)
            tmp.rename(self.suggestions_file)
            self.params["last_suggestion_at"] = self.params["total_episodes"]
            return True
        except IOError:
            return False

    def get_stats(self) -> dict:
        """Return current feedback stats for monitoring."""
        recent = self.params["reward_history"][-20:]
        avg_reward = (sum(r["reward"] for r in recent) / len(recent)) if recent else 0.0
        return {
            "total_episodes": self.params["total_episodes"],
            "ema_success_rate": dict(self.params["ema_success_rate"]),
            "verdict_counts": dict(self.params["verdict_counts"]),
            "avg_recent_reward": round(avg_reward, 4),
            "last_updated": self.params["last_updated"],
        }


# ---------------------------------------------------------------------------
# Module-level singleton for easy import
# ---------------------------------------------------------------------------

_instance: Optional[RetrievalFeedback] = None


def get_feedback(data_dir: Optional[Path] = None) -> RetrievalFeedback:
    """Get or create singleton RetrievalFeedback instance."""
    global _instance
    if _instance is None or (data_dir and _instance.data_dir != Path(data_dir)):
        _instance = RetrievalFeedback(data_dir)
    return _instance


def record_feedback(verdict: str, outcome: str,
                    max_score: Optional[float] = None,
                    task: str = "") -> dict:
    """Convenience wrapper: record feedback using singleton."""
    return get_feedback().record(verdict, outcome, max_score, task)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    fb = get_feedback()

    if len(sys.argv) < 2:
        print("Usage: python -m clarvis.brain.retrieval_feedback stats|record <verdict> <outcome>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "stats":
        stats = fb.get_stats()
        print(json.dumps(stats, indent=2))

    elif cmd == "record" and len(sys.argv) >= 4:
        verdict = sys.argv[2]
        outcome = sys.argv[3]
        max_score = float(sys.argv[4]) if len(sys.argv) > 4 else None
        result = fb.record(verdict, outcome, max_score)
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
