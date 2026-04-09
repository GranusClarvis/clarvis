#!/usr/bin/env python3
"""Wiki pipeline hooks — trigger points for automatic wiki ingestion.

Provides hook functions called from:
  - heartbeat_postflight.py  (auto-ingest research outputs)
  - research_to_queue.py     (register papers in wiki source registry)
  - CLI operator drops        (manual source drops via `clarvis wiki drop`)

Promotion gates:
  - RESEARCH task with output containing "RESEARCH_RESULT:" → auto-ingest
  - Successful repo analysis → auto-ingest
  - Operator drop → always ingest (operator intent = gate)
  - All other tasks → skip (wiki should not be a silent sidecar)

Each hook is fail-safe: exceptions are caught and logged, never breaking
the caller pipeline.
"""

import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"))
KNOWLEDGE = WORKSPACE / "knowledge"
RAW_DIR = KNOWLEDGE / "raw"
LOGS_DIR = KNOWLEDGE / "logs"
SOURCES_JSONL = LOGS_DIR / "sources.jsonl"
HOOK_LOG = WORKSPACE / "monitoring" / "wiki_hooks.log"

TODAY = datetime.date.today().isoformat()


def _log(msg: str) -> None:
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    line = f"[{ts}] WIKI_HOOK: {msg}\n"
    try:
        HOOK_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(HOOK_LOG, "a") as f:
            f.write(line)
    except Exception:
        pass
    print(line.rstrip(), file=sys.stderr)


# ============================================================
# Promotion gate: decides whether a task output is wiki-worthy
# ============================================================

# Task tags that trigger wiki ingestion on success
WIKI_ELIGIBLE_TAGS = {
    "RESEARCH", "WIKI_", "REPO_INGEST", "PAPER_INGEST",
}

# Output markers that indicate wiki-worthy content
WIKI_OUTPUT_MARKERS = [
    "RESEARCH_RESULT:",
    "## Abstract",
    "## Key Claims",
    "## Relevance to Clarvis",
    "## Repository Structure",
]


def should_ingest_output(task_tag: str, task_text: str, output_text: str, task_status: str) -> tuple[bool, str]:
    """Decide whether a task's output should be auto-ingested into the wiki.

    Returns (should_ingest, reason).
    Promotion gates are explicit — only known patterns trigger ingestion.
    """
    if task_status != "success":
        return False, "task_not_success"

    # Gate 1: task tag match
    tag_upper = (task_tag or "").upper()
    for prefix in WIKI_ELIGIBLE_TAGS:
        if tag_upper.startswith(prefix):
            # Still need output substance
            if len(output_text.strip()) < 200:
                return False, f"tag_match_{prefix}_but_output_too_short"
            return True, f"tag_match_{prefix}"

    # Gate 2: output contains research result marker
    for marker in WIKI_OUTPUT_MARKERS:
        if marker in output_text:
            return True, f"output_marker_{marker[:20]}"

    return False, "no_gate_matched"


# ============================================================
# Postflight hook: auto-ingest task output into wiki raw layer
# ============================================================

def postflight_wiki_ingest(task: str, task_tag: str, task_status: str,
                           output_text: str, exit_code: int) -> dict:
    """Called from heartbeat_postflight after task execution.

    Checks promotion gates, then ingests qualifying output as a raw source.
    Returns {ingested: bool, source_id: str|None, reason: str}.
    """
    result = {"ingested": False, "source_id": None, "reason": ""}

    try:
        should, reason = should_ingest_output(task_tag or "", task, output_text, task_status)
        result["reason"] = reason

        if not should:
            _log(f"Skip: {reason} (tag={task_tag}, status={task_status})")
            return result

        # Determine source type from task content
        task_lower = (task or "").lower()
        if "repo" in task_lower or "github" in task_lower:
            source_type = "repo"
        elif "paper" in task_lower or "arxiv" in task_lower:
            source_type = "paper"
        else:
            source_type = "web"  # research notes default to web type

        # Build raw content with frontmatter
        title = _extract_title(task, task_tag, output_text)
        content_bytes = output_text.encode("utf-8")
        checksum = hashlib.sha256(content_bytes).hexdigest()
        source_id = f"{TODAY}-{source_type}-{checksum[:8]}"

        # Check dedup
        if SOURCES_JSONL.exists():
            with open(SOURCES_JSONL) as f:
                for line in f:
                    if checksum[:16] in line:
                        result["reason"] = "duplicate_checksum"
                        _log(f"Skip: duplicate checksum for {source_id}")
                        return result

        # Store raw file
        dest_dir = RAW_DIR / source_type
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{source_id}.md"
        dest.write_text(output_text, encoding="utf-8")

        raw_path = str(dest.relative_to(KNOWLEDGE))

        # Register in source registry
        record = {
            "source_id": source_id,
            "source_url": f"heartbeat:{task_tag or 'auto'}",
            "raw_path": raw_path,
            "ingest_ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "checksum_sha256": checksum,
            "source_type": source_type,
            "status": "ingested",
            "title": title,
            "file_size": len(content_bytes),
            "entities": [],
            "concepts": _extract_concepts_quick(output_text),
            "linked_pages": [],
            "confidence": "medium",
            "meta": {"origin": "postflight", "task_tag": task_tag},
        }

        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(SOURCES_JSONL, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        result["ingested"] = True
        result["source_id"] = source_id
        _log(f"Ingested: {source_id} ({source_type}, {len(content_bytes)} bytes, gate={reason})")

    except Exception as e:
        result["reason"] = f"error:{e}"
        _log(f"Error: {e}")

    return result


# ============================================================
# Research bridge: register paper in wiki when research_to_queue processes it
# ============================================================

def research_paper_to_wiki(paper_file: str, paper_title: str, paper_source: str) -> dict:
    """Called from research_to_queue when scanning/injecting a paper.

    Registers the paper in wiki source registry if not already there.
    Does NOT compile — compilation is a separate promotion gate.
    Returns {registered: bool, source_id: str|None, reason: str}.
    """
    result = {"registered": False, "source_id": None, "reason": ""}

    try:
        ingested_dir = WORKSPACE / "memory" / "research" / "ingested"
        src_path = ingested_dir / paper_file

        if not src_path.exists():
            result["reason"] = "file_not_found"
            return result

        content = src_path.read_text(encoding="utf-8", errors="replace")
        content_bytes = content.encode("utf-8")
        checksum = hashlib.sha256(content_bytes).hexdigest()

        # Check if already in wiki registry
        if SOURCES_JSONL.exists():
            with open(SOURCES_JSONL) as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                        if rec.get("checksum_sha256") == checksum:
                            result["reason"] = "already_registered"
                            result["source_id"] = rec.get("source_id")
                            return result
                    except json.JSONDecodeError:
                        continue

        # Copy to wiki raw layer
        source_id = f"{TODAY}-paper-{checksum[:8]}"
        dest_dir = RAW_DIR / "paper"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{source_id}.md"
        dest.write_text(content, encoding="utf-8")

        raw_path = str(dest.relative_to(KNOWLEDGE))

        record = {
            "source_id": source_id,
            "source_url": paper_source or f"research:{paper_file}",
            "raw_path": raw_path,
            "ingest_ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "checksum_sha256": checksum,
            "source_type": "paper",
            "status": "ingested",
            "title": paper_title,
            "file_size": len(content_bytes),
            "entities": [],
            "concepts": _extract_concepts_quick(content),
            "linked_pages": [],
            "confidence": "low",
            "meta": {"origin": "research_to_queue", "paper_file": paper_file},
        }

        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(SOURCES_JSONL, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        result["registered"] = True
        result["source_id"] = source_id
        _log(f"Research→Wiki: {source_id} ({paper_title[:60]})")

    except Exception as e:
        result["reason"] = f"error:{e}"
        _log(f"Research→Wiki error: {e}")

    return result


# ============================================================
# Operator drop: manual source ingestion (delegates to wiki_ingest)
# ============================================================

def operator_drop(path_or_url: str, source_type: str | None = None, title: str | None = None) -> dict:
    """Operator-initiated source drop.

    Delegates to wiki_ingest.py functions for actual processing.
    This is the simplest path: operator intent = promotion gate.
    """
    try:
        # Import wiki_ingest functions
        sys.path.insert(0, str(Path(__file__).parent))
        from wiki_ingest import ingest_file, ingest_url, ingest_repo

        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            if "github.com" in path_or_url:
                return ingest_repo(path_or_url, title=title)
            else:
                return ingest_url(path_or_url, source_type=source_type or "web", title=title)
        else:
            return ingest_file(path_or_url, source_type=source_type, title=title)

    except Exception as e:
        _log(f"Operator drop error: {e}")
        return {"error": str(e)}


# ============================================================
# Helpers
# ============================================================

def _extract_title(task: str, task_tag: str, output: str) -> str:
    """Extract a title from task context or output."""
    # Try output first line / H1
    for line in output.split("\n")[:20]:
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()[:120]
    # Try TOPIC from RESEARCH_RESULT block
    m = re.search(r"TOPIC:\s*(.+)", output)
    if m:
        return m.group(1).strip()[:120]
    # Fallback to task tag or task text
    if task_tag:
        return task_tag.replace("_", " ").title()[:120]
    return (task or "Untitled")[:120]


def _extract_concepts_quick(text: str) -> list[str]:
    """Quick concept extraction from bold terms and headers."""
    concepts = set()
    for m in re.finditer(r"\*\*(.+?)\*\*", text):
        t = m.group(1).strip()
        if 3 < len(t) < 80:
            concepts.add(t)
    for m in re.finditer(r"^#{1,3}\s+(.+)$", text, re.MULTILINE):
        t = m.group(1).strip()
        if 3 < len(t) < 80:
            concepts.add(t)
    return sorted(concepts)[:20]


# ============================================================
# CLI (standalone testing)
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Wiki pipeline hooks")
    sub = parser.add_subparsers(dest="cmd")

    p_test = sub.add_parser("test-gate", help="Test promotion gate")
    p_test.add_argument("--tag", default="")
    p_test.add_argument("--task", default="test task")
    p_test.add_argument("--output", default="")
    p_test.add_argument("--status", default="success")

    p_drop = sub.add_parser("drop", help="Operator source drop")
    p_drop.add_argument("path_or_url")
    p_drop.add_argument("--type", default=None)
    p_drop.add_argument("--title", default=None)

    args = parser.parse_args()

    if args.cmd == "test-gate":
        ok, reason = should_ingest_output(args.tag, args.task, args.output, args.status)
        print(f"should_ingest={ok}  reason={reason}")
    elif args.cmd == "drop":
        result = operator_drop(args.path_or_url, source_type=args.type, title=args.title)
        print(json.dumps(result, indent=2, default=str))
    else:
        parser.print_help()
