#!/usr/bin/env python3
"""
Procedural Memory — Reusable step sequences for recurring tasks

Inspired by ACT-R procedural memory and Voyager's skill library.
When a multi-step task succeeds, store the step sequence as a reusable procedure.
Before starting similar tasks, check if a procedure already exists.

Procedures are stored in brain collection='clarvis-procedures' with metadata:
  - name: short identifier
  - steps: JSON list of step descriptions
  - use_count: times this procedure was applied
  - success_count: times it led to success
  - source_task: original task that generated it

Usage:
    # Check for existing procedure before starting a task
    python3 procedural_memory.py check "Build a monitoring dashboard"

    # Learn a new procedure from a successful task
    python3 procedural_memory.py learn "Build dashboard" '["Read requirements","Create script","Wire into cron","Test"]'

    # Record that a procedure was used (success or failure)
    python3 procedural_memory.py used "proc_build_dashboard" success

    # List all stored procedures
    python3 procedural_memory.py list
"""

import sys
import os
import json
import re
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from brain import brain, PROCEDURES


def find_procedure(task_text: str, threshold: float = 0.5) -> dict | None:
    """Search for a matching procedure for a given task.

    Uses semantic similarity via brain.recall() on the procedures collection.
    Returns the best match if similarity exceeds threshold, else None.

    Args:
        task_text: Description of the task to find a procedure for
        threshold: Maximum cosine distance to accept (lower = stricter match).
                   Default 0.5. Typical good matches are < 0.3.

    Returns:
        Dict with procedure info (name, steps, success_rate, id) or None
    """
    results = brain.recall(
        task_text,
        collections=[PROCEDURES],
        n=3,
    )

    if not results:
        return None

    # Pick the closest semantic match (lowest distance)
    results_with_dist = [r for r in results if r.get("distance") is not None]
    if results_with_dist:
        best = min(results_with_dist, key=lambda r: r["distance"])
    else:
        best = results[0]

    distance = best.get("distance")

    # Filter by similarity threshold — reject if too dissimilar
    if distance is not None and distance > threshold:
        return None

    meta = best.get("metadata", {})

    # Parse steps from metadata
    steps = []
    steps_raw = meta.get("steps", "[]")
    try:
        steps = json.loads(steps_raw) if isinstance(steps_raw, str) else steps_raw
    except (json.JSONDecodeError, TypeError):
        steps = []

    use_count = int(meta.get("use_count", 0))
    success_count = int(meta.get("success_count", 0))
    success_rate = success_count / use_count if use_count > 0 else 1.0

    return {
        "id": best["id"],
        "name": meta.get("name", "unknown"),
        "description": best["document"],
        "steps": steps,
        "use_count": use_count,
        "success_count": success_count,
        "success_rate": success_rate,
        "source_task": meta.get("source_task", ""),
    }


def store_procedure(name: str, description: str, steps: list[str],
                    source_task: str = "", importance: float = 0.8,
                    tags: list[str] | None = None) -> str:
    """Store a new procedure (or update existing one with same name).

    Args:
        name: Short procedure name (e.g., "build_monitoring_dashboard")
        description: What this procedure does
        steps: Ordered list of step descriptions
        source_task: The original task text that generated this procedure
        importance: How important/reusable (default 0.8)
        tags: Additional categorization tags

    Returns:
        The procedure memory ID
    """
    proc_id = f"proc_{_sanitize_name(name)}"
    tags = tags or []
    tags.extend(["procedure", "skill"])
    # Deduplicate tags
    tags = list(set(tags))

    doc_text = f"Procedure: {name} — {description}"

    # Check if procedure already exists — merge use stats
    existing_use_count = 0
    existing_success_count = 0
    try:
        col = brain.collections[PROCEDURES]
        existing = col.get(ids=[proc_id])
        if existing and existing["ids"]:
            old_meta = existing["metadatas"][0] if existing.get("metadatas") else {}
            existing_use_count = int(old_meta.get("use_count", 0))
            existing_success_count = int(old_meta.get("success_count", 0))
    except Exception:
        pass

    mem_id = brain.store(
        doc_text,
        collection=PROCEDURES,
        importance=importance,
        tags=tags,
        source="procedural_memory",
        memory_id=proc_id,
    )

    # Update with procedure-specific metadata
    col = brain.collections[PROCEDURES]
    existing = col.get(ids=[proc_id])
    if existing and existing["ids"]:
        meta = existing["metadatas"][0]
        meta["name"] = name
        meta["steps"] = json.dumps(steps)
        meta["source_task"] = source_task[:500]
        meta["use_count"] = existing_use_count
        meta["success_count"] = existing_success_count
        meta["step_count"] = len(steps)
        col.upsert(
            ids=[proc_id],
            documents=[doc_text],
            metadatas=[meta],
        )

    return mem_id


def record_use(proc_id: str, success: bool) -> dict:
    """Record that a procedure was used, updating use/success counts.

    Args:
        proc_id: The procedure memory ID
        success: Whether the procedure led to success

    Returns:
        Updated stats dict {use_count, success_count, success_rate}
    """
    col = brain.collections[PROCEDURES]
    existing = col.get(ids=[proc_id])

    if not existing or not existing["ids"]:
        return {"error": f"Procedure {proc_id} not found"}

    meta = existing["metadatas"][0]
    use_count = int(meta.get("use_count", 0)) + 1
    success_count = int(meta.get("success_count", 0)) + (1 if success else 0)

    meta["use_count"] = use_count
    meta["success_count"] = success_count
    meta["last_used"] = datetime.now(timezone.utc).isoformat()
    # Boost importance for frequently-used successful procedures
    if use_count >= 3 and success_count / use_count > 0.8:
        meta["importance"] = min(1.0, float(meta.get("importance", 0.8)) + 0.05)

    col.upsert(
        ids=[proc_id],
        documents=existing["documents"],
        metadatas=[meta],
    )

    return {
        "use_count": use_count,
        "success_count": success_count,
        "success_rate": success_count / use_count,
    }


def learn_from_task(task_text: str, steps: list[str], tags: list[str] | None = None) -> str:
    """Learn a procedure from a successful task execution.

    Extracts a reusable procedure name from the task text and stores it.

    Args:
        task_text: The original task description
        steps: The steps that were executed successfully

    Returns:
        The procedure memory ID
    """
    # Derive a short name from the task text
    name = _derive_name(task_text)
    description = task_text[:200]

    return store_procedure(
        name=name,
        description=description,
        steps=steps,
        source_task=task_text,
        tags=tags or [],
    )


def list_procedures(n: int = 50) -> list[dict]:
    """List all stored procedures.

    Returns:
        List of procedure dicts sorted by use_count (most used first)
    """
    results = brain.get(PROCEDURES, n=n)

    procedures = []
    for r in results:
        meta = r.get("metadata", {})
        steps = []
        try:
            steps = json.loads(meta.get("steps", "[]"))
        except (json.JSONDecodeError, TypeError):
            steps = []

        use_count = int(meta.get("use_count", 0))
        success_count = int(meta.get("success_count", 0))

        procedures.append({
            "id": r["id"],
            "name": meta.get("name", "unknown"),
            "description": r["document"],
            "steps": steps,
            "step_count": len(steps),
            "use_count": use_count,
            "success_count": success_count,
            "success_rate": success_count / use_count if use_count > 0 else 1.0,
            "importance": float(meta.get("importance", 0)),
        })

    procedures.sort(key=lambda p: p["use_count"], reverse=True)
    return procedures


def _sanitize_name(name: str) -> str:
    """Convert a name to a safe ID string."""
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower().strip())
    sanitized = re.sub(r'_+', '_', sanitized).strip('_')
    return sanitized[:80]


def _derive_name(task_text: str) -> str:
    """Derive a short procedure name from task text."""
    # Remove common prefixes
    text = task_text.strip()
    for prefix in ["Build ", "Create ", "Implement ", "Add ", "Wire ", "Make ", "Set up "]:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break

    # Take first meaningful chunk (up to first dash or period)
    text = text.split("—")[0].split(" — ")[0].split(". ")[0].strip()
    # Limit length
    words = text.split()[:6]
    return "_".join(words).lower()


# === CLI ===

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: procedural_memory.py <command> [args]")
        print("Commands:")
        print("  check <task_text>         - Find matching procedure for a task")
        print("  learn <task_text> <steps>  - Store procedure from successful task")
        print("  used <proc_id> <success|failure> - Record procedure usage")
        print("  list                       - List all procedures")
        print("  store <name> <desc> <steps> - Store a named procedure")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "check":
        task_text = sys.argv[2] if len(sys.argv) > 2 else ""
        if not task_text:
            print("{}", flush=True)
            sys.exit(0)
        result = find_procedure(task_text)
        if result:
            print(json.dumps(result, indent=2))
        else:
            print("{}", flush=True)

    elif cmd == "learn":
        task_text = sys.argv[2] if len(sys.argv) > 2 else ""
        steps_json = sys.argv[3] if len(sys.argv) > 3 else "[]"
        try:
            steps = json.loads(steps_json)
        except json.JSONDecodeError:
            # Try splitting by semicolons if not valid JSON
            steps = [s.strip() for s in steps_json.split(";") if s.strip()]
        proc_id = learn_from_task(task_text, steps)
        print(f"Learned: {proc_id}")

    elif cmd == "used":
        proc_id = sys.argv[2] if len(sys.argv) > 2 else ""
        success_str = sys.argv[3] if len(sys.argv) > 3 else "success"
        success = success_str.lower() in ("success", "true", "1", "yes")
        result = record_use(proc_id, success)
        print(json.dumps(result))

    elif cmd == "list":
        procs = list_procedures()
        if not procs:
            print("No procedures stored yet.")
        else:
            for p in procs:
                rate = f"{p['success_rate']:.0%}" if p['use_count'] > 0 else "new"
                print(f"  [{p['id']}] {p['name']} ({p['step_count']} steps, used {p['use_count']}x, {rate})")
                if p['steps']:
                    for i, step in enumerate(p['steps'], 1):
                        print(f"    {i}. {step}")

    elif cmd == "store":
        name = sys.argv[2] if len(sys.argv) > 2 else ""
        desc = sys.argv[3] if len(sys.argv) > 3 else ""
        steps_json = sys.argv[4] if len(sys.argv) > 4 else "[]"
        try:
            steps = json.loads(steps_json)
        except json.JSONDecodeError:
            steps = [s.strip() for s in steps_json.split(";") if s.strip()]
        proc_id = store_procedure(name, desc, steps)
        print(f"Stored: {proc_id}")

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
