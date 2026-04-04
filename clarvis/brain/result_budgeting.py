#!/usr/bin/env python3
"""Brain Result Budgeting — harness-inspired per-result + per-message size limits.

Prevents context bloat from large brain search results by persisting oversized
results to disk and injecting previews + pointers into context.

Based on Claude Code harness pattern:
  - Per-result limit: 30K chars (brain results rarely hit 50K)
  - Per-message aggregate: 100K chars (all collections in one heartbeat turn)
  - Overflow: persist full result to disk, inject 2KB preview

Usage:
    from clarvis.brain.result_budgeting import budget_results, cleanup_session

    # In brain_bridge.py after recall:
    results = budget_results(results, session_id="heartbeat_123")

    # In postflight cleanup:
    cleanup_session("heartbeat_123")
"""

import json
import os
import time
from pathlib import Path

# --- Limits (inspired by harness toolResultStorage.ts) ---
MAX_RESULT_CHARS = 30_000       # Per-memory limit before persisting
MAX_MESSAGE_CHARS = 100_000     # Aggregate across all results in one turn
PREVIEW_SIZE = 2_000            # Preview bytes when persisting

# Persistence directory
_DATA_ROOT = Path(os.environ.get(
    "CLARVIS_WORKSPACE", os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
)) / "data" / "brain_recall"


def _generate_preview(text: str, max_bytes: int = PREVIEW_SIZE) -> str:
    """Cut at last newline within limit, avoiding mid-line truncation."""
    if len(text) <= max_bytes:
        return text
    truncated = text[:max_bytes]
    last_nl = truncated.rfind('\n')
    if last_nl > max_bytes * 0.5:
        return truncated[:last_nl]
    return truncated


def _persist_result(result: dict, session_dir: Path) -> dict:
    """Write full result to disk, return preview version."""
    doc = result.get("document", "")
    mem_id = result.get("id", f"mem_{int(time.time() * 1000)}")

    session_dir.mkdir(parents=True, exist_ok=True)
    result_path = session_dir / f"{mem_id}.json"

    try:
        result_path.write_text(json.dumps(result, indent=2, default=str))
    except OSError:
        return result  # Can't persist — return unmodified

    preview = _generate_preview(doc)
    return {
        **result,
        "document": preview,
        "_persisted_path": str(result_path),
        "_persisted_full_size": len(doc),
        "_has_more": len(doc) > len(preview),
    }


def budget_results(results: list, session_id: str = None) -> list:
    """Apply per-result + per-message budgeting to brain search results.

    Args:
        results: List of brain recall result dicts.
        session_id: Session identifier for disk persistence directory.

    Returns:
        List of results with oversized ones replaced by previews + disk pointers.
    """
    if not results:
        return results

    session_id = session_id or f"anon_{int(time.time())}"
    session_dir = _DATA_ROOT / session_id

    # Phase 1: Per-result budgeting
    budgeted = []
    for r in results:
        doc = r.get("document", "")
        if len(doc) > MAX_RESULT_CHARS:
            budgeted.append(_persist_result(r, session_dir))
        else:
            budgeted.append(r)

    # Phase 2: Per-message aggregate budgeting
    total_chars = sum(len(r.get("document", "")) for r in budgeted)
    if total_chars <= MAX_MESSAGE_CHARS:
        return budgeted

    # Sort by distance (best first), persist largest until under budget
    by_distance = sorted(enumerate(budgeted), key=lambda x: x[1].get("distance", 1.0))
    current_total = total_chars

    for idx, r in reversed(by_distance):  # Persist worst-distance first
        if current_total <= MAX_MESSAGE_CHARS:
            break
        if "_persisted_path" in r:
            continue  # Already persisted
        doc_len = len(r.get("document", ""))
        if doc_len > PREVIEW_SIZE:
            persisted = _persist_result(r, session_dir)
            saved = doc_len - len(persisted.get("document", ""))
            current_total -= saved
            budgeted[idx] = persisted

    return budgeted


def cleanup_session(session_id: str) -> int:
    """Remove persisted results for a completed session. Returns files removed."""
    session_dir = _DATA_ROOT / session_id
    if not session_dir.exists():
        return 0
    count = 0
    for f in session_dir.glob("*.json"):
        try:
            f.unlink()
            count += 1
        except OSError:
            pass
    try:
        session_dir.rmdir()
    except OSError:
        pass
    return count


def get_budget_stats(results: list) -> dict:
    """Return budgeting statistics for logging/diagnostics."""
    persisted = [r for r in results if "_persisted_path" in r]
    return {
        "total_results": len(results),
        "persisted_count": len(persisted),
        "persisted_bytes": sum(r.get("_persisted_full_size", 0) for r in persisted),
        "inline_bytes": sum(len(r.get("document", "")) for r in results),
    }
