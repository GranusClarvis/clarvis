#!/usr/bin/env python3
import os
"""PR Factory Phase 3 — Execution Brief Compiler + Writeback.

Builds a contextual execution brief from artifacts, indexes, and LiteBrain,
injected into spawn prompts. After task completion, runs mandatory writeback
to store episode summaries, atomic facts, procedures, and golden QA.

Usage:
    from pr_factory import build_factory_context, run_writeback, classify_task
    brief = build_factory_context("star-world-order", "Fix login bug", agent_dir)
    # ... spawn and get result ...
    run_writeback("star-world-order", agent_dir, result, "Fix login bug")
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

CLARVIS_WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))

# ── Task Classification ──

TASK_CLASSES = {
    "bugfix":        ["fix", "bug", "broken", "crash", "error", "regression", "issue"],
    "feature":       ["add", "implement", "create", "new feature", "feature", "support"],
    "refactor":      ["refactor", "restructure", "reorganize", "clean up", "simplify",
                      "extract", "consolidate", "migrate"],
    "docs":          ["document", "readme", "docstring", "docs", "comment", "jsdoc"],
    "tests":         ["test", "spec", "coverage", "e2e", "unit test", "integration test"],
    "config":        ["config", "ci", "cd", "workflow", "yaml", "toml", "eslint",
                      "tsconfig", "dockerfile", "deploy"],
    "hardening":     ["harden", "security", "validate", "sanitize", "guard", "lint",
                      "type-check", "strict"],
    "investigation": ["investigate", "debug", "profile", "analyze", "diagnose",
                      "benchmark", "audit"],
}

DEFAULT_TASK_CLASS = "feature"


def classify_task(task: str) -> str:
    """Classify task string into one of the known task classes.

    Uses keyword matching against task text (case-insensitive).
    Returns the class with the most keyword hits; ties broken by
    declaration order (earlier = higher priority).
    """
    task_lower = task.lower()
    best_class = DEFAULT_TASK_CLASS
    best_score = 0

    for cls, keywords in TASK_CLASSES.items():
        score = sum(1 for kw in keywords if kw in task_lower)
        if score > best_score:
            best_score = score
            best_class = cls

    return best_class


# ── Execution Brief Compiler ──

BRIEF_TOKEN_CAP = 2000  # Hard cap in chars (~500 tokens)


def build_execution_brief(name: str, task: str, agent_dir: Path) -> dict:
    """Compile an execution brief from artifacts, indexes, and LiteBrain.

    Returns a dict with the brief schema. Also saves to
    <agent_dir>/data/execution_brief.json.
    """
    task_class = classify_task(task)

    brief = {
        "task_interpretation": task[:300],
        "task_class": task_class,
        "success_criteria": _infer_success_criteria(task, task_class),
        "non_negotiables": _get_non_negotiables(task_class),
        "relevant_files": [],
        "artifact_excerpts": {},
        "relevant_facts": [],
        "relevant_episodes": [],
        "sector_constraints": [],
        "required_validations": [],
        "verify_loop": {
            "max_refinements": 2,
            "allowed_triggers": [
                "test_failure", "requirement_miss",
                "scope_bloat", "pr_class_upgradeable",
            ],
        },
        "pr_class_decision": {
            "default": "A",
            "downgrade_to_B_if": "real blocker prevents full closure",
            "downgrade_to_C_if": "concrete blocker prevents the task entirely",
        },
        "compiled_at": datetime.now(timezone.utc).isoformat(),
    }

    # Load artifacts (once, used for excerpts + fact enrichment)
    artifacts = {}
    try:
        from clarvis.orch.pr_intake import load_all_artifacts
        artifacts = load_all_artifacts(agent_dir) or {}
    except ImportError:
        pass

    if artifacts:
        if "architecture_map" in artifacts:
            arch = artifacts["architecture_map"]
            if isinstance(arch, dict) and "data" in arch:
                arch = arch["data"]
            brief["artifact_excerpts"]["architecture"] = _summarize_architecture(arch)
        if "stack_detect" in artifacts:
            stack = artifacts["stack_detect"]
            if isinstance(stack, dict) and "data" in stack:
                stack = stack["data"]
            brief["artifact_excerpts"]["stack"] = _summarize_stack(stack)
        if "commands" in artifacts:
            cmds = artifacts["commands"]
            if isinstance(cmds, dict) and "data" in cmds:
                cmds = cmds["data"]
            brief["required_validations"] = _extract_validations(cmds)

    # Load indexes for relevant files + typed edges
    indexes = {}
    try:
        from clarvis.orch.pr_indexes import load_all_indexes
        indexes = load_all_indexes(agent_dir) or {}
    except ImportError:
        pass

    # Query LiteBrain with hybrid recall (vector + typed edges)
    try:
        brain_dir = agent_dir / "data" / "brain"
        if brain_dir.exists():
            from lite_brain import LiteBrain
            lb = LiteBrain(str(brain_dir))

            # Build/refresh typed edges from indexes (idempotent, deduped)
            if indexes:
                lb.build_typed_edges(indexes)

            # Hybrid recall: vector + typed edge expansion
            hybrid = lb.hybrid_recall(task, indexes=indexes, n_results=5)

            # Relevant files: combine index keyword matches + typed edge matches
            file_set = []
            if indexes:
                file_set = _find_relevant_files(task, indexes)
            # Add files found via typed edges (route→file, symbol→file)
            for f in hybrid.get("related_files", []):
                if f not in file_set:
                    file_set.append(f)
            # Add related test files
            for t in hybrid.get("related_tests", []):
                if t not in file_set:
                    file_set.append(t)
            brief["relevant_files"] = file_set[:12]

            # Dynamic relevance threshold: lower when brain is sparse
            total_mem = lb.stats().get("total_memories", 0)
            fact_threshold = 0.10 if total_mem < 50 else 0.20 if total_mem < 200 else 0.25

            # Facts from vector recall
            facts = lb.recall(task, n_results=5, collection="project-learnings")
            brief["relevant_facts"] = [
                f["document"] for f in facts if f.get("relevance", 0) > fact_threshold
            ][:5]

            # Episodes from vector recall (lower threshold + fallback to recent)
            episodes = lb.recall(task, n_results=5, collection="project-episodes")
            relevant_eps = [
                e["document"] for e in episodes if e.get("relevance", 0) > fact_threshold
            ][:3]
            brief["relevant_episodes"] = relevant_eps

            # Sector constraints from hybrid recall or direct sector recall
            sector = hybrid.get("sector_constraints", [])
            if not sector:
                sector_results = lb.sector_recall(task, n_results=3)
                sector = [s["document"] for s in sector_results
                          if s.get("relevance", 0) > 0.15]
            brief["sector_constraints"] = sector[:5]
    except Exception:
        # Fallback: at least use index keyword matching
        if indexes:
            brief["relevant_files"] = _find_relevant_files(task, indexes)

    # Fallback: surface recent task summaries as episode context
    if not brief["relevant_episodes"]:
        brief["relevant_episodes"] = _load_recent_summaries(agent_dir, task, max_items=3)

    # Fallback: if no files found, use entrypoints from architecture
    if not brief["relevant_files"] and artifacts:
        brief["relevant_files"] = _fallback_entrypoints(artifacts)

    # Enrich facts from artifacts (trust boundaries, project brief, constraints)
    if artifacts:
        _enrich_facts_from_artifacts(brief, task, task_class, artifacts)

    # Enrich sector from artifact if brain had no sector constraints
    if not brief["sector_constraints"] and artifacts:
        _enrich_sector_from_artifacts(brief, artifacts)

    # Save brief
    brief_path = agent_dir / "data" / "execution_brief.json"
    brief_path.parent.mkdir(parents=True, exist_ok=True)
    brief_path.write_text(json.dumps(brief, indent=2, default=str))

    return brief


def build_factory_context(name: str, task: str, agent_dir: Path) -> str:
    """Compile execution brief and format as prompt context.

    Returns a formatted string for injection into the spawn prompt,
    capped at BRIEF_TOKEN_CAP characters.
    """
    brief = build_execution_brief(name, task, agent_dir)
    return format_brief_for_prompt(brief)


def format_brief_for_prompt(brief: dict) -> str:
    """Format an execution brief dict as prompt text."""
    lines = []

    lines.append(f"**Task class**: {brief.get('task_class', 'unknown')}")

    criteria = brief.get("success_criteria", [])
    if criteria:
        lines.append("**Success criteria**:")
        for c in criteria[:5]:
            lines.append(f"  - {c}")

    non_neg = brief.get("non_negotiables", [])
    if non_neg:
        lines.append("**Non-negotiables**:")
        for n in non_neg[:3]:
            lines.append(f"  - {n}")

    validations = brief.get("required_validations", [])
    if validations:
        lines.append(f"**Required validations**: {', '.join(validations[:4])}")

    files = brief.get("relevant_files", [])
    if files:
        lines.append(f"**Likely relevant files**: {', '.join(files[:8])}")

    facts = brief.get("relevant_facts", [])
    if facts:
        lines.append("**Known facts (from prior runs)**:")
        for f in facts[:3]:
            lines.append(f"  - {f[:150]}")

    episodes = brief.get("relevant_episodes", [])
    if episodes:
        lines.append("**Prior episodes**:")
        for e in episodes[:2]:
            lines.append(f"  - {e[:150]}")

    sector = brief.get("sector_constraints", [])
    if sector:
        lines.append("**Sector/domain constraints**:")
        for s in sector[:4]:
            lines.append(f"  - {s[:150]}")

    excerpts = brief.get("artifact_excerpts", {})
    if excerpts.get("stack"):
        lines.append(f"**Stack**: {excerpts['stack'][:200]}")
    if excerpts.get("architecture"):
        lines.append(f"**Architecture**: {excerpts['architecture'][:200]}")

    # Verify/self-review loop instructions
    vl = brief.get("verify_loop", {})
    if vl:
        lines.append(f"**Verify loop**: max {vl.get('max_refinements', 2)} refinement passes. "
                      f"Triggers: {', '.join(vl.get('allowed_triggers', []))}")

    # PR class decision guide
    pcd = brief.get("pr_class_decision", {})
    if pcd:
        lines.append(f"**PR class**: default {pcd.get('default', 'A')}. "
                      f"→B if {pcd.get('downgrade_to_B_if', 'n/a')}. "
                      f"→C if {pcd.get('downgrade_to_C_if', 'n/a')}.")

    result = "\n".join(lines)
    if len(result) > BRIEF_TOKEN_CAP:
        result = result[:BRIEF_TOKEN_CAP - 20] + "\n[...truncated]"
    return result


# ── Helpers for brief compilation ──

def _infer_success_criteria(task: str, task_class: str) -> list[str]:
    """Infer success criteria from task text and class."""
    criteria = []
    base = {
        "bugfix":        ["Bug is fixed", "Regression test added", "No new failures"],
        "feature":       ["Feature implemented as specified", "Tests pass"],
        "refactor":      ["Behavior unchanged", "Tests pass", "Code is cleaner"],
        "docs":          ["Documentation is accurate and complete"],
        "tests":         ["Tests cover the target behavior", "All tests pass"],
        "config":        ["Configuration works correctly", "CI/CD passes"],
        "hardening":     ["Security issue resolved", "No regressions"],
        "investigation": ["Root cause identified", "Findings documented"],
    }
    criteria.extend(base.get(task_class, ["Task completed as described"]))

    # Add task-specific criteria from keywords
    if "pr" in task.lower() or "pull request" in task.lower():
        criteria.append("PR created and linked")

    return criteria


def _get_non_negotiables(task_class: str) -> list[str]:
    """Return hard constraints for the task class."""
    common = ["No secrets committed", "Scoped to the task"]
    per_class = {
        "bugfix":    ["Root cause addressed, not just symptoms"],
        "feature":   ["Existing tests still pass"],
        "refactor":  ["No behavior change"],
        "config":    ["CI pipeline remains functional"],
    }
    return common + per_class.get(task_class, [])


def _summarize_architecture(arch: dict) -> str:
    """One-line architecture summary from architecture_map artifact."""
    parts = []
    if arch.get("entry_points"):
        parts.append(f"entries: {', '.join(str(e) for e in arch['entry_points'][:3])}")
    if arch.get("source_dirs"):
        dirs = arch["source_dirs"]
        if isinstance(dirs, list) and dirs:
            names = [d.get("path", str(d)) if isinstance(d, dict) else str(d)
                     for d in dirs[:4]]
            parts.append(f"src: {', '.join(names)}")
    return "; ".join(parts) if parts else ""


def _summarize_stack(stack: dict) -> str:
    """One-line stack summary from stack_detect artifact."""
    parts = []
    if stack.get("languages"):
        parts.append(f"langs: {', '.join(stack['languages'][:3])}")
    if stack.get("frameworks"):
        parts.append(f"fw: {', '.join(stack['frameworks'][:3])}")
    if stack.get("package_managers"):
        parts.append(f"pkg: {', '.join(stack['package_managers'][:2])}")
    return "; ".join(parts) if parts else ""


def _extract_validations(commands: dict) -> list[str]:
    """Extract validation commands (test, lint, typecheck) from commands artifact.

    Handles both direct command format and nested {commands: {test: [...]}} format.
    """
    validations = []
    # The commands artifact may be wrapped: {commands: {test: [...], ...}, sources: [...]}
    cmd_data = commands
    if "commands" in commands and isinstance(commands["commands"], dict):
        cmd_data = commands["commands"]

    for key in ("test", "lint", "typecheck", "build"):
        if key not in cmd_data or not cmd_data[key]:
            continue
        val = cmd_data[key]
        if isinstance(val, list):
            # Take first command from each category
            for item in val[:2]:
                if isinstance(item, str) and item:
                    validations.append(item)
                elif isinstance(item, dict) and item.get("command"):
                    validations.append(str(item["command"]))
        elif isinstance(val, dict):
            cmd = val.get("command", "")
            if cmd:
                validations.append(str(cmd))
        elif isinstance(val, str) and val:
            validations.append(val)
    return validations


def _extract_task_keywords(task: str) -> list[str]:
    """Extract search keywords from task text with CamelCase/snake_case splitting.

    Handles: "Fix claimQuestReward race condition" →
        ["fix", "claim", "quest", "reward", "race", "condition",
         "claimquestreward"]
    """
    words = set()
    task_lower = task.lower()

    for raw in task_lower.split():
        if len(raw) < 3:
            continue
        words.add(raw)

    # Split CamelCase and snake_case from original (preserving case info)
    for raw_word in task.split():
        if len(raw_word) < 3:
            continue
        # CamelCase split: "claimQuestReward" → ["claim", "Quest", "Reward"]
        parts = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\b)', raw_word)
        for p in parts:
            if len(p) >= 3:
                words.add(p.lower())
        # snake_case / kebab-case split
        for p in re.split(r'[_\-]', raw_word):
            if len(p) >= 3:
                words.add(p.lower())
        # Keep compound as single token too (for symbol matching)
        words.add(raw_word.lower())

    # Filter common stop words that pollute matching
    stop = {"the", "and", "for", "with", "from", "that", "this", "should",
            "will", "can", "are", "has", "have", "into", "each", "when",
            "then", "also", "been", "being", "not", "add", "new", "use"}
    return [w for w in words if w not in stop]


def _find_relevant_files(task: str, indexes: dict) -> list[str]:
    """Find files likely relevant to the task from indexes.

    Uses multiple strategies: route matching, file name matching,
    symbol matching, and test file discovery.
    """
    files = []
    task_lower = task.lower()
    task_words = _extract_task_keywords(task)

    # Helper to unwrap index data (may be wrapped or raw)
    def _get_data(idx_name: str) -> dict:
        raw = indexes.get(idx_name, {})
        if isinstance(raw, dict):
            return raw.get("data", raw) if "data" in raw else raw
        return {}

    # 1. Route index: match task words against route paths
    route_data = _get_data("route_index")
    for r in route_data.get("routes", []):
        route_path = r.get("path", "")
        if any(word in route_path.lower() for word in task_words):
            files.append(r.get("file", route_path))

    # 2. File index: match task words against file names and paths
    file_data = _get_data("file_index")
    for f in file_data.get("files", []):
        fpath = f.get("path", "")
        fpath_lower = fpath.lower()
        # Match against full path components (more flexible than just filename)
        if any(word in fpath_lower for word in task_words):
            files.append(fpath)

    # 3. Symbol index: match task words against exported symbol names
    sym_data = _get_data("symbol_index")
    for entry in sym_data.get("symbols", []):
        file_path = entry.get("file", "")
        for sym in entry.get("symbols", []):
            sym_name = sym.get("name", "").lower()
            if any(word in sym_name for word in task_words):
                if file_path not in files:
                    files.append(file_path)
                break  # One match per file is enough

    # 4. Config index: for config/CI tasks, include relevant config files
    config_data = _get_data("config_index")
    task_class = classify_task(task)
    if task_class in ("config", "hardening") and config_data.get("configs"):
        for cfg in config_data["configs"]:
            cfg_path = cfg.get("path", "")
            if cfg_path and cfg_path not in files:
                # Match CI-related keywords
                if any(word in cfg_path.lower() for word in task_words):
                    files.append(cfg_path)

    # 5. Test index: find test files for matched source files
    test_data = _get_data("test_index")
    matched_sources = set(files[:10])  # Use already-found files
    for t in test_data.get("tests", []):
        test_file = t.get("test_file", "")
        likely_source = t.get("likely_source", "")
        # Include test if its source module matches any found file
        if likely_source and any(likely_source in src for src in matched_sources):
            if test_file not in files:
                files.append(test_file)
        # Also include if task mentions tests
        if "test" in task_lower and test_file not in files:
            files.append(test_file)

    return list(dict.fromkeys(files))[:12]  # Dedupe, cap at 12


def _load_recent_summaries(agent_dir: Path, task: str, max_items: int = 3) -> list[str]:
    """Load recent task summaries as episode context when brain episodes are empty.

    Extracts concise episode strings from memory/summaries/*.json files.
    """
    summaries_dir = agent_dir / "memory" / "summaries"
    if not summaries_dir.exists():
        return []

    episodes = []
    task_keywords = set(w.lower() for w in task.split() if len(w) >= 4)

    # Load summaries sorted by filename (timestamp-based)
    for sf in sorted(summaries_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(sf.read_text())
            result = data.get("result", {})
            if not isinstance(result, dict):
                continue
            status = result.get("status", "unknown")
            summary = result.get("summary", "")
            task_text = data.get("task", "")[:80]
            pr_url = result.get("pr_url", "")

            if not summary:
                continue

            # Build concise episode string
            ep = f"[{status.upper()}] {task_text}"
            if pr_url:
                ep += f" → PR: {pr_url}"
            ep += f": {summary[:150]}"
            episodes.append(ep)

        except (json.JSONDecodeError, OSError):
            continue

        if len(episodes) >= max_items + 2:
            break

    # Prefer episodes with keyword overlap, then most recent
    def _relevance(ep: str) -> int:
        ep_lower = ep.lower()
        return sum(1 for kw in task_keywords if kw in ep_lower)

    episodes.sort(key=_relevance, reverse=True)
    return episodes[:max_items]


def _fallback_entrypoints(artifacts: dict) -> list[str]:
    """When no files found via keyword matching, return architecture entrypoints."""
    arch = artifacts.get("architecture_map", {})
    if isinstance(arch, dict) and "data" in arch:
        arch = arch["data"]
    if not arch:
        return []

    files = []
    for ep in arch.get("entrypoints", [])[:4]:
        if isinstance(ep, str):
            files.append(ep)
    return files


def _enrich_facts_from_artifacts(brief: dict, task: str, task_class: str,
                                  artifacts: dict):
    """Add contextual facts from artifacts to the brief.

    Extracts: domain constraints, trust boundary warnings,
    project-specific constraints that are relevant to the task class.
    """
    facts = brief.get("relevant_facts", [])

    # Trust boundary facts for security-related tasks
    trust = artifacts.get("trust_boundaries", {})
    if isinstance(trust, dict) and trust.get("data"):
        trust = trust["data"]
    if trust and task_class in ("hardening", "bugfix", "feature"):
        if trust.get("auth_modules"):
            # Only add if task touches auth-related words
            if any(w in task.lower() for w in ("auth", "login", "session", "token", "user")):
                facts.append(f"Auth modules: {', '.join(trust['auth_modules'][:3])}")
        if trust.get("env_files"):
            facts.append(f"Env files present: {', '.join(trust['env_files'][:3])}")

    # Project brief domain/constraints as grounding facts
    project = artifacts.get("project_brief", {})
    if isinstance(project, dict) and project.get("data"):
        project = project["data"]
    if project:
        if project.get("domain") and len(project["domain"]) > 10:
            facts.append(f"Project domain: {project['domain'][:150]}")
        for constraint in project.get("constraints", [])[:3]:
            if constraint and len(constraint) > 5:
                facts.append(f"Constraint: {constraint[:120]}")

    # Dedupe and cap
    brief["relevant_facts"] = list(dict.fromkeys(facts))[:8]


def _enrich_sector_from_artifacts(brief: dict, artifacts: dict):
    """Add sector constraints from the sector_playbook artifact as fallback."""
    sector = artifacts.get("sector_playbook", {})
    if isinstance(sector, dict) and sector.get("data"):
        sector = sector["data"]
    if not sector:
        return

    constraints = brief.get("sector_constraints", [])

    if sector.get("sector"):
        constraints.append(f"Sector: {sector['sector']}")

    for c in sector.get("constraints", [])[:3]:
        if c and c not in constraints:
            constraints.append(c[:150])

    for inv in sector.get("safety_invariants", [])[:3]:
        if inv and inv not in constraints:
            constraints.append(f"[invariant] {inv[:150]}")

    brief["sector_constraints"] = constraints[:5]


# ── Mandatory Writeback ──

def run_writeback(name: str, agent_dir: Path, result: dict, task: str):
    """Mandatory post-spawn writeback: episode, facts, procedures, golden QA.

    Stores structured memories in the agent's LiteBrain so future runs
    benefit from accumulated knowledge.

    Args:
        name: Agent name
        agent_dir: Path to agent directory
        result: A2A result dict from agent output
        task: Original task string
    """
    brain_dir = agent_dir / "data" / "brain"
    brain_dir.mkdir(parents=True, exist_ok=True)

    # 1. Write episode summary
    episode = _build_episode_summary(task, result)
    episode_path = agent_dir / "data" / "episode_summary.json"
    episode_path.write_text(json.dumps(episode, indent=2, default=str))

    # 2-5. Store in LiteBrain (graceful if ChromaDB unavailable)
    try:
        from lite_brain import LiteBrain
        lb = LiteBrain(str(brain_dir))
        _store_episode(lb, episode)
        _store_facts(lb, result)
        _store_procedures(lb, result)
        _store_sector_insights(lb, result)
        _store_file_edges(lb, episode)
        _update_golden_qa(agent_dir, task, result)
    except Exception:
        # LiteBrain storage is best-effort — don't break spawn flow
        pass


def _build_episode_summary(task: str, result: dict) -> dict:
    """Build structured episode summary from task + A2A result."""
    return {
        "task": task[:500],
        "task_class": classify_task(task),
        "status": result.get("status", "unknown"),
        "pr_class": result.get("pr_class"),
        "pr_url": result.get("pr_url"),
        "summary": result.get("summary", ""),
        "files_changed": result.get("files_changed", []),
        "validations_run": result.get("procedures", []),
        "tests_passed": result.get("tests_passed"),
        "confidence": result.get("confidence"),
        "follow_ups": result.get("follow_ups", []),
        "error": result.get("error"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _store_episode(lb, episode: dict):
    """Store episode summary in project-episodes collection."""
    status = episode.get("status", "unknown")
    pr_class = episode.get("pr_class", "?")
    summary = episode.get("summary", "No summary")
    task_class = episode.get("task_class", "unknown")

    text = (f"[{status.upper()}] [{task_class}] "
            f"PR class {pr_class}: {summary[:300]}")

    tags = [f"status:{status}", f"class:{task_class}"]
    if episode.get("pr_class"):
        tags.append(f"pr_class:{episode['pr_class']}")

    importance = 0.7 if status == "success" else 0.5
    lb.store(text, "project-episodes", importance=importance,
             tags=tags, source="pr_factory_writeback")


def _store_facts(lb, result: dict):
    """Extract and store dense atomic facts from agent result.

    Produces structured facts across categories:
    - File-role facts: what each modified file does / what changed
    - Invariants/gotchas: constraints discovered during execution
    - Route/endpoint facts: API surface changes
    - Validated procedures: commands that were verified to work
    - Outcome summary: grounded knowledge from the task result
    """
    facts = []
    summary = result.get("summary", "")
    files_changed = result.get("files_changed", [])
    procedures = result.get("procedures", [])
    status = result.get("status", "unknown")

    # 1. File-role facts: what changed and why (denser than bare paths)
    if files_changed and summary:
        # Group files by directory for concise facts
        dirs = {}
        for f in files_changed[:10]:
            d = f.rsplit("/", 1)[0] if "/" in f else "root"
            dirs.setdefault(d, []).append(f.rsplit("/", 1)[-1] if "/" in f else f)
        for d, fnames in dirs.items():
            fact = f"Modified {d}/: {', '.join(fnames[:4])}"
            if len(summary) > 20:
                fact += f" — {summary[:120]}"
            facts.append(("file_role", fact, 0.5))

    # 2. Extract invariants and gotchas from summary
    invariant_patterns = [
        (r"(?:must|always|never|invariant|requires?)\s+.{10,80}", "invariant"),
        (r"(?:gotcha|caveat|note|important|warning):\s*.{10,100}", "gotcha"),
        (r"(?:race condition|deadlock|timeout|retry|idempoten)\w*\s+.{5,60}", "gotcha"),
    ]
    if summary:
        for pattern, fact_type in invariant_patterns:
            matches = re.findall(pattern, summary, re.IGNORECASE)
            for m in matches[:2]:
                clean = m.strip().rstrip(".,;")
                if len(clean) > 15:
                    facts.append((fact_type, f"[{fact_type}] {clean[:200]}", 0.7))

    # 3. Route/endpoint facts from file paths
    route_keywords = ("route", "api/", "endpoint", "handler", "middleware")
    for f in files_changed[:10]:
        if any(kw in f.lower() for kw in route_keywords):
            fact = f"[route] {f} — touched in {status} {result.get('pr_class', '?')}-class task"
            facts.append(("route", fact, 0.6))

    # 4. Validated procedure evidence
    if status == "success" and procedures:
        verified = [p for p in procedures[:5] if isinstance(p, str) and len(p) > 3]
        if verified:
            evidence = ", ".join(verified[:3])
            facts.append(("procedure_evidence",
                          f"[verified] Commands passed: {evidence}", 0.6))

    # 5. Outcome summary (always stored for grounding)
    if summary and len(summary) > 20:
        facts.append(("outcome", f"Outcome: {summary[:300]}", 0.5))

    # 6. Error/blocker facts (valuable for future avoidance)
    error = result.get("error", "")
    if error and len(error) > 10:
        facts.append(("blocker", f"[blocker] {error[:200]}", 0.6))

    # Deduplicate by content prefix (first 80 chars)
    seen = set()
    for fact_type, text, importance in facts:
        key = text[:80].lower()
        if key in seen:
            continue
        seen.add(key)
        lb.store(text, "project-learnings", importance=importance,
                 tags=["atomic_fact", fact_type], source="pr_factory_writeback")


def _store_procedures(lb, result: dict):
    """Store verified procedures from agent result."""
    procedures = result.get("procedures", [])
    if not procedures:
        return

    for proc in procedures[:5]:
        if isinstance(proc, str) and len(proc) > 5:
            lb.store(proc, "project-procedures", importance=0.7,
                     tags=["verified"], source="pr_factory_writeback")


def _store_sector_insights(lb, result: dict):
    """Store domain/sector insights discovered during task execution.

    Extracts sector-relevant knowledge from the agent's output summary
    and stores it in project-sector collection for future briefs.
    """
    summary = result.get("summary", "")
    if not summary or len(summary) < 20:
        return

    # Look for sector-like signals in summary
    sector_keywords = [
        "invariant", "constraint", "governance", "safety", "must not",
        "always", "never", "domain rule", "product rule", "requirement",
    ]

    summary_lower = summary.lower()
    if not any(kw in summary_lower for kw in sector_keywords):
        return

    # Store the sector-relevant portion as a constraint
    lb.store_sector(
        f"Discovered: {summary[:300]}",
        constraint_type="domain",
        importance=0.6,
        source="pr_factory_writeback",
    )


def _store_file_edges(lb, episode: dict):
    """Store typed edges linking task class to modified files."""
    task_class = episode.get("task_class", "unknown")
    files_changed = episode.get("files_changed", [])
    status = episode.get("status", "unknown")

    if status != "success" or not files_changed:
        return

    for fpath in files_changed[:10]:
        # task_class→file edges help future briefs find relevant files
        lb.add_edge(f"task_class:{task_class}", f"file:{fpath}",
                    edge_type="task_class_file", weight=0.6)


def _update_golden_qa(agent_dir: Path, task: str, result: dict):
    """Add golden QA entries if confidence is high enough."""
    confidence = result.get("confidence", 0)
    if confidence < 0.8:
        return

    qa_path = agent_dir / "data" / "golden_qa.json"
    qa_entries = []
    if qa_path.exists():
        try:
            qa_entries = json.loads(qa_path.read_text())
        except (json.JSONDecodeError, OSError):
            qa_entries = []

    # Generate QA from the task outcome
    summary = result.get("summary", "")
    if not summary:
        return

    task_class = classify_task(task)
    new_qa = {
        "query": task[:200],
        "expected_answer": summary[:300],
        "collection": "project-learnings",
        "source": "pr_factory_writeback",
        "task_class": task_class,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Avoid duplicates by checking task similarity
    for existing in qa_entries:
        if existing.get("query", "")[:100] == new_qa["query"][:100]:
            return

    qa_entries.append(new_qa)

    # Cap at 50 entries
    if len(qa_entries) > 50:
        qa_entries = qa_entries[-50:]

    qa_path.write_text(json.dumps(qa_entries, indent=2, default=str))


# ── CLI ──

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: pr_factory.py classify|brief|writeback-test")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "classify":
        task = sys.argv[2] if len(sys.argv) > 2 else "Fix the login bug"
        print(f"Task: {task}")
        print(f"Class: {classify_task(task)}")

    elif cmd == "brief":
        name = sys.argv[2] if len(sys.argv) > 2 else "star-world-order"
        task = sys.argv[3] if len(sys.argv) > 3 else "Add tests for auth module"
        agent_dir = Path(f"~/agents/{name}")
        if not agent_dir.exists():
            agent_dir = Path(f"/opt/clarvis-agents/{name}")
        if agent_dir.exists():
            brief = build_execution_brief(name, task, agent_dir)
            print(json.dumps(brief, indent=2, default=str))
        else:
            print(f"Agent dir not found for '{name}'")

    elif cmd == "writeback-test":
        print("Writeback module loaded OK")
        print(f"Functions: classify_task, build_execution_brief, "
              f"build_factory_context, format_brief_for_prompt, run_writeback")
    else:
        print(f"Unknown command: {cmd}")
