"""
Quality Metrics for Clarvis — Beyond Binary Success.

This module provides quality measurement for task outcomes,
not just completion/failure. Addresses audit finding that
"88% success could mean 88% mediocre."

Quality Dimensions:
  1. Task Quality Score — outcome quality, not just completion
  2. Code Quality Score — lint, structure, security for generated code
  3. Semantic Depth — meaningful connections in responses
  4. Efficiency Score — quality per token spent

These metrics feed into the performance benchmark PI calculation.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))


def compute_task_quality_score(days=7):
    """Compute task quality score based on episode outcomes.

    Quality isn't binary — a "completed" task could be:
    - Minimal (just did enough to pass)
    - Thorough (addressed root cause)
    - Excellent (went above and beyond)

    This looks at episode valence, confidence calibration, and
    whether the same task recurs (indicating poor fix).
    """
    try:
        from clarvis.memory.episodic_memory import EpisodicMemory
        em = EpisodicMemory()
        stats = em.get_stats()

        # Base: episode success rate (still matters)
        outcomes = stats.get("outcomes", {})
        total = stats.get("total", 0)
        successes = outcomes.get("success", 0)
        soft_failures = outcomes.get("soft_failure", 0)
        real_total = max(total - soft_failures, 1)
        success_rate = successes / real_total

        # Quality factor 1: Average valence (positive = good outcomes)
        # High valence = user satisfied, issue fully resolved
        avg_valence = stats.get("avg_valence", 0.5)
        valence_score = max(0, min(1, (avg_valence + 1) / 2))  # -1..1 -> 0..1

        # Quality factor 2: Strong memories ratio
        # More strong memories = important lessons learned
        strong_memories = stats.get("strong_memories", 0)
        strong_ratio = strong_memories / max(real_total, 1)

        # Quality factor 3: Recurrence penalty
        # Same task appearing repeatedly = poor quality fix
        from clarvis.brain import brain
        try:
            # Count how many "fix" tasks are in recent episodes
            recent_episodes = em.get_recent(limit=50)
            fix_pattern = re.compile(r'fix|bug|issue|error|broken', re.I)
            fix_count = sum(1 for ep in recent_episodes if fix_pattern.search(ep.get("task", "")))
            recurrence_penalty = min(fix_count / max(len(recent_episodes), 1), 1.0)
        except Exception:
            recurrence_penalty = 0.0

        # Quality factor 4: Action accuracy as quality proxy
        action_accuracy = stats.get("action_accuracy", success_rate)

        # Composite: weighted combination
        quality_score = (
            0.30 * success_rate +           # Did it work?
            0.20 * valence_score +          # Was it a good outcome?
            0.15 * strong_ratio +           # Did we learn from it?
            0.15 * action_accuracy +        # Did we do the right thing?
            0.20 * (1 - recurrence_penalty) # Did we actually fix it?
        )

        return {
            "quality_score": round(quality_score, 3),
            "components": {
                "success_rate": round(success_rate, 3),
                "valence_score": round(valence_score, 3),
                "strong_memory_ratio": round(strong_ratio, 3),
                "recurrence_penalty": round(recurrence_penalty, 3),
                "action_accuracy": round(action_accuracy, 3),
            },
            "total_episodes": total,
            "real_episodes": real_total,
        }

    except Exception as e:
        return {"quality_score": 0.5, "error": str(e)}


def _ast_structural_checks(tree, content):
    """Deterministic structural quality checks on an AST (Pattern 1: PyCapsule).

    Returns a dict of check_name -> pass/fail (bool) for:
    - no_bare_except: no `except:` without exception type
    - reasonable_function_length: no function >200 lines (raised from 100; see
      DECOMPOSITION_REMEDIATION plan 2026-03-29 — 100 caused false positives on
      healthy orchestrators/renderers)
    - no_star_imports: no `from X import *`
    - has_error_handling: try/except present if file has I/O or network calls
    """
    import ast

    results = {}

    # Check 1: No bare except clauses (anti-pattern that hides bugs)
    bare_excepts = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            bare_excepts += 1
    results["no_bare_except"] = bare_excepts == 0

    # Check 2: Reasonable function length (<200 lines)
    long_funcs = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, 'end_lineno') and node.end_lineno:
                length = node.end_lineno - node.lineno
                if length > 200:
                    long_funcs += 1
    results["reasonable_function_length"] = long_funcs == 0

    # Check 3: No star imports (namespace pollution)
    star_imports = sum(
        1 for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.names
        and any(alias.name == '*' for alias in node.names)
    )
    results["no_star_imports"] = star_imports == 0

    # Check 4: Error handling present if file does I/O
    io_patterns = re.compile(r'open\(|subprocess\.|requests\.|urlopen|socket\.')
    has_io = bool(io_patterns.search(content))
    has_try = any(isinstance(n, ast.Try) for n in ast.walk(tree))
    results["has_error_handling"] = (not has_io) or has_try

    return results


def _test_pass_rate():
    """Check latest pytest results (Pattern 1: deterministic validation).

    Reads cached test results rather than running pytest (too slow for scoring).
    Returns float 0.0-1.0 or None if no data.
    """
    # Check for recent pytest results in common locations
    test_result_paths = [
        os.path.join(WORKSPACE, "data/test_results.json"),
        os.path.join(WORKSPACE, ".pytest_cache/v/cache/lastfailed"),
    ]

    # Try data/test_results.json (written by postflight or CI)
    results_file = test_result_paths[0]
    if os.path.exists(results_file):
        try:
            age = datetime.now(timezone.utc).timestamp() - os.path.getmtime(results_file)
            if age < 86400 * 3:  # Within 3 days
                with open(results_file) as f:
                    data = json.load(f)
                passed = data.get("passed", 0)
                failed = data.get("failed", 0)
                total = passed + failed
                if total > 0:
                    return passed / total
        except Exception:
            pass

    # Fallback: check .pytest_cache/lastfailed
    lastfailed_path = test_result_paths[1]
    if os.path.exists(lastfailed_path):
        try:
            with open(lastfailed_path) as f:
                failed = json.load(f)
            # Empty dict = all passed last time
            if isinstance(failed, dict):
                return 1.0 if len(failed) == 0 else max(0.0, 1.0 - len(failed) / 100)
        except Exception:
            pass

    return None


def _first_pass_success_rate():
    """Episode-derived first-pass success rate for code tasks.

    From In-Execution Self-Debugging research: measures how often code
    tasks succeed without needing retries. Higher = better code generation.
    Returns float 0.0-1.0 or None if insufficient data.
    """
    try:
        from clarvis.memory.episodic_memory import EpisodicMemory
        em = EpisodicMemory()
        recent = em.get_recent(limit=50)

        code_pattern = re.compile(
            r'code|implement|fix|create|add|write|refactor|migrate|wire|test|build',
            re.I
        )
        code_episodes = [
            ep for ep in recent
            if ep.get("is_code_task") or code_pattern.search(ep.get("task", ""))
        ]

        if len(code_episodes) < 5:
            return None

        # Count episodes that succeeded (not retry/rework of same task)
        successes = sum(1 for ep in code_episodes if ep.get("outcome") == "success")
        return round(successes / len(code_episodes), 3)
    except Exception:
        return None


def compute_code_quality_score(days=7):
    """Compute code generation quality score.

    Enhanced with research-informed checks (PyCapsule deterministic
    pre-processing, MapCoder test-as-oracle, In-Exec self-debugging):
    1. Lint pass rate (syntax)
    2. Import integrity (static analysis, no runtime import)
    3. Security issues (secrets, hardcoded creds)
    4. Structural quality (bare excepts, function length, star imports)
    5. Test pass rate (from cached pytest results)
    6. First-pass success rate (episode-derived code task outcomes)
    """
    import ast

    try:
        # Check for recent code files in workspace
        code_extensions = {".py", ".js", ".ts", ".sh", ".yaml", ".yml", ".json"}
        recent_files = []
        cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)

        for root, dirs, files in os.walk(WORKSPACE):
            # Skip data, memory, .git directories
            if any(skip in root for skip in ["data/", "memory/", ".git/", "node_modules/"]):
                continue
            for f in files:
                if any(f.endswith(ext) for ext in code_extensions):
                    path = os.path.join(root, f)
                    try:
                        if os.path.getmtime(path) > cutoff:
                            recent_files.append(path)
                    except Exception:
                        pass

        if not recent_files:
            return {"quality_score": 0.7, "reason": "no_recent_code"}

        # Filter to Python files (only type we actually check)
        py_files = [f for f in recent_files if f.endswith(".py")]

        results = {
            "lint_passed": 0,
            "imports_valid": 0,
            "secrets_clean": 0,
            "structural_passed": 0,
            "total_checked": len(py_files),
            "total_recent_files": len(recent_files),
            "structural_details": {},
        }

        # Known Clarvis/local modules — skip runtime import checks for these
        known_local_modules = {
            "brain", "attention", "episodic_memory", "clarvis", "clarvis_confidence",
            "clarvis_reasoning", "reasoning_chain_hook", "procedural_memory",
            "context_compressor", "digest_writer", "evolution_loop", "extract_steps",
            "benchmark_brief", "performance_benchmark", "performance_gate",
            "latency_budget", "world_models", "meta_gradient_rl", "self_representation",
            "self_model", "soar_engine", "hyperon_atomspace", "workspace_broadcast",
            "brain_bridge", "cognitive_workspace", "tool_maker", "import_health",
            "retrieval_quality", "prediction_resolver", "prompt_optimizer",
            "clarvis_browser", "browser_agent", "task_router", "project_agent",
        }

        for filepath in py_files:
            try:
                with open(filepath, "r") as f:
                    content = f.read()

                # Check 1: Basic syntax (ast.parse)
                try:
                    tree = ast.parse(content)
                    results["lint_passed"] += 1
                except SyntaxError:
                    continue  # Can't do further checks without AST

                # Check 2: Import integrity (static, no runtime __import__)
                imports = re.findall(r'^import\s+(\w+)|^from\s+(\w+)', content, re.MULTILINE)
                if imports:
                    valid = True
                    for imp in imports[:10]:
                        mod = imp[0] or imp[1]
                        # Standard library and known local modules are always valid
                        if mod in {"os", "sys", "json", "re", "datetime", "time", "pathlib",
                                   "subprocess", "collections", "typing", "functools",
                                   "itertools", "hashlib", "math", "copy", "io", "abc",
                                   "dataclasses", "enum", "contextlib", "signal",
                                   "tempfile", "shutil", "glob", "argparse", "logging",
                                   "unittest", "pytest", "textwrap", "threading",
                                   "traceback", "uuid", "warnings", "importlib"}:
                            continue
                        if mod in known_local_modules:
                            continue
                        # For unknown modules, check if importable (but don't fail hard)
                        try:
                            __import__(mod)
                        except ImportError:
                            valid = False
                            break
                    if valid:
                        results["imports_valid"] += 1
                else:
                    results["imports_valid"] += 1

                # Check 3: No hardcoded secrets
                secret_patterns = [
                    r'password\s*=\s*["\'][^"\']{8,}',
                    r'api[_-]?key\s*=\s*["\'][A-Za-z0-9]{20,}',
                    r'secret\s*=\s*["\'][^"\']{20,}',
                    r'0x[a-fA-F0-9]{40}',
                ]
                has_secret = any(re.search(p, content, re.I) for p in secret_patterns)
                if not has_secret:
                    results["secrets_clean"] += 1

                # Check 4: Structural quality (new, from PyCapsule research)
                struct = _ast_structural_checks(tree, content)
                passed = sum(1 for v in struct.values() if v)
                total_checks = len(struct)
                if total_checks > 0 and passed / total_checks >= 0.75:
                    results["structural_passed"] += 1
                # Track per-check stats
                for check_name, check_passed in struct.items():
                    results["structural_details"].setdefault(check_name, {"pass": 0, "fail": 0})
                    results["structural_details"][check_name]["pass" if check_passed else "fail"] += 1

            except Exception:
                pass

        total = results["total_checked"]
        if total == 0:
            return {"quality_score": 0.7, "reason": "no_python_files"}

        # Per-file scores
        lint_score = results["lint_passed"] / max(total, 1)
        import_score = results["imports_valid"] / max(total, 1)
        secret_score = results["secrets_clean"] / max(total, 1)
        structural_score = results["structural_passed"] / max(total, 1)

        # Cross-file scores (from cached data, not per-file)
        test_rate = _test_pass_rate()
        first_pass = _first_pass_success_rate()

        # Composite: rebalanced weights (research-informed)
        # Base: per-file static analysis (60%)
        # Enhanced: cross-file quality signals (40%)
        base_score = (
            0.20 * lint_score +
            0.15 * import_score +
            0.10 * secret_score +
            0.15 * structural_score
        )

        enhanced_score = 0.0
        enhanced_weight = 0.0
        if test_rate is not None:
            enhanced_score += 0.20 * test_rate
            enhanced_weight += 0.20
        if first_pass is not None:
            enhanced_score += 0.20 * first_pass
            enhanced_weight += 0.20

        # If no enhanced signals, redistribute weight to base
        if enhanced_weight == 0:
            quality_score = base_score / 0.60  # Normalize to 0-1
        else:
            quality_score = base_score + enhanced_score + (0.40 - enhanced_weight) * (base_score / 0.60)

        components = {
            "lint_pass_rate": round(lint_score, 3),
            "import_valid_rate": round(import_score, 3),
            "secrets_clean_rate": round(secret_score, 3),
            "structural_pass_rate": round(structural_score, 3),
        }
        if test_rate is not None:
            components["test_pass_rate"] = round(test_rate, 3)
        if first_pass is not None:
            components["first_pass_success_rate"] = round(first_pass, 3)

        # Structural breakdown
        struct_summary = {}
        for check_name, counts in results["structural_details"].items():
            t = counts["pass"] + counts["fail"]
            struct_summary[check_name] = round(counts["pass"] / max(t, 1), 3)
        if struct_summary:
            components["structural_breakdown"] = struct_summary

        return {
            "quality_score": round(quality_score, 3),
            "components": components,
            "files_checked": total,
        }

    except Exception as e:
        return {"quality_score": 0.5, "error": str(e)}


def compute_semantic_depth():
    """Compute semantic depth score - how meaningful are connections?"""
    try:
        from clarvis.brain import brain
        stats = brain.stats()

        # Semantic depth based on:
        # 1. Cross-collection connections
        # 2. Graph density (already in metrics)
        # 3. Average connection strength

        collections = stats.get("collections", {})
        total_mem = stats.get("total_memories", 0)
        edges = stats.get("graph_edges", 0)

        if total_mem == 0:
            return {"depth_score": 0.0, "reason": "no_memories"}

        # Cross-collection overlap (semantic richness)
        if collections:
            collection_names = list(collections.keys())
            # Check if memories reference multiple collections
            # This is a proxy - real implementation would analyze memory content
            cross_collection_score = min(len(collection_names) / 10, 1.0)  # 10+ collections = full
        else:
            cross_collection_score = 0.0

        # Graph density as connectivity indicator
        density = edges / max(total_mem, 1)
        density_score = min(density / 2.0, 1.0)  # 2.0+ density = full

        # Composite
        depth_score = 0.4 * cross_collection_score + 0.6 * density_score

        return {
            "depth_score": round(depth_score, 3),
            "components": {
                "cross_collection_score": round(cross_collection_score, 3),
                "density_score": round(density_score, 3),
            },
            "collections": len(collections) if collections else 0,
        }

    except Exception as e:
        return {"depth_score": 0.5, "error": str(e)}


def compute_efficiency_score():
    """Compute efficiency score - quality per token spent."""
    try:
        # This would ideally come from cost tracking
        # For now, derive from context compression * success rate

        from clarvis.context.compressor import generate_tiered_brief

        # Measure compression efficiency
        brief = generate_tiered_brief("efficiency test", "standard", [])
        brief_len = len(brief) if brief else 0

        # Lower brief size = higher efficiency
        # Target: <2000 tokens for standard brief
        if brief_len > 0:
            compression_score = max(0, 1 - (brief_len / 3000))
        else:
            compression_score = 0.5

        # Success rate from episodes
        try:
            from clarvis.memory.episodic_memory import EpisodicMemory
            em = EpisodicMemory()
            stats = em.get_stats()
            outcomes = stats.get("outcomes", {})
            successes = outcomes.get("success", 0)
            total = stats.get("total", 1)
            success_rate = successes / max(total, 1)
        except Exception:
            success_rate = 0.7

        efficiency = compression_score * 0.4 + success_rate * 0.6

        return {
            "efficiency_score": round(efficiency, 3),
            "components": {
                "compression_score": round(compression_score, 3),
                "success_rate": round(success_rate, 3),
            },
            "brief_length": brief_len,
        }

    except Exception as e:
        return {"efficiency_score": 0.5, "error": str(e)}


def get_all_quality_metrics():
    """Get all quality metrics for benchmark integration."""
    return {
        "task_quality": compute_task_quality_score(),
        "code_quality": compute_code_quality_score(),
        "semantic_depth": compute_semantic_depth(),
        "efficiency": compute_efficiency_score(),
    }


# ---------------------------------------------------------------------------
# Advisory structural complexity risk (separate from quality scoring pipeline)
# ---------------------------------------------------------------------------
# This function is ADVISORY ONLY. It must NOT feed into compute_code_quality_score(),
# PI dimensions, or any autonomous optimization loop. See:
#   docs/DECOMPOSITION_REMEDIATION_AND_STRUCTURAL_POLICY_PLAN_2026-03-29.md
# ---------------------------------------------------------------------------

_ROLE_KEYWORDS = {
    "orchestrator": ["run_", "execute_", "main", "pipeline", "process_all", "dispatch"],
    "renderer": ["render_", "format_", "generate_html", "build_report", "_css", "template"],
    "algorithmic": ["compute_", "calculate_", "score_", "evaluate_", "benchmark"],
}


def structural_complexity_risk(file_path: str) -> dict:
    """Compute advisory structural risk for a Python file.

    Uses 3 signals (per executive review 2026-03-29):
      1. Length bucket (>120 / >180 / >260)
      2. Caller count proxy (single-caller helpers = fragmentation signal)
      3. Role classification (orchestrator / renderer / algorithmic / unknown)

    Returns:
        {
            "file": str,
            "risk": "low" | "medium" | "high",
            "candidates": [
                {"function": str, "lines": int, "role": str, "reasons": [str]}
            ]
        }

    INVARIANT: This output is informational. It must never be used to
    auto-generate queue tasks or feed into scoring pipelines.
    """
    import ast

    result = {"file": file_path, "risk": "low", "candidates": []}
    try:
        with open(file_path) as f:
            source = f.read()
        tree = ast.parse(source)
    except Exception:
        return result

    # Collect all function names for caller-count estimation
    all_func_names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            all_func_names.add(node.name)

    # Count how many times each name is called (rough proxy for caller count)
    call_counts: dict[str, int] = {name: 0 for name in all_func_names}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            callee_name = None
            if isinstance(node.func, ast.Name):
                callee_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                callee_name = node.func.attr
            if callee_name and callee_name in call_counts:
                call_counts[callee_name] += 1

    max_risk = "low"
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end_line = getattr(node, "end_lineno", None)
        if end_line is None:
            continue
        length = end_line - node.lineno + 1
        if length <= 120:
            continue

        reasons = []
        func_name = node.name

        # Signal 1: length bucket
        if length > 260:
            reasons.append("very_long_function")
            risk = "high"
        elif length > 180:
            reasons.append("long_function")
            risk = "medium"
        else:
            reasons.append("moderately_long_function")
            risk = "low"

        # Signal 2: role classification (dampens risk for orchestrators/renderers)
        role = "unknown"
        for role_name, keywords in _ROLE_KEYWORDS.items():
            if any(kw in func_name.lower() for kw in keywords):
                role = role_name
                break
        if role in ("orchestrator", "renderer") and risk == "medium":
            risk = "low"
            reasons.append(f"role_{role}_dampened")

        # Signal 3: if this is a helper with only 1 caller, it's a fragmentation signal
        callers = call_counts.get(func_name, 0)
        if callers <= 1 and length < 30 and not func_name.startswith("_"):
            reasons.append("single_caller_small_helper")

        if risk == "high":
            max_risk = "high"
        elif risk == "medium" and max_risk != "high":
            max_risk = "medium"

        if risk != "low":
            result["candidates"].append({
                "function": func_name, "lines": length, "role": role, "reasons": reasons,
            })

    result["risk"] = max_risk
    return result


if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "structural-risk":
        targets = sys.argv[2:] if len(sys.argv) > 2 else []
        for path in targets:
            report = structural_complexity_risk(path)
            print(json.dumps(report, indent=2))
    else:
        metrics = get_all_quality_metrics()
        print(json.dumps(metrics, indent=2))