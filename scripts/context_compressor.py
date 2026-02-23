#!/usr/bin/env python3
"""
Context Compressor — Summarize old context instead of full history

Reduces token consumption by:
1. compress_queue() — strips completed tasks from QUEUE.md, keeps only pending + last 5 completions
2. compress_health() — summarizes multi-line health data into compact key=value format
3. compress_episodes() — trims episodic recall to essentials (outcome, lesson, not full text)
4. generate_context_brief() — one-shot compressed context for Claude Code prompts

SAVINGS ESTIMATE:
  QUEUE.md: 48KB → ~4KB (85% reduction)
  Health data: ~8KB → ~1KB (87% reduction)
  Per heartbeat: ~15K tokens → ~2K tokens saved

Usage:
    from context_compressor import compress_queue, compress_health, generate_context_brief

    # CLI
    python3 context_compressor.py queue          # compressed queue
    python3 context_compressor.py health         # compressed health summary
    python3 context_compressor.py brief          # full context brief for prompts
    python3 context_compressor.py brief --file   # write to data/context_brief.txt
"""

import gzip
import glob
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(__file__))

QUEUE_FILE = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md"
QUEUE_ARCHIVE = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE_ARCHIVE.md"
BRIEF_FILE = "/home/agent/.openclaw/workspace/data/context_brief.txt"
CAPABILITY_HISTORY = "/home/agent/.openclaw/workspace/data/capability_history.json"
PHI_HISTORY = "/home/agent/.openclaw/workspace/data/phi_history.json"
MEMORY_DIR = "/home/agent/.openclaw/workspace/memory"
CRON_LOG_DIR = "/home/agent/.openclaw/workspace/memory/cron"
LOG_MAX_BYTES = 100_000  # 100KB cap per cron log


def compress_queue(queue_file=QUEUE_FILE, max_recent_completed=5):
    """Compress QUEUE.md: pending tasks in full, last N completed as 1-liners, rest stripped.

    Returns a string suitable for injection into Claude Code prompts.

    Typical reduction: 48KB → 3-5KB (85-90% token savings).
    """
    if not os.path.exists(queue_file):
        return "No evolution queue found."

    with open(queue_file, 'r') as f:
        lines = f.readlines()

    pending_tasks = []       # [ ] items — keep in full
    recent_completed = []    # [x] items — keep last N as summaries
    current_section = ""
    section_header = ""

    for line in lines:
        stripped = line.strip()

        # Track section headers
        if stripped.startswith('## '):
            current_section = stripped
            section_header = stripped
            continue

        # Skip completed section entirely
        if '## Completed' in current_section:
            continue

        # Pending tasks — keep verbatim with section context
        match_pending = re.match(r'^- \[ \] (.+)$', stripped)
        if match_pending:
            task_text = match_pending.group(1)
            # Strip long parenthetical timestamps/details for compression
            # Keep up to first ( or — to get the core task
            core = re.split(r'\s*[\(—]', task_text, 1)[0].strip()
            if len(core) < 20:
                core = task_text[:150]  # fallback: keep more if core is too short
            pending_tasks.append({
                "section": current_section,
                "task": core,
            })
            continue

        # Completed tasks — collect for recency trimming
        match_done = re.match(r'^- \[x\] (.+)$', stripped)
        if match_done:
            task_text = match_done.group(1)
            # Try to extract date BEFORE splitting (it's often in the parenthetical)
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', task_text)
            date_str = date_match.group(1) if date_match else "unknown"
            # Extract just the core task name (before timestamp/details)
            core = re.split(r'\s*[\(—]', task_text, 1)[0].strip()
            if len(core) < 15:
                core = task_text[:100]
            recent_completed.append({
                "section": current_section,
                "task": core,
                "date": date_str,
            })

    # Sort completed by date (newest first), "unknown" goes last
    recent_completed.sort(key=lambda x: x["date"] if x["date"] != "unknown" else "0000", reverse=True)
    recent_completed = recent_completed[:max_recent_completed]

    # Build compressed output
    output = []
    output.append("=== EVOLUTION QUEUE (compressed) ===\n")

    # Group pending by section
    pending_by_section = {}
    for t in pending_tasks:
        sec = t["section"]
        if sec not in pending_by_section:
            pending_by_section[sec] = []
        pending_by_section[sec].append(t["task"])

    if pending_by_section:
        output.append(f"PENDING ({len(pending_tasks)} tasks):")
        for section, tasks in pending_by_section.items():
            output.append(f"\n{section}")
            for task in tasks:
                output.append(f"  - [ ] {task}")
    else:
        output.append("PENDING: 0 tasks (queue empty)")

    if recent_completed:
        output.append(f"\nRECENT COMPLETIONS (last {len(recent_completed)}):")
        for t in recent_completed:
            output.append(f"  [x] ({t['date']}) {t['task'][:80]}")

    output.append(f"\nTOTAL: {len(pending_tasks)} pending, {len(recent_completed)} recently completed shown (older history stripped for token efficiency)")

    return "\n".join(output)


def compress_health(
    calibration_output="",
    phi_output="",
    capability_output="",
    retrieval_output="",
    episode_output="",
    goal_output="",
    param_output="",
    domain_output="",
):
    """Compress multi-line health data into compact key=value summary.

    Takes raw stdout from various health scripts and extracts only the
    essential metrics, discarding verbose explanations.

    Typical reduction: 8KB → 1KB (87% token savings).
    """
    summary = []
    summary.append("=== SYSTEM HEALTH (compressed) ===")

    # Extract key numbers from calibration
    if calibration_output:
        brier_match = re.search(r'[Bb]rier[:\s=]*([0-9.]+)', calibration_output)
        accuracy_match = re.search(r'(\d+)/(\d+)\s*correct|accuracy[:\s=]*([0-9.]+)', calibration_output)
        brier = brier_match.group(1) if brier_match else "?"
        if accuracy_match:
            if accuracy_match.group(1):
                accuracy = f"{accuracy_match.group(1)}/{accuracy_match.group(2)}"
            else:
                accuracy = accuracy_match.group(3)
        else:
            accuracy = "?"
        summary.append(f"Calibration: Brier={brier}, accuracy={accuracy}")

    # Extract Phi value
    if phi_output:
        phi_match = re.search(r'[Pp]hi[:\s=]*([0-9.]+)', phi_output)
        trend_match = re.search(r'trend[:\s=]*([a-z_]+|[↑↓→]+)', phi_output, re.IGNORECASE)
        phi_val = phi_match.group(1) if phi_match else "?"
        trend = trend_match.group(1) if trend_match else "stable"
        summary.append(f"Phi={phi_val} (trend: {trend})")

    # Extract capability scores — just the numbers
    if capability_output:
        # Pattern: "domain_name: 0.XX" or "domain: X.XX"
        scores = re.findall(r'(\w[\w_]+)[:=]\s*([0-9.]+)', capability_output)
        if scores:
            # Find lowest
            score_pairs = [(name, float(val)) for name, val in scores if 0 <= float(val) <= 1.0]
            if score_pairs:
                score_pairs.sort(key=lambda x: x[1])
                worst = score_pairs[0]
                avg = sum(v for _, v in score_pairs) / len(score_pairs)
                summary.append(f"Capabilities: avg={avg:.2f}, worst={worst[0]}={worst[1]:.2f}, n={len(score_pairs)}")
                # List all briefly
                scores_str = ", ".join(f"{n}={v:.2f}" for n, v in score_pairs)
                summary.append(f"  Scores: {scores_str}")

    # Extract retrieval health
    if retrieval_output:
        hit_match = re.search(r'hit[_ ]rate[:\s=]*([0-9.]+)%?', retrieval_output, re.IGNORECASE)
        health_match = re.search(r'(HEALTHY|DEGRADED|CRITICAL)', retrieval_output)
        hit = hit_match.group(1) if hit_match else "?"
        health = health_match.group(1) if health_match else "?"
        summary.append(f"Retrieval: hit_rate={hit}%, status={health}")

    # Episode stats — just count and success rate
    if episode_output:
        count_match = re.search(r'(\d+)\s*episodes?', episode_output)
        success_match = re.search(r'success[:\s=]*([0-9.]+)%?', episode_output, re.IGNORECASE)
        count = count_match.group(1) if count_match else "?"
        success = success_match.group(1) if success_match else "?"
        summary.append(f"Episodes: n={count}, success_rate={success}%")

    # Goal tracker — just stalled count
    if goal_output:
        stalled_match = re.search(r'(\d+)\s*stalled', goal_output, re.IGNORECASE)
        tasks_match = re.search(r'(\d+)\s*tasks?\s*(generated|added)', goal_output, re.IGNORECASE)
        stalled = stalled_match.group(1) if stalled_match else "0"
        tasks_gen = tasks_match.group(1) if tasks_match else "0"
        summary.append(f"Goals: {stalled} stalled, {tasks_gen} remediation tasks generated")

    if not any(line for line in summary if not line.startswith("===")):
        summary.append("No health data available this cycle.")

    return "\n".join(summary)


def compress_episodes(similar_episodes_text, failure_episodes_text):
    """Compress episodic memory hints for task prompts.

    Strips verbose episode details, keeps only outcome + key lesson.
    """
    lines = []
    if similar_episodes_text:
        # Each episode line typically has format: [outcome] (act=X.XX) Task: ...
        for line in similar_episodes_text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            # Extract outcome and task name, skip activation details
            outcome_match = re.match(r'\[(\w+)\]\s*\(act=[0-9.]+\)\s*(?:Task:\s*)?(.+)', line)
            if outcome_match:
                outcome = outcome_match.group(1)
                task = outcome_match.group(2)[:80]
                lines.append(f"  [{outcome}] {task}")
            else:
                lines.append(f"  {line[:100]}")

    if failure_episodes_text:
        for line in failure_episodes_text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            # Extract just the error pattern, not full text
            error_match = re.search(r'Error:\s*\[?(\w+)\]?\s*(.+)', line)
            if error_match:
                lines.append(f"  AVOID: [{error_match.group(1)}] {error_match.group(2)[:80]}")
            elif len(line) > 10:
                lines.append(f"  AVOID: {line[:100]}")

    if lines:
        return "EPISODIC HINTS:\n" + "\n".join(lines)
    return ""


def get_latest_scores():
    """Read latest capability scores and Phi from history files.

    Returns compact dict for embedding in prompts without needing
    to re-run assessment scripts.
    """
    scores = {}

    # Capability scores
    if os.path.exists(CAPABILITY_HISTORY):
        try:
            with open(CAPABILITY_HISTORY, 'r') as f:
                history = json.load(f)
            if history:
                latest = history[-1]
                scores["capabilities"] = {
                    k: round(v, 2) for k, v in latest.get("scores", {}).items()
                    if isinstance(v, (int, float))
                }
                scores["capability_avg"] = round(
                    sum(scores["capabilities"].values()) / max(1, len(scores["capabilities"])),
                    2
                )
        except Exception:
            pass

    # Phi
    if os.path.exists(PHI_HISTORY):
        try:
            with open(PHI_HISTORY, 'r') as f:
                phi_hist = json.load(f)
            if phi_hist:
                scores["phi"] = round(phi_hist[-1].get("phi", 0), 3)
        except Exception:
            pass

    return scores


def generate_context_brief(queue_file=QUEUE_FILE):
    """Generate a full compressed context brief for Claude Code prompts.

    Combines compressed queue + latest scores into a single compact payload.
    Designed to replace "Read memory/evolution/QUEUE.md for full context."

    Returns string (~1-3KB instead of ~50KB).
    """
    brief_parts = []

    # Compressed queue
    brief_parts.append(compress_queue(queue_file))

    # Latest scores (from files, no subprocess needed)
    scores = get_latest_scores()
    if scores:
        brief_parts.append("\n=== LATEST METRICS ===")
        if "capabilities" in scores:
            caps = scores["capabilities"]
            worst_k = min(caps, key=caps.get) if caps else "?"
            worst_v = caps.get(worst_k, "?") if caps else "?"
            brief_parts.append(f"Capability avg={scores.get('capability_avg', '?')}, worst={worst_k}={worst_v}")
            brief_parts.append(f"  All: {', '.join(f'{k}={v}' for k, v in sorted(caps.items(), key=lambda x: x[1]))}")
        if "phi" in scores:
            brief_parts.append(f"Phi={scores['phi']}")

    # Current brain stats (lightweight)
    try:
        from brain import brain
        stats = brain.stats()
        brief_parts.append(f"Brain: {stats['total_memories']} memories, {stats['graph_edges']} edges")
    except Exception:
        pass

    return "\n".join(brief_parts)


def archive_completed(queue_file=QUEUE_FILE, archive_file=QUEUE_ARCHIVE,
                      keep_days=7, dry_run=False):
    """Move old completed tasks from QUEUE.md to archive file.

    Keeps completed tasks from the last `keep_days` days in QUEUE.md.
    Older completed tasks are appended to QUEUE_ARCHIVE.md and removed
    from the main file.

    Returns dict with stats: {archived: N, kept: N, pending: N, bytes_saved: N}.
    """
    if not os.path.exists(queue_file):
        return {"error": "QUEUE.md not found"}

    with open(queue_file, 'r') as f:
        content = f.read()
        lines = content.splitlines(keepends=True)

    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    kept_lines = []
    archived_lines = []
    stats = {"archived": 0, "kept_completed": 0, "pending": 0, "bytes_before": len(content)}

    for line in lines:
        stripped = line.strip()

        # Check if this is a completed task
        match_done = re.match(r'^- \[x\] (.+)$', stripped)
        if match_done:
            task_text = match_done.group(1)
            # Extract date
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', task_text)
            if date_match:
                task_date = date_match.group(1)
                if task_date < cutoff_str:
                    # Old completed task — archive it
                    archived_lines.append(line)
                    stats["archived"] += 1
                    continue
            # No date or recent — keep
            stats["kept_completed"] += 1
            kept_lines.append(line)
            continue

        # Pending task — always keep
        if re.match(r'^- \[ \] ', stripped):
            stats["pending"] += 1

        kept_lines.append(line)

    new_content = "".join(kept_lines)
    stats["bytes_after"] = len(new_content)
    stats["bytes_saved"] = stats["bytes_before"] - stats["bytes_after"]

    if dry_run:
        return stats

    if archived_lines:
        # Append to archive file
        header = f"\n## Archived {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n"
        with open(archive_file, 'a') as f:
            f.write(header)
            f.writelines(archived_lines)

        # Store archive summary in brain (if available)
        try:
            from brain import brain
            brain.store(
                f"Archived {stats['archived']} completed tasks from QUEUE.md "
                f"(older than {keep_days} days). Saved {stats['bytes_saved']} bytes.",
                collection="context",
                metadata={"type": "archive_event", "date": datetime.now(timezone.utc).isoformat()},
                importance=0.3
            )
        except Exception:
            pass

        # Rewrite QUEUE.md without archived tasks
        with open(queue_file, 'w') as f:
            f.write(new_content)

    return stats


def rotate_logs(log_dir=CRON_LOG_DIR, max_bytes=LOG_MAX_BYTES, dry_run=False):
    """Rotate oversized cron logs and gzip old daily memory files.

    For cron logs > max_bytes:
      - Keep last max_bytes of content, discard older lines
      - Append a "[TRUNCATED]" marker

    For daily memory files > 7 days old:
      - Gzip them (memory/2026-02-15.md -> memory/2026-02-15.md.gz)

    Returns dict with stats.
    """
    stats = {"logs_truncated": 0, "logs_bytes_saved": 0, "files_gzipped": 0}

    # 1. Truncate oversized cron logs
    if os.path.isdir(log_dir):
        for logfile in glob.glob(os.path.join(log_dir, "*.log")):
            size = os.path.getsize(logfile)
            if size > max_bytes:
                if dry_run:
                    stats["logs_truncated"] += 1
                    stats["logs_bytes_saved"] += size - max_bytes
                    continue

                with open(logfile, 'rb') as f:
                    f.seek(size - max_bytes)
                    tail = f.read()

                # Find first newline to avoid partial line
                nl = tail.find(b'\n')
                if nl >= 0:
                    tail = tail[nl + 1:]

                marker = f"[TRUNCATED {datetime.now(timezone.utc).strftime('%Y-%m-%d')}] Older entries archived to save context window space\n".encode()
                with open(logfile, 'wb') as f:
                    f.write(marker)
                    f.write(tail)

                saved = size - os.path.getsize(logfile)
                stats["logs_truncated"] += 1
                stats["logs_bytes_saved"] += saved

    # 2. Gzip old daily memory files
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    for md_file in glob.glob(os.path.join(MEMORY_DIR, "2026-*.md")):
        basename = os.path.basename(md_file)
        # Extract date from filename (2026-02-15.md)
        date_match = re.match(r'(\d{4}-\d{2}-\d{2})\.md$', basename)
        if not date_match:
            continue
        file_date = date_match.group(1)
        if file_date >= cutoff_str:
            continue  # recent — keep uncompressed

        gz_path = md_file + ".gz"
        if os.path.exists(gz_path):
            continue  # already gzipped

        if dry_run:
            stats["files_gzipped"] += 1
            continue

        with open(md_file, 'rb') as f_in:
            with gzip.open(gz_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(md_file)
        stats["files_gzipped"] += 1

    return stats


def gc(dry_run=False):
    """Run full garbage collection: archive old tasks + rotate logs.

    Designed to run nightly in cron_reflection.sh.
    Returns combined stats dict.
    """
    results = {}
    results["archive"] = archive_completed(dry_run=dry_run)
    results["logs"] = rotate_logs(dry_run=dry_run)

    total_saved = (
        results["archive"].get("bytes_saved", 0)
        + results["logs"].get("logs_bytes_saved", 0)
    )
    results["total_bytes_saved"] = total_saved
    results["total_tokens_saved_est"] = total_saved // 4  # rough estimate

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: context_compressor.py <queue|health|brief|episodes|gc|savings>")
        print("  queue       — compressed evolution queue")
        print("  health      — compressed health summary (reads from stdin or args)")
        print("  brief       — full context brief for prompts")
        print("  brief --file — write brief to data/context_brief.txt")
        print("  episodes    — compress episode text from stdin")
        print("  savings     — estimate token savings")
        print("  gc          — archive old completed tasks + rotate logs")
        print("  gc --dry-run — show what gc would do without doing it")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "queue":
        print(compress_queue())

    elif cmd == "health":
        # Read from stdin if piped, else show empty
        if not sys.stdin.isatty():
            data = sys.stdin.read()
            print(compress_health(capability_output=data))
        else:
            print(compress_health())

    elif cmd == "brief":
        brief = generate_context_brief()
        if "--file" in sys.argv:
            os.makedirs(os.path.dirname(BRIEF_FILE), exist_ok=True)
            with open(BRIEF_FILE, 'w') as f:
                f.write(brief)
            print(f"Written to {BRIEF_FILE} ({len(brief)} bytes)")
        else:
            print(brief)

    elif cmd == "episodes":
        if not sys.stdin.isatty():
            data = sys.stdin.read()
            print(compress_episodes(data, ""))
        else:
            print("Pipe episode text to stdin")

    elif cmd == "gc":
        dry = "--dry-run" in sys.argv
        results = gc(dry_run=dry)
        prefix = "[DRY RUN] " if dry else ""
        arc = results["archive"]
        logs = results["logs"]
        print(f"{prefix}=== Context Window GC ===")
        print(f"{prefix}Archive: {arc.get('archived', 0)} completed tasks moved to QUEUE_ARCHIVE.md "
              f"({arc.get('bytes_saved', 0)} bytes saved), "
              f"{arc.get('kept_completed', 0)} recent kept, {arc.get('pending', 0)} pending")
        print(f"{prefix}Logs: {logs.get('logs_truncated', 0)} logs truncated "
              f"({logs.get('logs_bytes_saved', 0)} bytes saved), "
              f"{logs.get('files_gzipped', 0)} daily files gzipped")
        print(f"{prefix}Total: ~{results['total_tokens_saved_est']} tokens saved")

    elif cmd == "savings":
        # Estimate token savings
        if os.path.exists(QUEUE_FILE):
            with open(QUEUE_FILE, 'r') as f:
                raw = f.read()
            compressed = compress_queue()
            raw_tokens = len(raw) // 4  # rough estimate: 4 chars/token
            comp_tokens = len(compressed) // 4
            savings = raw_tokens - comp_tokens
            pct = (1 - comp_tokens / max(1, raw_tokens)) * 100
            print(f"QUEUE.md token estimate:")
            print(f"  Raw: ~{raw_tokens} tokens ({len(raw)} bytes)")
            print(f"  Compressed: ~{comp_tokens} tokens ({len(compressed)} bytes)")
            print(f"  Savings: ~{savings} tokens/heartbeat ({pct:.0f}% reduction)")
            print(f"  At 48 heartbeats/day: ~{savings * 48} tokens/day saved")
        else:
            print("QUEUE.md not found")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
