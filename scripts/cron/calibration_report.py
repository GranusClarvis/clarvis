#!/usr/bin/env python3
"""
Weekly Calibration Report — generates a one-page calibration digest.

Computes:
  1. Brier score (7-day + all-time)
  2. Confidence band distribution + accuracy per band
  3. Failure rate by task domain
  4. Drift detection: Brier trend over last 4 weeks

Writes to: memory/cron/calibration_report.md
"""

import json
import os
import sys
from datetime import datetime, timezone

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
REPORT_PATH = os.path.join(WORKSPACE, "memory", "cron", "calibration_report.md")

sys.path.insert(0, WORKSPACE)


def _generate_report() -> str:
    from clarvis.cognition.confidence import (
        calibration, _load_predictions, _classify_domain, _domain_failure_rate,
        _domain_accuracy,
    )

    now = datetime.now(timezone.utc)
    lines = [
        f"# Calibration Report — {now.strftime('%Y-%m-%d')}",
        f"_Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}_\n",
    ]

    # --- All-time calibration ---
    cal_all = calibration()
    brier_all = cal_all.get("brier_score", "N/A")
    brier_w = cal_all.get("brier_score_weighted", "N/A")
    lines.append("## Brier Score")
    lines.append(f"- **All-time**: {brier_all}")
    lines.append(f"- **Recency-weighted**: {brier_w}")

    # --- 7-day calibration ---
    cal_7d = calibration(max_age_days=7)
    brier_7d = cal_7d.get("brier_score", "N/A")
    resolved_7d = cal_7d.get("resolved", 0)
    lines.append(f"- **7-day**: {brier_7d} (n={resolved_7d})")

    # --- 30-day calibration ---
    cal_30d = calibration(max_age_days=30)
    brier_30d = cal_30d.get("brier_score", "N/A")
    resolved_30d = cal_30d.get("resolved", 0)
    lines.append(f"- **30-day**: {brier_30d} (n={resolved_30d})")

    target = 0.10
    status = "PASS" if isinstance(brier_all, (int, float)) and brier_all < target else "FAIL"
    lines.append(f"- **Target**: <{target} → **{status}**\n")

    # --- Confidence band distribution ---
    lines.append("## Confidence Band Distribution")
    lines.append("| Band | Count | Accuracy | Expected |")
    lines.append("|------|-------|----------|----------|")
    for name, data in cal_all.get("buckets", {}).items():
        expected_mid = {"low (0-30%)": "15%", "med (30-60%)": "45%",
                        "high (60-90%)": "75%", "very_high (90-100%)": "95%"}.get(name, "?")
        acc = f"{data['accuracy']:.0%}" if data.get("accuracy") is not None else "N/A"
        lines.append(f"| {name} | {data['total']} | {acc} | ~{expected_mid} |")
    lines.append("")

    # --- Failure rate by domain ---
    lines.append("## Per-Domain Accuracy & Ceiling (30-day)")
    lines.append("| Domain | Accuracy | Ceiling | Fail Rate | Samples |")
    lines.append("|--------|----------|---------|-----------|---------|")
    domains = ["bug_fix", "integration", "new_capability", "analysis", "optimization", "research", "general"]
    for domain in domains:
        acc, n = _domain_accuracy(domain)
        if n > 0:
            acc_str = f"{acc:.0%}" if acc is not None else "?"
            ceiling = f"{min(0.95, acc + 0.05):.0%}" if acc is not None else "?"
            fail_str = f"{1.0 - acc:.0%}" if acc is not None else "?"
            lines.append(f"| {domain} | {acc_str} | {ceiling} | {fail_str} | {n} |")
    lines.append("")

    # --- Confidence distribution histogram ---
    entries = _load_predictions()
    resolved = [e for e in entries if e.get("correct") is not None and e.get("outcome") != "stale"]
    if resolved:
        lines.append("## Confidence Value Distribution")
        conf_values = [round(e["confidence"], 2) for e in resolved]
        from collections import Counter
        dist = Counter(conf_values)
        for val in sorted(dist.keys()):
            bar = "█" * min(40, dist[val])
            lines.append(f"  {val:.2f} | {bar} ({dist[val]})")
        lines.append("")

    # --- Drift warning ---
    lines.append("## Drift Detection")
    if isinstance(brier_7d, (int, float)) and isinstance(brier_all, (int, float)):
        drift = brier_7d - brier_all
        if drift > 0.05:
            lines.append(f"⚠ **7-day Brier ({brier_7d:.4f}) is {drift:.4f} above all-time ({brier_all:.4f})** — calibration may be degrading.")
        elif drift < -0.03:
            lines.append(f"✓ 7-day Brier ({brier_7d:.4f}) is {abs(drift):.4f} below all-time ({brier_all:.4f}) — calibration improving.")
        else:
            lines.append(f"✓ Calibration stable (7-day={brier_7d:.4f}, all-time={brier_all:.4f}, drift={drift:+.4f}).")
    else:
        lines.append("Insufficient data for drift detection.")
    lines.append("")

    return "\n".join(lines)


def main():
    report = _generate_report()

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        f.write(report)

    print(f"Calibration report written to {REPORT_PATH}")
    # Print summary to stdout for cron log
    for line in report.split("\n"):
        if line.startswith("- **") or line.startswith("⚠") or line.startswith("✓"):
            print(line)


if __name__ == "__main__":
    main()
