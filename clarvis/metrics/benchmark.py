"""
Clarvis Performance Benchmark — canonical PI computation and targets.

Provides:
  - TARGETS: metric definitions, weights, thresholds, directions
  - compute_pi(): composite Performance Index (0.0-1.0)
  - check_self_optimization(): regression detection and alert generation

Migrated from scripts/performance_benchmark.py (Phase 5 spine refactor).
"""

# === TARGETS (measurable thresholds) ===
# Weights emphasize intelligence, not just performance.
# Speed is secondary — smarter connections, better retrieval, higher accuracy.
TARGETS = {
    # Dimension 1: Brain Query Speed
    "brain_query_avg_ms":   {"target": 8000.0, "direction": "lower",  "label": "Brain Query Avg (ms)",    "weight": 0.08, "critical": 12000.0},
    "brain_query_p95_ms":   {"target": 9000.0, "direction": "lower",  "label": "Brain Query P95 (ms)",    "weight": 0.05, "critical": 14000.0},
    # Dimension 2: Semantic Retrieval — CORE QUALITY
    "retrieval_hit_rate":   {"target": 0.80,  "direction": "higher",  "label": "Retrieval Hit Rate",      "weight": 0.18, "critical": 0.40},
    "retrieval_precision3": {"target": 0.60,  "direction": "higher",  "label": "Precision@3",             "weight": 0.08, "critical": 0.25},
    # Dimension 3: Efficiency (tracked, not primary focus)
    "avg_tokens_per_op":    {"target": None,   "direction": "monitor", "label": "Avg Tokens/Operation",    "weight": 0.00},
    "heartbeat_overhead_s": {"target": 15.0,  "direction": "lower",   "label": "Heartbeat Overhead (s)",  "weight": 0.03, "critical": 30.0},
    # Dimension 4: Accuracy — CORE QUALITY
    "episode_success_rate": {"target": 0.70,  "direction": "higher",  "label": "Episode Success Rate",    "weight": 0.18, "critical": 0.35},
    "action_accuracy":      {"target": 0.80,  "direction": "higher",  "label": "Action Accuracy",         "weight": 0.08, "critical": 0.45},
    # Dimension 5: Results Quality / Intelligence — CORE QUALITY
    "phi":                  {"target": 0.50,  "direction": "higher",  "label": "Phi (Integration)",       "weight": 0.12, "critical": 0.20},
    "context_relevance":    {"target": 0.70,  "direction": "higher",  "label": "Context Relevance",       "weight": 0.08, "critical": 0.35},
    # Dimension 6: Brain Health
    "graph_density":        {"target": 1.0,   "direction": "higher",  "label": "Graph Density (edges/mem)","weight": 0.05, "critical": 0.2},
    "brain_total_memories": {"target": None,   "direction": "monitor", "label": "Brain Size (memories)",    "weight": 0.00},
    "bloat_score":          {"target": 0.50,  "direction": "lower",   "label": "Bloat Score",             "weight": 0.02, "critical": 0.80},
    # Dimension 7: Context/Prompt Quality
    "brief_compression":    {"target": 0.50,  "direction": "higher",  "label": "Brief Compression Ratio", "weight": 0.02, "critical": 0.15},
    # Dimension 8: Load Scaling
    "load_degradation_pct": {"target": 20.0,  "direction": "lower",   "label": "Load Degradation (%)",    "weight": 0.02, "critical": 70.0},
}


def compute_pi(metrics):
    """Compute the Performance Index (PI): 0.0-1.0 composite score.

    Each metric contributes to PI based on its weight and how well it
    meets its target. Metrics that exceed critical thresholds get 0.
    Metrics that meet targets get full weight. In between is linear.

    PI Spectrum:
      0.00-0.20  Critical    — multiple systems degraded
      0.20-0.40  Poor        — below targets
      0.40-0.60  Acceptable  — meeting minimum targets
      0.60-0.80  Good        — above targets
      0.80-1.00  Excellent   — all systems optimal

    Args:
        metrics: flat dict of metric_name -> numeric value

    Returns:
        Dict with "pi" (float 0-1) and "interpretation" (str).
    """
    total_weight = 0
    weighted_score = 0

    for key, meta in TARGETS.items():
        weight = meta.get("weight", 0)
        if weight == 0:
            continue  # Monitor-only metric

        target = meta["target"]
        critical = meta.get("critical")
        direction = meta["direction"]
        value = metrics.get(key)

        if value is None or target is None:
            continue

        total_weight += weight

        if direction == "lower":
            if value <= target:
                score = 1.0
            elif critical and value >= critical:
                score = 0.0
            elif critical:
                score = max(0, 1.0 - (value - target) / (critical - target))
            else:
                score = max(0, 1.0 - (value - target) / target) if target > 0 else 0
        else:  # higher
            if value >= target:
                score = 1.0
            elif critical is not None and value <= critical:
                score = 0.0
            elif critical is not None:
                score = max(0, (value - critical) / (target - critical))
            else:
                score = min(1.0, value / target) if target > 0 else 0

        weighted_score += weight * score

    pi = round(weighted_score / max(total_weight, 0.01), 4)

    if pi >= 0.80:
        interpretation = "Excellent — all systems optimal"
    elif pi >= 0.60:
        interpretation = "Good — above targets, healthy"
    elif pi >= 0.40:
        interpretation = "Acceptable — meeting minimum targets"
    elif pi >= 0.20:
        interpretation = "Poor — below targets, optimization needed"
    else:
        interpretation = "Critical — multiple systems degraded"

    return {"pi": pi, "interpretation": interpretation}


def check_self_optimization(report, prev_report=None):
    """Check if any metrics regressed and generate optimization triggers.

    Args:
        report: current benchmark report with "metrics" and "pi" keys
        prev_report: previous report for comparison (optional)

    Returns:
        List of alert dicts with type, severity, message, and action.
    """
    alerts = []
    metrics = report.get("metrics", {})
    pi_data = report.get("pi", {})
    pi = pi_data.get("pi", 0)

    # Check PI drop
    if prev_report:
        prev_pi = prev_report.get("pi", {}).get("pi", 0)
        if prev_pi > 0 and pi < prev_pi - 0.05:
            alerts.append({
                "type": "pi_drop",
                "severity": "high",
                "message": f"PI dropped from {prev_pi:.3f} to {pi:.3f} (-{prev_pi - pi:.3f})",
                "action": "investigate_regression",
            })

    # Check individual metrics against critical thresholds
    for key, meta in TARGETS.items():
        value = metrics.get(key)
        critical = meta.get("critical")
        direction = meta.get("direction")
        if value is None or critical is None or direction == "monitor":
            continue

        breached = (direction == "lower" and value > critical) or \
                   (direction == "higher" and value < critical)

        if breached:
            alerts.append({
                "type": "critical_breach",
                "severity": "critical",
                "metric": key,
                "label": meta.get("label", key),
                "value": value,
                "critical": critical,
                "message": f"{meta.get('label', key)}: {value} breached critical threshold {critical}",
                "action": f"fix_{key}",
            })

    # Check for significant regressions (>30% drop from previous)
    if prev_report:
        prev_metrics = prev_report.get("metrics", {})
        for key, meta in TARGETS.items():
            if meta.get("weight", 0) == 0:
                continue
            value = metrics.get(key)
            prev_value = prev_metrics.get(key)
            if value is None or prev_value is None or prev_value == 0:
                continue

            direction = meta["direction"]
            if direction == "lower":
                # For "lower is better", regression means value increased
                if value > prev_value * 1.3:
                    alerts.append({
                        "type": "regression",
                        "severity": "medium",
                        "metric": key,
                        "message": f"{meta.get('label', key)} regressed: {prev_value:.2f} -> {value:.2f} (+{((value/prev_value)-1)*100:.0f}%)",
                        "action": f"investigate_{key}",
                    })
            else:
                # For "higher is better", regression means value decreased
                if value < prev_value * 0.7:
                    alerts.append({
                        "type": "regression",
                        "severity": "medium",
                        "metric": key,
                        "message": f"{meta.get('label', key)} regressed: {prev_value:.2f} -> {value:.2f} ({((value/prev_value)-1)*100:.0f}%)",
                        "action": f"investigate_{key}",
                    })

    # Brain bloat check
    bloat = metrics.get("bloat_score", 0)
    if bloat > 0.5:
        alerts.append({
            "type": "bloat_warning",
            "severity": "medium",
            "message": f"Brain bloat score {bloat:.2f} — consider pruning low-importance memories",
            "action": "brain_optimize",
        })

    return alerts
