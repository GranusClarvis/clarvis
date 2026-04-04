"""
Context GC — garbage collection for queue archive and log rotation.

Migrated from scripts/context_compressor.py (archive_completed, rotate_logs, gc).

Usage:
    from clarvis.context.gc import gc, archive_completed, rotate_logs
    results = gc()  # archive old tasks + rotate logs
"""

import gzip
import glob
import os
import re
import shutil
from datetime import datetime, timezone, timedelta

WORKSPACE = os.environ.get(
    "CLARVIS_WORKSPACE", os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
)
QUEUE_FILE = os.path.join(WORKSPACE, "memory/evolution/QUEUE.md")
QUEUE_ARCHIVE = os.path.join(WORKSPACE, "memory/evolution/QUEUE_ARCHIVE.md")
MEMORY_DIR = os.path.join(WORKSPACE, "memory")
CRON_LOG_DIR = os.path.join(WORKSPACE, "memory/cron")
LOG_MAX_BYTES = 100_000  # 100KB cap per cron log


def archive_completed(queue_file=None, archive_file=None,
                      keep_days=7, dry_run=False):
    """Move old completed tasks from QUEUE.md to archive file.

    Keeps completed tasks from the last `keep_days` days.
    Returns dict with stats.
    """
    queue_file = queue_file or QUEUE_FILE
    archive_file = archive_file or QUEUE_ARCHIVE

    if not os.path.exists(queue_file):
        return {"error": "QUEUE.md not found"}

    with open(queue_file, 'r') as f:
        content = f.read()
        lines = content.splitlines(keepends=True)

    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    kept_lines = []
    archived_lines = []
    stats = {"archived": 0, "kept_completed": 0, "pending": 0,
             "bytes_before": len(content)}

    for line in lines:
        stripped = line.strip()
        match_done = re.match(r'^- \[x\] (.+)$', stripped)
        if match_done:
            task_text = match_done.group(1)
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', task_text)
            if date_match and date_match.group(1) < cutoff_str:
                archived_lines.append(line)
                stats["archived"] += 1
                continue
            stats["kept_completed"] += 1
            kept_lines.append(line)
            continue

        if re.match(r'^- \[ \] ', stripped):
            stats["pending"] += 1
        kept_lines.append(line)

    new_content = "".join(kept_lines)
    stats["bytes_after"] = len(new_content)
    stats["bytes_saved"] = stats["bytes_before"] - stats["bytes_after"]

    if dry_run:
        return stats

    if archived_lines:
        header = f"\n## Archived {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n"
        with open(archive_file, 'a') as f:
            f.write(header)
            f.writelines(archived_lines)

        try:
            from clarvis.brain import brain
            brain.store(
                f"Archived {stats['archived']} completed tasks from QUEUE.md "
                f"(older than {keep_days} days). Saved {stats['bytes_saved']} bytes.",
                collection="context",
                metadata={"type": "archive_event",
                          "date": datetime.now(timezone.utc).isoformat()},
                importance=0.3
            )
        except Exception:
            pass

        with open(queue_file, 'w') as f:
            f.write(new_content)

    return stats


def rotate_logs(log_dir=None, max_bytes=None, dry_run=False):
    """Rotate oversized cron logs and gzip old daily memory files.

    Returns dict with stats.
    """
    log_dir = log_dir or CRON_LOG_DIR
    max_bytes = max_bytes or LOG_MAX_BYTES
    stats = {"logs_truncated": 0, "logs_bytes_saved": 0, "files_gzipped": 0}

    # Truncate oversized cron logs
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

                nl = tail.find(b'\n')
                if nl >= 0:
                    tail = tail[nl + 1:]

                marker = (
                    f"[TRUNCATED {datetime.now(timezone.utc).strftime('%Y-%m-%d')}] "
                    "Older entries archived to save context window space\n"
                ).encode()
                with open(logfile, 'wb') as f:
                    f.write(marker)
                    f.write(tail)

                saved = size - os.path.getsize(logfile)
                stats["logs_truncated"] += 1
                stats["logs_bytes_saved"] += saved

    # Gzip old daily memory files
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    for md_file in glob.glob(os.path.join(MEMORY_DIR, "2???-*.md")):
        basename = os.path.basename(md_file)
        date_match = re.match(r'(\d{4}-\d{2}-\d{2})\.md$', basename)
        if not date_match:
            continue
        if date_match.group(1) >= cutoff_str:
            continue

        gz_path = md_file + ".gz"
        if os.path.exists(gz_path):
            continue

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
    results["total_bytes_saved"] = (
        results["archive"].get("bytes_saved", 0)
        + results["logs"].get("logs_bytes_saved", 0)
    )
    results["total_tokens_saved_est"] = results["total_bytes_saved"] // 4
    return results
