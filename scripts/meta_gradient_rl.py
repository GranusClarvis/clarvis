#!/usr/bin/env python3
"""
Meta-Gradient RL — Online self-tuning of Clarvis hyperparameters.

Implements three key ideas from Bundle Q research:

1. Meta-Gradient RL (Xu, van Hasselt & Silver, 2018, NeurIPS)
   Online cross-validation: update hyperparameters η using the gradient of
   performance on consecutive experience batches. The agent tunes its OWN
   discount factor γ and bootstrapping λ while interacting.

   Clarvis adaptation: treat task-selection weights, learning rates, and
   exploration parameters as meta-parameters η. After each heartbeat,
   evaluate how the previous η settings affected performance, then update
   η via meta-gradient to improve next-heartbeat outcomes.

2. Hierarchical RL Options Framework (Sutton, Precup & Singh, 1999)
   Temporal abstraction via "options" — macro-actions with initiation sets,
   internal policies, and termination conditions. Enables long-horizon
   planning by composing primitive actions into reusable subroutines.

   Clarvis adaptation: define task-bundle "options" (e.g., "research bundle"
   = research → ingest → wire; "fix bundle" = diagnose → fix → test).
   Track which options succeed, learn option-level value estimates.

3. Global Workspace Cross-Modal Transfer (Dossa/Maytié/Devillers/VanRullen, 2024, RLC)
   Policies trained via a Global Workspace transfer zero-shot across input
   modalities. Cycle-consistent representations are key — CLIP fails, GW succeeds.

   Clarvis adaptation: strategies learned in one domain (e.g., code fixing)
   may transfer to another (e.g., research) IF the underlying pattern matches.
   Track cross-domain strategy transfer success.

Usage:
    python3 meta_gradient_rl.py adapt           # Run one meta-gradient adaptation step
    python3 meta_gradient_rl.py options          # Show learned options and their values
    python3 meta_gradient_rl.py transfer         # Show cross-domain transfer matrix
    python3 meta_gradient_rl.py stats            # Full statistics
    python3 meta_gradient_rl.py recommend        # Get meta-gradient-informed recommendations

Integration:
    - heartbeat_postflight.py: called after each task to update meta-parameters
    - meta_learning.py: complements strategy analysis with gradient-based tuning
    - context_compressor.py: meta-gradient recommendations feed into decision context
    - world_models.py: hierarchical options provide temporal structure for predictions
"""

import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brain import brain, AUTONOMOUS_LEARNING

DATA_DIR = Path("/home/agent/.openclaw/workspace/data/meta_gradient_rl")
DATA_DIR.mkdir(parents=True, exist_ok=True)

PARAMS_FILE = DATA_DIR / "meta_params.json"
OPTIONS_FILE = DATA_DIR / "options.json"
TRANSFER_FILE = DATA_DIR / "transfer_matrix.json"
HISTORY_FILE = DATA_DIR / "adaptation_history.jsonl"
EPISODES_FILE = Path("/home/agent/.openclaw/workspace/data/episodes.json")

# Meta-learning rate (β in Xu et al.)
META_LR = 0.05
# Smoothing for exponential moving averages
EMA_ALPHA = 0.3
# Minimum episodes before adapting
MIN_EPISODES = 3


# ======================================================================
# 1. META-PARAMETERS η — the knobs we tune online
# ======================================================================

DEFAULT_META_PARAMS = {
    # Discount factor: how much to weigh future rewards vs immediate
    # High γ → long-horizon planning; Low γ → greedy/immediate
    "gamma": 0.9,

    # Bootstrapping parameter: TD(λ) mixing of n-step returns
    # High λ → Monte Carlo-like (use full episode returns)
    # Low λ → TD(0)-like (bootstrap from 1-step predictions)
    "lambda": 0.7,

    # Exploration vs exploitation (ε-greedy analogue)
    # High → more novel/research tasks; Low → exploit known-good strategies
    "exploration_rate": 0.3,

    # Strategy weights: how much to prefer each task type
    # Meta-gradient adjusts these based on observed returns
    "strategy_weights": {
        "build": 1.0,
        "fix": 1.0,
        "wire": 1.0,
        "improve": 1.0,
        "research": 1.0,
        "refactor": 1.0,
    },

    # Domain investment weights: where to allocate effort
    "domain_weights": {
        "memory_system": 1.0,
        "autonomous_execution": 1.0,
        "code_generation": 1.0,
        "self_reflection": 1.0,
        "consciousness_metrics": 1.0,
        "learning_feedback": 1.0,
    },

    # Salience threshold for task selection (cf. GWT ignition)
    "salience_threshold": 0.3,

    # Option termination bias: tendency to complete vs abort multi-step tasks
    "option_persistence": 0.7,
}


def load_meta_params() -> dict:
    """Load current meta-parameters (or defaults)."""
    if PARAMS_FILE.exists():
        try:
            with open(PARAMS_FILE) as f:
                saved = json.load(f)
            # Merge with defaults (in case new params added)
            params = {**DEFAULT_META_PARAMS, **saved}
            for key in ["strategy_weights", "domain_weights"]:
                params[key] = {**DEFAULT_META_PARAMS[key], **saved.get(key, {})}
            return params
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_META_PARAMS)


def save_meta_params(params: dict):
    """Persist meta-parameters."""
    with open(PARAMS_FILE, "w") as f:
        json.dump(params, f, indent=2)


def _load_episodes() -> list:
    """Load episode history."""
    if EPISODES_FILE.exists():
        try:
            with open(EPISODES_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _log_adaptation(record: dict):
    """Append adaptation record to history."""
    record["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


# ======================================================================
# 2. META-GRADIENT ADAPTATION (Xu et al. 2018)
# ======================================================================

def compute_returns(episodes: list, gamma: float, lam: float) -> list:
    """Compute TD(λ) returns for a sequence of episodes.

    Each episode has a 'reward' (derived from outcome: success=1, timeout=0.3, fail=0).
    We compute the λ-return: G_λ = Σ (1-λ)λ^(n-1) G^(n)
    where G^(n) = r_t + γr_{t+1} + ... + γ^(n-1)r_{t+n-1} + γ^n V(s_{t+n})

    Since we don't have a learned V, we use the EMA success rate as bootstrap.
    """
    if not episodes:
        return []

    # Convert episodes to rewards
    rewards = []
    for ep in episodes:
        outcome = ep.get("outcome", "failure")
        if outcome == "success":
            r = 1.0
        elif outcome == "timeout":
            r = 0.3
        else:
            r = 0.0

        # Duration penalty: tasks > 300s get penalized
        duration = ep.get("duration_s", 0)
        if duration > 300:
            r *= max(0.5, 1.0 - (duration - 300) / 600)

        rewards.append(r)

    # Bootstrap value = EMA of recent rewards
    ema = rewards[-1]
    for r in reversed(rewards[:-1]):
        ema = EMA_ALPHA * r + (1 - EMA_ALPHA) * ema
    V_bootstrap = ema

    # Compute λ-returns (backward pass)
    T = len(rewards)
    returns = [0.0] * T
    returns[-1] = rewards[-1] + gamma * V_bootstrap

    for t in range(T - 2, -1, -1):
        # TD target: r_t + γ V_{t+1}
        td_target = rewards[t] + gamma * returns[t + 1]
        # λ-return: (1-λ) TD + λ MC
        returns[t] = (1 - lam) * td_target + lam * (rewards[t] + gamma * returns[t + 1])

    return returns


def meta_gradient_step(params: dict, episodes: list) -> dict:
    """One step of meta-gradient adaptation.

    Online cross-validation (Xu et al.):
    1. Split recent episodes into τ (training) and τ' (validation)
    2. Compute returns on τ with current η
    3. Evaluate performance on τ' with updated θ
    4. Compute ∂J(τ')/∂η and update η

    Returns updated params and adaptation info.
    """
    if len(episodes) < MIN_EPISODES * 2:
        return params, {"status": "insufficient_data", "n_episodes": len(episodes)}

    # Use last N episodes, split into consecutive halves (online cross-validation)
    recent = episodes[-20:]
    mid = len(recent) // 2
    tau = recent[:mid]       # "training" batch
    tau_prime = recent[mid:] # "validation" batch

    gamma = params["gamma"]
    lam = params["lambda"]

    # Compute returns on both batches
    returns_tau = compute_returns(tau, gamma, lam)
    returns_tau_prime = compute_returns(tau_prime, gamma, lam)

    if not returns_tau or not returns_tau_prime:
        return params, {"status": "empty_returns"}

    # Performance = mean return on validation batch
    J_current = sum(returns_tau_prime) / len(returns_tau_prime)

    # Numerical meta-gradient: ∂J/∂γ and ∂J/∂λ
    eps = 0.01
    adaptations = {}

    # --- γ gradient ---
    returns_gamma_plus = compute_returns(tau_prime, min(1.0, gamma + eps), lam)
    returns_gamma_minus = compute_returns(tau_prime, max(0.0, gamma - eps), lam)
    J_gamma_plus = sum(returns_gamma_plus) / len(returns_gamma_plus)
    J_gamma_minus = sum(returns_gamma_minus) / len(returns_gamma_minus)
    grad_gamma = (J_gamma_plus - J_gamma_minus) / (2 * eps)

    new_gamma = gamma + META_LR * grad_gamma
    new_gamma = max(0.5, min(0.99, new_gamma))  # Clamp
    adaptations["gamma"] = {"old": gamma, "new": round(new_gamma, 4),
                            "grad": round(grad_gamma, 4)}

    # --- λ gradient ---
    returns_lam_plus = compute_returns(tau_prime, gamma, min(1.0, lam + eps))
    returns_lam_minus = compute_returns(tau_prime, gamma, max(0.0, lam - eps))
    J_lam_plus = sum(returns_lam_plus) / len(returns_lam_plus)
    J_lam_minus = sum(returns_lam_minus) / len(returns_lam_minus)
    grad_lam = (J_lam_plus - J_lam_minus) / (2 * eps)

    new_lam = lam + META_LR * grad_lam
    new_lam = max(0.0, min(1.0, new_lam))
    adaptations["lambda"] = {"old": lam, "new": round(new_lam, 4),
                             "grad": round(grad_lam, 4)}

    # --- Strategy weight gradients ---
    strategy_grads = _compute_strategy_gradients(tau, tau_prime, params)
    new_weights = dict(params["strategy_weights"])
    for strategy, grad in strategy_grads.items():
        old_w = new_weights.get(strategy, 1.0)
        new_w = old_w + META_LR * grad
        new_w = max(0.2, min(3.0, new_w))  # Clamp weights
        new_weights[strategy] = round(new_w, 3)
        adaptations[f"w_{strategy}"] = {"old": old_w, "new": new_w,
                                         "grad": round(grad, 4)}

    # --- Exploration rate gradient ---
    explore = params["exploration_rate"]
    # If validation performance is low, increase exploration; if high, decrease
    explore_signal = 0.5 - J_current  # positive when underperforming
    new_explore = explore + META_LR * explore_signal
    new_explore = max(0.1, min(0.6, new_explore))
    adaptations["exploration_rate"] = {"old": explore,
                                        "new": round(new_explore, 3),
                                        "signal": round(explore_signal, 3)}

    # Apply updates
    params["gamma"] = new_gamma
    params["lambda"] = new_lam
    params["strategy_weights"] = new_weights
    params["exploration_rate"] = new_explore

    info = {
        "status": "adapted",
        "J_validation": round(J_current, 4),
        "n_train": len(tau),
        "n_val": len(tau_prime),
        "adaptations": adaptations,
    }

    return params, info


def _compute_strategy_gradients(tau, tau_prime, params):
    """Compute gradient of validation performance w.r.t. strategy weights.

    Intuition: strategies that appear more in high-return validation episodes
    should get higher weight. Strategies in low-return episodes get lower weight.
    """
    STRATEGY_VERBS = {
        "build": ["build", "create", "implement", "add", "design"],
        "fix": ["fix", "repair", "debug", "resolve", "patch"],
        "wire": ["wire", "connect", "integrate", "hook", "link"],
        "improve": ["improve", "boost", "enhance", "optimize", "strengthen"],
        "research": ["research", "analyze", "study", "investigate", "audit"],
        "refactor": ["refactor", "clean", "consolidate", "reorganize", "restructure"],
    }

    # Score each strategy by its average return in validation episodes
    strategy_returns = defaultdict(list)

    for ep in tau_prime:
        task_lower = (ep.get("task") or "").lower()
        outcome = ep.get("outcome", "failure")
        reward = 1.0 if outcome == "success" else (0.3 if outcome == "timeout" else 0.0)

        for cat, verbs in STRATEGY_VERBS.items():
            if any(v in task_lower[:80] for v in verbs):
                strategy_returns[cat].append(reward)
                break

    # Gradient = (strategy_mean_return - overall_mean) / overall_std
    all_returns = [r for rs in strategy_returns.values() for r in rs]
    if not all_returns:
        return {}

    overall_mean = sum(all_returns) / len(all_returns)
    overall_var = sum((r - overall_mean) ** 2 for r in all_returns) / max(1, len(all_returns))
    overall_std = max(0.1, math.sqrt(overall_var))

    grads = {}
    for strategy, returns in strategy_returns.items():
        if returns:
            strat_mean = sum(returns) / len(returns)
            grads[strategy] = (strat_mean - overall_mean) / overall_std

    return grads


# ======================================================================
# 3. HIERARCHICAL OPTIONS (Sutton, Precup & Singh, 1999)
# ======================================================================

# An "option" is a temporally extended action: (initiation, policy, termination)
# For Clarvis: an option is a multi-step task bundle

DEFAULT_OPTIONS = {
    "research_bundle": {
        "description": "Research → Ingest → Store in brain",
        "steps": ["research", "ingest", "store"],
        "initiation": ["idle", "research_needed"],
        "termination": "all_steps_complete",
        "value": 0.5,
        "success_count": 0,
        "total_count": 0,
    },
    "fix_bundle": {
        "description": "Diagnose → Fix → Test → Verify",
        "steps": ["diagnose", "fix", "test", "verify"],
        "initiation": ["failure_detected", "bug_reported"],
        "termination": "all_steps_complete",
        "value": 0.5,
        "success_count": 0,
        "total_count": 0,
    },
    "build_bundle": {
        "description": "Design → Implement → Wire → Test",
        "steps": ["design", "implement", "wire", "test"],
        "initiation": ["feature_needed", "queue_item"],
        "termination": "all_steps_complete",
        "value": 0.5,
        "success_count": 0,
        "total_count": 0,
    },
    "improve_bundle": {
        "description": "Measure → Optimize → Validate",
        "steps": ["measure", "optimize", "validate"],
        "initiation": ["performance_low", "metric_below_target"],
        "termination": "all_steps_complete",
        "value": 0.5,
        "success_count": 0,
        "total_count": 0,
    },
    "wire_bundle": {
        "description": "Identify targets → Connect → Integration test",
        "steps": ["identify", "connect", "test"],
        "initiation": ["integration_needed"],
        "termination": "all_steps_complete",
        "value": 0.5,
        "success_count": 0,
        "total_count": 0,
    },
}


def load_options() -> dict:
    """Load learned option values."""
    if OPTIONS_FILE.exists():
        try:
            with open(OPTIONS_FILE) as f:
                saved = json.load(f)
            # Merge with defaults
            merged = dict(DEFAULT_OPTIONS)
            for k, v in saved.items():
                if k in merged:
                    merged[k].update(v)
                else:
                    merged[k] = v
            return merged
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_OPTIONS)


def save_options(options: dict):
    """Persist options."""
    with open(OPTIONS_FILE, "w") as f:
        json.dump(options, f, indent=2)


def update_option_values(options: dict, episodes: list, gamma: float) -> dict:
    """Update option value estimates from episodic data.

    For each option, find episodes that match its step pattern and
    compute the discounted return across the option's duration.
    Uses intra-option learning (Sutton & Precup, 1998): update value
    estimates from partial option trajectories, not just completions.
    """
    STEP_KEYWORDS = {
        "research": ["research", "study", "analyze", "investigate", "read"],
        "ingest": ["ingest", "store", "save", "write", "create"],
        "store": ["store", "brain", "memory", "persist"],
        "diagnose": ["diagnose", "investigate", "analyze", "debug", "root cause"],
        "fix": ["fix", "repair", "patch", "resolve"],
        "test": ["test", "verify", "validate", "check", "confirm"],
        "verify": ["verify", "confirm", "check", "ensure"],
        "design": ["design", "plan", "architect", "outline"],
        "implement": ["implement", "build", "create", "code", "write"],
        "wire": ["wire", "connect", "integrate", "hook"],
        "measure": ["measure", "benchmark", "profile", "assess"],
        "optimize": ["optimize", "improve", "boost", "enhance"],
        "validate": ["validate", "verify", "confirm"],
        "identify": ["identify", "find", "locate", "discover"],
        "connect": ["connect", "link", "wire", "integrate"],
    }

    for opt_name, opt in options.items():
        steps = opt.get("steps", [])
        if not steps:
            continue

        # Find episode sequences matching option steps
        matched_sequences = []
        current_seq = []
        current_step_idx = 0

        for ep in episodes:
            task_lower = (ep.get("task") or "").lower()

            if current_step_idx < len(steps):
                step = steps[current_step_idx]
                keywords = STEP_KEYWORDS.get(step, [step])
                if any(kw in task_lower for kw in keywords):
                    current_seq.append(ep)
                    current_step_idx += 1

                    if current_step_idx >= len(steps):
                        matched_sequences.append(list(current_seq))
                        current_seq = []
                        current_step_idx = 0
                else:
                    # Reset if pattern broken
                    if current_seq:
                        # Intra-option: still learn from partial sequence
                        if len(current_seq) >= 2:
                            matched_sequences.append(list(current_seq))
                    current_seq = []
                    current_step_idx = 0

        # Compute option values from matched sequences
        option_returns = []
        for seq in matched_sequences:
            G = 0.0
            for i, ep in enumerate(reversed(seq)):
                outcome = ep.get("outcome", "failure")
                r = 1.0 if outcome == "success" else (0.3 if outcome == "timeout" else 0.0)
                G = r + gamma * G
            # Normalize by sequence length
            option_returns.append(G / len(seq))

        if option_returns:
            # EMA update of option value
            new_value = sum(option_returns) / len(option_returns)
            old_value = opt.get("value", 0.5)
            opt["value"] = round(EMA_ALPHA * new_value + (1 - EMA_ALPHA) * old_value, 4)
            opt["success_count"] = sum(
                1 for seq in matched_sequences
                if all(ep.get("outcome") == "success" for ep in seq)
            )
            opt["total_count"] = len(matched_sequences)

    return options


def recommend_option(options: dict, context: str = "") -> dict:
    """Recommend the best option for the current context.

    Uses option values + context matching for initiation conditions.
    Returns the recommended option with its expected value.
    """
    best = None
    best_score = -1

    for name, opt in options.items():
        # Base score = learned value
        score = opt.get("value", 0.5)

        # Initiation bonus: if context matches initiation condition
        for init_cond in opt.get("initiation", []):
            if init_cond.replace("_", " ") in context.lower():
                score *= 1.5
                break

        # Count bonus: more data = more confident
        count = opt.get("total_count", 0)
        confidence = min(1.0, count / 5.0)
        score *= (0.5 + 0.5 * confidence)

        if score > best_score:
            best_score = score
            best = {"name": name, "score": round(score, 3), **opt}

    return best or {}


# ======================================================================
# 4. CROSS-DOMAIN TRANSFER MATRIX (Dossa et al. 2024)
# ======================================================================

DOMAINS = [
    "memory_system", "autonomous_execution", "code_generation",
    "self_reflection", "consciousness_metrics", "learning_feedback",
]

DOMAIN_KEYWORDS = {
    "memory_system": ["memory", "brain", "recall", "store", "retrieval"],
    "autonomous_execution": ["cron", "autonomous", "task", "heartbeat", "execute"],
    "code_generation": ["code", "script", "build", "implement", "create", "fix"],
    "self_reflection": ["reflect", "meta", "self", "awareness", "calibrat"],
    "consciousness_metrics": ["consciousness", "phi", "attention", "gwt", "workspace"],
    "learning_feedback": ["learn", "predict", "procedure", "feedback", "evolut"],
}


def build_transfer_matrix(episodes: list) -> dict:
    """Build a cross-domain strategy transfer matrix.

    Inspired by Dossa et al. 2024: strategies (policies) learned in one domain
    may transfer to another via a shared "workspace" representation.

    For each pair of domains (A, B), compute:
    - How often a strategy that succeeds in domain A also succeeds in domain B
    - This is the transfer coefficient T(A→B)

    A high T(A→B) means strategies from A generalize to B — the GW has learned
    modality-agnostic representations for these domains.
    """
    # Classify episodes by domain
    domain_episodes = defaultdict(list)
    for ep in episodes:
        task_lower = (ep.get("task") or "").lower()
        for domain, keywords in DOMAIN_KEYWORDS.items():
            if any(kw in task_lower for kw in keywords):
                domain_episodes[domain].append(ep)
                break

    # Strategy extraction
    STRATEGY_VERBS = {
        "build": ["build", "create", "implement", "add"],
        "fix": ["fix", "repair", "debug", "resolve"],
        "wire": ["wire", "connect", "integrate"],
        "improve": ["improve", "boost", "enhance", "optimize"],
        "research": ["research", "analyze", "study"],
        "refactor": ["refactor", "clean", "consolidate"],
    }

    def get_strategy(task: str) -> str:
        task_lower = task.lower()
        for cat, verbs in STRATEGY_VERBS.items():
            if any(v in task_lower[:60] for v in verbs):
                return cat
        return "other"

    # Per domain: compute success rate per strategy
    domain_strategy_success = {}
    for domain, eps in domain_episodes.items():
        strat_stats = defaultdict(lambda: {"success": 0, "total": 0})
        for ep in eps:
            strat = get_strategy(ep.get("task", ""))
            strat_stats[strat]["total"] += 1
            if ep.get("outcome") == "success":
                strat_stats[strat]["success"] += 1
        domain_strategy_success[domain] = dict(strat_stats)

    # Build transfer matrix T(A→B)
    # T(A→B) = correlation of strategy success rates between domain A and B
    matrix = {}
    for da in DOMAINS:
        matrix[da] = {}
        for db in DOMAINS:
            if da == db:
                matrix[da][db] = 1.0
                continue

            sa = domain_strategy_success.get(da, {})
            sb = domain_strategy_success.get(db, {})

            # Find shared strategies
            shared = set(sa.keys()) & set(sb.keys())
            if not shared:
                matrix[da][db] = 0.0
                continue

            # Compute correlation of success rates
            rates_a = []
            rates_b = []
            for strat in shared:
                ra = sa[strat]["success"] / max(1, sa[strat]["total"])
                rb = sb[strat]["success"] / max(1, sb[strat]["total"])
                rates_a.append(ra)
                rates_b.append(rb)

            if len(rates_a) < 2:
                # Not enough data — use simple overlap
                matrix[da][db] = round(len(shared) / max(1, len(set(sa.keys()) | set(sb.keys()))), 3)
                continue

            # Pearson correlation
            mean_a = sum(rates_a) / len(rates_a)
            mean_b = sum(rates_b) / len(rates_b)
            cov = sum((a - mean_a) * (b - mean_b) for a, b in zip(rates_a, rates_b))
            var_a = sum((a - mean_a) ** 2 for a in rates_a)
            var_b = sum((b - mean_b) ** 2 for b in rates_b)
            denom = math.sqrt(max(1e-10, var_a * var_b))
            corr = cov / denom
            # Normalize to [0, 1]
            matrix[da][db] = round(max(0, (corr + 1) / 2), 3)

    return matrix


def save_transfer_matrix(matrix: dict):
    """Persist transfer matrix."""
    with open(TRANSFER_FILE, "w") as f:
        json.dump(matrix, f, indent=2)


def get_transferable_strategies(matrix: dict, source_domain: str, threshold: float = 0.6) -> list:
    """Find domains where strategies from source_domain are likely to transfer.

    Based on Dossa: only high-transfer pairs (T > threshold) should be used.
    Low-transfer pairs may degrade performance (like CLIP vs GW).
    """
    if source_domain not in matrix:
        return []

    transfers = []
    for target, score in matrix[source_domain].items():
        if target != source_domain and score >= threshold:
            transfers.append({"target": target, "transfer_score": score})

    return sorted(transfers, key=lambda x: -x["transfer_score"])


# ======================================================================
# 5. UNIFIED ADAPTATION STEP
# ======================================================================

def adapt():
    """Run one full meta-gradient adaptation cycle.

    1. Load episodes and current meta-parameters
    2. Meta-gradient update on γ, λ, strategy weights, exploration rate
    3. Update hierarchical option values
    4. Rebuild cross-domain transfer matrix
    5. Generate recommendations
    6. Store insights in brain
    """
    episodes = _load_episodes()
    if not episodes:
        print("No episodes found. Skipping adaptation.")
        return {"status": "no_episodes"}

    params = load_meta_params()
    options = load_options()

    # Step 1: Meta-gradient adaptation
    params, adapt_info = meta_gradient_step(params, episodes)
    print(f"Meta-gradient: {adapt_info.get('status', 'unknown')}")

    if adapt_info.get("status") == "adapted":
        for key, vals in adapt_info.get("adaptations", {}).items():
            if isinstance(vals, dict) and "old" in vals:
                direction = "↑" if vals.get("new", 0) > vals.get("old", 0) else "↓"
                print(f"  {key}: {vals['old']:.3f} → {vals['new']:.3f} {direction}")
        print(f"  J(validation) = {adapt_info.get('J_validation', 0):.3f}")

    # Step 2: Option value updates
    options = update_option_values(options, episodes, params["gamma"])
    print("\nOption values:")
    for name, opt in options.items():
        count = opt.get("total_count", 0)
        val = opt.get("value", 0.5)
        print(f"  {name}: value={val:.3f} ({count} sequences)")

    # Step 3: Transfer matrix
    matrix = build_transfer_matrix(episodes)
    print("\nCross-domain transfer (T > 0.6):")
    for src in DOMAINS:
        transfers = get_transferable_strategies(matrix, src)
        if transfers:
            targets = ", ".join(f"{t['target']}({t['transfer_score']:.2f})" for t in transfers[:3])
            print(f"  {src} → {targets}")

    # Step 4: Recommendations
    recs = generate_recommendations(params, options, matrix, episodes)
    print("\nRecommendations:")
    for r in recs[:3]:
        print(f"  • {r}")

    # Save everything
    save_meta_params(params)
    save_options(options)
    save_transfer_matrix(matrix)
    _log_adaptation({
        "params": params,
        "adapt_info": adapt_info,
        "n_episodes": len(episodes),
        "option_values": {k: v.get("value", 0) for k, v in options.items()},
        "recommendations": recs[:3],
    })

    # Step 5: Store key insight in brain
    insight = _generate_brain_insight(params, adapt_info, options, matrix)
    if insight:
        try:
            brain.store(
                insight,
                importance=0.7,
                tags=["meta-gradient-rl", "self-tuning", "bundle-q"],
                collection=AUTONOMOUS_LEARNING,
            )
        except Exception as e:
            print(f"Brain store failed: {e}")

    return {
        "status": "complete",
        "params": params,
        "adapt_info": adapt_info,
        "option_values": {k: v.get("value", 0) for k, v in options.items()},
        "recommendations": recs,
    }


def generate_recommendations(params, options, matrix, episodes) -> list:
    """Generate actionable recommendations from meta-gradient analysis."""
    recs = []

    # From meta-params
    if params["exploration_rate"] > 0.4:
        recs.append("High exploration rate ({:.0%}) — performance below potential, try more diverse strategies".format(
            params["exploration_rate"]))
    elif params["exploration_rate"] < 0.15:
        recs.append("Low exploration rate ({:.0%}) — may be stuck in local optimum, consider novel tasks".format(
            params["exploration_rate"]))

    # From strategy weights
    weights = params.get("strategy_weights", {})
    if weights:
        best = max(weights, key=weights.get)
        worst = min(weights, key=weights.get)
        if weights[best] > 1.5 * weights[worst]:
            recs.append(f"Strategy imbalance: '{best}' ({weights[best]:.2f}) >> '{worst}' ({weights[worst]:.2f}) — investigate why '{worst}' underperforms")

    # From options
    for name, opt in options.items():
        if opt.get("total_count", 0) >= 3 and opt.get("value", 0.5) < 0.3:
            recs.append(f"Option '{name}' has low value ({opt['value']:.2f}) — consider restructuring its step sequence")

    # From transfer matrix
    high_transfer_pairs = []
    for src in DOMAINS:
        for tgt, score in matrix.get(src, {}).items():
            if src != tgt and score > 0.7:
                high_transfer_pairs.append((src, tgt, score))

    if high_transfer_pairs:
        best_pair = max(high_transfer_pairs, key=lambda x: x[2])
        recs.append(f"Strong transfer {best_pair[0]}→{best_pair[1]} ({best_pair[2]:.2f}) — strategies from one should work in the other (GW-style cross-modal transfer)")

    # From gamma/lambda
    if params["gamma"] > 0.95:
        recs.append(f"Very high γ ({params['gamma']:.3f}) — may be over-weighting distant future, consider shorter planning horizon")
    if params["gamma"] < 0.7:
        recs.append(f"Low γ ({params['gamma']:.3f}) — too greedy/short-sighted, increase long-term planning")

    return recs


def _generate_brain_insight(params, adapt_info, options, matrix) -> str:
    """Generate a concise insight string for brain storage."""
    if adapt_info.get("status") != "adapted":
        return ""

    parts = []
    J = adapt_info.get("J_validation", 0)
    parts.append(f"[META-GRADIENT-RL] Adaptation cycle: J={J:.3f}")

    # Notable parameter changes
    for key, vals in adapt_info.get("adaptations", {}).items():
        if isinstance(vals, dict) and abs(vals.get("grad", 0)) > 0.1:
            parts.append(f"{key}: {vals['old']:.3f}→{vals['new']:.3f}")

    # Best option
    best_opt = max(options.items(), key=lambda x: x[1].get("value", 0))
    parts.append(f"Best option: {best_opt[0]} (v={best_opt[1].get('value', 0):.3f})")

    return " | ".join(parts)


# ======================================================================
# 6. QUERY INTERFACE (for other modules)
# ======================================================================

def get_recommended_exploration_rate() -> float:
    """Get current meta-gradient-tuned exploration rate."""
    return load_meta_params().get("exploration_rate", 0.3)


def get_strategy_weight(strategy: str) -> float:
    """Get meta-gradient-tuned weight for a strategy."""
    return load_meta_params().get("strategy_weights", {}).get(strategy, 1.0)


def get_gamma() -> float:
    """Get current meta-learned discount factor."""
    return load_meta_params().get("gamma", 0.9)


def should_explore() -> bool:
    """Stochastic decision: should we explore or exploit?"""
    import random
    return random.random() < get_recommended_exploration_rate()


# ======================================================================
# CLI
# ======================================================================

def show_stats():
    """Show comprehensive meta-gradient RL stats."""
    params = load_meta_params()
    options = load_options()
    episodes = _load_episodes()
    matrix = build_transfer_matrix(episodes) if episodes else {}

    print("=== Meta-Gradient RL Statistics ===\n")

    print("Meta-Parameters (η):")
    print(f"  γ (discount):      {params['gamma']:.4f}")
    print(f"  λ (bootstrapping): {params['lambda']:.4f}")
    print(f"  ε (exploration):   {params['exploration_rate']:.3f}")
    print(f"  Salience threshold: {params['salience_threshold']:.3f}")
    print(f"  Option persistence: {params['option_persistence']:.3f}")

    print("\nStrategy Weights:")
    for s, w in sorted(params.get("strategy_weights", {}).items(), key=lambda x: -x[1]):
        bar = "█" * int(w * 10)
        print(f"  {s:12s}: {w:.3f} {bar}")

    print("\nHierarchical Options:")
    for name, opt in options.items():
        steps = " → ".join(opt.get("steps", []))
        val = opt.get("value", 0.5)
        count = opt.get("total_count", 0)
        print(f"  {name}: value={val:.3f} | {count} sequences | {steps}")

    if matrix:
        print("\nCross-Domain Transfer Matrix (T > 0.5):")
        for src in DOMAINS:
            row = matrix.get(src, {})
            high = [(t, s) for t, s in row.items() if t != src and s > 0.5]
            if high:
                pairs = ", ".join(f"{t}={s:.2f}" for t, s in sorted(high, key=lambda x: -x[1]))
                print(f"  {src}: {pairs}")

    # History
    if HISTORY_FILE.exists():
        lines = HISTORY_FILE.read_text().strip().split("\n")
        print(f"\nAdaptation history: {len(lines)} steps")
        if lines:
            try:
                last = json.loads(lines[-1])
                print(f"  Last run: {last.get('timestamp', 'unknown')}")
            except json.JSONDecodeError:
                pass

    print(f"\nEpisodes available: {len(episodes)}")


def show_options():
    """Show option details."""
    options = load_options()
    print("=== Hierarchical Options (Sutton-Precup-Singh) ===\n")
    for name, opt in options.items():
        steps = " → ".join(opt.get("steps", []))
        print(f"{name}:")
        print(f"  Description: {opt.get('description', '')}")
        print(f"  Steps: {steps}")
        print(f"  Value: {opt.get('value', 0.5):.3f}")
        print(f"  Sequences: {opt.get('total_count', 0)} total, {opt.get('success_count', 0)} fully successful")
        print(f"  Initiation: {', '.join(opt.get('initiation', []))}")
        print()


def show_transfer():
    """Show cross-domain transfer matrix."""
    episodes = _load_episodes()
    matrix = build_transfer_matrix(episodes)

    print("=== Cross-Domain Transfer Matrix (Dossa et al. 2024) ===")
    print("T(A→B) = likelihood that strategies from domain A transfer to B\n")

    # Header
    short = {d: d[:8] for d in DOMAINS}
    header = f"{'':>20s} " + " ".join(f"{short[d]:>8s}" for d in DOMAINS)
    print(header)
    print("-" * len(header))

    for src in DOMAINS:
        row = matrix.get(src, {})
        vals = []
        for tgt in DOMAINS:
            score = row.get(tgt, 0)
            if src == tgt:
                vals.append("  ----  ")
            elif score > 0.7:
                vals.append(f"  {score:.2f}★ ")
            elif score > 0.5:
                vals.append(f"  {score:.2f}  ")
            else:
                vals.append(f"  {score:.2f}  ")
        print(f"{short[src]:>20s} {''.join(vals)}")

    save_transfer_matrix(matrix)
    print("\nTransfer matrix saved. High-transfer pairs (★) indicate GW-like")
    print("modality-agnostic representations enabling zero-shot transfer.")


def show_recommend():
    """Show meta-gradient recommendations."""
    params = load_meta_params()
    options = load_options()
    episodes = _load_episodes()
    matrix = build_transfer_matrix(episodes) if episodes else {}

    recs = generate_recommendations(params, options, matrix, episodes)
    print("=== Meta-Gradient RL Recommendations ===\n")
    if recs:
        for i, r in enumerate(recs, 1):
            print(f"  {i}. {r}")
    else:
        print("  No recommendations yet (need more episodic data).")

    # Best option recommendation
    if options:
        best = recommend_option(options)
        if best:
            print(f"\n  Recommended next option: {best.get('name', '?')} (score={best.get('score', 0):.3f})")
            print(f"    {best.get('description', '')}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"

    if cmd == "adapt":
        result = adapt()
        if result.get("status") == "complete":
            print("\nAdaptation complete. Parameters saved.")
    elif cmd == "options":
        show_options()
    elif cmd == "transfer":
        show_transfer()
    elif cmd == "stats":
        show_stats()
    elif cmd == "recommend":
        show_recommend()
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python3 meta_gradient_rl.py [adapt|options|transfer|stats|recommend]")
        sys.exit(1)
