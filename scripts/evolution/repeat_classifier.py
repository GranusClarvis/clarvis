#!/usr/bin/env python3
"""
repeat_classifier.py — Smart repeat detection for research selection/requeue paths.

Combines canonical topic matching with scope comparison to distinguish:
  - TRUE REPEATS:  same topic + same scope (block)
  - SCOPE SHIFTS:  same topic + different scope (allow as REFINEMENT)
  - NOVEL TOPICS:  no matching canonical topic (allow)

Design principles:
  1. Minimize false positives — never suppress a genuinely new angle
  2. Scope dimensions: depth (intro→deep-dive), angle (theory→practice→critique),
     specificity (broad→narrow)
  3. Canonical topic IDs: stable slugs derived from canonical_name for cross-system refs
  4. Shares word_set/word_overlap from research_novelty.py (single source of truth)

Integration:
  - Used by writer.py _is_research_topic_completed() for injection-time gating
  - Used by cron_research.sh pre-select novelty gate
  - CLI: python3 repeat_classifier.py classify "topic text"
         python3 repeat_classifier.py compare "topic A" "topic B"

Verdicts:
  NOVEL         — No matching canonical topic. Proceed.
  SCOPE_SHIFT   — Same topic, different scope. Proceed as REFINEMENT.
  REPEAT        — Same topic, same scope, recently covered. Block.
  SHALLOW_PRIOR — Same topic, same scope, but prior was shallow. Proceed.
"""

import hashlib
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from typing import Optional

# Import shared utilities from research_novelty (single source of truth)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)
try:
    from research_novelty import (
        TopicRegistry,
        TopicEntry,
        _normalize,
        _word_set,
        _word_overlap,
        _extract_anchor_phrases,
        _days_since,
        REFINEMENT_AGE_DAYS,
        REFINEMENT_MIN_MEMORIES,
        MAX_RESEARCH_COUNT,
    )
except ImportError:
    # Fallback for testing in isolation
    raise ImportError("repeat_classifier requires research_novelty.py in same directory")

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))

# --- Verdict constants ---
NOVEL = "NOVEL"
SCOPE_SHIFT = "SCOPE_SHIFT"
REPEAT = "REPEAT"
SHALLOW_PRIOR = "SHALLOW_PRIOR"

# --- Scope extraction ---

# Depth markers: ordered from shallow to deep
DEPTH_MARKERS = {
    "intro": ["intro", "basics", "overview", "primer", "getting started", "101", "beginner"],
    "survey": ["survey", "review", "landscape", "taxonomy", "state of the art", "comparison"],
    "focused": ["deep dive", "deep-dive", "analysis", "investigation", "focused", "case study"],
    "implementation": ["implementation", "build", "prototype", "code", "hands-on", "practical",
                       "apply", "integrate", "migration"],
    "advanced": ["advanced", "formalization", "mathematical", "theoretical foundations",
                 "scalable", "optimization", "production"],
}

# Angle markers: different perspectives on the same topic
ANGLE_MARKERS = {
    "theory": ["theory", "theoretical", "formal", "mathematical", "proof", "axiom"],
    "practice": ["practical", "applied", "real-world", "production", "deployment", "hands-on"],
    "critique": ["critique", "criticism", "limitations", "problems", "challenges", "weaknesses"],
    "comparison": ["comparison", "versus", "vs", "benchmark", "evaluation", "tradeoffs"],
    "synthesis": ["synthesis", "integration", "combining", "hybrid", "unified", "holistic"],
}

# Specificity markers
SPECIFICITY_MARKERS = {
    "broad": ["broad", "general", "comprehensive", "complete", "full", "all"],
    "focused": ["specific", "focused", "particular", "targeted", "narrow", "single"],
}


@dataclass
class Scope:
    """Extracted scope dimensions from a topic description."""
    depth: str = "unknown"       # intro|survey|focused|implementation|advanced|unknown
    angle: str = "unknown"       # theory|practice|critique|comparison|synthesis|unknown
    specificity: str = "unknown" # broad|focused|unknown
    scope_terms: list = None     # Raw terms that contributed to scope detection

    def __post_init__(self):
        if self.scope_terms is None:
            self.scope_terms = []

    def differs_from(self, other: "Scope") -> bool:
        """Check if two scopes are meaningfully different.

        Rules:
        1. Two unknowns on the same dimension do NOT count as different
           (avoids false scope-shift on vague topics).
        2. Two known, different values on the same dimension = definite difference.
        3. If the NEW scope has a specific non-default signal (critique, implementation,
           advanced, comparison) and the prior is fully unknown, count it as a likely
           scope shift — the new request is explicitly angling for something specific
           that the generic prior probably didn't cover.
        """
        diffs = 0
        # Rule 2: both known, different
        if self.depth != "unknown" and other.depth != "unknown" and self.depth != other.depth:
            diffs += 1
        if self.angle != "unknown" and other.angle != "unknown" and self.angle != other.angle:
            diffs += 1
        if self.specificity != "unknown" and other.specificity != "unknown" and self.specificity != other.specificity:
            diffs += 1
        if diffs >= 1:
            return True

        # Rule 3: new has strong signal, prior is fully unknown
        # Only applies to high-specificity angles/depths that are unlikely
        # to overlap with a generic prior research run.
        STRONG_SIGNALS = {"critique", "implementation", "advanced", "comparison", "synthesis"}
        if other.is_fully_unknown():
            if self.depth in STRONG_SIGNALS or self.angle in STRONG_SIGNALS:
                return True

        return False

    def is_fully_unknown(self) -> bool:
        return self.depth == "unknown" and self.angle == "unknown" and self.specificity == "unknown"


def extract_scope(text: str) -> Scope:
    """Extract scope dimensions from topic text.

    Uses keyword matching against scope marker dictionaries.
    Returns Scope with detected dimensions (or 'unknown' if not detectable).
    """
    norm = _normalize(text).lower()
    scope_terms = []

    # Detect depth
    depth = "unknown"
    for level, markers in DEPTH_MARKERS.items():
        for marker in markers:
            if marker in norm:
                depth = level
                scope_terms.append(f"depth:{marker}")
                break
        if depth != "unknown":
            break

    # Detect angle
    angle = "unknown"
    for perspective, markers in ANGLE_MARKERS.items():
        for marker in markers:
            if marker in norm:
                angle = perspective
                scope_terms.append(f"angle:{marker}")
                break
        if angle != "unknown":
            break

    # Detect specificity
    specificity = "unknown"
    for level, markers in SPECIFICITY_MARKERS.items():
        for marker in markers:
            if marker in norm:
                specificity = level
                scope_terms.append(f"spec:{marker}")
                break
        if specificity != "unknown":
            break

    return Scope(depth=depth, angle=angle, specificity=specificity, scope_terms=scope_terms)


# --- Canonical topic ID ---

def canonical_topic_id(name: str) -> str:
    """Generate a stable canonical topic ID from a topic name.

    Properties:
      - Deterministic: same input always produces same ID
      - Slug-based: human-readable prefix + short hash suffix
      - Collision-resistant: hash suffix distinguishes similar names
    """
    norm = _normalize(name)
    # Create slug: lowercase, alphanumeric + hyphens only
    slug = re.sub(r"[^a-z0-9]+", "-", norm).strip("-")
    # Truncate slug to reasonable length
    slug = slug[:50].rstrip("-")
    # Add short hash for collision resistance
    h = hashlib.sha256(norm.encode()).hexdigest()[:8]
    return f"{slug}-{h}" if slug else h


# --- Repeat Classifier ---

@dataclass
class ClassifyResult:
    """Result of repeat classification."""
    verdict: str            # NOVEL|SCOPE_SHIFT|REPEAT|SHALLOW_PRIOR
    reason: str             # Human-readable explanation
    topic_id: str = ""      # Canonical topic ID (if matched)
    canonical_name: str = ""  # Matched canonical topic name
    new_scope: Optional[Scope] = None
    prior_scope: Optional[Scope] = None
    match_score: float = 0.0  # Word overlap score with matched topic
    research_count: int = 0
    memory_count: int = 0
    age_days: float = 0.0


class RepeatClassifier:
    """Smart repeat detection combining topic identity with scope comparison.

    Integrates with TopicRegistry for canonical topic matching, then adds
    scope-aware comparison to distinguish genuine repeats from scope shifts.
    """

    def __init__(self, registry: Optional[TopicRegistry] = None):
        self._registry = registry or TopicRegistry()

    def classify(self, topic_text: str, source: str = "auto") -> ClassifyResult:
        """Classify a research topic for repeat detection.

        Args:
            topic_text: The research topic description
            source: Origin of the request (manual/cli/user bypass blocking)

        Returns:
            ClassifyResult with verdict and supporting data
        """
        # Manual sources always get NOVEL verdict (explicit override path)
        if source in ("manual", "cli", "user"):
            new_scope = extract_scope(topic_text)
            return ClassifyResult(
                verdict=NOVEL,
                reason="manual source bypasses repeat detection",
                topic_id=canonical_topic_id(topic_text),
                new_scope=new_scope,
            )

        # Find matching canonical topic
        match = self._registry.find_matching(topic_text)

        if match is None:
            new_scope = extract_scope(topic_text)
            return ClassifyResult(
                verdict=NOVEL,
                reason="no matching canonical topic in registry",
                topic_id=canonical_topic_id(topic_text),
                new_scope=new_scope,
            )

        # We have a match — compare scopes
        new_scope = extract_scope(topic_text)
        prior_scope = self._extract_prior_scope(match)
        age_days = _days_since(match.last_researched)
        topic_id = canonical_topic_id(match.canonical_name)

        # Compute match score for transparency
        norm_new = _normalize(topic_text)
        norm_prior = _normalize(match.canonical_name)
        match_score = _word_overlap(norm_new, norm_prior)
        # Also check aliases for best score
        for alias in match.aliases:
            alias_score = _word_overlap(norm_new, _normalize(alias))
            match_score = max(match_score, alias_score)

        base = ClassifyResult(
            verdict="",  # Set by decision tree below
            reason="",   # Set by decision tree below
            topic_id=topic_id,
            canonical_name=match.canonical_name,
            new_scope=new_scope,
            prior_scope=prior_scope,
            match_score=match_score,
            research_count=match.research_count,
            memory_count=match.memory_count,
            age_days=age_days,
        )

        # Decision tree (ordered from most permissive to most restrictive):

        # 1. Old research → always allow (time-based refresh)
        if age_days >= REFINEMENT_AGE_DAYS:
            base.verdict = SCOPE_SHIFT if new_scope.differs_from(prior_scope) else SHALLOW_PRIOR
            base.reason = (
                f"prior research is {age_days:.0f}d old (>{REFINEMENT_AGE_DAYS}d threshold), "
                f"canonical: '{match.canonical_name}'"
            )
            return base

        # 2. Shallow prior research → allow re-research
        if match.memory_count < REFINEMENT_MIN_MEMORIES:
            base.verdict = SHALLOW_PRIOR
            base.reason = (
                f"prior research was shallow ({match.memory_count} memories, "
                f"<{REFINEMENT_MIN_MEMORIES} threshold), canonical: '{match.canonical_name}'"
            )
            return base

        # 3. Scope differs → SCOPE_SHIFT (allow)
        if new_scope.differs_from(prior_scope):
            base.verdict = SCOPE_SHIFT
            diffs = []
            if new_scope.depth != prior_scope.depth and new_scope.depth != "unknown" and prior_scope.depth != "unknown":
                diffs.append(f"depth: {prior_scope.depth}→{new_scope.depth}")
            if new_scope.angle != prior_scope.angle and new_scope.angle != "unknown" and prior_scope.angle != "unknown":
                diffs.append(f"angle: {prior_scope.angle}→{new_scope.angle}")
            if new_scope.specificity != prior_scope.specificity and new_scope.specificity != "unknown" and prior_scope.specificity != "unknown":
                diffs.append(f"specificity: {prior_scope.specificity}→{new_scope.specificity}")
            base.reason = (
                f"same topic but different scope ({', '.join(diffs) or 'scope shift detected'}), "
                f"canonical: '{match.canonical_name}'"
            )
            return base

        # 4. Hard block: too many researches
        if match.research_count >= MAX_RESEARCH_COUNT:
            base.verdict = REPEAT
            base.reason = (
                f"researched {match.research_count}x recently with same scope, "
                f"canonical: '{match.canonical_name}'"
            )
            return base

        # 5. Recent + well-covered + same scope → REPEAT
        base.verdict = REPEAT
        base.reason = (
            f"recently researched ({age_days:.0f}d ago, {match.memory_count} memories, "
            f"same scope), canonical: '{match.canonical_name}'"
        )
        return base

    def _extract_prior_scope(self, entry: TopicEntry) -> Scope:
        """Extract scope from prior research by analyzing canonical name + aliases.

        Checks the canonical name and all aliases for scope markers,
        taking the most specific (non-unknown) value for each dimension.
        """
        # Combine canonical name + aliases for scope detection
        texts = [entry.canonical_name] + entry.aliases
        best_scope = Scope()

        for text in texts:
            scope = extract_scope(text)
            if scope.depth != "unknown" and best_scope.depth == "unknown":
                best_scope.depth = scope.depth
            if scope.angle != "unknown" and best_scope.angle == "unknown":
                best_scope.angle = scope.angle
            if scope.specificity != "unknown" and best_scope.specificity == "unknown":
                best_scope.specificity = scope.specificity
            best_scope.scope_terms.extend(scope.scope_terms)

        return best_scope

    def is_repeat(self, topic_text: str, source: str = "auto") -> bool:
        """Convenience method: returns True only for REPEAT verdict."""
        result = self.classify(topic_text, source=source)
        return result.verdict == REPEAT


# --- CLI ---

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Smart repeat detection for research topics")
    sub = parser.add_subparsers(dest="command")

    cls = sub.add_parser("classify", help="Classify a topic for repeat detection")
    cls.add_argument("topic", help="Topic text to classify")
    cls.add_argument("--source", default="auto", help="Source context (auto/manual/cli/user)")

    cmp = sub.add_parser("compare", help="Compare scope of two topics")
    cmp.add_argument("topic_a", help="First topic text")
    cmp.add_argument("topic_b", help="Second topic text")

    tid = sub.add_parser("topic-id", help="Generate canonical topic ID")
    tid.add_argument("topic", help="Topic text")

    scp = sub.add_parser("scope", help="Extract scope from topic text")
    scp.add_argument("topic", help="Topic text")

    args = parser.parse_args()

    if args.command == "classify":
        classifier = RepeatClassifier()
        result = classifier.classify(args.topic, source=args.source)
        print(f"VERDICT: {result.verdict}")
        print(f"REASON: {result.reason}")
        if result.topic_id:
            print(f"TOPIC_ID: {result.topic_id}")
        if result.canonical_name:
            print(f"CANONICAL: {result.canonical_name}")
        if result.new_scope:
            print(f"NEW_SCOPE: depth={result.new_scope.depth}, angle={result.new_scope.angle}, spec={result.new_scope.specificity}")
        if result.prior_scope:
            print(f"PRIOR_SCOPE: depth={result.prior_scope.depth}, angle={result.prior_scope.angle}, spec={result.prior_scope.specificity}")
        print(f"MATCH_SCORE: {result.match_score:.3f}")
        # Exit code: 0=allow (NOVEL/SCOPE_SHIFT/SHALLOW_PRIOR), 1=block (REPEAT)
        sys.exit(0 if result.verdict != REPEAT else 1)

    elif args.command == "compare":
        scope_a = extract_scope(args.topic_a)
        scope_b = extract_scope(args.topic_b)
        print(f"TOPIC A: depth={scope_a.depth}, angle={scope_a.angle}, spec={scope_a.specificity}")
        print(f"  terms: {scope_a.scope_terms}")
        print(f"TOPIC B: depth={scope_b.depth}, angle={scope_b.angle}, spec={scope_b.specificity}")
        print(f"  terms: {scope_b.scope_terms}")
        print(f"DIFFERS: {scope_a.differs_from(scope_b)}")

    elif args.command == "topic-id":
        print(canonical_topic_id(args.topic))

    elif args.command == "scope":
        scope = extract_scope(args.topic)
        print(f"depth={scope.depth}, angle={scope.angle}, specificity={scope.specificity}")
        print(f"terms: {scope.scope_terms}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
