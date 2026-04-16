#!/usr/bin/env python3
"""Phase 1 wiring inventory — pure-Python static analysis.

Walks scripts/ + clarvis/, builds a file corpus, then for every target
file determines: importers (spine/relative/script_loader/subprocess),
cron refs (shell + jobs.json + live crontab), and tests. Classifies as
ALIVE / DORMANT / DUPLICATE / DEAD.

Output: CSV under docs/internal/audits/ + JSON under data/audit/.
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
CLARVIS = ROOT / "clarvis"
TESTS = ROOT / "tests"
OPENCLAW_JOBS = Path("/home/agent/.openclaw/cron/jobs.json")
CRONTAB_REFERENCE = SCRIPTS / "crontab.reference"

IGNORE_DIRS = {"__pycache__", "dashboard_static", "node_modules"}


def iter_py(root: Path):
    for p in root.rglob("*.py"):
        if any(part in IGNORE_DIRS for part in p.parts):
            continue
        yield p


def iter_sh(root: Path):
    for p in root.rglob("*.sh"):
        if any(part in IGNORE_DIRS for part in p.parts):
            continue
        yield p


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def git_last_commit_date(p: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "log", "-1", "--format=%ad", "--date=short", "--",
             str(p.relative_to(ROOT))],
            cwd=str(ROOT),
            stderr=subprocess.DEVNULL,
            timeout=10,
        ).decode().strip()
        return out or ""
    except Exception:
        return ""


def days_since(date_str: str) -> int:
    if not date_str:
        return 9999
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return 9999


def dotted_module(py: Path) -> str | None:
    if not py.is_relative_to(CLARVIS):
        return None
    parts = py.relative_to(ROOT).with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else None


BRIDGE_MARKERS = ("# Bridge", "# Wrapper", "# Delegate", "# Re-export", "# Shim",
                  "delegates to", "re-exports")


def is_bridge_wrapper(py: Path, txt: str) -> tuple[bool, str]:
    if not py.is_relative_to(SCRIPTS):
        return False, ""
    if len(txt) > 8000:
        return False, ""
    imps = re.findall(r"from\s+(clarvis\.[a-zA-Z0-9_\.]+)\s+import", txt)
    if not imps:
        return False, ""
    # heuristic: short file re-exporting from clarvis.* counts as a bridge
    n_lines = txt.count("\n")
    has_marker = any(m.lower() in txt.lower() for m in BRIDGE_MARKERS)
    if has_marker or n_lines <= 150:
        return True, imps[0]
    return False, ""


def main():
    all_py = list(iter_py(SCRIPTS)) + list(iter_py(CLARVIS))
    all_py_set = set(all_py)
    all_sh = list(iter_sh(SCRIPTS))
    all_tests = list(iter_py(TESTS))
    total = len(all_py)
    sys.stderr.write(f"Analyzing {total} Python files ({len(all_sh)} shell, {len(all_tests)} test)...\n")

    # cache file contents
    corpus_py: dict[Path, str] = {p: read(p) for p in all_py}
    corpus_sh: dict[Path, str] = {p: read(p) for p in all_sh}
    corpus_tests: dict[Path, str] = {p: read(p) for p in all_tests}

    try:
        crontab_txt = subprocess.check_output(
            ["crontab", "-l"], stderr=subprocess.DEVNULL, timeout=5
        ).decode()
    except Exception:
        crontab_txt = ""

    jobs_txt = read(OPENCLAW_JOBS) if OPENCLAW_JOBS.exists() else ""
    crontab_ref_txt = read(CRONTAB_REFERENCE) if CRONTAB_REFERENCE.exists() else ""

    rows = []
    for i, py in enumerate(all_py, 1):
        if i % 25 == 0:
            sys.stderr.write(f"  [{i}/{total}] {rel(py)}\n")

        rel_path = rel(py)
        stem = py.stem
        dotted = dotted_module(py)

        txt_self = corpus_py[py]
        bridge, bridge_target = is_bridge_wrapper(py, txt_self)

        # patterns
        pats: list[re.Pattern] = []
        # literal path reference (subprocess invocation, docs)
        pats.append(re.compile(re.escape(rel_path)))
        # filename token `stem.py` anywhere with word-ish boundary
        pats.append(re.compile(rf"\b{re.escape(stem)}\.py\b"))
        # _script_loader.load("stem") / _load_script("stem", ...) / load("stem", ...)
        pats.append(re.compile(
            rf'''(?:_script_loader\.load|_load_script|\bload)\s*\(\s*["']{re.escape(stem)}["']'''
        ))
        # bare python `import stem` / `from stem import` (scripts-only, may be inside shell heredocs)
        pats.append(re.compile(rf"(?:^|\W)import\s+{re.escape(stem)}(?:\s|,|$)"))
        pats.append(re.compile(rf"(?:^|\W)from\s+{re.escape(stem)}\s+import\b"))
        if dotted:
            esc = re.escape(dotted)
            # `import dotted`, `from dotted import ...`, `from dotted as ...`
            pats.append(re.compile(rf"(?:^|\W)import\s+{esc}(?:\s|,|$|\.)"))
            pats.append(re.compile(rf"from\s+{esc}(?:\s+import\b|\s+as\b|\.)"))
            # `from parent import stem`
            parent_parts = dotted.rsplit(".", 1)
            if len(parent_parts) == 2 and parent_parts[-1] != "__init__":
                parent, name = parent_parts
                # match `from parent import a, b, stem, c` and `from parent import (stem, ...)`
                pats.append(re.compile(
                    rf"from\s+{re.escape(parent)}\s+import[^\n(]*?\b{re.escape(name)}\b"
                ))
                pats.append(re.compile(
                    rf"from\s+{re.escape(parent)}\s+import\s*\([^)]*?\b{re.escape(name)}\b[^)]*?\)",
                    re.DOTALL,
                ))
        # relative import from sibling: `from .stem import ...` (only within same package)
        stem_rel_pat = re.compile(rf"from\s+\.{re.escape(stem)}(?:\s+import\b|\s+as\b)")
        # also `from . import stem` within same package __init__
        stem_rel_pat2 = re.compile(rf"from\s+\.\s+import[^\n(]*?\b{re.escape(stem)}\b")
        stem_rel_pat3 = re.compile(
            rf"from\s+\.\s+import\s*\([^)]*?\b{re.escape(stem)}\b[^)]*?\)",
            re.DOTALL,
        )

        # scan python corpus
        importers: set[str] = set()
        for other, other_txt in corpus_py.items():
            if other == py:
                continue
            matched = False
            for pat in pats:
                if pat.search(other_txt):
                    matched = True
                    break
            if not matched:
                # relative import: only check files in same package directory
                if py.parent == other.parent and py.name != "__init__.py":
                    if stem_rel_pat.search(other_txt) or \
                       stem_rel_pat2.search(other_txt) or \
                       stem_rel_pat3.search(other_txt):
                        matched = True
            if matched:
                importers.add(rel(other))

        # test corpus — counted separately
        tests_hits: set[str] = set()
        # explicit test_<stem>.py / <stem>_test.py
        for tp in all_tests:
            if tp.name == f"test_{stem}.py" or tp.name == f"{stem}_test.py":
                tests_hits.add(rel(tp))
        for tp, ttxt in corpus_tests.items():
            if tp in tests_hits:
                continue
            for pat in pats:
                if pat.search(ttxt):
                    tests_hits.add(rel(tp))
                    break

        # shell / cron
        cron_hits: set[str] = set()
        shell_pats = [
            re.compile(re.escape(rel_path)),
            re.compile(rf"\b{re.escape(stem)}\.py\b"),
            # python invoked inside shell heredoc
            re.compile(rf"(?:^|\W)import\s+{re.escape(stem)}(?:\s|,|$)", re.M),
            re.compile(rf"(?:^|\W)from\s+{re.escape(stem)}\s+import\b", re.M),
            # clarvis CLI subcommand references like `clarvis cognition context-relevance`
            re.compile(rf"(?:python3?\s+-m\s+clarvis|\bclarvis\b)[^\n]*?\b{re.escape(dotted.split('.')[-1]) if dotted else re.escape(stem)}\b") if dotted else None,
        ]
        shell_pats = [p for p in shell_pats if p is not None]
        for sp, stxt in corpus_sh.items():
            for pat in shell_pats:
                if pat.search(stxt):
                    cron_hits.add(rel(sp))
                    break
        # openclaw jobs.json, live crontab, crontab.reference
        for label, blob in (("openclaw:jobs.json", jobs_txt),
                             ("system:crontab", crontab_txt),
                             ("scripts/crontab.reference", crontab_ref_txt)):
            if blob and (rel_path in blob
                         or f"/{stem}.py" in blob
                         or f" {stem}.py" in blob):
                cron_hits.add(label)

        last_commit = git_last_commit_date(py)

        row = {
            "path": rel_path,
            "lines": txt_self.count("\n") + 1 if txt_self else 0,
            "importers": len(importers),
            "importer_list": ";".join(sorted(importers))[:600],
            "cron_refs": len(cron_hits),
            "cron_ref_list": ";".join(sorted(cron_hits))[:400],
            "test_files": len(tests_hits),
            "test_list": ";".join(sorted(tests_hits))[:400],
            "bridge": "yes" if bridge else "",
            "bridge_target": bridge_target,
            "last_commit": last_commit,
            "days_since_commit": days_since(last_commit),
        }

        notes: list[str] = []
        if bridge:
            notes.append(f"bridge→{bridge_target}")
        if cron_hits:
            notes.append(f"cron:{len(cron_hits)}")
        if importers:
            notes.append(f"imp:{len(importers)}")
        if tests_hits:
            notes.append(f"tests:{len(tests_hits)}")

        if cron_hits or importers:
            cls = "ALIVE"
        elif tests_hits:
            cls = "DORMANT"
        else:
            cls = "DEAD"

        # bridge wrappers in scripts/ reclassify as DUPLICATE
        if bridge and py.is_relative_to(SCRIPTS):
            cls = "DUPLICATE"
            notes.append("duplicate-by-bridge")

        row["classification"] = cls
        row["notes"] = ";".join(notes)
        rows.append(row)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_csv = ROOT / f"docs/internal/audits/SCRIPT_WIRING_INVENTORY_{today}.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    sys.stderr.write(f"\nWrote {out_csv}\n")

    out_json = ROOT / "data/audit/script_wiring_inventory.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(rows, indent=2))

    by_class = defaultdict(int)
    for r in rows:
        by_class[r["classification"]] += 1
    sys.stderr.write("\nClassification summary:\n")
    for k, v in sorted(by_class.items()):
        sys.stderr.write(f"  {k:12s} {v}\n")
    sys.stderr.write(f"  {'TOTAL':12s} {len(rows)}\n")

    # zero-caller scripts (scripts/ only) — Phase 1 gate check
    dead_scripts = [r for r in rows
                    if r["classification"] == "DEAD"
                    and r["path"].startswith("scripts/")]
    sys.stderr.write(f"\nDEAD under scripts/ ({len(dead_scripts)}):\n")
    for r in dead_scripts:
        sys.stderr.write(f"  {r['path']:62s} last={r['last_commit']}\n")

    dead_clarvis = [r for r in rows
                    if r["classification"] == "DEAD"
                    and r["path"].startswith("clarvis/")]
    sys.stderr.write(f"\nDEAD under clarvis/ ({len(dead_clarvis)}):\n")
    for r in dead_clarvis:
        sys.stderr.write(f"  {r['path']:62s} last={r['last_commit']}\n")


if __name__ == "__main__":
    main()
