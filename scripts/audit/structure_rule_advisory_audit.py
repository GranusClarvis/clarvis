#!/usr/bin/env python3
"""
Structure-Rule Advisory Shadow-Verify Audit harness.

Runs the re-anchored §2 methodology from
``docs/internal/audits/POSTFLIGHT_RULE_TIGHTEN_SHADOW_VERIFY_2026-05-19.md``
against the live ``data/episodes.json`` store and emits the numeric verdict
(FLIP / HOLD / REVERT / PREMATURE) per §2.5.

Anchor: 2026-05-13 01:07:00 UTC (commit ``f4431f0`` — cherry-pick of ``0d4977a``
to ``main``). Window: anchor + 3 days. Until window closes, this script reports
PREMATURE regardless of intermediate signals.

Usage:
    python3 scripts/audit/structure_rule_advisory_audit.py            # status
    python3 scripts/audit/structure_rule_advisory_audit.py --markdown # §3-style block
    python3 scripts/audit/structure_rule_advisory_audit.py --json     # machine-readable
    python3 scripts/audit/structure_rule_advisory_audit.py --sample N # print N adv ids
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ANCHOR = datetime(2026, 5, 13, 1, 7, 0, tzinfo=timezone.utc)
WINDOW = timedelta(days=3)
ESR_FLOOR = 0.94
FP_THRESHOLD = 0.02  # §2.5 FLIP requires FP < 2%
FN_THRESHOLD = 0.05  # §2.5 FLIP requires FN < 5%

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"))
EPISODES = WORKSPACE / "data" / "episodes.json"


def _parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _load_window(anchor: datetime, end: datetime) -> list[dict]:
    with open(EPISODES) as f:
        eps = json.load(f)
    out = []
    for e in eps:
        t = _parse_ts(e.get("timestamp", ""))
        if t and anchor <= t <= end:
            out.append(e)
    return out


def _has_tag(ep: dict, needle: str) -> bool:
    tags = ep.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    return any(needle in (t or "") for t in tags)


def _census(window_eps: list[dict]) -> dict:
    advisory_fn_too_long = []
    advisory_bare_except = []  # would be a regression — shouldn't exist
    hard_cv_fail = []
    cv_pass = []

    for e in window_eps:
        tags = e.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        for t in tags:
            if not t:
                continue
            if "code_validation:advisory:function_too_long" in t:
                advisory_fn_too_long.append(e["id"])
            elif "code_validation:advisory:bare_except" in t:
                advisory_bare_except.append(e["id"])
            elif t == "code_validation:fail" or t.startswith("code_validation:fail:"):
                hard_cv_fail.append(e["id"])
            elif t == "code_validation:pass":
                cv_pass.append(e["id"])
    return {
        "advisory_fn_too_long": advisory_fn_too_long,
        "advisory_bare_except": advisory_bare_except,
        "hard_cv_fail": hard_cv_fail,
        "cv_pass": cv_pass,
    }


def _esr(window_eps: list[dict]) -> tuple[float | None, dict]:
    outcomes: dict[str, int] = {}
    for e in window_eps:
        o = (e.get("outcome") or "unknown").strip()
        outcomes[o] = outcomes.get(o, 0) + 1
    success = outcomes.get("success", 0)
    partial = outcomes.get("partial_success", 0) + outcomes.get("partial", 0)
    failure = outcomes.get("failure", 0) + outcomes.get("fail", 0)
    denom = success + partial + failure
    return (success / denom if denom else None, outcomes)


def _verdict(census: dict, esr: float | None, window_closed: bool) -> tuple[str, str]:
    """Apply §2.5 verdict criterion. Returns (verdict, reason)."""
    if not window_closed:
        return ("PREMATURE", "3-day shadow window has not yet elapsed")

    adv_count = len(census["advisory_fn_too_long"])
    struct_fail = len(census["hard_cv_fail"])  # not split by cause here; manual review for §2.3
    bare_advisory = len(census["advisory_bare_except"])

    if bare_advisory > 0:
        return ("REVERT", f"§2.4 regression: {bare_advisory} episode(s) tagged bare_except as advisory")
    if adv_count < 1:
        return ("HOLD", "§2.1 sanity: zero advisory:function_too_long episodes fired in window")
    if esr is None or esr < ESR_FLOOR:
        return ("HOLD", f"§2.2 ESR fell below floor {ESR_FLOOR} (got {esr})")
    return (
        "FLIP_CANDIDATE",
        f"§2.5: §2.1 fired ({adv_count} adv), §2.2 ESR={esr:.3f} ≥ {ESR_FLOOR}, §2.4 clean — pending §2.3 manual review",
    )


def run(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    end = ANCHOR + WINDOW
    window_closed = now >= end
    effective_end = min(now, end)
    eps = _load_window(ANCHOR, effective_end)
    census = _census(eps)
    esr, outcomes = _esr(eps)
    verdict, reason = _verdict(census, esr, window_closed)
    return {
        "anchor_utc": ANCHOR.isoformat(),
        "window_end_utc": end.isoformat(),
        "now_utc": now.isoformat(),
        "elapsed_hours": round((now - ANCHOR).total_seconds() / 3600, 2),
        "window_closed": window_closed,
        "episodes_in_window": len(eps),
        "outcomes": outcomes,
        "esr": esr,
        "esr_floor": ESR_FLOOR,
        "advisory_function_too_long": len(census["advisory_fn_too_long"]),
        "advisory_bare_except_regression": len(census["advisory_bare_except"]),
        "hard_code_validation_fail": len(census["hard_cv_fail"]),
        "code_validation_pass": len(census["cv_pass"]),
        "verdict": verdict,
        "reason": reason,
        "advisory_episode_ids": census["advisory_fn_too_long"],
    }


def _markdown(report: dict) -> str:
    lines = [
        "## 3. Audit results (auto-generated by structure_rule_advisory_audit.py)",
        "",
        f"- **As of:** {report['now_utc']}",
        f"- **Anchor:** {report['anchor_utc']} (merge of `f4431f0` to main)",
        f"- **Window end:** {report['window_end_utc']}",
        f"- **Window closed:** {report['window_closed']} ({report['elapsed_hours']}h elapsed / 72h)",
        f"- **Episodes in window:** {report['episodes_in_window']}",
        f"- **Outcomes:** {report['outcomes']}",
        "",
        "### §2.1 Episode-tag census",
        f"- `code_validation:advisory:function_too_long`: **{report['advisory_function_too_long']}** (target ≥ 1)",
        f"- `code_validation:advisory:bare_except` (regression — must be 0): **{report['advisory_bare_except_regression']}**",
        f"- Hard `code_validation:fail`: **{report['hard_code_validation_fail']}**",
        f"- `code_validation:pass`: **{report['code_validation_pass']}**",
        "",
        "### §2.2 ESR delta",
        f"- ESR over window: **{report['esr']}** (floor: {report['esr_floor']})",
        "",
        "### §2.4 Bare-except regression",
        (
            "- **PASS** — zero bare_except advisory tags."
            if report["advisory_bare_except_regression"] == 0
            else f"- **FAIL** — {report['advisory_bare_except_regression']} bare_except advisory tag(s)."
        ),
        "",
        "### §2.5 Verdict",
        f"- **{report['verdict']}** — {report['reason']}",
        "",
        "_§2.3 manual FP/FN review must be completed separately. Advisory episode IDs:_",
        f"`{report['advisory_episode_ids']}`",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--markdown", action="store_true", help="emit §3-style markdown block")
    ap.add_argument("--sample", type=int, default=10, help="advisory ids to sample for §2.3 (default 10)")
    args = ap.parse_args()

    report = run()
    report["advisory_episode_ids"] = report["advisory_episode_ids"][: args.sample]

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    elif args.markdown:
        print(_markdown(report))
    else:
        print(f"Anchor:        {report['anchor_utc']}")
        print(f"Window end:    {report['window_end_utc']}")
        print(f"Now:           {report['now_utc']}")
        print(f"Elapsed:       {report['elapsed_hours']}h / 72h")
        print(f"Window closed: {report['window_closed']}")
        print(f"Episodes:      {report['episodes_in_window']}")
        print(f"Outcomes:      {report['outcomes']}")
        print(f"ESR:           {report['esr']} (floor {report['esr_floor']})")
        print(f"Advisory tags: {report['advisory_function_too_long']}")
        print(f"Bare-except advisory (regression): {report['advisory_bare_except_regression']}")
        print(f"Hard cv-fail:  {report['hard_code_validation_fail']}")
        print(f"cv-pass:       {report['code_validation_pass']}")
        print(f"VERDICT:       {report['verdict']} — {report['reason']}")
        if report["advisory_episode_ids"]:
            print(f"Sample ids:    {report['advisory_episode_ids']}")

    return 0 if report["verdict"] != "REVERT" else 1


if __name__ == "__main__":
    sys.exit(main())
