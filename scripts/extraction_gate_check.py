#!/usr/bin/env python3
"""Extraction gate checker — machine-readable readiness verification.

Checks whether clarvis-db and clarvis-p meet the hard gates defined in
docs/EXTRACTION_GATES.md before extraction into standalone repos.

Usage:
    python3 scripts/extraction_gate_check.py               # Full report
    python3 scripts/extraction_gate_check.py --gate tests   # Single gate
    python3 scripts/extraction_gate_check.py --package clarvis-db  # Single package
    python3 scripts/extraction_gate_check.py --json         # JSON output
"""

import argparse
import importlib
import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Gate result types
# ---------------------------------------------------------------------------

@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""

@dataclass
class GateResult:
    gate: str
    hard: bool
    checks: list = field(default_factory=list)

    @property
    def passed(self):
        return all(c.passed for c in self.checks)

    @property
    def status(self):
        if self.passed:
            return "PASS"
        if any(c.passed for c in self.checks):
            return "PARTIAL"
        return "FAIL"


# ---------------------------------------------------------------------------
# Gate 1: Consumer Demand
# ---------------------------------------------------------------------------

def check_consumer_demand(package: str) -> GateResult:
    """Count distinct repos importing the package's public surface."""
    gate = GateResult(gate="consumer-demand", hard=True)

    # We can only check within this repo — external consumers need manual audit
    if package == "clarvis-db":
        search_patterns = ["from clarvis.brain import", "from clarvis_db import"]
    elif package == "clarvis-p":
        search_patterns = ["from clarvis.context.assembly import", "from clarvis_p import"]
    else:
        gate.checks.append(Check("unknown-package", False, f"Unknown package: {package}"))
        return gate

    # Count internal consumers (always 1 — the main repo)
    gate.checks.append(Check(
        "internal-consumer",
        True,
        "clarvis main repo is consumer #1",
    ))
    gate.checks.append(Check(
        "external-consumer",
        False,
        "No known external consumer. Need 2+ total consumers for extraction.",
    ))
    return gate


# ---------------------------------------------------------------------------
# Gate 2: API Stability
# ---------------------------------------------------------------------------

def check_api_stability(package: str) -> GateResult:
    gate = GateResult(gate="api-stability", hard=True)

    # Boundary doc exists?
    if package == "clarvis-db":
        doc = WORKSPACE / "docs" / "CLARVISDB_API_BOUNDARY.md"
    elif package == "clarvis-p":
        doc = WORKSPACE / "docs" / "CLARVISP_API_BOUNDARY.md"
    else:
        gate.checks.append(Check("unknown", False, f"Unknown: {package}"))
        return gate

    gate.checks.append(Check(
        "boundary-doc-exists",
        doc.exists(),
        str(doc) if doc.exists() else f"Missing: {doc}",
    ))

    # Public symbols exported?
    if package == "clarvis-db":
        try:
            mod = importlib.import_module("clarvis.brain")
            required = {"get_brain", "remember", "search", "capture"}
            exported = set(dir(mod))
            missing = required - exported
            gate.checks.append(Check(
                "public-symbols-exist",
                len(missing) == 0,
                f"Missing: {missing}" if missing else "All 4 core symbols present",
            ))
        except ImportError as e:
            gate.checks.append(Check("public-symbols-exist", False, str(e)))
    elif package == "clarvis-p":
        try:
            mod = importlib.import_module("clarvis.context.assembly")
            required = {"generate_tiered_brief", "build_decision_context",
                        "get_adjusted_budgets", "dycp_prune_brief"}
            exported = set(dir(mod))
            missing = required - exported
            gate.checks.append(Check(
                "public-symbols-exist",
                len(missing) == 0,
                f"Missing: {missing}" if missing else "All 4 core symbols present",
            ))
        except ImportError as e:
            gate.checks.append(Check("public-symbols-exist", False, str(e)))

    # Check for TODOs/HACKs in public surface
    if package == "clarvis-db":
        surface_files = list((WORKSPACE / "clarvis" / "brain").glob("*.py"))
    elif package == "clarvis-p":
        surface_files = list((WORKSPACE / "clarvis" / "context").glob("*.py"))
    else:
        surface_files = []

    todo_count = 0
    for f in surface_files:
        content = f.read_text(errors="ignore")
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") and any(tag in stripped.upper() for tag in ["TODO", "HACK", "FIXME"]):
                todo_count += 1

    gate.checks.append(Check(
        "no-todos-in-public-surface",
        todo_count == 0,
        f"{todo_count} TODO/HACK/FIXME comments found" if todo_count else "Clean",
    ))

    return gate


# ---------------------------------------------------------------------------
# Gate 3: Test Coverage
# ---------------------------------------------------------------------------

def check_tests(package: str) -> GateResult:
    gate = GateResult(gate="tests", hard=True)

    if package == "clarvis-db":
        # Package-level tests
        pkg_tests = WORKSPACE / "packages" / "clarvis-db" / "tests"
        has_pkg_tests = pkg_tests.exists() and list(pkg_tests.glob("test_*.py"))
        gate.checks.append(Check(
            "package-tests-exist",
            bool(has_pkg_tests),
            f"{len(has_pkg_tests)} test files" if has_pkg_tests else "No test files found",
        ))

        # Contract parity (fork merge smoke tests)
        smoke = WORKSPACE / "tests" / "test_fork_merge_smoke.py"
        gate.checks.append(Check(
            "contract-parity-tests",
            smoke.exists(),
            "test_fork_merge_smoke.py exists" if smoke.exists() else "Missing smoke tests",
        ))

    elif package == "clarvis-p":
        # No dedicated test suite for clarvis-p
        gate.checks.append(Check(
            "package-tests-exist",
            False,
            "No dedicated clarvis-p test suite exists",
        ))
        smoke = WORKSPACE / "tests" / "test_fork_merge_smoke.py"
        gate.checks.append(Check(
            "contract-parity-tests",
            smoke.exists(),
            "Assembly surface tested in smoke tests" if smoke.exists() else "Missing",
        ))

    return gate


# ---------------------------------------------------------------------------
# Gate 4: Documentation Honesty
# ---------------------------------------------------------------------------

def check_docs(package: str) -> GateResult:
    gate = GateResult(gate="docs", hard=False)

    if package == "clarvis-db":
        readme = WORKSPACE / "packages" / "clarvis-db" / "README.md"
        gate.checks.append(Check(
            "readme-exists",
            readme.exists(),
            str(readme) if readme.exists() else "No README",
        ))

        if readme.exists():
            content = readme.read_text(errors="ignore").lower()
            aspirational = ["coming soon", "planned", "future", "will be", "not yet"]
            found = [p for p in aspirational if p in content]
            gate.checks.append(Check(
                "no-aspirational-claims",
                len(found) == 0,
                f"Aspirational phrases found: {found}" if found else "No aspirational claims",
            ))
        else:
            gate.checks.append(Check("no-aspirational-claims", False, "No README to check"))

    elif package == "clarvis-p":
        gate.checks.append(Check("readme-exists", False, "No clarvis-p package exists"))

    return gate


# ---------------------------------------------------------------------------
# Gate 5: Low Bloat
# ---------------------------------------------------------------------------

def check_bloat(package: str) -> GateResult:
    gate = GateResult(gate="bloat", hard=False)

    if package == "clarvis-db":
        pkg_dir = WORKSPACE / "packages" / "clarvis-db" / "clarvis_db"
        py_files = [f for f in pkg_dir.glob("*.py") if not f.name.startswith("__")]
        gate.checks.append(Check(
            "file-count-under-15",
            len(py_files) < 15,
            f"{len(py_files)} Python source files",
        ))

        # Check pyproject.toml for deps
        pyproject = WORKSPACE / "packages" / "clarvis-db" / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            # Count lines in dependencies section (rough)
            in_deps = False
            dep_count = 0
            for line in content.splitlines():
                if "dependencies" in line and "=" in line:
                    in_deps = True
                    continue
                if in_deps:
                    if line.strip().startswith("]"):
                        in_deps = False
                    elif line.strip() and not line.strip().startswith("#"):
                        dep_count += 1
            gate.checks.append(Check(
                "deps-under-5",
                dep_count < 5,
                f"{dep_count} runtime dependencies",
            ))
        else:
            gate.checks.append(Check("deps-under-5", False, "No pyproject.toml"))

    elif package == "clarvis-p":
        gate.checks.append(Check("file-count-under-15", True, "No package exists (0 files)"))

    return gate


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

GATE_FUNCS = {
    "consumer-demand": check_consumer_demand,
    "api-stability": check_api_stability,
    "tests": check_tests,
    "docs": check_docs,
    "bloat": check_bloat,
}

PACKAGES = ["clarvis-db", "clarvis-p"]


def run_all(packages=None, gates=None):
    packages = packages or PACKAGES
    gates = gates or list(GATE_FUNCS.keys())

    results = {}
    for pkg in packages:
        results[pkg] = {}
        for gate_name in gates:
            if gate_name in GATE_FUNCS:
                results[pkg][gate_name] = GATE_FUNCS[gate_name](pkg)
    return results


def print_report(results):
    for pkg, gates in results.items():
        print(f"\n{'='*60}")
        print(f"  {pkg.upper()}")
        print(f"{'='*60}")

        all_hard_pass = True
        for gate_name, gate in gates.items():
            marker = "HARD" if gate.hard else "SOFT"
            status = gate.status
            icon = {"PASS": "+", "PARTIAL": "~", "FAIL": "-"}[status]
            print(f"\n  [{icon}] Gate: {gate_name} ({marker}) — {status}")
            for check in gate.checks:
                c_icon = "+" if check.passed else "-"
                print(f"      [{c_icon}] {check.name}: {check.detail}")
            if gate.hard and not gate.passed:
                all_hard_pass = False

        verdict = "READY" if all_hard_pass else "NOT READY"
        blockers = [g for g, r in gates.items() if r.hard and not r.passed]
        blocker_str = f" — blocked on: {', '.join(blockers)}" if blockers else ""
        print(f"\n  VERDICT: {verdict}{blocker_str}")
    print()


def print_json(results):
    out = {}
    for pkg, gates in results.items():
        out[pkg] = {
            "verdict": "READY" if all(g.passed for g in gates.values() if g.hard) else "NOT_READY",
            "gates": {
                name: {
                    "status": gate.status,
                    "hard": gate.hard,
                    "checks": [asdict(c) for c in gate.checks],
                }
                for name, gate in gates.items()
            },
        }
    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Extraction gate checker")
    parser.add_argument("--gate", choices=list(GATE_FUNCS.keys()), help="Check single gate")
    parser.add_argument("--package", choices=PACKAGES, help="Check single package")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    packages = [args.package] if args.package else None
    gates = [args.gate] if args.gate else None

    results = run_all(packages=packages, gates=gates)

    if args.json:
        print_json(results)
    else:
        print_report(results)

    # Exit 1 if any hard gate fails
    for pkg_gates in results.values():
        for gate in pkg_gates.values():
            if gate.hard and not gate.passed:
                sys.exit(1)


if __name__ == "__main__":
    main()
