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
import sys

from clarvis.cognition.attention import attention, get_codelet_competition
from clarvis.brain import brain

_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'scripts')

try:
    if _SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, _SCRIPTS_DIR)
    from retrieval_experiment import smart_recall
except ImportError:
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
    from world_models import get_world_model
    _wm = get_world_model()
except Exception:
    _wm = None

PERF_METRICS_FILE = "/home/agent/.openclaw/workspace/data/performance_metrics.json"
QUEUE_FILE = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md"
DELIVERY_LOCK_FILE = "/home/agent/.openclaw/workspace/DELIVERY_LOCK.md"
QUALITY_GATE_FILE = "/home/agent/.openclaw/workspace/data/memory_quality_gate.json"
EPISODES_FILE = "/home/agent/.openclaw/workspace/data/episodes.json"

# Keywords that signal AGI/consciousness relevance (high-value work)
AGI_KEYWORDS = [
    "agi", "consciousness", "attention", "working memory", "self model",
    "reasoning", "phi", "neural", "meta-cognition", "awareness", "gwt",
    "spotlight", "global workspace", "prediction", "calibration",
]

# Keywords that signal integration work (connecting existing components)
INTEGRATION_KEYWORDS = [
    "wire", "integrate", "connect", "hook", "persistent", "feedback loop",
    "into cron", "into daily", "run daily", "automat",
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

    with open(queue_file, 'r') as f:
        for line_num, line in enumerate(f, 1):
            stripped = line.strip()

            # Detect section headers
            if '## P0' in line:
                current_section = "P0"
            elif '## P1' in line:
                current_section = "P1"
            elif '## P2' in line:
                current_section = "P2"
            elif '## Completed' in line:
                current_section = "completed"

            # Match unchecked tasks
            match = re.match(r'^- \[ \] (.+)$', stripped)
            if match and current_section != "completed":
                tasks.append({
                    "line_num": line_num,
                    "text": match.group(1),
                    "section": current_section,
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

    theme_words, spotlight_texts = _get_spotlight_themes()

    # Load recent completed tasks for novelty scoring
    recent_completed = _get_recent_completed_tasks(n=15)

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

    # Pre-fetch failure lessons once (was per-task, causing ~100s overhead)
    _failure_docs = []
    try:
        _failure_raw = brain.recall(
            "failure failed avoid error crash timeout",
            collections=["clarvis-learnings"], n=20, min_importance=0.5
        )
        _failure_docs = [
            r["document"].lower() for r in _failure_raw
            if r.get("distance", 1.0) < 0.8
            and any(kw in r.get("document", "").lower()
                    for kw in ("failure", "failed", "avoid"))
        ]
    except Exception:
        pass

    # Context-improvement priority boost when context_relevance metric is low
    _cr_boost_active = False
    try:
        with open(PERF_METRICS_FILE) as _pf:
            _perf = json.load(_pf)
        _cr_value = _perf.get("metrics", {}).get("context_relevance")
        if _cr_value is not None and _cr_value < CONTEXT_RELEVANCE_THRESHOLD:
            _cr_boost_active = True
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass

    # Mode compliance filter: skip tasks not allowed in current operating mode
    _current_mode = None
    try:
        from clarvis.runtime.mode import get_mode, is_task_allowed_for_mode
        _current_mode = get_mode()
    except ImportError:
        pass

    scored = []

    for task in tasks:
        text = task["text"]
        section = task["section"]
        text_lower = text.lower()

        # Mode gate: skip tasks disallowed by current operating mode
        if _current_mode and _current_mode != "ge":
            try:
                allowed, _mode_reason = is_task_allowed_for_mode(text, _current_mode)
                if not allowed:
                    continue
            except Exception:
                pass

        section_importance = {"P0": 0.9, "P1": 0.6, "P2": 0.3}.get(section, 0.3)

        context_words = set(context.lower().split()) if context else set()
        task_words = set(text_lower.split())
        if task_words:
            context_overlap = len(context_words & task_words) / len(task_words)
            context_relevance = min(1.0, context_overlap * 2)
        else:
            context_relevance = 0.0

        recent_words = set(recent_text.lower().split()) if recent_text else set()
        if task_words:
            recent_overlap = len(recent_words & task_words) / len(task_words)
            recent_relevance = min(1.0, recent_overlap * 1.5)
        else:
            recent_relevance = 0.0

        relevance = max(context_relevance, recent_relevance * 0.8, 0.3)

        agi_boost = 0.0
        for kw in AGI_KEYWORDS:
            if kw in text_lower:
                agi_boost = min(0.3, agi_boost + 0.1)

        integration_boost = 0.0
        for kw in INTEGRATION_KEYWORDS:
            if kw in text_lower:
                integration_boost = min(0.2, integration_boost + 0.1)

        architectural_boost = 0.0
        for kw in ARCHITECTURAL_KEYWORDS:
            if kw in text_lower:
                architectural_boost = min(0.2, architectural_boost + 0.1)

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

        # Failure penalty via pre-fetched docs (string match, no per-task brain call)
        failure_penalty = 0.0
        if _failure_docs:
            task_keywords = {w for w in text_lower.split() if len(w) > 4}
            for fdoc in _failure_docs:
                if any(kw in fdoc for kw in task_keywords):
                    failure_penalty = min(0.15, failure_penalty + 0.05)

        # Novelty: boost tasks that differ from recent completed work
        novelty = _compute_novelty(text, recent_completed)

        # Improve-existing-over-new policy bias
        improve_bias = _improve_existing_bias(text)

        # Context-improvement boost when context_relevance < threshold
        cr_boost = 0.0
        if _cr_boost_active:
            for kw in CONTEXT_IMPROVEMENT_KEYWORDS:
                if kw in text_lower:
                    cr_boost = min(0.35, cr_boost + 0.1)

        total_boost = agi_boost + integration_boost + architectural_boost - failure_penalty + improve_bias + cr_boost

        effective_relevance = min(1.0, relevance + spotlight_align * 0.15)
        item = attention.submit(
            content=f"TASK: {text[:120]}",
            source="evolution_queue",
            importance=section_importance,
            relevance=effective_relevance,
            boost=total_boost,
        )

        salience = item.salience()

        somatic_component = max(0.0, min(1.0, 0.5 + somatic_bias))
        codelet_component = max(0.0, min(1.0, 0.5 + codelet_bias))
        base_final = (0.70 * salience + 0.10 * spotlight_align
                      + 0.10 * somatic_component + 0.10 * codelet_component)

        # Novelty boost: prevent "more of the same" trap
        # final_score = base_score * (1 + 0.3 * novelty)
        final_score = base_final * (1.0 + 0.3 * novelty)

        scored.append({
            "text": text,
            "section": section,
            "line_num": task["line_num"],
            "salience": round(final_score, 4),
            "details": {
                "section_importance": section_importance,
                "context_relevance": round(context_relevance, 3),
                "recent_relevance": round(recent_relevance, 3),
                "agi_boost": round(agi_boost, 3),
                "integration_boost": round(integration_boost, 3),
                "architectural_boost": round(architectural_boost, 3),
                "combined_relevance": round(relevance, 3),
                "spotlight_alignment": round(spotlight_align, 3),
                "somatic_bias": round(somatic_bias, 4),
                "somatic_signal": somatic_signal,
                "codelet_bias": round(codelet_bias, 4),
                "failure_penalty": round(failure_penalty, 3),
                "improve_bias": round(improve_bias, 3),
                "novelty": round(novelty, 4),
                "base_salience": round(salience, 4),
            }
        })

    # Delivery lock: penalize non-delivery tasks when lock is active
    _delivery_locked = os.path.exists(DELIVERY_LOCK_FILE)
    if _delivery_locked:
        _DLV_KEYWORDS = {"dlv", "delivery", "cleanup", "consolidat", "wire", "wiring",
                         "test", "context", "website", "open-source", "readiness",
                         "presentation", "repo", "bug", "fix"}
        for item in scored:
            t = item["text"].lower()
            is_delivery = any(kw in t for kw in _DLV_KEYWORDS)
            if not is_delivery:
                item["salience"] = round(item["salience"] * 0.3, 4)
                item["details"]["delivery_lock_penalty"] = True

    scored.sort(key=lambda x: x["salience"], reverse=True)

    # P0 priority floor: guarantee P0 tasks always rank in top-3.
    # Without this, well-aligned P1/P2 tasks can outrank P0 delivery items,
    # undermining deadline commitments.
    _P0_FLOOR_RANK = 3
    p0_in_top = sum(1 for s in scored[:_P0_FLOOR_RANK] if s["section"] == "P0")
    p0_below = [i for i, s in enumerate(scored) if s["section"] == "P0" and i >= _P0_FLOOR_RANK]
    if p0_below:
        # Find non-P0 items in top-3 that can be displaced
        non_p0_top = [i for i in range(_P0_FLOOR_RANK) if i < len(scored) and scored[i]["section"] != "P0"]
        for p0_idx in p0_below:
            if not non_p0_top:
                break
            swap_idx = non_p0_top.pop()  # displace lowest non-P0 in top-3
            scored[swap_idx], scored[p0_idx] = scored[p0_idx], scored[swap_idx]
            scored[swap_idx]["details"]["p0_floor_promoted"] = True

    # World model re-ranking: adjust scores by predicted success probability
    if _wm is not None and len(scored) > 1:
        try:
            top_candidates = scored[:min(5, len(scored))]
            for item in top_candidates:
                prediction = _wm.predict(item["text"])
                if prediction:
                    p_success = prediction.get("p_success", 0.5)
                    curiosity = prediction.get("curiosity", 0.0)
                    # Blend: 85% original salience + 15% world model signal
                    wm_signal = p_success * 0.7 + curiosity * 0.3
                    item["salience"] = round(
                        0.85 * item["salience"] + 0.15 * wm_signal, 4
                    )
                    item["details"]["wm_p_success"] = round(p_success, 3)
                    item["details"]["wm_curiosity"] = round(curiosity, 3)
        except Exception:
            pass  # World model failure is non-fatal
        scored.sort(key=lambda x: x["salience"], reverse=True)

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
