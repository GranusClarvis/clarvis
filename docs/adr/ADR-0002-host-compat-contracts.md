# ADR-0002 — Add host compatibility contract checks

- **Date:** 2026-03-15
- **Status:** Accepted
- **Decision type:** **Improve**
- **Scope:** Plug-and-play viability (OpenClaw/Hermes/NanoClaw)

## Context

The plan requires explicit compatibility contract tests for target hosts and
adapter-friendly boundaries before extraction.

Before this ADR:

- API boundary docs existed for ClarvisDB/ClarvisP.
- there was no executable compatibility contract runner.

## Decision

Add explicit host contract definitions and executable checks:

1. `clarvis/compat/contracts.py`
   - host matrix: openclaw, hermes, nanoclaw
   - required brain/context operations per host
   - `run_contract_checks()` report
2. `scripts/compat_contract_check.py`
   - JSON report + process exit code contract
3. tests and doc linkage
   - `tests/test_host_compat_contracts.py`
   - boundary docs updated with command usage

## Benchmark delta / evidence

- `pytest tests/test_host_compat_contracts.py` ✅
- `python3 scripts/compat_contract_check.py` ✅ (all hosts pass)

## Consequences

Positive:

- Converts plug-and-play requirement into executable checks.
- Adds a repeatable pre-extraction signal.

Tradeoffs:

- Current checks validate API contracts, not full runtime adapters.
- Real host adapters still required for full end-to-end certification.
