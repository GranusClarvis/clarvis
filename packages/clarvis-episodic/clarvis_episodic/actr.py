"""
ACT-R cognitive architecture primitives for episodic memory.

Implements:
- Base-level activation with adaptive decay (Pavlik & Anderson 2005)
- Emotional valence scoring with negativity bias and novelty detection

These functions are pure — no side effects, no storage dependencies.
They can be used independently of the EpisodicStore.

References:
    Anderson, J. R. (2007). How Can the Human Mind Occur in the Physical Universe?
    Pavlik, P. I., & Anderson, J. R. (2005). Practice and Forgetting Effects on
        Vocabulary Memory: An Activation-Based Model of the Spacing Effect.
"""

import math
from datetime import datetime, timezone
from typing import List, Optional


def compute_activation(
    access_times: List[float],
    now: Optional[float] = None,
    c: float = 0.5,
    gamma: float = 1.6,
    d_min: float = 0.1,
    d_max: float = 0.9,
) -> float:
    """Compute ACT-R base-level activation with adaptive decay.

    Standard ACT-R: A(i) = ln(sum(t_j^(-d))) with fixed d=0.5
    Pavlik extension: d_j = c * lag_j^(-1/gamma)

    The decay rate d itself follows a power law of the inter-retrieval lag.
    This captures the spacing effect:
    - Spaced repetitions -> lower d -> slower forgetting
    - Massed repetitions -> higher d -> faster forgetting

    Args:
        access_times: List of Unix timestamps when the episode was accessed.
        now: Current time as Unix timestamp (default: now).
        c: Base decay scaling factor.
        gamma: Spacing effect strength (typical ACT-R range: 1.0-2.0).
        d_min: Floor decay rate (prevents infinite memory).
        d_max: Ceiling decay rate (prevents instant forgetting).

    Returns:
        Base-level activation (log scale). Higher = more accessible.
        Typical range: -8 (forgotten) to +2 (very active).
    """
    if not access_times:
        return -10.0  # No accesses = effectively forgotten

    if now is None:
        now = datetime.now(timezone.utc).timestamp()

    sorted_times = sorted(access_times)
    total = 0.0

    for j, t in enumerate(sorted_times):
        age = max(1.0, now - t)

        # Inter-retrieval lag in hours (stable power-law range)
        if j == 0:
            lag_hours = age / 3600.0
        else:
            lag_hours = max(1.0 / 60.0, (t - sorted_times[j - 1]) / 3600.0)

        # Adaptive decay: d = c * lag_hours^(-1/gamma)
        d_j = c * (lag_hours ** (-1.0 / gamma))
        d_j = max(d_min, min(d_max, d_j))

        total += age ** (-d_j)

    return math.log(max(1e-10, total))


def compute_valence(
    outcome: str,
    salience: float,
    duration_s: float = 0,
    is_novel_error: bool = False,
) -> float:
    """Compute emotional valence (memorability) of an episode.

    Higher valence = more emotionally significant = worth remembering.
    Incorporates negativity bias (failures weighted more) and novelty.

    Args:
        outcome: "success", "failure", "soft_failure", or "timeout".
        salience: Task salience (0.0-1.0).
        duration_s: Task duration in seconds.
        is_novel_error: Whether the error is novel (not seen recently).

    Returns:
        Valence score (0.0-1.0).
    """
    valence = 0.3  # baseline

    # Negativity bias: failures are more memorable
    if outcome == "failure":
        valence += 0.3
    elif outcome in ("timeout", "soft_failure"):
        valence += 0.2

    # High-salience tasks are more memorable
    valence += float(salience) * 0.2

    # Long tasks are more memorable
    if duration_s > 300:
        valence += 0.1

    # Novel errors are more memorable
    if is_novel_error:
        valence += 0.1

    return min(1.0, valence)


def activation_threshold(n_episodes: int, percentile: float = 0.3) -> float:
    """Estimate activation threshold for "forgotten" episodes.

    Returns a threshold below which episodes are effectively forgotten.
    Based on the observation that activation is log-scale and episodes
    with activation < -4.0 are rarely useful.

    Args:
        n_episodes: Total number of episodes (used for adaptive scaling).
        percentile: What fraction of episodes to consider "forgotten".

    Returns:
        Activation threshold.
    """
    # With more episodes, we can afford a stricter threshold
    base = -4.0
    if n_episodes > 100:
        base = -3.5
    elif n_episodes > 500:
        base = -3.0
    return base
