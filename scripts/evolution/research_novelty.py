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

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
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


@dataclass
class TopicEntry:
    canonical_name: str
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
    """Normalize text for comparison: lowercase, strip tags/dates/prefixes."""
    text = text.lower()
    # Strip common prefixes
    text = re.sub(r"^(research:\s*|bundle\s+[a-z]:\s*|study\s+)", "", text)
    # Strip queue tags like [RESEARCH_DISCOVERY 2026-02-27]
    text = re.sub(r"\[[A-Z_]+\s+\d{4}-\d{2}-\d{2}\]\s*", "", text)
    # Normalize common variants
    text = text.replace("integrated information theory", "iit")
    text = text.replace("Φ", "phi")
    text = text.replace("phi (φ)", "phi")
    # Strip markdown formatting
    text = re.sub(r"[*_#`]", "", text)
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

        Returns: (novelty_tier, reason, matched_entry_or_None)
        """
        match = self.find_matching(topic_text)

        if match is None:
            return NEW, "no prior research found on this topic", None

        age_days = _days_since(match.last_researched)

        # Hard block: too many researches on same topic
        if match.research_count >= MAX_RESEARCH_COUNT and age_days < REFINEMENT_AGE_DAYS:
            return ALREADY_KNOWN, (
                f"researched {match.research_count}x (last {age_days:.0f}d ago), "
                f"canonical: '{match.canonical_name}'"
            ), match

        # Recent + well-covered → ALREADY_KNOWN
        if age_days < REFINEMENT_AGE_DAYS and match.memory_count >= REFINEMENT_MIN_MEMORIES:
            return ALREADY_KNOWN, (
                f"recently researched ({age_days:.0f}d ago, {match.memory_count} memories), "
                f"canonical: '{match.canonical_name}'"
            ), match

        # Old or shallow → REFINEMENT
        reasons = []
        if age_days >= REFINEMENT_AGE_DAYS:
            reasons.append(f"last researched {age_days:.0f}d ago")
        if match.memory_count < REFINEMENT_MIN_MEMORIES:
            reasons.append(f"only {match.memory_count} memories stored")
        return REFINEMENT, (
            f"prior research exists but {' and '.join(reasons)}, "
            f"canonical: '{match.canonical_name}'"
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
        else:
            entry = TopicEntry(
                canonical_name=canonical_name,
                aliases=[alias] if alias else [],
                source_files=[source_file] if source_file else [],
                research_count=1,
                memory_count=memory_count,
            )
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

    args = parser.parse_args()
    registry = TopicRegistry()

    if args.command == "classify":
        novelty, reason, match = registry.classify(args.topic)
        print(f"NOVELTY: {novelty}")
        print(f"REASON: {reason}")
        if match:
            print(f"CANONICAL: {match.canonical_name}")
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
            print(f"  [{t.research_count}x, {t.memory_count}mem, {age:.0f}d] {t.canonical_name}")
            if t.aliases:
                print(f"    aliases: {', '.join(t.aliases[:3])}")

    elif args.command == "stats":
        stats = registry.stats()
        print(json.dumps(stats, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
