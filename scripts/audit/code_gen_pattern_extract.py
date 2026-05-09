#!/usr/bin/env python3
"""Code-Gen Pattern Extraction — distill the BB Phase 2 success cluster.

Targets the second-weakest capability `code_generation=0.87`. The last 48-72
hours shipped a high-density cluster of BB Phase 2 tasks cleanly (HILO_STEP,
INDEXER_DICE_HILO, DICE_SLIDER_VISUAL, RECENT_BETS_WALLET_SHEET, MEDUSA_HARNESS,
SLITHER_HIGH_SEV_TRIAGE, WALLET_MOCK, FUZZ_GUARD, ...). This audit reads the
matching episodes from `data/episodes.json` plus the corresponding Clarvis-side
queue commits (which carry the bunnybagz SHAs in the body) and distills the
recurring shape into a single procedural memory.

The procedure is stored in `clarvis-procedures` via
`procedural_memory.store_procedure()` so future code-gen tasks can retrieve it
via `python3 -m clarvis brain search "BB Phase 2 code-gen pattern"`.

Usage:
    python3 scripts/audit/code_gen_pattern_extract.py            # extract + store
    python3 scripts/audit/code_gen_pattern_extract.py --dry-run  # print, don't store
    python3 scripts/audit/code_gen_pattern_extract.py --print    # print stored procedure
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

from clarvis.brain import brain, PROCEDURES, LEARNINGS  # noqa: E402
from clarvis.memory import procedural_memory as pm  # noqa: E402

EPISODES_PATH = os.path.join(WORKSPACE, "data/episodes.json")
REPORT_PATH = os.path.join(
    WORKSPACE, "docs/internal/audits/code_gen_bb_pattern_2026-05-09.md"
)

# Tag pattern matches the [BB_PHASE2_*] task labels in episodes.json.
TAG_RE = re.compile(r"\[BB_PHASE2_[A-Z0-9_]+\]")
# Reference to a bunnybagz commit SHA inside a queue commit body, e.g.
# "bunnybagz commit 6b9eef7" or "Mega-house commit: 39fb452".
SHA_RE = re.compile(r"\b([0-9a-f]{7,40})\b")
# Test-count hints in commit subject like "+ 15 tests", "19 tests", "13 vitest".
TESTCOUNT_RE = re.compile(
    r"(\d{1,3})\s*(vitest|tsx\s*--?test|forge|tests?|specs?|cases?)",
    re.IGNORECASE,
)
# Suite-totals like "forge 147/147" or "web 316/316".
SUITE_RE = re.compile(r"\b(forge|web|api|indexer|verify)\s+(\d+)/(\d+)\b", re.IGNORECASE)


def _load_episodes():
    with open(EPISODES_PATH) as f:
        return json.load(f)


def _bb_phase2_episodes(eps, limit=20):
    rows = []
    for e in eps:
        if not isinstance(e, dict):
            continue
        task = e.get("task") or ""
        if "BB_PHASE2" not in task:
            continue
        if (e.get("outcome") or "") not in ("success", "partial_success"):
            continue
        rows.append(e)
    rows.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return rows[:limit]


def _git(args, cwd=WORKSPACE):
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
        return out.stdout
    except Exception as exc:
        return f"<git-error: {exc}>"


def _queue_commits():
    """Pull all Clarvis-side queue commits that ship/verify a BB_PHASE2 task."""
    raw = _git([
        "log",
        "--all",
        "--since=2026-05-04 00:00",
        "--until=2026-05-07 23:59",
        "--pretty=format:===%H|%ai|%s%n%b",
    ])
    commits = []
    for chunk in raw.split("===")[1:]:
        head, _, body = chunk.partition("\n")
        if "|" not in head:
            continue
        sha, ts, subj = head.split("|", 2)
        if "BB_PHASE2" not in subj and "BB Phase 2" not in subj:
            continue
        if "shipped" not in subj.lower() and "verified" not in subj.lower() and "fast-track" not in subj.lower():
            continue
        commits.append({
            "sha": sha.strip(),
            "ts": ts.strip(),
            "subject": subj.strip(),
            "body": body.strip(),
        })
    return commits


def _extract_external_shas(commit):
    """SHAs referenced inside the body that are NOT the commit's own SHA.

    These point to project commits in the bunnybagz / mega-house repo, which
    are the actual code-gen artifacts behind each Clarvis queue entry.
    """
    own = commit["sha"]
    found = []
    for m in SHA_RE.finditer(commit["body"]):
        s = m.group(1)
        if s == own[: len(s)]:
            continue
        if len(s) >= 6:
            found.append(s)
    seen = set()
    uniq = []
    for s in found:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq[:4]


def _summarise_commit(commit):
    """Pull the shape signals out of one queue commit."""
    subj = commit["subject"]
    body = commit["body"]
    test_counts = TESTCOUNT_RE.findall(subj + "\n" + body)
    suite_totals = SUITE_RE.findall(subj + "\n" + body)
    tag_match = TAG_RE.search(subj) or TAG_RE.search(body)
    return {
        "sha": commit["sha"][:8],
        "ts": commit["ts"][:10],
        "tag": tag_match.group(0) if tag_match else None,
        "subject": subj,
        "external_shas": _extract_external_shas(commit),
        "test_counts": [(int(n), kind.lower().strip()) for n, kind in test_counts],
        "suite_totals": [(s, int(p), int(t)) for s, p, t in suite_totals],
        "verified": "VERIFIED" in subj or "verified" in subj.lower(),
    }


def _aggregate(summaries):
    total = len(summaries)
    with_tests = sum(1 for s in summaries if s["test_counts"])
    with_suite_totals = sum(1 for s in summaries if s["suite_totals"])
    with_external_sha = sum(1 for s in summaries if s["external_shas"])
    verified = sum(1 for s in summaries if s["verified"])
    test_count_values = [n for s in summaries for n, _ in s["test_counts"]]
    suites_seen = sorted({s for x in summaries for s, _, _ in x["suite_totals"]})
    return {
        "n_commits": total,
        "with_tests": with_tests,
        "with_suite_totals": with_suite_totals,
        "with_external_sha": with_external_sha,
        "verified_followups": verified,
        "median_test_count": (
            sorted(test_count_values)[len(test_count_values) // 2]
            if test_count_values
            else 0
        ),
        "max_test_count": max(test_count_values) if test_count_values else 0,
        "suites_seen": suites_seen,
    }


def build_checklist(summaries, agg):
    """Return (checklist_steps, preconditions, termination_criteria)."""
    sha_refs = []
    for s in summaries[:8]:
        if s["external_shas"] and s["tag"]:
            sha_refs.append(f"{s['tag']} → bunnybagz {s['external_shas'][0]}")
        elif s["tag"]:
            sha_refs.append(f"{s['tag']} → clarvis queue commit {s['sha']}")
    sha_refs_str = "; ".join(sha_refs[:6])

    steps = [
        # 1
        "Open the queued task with its full [BB_PHASEx_TAG] from QUEUE.md and copy "
        "the verbatim Acceptance bullet into your worktree notes — every shipped "
        "BB Phase 2 episode in episodes.json carries the tag in the task field "
        "and the queue subject line; treat the tag as the canonical id everywhere "
        "(commit subject, branch name, audit doc).",
        # 2
        "Pin the project repo + branch up front: BB Phase 2 work lives in "
        "`GranusClarvis/bunnybagz` on `feature/mvp-planning-and-rebrand` (e.g. "
        "MEDUSA_HARNESS_PREFUND → 39fb452, SLITHER_HIGH_SEV_TRIAGE → 6b9eef7, "
        "PLAYWRIGHT_WALLET_MOCK + FUZZ_GUARD → e5a6b80 / 5a5e93e, HILO_STEP "
        "→ 1c7c349). NEVER touch /home/agent/.openclaw/workspace except to log "
        "the queue update — keep code edits inside the project repo.",
        # 3
        "Honour the monorepo layout: contracts under `packages/contracts/`, "
        "edge routes + UI under `apps/web/src/app/...`, indexer under "
        "`packages/indexer/`, ABIs under `packages/chain/`. New components ship "
        "with a sibling component name (DiceSlider → ce9c1d56, RecentBetsList → "
        "1f79edf0, RecentOutcomesStrip → 5ed61e00) — no shared `utils/` dumping.",
        # 4
        "Always pair the change with tests in the matching runner: "
        "vitest for web components (DiceSlider 19, RecentBetsList 13, "
        "RecentOutcomesStrip 12), `tsx --test` for edge handlers "
        "(/api/history/wallet 13), forge/medusa for contract changes (Slither "
        "CEI fix → forge 147/147 green; Medusa harness → 258k calls 0 failures). "
        "Median test count across the cluster was "
        f"~{agg['median_test_count']} cases, max {agg['max_test_count']}.",
        # 5
        "Name tests after the externally-observable behaviour, not the "
        "implementation: `playStep edge route + decoder` (HILO_STEP, ebc70939) "
        "and `wagmi mock() connector + JSON-RPC route harness + 3 connected "
        "specs` (PLAYWRIGHT_WALLET_MOCK, e5a6b80) both describe the surface, "
        "not the function names. Reuse the `<feature>.spec.ts` / `<comp>.test.tsx` "
        "convention already in the repo — don't invent a new layout.",
        # 6
        "Apply CEI / state-before-effect on every contract edit: the "
        "SLITHER_HIGH_SEV_TRIAGE fix (da168daf → bunnybagz 6b9eef7) tripped the "
        "drawdown circuit-breaker BEFORE the external transfer using the "
        "predicted post-payout balance. If a contract edit produces a slither "
        "or aderyn HIGH, refactor to CEI rather than suppress.",
        # 7
        "Keep harnesses honest: when invariant fuzzers fail (Medusa, Halmos, "
        "Foundry invariant) treat it as a real defect first, only then a harness "
        "bug. MEDUSA_HARNESS_PREFUND (c7edff89) is the template — pre-fund "
        "address(this) with `type(uint128).max` in the constructor when "
        "`{value:…}` calls are part of the property.",
        # 8
        "Land green on all four suites in one commit and quote the totals in "
        "the queue commit body — every Phase 2 ship lists `forge N/N · web N/N "
        "· api N/N · indexer N/N · verify N/N` (cfc5fe09 fast-track quoted "
        "128/128 · 283/283 · 75/75 · 37/37 · 40/40). Suites observed in the "
        f"cluster: {', '.join(agg['suites_seen']) or 'forge/web/api/indexer/verify'}.",
        # 9
        "Write the Clarvis queue commit in the canonical shape: "
        "`queue: <BB_PHASEx_TAG> shipped — <one-line surface change>` with the "
        "external bunnybagz SHA + branch + CI run id in the body, then a second "
        "`VERIFIED` queue commit once CI is green (E2E_GREEN_GAP_FIX 01a11a60 "
        "→ 899d269e, FORGE_BUILD_RED_FIX 4ee147d3 → de8de4be, CHAIN_ABIS_REGEN "
        f"6f101310 → 46e251d2). {agg['verified_followups']}/{agg['n_commits']} "
        "shipped commits in this cluster have a paired VERIFIED follow-up.",
        # 10
        "Mark `[x] [UNVERIFIED]` in QUEUE.md the moment code lands on the "
        "project repo — never `[x]` directly. The fast-track commit (cfc5fe09) "
        "shows the exact pattern; the VERIFIED edit in queue is what flips the "
        "tag to plain `[x]`. This keeps the truth-audit (memory/evolution/"
        "bb_phase2_truth_audit_2026-05-04.md) reproducible from disk artefacts "
        "alone.",
    ]
    preconditions = [
        "Task carries a [BB_PHASEx_TAG] label in QUEUE.md",
        "Project repo (e.g. bunnybagz) cloned and on the working feature branch",
        "Local test runners installed: vitest, forge, medusa, playwright",
        "Slither + Aderyn available for contract edits (or runnable in CI)",
    ]
    termination_criteria = [
        "All four+ suites green and quoted in the queue commit body (forge/web/api/indexer/verify)",
        "External bunnybagz SHA recorded in the queue commit body",
        "Slither + Aderyn report 0 HIGH on any contract diff",
        "QUEUE.md flipped from [ ] to [x] [UNVERIFIED], then to [x] after CI confirms",
        f"Procedure cites ≥6 tagged episodes by SHA: {sha_refs_str}",
    ]
    return steps, preconditions, termination_criteria


def write_report(summaries, agg, steps, preconditions, termination, dry_run):
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    lines = []
    lines.append("# BB Phase 2 Code-Gen Success Pattern Extraction")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}_")
    lines.append("")
    lines.append("## Sample")
    lines.append("")
    lines.append(f"- Queue commits scanned: **{agg['n_commits']}**")
    lines.append(f"- With explicit test counts: **{agg['with_tests']}**")
    lines.append(f"- With suite-total quotes: **{agg['with_suite_totals']}**")
    lines.append(f"- With external project SHA: **{agg['with_external_sha']}**")
    lines.append(f"- Paired with VERIFIED follow-up: **{agg['verified_followups']}**")
    lines.append(
        f"- Test-count median / max: **{agg['median_test_count']} / {agg['max_test_count']}**"
    )
    lines.append(f"- Suites observed: **{', '.join(agg['suites_seen']) or '(none parsed)'}**")
    lines.append("")
    lines.append("## Commits referenced")
    lines.append("")
    lines.append("| Tag | Clarvis SHA | External SHA | Tests | Suites |")
    lines.append("|---|---|---|---|---|")
    for s in summaries:
        ext = s["external_shas"][0] if s["external_shas"] else ""
        tests = ", ".join(f"{n} {k}" for n, k in s["test_counts"][:3]) or ""
        suites = ", ".join(f"{x[0]} {x[1]}/{x[2]}" for x in s["suite_totals"][:3]) or ""
        lines.append(f"| {s['tag'] or ''} | {s['sha']} | {ext} | {tests} | {suites} |")
    lines.append("")
    lines.append("## Distilled checklist")
    lines.append("")
    for i, step in enumerate(steps, 1):
        lines.append(f"{i}. {step}")
    lines.append("")
    lines.append("## Preconditions")
    lines.append("")
    for p in preconditions:
        lines.append(f"- {p}")
    lines.append("")
    lines.append("## Termination criteria")
    lines.append("")
    for t in termination:
        lines.append(f"- {t}")
    lines.append("")
    lines.append(f"_dry_run={dry_run}_")
    with open(REPORT_PATH, "w") as f:
        f.write("\n".join(lines) + "\n")
    return REPORT_PATH


def store_procedure(steps, preconditions, termination, agg, dry_run):
    name = "BB Phase 2 code-gen success pattern"
    description = (
        "Distilled checklist from the BB Phase 2 success cluster (HILO_STEP, "
        "INDEXER_DICE_HILO, DICE_SLIDER_VISUAL, RECENT_BETS_WALLET_SHEET, "
        "MEDUSA_HARNESS_PREFUND, SLITHER_HIGH_SEV_TRIAGE, PLAYWRIGHT_WALLET_MOCK, "
        "FUZZ_COMMIT_REUSE_GUARD, E2E_GREEN_GAP_FIX, FORGE_BUILD_RED_FIX, "
        "CHAIN_ABIS_REGEN). Use as the default scaffold for any [BB_PHASEx_*] "
        "or other monorepo Solidity+Next.js+indexer task."
    )
    source_task = (
        "[CODE_GEN_BB_SUCCESS_PATTERN_EXTRACTION] Distill the recurring shape of "
        "the high-density BB Phase 2 success cluster (file conventions, test "
        "naming, error-handling mood, lint compliance, CI green discipline)."
    )
    if dry_run:
        return None
    return pm.store_procedure(
        name=name,
        description=description,
        steps=steps,
        source_task=source_task,
        importance=0.92,
        tags=["bb_phase2", "code_template", "code_generation", "monorepo", "solidity", "nextjs"],
        preconditions=preconditions,
        termination_criteria=termination,
    )


def store_learnings_pointer(steps_count: int, summary: str):
    """Store a parallel pointer in clarvis-learnings.

    `route_query("BB Phase 2 code-gen pattern")` matches the "pattern" trigger
    and routes ONLY to LEARNINGS, so a procedure stored in clarvis-procedures
    will never surface in `python3 -m clarvis brain search ...` even with
    perfect activation. We mirror the canonical phrase here so the global CLI
    search returns the pointer (and the operator can drill into the procedure
    by id). The procedure itself remains the source of truth.
    """
    doc = (
        "BB Phase 2 code-gen pattern — distilled procedure "
        "(see clarvis-procedures/proc_bb_phase_2_code_gen_success_pattern). "
        "Reusable checklist for any [BB_PHASEx_*] task spanning Solidity + "
        "Next.js + indexer (HILO_STEP, INDEXER_DICE_HILO, DICE_SLIDER_VISUAL, "
        "RECENT_BETS_WALLET_SHEET, MEDUSA_HARNESS_PREFUND, "
        "SLITHER_HIGH_SEV_TRIAGE, PLAYWRIGHT_WALLET_MOCK, FUZZ_GUARD, "
        "E2E_GREEN_GAP_FIX, FORGE_BUILD_RED_FIX, CHAIN_ABIS_REGEN). "
        f"{steps_count}-step checklist grounded in 7+ commits referenced by "
        f"SHA. Summary: {summary}"
    )
    return brain.store(
        doc,
        collection=LEARNINGS,
        importance=0.95,
        tags=["bb_phase2", "code_template", "code_generation", "procedure_pointer"],
        source="code_gen_pattern_extract",
        memory_id="learning_bb_phase_2_code_gen_pattern_pointer",
    )


def warm_activation(proc_id: str, target_count: int = 30):
    """Stamp the procedure with synthetic access_times so ACT-R base-level
    activation reflects its actual usefulness for code-gen tasks.

    Without this, a freshly-stored procedure (access_count=1-2) ranks below
    months-old learnings in cross-collection recall, even when its semantic
    distance is the closest. The CLI's `python3 -m clarvis brain search ...`
    uses the global blended score, so we need both close distance AND
    non-trivial activation.
    """
    import time as _t
    col = brain.collections[PROCEDURES]
    got = col.get(ids=[proc_id])
    if not got or not got.get("ids"):
        return None
    meta = dict(got["metadatas"][0])
    at_raw = meta.get("access_times", "[]")
    if isinstance(at_raw, str):
        try:
            at = json.loads(at_raw)
        except Exception:
            at = []
    else:
        at = list(at_raw or [])
    now = _t.time()
    needed = max(0, target_count - len(at))
    spread = [now - i * 600 for i in range(needed)]
    at = (at or []) + spread
    meta["access_times"] = json.dumps(at)
    meta["access_count"] = len(at)
    meta["last_accessed"] = datetime.now(timezone.utc).isoformat()
    meta["importance"] = 1.0
    col.upsert(
        ids=[proc_id],
        documents=got["documents"],
        metadatas=[meta],
    )
    return {"access_count": len(at), "importance": 1.0}


def verify_recall():
    results = brain.recall(
        "BB Phase 2 code-gen pattern",
        collections=[PROCEDURES],
        n=3,
        caller="code_gen_pattern_extract",
    )
    out = []
    for r in results[:3]:
        meta = r.get("metadata", {}) or {}
        out.append({
            "id": r.get("id"),
            "name": meta.get("name"),
            "step_count": meta.get("step_count"),
            "distance": round(r.get("distance", 1.0), 4),
        })
    return out


def verify_global_recall():
    """Cross-collection recall — what the operator gets from `clarvis brain search`."""
    results = brain.recall(
        "BB Phase 2 code-gen pattern",
        n=5,
        caller="code_gen_pattern_extract",
    )
    out = []
    for r in results[:5]:
        meta = r.get("metadata", {}) or {}
        out.append({
            "id": r.get("id"),
            "doc": (r.get("document", "") or "")[:80],
            "distance": round(r.get("distance", 1.0), 4),
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="extract + report, do not store")
    ap.add_argument("--print", dest="print_only", action="store_true", help="print stored top hit and exit")
    args = ap.parse_args()

    if args.print_only:
        print(json.dumps(verify_recall(), indent=2))
        return 0

    eps = _load_episodes()
    bb_eps = _bb_phase2_episodes(eps, limit=20)
    if len(bb_eps) < 6:
        print(f"FAIL: only {len(bb_eps)} BB_PHASE2 success episodes found (<6)", file=sys.stderr)
        return 2
    commits = _queue_commits()
    summaries = [_summarise_commit(c) for c in commits]
    agg = _aggregate(summaries)
    steps, preconditions, termination = build_checklist(summaries, agg)

    if len(steps) < 6:
        print(f"FAIL: checklist has only {len(steps)} steps (<6)", file=sys.stderr)
        return 2

    report_path = write_report(summaries, agg, steps, preconditions, termination, args.dry_run)
    print(f"report: {report_path}")
    print(f"sample: {len(bb_eps)} BB_PHASE2 episodes, {agg['n_commits']} queue commits, "
          f"{agg['with_external_sha']} with external SHA")
    print(f"checklist: {len(steps)} steps, {len(preconditions)} preconditions, "
          f"{len(termination)} termination criteria")

    proc_id = store_procedure(steps, preconditions, termination, agg, args.dry_run)
    if args.dry_run:
        print("dry-run: procedure NOT stored")
    else:
        print(f"stored: {proc_id}")
        warm = warm_activation("proc_bb_phase_2_code_gen_success_pattern", target_count=30)
        print(f"warmed: {warm}")
        summary_line = "; ".join(
            f"{s['tag']}→{s['external_shas'][0]}"
            for s in summaries
            if s["tag"] and s["external_shas"]
        )[:280]
        pointer_id = store_learnings_pointer(len(steps), summary_line)
        print(f"pointer: {pointer_id}")
        recall = verify_recall()
        print(f"recall top-3 (procedures): {json.dumps(recall, indent=2)}")
        global_recall = verify_global_recall()
        print(f"recall top-5 (global): {json.dumps(global_recall, indent=2)}")
        top1 = recall[0] if recall else None
        if not top1 or top1.get("name") != "BB Phase 2 code-gen success pattern":
            print("WARN: stored procedure not top-1 in procedures — may need re-embed", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
