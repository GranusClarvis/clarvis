"""Open-source readiness smoke tests.

Validates that the Clarvis repo is in a presentable, releasable state:
  1. All core modules import cleanly
  2. Mode system wiring is complete (gates exist in pipeline)
  3. No hardcoded secrets in tracked Python files
  4. Key API surfaces are consistent
  5. Package metadata is valid
  6. Brain query policy (retrieval gate) classifies correctly

These are fast, offline tests — no ChromaDB, no LLM, no network.
"""

import ast
import importlib
import os
import re

import pytest

WORKSPACE = os.environ.get(
    "CLARVIS_WORKSPACE",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)


# ---------------------------------------------------------------------------
# §1  Core module imports — every public module imports without error
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module_path", [
    "clarvis.brain",
    "clarvis.brain.retrieval_gate",
    "clarvis.context.assembly",
    "clarvis.cognition.attention",
    "clarvis.adapters",
    "clarvis.adapters.openclaw",
    "clarvis.compat.contracts",
    "clarvis.runtime",
    "clarvis.runtime.mode",
    "clarvis.metrics.clr",
    "clarvis.metrics.trajectory",
    "clarvis.orch.task_selector",
    "clarvis.cli",
])
def test_core_module_imports(module_path):
    """Every public Clarvis module imports without error."""
    mod = importlib.import_module(module_path)
    assert mod is not None


# ---------------------------------------------------------------------------
# §2  Mode system wiring — gates exist in execution pipeline
# ---------------------------------------------------------------------------

def test_mode_gate_in_task_selector():
    """task_selector.score_tasks() contains mode compliance filtering."""
    import inspect
    from clarvis.orch import task_selector
    source = inspect.getsource(task_selector.score_tasks)
    assert "is_task_allowed_for_mode" in source, \
        "score_tasks() missing mode gate — tasks won't be filtered by operating mode"


def test_mode_gate_in_heartbeat_preflight():
    """heartbeat_preflight.py contains mode compliance gate (Gate 4)."""
    preflight_path = os.path.join(WORKSPACE, "scripts", "pipeline", "heartbeat_preflight.py")
    with open(preflight_path) as f:
        content = f.read()
    assert "is_task_allowed_for_mode" in content, \
        "heartbeat_preflight.py missing mode gate — tasks bypass mode filtering"
    assert "mode_gate" in content, \
        "heartbeat_preflight.py missing mode_gate label in deferred reason"


def test_mode_gate_in_heartbeat_gate():
    """heartbeat gate checks mode_policies before waking."""
    import inspect
    from clarvis.heartbeat import gate
    source = inspect.getsource(gate)
    assert "mode_policies" in source, \
        "heartbeat gate.py missing mode_policies check — passive mode won't block wake"


def test_mode_gate_in_queue_writer():
    """queue_writer.py gates task injection by mode."""
    qw_path = os.path.join(WORKSPACE, "scripts", "evolution", "queue_writer.py")
    with open(qw_path) as f:
        content = f.read()
    assert "should_allow_auto_task_injection" in content, \
        "queue_writer.py missing auto-injection mode gate"


def test_mode_policies_cover_all_behavioral_dimensions():
    """mode_policies returns all 8 expected policy keys for every mode."""
    from clarvis.runtime.mode import mode_policies, VALID_MODES
    expected_keys = {
        "mode", "allow_autonomous_execution",
        "allow_autonomous_queue_generation", "allow_research_bursts",
        "allow_self_surgery", "allow_user_assigned_execution",
        "enforce_improve_existing", "allow_new_feature_work",
    }
    for m in VALID_MODES:
        policies = mode_policies(m)
        missing = expected_keys - set(policies.keys())
        assert not missing, f"Mode '{m}' missing policy keys: {missing}"


def test_mode_task_filtering_correctness():
    """Mode system correctly blocks/allows tasks by mode + source."""
    from clarvis.runtime.mode import is_task_allowed_for_mode

    # ge allows everything
    allowed, _ = is_task_allowed_for_mode("[AUTO 2026-03-17] Build new feature", mode="ge")
    assert allowed is True

    # passive blocks autonomous
    allowed, reason = is_task_allowed_for_mode("[AUTO 2026-03-17] Build new feature", mode="passive")
    assert allowed is False
    assert "passive_blocks" in reason

    # passive allows user-directed
    allowed, _ = is_task_allowed_for_mode("[MANUAL 2026-03-17] Build new feature", mode="passive")
    assert allowed is True

    # architecture blocks non-improvement autonomous
    allowed, reason = is_task_allowed_for_mode(
        "[AUTO 2026-03-17] Build new feature for discovery", mode="architecture"
    )
    assert allowed is False

    # architecture allows improvement tasks
    allowed, _ = is_task_allowed_for_mode(
        "[AUTO 2026-03-17] Fix retrieval regression", mode="architecture"
    )
    assert allowed is True


# ---------------------------------------------------------------------------
# §3  Retrieval gate — brain query policy classifies correctly
# ---------------------------------------------------------------------------

def test_retrieval_gate_maintenance_is_no_retrieval():
    """Maintenance tasks should not trigger brain queries."""
    from clarvis.brain.retrieval_gate import classify_retrieval
    tier = classify_retrieval("[BACKUP] Run backup_daily.sh")
    assert tier.tier == "NO_RETRIEVAL"


def test_retrieval_gate_research_is_deep():
    """Research tasks should trigger deep retrieval."""
    from clarvis.brain.retrieval_gate import classify_retrieval
    tier = classify_retrieval("[RESEARCH_DISCOVERY] Survey consciousness architectures")
    assert tier.tier == "DEEP_RETRIEVAL"
    assert tier.graph_expand is True


def test_retrieval_gate_delivery_is_light():
    """Delivery tasks use light retrieval (scoped, not deep)."""
    from clarvis.brain.retrieval_gate import classify_retrieval
    tier = classify_retrieval("[DLV_WEBSITE] Build website landing page")
    assert tier.tier == "LIGHT_RETRIEVAL"
    assert tier.n_results <= 5


# ---------------------------------------------------------------------------
# §4  No hardcoded secrets in tracked Python files
# ---------------------------------------------------------------------------

_SECRET_PATTERNS = [
    re.compile(r'sk-or-v1-[a-f0-9]{64}', re.I),      # OpenRouter API key
    re.compile(r'\b\d{10}:AAF-[A-Za-z0-9_-]{30,}'),   # Telegram bot token
    re.compile(r'C_artOnHs\$32'),                       # Known test password
]


def _get_tracked_python_files():
    """Get list of tracked (non-deprecated) Python files."""
    result = []
    for root, dirs, files in os.walk(WORKSPACE):
        # Skip non-tracked directories
        if "deprecated" in root or ".git" in root or "node_modules" in root:
            continue
        if "data/" in root.replace(WORKSPACE, ""):
            continue
        for f in files:
            if f.endswith(".py"):
                result.append(os.path.join(root, f))
    return result


@pytest.mark.parametrize("pattern", _SECRET_PATTERNS, ids=["openrouter_key", "telegram_token", "test_password"])
def test_no_secrets_in_python_source(pattern):
    """No hardcoded secrets in tracked Python source files."""
    violations = []
    for fpath in _get_tracked_python_files():
        try:
            with open(fpath) as f:
                content = f.read()
            if pattern.search(content):
                rel = os.path.relpath(fpath, WORKSPACE)
                violations.append(rel)
        except (OSError, UnicodeDecodeError):
            continue
    assert not violations, f"Secret pattern found in: {violations}"


# ---------------------------------------------------------------------------
# §5  Package metadata — pyproject.toml files are valid
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pkg", ["clarvis-db", "clarvis-cost", "clarvis-reasoning"])
def test_package_pyproject_valid(pkg):
    """Each legacy package has a parseable pyproject.toml with name and version.

    Note: packages are deprecated — clarvis-cost migrated to clarvis.orch.cost_tracker,
    clarvis-reasoning to clarvis.cognition.reasoning, clarvis-db to clarvis.brain.
    """
    import tomllib
    toml_path = os.path.join(WORKSPACE, "packages", pkg, "pyproject.toml")
    if not os.path.exists(toml_path):
        pytest.skip(f"{pkg}/pyproject.toml not found (package may have been removed)")
    with open(toml_path, "rb") as f:
        data = tomllib.load(f)
    project = data.get("project", {})
    assert project.get("name"), f"{pkg} missing project.name"
    assert project.get("version"), f"{pkg} missing project.version"


# ---------------------------------------------------------------------------
# §6  Contract checks pass — adapter/compat boundary is sound
# ---------------------------------------------------------------------------

def test_compat_contract_checks_pass():
    """Full contract check passes against current live modules."""
    from clarvis.compat.contracts import run_contract_checks
    result = run_contract_checks()
    assert result["all_passed"] is True, f"Contract failures: {result['checks']}"


# ---------------------------------------------------------------------------
# §7  CLI structure — all expected subcommands registered
# ---------------------------------------------------------------------------

def test_cli_has_all_subcommands():
    """CLI app registers brain, bench, mode, heartbeat, queue subcommands."""
    from clarvis.cli import app, _register_subcommands
    _register_subcommands()
    group_names = [
        g.typer_instance.info.name or g.name
        for g in app.registered_groups
    ]
    for expected in ("brain", "bench", "mode", "heartbeat", "queue"):
        assert expected in group_names, f"'{expected}' missing from CLI groups: {group_names}"
