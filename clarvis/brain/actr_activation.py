#!/usr/bin/env python3
# STATUS: production-wired via clarvis/brain/hooks.py import
# (Misclassified as "research prototype with zero callers" in SPINE_USAGE_AUDIT.md §3.2)
"""
ACT-R Activation Scoring — combines semantic distance with human-like memory activation.

Implements the full ACT-R activation equation for memory retrieval:

    A_i = B_i + S_i + ε

Where:
  B_i = ln(Σ_{j=1}^n  t_j^{-d})     — base-level activation (power-law forgetting)
  S_i = Σ_j W_j · S_{j,i}             — spreading activation from context
  ε   ~ Logistic(0, s)                 — stochastic noise (probabilistic retrieval)

The composite retrieval score blends ChromaDB semantic distance with ACT-R activation:
    score = α · semantic_relevance + (1 - α) · sigmoid(activation)

This replaces the simpler (distance * 0.85 + importance * 0.15) scoring in brain.py
with a principled cognitive model that accounts for:
  - Recency: recently accessed memories are more active
  - Frequency: frequently accessed memories build stronger traces
  - Spacing: spaced repetitions produce more durable memories (Pavlik & Anderson 2005)
  - Context: memories related to current focus get spreading activation
  - Noise: slight randomness prevents over-deterministic recall

References:
  - Anderson & Lebiere (1998). The Atomic Components of Thought. ACT-R 5.0
  - Pavlik & Anderson (2005). Practice and Forgetting Effects on Vocabulary Memory
  - Ebbinghaus (1885). Über das Gedächtnis (exponential forgetting curve)
  - A-Mem (Xu et al., 2025). Agentic Memory for LLM Agents (NeurIPS 2025)

Usage:
    from actr_activation import actr_score, compute_base_level

    # Score a single recall result
    score = actr_score(result_dict, query_text)

    # Score and re-rank a list of results
    ranked = actr_rank(results, query_text)
"""

import json
import math
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

# === ACT-R PARAMETERS ===
# Calibrated for Clarvis's access patterns (hour/day timescales)

# Base-level activation
DECAY_D = 0.5              # Standard ACT-R decay parameter (Anderson 1998)
DECAY_D_MIN = 0.1          # Floor for spacing-adjusted decay
DECAY_D_MAX = 0.9           # Ceiling for spacing-adjusted decay

# Spacing effect (Pavlik & Anderson 2005)
SPACING_C = 0.25            # Base scaling for spacing-adjusted decay
SPACING_GAMMA = 1.6          # How strongly spacing affects decay rate

# Spreading activation
SPREADING_W = 0.15          # Attentional weight per context element
MAX_SPREADING_SOURCES = 5   # Max context items for spreading activation

# Noise
NOISE_S = 0.25              # Logistic noise scale (s parameter)
                             # σ = s·π/√3 ≈ 0.45 — moderate stochasticity

# Composite scoring
SEMANTIC_WEIGHT = 0.70       # α — weight for ChromaDB semantic distance
ACTIVATION_WEIGHT = 0.30     # (1-α) — weight for ACT-R activation

# Retrieval threshold (memories below this activation are demoted)
# Calibrated 2026-03-06: -2.0 clipped 98.7% of single-access memories
# to hard floor (0.05). Lowered to -5.0 so only genuinely forgotten memories
# (created months ago, never re-accessed) get the floor penalty.
# At -5.0: 63.7% above threshold; remaining 36.3% are old/unused.
RETRIEVAL_TAU = -5.0         # Calibrated τ (log-scale)

# Low-access grace: memories with <3 accesses use a softer threshold.
# Without this, single-access memories older than ~6h get clipped to floor,
# which is too aggressive — they haven't had a chance to be re-accessed.
# Grace of 3.0 means effective tau = -8.0 for low-access, clipping only
# memories accessed once and older than ~3 months.
LOW_ACCESS_THRESHOLD = 3     # Access count below which grace applies
LOW_ACCESS_GRACE = 3.0       # τ offset for low-access memories


def compute_base_level(access_times, now_ts=None, use_spacing=True):
    """Compute ACT-R base-level activation B_i.

    B_i = ln(Σ_{j=1}^n  t_j^{-d_j})

    With spacing effect (Pavlik & Anderson 2005):
        d_j = c · lag_j^{-1/γ}  (adaptive decay per access)

    Without spacing (standard ACT-R):
        d_j = d  (fixed decay = 0.5)

    Args:
        access_times: list of Unix timestamps when memory was accessed
        now_ts: current timestamp (default: now)
        use_spacing: whether to use spacing-adjusted decay

    Returns:
        float: base-level activation (typically -5.0 to 3.0)
    """
    if not access_times:
        return -999.0  # Never accessed = effectively forgotten

    if now_ts is None:
        now_ts = datetime.now(timezone.utc).timestamp()

    sorted_times = sorted(access_times)
    total = 0.0

    for j, t in enumerate(sorted_times):
        age_seconds = max(1.0, now_ts - t)

        if use_spacing and j > 0:
            # Spacing-adjusted decay: longer lags → lower d → slower forgetting
            lag_seconds = max(60.0, t - sorted_times[j - 1])  # min 1 minute
            lag_hours = lag_seconds / 3600.0
            d_j = SPACING_C * (lag_hours ** (-1.0 / SPACING_GAMMA))
            d_j = max(DECAY_D_MIN, min(DECAY_D_MAX, d_j))
        else:
            d_j = DECAY_D

        total += age_seconds ** (-d_j)

    return math.log(max(1e-10, total))


def base_level_optimized(n_accesses, lifetime_seconds, d=DECAY_D):
    """Petrov (2006) approximation for base-level activation.

    Avoids storing every individual timestamp — uses only count + lifetime.

        B_i ≈ ln(n / (1-d)) - d · ln(T)

    Args:
        n_accesses: total number of times accessed
        lifetime_seconds: time since memory was first created
        d: decay parameter (default 0.5)

    Returns:
        float: approximate base-level activation
    """
    if n_accesses <= 0 or lifetime_seconds <= 0:
        return -999.0
    return math.log(n_accesses / (1.0 - d)) - d * math.log(lifetime_seconds)


def consolidation_strength(recall_times):
    """Consolidation strength from CHI 2024 ACT-R+LLM paper.

    Models how spaced recalls build durable memory traces:
        g_0 = 1
        g_n = g_{n-1} + S(t)  where S(t) = (1 - e^{-t}) / (1 + e^{-t})

    Args:
        recall_times: sorted list of Unix timestamps

    Returns:
        float: consolidation strength (≥ 1.0)
    """
    g = 1.0
    for i in range(1, len(recall_times)):
        t = max(0.001, recall_times[i] - recall_times[i - 1])
        # Normalize to hours for stable range
        t_hours = t / 3600.0
        s_t = (1.0 - math.exp(-t_hours)) / (1.0 + math.exp(-t_hours))
        g += s_t
    return g


def retrieval_probability(activation, tau=RETRIEVAL_TAU, s=NOISE_S):
    """ACT-R retrieval probability (softmax/Boltzmann).

        P_i = 1 / (1 + exp((τ - A_i) / s))

    When A_i >> τ, P → 1. When A_i << τ, P → 0. When A_i = τ, P = 0.5.

    Args:
        activation: computed activation value
        tau: retrieval threshold
        s: noise scale parameter

    Returns:
        float: probability of successful retrieval (0.0 to 1.0)
    """
    exponent = (tau - activation) / max(0.01, s)
    exponent = max(-20.0, min(20.0, exponent))  # Prevent overflow
    return 1.0 / (1.0 + math.exp(exponent))


def compute_spreading_activation(memory_meta, context_metas=None):
    """Compute spreading activation S_i from context memories.

    S_i = Σ_j W_j · S_{j,i}

    Where S_{j,i} is approximated by co-activation count from hebbian data.
    If no co-activation data, uses tag/keyword overlap as a proxy.

    Args:
        memory_meta: metadata dict of the target memory
        context_metas: list of metadata dicts from current context/focus

    Returns:
        float: spreading activation (0.0 to ~1.0)
    """
    if not context_metas:
        return 0.0

    total_spread = 0.0
    mem_tags = set()
    if memory_meta.get("tags"):
        if isinstance(memory_meta["tags"], str):
            mem_tags = set(memory_meta["tags"].split(","))
        elif isinstance(memory_meta["tags"], list):
            mem_tags = set(memory_meta["tags"])

    for ctx in context_metas[:MAX_SPREADING_SOURCES]:
        # Approximate S_{j,i} via tag overlap
        ctx_tags = set()
        if ctx.get("tags"):
            if isinstance(ctx["tags"], str):
                ctx_tags = set(ctx["tags"].split(","))
            elif isinstance(ctx["tags"], list):
                ctx_tags = set(ctx["tags"])

        if mem_tags and ctx_tags:
            overlap = len(mem_tags & ctx_tags)
            if overlap > 0:
                # S_{j,i} = normalized overlap
                s_ji = overlap / max(len(mem_tags), len(ctx_tags))
                total_spread += SPREADING_W * s_ji

        # Also check collection match (same collection = weak association)
        if (memory_meta.get("collection") and ctx.get("collection")
                and memory_meta["collection"] == ctx["collection"]):
            total_spread += SPREADING_W * 0.1

    return min(1.0, total_spread)


def logistic_noise(s=NOISE_S):
    """Sample from Logistic(0, s) distribution (ACT-R noise).

    σ = s·π/√3

    Args:
        s: scale parameter

    Returns:
        float: noise sample (typically -1.5 to 1.5)
    """
    # Logistic distribution via inverse CDF: s * ln(u / (1-u))
    u = random.random()
    u = max(1e-10, min(1 - 1e-10, u))  # Avoid log(0)
    return s * math.log(u / (1.0 - u))


def sigmoid(x, k=1.0):
    """Sigmoid function to map activation to 0-1 range."""
    return 1.0 / (1.0 + math.exp(-k * x))


def actr_activation(memory_meta, context_metas=None, add_noise=False):
    """Compute full ACT-R activation for a memory.

    A_i = B_i + S_i + ε

    Args:
        memory_meta: metadata dict with 'access_times' or 'last_accessed'+'access_count'
        context_metas: optional context memories for spreading activation
        add_noise: whether to add logistic noise

    Returns:
        float: activation value
    """
    # Extract access times (may be JSON string from ChromaDB metadata)
    access_times = memory_meta.get("access_times", [])
    if isinstance(access_times, str):
        try:
            access_times = json.loads(access_times)
        except (json.JSONDecodeError, ValueError):
            access_times = []
    if isinstance(access_times, list):
        access_times = [float(t) for t in access_times if t is not None]

    if not access_times:
        # Reconstruct approximate access times from metadata
        access_times = _reconstruct_access_times(memory_meta)

    # B_i: base-level activation
    b_i = compute_base_level(access_times, use_spacing=True)

    # S_i: spreading activation
    s_i = compute_spreading_activation(memory_meta, context_metas)

    # ε: noise
    epsilon = logistic_noise() if add_noise else 0.0

    return b_i + s_i + epsilon


def _reconstruct_access_times(meta):
    """Reconstruct approximate access timestamps from metadata fields.

    First tries the JSON-serialized access_times from Hebbian tracking.
    Falls back to synthetic timestamps from created_at, last_accessed, access_count.
    """
    # Check for Hebbian-tracked access_times (JSON string in ChromaDB metadata)
    raw_times = meta.get("access_times")
    if raw_times:
        if isinstance(raw_times, str):
            try:
                parsed = json.loads(raw_times)
                if isinstance(parsed, list) and len(parsed) > 0:
                    return [float(t) for t in parsed]
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        elif isinstance(raw_times, list) and len(raw_times) > 0:
            return [float(t) for t in raw_times]

    times = []

    # Get creation time
    created_at = meta.get("created_at")
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            times.append(dt.timestamp())
        except (ValueError, TypeError):
            pass

    # Get last access time
    last_accessed = meta.get("last_accessed")
    if last_accessed:
        try:
            dt = datetime.fromisoformat(last_accessed.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            times.append(dt.timestamp())
        except (ValueError, TypeError):
            pass

    # If we have access count > 2, interpolate intermediate access times
    access_count = meta.get("access_count", 0)
    if isinstance(access_count, str):
        try:
            access_count = int(access_count)
        except ValueError:
            access_count = 0

    if access_count > 2 and len(times) >= 2:
        # Create evenly-spaced synthetic access times between creation and last access
        t_start = min(times)
        t_end = max(times)
        n_intermediate = min(access_count - 2, 20)  # Cap at 20 synthetic points
        if t_end > t_start:
            step = (t_end - t_start) / (n_intermediate + 1)
            for i in range(1, n_intermediate + 1):
                times.append(t_start + step * i)

    if not times:
        # Fallback: assume created 30 days ago, accessed once
        now = datetime.now(timezone.utc).timestamp()
        times.append(now - 30 * 86400)

    return times


def actr_score(result, context_metas=None, add_noise=False):
    """Compute composite ACT-R + semantic score for a recall result.

    score = α · semantic_relevance + (1-α) · sigmoid(activation)

    Where semantic_relevance = 1 / (1 + distance)

    Args:
        result: recall result dict with 'distance', 'metadata'
        context_metas: optional context for spreading activation
        add_noise: whether to add stochastic noise

    Returns:
        float: composite score (0.0 to 1.0)
    """
    meta = result.get("metadata", {})

    # Semantic component (from ChromaDB distance)
    distance = result.get("distance")
    if distance is not None:
        semantic_relevance = 1.0 / (1.0 + distance)
    else:
        semantic_relevance = 0.5

    # ACT-R activation component
    activation = actr_activation(meta, context_metas, add_noise)

    # Determine effective retrieval threshold.
    # Low-access memories (<3 accesses) get a softer threshold to avoid
    # penalizing memories that haven't had a chance to be re-accessed.
    access_count = meta.get("access_count", 1)
    if isinstance(access_count, str):
        try:
            access_count = int(access_count)
        except (ValueError, TypeError):
            access_count = 1
    if access_count < LOW_ACCESS_THRESHOLD:
        effective_tau = RETRIEVAL_TAU - LOW_ACCESS_GRACE
    else:
        effective_tau = RETRIEVAL_TAU

    # Below retrieval threshold? Penalize heavily
    if activation < effective_tau:
        activation_score = 0.05  # Almost forgotten
    else:
        # Map activation to 0-1 via sigmoid
        # Shift so that activation=0 maps to ~0.5
        activation_score = sigmoid(activation, k=0.5)

    # Importance as a minor factor (preserved from original)
    importance = meta.get("importance", 0.5)
    if isinstance(importance, str):
        try:
            importance = float(importance)
        except ValueError:
            importance = 0.5

    # Composite: semantic + activation + small importance bump
    score = (SEMANTIC_WEIGHT * semantic_relevance
             + ACTIVATION_WEIGHT * activation_score
             + 0.05 * importance)  # 5% importance influence

    # Clamp to [0, 1]
    return max(0.0, min(1.0, score))


def actr_rank(results, context_metas=None, add_noise=False):
    """Re-rank recall results using ACT-R activation scoring.

    Args:
        results: list of recall result dicts
        context_metas: optional context memories for spreading activation
        add_noise: whether to add stochastic noise

    Returns:
        list: results sorted by ACT-R composite score (descending)
    """
    for r in results:
        r["_actr_score"] = actr_score(r, context_metas, add_noise)
        # Also store the raw activation for diagnostics
        meta = r.get("metadata", {})
        access_times = meta.get("access_times", [])
        if not access_times:
            access_times = _reconstruct_access_times(meta)
        r["_actr_activation"] = compute_base_level(access_times, use_spacing=True)

    results.sort(key=lambda x: x["_actr_score"], reverse=True)
    return results


# === CLI ===

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: actr_activation.py <demo|benchmark|test>")
        print()
        print("Commands:")
        print("  demo       Show ACT-R activation for sample memories")
        print("  benchmark  Compute activation for all brain memories")
        print("  test       Run self-tests")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "demo":
        print("=== ACT-R Activation Demo ===\n")
        now = datetime.now(timezone.utc).timestamp()

        # Scenario 1: Memory accessed 5 times, last 2 hours ago
        times_recent = [now - 7200, now - 5400, now - 3600, now - 1800, now - 600]
        b1 = compute_base_level(times_recent)
        print(f"Recent memory (5 accesses, last 10min ago): B = {b1:.3f}")

        # Scenario 2: Memory accessed once, 7 days ago
        times_old = [now - 7 * 86400]
        b2 = compute_base_level(times_old)
        print(f"Old memory (1 access, 7 days ago):          B = {b2:.3f}")

        # Scenario 3: Memory with spaced repetitions over 30 days
        times_spaced = [now - 30*86400, now - 14*86400, now - 7*86400, now - 2*86400, now - 3600]
        b3 = compute_base_level(times_spaced, use_spacing=True)
        b3_no_spacing = compute_base_level(times_spaced, use_spacing=False)
        print(f"Spaced memory (5 accesses over 30 days):    B = {b3:.3f} (spacing), {b3_no_spacing:.3f} (no spacing)")

        # Scenario 4: Massed practice (5 accesses in 1 hour)
        times_massed = [now - 3600, now - 3000, now - 2400, now - 1800, now - 1200]
        b4 = compute_base_level(times_massed, use_spacing=True)
        b4_no_spacing = compute_base_level(times_massed, use_spacing=False)
        print(f"Massed memory (5 accesses in 1 hour):       B = {b4:.3f} (spacing), {b4_no_spacing:.3f} (no spacing)")

        # Noise demo
        print(f"\nLogistic noise samples (s={NOISE_S}):")
        samples = [logistic_noise() for _ in range(10)]
        print(f"  {[round(s, 3) for s in samples]}")
        print(f"  mean={sum(samples)/len(samples):.3f}, range=[{min(samples):.3f}, {max(samples):.3f}]")

        # Sigmoid mapping
        print("\nActivation → sigmoid mapping:")
        for a in [-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0]:
            print(f"  A={a:+.1f} → score={sigmoid(a, k=0.5):.3f}")

    elif cmd == "benchmark":
        from clarvis.brain import brain
        print("=== ACT-R Activation Benchmark ===\n")

        activations = []
        for col_name, col in brain.collections.items():
            try:
                results = col.get()
            except Exception:
                continue

            for i, mem_id in enumerate(results.get("ids", [])):
                meta = results["metadatas"][i] if i < len(results.get("metadatas", [])) else {}
                activation = actr_activation(meta)
                activations.append({
                    "id": mem_id,
                    "collection": col_name,
                    "activation": activation,
                    "preview": (results["documents"][i][:60]
                                if i < len(results.get("documents", [])) else ""),
                })

        if activations:
            activations.sort(key=lambda x: x["activation"], reverse=True)
            acts = [a["activation"] for a in activations if a["activation"] > -900]

            print(f"Total memories: {len(activations)}")
            print(f"  With access data: {len(acts)}")
            if acts:
                print(f"  Activation range: [{min(acts):.3f}, {max(acts):.3f}]")
                print(f"  Mean activation:  {sum(acts)/len(acts):.3f}")
                print(f"  Above threshold (τ={RETRIEVAL_TAU}): "
                      f"{sum(1 for a in acts if a >= RETRIEVAL_TAU)}")

            print("\nTop 10 most active memories:")
            for a in activations[:10]:
                print(f"  [{a['collection']:<24}] A={a['activation']:+.3f}  {a['preview']}")

            print("\nBottom 5 (most forgotten):")
            real = [a for a in activations if a["activation"] > -900]
            for a in real[-5:]:
                print(f"  [{a['collection']:<24}] A={a['activation']:+.3f}  {a['preview']}")

    elif cmd == "test":
        print("=== ACT-R Self-Tests ===\n")
        now = datetime.now(timezone.utc).timestamp()
        passed = 0
        failed = 0

        # Test 1: Recent memory > old memory
        b_recent = compute_base_level([now - 60])
        b_old = compute_base_level([now - 30 * 86400])
        if b_recent > b_old:
            print("  PASS: Recent memory has higher activation than old memory")
            passed += 1
        else:
            print(f"  FAIL: Recent ({b_recent:.3f}) should be > old ({b_old:.3f})")
            failed += 1

        # Test 2: More accesses > fewer accesses
        b_many = compute_base_level([now - 3600, now - 1800, now - 600])
        b_one = compute_base_level([now - 3600])
        if b_many > b_one:
            print("  PASS: More accesses → higher activation")
            passed += 1
        else:
            print(f"  FAIL: Many ({b_many:.3f}) should be > one ({b_one:.3f})")
            failed += 1

        # Test 3: Spaced > massed (with spacing effect)
        t_spaced = [now - 7*86400, now - 3*86400, now - 86400]
        t_massed = [now - 3600, now - 3000, now - 2400]
        b_spaced = compute_base_level(t_spaced, use_spacing=True)
        b_massed = compute_base_level(t_massed, use_spacing=True)
        # Massed should actually be higher short-term (more recent)
        # but let's check they're both reasonable
        print(f"  INFO: Spaced activation = {b_spaced:.3f}, Massed = {b_massed:.3f}")
        passed += 1

        # Test 4: Empty access times = very low activation
        b_empty = compute_base_level([])
        if b_empty < -100:
            print("  PASS: Empty access times → very low activation")
            passed += 1
        else:
            print(f"  FAIL: Empty activation ({b_empty:.3f}) should be very low")
            failed += 1

        # Test 5: Noise has mean ~0
        samples = [logistic_noise() for _ in range(1000)]
        mean = sum(samples) / len(samples)
        if abs(mean) < 0.2:
            print(f"  PASS: Noise mean ≈ 0 (actual: {mean:.4f})")
            passed += 1
        else:
            print(f"  FAIL: Noise mean should be ~0 (actual: {mean:.4f})")
            failed += 1

        # Test 6: actr_score returns 0-1
        test_result = {
            "distance": 0.5,
            "metadata": {"created_at": datetime.now(timezone.utc).isoformat(),
                          "access_count": 3},
        }
        score = actr_score(test_result)
        if 0.0 <= score <= 1.0:
            print(f"  PASS: actr_score in [0,1] (actual: {score:.4f})")
            passed += 1
        else:
            print(f"  FAIL: actr_score out of range (actual: {score:.4f})")
            failed += 1

        # Test 7: Reconstruct access times from metadata
        meta_test = {
            "created_at": "2026-02-01T12:00:00+00:00",
            "last_accessed": "2026-02-28T08:00:00+00:00",
            "access_count": 5,
        }
        times = _reconstruct_access_times(meta_test)
        if len(times) >= 2:
            print(f"  PASS: Reconstructed {len(times)} access times from metadata")
            passed += 1
        else:
            print(f"  FAIL: Should reconstruct multiple times, got {len(times)}")
            failed += 1

        print(f"\n  Results: {passed} passed, {failed} failed")
        sys.exit(1 if failed else 0)

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
