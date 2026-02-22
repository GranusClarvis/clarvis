#!/usr/bin/env python3
"""
Failure Amplifier — Surface soft failures that hide inside "successful" tasks.

Scans autonomous.log and reasoning chains for signals like:
  - Duplicate task executions (same task ran >1 time)
  - Long durations suggesting struggle (>5 min)
  - Skipped procedural learning (output too vague to extract steps)
  - Retroactive bug fixes (Fix X — means X was silently broken before)
  - Prediction tracking misses ("No unresolved prediction found")
  - Low capability scores mentioned in output
  - Single-step reasoning chains (no real reasoning captured)
  - Low-confidence predictions (hedging, <60% confidence)
  - Uncompleted tasks (EXECUTING without matching COMPLETED)

Encodes these as negative-valence episodes so episodic_memory.py synthesize()
can detect patterns and generate corrective goals.
"""

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brain import brain

AUTONOMOUS_LOG = Path("/home/agent/.openclaw/workspace/memory/cron/autonomous.log")
CHAINS_DIR = Path("/home/agent/.openclaw/workspace/data/reasoning_chains")
EPISODES_FILE = Path("/home/agent/.openclaw/workspace/data/episodes.json")
AMPLIFIER_STATE = Path("/home/agent/.openclaw/workspace/data/failure_amplifier_state.json")


def load_state():
    """Load state to track what we've already amplified."""
    if AMPLIFIER_STATE.exists():
        with open(AMPLIFIER_STATE) as f:
            return json.load(f)
    return {"last_log_offset": 0, "amplified_ids": [], "scanned_chains": []}


def save_state(state):
    AMPLIFIER_STATE.parent.mkdir(parents=True, exist_ok=True)
    with open(AMPLIFIER_STATE, "w") as f:
        json.dump(state, f, indent=2)


def load_episodes():
    if EPISODES_FILE.exists():
        with open(EPISODES_FILE) as f:
            return json.load(f)
    return []


def save_episodes(episodes):
    EPISODES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(EPISODES_FILE, "w") as f:
        json.dump(episodes[-500:], f, indent=2)


def parse_log_entries(log_text):
    """Parse autonomous.log into structured entries.
    Each entry has: timestamp, task, output_lines, completed_at, full log block.
    """
    entries = []
    current = None

    for line in log_text.split("\n"):
        ts_match = re.match(r'\[(\d{4}-\d{2}-\d{2}T[\d:]+)\]\s+(\w+):\s*(.*)', line)
        if ts_match:
            ts_str, event, detail = ts_match.groups()
            if event == "EXECUTING":
                current = {
                    "timestamp": ts_str,
                    "task": detail.strip(),
                    "output_lines": [],
                    "completed_at": None,
                }
            elif event == "COMPLETED" and current:
                current["completed_at"] = ts_str
                entries.append(current)
                current = None
            elif event == "COMPLETED" and not current:
                # Orphaned COMPLETED — task may have started before log window
                pass
            elif current and event in ("PROCEDURAL", "REASONING", "PREDICTION", "SELECTED"):
                current["output_lines"].append(f"{event}: {detail}")
        elif current and line.strip():
            current["output_lines"].append(line.strip())

    # If there's a current task that never completed, track it
    if current:
        entries.append(current)  # Will have completed_at=None

    return entries


def scan_duplicate_tasks(entries):
    """Detect tasks that were executed more than once (first attempt was inadequate)."""
    soft_failures = []
    task_counts = {}
    for e in entries:
        # Normalize: strip line numbers and checkboxes
        clean = re.sub(r'\d+:- \[.\]\s*', '', e["task"])[:120]
        task_counts.setdefault(clean, []).append(e)

    for task_key, occurrences in task_counts.items():
        if len(occurrences) > 1:
            soft_failures.append({
                "type": "duplicate_execution",
                "task": occurrences[0]["task"][:200],
                "detail": f"Task executed {len(occurrences)} times — first attempt was insufficient",
                "severity": 0.5,
                "timestamp": occurrences[0]["timestamp"],
            })
    return soft_failures


def scan_long_durations(entries):
    """Detect tasks that took unusually long (>5 min)."""
    soft_failures = []
    for e in entries:
        if not e.get("completed_at"):
            continue
        try:
            start = datetime.fromisoformat(e["timestamp"])
            end = datetime.fromisoformat(e["completed_at"])
            duration = (end - start).total_seconds()
            if duration > 300:
                soft_failures.append({
                    "type": "long_duration",
                    "task": e["task"][:200],
                    "detail": f"Task took {duration:.0f}s (>300s threshold) — may indicate struggle",
                    "severity": min(0.7, 0.3 + (duration - 300) / 600),
                    "timestamp": e["timestamp"],
                })
        except (ValueError, TypeError):
            continue
    return soft_failures


def scan_skipped_learning(entries):
    """Detect tasks where procedural learning was skipped."""
    soft_failures = []
    for e in entries:
        output = "\n".join(e.get("output_lines", []))
        if "Skipped learning" in output:
            soft_failures.append({
                "type": "skipped_learning",
                "task": e["task"][:200],
                "detail": "Procedural learning skipped — output too vague to extract concrete steps",
                "severity": 0.3,
                "timestamp": e["timestamp"],
            })
    return soft_failures


def scan_prediction_misses(entries):
    """Detect prediction tracking failures."""
    soft_failures = []
    for e in entries:
        output = "\n".join(e.get("output_lines", []))
        if "No unresolved prediction found" in output:
            soft_failures.append({
                "type": "prediction_miss",
                "task": e["task"][:200],
                "detail": "Prediction outcome not recorded — tracking gap",
                "severity": 0.4,
                "timestamp": e["timestamp"],
            })
    return soft_failures


def scan_retroactive_fixes(entries):
    """Detect tasks that are fixes for silently broken prior work."""
    soft_failures = []
    fix_patterns = [
        r"wrong param",
        r"silently fail",
        r"never used",
        r"bug was in",
        r"threshold.*never",
        r"assessor checked.*instead of",
        r"impossible to meet",
        r"silent",
    ]
    for e in entries:
        task_lower = e["task"].lower()
        output = "\n".join(e.get("output_lines", []))
        combined = (task_lower + " " + output).lower()

        if task_lower.startswith("fix "):
            for pat in fix_patterns:
                if re.search(pat, combined):
                    soft_failures.append({
                        "type": "retroactive_fix",
                        "task": e["task"][:200],
                        "detail": f"Fix reveals prior silent failure (pattern: {pat})",
                        "severity": 0.6,
                        "timestamp": e["timestamp"],
                    })
                    break
    return soft_failures


def scan_reasoning_chains(already_scanned=None):
    """Detect reasoning chains with minimal structure (single-step = no real reasoning).
    Only scans chains not already processed."""
    soft_failures = []
    if not CHAINS_DIR.exists():
        return soft_failures, []

    already_scanned = set(already_scanned or [])
    newly_scanned = []

    for chain_file in sorted(CHAINS_DIR.glob("chain_*.json")):
        fname = chain_file.name
        if fname in already_scanned:
            continue
        newly_scanned.append(fname)

        try:
            with open(chain_file) as f:
                chain = json.load(f)
            title = chain.get("title", "")
            if "test" in title.lower() or "verify" in title.lower():
                continue
            steps = chain.get("steps", [])
            if len(steps) <= 1:
                soft_failures.append({
                    "type": "shallow_reasoning",
                    "task": title[:200],
                    "detail": f"Reasoning chain has only {len(steps)} step(s) — no real multi-step reasoning captured",
                    "severity": 0.35,
                    "timestamp": chain.get("created", ""),
                })
        except (json.JSONDecodeError, IOError):
            continue

    return soft_failures, newly_scanned


def scan_low_capability_scores(entries):
    """Detect mentions of low capability scores in task output.
    Associates the score with the correct task rather than grabbing random fragments."""
    soft_failures = []
    score_pattern = re.compile(
        r'(?:score|capability|Phi|hit.rate)\D{0,20}(\d+\.\d+)',
        re.IGNORECASE
    )

    for e in entries:
        output = "\n".join(e.get("output_lines", []))
        combined = e["task"] + " " + output

        seen_scores = set()
        for match in score_pattern.finditer(combined):
            score = float(match.group(1))
            score_key = f"{score:.2f}"
            if score < 0.5 and score > 0.0 and score_key not in seen_scores:
                seen_scores.add(score_key)
                soft_failures.append({
                    "type": "low_capability",
                    "task": e["task"][:200],
                    "detail": f"Low score detected: {score:.2f} — indicates capability gap",
                    "severity": min(0.7, 0.8 - score),
                    "timestamp": e.get("timestamp", ""),
                })

    # Deduplicate by task + score detail
    seen = set()
    unique = []
    for sf in soft_failures:
        key = (sf["task"][:80], sf["detail"])
        if key not in seen:
            seen.add(key)
            unique.append(sf)
    return unique


def scan_low_confidence_predictions(entries):
    """Detect predictions with very low confidence (<60%), suggesting hedging or uncertainty."""
    soft_failures = []
    conf_pattern = re.compile(r'@ (\d+)% confidence')

    for e in entries:
        output = "\n".join(e.get("output_lines", []))
        for match in conf_pattern.finditer(output):
            confidence = int(match.group(1))
            if confidence < 60:
                soft_failures.append({
                    "type": "low_confidence",
                    "task": e["task"][:200],
                    "detail": f"Prediction at only {confidence}% confidence — low self-trust",
                    "severity": min(0.6, 0.3 + (60 - confidence) / 100),
                    "timestamp": e.get("timestamp", ""),
                })
    return soft_failures


def scan_uncompleted_tasks(entries):
    """Detect tasks that started (EXECUTING) but never got a COMPLETED line.
    Could indicate timeout, crash, or manual abort."""
    soft_failures = []
    for e in entries:
        if e.get("completed_at") is None:
            soft_failures.append({
                "type": "uncompleted_task",
                "task": e["task"][:200],
                "detail": "Task started but never completed — possible timeout or crash",
                "severity": 0.6,
                "timestamp": e.get("timestamp", ""),
            })
    return soft_failures


def make_episode_id(sf_type, task_prefix):
    """Create a deterministic episode ID for deduplication.
    Uses type + task fingerprint so the same soft failure is never re-encoded."""
    fingerprint = f"{sf_type}_{task_prefix[:60]}"
    digest = hashlib.md5(fingerprint.encode()).hexdigest()[:8]
    return f"ep_soft_{digest}"


def encode_soft_failure(sf, existing_ids):
    """Convert a soft failure dict into an episode with negative valence."""
    now = datetime.now(timezone.utc)

    ep_id = make_episode_id(sf["type"], sf["task"])
    if ep_id in existing_ids:
        return None  # Already amplified

    # Valence: higher = more emotionally significant (like real failures)
    valence = min(1.0, 0.5 + sf["severity"] * 0.4)

    episode = {
        "id": ep_id,
        "timestamp": now.isoformat(),
        "task": sf["task"][:200],
        "section": "SOFT_FAIL",
        "salience": round(sf["severity"], 4),
        "outcome": "soft_failure",
        "valence": round(valence, 4),
        "duration_s": 0,
        "error": f"[{sf['type']}] {sf['detail'][:180]}",
        "steps": None,
        "access_times": [now.timestamp()],
        "activation": 1.0,
    }
    return episode


def amplify():
    """Main entry point: scan for soft failures and encode them as episodes."""
    state = load_state()
    episodes = load_episodes()
    existing_ids = {ep["id"] for ep in episodes}

    if not AUTONOMOUS_LOG.exists():
        print("No autonomous.log found")
        return {"amplified": 0, "scanned": 0}

    log_text = AUTONOMOUS_LOG.read_text()

    # Incremental: only parse new log content if state has offset
    log_offset = state.get("last_log_offset", 0)
    if log_offset > 0 and log_offset < len(log_text):
        # Parse new content, but include some overlap for context
        overlap_start = max(0, log_offset - 500)
        new_log_text = log_text[overlap_start:]
    else:
        new_log_text = log_text

    entries = parse_log_entries(new_log_text)

    # Run all scanners
    all_soft_failures = []
    all_soft_failures.extend(scan_duplicate_tasks(entries))
    all_soft_failures.extend(scan_long_durations(entries))
    all_soft_failures.extend(scan_skipped_learning(entries))
    all_soft_failures.extend(scan_prediction_misses(entries))
    all_soft_failures.extend(scan_retroactive_fixes(entries))
    all_soft_failures.extend(scan_low_capability_scores(entries))
    all_soft_failures.extend(scan_low_confidence_predictions(entries))
    all_soft_failures.extend(scan_uncompleted_tasks(entries))

    # Reasoning chains: only scan new ones
    chain_failures, newly_scanned_chains = scan_reasoning_chains(
        state.get("scanned_chains", [])
    )
    all_soft_failures.extend(chain_failures)

    # Encode as episodes (with dedup)
    new_episodes = []
    for sf in all_soft_failures:
        ep = encode_soft_failure(sf, existing_ids | {e["id"] for e in new_episodes})
        if ep:
            new_episodes.append(ep)
            # Also store in brain for searchable access
            importance = min(1.0, 0.5 + ep["valence"] * 0.3)
            brain.store(
                f"Soft failure: {ep['task'][:100]} — {sf['detail'][:100]}",
                collection="clarvis-episodes",
                importance=importance,
                tags=["episode", "soft_failure", sf["type"]],
                source="failure_amplifier",
            )

    if new_episodes:
        episodes.extend(new_episodes)
        save_episodes(episodes)

    # Update state
    state["last_log_offset"] = len(log_text)
    state["amplified_ids"] = list(
        set(state.get("amplified_ids", [])) | {e["id"] for e in new_episodes}
    )[-200:]
    prev_chains = set(state.get("scanned_chains", []))
    state["scanned_chains"] = list(prev_chains | set(newly_scanned_chains))[-200:]
    save_state(state)

    result = {
        "scanned_entries": len(entries),
        "soft_failures_found": len(all_soft_failures),
        "new_episodes_encoded": len(new_episodes),
        "by_type": {},
        "total_episodes_now": len(episodes),
    }

    for sf in all_soft_failures:
        t = sf["type"]
        result["by_type"][t] = result["by_type"].get(t, 0) + 1

    return result


# CLI
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "amplify"

    if cmd == "amplify":
        result = amplify()

        print("=" * 60)
        print("FAILURE AMPLIFIER REPORT")
        print("=" * 60)
        print(f"\nLog entries scanned  : {result['scanned_entries']}")
        print(f"Soft failures found  : {result['soft_failures_found']}")
        print(f"New episodes encoded : {result['new_episodes_encoded']}")
        print(f"Total episodes now   : {result['total_episodes_now']}")

        if result["by_type"]:
            print("\nBreakdown by type:")
            for ftype, count in sorted(result["by_type"].items(), key=lambda x: -x[1]):
                print(f"  {count:2d}x  {ftype}")
        else:
            print("\n  (no new soft failures detected)")

        print(f"\n[JSON] {json.dumps(result)}")

    elif cmd == "scan":
        # Dry run — show what would be amplified without encoding
        if not AUTONOMOUS_LOG.exists():
            print("No autonomous.log found")
            sys.exit(1)

        log_text = AUTONOMOUS_LOG.read_text()
        entries = parse_log_entries(log_text)

        all_sf = []
        all_sf.extend(scan_duplicate_tasks(entries))
        all_sf.extend(scan_long_durations(entries))
        all_sf.extend(scan_skipped_learning(entries))
        all_sf.extend(scan_prediction_misses(entries))
        all_sf.extend(scan_retroactive_fixes(entries))
        all_sf.extend(scan_low_capability_scores(entries))
        all_sf.extend(scan_low_confidence_predictions(entries))
        all_sf.extend(scan_uncompleted_tasks(entries))

        chain_sf, _ = scan_reasoning_chains()
        all_sf.extend(chain_sf)

        print(f"Found {len(all_sf)} soft failures (dry run — not encoding):\n")
        for sf in all_sf:
            print(f"  [{sf['type']:20s}] (sev={sf['severity']:.2f}) {sf['task'][:70]}")
            print(f"    {sf['detail']}")
            print()

    else:
        print("Usage: failure_amplifier.py [amplify|scan]")
        sys.exit(1)
