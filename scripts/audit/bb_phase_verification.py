#!/usr/bin/env python3
"""bb_phase_verification.py — Weekly BB phase verification pass.

Walks ``memory/evolution/QUEUE_ARCHIVE.md`` for ``[x] [BB_*]`` items archived
in the last N days (default 7), and for each item:

  1. Extracts cited commit hashes (7-40 hex chars) and asserts they exist in
     ``mega-house/workspace``'s git log.
  2. Extracts cited file paths (``apps/...``, ``packages/...``) and asserts
     they exist on disk.
  3. Extracts cited test counts (e.g. "76/76", "web 76/76", "21/21 pass")
     and verifies them with a fresh ``pnpm --filter @bunnybagz/<pkg> test``
     run when ``--run-tests`` is passed (default: skip tests; cite cache).

Outputs a markdown report at
``memory/cron/bb_phase_verification_<YYYY-MM-DD>.md`` mirroring the
2026-05-01 schema. On any drift, appends a ``[BB_<TAG>_REAL]`` reopen task
to ``QUEUE.md`` via ``clarvis.queue.writer.add_task``.

Designed to run from the maintenance window cron (Sunday 04:30 CET) with
``/tmp/clarvis_maintenance.lock``.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

WORKSPACE = Path(os.environ.get(
    "CLARVIS_WORKSPACE",
    os.path.expanduser("~/.openclaw/workspace"),
))
QUEUE_ARCHIVE = WORKSPACE / "memory" / "evolution" / "QUEUE_ARCHIVE.md"
CRON_DIR = WORKSPACE / "memory" / "cron"

MEGA_HOUSE = Path(os.environ.get(
    "BUNNYBAGZ_REPO",
    os.path.expanduser("~/agents/mega-house/workspace"),
))

ARCHIVED_HEADER = re.compile(r"^##\s*Archived\s+(\d{4}-\d{2}-\d{2})\s*$")
BB_LINE = re.compile(r"^- \[x\].*?\[(BB_[A-Z0-9_]+)\]")
COMMIT_HASH = re.compile(r"\b([0-9a-f]{7,40})\b")
FILE_PATH = re.compile(r"`((?:apps|packages)/[A-Za-z0-9_./\-\[\]@]+)`")
TEST_COUNT = re.compile(
    r"(@bunnybagz/(?:web|api|verify|indexer|contracts|chain)|web|api|verify|indexer|contracts|chain)"
    r"(?:\s+(?:suite|tests?|vitest))?"
    r"\s*(?:[:=]\s*)?"
    r"(\d{1,4})\s*/\s*\d{1,4}",
    re.IGNORECASE,
)

PKG_FILTER = {
    "web": "@bunnybagz/web",
    "api": "@bunnybagz/api",
    "verify": "@bunnybagz/verify",
    "indexer": "@bunnybagz/indexer",
    "chain": "@bunnybagz/chain",
    "contracts": "@bunnybagz/contracts",
}


REOPENED_FROM = re.compile(r"\[REOPENED\][^\n]*?from\s*`\[(BB_[A-Z0-9_]+)\]`", re.IGNORECASE)


def _all_archived_tags() -> tuple[set[str], set[str]]:
    """Return (every_archived_tag, set_of_tags_acknowledged_as_reopened).

    A tag is acknowledged if any other archived row references it via
    "[REOPENED] from `[<TAG>]`" — covers cases where the new tag drops
    a suffix like ``_INSTALL``/``_ART`` instead of just appending ``_REAL``.
    """
    if not QUEUE_ARCHIVE.exists():
        return set(), set()
    text = QUEUE_ARCHIVE.read_text()
    archived: set[str] = set()
    for ln in text.splitlines():
        m = BB_LINE.match(ln)
        if m:
            archived.add(m.group(1))
    reopened = set(REOPENED_FROM.findall(text))
    return archived, reopened


def parse_archive(days: int = 7, today: date | None = None) -> list[dict]:
    """Return BB items archived within the last `days`.

    Each item: {task_id, archived_date, raw, commits, files, test_claims,
    has_real_sibling}
    """
    today = today or date.today()
    cutoff = today - timedelta(days=days)
    if not QUEUE_ARCHIVE.exists():
        return []

    all_tags, reopened_tags = _all_archived_tags()
    text = QUEUE_ARCHIVE.read_text()
    items: list[dict] = []
    cur_date: date | None = None
    cur_buf: list[str] = []

    def _flush(d: date | None, buf: list[str]) -> None:
        if d is None or not buf or d < cutoff or d > today:
            return
        # Each `- [x]` starts a new item in the buf
        item_lines: list[str] = []
        for ln in buf:
            if ln.startswith("- [x]") or ln.startswith("- [ ]"):
                if item_lines:
                    _emit(d, item_lines)
                item_lines = [ln]
            elif item_lines and ln.strip():
                item_lines.append(ln)
        if item_lines:
            _emit(d, item_lines)

    def _emit(d: date, item_lines: list[str]) -> None:
        line = " ".join(item_lines)
        m = BB_LINE.match(item_lines[0])
        if not m:
            return
        task_id = m.group(1)
        commits = sorted(set(COMMIT_HASH.findall(line.lower())))
        commits = [c for c in commits if not _looks_like_noise(c)]
        files = sorted(set(FILE_PATH.findall(line)))
        test_claims: dict[str, int] = {}
        for pkg, n in TEST_COUNT.findall(line):
            key = pkg.lower().replace("@bunnybagz/", "")
            if key in PKG_FILTER:
                test_claims[key] = max(test_claims.get(key, 0), int(n))
        has_real_sibling = (
            not task_id.endswith("_REAL")
            and (
                f"{task_id}_REAL" in all_tags
                or task_id in reopened_tags
            )
        )
        items.append({
            "task_id": task_id,
            "archived_date": d.isoformat(),
            "raw": line,
            "commits": commits,
            "files": files,
            "test_claims": test_claims,
            "has_real_sibling": has_real_sibling,
        })

    for ln in text.splitlines():
        h = ARCHIVED_HEADER.match(ln)
        if h:
            _flush(cur_date, cur_buf)
            try:
                cur_date = date.fromisoformat(h.group(1))
            except ValueError:
                cur_date = None
            cur_buf = []
        else:
            cur_buf.append(ln)
    _flush(cur_date, cur_buf)
    return items


def _looks_like_noise(s: str) -> bool:
    """Filter false-positive 'commit' matches (years, all-digit dates)."""
    if s.isdigit():
        return True
    # ISO-date-ish strings of length 7-10 starting with 20 or year
    if len(s) <= 10 and s.startswith("20") and s[:4].isdigit():
        return True
    return False


def verify_commit(repo: Path, commit: str) -> bool:
    if not (repo / ".git").exists():
        return False
    try:
        subprocess.run(
            ["git", "-C", str(repo), "cat-file", "-e", f"{commit}^{{commit}}"],
            check=True, capture_output=True, timeout=10,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def verify_file(repo: Path, rel: str) -> bool:
    p = repo / rel
    return p.exists()


def run_tests(repo: Path, pkg_filter: str, timeout_s: int = 600) -> tuple[int | None, str]:
    """Run pnpm --filter <pkg> test, return (passed_count, raw_tail)."""
    if not (repo / "package.json").exists():
        return None, "no package.json"
    try:
        proc = subprocess.run(
            ["pnpm", "--filter", pkg_filter, "test"],
            cwd=str(repo), capture_output=True, text=True, timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return None, f"timeout after {timeout_s}s"
    except FileNotFoundError:
        return None, "pnpm not on PATH"
    out = proc.stdout + "\n" + proc.stderr
    # vitest summary patterns
    patterns = [
        re.compile(r"Tests\s+(\d+)\s+passed", re.IGNORECASE),
        re.compile(r"(\d+)\s+passed", re.IGNORECASE),
        re.compile(r"#\s*pass\s+(\d+)"),
    ]
    for pat in patterns:
        m = pat.search(out)
        if m:
            return int(m.group(1)), out[-500:]
    return None, out[-500:]


def append_reopen_task(task_id: str, drift_reasons: list[str]) -> bool:
    """Append [BB_<TAG>_REAL] reopen task via clarvis.queue.writer."""
    new_tag = task_id
    if not new_tag.endswith("_REAL"):
        new_tag = f"{task_id}_REAL"
    body = (
        f"**[{new_tag}]** ([REOPENED] from `[{task_id}]` by weekly bb_phase_verification, "
        f"{date.today().isoformat()}). Drift detected: "
        + "; ".join(drift_reasons)
        + ". Re-implement the missing artifacts and re-run tests; cite the new "
        "commit + file paths + test counts in the archive entry. (PROJECT:BUNNYBAGZ)"
    )
    try:
        sys.path.insert(0, str(WORKSPACE))
        from clarvis.queue.writer import add_task  # type: ignore
        return add_task(body, priority="P0", source="audit")
    except Exception as e:
        print(f"[warn] could not append reopen task for {task_id}: {e}", file=sys.stderr)
        return False


def verify_all(items: list[dict], run_tests_flag: bool, repo: Path) -> list[dict]:
    """Verify each item; return rows with verification results."""
    rows: list[dict] = []
    test_cache: dict[str, tuple[int | None, str]] = {}
    for it in items:
        commit_results: dict[str, bool] = {c: verify_commit(repo, c) for c in it["commits"]}
        file_results: dict[str, bool] = {f: verify_file(repo, f) for f in it["files"]}
        test_results: dict[str, dict] = {}
        for pkg, claimed in it["test_claims"].items():
            pkg_filter = PKG_FILTER[pkg]
            if run_tests_flag:
                if pkg_filter not in test_cache:
                    test_cache[pkg_filter] = run_tests(repo, pkg_filter)
                actual, _ = test_cache[pkg_filter]
            else:
                actual = None
            test_results[pkg] = {
                "claimed": claimed,
                "actual": actual,
                "match": (actual is not None and actual >= claimed),
            }

        commit_ok = bool(commit_results) and all(commit_results.values())
        # File drift only when MOST cited paths are missing — a single
        # in-text reference (e.g. "see existing pattern in `apps/web/...`")
        # should not trigger reopen if the bulk of deliverables exist.
        file_present = sum(file_results.values())
        file_total = len(file_results)
        file_drift = file_total > 0 and (file_present / file_total) < 0.5
        commit_drift = bool(it["commits"]) and not commit_ok
        test_drift = run_tests_flag and any(
            (r["actual"] is not None and not r["match"]) for r in test_results.values()
        )
        drift = commit_drift or file_drift or test_drift

        # Skip drift on items with no claims at all (e.g. operator-gated deferrals)
        if not it["commits"] and not it["files"] and not it["test_claims"]:
            drift = False

        # Skip drift on items already acknowledged via a `<TAG>_REAL` reopen.
        if it.get("has_real_sibling"):
            drift = False

        reasons: list[str] = []
        if commit_drift:
            missing = [c for c, ok in commit_results.items() if not ok]
            reasons.append(f"missing commits: {missing}")
        if file_drift:
            missing = [f for f, ok in file_results.items() if not ok]
            reasons.append(
                f"missing files ({file_present}/{file_total}): {missing}"
            )
        if test_drift:
            mismatches = [
                f"{pkg} claimed {r['claimed']} got {r['actual']}"
                for pkg, r in test_results.items()
                if r["actual"] is not None and not r["match"]
            ]
            reasons.append(f"test mismatch: {mismatches}")

        rows.append({
            **it,
            "commit_results": commit_results,
            "file_results": file_results,
            "test_results": test_results,
            "drift": drift,
            "reasons": reasons,
        })
    return rows


def render_report(rows: list[dict], days: int, run_tests_flag: bool, today: date) -> str:
    lines: list[str] = []
    lines.append(f"# BB Phase Verification — {today.isoformat()}")
    lines.append("")
    lines.append(
        f"Weekly verification pass over `[x] [BB_*]` items archived in the last "
        f"{days} days. Tests {'were re-run' if run_tests_flag else 'were not re-run (cache mode)'}."
    )
    lines.append("")
    lines.append(f"Items audited: **{len(rows)}**.")
    lines.append("")
    lines.append("## Verification table")
    lines.append("")
    lines.append("| task_id | archived | commits_ok | files_ok | tests_ok | drift |")
    lines.append("|---|---|---|---|---|---|")
    for r in rows:
        c_ok = (
            f"{sum(r['commit_results'].values())}/{len(r['commit_results'])}"
            if r["commit_results"] else "—"
        )
        f_ok = (
            f"{sum(r['file_results'].values())}/{len(r['file_results'])}"
            if r["file_results"] else "—"
        )
        t_summary = (
            ", ".join(
                f"{pkg}: {x['actual']}/{x['claimed']}"
                for pkg, x in r["test_results"].items()
            ) or "—"
        )
        drift = "**YES**" if r["drift"] else "NO"
        lines.append(
            f"| `{r['task_id']}` | {r['archived_date']} | {c_ok} | {f_ok} | {t_summary} | {drift} |"
        )
    lines.append("")

    drift_rows = [r for r in rows if r["drift"]]
    lines.append("## Drift summary")
    lines.append("")
    lines.append(f"- Drifted items: **{len(drift_rows)} / {len(rows)}**")
    if drift_rows:
        lines.append("")
        for r in drift_rows:
            lines.append(f"### `{r['task_id']}`")
            for reason in r["reasons"]:
                lines.append(f"  - {reason}")
            lines.append("")
    lines.append("")
    lines.append("## Reopen actions")
    lines.append("")
    if not drift_rows:
        lines.append("No drift detected — no reopen tasks appended.")
    else:
        for r in drift_rows:
            lines.append(f"- `[{r['task_id']}_REAL]` queued via `clarvis.queue.writer.add_task`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=7, help="Days back to scan (default 7)")
    p.add_argument("--run-tests", action="store_true", help="Run pnpm tests (slow)")
    p.add_argument("--no-reopen", action="store_true", help="Do not append reopen tasks")
    p.add_argument("--out", type=str, default=None, help="Override output path")
    p.add_argument("--repo", type=str, default=str(MEGA_HOUSE), help="mega-house repo path")
    p.add_argument(
        "--today", type=str, default=None,
        help="Override today's date (YYYY-MM-DD) — for testing",
    )
    args = p.parse_args()

    today = date.fromisoformat(args.today) if args.today else date.today()
    repo = Path(args.repo)

    items = parse_archive(days=args.days, today=today)
    if not items:
        print(f"[bb_phase_verification] no BB items in last {args.days} days; nothing to do")
        # Still write a report so we have a paper trail of the no-op
        rows: list[dict] = []
    else:
        rows = verify_all(items, run_tests_flag=args.run_tests, repo=repo)

    report = render_report(rows, days=args.days, run_tests_flag=args.run_tests, today=today)
    out_path = Path(args.out) if args.out else (
        CRON_DIR / f"bb_phase_verification_{today.isoformat()}.md"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report)
    print(f"[bb_phase_verification] wrote {out_path}")

    drift_rows = [r for r in rows if r["drift"]]
    if drift_rows and not args.no_reopen:
        for r in drift_rows:
            ok = append_reopen_task(r["task_id"], r["reasons"])
            status = "queued" if ok else "skipped"
            print(f"[bb_phase_verification] reopen {r['task_id']}_REAL: {status}")

    print(f"[bb_phase_verification] audited={len(rows)} drifted={len(drift_rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
