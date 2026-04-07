#!/usr/bin/env python3
"""
research_novelty.py — Canonical topic registry + novelty classification.

Prevents research pipeline duplication by maintaining a registry of researched
topics and classifying incoming topics into novelty tiers:

  NEW           — No prior research on this topic
  REFINEMENT    — Prior research exists but is old (>14d) or shallow (<3 memories)
  CONTRADICTION — Findings contradict prior research (requires manual flag)
  ALREADY_KNOWN — Recent, thorough research already covers this topic

Pipeline integration:
  1. PRE-SELECT:  cron_research.sh calls `classify` before spawning Claude Code
  2. POST-EXECUTE: cron_research.sh calls `evaluate-file` on output before ingestion
  3. REGISTER:    cron_research.sh calls `register` after successful ingestion

The registry is backed by data/research_topic_registry.json. It is built initially
from data/research_ingested.json + data/research_lessons.jsonl, then maintained
incrementally.

CLI:
    python3 research_novelty.py classify "Phi/IIT consciousness measurement"
    python3 research_novelty.py evaluate-file memory/research/runs/2026-03-27/output.md
    python3 research_novelty.py register "phi-computation" --source "phi-computation-2026-03-27.md"
    python3 research_novelty.py build          # Build registry from existing data
    python3 research_novelty.py list           # Show all canonical topics
    python3 research_novelty.py stats          # Registry statistics
"""

import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
REGISTRY_PATH = os.path.join(WORKSPACE, "data", "research_topic_registry.json")
INGESTED_TRACKER = os.path.join(WORKSPACE, "data", "research_ingested.json")
LESSONS_PATH = os.path.join(WORKSPACE, "data", "research_lessons.jsonl")
INGESTED_DIR = os.path.join(WORKSPACE, "memory", "research", "ingested")

# Novelty tiers
NEW = "NEW"
REFINEMENT = "REFINEMENT"
CONTRADICTION = "CONTRADICTION"
ALREADY_KNOWN = "ALREADY_KNOWN"

# Thresholds
SIMILARITY_THRESHOLD = 0.45       # Word overlap above this = same topic
REFINEMENT_AGE_DAYS = 14          # Older than this → REFINEMENT instead of ALREADY_KNOWN
REFINEMENT_MIN_MEMORIES = 3       # Fewer stored memories → REFINEMENT
MAX_RESEARCH_COUNT = 3            # More than this many researches on same topic → hard block

# Family-level completion locking
FAMILY_LOCK_THRESHOLD = 0.6       # If >= 60% of family topics are done/blocked, lock the family
FAMILY_MIN_TOPICS = 2             # Only lock families with at least this many topics
FAMILY_MIN_RESEARCH = 3           # Family needs at least this total research count to lock

# Predefined topic families: keyword patterns → family name
# Topics matching multiple families go to the first match.
TOPIC_FAMILIES = {
    "iit-phi": {
        "keywords": ["iit", "phi computation", "phi approximat", "scalable phi", "phiid",
                      "integrated information", "consciousness metric"],
        "description": "IIT / Phi consciousness measurement",
    },
    "consciousness": {
        "keywords": ["consciousness", "attention schema", "awareness", "butlin",
                      "global workspace", "gwt", "just aware enough"],
        "description": "Consciousness architectures and theories",
    },
    "rag-retrieval": {
        "keywords": ["rag", "retrieval", "chunking", "reranking", "late interaction",
                      "context pruning", "noise filtering", "hybrid rag", "arag",
                      "macrag", "crag", "targ"],
        "description": "RAG and retrieval optimization",
    },
    "memory-systems": {
        "keywords": ["mem0", "memgpt", "memory benchmark", "memoryagent", "memrl",
                      "memory layer", "memory consolidation", "trajectory.*memory",
                      "agemem", "learned memory"],
        "description": "Memory systems and benchmarks",
    },
    "self-evolution": {
        "keywords": ["self.evolv", "self.improv", "hermes.*evolution", "swe.evo",
                      "a.evolve", "autoresearch", "evolving constitution",
                      "open.ended evolution"],
        "description": "Self-evolution and autonomous improvement",
    },
    "world-models": {
        "keywords": ["world model", "jepa", "dreamer", "free energy", "predictive processing",
                      "generative model.*cognitive", "bayesian brain"],
        "description": "World models and predictive processing",
    },
    "agent-tools": {
        "keywords": ["browser.*autom", "agent browser", "agent.*tool", "browser.*research",
                      "plugin.*config", "harness"],
        "description": "Agent tooling and browser automation",
    },
    "metacognition": {
        "keywords": ["metacognit", "confidence calibrat", "self.debug", "reasoning failure",
                      "runtime verification", "reflexion", "intrinsic.*learning"],
        "description": "Metacognition and self-monitoring",
    },
}

# Topic anchors: if present, they should generally match on both sides for a
# topic to be considered the same. Prevents over-broad matches like
# "Phi computation in IIT" -> canonical "iit 4.0" just because both mention IIT.
PROTECTED_PHRASES = [
    "phi computation",
    "phi approximations",
    "scalable phi",
    "retrieval optimization",
    "consciousness architectures",
    "world models",
    "free energy principle",
    "global workspace",
    "attention schema",
    "hybrid rag",
    "late chunking",
    "temporal retrieval",
    "integrated information theory",
    "iit 4.0",
    "phiid",
]


def _generate_topic_id(name: str) -> str:
    """Generate a stable, deterministic topic ID from a canonical name.

    Produces a short slug like 'phi-computation', 'world-models-jepa'.
    Strips noise, lowercases, replaces spaces with hyphens, deduplicates hyphens.
    """
    slug = _normalize(name)
    # Strip .md extension if present
    slug = re.sub(r"\.md$", "", slug)
    # Remove leftover punctuation except hyphens
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-{2,}", "-", slug)
    slug = slug.strip("-")
    # Cap at 60 chars to keep IDs readable
    if len(slug) > 60:
        slug = slug[:60].rsplit("-", 1)[0]
    return slug or "unknown"


# Topic family status — the single source of truth for "is this topic done?"
# These are persisted in the registry entry's `status` field.
STATUS_NEW = "new"                 # No research yet (just discovered/queued)
STATUS_ACTIVE = "active"           # Currently being researched or queued
STATUS_DONE = "done"               # Sufficiently covered — blocks re-research
STATUS_REVISITABLE = "revisitable" # Done but explicitly marked for future revisit
STATUS_BLOCKED = "blocked_duplicate"  # Hard-blocked repeat (research_count >= MAX)


@dataclass
class TopicEntry:
    canonical_name: str
    topic_id: str = ""              # Stable canonical slug (e.g. "phi-computation")
    status: str = ""                # Single source of truth: new/active/done/revisitable/blocked_duplicate
    family: str = ""                # Topic family for group-level locking (e.g. "iit-phi", "rag-retrieval")
    aliases: list[str] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)
    first_seen: str = ""
    last_researched: str = ""
    research_count: int = 0
    memory_count: int = 0           # How many brain memories were stored
    last_novelty: str = ""          # Last classification result

    def __post_init__(self):
        if not self.first_seen:
            self.first_seen = _now_iso()
        if not self.last_researched:
            self.last_researched = self.first_seen
        if not self.topic_id:
            self.topic_id = _generate_topic_id(self.canonical_name)
        if not self.status:
            self.status = self._compute_status()

    def _compute_status(self) -> str:
        """Derive status from research_count and age when not explicitly set."""
        if self.research_count == 0:
            return STATUS_NEW
        if self.research_count >= MAX_RESEARCH_COUNT:
            return STATUS_BLOCKED
        age = _days_since(self.last_researched)
        if age < REFINEMENT_AGE_DAYS and self.memory_count >= REFINEMENT_MIN_MEMORIES:
            return STATUS_DONE
        return STATUS_ACTIVE


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _days_since(iso_date: str) -> float:
    """Days elapsed since an ISO date string."""
    try:
        # Parse ISO format
        t = time.strptime(iso_date[:19], "%Y-%m-%dT%H:%M:%S")
        elapsed = time.time() - time.mktime(t)
        return max(0.0, elapsed / 86400)
    except (ValueError, TypeError):
        return 999.0  # Unknown date → treat as old


def _normalize(text: str) -> str:
    """Normalize text for comparison: lowercase, strip all noise deterministically.

    Stripping order matters — broadest removals first, then fine-grained cleanup.
    Every rule here should be boring and obvious; no clever heuristics.
    """
    text = text.lower()
    # 1. Strip all bracket tags: [RESEARCH_FOO], [P0], [2026-03-27], etc.
    text = re.sub(r"\[[^\]]*\]\s*", "", text)
    # 2. Strip common boilerplate prefixes (after bracket removal)
    text = re.sub(r"^(research:\s*|bundle\s+[a-z]:\s*|study\s+|investigate\s+|explore\s+)", "", text)
    # 3. Strip standalone dates: 2026-03-27, 2026-03-27-, (2026-03-27)
    text = re.sub(r"\(?\d{4}-\d{2}-\d{2}\)?-?\s*", "", text)
    # 4. Strip queue task IDs (must contain underscore): RESEARCH_NORMALIZATION_HARDENING
    #    Preserves plain acronyms like IIT, RAG, CRAG
    text = re.sub(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b\s*", "", text)
    # 5. Strip filename artifacts: .md extension, path prefixes, separators
    text = re.sub(r"\.md\b", "", text)
    text = re.sub(r"(?:memory|research|ingested|runs)/", "", text)
    text = re.sub(r"[/\\]", " ", text)
    # 6. Normalize common domain variants
    text = text.replace("integrated information theory", "iit")
    text = text.replace("Φ", "phi")
    text = text.replace("phi (φ)", "phi")
    # 7. Strip markdown formatting
    text = re.sub(r"[*_#`]", "", text)
    # 8. Collapse whitespace and strip
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_anchor_phrases(text: str) -> set[str]:
    """Extract protected multiword topic anchors present in the text."""
    norm = _normalize(text)
    found = set()
    for phrase in PROTECTED_PHRASES:
        p = _normalize(phrase)
        if p in norm:
            found.add(p)
    return found


def _word_set(text: str) -> set[str]:
    """Extract meaningful words, excluding stopwords."""
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "and", "or", "not", "this", "that", "it", "as", "do", "if",
        "can", "could", "would", "should", "will", "may", "might",
        "has", "have", "had", "its", "their", "our", "but", "so",
        "how", "what", "which", "about", "into", "through", "new",
        "using", "based", "via", "between", "more", "also", "than",
        "research", "study", "investigate", "explore", "paper",
    }
    words = set(re.findall(r"[a-z]{3,}", text.lower()))
    return words - stopwords


def _word_overlap(text1: str, text2: str) -> float:
    """Similarity score using a conservative F1-style token overlap.

    Using intersection/smaller-set was too permissive: a tiny canonical topic like
    "iit" looked like a perfect match for any larger query mentioning IIT once.
    """
    w1 = _word_set(text1)
    w2 = _word_set(text2)
    if not w1 or not w2:
        return 0.0
    intersection = len(w1 & w2)
    precision = intersection / len(w1)
    recall = intersection / len(w2)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _canonical_from_filename(filename: str) -> str:
    """Derive a canonical topic name from a research filename."""
    name = filename.replace(".md", "")
    # Strip date prefixes like 2026-03-27-
    name = re.sub(r"^\d{4}-\d{2}-\d{2}-?", "", name)
    # Replace separators with spaces
    name = re.sub(r"[-_]+", " ", name)
    return name.strip()


class TopicRegistry:
    """Persistent registry of canonical research topics."""

    def __init__(self, path: str = REGISTRY_PATH):
        self._path = path
        self._topics: dict[str, TopicEntry] = {}
        self._load()

    def _load(self):
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path) as f:
                data = json.load(f)
            for name, entry_data in data.items():
                self._topics[name] = TopicEntry(**entry_data)
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

    def _save(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        tmp = self._path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(
                {name: asdict(entry) for name, entry in self._topics.items()},
                f, indent=2, default=str
            )
        os.replace(tmp, self._path)

    def _auto_detect_family(self, text: str) -> str:
        """Auto-detect which family a topic belongs to via keyword matching.

        Returns family key (e.g. "iit-phi") or "" if no match.
        """
        norm = _normalize(text).lower()
        for family_key, family_def in TOPIC_FAMILIES.items():
            for kw in family_def["keywords"]:
                # Support regex-like dots in keyword patterns
                if "." in kw or "*" in kw:
                    if re.search(kw.replace("*", ".*"), norm):
                        return family_key
                elif kw in norm:
                    return family_key
        return ""

    def assign_families(self) -> int:
        """Auto-assign family labels to all topics missing one. Returns count updated."""
        count = 0
        for entry in self._topics.values():
            if not entry.family:
                detected = self._auto_detect_family(entry.canonical_name)
                # Also check aliases
                if not detected:
                    for alias in entry.aliases:
                        detected = self._auto_detect_family(alias)
                        if detected:
                            break
                if detected:
                    entry.family = detected
                    count += 1
        if count:
            self._save()
        return count

    def get_family_topics(self, family_key: str) -> list[TopicEntry]:
        """Get all topics belonging to a family."""
        return [e for e in self._topics.values() if e.family == family_key]

    def is_family_locked(self, family_key: str) -> tuple[bool, str]:
        """Check if a topic family is sufficiently covered and should be locked.

        A family is locked when:
          1. It has >= FAMILY_MIN_TOPICS topics
          2. Total research count >= FAMILY_MIN_RESEARCH
          3. >= FAMILY_LOCK_THRESHOLD fraction of topics are done/blocked

        Returns: (is_locked, reason)
        """
        if not family_key:
            return False, ""

        members = self.get_family_topics(family_key)
        if len(members) < FAMILY_MIN_TOPICS:
            return False, f"family '{family_key}' has only {len(members)} topics (need {FAMILY_MIN_TOPICS})"

        total_research = sum(m.research_count for m in members)
        if total_research < FAMILY_MIN_RESEARCH:
            return False, f"family '{family_key}' has only {total_research} total researches (need {FAMILY_MIN_RESEARCH})"

        done_statuses = {STATUS_DONE, STATUS_BLOCKED}
        done_count = sum(1 for m in members if m.status in done_statuses)
        done_ratio = done_count / len(members)

        if done_ratio >= FAMILY_LOCK_THRESHOLD:
            family_desc = TOPIC_FAMILIES.get(family_key, {}).get("description", family_key)
            return True, (
                f"family '{family_desc}' is locked: {done_count}/{len(members)} topics "
                f"done/blocked ({done_ratio:.0%}), {total_research} total researches"
            )

        return False, f"family '{family_key}' not locked: {done_count}/{len(members)} done ({done_ratio:.0%})"

    def family_stats(self) -> dict[str, dict]:
        """Get statistics for all families."""
        stats = {}
        # Collect all families (predefined + any custom ones assigned to topics)
        all_families = set(TOPIC_FAMILIES.keys())
        for entry in self._topics.values():
            if entry.family:
                all_families.add(entry.family)

        for fk in sorted(all_families):
            members = self.get_family_topics(fk)
            if not members:
                continue
            done_statuses = {STATUS_DONE, STATUS_BLOCKED}
            done_count = sum(1 for m in members if m.status in done_statuses)
            total_research = sum(m.research_count for m in members)
            locked, reason = self.is_family_locked(fk)
            desc = TOPIC_FAMILIES.get(fk, {}).get("description", fk)
            stats[fk] = {
                "description": desc,
                "topic_count": len(members),
                "done_count": done_count,
                "total_research": total_research,
                "locked": locked,
                "reason": reason,
                "topics": [m.canonical_name for m in members],
            }
        return stats

    def find_matching(self, topic_text: str, threshold: float = SIMILARITY_THRESHOLD) -> Optional[TopicEntry]:
        """Find the best matching canonical topic, or None if no match.

        Matching is conservative: protected anchor phrases (e.g. "phi computation",
        "retrieval optimization") must usually align to avoid overly broad topic
        collisions.
        """
        normalized = _normalize(topic_text)
        query_anchors = _extract_anchor_phrases(normalized)
        best_match = None
        best_score = 0.0

        def consider(candidate_text: str, entry: TopicEntry):
            nonlocal best_match, best_score
            cand_norm = _normalize(candidate_text)
            cand_anchors = _extract_anchor_phrases(cand_norm)
            score = _word_overlap(normalized, cand_norm)

            # If either side has anchor phrases, require intersection for a high-confidence
            # match. Otherwise broad umbrella topics like "iit 4.0" absorb everything with IIT.
            if query_anchors or cand_anchors:
                if not (query_anchors & cand_anchors):
                    # Allow only near-identical full-text overlap as a fallback.
                    if score < 0.8:
                        return
                else:
                    # Reward aligned anchor phrases.
                    score += 0.15

            if score > best_score:
                best_score = score
                best_match = entry

        for name, entry in self._topics.items():
            consider(name, entry)
            for alias in entry.aliases:
                consider(alias, entry)

        if best_score >= threshold:
            return best_match
        return None

    def classify(self, topic_text: str) -> tuple[str, str, Optional[TopicEntry]]:
        """Classify a research topic's novelty.

        Checks both topic-level and family-level completion status.
        The topic's `status` field is the single source of truth for individual completion.
        Family-level locking blocks new entries in sufficiently covered families.
        Returns: (novelty_tier, reason, matched_entry_or_None)
        """
        match = self.find_matching(topic_text)

        if match is None:
            # Even with no exact match, check if the topic would fall into a locked family
            detected_family = self._auto_detect_family(topic_text)
            if detected_family:
                locked, reason = self.is_family_locked(detected_family)
                if locked:
                    return ALREADY_KNOWN, f"family-locked: {reason}", None
            return NEW, "no prior research found on this topic", None

        age_days = _days_since(match.last_researched)

        # Check family-level lock before individual status (broader block)
        family_key = match.family or self._auto_detect_family(match.canonical_name)
        if family_key:
            # Auto-assign family if not set yet
            if not match.family:
                match.family = family_key
                self._save()
            locked, lock_reason = self.is_family_locked(family_key)
            if locked and match.status != STATUS_REVISITABLE:
                return ALREADY_KNOWN, (
                    f"family-locked: {lock_reason}, "
                    f"topic: '{match.canonical_name}' (id: {match.topic_id})"
                ), match

        # Check explicit status first — this is the single source of truth
        if match.status == STATUS_REVISITABLE:
            return REFINEMENT, (
                f"topic explicitly marked revisitable, "
                f"canonical: '{match.canonical_name}' (id: {match.topic_id})"
            ), match

        if match.status == STATUS_BLOCKED:
            return ALREADY_KNOWN, (
                f"hard-blocked (status={match.status}), "
                f"canonical: '{match.canonical_name}' (id: {match.topic_id})"
            ), match

        # Hard block: too many researches on same topic
        if match.research_count >= MAX_RESEARCH_COUNT and age_days < REFINEMENT_AGE_DAYS:
            return ALREADY_KNOWN, (
                f"researched {match.research_count}x (last {age_days:.0f}d ago), "
                f"canonical: '{match.canonical_name}' (id: {match.topic_id})"
            ), match

        # Recent + well-covered → ALREADY_KNOWN
        if age_days < REFINEMENT_AGE_DAYS and match.memory_count >= REFINEMENT_MIN_MEMORIES:
            return ALREADY_KNOWN, (
                f"recently researched ({age_days:.0f}d ago, {match.memory_count} memories), "
                f"canonical: '{match.canonical_name}' (id: {match.topic_id})"
            ), match

        # Old or shallow → REFINEMENT
        reasons = []
        if age_days >= REFINEMENT_AGE_DAYS:
            reasons.append(f"last researched {age_days:.0f}d ago")
        if match.memory_count < REFINEMENT_MIN_MEMORIES:
            reasons.append(f"only {match.memory_count} memories stored")
        return REFINEMENT, (
            f"prior research exists but {' and '.join(reasons)}, "
            f"canonical: '{match.canonical_name}' (id: {match.topic_id})"
        ), match

    def evaluate_file(self, filepath: str) -> tuple[str, str]:
        """Evaluate novelty of a research output file by checking its content
        against existing brain memories.

        Returns: (novelty_tier, reason)
        """
        if not os.path.exists(filepath):
            return NEW, f"file not found: {filepath}"

        with open(filepath) as f:
            content = f.read()

        # Extract title from first heading
        title = ""
        for line in content.split("\n"):
            if line.startswith("# "):
                title = line[2:].strip()
                break
        if not title:
            title = os.path.basename(filepath).replace(".md", "").replace("-", " ")

        # Classify the title against registry
        novelty, reason, match = self.classify(title)

        # If classified as ALREADY_KNOWN, do a deeper content check:
        # see if the file has substantial new content vs what's in ingested/
        if novelty == ALREADY_KNOWN and match and match.source_files:
            new_words = _word_set(content)
            existing_content = ""
            for src in match.source_files[-3:]:  # Check last 3 source files
                src_path = os.path.join(INGESTED_DIR, src)
                if os.path.exists(src_path):
                    with open(src_path) as f:
                        existing_content += f.read() + "\n"
            if existing_content:
                existing_words = _word_set(existing_content)
                truly_new = new_words - existing_words
                new_ratio = len(truly_new) / len(new_words) if new_words else 0
                if new_ratio > 0.4:
                    # >40% new content → upgrade to REFINEMENT
                    return REFINEMENT, (
                        f"topic is known but file has {new_ratio:.0%} new content "
                        f"(canonical: '{match.canonical_name}')"
                    )

        return novelty, reason

    def register(self, canonical_name: str, source_file: str = "",
                 memory_count: int = 0, alias: str = ""):
        """Register or update a topic after successful ingestion."""
        existing = self.find_matching(canonical_name)

        if existing:
            entry = existing
            entry.research_count += 1
            entry.last_researched = _now_iso()
            if source_file and source_file not in entry.source_files:
                entry.source_files.append(source_file)
            if alias and alias not in entry.aliases:
                entry.aliases.append(alias)
            if memory_count > 0:
                entry.memory_count += memory_count
            entry.last_novelty = ""  # Reset after new research
            # Ensure topic_id is set (backfill for pre-existing entries)
            if not entry.topic_id:
                entry.topic_id = _generate_topic_id(entry.canonical_name)
            # Auto-assign family if not set
            if not entry.family:
                entry.family = self._auto_detect_family(entry.canonical_name)
            # Update status based on current state
            entry.status = entry._compute_status()
        else:
            topic_id = _generate_topic_id(canonical_name)
            family = self._auto_detect_family(canonical_name)
            entry = TopicEntry(
                canonical_name=canonical_name,
                topic_id=topic_id,
                family=family,
                aliases=[alias] if alias else [],
                source_files=[source_file] if source_file else [],
                research_count=1,
                memory_count=memory_count,
            )
            # status is computed in __post_init__
            self._topics[canonical_name] = entry

        self._save()
        return entry

    def build_from_existing(self) -> int:
        """Build registry from existing ingested data and lessons.

        Clusters filenames by word overlap to find canonical topics.
        """
        # Gather all known research filenames
        filenames = []
        if os.path.exists(INGESTED_TRACKER):
            with open(INGESTED_TRACKER) as f:
                tracker = json.load(f)
            filenames = list(tracker.keys())

        # Gather lessons
        lesson_topics = []
        if os.path.exists(LESSONS_PATH):
            with open(LESSONS_PATH) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            lesson_topics.append(data.get("topic", ""))
                        except json.JSONDecodeError:
                            pass

        # Cluster filenames into canonical topics
        clusters: dict[str, list[str]] = {}  # canonical_name -> [filenames]

        for fname in sorted(filenames):
            topic_name = _canonical_from_filename(fname)
            # Try to find an existing cluster
            matched_cluster = None
            best_score = 0.0
            for canonical in clusters:
                score = _word_overlap(topic_name, canonical)
                if score > best_score:
                    best_score = score
                    matched_cluster = canonical

            if best_score >= SIMILARITY_THRESHOLD and matched_cluster:
                clusters[matched_cluster].append(fname)
            else:
                clusters[topic_name] = [fname]

        # Build topic entries
        count = 0
        tracker_data = {}
        if os.path.exists(INGESTED_TRACKER):
            with open(INGESTED_TRACKER) as f:
                tracker_data = json.load(f)

        for canonical, fnames in clusters.items():
            if canonical in self._topics:
                # Update existing
                entry = self._topics[canonical]
                for fn in fnames:
                    if fn not in entry.source_files:
                        entry.source_files.append(fn)
            else:
                # Compute stats from tracker
                total_memories = 0
                earliest = ""
                latest = ""
                for fn in fnames:
                    info = tracker_data.get(fn, {})
                    total_memories += info.get("memory_count", 0)
                    ts = info.get("ingested_at", "")
                    if ts:
                        if not earliest or ts < earliest:
                            earliest = ts
                        if not latest or ts > latest:
                            latest = ts

                entry = TopicEntry(
                    canonical_name=canonical,
                    aliases=[_canonical_from_filename(fn) for fn in fnames[1:]],
                    source_files=fnames,
                    first_seen=earliest or _now_iso(),
                    last_researched=latest or _now_iso(),
                    research_count=len(fnames),
                    memory_count=total_memories,
                )
                self._topics[canonical] = entry
                count += 1

        self._save()
        return count

    def set_status(self, topic_text: str, status: str) -> Optional[TopicEntry]:
        """Explicitly set the status of a topic family. Operator override."""
        valid = {STATUS_NEW, STATUS_ACTIVE, STATUS_DONE, STATUS_REVISITABLE, STATUS_BLOCKED}
        if status not in valid:
            raise ValueError(f"Invalid status '{status}'. Valid: {', '.join(sorted(valid))}")
        match = self.find_matching(topic_text)
        if not match:
            return None
        match.status = status
        self._save()
        return match

    def find_by_id(self, topic_id: str) -> Optional[TopicEntry]:
        """Look up a topic by its stable topic_id slug."""
        for entry in self._topics.values():
            if entry.topic_id == topic_id:
                return entry
        return None

    def migrate_ids_and_status(self) -> int:
        """Backfill topic_id and status for all existing entries.

        Always force-saves to persist fields computed by __post_init__
        that may not have been in the JSON yet.
        """
        count = 0
        for entry in self._topics.values():
            if not entry.topic_id:
                entry.topic_id = _generate_topic_id(entry.canonical_name)
                count += 1
            if not entry.status:
                entry.status = entry._compute_status()
                count += 1
        # Always save — __post_init__ may have computed fields that aren't persisted yet
        self._save()
        return count

    def list_topics(self) -> list[TopicEntry]:
        return sorted(self._topics.values(), key=lambda e: e.last_researched, reverse=True)

    def stats(self) -> dict:
        topics = list(self._topics.values())
        if not topics:
            return {"total_topics": 0}
        total_research = sum(t.research_count for t in topics)
        total_memories = sum(t.memory_count for t in topics)
        duplicated = [t for t in topics if t.research_count > 2]
        return {
            "total_topics": len(topics),
            "total_research_runs": total_research,
            "total_memories": total_memories,
            "avg_research_per_topic": round(total_research / len(topics), 1),
            "over_researched": len(duplicated),
            "over_researched_names": [t.canonical_name for t in duplicated[:10]],
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Research topic novelty classification")
    sub = parser.add_subparsers(dest="command")

    cls = sub.add_parser("classify", help="Classify a topic's novelty")
    cls.add_argument("topic", help="Topic text to classify")

    evf = sub.add_parser("evaluate-file", help="Evaluate novelty of a research output file")
    evf.add_argument("filepath", help="Path to research output markdown")

    reg = sub.add_parser("register", help="Register a topic after ingestion")
    reg.add_argument("canonical_name", help="Canonical topic name")
    reg.add_argument("--source", default="", help="Source filename")
    reg.add_argument("--memories", type=int, default=0, help="Number of memories stored")
    reg.add_argument("--alias", default="", help="Alternative name for the topic")

    sub.add_parser("build", help="Build registry from existing ingested data")
    sub.add_parser("list", help="List all canonical topics")
    sub.add_parser("stats", help="Show registry statistics")
    sub.add_parser("migrate", help="Backfill topic_id and status for existing entries")

    ss = sub.add_parser("set-status", help="Set status of a topic family (operator override)")
    ss.add_argument("topic", help="Topic text or ID to match")
    ss.add_argument("status", choices=[STATUS_NEW, STATUS_ACTIVE, STATUS_DONE, STATUS_REVISITABLE, STATUS_BLOCKED],
                     help="New status")

    sub.add_parser("families", help="Show all topic families and their lock status")
    sub.add_parser("assign-families", help="Auto-assign family labels to unassigned topics")

    sf = sub.add_parser("set-family", help="Manually set a topic's family")
    sf.add_argument("topic", help="Topic text or ID to match")
    sf.add_argument("family", help="Family key (e.g. 'iit-phi', 'rag-retrieval', or custom)")

    uf = sub.add_parser("unlock-family", help="Mark all topics in a family as revisitable (unlock)")
    uf.add_argument("family", help="Family key to unlock")

    args = parser.parse_args()
    registry = TopicRegistry()

    if args.command == "classify":
        novelty, reason, match = registry.classify(args.topic)
        print(f"NOVELTY: {novelty}")
        print(f"REASON: {reason}")
        if match:
            print(f"CANONICAL: {match.canonical_name}")
            print(f"TOPIC_ID: {match.topic_id}")
            print(f"STATUS: {match.status}")
            print(f"RESEARCH_COUNT: {match.research_count}")
            print(f"LAST_RESEARCHED: {match.last_researched}")
        # Exit code: 0=NEW/REFINEMENT (proceed), 1=ALREADY_KNOWN (skip)
        sys.exit(0 if novelty in (NEW, REFINEMENT, CONTRADICTION) else 1)

    elif args.command == "evaluate-file":
        novelty, reason = registry.evaluate_file(args.filepath)
        print(f"NOVELTY: {novelty}")
        print(f"REASON: {reason}")
        sys.exit(0 if novelty in (NEW, REFINEMENT, CONTRADICTION) else 1)

    elif args.command == "register":
        entry = registry.register(
            args.canonical_name,
            source_file=args.source,
            memory_count=args.memories,
            alias=args.alias,
        )
        print(f"Registered: {entry.canonical_name} (count={entry.research_count}, memories={entry.memory_count})")

    elif args.command == "build":
        count = registry.build_from_existing()
        print(f"Built registry: {count} new canonical topics")
        stats = registry.stats()
        print(f"Total: {stats['total_topics']} topics, {stats['total_research_runs']} research runs")
        if stats.get("over_researched_names"):
            print(f"Over-researched: {', '.join(stats['over_researched_names'])}")

    elif args.command == "list":
        topics = registry.list_topics()
        if not topics:
            print("Registry is empty. Run 'build' first.")
            return
        for t in topics:
            age = _days_since(t.last_researched)
            status_tag = t.status or "?"
            family_tag = f" fam={t.family}" if t.family else ""
            print(f"  [{status_tag}] [{t.research_count}x, {t.memory_count}mem, {age:.0f}d{family_tag}] {t.canonical_name}")
            print(f"    id: {t.topic_id}")
            if t.aliases:
                print(f"    aliases: {', '.join(t.aliases[:3])}")

    elif args.command == "stats":
        stats = registry.stats()
        print(json.dumps(stats, indent=2))

    elif args.command == "migrate":
        count = registry.migrate_ids_and_status()
        print(f"Migrated {count} entries (backfilled topic_id and/or status)")
        stats = registry.stats()
        print(f"Total: {stats['total_topics']} topics")

    elif args.command == "set-status":
        # Try by topic_id first, then by text match
        entry = registry.find_by_id(args.topic)
        if entry:
            entry.status = args.status
            registry._save()
        else:
            entry = registry.set_status(args.topic, args.status)
        if entry:
            print(f"Set status of '{entry.canonical_name}' (id: {entry.topic_id}) to: {args.status}")
        else:
            print(f"No matching topic found for: {args.topic}")
            sys.exit(1)

    elif args.command == "families":
        # Auto-assign first so we have the latest
        assigned = registry.assign_families()
        if assigned:
            print(f"(auto-assigned {assigned} topics to families)")
        fstats = registry.family_stats()
        if not fstats:
            print("No families found. Run 'assign-families' first.")
            return
        for fk, fs in fstats.items():
            lock_icon = "LOCKED" if fs["locked"] else "open"
            print(f"\n  [{lock_icon}] {fk} — {fs['description']}")
            print(f"    topics: {fs['topic_count']}, done: {fs['done_count']}, "
                  f"total research: {fs['total_research']}")
            for tname in fs["topics"]:
                print(f"      - {tname}")

    elif args.command == "assign-families":
        count = registry.assign_families()
        print(f"Auto-assigned {count} topics to families")
        fstats = registry.family_stats()
        for fk, fs in fstats.items():
            print(f"  {fk}: {fs['topic_count']} topics")

    elif args.command == "set-family":
        entry = registry.find_by_id(args.topic)
        if not entry:
            entry = registry.find_matching(args.topic)
        if entry:
            entry.family = args.family
            registry._save()
            print(f"Set family of '{entry.canonical_name}' to: {args.family}")
        else:
            print(f"No matching topic found for: {args.topic}")
            sys.exit(1)

    elif args.command == "unlock-family":
        members = registry.get_family_topics(args.family)
        if not members:
            print(f"No topics in family '{args.family}'")
            sys.exit(1)
        for m in members:
            if m.status in (STATUS_DONE, STATUS_BLOCKED):
                m.status = STATUS_REVISITABLE
        registry._save()
        print(f"Unlocked family '{args.family}': {len(members)} topics set to revisitable")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
