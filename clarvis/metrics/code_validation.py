"""
Deterministic Code Validation — Pattern 1 from PyCapsule research.

Provides pre-LLM validation for code generated during heartbeat tasks.
Runs fast, deterministic checks BEFORE feeding errors back to LLM debug loops.

Research basis:
- PyCapsule (arXiv:2502.02928): 3 deterministic error pre-processing steps
- MapCoder (arXiv:2405.11403): Plan-derived debugging context
- In-Exec Self-Debug (arXiv:2501.12793): Runtime state > test verdicts

Usage:
    from clarvis.metrics.code_validation import validate_python_file, validate_output
    result = validate_python_file("/path/to/file.py")
    # result = {"valid": True/False, "errors": [...], "refinement": "..."}
"""

import ast
import os
import re
import sys


# Maximum debug iterations before giving up (Pattern 2: exponential decay caps)
MAX_DEBUG_ITERATIONS = 3

# Error categories (Pattern 1: PyCapsule error type classification)
ERROR_TYPES = {
    "syntax": "Code has syntax errors — cannot be parsed",
    "import": "Missing or broken imports",
    "structure": "Structural issues (bare excepts, oversized functions)",
    "runtime": "Runtime errors detected in output",
    "test": "Test failures",
}


def validate_python_file(filepath):
    """Run deterministic validation on a Python file.

    Returns dict with:
        valid: bool — all checks passed
        errors: list of {type, message, line} dicts
        refinement: str — concise error summary for LLM (Pattern 1: filtered context)
    """
    errors = []

    try:
        with open(filepath, "r") as f:
            content = f.read()
    except (OSError, IOError) as e:
        return {"valid": False, "errors": [{"type": "io", "message": str(e)}], "refinement": str(e)}

    # Stage 1: Syntax check
    try:
        tree = ast.parse(content, filename=filepath)
    except SyntaxError as e:
        errors.append({
            "type": "syntax",
            "message": f"SyntaxError: {e.msg}",
            "line": e.lineno,
            "text": e.text.strip() if e.text else "",
        })
        refinement = f"Syntax error at line {e.lineno}: {e.msg}"
        if e.text:
            refinement += f"\n  {e.text.strip()}"
        return {"valid": False, "errors": errors, "refinement": refinement}

    # Stage 2: Import analysis (static — no runtime imports)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.names:
            for alias in node.names:
                if alias.name == '*':
                    errors.append({
                        "type": "import",
                        "message": f"Star import from {node.module}",
                        "line": node.lineno,
                    })

    # Stage 3: Structural checks
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, 'end_lineno') and node.end_lineno:
                length = node.end_lineno - node.lineno
                if length > 100:
                    errors.append({
                        "type": "structure",
                        "message": f"Function '{node.name}' is {length} lines (>100)",
                        "line": node.lineno,
                    })

        if isinstance(node, ast.ExceptHandler) and node.type is None:
            errors.append({
                "type": "structure",
                "message": "Bare except clause (catches all exceptions including KeyboardInterrupt)",
                "line": node.lineno,
            })

    # Build refinement (Pattern 1: filtered, relevant error context for LLM)
    if errors:
        lines = []
        for e in errors[:5]:  # Cap at 5 errors (Pattern 2: don't overwhelm)
            loc = f" (line {e['line']})" if "line" in e else ""
            lines.append(f"- [{e['type']}]{loc}: {e['message']}")
        refinement = "Validation issues:\n" + "\n".join(lines)
    else:
        refinement = ""

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "refinement": refinement,
    }


def validate_output(output_text, task_description=""):
    """Classify errors in execution output (Pattern 1: error type analysis).

    Filters and truncates error output to keep LLM context clean.
    Returns dict with error classification and refined context.
    """
    if not output_text:
        return {"has_errors": False, "error_type": None, "refinement": ""}

    text = output_text[-3000:]  # Only look at tail (Pattern 5: Markov pruning)
    text_lower = text.lower()

    detected = []

    # Detect Python tracebacks
    tb_pattern = re.compile(r'Traceback \(most recent call last\):.*?(?=\n\S|\Z)', re.DOTALL)
    tracebacks = tb_pattern.findall(text)
    if tracebacks:
        # Take only the last traceback (Pattern 5: most recent only)
        last_tb = tracebacks[-1]
        # Truncate long tracebacks (Pattern 1: critical error truncation)
        tb_lines = last_tb.split('\n')
        if len(tb_lines) > 10:
            tb_lines = tb_lines[:3] + ["  ... (truncated)"] + tb_lines[-5:]
        detected.append({
            "type": "runtime",
            "summary": tb_lines[-1] if tb_lines else "Unknown error",
            "traceback": "\n".join(tb_lines),
        })

    # Detect test failures
    test_fail_match = re.search(r'(\d+)\s+failed', text_lower)
    test_pass_match = re.search(r'(\d+)\s+passed', text_lower)
    if test_fail_match:
        failed = int(test_fail_match.group(1))
        passed = int(test_pass_match.group(1)) if test_pass_match else 0
        detected.append({
            "type": "test",
            "summary": f"{failed} tests failed, {passed} passed",
        })

    # Detect permission/system errors
    if any(kw in text_lower for kw in ["permission denied", "no such file", "command not found"]):
        detected.append({"type": "system", "summary": "System-level error detected"})

    if not detected:
        return {"has_errors": False, "error_type": None, "refinement": ""}

    primary = detected[0]
    refinement_parts = []
    if task_description:
        refinement_parts.append(f"Task: {task_description[:100]}")
    for d in detected[:3]:
        refinement_parts.append(f"[{d['type']}] {d['summary']}")
        if "traceback" in d:
            refinement_parts.append(d["traceback"])

    return {
        "has_errors": True,
        "error_type": primary["type"],
        "errors": detected,
        "refinement": "\n".join(refinement_parts),
    }


def should_retry(iteration, error_type, task_description=""):
    """Decide whether to retry based on iteration count and error type.

    Implements Pattern 2 (exponential decay caps) and Pattern 3 (plan-derived strategy).

    Returns dict with:
        retry: bool — should we retry?
        strategy: str — "same_approach" or "alternative_approach"
        reason: str — why this decision
    """
    if iteration >= MAX_DEBUG_ITERATIONS:
        return {
            "retry": False,
            "strategy": "give_up",
            "reason": f"Max iterations ({MAX_DEBUG_ITERATIONS}) reached — exponential decay cap",
        }

    # System errors are unlikely to be fixed by retry
    if error_type == "system":
        return {
            "retry": False,
            "strategy": "escalate",
            "reason": "System errors need infrastructure fix, not code retry",
        }

    # Timeout — try with reduced scope (Pattern 3: alternative plan)
    if error_type == "timeout":
        return {
            "retry": iteration < 2,
            "strategy": "alternative_approach",
            "reason": "Timeout — reduce scope or split task" if iteration < 2 else "Multiple timeouts",
        }

    # First retry: same approach with error context
    if iteration == 0:
        return {
            "retry": True,
            "strategy": "same_approach",
            "reason": "First attempt failed — retry with error context",
        }

    # Second retry: switch strategy (Pattern 3: MapCoder multi-plan fallback)
    return {
        "retry": True,
        "strategy": "alternative_approach",
        "reason": f"Iteration {iteration} — switch to alternative approach",
    }
