#!/usr/bin/env python3
"""
Self-Representation & Modeling — Bundle U implementation.

Implements three key research threads:

1. VanRullen & Kanai (2021) "Global Latent Workspace"
   Specialist modules each have their own latent space, connected through a
   shared global workspace. THIS module is the "self-specialist": it observes
   the global workspace and other specialists' outputs to build a compressed
   representation of the system's own cognitive state.

   Key idea: the self-model is NOT raw data; it's a LATENT vector that
   compresses the system's capabilities, performance, and trajectory into
   a fixed-dimensional representation that can be broadcast via GWT.

2. Dossa, Maytié, Devillers & VanRullen (2024) "GW Cross-Modal Transfer"
   Cycle-consistent representations are key to zero-shot transfer. The
   self-representation must be consistent across modalities:
   - Episodic view: "what happened" (success/failure patterns)
   - Semantic view: "what I know" (knowledge density per domain)
   - Procedural view: "what I can do" (procedure success rates)
   If these three views agree, the self-model is consistent. Divergence
   signals a calibration gap (e.g., I think I'm good at X but keep failing).

3. Anticipatory Systems (Rosen, 1985; Butz, 2008)
   A system that contains a predictive model of ITSELF and its environment,
   and uses that model to select actions. The self-model should:
   - Predict its own future state (anticipatory encoding)
   - Compare predicted vs actual state (prediction error → learning signal)
   - Use anticipated states to inform task selection (proactive adaptation)

Integration:
  - self_model.py: extends the existing self-model with latent state + anticipation
  - attention.py: reads spotlight to see what's globally broadcast
  - episodic_memory.py: uses episodes as training data for self-predictions
  - world_models.py: LatentState provides environment encoding; we add self-encoding
  - meta_gradient_rl.py: meta-parameters feed into self-representation
  - heartbeat_postflight.py: called after each task to update self-state + check predictions

Usage:
    python3 self_representation.py update       # Update self-representation from current state
    python3 self_representation.py predict       # Generate anticipatory predictions
    python3 self_representation.py check         # Check cross-modal consistency
    python3 self_representation.py report        # Full self-representation report
    python3 self_representation.py history        # Show state trajectory
"""

import json
import sys
import os
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _paths  # noqa: F401 — registers all script subdirs on sys.path

DATA_DIR = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))) / "data/self_representation"
DATA_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = DATA_DIR / "latent_state.json"
PREDICTIONS_FILE = DATA_DIR / "anticipatory_predictions.json"
HISTORY_FILE = DATA_DIR / "state_history.jsonl"
CONSISTENCY_FILE = DATA_DIR / "consistency_log.json"

# Latent self-state dimensions (VanRullen & Kanai: specialist module latent space)
SELF_STATE_DIMS = [
    "competence",          # Overall task success rate (recent window)
    "knowledge_density",   # How much semantic knowledge per domain
    "procedural_fluency",  # Procedure availability and success rate
    "episodic_richness",   # Diversity and depth of episodic memory
    "integration",         # Phi-like cross-module connectivity
    "adaptability",        # Meta-gradient learning rate / improvement trend
    "prediction_accuracy", # Confidence calibration quality
    "cognitive_load",      # Current task throughput vs capacity
    "momentum",            # Success/failure streak direction
    "novelty_exposure",    # Encountering new task types / error patterns
]

# Anticipatory prediction horizons
HORIZON_IMMEDIATE = 1    # Next task
HORIZON_SHORT = 5        # Next 5 tasks
HORIZON_SESSION = 20     # This session


# ======================================================================
# 1. LATENT SELF-STATE (VanRullen & Kanai specialist module)
# ======================================================================

def _load_state():
    """Load current latent self-state."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, KeyError):
            pass
    return {
        "z": {dim: 0.5 for dim in SELF_STATE_DIMS},
        "timestamp": None,
        "update_count": 0,
    }


def _save_state(state):
    """Save latent self-state and append to history."""
    state["timestamp"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2))

    # Append to history (capped at 500 entries)
    entry = {
        "z": state["z"],
        "t": state["timestamp"],
        "n": state["update_count"],
    }
    history = []
    if HISTORY_FILE.exists():
        try:
            for line in HISTORY_FILE.read_text().strip().split("\n"):
                if line.strip():
                    history.append(json.loads(line))
        except Exception:
            pass
    history.append(entry)
    history = history[-500:]
    HISTORY_FILE.write_text("\n".join(json.dumps(h) for h in history) + "\n")


def _encode_competence():
    """Compute competence dimension from recent task success rate."""
    try:
        from clarvis.memory.episodic_memory import EpisodicMemory
        em = EpisodicMemory()
        recent = em.episodes[-20:] if em.episodes else []
        if recent:
            successes = sum(1 for ep in recent if ep.get("outcome") == "success")
            return successes / len(recent), f"{successes}/{len(recent)} recent success"
        return 0.5, "no episodes (default)"
    except Exception as e:
        return 0.5, f"error: {e}"


def _encode_knowledge_density():
    """Compute knowledge density from brain stats."""
    try:
        from brain import brain
        stats = brain.stats()
        collections = stats.get("collections", {})
        total = stats.get("total_memories", 0)
        active_collections = sum(1 for v in collections.values() if v > 0)
        return min(1.0, total / 1000.0), f"{total} memories across {active_collections} collections"
    except Exception as e:
        return 0.3, f"error: {e}"


def _encode_procedural_fluency():
    """Compute procedural fluency from procedure count and success rate."""
    try:
        proc_file = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))) / "data/procedural_memory.json"
        if proc_file.exists():
            procs = json.loads(proc_file.read_text())
            if isinstance(procs, list) and procs:
                total_uses = sum(p.get("use_count", 0) for p in procs)
                total_success = sum(p.get("success_count", 0) for p in procs)
                rate = total_success / max(1, total_uses)
                count_score = min(1.0, len(procs) / 20.0)
                return 0.4 * count_score + 0.6 * rate, f"{len(procs)} procedures, {rate:.0%} success"
            return 0.2, "no procedures yet"
        return 0.1, "no procedural memory file"
    except Exception as e:
        return 0.2, f"error: {e}"


def _encode_episodic_richness():
    """Compute episodic richness from episode count and domain diversity."""
    try:
        from clarvis.memory.episodic_memory import EpisodicMemory
        em = EpisodicMemory()
        n_episodes = len(em.episodes)
        domains = set()
        for ep in em.episodes[-50:]:
            task = ep.get("task", "").lower()
            for kw in ["memory", "code", "fix", "wire", "research", "cron", "test", "phi"]:
                if kw in task:
                    domains.add(kw)
        count_score = min(1.0, n_episodes / 100.0)
        diversity_score = min(1.0, len(domains) / 5.0)
        return 0.5 * count_score + 0.5 * diversity_score, f"{n_episodes} episodes, {len(domains)} domains"
    except Exception as e:
        return 0.3, f"error: {e}"


def _encode_integration():
    """Compute integration dimension from Phi metric."""
    try:
        phi_file = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))) / "data/phi_history.json"
        if phi_file.exists():
            phi_data = json.loads(phi_file.read_text())
            if isinstance(phi_data, list) and phi_data:
                latest_phi = phi_data[-1].get("phi", 0.5)
                return min(1.0, latest_phi), f"Phi={latest_phi:.3f}"
            return 0.4, "phi history empty"
        return 0.3, "no phi data"
    except Exception as e:
        return 0.3, f"error: {e}"


def _encode_adaptability():
    """Compute adaptability from meta-gradient adaptation trend."""
    try:
        adapt_file = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))) / "data/meta_gradient_rl/adaptation_history.jsonl"
        if adapt_file.exists():
            lines = [l.strip() for l in adapt_file.read_text().strip().split("\n") if l.strip()]
            recent_adaptations = lines[-10:]
            if recent_adaptations:
                improvements = 0
                for line in recent_adaptations:
                    rec = json.loads(line)
                    if rec.get("j_after", 0) > rec.get("j_before", 0):
                        improvements += 1
                return improvements / len(recent_adaptations), f"{improvements}/{len(recent_adaptations)} improving"
            return 0.5, "no adaptation history"
        return 0.5, "no meta-gradient data"
    except Exception as e:
        return 0.5, f"error: {e}"


def _encode_prediction_accuracy():
    """Compute prediction accuracy from calibration data."""
    try:
        cal_file = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))) / "data/calibration/predictions.jsonl"
        if cal_file.exists():
            lines = [l.strip() for l in cal_file.read_text().strip().split("\n") if l.strip()]
            recent = lines[-20:]
            correct = 0
            total = 0
            for line in recent:
                try:
                    rec = json.loads(line)
                    if rec.get("correct") is not None:
                        total += 1
                        if rec["correct"]:
                            correct += 1
                except json.JSONDecodeError:
                    pass
            if total > 0:
                return correct / total, f"{correct}/{total} correct"
            return 0.5, "no resolved predictions"
        return 0.5, "no calibration data"
    except Exception as e:
        return 0.5, f"error: {e}"


def _encode_cognitive_load():
    """Compute cognitive load from tasks per hour (last 3 hours)."""
    try:
        from clarvis.memory.episodic_memory import EpisodicMemory
        em = EpisodicMemory()
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=3)
        recent_eps = [
            ep for ep in em.episodes
            if ep.get("timestamp") and
            datetime.fromisoformat(ep["timestamp"].replace("Z", "+00:00")) > cutoff
        ]
        tasks_per_hour = len(recent_eps) / 3.0
        return min(1.0, tasks_per_hour / 10.0), f"{tasks_per_hour:.1f} tasks/hr"
    except Exception as e:
        return 0.3, f"error: {e}"


def _encode_momentum():
    """Compute momentum from success/failure streak direction."""
    try:
        from clarvis.memory.episodic_memory import EpisodicMemory
        em = EpisodicMemory()
        last_5 = em.episodes[-5:] if em.episodes else []
        if last_5:
            streak = 0
            for ep in reversed(last_5):
                if ep.get("outcome") == "success":
                    streak += 1
                else:
                    streak -= 1
            return (streak + 5) / 10.0, f"streak={streak:+d} (last 5)"
        return 0.5, "no episodes"
    except Exception as e:
        return 0.5, f"error: {e}"


def _encode_novelty_exposure():
    """Compute novelty exposure from unique error patterns in recent tasks."""
    try:
        from clarvis.memory.episodic_memory import EpisodicMemory
        em = EpisodicMemory()
        recent = em.episodes[-20:] if em.episodes else []
        error_set = set()
        task_set = set()
        for ep in recent:
            if ep.get("error"):
                error_set.add(ep["error"][:50])
            task_set.add(ep.get("task", "")[:30])
        error_novelty = min(1.0, len(error_set) / 5.0) if error_set else 0.0
        task_novelty = min(1.0, len(task_set) / 10.0) if task_set else 0.0
        return 0.5 * error_novelty + 0.5 * task_novelty, f"{len(error_set)} unique errors, {len(task_set)} unique tasks"
    except Exception as e:
        return 0.3, f"error: {e}"


# Dimension encoders mapped by name for encode_self_state
_DIMENSION_ENCODERS = [
    ("competence", _encode_competence),
    ("knowledge_density", _encode_knowledge_density),
    ("procedural_fluency", _encode_procedural_fluency),
    ("episodic_richness", _encode_episodic_richness),
    ("integration", _encode_integration),
    ("adaptability", _encode_adaptability),
    ("prediction_accuracy", _encode_prediction_accuracy),
    ("cognitive_load", _encode_cognitive_load),
    ("momentum", _encode_momentum),
    ("novelty_exposure", _encode_novelty_exposure),
]


def encode_self_state():
    """
    Encode the system's current state into a latent vector z ∈ [0,1]^D.

    Each dimension is computed from real system data — no LLM calls needed.
    This is the VanRullen "specialist module" producing its latent representation
    to broadcast into the global workspace.

    Returns:
        dict with z (latent vector), component details, and timestamp.
    """
    z = {}
    details = {}
    t0 = time.monotonic()

    for dim_name, encoder_fn in _DIMENSION_ENCODERS:
        z[dim_name], details[dim_name] = encoder_fn()

    elapsed = round(time.monotonic() - t0, 3)

    state = _load_state()
    state["z"] = {k: round(v, 4) for k, v in z.items()}
    state["details"] = details
    state["update_count"] = state.get("update_count", 0) + 1
    state["encode_time_s"] = elapsed
    _save_state(state)

    return state


# ======================================================================
# 2. CROSS-MODAL CONSISTENCY CHECK (Dossa et al. 2024)
# ======================================================================

def check_consistency():
    """
    Check whether the three views of self agree (cycle-consistency).

    Episodic view: "what happened" → success/failure patterns per domain
    Semantic view: "what I know" → knowledge claims per domain
    Procedural view: "what I can do" → procedure success rates per domain

    Divergence means the self-model is miscalibrated:
    - "I know a lot about X" + "I keep failing at X" → overconfident
    - "I keep succeeding at X" + "I have no knowledge about X" → underrepresented
    - "I have procedures for X" + "I never use them" → stale procedures

    Returns:
        dict with consistency scores and identified gaps.
    """
    t0 = time.monotonic()
    gaps = []
    domain_views = defaultdict(lambda: {"episodic": 0.0, "semantic": 0.0, "procedural": 0.0})

    # --- Episodic view: success rates per domain ---
    try:
        from clarvis.memory.episodic_memory import EpisodicMemory
        em = EpisodicMemory()
        domain_eps = defaultdict(lambda: {"success": 0, "total": 0})
        for ep in em.episodes[-50:]:
            task = ep.get("task", "").lower()
            for domain in ["memory", "code", "fix", "wire", "research", "cron", "test", "phi", "infra"]:
                if domain in task:
                    domain_eps[domain]["total"] += 1
                    if ep.get("outcome") == "success":
                        domain_eps[domain]["success"] += 1
        for domain, counts in domain_eps.items():
            if counts["total"] > 0:
                domain_views[domain]["episodic"] = counts["success"] / counts["total"]
    except Exception:
        pass

    # --- Semantic view: knowledge density per domain (brain recall) ---
    try:
        from brain import brain
        for domain in list(domain_views.keys()):
            results = brain.recall(f"{domain} knowledge", n=5, collections=["clarvis-learnings"])
            if results:
                # Use number of relevant results as density proxy
                close = sum(1 for r in results if r.get("distance", 2.0) < 1.0)
                domain_views[domain]["semantic"] = min(1.0, close / 3.0)
    except Exception:
        pass

    # --- Procedural view: procedure success rates per domain ---
    try:
        proc_file = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))) / "data/procedural_memory.json"
        if proc_file.exists():
            procs = json.loads(proc_file.read_text())
            if isinstance(procs, list):
                for proc in procs:
                    name = proc.get("name", "").lower()
                    for domain in list(domain_views.keys()):
                        if domain in name:
                            uses = proc.get("use_count", 0)
                            success = proc.get("success_count", 0)
                            if uses > 0:
                                domain_views[domain]["procedural"] = success / uses
    except Exception:
        pass

    # --- Detect inconsistencies ---
    consistency_scores = {}
    for domain, views in domain_views.items():
        ep = views["episodic"]
        sem = views["semantic"]
        proc = views["procedural"]

        # Pairwise agreement: |a - b| for each pair
        ep_sem = abs(ep - sem)
        ep_proc = abs(ep - proc)
        sem_proc = abs(sem - proc)

        # Consistency = 1 - max divergence
        max_div = max(ep_sem, ep_proc, sem_proc)
        consistency_scores[domain] = round(1.0 - max_div, 3)

        # Flag specific gaps
        if ep > 0.7 and sem < 0.3:
            gaps.append(f"{domain}: succeeding episodically but knowledge underrepresented")
        if sem > 0.7 and ep < 0.3:
            gaps.append(f"{domain}: rich knowledge but poor episodic performance → overconfident")
        if proc > 0.7 and ep < 0.3:
            gaps.append(f"{domain}: procedures exist but poor execution → stale procedures")
        if ep > 0.5 and proc < 0.1:
            gaps.append(f"{domain}: performing well but no procedures captured → missing codification")

    overall = sum(consistency_scores.values()) / max(1, len(consistency_scores))
    elapsed = round(time.monotonic() - t0, 3)

    result = {
        "overall_consistency": round(overall, 3),
        "per_domain": consistency_scores,
        "domain_views": {k: {kk: round(vv, 3) for kk, vv in v.items()} for k, v in domain_views.items()},
        "gaps": gaps,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": elapsed,
    }

    # Persist
    CONSISTENCY_FILE.write_text(json.dumps(result, indent=2))

    return result


# ======================================================================
# 3. ANTICIPATORY PREDICTIONS (Rosen / Butz)
# ======================================================================

def _load_predictions():
    """Load outstanding anticipatory predictions."""
    if PREDICTIONS_FILE.exists():
        try:
            return json.loads(PREDICTIONS_FILE.read_text())
        except (json.JSONDecodeError, KeyError):
            pass
    return {"predictions": [], "resolved": [], "stats": {"total": 0, "correct": 0}}


def _save_predictions(data):
    """Save predictions."""
    PREDICTIONS_FILE.write_text(json.dumps(data, indent=2))


def anticipate():
    """
    Generate anticipatory predictions about the system's own future state.

    Uses current self-state z_t to predict z_{t+1} after the next task batch.
    This is the core of anticipatory cognition: the system models itself forward
    in time and can use those predictions to adapt proactively.

    Predictions:
    1. Next-task success probability (from momentum + competence)
    2. Expected competence trajectory (improving, stable, declining)
    3. Predicted cognitive load shift (overloaded, comfortable, idle)
    4. Identified risk: which dimension is most likely to drop?
    5. Opportunity: which dimension has the most improvement potential?

    Returns:
        dict with predictions and confidence levels.
    """
    state = _load_state()
    z = state.get("z", {})

    # Load history for trend analysis
    history = []
    if HISTORY_FILE.exists():
        try:
            for line in HISTORY_FILE.read_text().strip().split("\n"):
                if line.strip():
                    history.append(json.loads(line))
        except Exception:
            pass

    predictions = []
    now = datetime.now(timezone.utc).isoformat()

    # --- 1. Next-task success probability ---
    competence = z.get("competence", 0.5)
    momentum = z.get("momentum", 0.5)
    pred_accuracy = z.get("prediction_accuracy", 0.5)
    # Weighted blend: competence matters most, momentum gives direction
    p_success = 0.6 * competence + 0.3 * momentum + 0.1 * pred_accuracy
    p_success = max(0.05, min(0.95, p_success))
    predictions.append({
        "type": "next_task_success",
        "horizon": HORIZON_IMMEDIATE,
        "prediction": round(p_success, 3),
        "confidence": round(min(0.9, 0.3 + 0.7 * pred_accuracy), 3),
        "reasoning": f"competence={competence:.2f}, momentum={momentum:.2f}",
        "created": now,
        "resolved": False,
    })

    # --- 2. Competence trajectory (using history slope) ---
    if len(history) >= 3:
        recent_comp = [h["z"].get("competence", 0.5) for h in history[-5:]]
        if len(recent_comp) >= 2:
            # Simple linear trend
            slope = (recent_comp[-1] - recent_comp[0]) / len(recent_comp)
            if slope > 0.02:
                trajectory = "improving"
            elif slope < -0.02:
                trajectory = "declining"
            else:
                trajectory = "stable"
            predictions.append({
                "type": "competence_trajectory",
                "horizon": HORIZON_SHORT,
                "prediction": trajectory,
                "slope": round(slope, 4),
                "confidence": round(min(0.8, len(recent_comp) / 10.0), 3),
                "reasoning": f"slope={slope:+.4f} over {len(recent_comp)} states",
                "created": now,
                "resolved": False,
            })

    # --- 3. Cognitive load forecast ---
    cog_load = z.get("cognitive_load", 0.3)
    if cog_load > 0.7:
        load_prediction = "overloaded"
    elif cog_load > 0.3:
        load_prediction = "comfortable"
    else:
        load_prediction = "idle"
    predictions.append({
        "type": "cognitive_load_forecast",
        "horizon": HORIZON_SHORT,
        "prediction": load_prediction,
        "value": round(cog_load, 3),
        "confidence": 0.6,
        "reasoning": f"current load={cog_load:.2f}",
        "created": now,
        "resolved": False,
    })

    # --- 4. At-risk dimension (most likely to drop) ---
    at_risk = None
    risk_score = 0
    for dim, val in z.items():
        # Check trend: if dimension has been declining
        if len(history) >= 2:
            recent_vals = [h["z"].get(dim, 0.5) for h in history[-3:]]
            if len(recent_vals) >= 2:
                delta = recent_vals[-1] - recent_vals[0]
                # Risk = low value + declining trend
                risk = (1.0 - val) * 0.5 + max(0, -delta) * 0.5
                if risk > risk_score:
                    risk_score = risk
                    at_risk = dim
    if at_risk:
        predictions.append({
            "type": "at_risk_dimension",
            "horizon": HORIZON_SHORT,
            "prediction": at_risk,
            "current_value": round(z.get(at_risk, 0.5), 3),
            "risk_score": round(risk_score, 3),
            "confidence": 0.5,
            "reasoning": "low value + declining trend",
            "created": now,
            "resolved": False,
        })

    # --- 5. Opportunity dimension (most improvable) ---
    opportunity = None
    opp_score = 0
    for dim, val in z.items():
        # Opportunity = room to grow (1 - val) + positive trend
        if len(history) >= 2:
            recent_vals = [h["z"].get(dim, 0.5) for h in history[-3:]]
            if len(recent_vals) >= 2:
                delta = recent_vals[-1] - recent_vals[0]
                opp = (1.0 - val) * 0.4 + max(0, delta) * 0.6
                if opp > opp_score and val < 0.8:
                    opp_score = opp
                    opportunity = dim
    if opportunity:
        predictions.append({
            "type": "opportunity_dimension",
            "horizon": HORIZON_SESSION,
            "prediction": opportunity,
            "current_value": round(z.get(opportunity, 0.5), 3),
            "opportunity_score": round(opp_score, 3),
            "confidence": 0.4,
            "reasoning": "room to grow + positive trend",
            "created": now,
            "resolved": False,
        })

    # Save predictions
    pred_data = _load_predictions()
    pred_data["predictions"].extend(predictions)
    # Keep only recent unresolved (cap 50)
    pred_data["predictions"] = [
        p for p in pred_data["predictions"] if not p.get("resolved")
    ][-50:]
    _save_predictions(pred_data)

    return {
        "predictions": predictions,
        "state_summary": {k: round(v, 3) for k, v in z.items()},
        "timestamp": now,
    }


def resolve_prediction(prediction_type, actual_value):
    """
    Resolve an anticipatory prediction against actual outcome.

    This is the prediction error signal that drives self-model learning:
    - If prediction was accurate → self-model is well-calibrated
    - If prediction was wrong → self-model needs updating

    Args:
        prediction_type: str, e.g. "next_task_success"
        actual_value: the actual outcome (True/False for success, or string for trajectory)

    Returns:
        dict with resolution details and error magnitude.
    """
    pred_data = _load_predictions()

    # Find most recent unresolved prediction of this type
    target = None
    for p in reversed(pred_data["predictions"]):
        if p.get("type") == prediction_type and not p.get("resolved"):
            target = p
            break

    if not target:
        return {"status": "no_matching_prediction", "type": prediction_type}

    # Compute prediction error
    predicted = target["prediction"]
    if prediction_type == "next_task_success":
        # Continuous: predicted probability vs binary outcome
        actual_binary = 1.0 if actual_value else 0.0
        error = abs(predicted - actual_binary)
        correct = (predicted >= 0.5) == actual_value
    elif prediction_type in ("competence_trajectory", "cognitive_load_forecast"):
        # Categorical
        correct = predicted == actual_value
        error = 0.0 if correct else 1.0
    else:
        correct = predicted == actual_value
        error = 0.0 if correct else 1.0

    # Update prediction
    target["resolved"] = True
    target["actual"] = actual_value if isinstance(actual_value, (str, int, float, bool)) else str(actual_value)
    target["error"] = round(error, 4)
    target["correct"] = correct
    target["resolved_at"] = datetime.now(timezone.utc).isoformat()

    # Move to resolved list
    pred_data["resolved"].append(target)
    pred_data["predictions"] = [p for p in pred_data["predictions"] if not p.get("resolved")]
    # Cap resolved at 200
    pred_data["resolved"] = pred_data["resolved"][-200:]

    # Update stats
    pred_data["stats"]["total"] = pred_data["stats"].get("total", 0) + 1
    if correct:
        pred_data["stats"]["correct"] = pred_data["stats"].get("correct", 0) + 1

    _save_predictions(pred_data)

    return {
        "status": "resolved",
        "type": prediction_type,
        "predicted": predicted,
        "actual": actual_value,
        "error": round(error, 4),
        "correct": correct,
        "cumulative_accuracy": round(
            pred_data["stats"]["correct"] / max(1, pred_data["stats"]["total"]), 3
        ),
    }


# ======================================================================
# 4. GWT BROADCAST INTEGRATION
# ======================================================================

def broadcast_self_state():
    """
    Broadcast the current self-state to the global workspace.

    VanRullen & Kanai: specialist modules push their latent representations
    into the global workspace. The self-specialist broadcasts a compressed
    summary of z_t so other modules can condition on it.

    Returns the broadcast summary string.
    """
    state = _load_state()
    z = state.get("z", {})

    if not z:
        return "Self-state: not yet encoded"

    # Compress to top insights
    sorted_dims = sorted(z.items(), key=lambda x: x[1], reverse=True)
    top_3 = sorted_dims[:3]
    bottom_2 = sorted_dims[-2:]

    lines = ["Self-state z_t:"]
    lines.append(f"  Strengths: {', '.join(f'{d}={v:.2f}' for d, v in top_3)}")
    lines.append(f"  Gaps: {', '.join(f'{d}={v:.2f}' for d, v in bottom_2)}")

    # Add anticipatory note if predictions exist
    pred_data = _load_predictions()
    unresolved = [p for p in pred_data.get("predictions", []) if not p.get("resolved")]
    if unresolved:
        risk_preds = [p for p in unresolved if p["type"] == "at_risk_dimension"]
        if risk_preds:
            dim = risk_preds[-1]["prediction"]
            lines.append(f"  At-risk: {dim} (val={z.get(dim, 0):.2f})")

    summary = "\n".join(lines)

    # Push to attention spotlight
    try:
        from clarvis.cognition.attention import attention
        attention.submit(
            summary,
            source="self_representation",
            importance=0.6,
            relevance=0.7,
            boost=0.1,
        )
    except Exception:
        pass

    # Store in brain identity — fixed ID so repeated updates upsert in place
    try:
        from brain import brain
        brain.store(
            f"Self-representation update: {summary}",
            collection="clarvis-identity",
            importance=0.5,
            tags=["self-representation", "latent-state", "gwt-broadcast"],
            source="self_representation",
            memory_id="self-rep-current",
        )
    except Exception:
        pass

    return summary


# ======================================================================
# 5. POSTFLIGHT INTEGRATION HOOK
# ======================================================================

def postflight_update(task_status, task_text="", duration_s=0):
    """
    Called from heartbeat_postflight after each task.

    1. Resolve the "next_task_success" anticipatory prediction
    2. Re-encode the self-state
    3. Generate new anticipatory predictions
    4. Check cross-modal consistency (every 10 updates)
    5. Broadcast updated self-state

    Args:
        task_status: "success" | "failure" | "timeout"
        task_text: the task description
        duration_s: task duration in seconds

    Returns:
        dict with update results.
    """
    t0 = time.monotonic()
    results = {}

    # 1. Resolve prediction
    actual_success = task_status == "success"
    resolution = resolve_prediction("next_task_success", actual_success)
    results["prediction_resolution"] = resolution

    # 2. Re-encode
    new_state = encode_self_state()
    results["self_state"] = {k: round(v, 3) for k, v in new_state["z"].items()}

    # 3. New predictions
    anticipation = anticipate()
    results["anticipation"] = {
        "n_predictions": len(anticipation["predictions"]),
        "p_next_success": next(
            (p["prediction"] for p in anticipation["predictions"]
             if p["type"] == "next_task_success"), None
        ),
    }

    # 4. Consistency check (every 10 updates)
    if new_state.get("update_count", 0) % 10 == 0:
        consistency = check_consistency()
        results["consistency"] = {
            "overall": consistency["overall_consistency"],
            "gaps": consistency["gaps"][:3],
        }

    # 5. Broadcast
    broadcast = broadcast_self_state()
    results["broadcast"] = broadcast[:100]

    results["elapsed_s"] = round(time.monotonic() - t0, 3)
    return results


# ======================================================================
# 6. REPORTING
# ======================================================================

def report():
    """Generate a full self-representation report."""
    state = _load_state()
    z = state.get("z", {})
    details = state.get("details", {})

    print("=" * 60)
    print("SELF-REPRESENTATION REPORT (Bundle U)")
    print(f"Updated: {state.get('timestamp', 'never')}")
    print(f"Updates: {state.get('update_count', 0)}")
    print("=" * 60)

    print("\n--- Latent Self-State z_t ---")
    if z:
        sorted_dims = sorted(z.items(), key=lambda x: x[1], reverse=True)
        for dim, val in sorted_dims:
            bar = "#" * int(val * 20)
            detail = details.get(dim, "")
            print(f"  {dim:22s} {val:.3f} |{bar:20s}| {detail}")
    else:
        print("  (not yet encoded)")

    # Predictions
    pred_data = _load_predictions()
    unresolved = [p for p in pred_data.get("predictions", []) if not p.get("resolved")]
    resolved = pred_data.get("resolved", [])
    stats = pred_data.get("stats", {})

    print("\n--- Anticipatory Predictions ---")
    print(f"  Active: {len(unresolved)}  Resolved: {len(resolved)}")
    if stats.get("total", 0) > 0:
        acc = stats["correct"] / stats["total"]
        print(f"  Cumulative accuracy: {acc:.0%} ({stats['correct']}/{stats['total']})")

    for p in unresolved[:5]:
        print(f"  [{p['type']}] prediction={p['prediction']} conf={p.get('confidence', '?')}")

    # Consistency
    if CONSISTENCY_FILE.exists():
        try:
            cons = json.loads(CONSISTENCY_FILE.read_text())
            print("\n--- Cross-Modal Consistency ---")
            print(f"  Overall: {cons['overall_consistency']:.3f}")
            if cons.get("gaps"):
                for gap in cons["gaps"][:3]:
                    print(f"  GAP: {gap}")
        except Exception:
            pass

    # History trend
    history = []
    if HISTORY_FILE.exists():
        try:
            for line in HISTORY_FILE.read_text().strip().split("\n"):
                if line.strip():
                    history.append(json.loads(line))
        except Exception:
            pass

    if len(history) >= 2:
        print(f"\n--- Trajectory (last {min(5, len(history))} states) ---")
        for h in history[-5:]:
            comp = h["z"].get("competence", 0)
            integ = h["z"].get("integration", 0)
            mom = h["z"].get("momentum", 0)
            print(f"  [{h.get('t', '?')[:19]}] comp={comp:.2f} integ={integ:.2f} mom={mom:.2f}")

    print("\n" + "=" * 60)


# ======================================================================
# CLI
# ======================================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: self_representation.py <command>")
        print("Commands: update, predict, check, report, history, broadcast")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "update":
        state = encode_self_state()
        z = state["z"]
        print(f"Encoded self-state ({state['encode_time_s']:.2f}s):")
        for dim in SELF_STATE_DIMS:
            print(f"  {dim:22s} = {z.get(dim, 0):.3f}")

    elif cmd == "predict":
        result = anticipate()
        print(f"Anticipatory predictions ({len(result['predictions'])}):")
        for p in result["predictions"]:
            print(f"  [{p['type']}] {p['prediction']} (conf={p.get('confidence', '?')})")

    elif cmd == "check":
        result = check_consistency()
        print(f"Cross-modal consistency: {result['overall_consistency']:.3f}")
        for domain, score in sorted(result["per_domain"].items(), key=lambda x: x[1]):
            print(f"  {domain:15s} {score:.3f}")
        if result["gaps"]:
            print("\nGaps:")
            for gap in result["gaps"]:
                print(f"  - {gap}")

    elif cmd == "report":
        report()

    elif cmd == "history":
        history = []
        if HISTORY_FILE.exists():
            for line in HISTORY_FILE.read_text().strip().split("\n"):
                if line.strip():
                    history.append(json.loads(line))
        print(f"State history: {len(history)} entries")
        for h in history[-10:]:
            z = h["z"]
            dims = " ".join(f"{k[:4]}={v:.2f}" for k, v in sorted(z.items()))
            print(f"  [{h.get('t', '?')[:19]}] {dims}")

    elif cmd == "broadcast":
        summary = broadcast_self_state()
        print(summary)

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
