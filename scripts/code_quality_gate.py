#!/usr/bin/env python3
"""
Code Quality Gate — nightly AST + pyflakes audit of scripts/*.py

Counts syntax errors, undefined names, unused imports.
Auto-fixes trivial issues (unused imports).
Logs quality trend to data/code_quality_history.json.

Usage:
    python3 code_quality_gate.py scan          # scan + report (no fixes)
    python3 code_quality_gate.py fix           # scan + auto-fix unused imports
    python3 code_quality_gate.py trend         # show quality trend
"""
import ast
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path("/home/agent/.openclaw/workspace/scripts")
HISTORY_FILE = Path("/home/agent/.openclaw/workspace/data/code_quality_history.json")


def ast_check(filepath):
    """Parse file with AST, return list of syntax errors."""
    errors = []
    try:
        with open(filepath) as f:
            source = f.read()
        ast.parse(source, filename=str(filepath))
    except SyntaxError as e:
        errors.append({
            "file": str(filepath),
            "type": "syntax_error",
            "line": e.lineno,
            "msg": str(e.msg),
        })
    return errors


def pyflakes_check(filepath):
    """Run pyflakes on a single file, parse output into structured issues."""
    issues = []
    try:
        r = subprocess.run(
            ["python3", "-m", "pyflakes", str(filepath)],
            capture_output=True, text=True, timeout=15,
        )
        for line in r.stdout.strip().split("\n"):
            if not line.strip():
                continue
            # Format: path:line:col message  or  path:line: message
            m = re.match(r"^(.+?):(\d+):(?:\d+:)?\s*(.+)$", line)
            if m:
                msg = m.group(3)
                issue = {
                    "file": str(filepath),
                    "line": int(m.group(2)),
                    "msg": msg,
                }
                if "imported but unused" in msg:
                    issue["type"] = "unused_import"
                    # Extract the import name
                    im = re.search(r"'([^']+)'", msg)
                    if im:
                        issue["name"] = im.group(1)
                elif "undefined name" in msg:
                    issue["type"] = "undefined_name"
                elif "redefined unused" in msg:
                    issue["type"] = "redefined_unused"
                else:
                    issue["type"] = "other"
                issues.append(issue)
    except Exception as e:
        issues.append({
            "file": str(filepath),
            "type": "pyflakes_error",
            "line": 0,
            "msg": f"pyflakes failed: {e}",
        })
    return issues


def fix_unused_import(filepath, import_name, line_num):
    """Remove an unused import line from a file. Returns True if fixed."""
    try:
        with open(filepath) as f:
            lines = f.readlines()

        if line_num < 1 or line_num > len(lines):
            return False

        target_line = lines[line_num - 1]

        # Handle "from X import Y" — only remove the specific name if multi-import
        if re.match(r"^\s*from\s+\S+\s+import\s+", target_line):
            # Multi-import: "from X import A, B, C"
            m = re.match(r"^(\s*from\s+\S+\s+import\s+)(.+)$", target_line.rstrip())
            if m:
                prefix = m.group(1)
                names = [n.strip() for n in m.group(2).split(",")]
                # Only the specific unused name
                short_name = import_name.split(".")[-1]
                remaining = [n for n in names if n != short_name]
                if remaining and len(remaining) < len(names):
                    lines[line_num - 1] = prefix + ", ".join(remaining) + "\n"
                    with open(filepath, "w") as f:
                        f.writelines(lines)
                    return True
                elif not remaining:
                    # All names unused — remove entire line
                    lines.pop(line_num - 1)
                    with open(filepath, "w") as f:
                        f.writelines(lines)
                    return True
        # Simple "import X" — remove the line
        elif re.match(r"^\s*import\s+", target_line):
            lines.pop(line_num - 1)
            with open(filepath, "w") as f:
                f.writelines(lines)
            return True

        return False
    except Exception:
        return False


def scan_all(do_fix=False):
    """Scan all scripts/*.py files. Returns summary dict."""
    py_files = sorted(SCRIPTS_DIR.glob("*.py"))
    all_syntax_errors = []
    all_issues = []
    fixes_applied = []
    per_file = {}

    for fp in py_files:
        file_syntax = ast_check(fp)
        all_syntax_errors.extend(file_syntax)

        if file_syntax:
            # Skip pyflakes if file has syntax errors
            per_file[fp.name] = {"syntax_errors": len(file_syntax), "issues": 0, "clean": False}
            continue

        file_issues = pyflakes_check(fp)

        if do_fix:
            # Auto-fix unused imports (iterate in reverse line order to preserve line numbers)
            unused = sorted(
                [i for i in file_issues if i["type"] == "unused_import"],
                key=lambda x: x["line"],
                reverse=True,
            )
            for issue in unused:
                name = issue.get("name", "")
                if fix_unused_import(fp, name, issue["line"]):
                    fixes_applied.append({
                        "file": fp.name,
                        "line": issue["line"],
                        "name": name,
                    })
                    file_issues.remove(issue)

        all_issues.extend(file_issues)
        per_file[fp.name] = {
            "syntax_errors": 0,
            "issues": len(file_issues),
            "clean": len(file_issues) == 0,
        }

    total_files = len(py_files)
    clean_files = sum(1 for v in per_file.values() if v["clean"])
    by_type = {}
    for issue in all_issues:
        t = issue["type"]
        by_type[t] = by_type.get(t, 0) + 1

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_files": total_files,
        "clean_files": clean_files,
        "clean_ratio": round(clean_files / total_files, 3) if total_files else 0,
        "syntax_errors": len(all_syntax_errors),
        "total_issues": len(all_issues),
        "by_type": by_type,
        "fixes_applied": len(fixes_applied),
    }

    return summary, all_syntax_errors, all_issues, fixes_applied, per_file


def record_history(summary):
    """Append summary to quality trend history (90-day cap).

    Also checks for week-over-week regression and auto-queues a P1 fix task
    via queue_writer when clean_ratio drops >15%.
    """
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    history = []
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE) as f:
                history = json.load(f)
        except (json.JSONDecodeError, ValueError):
            history = []

    # Regression guard: compare against ~7 days ago
    if len(history) >= 7:
        week_ago = history[-7]
        current_ratio = summary["clean_ratio"]
        prev_ratio = week_ago.get("clean_ratio", current_ratio)
        if prev_ratio > 0:
            pct_drop = (prev_ratio - current_ratio) / prev_ratio
            if pct_drop > 0.15:
                try:
                    sys.path.insert(0, str(SCRIPTS_DIR))
                    from queue_writer import add_task
                    drop_pct = round(pct_drop * 100)
                    fix_desc = (
                        f"[CODE_QUALITY_FIX] clean_ratio dropped {drop_pct}% "
                        f"week-over-week ({prev_ratio:.0%} -> {current_ratio:.0%}). "
                        f"Top issues: {summary.get('by_type', {})}. "
                        f"Run `code_quality_gate.py fix` to auto-fix unused imports."
                    )
                    add_task(fix_desc, priority="P1", source="quality_regression")
                except Exception:
                    pass  # Non-fatal — don't break the gate

    history.append(summary)
    history = history[-90:]

    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def print_report(summary, syntax_errors, issues, fixes, per_file):
    """Print human-readable report."""
    print("=== Code Quality Gate ===")
    print(f"Files scanned: {summary['total_files']}")
    print(f"Clean files:   {summary['clean_files']}/{summary['total_files']} ({summary['clean_ratio']:.0%})")
    print(f"Syntax errors: {summary['syntax_errors']}")
    print(f"Total issues:  {summary['total_issues']}")
    if summary["by_type"]:
        print(f"  Breakdown: {summary['by_type']}")

    if syntax_errors:
        print("\n--- Syntax Errors ---")
        for e in syntax_errors:
            print(f"  {Path(e['file']).name}:{e['line']}: {e['msg']}")

    if issues:
        # Only show undefined names (most critical)
        undefined = [i for i in issues if i["type"] == "undefined_name"]
        if undefined:
            print(f"\n--- Undefined Names ({len(undefined)}) ---")
            for i in undefined[:10]:
                print(f"  {Path(i['file']).name}:{i['line']}: {i['msg']}")
            if len(undefined) > 10:
                print(f"  ... and {len(undefined) - 10} more")

    if fixes:
        print(f"\n--- Auto-fixed ({len(fixes)} unused imports) ---")
        for fix in fixes:
            print(f"  {fix['file']}:{fix['line']}: removed '{fix['name']}'")

    print(f"\nQuality score: {summary['clean_ratio']:.0%}")


def show_trend():
    """Show quality trend from history."""
    if not HISTORY_FILE.exists():
        print("No quality history yet. Run 'scan' first.")
        return

    with open(HISTORY_FILE) as f:
        history = json.load(f)

    if not history:
        print("Empty history.")
        return

    print("=== Code Quality Trend ===")
    print(f"{'Date':<22} {'Files':<7} {'Clean':<7} {'Ratio':<7} {'Issues':<8} {'Fixes':<6}")
    print("-" * 60)
    for entry in history[-14:]:
        ts = entry["timestamp"][:19].replace("T", " ")
        print(f"{ts:<22} {entry['total_files']:<7} {entry['clean_files']:<7} "
              f"{entry['clean_ratio']:<7.0%} {entry['total_issues']:<8} {entry.get('fixes_applied', 0):<6}")

    if len(history) >= 2:
        first = history[0]["clean_ratio"]
        last = history[-1]["clean_ratio"]
        delta = last - first
        direction = "improving" if delta > 0 else "degrading" if delta < 0 else "stable"
        print(f"\nTrend: {first:.0%} -> {last:.0%} ({direction}, {delta:+.0%})")


def main():
    if len(sys.argv) < 2:
        print("Usage: code_quality_gate.py [scan|fix|trend]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "scan":
        summary, syntax_errors, issues, fixes, per_file = scan_all(do_fix=False)
        print_report(summary, syntax_errors, issues, fixes, per_file)
        record_history(summary)

    elif cmd == "fix":
        summary, syntax_errors, issues, fixes, per_file = scan_all(do_fix=True)
        print_report(summary, syntax_errors, issues, fixes, per_file)
        record_history(summary)

    elif cmd == "trend":
        show_trend()

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
