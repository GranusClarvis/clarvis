#!/usr/bin/env python3
"""
External Challenge Feed — inject novel external challenges into the evolution loop.

Sources:
  1. Curated challenge set (seed/challenge_feed.json) — coding, reasoning, benchmark tasks
  2. GitHub issues labeled 'challenge' from GranusClarvis/clarvis (when gh CLI available)

The evolution loop calls `inject` to add one fresh challenge to QUEUE.md under
"### External Challenges". Each challenge is used at most once (tracked via completed set).

Usage:
    python3 external_challenge_feed.py inject       # Add one challenge to QUEUE.md
    python3 external_challenge_feed.py list          # Show available challenges
    python3 external_challenge_feed.py status        # Show feed status / stats
    python3 external_challenge_feed.py refresh-gh    # Refresh GitHub issues cache
"""

import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent.parent
DATA_DIR = WORKSPACE / "data"
SEED_DIR = WORKSPACE / "seed"
FEED_FILE = SEED_DIR / "challenge_feed.json"
STATE_FILE = DATA_DIR / "challenge_feed_state.json"
QUEUE_FILE = WORKSPACE / "memory" / "evolution" / "QUEUE.md"
GH_CACHE_FILE = DATA_DIR / "challenge_feed_gh_cache.json"

# Maximum challenges to inject per day (prevent flooding)
MAX_PER_DAY = 2
# Minimum hours between injections
MIN_INTERVAL_HOURS = 8


def _load_feed():
    """Load the curated challenge feed."""
    if not FEED_FILE.exists():
        return {"challenges": [], "version": "1.0"}
    with open(FEED_FILE) as f:
        return json.load(f)


def _load_state():
    """Load injection state (completed, timestamps)."""
    if not STATE_FILE.exists():
        return {"completed": [], "injections": [], "gh_last_refresh": None}
    with open(STATE_FILE) as f:
        return json.load(f)


def _save_state(state):
    """Save injection state atomically."""
    tmp = str(STATE_FILE) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.rename(tmp, str(STATE_FILE))


def _fetch_github_challenges():
    """Fetch open issues labeled 'challenge' from GranusClarvis/clarvis."""
    try:
        result = subprocess.run(
            ["gh", "issue", "list", "--repo", "GranusClarvis/clarvis",
             "--label", "challenge", "--state", "open", "--json",
             "number,title,body", "--limit", "20"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return []
        issues = json.loads(result.stdout)
        challenges = []
        for issue in issues:
            body = (issue.get("body") or "")[:500]
            challenges.append({
                "id": f"gh-issue-{issue['number']}",
                "title": issue["title"],
                "description": body,
                "source": "github",
                "category": "external",
                "difficulty": "unknown",
                "tags": ["github-issue"],
            })
        return challenges
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        return []


def _get_available_challenges(feed, state):
    """Return challenges not yet completed."""
    completed_ids = set(state.get("completed", []))
    available = [c for c in feed.get("challenges", []) if c["id"] not in completed_ids]
    return available


def _can_inject(state):
    """Check rate limiting: max N per day, min interval between injections."""
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    injections = state.get("injections", [])

    # Count today's injections
    today_count = sum(1 for inj in injections if inj.get("date", "").startswith(today))
    if today_count >= MAX_PER_DAY:
        return False, f"Already injected {today_count}/{MAX_PER_DAY} today"

    # Check minimum interval
    if injections:
        last_ts = injections[-1].get("timestamp", 0)
        hours_since = (time.time() - last_ts) / 3600
        if hours_since < MIN_INTERVAL_HOURS:
            return False, f"Only {hours_since:.1f}h since last injection (min {MIN_INTERVAL_HOURS}h)"

    return True, "ok"


def _select_challenge(available):
    """Select one challenge, preferring diverse categories and higher difficulty."""
    if not available:
        return None

    # Weight by category diversity — prefer categories with fewer completions
    # Simple: pick randomly with slight preference for harder challenges
    weights = []
    for c in available:
        w = 1.0
        diff = c.get("difficulty", "medium")
        if diff == "hard":
            w = 1.5
        elif diff == "easy":
            w = 0.7
        # Boost external sources (GitHub issues are more novel)
        if c.get("source") == "github":
            w *= 1.3
        weights.append(w)

    total = sum(weights)
    weights = [w / total for w in weights]

    # Weighted random selection
    r = random.random()
    cumulative = 0
    for i, w in enumerate(weights):
        cumulative += w
        if r <= cumulative:
            return available[i]
    return available[-1]


def _inject_to_queue(challenge):
    """Add a challenge task to QUEUE.md under 'External Challenges' in NEW ITEMS."""
    queue_text = QUEUE_FILE.read_text()

    # Format the task line
    task_line = (
        f"- [ ] [EXTERNAL_CHALLENGE:{challenge['id']}] "
        f"{challenge['title']}"
    )
    if challenge.get("description"):
        # Truncate description for queue readability
        desc = challenge["description"][:200].replace("\n", " ").strip()
        task_line += f" — {desc}"

    # Find insertion point: after "### External Challenges" or create it under NEW ITEMS
    section_header = "### External Challenges"
    if section_header in queue_text:
        # Insert after the header
        idx = queue_text.index(section_header)
        end_of_header = queue_text.index("\n", idx) + 1
        queue_text = queue_text[:end_of_header] + "\n" + task_line + "\n" + queue_text[end_of_header:]
    elif "## NEW ITEMS" in queue_text:
        # Create section under NEW ITEMS
        idx = queue_text.index("## NEW ITEMS")
        end_of_header = queue_text.index("\n", idx) + 1
        queue_text = (
            queue_text[:end_of_header] + "\n"
            + section_header + "\n\n"
            + task_line + "\n"
            + queue_text[end_of_header:]
        )
    else:
        # Append at end
        queue_text = queue_text.rstrip() + "\n\n" + section_header + "\n\n" + task_line + "\n"

    QUEUE_FILE.write_text(queue_text)
    return task_line


def inject():
    """Main entry: inject one external challenge into the queue."""
    state = _load_state()

    # Rate limit check
    can, reason = _can_inject(state)
    if not can:
        print(f"SKIP: {reason}")
        return False

    feed = _load_feed()

    # Merge GitHub challenges if cache exists and is fresh
    if GH_CACHE_FILE.exists():
        try:
            with open(GH_CACHE_FILE) as f:
                gh_data = json.load(f)
            gh_challenges = gh_data.get("challenges", [])
            # Merge without duplicates
            existing_ids = {c["id"] for c in feed.get("challenges", [])}
            for ghc in gh_challenges:
                if ghc["id"] not in existing_ids:
                    feed.setdefault("challenges", []).append(ghc)
        except (json.JSONDecodeError, KeyError):
            pass

    available = _get_available_challenges(feed, state)
    if not available:
        print("SKIP: No available challenges (all completed or feed empty)")
        return False

    challenge = _select_challenge(available)
    if not challenge:
        print("SKIP: Could not select a challenge")
        return False

    task_line = _inject_to_queue(challenge)

    # Update state
    now = datetime.now(timezone.utc)
    state["completed"].append(challenge["id"])
    state.setdefault("injections", []).append({
        "id": challenge["id"],
        "title": challenge["title"],
        "timestamp": time.time(),
        "date": now.strftime("%Y-%m-%dT%H:%M:%S"),
    })
    _save_state(state)

    remaining = len(_get_available_challenges(feed, state))
    print(f"INJECTED: {challenge['title']} (id={challenge['id']}, {remaining} remaining)")
    print(f"QUEUE LINE: {task_line}")
    return True


def refresh_gh():
    """Refresh GitHub issues cache."""
    challenges = _fetch_github_challenges()
    cache = {
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "challenges": challenges,
    }
    with open(GH_CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)
    print(f"Cached {len(challenges)} GitHub challenges")


def list_challenges():
    """Show available challenges."""
    feed = _load_feed()
    state = _load_state()
    available = _get_available_challenges(feed, state)
    completed = set(state.get("completed", []))

    print(f"=== External Challenge Feed ===")
    print(f"Total: {len(feed.get('challenges', []))}, Available: {len(available)}, Completed: {len(completed)}")
    print()
    for c in feed.get("challenges", []):
        status = "[x]" if c["id"] in completed else "[ ]"
        print(f"  {status} [{c.get('category','?')}] {c['title']} (id={c['id']}, diff={c.get('difficulty','?')})")


def status():
    """Show feed status."""
    feed = _load_feed()
    state = _load_state()
    available = _get_available_challenges(feed, state)
    injections = state.get("injections", [])

    print(f"Feed: {len(feed.get('challenges', []))} challenges")
    print(f"Available: {len(available)}")
    print(f"Completed: {len(state.get('completed', []))}")
    print(f"Total injections: {len(injections)}")

    can, reason = _can_inject(state)
    print(f"Can inject now: {can} ({reason})")

    if injections:
        last = injections[-1]
        print(f"Last injection: {last.get('title', '?')} at {last.get('date', '?')}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "inject":
        inject()
    elif cmd == "list":
        list_challenges()
    elif cmd == "status":
        status()
    elif cmd == "refresh-gh":
        refresh_gh()
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: external_challenge_feed.py inject|list|status|refresh-gh")
        sys.exit(1)
