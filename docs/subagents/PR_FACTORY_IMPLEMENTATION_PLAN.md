# PR Factory Implementation Plan

_Concrete wrapper integration around `scripts/project_agent.py`. Three phases, additive only._

Authoritative spec: `docs/subagents/PR_FACTORY_SPEC.md`

---

## Architecture: Wrapper, Not Rewrite

The PR factory is **not** a new orchestrator. It is a set of modules that enrich the existing `cmd_spawn` flow at well-defined seams.

### What Stays Unchanged

| Component | File | Lines | Why |
|-----------|------|-------|-----|
| Agent isolation | `project_agent.py` | `_agent_dir`, `create`, `destroy` | Works, tested |
| Branch creation | `project_agent.py` | `_sync_and_checkout_work_branch` (648) | Works, tested |
| Concurrency locks | `project_agent.py` | `_acquire_agent_claude_lock`, `_acquire_claude_slot` | Works, tested |
| A2A protocol | `project_agent.py` | `normalize_a2a_result`, `validate_a2a_result` | Works, tested |
| Commit safety | `project_agent.py` | `safe_stage_files`, `COMMIT_EXT_WHITELIST` | Works, tested |
| Trust gates | `project_agent.py` | `get_trust_tier`, `_apply_spawn_trust` | Works, tested |
| Retry logic | `project_agent.py` | `cmd_spawn_with_retry` (1622) | Works, tested |
| CI context scan | `project_agent.py` | `build_ci_context` (1056) | Works, evolves separately |
| Dependency map | `project_agent.py` | `build_dependency_map` (848) | Works, evolves separately |
| LiteBrain | `scripts/lite_brain.py` | All | Works, tested |

### Integration Seams

Two seams in `cmd_spawn` (line 1323):

**Seam 1 — Pre-prompt enrichment** (after line 1378, before `build_spawn_prompt`):
```python
# NEW: PR factory context build (Phase 2+3)
factory_context = ""
try:
    from pr_factory import build_factory_context
    factory_context = build_factory_context(name, task, agent_dir)
except ImportError:
    pass  # factory not installed yet — graceful degradation
```

**Seam 2 — Prompt injection** (inside `build_spawn_prompt`, after existing sections, before A2A protocol):
```python
# NEW: PR factory rules (Phase 1)
pr_factory_rules = _load_pr_factory_rules(agent_dir)
if pr_factory_rules:
    prompt_parts.extend(pr_factory_rules)

# NEW: Execution brief (Phase 3)
if factory_context:
    prompt_parts.extend([
        "## Execution Brief (compiled)",
        factory_context,
        "",
    ])
```

**Seam 3 — Post-spawn writeback** (after line 1503, after summary_file write):
```python
# NEW: PR factory memory writeback (Phase 3)
try:
    from pr_factory import run_writeback
    run_writeback(name, agent_dir, agent_result, task)
except (ImportError, Exception) as e:
    _log(f"PR factory writeback skipped: {e}")
```

---

## New Files

### Phase 1

| File | Purpose | Size |
|------|---------|------|
| `scripts/pr_factory_rules.py` | Generates PR class rules, two-PR policy, refinement limits as prompt sections | ~120 lines |
| `scripts/tests/test_pr_factory_rules.py` | Acceptance tests for prompt injection | ~200 lines |

### Phase 2

| File | Purpose | Size |
|------|---------|------|
| `scripts/pr_factory_intake.py` | Deterministic artifact generators (project_brief, stack_detect, commands, architecture_map) | ~300 lines |
| `scripts/pr_factory_indexes.py` | Precision index builders (file, symbol, route, config, test) | ~250 lines |
| `scripts/tests/test_pr_factory_intake.py` | Tests for artifact generation + staleness | ~150 lines |

### Phase 3

| File | Purpose | Size |
|------|---------|------|
| `scripts/pr_factory.py` | Main module: `build_factory_context()` (brief compiler) + `run_writeback()` | ~200 lines |
| `scripts/tests/test_pr_factory.py` | Tests for brief compilation + writeback | ~150 lines |

Total new code: ~1370 lines across 6 files. No existing files rewritten.

---

## Phase 1: Spec Sync + Prompt Injection

### Goal
Inject PR factory rules into the spawn prompt so the agent knows about PR classes, two-PR policy, refinement limits, and task-linkage.

### Changes to `project_agent.py`

1. **In `build_spawn_prompt()` (line 1178):** Add a call to load PR factory rules before the A2A protocol section.

```python
# After line 1260 (after context injection), before line 1262 (## Task)
# Load PR factory rules
try:
    from pr_factory_rules import build_pr_rules_section
    rules = build_pr_rules_section()
    prompt_parts.extend(rules)
except ImportError:
    pass
```

2. **In A2A protocol section:** Extend the JSON schema to include `pr_class` field:
```json
"pr_class": "A|B|C"  // REQUIRED when pr_url is set
```

### `scripts/pr_factory_rules.py`

```python
def build_pr_rules_section() -> list[str]:
    """Return prompt lines for PR class rules, injected into spawn prompt."""
    return [
        "## PR Factory Rules (MANDATORY)",
        "",
        "### PR Classes — Every Run Ships a PR",
        "- **Class A**: Task fully implemented and validated.",
        "- **Class B**: Core task done, a real blocker prevented full closure. "
        "Document gap + next step.",
        "- **Class C**: Task blocked. Ship smallest enabling change that "
        "unblocks THE SAME requested task. Not for drive-by cleanups.",
        "",
        "### Two-PR Policy",
        "If blocked: ship Class C first (unblocking), then Class A/B (task).",
        "The unblocking PR must be linked to the original task.",
        "",
        "### Class C Task-Linkage (required in PR body)",
        "- `Original task:` (verbatim)",
        "- `Blocker:` (what prevented implementation)",
        "- `Unblocks:` (how this PR enables the task)",
        "- `Next PR:` (exact next step)",
        "",
        "### Refinement Policy — Max 2 Loops",
        "1. Implement + verify",
        "2. Refine ONLY if: test failed, requirement missed, "
        "scope bloat found, or PR class upgradeable",
        "3. Refine again ONLY if still justified by evidence",
        "4. Then ship. No fourth pass.",
        "",
        "Do NOT loop on: vague unease, speculative perfectionism, "
        "or hallucinated concerns.",
        "Evidence steers but never blocks the requested task.",
        "",
    ]
```

### Changes to A2A Protocol

Add `pr_class` to `A2A_RESULT_SCHEMA` and prompt output protocol section. Validation: if `pr_url` is set, `pr_class` must be one of `A`, `B`, `C`.

---

## Phase 2: Deterministic Intake + Indexes

### Goal
Generate repo artifacts and precision indexes for each agent, stored in `<agent_dir>/data/artifacts/` and `<agent_dir>/data/indexes/`.

### `scripts/pr_factory_intake.py`

Key functions:
- `generate_project_brief(workspace) -> str` — Scan README, docs/, package.json/Cargo.toml/pyproject.toml for product description, domain, constraints.
- `generate_stack_detect(workspace) -> dict` — Detect languages, frameworks, package managers, test/lint/build tools from config files.
- `generate_commands(workspace) -> dict` — Extract install/build/test/lint/typecheck commands from package.json, Makefile, pyproject.toml, etc. Include confidence + verified flag.
- `generate_architecture_map(workspace) -> str` — Entrypoints, module layout from directory scanning + config files.
- `refresh_artifacts(agent_dir, workspace) -> dict` — Orchestrator: check git SHA staleness, regenerate stale artifacts, return freshness report.

Staleness detection: compare `generated_at_sha` in artifact metadata vs current `git rev-parse HEAD`. Refresh if different and >5 files changed.

### `scripts/pr_factory_indexes.py`

Key functions:
- `build_file_index(workspace) -> dict` — Walk source dirs, record path/type/hash/tags.
- `build_symbol_index(workspace, stack) -> dict` — Parse exports/classes/functions from source files. Language-aware (JS/TS: regex on export/class/function; Python: ast.parse; Go: regex on func/type).
- `build_route_index(workspace, stack) -> dict` — Detect routes from Next.js app dir, Express routers, Flask/FastAPI decorators.
- `build_test_index(workspace) -> dict` — Map test files to source modules.
- `refresh_indexes(agent_dir, workspace) -> dict` — Orchestrator: check staleness, regenerate, return freshness.

### Integration

Wire into `cmd_spawn` at Seam 1 (after CI context, before prompt build):

```python
try:
    from pr_factory_intake import refresh_artifacts
    from pr_factory_indexes import refresh_indexes
    refresh_artifacts(agent_dir, workspace)
    refresh_indexes(agent_dir, workspace)
except ImportError:
    pass  # Phase 2 not yet installed
```

Wire artifact summaries into `build_spawn_prompt` — load from `data/artifacts/` and `data/indexes/` similar to existing CI context and dependency map loading.

---

## Phase 3: Brief Compiler + Writeback

### Goal
Compile an execution brief from artifacts + LiteBrain + task classification, and enforce mandatory memory writeback after each run.

### `scripts/pr_factory.py`

Key functions:

```python
def classify_task(task: str) -> str:
    """Classify task into: bugfix|feature|refactor|docs|tests|config|hardening|investigation"""
    # Keyword matching + simple heuristics

def build_factory_context(name: str, task: str, agent_dir: Path) -> str:
    """Compile execution brief from artifacts + indexes + LiteBrain.

    Returns formatted string for prompt injection.
    """
    # 1. Load artifacts (project_brief, stack, commands, architecture)
    # 2. Load relevant indexes
    # 3. Query LiteBrain for relevant facts/episodes
    # 4. Classify task
    # 5. Compile tiered context (Tier 0 always, Tier 1 if relevant)
    # 6. Save execution_brief.json
    # 7. Return formatted brief for prompt

def run_writeback(name: str, agent_dir: Path, result: dict, task: str):
    """Mandatory post-spawn writeback: episode, facts, procedures, golden QA."""
    # 1. Write episode_summary.json from A2A result
    # 2. Extract new facts from result summary → LiteBrain
    # 3. Extract working procedures from result → LiteBrain
    # 4. Update golden QA if confidence > 0.8
```

### Integration

- Seam 1: `build_factory_context()` called in `cmd_spawn` before `build_spawn_prompt`
- Seam 2: Brief injected into prompt via `build_spawn_prompt`
- Seam 3: `run_writeback()` called in `cmd_spawn` after result parsing

---

## Acceptance Test Plan (15 Tests)

All tests in `scripts/tests/test_pr_factory_rules.py` and `scripts/tests/test_pr_factory.py`.

### PR Class Rules (test_pr_factory_rules.py)

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_rules_contain_all_pr_classes` | Output mentions Class A, Class B, Class C |
| 2 | `test_rules_contain_two_pr_policy` | Output mentions "two-PR" or "Class C first" |
| 3 | `test_rules_contain_max_refinement_limit` | Output mentions "Max 2" or "No fourth pass" |
| 4 | `test_rules_contain_task_linkage_fields` | Output mentions Original task, Blocker, Unblocks, Next PR |
| 5 | `test_rules_no_blocking_language` | Output does NOT contain "must prove", "halt", "abort" as unconditional blockers |
| 6 | `test_rules_evidence_steers_not_blocks` | Output contains "steers but never blocks" or equivalent |

### Prompt Integration (test_pr_factory_rules.py)

| # | Test | Verifies |
|---|------|----------|
| 7 | `test_spawn_prompt_includes_pr_rules` | `build_spawn_prompt()` output contains "PR Factory Rules" section |
| 8 | `test_spawn_prompt_includes_a2a_pr_class` | A2A protocol section mentions `pr_class` field |
| 9 | `test_spawn_prompt_graceful_without_factory` | If `pr_factory_rules` not importable, prompt still builds (no crash) |

### A2A Protocol Extension (test_pr_factory_rules.py)

| # | Test | Verifies |
|---|------|----------|
| 10 | `test_a2a_validates_pr_class_when_pr_url_set` | Validation warns if `pr_url` set but `pr_class` missing |
| 11 | `test_a2a_accepts_valid_pr_class` | Validation passes for pr_class in {A, B, C} |

### Factory Context (test_pr_factory.py — Phase 3)

| # | Test | Verifies |
|---|------|----------|
| 12 | `test_task_classification` | Known task strings map to correct classes (bugfix, feature, refactor) |
| 13 | `test_execution_brief_schema` | Brief contains required fields: task_interpretation, task_class, success_criteria |
| 14 | `test_writeback_creates_episode_summary` | After `run_writeback()`, episode_summary.json exists with required fields |
| 15 | `test_writeback_stores_procedures_in_litebrain` | After `run_writeback()` with procedures, LiteBrain query returns them |

### End-to-End Behavioral Tests (manual / integration)

These verify the user's core requirements during pilot runs:

- **E2E-1:** Spawn task → agent creates PR → PR body contains pr_class
- **E2E-2:** Spawn blocked task → agent creates Class C PR with task-linkage fields → next spawn creates Class A/B
- **E2E-3:** Spawn task with pre-existing CI failure → agent does not refine endlessly (max 2 loops) → ships best available class
- **E2E-4:** Spawn task → no drive-by lint/security PRs (diff is scoped to requested task only)
- **E2E-5:** Spawn task → memory writeback creates episode_summary.json with correct fields

---

## Rollout Schedule

| Phase | What | Depends On | Pilot Repo |
|-------|------|------------|------------|
| 1 | Spec sync + prompt injection + acceptance tests | Nothing | star-world-order |
| 2 | Deterministic intake + indexes | Phase 1 | star-world-order |
| 3 | Brief compiler + writeback | Phase 2 | star-world-order |
| General | Roll out to all agents | Phase 3 validated | all |

Each phase: implement → test → pilot 3 runs → validate → next phase.

---

## Risk Mitigations

- **Graceful degradation:** Every import is wrapped in try/except. If a phase isn't installed, the existing flow works unchanged.
- **No rewrite risk:** Only 3 seams touched in `project_agent.py`, each <5 lines.
- **Token budget:** Execution brief has hard cap (~2000 tokens). Tiered context prevents bloat.
- **Rollback:** Remove imports from `project_agent.py` → immediate rollback to pre-factory behavior.
