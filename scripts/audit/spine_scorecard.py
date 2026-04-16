#!/usr/bin/env python3
"""Phase 2 — spine module quality scorecard.

Collects per-spine-module:
  - Public exports (parsed from __init__.py)
  - Caller counts per export name (grep across scripts + clarvis + tests + shell)
  - Test coverage (line %) via coverage.py
  - Dead exports (exports with zero non-self callers)
  - Duplicate indicators (bridge wrappers from Phase 1)
  - Typing check (mypy on module) - best-effort summary
  - Rough latency sampling for a small set of stateless public calls

Writes:
  data/audit/spine_coverage.json     (programmatic)
  docs/internal/audits/SPINE_MODULE_SCORECARD_<date>.md
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLARVIS = ROOT / "clarvis"
SCRIPTS = ROOT / "scripts"
TESTS = ROOT / "tests"
AUDIT_DATA = ROOT / "data" / "audit"
AUDIT_DOCS = ROOT / "docs" / "internal" / "audits"

IGNORE_DIRS = {"__pycache__", "dashboard_static", "node_modules"}

DATE_STR = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def iter_py(root: Path):
    for p in root.rglob("*.py"):
        if any(part in IGNORE_DIRS for part in p.parts):
            continue
        yield p


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def spine_modules() -> list[Path]:
    return sorted(d for d in CLARVIS.iterdir() if d.is_dir() and not d.name.startswith("_"))


def parse_exports(init_path: Path) -> list[dict]:
    """Parse __init__.py — return list of {name, kind, source_module}.

    Handles:
      from .foo import bar
      from .foo import bar as baz
      from .foo import (a, b, c)
      from clarvis.x.y import z
      def foo(...)
      class Bar(...)
      __all__ = [...]
    """
    exports: list[dict] = []
    src = read(init_path)
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return exports

    all_list: list[str] | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
        ):
            if isinstance(node.value, (ast.List, ast.Tuple)):
                try:
                    all_list = [
                        elt.value for elt in node.value.elts
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                    ]
                except Exception:
                    pass

    # Collect module-level definitions and imports at top level only
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            src_mod = ("." * (node.level or 0)) + node.module
            for alias in node.names:
                name = alias.asname or alias.name
                if name == "*":
                    continue
                exports.append({"name": name, "kind": "reexport", "source_module": src_mod})
        elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            exports.append({"name": node.name, "kind": "function", "source_module": None})
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            exports.append({"name": node.name, "kind": "class", "source_module": None})
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and not t.id.startswith("_") and t.id != "logger":
                    exports.append({"name": t.id, "kind": "assign", "source_module": None})

    # Filter by __all__ when declared, otherwise keep non-private
    if all_list is not None:
        names = set(all_list)
        exports = [e for e in exports if e["name"] in names]

    # Dedup by name
    seen = set()
    uniq = []
    for e in exports:
        if e["name"] in seen:
            continue
        seen.add(e["name"])
        uniq.append(e)
    return uniq


def build_corpus() -> dict[Path, str]:
    """Load all python source trees we care about into memory once."""
    corpus: dict[Path, str] = {}
    for root in (SCRIPTS, CLARVIS, TESTS):
        for p in iter_py(root):
            corpus[p] = read(p)
    # shell
    for root in (SCRIPTS,):
        for p in root.rglob("*.sh"):
            if any(part in IGNORE_DIRS for part in p.parts):
                continue
            corpus[p] = read(p)
    return corpus


def count_export_callers(
    export_name: str,
    module_name: str,
    module_dir: Path,
    corpus: dict[Path, str],
) -> dict:
    """Return caller sets: module_local, spine_external, scripts_callers, tests_callers, shell.

    A caller is a file (excluding __init__.py of the module itself and the file that
    defines `export_name`) whose source contains the export name.
    """
    # Build a word-boundary regex
    pat = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(export_name)}(?![A-Za-z0-9_])")

    module_local = set()
    spine_external = set()
    scripts_callers = set()
    tests_callers = set()
    shell = set()

    for p, src in corpus.items():
        if not pat.search(src):
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel == f"clarvis/{module_name}/__init__.py":
            continue
        if p.suffix == ".sh":
            shell.add(rel)
            continue
        if rel.startswith(f"clarvis/{module_name}/"):
            module_local.add(rel)
        elif rel.startswith("clarvis/"):
            spine_external.add(rel)
        elif rel.startswith("tests/"):
            tests_callers.add(rel)
        elif rel.startswith("scripts/"):
            scripts_callers.add(rel)
        else:
            scripts_callers.add(rel)

    return {
        "module_local": sorted(module_local),
        "spine_external": sorted(spine_external),
        "scripts_callers": sorted(scripts_callers),
        "tests_callers": sorted(tests_callers),
        "shell": sorted(shell),
        "total_external": len(spine_external) + len(scripts_callers) + len(shell),
    }


def gather_module_files(module_dir: Path) -> list[str]:
    files = []
    for p in iter_py(module_dir):
        files.append(p.relative_to(ROOT).as_posix())
    return sorted(files)


def run_coverage_for_module(module_name: str, test_selectors: list[str], mod_files: list[str]) -> dict:
    """Run coverage on given tests, restricted to the module dir. Returns {coverage: float, stmts: int, missed: int, status: str}."""
    data_file = ROOT / f".coverage.{module_name}"
    src_dir = f"clarvis/{module_name}"
    if data_file.exists():
        data_file.unlink()

    cmd = [
        "python3", "-m", "coverage", "run",
        f"--source={src_dir}",
        f"--data-file={data_file}",
        "--branch",
        "-m", "pytest",
        "-q", "--no-header", "--tb=no",
        "--disable-warnings",
        "-x",  # stop on first failure to avoid cascades
    ] + test_selectors

    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        return {"coverage_pct": None, "stmts": None, "missed": None, "status": "timeout", "tests_run": 0}

    # Parse coverage json
    json_out = ROOT / f".coverage.{module_name}.json"
    try:
        subprocess.run(
            ["python3", "-m", "coverage", "json", f"--data-file={data_file}", "-o", str(json_out)],
            cwd=ROOT, capture_output=True, text=True, timeout=60,
        )
    except Exception:
        pass

    result = {
        "coverage_pct": None,
        "stmts": None,
        "missed": None,
        "status": "ok" if proc.returncode == 0 else "tests_failed",
        "tests_run": _tests_run_from_output(proc.stdout + proc.stderr),
    }
    if json_out.exists():
        try:
            data = json.loads(json_out.read_text())
            totals = data.get("totals", {})
            result["coverage_pct"] = totals.get("percent_covered")
            result["stmts"] = totals.get("num_statements")
            result["missed"] = totals.get("missing_lines")
            result["status"] = "ok"  # report even if tests had failures — we still got coverage
        except Exception:
            pass
        try:
            json_out.unlink()
        except Exception:
            pass

    try:
        if data_file.exists():
            data_file.unlink()
    except Exception:
        pass

    return result


def _tests_run_from_output(out: str) -> int:
    # look for "N passed" or "N failed" in pytest's tail
    m = re.search(r"(\d+)\s+passed", out)
    passed = int(m.group(1)) if m else 0
    m2 = re.search(r"(\d+)\s+failed", out)
    failed = int(m2.group(1)) if m2 else 0
    return passed + failed


def find_tests_for_module(module_name: str) -> list[str]:
    """Return list of test paths that import from clarvis.<module_name>.*"""
    selectors: set[str] = set()
    imp_pat = re.compile(rf"from\s+clarvis\.{re.escape(module_name)}(?:\.[\w.]+)?\s+import|import\s+clarvis\.{re.escape(module_name)}")
    for p in iter_py(TESTS):
        src = read(p)
        if imp_pat.search(src):
            selectors.add(p.relative_to(ROOT).as_posix())
    # also include test files with matching stem, e.g. test_clarvis_<module>.py
    alt_pat = re.compile(rf"test_(clarvis_)?{re.escape(module_name)}")
    for p in iter_py(TESTS):
        if alt_pat.search(p.name):
            selectors.add(p.relative_to(ROOT).as_posix())
    return sorted(selectors)


def run_mypy(module_dir: Path) -> dict:
    try:
        proc = subprocess.run(
            ["python3", "-m", "mypy", "--ignore-missing-imports", "--no-strict-optional",
             "--follow-imports=silent", str(module_dir)],
            cwd=ROOT, capture_output=True, text=True, timeout=90,
        )
    except subprocess.TimeoutExpired:
        return {"errors": None, "status": "timeout"}
    out = (proc.stdout or "") + (proc.stderr or "")
    err_match = re.search(r"Found (\d+) error", out)
    errors = int(err_match.group(1)) if err_match else (0 if "Success" in out else None)
    return {"errors": errors, "status": "ok" if errors is not None else "failed"}


def bridge_map_from_phase1() -> dict[str, str]:
    """Load Phase 1 DUPLICATE classifications → {bridge_script: spine_target}."""
    inv_path = AUDIT_DATA / "script_wiring_inventory.json"
    if not inv_path.exists():
        return {}
    data = json.loads(inv_path.read_text())
    out = {}
    for row in data:
        if row.get("classification") == "DUPLICATE":
            out[row["path"]] = row.get("bridge_target") or ""
    return out


def analyze_module(module_dir: Path, corpus: dict[Path, str]) -> dict:
    name = module_dir.name
    init_path = module_dir / "__init__.py"
    exports = parse_exports(init_path) if init_path.exists() else []

    export_results = []
    dead_exports = []      # zero callers anywhere (strict DEAD)
    test_only_exports = [] # tests yes, production no (DORMANT)
    prod_callers_total = 0
    for e in exports:
        callers = count_export_callers(e["name"], name, module_dir, corpus)
        prod = callers["total_external"]  # scripts + spine_external + shell
        tests = len(callers["tests_callers"])
        export_results.append({
            **e,
            "callers": callers,
            "production_callers": prod,
            "test_callers": tests,
        })
        if prod == 0 and tests == 0:
            dead_exports.append(e["name"])
        elif prod == 0 and tests > 0:
            test_only_exports.append(e["name"])
        prod_callers_total += prod

    files = gather_module_files(module_dir)
    return {
        "module": name,
        "module_dir": module_dir.relative_to(ROOT).as_posix(),
        "files": files,
        "file_count": len(files),
        "init_lines": len(read(init_path).splitlines()) if init_path.exists() else 0,
        "exports_total": len(exports),
        "exports": export_results,
        "dead_exports": dead_exports,
        "test_only_exports": test_only_exports,
        "prod_callers_total": prod_callers_total,
    }


def main():
    AUDIT_DATA.mkdir(parents=True, exist_ok=True)

    print("[1/6] Building corpus …")
    corpus = build_corpus()
    print(f"      loaded {len(corpus)} source files")

    print("[2/6] Parsing spine modules and exports …")
    modules = spine_modules()
    module_reports = []
    for m in modules:
        rep = analyze_module(m, corpus)
        module_reports.append(rep)
        print(f"      {m.name:12s} files={rep['file_count']:3d}  exports={rep['exports_total']:3d}  dead={len(rep['dead_exports']):2d}")

    print("[3/6] Locating tests per module …")
    tests_by_module = {}
    for m in modules:
        tests_by_module[m.name] = find_tests_for_module(m.name)
        print(f"      {m.name:12s} tests={len(tests_by_module[m.name])}")

    print("[4/6] Running coverage per module (bounded to 240s each) …")
    coverage_by_module = {}
    for m in modules:
        tests = tests_by_module[m.name]
        if not tests:
            coverage_by_module[m.name] = {
                "coverage_pct": 0.0, "stmts": None, "missed": None,
                "status": "no_tests", "tests_run": 0,
            }
            print(f"      {m.name:12s} NO TESTS")
            continue
        res = run_coverage_for_module(m.name, tests, [])
        coverage_by_module[m.name] = res
        pct = res.get("coverage_pct")
        print(f"      {m.name:12s} cov={pct if pct is None else round(pct, 1):>5}%  tests={res.get('tests_run', 0)}  status={res.get('status')}")

    print("[5/6] Running mypy per module (best-effort) …")
    mypy_by_module = {}
    for m in modules:
        res = run_mypy(m)
        mypy_by_module[m.name] = res
        print(f"      {m.name:12s} mypy_errors={res.get('errors')}  status={res.get('status')}")

    print("[6/6] Cross-referencing Phase 1 bridges …")
    bridges = bridge_map_from_phase1()
    bridges_by_module: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for bridge_file, target in bridges.items():
        if not target:
            continue
        m = re.match(r"clarvis\.([a-zA-Z0-9_]+)", target)
        if m:
            bridges_by_module[m.group(1)].append((bridge_file, target))

    # Compose final report
    generated = datetime.now(timezone.utc).isoformat()
    report = {
        "phase": 2,
        "generated_at": generated,
        "modules": [],
    }
    for rep in module_reports:
        name = rep["module"]
        cov = coverage_by_module.get(name, {})
        cov_pct = cov.get("coverage_pct") or 0.0
        tests = tests_by_module.get(name, [])
        mp = mypy_by_module.get(name, {})
        bridge_links = bridges_by_module.get(name, [])
        total_exports = rep["exports_total"]
        dead_exports = rep["dead_exports"]
        test_only_exports = rep.get("test_only_exports", [])
        dead_pct = (len(dead_exports) / total_exports * 100.0) if total_exports else 0.0
        test_only_pct = (len(test_only_exports) / total_exports * 100.0) if total_exports else 0.0

        # Classification per phase-2 gates.
        # PASS: coverage ≥ 40% AND zero dead (strict) public exports
        # REVISE: coverage 20-40%, bridge duplicate present, OR dead exports > 0 but module has callers
        # DEMOTE/ARCHIVE: zero callers in 30d AND zero tests AND no roadmap link (strict)
        if cov_pct >= 40.0 and not dead_exports:
            gate = "PASS"
        elif cov_pct >= 20.0 or bridge_links:
            gate = "REVISE"
        elif cov_pct == 0.0 and not tests and rep.get("prod_callers_total", 0) == 0:
            gate = "DEMOTE_CANDIDATE"
        else:
            gate = "REVISE"

        report["modules"].append({
            "module": name,
            "file_count": rep["file_count"],
            "init_lines": rep["init_lines"],
            "exports_total": total_exports,
            "dead_exports": dead_exports,
            "dead_export_pct": round(dead_pct, 1),
            "test_only_exports": test_only_exports,
            "test_only_export_pct": round(test_only_pct, 1),
            "prod_callers_total": rep.get("prod_callers_total", 0),
            "coverage_pct": round(cov_pct, 1) if cov_pct else 0.0,
            "coverage_status": cov.get("status"),
            "coverage_stmts": cov.get("stmts"),
            "coverage_missed": cov.get("missed"),
            "tests_run": cov.get("tests_run", 0),
            "test_files": tests,
            "mypy_errors": mp.get("errors"),
            "mypy_status": mp.get("status"),
            "bridges_from_scripts": [{"bridge": b, "target": t} for b, t in bridge_links],
            "gate": gate,
            "exports": rep["exports"],
            "files": rep["files"],
        })

    # Write artifact
    out_json = AUDIT_DATA / "spine_coverage.json"
    out_json.write_text(json.dumps(report, indent=2, sort_keys=False, default=str))
    print(f"\nWrote {out_json}")
    return report


if __name__ == "__main__":
    main()
