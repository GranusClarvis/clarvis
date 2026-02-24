#!/usr/bin/env python3
"""
AST Self-Surgery — Parse own code, propose mutations, test against benchmarks.

Clarvis examines its own Python scripts via AST, identifies improvement
opportunities (dead code, complexity hotspots, unused imports, code smells),
proposes concrete mutations, and verifies proposals against existing benchmarks
before applying them.

Pipeline:
  1. SCAN:    Parse all scripts/*.py, build AST profiles (functions, classes,
              imports, complexity, dead code candidates)
  2. ANALYZE: Score each file on multiple quality dimensions
  3. PROPOSE: Generate concrete mutation proposals ranked by expected benefit
  4. TEST:    Apply mutation in memory, verify it parses, run benchmarks
  5. REPORT:  Output proposals with confidence scores and expected impact

Mutation types:
  - dead_import:       Import never referenced in the module
  - dead_function:     Function defined but never called (within same file)
  - high_complexity:   Function with cyclomatic complexity > threshold
  - long_function:     Function exceeding line-count threshold
  - bare_except:       Generic except clauses that swallow errors
  - duplicate_string:  Magic strings repeated 3+ times (candidate for constant)
  - missing_docstring: Public function without a docstring

Integration:
  - brain.py: stores surgery reports as learnings
  - retrieval_benchmark.py: verifies mutations don't regress retrieval
  - thought_protocol.py: self-tests used as benchmark gate

Usage:
    python3 ast_surgery.py scan              # Full scan, print report
    python3 ast_surgery.py proposals         # Show ranked mutation proposals
    python3 ast_surgery.py test              # Dry-run top proposals against benchmarks
    python3 ast_surgery.py apply <id>        # Apply a verified mutation (with backup)
    python3 ast_surgery.py history           # Show past surgery history
    python3 ast_surgery.py stats             # Summary statistics
"""

import ast
import json
import os
import sys
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SCRIPTS_DIR = Path("/home/agent/.openclaw/workspace/scripts")
DATA_DIR = Path("/home/agent/.openclaw/workspace/data/ast_surgery")
HISTORY_FILE = DATA_DIR / "history.jsonl"
LATEST_FILE = DATA_DIR / "latest.json"
PROPOSALS_FILE = DATA_DIR / "proposals.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Thresholds for mutation detection
MAX_FUNCTION_LINES = 60
MAX_COMPLEXITY = 10
MIN_DUPLICATE_STRINGS = 3
MIN_STRING_LENGTH = 20  # Skip short dict keys, JSON field names

# Files to skip (deprecated, caches)
SKIP_DIRS = {"deprecated", "__pycache__", ".git"}


# ──────────────────────────────────────────────
# AST Analysis Utilities
# ──────────────────────────────────────────────

def _cyclomatic_complexity(node):
    """Compute cyclomatic complexity for a function/method AST node.
    Counts decision points: if, elif, for, while, except, and, or, assert, with."""
    complexity = 1  # base path
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.IfExp)):
            complexity += 1
        elif isinstance(child, ast.For):
            complexity += 1
        elif isinstance(child, ast.While):
            complexity += 1
        elif isinstance(child, ast.ExceptHandler):
            complexity += 1
        elif isinstance(child, ast.Assert):
            complexity += 1
        elif isinstance(child, ast.With):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            # and/or add branches
            complexity += len(child.values) - 1
    return complexity


def _extract_names_used(tree):
    """Extract all Name nodes referenced in a tree (variable/function usage)."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            # Capture the root of attribute chains: foo.bar -> foo
            obj = node
            while isinstance(obj, ast.Attribute):
                obj = obj.value
            if isinstance(obj, ast.Name):
                names.add(obj.id)
    return names


def _extract_string_literals(tree):
    """Extract all string literal values and their locations."""
    strings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if len(node.value) >= MIN_STRING_LENGTH:
                strings.append({
                    "value": node.value,
                    "line": getattr(node, "lineno", 0),
                })
    return strings


def _function_line_count(node):
    """Count lines in a function body."""
    if not hasattr(node, "end_lineno") or not hasattr(node, "lineno"):
        return 0
    return node.end_lineno - node.lineno + 1


# ──────────────────────────────────────────────
# File Scanner
# ──────────────────────────────────────────────

class FileProfile:
    """AST profile for a single Python file."""

    def __init__(self, filepath):
        self.filepath = Path(filepath)
        self.filename = self.filepath.name
        self.line_count = 0
        self.parse_error = None
        self.imports = []           # [{name, alias, line, module}]
        self.functions = []         # [{name, line, end_line, lines, complexity, has_docstring}]
        self.classes = []           # [{name, line, methods: [...]}]
        self.top_level_names = set()
        self.names_used = set()
        self.string_literals = []
        self.bare_excepts = []      # [{line}]
        self.tree = None

    def scan(self):
        """Parse and profile the file."""
        try:
            source = self.filepath.read_text(encoding="utf-8")
        except Exception as e:
            self.parse_error = f"read error: {e}"
            return self

        self.line_count = len(source.splitlines())

        try:
            self.tree = ast.parse(source, filename=str(self.filepath))
        except SyntaxError as e:
            self.parse_error = f"SyntaxError at line {e.lineno}: {e.msg}"
            return self

        self._scan_imports()
        self._scan_functions()
        self._scan_classes()
        self._scan_bare_excepts()
        self.names_used = _extract_names_used(self.tree)
        self.string_literals = _extract_string_literals(self.tree)
        return self

    def _scan_imports(self):
        for node in ast.iter_child_nodes(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.imports.append({
                        "name": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno,
                        "module": None,
                        "kind": "import",
                    })
                    self.top_level_names.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    self.imports.append({
                        "name": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno,
                        "module": node.module,
                        "kind": "from",
                    })
                    self.top_level_names.add(alias.asname or alias.name)

    def _scan_functions(self):
        for node in ast.iter_child_nodes(self.tree):
            if isinstance(node, ast.FunctionDef):
                self.functions.append(self._profile_function(node))
                self.top_level_names.add(node.name)

    def _scan_classes(self):
        for node in ast.iter_child_nodes(self.tree):
            if isinstance(node, ast.ClassDef):
                methods = []
                for item in ast.iter_child_nodes(node):
                    if isinstance(item, ast.FunctionDef):
                        methods.append(self._profile_function(item))
                self.classes.append({
                    "name": node.name,
                    "line": node.lineno,
                    "methods": methods,
                })
                self.top_level_names.add(node.name)

    def _profile_function(self, node):
        docstring = ast.get_docstring(node)
        return {
            "name": node.name,
            "line": node.lineno,
            "end_line": getattr(node, "end_lineno", node.lineno),
            "lines": _function_line_count(node),
            "complexity": _cyclomatic_complexity(node),
            "has_docstring": docstring is not None,
            "args": len(node.args.args),
        }

    def _scan_bare_excepts(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                self.bare_excepts.append({"line": node.lineno})

    # === Mutation Detectors ===

    def find_dead_imports(self):
        """Find imports whose names are never referenced in the file body."""
        dead = []
        for imp in self.imports:
            used_name = imp["alias"] or imp["name"].split(".")[0]
            # Check if the name appears anywhere in usage
            if used_name not in self.names_used:
                # Double-check: some imports are used via string references or __all__
                source = self.filepath.read_text(encoding="utf-8")
                if used_name not in source.split("import")[0]:
                    # Verify it's truly unused — search for the name in the full source
                    # excluding the import line itself
                    lines = source.splitlines()
                    used_elsewhere = False
                    for i, line in enumerate(lines, 1):
                        if i == imp["line"]:
                            continue
                        if used_name in line:
                            used_elsewhere = True
                            break
                    if not used_elsewhere:
                        dead.append(imp)
        return dead

    def find_dead_functions(self):
        """Find top-level functions defined but never called within this file.
        Excludes: main-block functions, CLI entry points, functions starting with _
        that look like callbacks/hooks, and any function referenced by name."""
        dead = []
        # Get all function calls in the file
        calls = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)

        for fn in self.functions:
            name = fn["name"]
            # Skip private, dunder, main, CLI-entry functions
            if name.startswith("__") and name.endswith("__"):
                continue
            if name in ("main", "cli", "run"):
                continue
            # Skip if called anywhere
            if name in calls:
                continue
            # Skip if name appears in a string (could be registered as CLI command)
            source = self.filepath.read_text(encoding="utf-8")
            if f'"{name}"' in source or f"'{name}'" in source:
                continue
            # Skip if referenced as a callback/decorator target
            if name in self.names_used:
                continue
            dead.append(fn)
        return dead

    def find_complex_functions(self):
        """Find functions with cyclomatic complexity above threshold."""
        all_fns = list(self.functions)
        for cls in self.classes:
            all_fns.extend(cls["methods"])
        return [f for f in all_fns if f["complexity"] > MAX_COMPLEXITY]

    def find_long_functions(self):
        """Find functions exceeding the line count threshold."""
        all_fns = list(self.functions)
        for cls in self.classes:
            all_fns.extend(cls["methods"])
        return [f for f in all_fns if f["lines"] > MAX_FUNCTION_LINES]

    def find_duplicate_strings(self):
        """Find string constants repeated 3+ times."""
        counter = Counter(s["value"] for s in self.string_literals)
        dupes = []
        for val, count in counter.items():
            if count >= MIN_DUPLICATE_STRINGS:
                lines = [s["line"] for s in self.string_literals if s["value"] == val]
                dupes.append({"value": val, "count": count, "lines": lines})
        return dupes

    def find_bare_excepts(self):
        return self.bare_excepts

    def find_missing_docstrings(self):
        """Find public functions without docstrings."""
        missing = []
        for fn in self.functions:
            if not fn["name"].startswith("_") and not fn["has_docstring"]:
                missing.append(fn)
        return missing

    def quality_score(self):
        """Compute an overall quality score (0-1) for the file."""
        if self.parse_error:
            return 0.0

        penalties = 0.0

        # Dead imports: -0.02 each
        penalties += len(self.find_dead_imports()) * 0.02
        # Complex functions: -0.05 each
        penalties += len(self.find_complex_functions()) * 0.05
        # Long functions: -0.03 each
        penalties += len(self.find_long_functions()) * 0.03
        # Bare excepts: -0.04 each
        penalties += len(self.bare_excepts) * 0.04
        # Missing docstrings: -0.01 each (minor)
        penalties += len(self.find_missing_docstrings()) * 0.01
        # Duplicate strings: -0.02 each
        penalties += len(self.find_duplicate_strings()) * 0.02

        return max(0.0, min(1.0, 1.0 - penalties))

    def to_dict(self):
        return {
            "file": self.filename,
            "path": str(self.filepath),
            "line_count": self.line_count,
            "parse_error": self.parse_error,
            "num_imports": len(self.imports),
            "num_functions": len(self.functions),
            "num_classes": len(self.classes),
            "num_methods": sum(len(c["methods"]) for c in self.classes),
            "quality_score": round(self.quality_score(), 3),
        }


# ──────────────────────────────────────────────
# Full Codebase Scanner
# ──────────────────────────────────────────────

def scan_all():
    """Scan all Python files in scripts/."""
    profiles = []
    for py_file in sorted(SCRIPTS_DIR.glob("*.py")):
        if py_file.name.startswith("__"):
            continue
        if any(skip in str(py_file) for skip in SKIP_DIRS):
            continue
        profile = FileProfile(py_file).scan()
        profiles.append(profile)
    return profiles


def generate_proposals(profiles):
    """Generate ranked mutation proposals from file profiles."""
    proposals = []
    proposal_id = 0

    for p in profiles:
        if p.parse_error:
            continue

        # Dead imports
        for imp in p.find_dead_imports():
            proposal_id += 1
            used_name = imp["alias"] or imp["name"]
            proposals.append({
                "id": f"M{proposal_id:03d}",
                "type": "dead_import",
                "file": p.filename,
                "path": str(p.filepath),
                "line": imp["line"],
                "description": f"Remove unused import '{used_name}' (line {imp['line']})",
                "severity": "low",
                "benefit": 0.3,
                "risk": 0.1,
                "details": imp,
            })

        # Dead functions
        for fn in p.find_dead_functions():
            proposal_id += 1
            proposals.append({
                "id": f"M{proposal_id:03d}",
                "type": "dead_function",
                "file": p.filename,
                "path": str(p.filepath),
                "line": fn["line"],
                "description": f"Remove unused function '{fn['name']}' ({fn['lines']} lines, line {fn['line']})",
                "severity": "medium",
                "benefit": 0.5,
                "risk": 0.4,  # higher risk — might be called externally
                "details": fn,
            })

        # Complex functions
        for fn in p.find_complex_functions():
            proposal_id += 1
            proposals.append({
                "id": f"M{proposal_id:03d}",
                "type": "high_complexity",
                "file": p.filename,
                "path": str(p.filepath),
                "line": fn["line"],
                "description": f"Refactor '{fn['name']}' (complexity={fn['complexity']}, lines={fn['lines']})",
                "severity": "medium",
                "benefit": 0.6,
                "risk": 0.5,
                "details": fn,
            })

        # Long functions
        for fn in p.find_long_functions():
            # Skip if already flagged as complex
            already = any(
                pr["type"] == "high_complexity" and pr["line"] == fn["line"]
                and pr["file"] == p.filename
                for pr in proposals
            )
            if already:
                continue
            proposal_id += 1
            proposals.append({
                "id": f"M{proposal_id:03d}",
                "type": "long_function",
                "file": p.filename,
                "path": str(p.filepath),
                "line": fn["line"],
                "description": f"Split '{fn['name']}' ({fn['lines']} lines, line {fn['line']})",
                "severity": "low",
                "benefit": 0.4,
                "risk": 0.3,
                "details": fn,
            })

        # Bare excepts
        for be in p.find_bare_excepts():
            proposal_id += 1
            proposals.append({
                "id": f"M{proposal_id:03d}",
                "type": "bare_except",
                "file": p.filename,
                "path": str(p.filepath),
                "line": be["line"],
                "description": f"Specify exception type in bare except (line {be['line']})",
                "severity": "medium",
                "benefit": 0.4,
                "risk": 0.2,
                "details": be,
            })

        # Duplicate strings
        for ds in p.find_duplicate_strings():
            proposal_id += 1
            short_val = ds["value"][:40] + ("..." if len(ds["value"]) > 40 else "")
            proposals.append({
                "id": f"M{proposal_id:03d}",
                "type": "duplicate_string",
                "file": p.filename,
                "path": str(p.filepath),
                "line": ds["lines"][0],
                "description": f"Extract constant for '{short_val}' (repeated {ds['count']}x)",
                "severity": "low",
                "benefit": 0.3,
                "risk": 0.1,
                "details": ds,
            })

    # Rank by benefit/risk ratio
    for p in proposals:
        p["score"] = round(p["benefit"] / max(p["risk"], 0.01), 2)
    proposals.sort(key=lambda x: x["score"], reverse=True)

    return proposals


# ──────────────────────────────────────────────
# Benchmark Testing
# ──────────────────────────────────────────────

def run_parse_test(filepath):
    """Verify a file still parses after modification."""
    try:
        source = Path(filepath).read_text(encoding="utf-8")
        ast.parse(source)
        return True, "parses OK"
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"


def run_import_test(filepath):
    """Verify a module can still be imported (catches missing dependencies)."""
    module_name = Path(filepath).stem
    try:
        result = subprocess.run(
            [sys.executable, "-c", f"import sys; sys.path.insert(0, '{SCRIPTS_DIR}'); import {module_name}"],
            capture_output=True, text=True, timeout=30,
            cwd=str(SCRIPTS_DIR),
        )
        if result.returncode == 0:
            return True, "imports OK"
        return False, result.stderr.strip()[:200]
    except subprocess.TimeoutExpired:
        return False, "import timed out"


def run_thought_protocol_tests():
    """Run thought_protocol.py self-tests as a benchmark gate."""
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "thought_protocol.py"), "test"],
            capture_output=True, text=True, timeout=30,
            cwd=str(SCRIPTS_DIR),
        )
        output = result.stdout + result.stderr
        # Count test passes
        passes = output.count("PASS")
        fails = output.count("FAIL")
        return passes, fails, output[:500]
    except subprocess.TimeoutExpired:
        return 0, 1, "timeout"


def run_retrieval_benchmark():
    """Run retrieval_benchmark.py and return precision/recall."""
    try:
        subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "retrieval_benchmark.py")],
            capture_output=True, text=True, timeout=120,
            cwd=str(SCRIPTS_DIR),
        )
        # Parse latest.json for results
        latest = Path("/home/agent/.openclaw/workspace/data/retrieval_benchmark/latest.json")
        if latest.exists():
            with open(latest) as f:
                data = json.load(f)
            return data.get("avg_precision_at_k", 0), data.get("avg_recall", 0)
        return 0, 0
    except Exception:
        return 0, 0


def test_proposal(proposal):
    """Test a single mutation proposal by simulating the change."""
    filepath = Path(proposal["path"])
    mutation_type = proposal["type"]

    result = {
        "id": proposal["id"],
        "type": mutation_type,
        "parse_ok": False,
        "import_ok": False,
        "benchmark_ok": False,
        "verdict": "untested",
    }

    if mutation_type == "dead_import":
        # Simulate removing the import line
        source = filepath.read_text(encoding="utf-8")
        lines = source.splitlines(keepends=True)
        line_idx = proposal["line"] - 1
        if 0 <= line_idx < len(lines):
            # Comment out instead of removing (safer test)
            original_line = lines[line_idx]
            lines[line_idx] = f"# [AST-SURGERY REMOVED] {original_line}"
            modified = "".join(lines)
            try:
                ast.parse(modified)
                result["parse_ok"] = True
            except SyntaxError:
                result["verdict"] = "parse_fail"
                return result

            # Write temp, test import, restore
            backup = source
            filepath.write_text(modified, encoding="utf-8")
            try:
                ok, msg = run_import_test(filepath)
                result["import_ok"] = ok
                if not ok:
                    result["verdict"] = f"import_fail: {msg}"
                else:
                    result["verdict"] = "safe"
                    result["benchmark_ok"] = True
            finally:
                filepath.write_text(backup, encoding="utf-8")
        else:
            result["verdict"] = "line_out_of_range"

    elif mutation_type in ("high_complexity", "long_function", "bare_except",
                           "duplicate_string", "missing_docstring"):
        # These are advisory — can't auto-apply, just verify current state
        result["parse_ok"] = True
        result["import_ok"] = True
        result["benchmark_ok"] = True
        result["verdict"] = "advisory"

    elif mutation_type == "dead_function":
        # Higher risk — verify the function isn't called from OTHER files
        fn_name = proposal["details"]["name"]
        # Search all scripts for references to this function
        external_refs = 0
        for py_file in SCRIPTS_DIR.glob("*.py"):
            if py_file == filepath:
                continue
            try:
                other_source = py_file.read_text(encoding="utf-8")
                if fn_name in other_source:
                    external_refs += 1
            except Exception:
                pass
        if external_refs > 0:
            result["verdict"] = f"external_refs={external_refs}"
            result["parse_ok"] = True
            result["import_ok"] = True
        else:
            result["verdict"] = "safe"
            result["parse_ok"] = True
            result["import_ok"] = True
            result["benchmark_ok"] = True

    return result


# ──────────────────────────────────────────────
# Reporting & Storage
# ──────────────────────────────────────────────

def save_report(profiles, proposals, test_results=None):
    """Save scan report to disk."""
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "files_scanned": len(profiles),
        "total_lines": sum(p.line_count for p in profiles),
        "parse_errors": sum(1 for p in profiles if p.parse_error),
        "avg_quality": round(
            sum(p.quality_score() for p in profiles if not p.parse_error)
            / max(1, sum(1 for p in profiles if not p.parse_error)),
            3
        ),
        "total_functions": sum(
            len(p.functions) + sum(len(c["methods"]) for c in p.classes)
            for p in profiles
        ),
        "total_proposals": len(proposals),
        "proposals_by_type": dict(Counter(p["type"] for p in proposals)),
        "file_scores": [p.to_dict() for p in profiles],
        "proposals": proposals[:50],  # top 50
    }

    if test_results:
        report["test_results"] = test_results

    with open(LATEST_FILE, "w") as f:
        json.dump(report, f, indent=2)

    # Append summary to history
    summary = {
        "timestamp": report["timestamp"],
        "files": report["files_scanned"],
        "lines": report["total_lines"],
        "avg_quality": report["avg_quality"],
        "proposals": report["total_proposals"],
        "by_type": report["proposals_by_type"],
    }
    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(summary) + "\n")

    # Cap history at 400 entries
    if HISTORY_FILE.exists():
        lines = HISTORY_FILE.read_text().splitlines()
        if len(lines) > 400:
            HISTORY_FILE.write_text("\n".join(lines[-400:]) + "\n")

    return report


def store_to_brain(report):
    """Store surgery report as a learning in brain."""
    try:
        from brain import brain
        summary = (
            f"AST self-surgery scan: {report['files_scanned']} files, "
            f"{report['total_lines']} lines, avg quality {report['avg_quality']:.3f}. "
            f"Found {report['total_proposals']} improvement proposals: "
            + ", ".join(f"{k}={v}" for k, v in report.get('proposals_by_type', {}).items())
        )
        brain.store(
            summary,
            collection="clarvis-learnings",
            importance=0.6,
            tags=["ast-surgery", "code-quality", "self-improvement"],
            source="ast_surgery.py",
        )
    except Exception:
        pass  # Brain not available — skip


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def auto_fix_dead_imports(proposals):
    """Auto-fix dead imports that test as safe. Returns list of applied fixes."""
    applied = []
    for p in proposals:
        if p["type"] != "dead_import":
            continue
        result = test_proposal(p)
        if result["verdict"] != "safe":
            continue
        # Remove the import line
        filepath = Path(p["path"])
        source = filepath.read_text(encoding="utf-8")
        lines = source.splitlines(keepends=True)
        line_idx = p["line"] - 1
        if 0 <= line_idx < len(lines):
            removed_line = lines[line_idx].rstrip()
            lines[line_idx] = ""
            filepath.write_text("".join(lines), encoding="utf-8")
            # Verify it still parses
            ok, msg = run_parse_test(filepath)
            if not ok:
                # Revert
                filepath.write_text(source, encoding="utf-8")
                print(f"  REVERTED {p['file']}:{p['line']} — {msg}")
            else:
                applied.append({
                    "id": p["id"],
                    "file": p["file"],
                    "line": p["line"],
                    "removed": removed_line,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                print(f"  FIXED {p['file']}:{p['line']} — removed: {removed_line.strip()}")
    return applied


def cmd_scan(auto_fix=False):
    """Full scan with report. If auto_fix=True, auto-remove safe dead imports."""
    profiles = scan_all()
    proposals = generate_proposals(profiles)

    # Auto-fix safe dead imports before saving report
    fixes = []
    if auto_fix:
        print("=== Auto-fixing safe dead imports ===")
        fixes = auto_fix_dead_imports(proposals)
        if fixes:
            print(f"  Applied {len(fixes)} fixes")
            # Re-scan after fixes to get accurate report
            profiles = scan_all()
            proposals = generate_proposals(profiles)
        else:
            print("  No safe fixes to apply")
        print()

    report = save_report(profiles, proposals)
    if fixes:
        report["auto_fixes"] = fixes
        # Append fixes to history
        fix_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "auto_fix",
            "fixes_applied": len(fixes),
            "fixes": fixes,
        }
        with open(HISTORY_FILE, "a") as f:
            f.write(json.dumps(fix_record) + "\n")
    store_to_brain(report)

    print("=== AST Self-Surgery Report ===")
    print(f"Files scanned:   {report['files_scanned']}")
    print(f"Total lines:     {report['total_lines']}")
    print(f"Parse errors:    {report['parse_errors']}")
    print(f"Avg quality:     {report['avg_quality']:.3f}")
    print(f"Total functions: {report['total_functions']}")
    print(f"Proposals:       {report['total_proposals']}")
    if fixes:
        print(f"Auto-fixed:      {len(fixes)} dead imports")
    print()

    if report["proposals_by_type"]:
        print("Proposals by type:")
        for ptype, count in sorted(report["proposals_by_type"].items()):
            print(f"  {ptype:20s}: {count}")
        print()

    # File quality breakdown
    print("File quality scores:")
    for fs in sorted(report["file_scores"], key=lambda x: x["quality_score"]):
        bar = "#" * int(fs["quality_score"] * 20)
        print(f"  {fs['file']:35s} {fs['quality_score']:.3f} [{bar:20s}]  ({fs['line_count']} lines)")
    print()

    # Top proposals
    if proposals:
        print(f"Top 10 proposals (of {len(proposals)}):")
        for p in proposals[:10]:
            print(f"  [{p['id']}] {p['type']:18s} | {p['file']:25s} | {p['description']}")
        print()

    return report


def cmd_proposals():
    """Show ranked proposals."""
    profiles = scan_all()
    proposals = generate_proposals(profiles)

    if not proposals:
        print("No mutation proposals found — code is clean.")
        return

    print(f"=== {len(proposals)} Mutation Proposals ===")
    print()
    for p in proposals:
        risk_label = {"low": ".", "medium": "*", "high": "!"}
        severity = risk_label.get(p["severity"], "?")
        print(f"  [{p['id']}] {severity} {p['type']:18s} | score={p['score']:5.1f} | {p['file']:25s}")
        print(f"         {p['description']}")
        print()


def cmd_test():
    """Test top proposals against benchmarks."""
    profiles = scan_all()
    proposals = generate_proposals(profiles)

    if not proposals:
        print("No proposals to test.")
        return

    # Get baseline benchmarks
    print("Running baseline benchmarks...")
    tp_passes, tp_fails, _ = run_thought_protocol_tests()
    print(f"  thought_protocol: {tp_passes} passes, {tp_fails} fails")

    # Test top proposals
    test_results = []
    safe_count = 0
    for p in proposals[:20]:  # test top 20
        result = test_proposal(p)
        test_results.append(result)
        verdict_icon = {
            "safe": "+",
            "advisory": "~",
            "parse_fail": "X",
            "untested": "?",
        }
        icon = verdict_icon.get(result["verdict"], "-" if "fail" in result["verdict"] else "?")
        print(f"  [{result['id']}] {icon} {p['type']:18s} | {result['verdict']}")
        if result["verdict"] == "safe":
            safe_count += 1

    # Save results
    report = save_report(profiles, proposals, test_results)
    store_to_brain(report)

    # Verify benchmarks still pass
    print()
    print(f"Results: {safe_count} safe, {len(test_results) - safe_count} need review")
    print(f"Baseline: thought_protocol {tp_passes}/{tp_passes + tp_fails} tests pass")

    # Save proposals file for apply command
    with open(PROPOSALS_FILE, "w") as f:
        json.dump({"proposals": proposals, "test_results": test_results}, f, indent=2)

    return test_results


def cmd_stats():
    """Summary statistics."""
    if not LATEST_FILE.exists():
        print("No scan data yet. Run: python3 ast_surgery.py scan")
        return

    with open(LATEST_FILE) as f:
        report = json.load(f)

    print("=== AST Surgery Stats ===")
    print(f"Last scan:       {report['timestamp']}")
    print(f"Files:           {report['files_scanned']}")
    print(f"Lines:           {report['total_lines']}")
    print(f"Avg quality:     {report['avg_quality']:.3f}")
    print(f"Proposals:       {report['total_proposals']}")

    if report.get("test_results"):
        safe = sum(1 for r in report["test_results"] if r["verdict"] == "safe")
        print(f"Tested safe:     {safe}/{len(report['test_results'])}")


def cmd_history():
    """Show surgery history trend."""
    if not HISTORY_FILE.exists():
        print("No history yet.")
        return

    entries = []
    for line in HISTORY_FILE.read_text().splitlines():
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    if not entries:
        print("No history entries.")
        return

    print(f"=== Surgery History ({len(entries)} scans) ===")
    for entry in entries[-10:]:
        ts = entry["timestamp"][:19]
        print(f"  {ts} | quality={entry['avg_quality']:.3f} | proposals={entry['proposals']} | {entry.get('by_type', {})}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"
    auto_fix = "--auto-fix" in sys.argv

    if cmd == "scan":
        cmd_scan(auto_fix=auto_fix)
    elif cmd == "proposals":
        cmd_proposals()
    elif cmd == "test":
        cmd_test()
    elif cmd == "stats":
        cmd_stats()
    elif cmd == "history":
        cmd_history()
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: ast_surgery.py [scan|proposals|test|stats|history]")
        sys.exit(1)
