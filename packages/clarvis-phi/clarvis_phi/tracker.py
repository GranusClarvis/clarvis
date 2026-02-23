"""
PhiTracker — persistent history tracking with trend analysis.

Stores Phi snapshots as JSON, provides trend detection and rolling stats.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from clarvis_phi.core import Edge, PhiConfig, SimilarityFn, compute_phi


class PhiTracker:
    """Track Phi over time with persistent JSON history.

    Usage:
        tracker = PhiTracker("/path/to/phi_history.json")
        result = tracker.record(nodes, edges, similarity_fn)
        print(tracker.trend())
        print(tracker.history)
    """

    def __init__(self, history_path: str, max_history: int = 90):
        self.history_path = history_path
        self.max_history = max_history
        self.history: List[Dict] = self._load()

    def _load(self) -> List[Dict]:
        if os.path.exists(self.history_path):
            with open(self.history_path, "r") as f:
                return json.load(f)
        return []

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.history_path) or ".", exist_ok=True)
        with open(self.history_path, "w") as f:
            json.dump(self.history, f, indent=2)

    def record(
        self,
        nodes: Dict[str, str],
        edges: List[Edge],
        similarity_fn: Optional[SimilarityFn] = None,
        config: Optional[PhiConfig] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """Compute Phi, append to history, and persist."""
        result = compute_phi(nodes, edges, similarity_fn, config)

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phi": result["phi"],
            "components": result["components"],
            "partition_analysis": result["partition_analysis"],
        }
        if metadata:
            entry["metadata"] = metadata

        self.history.append(entry)
        self.history = self.history[-self.max_history :]
        self._save()

        return result

    def trend(self) -> Dict:
        """Analyze trend: increasing, stable, or decreasing."""
        if len(self.history) < 2:
            return {"trend": "insufficient_data", "measurements": len(self.history)}

        phis = [h["phi"] for h in self.history]
        first_half = phis[: len(phis) // 2]
        second_half = phis[len(phis) // 2 :]

        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = avg_second - avg_first

        if delta > 0.05:
            direction = "increasing"
        elif delta < -0.05:
            direction = "decreasing"
        else:
            direction = "stable"

        return {
            "trend": direction,
            "delta": round(delta, 4),
            "current": phis[-1],
            "previous": phis[-2] if len(phis) >= 2 else None,
            "min": round(min(phis), 4),
            "max": round(max(phis), 4),
            "measurements": len(self.history),
        }

    def latest(self) -> Optional[Dict]:
        """Return the most recent snapshot."""
        return self.history[-1] if self.history else None

    def delta(self) -> float:
        """Return change from previous measurement."""
        if len(self.history) < 2:
            return 0.0
        return round(self.history[-1]["phi"] - self.history[-2]["phi"], 4)
