#!/usr/bin/env python3
"""
World Models & Simulation Engine — Bundle C implementation.

Implements concepts from four key papers/frameworks:

1. Ha & Schmidhuber (2018) "World Models"
   - VAE-like compressed representation of environment (latent state z)
   - MDN-RNN for forward prediction (given z_t, a_t → predict z_{t+1})
   - Controller operates in latent space, not raw observation space
   - Here: compress episodic history into a latent "environment state",
     learn transition dynamics, predict next-state outcomes

2. LeCun — JEPA (Joint Embedding Predictive Architecture)
   - Predict in embedding space, not pixel space
   - Representations that capture abstract structure, discard noise
   - Here: embed tasks/outcomes into a shared representation,
     predict task outcomes via embedding similarity (not raw text matching)

3. Mind's Eye — Simulation-grounded reasoning
   - Mental simulation before acting: "imagine" the outcome
   - Run forward model N steps, evaluate candidate actions
   - Here: simulate multiple action paths, score them, pick the best

4. LeCun (2022) "A Path Towards Autonomous Machine Intelligence"
   - Hierarchical world model with multiple levels of abstraction
   - Configurator selects which modules to activate
   - Intrinsic motivation via prediction error (curiosity)
   - Here: hierarchical state (task-level, domain-level, system-level),
     curiosity signal from prediction errors drives exploration

Integration points:
  - episodic_memory.py: source of training data (episodes)
  - causal_model.py: SCM provides causal structure for predictions
  - dream_engine.py: uses world model for higher-fidelity counterfactuals
  - heartbeat_preflight.py: world model prediction informs task selection
  - clarvis_reasoning.py: Mind's Eye simulation augments reasoning chains

Usage:
    python3 world_models.py train          # Train world model from episodes
    python3 world_models.py predict <task>  # Predict outcome for a task
    python3 world_models.py simulate <task> # Mind's Eye: simulate action paths
    python3 world_models.py curiosity      # Show curiosity-ranked tasks
    python3 world_models.py stats          # Model statistics
    python3 world_models.py evaluate       # Evaluate prediction accuracy
"""

import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DATA_DIR = Path("/home/agent/.openclaw/workspace/data/world_model")
DATA_DIR.mkdir(parents=True, exist_ok=True)
MODEL_FILE = DATA_DIR / "world_model.json"
PREDICTIONS_LOG = DATA_DIR / "predictions.json"


# ======================================================================
# 1. Latent State Representation (Ha & Schmidhuber "World Models")
# ======================================================================

class LatentState:
    """Compressed representation of the cognitive environment.

    Instead of a VAE over pixels, this encodes the "state of the world"
    from Clarvis's perspective: recent outcomes, domain health, momentum,
    and resource utilization. This is z_t in the World Models framework.
    """

    # Feature extractors: each returns a float in [0, 1]
    FEATURES = [
        "success_rate_5",     # Recent success rate (last 5 episodes)
        "success_rate_20",    # Medium-term success rate (last 20)
        "domain_diversity",   # How many domains active recently
        "momentum",           # Streak direction (+success/-failure)
        "avg_duration_norm",  # Normalized average task duration
        "error_novelty",      # How novel recent errors are
        "time_of_day",        # Normalized hour (0=midnight, 0.5=noon)
        "cognitive_load",     # Estimated current load
    ]

    def __init__(self):
        self.z = [0.0] * len(self.FEATURES)
        self.feature_names = list(self.FEATURES)

    def encode(self, episodes, recent_n=20):
        """Encode recent episodes into latent state vector z.

        Like a VAE encoder: observations → z
        But deterministic (no sampling from posterior) since we're
        operating on discrete task data, not continuous images.
        """
        if not episodes:
            return self.z

        recent = episodes[-recent_n:]
        last_5 = episodes[-5:] if len(episodes) >= 5 else episodes

        # Feature 0: success_rate_5
        if last_5:
            self.z[0] = sum(1 for e in last_5 if e.get("outcome") == "success") / len(last_5)

        # Feature 1: success_rate_20
        if recent:
            self.z[1] = sum(1 for e in recent if e.get("outcome") == "success") / len(recent)

        # Feature 2: domain_diversity (entropy-like)
        sections = [e.get("section", "unknown") for e in recent]
        unique = len(set(sections))
        self.z[2] = min(1.0, unique / 6.0)  # normalize: 6+ domains = 1.0

        # Feature 3: momentum (streak)
        streak = 0
        for e in reversed(recent):
            if e.get("outcome") == "success":
                streak += 1
            else:
                streak -= 1
                break
        self.z[3] = max(0.0, min(1.0, (streak + 5) / 10.0))  # center at 0.5

        # Feature 4: avg_duration_norm
        durations = [e.get("duration_s", 60) for e in recent]
        avg_dur = sum(durations) / len(durations) if durations else 60
        self.z[4] = min(1.0, avg_dur / 600.0)  # 600s = full scale

        # Feature 5: error_novelty
        errors = [e.get("error", "") for e in recent if e.get("error")]
        if errors:
            unique_prefixes = len(set(e[:30] for e in errors))
            self.z[5] = min(1.0, unique_prefixes / max(1, len(errors)))
        else:
            self.z[5] = 0.0

        # Feature 6: time_of_day
        now = datetime.now(timezone.utc)
        self.z[6] = now.hour / 24.0

        # Feature 7: cognitive_load (proxy: tasks in last hour)
        try:
            one_hour_ago = now.timestamp() - 3600
            recent_tasks = sum(
                1 for e in episodes
                if e.get("timestamp", "") and
                datetime.fromisoformat(e["timestamp"]).timestamp() > one_hour_ago
            )
            self.z[7] = min(1.0, recent_tasks / 10.0)
        except (ValueError, TypeError):
            self.z[7] = 0.5

        return self.z

    def distance(self, other_z):
        """Euclidean distance between two latent states."""
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(self.z, other_z)))

    def to_dict(self):
        return {name: round(val, 4) for name, val in zip(self.feature_names, self.z)}


# ======================================================================
# 2. Transition Model (MDN-RNN / Forward Dynamics)
# ======================================================================

class TransitionModel:
    """Predicts next state given current state and action.

    In Ha & Schmidhuber, this is the MDN-RNN: P(z_{t+1} | z_t, a_t).
    Here we use a simpler learned transition table:
    - Group episodes by (domain, strategy) pairs
    - For each group, learn: mean outcome, variance, transition probabilities
    - This is a discrete MDN without the neural network — same principle.

    The key insight from World Models: the controller never sees raw data,
    it only operates on the latent state + transition model predictions.
    """

    def __init__(self):
        # Transition table: (domain, strategy) → outcome statistics
        self.transitions = {}
        # State history: list of (z_t, action, z_{t+1}) for learning
        self.state_history = []
        self.n_episodes_trained = 0

    def train(self, episodes):
        """Learn transition dynamics from episodic data.

        For each episode, record: what domain+strategy led to what outcome,
        and how the latent state changed.
        """
        self.transitions = {}

        for ep in episodes:
            domain = ep.get("section", "unknown")
            strategy = self._infer_strategy(ep.get("task", ""))
            outcome = ep.get("outcome", "unknown")
            duration = ep.get("duration_s", 0)

            key = (domain, strategy)
            if key not in self.transitions:
                self.transitions[key] = {
                    "outcomes": defaultdict(int),
                    "durations": [],
                    "total": 0,
                    "errors": [],
                }

            self.transitions[key]["outcomes"][outcome] += 1
            self.transitions[key]["durations"].append(duration)
            self.transitions[key]["total"] += 1
            if ep.get("error"):
                self.transitions[key]["errors"].append(ep["error"][:80])

        self.n_episodes_trained = len(episodes)

        # Also build state transition history
        encoder = LatentState()
        for i in range(1, len(episodes)):
            z_t = encoder.encode(episodes[:i])
            z_t1 = encoder.encode(episodes[:i + 1])
            action = self._infer_strategy(episodes[i].get("task", ""))
            self.state_history.append({
                "z_t": list(z_t),
                "action": action,
                "z_t1": list(z_t1),
                "domain": episodes[i].get("section", "unknown"),
            })

        return len(self.transitions)

    def predict(self, domain, strategy):
        """Predict outcome distribution: P(outcome | domain, strategy).

        Returns distribution + confidence based on sample size.
        """
        key = (domain, strategy)
        if key in self.transitions:
            t = self.transitions[key]
            total = t["total"]
            dist = {k: round(v / total, 3) for k, v in t["outcomes"].items()}
            avg_dur = sum(t["durations"]) / len(t["durations"]) if t["durations"] else 0
            most_likely = max(t["outcomes"], key=t["outcomes"].get)

            # Confidence scales with sample size (saturates at ~20)
            confidence = min(0.95, 1.0 - 1.0 / (total + 1))

            return {
                "prediction": most_likely,
                "distribution": dist,
                "confidence": round(confidence, 3),
                "avg_duration_s": round(avg_dur, 1),
                "n_samples": total,
                "common_errors": list(set(t["errors"]))[:3],
            }

        # Fallback: check domain-only (marginalize over strategies)
        domain_matches = {
            k: v for k, v in self.transitions.items() if k[0] == domain
        }
        if domain_matches:
            combined_outcomes = defaultdict(int)
            total = 0
            for v in domain_matches.values():
                for outcome, count in v["outcomes"].items():
                    combined_outcomes[outcome] += count
                total += v["total"]

            dist = {k: round(v / total, 3) for k, v in combined_outcomes.items()}
            most_likely = max(combined_outcomes, key=combined_outcomes.get)
            return {
                "prediction": most_likely,
                "distribution": dist,
                "confidence": round(min(0.8, 1.0 - 1.0 / (total + 1)), 3),
                "avg_duration_s": 0,
                "n_samples": total,
                "note": f"domain-level prediction (no exact match for strategy='{strategy}')",
            }

        # No data at all
        return {
            "prediction": "unknown",
            "distribution": {},
            "confidence": 0.0,
            "n_samples": 0,
            "note": "no training data for this domain+strategy",
        }

    def _infer_strategy(self, task):
        """Infer strategy from task text (shared with causal_model.py)."""
        words = task.lower().split()
        if any(w in words for w in ["fix", "repair", "debug"]):
            return "fix"
        elif any(w in words for w in ["implement", "build", "create", "add"]):
            return "implement"
        elif any(w in words for w in ["research", "investigate", "study", "analyze"]):
            return "research"
        elif any(w in words for w in ["optimize", "improve", "boost", "reduce"]):
            return "optimize"
        elif any(w in words for w in ["test", "benchmark", "verify"]):
            return "test"
        elif any(w in words for w in ["wire", "connect", "integrate"]):
            return "wire"
        return "unknown"

    def to_dict(self):
        result = {}
        for (domain, strategy), data in self.transitions.items():
            key = f"{domain}|{strategy}"
            result[key] = {
                "outcomes": dict(data["outcomes"]),
                "total": data["total"],
                "avg_duration": round(
                    sum(data["durations"]) / len(data["durations"]), 1
                ) if data["durations"] else 0,
            }
        return result


# ======================================================================
# 3. JEPA: Joint Embedding Predictive Architecture
# ======================================================================

class TaskEmbedding:
    """JEPA-inspired embedding space for tasks and outcomes.

    LeCun's JEPA insight: predict in *representation space*, not observation
    space. Instead of predicting raw task text, we embed tasks into a
    feature vector and predict outcome embeddings from task embeddings.

    The embedding captures abstract task structure:
    - What domain? What strategy? How complex?
    - What's the latent state context?
    - What resources are needed?

    Prediction happens by finding nearest neighbors in embedding space
    (similar tasks had similar outcomes) rather than exact text matching.
    """

    TASK_FEATURES = [
        "domain_idx",      # Numeric domain encoding
        "strategy_idx",    # Numeric strategy encoding
        "complexity",      # Word count / 20 (proxy for complexity)
        "has_error_ref",   # References fixing an error?
        "has_create_ref",  # Creating something new?
        "has_analysis",    # Analytical / investigative?
        "word_overlap_avg", # Average overlap with training tasks (novelty)
    ]

    DOMAINS = ["memory", "attention", "reasoning", "infrastructure",
               "consciousness", "automation", "research", "general", "unknown"]
    STRATEGIES = ["fix", "implement", "research", "optimize", "test", "wire", "unknown"]

    def __init__(self):
        self.task_vectors = []  # List of (embedding, outcome, task_text)

    def embed(self, task_text, domain="unknown"):
        """Encode a task description into embedding space."""
        words = task_text.lower().split()

        # Strategy inference
        strategy = "unknown"
        if any(w in words for w in ["fix", "repair", "debug"]):
            strategy = "fix"
        elif any(w in words for w in ["implement", "build", "create", "add"]):
            strategy = "implement"
        elif any(w in words for w in ["research", "investigate", "study", "analyze"]):
            strategy = "research"
        elif any(w in words for w in ["optimize", "improve", "boost", "reduce"]):
            strategy = "optimize"
        elif any(w in words for w in ["test", "benchmark", "verify"]):
            strategy = "test"
        elif any(w in words for w in ["wire", "connect", "integrate"]):
            strategy = "wire"

        vec = [
            self.DOMAINS.index(domain) / len(self.DOMAINS) if domain in self.DOMAINS else 0.5,
            self.STRATEGIES.index(strategy) / len(self.STRATEGIES) if strategy in self.STRATEGIES else 0.5,
            min(1.0, len(words) / 20.0),
            1.0 if any(w in words for w in ["error", "bug", "broken", "fail"]) else 0.0,
            1.0 if any(w in words for w in ["create", "new", "add", "build"]) else 0.0,
            1.0 if any(w in words for w in ["analyze", "investigate", "study", "review"]) else 0.0,
            self._novelty_score(words),
        ]
        return vec

    def _novelty_score(self, words):
        """How novel is this task compared to training data?

        High novelty = high prediction error = high curiosity signal.
        This implements LeCun's intrinsic motivation via prediction error.
        """
        if not self.task_vectors:
            return 1.0  # Everything is novel when untrained

        word_set = set(words)
        overlaps = []
        for emb, outcome, train_text in self.task_vectors:
            train_words = set(train_text.lower().split())
            if not train_words:
                continue
            overlap = len(word_set & train_words) / max(1, len(word_set | train_words))
            overlaps.append(overlap)

        if not overlaps:
            return 1.0
        avg_overlap = sum(overlaps) / len(overlaps)
        return 1.0 - avg_overlap  # High overlap = low novelty

    def train(self, episodes):
        """Build embedding space from episodic data."""
        self.task_vectors = []
        for ep in episodes:
            vec = self.embed(ep.get("task", ""), ep.get("section", "unknown"))
            self.task_vectors.append((vec, ep.get("outcome", "unknown"), ep.get("task", "")))
        return len(self.task_vectors)

    def predict_by_similarity(self, task_text, domain="unknown", k=5):
        """JEPA-style prediction: find k nearest neighbors in embedding space.

        Instead of predicting raw outcomes, we predict in the shared
        embedding space — finding tasks with similar representations
        and aggregating their outcomes.
        """
        if not self.task_vectors:
            return {"prediction": "unknown", "confidence": 0.0, "neighbors": []}

        query_vec = self.embed(task_text, domain)

        # Find k nearest neighbors by cosine-like distance
        scored = []
        for emb, outcome, train_task in self.task_vectors:
            dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(query_vec, emb)))
            scored.append((dist, outcome, train_task))

        scored.sort(key=lambda x: x[0])
        top_k = scored[:k]

        # Aggregate outcomes (weighted by inverse distance)
        outcome_weights = defaultdict(float)
        for dist, outcome, _ in top_k:
            weight = 1.0 / (dist + 0.01)
            outcome_weights[outcome] += weight

        total_weight = sum(outcome_weights.values())
        dist_norm = {k: round(v / total_weight, 3) for k, v in outcome_weights.items()}
        best = max(outcome_weights, key=outcome_weights.get)

        return {
            "prediction": best,
            "distribution": dist_norm,
            "confidence": round(dist_norm.get(best, 0), 3),
            "neighbors": [
                {"task": t[:60], "outcome": o, "distance": round(d, 4)}
                for d, o, t in top_k
            ],
            "novelty": round(query_vec[-1], 3),  # Last feature = novelty
        }


# ======================================================================
# 4. Mind's Eye: Simulation-Grounded Reasoning
# ======================================================================

class MindsEye:
    """Mental simulation engine — imagine outcomes before acting.

    The Mind's Eye concept: before executing an action, run it through
    the world model to predict what will happen. Compare multiple
    candidate actions by simulating each one.

    This augments the dream_engine (which looks backward at past episodes)
    with forward-looking simulation (predicting outcomes of proposed actions).
    """

    def __init__(self, transition_model, jepa_model, latent_encoder):
        self.transition = transition_model
        self.jepa = jepa_model
        self.encoder = latent_encoder

    def simulate(self, candidate_tasks, episodes, domain="unknown"):
        """Simulate multiple candidate tasks, return ranked results.

        For each candidate:
        1. Predict outcome via transition model (causal dynamics)
        2. Predict outcome via JEPA (embedding similarity)
        3. Estimate curiosity value (prediction uncertainty)
        4. Combine into expected utility score

        Returns candidates ranked by expected utility.
        """
        # Encode current state
        self.encoder.encode(episodes)

        results = []
        for task_text in candidate_tasks:
            strategy = self.transition._infer_strategy(task_text)

            # Prediction 1: Transition model (causal dynamics)
            trans_pred = self.transition.predict(domain, strategy)

            # Prediction 2: JEPA (embedding neighbors)
            jepa_pred = self.jepa.predict_by_similarity(task_text, domain)

            # Ensemble: average the two prediction sources
            combined_dist = defaultdict(float)
            for source in [trans_pred, jepa_pred]:
                for outcome, prob in source.get("distribution", {}).items():
                    combined_dist[outcome] += prob * 0.5

            # Normalize
            total = sum(combined_dist.values())
            if total > 0:
                combined_dist = {k: round(v / total, 3) for k, v in combined_dist.items()}

            # Expected utility: P(success) - P(failure) + curiosity_bonus
            p_success = combined_dist.get("success", 0)
            p_failure = combined_dist.get("failure", 0) + combined_dist.get("timeout", 0)
            curiosity = jepa_pred.get("novelty", 0.5)

            # Curiosity bonus (LeCun's intrinsic motivation):
            # Novel tasks are worth exploring even if success is uncertain
            curiosity_bonus = curiosity * 0.15  # 15% weight on exploration

            expected_utility = p_success - 0.5 * p_failure + curiosity_bonus

            results.append({
                "task": task_text,
                "strategy": strategy,
                "expected_utility": round(expected_utility, 4),
                "p_success": round(p_success, 3),
                "p_failure": round(p_failure, 3),
                "curiosity": round(curiosity, 3),
                "transition_prediction": trans_pred.get("prediction", "unknown"),
                "jepa_prediction": jepa_pred.get("prediction", "unknown"),
                "combined_distribution": dict(combined_dist),
                "confidence": round(
                    (trans_pred.get("confidence", 0) + jepa_pred.get("confidence", 0)) / 2,
                    3
                ),
            })

        # Rank by expected utility (highest first)
        results.sort(key=lambda x: x["expected_utility"], reverse=True)
        return results


# ======================================================================
# 5. Hierarchical World Model (LeCun AMI Architecture)
# ======================================================================

class HierarchicalWorldModel:
    """LeCun's hierarchical world model with curiosity-driven exploration.

    Three levels of abstraction:
    1. Task-level:   per-task predictions (what will this task outcome be?)
    2. Domain-level:  per-domain health (is this domain improving/degrading?)
    3. System-level:  global cognitive state (overall trajectory)

    The Configurator (from LeCun's AMI paper) decides which level
    of the hierarchy is most relevant for a given decision.

    Curiosity signal: prediction errors at each level drive exploration.
    High prediction error = the model is wrong = learn here.
    """

    def __init__(self):
        self.latent = LatentState()
        self.transition = TransitionModel()
        self.jepa = TaskEmbedding()
        self.minds_eye = MindsEye(self.transition, self.jepa, self.latent)

        # Prediction tracking for curiosity
        self.predictions = []  # [{task, predicted, actual, error, timestamp}]
        self.domain_health = {}  # domain → {trend, recent_rate, prediction_error}
        self.system_state = {}   # global metrics

    def train(self, episodes):
        """Train all components of the hierarchical world model."""
        results = {}

        # 1. Train transition model (task-level dynamics)
        n_transitions = self.transition.train(episodes)
        results["transitions_learned"] = n_transitions

        # 2. Train JEPA embeddings
        n_embeddings = self.jepa.train(episodes)
        results["embeddings_built"] = n_embeddings

        # 3. Encode current latent state
        self.latent.encode(episodes)
        results["latent_state"] = self.latent.to_dict()

        # 4. Compute domain-level health (hierarchical abstraction)
        self._compute_domain_health(episodes)
        results["domain_health"] = self.domain_health

        # 5. Compute system-level state
        self._compute_system_state(episodes)
        results["system_state"] = self.system_state

        # 6. Load prediction history for curiosity scoring
        self._load_predictions()
        results["prediction_history_size"] = len(self.predictions)

        results["n_episodes"] = len(episodes)
        results["trained_at"] = datetime.now(timezone.utc).isoformat()
        return results

    def predict(self, task_text, domain="unknown"):
        """Full hierarchical prediction for a task.

        Combines task-level, domain-level, and system-level signals.
        """
        # Task-level predictions
        strategy = self.transition._infer_strategy(task_text)
        trans = self.transition.predict(domain, strategy)
        jepa = self.jepa.predict_by_similarity(task_text, domain)

        # Domain-level context
        dh = self.domain_health.get(domain, {})
        domain_trend = dh.get("trend", "stable")
        domain_rate = dh.get("recent_success_rate", 0.5)

        # System-level context
        sys_momentum = self.system_state.get("momentum", "neutral")

        # Combine into final prediction
        p_success_trans = trans.get("distribution", {}).get("success", 0.5)
        p_success_jepa = jepa.get("distribution", {}).get("success", 0.5)

        # Weight by confidence
        w_trans = trans.get("confidence", 0.1)
        w_jepa = jepa.get("confidence", 0.1)
        total_w = w_trans + w_jepa + 0.01

        p_success = (p_success_trans * w_trans + p_success_jepa * w_jepa) / total_w

        # Domain-level adjustment (±10%)
        if domain_trend == "improving":
            p_success = min(1.0, p_success * 1.1)
        elif domain_trend == "degrading":
            p_success *= 0.9

        # System-level adjustment (±5%)
        if sys_momentum == "positive":
            p_success = min(1.0, p_success * 1.05)
        elif sys_momentum == "negative":
            p_success *= 0.95

        prediction = "success" if p_success >= 0.5 else "failure"

        # Curiosity: how surprising would each outcome be?
        curiosity = jepa.get("novelty", 0.5)
        domain_pred_error = dh.get("prediction_error", 0.5)
        curiosity_score = 0.6 * curiosity + 0.4 * domain_pred_error

        result = {
            "task": task_text[:100],
            "prediction": prediction,
            "p_success": round(p_success, 3),
            "confidence": round(total_w / 2.0, 3),
            "curiosity": round(curiosity_score, 3),
            "strategy": strategy,
            "domain": domain,
            "hierarchy": {
                "task_level": {
                    "transition": trans.get("prediction", "?"),
                    "jepa": jepa.get("prediction", "?"),
                },
                "domain_level": {
                    "trend": domain_trend,
                    "recent_rate": round(domain_rate, 3),
                },
                "system_level": {
                    "momentum": sys_momentum,
                    "latent_state": self.latent.to_dict(),
                },
            },
        }

        # Log prediction for later accuracy evaluation
        self._log_prediction(task_text, prediction, p_success, curiosity_score, domain)

        return result

    def simulate_candidates(self, candidate_tasks, episodes, domain="unknown"):
        """Mind's Eye: simulate and rank candidate tasks."""
        return self.minds_eye.simulate(candidate_tasks, episodes, domain)

    def record_outcome(self, task_text, actual_outcome):
        """Record actual outcome — feeds back into curiosity signal.

        High prediction error → high curiosity → explore this domain more.
        """
        self._load_predictions()

        for pred in reversed(self.predictions):
            if pred["task"][:60] == task_text[:60] and pred.get("actual") is None:
                pred["actual"] = actual_outcome
                pred["error"] = 0.0 if pred["predicted"] == actual_outcome else 1.0
                pred["resolved_at"] = datetime.now(timezone.utc).isoformat()
                break

        self._save_predictions()

    def get_curiosity_ranking(self):
        """Rank domains by curiosity signal (prediction error).

        Domains where the model is wrong most often → highest curiosity →
        most valuable to explore (LeCun's intrinsic motivation).
        """
        self._load_predictions()
        resolved = [p for p in self.predictions if p.get("actual") is not None]

        if not resolved:
            return {"domains": {}, "note": "no resolved predictions yet"}

        domain_errors = defaultdict(list)
        for p in resolved:
            domain_errors[p.get("domain", "unknown")].append(p.get("error", 0))

        ranking = {}
        for domain, errors in domain_errors.items():
            avg_error = sum(errors) / len(errors)
            ranking[domain] = {
                "prediction_error": round(avg_error, 3),
                "n_predictions": len(errors),
                "curiosity_rank": "high" if avg_error > 0.4 else (
                    "medium" if avg_error > 0.2 else "low"
                ),
            }

        # Sort by prediction error (highest = most curious)
        sorted_domains = sorted(ranking.items(),
                                key=lambda x: x[1]["prediction_error"],
                                reverse=True)

        return {
            "domains": dict(sorted_domains),
            "most_curious": sorted_domains[0][0] if sorted_domains else None,
            "total_resolved": len(resolved),
        }

    def evaluate_accuracy(self):
        """Evaluate world model prediction accuracy."""
        self._load_predictions()
        resolved = [p for p in self.predictions if p.get("actual") is not None]

        if not resolved:
            return {"accuracy": None, "n": 0, "note": "no resolved predictions"}

        correct = sum(1 for p in resolved if p.get("error", 1) == 0.0)
        total = len(resolved)

        # By domain
        domain_accuracy = defaultdict(lambda: {"correct": 0, "total": 0})
        for p in resolved:
            d = p.get("domain", "unknown")
            domain_accuracy[d]["total"] += 1
            if p.get("error", 1) == 0.0:
                domain_accuracy[d]["correct"] += 1

        domain_results = {
            d: round(v["correct"] / v["total"], 3) if v["total"] > 0 else 0
            for d, v in domain_accuracy.items()
        }

        return {
            "accuracy": round(correct / total, 3),
            "correct": correct,
            "total": total,
            "domain_accuracy": domain_results,
        }

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------

    def _compute_domain_health(self, episodes):
        """Compute domain-level abstraction: health trends per domain."""
        domain_episodes = defaultdict(list)
        for ep in episodes:
            domain_episodes[ep.get("section", "unknown")].append(ep)

        self.domain_health = {}
        for domain, eps in domain_episodes.items():
            recent = eps[-10:]
            older = eps[-20:-10] if len(eps) > 10 else []

            recent_rate = sum(1 for e in recent if e.get("outcome") == "success") / max(1, len(recent))
            older_rate = sum(1 for e in older if e.get("outcome") == "success") / max(1, len(older)) if older else recent_rate

            delta = recent_rate - older_rate
            trend = "improving" if delta > 0.1 else ("degrading" if delta < -0.1 else "stable")

            # Prediction error from past predictions in this domain
            pred_errors = [
                p.get("error", 0) for p in self.predictions
                if p.get("domain") == domain and p.get("actual") is not None
            ]
            avg_pred_error = sum(pred_errors) / len(pred_errors) if pred_errors else 0.5

            self.domain_health[domain] = {
                "recent_success_rate": round(recent_rate, 3),
                "older_success_rate": round(older_rate, 3),
                "trend": trend,
                "n_episodes": len(eps),
                "prediction_error": round(avg_pred_error, 3),
            }

    def _compute_system_state(self, episodes):
        """System-level abstraction: overall trajectory."""
        if not episodes:
            self.system_state = {"momentum": "neutral"}
            return

        recent = episodes[-10:]
        success_rate = sum(1 for e in recent if e.get("outcome") == "success") / len(recent)

        self.system_state = {
            "overall_success_rate": round(success_rate, 3),
            "momentum": "positive" if success_rate > 0.7 else (
                "negative" if success_rate < 0.4 else "neutral"
            ),
            "n_domains_active": len(set(e.get("section", "?") for e in recent)),
            "latent_state": self.latent.to_dict(),
        }

    def _log_prediction(self, task, predicted, p_success, curiosity, domain):
        """Log a prediction for later accuracy evaluation."""
        self._load_predictions()
        self.predictions.append({
            "task": task[:100],
            "predicted": predicted,
            "p_success": round(p_success, 3),
            "curiosity": round(curiosity, 3),
            "domain": domain,
            "actual": None,
            "error": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._save_predictions()

    def _load_predictions(self):
        if PREDICTIONS_LOG.exists() and not self.predictions:
            with open(PREDICTIONS_LOG) as f:
                self.predictions = json.load(f)

    def _save_predictions(self):
        # Cap at 500 predictions
        self.predictions = self.predictions[-500:]
        with open(PREDICTIONS_LOG, "w") as f:
            json.dump(self.predictions, f, indent=2)

    def save(self):
        """Save the trained world model."""
        data = {
            "transitions": self.transition.to_dict(),
            "n_episodes_trained": self.transition.n_episodes_trained,
            "domain_health": self.domain_health,
            "system_state": self.system_state,
            "latent_state": self.latent.to_dict(),
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(MODEL_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def load(self):
        """Load previously saved model state."""
        if MODEL_FILE.exists():
            with open(MODEL_FILE) as f:
                data = json.load(f)
            self.domain_health = data.get("domain_health", {})
            self.system_state = data.get("system_state", {})
            # Latent state and transitions need retraining from live data


# ======================================================================
# High-level API (used by other Clarvis subsystems)
# ======================================================================

def get_world_model():
    """Get a trained world model instance."""
    from episodic_memory import episodic

    wm = HierarchicalWorldModel()
    wm.train(episodic.episodes)
    return wm


def predict_task_outcome(task_text, domain="unknown"):
    """Quick API: predict outcome for a task."""
    wm = get_world_model()
    return wm.predict(task_text, domain)


def simulate_and_rank(candidate_tasks, domain="unknown"):
    """Quick API: Mind's Eye simulation for candidate tasks."""
    from episodic_memory import episodic
    wm = get_world_model()
    return wm.simulate_candidates(candidate_tasks, episodic.episodes, domain)


def get_curiosity_signal():
    """Quick API: get curiosity ranking across domains."""
    wm = get_world_model()
    return wm.get_curiosity_ranking()


# ======================================================================
# CLI
# ======================================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("World Models & Simulation Engine (Bundle C)")
        print()
        print("Based on: Ha & Schmidhuber (2018), LeCun JEPA, Mind's Eye,")
        print("          LeCun (2022) Path Toward Autonomous Machine Intelligence")
        print()
        print("Usage:")
        print("  train                    Train world model from episodes")
        print("  predict <task>           Predict outcome for a task")
        print("  simulate <t1> [t2] ...   Mind's Eye: simulate & rank candidates")
        print("  curiosity                Show curiosity-ranked domains")
        print("  stats                    Model statistics")
        print("  evaluate                 Evaluate prediction accuracy")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "train":
        from episodic_memory import episodic
        wm = HierarchicalWorldModel()
        results = wm.train(episodic.episodes)
        wm.save()

        print(f"\n{'='*60}")
        print("WORLD MODEL TRAINING COMPLETE")
        print(f"{'='*60}")
        print(f"\nEpisodes trained on: {results['n_episodes']}")
        print(f"Transition rules learned: {results['transitions_learned']}")
        print(f"JEPA embeddings built: {results['embeddings_built']}")

        print("\nLatent state z:")
        for name, val in results["latent_state"].items():
            bar = "█" * int(val * 20)
            print(f"  {name:20s} {bar:20s} {val:.3f}")

        print("\nDomain health:")
        for domain, health in sorted(results["domain_health"].items()):
            rate = health["recent_success_rate"]
            trend = health["trend"]
            arrow = "↑" if trend == "improving" else ("↓" if trend == "degrading" else "→")
            print(f"  {domain:20s} {rate:.0%} {arrow} ({health['n_episodes']} eps)")

        print(f"\nSystem momentum: {results['system_state'].get('momentum', '?')}")
        print(f"Model saved to: {MODEL_FILE}")

        # Store summary in brain
        try:
            from brain import brain
            summary = (
                f"[WORLD MODEL] Trained on {results['n_episodes']} episodes. "
                f"System momentum: {results['system_state'].get('momentum', '?')}. "
                f"Domains: {', '.join(d + '=' + h['trend'] for d, h in results['domain_health'].items())}. "
                f"Latent state: success_rate_5={results['latent_state'].get('success_rate_5', 0):.2f}, "
                f"momentum={results['latent_state'].get('momentum', 0):.2f}."
            )
            brain.store(
                summary,
                collection="clarvis-learnings",
                importance=0.7,
                tags=["world_model", "bundle_c", "ha_schmidhuber", "jepa", "lecun"],
                source="world_models",
                memory_id="world_model_latest",
            )
            print("\n[Summary stored in brain]")
        except Exception as e:
            print(f"\n[Warning: could not store in brain: {e}]")

    elif cmd == "predict":
        if len(sys.argv) < 3:
            print("Usage: predict <task_description>")
            sys.exit(1)
        task = " ".join(sys.argv[2:])
        result = predict_task_outcome(task)
        print(f"\nPrediction for: {task}")
        print(f"  Outcome:    {result['prediction']}")
        print(f"  P(success): {result['p_success']:.1%}")
        print(f"  Confidence: {result['confidence']:.1%}")
        print(f"  Curiosity:  {result['curiosity']:.3f}")
        print(f"  Strategy:   {result['strategy']}")
        print("\n  Hierarchy:")
        h = result["hierarchy"]
        print(f"    Task:   transition={h['task_level']['transition']}, jepa={h['task_level']['jepa']}")
        print(f"    Domain: trend={h['domain_level']['trend']}, rate={h['domain_level']['recent_rate']:.0%}")
        print(f"    System: momentum={h['system_level']['momentum']}")

    elif cmd == "simulate":
        if len(sys.argv) < 3:
            print("Usage: simulate <task1> [| task2] [| task3] ...")
            print("  Separate tasks with ' | '")
            sys.exit(1)
        tasks_raw = " ".join(sys.argv[2:])
        tasks = [t.strip() for t in tasks_raw.split("|")]
        results = simulate_and_rank(tasks)

        print(f"\n{'='*60}")
        print("MIND'S EYE SIMULATION RESULTS")
        print(f"{'='*60}")
        for i, r in enumerate(results, 1):
            u = r["expected_utility"]
            bar = "█" * max(0, int(u * 20))
            print(f"\n  #{i} [{r['strategy']:8s}] utility={u:+.3f} {bar}")
            print(f"     {r['task'][:70]}")
            print(f"     P(success)={r['p_success']:.0%}  P(fail)={r['p_failure']:.0%}  "
                  f"curiosity={r['curiosity']:.2f}  confidence={r['confidence']:.0%}")

    elif cmd == "curiosity":
        result = get_curiosity_signal()
        if result.get("note"):
            print(f"Note: {result['note']}")
        else:
            print("\nCuriosity ranking (prediction error → explore here):")
            print(f"Total resolved predictions: {result['total_resolved']}")
            if result.get("most_curious"):
                print(f"Most curious domain: {result['most_curious']}")
            for domain, data in result["domains"].items():
                bar = "█" * int(data["prediction_error"] * 20)
                print(f"  {domain:20s} error={data['prediction_error']:.0%} {bar} "
                      f"({data['curiosity_rank']}, n={data['n_predictions']})")

    elif cmd == "stats":
        wm = get_world_model()
        print("\nWorld Model Statistics:")
        print(f"  Episodes trained: {wm.transition.n_episodes_trained}")
        print(f"  Transition rules: {len(wm.transition.transitions)}")
        print(f"  JEPA embeddings:  {len(wm.jepa.task_vectors)}")
        print(f"  Predictions logged: {len(wm.predictions)}")
        print(f"\n  Latent state: {wm.latent.to_dict()}")
        print("\n  Domain health:")
        for d, h in sorted(wm.domain_health.items()):
            print(f"    {d:20s} {h['trend']:10s} rate={h['recent_success_rate']:.0%}")

    elif cmd == "evaluate":
        wm = get_world_model()
        acc = wm.evaluate_accuracy()
        print("\nWorld Model Evaluation:")
        if acc["accuracy"] is None:
            print("  No resolved predictions yet.")
        else:
            print(f"  Overall accuracy: {acc['accuracy']:.0%} ({acc['correct']}/{acc['total']})")
            print("\n  By domain:")
            for d, a in sorted(acc["domain_accuracy"].items()):
                print(f"    {d:20s} {a:.0%}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
