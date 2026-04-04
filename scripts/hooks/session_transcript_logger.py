#!/usr/bin/env python3
"""
Session Transcript Logger — persist task execution metadata and raw output.

Writes:
  data/session_transcripts/YYYY-MM-DD.jsonl  — one JSON line per task execution
  data/session_transcripts/raw/<hash>.txt     — full raw output (only when >500 chars)

The JSONL metadata enables conversation_learner.py to do prompt-outcome analysis
instead of relying on 200-char digest snippets.

Privacy: output is already sanitized by the heartbeat pipeline (no user PII).
Raw files are rotated by cleanup_policy.py (compress >7d, delete >90d).
"""

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
TRANSCRIPTS_DIR = WORKSPACE / "data" / "session_transcripts"
RAW_DIR = TRANSCRIPTS_DIR / "raw"

# Only persist raw output files above this size (smaller output is inline in JSONL)
RAW_THRESHOLD = 500
# Cap inline output in JSONL to avoid bloated lines
INLINE_CAP = 2000
# Cap raw file size to avoid persisting huge Claude dumps
RAW_CAP = 200_000


def _ensure_dirs():
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)


def _task_slug(task: str, max_len: int = 48) -> str:
    """Derive a short, filesystem-safe slug from a task title.

    Extracts [BRACKET_TAG] if present, otherwise takes the first few
    significant words. Result is lowercased, alphanumeric + hyphens.
    """
    # Try bracket tag first (e.g. "[SPINE_MIGRATION] ..." or "[EXTERNAL_CHALLENGE:bench-01]")
    tag_match = re.search(r"\[([A-Za-z0-9_:.-]+)\]", task)
    if tag_match:
        slug = tag_match.group(1).lower().replace("_", "-").replace(":", "-")
    else:
        # First 5 significant words
        words = re.findall(r"[a-z0-9]+", task.lower())
        stop = {"the", "a", "an", "in", "to", "for", "of", "and", "or", "with", "is", "on"}
        words = [w for w in words if w not in stop][:5]
        slug = "-".join(words) if words else "task"
    return slug[:max_len]


def log_transcript(
    task: str,
    task_status: str,
    exit_code: int,
    task_duration: int,
    output_text: str,
    error_type: str | None = None,
    worker_type: str = "general",
    task_section: str = "P1",
    chain_id: str | None = None,
    extra: dict | None = None,
) -> dict:
    """Persist a task execution transcript. Returns metadata dict written."""
    _ensure_dirs()

    now = datetime.now(timezone.utc)
    ts = now.isoformat()
    date_str = now.strftime("%Y-%m-%d")

    # Build metadata record
    slug = _task_slug(task)
    record = {
        "ts": ts,
        "slug": slug,
        "task": task[:500],
        "status": task_status,
        "exit_code": exit_code,
        "duration_s": task_duration,
        "section": task_section,
        "worker_type": worker_type,
    }
    if error_type:
        record["error_type"] = error_type
    if chain_id:
        record["chain_id"] = chain_id

    # Handle output: inline if small, raw file if large
    output_len = len(output_text) if output_text else 0
    record["output_len"] = output_len

    if output_text and output_len > RAW_THRESHOLD:
        # Write raw file, reference by content hash
        capped = output_text[-RAW_CAP:] if output_len > RAW_CAP else output_text
        content_hash = hashlib.sha256(capped.encode("utf-8", errors="replace")).hexdigest()[:16]
        raw_name = f"{date_str}_{int(time.time())}_{content_hash}.txt"
        raw_path = RAW_DIR / raw_name
        try:
            raw_path.write_text(capped, encoding="utf-8", errors="replace")
            record["raw_file"] = raw_name
        except OSError:
            # Fall back to inline if write fails
            record["output_tail"] = output_text[-INLINE_CAP:]
    elif output_text:
        record["output_tail"] = output_text[-INLINE_CAP:]

    if extra:
        record["extra"] = extra

    # Append to daily JSONL
    jsonl_path = TRANSCRIPTS_DIR / f"{date_str}.jsonl"
    try:
        with open(jsonl_path, "a") as f:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")
    except OSError as e:
        # Non-fatal: don't crash postflight for logging
        return {"error": str(e)}

    return record
