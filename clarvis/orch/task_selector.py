"""
Clarvis Task Selector — attention-based task prioritization.

Provides:
  - parse_tasks(): parse unchecked tasks from QUEUE.md
  - score_tasks(): 9-factor multi-modal salience scoring
  - _get_spotlight_themes(), _spotlight_alignment(): attention coherence
  - _check_quality_gate(), _is_repair_task(): gate enforcement

Migrated from scripts/task_selector.py (Phase 5 spine refactor).
"""

import json
import os
import re

from clarvis.cognition.attention import attention, get_codelet_competition
from clarvis.brain import brain

try:
    from clarvis._script_loader import load as _load_script
    _retrieval_mod = _load_script("retrieval_experiment", "brain_mem")
    smart_recall = _retrieval_mod.smart_recall
except Exception:
    smart_recall = None

try:
    from clarvis.cognition.somatic_markers import somatic
except Exception:
    somatic = None

try:
    from clarvis.cognition.thought_protocol import thought as thought_proto
except Exception:
    thought_proto = None

try:
    _world_models_mod = _load_script("world_models", "cognition")
    _wm = _world_models_mod.get_world_model()
except Exception:
    _wm = None

_WS = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
PERF_METRICS_FILE = os.path.join(_WS, "data", "performance_metrics.json")
QUEUE_FILE = os.path.join(_WS, "memory", "evolution", "QUEUE.md")
DELIVERY_LOCK_FILE = os.path.join(_WS, "DELIVERY_LOCK.md")
QUALITY_GATE_FILE = os.path.join(_WS, "data", "memory_quality_gate.json")
EPISODES_FILE = os.path.join(_WS, "data", "episodes.json")

# Project Lane — operator-directed project boost (see docs/PROJECT_LANES.md).
# When CLARVIS_PROJECT_LANE is set (e.g. "SWO"), tasks containing [PROJECT:<lane>]
# get a +0.3 scoring boost so project work wins over internal experimentation.
_PROJECT_LANE = os.environ.get("CLARVIS_PROJECT_LANE", "").strip()
PROJECT_LANE_BOOST = 0.3

# Keywords that signal AGI/consciousness relevance (high-value work)
AGI_KEYWORDS = [
    "agi", "consciousness", "attention", "working memory", "self model",
    "reasoning", "phi", "neural", "meta-cognition", "awareness", "gwt",
    "spotlight", "global workspace", "prediction", "calibration",
    "socratic", "conceptual", "framework", "obligation", "cognitive load",
    "lida", "codelet", "coalition", "workspace broadcast",
]

# Keywords that signal integration work (connecting existing components)
INTEGRATION_KEYWORDS = [
    "wire", "integrate", "connect", "hook", "persistent", "feedback loop",
    "into cron", "into daily", "run daily", "automat",
    "density", "intra", "graph edge", "cross-collection",
]

# Keywords that signal architectural or strategic work (non-Python improvements)
ARCHITECTURAL_KEYWORDS = [
    "redesign", "refactor", "architecture", "simplify", "merge",
    "config", "skill", "protocol", "tune", "audit", "review",
    "heartbeat.md", "agents.md", "roadmap", "prompt", "schedule",
]

# IMPROVE_EXISTING_OVER_NEW policy — boosts fix/improve tasks, penalizes new features.
# Active when CLARVIS_IMPROVE_EXISTING env var is set or policy file exists.
# Rationale: prevents surface area sprawl; prioritizes fixing, wiring, validating.
IMPROVE_EXISTING_KEYWORDS = [
    "fix", "simplify", "wire", "validate", "benchmark", "optimize",
    "test", "improve", "repair", "migrate", "soak", "verify",
    "reduce", "consolidate", "decompose", "cleanup", "stabilize",
]
NEW_FEATURE_KEYWORDS = [
    "new feature", "add new", "create new", "build new", "implement new",
    "introduce", "design new", "prototype",
]

# Keywords signaling context-improvement tasks (boosted when context_relevance is low)
CONTEXT_IMPROVEMENT_KEYWORDS = [
    "context", "relevance", "retrieval", "brain search", "recall",
    "brief", "compression", "noise", "prune", "dedup", "quality",
    "section", "ranking", "top-3", "preflight", "brain",
]
CONTEXT_RELEVANCE_THRESHOLD = 0.60


def _project_lane_boost(task_text, subsection=""):
    """Return PROJECT_LANE_BOOST if the task matches the active project lane, else 0."""
    if not _PROJECT_LANE:
        return 0.0
    lane_upper = _PROJECT_LANE.upper()
    combined = (task_text + " " + subsection).upper()
    if f"PROJECT:{lane_upper}" in combined or f"({lane_upper})" in combined:
        return PROJECT_LANE_BOOST
    if f"[{lane_upper}]" in combined:
        return PROJECT_LANE_BOOST
    return 0.0


def _compute_novelty(task_text, recent_tasks, min_words=3):
    """Compute novelty score (0.0-1.0) as inverse Jaccard similarity to recent tasks.

    Compares the candidate task's word set against the last N completed tasks.
    High novelty = low overlap with recent work = prevents "more of the same".

    Returns float 0.0 (identical to recent) to 1.0 (completely novel).
    """
    if not recent_tasks:
        return 1.0  # No history = maximally novel

    task_words = set(w.lower() for w in task_text.split() if len(w) > min_words)
    if not task_words:
        return 0.5

    similarities = []
    for rt in recent_tasks:
        rt_words = set(w.lower() for w in rt.split() if len(w) > min_words)
        if not rt_words:
            continue
        intersection = len(task_words & rt_words)
        union = len(task_words | rt_words)
        if union > 0:
            similarities.append(intersection / union)

    if not similarities:
        return 1.0

    # Use max similarity (most similar recent task) as the overlap measure
    max_sim = max(similarities)
    return round(1.0 - max_sim, 4)


def _get_recent_completed_tasks(n=15):
    """Load the last N completed task texts from episodes.json."""
    try:
        if not os.path.exists(EPISODES_FILE):
            return []
        with open(EPISODES_FILE) as f:
            episodes = json.load(f)
        # Get completed (success/failure/timeout) tasks, most recent first
        completed = [
            ep.get("task", "")
            for ep in reversed(episodes)
            if ep.get("task")
        ]
        return completed[:n]
    except Exception:
        return []


def parse_tasks(queue_file=QUEUE_FILE):
    """Parse unchecked tasks from QUEUE.md with their priority section."""
    tasks = []
    current_section = "P2"
    current_subsection = ""

    with open(queue_file, 'r') as f:
        for line_num, line in enumerate(f, 1):
            stripped = line.strip()

            # Detect section headers
            if '## P0' in line:
                current_section = "P0"
                current_subsection = ""
            elif '## P1' in line:
                current_section = "P1"
                current_subsection = ""
            elif '## P2' in line:
                current_section = "P2"
                current_subsection = ""
            elif '## Completed' in line:
                current_section = "completed"
                current_subsection = ""
            elif stripped.startswith("###"):
                current_subsection = stripped

            # Match unchecked tasks
            match = re.match(r'^- \[ \] (.+)$', stripped)
            if match and current_section != "completed":
                tasks.append({
                    "line_num": line_num,
                    "text": match.group(1),
                    "section": current_section,
                    "subsection": current_subsection,
                })

    return tasks


def _get_spotlight_themes():
    """Extract themes from current attention spotlight.

    Returns (theme_words, spotlight_texts) from the top-K items in the spotlight.
    Only considers non-TASK items to avoid circular self-reinforcement.
    """
    try:
        spotlight = attention.focus()
    except Exception:
        return set(), []

    theme_words = set()
    spotlight_texts = []
    for item in spotlight:
        content = item.get("content", "")
        if content.startswith("TASK: ") or content.startswith("Task salience="):
            continue
        spotlight_texts.append(content)
        words = set(w.lower() for w in content.split() if len(w) > 3)
        theme_words.update(words)

    return theme_words, spotlight_texts


def _spotlight_alignment(task_text, theme_words, spotlight_texts):
    """Score how well a task aligns with the current attention spotlight themes.

    Uses word overlap + spreading activation for coherent focus.
    Returns float 0.0-1.0 representing alignment strength.
    """
    if not theme_words:
        return 0.0

    task_words = set(w.lower() for w in task_text.split() if len(w) > 3)
    if not task_words:
        return 0.0

    overlap = len(task_words & theme_words)
    overlap_score = min(1.0, overlap / max(5, len(task_words)) * 2.0)

    try:
        activated = attention.spreading_activation(task_text, n=3)
        activation_score = len(activated) / 3.0 if activated else 0.0
    except Exception:
        activation_score = 0.0

    return round(min(1.0, 0.6 * overlap_score + 0.4 * activation_score), 4)


def _fetch_task_context():
    """Fetch brain context and recent activity for scoring."""
    try:
        context = brain.get_context()
    except Exception:
        context = ""

    try:
        if smart_recall is not None:
            recent = smart_recall("recent activity and current work", n=10)
        else:
            recent = brain.recall_recent(days=1, n=10)
        recent_text = " ".join([r["document"] for r in recent])
    except Exception:
        recent_text = ""

    try:
        from retrieval_quality import tracker
        if context and context != "idle":
            tracker.rate_last("smart_recall", useful=True, reason="task_selector: has active context")
        if recent_text and len(recent_text) > 50:
            tracker.rate_last("smart_recall", useful=True, reason="task_selector: recent memories found")
        elif recent_text:
            tracker.rate_last("smart_recall", useful=False, reason="task_selector: sparse recent text")
    except Exception:
        pass

    return context, recent_text


def _fetch_failure_lessons():
    """Pre-fetch failure lessons from brain (once, not per-task)."""
    try:
        raw = brain.recall(
            "failure failed avoid error crash timeout",
            collections=["clarvis-learnings"], n=20, min_importance=0.5
        )
        return [
            r["document"].lower() for r in raw
            if r.get("distance", 1.0) < 0.8
            and any(kw in r.get("document", "").lower()
                    for kw in ("failure", "failed", "avoid"))
        ]
    except Exception:
        return []


def _is_cr_boost_active():
    """Check if context-relevance boost should be active (metric below threshold)."""
    try:
        with open(PERF_METRICS_FILE) as f:
            perf = json.load(f)
        cr_value = perf.get("metrics", {}).get("context_relevance")
        return cr_value is not None and cr_value < CONTEXT_RELEVANCE_THRESHOLD
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return False


def _keyword_boost(text_lower, keywords, cap):
    """Accumulate keyword matches up to a cap."""
    boost = 0.0
    for kw in keywords:
        if kw in text_lower:
            boost = min(cap, boost + 0.1)
    return boost


def _compute_relevance(text_lower, context, recent_text):
    """Compute context and recent-activity relevance for a task."""
    context_words = set(context.lower().split()) if context else set()
    task_words = set(text_lower.split())
    if task_words:
        context_relevance = min(1.0, len(context_words & task_words) / len(task_words) * 2)
    else:
        context_relevance = 0.0

    recent_words = set(recent_text.lower().split()) if recent_text else set()
    if task_words:
        recent_relevance = min(1.0, len(recent_words & task_words) / len(task_words) * 1.5)
    else:
        recent_relevance = 0.0

    combined = max(context_relevance, recent_relevance * 0.8, 0.3)
    return context_relevance, recent_relevance, combined


def _compute_task_boosts(text, text_lower, theme_words, spotlight_texts,
                         failure_docs, recent_completed, cr_boost_active, codelet_result,
                         subsection=""):
    """Compute all boost/penalty factors for a task. Returns dict of factors."""
    agi_boost = _keyword_boost(text_lower, AGI_KEYWORDS, 0.3)
    integration_boost = _keyword_boost(text_lower, INTEGRATION_KEYWORDS, 0.2)
    architectural_boost = _keyword_boost(text_lower, ARCHITECTURAL_KEYWORDS, 0.2)
    spotlight_align = _spotlight_alignment(text, theme_words, spotlight_texts)

    somatic_bias = 0.0
    somatic_signal = "neutral"
    if somatic is not None:
        try:
            bias_result = somatic.get_bias(text)
            somatic_bias = bias_result.get("bias_score", 0.0)
            somatic_signal = bias_result.get("signal", "neutral")
        except Exception:
            pass

    codelet_bias = 0.0
    if codelet_result:
        try:
            competition = get_codelet_competition()
            codelet_bias = competition.bias_for_task(text)
        except Exception:
            pass

    failure_penalty = 0.0
    if failure_docs:
        task_keywords = {w for w in text_lower.split() if len(w) > 4}
        for fdoc in failure_docs:
            if any(kw in fdoc for kw in task_keywords):
                failure_penalty = min(0.15, failure_penalty + 0.05)

    novelty = _compute_novelty(text, recent_completed)
    improve_bias = _improve_existing_bias(text)

    cr_boost = 0.0
    if cr_boost_active:
        cr_boost = _keyword_boost(text_lower, CONTEXT_IMPROVEMENT_KEYWORDS, 0.35)

    project_boost = _project_lane_boost(text, subsection)
    total_boost = agi_boost + integration_boost + architectural_boost - failure_penalty + improve_bias + cr_boost + project_boost

    return {
        "agi_boost": agi_boost, "integration_boost": integration_boost,
        "architectural_boost": architectural_boost, "spotlight_align": spotlight_align,
        "somatic_bias": somatic_bias, "somatic_signal": somatic_signal,
        "codelet_bias": codelet_bias, "failure_penalty": failure_penalty,
        "novelty": novelty, "improve_bias": improve_bias,
        "project_lane_boost": project_boost, "total_boost": total_boost,
    }


def _score_single_task(task, context, recent_text, theme_words, spotlight_texts,
                       recent_completed, failure_docs, cr_boost_active, codelet_result):
    """Score a single task on all 9 factors. Returns scored dict."""
    text = task["text"]
    section = task["section"]
    subsection = task.get("subsection", "")
    text_lower = text.lower()

    section_importance = {"P0": 0.9, "P1": 0.6, "P2": 0.3}.get(section, 0.3)
    ctx_rel, rec_rel, relevance = _compute_relevance(text_lower, context, recent_text)
    b = _compute_task_boosts(text, text_lower, theme_words, spotlight_texts,
                             failure_docs, recent_completed, cr_boost_active, codelet_result,
                             subsection=subsection)

    effective_relevance = min(1.0, relevance + b["spotlight_align"] * 0.15)
    item = attention.submit(
        content=f"TASK: {text[:120]}",
        source="evolution_queue",
        importance=section_importance,
        relevance=effective_relevance,
        boost=b["total_boost"],
    )

    salience = item.salience()
    somatic_component = max(0.0, min(1.0, 0.5 + b["somatic_bias"]))
    codelet_component = max(0.0, min(1.0, 0.5 + b["codelet_bias"]))
    base_final = (0.70 * salience + 0.10 * b["spotlight_align"]
                  + 0.10 * somatic_component + 0.10 * codelet_component)
    final_score = base_final * (1.0 + 0.3 * b["novelty"])

    return {
        "text": text,
        "section": section,
        "line_num": task["line_num"],
        "salience": round(final_score, 4),
        "details": {
            "section_importance": section_importance,
            "context_relevance": round(ctx_rel, 3),
            "recent_relevance": round(rec_rel, 3),
            "agi_boost": round(b["agi_boost"], 3),
            "integration_boost": round(b["integration_boost"], 3),
            "architectural_boost": round(b["architectural_boost"], 3),
            "combined_relevance": round(relevance, 3),
            "spotlight_alignment": round(b["spotlight_align"], 3),
            "somatic_bias": round(b["somatic_bias"], 4),
            "somatic_signal": b["somatic_signal"],
            "codelet_bias": round(b["codelet_bias"], 4),
            "failure_penalty": round(b["failure_penalty"], 3),
            "improve_bias": round(b["improve_bias"], 3),
            "project_lane_boost": round(b["project_lane_boost"], 3),
            "novelty": round(b["novelty"], 4),
            "base_salience": round(salience, 4),
        }
    }


def _apply_delivery_lock(scored):
    """Penalize non-delivery tasks when delivery lock is active."""
    if not os.path.exists(DELIVERY_LOCK_FILE):
        return
    dlv_keywords = {"dlv", "delivery", "cleanup", "consolidat", "wire", "wiring",
                    "test", "context", "website", "open-source", "readiness",
                    "presentation", "repo", "bug", "fix"}
    for item in scored:
        t = item["text"].lower()
        if not any(kw in t for kw in dlv_keywords):
            item["salience"] = round(item["salience"] * 0.3, 4)
            item["details"]["delivery_lock_penalty"] = True


def _enforce_p0_floor(scored, floor_rank=3):
    """Guarantee P0 tasks rank in top-N to protect deadline commitments."""
    p0_below = [i for i, s in enumerate(scored) if s["section"] == "P0" and i >= floor_rank]
    if not p0_below:
        return
    non_p0_top = [i for i in range(floor_rank) if i < len(scored) and scored[i]["section"] != "P0"]
    for p0_idx in p0_below:
        if not non_p0_top:
            break
        swap_idx = non_p0_top.pop()
        scored[swap_idx], scored[p0_idx] = scored[p0_idx], scored[swap_idx]
        scored[swap_idx]["details"]["p0_floor_promoted"] = True


def _apply_world_model_reranking(scored):
    """Re-rank top candidates using world model predicted success probability."""
    if _wm is None or len(scored) <= 1:
        return
    try:
        for item in scored[:min(5, len(scored))]:
            prediction = _wm.predict(item["text"])
            if prediction:
                p_success = prediction.get("p_success", 0.5)
                curiosity = prediction.get("curiosity", 0.0)
                wm_signal = p_success * 0.7 + curiosity * 0.3
                item["salience"] = round(0.85 * item["salience"] + 0.15 * wm_signal, 4)
                item["details"]["wm_p_success"] = round(p_success, 3)
                item["details"]["wm_curiosity"] = round(curiosity, 3)
    except Exception:
        pass
    scored.sort(key=lambda x: x["salience"], reverse=True)


def score_tasks(tasks, codelet_result=None):
    """Score each task using attention-based salience + brain context + spotlight alignment.

    Scoring factors:
      1. Section importance: P0=0.9, P1=0.6, P2=0.3
      2. Context relevance: word overlap with current brain context
      3. Recent activity relevance: overlap with last day's memories
      4. AGI/consciousness boost
      5. Integration/wiring boost
      6. Spotlight alignment: coherence with current attention focus
      7. Somatic marker bias
      8. Codelet domain bias
      9. Failure penalty from learnings

    Final: 70% salience + 10% spotlight + 10% somatic + 10% codelet
    """
    context, recent_text = _fetch_task_context()
    theme_words, spotlight_texts = _get_spotlight_themes()
    recent_completed = _get_recent_completed_tasks(n=15)
    failure_docs = _fetch_failure_lessons()
    cr_boost_active = _is_cr_boost_active()

    # Mode compliance filter
    _current_mode = None
    try:
        from clarvis.runtime.mode import get_mode, is_task_allowed_for_mode
        _current_mode = get_mode()
    except ImportError:
        pass

    scored = []
    for task in tasks:
        # Mode gate: skip tasks disallowed by current operating mode
        if _current_mode and _current_mode != "ge":
            try:
                allowed, _ = is_task_allowed_for_mode(task["text"], _current_mode)
                if not allowed:
                    continue
            except Exception:
                pass

        result = _score_single_task(
            task, context, recent_text, theme_words, spotlight_texts,
            recent_completed, failure_docs, cr_boost_active, codelet_result,
        )
        if result:
            scored.append(result)

    _apply_delivery_lock(scored)
    scored.sort(key=lambda x: x["salience"], reverse=True)
    _enforce_p0_floor(scored)
    _apply_world_model_reranking(scored)

    if thought_proto and scored:
        try:
            best = scored[0]
            thought_proto.task_decision(
                best["text"][:120],
                salience=best["salience"],
                somatic_bias=best["details"].get("somatic_bias", 0.0),
                spotlight_align=best["details"].get("spotlight_alignment", 0.0),
            )
        except Exception:
            pass

    return scored


def _check_quality_gate():
    """Check if memory quality gate is active (degraded).
    Returns gate data dict if degraded, None if healthy."""
    try:
        if os.path.exists(QUALITY_GATE_FILE):
            with open(QUALITY_GATE_FILE) as f:
                gate = json.load(f)
            if gate.get("status") == "DEGRADED":
                return gate
    except Exception:
        pass
    return None


def _is_repair_task(task_text):
    """Check if a task is a repair/fix/maintenance task (allowed during quality gate)."""
    text_lower = task_text.lower()
    repair_keywords = [
        "memory_repair", "fix retrieval", "repair", "fix regression",
        "brain eval", "retrieval quality", "memory quality",
        "fix brain", "debug memory", "investigate failure",
    ]
    return any(kw in text_lower for kw in repair_keywords)


# ---------------------------------------------------------------------------
# IMPROVE_EXISTING_OVER_NEW policy
# ---------------------------------------------------------------------------

_IMPROVE_POLICY_FILE = os.path.join(
    os.path.dirname(QUEUE_FILE), "..", "..", "data", "improve_existing_policy.json"
)


def _is_improve_existing_active():
    """Check if the improve-existing-over-new policy is active.

    Active when:
    - CLARVIS_IMPROVE_EXISTING=1 env var is set, OR
    - data/improve_existing_policy.json exists with active=true
    """
    if os.environ.get("CLARVIS_IMPROVE_EXISTING", "").strip() in ("1", "true"):
        return True
    try:
        if os.path.exists(_IMPROVE_POLICY_FILE):
            with open(_IMPROVE_POLICY_FILE) as f:
                data = json.load(f)
            return data.get("active", False)
    except Exception:
        pass
    return False


def _improve_existing_bias(task_text):
    """Return a scoring bias for the improve-existing-over-new policy.

    Returns positive bias for fix/improve/optimize tasks,
    negative bias for new feature tasks, 0.0 for neutral.
    """
    if not _is_improve_existing_active():
        return 0.0

    text_lower = task_text.lower()

    # Boost for improving existing systems
    improve_hits = sum(1 for kw in IMPROVE_EXISTING_KEYWORDS if kw in text_lower)
    if improve_hits > 0:
        return min(0.25, improve_hits * 0.08)

    # Penalty for new feature surface area
    new_hits = sum(1 for kw in NEW_FEATURE_KEYWORDS if kw in text_lower)
    if new_hits > 0:
        return max(-0.20, -(new_hits * 0.10))

    return 0.0
