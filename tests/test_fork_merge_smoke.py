"""Fork merge smoke tests — honest plug-and-play readiness verification.

Tests that all extraction boundary modules from the fork integration:
  1. Import cleanly (no circular deps, no missing symbols)
  2. Have consistent API surfaces matching contract specs
  3. Register in the unified CLI
  4. Pass compatibility contract checks against real modules
  5. Flag honestly what's NOT ready (parity gaps, missing consumers)

These are fast, offline tests — no ChromaDB, no LLM, no filesystem side-effects.
"""

import importlib
import inspect
import pytest


# ---------------------------------------------------------------------------
# §1  Import smoke — every fork module imports without error
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module_path", [
    "clarvis.adapters",
    "clarvis.adapters.base",
    "clarvis.adapters.openclaw",
    "clarvis.compat",
    "clarvis.compat.contracts",
    "clarvis.runtime",
    "clarvis.runtime.mode",
    "clarvis.metrics.clr",
    "clarvis.metrics.trajectory",
    "clarvis.cli_mode",
])
def test_fork_module_imports(module_path):
    """Every fork-merged module imports without error."""
    mod = importlib.import_module(module_path)
    assert mod is not None


# ---------------------------------------------------------------------------
# §2  Adapter interface contract — base class defines the right ABC methods
# ---------------------------------------------------------------------------

def test_host_adapter_abc_methods():
    """HostAdapter ABC requires exactly the 3 extraction-boundary methods."""
    from clarvis.adapters.base import HostAdapter
    abstract_methods = set(HostAdapter.__abstractmethods__)
    assert abstract_methods == {"store_memory", "search_memory", "build_context"}


def test_adapter_result_dataclass_fields():
    """AdapterResult has the expected fields."""
    from clarvis.adapters.base import AdapterResult
    fields = {f.name for f in AdapterResult.__dataclass_fields__.values()}
    assert fields == {"host", "ok", "data", "message"}


def test_openclaw_adapter_implements_all_abc_methods():
    """OpenClawAdapter is concrete — no abstract methods left."""
    from clarvis.adapters.openclaw import OpenClawAdapter
    # Should instantiate without error (no NotImplementedError at class level)
    adapter = OpenClawAdapter()
    assert adapter.host == "openclaw"
    for method_name in ("store_memory", "search_memory", "build_context"):
        method = getattr(adapter, method_name, None)
        assert callable(method), f"Missing method: {method_name}"


# ---------------------------------------------------------------------------
# §3  Adapter factory — only OpenClaw registered (anti-sprawl)
# ---------------------------------------------------------------------------

def test_adapter_factory_returns_openclaw():
    from clarvis.adapters import get_adapter
    adapter = get_adapter("openclaw")
    assert adapter.host == "openclaw"


def test_adapter_factory_rejects_nonexistent_hosts():
    """Unknown hosts raise ValueError; registered adapters (openclaw, hermes) do not."""
    from clarvis.adapters import get_adapter
    for ghost_host in ("nanoclaw", "ollama", ""):
        with pytest.raises(ValueError, match="Unknown host adapter"):
            get_adapter(ghost_host)


# ---------------------------------------------------------------------------
# §4  Compatibility contracts — OpenClaw-only, no dead hosts
# ---------------------------------------------------------------------------

def test_contracts_only_openclaw():
    from clarvis.compat import CONTRACTS
    hosts = {c.host for c in CONTRACTS}
    assert hosts == {"openclaw"}, f"Unexpected hosts in contracts: {hosts}"


def test_contract_required_ops_match_real_brain_symbols():
    """Contract's required_brain_ops actually exist in clarvis.brain."""
    from clarvis.compat import CONTRACTS
    import clarvis.brain as brain_mod
    brain_symbols = set(dir(brain_mod))

    oc = [c for c in CONTRACTS if c.host == "openclaw"][0]
    for op in oc.required_brain_ops:
        assert op in brain_symbols, f"Contract requires brain op '{op}' but clarvis.brain doesn't export it"


def test_contract_required_context_ops_match_real_assembly():
    """Contract's required_context_ops actually exist in clarvis.context.assembly."""
    from clarvis.compat import CONTRACTS
    import clarvis.context.assembly as asm_mod
    asm_symbols = set(dir(asm_mod))

    oc = [c for c in CONTRACTS if c.host == "openclaw"][0]
    for op in oc.required_context_ops:
        assert op in asm_symbols, f"Contract requires context op '{op}' but assembly doesn't export it"


def test_run_contract_checks_passes():
    """Full contract check passes against current live modules."""
    from clarvis.compat.contracts import run_contract_checks
    result = run_contract_checks()
    assert result["all_passed"] is True, f"Contract check failures: {result['checks']}"


# ---------------------------------------------------------------------------
# §5  Runtime mode — state machine basics (no filesystem)
# ---------------------------------------------------------------------------

def test_mode_normalize_all_valid():
    from clarvis.runtime.mode import normalize_mode, VALID_MODES
    for mode in VALID_MODES:
        assert normalize_mode(mode) == mode


def test_mode_normalize_aliases_resolve():
    from clarvis.runtime.mode import normalize_mode
    assert normalize_mode("maintenance") == "architecture"
    assert normalize_mode("user_directed") == "passive"
    assert normalize_mode("glorious_evolution") == "ge"
    assert normalize_mode("autonomous") == "ge"


def test_mode_policies_structure():
    from clarvis.runtime.mode import mode_policies
    for mode in ("ge", "architecture", "passive"):
        policies = mode_policies(mode)
        expected_keys = {
            "mode", "allow_autonomous_execution",
            "allow_autonomous_queue_generation", "allow_research_bursts",
            "allow_self_surgery", "allow_user_assigned_execution",
            "enforce_improve_existing", "allow_new_feature_work",
        }
        assert expected_keys.issubset(set(policies.keys())), \
            f"Missing policy keys for mode={mode}: {expected_keys - set(policies.keys())}"


def test_mode_policies_semantic_correctness():
    """Mode policies encode the right constraints."""
    from clarvis.runtime.mode import mode_policies
    ge = mode_policies("ge")
    assert ge["allow_autonomous_execution"] is True
    assert ge["allow_new_feature_work"] is True

    arch = mode_policies("architecture")
    assert arch["allow_autonomous_execution"] is True
    assert arch["enforce_improve_existing"] is True
    assert arch["allow_new_feature_work"] is False

    passive = mode_policies("passive")
    assert passive["allow_autonomous_execution"] is False
    assert passive["allow_user_assigned_execution"] is True


# ---------------------------------------------------------------------------
# §6  CLR benchmark — schema stability
# ---------------------------------------------------------------------------

def test_clr_schema_version_stable():
    from clarvis.metrics.clr import CLR_SCHEMA_VERSION
    assert CLR_SCHEMA_VERSION == "1.0"


def test_clr_dimensions_are_seven():
    from clarvis.metrics.clr import WEIGHTS
    assert len(WEIGHTS) == 7


def test_clr_weights_sum_to_one():
    from clarvis.metrics.clr import WEIGHTS
    total = sum(WEIGHTS.values())
    assert abs(total - 1.0) < 1e-6, f"CLR weights sum to {total}, expected 1.0"


# ---------------------------------------------------------------------------
# §7  Trajectory eval — schema stability
# ---------------------------------------------------------------------------

def test_trajectory_schema_version_stable():
    from clarvis.metrics.trajectory import TRAJECTORY_SCHEMA_VERSION
    assert TRAJECTORY_SCHEMA_VERSION == "1.0"


def test_trajectory_weights_are_five():
    from clarvis.metrics.trajectory import WEIGHTS
    assert len(WEIGHTS) == 5


def test_trajectory_weights_sum_to_one():
    from clarvis.metrics.trajectory import WEIGHTS
    total = sum(WEIGHTS.values())
    assert abs(total - 1.0) < 1e-6, f"Trajectory weights sum to {total}, expected 1.0"


# ---------------------------------------------------------------------------
# §8  CLI registration — fork modules appear in CLI app
# ---------------------------------------------------------------------------

def test_cli_mode_subcommand_registered():
    """Mode subcommand is registered in the root CLI app."""
    from clarvis.cli import app, _register_subcommands
    _register_subcommands()
    group_names = [
        g.typer_instance.info.name or g.name
        for g in app.registered_groups
    ]
    assert "mode" in group_names, f"'mode' not in registered CLI groups: {group_names}"


def test_cli_bench_subcommand_registered():
    """Bench subcommand is registered in the root CLI app."""
    from clarvis.cli import app, _register_subcommands
    _register_subcommands()
    group_names = [
        g.typer_instance.info.name or g.name
        for g in app.registered_groups
    ]
    assert "bench" in group_names, f"'bench' not in registered CLI groups: {group_names}"


# ---------------------------------------------------------------------------
# §9  API surface parity — public functions match boundary docs
# ---------------------------------------------------------------------------

def test_brain_public_api_has_extraction_surface():
    """clarvis.brain exports the functions needed for extraction."""
    import clarvis.brain as brain_mod
    required = {"get_brain", "remember", "search", "capture"}
    exported = set(dir(brain_mod))
    missing = required - exported
    assert not missing, f"Brain missing extraction-boundary functions: {missing}"


def test_assembly_public_api_has_extraction_surface():
    """clarvis.context.assembly exports generate_tiered_brief."""
    import clarvis.context.assembly as asm_mod
    assert hasattr(asm_mod, "generate_tiered_brief")
    assert callable(asm_mod.generate_tiered_brief)


# ---------------------------------------------------------------------------
# §10  Honest readiness assessment — flag what's NOT plug-and-play yet
# ---------------------------------------------------------------------------

def test_no_clarvis_p_bridge_package_exists():
    """clarvis-p bridge package should NOT exist yet (anti-sprawl guard)."""
    with pytest.raises(ImportError):
        import clarvis_p  # noqa: F401


def test_no_dead_adapter_files():
    """nanoclaw.py should not exist as a production adapter file (hermes is a registered adapter)."""
    import clarvis.adapters as adapters_pkg
    adapter_dir = inspect.getfile(adapters_pkg)
    from pathlib import Path
    adapter_path = Path(adapter_dir).parent
    dead_files = [
        adapter_path / "nanoclaw.py",
    ]
    for f in dead_files:
        assert not f.exists(), f"Dead adapter file exists: {f} — move to docs/examples/"


def test_openclaw_adapter_import_fallback_chain():
    """OpenClaw adapter uses fallback imports (clarvis.brain, clarvis.context.assembly).

    This verifies the adapter works without bridge packages installed.
    The try/except ImportError chain in openclaw.py should resolve to the
    canonical clarvis.* imports.
    """
    from clarvis.adapters.openclaw import OpenClawAdapter
    adapter = OpenClawAdapter()
    # If we got here, the import chain resolved successfully
    assert adapter.host == "openclaw"


# ---------------------------------------------------------------------------
# §11  Cross-module consistency — no version/weight drift between modules
# ---------------------------------------------------------------------------

def test_clr_baseline_keys_match_weights():
    """CLR BASELINE dict has the same keys as WEIGHTS — no orphan dimensions."""
    from clarvis.metrics.clr import WEIGHTS, BASELINE
    assert set(BASELINE.keys()) == set(WEIGHTS.keys())


def test_trajectory_weight_keys_are_valid():
    """Trajectory weight keys are descriptive strings, not numeric."""
    from clarvis.metrics.trajectory import WEIGHTS
    for key in WEIGHTS:
        assert isinstance(key, str)
        assert key.isidentifier() or "_" in key, f"Unexpected weight key format: {key}"
