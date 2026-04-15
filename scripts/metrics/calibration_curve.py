#!/usr/bin/env python3
"""Calibration curve plotter — bins predictions by confidence, computes ECE, plots ASCII."""

import json
import os
import sys
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
PREDICTIONS_PATH = WORKSPACE / "data" / "calibration" / "predictions.jsonl"
OUTPUT_DIR = WORKSPACE / "data" / "calibration"


def load_predictions(path: Path = PREDICTIONS_PATH) -> list[dict]:
    preds = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if "confidence" in d and "correct" in d:
                preds.append(d)
    return preds


def bin_predictions(preds: list[dict], bins: list[tuple[float, float]] = None) -> dict:
    if bins is None:
        bins = [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0)]
    result = {}
    for lo, hi in bins:
        key = f"{lo:.1f}-{hi:.1f}"
        in_bin = [p for p in preds if lo <= p["confidence"] < hi]
        if hi == 1.0:
            in_bin = [p for p in preds if lo <= p["confidence"] <= hi]
        n = len(in_bin)
        correct = sum(1 for p in in_bin if p["correct"])
        accuracy = correct / n if n > 0 else 0.0
        midpoint = (lo + hi) / 2
        result[key] = {
            "lo": lo, "hi": hi, "midpoint": midpoint,
            "n": n, "correct": correct, "accuracy": accuracy,
        }
    return result


def compute_ece(binned: dict, total_n: int) -> float:
    ece = 0.0
    for info in binned.values():
        if info["n"] == 0:
            continue
        gap = abs(info["accuracy"] - info["midpoint"])
        ece += (info["n"] / total_n) * gap
    return ece


def compute_mce(binned: dict) -> float:
    mce = 0.0
    for info in binned.values():
        if info["n"] == 0:
            continue
        gap = abs(info["accuracy"] - info["midpoint"])
        mce = max(mce, gap)
    return mce


def ascii_calibration_curve(binned: dict, width: int = 50) -> str:
    lines = []
    lines.append("Calibration Curve (predicted confidence vs actual accuracy)")
    lines.append("=" * 60)
    lines.append(f"{'Bin':>9}  {'n':>4}  {'Actual':>6}  {'Expected':>8}  {'Gap':>5}  Bar")
    lines.append("-" * 60)

    for key in sorted(binned.keys()):
        info = binned[key]
        n = info["n"]
        acc = info["accuracy"]
        mid = info["midpoint"]
        gap = acc - mid

        bar_len = int(acc * width)
        expected_mark = int(mid * width)
        bar = ""
        for i in range(width):
            if i == expected_mark:
                bar += "|"
            elif i < bar_len:
                bar += "#"
            else:
                bar += "."
        gap_str = f"{gap:+.3f}"
        lines.append(f"{key:>9}  {n:>4}  {acc:>6.3f}  {mid:>8.2f}  {gap_str:>5}  {bar}")

    lines.append("-" * 60)
    lines.append("  # = actual accuracy    | = perfect calibration line")
    lines.append("")

    lines.append("Reliability Diagram (visual):")
    lines.append(f"  1.0 |{'':>50}")
    for row_val in [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0]:
        row = "  "
        for key in sorted(binned.keys()):
            info = binned[key]
            if info["n"] == 0:
                row += "     "
                continue
            if abs(info["accuracy"] - row_val) < 0.05:
                row += "  *  "
            elif abs(info["midpoint"] - row_val) < 0.05:
                row += "  o  "
            else:
                row += "     "
        lines.append(f"  {row_val:.1f} |{row}")
    lines.append(f"      +{'-----' * len(binned)}")
    bin_labels = "  ".join(f"{k[:3]}" for k in sorted(binned.keys()))
    lines.append(f"       {bin_labels}")
    lines.append("  * = actual accuracy    o = perfect calibration")

    return "\n".join(lines)


def generate_report(preds: list[dict] = None) -> str:
    if preds is None:
        preds = load_predictions()

    binned = bin_predictions(preds)
    total_n = len(preds)
    ece = compute_ece(binned, total_n)
    mce = compute_mce(binned)

    lines = []
    lines.append(f"# Calibration Curve Report")
    lines.append(f"Total predictions: {total_n}")
    lines.append(f"Overall accuracy: {sum(1 for p in preds if p['correct']) / total_n:.3f}")
    lines.append(f"ECE (Expected Calibration Error): {ece:.4f}")
    lines.append(f"MCE (Maximum Calibration Error): {mce:.4f}")
    lines.append("")

    interpretation = "well-calibrated" if ece < 0.05 else "moderately calibrated" if ece < 0.10 else "poorly calibrated"
    lines.append(f"Interpretation: {interpretation} (ECE {'<' if ece < 0.05 else '>'} 0.05)")
    lines.append("")

    lines.append(ascii_calibration_curve(binned))
    lines.append("")

    lines.append("## Per-Bin Details")
    for key in sorted(binned.keys()):
        info = binned[key]
        gap = info["accuracy"] - info["midpoint"]
        direction = "overconfident" if gap < -0.02 else "underconfident" if gap > 0.02 else "well-calibrated"
        lines.append(f"  {key}: n={info['n']:>3}, accuracy={info['accuracy']:.3f}, expected={info['midpoint']:.2f}, gap={gap:+.3f} ({direction})")

    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Calibration curve plotter")
    parser.add_argument("command", nargs="?", default="report", choices=["report", "ece", "plot", "json"])
    parser.add_argument("--input", type=str, default=str(PREDICTIONS_PATH))
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    preds = load_predictions(Path(args.input))

    if args.command == "ece":
        binned = bin_predictions(preds)
        ece = compute_ece(binned, len(preds))
        print(f"{ece:.4f}")
        return

    if args.command == "json":
        binned = bin_predictions(preds)
        ece = compute_ece(binned, len(preds))
        mce = compute_mce(binned)
        result = {"ece": ece, "mce": mce, "total": len(preds), "bins": binned}
        print(json.dumps(result, indent=2))
        return

    if args.command == "plot":
        binned = bin_predictions(preds)
        print(ascii_calibration_curve(binned))
        return

    report = generate_report(preds)
    print(report)

    if args.output:
        out = Path(args.output)
        os.makedirs(out.parent, exist_ok=True)
        out.write_text(report + "\n")
        print(f"\nWritten to: {out}")


if __name__ == "__main__":
    main()
