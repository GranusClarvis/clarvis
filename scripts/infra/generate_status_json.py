#!/usr/bin/env python3
"""Generate static status.json for the public website.

Reads CLR benchmark, Performance Index, brain stats, episode data,
and evolution queue to produce a public-safe status snapshot.

Usage:
    python3 scripts/generate_status_json.py
    # Writes to both docs/status.json and website/static/status.json
"""

import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent.parent
DATA_DIR = WORKSPACE / "data"
MEMORY_DIR = WORKSPACE / "memory"

CLR_FILE = DATA_DIR / "clr_benchmark.json"
PI_FILE = DATA_DIR / "performance_metrics.json"
EPISODES_FILE = DATA_DIR / "episodes.json"
QUEUE_FILE = MEMORY_DIR / "evolution" / "QUEUE.md"
QUEUE_ARCHIVE = MEMORY_DIR / "evolution" / "QUEUE_ARCHIVE.md"
MODE_FILE = DATA_DIR / "runtime_mode.json"
PHI_HISTORY_FILE = DATA_DIR / "phi_history.json"

# Output locations
DOCS_DIR = WORKSPACE / "docs"
WEBSITE_STATIC = WORKSPACE / "website" / "static"


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def get_clr_payload(data: dict) -> dict:
    return {
        "clr": data.get("clr"),
        "baseline_clr": data.get("baseline_clr"),
        "value_add": data.get("value_add"),
        "gate_pass": data.get("gate", {}).get("pass"),
        "dimensions": {
            k: v.get("score") for k, v in data.get("dimensions", {}).items()
        },
        "timestamp": data.get("timestamp"),
    }


def get_pi_payload(data: dict) -> dict:
    summary = data.get("summary", {})
    return {
        "pi": data.get("pi", {}).get("pi") or summary.get("pi"),
        "dimensions": summary.get("total_scored", 0),
        "timestamp": data.get("timestamp"),
    }


def get_brain_stats() -> dict:
    """Get brain stats without importing heavy modules."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "clarvis", "brain", "stats"],
            capture_output=True, text=True, timeout=30,
            cwd=str(WORKSPACE),
        )
        output = result.stdout
        # Parse total memories and collections from stats output
        total = 0
        collections = 0
        for line in output.splitlines():
            if "total" in line.lower() and "memor" in line.lower():
                nums = re.findall(r"\d+", line)
                if nums:
                    total = int(nums[0])
            elif "collection" in line.lower():
                nums = re.findall(r"\d+", line)
                if nums:
                    collections = int(nums[0])
        if total == 0:
            # Fallback: count all numbers that look like memory counts
            nums = re.findall(r"(\d+)\s+memor", output, re.IGNORECASE)
            if nums:
                total = sum(int(n) for n in nums)
            collections = 10  # known constant
        return {"total_memories": total, "collections": collections or 10}
    except Exception:
        return {"total_memories": 0, "collections": 10}


def get_episode_stats() -> dict:
    """Calculate episode success rate from episodes.json."""
    try:
        episodes = json.loads(EPISODES_FILE.read_text())
        if not isinstance(episodes, list) or not episodes:
            return {"success_rate": 0, "total": 0}
        outcomes = Counter(e.get("outcome", "unknown") for e in episodes)
        total = len(episodes)
        success = outcomes.get("success", 0)
        return {
            "success_rate": round(success / total, 3) if total > 0 else 0,
            "total": total,
            "breakdown": {
                "success": success,
                "soft_failure": outcomes.get("soft_failure", 0),
                "failure": outcomes.get("failure", 0),
                "timeout": outcomes.get("timeout", 0),
            },
        }
    except (OSError, json.JSONDecodeError):
        return {"success_rate": 0, "total": 0}


def get_uptime() -> str:
    """Get system uptime."""
    try:
        result = subprocess.run(
            ["uptime", "-s"], capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def parse_queue_counts(path: Path) -> dict:
    pending = in_progress = done = 0
    try:
        text = path.read_text()
    except OSError:
        return {"pending": 0, "in_progress": 0, "done": 0}
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("- [ ]"):
            pending += 1
        elif s.startswith("- [~]"):
            in_progress += 1
        elif s.startswith("- [x]"):
            done += 1
    return {"pending": pending, "in_progress": in_progress, "done": done}


def recent_completions(queue_path: Path, archive_path: Path, limit: int = 5) -> list:
    completions = []
    tag_re = re.compile(r"\[x\]\s*\[([A-Z0-9_]+)\]")
    for path in [queue_path, archive_path]:
        try:
            text = path.read_text()
        except OSError:
            continue
        for line in text.splitlines():
            m = tag_re.search(line.strip())
            if m:
                completions.append({"tag": m.group(1), "status": "success"})
    return completions[:limit]


def get_phi_payload() -> dict | None:
    """Extract latest phi value from phi_history.json."""
    try:
        data = json.loads(PHI_HISTORY_FILE.read_text())
        if isinstance(data, list) and data:
            latest = data[-1]
            return {
                "current": latest.get("phi"),
                "timestamp": latest.get("timestamp"),
            }
    except (OSError, json.JSONDecodeError):
        pass
    return None


def get_bloat_score(pi_raw: dict | None) -> float | None:
    """Extract bloat_score from performance metrics."""
    if pi_raw:
        metrics = pi_raw.get("metrics", {})
        bs = metrics.get("bloat_score")
        if bs is not None:
            return bs
    return None


def get_mode() -> dict:
    data = read_json(MODE_FILE)
    if data:
        return {"mode": data.get("mode", "ge"), "pending_mode": data.get("pending_mode")}
    return {"mode": "ge", "pending_mode": None}


def generate() -> dict:
    clr_raw = read_json(CLR_FILE)
    pi_raw = read_json(PI_FILE)
    queue = parse_queue_counts(QUEUE_FILE)
    completions = recent_completions(QUEUE_FILE, QUEUE_ARCHIVE)
    brain = get_brain_stats()
    episodes = get_episode_stats()
    mode = get_mode()

    phi = get_phi_payload()
    bloat = get_bloat_score(pi_raw)

    payload = {
        "mode": mode,
        "queue": queue,
        "benchmarks": {
            "clr": get_clr_payload(clr_raw) if clr_raw else None,
            "pi": get_pi_payload(pi_raw) if pi_raw else None,
        },
        "phi": phi,
        "bloat_score": bloat,
        "brain": brain,
        "episodes": episodes,
        "uptime_since": get_uptime(),
        "recent_completions": completions,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return payload


def main():
    payload = generate()
    content = json.dumps(payload, indent=2)

    # Write to both output locations
    for out_dir in [DOCS_DIR, WEBSITE_STATIC]:
        if out_dir.exists():
            out = out_dir / "status.json"
            out.write_text(content)
            print(f"Wrote {out}")

    # Summary
    ep = payload.get("episodes", {})
    brain = payload.get("brain", {})
    print(f"Brain: {brain.get('total_memories', '?')} memories, "
          f"Episodes: {ep.get('total', '?')} ({ep.get('success_rate', '?')} success rate)")


if __name__ == "__main__":
    main()
