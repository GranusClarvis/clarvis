"""Host compatibility contracts for ClarvisDB extraction readiness.

Currently scoped to OpenClaw only.  Add Hermes/NanoClaw contracts when
real host consumers exist (see docs/FORK_INTEGRATION_PLAN §2.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class HostContract:
    host: str
    required_brain_ops: tuple[str, ...]
    required_context_ops: tuple[str, ...]
    required_adapter_methods: tuple[str, ...]
    notes: str


CONTRACTS: tuple[HostContract, ...] = (
    HostContract(
        host="openclaw",
        required_brain_ops=("get_brain", "remember", "search"),
        required_context_ops=("generate_tiered_brief",),
        required_adapter_methods=("store_memory", "search_memory", "build_context"),
        notes="primary host; supports context engine injection",
    ),
    # Hermes and NanoClaw contracts deferred until real consumers exist.
    # See docs/FORK_INTEGRATION_PLAN_2026-03-15.md §2.2 for templates.
)


def _missing(symbols: Iterable[str], required: tuple[str, ...]) -> list[str]:
    symbol_set = set(symbols)
    return [name for name in required if name not in symbol_set]


def run_contract_checks() -> dict:
    """Validate host contract requirements against current public APIs."""
    import clarvis.brain as brain_mod
    import clarvis.context.assembly as context_assembly
    from clarvis.adapters import get_adapter

    brain_symbols = set(dir(brain_mod))
    context_symbols = set(dir(context_assembly))

    checks = []
    for c in CONTRACTS:
        missing_brain = _missing(brain_symbols, c.required_brain_ops)
        missing_context = _missing(context_symbols, c.required_context_ops)
        adapter = get_adapter(c.host)
        adapter_symbols = set(dir(adapter))
        missing_adapter = _missing(adapter_symbols, c.required_adapter_methods)
        checks.append(
            {
                "host": c.host,
                "missing_brain_ops": missing_brain,
                "missing_context_ops": missing_context,
                "missing_adapter_methods": missing_adapter,
                "pass": not missing_brain and not missing_context and not missing_adapter,
                "notes": c.notes,
            }
        )

    all_passed = all(item["pass"] for item in checks)
    return {"all_passed": all_passed, "checks": checks}
