"""Context Relevance Feedback — outcome-based section-level relevance scoring.

Compares brief sections against Claude Code output to compute true relevance
using importance-weighted soft-threshold scoring:
  relevance = sum(normalized_containment_i * importance_i) / sum(importance_i)

Each section is scored by containment (fraction of section tokens in output).
Containment is normalized via soft-threshold: min(containment / threshold, 1.0),
giving proportional credit instead of binary referenced/not-referenced.
Importance weights are empirical per-section means from historical data.

Data stored per-episode in data/retrieval_quality/context_relevance.jsonl.
Aggregated by performance_benchmark.py for the context_relevance metric.

Usage:
    from clarvis.cognition.context_relevance import score_section_relevance, aggregate_relevance

    # Score after task execution
    result = score_section_relevance(brief_text, output_text, task="...")
    # result = {
    #   "overall": 0.71,
    #   "sections_total": 7,
    #   "sections_referenced": 5,
    #   "per_section": {"decision_context": 0.23, "knowledge": 0.18, ...},
    #   "outcome": "success",
    # }

    # Aggregate for metrics
    agg = aggregate_relevance(days=7)
    # agg = {"mean_relevance": 0.68, "episodes": 42, "per_section_mean": {...}}
"""

import json
import logging
import os
import re
from datetime import datetime, timezone, timedelta

_log = logging.getLogger(__name__)

# Section markers used in tiered briefs (assembly.py) and supplementary
# context appended by heartbeat_preflight.py.
_SECTION_MARKERS = [
    # --- From generate_tiered_brief (assembly.py) ---
    ("decision_context", re.compile(r"^(?:SUCCESS CRITERIA|CONSTRAINTS|DECISION CONTEXT)", re.I | re.M)),
    ("knowledge", re.compile(r"^RELEVANT KNOWLEDGE:", re.I | re.M)),
    ("working_memory", re.compile(r"^(?:WORKING MEMORY|COGNITIVE WORKSPACE|ACTIVE BUFFER)", re.I | re.M)),
    ("related_tasks", re.compile(r"^RELATED TASKS:", re.I | re.M)),
    ("metrics", re.compile(r"^METRICS:", re.I | re.M)),
    ("completions", re.compile(r"^RECENT:", re.I | re.M)),
    ("episodes", re.compile(r"^(?:EPISODIC LESSONS|EPISODIC HINTS|LESSONS FROM)", re.I | re.M)),
    ("reasoning", re.compile(r"^(?:REASONING|THINK BEFORE|APPROACH):", re.I | re.M)),
    # --- Supplementary context from heartbeat_preflight.py ---
    ("brain_goals", re.compile(r"^BRAIN GOALS", re.I | re.M)),
    ("brain_context", re.compile(r"^BRAIN CONTEXT:", re.I | re.M)),
    ("world_model", re.compile(r"^WORLD MODEL:", re.I | re.M)),
    ("failure_avoidance", re.compile(r"^(?:FAILURE AVOIDANCE|AVOID THESE FAILURE PATTERNS)", re.I | re.M)),
    ("synaptic", re.compile(r"^SYNAPTIC ASSOCIATIONS", re.I | re.M)),
    ("attention", re.compile(r"^ATTENTION CODELETS", re.I | re.M)),
    ("gwt_broadcast", re.compile(r"^GWT BROADCAST", re.I | re.M)),
    ("introspection", re.compile(r"^(?:BRAIN INTROSPECTION|=== BRAIN INTROSPECTION)", re.I | re.M)),
    ("confidence_gate", re.compile(r"^CONFIDENCE GATE", re.I | re.M)),
    ("meta_gradient", re.compile(r"^META-GRADIENT:", re.I | re.M)),
    ("procedures", re.compile(r"^(?:RECOMMENDED PROCEDURES|PROCEDURES FOR INJECTION)", re.I | re.M)),
]

# Stopwords for tokenization
_STOPWORDS = frozenset(
    "a an the is are was were be been being have has had do does did will would "
    "shall should may might can could to of in for on with at by from as into "
    "through during before after above below between under again further then "
    "once here there when where why how all each every both few more most other "
    "some such no nor not only own same so than too very and but if or because "
    "until while that this these those it its he she they them their what which "
    "who whom".split()
)

# Brief template markers that inflate section token counts without carrying
# task-specific information.  These appear as section headers/labels in the
# brief and are never repeated in Claude Code's output.  Stripping them
# improves containment accuracy.
_TEMPLATE_MARKERS = frozenset(
    "current task success criteria constraints decision context relevant "
    "knowledge working memory cognitive workspace active buffer related tasks "
    "metrics recent approach analyze before implementing check failure patterns "
    "test your changes report what you accomplished avoid these failure "
    "brain goals brain context world model attention codelets gwt broadcast "
    "introspection confidence gate meta gradient recommended procedures "
    "synaptic associations episodic lessons episodic hints lessons from "
    "reasoning think weak areas extra careful wire guidance required sub steps"
    .split()
)

# Minimum containment for a section to count as "referenced" (legacy binary mode).
# Containment = |section ∩ output| / |section|, so 0.15 means at least 15% of
# the section's unique terms must appear in the output.
REFERENCE_THRESHOLD = 0.12

# Sections with fewer unique tokens than this are excluded from scoring —
# too small to meaningfully evaluate (e.g., "METRICS: Phi=0.72" has ~4 tokens).
MIN_SECTION_TOKENS = 5

# Episodes with fewer scorable sections than this are excluded from
# aggregation — minimal briefs produce noisy scores that drag down the mean.
MIN_SECTIONS_FOR_AGGREGATION = 5

# Hardcoded baseline importance weights (fallback when no disk file exists).
_SECTION_IMPORTANCE_DEFAULTS: dict[str, float] = {
    # Recalibrated 2026-03-21 from 95 episodes (14-day recency-weighted)
    "episodes":          0.330,
    "related_tasks":     0.320,
    "decision_context":  0.308,
    "knowledge":         0.224,
    "working_memory":    0.213,
    "brain_context":     0.199,
    "attention":         0.172,
    "completions":       0.167,
    "confidence_gate":   0.167,
    "reasoning":         0.141,
    "introspection":     0.129,
    "gwt_broadcast":     0.128,
    "failure_avoidance": 0.126,
    "world_model":       0.122,
    "synaptic":          0.112,
    "metrics":           0.099,
    "brain_goals":       0.089,
    "meta_gradient":     0.083,
}
_DEFAULT_IMPORTANCE = 0.12  # fallback for unknown sections

# Data paths
_WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
RELEVANCE_FILE = os.path.join(_WORKSPACE, "data", "retrieval_quality", "context_relevance.jsonl")
WEIGHTS_FILE = os.path.join(_WORKSPACE, "data", "retrieval_quality", "section_weights.json")


def _load_section_importance() -> dict[str, float]:
    """Load section importance weights from disk, falling back to hardcoded defaults."""
    try:
        with open(WEIGHTS_FILE) as f:
            data = json.load(f)
        weights = data.get("weights", {})
        if weights and isinstance(weights, dict):
            return weights
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return dict(_SECTION_IMPORTANCE_DEFAULTS)


# Live weights — loaded from disk if available, otherwise hardcoded defaults.
# Refreshed nightly by `python3 -m clarvis cognition context-relevance refresh`.
_SECTION_IMPORTANCE: dict[str, float] = _load_section_importance()


def _tokenize(text: str) -> set[str]:
    """Extract meaningful lowercase tokens (3+ chars, no stopwords/template markers)."""
    return {
        w for w in re.findall(r"[a-z][a-z0-9_]{2,}", text.lower())
        if w not in _STOPWORDS and w not in _TEMPLATE_MARKERS
    }


def _jaccard(a: set, b: set) -> float:
    """Jaccard similarity between two token sets."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _containment(section_tokens: set, output_tokens: set) -> float:
    """Containment similarity: fraction of section tokens found in output.

    Better than Jaccard for section-vs-output comparison because sections are
    much smaller than outputs. Even a perfectly referenced section gets low
    Jaccard (~0.01) when |output| >> |section|, but containment correctly
    returns ~1.0 if all section terms appear in the output.
    """
    if not section_tokens or not output_tokens:
        return 0.0
    return len(section_tokens & output_tokens) / len(section_tokens)


# ---------------------------------------------------------------------------
# Semantic containment via MiniLM embeddings
# ---------------------------------------------------------------------------

# Blend ratio: semantic vs token containment.
# Semantic captures synonyms/rephrasings that token overlap misses.
SEMANTIC_WEIGHT = 0.6
TOKEN_WEIGHT = 0.4

# Singleton embedding function — lazily loaded to avoid import cost in tests.
_embed_fn = None
_embed_available: bool | None = None  # None = not yet checked


def _get_embed_fn():
    """Lazily load the MiniLM embedding function. Returns None if unavailable."""
    global _embed_fn, _embed_available
    if _embed_available is False:
        return None
    if _embed_fn is not None:
        return _embed_fn
    try:
        from clarvis.brain.factory import get_embedding_function
        _embed_fn = get_embedding_function(use_onnx=True)
        _embed_available = True
        return _embed_fn
    except Exception as exc:
        _log.debug("Semantic containment unavailable: %s", exc)
        _embed_available = False
        return None


def _cosine_similarity(a, b) -> float:
    """Cosine similarity between two embedding vectors."""
    import numpy as np
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    return float(dot / norm) if norm > 0 else 0.0


def _embed_text(text: str, embed_fn) -> list[float] | None:
    """Embed a single text string. Returns None on failure."""
    if not text or not text.strip():
        return None
    try:
        # ChromaDB embedding functions expect a list and return a list of embeddings
        result = embed_fn([text])
        if result and len(result) > 0:
            return result[0]
    except Exception as exc:
        _log.debug("Embedding failed: %s", exc)
    return None


def _semantic_containment(section_text: str, output_embedding, embed_fn) -> float | None:
    """Compute semantic similarity between section content and output.

    Returns cosine similarity in [0, 1], or None if embedding fails.
    The output_embedding is pre-computed (one per scoring call) to avoid
    re-embedding the full output for every section.
    """
    if output_embedding is None or embed_fn is None:
        return None
    section_emb = _embed_text(section_text, embed_fn)
    if section_emb is None:
        return None
    sim = _cosine_similarity(section_emb, output_embedding)
    # Cosine similarity is in [-1, 1]; clamp to [0, 1]
    return max(0.0, sim)


def parse_brief_sections(brief_text: str) -> dict[str, str]:
    """Parse a tiered brief into named sections.

    Returns dict mapping section_name → section_content.
    Sections are identified by known markers. Text before the first marker
    is assigned to 'decision_context'. Text between --- separators that
    doesn't match any marker is assigned to the preceding section.
    """
    if not brief_text or not brief_text.strip():
        return {}

    # Find all marker positions
    markers_found = []
    for name, pattern in _SECTION_MARKERS:
        match = pattern.search(brief_text)
        if match:
            markers_found.append((match.start(), name, match.end()))

    if not markers_found:
        # No markers found — treat entire brief as one section
        return {"brief": brief_text.strip()}

    # Sort by position
    markers_found.sort(key=lambda x: x[0])

    # If there's text before the first marker, assign to decision_context
    sections = {}
    first_pos = markers_found[0][0]
    if first_pos > 0:
        preamble = brief_text[:first_pos].strip()
        if preamble:
            sections["decision_context"] = preamble

    # Extract content between markers
    for i, (start, name, content_start) in enumerate(markers_found):
        if i + 1 < len(markers_found):
            end = markers_found[i + 1][0]
        else:
            end = len(brief_text)
        content = brief_text[content_start:end].strip().strip("-").strip()
        if content:
            # Merge if same name already exists (e.g., multiple decision_context blocks)
            if name in sections:
                sections[name] += "\n" + content
            else:
                sections[name] = content

    return sections


def score_section_relevance(
    brief_text: str,
    output_text: str,
    task: str = "",
    outcome: str = "",
    threshold: float = REFERENCE_THRESHOLD,
) -> dict:
    """Score how much of the brief was actually referenced in the output.

    Args:
        brief_text: The context brief provided to Claude Code.
        output_text: Claude Code's execution output.
        task: Task description (for logging).
        outcome: Task outcome (success/failure/timeout).
        threshold: Containment threshold for counting a section as referenced.

    Returns:
        Dict with overall score, section counts, and per-section Jaccard scores.
    """
    if not brief_text or not output_text:
        return {
            "overall": 0.0,
            "sections_total": 0,
            "sections_referenced": 0,
            "per_section": {},
            "task": task[:120],
            "outcome": outcome,
        }

    sections = parse_brief_sections(brief_text)
    if not sections:
        return {
            "overall": 0.0,
            "sections_total": 0,
            "sections_referenced": 0,
            "per_section": {},
            "task": task[:120],
            "outcome": outcome,
        }

    output_tokens = _tokenize(output_text)

    # Try to get semantic embeddings (lazy, cached singleton)
    embed_fn = _get_embed_fn()
    output_embedding = None
    if embed_fn is not None:
        output_embedding = _embed_text(output_text[:4000], embed_fn)  # truncate for perf

    per_section = {}
    referenced = 0
    scorable = 0  # sections with enough tokens to evaluate
    weighted_sum = 0.0
    importance_sum = 0.0

    for name, content in sections.items():
        section_tokens = _tokenize(content)
        token_score = _containment(section_tokens, output_tokens)

        # Blend semantic similarity when available
        sem_score = _semantic_containment(content, output_embedding, embed_fn)
        if sem_score is not None:
            score = SEMANTIC_WEIGHT * sem_score + TOKEN_WEIGHT * token_score
        else:
            score = token_score  # fallback: token-only

        per_section[name] = round(score, 4)
        if len(section_tokens) < MIN_SECTION_TOKENS:
            continue  # too small to meaningfully evaluate
        scorable += 1
        if score >= threshold:
            referenced += 1
        # Soft-threshold: proportional credit up to threshold, capped at 1.0.
        # Replaces binary 0/1: containment 0.075 → 0.5, 0.15 → 1.0, 0.30 → 1.0.
        normalized = min(score / threshold, 1.0) if threshold > 0 else (1.0 if score > 0 else 0.0)
        importance = _SECTION_IMPORTANCE.get(name, _DEFAULT_IMPORTANCE)
        weighted_sum += normalized * importance
        importance_sum += importance

    total = scorable if scorable > 0 else len(sections)
    # Weighted overall: importance-weighted soft-threshold scores.
    # Gives continuous signal instead of binary referenced/total.
    overall = weighted_sum / importance_sum if importance_sum > 0 else 0.0

    return {
        "overall": round(overall, 4),
        "sections_total": total,
        "sections_referenced": referenced,
        "per_section": per_section,
        "task": task[:120],
        "outcome": outcome,
    }


def record_relevance(result: dict) -> str:
    """Append a relevance result to the JSONL history file.

    Returns the path written to.
    """
    os.makedirs(os.path.dirname(RELEVANCE_FILE), exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        **result,
    }
    with open(RELEVANCE_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return RELEVANCE_FILE


# Bottom-4 noise sections unconditionally suppressed (mean < 0.12).
# Mirrored from assembly.HARD_SUPPRESS — defined here too so preflight
# can import without pulling in the full assembly module.
# Recalibrated 2026-03-21: failure_avoidance promoted (mean=0.126 > 0.12)
HARD_SUPPRESS = frozenset({
    "meta_gradient",      # mean=0.083
    "brain_goals",        # mean=0.089
    "metrics",            # mean=0.099
    "synaptic",           # mean=0.112
})


def get_suppressed_sections(
    threshold: float = 0.13,
    min_episodes: int = 10,
    days: int = 14,
    relevance_file: str = RELEVANCE_FILE,
) -> set[str]:
    """Return set of section names whose mean relevance is below threshold.

    Always includes HARD_SUPPRESS sections (unconditional noise gate).
    Additionally includes any section whose historical mean is below threshold
    when sufficient episode data exists.

    Returns at minimum HARD_SUPPRESS even when insufficient data exists.
    """
    result = set(HARD_SUPPRESS)

    agg = aggregate_relevance(days=days, relevance_file=relevance_file)
    if agg.get("episodes", 0) < min_episodes:
        return result

    per_section = agg.get("per_section_mean", {})
    result |= {name for name, score in per_section.items() if score < threshold}
    return result


def aggregate_relevance(days: int = 7, relevance_file: str = RELEVANCE_FILE,
                        recency_boost: int = 0) -> dict:
    """Aggregate context relevance scores from episode history.

    Args:
        days: Look back N days from now.
        relevance_file: Path to the JSONL file.
        recency_boost: If > 0, apply exponential recency weighting where the
            most recent `recency_boost` episodes get up to 3x weight.  Episodes
            are sorted newest-first; weight = 1 + 2*exp(-rank * ln(3) / recency_boost)
            so rank-0 (newest) gets 3x, rank=recency_boost gets ~2x, and older
            episodes taper toward 1x.  This lets budget adjustments respond
            within 1-2 cycles instead of waiting for the 14-day window to rotate.

    Returns:
        Dict with mean_relevance, episode count, per_section means,
        and success vs failure breakdown.
    """
    import math

    if not os.path.exists(relevance_file):
        return {"mean_relevance": 0.0, "episodes": 0, "per_section_mean": {}}

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    entries = []

    with open(relevance_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                ts = entry.get("ts", "")
                if ts and ts >= cutoff.isoformat():
                    entries.append(entry)
            except (json.JSONDecodeError, ValueError):
                continue

    if not entries:
        return {"mean_relevance": 0.0, "episodes": 0, "per_section_mean": {}}

    # Filter out sparse episodes — minimal briefs with < MIN_SECTIONS produce
    # unreliable scores (often 0.0) that drag down the aggregate.
    entries = [
        e for e in entries
        if e.get("sections_total", 0) >= MIN_SECTIONS_FOR_AGGREGATION
    ]
    if not entries:
        return {"mean_relevance": 0.0, "episodes": 0, "per_section_mean": {}}

    # Sort newest-first by timestamp for recency weighting
    entries.sort(key=lambda e: e.get("ts", ""), reverse=True)

    # Compute per-entry weights
    if recency_boost > 0 and len(entries) > 1:
        decay = math.log(3) / max(recency_boost, 1)
        entry_weights = [1.0 + 2.0 * math.exp(-i * decay) for i in range(len(entries))]
    else:
        entry_weights = [1.0] * len(entries)

    # Overall weighted mean
    weighted_sum = 0.0
    weight_total = 0.0
    for entry, w in zip(entries, entry_weights):
        if "overall" in entry:
            weighted_sum += entry["overall"] * w
            weight_total += w
    mean_relevance = weighted_sum / weight_total if weight_total > 0 else 0.0

    # Per-section weighted means
    section_weighted: dict[str, float] = {}
    section_weight_totals: dict[str, float] = {}
    for entry, w in zip(entries, entry_weights):
        for name, score in entry.get("per_section", {}).items():
            section_weighted[name] = section_weighted.get(name, 0.0) + score * w
            section_weight_totals[name] = section_weight_totals.get(name, 0.0) + w

    per_section_mean = {
        name: round(section_weighted[name] / section_weight_totals[name], 4)
        for name in section_weighted
        if section_weight_totals.get(name, 0) > 0
    }

    # Breakdown by outcome
    success_sum, success_w = 0.0, 0.0
    failure_sum, failure_w = 0.0, 0.0
    for entry, w in zip(entries, entry_weights):
        if "overall" not in entry:
            continue
        if entry.get("outcome") == "success":
            success_sum += entry["overall"] * w
            success_w += w
        else:
            failure_sum += entry["overall"] * w
            failure_w += w

    return {
        "mean_relevance": round(mean_relevance, 4),
        "episodes": len(entries),
        "per_section_mean": per_section_mean,
        "success_mean": round(success_sum / success_w, 4) if success_w > 0 else 0.0,
        "failure_mean": round(failure_sum / failure_w, 4) if failure_w > 0 else 0.0,
    }


def regenerate_report(days: int = 7) -> dict:
    """Regenerate brief_v2_report.json with real context_relevance from episode data.

    Reads the existing report, enriches it with episode-derived context_relevance
    and per-section breakdown, then writes it back. Safe to run as a weekly cron job.

    Returns the aggregated relevance data that was merged into the report.
    """
    report_path = os.path.join(_WORKSPACE, "data", "benchmarks", "brief_v2_report.json")
    agg = aggregate_relevance(days=days, relevance_file=RELEVANCE_FILE)

    if agg["episodes"] < 3:
        return agg

    report = {}
    if os.path.exists(report_path):
        try:
            with open(report_path) as f:
                report = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    report["context_relevance_from_episodes"] = {
        "mean_relevance": agg["mean_relevance"],
        "episodes": agg["episodes"],
        "per_section_mean": agg["per_section_mean"],
        "success_mean": agg.get("success_mean", 0.0),
        "failure_mean": agg.get("failure_mean", 0.0),
        "generated": datetime.now(timezone.utc).isoformat(),
        "lookback_days": days,
    }

    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    return agg


def refresh_weights(days: int = 14, recency_boost: int = 5,
                    min_episodes: int = 10) -> dict:
    """Aggregate recent episode data and write updated section importance weights to disk.

    This closes the feedback loop: postflight records per-section relevance,
    this function aggregates it into weights, and assembly.py / scoring reads
    the weights on next import.

    Returns dict with weights written and metadata.
    """
    agg = aggregate_relevance(days=days, recency_boost=recency_boost)

    if agg.get("episodes", 0) < min_episodes:
        return {
            "status": "skipped",
            "reason": f"insufficient episodes ({agg.get('episodes', 0)} < {min_episodes})",
            "episodes": agg.get("episodes", 0),
        }

    per_section = agg.get("per_section_mean", {})
    # Merge with defaults so all known sections have a weight
    weights = dict(_SECTION_IMPORTANCE_DEFAULTS)
    weights.update(per_section)

    output = {
        "weights": weights,
        "episodes": agg["episodes"],
        "mean_relevance": agg["mean_relevance"],
        "days": days,
        "recency_boost": recency_boost,
        "refreshed": datetime.now(timezone.utc).isoformat(),
    }

    os.makedirs(os.path.dirname(WEIGHTS_FILE), exist_ok=True)
    with open(WEIGHTS_FILE, "w") as f:
        json.dump(output, f, indent=2)

    # Update in-memory weights for this process
    global _SECTION_IMPORTANCE
    _SECTION_IMPORTANCE = weights

    return {
        "status": "ok",
        "weights_file": WEIGHTS_FILE,
        "episodes": agg["episodes"],
        "mean_relevance": agg["mean_relevance"],
        "sections": len(weights),
    }
