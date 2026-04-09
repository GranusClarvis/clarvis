#!/usr/bin/env python3
"""
research_to_queue.py — Bridge between ingested research and the evolution queue.

Every research finding must be classified into one of four dispositions:
  - benchmark_target: maps to a measurable metric improvement
  - code_change: maps to a specific file/function modification
  - queue_item: maps to a new QUEUE.md task (not benchmark or code)
  - discard: theory-only, already covered, or too vague to act on

Scans memory/research/ingested/ for papers with actionable findings,
cross-references QUEUE.md + QUEUE_ARCHIVE.md for existing tasks,
classifies each proposal, and injects actionable ones into QUEUE.md.
Discarded proposals are logged to a disposition log for audit.

Usage:
    python3 research_to_queue.py scan          # Print candidates with dispositions
    python3 research_to_queue.py inject        # Inject actionable candidates into QUEUE.md
    python3 research_to_queue.py inject --max 3  # Inject up to 3 candidates
    python3 research_to_queue.py audit         # Show disposition stats and discard reasons

Run monthly via cron_reflection.sh.
"""

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
INGESTED_DIR = os.path.join(WORKSPACE, "memory", "research", "ingested")
QUEUE_FILE = os.path.join(WORKSPACE, "memory", "evolution", "QUEUE.md")
ARCHIVE_FILE = os.path.join(WORKSPACE, "memory", "evolution", "QUEUE_ARCHIVE.md")
DISPOSITION_LOG = os.path.join(WORKSPACE, "data", "research_dispositions.jsonl")

# Disposition categories — every proposal MUST be classified into one
DISPOSITIONS = ("benchmark_target", "code_change", "queue_item", "discard")

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


# --- Disposition keywords for classification ---
_BENCHMARK_KEYWORDS = [
    "metric", "benchmark", "score", "target", "threshold", "measure",
    "latency", "speed", "accuracy", "precision", "recall", "f1",
    "context relevance", "pi ", "performance index", "retrieval quality",
]
_CODE_CHANGE_KEYWORDS = [
    "modify", "refactor", "implement", "add to", "change", "fix",
    "update", "wire", "integrate", "replace", "rewrite", "patch",
    ".py", ".sh", "function", "class", "module", "method",
    "brain.py", "search.py", "store.py", "recall()", "store()",
]
_DISCARD_KEYWORDS = [
    "theoretical", "philosophy", "conceptual framework", "future work",
    "long-term vision", "speculative", "open question",
]


def classify_disposition(proposal: str, covered: bool) -> tuple[str, str]:
    """Classify a proposal into a disposition category.

    Returns (disposition, reason) where disposition is one of DISPOSITIONS.
    """
    text = proposal.lower()

    # Already covered by existing queue item → discard
    if covered:
        return "discard", "already covered by existing queue/archive item"

    # Too short or vague → discard
    if len(proposal) < 30:
        return "discard", "too vague (under 30 chars)"

    # Check for discard signals
    discard_hits = sum(1 for kw in _DISCARD_KEYWORDS if kw in text)
    if discard_hits >= 2:
        return "discard", f"theory-only ({discard_hits} abstract keywords)"

    # Check for benchmark target signals
    benchmark_hits = sum(1 for kw in _BENCHMARK_KEYWORDS if kw in text)
    code_hits = sum(1 for kw in _CODE_CHANGE_KEYWORDS if kw in text)

    if benchmark_hits >= 2 and benchmark_hits > code_hits:
        return "benchmark_target", f"maps to measurable metric ({benchmark_hits} benchmark signals)"
    if code_hits >= 2:
        return "code_change", f"maps to specific code modification ({code_hits} code signals)"

    # Default: actionable but general → queue_item
    if len(proposal) >= 40:
        return "queue_item", "actionable proposal for evolution queue"

    return "discard", "insufficient actionable signals"


def _dedup_key(entry: dict) -> str:
    """Compute an idempotency key from paper_file + normalized proposal + disposition."""
    paper = entry.get("paper_file", "")
    proposal = re.sub(r"\s+", " ", entry.get("proposal", "")).strip().lower()
    disposition = entry.get("disposition", "")
    raw = f"{paper}|{proposal}|{disposition}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _proposal_fingerprint(paper_file: str, proposal: str) -> str:
    """Disposition-agnostic fingerprint: paper_file + normalized proposal.

    Used at scan time to skip proposals that were previously processed
    (regardless of their disposition), preventing completed/discarded
    research from leaking back into the actionable pipeline.
    """
    norm = re.sub(r"\s+", " ", proposal).strip().lower()
    raw = f"{paper_file}|{norm}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _load_existing_keys(path: str) -> set[str]:
    """Load dedup keys from an existing disposition log."""
    keys: set[str] = set()
    if not os.path.exists(path):
        return keys
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    k = rec.get("dedup_key") or _dedup_key(rec)
                    keys.add(k)
                except json.JSONDecodeError:
                    pass
    except Exception:
        pass
    return keys


def _load_processed_fingerprints(path: str) -> set[str]:
    """Load disposition-agnostic fingerprints from the disposition log.

    Returns a set of fingerprints for proposals that have already been
    classified (any disposition), so scan_papers() can skip them.
    """
    fps: set[str] = set()
    if not os.path.exists(path):
        return fps
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    fp = _proposal_fingerprint(
                        rec.get("paper_file", ""),
                        rec.get("proposal", ""),
                    )
                    fps.add(fp)
                except json.JSONDecodeError:
                    pass
    except Exception:
        pass
    return fps


def _log_dispositions(entries: list[dict]):
    """Append disposition records to the JSONL log, skipping duplicates.

    Deduplication uses a hash of (paper_file, normalized proposal, disposition).
    Records already in the log (matched by dedup_key) are silently skipped.
    """
    if not entries:
        return
    try:
        os.makedirs(os.path.dirname(DISPOSITION_LOG), exist_ok=True)
    except Exception:
        return

    existing_keys = _load_existing_keys(DISPOSITION_LOG)
    new_count = 0
    try:
        with open(DISPOSITION_LOG, "a") as f:
            for entry in entries:
                key = _dedup_key(entry)
                if key in existing_keys:
                    continue
                entry["dedup_key"] = key
                f.write(json.dumps(entry, default=str) + "\n")
                existing_keys.add(key)
                new_count += 1
    except Exception:
        pass
    return new_count


def _load_disposition_log() -> list[dict]:
    """Load all disposition records."""
    if not os.path.exists(DISPOSITION_LOG):
        return []
    entries = []
    try:
        with open(DISPOSITION_LOG) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    except Exception:
        pass
    return entries


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

    # Load previously-processed proposal fingerprints from disposition log.
    # This prevents completed/partial/discarded proposals from re-entering
    # the actionable pipeline on subsequent scans.
    processed_fps = _load_processed_fingerprints(DISPOSITION_LOG)

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
            # Skip proposals already processed in a previous run
            fp = _proposal_fingerprint(filename, proposal)
            if fp in processed_fps:
                continue

            covered = _is_covered(proposal, queue_items)
            score = _score_proposal(proposal)
            disposition, reason = classify_disposition(proposal, covered)
            results.append({
                "paper": title,
                "paper_file": filename,
                "source": source,
                "proposal": proposal,
                "score": score,
                "covered": covered,
                "disposition": disposition,
                "disposition_reason": reason,
            })

    # Sort: actionable first (non-discard), then by score descending
    disposition_order = {"benchmark_target": 0, "code_change": 1, "queue_item": 2, "discard": 3}
    results.sort(key=lambda r: (disposition_order.get(r["disposition"], 9), -r["score"]))
    return results


def format_queue_item(result: dict) -> str:
    """Format a research proposal as a QUEUE.md task with disposition tag."""
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

    # Include disposition type so queue consumers know what kind of action
    disp = result.get("disposition", "queue_item")
    disp_label = {"benchmark_target": "BENCH", "code_change": "CODE", "queue_item": "TASK"}.get(disp, "TASK")

    return f"[RESEARCH_{tag}] [{disp_label}] From {paper_ref}: {proposal}"


def main():
    if len(sys.argv) < 2:
        print("Usage: research_to_queue.py scan|inject|audit [--max N]")
        sys.exit(1)

    cmd = sys.argv[1]
    max_inject = 3
    for i, arg in enumerate(sys.argv):
        if arg == "--max" and i + 1 < len(sys.argv):
            max_inject = int(sys.argv[i + 1])

    if cmd == "audit":
        _cmd_audit()
        return

    results = scan_papers()

    if not results:
        print("No actionable proposals found in ingested papers.")
        return

    # Group by disposition
    by_disp = {}
    for r in results:
        by_disp.setdefault(r["disposition"], []).append(r)

    actionable = [r for r in results if r["disposition"] != "discard"]
    discarded = by_disp.get("discard", [])

    print(f"=== Research-to-Action Pipeline ===")
    print(f"Papers scanned: {len(set(r['paper_file'] for r in results))}")
    print(f"Total proposals: {len(results)}")
    for disp in DISPOSITIONS:
        count = len(by_disp.get(disp, []))
        print(f"  {disp}: {count}")
    print()

    # Log all dispositions (idempotent — duplicates are skipped)
    now = datetime.now(timezone.utc).isoformat()
    log_entries = [
        {
            "timestamp": now,
            "paper": r["paper"],
            "paper_file": r["paper_file"],
            "proposal": r["proposal"][:200],
            "disposition": r["disposition"],
            "reason": r["disposition_reason"],
            "score": r["score"],
        }
        for r in results
    ]
    new_count = _log_dispositions(log_entries)
    if new_count:
        print(f"Logged {new_count} new disposition(s) ({len(log_entries) - new_count} already recorded).")

    if actionable:
        print("--- ACTIONABLE PROPOSALS ---")
        for i, r in enumerate(actionable[:15], 1):
            status = f"[{r['disposition']}] [score={r['score']:.2f}]"
            print(f"  {i}. {status} {r['paper']}: {r['proposal'][:100]}")
        print()

    if discarded:
        print(f"--- DISCARDED ({len(discarded)} proposals) ---")
        for r in discarded[:5]:
            print(f"  - [{r['disposition_reason']}] {r['paper']}: {r['proposal'][:60]}...")
        print()

    if cmd == "inject" and actionable:
        # Check durable research config before injecting
        try:
            from clarvis.research_config import is_enabled
            if not is_enabled("research_inject_from_papers"):
                print("Research inject is OFF (data/research_config.json). Use 'python3 -m clarvis.research_config enable' to re-enable.")
                return
        except ImportError:
            pass  # Config module not available — allow (backward compat)

        # Import queue_writer for injection
        sys.path.insert(0, os.path.join(WORKSPACE, "scripts"))
        import _paths  # noqa: F401 — registers all script subdirs on sys.path
        try:
            from queue_writer import add_tasks
        except ImportError:
            print("ERROR: Could not import queue_writer", file=sys.stderr)
            sys.exit(1)

        tasks = [format_queue_item(r) for r in actionable[:max_inject]]
        added = add_tasks(tasks, priority="P1", source="research_bridge")
        print(f"Injected {len(added)} task(s) into QUEUE.md (P1)")
        for t in added:
            print(f"  + {t[:100]}...")

    elif cmd == "scan":
        if actionable:
            print(f"Run 'research_to_queue.py inject' to add top {min(max_inject, len(actionable))} to QUEUE.md")
        else:
            print("No actionable proposals found (all discarded).")
    else:
        print("No actionable candidates to inject.")


def _cmd_audit():
    """Show disposition statistics from the log."""
    entries = _load_disposition_log()
    if not entries:
        print("No disposition records yet. Run 'scan' or 'inject' first.")
        return

    by_disp = {}
    by_reason = {}
    for e in entries:
        d = e.get("disposition", "unknown")
        by_disp[d] = by_disp.get(d, 0) + 1
        if d == "discard":
            r = e.get("reason", "unknown")
            by_reason[r] = by_reason.get(r, 0) + 1

    total = len(entries)
    print(f"=== Research Disposition Audit ({total} records) ===")
    for d in DISPOSITIONS:
        count = by_disp.get(d, 0)
        pct = (count / total * 100) if total else 0
        print(f"  {d}: {count} ({pct:.0f}%)")

    action_count = total - by_disp.get("discard", 0)
    print(f"\nActionable rate: {action_count}/{total} ({action_count/total*100:.0f}%)" if total else "")

    if by_reason:
        print(f"\nDiscard reasons:")
        for reason, count in sorted(by_reason.items(), key=lambda x: -x[1]):
            print(f"  {count}x {reason}")


if __name__ == "__main__":
    main()
