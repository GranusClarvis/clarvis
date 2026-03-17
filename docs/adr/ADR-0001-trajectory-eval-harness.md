# ADR-0001 — Add trajectory evaluation harness

- **Date:** 2026-03-15
- **Status:** Accepted
- **Decision type:** **Build**
- **Scope:** Benchmark discipline / execution quality

## Context

The plan calls for agentevals-style trajectory scoring to move quality checks from
binary task success toward richer execution-quality signals.

Before this ADR:

- postflight tracked outcomes and validation signals, but no unified trajectory score.
- no dedicated gate for trajectory quality in `clarvis bench` / performance gate.

## Decision

Introduce a first-class trajectory harness:

1. `clarvis/metrics/trajectory.py`
   - per-episode scoring across completion/validation/retrieval alignment/efficiency/tool-call shape
   - persisted history + summary + gate evaluation
2. `scripts/trajectory_eval_harness.py`
   - `report` and `check` commands
3. postflight integration
   - record trajectory events on each execution outcome
4. bench + perf gate integration
   - `clarvis bench trajectory`
   - `clarvis bench trajectory-check`
   - trajectory gate in `scripts/performance_gate.py` (warmup-aware)

## Benchmark delta / evidence

- Unit/contract tests:
  - `tests/test_trajectory_eval.py` ✅
  - `tests/test_performance_gate_trajectory.py` ✅
- Runtime evidence:
  - `scripts/trajectory_eval_harness.py report 24` emits scored summary
  - `scripts/trajectory_eval_harness.py check 24` enforces gate
  - `clarvis bench trajectory-check --hours 24` enforces same gate

## Consequences

Positive:

- Adds trajectory-level quality discipline aligned with plan requirements.
- Gives a structured signal for future regressions and release gates.

Tradeoffs:

- Requires minimum episode count before hard enforcement is meaningful.
- Early environments may run in warmup mode until enough data accrues.
