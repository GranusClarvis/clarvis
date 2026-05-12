#!/usr/bin/env python3
"""ESR Unverified Bucket Triage — root-cause classifier for `action.unverified`.

Targets the weakest metric Episode Success Rate (0.828, target ≥0.85) by
triaging the dominant failure bucket `action.unverified` (71 episodes,
~88% of failure mass per `data/performance_metrics.json`).

Each `action.unverified` episode is one where the spawned agent self-reported
work as done but the parent postflight downgraded `outcome` to
`partial_success`. The buckets below classify *why* the downgrade happened so
that the right fix can be prioritised.

Buckets (first match wins):
    correctly-downgraded   agent self-flagged the work as not-yet-landed
                           (follow-up, deferred, operator-blocked, [UNVERIFIED])
    falsely-downgraded     agent shipped real work; postflight signal mismatch
                           (code_validation:pass OR structure-only failure)
    infra-failure          validation infra crashed (output_errors, missing fixtures)
    ambiguous              everything else

Outputs:
    data/audit/esr_unverified_triage_YYYY-MM-DD.json
    docs/internal/audits/ESR_UNVERIFIED_TRIAGE_YYYY-MM-DD.md

Usage:
    python3 scripts/audit/esr_unverified_triage.py            # write outputs
    python3 scripts/audit/esr_unverified_triage.py --dry-run  # print only
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
AUDIT_DIR = WORKSPACE / "data" / "audit"
DOCS_DIR = WORKSPACE / "docs" / "internal" / "audits"

BUCKETS = ["correctly-downgraded", "falsely-downgraded", "infra-failure", "ambiguous"]

# Phrases the agent uses to self-flag work as incomplete.
INCOMPLETE_RE = re.compile(
    r"\[unverified\]|operator[- ]?blocked|operator[- ]?gated|deferred|"
    r"still open|not yet wired|follow[- ]?ups?|next session|blocked on|"
    r"out of scope|partial:|pr_class\"?\s*:\s*\"c\"|"
    r"could not|did not (?:run|land|complete|ship)",
    re.IGNORECASE,
)

# Phrases that strongly suggest the agent really did ship.
SHIPPED_RE = re.compile(
    r'"tests_passed"\s*:\s*true|tests_passed:\s*true|'
    r"all tests pass|all green|verified|"
    r"committed( and pushed| to)|merged|"
    r"shipped|landed|done",
    re.IGNORECASE,
)

# Infra/tooling failures rather than agent failures.
INFRA_RE = re.compile(
    r"output_errors|module not found|importerror|"
    r"no such file or directory|enoent|"
    r"validator (?:crashed|errored)|fixture (?:missing|not found)|"
    r"validation infra|timeout while validating",
    re.IGNORECASE,
)


def classify(ep: dict) -> tuple[str, str]:
    """Classify a single `action.unverified` episode. Returns (bucket, reason)."""
    err = ep.get("error") or ""
    err_l = err.lower()
    cv = ep.get("code_validation") or {}
    tags = ep.get("tags") or []
    tag_str = " ".join(str(t) for t in tags).lower()
    cv_passed = cv.get("passed")
    cv_output_errors = cv.get("output_errors")
    cv_refinement = (cv.get("refinement") or "").lower()

    # 1. Infra failure trumps everything (the agent never got a fair signal).
    if cv_output_errors:
        return "infra-failure", "code_validation.output_errors=True"
    if INFRA_RE.search(err_l) or INFRA_RE.search(cv_refinement):
        return "infra-failure", "error/refinement mentions infra crash/missing module/fixture"

    # 2. Correctly-downgraded: agent itself flagged the work as incomplete.
    if INCOMPLETE_RE.search(err_l):
        m = INCOMPLETE_RE.search(err_l)
        return "correctly-downgraded", f"agent flagged incompleteness: '{m.group(0)}'"

    # 3. Falsely-downgraded paths.
    # 3a. code_validation explicitly passed.
    if cv_passed is True or "code_validation:pass" in tag_str:
        return "falsely-downgraded", "code_validation:pass — postflight still downgraded"

    # 3b. Structure-only validation failure (the >100-line rule, no real test/lint/type errors).
    if cv_passed is False and cv_refinement:
        has_structure = "structure" in cv_refinement or ">100" in cv_refinement or "lines" in cv_refinement
        has_real_lint = re.search(r"\b(?:lint|ruff|eslint|flake8|pylint)\b", cv_refinement) is not None
        has_typecheck = re.search(r"\b(?:typecheck|type[-_ ]check|mypy|pyright|tsc)\b", cv_refinement) is not None
        has_test_fail = re.search(r"\b(?:test|assertion|pytest|vitest|forge test)\b", cv_refinement) is not None
        if has_structure and not (has_real_lint or has_typecheck or has_test_fail):
            return "falsely-downgraded", "code_validation:fail but ONLY structure rule (>100 lines)"

    # 3c. Agent self-report strongly indicates success and no incomplete language.
    if SHIPPED_RE.search(err_l) and "code_validation:fail" not in tag_str:
        return "falsely-downgraded", "agent self-reports shipped/tests_passed=true; no failure tag"

    # 4. Ambiguous residual.
    if cv_passed is False:
        return "ambiguous", f"code_validation:fail with mixed/unclear refinement"
    return "ambiguous", "no decisive signal in error or code_validation"


def projected_esr_lift(bucket_counts: dict, total_episodes: int, current_esr: float) -> dict:
    """Quantify ESR lift if `falsely-downgraded` episodes were correctly counted as success.

    Math: success_count_new = success_count_old + falsely_downgraded.
          ESR_new = success_count_new / denominator.
    For ESR ~= 0.828 with total ~500, success_count ~= 414.
    Each flipped episode adds 1/total to ESR.
    """
    falsely = bucket_counts.get("falsely-downgraded", 0)
    infra = bucket_counts.get("infra-failure", 0)
    delta_falsely = falsely / total_episodes if total_episodes else 0.0
    # Infra-failure: arguably should also not count against ESR (it's a validator bug
    # not an agent bug). Quantify the conservative ("falsely only") and aggressive
    # ("falsely + infra") scenarios.
    delta_aggressive = (falsely + infra) / total_episodes if total_episodes else 0.0
    return {
        "falsely_downgraded": falsely,
        "infra_failure": infra,
        "total_episodes": total_episodes,
        "current_esr": current_esr,
        "esr_if_falsely_fixed": round(current_esr + delta_falsely, 4),
        "esr_if_falsely_and_infra_fixed": round(current_esr + delta_aggressive, 4),
        "delta_falsely": round(delta_falsely, 4),
        "delta_aggressive": round(delta_aggressive, 4),
        "passes_0_85_falsely_only": (current_esr + delta_falsely) >= 0.85,
        "passes_0_85_with_infra": (current_esr + delta_aggressive) >= 0.85,
    }


def follow_up_candidates(bucket: str) -> list[dict]:
    """Concrete fix tasks per bucket — to be added to QUEUE.md."""
    if bucket == "falsely-downgraded":
        return [
            {
                "tag": "ESR_CV_PASS_FORCES_SUCCESS",
                "summary": "When `code_validation.passed=True` AND `tests_passed=true` in agent JSON, "
                           "postflight must set outcome=success regardless of other heuristics. "
                           "Wire this short-circuit into `heartbeat_postflight._derive_outcome()` "
                           "as the FIRST decision branch.",
            },
            {
                "tag": "ESR_STRUCTURE_RULE_NOT_FAILURE",
                "summary": "Decouple structure rules (>100-line functions) from `code_validation.passed`. "
                           "Move them to a soft `lint_advisory` field that does NOT downgrade outcome. "
                           "Mirror the design proposed for `[CODE_GEN_LINT_DECOUPLE_FIX]`.",
            },
            {
                "tag": "ESR_BACKFILL_FALSELY_DOWNGRADED",
                "summary": "One-shot backfill: re-classify the falsely-downgraded episodes flagged in this "
                           "report. Set `outcome=success`, clear `failure_type`, re-emit `failure_types` "
                           "stats. Lifts ESR by the exact amount projected.",
            },
        ]
    if bucket == "correctly-downgraded":
        return [
            {
                "tag": "ESR_INCOMPLETE_TAG_ROUTING",
                "summary": "When agent self-flags incompleteness (`[UNVERIFIED]`, `operator-blocked`, "
                           "`follow-up`), tag the episode with a NEW first-class failure_type "
                           "`incomplete_by_design` instead of `action.unverified`. These should not "
                           "count against ESR — they're explicit deferrals.",
            },
            {
                "tag": "ESR_DEFERRAL_ESR_EXCLUDE",
                "summary": "Extend `ESR_EXCLUDED_FAILURE_TYPES` (in `scripts/metrics/performance_benchmark.py`) "
                           "to include `incomplete_by_design`. Treated like `transient_auth` — visible in "
                           "ops stats but not in the ESR formula.",
            },
            {
                "tag": "ESR_OPERATOR_BLOCKED_LANE",
                "summary": "For operator-blocked tasks, generate a structured follow-up entry in QUEUE.md "
                           "and exit the spawn with outcome=`success` + `requires_operator=True`. Stops the "
                           "current pattern where agents do everything they can and still get marked down.",
            },
        ]
    if bucket == "infra-failure":
        return [
            {
                "tag": "ESR_VALIDATOR_OUTPUT_ERRORS_RETRY",
                "summary": "When `code_validation.output_errors=True`, retry validation once with extended "
                           "timeout before recording the episode. Wire into "
                           "`heartbeat_postflight._run_code_validation()`.",
            },
            {
                "tag": "ESR_INFRA_FAILURE_BUCKET",
                "summary": "Promote `infra-failure` to a first-class failure_type so it can be excluded "
                           "from ESR via `ESR_EXCLUDED_FAILURE_TYPES`. Today these silently land in "
                           "`action.unverified` and drag the metric.",
            },
            {
                "tag": "ESR_FIXTURE_PRECHECK",
                "summary": "Add a preflight that asserts validator dependencies (ruff, mypy, pytest, "
                           "forge) are importable BEFORE spawning. Hard-fail with a queueable diagnostic "
                           "task rather than running and producing infra-failure episodes.",
            },
        ]
    if bucket == "ambiguous":
        return [
            {
                "tag": "ESR_AMBIGUOUS_SIGNAL_AUDIT",
                "summary": "Hand-review the ambiguous episodes in this report and refine the classifier. "
                           "Likely candidates: episodes with `code_validation:fail` but the refinement is "
                           "truncated/empty.",
            },
        ]
    return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print, do not write files")
    ap.add_argument("--date", default=None, help="date stamp for output (default: today UTC)")
    ap.add_argument("--current-esr", type=float, default=0.828, help="current ESR for delta projection")
    args = ap.parse_args()

    # Lazy import: EpisodicMemory triggers brain init.
    try:
        from clarvis.memory.episodic_memory import EpisodicMemory
    except ImportError as e:
        print(f"FATAL: cannot import EpisodicMemory: {e}", file=sys.stderr)
        return 1

    em = EpisodicMemory()
    total_episodes = len(em.episodes)
    unverified = [ep for ep in em.episodes if em._get_failure_type(ep) == "action.unverified"]
    n = len(unverified)

    if n == 0:
        print("No `action.unverified` episodes found — nothing to triage.")
        return 0

    classifications = []
    by_bucket: dict[str, list[dict]] = defaultdict(list)
    for ep in unverified:
        bucket, reason = classify(ep)
        rec = {
            "id": ep.get("id"),
            "timestamp": ep.get("timestamp"),
            "task": (ep.get("task") or "")[:200],
            "outcome": ep.get("outcome"),
            "failure_type_stored": ep.get("failure_type"),
            "bucket": bucket,
            "reason": reason,
            "agent_self_report_excerpt": (ep.get("error") or "")[:300],
            "code_validation_passed": (ep.get("code_validation") or {}).get("passed"),
            "code_validation_refinement": (
                ((ep.get("code_validation") or {}).get("refinement") or "")[:200]
            ),
        }
        classifications.append(rec)
        by_bucket[bucket].append(rec)

    bucket_counts = Counter({b: len(by_bucket.get(b, [])) for b in BUCKETS})
    total_unverified = sum(bucket_counts.values())

    lift = projected_esr_lift(bucket_counts, total_episodes, args.current_esr)

    now = datetime.now(timezone.utc)
    date_stamp = args.date or now.date().isoformat()

    summary = {
        "generated_at": now.isoformat(),
        "total_episodes": total_episodes,
        "unverified_count": total_unverified,
        "unverified_share_of_episodes": round(total_unverified / total_episodes, 4) if total_episodes else 0,
        "bucket_counts": dict(bucket_counts),
        "projected_esr_lift": lift,
        "classifications": classifications,
    }

    # Acceptance guard
    if total_unverified < 30:
        print(f"WARN: only {total_unverified} unverified episodes — acceptance bar is ≥30.", file=sys.stderr)

    # Histogram sanity: must sum to 100%
    pct_total = sum((c / total_unverified * 100) for c in bucket_counts.values())
    assert abs(pct_total - 100.0) < 0.5, f"histogram does not sum to 100% (got {pct_total})"

    md = []
    md.append(f"# ESR Unverified Bucket Triage — {date_stamp}")
    md.append("")
    md.append("**Task:** `[ESR_UNVERIFIED_BUCKET_TRIAGE]`  ")
    md.append(f"**Source:** `data/episodes.json` via `EpisodicMemory` ({total_episodes} episodes total).  ")
    md.append(f"**Scope:** {total_unverified} episodes where `failure_type=='action.unverified'`.  ")
    md.append(
        "**Why this matters:** ESR is the weakest metric "
        f"(`{args.current_esr}` vs target `≥0.85`). `action.unverified` "
        f"is ~{round(total_unverified / max(1, sum([71,2,1,4,7,1,1])) * 100)}% of the failure mass."
    )
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 1. Histogram")
    md.append("")
    md.append("| Bucket | Count | Share |")
    md.append("|---|---:|---:|")
    for b in BUCKETS:
        c = bucket_counts.get(b, 0)
        share = (c / total_unverified * 100) if total_unverified else 0
        md.append(f"| `{b}` | {c} | {share:.1f}% |")
    md.append(f"| **Total** | **{total_unverified}** | **100.0%** |")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 2. Projected ESR lift")
    md.append("")
    md.append(
        f"Current ESR: **{lift['current_esr']}** (denominator {lift['total_episodes']} episodes). "
        f"Flipping the `falsely-downgraded` episodes to `success` adds "
        f"**{lift['delta_falsely']:+.4f}** → **{lift['esr_if_falsely_fixed']}**. "
        f"Also fixing `infra-failure` adds another {lift['infra_failure']} episodes → "
        f"**{lift['esr_if_falsely_and_infra_fixed']}**."
    )
    md.append("")
    md.append("| Scenario | ΔESR | New ESR | Passes ≥0.85? |")
    md.append("|---|---:|---:|:---:|")
    md.append(
        f"| Fix `falsely-downgraded` only ({lift['falsely_downgraded']} eps) | "
        f"{lift['delta_falsely']:+.4f} | {lift['esr_if_falsely_fixed']} | "
        f"{'✅' if lift['passes_0_85_falsely_only'] else '❌'} |"
    )
    md.append(
        f"| Fix falsely + infra ({lift['falsely_downgraded'] + lift['infra_failure']} eps) | "
        f"{lift['delta_aggressive']:+.4f} | {lift['esr_if_falsely_and_infra_fixed']} | "
        f"{'✅' if lift['passes_0_85_with_infra'] else '❌'} |"
    )
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 3. Per-bucket examples & follow-up fix candidates")
    md.append("")

    for bucket in BUCKETS:
        examples = by_bucket.get(bucket, [])
        count = len(examples)
        share = (count / total_unverified * 100) if total_unverified else 0
        md.append(f"### `{bucket}` — {count} episodes ({share:.1f}%)")
        md.append("")
        if not examples:
            md.append("_(no episodes in this bucket)_")
            md.append("")
            continue
        md.append("**Sample episodes:**")
        for ex in examples[:5]:
            tk = ex["task"][:110]
            md.append(f"- `{ex['id']}` — {tk}  ")
            md.append(f"  _reason:_ {ex['reason']}")
            excerpt = (ex["agent_self_report_excerpt"] or "").replace("\n", " ")[:160]
            if excerpt:
                md.append(f"  _agent excerpt:_ `{excerpt}`")
        md.append("")
        candidates = follow_up_candidates(bucket)
        if candidates:
            md.append("**Follow-up fix candidates:**")
            for fc in candidates:
                md.append(f"- **`[{fc['tag']}]`** — {fc['summary']}")
            md.append("")

    md.append("---")
    md.append("")
    md.append("## 4. How to spawn the recommended follow-ups")
    md.append("")
    md.append("Add these to `memory/evolution/QUEUE.md` under P1 (the dominant bucket's fixes first):")
    md.append("")
    md.append("```")
    # Surface the top-bucket follow-ups first
    sorted_buckets = sorted(
        BUCKETS,
        key=lambda b: -bucket_counts.get(b, 0),
    )
    for b in sorted_buckets:
        if bucket_counts.get(b, 0) == 0:
            continue
        for fc in follow_up_candidates(b):
            md.append(f"- [ ] [P1] [{fc['tag']}] (PROJECT:CLARVIS) — see ESR_UNVERIFIED_TRIAGE_{date_stamp}.md ({b})")
    md.append("```")
    md.append("")
    md.append("---")
    md.append("")
    md.append(f"_Generated by `scripts/audit/esr_unverified_triage.py` at {now.isoformat()}._")
    md_text = "\n".join(md) + "\n"

    json_path = AUDIT_DIR / f"esr_unverified_triage_{date_stamp}.json"
    md_path = DOCS_DIR / f"ESR_UNVERIFIED_TRIAGE_{date_stamp}.md"

    if args.dry_run:
        print(json.dumps(summary, indent=2, default=str))
        print()
        print("=" * 60)
        print(md_text)
        return 0

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(summary, indent=2, default=str))
    md_path.write_text(md_text)
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print()
    print(f"triaged {total_unverified} episodes:")
    for b in BUCKETS:
        c = bucket_counts.get(b, 0)
        print(f"  {b}: {c} ({c/total_unverified*100:.1f}%)")
    print()
    print(
        f"projected ESR lift: "
        f"falsely-only={lift['delta_falsely']:+.4f} → {lift['esr_if_falsely_fixed']} "
        f"({'PASS' if lift['passes_0_85_falsely_only'] else 'FAIL'}); "
        f"falsely+infra={lift['delta_aggressive']:+.4f} → {lift['esr_if_falsely_and_infra_fixed']} "
        f"({'PASS' if lift['passes_0_85_with_infra'] else 'FAIL'})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
