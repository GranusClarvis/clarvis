"""Chain-of-thought self-evaluation for episode quality scoring.

Analyzes reasoning chain quality by:
  1. Counting reasoning steps (depth)
  2. Detecting backtracking / correction patterns
  3. Measuring conclusion support (does the output follow from the reasoning?)

Complements trajectory.py (execution-level scoring) with reasoning-level scoring.
Can be used standalone or integrated into heartbeat postflight.

Usage:
    from clarvis.metrics.cot_evaluator import evaluate_cot, score_episode_cot

    # Score a single reasoning chain file
    result = evaluate_cot("/path/to/chain.json")

    # Score using both chain + session data
    result = score_episode_cot(chain_path="/path/to/chain.json",
                                session_path="/path/to/session.json")

CLI:
    python3 -m clarvis.metrics.cot_evaluator score <chain_id>
    python3 -m clarvis.metrics.cot_evaluator recent [--hours 24]
    python3 -m clarvis.metrics.cot_evaluator stats [--hours 168]
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import os

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
CHAINS_DIR = WORKSPACE / "data" / "reasoning_chains"
SESSIONS_DIR = CHAINS_DIR / "sessions"
SESSION_MAP = CHAINS_DIR / "session_map.json"
COT_HISTORY = WORKSPACE / "data" / "trajectory_eval" / "cot_history.jsonl"

# Weights for the composite CoT quality score
COT_WEIGHTS = {
    "depth": 0.20,           # Number of reasoning steps
    "backtracking": 0.20,    # Correction/backtracking detection
    "conclusion_support": 0.25,  # Does conclusion follow from steps?
    "evidence_density": 0.20,    # Fraction of steps with evidence
    "coherence": 0.15,          # Step-to-step logical flow
}


# --- Backtracking / correction detection ---

_BACKTRACK_PATTERNS = [
    re.compile(r"\b(actually|wait|correction|revise|reconsider|on second thought)\b", re.I),
    re.compile(r"\b(instead|rather than|not .* but|changed approach)\b", re.I),
    re.compile(r"\b(wrong|mistake|error in .* reasoning|go back)\b", re.I),
    re.compile(r"\b(retry|re-attempt|try again|different approach)\b", re.I),
]

_CORRECTION_INDICATORS = [
    re.compile(r"\b(fix|fixed|corrected|updated|amended)\b", re.I),
    re.compile(r"\b(previous .* (wrong|incorrect|flawed))\b", re.I),
]


def _detect_backtracking(steps: list[dict]) -> dict[str, Any]:
    """Detect backtracking and self-correction in reasoning steps."""
    backtrack_count = 0
    correction_count = 0
    backtrack_steps = []

    for step in steps:
        thought = step.get("thought", "")
        is_backtrack = any(p.search(thought) for p in _BACKTRACK_PATTERNS)
        is_correction = any(p.search(thought) for p in _CORRECTION_INDICATORS)

        if is_backtrack:
            backtrack_count += 1
            backtrack_steps.append(step.get("step", step.get("step_num", "?")))
        if is_correction:
            correction_count += 1

    return {
        "backtrack_count": backtrack_count,
        "correction_count": correction_count,
        "backtrack_steps": backtrack_steps,
        "has_self_correction": correction_count > 0,
    }


# --- Conclusion support measurement ---

def _extract_key_terms(text: str, min_len: int = 4) -> set[str]:
    """Extract meaningful terms from text, filtering stop words."""
    stop = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "to", "of", "in", "for", "on", "with", "at", "by", "from", "into",
        "and", "or", "but", "not", "this", "that", "it", "its", "they",
        "them", "their", "has", "have", "had", "will", "would", "could",
        "should", "may", "might", "shall", "can", "than", "then", "when",
        "where", "which", "what", "who", "how", "there", "here", "these",
        "those", "each", "every", "some", "any", "all", "most", "other",
        "more", "also", "just", "only", "very", "task", "step", "approach",
    }
    words = set(re.findall(r"[a-z]{%d,}" % min_len, text.lower()))
    return words - stop


def _measure_conclusion_support(steps: list[dict], outcome: str | None,
                                 summary: str | None) -> float:
    """Measure how well the conclusion/outcome is supported by reasoning steps.

    Returns 0.0-1.0 where 1.0 means the conclusion terms are well-covered
    by the reasoning chain's vocabulary.
    """
    if not steps:
        return 0.0

    # Gather all reasoning terms
    reasoning_terms: set[str] = set()
    for step in steps:
        thought = step.get("thought", "")
        reasoning_terms |= _extract_key_terms(thought)
        for ev in step.get("evidence", []):
            if isinstance(ev, str):
                reasoning_terms |= _extract_key_terms(ev)

    if not reasoning_terms:
        return 0.3  # Some reasoning happened but no extractable terms

    # Gather conclusion terms from outcome + summary
    conclusion_text = ""
    if outcome:
        conclusion_text += f" {outcome}"
    if summary:
        conclusion_text += f" {summary}"

    # Also use the last step's thought as part of the conclusion
    if steps:
        last = steps[-1].get("thought", "")
        conclusion_text += f" {last}"

    conclusion_terms = _extract_key_terms(conclusion_text)
    if not conclusion_terms:
        return 0.5  # No conclusion to evaluate

    # What fraction of conclusion terms appear in the reasoning chain?
    supported = conclusion_terms & reasoning_terms
    support_ratio = len(supported) / len(conclusion_terms) if conclusion_terms else 0.0

    # Normalize: 60%+ term overlap = full support, 0% = zero support
    return min(1.0, support_ratio / 0.6)


# --- Step-to-step coherence ---

def _compute_step_coherence(steps: list[dict]) -> float:
    """Measure coherence between consecutive reasoning steps.

    Uses term overlap between consecutive steps.
    Ideal: moderate overlap (0.1-0.4) — too high = repetition, too low = disconnected.
    """
    if len(steps) < 2:
        return 0.5

    overlaps = []
    for i in range(1, len(steps)):
        prev_terms = _extract_key_terms(steps[i - 1].get("thought", ""))
        curr_terms = _extract_key_terms(steps[i].get("thought", ""))
        if prev_terms and curr_terms:
            overlap = len(prev_terms & curr_terms) / max(1, len(prev_terms | curr_terms))
            overlaps.append(overlap)

    if not overlaps:
        return 0.5

    avg_overlap = sum(overlaps) / len(overlaps)
    # Bell curve peaking at 0.25
    coherence = 1.0 - 4.0 * (avg_overlap - 0.25) ** 2
    return max(0.0, min(1.0, coherence))


# --- Depth scoring ---

def _score_depth(num_steps: int) -> float:
    """Score reasoning depth. More steps = deeper reasoning, with diminishing returns."""
    if num_steps <= 0:
        return 0.0
    if num_steps == 1:
        return 0.2
    if num_steps == 2:
        return 0.5
    if num_steps <= 4:
        return 0.75
    if num_steps <= 7:
        return 0.9
    return 1.0  # 8+ steps


# --- Backtracking scoring ---

def _score_backtracking(bt: dict, num_steps: int) -> float:
    """Score backtracking quality.

    Some backtracking is GOOD (self-correction). Too much is bad (thrashing).
    Zero backtracking in a complex chain might mean lack of self-monitoring.
    """
    bt_count = bt["backtrack_count"]
    has_correction = bt["has_self_correction"]

    if num_steps <= 1:
        return 0.5  # Too short to evaluate

    bt_ratio = bt_count / num_steps

    if bt_count == 0:
        # No backtracking at all
        if num_steps >= 4:
            return 0.6  # Suspicious for complex chains — might be linear without self-check
        return 0.7  # Fine for short chains

    if has_correction:
        # Self-correction detected — this is valuable
        if bt_ratio <= 0.3:
            return 1.0  # Healthy self-correction
        if bt_ratio <= 0.5:
            return 0.8  # Moderate correction
        return 0.5  # Too much thrashing even with corrections

    # Backtracking without clear correction
    if bt_ratio <= 0.2:
        return 0.7  # Minor
    if bt_ratio <= 0.4:
        return 0.5  # Moderate confusion
    return 0.3  # Significant confusion


# --- Main evaluator ---

def evaluate_cot(chain_path: str | Path | None = None,
                 chain_data: dict | None = None,
                 session_path: str | Path | None = None,
                 session_data: dict | None = None) -> dict[str, Any]:
    """Evaluate chain-of-thought quality for a reasoning chain/session.

    Accepts either file paths or pre-loaded dicts.
    Returns a scored evaluation with component breakdown.
    """
    # Load chain data
    if chain_data is None and chain_path:
        chain_path = Path(chain_path)
        if chain_path.exists():
            chain_data = json.loads(chain_path.read_text())

    # Load session data
    if session_data is None and session_path:
        session_path = Path(session_path)
        if session_path.exists():
            session_data = json.loads(session_path.read_text())

    # Merge steps from both sources (chain has legacy format, session has richer format)
    steps = []
    outcome = None
    summary = None
    task = None

    if chain_data:
        steps = chain_data.get("steps", [])
        outcome = chain_data.get("outcome")
        task = chain_data.get("title", chain_data.get("task", ""))

    if session_data:
        session_steps = session_data.get("steps", [])
        if len(session_steps) >= len(steps):
            steps = session_steps  # Prefer session (has evidence, sub_problem, etc.)
        outcome = session_data.get("actual_outcome", outcome)
        summary = session_data.get("summary", summary)
        task = session_data.get("task", task)

    num_steps = len(steps)

    # Component scores
    depth_score = _score_depth(num_steps)
    bt_info = _detect_backtracking(steps)
    bt_score = _score_backtracking(bt_info, num_steps)
    conclusion_support = _measure_conclusion_support(steps, outcome, summary)
    coherence = _compute_step_coherence(steps)

    # Evidence density
    steps_with_evidence = sum(
        1 for s in steps
        if s.get("evidence") and len(s["evidence"]) > 0
    )
    evidence_density = steps_with_evidence / num_steps if num_steps > 0 else 0.0

    # Composite score
    composite = (
        COT_WEIGHTS["depth"] * depth_score
        + COT_WEIGHTS["backtracking"] * bt_score
        + COT_WEIGHTS["conclusion_support"] * conclusion_support
        + COT_WEIGHTS["evidence_density"] * evidence_density
        + COT_WEIGHTS["coherence"] * coherence
    )
    composite = round(min(1.0, max(0.0, composite)), 3)

    # Grade
    if composite >= 0.75:
        grade = "strong"
    elif composite >= 0.55:
        grade = "adequate"
    elif composite >= 0.35:
        grade = "weak"
    else:
        grade = "poor"

    # Issues
    issues = []
    if num_steps <= 1:
        issues.append("single_step_only")
    if evidence_density < 0.3:
        issues.append("low_evidence")
    if bt_info["backtrack_count"] > num_steps * 0.5 and num_steps > 2:
        issues.append("excessive_backtracking")
    if conclusion_support < 0.3:
        issues.append("unsupported_conclusion")
    if coherence < 0.3:
        issues.append("incoherent_chain")

    return {
        "task": (task or "")[:120],
        "num_steps": num_steps,
        "cot_score": composite,
        "cot_grade": grade,
        "components": {
            "depth": round(depth_score, 3),
            "backtracking": round(bt_score, 3),
            "conclusion_support": round(conclusion_support, 3),
            "evidence_density": round(evidence_density, 3),
            "coherence": round(coherence, 3),
        },
        "backtracking_detail": {
            "count": bt_info["backtrack_count"],
            "corrections": bt_info["correction_count"],
            "has_self_correction": bt_info["has_self_correction"],
        },
        "issues": issues,
        "outcome": outcome,
    }


def score_episode_cot(chain_id: str | None = None,
                      chain_path: str | Path | None = None,
                      session_path: str | Path | None = None) -> dict[str, Any]:
    """Score a single episode's chain-of-thought quality by ID or path.

    Looks up chain + session files if only an ID is given.
    """
    if chain_id and not chain_path:
        chain_path = CHAINS_DIR / f"{chain_id}.json"
        # Look up matching session via session_map.json
        if not session_path:
            try:
                smap = json.loads(SESSION_MAP.read_text()) if SESSION_MAP.exists() else {}
                sid = smap.get(chain_id)
                if sid:
                    session_candidate = SESSIONS_DIR / f"{sid}.json"
                    if session_candidate.exists():
                        session_path = session_candidate
            except (json.JSONDecodeError, OSError):
                pass
        # Fallback: try simple name substitution
        if not session_path:
            sid = chain_id.replace("chain_", "rs_")
            session_candidate = SESSIONS_DIR / f"{sid}.json"
            if session_candidate.exists():
                session_path = session_candidate

    result = evaluate_cot(chain_path=chain_path, session_path=session_path)
    return result


def record_cot_score(result: dict[str, Any]) -> dict[str, Any]:
    """Append a CoT evaluation result to history."""
    COT_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(result)
    payload.setdefault("ts", datetime.now(timezone.utc).isoformat())
    with open(COT_HISTORY, "a") as f:
        f.write(json.dumps(payload) + "\n")
    return payload


def evaluate_recent(hours: int = 24) -> list[dict[str, Any]]:
    """Evaluate all reasoning chains from the last N hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    results = []

    for chain_file in sorted(CHAINS_DIR.glob("chain_*.json")):
        try:
            data = json.loads(chain_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        created_str = data.get("created", "")
        if not created_str:
            continue
        try:
            created = datetime.fromisoformat(created_str)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

        if created < cutoff:
            continue

        chain_id = chain_file.stem
        result = score_episode_cot(chain_id=chain_id, chain_path=chain_file)
        result["chain_id"] = chain_id
        results.append(result)

    return results


def summarize_cot(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize CoT evaluation results."""
    if not results:
        return {"episodes": 0, "avg_cot_score": None, "grade_distribution": {}}

    scores = [r["cot_score"] for r in results]
    grades = {}
    for r in results:
        g = r["cot_grade"]
        grades[g] = grades.get(g, 0) + 1

    all_issues: dict[str, int] = {}
    for r in results:
        for issue in r.get("issues", []):
            all_issues[issue] = all_issues.get(issue, 0) + 1

    avg_components: dict[str, float] = {}
    for key in COT_WEIGHTS:
        vals = [r["components"][key] for r in results if key in r.get("components", {})]
        if vals:
            avg_components[key] = round(sum(vals) / len(vals), 3)

    return {
        "episodes": len(results),
        "avg_cot_score": round(sum(scores) / len(scores), 3),
        "grade_distribution": grades,
        "avg_components": avg_components,
        "common_issues": dict(sorted(all_issues.items(), key=lambda x: -x[1])[:5]),
    }


def format_cot_summary(summary: dict[str, Any], hours: int = 24) -> str:
    """Format a human-readable CoT evaluation summary."""
    lines = [f"=== CoT Quality Summary (last {hours}h) ==="]
    lines.append(f"Episodes evaluated: {summary.get('episodes', 0)}")

    if summary.get("episodes", 0) == 0:
        return "\n".join(lines)

    lines.append(f"Avg CoT score: {summary['avg_cot_score']:.3f}")
    lines.append("Grades:")
    for grade, count in sorted(summary.get("grade_distribution", {}).items()):
        lines.append(f"  {grade}: {count}")
    lines.append("Avg components:")
    for k, v in sorted(summary.get("avg_components", {}).items()):
        lines.append(f"  {k}: {v:.3f}")
    if summary.get("common_issues"):
        lines.append("Common issues:")
        for issue, count in summary["common_issues"].items():
            lines.append(f"  {issue}: {count}")
    return "\n".join(lines)


# --- CLI ---

def main():
    import sys
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("Usage: python3 -m clarvis.metrics.cot_evaluator <command> [args]")
        print("Commands:")
        print("  score <chain_id>         Score a single chain")
        print("  recent [--hours N]       Evaluate recent chains (default 24h)")
        print("  stats [--hours N]        Summary statistics (default 168h)")
        return

    cmd = args[0]

    if cmd == "score":
        if len(args) < 2:
            print("Usage: score <chain_id>")
            return
        result = score_episode_cot(chain_id=args[1])
        print(json.dumps(result, indent=2))

    elif cmd == "recent":
        hours = 24
        if "--hours" in args:
            idx = args.index("--hours")
            if idx + 1 < len(args):
                hours = int(args[idx + 1])
        results = evaluate_recent(hours=hours)
        for r in results:
            record_cot_score(r)
            print(f"  [{r['cot_grade']:>8}] {r['cot_score']:.3f} | {r['task'][:70]}")
        print()
        summary = summarize_cot(results)
        print(format_cot_summary(summary, hours))

    elif cmd == "stats":
        hours = 168
        if "--hours" in args:
            idx = args.index("--hours")
            if idx + 1 < len(args):
                hours = int(args[idx + 1])
        results = evaluate_recent(hours=hours)
        summary = summarize_cot(results)
        print(format_cot_summary(summary, hours))

    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
