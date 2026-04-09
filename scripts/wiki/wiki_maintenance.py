#!/usr/bin/env python3
"""Wiki autonomous maintenance — lightweight jobs for cron/heartbeat.

Jobs:
  lint       — Run wiki lint, write results to logs/lint-log.md
  drift      — Detect wiki drift: stale pages, uncompiled sources, broken links
  promote    — Promote recent high-value research into the knowledge layer
  full       — Run all jobs sequentially

Usage:
    python3 wiki_maintenance.py lint
    python3 wiki_maintenance.py drift
    python3 wiki_maintenance.py promote [--limit 5] [--dry-run]
    python3 wiki_maintenance.py full [--dry-run]

Exit codes:
    0 = OK (or warnings only)
    1 = Errors found requiring attention
    2 = Script/import failure
"""

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"))
KNOWLEDGE = WORKSPACE / "knowledge"
WIKI_DIR = KNOWLEDGE / "wiki"
RAW_DIR = KNOWLEDGE / "raw"
LOGS_DIR = KNOWLEDGE / "logs"
SOURCES_JSONL = LOGS_DIR / "sources.jsonl"
RESEARCH_DIR = WORKSPACE / "memory" / "research"
RESEARCH_INGESTED = RESEARCH_DIR / "ingested"
LINT_LOG = LOGS_DIR / "lint-log.md"
MAINTENANCE_LOG = LOGS_DIR / "maintenance.log"

TODAY = datetime.date.today().isoformat()
NOW = datetime.datetime.now().isoformat(timespec="seconds")

sys.path.insert(0, str(Path(__file__).resolve().parent))


def log(msg: str):
    """Append to maintenance log and print."""
    print(msg)
    with open(MAINTENANCE_LOG, "a") as f:
        f.write(f"[{NOW}] {msg}\n")


# ── Lint Job ──────────────────────────────────────────────────

def job_lint() -> dict:
    """Run wiki lint and return summary."""
    try:
        from wiki_lint import run_lint
        issues = run_lint()  # returns list of LintIssue objects
        total_issues = len(issues)
        errors = sum(1 for i in issues if getattr(i, "severity", "warning") == "error")
        warnings = total_issues - errors

        log(f"LINT: {total_issues} issues ({errors} errors, {warnings} warnings)")

        # Group by check name
        by_check: dict[str, list] = {}
        for issue in issues:
            check = getattr(issue, "check", "unknown")
            by_check.setdefault(check, []).append(issue)

        # Write lint summary to log
        with open(LINT_LOG, "w") as f:
            f.write(f"# Wiki Lint Report\n\n_Generated {NOW}_\n\n")
            for check, check_issues in sorted(by_check.items()):
                f.write(f"## {check} ({len(check_issues)})\n\n")
                for issue in check_issues[:20]:
                    page = getattr(issue, "page", "")
                    msg = getattr(issue, "message", str(issue))
                    f.write(f"- `{page}`: {msg}\n")
                if len(check_issues) > 20:
                    f.write(f"- _...and {len(check_issues) - 20} more_\n")
                f.write("\n")
            if total_issues == 0:
                f.write("All checks passed.\n")

        return {"lint_issues": total_issues, "errors": errors, "warnings": warnings}
    except Exception as e:
        log(f"LINT ERROR: {e}")
        return {"lint_issues": -1, "error": str(e)}


# ── Drift Detection ──────────────────────────────────────────

def job_drift() -> dict:
    """Detect wiki drift: stale pages, uncompiled sources, orphan raw files."""
    drift = {"stale_pages": [], "uncompiled_sources": [], "thin_pages": []}

    # 1. Stale pages (not updated in 90+ days)
    for section_dir in WIKI_DIR.iterdir():
        if not section_dir.is_dir() or section_dir.name in ("indexes",):
            continue
        for page in section_dir.glob("*.md"):
            if page.name == "index.md":
                continue
            text = page.read_text(errors="replace")
            match = re.search(r"^updated:\s*(\d{4}-\d{2}-\d{2})", text, re.MULTILINE)
            if match:
                try:
                    updated = datetime.date.fromisoformat(match.group(1))
                    age_days = (datetime.date.today() - updated).days
                    if age_days > 90:
                        drift["stale_pages"].append(f"{page.relative_to(KNOWLEDGE)} ({age_days}d)")
                except ValueError:
                    pass

    # 2. Uncompiled sources (in registry but no wiki page links to them)
    if SOURCES_JSONL.exists():
        registry = []
        with open(SOURCES_JSONL) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        registry.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        # Collect all sources referenced in wiki pages
        referenced_sources = set()
        for section_dir in WIKI_DIR.iterdir():
            if not section_dir.is_dir():
                continue
            for page in section_dir.glob("*.md"):
                text = page.read_text(errors="replace")
                # Match raw/ paths in sources: frontmatter
                for m in re.finditer(r"raw/\S+\.md", text):
                    referenced_sources.add(m.group(0))

        for entry in registry:
            src_path = entry.get("raw_path", "")
            status = entry.get("status", "")
            if status == "ingested" and src_path:
                rel = src_path.replace(str(KNOWLEDGE) + "/", "")
                if rel not in referenced_sources:
                    drift["uncompiled_sources"].append(rel)

    # 3. Thin pages (body < 200 chars)
    for section_dir in WIKI_DIR.iterdir():
        if not section_dir.is_dir() or section_dir.name in ("indexes",):
            continue
        for page in section_dir.glob("*.md"):
            if page.name == "index.md":
                continue
            text = page.read_text(errors="replace")
            # Strip frontmatter
            body = re.sub(r"^---.*?---\s*", "", text, count=1, flags=re.DOTALL)
            if len(body.strip()) < 200:
                drift["thin_pages"].append(str(page.relative_to(KNOWLEDGE)))

    total = sum(len(v) for v in drift.values())
    log(f"DRIFT: {len(drift['stale_pages'])} stale, {len(drift['uncompiled_sources'])} uncompiled, {len(drift['thin_pages'])} thin — {total} total")

    for category, items in drift.items():
        if items:
            log(f"  {category}: {', '.join(items[:5])}")

    return drift


# ── Source Type Detection ─────────────────────────────────────

def _detect_source_type(filepath: Path) -> str:
    """Detect wiki source type from file content heuristics.

    Returns one of: paper, web, repo, transcript.
    Falls back to 'web' for generic research markdown (not 'paper').
    """
    try:
        text = filepath.read_text(errors="replace")[:3000]
    except OSError:
        return "web"
    text_lower = text.lower()

    # Paper signals: arxiv, DOI, abstract section, citation-heavy
    paper_signals = (
        "arxiv" in text_lower,
        "doi:" in text_lower or "doi.org" in text_lower,
        re.search(r"^##?\s*abstract\b", text, re.MULTILINE | re.IGNORECASE) is not None,
        text_lower.count("et al") >= 2,
        re.search(r"\[\d+\]", text) is not None and text.count("[") > 5,
    )
    if sum(paper_signals) >= 2:
        return "paper"

    # Repo signals: code blocks, file paths, imports
    repo_signals = (
        text.count("```") >= 4,
        re.search(r"(import |from .+ import |require\(|#include)", text) is not None,
        re.search(r"(README|setup\.py|package\.json|Cargo\.toml)", text) is not None,
    )
    if sum(repo_signals) >= 2:
        return "repo"

    # Transcript signals: speaker labels, timestamps
    transcript_signals = (
        re.search(r"^\[?\d{1,2}:\d{2}", text, re.MULTILINE) is not None,
        re.search(r"^(Speaker|Host|Guest|Q:|A:)\s", text, re.MULTILINE) is not None,
    )
    if sum(transcript_signals) >= 1:
        return "transcript"

    # Default: generic research/web content
    return "web"


# ── Research Promotion ────────────────────────────────────────

def job_promote(limit: int = 5, dry_run: bool = False) -> dict:
    """Promote recent high-value research notes into wiki raw layer."""
    promoted = []
    skipped = 0

    # Collect already-known source hashes
    known_hashes = set()
    if SOURCES_JSONL.exists():
        with open(SOURCES_JSONL) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        known_hashes.add(entry.get("checksum_sha256", ""))
                        # Also track by raw path
                        known_hashes.add(entry.get("raw_path", ""))
                    except json.JSONDecodeError:
                        continue

    # Scan research/ingested for recent, high-value candidates
    candidates = []
    for src_dir in [RESEARCH_INGESTED, RESEARCH_DIR]:
        if not src_dir.exists():
            continue
        for f in src_dir.glob("*.md"):
            if f.name.startswith(".") or f.name == "index.md":
                continue
            # Skip if already in registry (by path)
            if str(f) in known_hashes:
                skipped += 1
                continue
            text = f.read_text(errors="replace")
            if len(text) < 500:
                continue
            # Skip test/crawl artifacts
            if re.search(r"(example\.com|httpbin\.org|test-crawl)", text, re.I):
                continue
            mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime)
            age_days = (datetime.datetime.now() - mtime).days
            # Prefer recent files (within 14 days)
            if age_days > 14:
                continue
            candidates.append((f, age_days, len(text)))

    # Sort by recency, then size
    candidates.sort(key=lambda x: (x[1], -x[2]))

    for f, age, size in candidates[:limit]:
        # Detect source type from content instead of assuming paper
        source_type = _detect_source_type(f)

        if dry_run:
            log(f"  WOULD PROMOTE: {f.name} ({age}d old, {size} chars, type={source_type})")
            promoted.append(f.name)
        else:
            # Delegate to wiki_ingest
            try:
                import subprocess
                result = subprocess.run(
                    [sys.executable, str(WORKSPACE / "scripts" / "wiki" / "wiki_ingest.py"),
                     "file", str(f), "--type", source_type],
                    capture_output=True, text=True, timeout=60
                )
                if result.returncode == 0:
                    log(f"  PROMOTED: {f.name}")
                    promoted.append(f.name)
                else:
                    log(f"  FAILED: {f.name}: {result.stderr[:200]}")
            except Exception as e:
                log(f"  ERROR promoting {f.name}: {e}")

    log(f"PROMOTE: {len(promoted)} promoted, {skipped} already known, {len(candidates)} candidates")
    return {"promoted": promoted, "skipped": skipped, "candidates": len(candidates)}


# ── Full Run ──────────────────────────────────────────────────

def job_full(dry_run: bool = False) -> dict:
    """Run all maintenance jobs."""
    log(f"=== Wiki Maintenance — {NOW} ===")
    results = {}
    results["lint"] = job_lint()
    results["drift"] = job_drift()
    results["promote"] = job_promote(dry_run=dry_run)

    # Rebuild indexes after any changes
    if not dry_run and results["promote"].get("promoted"):
        try:
            import subprocess
            subprocess.run(
                [sys.executable, str(WORKSPACE / "scripts" / "wiki" / "wiki_index.py"), "rebuild"],
                capture_output=True, timeout=60
            )
            log("INDEX: Rebuilt after promotions.")
        except Exception as e:
            log(f"INDEX ERROR: {e}")

    log(f"=== Maintenance complete ===")
    return results


# ── CLI ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Wiki autonomous maintenance")
    parser.add_argument("job", choices=["lint", "drift", "promote", "full"],
                        help="Maintenance job to run")
    parser.add_argument("--limit", type=int, default=5, help="Promotion limit")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    args = parser.parse_args()

    if args.job == "lint":
        result = job_lint()
    elif args.job == "drift":
        result = job_drift()
    elif args.job == "promote":
        result = job_promote(limit=args.limit, dry_run=args.dry_run)
    elif args.job == "full":
        result = job_full(dry_run=args.dry_run)

    # Exit 1 if lint found errors
    if args.job in ("lint", "full"):
        lint_result = result if args.job == "lint" else result.get("lint", {})
        if lint_result.get("errors", 0) > 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
