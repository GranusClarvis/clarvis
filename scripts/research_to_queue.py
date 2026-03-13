#!/usr/bin/env python3
"""
research_to_queue.py — Bridge between ingested research and the evolution queue.

Scans memory/research/ingested/ for papers with actionable findings,
cross-references QUEUE.md + QUEUE_ARCHIVE.md for existing tasks,
and prints candidate queue items for unimplemented research.

Optionally injects top candidates into QUEUE.md via queue_writer.

Usage:
    python3 research_to_queue.py scan          # Print candidates (dry run)
    python3 research_to_queue.py inject        # Inject top candidates into QUEUE.md
    python3 research_to_queue.py inject --max 3  # Inject up to 3 candidates

Run monthly via cron_reflection.sh.
"""

import os
import re
import sys
from datetime import datetime, timezone

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
INGESTED_DIR = os.path.join(WORKSPACE, "memory", "research", "ingested")
QUEUE_FILE = os.path.join(WORKSPACE, "memory", "evolution", "QUEUE.md")
ARCHIVE_FILE = os.path.join(WORKSPACE, "memory", "evolution", "QUEUE_ARCHIVE.md")

# Actionable signal patterns — sections/headings that indicate concrete proposals
ACTIONABLE_PATTERNS = [
    r"(?i)(?:concrete\s+)?improvement\s+proposals?",
    r"(?i)actionable\s+patterns?",
    r"(?i)application\s+to\s+clarvis",
    r"(?i)relevance\s+to\s+clarvis",
    r"(?i)clarvis\s+gap\s+analysis",
    r"(?i)priority\s+implementation",
    r"(?i)what\s+clarvis\s+lacks",
    r"(?i)implementation\s+order",
    r"(?i)key\s+insight",
    r"(?i)proposals?\s+for\s+code",
    r"(?i)target:\s+code\s+generation",
    r"(?i)\d+\s+actionable\s+patterns?",
    r"(?i)patterns?\s+for\s+clarvis",
]

# Patterns that indicate a paper has already been implemented or queued
IMPLEMENTED_SIGNALS = [
    r"(?i)\bimplemented\b",
    r"(?i)\balready\s+done\b",
    r"(?i)\bshipped\b",
    r"(?i)\bmerged\b",
]


def _read_file(path: str) -> str:
    """Read file content, return empty string if missing."""
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _extract_queue_items(content: str) -> list[str]:
    """Extract all task text from QUEUE.md or QUEUE_ARCHIVE.md."""
    items = []
    for line in content.split("\n"):
        m = re.match(r"^-\s*\[[ x~]\]\s*(.+)", line.strip())
        if m:
            items.append(m.group(1).lower())
    return items


def _word_set(text: str) -> set[str]:
    """Extract meaningful words from text."""
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "and", "or", "not", "this", "that", "it", "as", "do", "if",
        "can", "could", "would", "should", "will", "may", "might",
        "has", "have", "had", "its", "their", "our", "but", "so",
    }
    words = set(re.findall(r"[a-z]{3,}", text.lower()))
    return words - stopwords


def _word_overlap(text1: str, text2: str) -> float:
    """Jaccard-like word overlap between two texts."""
    w1 = _word_set(text1)
    w2 = _word_set(text2)
    if not w1 or not w2:
        return 0.0
    intersection = w1 & w2
    smaller = min(len(w1), len(w2))
    return len(intersection) / smaller if smaller > 0 else 0.0


def _is_covered(proposal: str, queue_items: list[str], threshold: float = 0.45) -> bool:
    """Check if a proposal is already covered by an existing queue item."""
    for item in queue_items:
        if _word_overlap(proposal, item) >= threshold:
            return True
    return False


def _extract_paper_title(content: str) -> str:
    """Extract paper title from markdown header."""
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return "Unknown"


def _extract_paper_source(content: str) -> str:
    """Extract paper source/arXiv ID."""
    m = re.search(r"arXiv:(\S+)", content)
    if m:
        return f"arXiv:{m.group(1)}"
    m = re.search(r"\*\*(?:Paper|Source)\*\*:\s*(.+)", content)
    if m:
        return m.group(1).strip()
    return ""


def _extract_actionable_sections(content: str) -> list[str]:
    """Extract actionable proposals from a research paper."""
    proposals = []
    lines = content.split("\n")
    in_actionable = False
    actionable_depth = 0  # heading depth (# count) of the actionable section
    current_items = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Check if this line is a heading
        if stripped.startswith("#"):
            heading_match = re.match(r"^(#+)\s*(.*)", stripped)
            if not heading_match:
                continue
            depth = len(heading_match.group(1))
            heading_text = heading_match.group(2)

            # If we hit a heading at same or higher level as actionable parent, check if new section
            if in_actionable and depth <= actionable_depth:
                # Save items from previous actionable section
                if current_items:
                    proposals.extend(current_items)
                current_items = []
                in_actionable = False

            # Check if this heading starts a new actionable section
            if any(re.search(p, heading_text) for p in ACTIONABLE_PATTERNS):
                in_actionable = True
                actionable_depth = depth
                current_items = []
            elif in_actionable and depth > actionable_depth:
                # Sub-heading within actionable section — extract heading as proposal
                if len(heading_text) > 20:
                    current_items.append(heading_text)
            continue

        if not in_actionable:
            continue

        # Extract numbered or bulleted items with substance
        # Match: "1. **Name**: description" or "- **Name**: description" or "### P1: Title"
        m = re.match(r"^(?:\d+\.\s+|\-\s+)(?:\*\*(.+?)\*\*[:\s]*)?(.+)", stripped)
        if m:
            name = m.group(1) or ""
            desc = m.group(2).strip()
            # Skip very short items or table rows
            if len(desc) > 20 and not desc.startswith("|"):
                item = f"{name}: {desc}" if name else desc
                current_items.append(item)

    # Don't forget last section
    if in_actionable and current_items:
        proposals.extend(current_items)

    return proposals


def _score_proposal(proposal: str) -> float:
    """Score a proposal by impact signals (0.0-1.0)."""
    text = proposal.lower()
    score = 0.5  # base

    # Impact keywords
    if "high" in text and "impact" in text:
        score += 0.2
    elif "medium" in text and "impact" in text:
        score += 0.1
    if "code generation" in text or "code quality" in text:
        score += 0.15  # directly targets weakest metric
    if "directly" in text:
        score += 0.05
    if "low" in text and "effort" in text:
        score += 0.1

    # Penalty for vague
    if len(proposal) < 40:
        score -= 0.1

    return min(1.0, max(0.0, score))


def scan_papers() -> list[dict]:
    """Scan all ingested papers and extract actionable proposals.

    Returns list of dicts: {paper, source, proposal, score, covered}
    """
    if not os.path.isdir(INGESTED_DIR):
        print(f"No ingested directory: {INGESTED_DIR}", file=sys.stderr)
        return []

    # Load queue items for cross-referencing
    queue_content = _read_file(QUEUE_FILE)
    archive_content = _read_file(ARCHIVE_FILE)
    queue_items = _extract_queue_items(queue_content) + _extract_queue_items(archive_content)

    # Also include the raw queue text for broader matching
    all_queue_text = (queue_content + "\n" + archive_content).lower()

    results = []

    for filename in sorted(os.listdir(INGESTED_DIR)):
        if not filename.endswith(".md"):
            continue

        filepath = os.path.join(INGESTED_DIR, filename)
        content = _read_file(filepath)
        if not content:
            continue

        title = _extract_paper_title(content)
        source = _extract_paper_source(content)
        proposals = _extract_actionable_sections(content)

        for proposal in proposals:
            covered = _is_covered(proposal, queue_items)
            score = _score_proposal(proposal)
            results.append({
                "paper": title,
                "paper_file": filename,
                "source": source,
                "proposal": proposal,
                "score": score,
                "covered": covered,
            })

    # Sort: uncovered first, then by score descending
    results.sort(key=lambda r: (r["covered"], -r["score"]))
    return results


def format_queue_item(result: dict) -> str:
    """Format a research proposal as a QUEUE.md task."""
    # Generate a tag from the paper filename
    tag = re.sub(r"\.md$", "", result["paper_file"])
    tag = re.sub(r"[-_]+", "_", tag).upper()
    # Truncate tag to reasonable length
    if len(tag) > 30:
        tag = tag[:30]

    proposal = result["proposal"]
    # Clean up markdown bold
    proposal = re.sub(r"\*\*(.+?)\*\*", r"\1", proposal)
    # Truncate very long proposals
    if len(proposal) > 200:
        proposal = proposal[:197] + "..."

    paper_ref = result["paper"]
    if result["source"]:
        paper_ref += f" ({result['source']})"

    return f"[RESEARCH_{tag}] From {paper_ref}: {proposal}"


def main():
    if len(sys.argv) < 2:
        print("Usage: research_to_queue.py scan|inject [--max N]")
        sys.exit(1)

    cmd = sys.argv[1]
    max_inject = 3
    for i, arg in enumerate(sys.argv):
        if arg == "--max" and i + 1 < len(sys.argv):
            max_inject = int(sys.argv[i + 1])

    results = scan_papers()

    if not results:
        print("No actionable proposals found in ingested papers.")
        return

    uncovered = [r for r in results if not r["covered"]]
    covered = [r for r in results if r["covered"]]

    print(f"=== Research-to-Queue Bridge ===")
    print(f"Papers scanned: {len(set(r['paper_file'] for r in results))}")
    print(f"Total proposals: {len(results)}")
    print(f"Uncovered (new): {len(uncovered)}")
    print(f"Already covered: {len(covered)}")
    print()

    if uncovered:
        print("--- NEW CANDIDATES (not in QUEUE) ---")
        for i, r in enumerate(uncovered[:15], 1):
            status = f"[score={r['score']:.2f}]"
            print(f"  {i}. {status} {format_queue_item(r)}")
        print()

    if covered:
        print(f"--- ALREADY COVERED ({len(covered)} items, showing top 5) ---")
        for r in covered[:5]:
            print(f"  - {r['paper']}: {r['proposal'][:80]}...")
        print()

    if cmd == "inject" and uncovered:
        # Import queue_writer for injection
        sys.path.insert(0, os.path.join(WORKSPACE, "scripts"))
        try:
            from queue_writer import add_tasks
        except ImportError:
            print("ERROR: Could not import queue_writer", file=sys.stderr)
            sys.exit(1)

        tasks = [format_queue_item(r) for r in uncovered[:max_inject]]
        added = add_tasks(tasks, priority="P1", source="research_bridge")
        print(f"Injected {len(added)} task(s) into QUEUE.md (P1)")
        for t in added:
            print(f"  + {t[:100]}...")

    elif cmd == "scan":
        if uncovered:
            print(f"Run 'research_to_queue.py inject' to add top {min(max_inject, len(uncovered))} to QUEUE.md")
    else:
        print("No new candidates to inject.")


if __name__ == "__main__":
    main()
