#!/usr/bin/env python3
"""
Structural health check for Clarvis codebase.

Zero external dependencies — uses only Python stdlib (ast module).
Checks: circular imports, dependency depth, fan-in/fan-out, import side effects,
        sys.path patterns, import timing.

Usage:
    python3 import_health.py                  # Full report (relaxed thresholds)
    python3 import_health.py --strict         # CI gate: post-refactor thresholds, exit 1 on fail
    python3 import_health.py --side-effects   # CI gate: only check import side effects (exit 1 if >0)
    python3 import_health.py --cycles         # Circular import check only
    python3 import_health.py --depth          # Dependency depth check only
    python3 import_health.py --quick          # Quick pass/fail for heartbeat postflight
    python3 import_health.py --json           # Machine-readable JSON output
"""
import ast
import json
import sys
import os
import time
from collections import defaultdict
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = SCRIPTS_DIR.parent

# Thresholds (targets for post-refactor)
THRESHOLDS = {
    "max_scc_size": 0,          # No circular imports
    "max_depth": 5,             # Max dependency depth
    "max_fan_in": 20,           # Max times any module is imported
    "max_fan_out": 10,          # Max imports in any module
    "max_side_effects": 0,      # No import-time side effects
    "max_import_time_ms": 300,  # brain.py import time
}

# Relaxed thresholds for current state (before refactor)
THRESHOLDS_CURRENT = {
    "max_scc_size": 12,
    "max_depth": 15,
    "max_fan_in": 60,
    "max_fan_out": 30,
    "max_side_effects": 5,
    "max_import_time_ms": 600,
}


def build_import_graph(directory: Path) -> dict[str, set[str]]:
    """Build local import graph from AST analysis. Returns {module: {deps}}."""
    files = sorted(directory.glob("*.py"))
    local_modules = {f.stem for f in files}
    graph = defaultdict(set)

    for f in files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name.split(".")[0]
                    if mod in local_modules and mod != f.stem:
                        graph[f.stem].add(mod)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    mod = node.module.split(".")[0]
                    if mod in local_modules and mod != f.stem:
                        graph[f.stem].add(mod)

    # Ensure all modules appear as keys
    for f in files:
        if f.stem not in graph:
            graph[f.stem] = set()

    return dict(graph)


def find_sccs(graph: dict[str, set[str]]) -> list[list[str]]:
    """Tarjan's algorithm for strongly connected components."""
    index_counter = [0]
    stack = []
    lowlink = {}
    index = {}
    on_stack = {}
    sccs = []

    def strongconnect(v):
        index[v] = index_counter[0]
        lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack[v] = True

        for w in graph.get(v, []):
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif on_stack.get(w, False):
                lowlink[v] = min(lowlink[v], index[w])

        if lowlink[v] == index[v]:
            scc = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                scc.append(w)
                if w == v:
                    break
            if len(scc) > 1:
                sccs.append(sorted(scc))

    for v in sorted(graph.keys()):
        if v not in index:
            strongconnect(v)

    return sccs


def compute_depths(graph: dict[str, set[str]]) -> dict[str, int]:
    """Compute max dependency depth for each module (cycle-safe)."""
    depths = {}

    def _depth(node, visiting):
        if node in depths:
            return depths[node]
        if node in visiting:
            return 0  # Break cycle
        visiting.add(node)
        deps = graph.get(node, set())
        if not deps:
            depths[node] = 0
        else:
            depths[node] = 1 + max(_depth(d, visiting) for d in deps)
        visiting.discard(node)
        return depths[node]

    for node in graph:
        _depth(node, set())

    return depths


def compute_fan_in(graph: dict[str, set[str]]) -> dict[str, int]:
    """Count how many modules import each module."""
    counts = defaultdict(int)
    for deps in graph.values():
        for d in deps:
            counts[d] += 1
    return dict(counts)


def _extract_call_name(call_node: ast.Call) -> str:
    """Extract the function/class name from a Call node."""
    if isinstance(call_node.func, ast.Name):
        return call_node.func.id
    elif isinstance(call_node.func, ast.Attribute):
        return call_node.func.attr
    return ""


def detect_side_effects(directory: Path) -> list[dict]:
    """Detect modules with import-time side effects (unguarded top-level calls).

    Catches:
      1. Bare function calls: ``log("msg")``
      2. Assignment with function/class call: ``x = ClassName()`` or ``x = func()``
    Skips known-safe patterns (constructors, lazy proxies, stdlib helpers).
    """
    issues = []

    # Safe bare-call names (standalone statements)
    SAFE_CALLS = {
        "getLogger", "Path", "dirname", "abspath", "join", "resolve",
        "set", "dict", "list", "tuple", "frozenset", "defaultdict",
        "namedtuple", "dataclass", "monotonic", "time",
        "getenv", "environ", "makedirs", "insert",
        "mkdir",  # Path.mkdir() for data dirs is acceptable at module level
    }

    # Safe RHS calls in assignments (constructors that don't do I/O)
    SAFE_ASSIGN_CALLS = {
        # Stdlib / data structures
        "Path", "set", "dict", "list", "tuple", "frozenset", "defaultdict",
        "namedtuple", "OrderedDict", "deque", "Counter",
        "getLogger", "getenv", "environ", "Lock", "RLock", "Event",
        "monotonic", "time", "compile",
        # Type conversions
        "int", "str", "float", "bool", "bytes",
        # Path / string helpers (used to build constants)
        "join", "dirname", "abspath", "resolve", "expanduser", "basename",
        "get",  # dict.get / os.environ.get
        "format", "encode", "decode", "strip", "replace",
        # Lazy proxy wrappers (deferred init — no I/O on construction)
        "_LazyBrain", "_LazyWorkspace", "_LazyLocalBrain",
    }

    # Prefixes that indicate a lazy/safe pattern
    SAFE_ASSIGN_PREFIXES = ("_Lazy",)

    for f in sorted(directory.glob("*.py")):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.iter_child_nodes(tree):
            # 1. Bare function calls at module level
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                func_name = _extract_call_name(node.value)
                if func_name and func_name not in SAFE_CALLS:
                    issues.append({
                        "file": f.name,
                        "line": node.lineno,
                        "call": func_name,
                        "kind": "bare_call",
                    })

            # 2. Assignment with function/class call at module level
            #    e.g., ``singleton = ClassName()`` or ``singleton = get_thing()``
            elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                func_name = _extract_call_name(node.value)
                if not func_name:
                    continue
                # Skip safe constructors and lazy proxies
                if func_name in SAFE_ASSIGN_CALLS:
                    continue
                if any(func_name.startswith(p) for p in SAFE_ASSIGN_PREFIXES):
                    continue
                # Skip private/underscore target names that are just caching
                # (e.g., _attention = None is fine, but _attention = get_attention() is not)
                issues.append({
                    "file": f.name,
                    "line": node.lineno,
                    "call": func_name,
                    "kind": "assign_call",
                })

    return issues


def measure_import_time(module_name: str, directory: Path) -> float:
    """Measure import time of a module in milliseconds."""
    import subprocess
    result = subprocess.run(
        [sys.executable, "-c",
         f"import sys, time; sys.path.insert(0, '{directory}'); "
         f"t=time.monotonic(); import {module_name}; "
         f"print(f'{{(time.monotonic()-t)*1000:.0f}}')"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode == 0:
        try:
            return float(result.stdout.strip())
        except ValueError:
            return -1
    return -1


def full_report(graph, use_current_thresholds=True):
    """Generate full structural health report."""
    thresholds = THRESHOLDS_CURRENT if use_current_thresholds else THRESHOLDS

    sccs = find_sccs(graph)
    depths = compute_depths(graph)
    fan_in = compute_fan_in(graph)
    fan_out = {k: len(v) for k, v in graph.items() if v}
    side_effects = detect_side_effects(SCRIPTS_DIR)

    max_scc = max((len(s) for s in sccs), default=0)
    max_depth = max(depths.values(), default=0)
    max_fi = max(fan_in.values(), default=0)
    max_fo = max(fan_out.values(), default=0)

    violations = []
    if max_scc > thresholds["max_scc_size"]:
        violations.append(f"circular_imports={max_scc}")
    if max_depth > thresholds["max_depth"]:
        violations.append(f"depth={max_depth}")
    if max_fi > thresholds["max_fan_in"]:
        violations.append(f"fan_in={max_fi}")
    if max_fo > thresholds["max_fan_out"]:
        violations.append(f"fan_out={max_fo}")
    if len(side_effects) > thresholds["max_side_effects"]:
        violations.append(f"side_effects={len(side_effects)}")

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_modules": len(graph),
        "modules_with_imports": sum(1 for v in graph.values() if v),
        "leaf_modules": sum(1 for v in graph.values() if not v),
        "circular_imports": {
            "scc_count": len(sccs),
            "max_scc_size": max_scc,
            "sccs": sccs,
            "threshold": thresholds["max_scc_size"],
        },
        "dependency_depth": {
            "max": max_depth,
            "threshold": thresholds["max_depth"],
            "top_5": sorted(depths.items(), key=lambda x: -x[1])[:5],
        },
        "fan_in": {
            "max": max_fi,
            "threshold": thresholds["max_fan_in"],
            "top_5": sorted(fan_in.items(), key=lambda x: -x[1])[:5],
        },
        "fan_out": {
            "max": max_fo,
            "threshold": thresholds["max_fan_out"],
            "top_5": sorted(fan_out.items(), key=lambda x: -x[1])[:5],
        },
        "side_effects": {
            "count": len(side_effects),
            "threshold": thresholds["max_side_effects"],
            "issues": side_effects,
        },
        "violations": violations,
        "healthy": len(violations) == 0,
    }
    return report


def quick_check() -> list[str]:
    """Quick pass/fail for heartbeat postflight. Returns list of violations."""
    graph = build_import_graph(SCRIPTS_DIR)
    report = full_report(graph, use_current_thresholds=True)
    return report["violations"]


def print_report(report: dict):
    """Pretty-print the structural health report."""
    healthy = report["healthy"]
    status = "HEALTHY" if healthy else "DEGRADED"

    print(f"=== STRUCTURAL HEALTH: {status} ===")
    print(f"Modules: {report['total_modules']} total, "
          f"{report['modules_with_imports']} with imports, "
          f"{report['leaf_modules']} leaf")
    print()

    # Circular imports
    ci = report["circular_imports"]
    flag = "PASS" if ci["max_scc_size"] <= ci["threshold"] else "FAIL"
    print(f"[{flag}] Circular imports: {ci['scc_count']} SCCs, "
          f"max size {ci['max_scc_size']} (threshold: {ci['threshold']})")
    for scc in ci["sccs"]:
        print(f"       SCC: {' <-> '.join(scc)}")

    # Depth
    dd = report["dependency_depth"]
    flag = "PASS" if dd["max"] <= dd["threshold"] else "FAIL"
    print(f"[{flag}] Max dependency depth: {dd['max']} (threshold: {dd['threshold']})")
    for name, d in dd["top_5"]:
        print(f"       depth={d}: {name}")

    # Fan-in
    fi = report["fan_in"]
    flag = "PASS" if fi["max"] <= fi["threshold"] else "FAIL"
    print(f"[{flag}] Max fan-in: {fi['max']} (threshold: {fi['threshold']})")
    for name, c in fi["top_5"]:
        print(f"       {c}x: {name}")

    # Fan-out
    fo = report["fan_out"]
    flag = "PASS" if fo["max"] <= fo["threshold"] else "FAIL"
    print(f"[{flag}] Max fan-out: {fo['max']} (threshold: {fo['threshold']})")
    for name, c in fo["top_5"]:
        print(f"       {c} deps: {name}")

    # Side effects
    se = report["side_effects"]
    flag = "PASS" if se["count"] <= se["threshold"] else "FAIL"
    print(f"[{flag}] Import side effects: {se['count']} (threshold: {se['threshold']})")
    for issue in se["issues"][:10]:
        kind = issue.get("kind", "bare_call")
        label = "assign" if kind == "assign_call" else "call"
        print(f"       {issue['file']}:{issue['line']} — {issue['call']}() [{label}]")

    # Violations
    if report["violations"]:
        print(f"\nVIOLATIONS: {', '.join(report['violations'])}")
    else:
        print(f"\nAll checks passed.")

    # Target thresholds (post-refactor)
    print(f"\n--- Post-Refactor Targets ---")
    for k, v in THRESHOLDS.items():
        print(f"  {k}: {v}")


def main(argv=None):
    argv = argv or sys.argv[1:]

    graph = build_import_graph(SCRIPTS_DIR)

    if "--json" in argv:
        report = full_report(graph, use_current_thresholds="--strict" not in argv)
        print(json.dumps(report, indent=2, default=str))
    elif "--cycles" in argv:
        sccs = find_sccs(graph)
        if sccs:
            print(f"CIRCULAR IMPORTS DETECTED: {len(sccs)} SCCs")
            for scc in sccs:
                print(f"  {' <-> '.join(scc)}")
            sys.exit(1)
        else:
            print("No circular imports.")
    elif "--depth" in argv:
        depths = compute_depths(graph)
        for name, d in sorted(depths.items(), key=lambda x: -x[1])[:15]:
            if d > 0:
                print(f"  depth={d}: {name}")
    elif "--side-effects" in argv:
        # Focused CI gate: only check import-time side effects (exit 1 if any found)
        side_effects = detect_side_effects(SCRIPTS_DIR)
        if side_effects:
            print(f"IMPORT SIDE EFFECTS: {len(side_effects)} found (threshold: 0)")
            for issue in side_effects:
                kind = issue.get("kind", "bare_call")
                print(f"  {issue['file']}:{issue['line']} {issue['call']}() [{kind}]")
            sys.exit(1)
        else:
            print("OK: 0 import side effects")
    elif "--quick" in argv:
        violations = quick_check()
        if violations:
            print(f"STRUCTURAL VIOLATIONS: {', '.join(violations)}")
            sys.exit(1)
        else:
            print("OK")
    elif "--strict" in argv:
        # CI gate: use post-refactor (strict) thresholds, exit 1 on any violation
        report = full_report(graph, use_current_thresholds=False)
        print_report(report)

        # Side-effects-only summary for quick CI feedback
        se = report["side_effects"]
        if se["count"] > 0:
            print(f"\n--- Side Effects Detail ({se['count']} found) ---")
            for issue in se["issues"]:
                kind = issue.get("kind", "bare_call")
                print(f"  {issue['file']}:{issue['line']} {issue['call']}() [{kind}]")

        if not report["healthy"]:
            print(f"\nSTRICT CHECK FAILED: {', '.join(report['violations'])}")
            sys.exit(1)
        else:
            print(f"\nSTRICT CHECK PASSED")
    else:
        report = full_report(graph, use_current_thresholds=True)
        print_report(report)

        # Measure import time for brain
        print(f"\n--- Import Timing ---")
        brain_ms = measure_import_time("brain", SCRIPTS_DIR)
        threshold = THRESHOLDS_CURRENT["max_import_time_ms"]
        flag = "PASS" if brain_ms <= threshold else "FAIL"
        print(f"[{flag}] brain.py import: {brain_ms:.0f}ms (threshold: {threshold}ms)")


if __name__ == "__main__":
    main()
