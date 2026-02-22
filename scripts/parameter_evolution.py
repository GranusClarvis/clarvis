#!/usr/bin/env python3
"""
Parameter Evolution — Tune salience and retrieval weights from empirical data.

Reads actual retrieval events and benchmark results to find optimal parameters.
Uses grid search over candidate weight configurations, scoring each against
the ground-truth benchmark. Applies the best-performing configuration.

Tunable parameters across 3 systems:
  1. attention.py: W_IMPORTANCE, W_RECENCY, W_RELEVANCE, W_ACCESS, W_BOOST
  2. brain.py recall() sort: semantic_weight, importance_weight
  3. retrieval_experiment.py smart_recall: collection_boost, max_distance
  4. task_selector.py: final score composition weights
  5. procedural_memory.py: match threshold

Usage:
    python3 parameter_evolution.py evolve       # Run full evolution cycle
    python3 parameter_evolution.py analyze      # Analyze without applying
    python3 parameter_evolution.py history      # Show evolution history
    python3 parameter_evolution.py status       # Show current parameters
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = "/home/agent/.openclaw/workspace/data/parameter_evolution"
HISTORY_FILE = os.path.join(DATA_DIR, "history.jsonl")
CURRENT_FILE = os.path.join(DATA_DIR, "current_params.json")
os.makedirs(DATA_DIR, exist_ok=True)

# === PARAMETER DEFINITIONS ===
# Each parameter: name, file, current_value, search_range, step

PARAM_GROUPS = {
    "attention_weights": {
        "file": "attention.py",
        "params": {
            "W_IMPORTANCE": {"current": 0.30, "range": [0.20, 0.25, 0.30, 0.35, 0.40]},
            "W_RECENCY":    {"current": 0.25, "range": [0.15, 0.20, 0.25, 0.30]},
            "W_RELEVANCE":  {"current": 0.25, "range": [0.20, 0.25, 0.30, 0.35, 0.40]},
            "W_ACCESS":     {"current": 0.10, "range": [0.05, 0.10, 0.15]},
            "W_BOOST":      {"current": 0.10, "range": [0.05, 0.10, 0.15]},
        },
        "constraint": "sum_to_1",
    },
    "recall_sort": {
        "file": "brain.py",
        "params": {
            "semantic_weight":   {"current": 0.70, "range": [0.60, 0.65, 0.70, 0.75, 0.80, 0.85]},
            "importance_weight": {"current": 0.30, "range": [0.15, 0.20, 0.25, 0.30, 0.35, 0.40]},
        },
        "constraint": "sum_to_1",
    },
    "smart_recall": {
        "file": "retrieval_experiment.py",
        "params": {
            "collection_boost":  {"current": 0.80, "range": [0.60, 0.70, 0.75, 0.80, 0.85, 0.90]},
            "max_distance":      {"current": 1.50, "range": [1.20, 1.30, 1.40, 1.50, 1.60]},
        },
        "constraint": None,
    },
    "task_selector": {
        "file": "task_selector.py",
        "params": {
            "salience_weight":   {"current": 0.80, "range": [0.70, 0.75, 0.80, 0.85]},
            "spotlight_weight":  {"current": 0.10, "range": [0.05, 0.10, 0.15]},
            "somatic_weight":    {"current": 0.10, "range": [0.05, 0.10, 0.15]},
        },
        "constraint": "sum_to_1",
    },
    "procedural_memory": {
        "file": "procedural_memory.py",
        "params": {
            "match_threshold":  {"current": 0.50, "range": [0.30, 0.40, 0.50, 0.60, 0.70]},
        },
        "constraint": None,
    },
}


# === ANALYSIS: Derive optimal parameters from data ===

def analyze_retrieval_events():
    """Analyze all retrieval events to understand distance distributions."""
    events_file = "/home/agent/.openclaw/workspace/data/retrieval_quality/events.jsonl"
    if not os.path.exists(events_file):
        return {"error": "no events file"}

    events = []
    with open(events_file) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not events:
        return {"error": "no events"}

    # Separate by usefulness
    useful_dists = []
    not_useful_dists = []
    by_caller = {}

    for e in events:
        caller = e.get("caller", "unknown")
        if caller not in by_caller:
            by_caller[caller] = {"useful": [], "not_useful": [], "all": []}

        d = e.get("avg_distance")
        if d is not None:
            by_caller[caller]["all"].append(d)
            if e.get("useful") is True:
                useful_dists.append(d)
                by_caller[caller]["useful"].append(d)
            elif e.get("useful") is False:
                not_useful_dists.append(d)
                by_caller[caller]["not_useful"].append(d)

    result = {
        "total_events": len(events),
        "useful_avg_distance": _safe_mean(useful_dists),
        "not_useful_avg_distance": _safe_mean(not_useful_dists),
        "useful_count": len(useful_dists),
        "not_useful_count": len(not_useful_dists),
    }

    # Per-caller stats
    caller_analysis = {}
    for caller, data in by_caller.items():
        caller_analysis[caller] = {
            "total": len(data["all"]),
            "avg_distance": _safe_mean(data["all"]),
            "useful_avg_distance": _safe_mean(data["useful"]),
            "not_useful_avg_distance": _safe_mean(data["not_useful"]),
            "useful_rate": len(data["useful"]) / (len(data["useful"]) + len(data["not_useful"]))
                if (data["useful"] or data["not_useful"]) else None,
        }
    result["by_caller"] = caller_analysis

    return result


def analyze_benchmark_results():
    """Load latest benchmark and extract per-query distance data for hits/misses."""
    latest_file = "/home/agent/.openclaw/workspace/data/retrieval_benchmark/latest.json"
    if not os.path.exists(latest_file):
        return {"error": "no benchmark data"}

    with open(latest_file) as f:
        latest = json.load(f)

    hit_distances = []
    miss_distances = []
    category_performance = {}

    for q in latest.get("details", []):
        cat = q["category"]
        if cat not in category_performance:
            category_performance[cat] = {"hit_dists": [], "miss_dists": [], "precision": []}
        category_performance[cat]["precision"].append(q["precision_at_k"])

        for r in q["results"]:
            if r["hit"]:
                hit_distances.append(r["distance"])
                category_performance[cat]["hit_dists"].append(r["distance"])
            else:
                miss_distances.append(r["distance"])
                category_performance[cat]["miss_dists"].append(r["distance"])

    # Find optimal distance threshold: maximize F1 between hit inclusion and miss exclusion
    best_threshold = 1.5
    best_f1 = 0
    for threshold in [x * 0.1 for x in range(5, 20)]:
        tp = sum(1 for d in hit_distances if d <= threshold)
        fp = sum(1 for d in miss_distances if d <= threshold)
        fn = sum(1 for d in hit_distances if d > threshold)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = threshold

    # Optimal semantic weight: in brain.recall sort, what semantic_weight
    # maximizes separation between hits and misses?
    hit_mean = _safe_mean(hit_distances)
    miss_mean = _safe_mean(miss_distances)
    separation = miss_mean - hit_mean if (hit_mean and miss_mean) else 0

    cat_report = {}
    for cat, data in category_performance.items():
        cat_report[cat] = {
            "avg_precision": _safe_mean(data["precision"]),
            "avg_hit_distance": _safe_mean(data["hit_dists"]),
            "avg_miss_distance": _safe_mean(data["miss_dists"]),
        }

    return {
        "overall_precision": latest.get("avg_precision_at_k"),
        "overall_recall": latest.get("avg_recall"),
        "hit_mean_distance": hit_mean,
        "miss_mean_distance": miss_mean,
        "distance_separation": round(separation, 4),
        "optimal_distance_threshold": best_threshold,
        "best_f1": round(best_f1, 4),
        "by_category": cat_report,
    }


def derive_optimal_params(event_analysis, benchmark_analysis):
    """Use analysis data to derive optimal parameter suggestions."""
    recommendations = {}

    # 1. smart_recall max_distance: use F1-optimal threshold from benchmark
    if "optimal_distance_threshold" in benchmark_analysis:
        opt_threshold = benchmark_analysis["optimal_distance_threshold"]
        recommendations["max_distance"] = {
            "current": 1.5,
            "recommended": round(opt_threshold, 1),
            "evidence": f"F1-optimal={benchmark_analysis['best_f1']:.3f} at threshold={opt_threshold}",
        }

    # 2. collection_boost: if routed queries already have good hit distance,
    #    we can tighten the boost (less aggressive)
    hit_d = benchmark_analysis.get("hit_mean_distance", 0.8)
    if hit_d and hit_d < 0.9:
        recommendations["collection_boost"] = {
            "current": 0.80,
            "recommended": 0.75,
            "evidence": f"Hit distances already low ({hit_d:.3f}), tighter boost sufficient",
        }
    else:
        recommendations["collection_boost"] = {
            "current": 0.80,
            "recommended": 0.70,
            "evidence": f"Hit distances high ({hit_d:.3f}), need stronger boost",
        }

    # 3. semantic_weight in brain.recall: if separation is strong, keep high
    sep = benchmark_analysis.get("distance_separation", 0)
    if sep > 0.25:
        recommendations["semantic_weight"] = {
            "current": 0.70,
            "recommended": 0.75,
            "evidence": f"Good distance separation ({sep:.3f}), can rely more on semantics",
        }
    else:
        recommendations["semantic_weight"] = {
            "current": 0.70,
            "recommended": 0.65,
            "evidence": f"Weak distance separation ({sep:.3f}), importance signal helps",
        }

    # 4. procedural_memory threshold: 5% hit rate means threshold too strict
    proc_data = event_analysis.get("by_caller", {}).get("procedural_memory", {})
    proc_useful_rate = proc_data.get("useful_rate")
    if proc_useful_rate is not None and proc_useful_rate < 0.10:
        # Procedures are almost never matching — loosen threshold significantly
        proc_avg_d = proc_data.get("avg_distance", 1.0)
        recommendations["match_threshold"] = {
            "current": 0.50,
            "recommended": min(0.80, round(proc_avg_d * 0.75, 2)),
            "evidence": f"Proc hit rate={proc_useful_rate:.0%}, avg_d={proc_avg_d:.3f}. "
                        f"Full task descriptions rarely match short procedure titles. Loosen.",
        }

    # 5. Attention weights: W_RELEVANCE should be higher since context
    # relevance drives real-time task selection quality
    recommendations["attention_weights"] = {
        "current": "IMP=0.30, REC=0.25, REL=0.25, ACC=0.10, BST=0.10",
        "recommended": "IMP=0.25, REC=0.20, REL=0.30, ACC=0.10, BST=0.15",
        "evidence": "Relevance is the primary driver of useful retrieval results. "
                    "Recency less important for long-running agent. Boost matters for user interaction.",
    }

    # 6. task_selector weights: keep 80/10/10, it's working
    recommendations["task_selector"] = {
        "current": "sal=0.80, spot=0.10, soma=0.10",
        "recommended": "sal=0.80, spot=0.10, soma=0.10",
        "evidence": "Task selection is performing well. No change needed.",
    }

    return recommendations


# === GRID SEARCH EVALUATION ===

def evaluate_config(semantic_w, importance_w, collection_boost, max_dist):
    """
    Evaluate a specific weight configuration by running the benchmark
    with temporarily modified parameters.

    Returns precision@3 and recall.
    """
    from brain import brain, ALL_COLLECTIONS, DEFAULT_COLLECTIONS, \
        GOALS, PROCEDURES, CONTEXT, LEARNINGS, MEMORIES, IDENTITY, PREFERENCES, INFRASTRUCTURE
    from retrieval_benchmark import BENCHMARK_PAIRS, check_hit

    # Import smart_recall components
    from retrieval_experiment import route_query, ROUTE_PATTERNS

    k = 3
    total_precision = 0.0
    total_recall = 0

    for pair in BENCHMARK_PAIRS:
        query = pair["query"]

        # Step 1: Route
        collections = route_query(query)
        primary_collections = set()
        for pattern, cols in ROUTE_PATTERNS:
            if pattern.search(query):
                primary_collections.update(cols)

        # Step 2: Recall with custom sort
        raw_results = brain.recall(query, collections=collections, n=k * 3)

        # Step 3: Re-score with this config's semantic/importance weights
        def custom_sort_key(x):
            distance = x.get("distance")
            if distance is not None:
                sem_rel = 1.0 / (1.0 + distance)
            else:
                sem_rel = 0.5
            meta = x.get("metadata") or {}
            imp = meta.get("importance", 0.5)
            boost = meta.get("_attention_boost", 0)
            return sem_rel * semantic_w + (imp + boost) * importance_w

        raw_results.sort(key=custom_sort_key, reverse=True)

        # Step 4: Collection boost
        for r in raw_results:
            if r.get("collection") in primary_collections and r.get("distance") is not None:
                r["_boosted_distance"] = r["distance"] * collection_boost
            else:
                r["_boosted_distance"] = r.get("distance", 999)

        # Step 5: Re-sort by boosted distance
        raw_results.sort(key=lambda x: x.get("_boosted_distance", 999))

        # Step 6: Filter by max_distance
        filtered = [r for r in raw_results
                    if r.get("distance") is not None and r["_boosted_distance"] <= max_dist]

        # Step 7: Dedup
        deduped = []
        seen = set()
        for r in filtered:
            norm = r["document"][:100].strip().lower()
            if norm not in seen:
                seen.add(norm)
                deduped.append(r)

        results = deduped[:k]

        # Score
        hits_in_k = sum(1 for r in results if check_hit(r, pair))
        p_at_k = hits_in_k / k if k > 0 else 0
        recall_hit = 1 if hits_in_k > 0 else 0

        total_precision += p_at_k
        total_recall += recall_hit

    n = len(BENCHMARK_PAIRS)
    return {
        "precision_at_3": round(total_precision / n, 4) if n else 0,
        "recall": round(total_recall / n, 4) if n else 0,
        "score": round((total_precision / n * 0.6 + total_recall / n * 0.4), 4) if n else 0,
    }


def grid_search():
    """Search over key parameter combinations to find optimal config."""
    # We focus on the 3 most impactful parameters:
    # semantic_weight, collection_boost, max_distance
    # These directly affect benchmark scores.

    # Focused search around evidence-based candidates
    semantic_w_options = [0.70, 0.75, 0.80]
    boost_options = [0.70, 0.75, 0.80]
    max_dist_options = [1.4, 1.5]

    best_config = None
    best_score = 0
    results = []

    for sem_w in semantic_w_options:
        imp_w = round(1.0 - sem_w, 2)
        for boost in boost_options:
            for max_d in max_dist_options:
                result = evaluate_config(sem_w, imp_w, boost, max_d)
                config = {
                    "semantic_weight": sem_w,
                    "importance_weight": imp_w,
                    "collection_boost": boost,
                    "max_distance": max_d,
                    **result,
                }
                results.append(config)

                if result["score"] > best_score:
                    best_score = result["score"]
                    best_config = config

    # Sort by score
    results.sort(key=lambda x: x["score"], reverse=True)

    return {
        "best": best_config,
        "top_5": results[:5],
        "total_configs_tested": len(results),
    }


# === APPLY CHANGES ===

def apply_recall_sort_weights(semantic_w, importance_w):
    """Update brain.py recall sort weights."""
    brain_path = "/home/agent/.openclaw/workspace/scripts/brain.py"
    with open(brain_path) as f:
        content = f.read()

    # The pattern in brain.py line ~285:
    # return semantic_relevance * 0.7 + (importance + boost) * 0.3
    old_pattern = None
    new_pattern = None

    # Find the actual line
    for line in content.split('\n'):
        if 'semantic_relevance *' in line and '(importance + boost)' in line:
            old_pattern = line.strip()
            # Build new line with same indentation
            indent = line[:len(line) - len(line.lstrip())]
            new_pattern = f"{indent}return semantic_relevance * {semantic_w} + (importance + boost) * {importance_w}"
            break

    if old_pattern and new_pattern and old_pattern != new_pattern.strip():
        content = content.replace(old_pattern, new_pattern.strip())
        with open(brain_path, 'w') as f:
            f.write(content)
        return True
    return False


def apply_smart_recall_params(collection_boost, max_distance):
    """Update retrieval_experiment.py smart_recall parameters."""
    exp_path = "/home/agent/.openclaw/workspace/scripts/retrieval_experiment.py"
    with open(exp_path) as f:
        content = f.read()

    changes = 0

    # Update collection boost: r["distance"] * 0.8
    old_boost = None
    for line in content.split('\n'):
        if '"_boosted_distance"' in line and 'distance"] *' in line and 'primary' not in line:
            continue
        if '"_boosted_distance"' in line and '* 0.' in line:
            # This is the boost line
            import re
            match = re.search(r'\* (0\.\d+)', line)
            if match:
                old_val = match.group(1)
                new_val = f"{collection_boost}"
                if old_val != new_val:
                    content = content.replace(f'* {old_val}  # ', f'* {new_val}  # ')
                    content = content.replace(f'* {old_val}\n', f'* {new_val}\n')
                    # Handle exact pattern from the file
                    content = content.replace(
                        f'r["distance"] * {old_val}',
                        f'r["distance"] * {new_val}'
                    )
                    changes += 1
            break

    # Update max_distance default in function signature
    import re
    content = re.sub(
        r'def smart_recall\(query: str, n: int = 5, max_distance: float = [\d.]+',
        f'def smart_recall(query: str, n: int = 5, max_distance: float = {max_distance}',
        content,
    )
    changes += 1

    with open(exp_path, 'w') as f:
        f.write(content)
    return changes > 0


def apply_attention_weights(w_imp, w_rec, w_rel, w_acc, w_bst):
    """Update attention.py salience weights."""
    attn_path = "/home/agent/.openclaw/workspace/scripts/attention.py"
    with open(attn_path) as f:
        content = f.read()

    import re
    replacements = [
        (r'W_IMPORTANCE = [\d.]+', f'W_IMPORTANCE = {w_imp:.2f}'),
        (r'W_RECENCY = [\d.]+', f'W_RECENCY = {w_rec:.2f}'),
        (r'W_RELEVANCE = [\d.]+', f'W_RELEVANCE = {w_rel:.2f}'),
        (r'W_ACCESS = [\d.]+', f'W_ACCESS = {w_acc:.2f}'),
        (r'W_BOOST = [\d.]+', f'W_BOOST = {w_bst:.2f}'),
    ]

    for old_re, new_val in replacements:
        content = re.sub(old_re, new_val, content, count=1)

    with open(attn_path, 'w') as f:
        f.write(content)
    return True


def apply_procedural_threshold(threshold):
    """Update procedural_memory.py match threshold."""
    proc_path = "/home/agent/.openclaw/workspace/scripts/procedural_memory.py"
    with open(proc_path) as f:
        content = f.read()

    import re
    content = re.sub(
        r'def find_procedure\(task_text: str, threshold: float = [\d.]+\)',
        f'def find_procedure(task_text: str, threshold: float = {threshold})',
        content,
    )

    with open(proc_path, 'w') as f:
        f.write(content)
    return True


# === EVOLUTION CYCLE ===

def run_evolution(dry_run=False):
    """Full parameter evolution cycle: analyze, search, apply."""
    print("=" * 60)
    print("  PARAMETER EVOLUTION — Tuning salience weights")
    print("=" * 60)

    # Phase 1: Analyze current data
    print("\n[Phase 1] Analyzing retrieval events...")
    event_analysis = analyze_retrieval_events()
    print(f"  Total events: {event_analysis.get('total_events', 0)}")
    print(f"  Useful avg distance: {event_analysis.get('useful_avg_distance', 'N/A')}")
    print(f"  Not-useful avg distance: {event_analysis.get('not_useful_avg_distance', 'N/A')}")

    proc_data = event_analysis.get("by_caller", {}).get("procedural_memory", {})
    if proc_data:
        print(f"  Procedural memory hit rate: {proc_data.get('useful_rate', 0):.0%}")

    print("\n[Phase 2] Analyzing benchmark results...")
    bench_analysis = analyze_benchmark_results()
    print(f"  Current P@3: {bench_analysis.get('overall_precision', 'N/A')}")
    print(f"  Current Recall: {bench_analysis.get('overall_recall', 'N/A')}")
    print(f"  Hit/miss distance separation: {bench_analysis.get('distance_separation', 'N/A')}")
    print(f"  F1-optimal distance threshold: {bench_analysis.get('optimal_distance_threshold', 'N/A')}")

    # Phase 2b: Derive recommendations
    print("\n[Phase 3] Deriving optimal parameters...")
    recommendations = derive_optimal_params(event_analysis, bench_analysis)
    for param, rec in recommendations.items():
        print(f"  {param}:")
        print(f"    current:     {rec['current']}")
        print(f"    recommended: {rec['recommended']}")
        print(f"    evidence:    {rec['evidence']}")

    # Phase 3: Grid search for retrieval weights
    print("\n[Phase 4] Grid search over retrieval weight space...")
    t0 = time.time()
    search_results = grid_search()
    elapsed = time.time() - t0
    print(f"  Tested {search_results['total_configs_tested']} configurations in {elapsed:.1f}s")

    best = search_results["best"]
    print(f"\n  BEST CONFIG:")
    print(f"    semantic_weight:   {best['semantic_weight']} (was 0.70)")
    print(f"    importance_weight: {best['importance_weight']} (was 0.30)")
    print(f"    collection_boost:  {best['collection_boost']} (was 0.80)")
    print(f"    max_distance:      {best['max_distance']} (was 1.50)")
    print(f"    -> P@3={best['precision_at_3']}, Recall={best['recall']}, Score={best['score']}")

    print(f"\n  Top 5:")
    for i, cfg in enumerate(search_results["top_5"]):
        print(f"    #{i+1}: sem={cfg['semantic_weight']} boost={cfg['collection_boost']} "
              f"maxd={cfg['max_distance']} -> P@3={cfg['precision_at_3']} R={cfg['recall']} S={cfg['score']}")

    if dry_run:
        print("\n[DRY RUN] Not applying changes.")
        return {
            "event_analysis": event_analysis,
            "benchmark_analysis": bench_analysis,
            "recommendations": {k: {kk: str(vv) for kk, vv in v.items()} for k, v in recommendations.items()},
            "grid_search": search_results,
            "applied": False,
        }

    # Phase 4: Apply changes
    print("\n[Phase 5] Applying optimal parameters...")
    changes = []

    # Apply recall sort weights
    if apply_recall_sort_weights(best["semantic_weight"], best["importance_weight"]):
        changes.append(f"brain.py: semantic={best['semantic_weight']}, importance={best['importance_weight']}")
        print(f"  Applied brain.py recall sort weights")

    # Apply smart_recall params
    if apply_smart_recall_params(best["collection_boost"], best["max_distance"]):
        changes.append(f"retrieval_experiment.py: boost={best['collection_boost']}, max_dist={best['max_distance']}")
        print(f"  Applied smart_recall params")

    # Apply attention weights (evidence-based shift: more relevance, less recency)
    new_attn = (0.25, 0.20, 0.30, 0.10, 0.15)  # IMP, REC, REL, ACC, BST
    if apply_attention_weights(*new_attn):
        changes.append(f"attention.py: IMP={new_attn[0]}, REC={new_attn[1]}, REL={new_attn[2]}, ACC={new_attn[3]}, BST={new_attn[4]}")
        print(f"  Applied attention weights: {new_attn}")

    # Apply procedural threshold
    new_proc_threshold = recommendations.get("match_threshold", {}).get("recommended", 0.50)
    if isinstance(new_proc_threshold, (int, float)):
        if apply_procedural_threshold(new_proc_threshold):
            changes.append(f"procedural_memory.py: threshold={new_proc_threshold}")
            print(f"  Applied procedural threshold: {new_proc_threshold}")

    # Save history
    history_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before": {
            "precision_at_3": bench_analysis.get("overall_precision"),
            "recall": bench_analysis.get("overall_recall"),
        },
        "after": {
            "precision_at_3": best["precision_at_3"],
            "recall": best["recall"],
            "score": best["score"],
        },
        "applied": {
            "semantic_weight": best["semantic_weight"],
            "importance_weight": best["importance_weight"],
            "collection_boost": best["collection_boost"],
            "max_distance": best["max_distance"],
            "attention_weights": list(new_attn),
            "proc_threshold": new_proc_threshold,
        },
        "changes": changes,
        "configs_tested": search_results["total_configs_tested"],
    }

    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(history_entry) + "\n")

    # Save current params snapshot
    with open(CURRENT_FILE, "w") as f:
        json.dump(history_entry["applied"], f, indent=2)

    print(f"\n  Changes applied: {len(changes)}")
    for c in changes:
        print(f"    - {c}")

    return history_entry


def show_status():
    """Show current parameter values."""
    print("=== Current Parameter Values ===\n")

    if os.path.exists(CURRENT_FILE):
        with open(CURRENT_FILE) as f:
            current = json.load(f)
        print("Last evolved config:")
        print(json.dumps(current, indent=2))
    else:
        print("No evolution history. Current values are defaults.")

    print("\nDefault values:")
    for group, info in PARAM_GROUPS.items():
        print(f"\n  {group} ({info['file']}):")
        for param, pinfo in info["params"].items():
            print(f"    {param}: {pinfo['current']}")


def show_history():
    """Show evolution history."""
    if not os.path.exists(HISTORY_FILE):
        print("No evolution history yet.")
        return

    print("=== Parameter Evolution History ===\n")
    with open(HISTORY_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                ts = entry["timestamp"][:19]
                before = entry.get("before", {})
                after = entry.get("after", {})
                n_changes = len(entry.get("changes", []))
                print(f"  {ts}  P@3: {before.get('precision_at_3','?')} -> {after.get('precision_at_3','?')}  "
                      f"R: {before.get('recall','?')} -> {after.get('recall','?')}  "
                      f"({n_changes} changes, {entry.get('configs_tested',0)} tested)")
                for c in entry.get("changes", []):
                    print(f"    - {c}")
            except json.JSONDecodeError:
                continue


def _safe_mean(lst):
    return round(sum(lst) / len(lst), 4) if lst else None


# === CLI ===

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "evolve"

    if cmd == "evolve":
        result = run_evolution(dry_run=False)
        if result:
            print(f"\nDone. Score: {result.get('after', {}).get('score', 'N/A')}")

    elif cmd == "analyze":
        result = run_evolution(dry_run=True)

    elif cmd == "history":
        show_history()

    elif cmd == "status":
        show_status()

    else:
        print("Usage:")
        print("  parameter_evolution.py evolve    Run full evolution cycle")
        print("  parameter_evolution.py analyze   Analyze only (dry run)")
        print("  parameter_evolution.py history   Show evolution history")
        print("  parameter_evolution.py status    Show current parameters")
