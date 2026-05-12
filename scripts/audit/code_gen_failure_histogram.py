#!/usr/bin/env python3
"""Code-Gen Failure Mode Histogram — root-cause classifier for code-gen non-success.

Mirrors `FAILURE_HISTOGRAM_TRUTH_AUDIT` (2026-05-02) but scoped to the
second-weakest capability `code_generation=0.85`. Reads `data/episodes.json`,
filters to the last `--days` (default 30) of code-gen episodes, and classifies
each non-success (`partial_success`/`failure`/`timeout`) into one of 7 buckets:

    lint_fail, type_check_fail, test_fail, compile_fail,
    wrong_file_edited, incomplete_implementation, other

Emits:
    data/audit/code_gen_failures_YYYY-MM-DD.json
    docs/internal/audits/CODE_GEN_FAILURE_HISTOGRAM_YYYY-MM-DD.md

Usage:
    python3 scripts/audit/code_gen_failure_histogram.py            # write outputs
    python3 scripts/audit/code_gen_failure_histogram.py --dry-run  # print only
    python3 scripts/audit/code_gen_failure_histogram.py --days 60  # wider window
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
EPISODES = WORKSPACE / "data" / "episodes.json"
AUDIT_DIR = WORKSPACE / "data" / "audit"
DOCS_DIR = WORKSPACE / "docs" / "internal" / "audits"

# Buckets, in evaluation order (first match wins).
BUCKETS = [
    "lint_fail",
    "type_check_fail",
    "test_fail",
    "compile_fail",
    "wrong_file_edited",
    "incomplete_implementation",
    "other",
]

# Code-gen task signals: tag patterns, lane prefixes, file-edit hints.
CODEGEN_TASK_RE = re.compile(
    r"\b(?:"
    r"BB_|SWO_V[123]?_|\[BB|\[SWO|"
    r"implementation_sprint|code_generation|"
    r"FIX|PATCH|WIRE|REFACTOR|MIGRATE|"
    r"BACKFILL|GUARD|INSTALL|"
    r"_REAL\b|_FIX\b|_KICKOFF\b|_EXECUTION\b"
    r")",
    re.IGNORECASE,
)
CODEGEN_FILEHINT_RE = re.compile(
    r"(?:scripts/|clarvis/|packages/|apps/|tests/|\.py\b|\.ts\b|\.tsx\b|\.sol\b|\.sh\b)"
)


def _is_codegen(ep: dict) -> bool:
    task = ep.get("task") or ""
    section = ep.get("section") or ""
    if section == "project-agent":
        return True
    if CODEGEN_TASK_RE.search(task):
        return True
    if CODEGEN_FILEHINT_RE.search(task):
        return True
    # Episodes with structured code_validation are code-gen by construction.
    if ep.get("code_validation"):
        return True
    return False


def _classify(ep: dict) -> tuple[str, str]:
    """Return (bucket, reason) for a non-success episode."""
    err = (ep.get("error") or "")
    ft = (ep.get("failure_type") or "").lower()
    task = (ep.get("task") or "")
    outcome = ep.get("outcome") or ""
    code_val = ep.get("code_validation") or {}
    err_l = err.lower()

    # 1. Misroute / wrong workspace edited — strongest signal first.
    if re.search(r"misrout|wrong workspace|does not exist in|outside the repo|outside.*workspace", err_l):
        return "wrong_file_edited", "error mentions misroute/wrong-workspace"
    if "pr_class" in err_l and re.search(r'"pr_class"\s*:\s*"c"', err_l):
        return "wrong_file_edited", "agent self-classified pr_class=C (rejected scope)"

    # 2. Lint / structure failures (the 25% bucket in the prior audit).
    if "lint" in ft or "lint" in err_l:
        return "lint_fail", "failure_type or error contains 'lint'"
    if "lint_structure" in err_l or re.search(r"lines.*>\s*100|>\s*100 lines", err_l):
        return "lint_fail", "structure rule (>100-line function)"
    if isinstance(code_val, dict):
        cv_status = str(code_val.get("status", "")).lower()
        cv_reason = str(code_val.get("reason", "")).lower()
        if "lint" in cv_status or "lint" in cv_reason or "structure" in cv_reason:
            return "lint_fail", f"code_validation flagged lint/structure ({cv_reason or cv_status})"

    # 3. Type-check failures.
    if "typecheck" in ft or "type_check" in ft or "typecheck" in err_l:
        return "type_check_fail", "failure_type/error mentions typecheck"
    if re.search(r"\b(?:mypy|tsc|pyright|tsx? --noEmit)\b", err):
        return "type_check_fail", "error references type checker tooling"

    # 4. Real test failures.
    if ft in ("action.test_failed", "action.assertion_failed"):
        # But if the agent reply self-reports tests_passed: true, this is misclassified.
        if re.search(r'"tests_passed"\s*:\s*true', err_l) and re.search(r'"error"\s*:\s*null', err_l):
            return "other", "classifier_misclassified (test_failed but agent reported tests_passed=true)"
        return "test_fail", f"failure_type={ft}"
    if re.search(r"\btests?\s+failed\b|\bassert(?:ion)?\s+failed\b|\b\d+\s+tests?\s+failed\b", err_l):
        return "test_fail", "error explicitly reports failed tests"
    if re.search(r"forge test.*fail|vitest.*fail|pytest.*fail", err_l):
        return "test_fail", "test runner failure in error"

    # 5. Compile failures (forge build, tsc, pyimport).
    if re.search(r"forge build.*fail|compilation\s+failed|cannot find module|importerror|syntaxerror", err_l):
        return "compile_fail", "build/compile/import error in error text"
    if "compile" in ft:
        return "compile_fail", "failure_type contains 'compile'"

    # 6. Incomplete implementation — partial work, follow-up offered, still-open scope.
    if outcome == "partial_success":
        if re.search(r'"tests_passed"\s*:\s*true', err_l) and re.search(r'"pr_class"\s*:\s*"[ab]"', err_l):
            return "other", "classifier_misclassified (tests_passed=true & pr_class A/B)"
        if re.search(r"still open|follow-?up|not yet wired|operator-blocked|operator-gated|deferred", err_l):
            return "incomplete_implementation", "explicit follow-up/blocked language"
        if re.search(r"only.*touched|no source change|tracker.*entries.*touched|markdown.*only", err_l):
            return "incomplete_implementation", "scope-only edit (no source change)"
        if re.search(r"\[unverified\]|action\.unverified", err_l):
            return "incomplete_implementation", "[UNVERIFIED] marker present"

    # 7. Residual.
    return "other", f"residual (ft={ft or 'none'}, outcome={outcome})"


def _bucket_recommendation(bucket: str, examples: list[dict]) -> str:
    """One concrete, actionable fix per top bucket — modeled on the ESR audit."""
    if bucket == "lint_fail":
        return (
            "Decouple lint/structure verdicts from `outcome`. The `code_validation` "
            "step should write a *separate* `lint_status` field; `outcome` stays "
            "`success` when tests pass and a PR shipped. Spawn `[CODE_GEN_LINT_DECOUPLE_FIX]` "
            "to update `heartbeat_postflight.py` so structure-only failures no longer "
            "downgrade success episodes."
        )
    if bucket == "incomplete_implementation":
        return (
            "Tighten task acceptance: postflight should treat tasks whose only "
            "touched files are `memory/` or `QUEUE.md` as `partial_success` with "
            "`failure_type=incomplete_implementation` (currently they tag as plain "
            "`action`). Spawn `[CODE_GEN_INCOMPLETE_TAG_FIX]` to wire this into "
            "`heartbeat_postflight._derive_failure_type()`."
        )
    if bucket == "wrong_file_edited":
        return (
            "Add a pre-spawn lane-route check: when a task body names `clarvis/` or "
            "`scripts/` paths but `(PROJECT:<NAME>)` is set to a non-Clarvis project, "
            "block the spawn and re-route to the Clarvis lane. Spawn "
            "`[CODE_GEN_LANE_ROUTE_GUARD]` to add this guard in `task_router.py`."
        )
    if bucket == "test_fail":
        return (
            "Real red tests deserve a distinct surface: add a `test_red_count` "
            "rolling counter in `data/audit/code_gen_failures_*.json` so each red "
            "test failure auto-promotes a `[<TASK>_RED_FIX]` follow-up into the "
            "queue, with the failing test ID captured from the error blob."
        )
    if bucket == "type_check_fail":
        return (
            "Add `pnpm typecheck` / `mypy --strict` to the postflight code_validation "
            "step so type errors are captured at *first* run rather than rediscovered "
            "later. Spawn `[CODE_GEN_TYPECHECK_GATE]` to wire this in."
        )
    if bucket == "compile_fail":
        return (
            "Run `forge build` / `python -m compileall` as a pre-commit check inside "
            "the agent worktree. Spawn `[CODE_GEN_BUILD_GATE]` to add a compile gate "
            "before postflight encoding."
        )
    if bucket == "other":
        return (
            "Mostly classifier-misclassified rows (agent reports `tests_passed=true` "
            "yet episode tagged `partial_success`). Cross-references the live "
            "`[ESR_CLASSIFIER_MISCLASSIFIED_FIX]` work — no new fix needed beyond "
            "that one shipping cleanly."
        )
    return "(no recommendation)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30, help="window in days (default 30)")
    ap.add_argument("--dry-run", action="store_true", help="print, do not write")
    ap.add_argument("--date", default=None, help="date stamp for output files (YYYY-MM-DD)")
    args = ap.parse_args()

    if not EPISODES.exists():
        print(f"FATAL: {EPISODES} not found", file=sys.stderr)
        return 1
    episodes = json.loads(EPISODES.read_text())

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=args.days)
    date_stamp = args.date or now.date().isoformat()

    recent = []
    for ep in episodes:
        ts = ep.get("timestamp") or ""
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            continue
        if dt >= cutoff:
            recent.append(ep)

    codegen = [e for e in recent if _is_codegen(e)]
    nonsucc = [e for e in codegen if e.get("outcome") != "success"]

    by_bucket: dict[str, list[dict]] = defaultdict(list)
    classifications = []
    for ep in nonsucc:
        bucket, reason = _classify(ep)
        rec = {
            "id": ep.get("id"),
            "timestamp": ep.get("timestamp"),
            "task": (ep.get("task") or "")[:160],
            "outcome": ep.get("outcome"),
            "failure_type_stored": ep.get("failure_type"),
            "bucket": bucket,
            "reason": reason,
        }
        classifications.append(rec)
        by_bucket[bucket].append(rec)

    bucket_counts = Counter({b: len(by_bucket.get(b, [])) for b in BUCKETS})
    total_codegen = len(codegen)
    total_nonsucc = len(nonsucc)
    total_success = total_codegen - total_nonsucc

    top3 = bucket_counts.most_common(3)

    summary = {
        "generated_at": now.isoformat(),
        "window_days": args.days,
        "window_start": cutoff.isoformat(),
        "window_end": now.isoformat(),
        "total_episodes_in_window": len(recent),
        "code_gen_episodes": total_codegen,
        "code_gen_success": total_success,
        "code_gen_non_success": total_nonsucc,
        "bucket_counts": dict(bucket_counts),
        "top_3_buckets": [{"bucket": b, "count": c} for b, c in top3],
        "classifications": classifications,
    }

    # Acceptance: ≥50 code-gen episodes
    if total_codegen < 50:
        print(
            f"WARN: only {total_codegen} code-gen episodes in window — "
            f"acceptance requires ≥50. Widen --days.",
            file=sys.stderr,
        )

    # Markdown summary.
    md = []
    md.append(f"# Code-Gen Failure Mode Histogram — {date_stamp}")
    md.append("")
    md.append("**Task:** `[CODE_GEN_FAILURE_MODE_HISTOGRAM]`  ")
    md.append(
        f"**Scope:** Last {args.days} days of code-gen episodes "
        f"(`{cutoff.date().isoformat()} → {now.date().isoformat()}`).  "
    )
    md.append(
        f"**Source:** `data/episodes.json` ({len(recent)} episodes in window; "
        f"{total_codegen} classified as code-gen).  "
    )
    md.append("**Mirrors:** `FAILURE_HISTOGRAM_AUDIT_2026-05-02.md` (same shape, code-gen-scoped).")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 1. Counts")
    md.append("")
    md.append(f"- Code-gen episodes: **{total_codegen}**")
    md.append(f"- Success: **{total_success}** ({(total_success/total_codegen*100 if total_codegen else 0):.1f}%)")
    md.append(f"- Non-success: **{total_nonsucc}** ({(total_nonsucc/total_codegen*100 if total_codegen else 0):.1f}%)")
    md.append("")
    md.append("| Bucket | Count | Share of non-success |")
    md.append("|---|---:|---:|")
    for b in BUCKETS:
        c = bucket_counts.get(b, 0)
        share = (c / total_nonsucc * 100) if total_nonsucc else 0
        md.append(f"| `{b}` | {c} | {share:.1f}% |")
    md.append(f"| **Total** | **{total_nonsucc}** | **100%** |")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 2. Top-3 buckets with examples")
    md.append("")
    for i, (bucket, count) in enumerate(top3, start=1):
        share = (count / total_nonsucc * 100) if total_nonsucc else 0
        md.append(f"### {i}. `{bucket}` — {count} episodes ({share:.1f}% of non-success)")
        md.append("")
        examples = by_bucket.get(bucket, [])[:3]
        if not examples:
            md.append("_(no episodes in this bucket)_")
            md.append("")
            continue
        for ex in examples:
            tid = ex["id"]
            tk = ex["task"][:110]
            why = ex["reason"]
            md.append(f"- `{tid}` — {tk}  ")
            md.append(f"  _classifier reason:_ {why}")
        md.append("")
        md.append("**Fix recommendation:** " + _bucket_recommendation(bucket, examples))
        md.append("")
    md.append("---")
    md.append("")
    md.append("## 3. How to spawn the recommended follow-ups")
    md.append("")
    md.append("Append to `memory/evolution/QUEUE.md` under the next free P1 slot:")
    md.append("")
    md.append("```")
    for bucket, _ in top3:
        rec = _bucket_recommendation(bucket, [])
        # Extract the bracketed tag.
        m = re.search(r"`\[([A-Z0-9_]+)\]`", rec)
        if m:
            md.append(f"- [ ] [P1] [{m.group(1)}] (PROJECT:CLARVIS) — see CODE_GEN_FAILURE_HISTOGRAM_{date_stamp}.md")
    md.append("```")
    md.append("")
    md.append("---")
    md.append("")
    md.append(f"_Generated by `scripts/audit/code_gen_failure_histogram.py` at {now.isoformat()}_")
    md_text = "\n".join(md)

    json_path = AUDIT_DIR / f"code_gen_failures_{date_stamp}.json"
    md_path = DOCS_DIR / f"CODE_GEN_FAILURE_HISTOGRAM_{date_stamp}.md"

    if args.dry_run:
        print(json.dumps(summary, indent=2, default=str))
        print()
        print("=" * 60)
        print(md_text)
        return 0

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(summary, indent=2, default=str))
    md_path.write_text(md_text + "\n")
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print()
    print(f"code-gen episodes: {total_codegen} | non-success: {total_nonsucc}")
    print(f"top-3: {[(b, c) for b, c in top3]}")
    if total_codegen < 50:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
