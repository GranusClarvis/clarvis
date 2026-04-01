"""
Memory Audit — Archived vs Active + Canonical vs Synthetic Ratio tracking.

Two audits:
  1. Archived Memory Audit: Compares archived/pruned memories against active ones
     to detect if useful memories were pushed out while noisy synthetic ones remained.
  2. Canonical vs Synthetic Ratio: Tracks ratios per collection, alerts when
     synthetic support memories exceed healthy thresholds.

Synthetic sources: memories created by automated processes (bridges, boosters,
conversation_learner patterns) rather than direct user/conversation/manual input.
"""

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
AUDIT_FILE = os.path.join(WORKSPACE, "data/memory_audit.json")
AUDIT_HISTORY = os.path.join(WORKSPACE, "data/memory_audit_history.jsonl")
MAX_HISTORY = 200

# Sources that are synthetic/automated (not from direct conversation or manual input)
SYNTHETIC_SOURCES = {
    "conversation_learner", "semantic_bridge_builder", "semantic_overlap_booster",
    "semantic_overlap_booster_fresh", "semantic_overlap_booster_targeted",
    "semantic_overlap_booster_mirror", "brain_bridge_postflight",
    "dream_engine", "failure_amplifier", "crosslink", "synthesized",
    "intra_linker", "semantic_bridge",
}

# Canonical sources — direct from user interaction, manual input, or primary systems
CANONICAL_SOURCES = {
    "conversation", "manual", "user", "feedback", "self-reflection",
    "research_ingest", "research", "episodic_memory", "internal",
    "procedural_memory", "clarvis_reasoning", "confidence_tracker",
    "self-assessment", "workspace_broadcast",
}

# Per-collection healthy synthetic ratio thresholds (synthetic / total)
# Above these triggers an alert
SYNTHETIC_THRESHOLDS = {
    "clarvis-identity": 0.30,      # Identity should be mostly canonical
    "clarvis-preferences": 0.30,   # Preferences from user
    "clarvis-goals": 0.25,         # Goals should be user-driven
    "clarvis-learnings": 0.50,     # Learnings can have more synthetic (patterns)
    "clarvis-memories": 0.40,      # General memories
    "clarvis-infrastructure": 0.40,
    "clarvis-context": 0.60,       # Context can be more synthetic
    "clarvis-episodes": 0.30,      # Episodes are from execution
    "clarvis-procedures": 0.40,    # Procedures can be extracted
    "autonomous-learning": 0.70,   # Naturally more synthetic
}

DEFAULT_THRESHOLD = 0.50


def classify_source(source):
    """Classify a memory source as canonical, synthetic, or unknown."""
    source = (source or "unknown").lower().strip()
    if source in SYNTHETIC_SOURCES:
        return "synthetic"
    if source in CANONICAL_SOURCES:
        return "canonical"
    # Heuristic: if it contains bridge/boost/mirror, it's synthetic
    if any(kw in source for kw in ("bridge", "boost", "mirror", "synth")):
        return "synthetic"
    return "unknown"


def audit_memory_ratios():
    """Audit canonical vs synthetic ratios per collection.

    Returns dict with per-collection stats and alerts.
    """
    from clarvis.brain import brain

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "collections": {},
        "totals": {"canonical": 0, "synthetic": 0, "unknown": 0, "total": 0},
        "alerts": [],
        "source_distribution": {},
    }

    source_counts = Counter()

    for col_name, col in brain.collections.items():
        col_results = col.get(include=["metadatas"], limit=col.count())
        metas = col_results.get("metadatas", [])

        canonical = 0
        synthetic = 0
        unknown = 0
        col_sources = Counter()
        importance_by_type = {"canonical": [], "synthetic": [], "unknown": []}

        for meta in metas:
            src = meta.get("source", "unknown")
            source_counts[src] += 1
            col_sources[src] += 1
            classification = classify_source(src)
            importance = meta.get("importance", 0.5)

            if classification == "canonical":
                canonical += 1
            elif classification == "synthetic":
                synthetic += 1
            else:
                unknown += 1

            importance_by_type[classification].append(importance)

        total = canonical + synthetic + unknown
        ratio = synthetic / total if total > 0 else 0.0
        threshold = SYNTHETIC_THRESHOLDS.get(col_name, DEFAULT_THRESHOLD)

        avg_importance = {}
        for typ, imps in importance_by_type.items():
            if imps:
                avg_importance[typ] = round(sum(imps) / len(imps), 3)

        col_data = {
            "total": total,
            "canonical": canonical,
            "synthetic": synthetic,
            "unknown": unknown,
            "synthetic_ratio": round(ratio, 3),
            "threshold": threshold,
            "over_threshold": ratio > threshold,
            "avg_importance": avg_importance,
            "top_sources": dict(col_sources.most_common(5)),
        }
        results["collections"][col_name] = col_data

        results["totals"]["canonical"] += canonical
        results["totals"]["synthetic"] += synthetic
        results["totals"]["unknown"] += unknown
        results["totals"]["total"] += total

        if ratio > threshold:
            results["alerts"].append(
                f"{col_name}: synthetic ratio {ratio:.1%} exceeds threshold {threshold:.0%} "
                f"({synthetic}/{total} synthetic)"
            )

    # Overall synthetic ratio
    t = results["totals"]
    overall_ratio = t["synthetic"] / t["total"] if t["total"] > 0 else 0.0
    results["totals"]["synthetic_ratio"] = round(overall_ratio, 3)

    # Source distribution
    results["source_distribution"] = {
        src: {"count": count, "type": classify_source(src)}
        for src, count in source_counts.most_common(30)
    }

    return results


def audit_archived_vs_active():
    """Compare archived/pruned memories against active ones.

    Checks if active brain has high-importance canonical memories vs
    low-importance synthetic ones. Detects quality displacement.
    """
    from clarvis.brain import brain

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "low_importance_synthetic": [],
        "high_importance_canonical_at_risk": [],
        "importance_distribution": {},
        "quality_signals": {},
    }

    for col_name, col in brain.collections.items():
        col_results = col.get(include=["metadatas", "documents"], limit=col.count())
        metas = col_results.get("metadatas", [])
        docs = col_results.get("documents", [])

        low_imp_synthetic = []
        high_imp_canonical = []

        for i, meta in enumerate(metas):
            src = meta.get("source", "unknown")
            classification = classify_source(src)
            importance = meta.get("importance", 0.5)
            doc = (docs[i] or "")[:100] if i < len(docs) else ""

            if classification == "synthetic" and importance < 0.3:
                low_imp_synthetic.append({
                    "source": src,
                    "importance": round(importance, 3),
                    "preview": doc,
                })
            elif classification == "canonical" and importance >= 0.7:
                high_imp_canonical.append({
                    "source": src,
                    "importance": round(importance, 3),
                    "preview": doc,
                })

        # Report: low-importance synthetic that could be pruned
        if low_imp_synthetic:
            results["low_importance_synthetic"].append({
                "collection": col_name,
                "count": len(low_imp_synthetic),
                "samples": low_imp_synthetic[:3],
            })

        # Report: high-importance canonical that should be preserved
        if high_imp_canonical:
            results["high_importance_canonical_at_risk"].append({
                "collection": col_name,
                "count": len(high_imp_canonical),
            })

    # Summary quality signals
    total_low_synth = sum(r["count"] for r in results["low_importance_synthetic"])
    results["quality_signals"] = {
        "low_importance_synthetic_count": total_low_synth,
        "recommendation": (
            "PRUNE" if total_low_synth > 50
            else "MONITOR" if total_low_synth > 20
            else "HEALTHY"
        ),
    }

    return results


def run_full_audit():
    """Run both audits and return combined results."""
    ratio_audit = audit_memory_ratios()
    archive_audit = audit_archived_vs_active()

    combined = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ratios": ratio_audit,
        "archive_vs_active": archive_audit,
        "overall_health": "HEALTHY",
    }

    # Determine overall health
    if ratio_audit["alerts"]:
        combined["overall_health"] = "ALERT"
    if archive_audit["quality_signals"].get("recommendation") == "PRUNE":
        combined["overall_health"] = "ACTION_NEEDED"

    return combined


def record_audit(result):
    """Record audit result to history."""
    os.makedirs(os.path.dirname(AUDIT_HISTORY), exist_ok=True)

    entry = {
        "timestamp": result["timestamp"],
        "overall_health": result["overall_health"],
        "totals": result["ratios"]["totals"],
        "alerts_count": len(result["ratios"]["alerts"]),
        "low_imp_synthetic": result["archive_vs_active"]["quality_signals"]["low_importance_synthetic_count"],
    }

    with open(AUDIT_HISTORY, "a") as f:
        f.write(json.dumps(entry) + "\n")

    # Trim
    if os.path.exists(AUDIT_HISTORY):
        with open(AUDIT_HISTORY) as f:
            lines = f.readlines()
        if len(lines) > MAX_HISTORY:
            with open(AUDIT_HISTORY, "w") as f:
                f.writelines(lines[-MAX_HISTORY:])

    with open(AUDIT_FILE, "w") as f:
        json.dump(result, f, indent=2)


def format_audit(result):
    """Format audit results as a human-readable string."""
    lines = []
    lines.append("=== Memory Audit Report ===")
    lines.append(f"Timestamp: {result['timestamp']}")
    lines.append(f"Overall Health: {result['overall_health']}")
    lines.append("")

    # Ratios
    ratios = result["ratios"]
    t = ratios["totals"]
    lines.append(f"--- Canonical vs Synthetic Ratios ---")
    lines.append(f"Total: {t['total']} memories ({t['canonical']} canonical, {t['synthetic']} synthetic, {t['unknown']} unknown)")
    lines.append(f"Overall synthetic ratio: {t['synthetic_ratio']:.1%}")
    lines.append("")

    for col_name, data in sorted(ratios["collections"].items()):
        flag = " *** OVER THRESHOLD ***" if data["over_threshold"] else ""
        lines.append(
            f"  {col_name:25s}  total={data['total']:4d}  "
            f"canonical={data['canonical']:3d}  synthetic={data['synthetic']:3d}  "
            f"ratio={data['synthetic_ratio']:.1%} (threshold={data['threshold']:.0%}){flag}"
        )
        if data.get("avg_importance"):
            imp_parts = [f"{k}={v:.2f}" for k, v in data["avg_importance"].items()]
            lines.append(f"    avg_importance: {', '.join(imp_parts)}")

    # Alerts
    if ratios["alerts"]:
        lines.append("")
        lines.append("--- ALERTS ---")
        for alert in ratios["alerts"]:
            lines.append(f"  ! {alert}")

    # Archive vs active
    archive = result["archive_vs_active"]
    lines.append("")
    lines.append(f"--- Archive vs Active Quality ---")
    lines.append(f"Low-importance synthetic memories: {archive['quality_signals']['low_importance_synthetic_count']}")
    lines.append(f"Recommendation: {archive['quality_signals']['recommendation']}")

    if archive["low_importance_synthetic"]:
        lines.append("")
        for entry in archive["low_importance_synthetic"][:5]:
            lines.append(f"  {entry['collection']}: {entry['count']} low-importance synthetic")
            for sample in entry.get("samples", [])[:2]:
                lines.append(f"    [{sample['importance']:.2f}] {sample['source']}: {sample['preview'][:60]}")

    return "\n".join(lines)
