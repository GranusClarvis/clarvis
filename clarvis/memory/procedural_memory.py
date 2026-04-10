#!/usr/bin/env python3
"""
Procedural Memory — Reusable step sequences for recurring tasks

Inspired by ACT-R procedural memory, Voyager's skill library, and the
SoK on Agentic Skills (arxiv 2602.20867). Implements the 7-stage skill
lifecycle: discovery → practice → distillation → storage → composition →
evaluation → update.

Each procedure is stored as a skill tuple S = (C, π, T, R):
  C — applicability: preconditions that must hold before running
  π — policy: ordered step list (the procedure itself)
  T — termination: success criteria to verify completion
  R — interface: name, tags, dependencies, metadata for retrieval

Metadata in brain collection='clarvis-procedures':
  - name, steps (JSON), use_count, success_count, source_task
  - preconditions: JSON list of conditions required before execution
  - termination_criteria: JSON list of success verification checks
  - dependencies: JSON list of other procedure IDs this composes
  - quality_tier: "verified" | "candidate" | "stale" (lifecycle stage)
  - created_at, last_used: ISO timestamps for staleness tracking

Usage:
    python3 procedural_memory.py check "Build a monitoring dashboard"
    python3 procedural_memory.py learn "Build dashboard" '["Read requirements","Create script","Wire into cron","Test"]'
    python3 procedural_memory.py used "proc_build_dashboard" success
    python3 procedural_memory.py list
    python3 procedural_memory.py retire      # Prune stale/low-quality procedures
    python3 procedural_memory.py compose "deploy_feature" '["proc_write_code","proc_run_tests","proc_push"]'
    python3 procedural_memory.py stats       # Library health metrics
"""

import sys
import os
import json
import re
from datetime import datetime, timezone, timedelta

from clarvis.brain import brain, PROCEDURES

from clarvis._script_loader import load as _load_script

try:
    _retrieval_mod = _load_script("retrieval_experiment", "brain_mem")
    smart_recall = _retrieval_mod.smart_recall
except Exception:
    smart_recall = None

try:
    _fa_mod = _load_script("failure_amplifier", "evolution")
    parse_log_entries = _fa_mod.parse_log_entries
    scan_duplicate_tasks = _fa_mod.scan_duplicate_tasks
    scan_long_durations = _fa_mod.scan_long_durations
    scan_skipped_learning = _fa_mod.scan_skipped_learning
    scan_prediction_misses = _fa_mod.scan_prediction_misses
    scan_retroactive_fixes = _fa_mod.scan_retroactive_fixes
    scan_low_capability_scores = _fa_mod.scan_low_capability_scores
    scan_low_confidence_predictions = _fa_mod.scan_low_confidence_predictions
    scan_uncompleted_tasks = _fa_mod.scan_uncompleted_tasks
    scan_reasoning_chains = _fa_mod.scan_reasoning_chains
    AUTONOMOUS_LOG = _fa_mod.AUTONOMOUS_LOG
    _HAS_FAILURE_AMPLIFIER = True
except Exception:
    _HAS_FAILURE_AMPLIFIER = False

# Quality tiers for skill lifecycle (SoK Pattern 4: Self-Evolving Libraries)
TIER_CANDIDATE = "candidate"   # Newly learned, not yet verified by reuse
TIER_VERIFIED = "verified"     # Used 3+ times with >60% success rate
TIER_STALE = "stale"           # Unused >30 days or success rate <30%

# Thresholds for tier transitions
VERIFY_MIN_USES = 3
VERIFY_MIN_SUCCESS_RATE = 0.6
STALE_DAYS = 30
STALE_MAX_SUCCESS_RATE = 0.3
RETIRE_DAYS = 60               # Remove after 60 days of no use + low quality


# === CODE GENERATION TEMPLATES ===
# Extracted from the 10 most-edited scripts (brain.py, self_model.py, task_selector.py,
# episodic_memory.py, session_hook.py, reasoning_chain_hook.py, phi_metric.py,
# clarvis_model_switch.py, retrieval_experiment.py, attention.py).
# Each template is a reusable scaffold tagged 'code_template' in procedural_memory.

CODE_TEMPLATES = {
    "cognitive_module": {
        "name": "cognitive_module",
        "description": "New cognitive module with brain integration, CLI, and JSON persistence",
        "match_keywords": ["create script", "build module", "new module", "implement.*script",
                           "create.*py", "build.*system", "cognitive", "create.*monitor",
                           "code", "build.*script"],
        "scaffold": [
            "Add shebang + docstring with purpose, usage examples, and CLI commands",
            "Import stdlib (json, os, sys, time, pathlib, datetime)",
            "Use clarvis spine imports (from clarvis.brain import brain) for local imports",
            "Try/except import brain: from brain import brain, LEARNINGS (with fallback)",
            "Try/except import optional deps (attention, episodic_memory, etc.)",
            "Define DATA_FILE = Path(WORKSPACE) / 'data/<name>.json'",
            "Define constants/thresholds at module level",
            "Implement core logic (class or functions based on complexity)",
            "Add _load_state()/_save_state() helpers using json.dump(obj, f, indent=2, default=str)",
            "Add if __name__ == '__main__' with sys.argv subcommand dispatch",
            "Add usage/help on invalid args, sys.exit(0/1) on success/failure",
        ],
        "preconditions": ["scripts/ directory exists", "brain.py importable"],
        "termination_criteria": ["python3 -c 'import <module>' succeeds", "CLI --help works"],
    },
    "brain_integration": {
        "name": "brain_integration",
        "description": "Wire a new data source into ClarvisDB brain (store/recall pattern)",
        "match_keywords": ["wire into brain", "brain integration", "store in brain",
                           "brain.store", "brain.recall", "add to brain", "remember"],
        "scaffold": [
            "Import brain: from brain import brain, get_brain, <COLLECTION>",
            "Define collection constant if new: COLLECTION_NAME = 'clarvis-<name>'",
            "Implement store function: brain.store(doc, collection=COL, importance=N, tags=[...])",
            "Implement recall function: brain.recall(query, collections=[COL], n=5)",
            "Add try/except around all brain calls (ChromaDB may be slow/unavailable)",
            "Test with: python3 -c 'from brain import brain; print(brain.stats())'",
        ],
        "preconditions": ["brain.py accessible", "ChromaDB healthy"],
        "termination_criteria": ["brain.store() succeeds", "brain.recall() returns results"],
    },
    "wire_integration": {
        "name": "wire_integration",
        "description": "Wire a new module into heartbeat pipeline (preflight/postflight)",
        "match_keywords": ["wire into", "integrate into", "add to preflight",
                           "add to postflight", "heartbeat integration", "wire.*heartbeat",
                           "connect.*pipeline"],
        "scaffold": [
            "READ target file — find exact insertion point (line number, section comment)",
            "READ source module — find function/class to import and its signature",
            "Add try/except import at top of target: try: from <mod> import <func> except ImportError: <func> = None",
            "Add call at insertion point with guard: if <func>: try: result = <func>(...) except Exception as e: log(f'failed: {e}')",
            "Add timing wrapper: t = time.monotonic() ... result['timings']['<name>'] = round(time.monotonic() - t, 3)",
            "Test: python3 -c 'import <target_module>' to verify no syntax errors",
            "Verify: run target in --dry-run mode or grep for added lines",
        ],
        "preconditions": ["target file readable", "source module importable"],
        "termination_criteria": ["import succeeds", "no syntax errors", "function called in pipeline"],
    },
    "data_processor": {
        "name": "data_processor",
        "description": "Script that processes JSONL/JSON data with load/transform/save pattern",
        "match_keywords": ["process data", "parse log", "analyze", "transform",
                           "jsonl", "data pipeline", "extract.*from", "scan.*log"],
        "scaffold": [
            "Define input/output paths as Path constants",
            "Implement _load_data(path) with json.loads per line (JSONL) or json.load (JSON)",
            "Implement processing/transform logic as pure functions",
            "Implement _save_results(data, path) with json.dump(obj, f, indent=2, default=str)",
            "Add os.makedirs(path.parent, exist_ok=True) before writes",
            "Add CLI: if __name__ == '__main__' with subcommands (process, stats, export)",
            "Add progress logging to stderr for cron visibility",
        ],
        "preconditions": ["input data file exists"],
        "termination_criteria": ["output file created", "no data corruption"],
    },
    "class_with_state": {
        "name": "class_with_state",
        "description": "Stateful class with JSON persistence (like EpisodicMemory, AttentionSpotlight)",
        "match_keywords": ["class", "stateful", "memory system", "tracker",
                           "manager", "engine", "system with state"],
        "scaffold": [
            "Define class with __init__(self, data_path=DEFAULT_PATH)",
            "Load state in __init__: self._state = self._load() or default_state()",
            "Implement _load(self) -> dict: read JSON from self.data_path",
            "Implement _save(self): json.dump(self._state, f, indent=2, default=str)",
            "Implement core methods that modify self._state then call self._save()",
            "Add stats(self) -> dict for health/status reporting",
            "Add CLI wrapper in __main__ block instantiating the class",
        ],
        "preconditions": ["data directory writable"],
        "termination_criteria": ["state persists across instantiations", "stats() returns valid data"],
    },
    "cron_orchestrator": {
        "name": "cron_orchestrator",
        "description": "Bash cron script that spawns Claude Code with a task prompt",
        "match_keywords": ["cron script", "cron job", "autonomous", "scheduled task",
                           "spawn claude", "cron_*.sh"],
        "scaffold": [
            "Add shebang: #!/usr/bin/env bash, set -euo pipefail",
            "Source environment: source $CLARVIS_WORKSPACE/scripts/cron_env.sh",
            "Add lockfile: LOCKFILE=/tmp/clarvis_<name>.lock with trap 'rm -f $LOCKFILE' EXIT",
            "Check lock: [ -f $LOCKFILE ] && check_stale_lock || create lock",
            "Build task prompt: write to /tmp/clarvis_<name>_prompt.txt",
            "Run preflight: PREFLIGHT=$(python3 scripts/pipeline/heartbeat_preflight.py)",
            "Spawn Claude: timeout 1200 env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT /home/agent/.local/bin/claude -p \"$(cat prompt)\" --dangerously-skip-permissions --model claude-opus-4-6",
            "Run postflight: python3 scripts/pipeline/heartbeat_postflight.py",
            "Clean up lockfile on exit",
        ],
        "preconditions": ["cron_env.sh exists", "claude binary available"],
        "termination_criteria": ["bash -n <script>.sh passes", "lockfile cleaned on exit"],
    },
    "metric_tracker": {
        "name": "metric_tracker",
        "description": "Track and score a numeric metric over time with history and thresholds",
        "match_keywords": ["metric", "score", "benchmark", "track.*over time",
                           "measure", "performance", "quality gate"],
        "scaffold": [
            "Define HISTORY_FILE = Path('data/<metric>_history.jsonl')",
            "Define STATE_FILE = Path('data/<metric>.json') for current state",
            "Define thresholds: TARGET, WARNING, CRITICAL as module constants",
            "Implement compute() -> float that calculates current metric value",
            "Implement record(): append {timestamp, value, details} to HISTORY_FILE",
            "Implement trend(n=10) -> dict: load last N entries, compute delta/direction",
            "Add alert logic: if value < CRITICAL, log warning or push to QUEUE.md",
            "Add CLI: compute, record, trend, history subcommands",
        ],
        "preconditions": ["data directory writable"],
        "termination_criteria": ["compute() returns float", "history file grows on record()"],
    },
    "test_suite": {
        "name": "test_suite",
        "description": "pytest test file for a Clarvis module",
        "match_keywords": ["test", "pytest", "unit test", "test suite",
                           "write tests", "add tests"],
        "scaffold": [
            "Import pytest and set up imports for local modules",
            "Import the module under test with try/except",
            "Add fixtures: @pytest.fixture for common test data",
            "Test happy path: def test_<func>_basic(): assert expected_result",
            "Test edge cases: empty input, None, malformed data",
            "Test error handling: ensure graceful failures (no crashes)",
            "Run with: cd workspace && python3 -m pytest tests/ -v",
        ],
        "preconditions": ["pytest installed", "module importable"],
        "termination_criteria": ["all tests pass", "no import errors"],
    },
}


def find_code_templates(task_text: str, top_n: int = 2) -> list[dict]:
    """Find matching code generation templates for a task.

    Matches task text against keyword patterns in CODE_TEMPLATES,
    then also checks procedural_memory for stored templates tagged 'code_template'.

    Args:
        task_text: Description of the coding task
        top_n: Maximum number of templates to return

    Returns:
        List of template dicts with name, scaffold steps, and match score
    """
    task_lower = task_text.lower()
    scored = []

    # Score built-in templates by keyword matches
    for key, tmpl in CODE_TEMPLATES.items():
        score = 0
        for kw in tmpl["match_keywords"]:
            if kw in task_lower:
                score += 1
            elif re.search(kw, task_lower):
                score += 0.8
        if score > 0:
            scored.append({
                "name": tmpl["name"],
                "description": tmpl["description"],
                "scaffold": tmpl["scaffold"],
                "preconditions": tmpl.get("preconditions", []),
                "termination_criteria": tmpl.get("termination_criteria", []),
                "score": score,
                "source": "builtin",
            })

    # Also check stored procedures tagged 'code_template'
    try:
        results = brain.recall(
            task_text,
            collections=[PROCEDURES],
            n=5,
            caller="code_templates",
        )
        for r in results:
            meta = r.get("metadata", {})
            tags = meta.get("tags", "")
            if "code_template" in str(tags):
                steps = _parse_json_field(meta.get("steps", "[]"))
                dist = r.get("distance", 1.0)
                scored.append({
                    "name": meta.get("name", "unknown"),
                    "description": r.get("document", "")[:200],
                    "scaffold": steps,
                    "preconditions": _parse_json_field(meta.get("preconditions", "[]")),
                    "termination_criteria": _parse_json_field(meta.get("termination_criteria", "[]")),
                    "score": max(0, 2.0 - dist),  # Convert distance to score
                    "source": "stored",
                })
    except Exception:
        pass

    # Deduplicate by name — prefer higher score
    seen = {}
    for tmpl in scored:
        name = tmpl["name"]
        if name not in seen or tmpl["score"] > seen[name]["score"]:
            seen[name] = tmpl
    deduped = sorted(seen.values(), key=lambda t: t["score"], reverse=True)
    return deduped[:top_n]


def format_code_templates(templates: list[dict]) -> str:
    """Format code templates into a prompt-injectable hint string.

    Args:
        templates: List of template dicts from find_code_templates()

    Returns:
        Formatted string for injection into the task prompt
    """
    if not templates:
        return ""

    parts = ["CODE GENERATION TEMPLATES (matched scaffolds from top patterns):"]
    for tmpl in templates:
        parts.append(f"\n  [{tmpl['name']}] {tmpl['description']}")
        for i, step in enumerate(tmpl["scaffold"], 1):
            parts.append(f"    {i}. {step}")
        if tmpl.get("preconditions"):
            parts.append(f"    PRE: {', '.join(tmpl['preconditions'])}")
        if tmpl.get("termination_criteria"):
            parts.append(f"    VERIFY: {', '.join(tmpl['termination_criteria'])}")
    return "\n".join(parts)


def seed_code_templates() -> dict:
    """Seed the built-in CODE_TEMPLATES into procedural_memory as stored procedures.

    This makes them available via brain recall (semantic search) in addition to
    keyword matching. Idempotent — re-running updates existing entries.

    Returns:
        Dict with count of templates seeded.
    """
    seeded = 0
    for key, tmpl in CODE_TEMPLATES.items():
        store_procedure(
            name=tmpl["name"],
            description=tmpl["description"],
            steps=tmpl["scaffold"],
            source_task="[SEED] code generation templates from top 10 scripts",
            importance=0.85,
            tags=["code_template", "scaffold", "procedure", "skill"],
            preconditions=tmpl.get("preconditions"),
            termination_criteria=tmpl.get("termination_criteria"),
        )
        seeded += 1
    return {"seeded": seeded, "total_templates": len(CODE_TEMPLATES)}


def find_procedure(task_text: str, threshold: float = 0.8) -> dict | None:
    """Search for a matching procedure for a given task.

    Uses semantic similarity via brain.recall() on the procedures collection.
    Returns the best match if similarity exceeds threshold, else None.

    Args:
        task_text: Description of the task to find a procedure for
        threshold: Maximum cosine distance to accept (lower = stricter match).
                   Default 0.8 (evolved via parameter_evolution). Typical good matches are < 0.3.

    Returns:
        Dict with procedure info (name, steps, success_rate, id) or None
    """
    try:
        # Always search PROCEDURES directly for best procedure matches
        results = brain.recall(
            task_text,
            collections=[PROCEDURES],
            n=3,
            caller="procedural_memory",
        )
        # If smart_recall is available, also check for cross-collection procedure hints
        if smart_recall is not None:
            try:
                sr_results = smart_recall(task_text, n=5)
                sr_procs = [r for r in sr_results if r.get("collection") == PROCEDURES]
                # Merge any procedure results from smart_recall we didn't already find
                existing_ids = {r["id"] for r in results}
                for r in sr_procs:
                    if r["id"] not in existing_ids:
                        results.append(r)
            except Exception:
                pass
    except Exception:
        results = brain.recall(
            task_text,
            collections=[PROCEDURES],
            n=3,
            caller="procedural_memory",
        )

    if not results:
        # No results means ChromaDB returned nothing — don't rate this as
        # "not useful" because absence of stored procedures isn't a retrieval
        # failure. Only rate when we actually evaluate a candidate.
        return None

    # Pick the closest semantic match (lowest distance)
    results_with_dist = [r for r in results if r.get("distance") is not None]
    if results_with_dist:
        best = min(results_with_dist, key=lambda r: r["distance"])
    else:
        best = results[0]

    distance = best.get("distance")

    # Filter by similarity threshold — reject if too dissimilar
    if distance is not None and distance > threshold:
        # Don't rate as "not useful" — having no matching procedure for a
        # novel task is expected, not a retrieval failure. Rating these as
        # failures inflates false-negative counts and drags down hit_rate.
        return None

    meta = best.get("metadata", {})

    # Parse steps from metadata
    steps = []
    steps_raw = meta.get("steps", "[]")
    try:
        steps = json.loads(steps_raw) if isinstance(steps_raw, str) else steps_raw
    except (json.JSONDecodeError, TypeError):
        steps = []

    use_count = int(meta.get("use_count", 0))
    success_count = int(meta.get("success_count", 0))
    success_rate = success_count / use_count if use_count > 0 else 1.0

    # Rate: found a matching procedure = useful retrieval
    try:
        from retrieval_quality import tracker
        tracker.rate_last("procedural_memory", useful=True, reason=f"matched_d={distance:.3f}")
    except Exception:
        pass

    # Parse extended skill tuple fields (C, T, dependencies)
    preconditions = _parse_json_field(meta.get("preconditions", "[]"))
    termination_criteria = _parse_json_field(meta.get("termination_criteria", "[]"))
    dependencies = _parse_json_field(meta.get("dependencies", "[]"))
    quality_tier = meta.get("quality_tier", TIER_CANDIDATE)

    return {
        "id": best["id"],
        "name": meta.get("name", "unknown"),
        "description": best["document"],
        "steps": steps,
        "use_count": use_count,
        "success_count": success_count,
        "success_rate": success_rate,
        "source_task": meta.get("source_task", ""),
        # Skill tuple extensions
        "preconditions": preconditions,
        "termination_criteria": termination_criteria,
        "dependencies": dependencies,
        "quality_tier": quality_tier,
    }


def store_procedure(name: str, description: str, steps: list[str],
                    source_task: str = "", importance: float = 0.8,
                    tags: list[str] | None = None,
                    preconditions: list[str] | None = None,
                    termination_criteria: list[str] | None = None,
                    dependencies: list[str] | None = None) -> str:
    """Store a new procedure as a skill tuple S = (C, π, T, R).

    Args:
        name: Short procedure name (R.name)
        description: What this procedure does
        steps: Ordered list of step descriptions (π — policy)
        source_task: The original task text that generated this procedure
        importance: How important/reusable (default 0.8)
        tags: Additional categorization tags (R.tags)
        preconditions: Conditions required before execution (C — applicability)
        termination_criteria: How to verify success (T — termination)
        dependencies: IDs of other procedures this composes (R.deps)

    Returns:
        The procedure memory ID
    """
    proc_id = f"proc_{_sanitize_name(name)}"
    tags = tags or []
    tags.extend(["procedure", "skill"])
    # Deduplicate tags
    tags = list(set(tags))

    doc_text = f"Procedure: {name} — {description}"

    # Check if procedure already exists — merge use stats
    existing_use_count = 0
    existing_success_count = 0
    existing_tier = TIER_CANDIDATE
    try:
        col = brain.collections[PROCEDURES]
        existing = col.get(ids=[proc_id])
        if existing and existing["ids"]:
            old_meta = existing["metadatas"][0] if existing.get("metadatas") else {}
            existing_use_count = int(old_meta.get("use_count", 0))
            existing_success_count = int(old_meta.get("success_count", 0))
            existing_tier = old_meta.get("quality_tier", TIER_CANDIDATE)
    except Exception:
        pass

    mem_id = brain.store(
        doc_text,
        collection=PROCEDURES,
        importance=importance,
        tags=tags,
        source="procedural_memory",
        memory_id=proc_id,
    )

    # Update with procedure-specific metadata (full skill tuple)
    col = brain.collections[PROCEDURES]
    existing = col.get(ids=[proc_id])
    if existing and existing["ids"]:
        meta = existing["metadatas"][0]
        meta["name"] = name
        meta["steps"] = json.dumps(steps)
        meta["source_task"] = source_task[:500]
        meta["use_count"] = existing_use_count
        meta["success_count"] = existing_success_count
        meta["step_count"] = len(steps)
        # Skill tuple extensions
        meta["preconditions"] = json.dumps(preconditions or [])
        meta["termination_criteria"] = json.dumps(termination_criteria or [])
        meta["dependencies"] = json.dumps(dependencies or [])
        meta["quality_tier"] = existing_tier
        if "created_at" not in meta:
            meta["created_at"] = datetime.now(timezone.utc).isoformat()
        col.upsert(
            ids=[proc_id],
            documents=[doc_text],
            metadatas=[meta],
        )

    return mem_id


def record_use(proc_id: str, success: bool) -> dict:
    """Record that a procedure was used, updating use/success counts.

    Args:
        proc_id: The procedure memory ID
        success: Whether the procedure led to success

    Returns:
        Updated stats dict {use_count, success_count, success_rate}
    """
    col = brain.collections[PROCEDURES]
    existing = col.get(ids=[proc_id])

    if not existing or not existing["ids"]:
        return {"error": f"Procedure {proc_id} not found"}

    meta = existing["metadatas"][0]
    use_count = int(meta.get("use_count", 0)) + 1
    success_count = int(meta.get("success_count", 0)) + (1 if success else 0)

    meta["use_count"] = use_count
    meta["success_count"] = success_count
    meta["last_used"] = datetime.now(timezone.utc).isoformat()

    # Quality tier transitions (SoK lifecycle: evaluation → update)
    old_tier = meta.get("quality_tier", TIER_CANDIDATE)
    success_rate = success_count / use_count
    if use_count >= VERIFY_MIN_USES and success_rate >= VERIFY_MIN_SUCCESS_RATE:
        meta["quality_tier"] = TIER_VERIFIED
        # Boost importance for verified procedures
        meta["importance"] = min(1.0, float(meta.get("importance", 0.8)) + 0.05)
    elif use_count >= VERIFY_MIN_USES and success_rate < STALE_MAX_SUCCESS_RATE:
        meta["quality_tier"] = TIER_STALE

    col.upsert(
        ids=[proc_id],
        documents=existing["documents"],
        metadatas=[meta],
    )

    return {
        "use_count": use_count,
        "success_count": success_count,
        "success_rate": success_rate,
        "quality_tier": meta["quality_tier"],
        "tier_changed": old_tier != meta["quality_tier"],
    }


def learn_from_task(task_text: str, steps: list[str], tags: list[str] | None = None) -> str:
    """Learn a procedure from a successful task execution.

    Extracts a reusable procedure name from the task text and stores it.

    Args:
        task_text: The original task description
        steps: The steps that were executed successfully

    Returns:
        The procedure memory ID
    """
    # Derive a short name from the task text
    name = _derive_name(task_text)
    description = task_text[:200]

    return store_procedure(
        name=name,
        description=description,
        steps=steps,
        source_task=task_text,
        tags=tags or [],
    )


def learn_from_failures() -> dict:
    """Convert soft failures from failure_amplifier into corrective procedures.

    Scans autonomous.log and reasoning chains for soft failures, then creates
    a procedure for each failure type+task combo with avoidance steps.
    This closes the failure→learning pipeline gap.

    Returns:
        Dict with counts: {scanned, failures_found, procedures_created, skipped}
    """
    if not _HAS_FAILURE_AMPLIFIER:
        return {"error": "failure_amplifier not available", "procedures_created": 0}

    if not AUTONOMOUS_LOG.exists():
        return {"scanned": 0, "failures_found": 0, "procedures_created": 0, "skipped": 0}

    log_text = AUTONOMOUS_LOG.read_text()
    entries = parse_log_entries(log_text)

    all_failures = []
    all_failures.extend(scan_duplicate_tasks(entries))
    all_failures.extend(scan_long_durations(entries))
    all_failures.extend(scan_skipped_learning(entries))
    all_failures.extend(scan_prediction_misses(entries))
    all_failures.extend(scan_retroactive_fixes(entries))
    all_failures.extend(scan_low_capability_scores(entries))
    all_failures.extend(scan_low_confidence_predictions(entries))
    all_failures.extend(scan_uncompleted_tasks(entries))

    chain_failures, _ = scan_reasoning_chains()
    all_failures.extend(chain_failures)

    created = 0
    skipped = 0

    for sf in all_failures:
        task_short = sf["task"][:120]
        fail_type = sf["type"]
        detail = sf["detail"]

        # Build a corrective procedure name
        proc_name = f"avoid_{fail_type}_{_sanitize_name(task_short)}"[:80]

        # Check if we already have this procedure (avoid duplicates)
        existing = find_procedure(f"avoid {fail_type} {task_short}", threshold=0.3)
        if existing:
            skipped += 1
            continue

        # Generate corrective steps based on failure type
        steps = _failure_to_steps(fail_type, task_short, detail)

        store_procedure(
            name=proc_name,
            description=f"Corrective procedure: {detail[:150]}",
            steps=steps,
            source_task=f"[FAILURE] {task_short}",
            importance=min(0.9, 0.6 + sf["severity"] * 0.3),
            tags=["corrective", "failure_learned", fail_type],
        )
        created += 1

    return {
        "scanned": len(entries),
        "failures_found": len(all_failures),
        "procedures_created": created,
        "skipped": skipped,
    }


def retire_stale(dry_run: bool = False) -> dict:
    """Prune stale and low-quality procedures (SoK Pattern 4: quality gates).

    Marks unused/failing procedures as STALE, and deletes procedures that have
    been stale for >RETIRE_DAYS. Prevents "skill debt" accumulation.

    Args:
        dry_run: If True, report what would happen without changing anything.

    Returns:
        Dict with counts: {checked, marked_stale, retired, kept}
    """
    now = datetime.now(timezone.utc)
    results = brain.get(PROCEDURES, n=200)

    marked_stale = 0
    retired = 0
    kept = 0

    for r in results:
        meta = r.get("metadata", {})
        proc_id = r["id"]
        use_count = int(meta.get("use_count", 0))
        success_count = int(meta.get("success_count", 0))
        success_rate = success_count / use_count if use_count > 0 else 1.0
        tier = meta.get("quality_tier", TIER_CANDIDATE)

        # Parse last_used / created_at for staleness
        last_active = meta.get("last_used") or meta.get("created_at") or meta.get("timestamp", "")
        try:
            last_dt = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            last_dt = now - timedelta(days=RETIRE_DAYS + 1)  # Unknown = treat as old

        days_inactive = (now - last_dt).days

        # Rule 1: Mark stale if unused >STALE_DAYS and not already verified
        if days_inactive > STALE_DAYS and tier != TIER_VERIFIED:
            if tier != TIER_STALE:
                if not dry_run:
                    meta["quality_tier"] = TIER_STALE
                    col = brain.collections[PROCEDURES]
                    col.upsert(ids=[proc_id], documents=[r["document"]], metadatas=[meta])
                marked_stale += 1
                continue

        # Rule 2: Mark stale if used 3+ times but success rate <30%
        if use_count >= VERIFY_MIN_USES and success_rate < STALE_MAX_SUCCESS_RATE:
            if tier != TIER_STALE:
                if not dry_run:
                    meta["quality_tier"] = TIER_STALE
                    col = brain.collections[PROCEDURES]
                    col.upsert(ids=[proc_id], documents=[r["document"]], metadatas=[meta])
                marked_stale += 1
                continue

        # Rule 3: Retire (delete) if stale + inactive > RETIRE_DAYS
        if tier == TIER_STALE and days_inactive > RETIRE_DAYS:
            if not dry_run:
                col = brain.collections[PROCEDURES]
                col.delete(ids=[proc_id])
            retired += 1
            continue

        kept += 1

    return {
        "checked": len(results),
        "marked_stale": marked_stale,
        "retired": retired,
        "kept": kept,
        "dry_run": dry_run,
    }


def compose_procedures(name: str, description: str,
                       procedure_ids: list[str],
                       preconditions: list[str] | None = None,
                       termination_criteria: list[str] | None = None) -> str:
    """Create a composite procedure from existing ones (SoK: hierarchical composition).

    The composed procedure stores references to sub-procedures and flattens
    their steps into a single sequence with sub-procedure markers.

    Args:
        name: Name for the composite procedure
        description: What the composed workflow does
        procedure_ids: Ordered list of procedure IDs to compose
        preconditions: Overall preconditions for the composite
        termination_criteria: Overall success criteria

    Returns:
        The composite procedure ID
    """
    col = brain.collections[PROCEDURES]
    composed_steps = []
    valid_deps = []

    for pid in procedure_ids:
        existing = col.get(ids=[pid])
        if not existing or not existing["ids"]:
            composed_steps.append(f"[MISSING: {pid}]")
            continue

        meta = existing["metadatas"][0]
        sub_name = meta.get("name", pid)
        sub_steps = _parse_json_field(meta.get("steps", "[]"))

        composed_steps.append(f"--- {sub_name} ---")
        composed_steps.extend(sub_steps)
        valid_deps.append(pid)

    return store_procedure(
        name=name,
        description=description,
        steps=composed_steps,
        source_task=f"Composed from: {', '.join(valid_deps)}",
        importance=0.85,
        tags=["composite", "workflow"],
        preconditions=preconditions,
        termination_criteria=termination_criteria,
        dependencies=valid_deps,
    )


def library_stats() -> dict:
    """Return health metrics for the procedure library.

    Tracks the distribution across quality tiers, composition depth,
    and overall library utilization — SoK evaluation dimension.
    """
    results = brain.get(PROCEDURES, n=200)

    tiers = {TIER_CANDIDATE: 0, TIER_VERIFIED: 0, TIER_STALE: 0}
    total_uses = 0
    total_successes = 0
    composites = 0
    with_preconditions = 0
    with_termination = 0

    for r in results:
        meta = r.get("metadata", {})
        tier = meta.get("quality_tier", TIER_CANDIDATE)
        tiers[tier] = tiers.get(tier, 0) + 1
        total_uses += int(meta.get("use_count", 0))
        total_successes += int(meta.get("success_count", 0))
        deps = _parse_json_field(meta.get("dependencies", "[]"))
        if deps:
            composites += 1
        if _parse_json_field(meta.get("preconditions", "[]")):
            with_preconditions += 1
        if _parse_json_field(meta.get("termination_criteria", "[]")):
            with_termination += 1

    total = len(results)
    return {
        "total": total,
        "tiers": tiers,
        "verified_pct": round(tiers.get(TIER_VERIFIED, 0) / total * 100, 1) if total else 0,
        "total_uses": total_uses,
        "total_successes": total_successes,
        "overall_success_rate": round(total_successes / total_uses, 3) if total_uses else 1.0,
        "composites": composites,
        "with_preconditions": with_preconditions,
        "with_termination_criteria": with_termination,
        "skill_tuple_completeness": round(
            (with_preconditions + with_termination + total) / (total * 3) * 100, 1
        ) if total else 0,
    }


def _parse_json_field(raw) -> list:
    """Safely parse a JSON field that may be a string or already a list."""
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw) if raw else []
    except (json.JSONDecodeError, TypeError):
        return []


def _failure_to_steps(fail_type: str, task: str, detail: str) -> list[str]:
    """Generate corrective steps based on the failure type."""
    base_steps = {
        "duplicate_execution": [
            "Check if task was already attempted (search episodes)",
            "Review prior attempt output before re-executing",
            "Identify what was insufficient in first attempt",
            "Address root cause, not just symptoms",
            "Verify completion criteria before marking done",
        ],
        "long_duration": [
            "Set explicit time budget before starting (max 5 min)",
            "Break task into smaller sub-steps first",
            "Check for existing procedures before attempting",
            "If stuck >3 min, pivot to alternative approach",
            "Record what caused the delay for future avoidance",
        ],
        "skipped_learning": [
            "Ensure task output includes concrete, extractable steps",
            "Write explicit step list in output summary",
            "Avoid vague summaries — be specific about what was done",
            "Include file paths and commands in step descriptions",
        ],
        "prediction_miss": [
            "Record prediction ID when making predictions",
            "Check for unresolved predictions at session end",
            "Use explicit prediction format with trackable IDs",
        ],
        "retroactive_fix": [
            "Add verification step after initial implementation",
            "Test the actual behavior, not just syntax",
            "Check edge cases before marking task complete",
            "Run integration test if wiring new components",
        ],
        "low_capability": [
            "Identify the specific capability gap",
            "Search brain for relevant procedures/learnings",
            "Consider if task needs a different approach or model",
            "Record what capability needs improvement",
        ],
        "shallow_reasoning": [
            "Use multi-step reasoning for non-trivial tasks",
            "Record intermediate conclusions, not just final answer",
            "Include evidence/reasoning for each step",
        ],
        "low_confidence": [
            "Gather more evidence before making predictions",
            "Only predict when confidence > 60%",
            "State uncertainty explicitly rather than hedging",
        ],
        "uncompleted_task": [
            "Set appropriate timeout for task complexity",
            "Add checkpoint saves for long-running tasks",
            "Log progress so partial work is recoverable",
            "Check for lock files or resource conflicts before starting",
        ],
    }
    return base_steps.get(fail_type, [
        f"Analyze root cause of {fail_type} failure",
        "Identify corrective action",
        "Implement fix and verify",
        "Record learnings for future avoidance",
    ])


def list_procedures(n: int = 50) -> list[dict]:
    """List all stored procedures.

    Returns:
        List of procedure dicts sorted by use_count (most used first)
    """
    results = brain.get(PROCEDURES, n=n)

    procedures = []
    for r in results:
        meta = r.get("metadata", {})
        steps = []
        try:
            steps = json.loads(meta.get("steps", "[]"))
        except (json.JSONDecodeError, TypeError):
            steps = []

        use_count = int(meta.get("use_count", 0))
        success_count = int(meta.get("success_count", 0))

        procedures.append({
            "id": r["id"],
            "name": meta.get("name", "unknown"),
            "description": r["document"],
            "steps": steps,
            "step_count": len(steps),
            "use_count": use_count,
            "success_count": success_count,
            "success_rate": success_count / use_count if use_count > 0 else 1.0,
            "importance": float(meta.get("importance", 0)),
            "quality_tier": meta.get("quality_tier", TIER_CANDIDATE),
            "dependencies": _parse_json_field(meta.get("dependencies", "[]")),
        })

    procedures.sort(key=lambda p: p["use_count"], reverse=True)
    return procedures


def _sanitize_name(name: str) -> str:
    """Convert a name to a safe ID string."""
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower().strip())
    sanitized = re.sub(r'_+', '_', sanitized).strip('_')
    return sanitized[:80]


def _derive_name(task_text: str) -> str:
    """Derive a short procedure name from task text."""
    # Remove common prefixes
    text = task_text.strip()
    for prefix in ["Build ", "Create ", "Implement ", "Add ", "Wire ", "Make ", "Set up "]:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break

    # Take first meaningful chunk (up to first dash or period)
    text = text.split("—")[0].split(" — ")[0].split(". ")[0].strip()
    # Limit length
    words = text.split()[:6]
    return "_".join(words).lower()


# === CLI ===

def main():
    if len(sys.argv) < 2:
        print("Usage: procedural_memory.py <command> [args]")
        print("Commands:")
        print("  check <task_text>         - Find matching procedure for a task")
        print("  learn <task_text> <steps>  - Store procedure from successful task")
        print("  used <proc_id> <success|failure> - Record procedure usage")
        print("  list                       - List all procedures")
        print("  store <name> <desc> <steps> - Store a named procedure")
        print("  failures                   - Learn procedures from soft failures")
        print("  retire [--dry-run]         - Prune stale/low-quality procedures")
        print("  compose <name> <proc_ids>  - Create composite from existing procs")
        print("  stats                      - Library health metrics")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "check":
        task_text = sys.argv[2] if len(sys.argv) > 2 else ""
        if not task_text:
            print("{}", flush=True)
            sys.exit(0)
        result = find_procedure(task_text)
        if result:
            print(json.dumps(result, indent=2))
        else:
            print("{}", flush=True)

    elif cmd == "learn":
        task_text = sys.argv[2] if len(sys.argv) > 2 else ""
        steps_json = sys.argv[3] if len(sys.argv) > 3 else "[]"
        try:
            steps = json.loads(steps_json)
        except json.JSONDecodeError:
            # Try splitting by semicolons if not valid JSON
            steps = [s.strip() for s in steps_json.split(";") if s.strip()]
        proc_id = learn_from_task(task_text, steps)
        print(f"Learned: {proc_id}")

    elif cmd == "used":
        proc_id = sys.argv[2] if len(sys.argv) > 2 else ""
        success_str = sys.argv[3] if len(sys.argv) > 3 else "success"
        success = success_str.lower() in ("success", "true", "1", "yes")
        result = record_use(proc_id, success)
        print(json.dumps(result))

    elif cmd == "list":
        procs = list_procedures()
        if not procs:
            print("No procedures stored yet.")
        else:
            for p in procs:
                rate = f"{p['success_rate']:.0%}" if p['use_count'] > 0 else "new"
                tier = p.get('quality_tier', '?')[0].upper()  # V/C/S
                deps = p.get('dependencies', [])
                dep_tag = f" [composed:{len(deps)}]" if deps else ""
                print(f"  [{tier}] [{p['id']}] {p['name']} ({p['step_count']} steps, used {p['use_count']}x, {rate}){dep_tag}")
                if p['steps']:
                    for i, step in enumerate(p['steps'], 1):
                        print(f"    {i}. {step}")

    elif cmd == "failures" or cmd == "learn-failures":
        result = learn_from_failures()
        print(f"Scanned: {result.get('scanned', 0)} entries")
        print(f"Failures found: {result.get('failures_found', 0)}")
        print(f"Procedures created: {result.get('procedures_created', 0)}")
        print(f"Skipped (already exists): {result.get('skipped', 0)}")
        if result.get("error"):
            print(f"Error: {result['error']}")

    elif cmd == "store":
        name = sys.argv[2] if len(sys.argv) > 2 else ""
        desc = sys.argv[3] if len(sys.argv) > 3 else ""
        steps_json = sys.argv[4] if len(sys.argv) > 4 else "[]"
        try:
            steps = json.loads(steps_json)
        except json.JSONDecodeError:
            steps = [s.strip() for s in steps_json.split(";") if s.strip()]
        proc_id = store_procedure(name, desc, steps)
        print(f"Stored: {proc_id}")

    elif cmd == "retire":
        dry = "--dry-run" in sys.argv
        result = retire_stale(dry_run=dry)
        prefix = "[DRY RUN] " if dry else ""
        print(f"{prefix}Checked: {result['checked']}")
        print(f"{prefix}Marked stale: {result['marked_stale']}")
        print(f"{prefix}Retired (deleted): {result['retired']}")
        print(f"{prefix}Kept: {result['kept']}")

    elif cmd == "compose":
        name = sys.argv[2] if len(sys.argv) > 2 else ""
        ids_json = sys.argv[3] if len(sys.argv) > 3 else "[]"
        try:
            proc_ids = json.loads(ids_json)
        except json.JSONDecodeError:
            proc_ids = [s.strip() for s in ids_json.split(",") if s.strip()]
        desc = sys.argv[4] if len(sys.argv) > 4 else f"Composite: {name}"
        proc_id = compose_procedures(name, desc, proc_ids)
        print(f"Composed: {proc_id}")

    elif cmd == "seed-templates":
        result = seed_code_templates()
        print(f"Seeded {result['seeded']} code templates into procedural memory")
        print(f"Total built-in templates: {result['total_templates']}")

    elif cmd == "templates":
        task_text = sys.argv[2] if len(sys.argv) > 2 else ""
        if not task_text:
            # List all built-in templates
            for key, tmpl in CODE_TEMPLATES.items():
                print(f"  [{key}] {tmpl['description']}")
                for kw in tmpl["match_keywords"][:3]:
                    print(f"    keyword: {kw}")
        else:
            templates = find_code_templates(task_text)
            if templates:
                print(format_code_templates(templates))
            else:
                print("No matching templates found.")

    elif cmd == "stats":
        s = library_stats()
        print(f"Procedure Library Stats:")
        print(f"  Total: {s['total']}")
        print(f"  Tiers: verified={s['tiers'].get('verified',0)}, candidate={s['tiers'].get('candidate',0)}, stale={s['tiers'].get('stale',0)}")
        print(f"  Verified: {s['verified_pct']}%")
        print(f"  Total uses: {s['total_uses']} ({s['total_successes']} successes)")
        print(f"  Overall success rate: {s['overall_success_rate']:.1%}")
        print(f"  Composites: {s['composites']}")
        print(f"  Skill tuple completeness: {s['skill_tuple_completeness']}%")
        print(f"    with preconditions: {s['with_preconditions']}")
        print(f"    with termination criteria: {s['with_termination_criteria']}")

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
