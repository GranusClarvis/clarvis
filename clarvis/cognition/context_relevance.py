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
import os
import re
from datetime import datetime, timezone, timedelta

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

# Empirical importance weights per section — derived from 14-day mean relevance
# data (2026-03-16).  Sections with higher historical mean relevance are weighted
# more in the overall score.  Sections not listed here get a default weight.
_SECTION_IMPORTANCE: dict[str, float] = {
    "related_tasks":     0.304,
    "episodes":          0.273,
    "decision_context":  0.267,
    "completions":       0.183,
    "confidence_gate":   0.167,
    "brain_context":     0.158,
    "reasoning":         0.157,
    "knowledge":         0.155,
    "working_memory":    0.145,
    "attention":         0.146,
    "gwt_broadcast":     0.128,
    "introspection":     0.129,
    "world_model":       0.122,
    "synaptic":          0.112,
    "metrics":           0.100,
    "failure_avoidance": 0.091,
    "brain_goals":       0.089,
    "meta_gradient":     0.054,
}
_DEFAULT_IMPORTANCE = 0.12  # fallback for unknown sections

# Data paths
_WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
RELEVANCE_FILE = os.path.join(_WORKSPACE, "data", "retrieval_quality", "context_relevance.jsonl")


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
    per_section = {}
    referenced = 0
    scorable = 0  # sections with enough tokens to evaluate
    weighted_sum = 0.0
    importance_sum = 0.0

    for name, content in sections.items():
        section_tokens = _tokenize(content)
        score = _containment(section_tokens, output_tokens)
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


def get_suppressed_sections(
    threshold: float = 0.13,
    min_episodes: int = 10,
    days: int = 14,
    relevance_file: str = RELEVANCE_FILE,
) -> set[str]:
    """Return set of section names whose mean relevance is below threshold.

    Sections consistently below the threshold are noise — the context they
    provide is almost never referenced in task output.  Callers (preflight,
    assembly) should skip injecting these sections to improve overall
    context relevance.

    Returns empty set when insufficient data exists (< min_episodes).
    """
    agg = aggregate_relevance(days=days, relevance_file=relevance_file)
    if agg.get("episodes", 0) < min_episodes:
        return set()

    per_section = agg.get("per_section_mean", {})
    return {name for name, score in per_section.items() if score < threshold}


def aggregate_relevance(days: int = 7, relevance_file: str = RELEVANCE_FILE) -> dict:
    """Aggregate context relevance scores from episode history.

    Args:
        days: Look back N days from now.
        relevance_file: Path to the JSONL file.

    Returns:
        Dict with mean_relevance, episode count, per_section means,
        and success vs failure breakdown.
    """
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

    # Overall mean
    overall_scores = [e["overall"] for e in entries if "overall" in e]
    mean_relevance = sum(overall_scores) / len(overall_scores) if overall_scores else 0.0

    # Per-section means
    section_scores: dict[str, list[float]] = {}
    for entry in entries:
        for name, score in entry.get("per_section", {}).items():
            section_scores.setdefault(name, []).append(score)

    per_section_mean = {
        name: round(sum(scores) / len(scores), 4)
        for name, scores in section_scores.items()
    }

    # Breakdown by outcome
    success_scores = [e["overall"] for e in entries if e.get("outcome") == "success" and "overall" in e]
    failure_scores = [e["overall"] for e in entries if e.get("outcome") != "success" and "overall" in e]

    return {
        "mean_relevance": round(mean_relevance, 4),
        "episodes": len(entries),
        "per_section_mean": per_section_mean,
        "success_mean": round(sum(success_scores) / len(success_scores), 4) if success_scores else 0.0,
        "failure_mean": round(sum(failure_scores) / len(failure_scores), 4) if failure_scores else 0.0,
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
