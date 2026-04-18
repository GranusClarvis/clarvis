"""
Dynamic Context Pruning (DyCP) — query-dependent section-level pruning.

Inspired by DyCP (arXiv:2601.07994): score each brief section against the
task query and prune sections that are both historically low-relevance AND
have low task-overlap.  Protected sections are never pruned.

Also provides:
  - Dynamic suppress feedback loop (hard/soft suppression from live data)
  - Task-containment scoring (name-based and content-based)
  - Knowledge-hint reranking by keyword relevance
"""

import logging
import re
import time

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Sections that are never pruned by DyCP (high-value regardless of task overlap)
DYCP_PROTECTED_SECTIONS = frozenset({
    "decision_context", "reasoning", "knowledge", "related_tasks",
    "episodes", "completions",
})

# Minimum containment (section∩task / section) to keep a prunable section.
# Calibrated from per-section data: sections with mean relevance < 0.10
# almost never contribute. Raised 0.04→0.08 on 2026-03-18 to prune more
# aggressively — the 5 weakest sections (mean < 0.12) were still leaking through.
# Raised 0.08→0.10 on 2026-03-30 to further improve brief compression ratio.
DYCP_MIN_CONTAINMENT = 0.10

# Also consider historical mean relevance — sections historically below
# this AND below task-containment threshold get pruned.
# History: 0.13→0.16 (2026-03-15) → 0.20 (2026-03-18) → 0.15 (2026-03-19).
# Lowered back: 0.20 was too aggressive — pruned moderately useful sections
# (brain_context=0.163, confidence_gate=0.167) that agents do reference.
# Tier 0 (hardcoded < 0.15) still catches truly noisy sections.
DYCP_HISTORICAL_FLOOR = 0.15

# Sections with zero task overlap AND historical score below this
# stricter ceiling are also pruned (DyCP query-dependent tier 2).
# Lowered 0.20→0.15 on 2026-03-19: same rationale — borderline-useful
# sections (hist 0.15-0.20) shouldn't be pruned even with zero overlap.
DYCP_ZERO_OVERLAP_CEILING = 0.15

# Hard-suppressed: bottom-4 noise sections with 14-day mean < 0.12.
# These are ALWAYS suppressed — no task-containment override.  They waste
# ~600 tokens per brief for near-zero downstream signal.
# Recalibrated 2026-03-21: failure_avoidance promoted (mean=0.126 > 0.12)
HARD_SUPPRESS = frozenset({
    "meta_gradient",      # mean=0.083
    "brain_goals",        # mean=0.089
    "metrics",            # mean=0.099
    "synaptic",           # mean=0.112
    "world_model",        # HELPFUL=5.6%, NOISE=22.2% — suppress until HELPFUL≥20%
})

# Soft-suppressed: borderline sections (mean 0.12-0.13) that ARE included
# when task-containment exceeds DYCP_DEFAULT_SUPPRESS_CONTAINMENT_OVERRIDE.
# This list is separate from DyCP pruning — DyCP prunes post-assembly,
# while default-suppress prevents generation in the first place (cheaper).
DYCP_DEFAULT_SUPPRESS = frozenset({
    "world_model",        # mean=0.122
    "gwt_broadcast",      # mean=0.128
    "introspection",      # mean=0.129
})
# Task-containment threshold to override default suppression — if the task
# tokens overlap significantly with a suppressed section, include it anyway.
DYCP_DEFAULT_SUPPRESS_CONTAINMENT_OVERRIDE = 0.10

# Per-section overrides: sections whose content words rarely match task tokens
# need a higher bar before being included. gwt_broadcast (conscious workspace
# broadcast) contains attention codelets and winner labels that often share
# generic tokens with tasks without actually being relevant — require stronger
# containment (0.20) to override suppression.
DYCP_PER_SECTION_CONTAINMENT_OVERRIDE = {
    "gwt_broadcast": 0.20,
}

# Threshold for dynamic hard-suppression feedback loop.  Sections with
# 14-day recency-weighted mean below this are auto-suppressed (same as
# HARD_SUPPRESS but computed from live data instead of hardcoded).
DYNAMIC_SUPPRESS_THRESHOLD = 0.12
# Sections with mean between DYNAMIC_SUPPRESS_THRESHOLD and this value
# become soft-suppressed (overridable by task containment).
DYNAMIC_SOFT_SUPPRESS_CEILING = 0.13

# Cache: (timestamp, hard_set, soft_set).  TTL = 300s (5 min) to avoid
# re-reading the relevance JSONL on every brief assembly.
_dynamic_suppress_cache: tuple = (0.0, None, None)
_DYNAMIC_SUPPRESS_TTL = 300

# Cache of section name → content token sample from the last assembled brief.
# Populated by dycp_prune_brief(); used by _dycp_task_containment_fast() so
# that suppression decisions consider actual section content, not just the
# section name.  First run (empty cache) falls back to name-only matching.
_section_content_cache: dict = {}

# Maximum number of content tokens to sample per section for the cache.
# Kept small to make the containment check fast (O(n) set intersection).
_CONTENT_SAMPLE_SIZE = 40

# Common stopwords for token-based containment scoring
_CONTAINMENT_STOPWORDS = frozenset({
    "the", "and", "for", "are", "but", "not", "you", "all", "can",
    "had", "her", "was", "one", "our", "out", "has", "have", "from",
    "with", "this", "that", "they", "been", "will", "each", "make",
    "like", "into", "than", "its", "also", "use", "two", "how",
})

# Stopwords excluded from keyword overlap scoring (knowledge reranking)
_RERANK_STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "must", "to", "of",
    "in", "for", "on", "with", "at", "by", "from", "as", "into", "through",
    "during", "before", "after", "above", "below", "between", "out", "off",
    "over", "under", "again", "further", "then", "once", "and", "but", "or",
    "nor", "not", "so", "very", "just", "also", "than", "that", "this",
    "these", "those", "it", "its", "all", "each", "every", "both", "few",
    "more", "most", "other", "some", "such", "only", "own", "same", "too",
    "add", "use", "new", "get", "set", "run", "see", "now", "one", "two",
})


# ---------------------------------------------------------------------------
# Dynamic suppress feedback loop
# ---------------------------------------------------------------------------

def _compute_dynamic_suppress(recency_boost_episodes=5, min_episodes=5):
    """Compute hard and soft suppress sets from live relevance data.

    Returns (hard_set, soft_set) where:
      - hard_set: sections with 14-day recency-weighted mean < DYNAMIC_SUPPRESS_THRESHOLD
      - soft_set: sections with mean in [DYNAMIC_SUPPRESS_THRESHOLD, DYNAMIC_SOFT_SUPPRESS_CEILING)

    Falls back to static HARD_SUPPRESS / DYCP_DEFAULT_SUPPRESS if no data.
    """
    global _dynamic_suppress_cache
    now = time.monotonic()
    cached_ts, cached_hard, cached_soft = _dynamic_suppress_cache
    if cached_hard is not None and (now - cached_ts) < _DYNAMIC_SUPPRESS_TTL:
        return cached_hard, cached_soft

    try:
        from clarvis.cognition.context_relevance import aggregate_relevance
        agg = aggregate_relevance(days=14, recency_boost=recency_boost_episodes)
    except Exception:
        _dynamic_suppress_cache = (now, HARD_SUPPRESS, DYCP_DEFAULT_SUPPRESS)
        return HARD_SUPPRESS, DYCP_DEFAULT_SUPPRESS

    if agg.get("episodes", 0) < min_episodes:
        _dynamic_suppress_cache = (now, HARD_SUPPRESS, DYCP_DEFAULT_SUPPRESS)
        return HARD_SUPPRESS, DYCP_DEFAULT_SUPPRESS

    per_section = agg.get("per_section_mean", {})
    if not per_section:
        _dynamic_suppress_cache = (now, HARD_SUPPRESS, DYCP_DEFAULT_SUPPRESS)
        return HARD_SUPPRESS, DYCP_DEFAULT_SUPPRESS

    hard = set()
    soft = set()
    for section, mean_score in per_section.items():
        # Never suppress protected sections regardless of score
        if section in DYCP_PROTECTED_SECTIONS:
            continue
        if mean_score < DYNAMIC_SUPPRESS_THRESHOLD:
            hard.add(section)
        elif mean_score < DYNAMIC_SOFT_SUPPRESS_CEILING:
            soft.add(section)

    hard = frozenset(hard) if hard else HARD_SUPPRESS
    soft = frozenset(soft) if soft else DYCP_DEFAULT_SUPPRESS
    _dynamic_suppress_cache = (now, hard, soft)
    return hard, soft


# ---------------------------------------------------------------------------
# Task containment scoring
# ---------------------------------------------------------------------------

def _dycp_task_containment_fast(section_name: str, task_text: str) -> float:
    """Fast containment check using section name + cached content vs task tokens.

    Checks both the section *name* tokens AND a small sample of actual content
    tokens (cached from the previous brief assembly).  This prevents sections
    with relevant content but non-matching names from being wrongly suppressed.
    """
    task_lower = task_text.lower()
    task_words = set(re.findall(r"[a-z][a-z0-9_]{2,}", task_lower))
    if not task_words:
        return 0.0

    # Name-based score (original heuristic)
    name_words = set(section_name.replace("_", " ").split())
    name_score = (
        len(name_words & task_words) / len(name_words) if name_words else 0.0
    )

    # Content-based score from cache (populated by previous dycp_prune_brief)
    content_tokens = _section_content_cache.get(section_name)
    if content_tokens:
        overlap = len(content_tokens & task_words)
        content_score = overlap / max(1, len(content_tokens))
    else:
        content_score = 0.0

    # Return the higher of the two — either signal is enough to keep
    return max(name_score, content_score)


def _dycp_task_containment(section_text: str, task_text: str) -> float:
    """Compute bidirectional containment between section and task tokens.

    Returns max(section_in_task, task_in_section) — captures relevance
    regardless of which text is larger.
    """
    sec_tokens = set(re.findall(r"[a-z][a-z0-9_]{2,}", section_text.lower()))
    task_tokens = set(re.findall(r"[a-z][a-z0-9_]{2,}", task_text.lower()))
    sec_tokens -= _CONTAINMENT_STOPWORDS
    task_tokens -= _CONTAINMENT_STOPWORDS
    if not sec_tokens or not task_tokens:
        return 0.0
    sec_in_task = len(sec_tokens & task_tokens) / len(sec_tokens)
    task_in_sec = len(sec_tokens & task_tokens) / len(task_tokens)
    return max(sec_in_task, task_in_sec)


# ---------------------------------------------------------------------------
# Section suppression
# ---------------------------------------------------------------------------

def should_suppress_section(section_name: str, task_text: str = "") -> bool:
    """Check if a section should be suppressed before generation.

    Uses a dynamic feedback loop: sections are classified as hard or soft
    suppressed based on their 14-day recency-weighted mean relevance score
    (computed from live context_relevance data).

    Hard-suppressed (mean < 0.12): ALWAYS suppressed — no override.
    Soft-suppressed (mean 0.12-0.13): suppressed unless task-containment
    exceeds the override threshold.
    Protected sections are never suppressed.
    """
    if section_name in DYCP_PROTECTED_SECTIONS:
        return False
    # Static hard suppress: unconditional floor — these are always suppressed
    if section_name in HARD_SUPPRESS:
        return True
    # Dynamic feedback loop: compute suppress sets from live relevance data
    dynamic_hard, dynamic_soft = _compute_dynamic_suppress()
    # Dynamic hard suppress: sections classified as noise from live data
    if section_name in dynamic_hard:
        return True
    # Soft suppress: can be overridden by task containment
    if section_name not in dynamic_soft:
        return False
    if not task_text:
        return True  # no task context → suppress by default
    containment = _dycp_task_containment_fast(section_name, task_text)
    threshold = DYCP_PER_SECTION_CONTAINMENT_OVERRIDE.get(
        section_name, DYCP_DEFAULT_SUPPRESS_CONTAINMENT_OVERRIDE
    )
    return containment < threshold


def _load_historical_section_means() -> dict:
    """Load per-section historical mean relevance scores.

    Returns dict mapping section_name → mean_relevance, or empty dict on error.
    """
    try:
        from clarvis.cognition.context_relevance import aggregate_relevance
        agg = aggregate_relevance(days=14)
        if agg.get("episodes", 0) >= 5:
            return agg.get("per_section_mean", {})
    except Exception:
        logger.debug("Failed to load historical section means", exc_info=True)
    return {}


# ---------------------------------------------------------------------------
# Cross-section sentence dedup
# ---------------------------------------------------------------------------

# Minimum Jaccard similarity to consider two lines near-duplicates.
_XSEC_DEDUP_JACCARD = 0.55
# Lines shorter than this (non-whitespace chars) are never deduped — they're
# structural (headers, separators, stubs) rather than content.
_XSEC_DEDUP_MIN_LEN = 40


def _tokenize_line(line: str) -> frozenset:
    """Extract lowercase 3+ char tokens from a line for similarity comparison."""
    return frozenset(re.findall(r"[a-z][a-z0-9_]{2,}", line.lower())) - _CONTAINMENT_STOPWORDS


def _cross_section_dedup(text: str) -> str:
    """Remove near-duplicate lines across section boundaries.

    Scans all content lines and drops later occurrences that have high
    Jaccard overlap with an earlier line (from a *different* section).
    Structural lines (headers, separators, short lines) are always kept.

    This catches the common pattern where episodic hints, knowledge hints,
    and working memory repeat the same information in slightly different
    phrasing, bloating the brief without adding signal.
    """
    if not text:
        return text

    lines = text.split("\n")
    if len(lines) < 10:
        return text  # too short to benefit

    # Build fingerprints for content lines; track which section each is in.
    # We detect section boundaries by looking for common header patterns.
    _header_re = re.compile(
        r"^(?:#{1,4}\s|[A-Z][A-Z _/]{4,}:|---$|\[.*: pruned)",
    )

    current_section_idx = 0
    line_meta = []  # (tokens, section_idx, is_content)
    for line in lines:
        stripped = line.strip()
        # Detect section boundary
        if _header_re.match(stripped) or stripped == "---":
            if stripped != "---":
                current_section_idx += 1
            line_meta.append((frozenset(), current_section_idx, False))
            continue

        is_content = len(stripped) >= _XSEC_DEDUP_MIN_LEN
        tokens = _tokenize_line(stripped) if is_content else frozenset()
        line_meta.append((tokens, current_section_idx, is_content))

    # First pass: collect fingerprints keyed by section
    seen: list[tuple[frozenset, int]] = []  # (tokens, section_idx)
    drop = set()  # line indices to drop

    for i, (tokens, sec_idx, is_content) in enumerate(line_meta):
        if not is_content or len(tokens) < 3:
            continue
        # Check against all previously seen content lines from OTHER sections
        for prev_tokens, prev_sec in seen:
            if prev_sec == sec_idx:
                continue  # same section — intra-section dedup is not our job
            # Jaccard similarity
            intersection = len(tokens & prev_tokens)
            union = len(tokens | prev_tokens)
            if union > 0 and intersection / union >= _XSEC_DEDUP_JACCARD:
                drop.add(i)
                break
        else:
            seen.append((tokens, sec_idx))

    if not drop:
        return text

    result = [line for i, line in enumerate(lines) if i not in drop]

    # Clean up any resulting empty sequences (consecutive blank lines → max 1)
    cleaned = []
    for line in result:
        if line.strip() == "" and cleaned and cleaned[-1].strip() == "":
            continue
        cleaned.append(line)

    logger.debug("cross-section dedup: removed %d near-duplicate lines", len(drop))
    return "\n".join(cleaned)


# ---------------------------------------------------------------------------
# DyCP brief pruning
# ---------------------------------------------------------------------------

def _update_content_cache(sections: dict) -> None:
    """Update the section content cache for future containment checks."""
    global _section_content_cache
    new_cache = {}
    for sname, scontent in sections.items():
        tokens = set(re.findall(r"[a-z][a-z0-9_]{2,}", scontent.lower())) - _CONTAINMENT_STOPWORDS
        if len(tokens) > _CONTENT_SAMPLE_SIZE:
            tokens = set(sorted(tokens)[:_CONTENT_SAMPLE_SIZE])
        new_cache[sname] = tokens
    _section_content_cache = new_cache


def _find_prunable_sections(sections: dict, task_text: str, historical: dict) -> set:
    """Identify sections to prune based on task containment and historical scores."""
    pruned = set()
    for name, content in sections.items():
        if name in DYCP_PROTECTED_SECTIONS:
            continue
        enriched = f"{name.replace('_', ' ')} {content}"
        containment = _dycp_task_containment(enriched, task_text)
        if containment >= DYCP_MIN_CONTAINMENT:
            continue
        hist_score = historical.get(name, 0.5)
        # Tier 0: chronic noise (hist < 0.15) → always prune
        if hist_score < 0.15:
            pruned.add(name)
        # Tier 1: historically weak + low task overlap → prune
        elif hist_score < DYCP_HISTORICAL_FLOOR:
            pruned.add(name)
        # Tier 2: zero overlap + borderline history → prune
        elif containment == 0.0 and hist_score < DYCP_ZERO_OVERLAP_CEILING:
            pruned.add(name)
    return pruned


def _rebuild_pruned_brief(brief_text: str, pruned_names: set, historical: dict) -> str:
    """Replace pruned sections with 1-line stubs and clean up separators."""
    from clarvis.cognition.context_relevance import _SECTION_MARKERS
    lines = brief_text.split("\n")
    result_lines = []
    skip_until_next = False

    for line in lines:
        new_section = None
        for sname, pattern in _SECTION_MARKERS:
            if pattern.search(line):
                new_section = sname
                break
        if new_section is not None:
            skip_until_next = new_section in pruned_names
            if skip_until_next:
                hist_score = historical.get(new_section, 0.0)
                result_lines.append(
                    f"[{new_section}: pruned — hist_relevance={hist_score:.2f}]"
                )
                continue
        elif line.strip() == "---":
            skip_until_next = False
        if not skip_until_next:
            result_lines.append(line)

    # Clean consecutive/trailing separators
    cleaned = []
    for line in result_lines:
        if line.strip() == "---" and cleaned and cleaned[-1].strip() == "---":
            continue
        cleaned.append(line)
    while cleaned and cleaned[-1].strip() == "---":
        cleaned.pop()
    return "\n".join(cleaned)


def dycp_prune_brief(brief_text: str, task_text: str) -> str:
    """Dynamic Context Pruning — remove sections irrelevant to the current task.

    Inspired by DyCP (arXiv:2601.07994): query-dependent segment-level pruning.
    Protected sections are never pruned.
    """
    if not brief_text or not task_text:
        return brief_text
    try:
        from clarvis.cognition.context_relevance import parse_brief_sections
    except ImportError:
        return brief_text

    sections = parse_brief_sections(brief_text)
    if len(sections) <= 3:
        return brief_text

    _update_content_cache(sections)
    historical = _load_historical_section_means()
    pruned_names = _find_prunable_sections(sections, task_text, historical)

    if pruned_names:
        text_after_prune = _rebuild_pruned_brief(brief_text, pruned_names, historical)
    else:
        text_after_prune = brief_text

    return _cross_section_dedup(text_after_prune)


# ---------------------------------------------------------------------------
# Knowledge hint reranking
# ---------------------------------------------------------------------------

def _extract_task_keywords(task_text):
    """Extract meaningful keywords from task text for relevance scoring."""
    words = set(re.findall(r'[a-z][a-z0-9_]+', task_text.lower()))
    # Also extract backtick content (file names, identifiers)
    backtick_tokens = re.findall(r'`([^`]+)`', task_text)
    for tok in backtick_tokens:
        words.update(re.findall(r'[a-z][a-z0-9_]+', tok.lower()))
    # Extract UPPER_SNAKE identifiers (like CONTEXT_BRAIN_SEARCH_RERANKING)
    upper_ids = re.findall(r'[A-Z][A-Z0-9_]{3,}', task_text)
    for uid in upper_ids:
        words.update(w.lower() for w in uid.split('_') if len(w) >= 3)
    return words - _RERANK_STOPWORDS


def rerank_knowledge_hints(knowledge_hints, current_task, min_score=0.08,
                           boost_threshold=0.25):
    """Rerank knowledge hint lines by keyword relevance to the current task.

    Each line of knowledge_hints is scored by:
      - Keyword overlap: |task_words ∩ hint_words| / |task_words|
      - Identifier match bonus: extra weight for matching file/function names

    Lines below min_score are dropped (tangential matches).
    Lines above boost_threshold get priority ordering.

    Returns reranked knowledge_hints string.
    """
    if not knowledge_hints or not current_task:
        return knowledge_hints

    task_keywords = _extract_task_keywords(current_task)
    if not task_keywords:
        return knowledge_hints

    # Extract high-signal identifiers (file names, function names) for bonus
    task_identifiers = set()
    for kw in task_keywords:
        if '_' in kw or '.' in kw:  # underscore_names or file.ext
            task_identifiers.add(kw)
    # Also grab CamelCase and file paths from original text
    task_identifiers.update(
        t.lower() for t in re.findall(r'[a-z_]+\.py|[a-z_]+\.sh', current_task.lower())
    )

    lines = knowledge_hints.split('\n')
    scored = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        hint_words = set(re.findall(r'[a-z][a-z0-9_]+', stripped.lower()))
        hint_words -= _RERANK_STOPWORDS

        if not hint_words:
            scored.append((0.0, line))
            continue

        # Base score: keyword overlap ratio
        overlap = task_keywords & hint_words
        base_score = len(overlap) / len(task_keywords) if task_keywords else 0.0

        # Identifier bonus: matching specific file/function names is high signal
        id_bonus = 0.0
        if task_identifiers:
            id_overlap = task_identifiers & hint_words
            id_bonus = len(id_overlap) * 0.15  # 0.15 per identifier match

        score = base_score + id_bonus
        scored.append((score, line))

    # Filter out low-relevance lines
    kept = [(s, l) for s, l in scored if s >= min_score]

    if not kept:
        # If all filtered out, keep top 2 by score as fallback
        scored.sort(key=lambda x: x[0], reverse=True)
        kept = scored[:2]

    # Sort by score descending (most relevant first)
    kept.sort(key=lambda x: x[0], reverse=True)

    return '\n'.join(line for _, line in kept)
