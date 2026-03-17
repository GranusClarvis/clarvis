# Fork Integration Plan — 2026-03-15

**Source:** `InverseAltruism/Clarvis_Fork` (commit `db50e45`)
**Target:** `GranusClarvis/clarvis` (main, commit `799575d`)
**Author:** Clarvis executive function (Claude Code Opus)

## Executive Summary

The fork is a **high-quality architectural stabilization snapshot** that adds:
- Runtime mode control-plane (GE / Architecture / Passive)
- CLR benchmark (6-dimension agent intelligence score, schema v1.0 frozen)
- Trajectory evaluation harness (agentevals-style 5-dimension scoring)
- Host adapter pattern (OpenClaw / Hermes / NanoClaw references)
- Compatibility contracts (executable host checks)
- clarvis-p bridge package (context/prompt extraction scaffold)
- Unified CLI `clarvis mode` subcommand
- ADR documentation (2 records), API boundary docs, website v0 scaffold
- 15+ new test files

**Key conflict:** The fork reverts 2026-03-15 assembly.py tuning (DyCP constants, section suppression). Current repo has better-calibrated values based on 14-day data.

**Overall verdict:** ~80% of the fork is merge-worthy. The remaining 20% is either premature (website v0), needs adaptation (assembly.py), or is vanity packaging (clarvis-p as separate package).

---

## Category 1: MERGE NOW (low risk, high value)

These can be cherry-picked or applied directly with minimal adaptation.

### 1.1 Runtime Mode Control-Plane
- **Files:** `clarvis/runtime/__init__.py`, `clarvis/runtime/mode.py`, `clarvis/cli_mode.py`
- **Why merge:** The mode system (GE/Architecture/Passive) is well-designed, production-ready, and addresses a real operational need — controlling autonomous behavior without code changes. Clean state machine, deferred switching, history tracking.
- **Tests:** `tests/test_runtime_mode.py`, `tests/test_queue_writer_mode_gate.py`
- **Risk:** LOW — no conflicts with existing code; additive only.
- **Integration steps:**
  1. Copy `clarvis/runtime/` directory (2 files)
  2. Copy `clarvis/cli_mode.py`
  3. Register in `clarvis/cli.py` (add mode subcommand)
  4. Copy tests
  5. Wire into `queue_writer.py` (optional, can defer)
  6. Create `data/runtime_mode.json` with `{"mode": "ge"}` default

### 1.2 CLR Benchmark (Clarvis Rating)
- **Files:** `clarvis/metrics/clr.py`
- **Why merge:** 672 lines of production-quality benchmark code. 6-dimension composite score with gates, history, stability evaluation. Fills a real gap — PI measures operational health, CLR measures intelligence value-add over bare Claude Code.
- **Tests:** `tests/test_clr_benchmark_gates.py`, `tests/test_clr_stability_gate.py`, `tests/test_clr_schema_freeze.py`
- **Risk:** LOW — new file, no conflicts. Schema is frozen v1.0 (good discipline).
- **Integration steps:**
  1. Copy `clarvis/metrics/clr.py`
  2. Register in `clarvis/cli_bench.py` (add `clr` subcommand)
  3. Copy tests
  4. Add to `cron_pi_refresh.sh` or new CLR cron slot

### 1.3 Trajectory Evaluation Harness
- **Files:** `clarvis/metrics/trajectory.py`
- **Why merge:** 270 lines, agentevals-style execution scoring. Complements CLR (which is aggregate) with per-episode quality tracking. 5 scoring dimensions with configurable gates.
- **Tests:** `tests/test_trajectory_eval.py`, `tests/test_performance_gate_trajectory.py`
- **Risk:** LOW — new file, no conflicts.
- **Integration steps:**
  1. Copy `clarvis/metrics/trajectory.py`
  2. Register in `clarvis/cli_bench.py` (add `trajectory-check` subcommand)
  3. Copy tests
  4. Wire into `heartbeat_postflight.py` (score each episode)
  5. Create `data/trajectory_eval/` directory

### 1.4 ADR Documentation
- **Files:** `docs/adr/ADR-0001-trajectory-eval-harness.md`, `docs/adr/ADR-0002-host-compat-contracts.md`
- **Why merge:** Professional architectural decision records. Low cost, high documentation value.
- **Risk:** NONE — documentation only.

### 1.5 API Boundary Documentation
- **Files:** `docs/CLARVISDB_API_BOUNDARY.md`, `docs/CLARVISP_API_BOUNDARY.md`
- **Why merge:** Clear extraction boundary specs. Even if we don't extract yet, these define what the stable APIs should look like.
- **Risk:** NONE — documentation only.

---

## Category 2: MERGE AFTER ADAPTATION (needs work)

### 2.1 Host Adapter Pattern
- **Files:** `clarvis/adapters/base.py`, `clarvis/adapters/openclaw.py`, `clarvis/adapters/hermes.py`, `clarvis/adapters/nanoclaw.py`, `clarvis/adapters/__init__.py`
- **Why adapt:** The pattern is sound (abstract base, factory function, bridge-aware imports). But Hermes and NanoClaw adapters are **reference implementations with no actual host to talk to**. Merging them now creates dead code.
- **What to adapt:**
  - Merge `base.py` and `openclaw.py` only (these are actionable)
  - Move `hermes.py` and `nanoclaw.py` to `docs/examples/` as reference code
  - Simplify factory to only register `openclaw` (add others when hosts exist)
- **Tests:** Adapt `tests/test_host_adapters.py` to only test OpenClaw
- **Risk:** LOW after adaptation.

### 2.2 Compatibility Contracts
- **Files:** `clarvis/compat/contracts.py`, `clarvis/compat/__init__.py`
- **Why adapt:** The contract verification pattern is valuable, but checking Hermes/NanoClaw contracts will always fail (those hosts don't exist). Should only verify OpenClaw.
- **What to adapt:**
  - Keep `HostContract` dataclass and `run_contract_checks()`
  - Reduce CONTRACTS to OpenClaw only
  - Add Hermes/NanoClaw as commented templates
- **Tests:** Adapt `tests/test_host_compat_contracts.py`
- **Risk:** LOW after adaptation.

### 2.3 Assembly.py — REJECT FORK VERSION, KEEP CURRENT
- **File:** `clarvis/context/assembly.py`
- **Why reject fork version:** The fork reverts calibrated tuning from 2026-03-15:
  - `DYCP_HISTORICAL_FLOOR: 0.16 → 0.13` (undoes 14-day calibration)
  - `DYCP_ZERO_OVERLAP_CEILING: 0.20 → 0.16` (undoes noise reduction)
  - Removes `should_suppress_section()` (removes smart pre-assembly gating)
  - Removes `DYCP_DEFAULT_SUPPRESS` frozenset (removes evidence-based suppression)
  - Removes `DYCP_DEFAULT_SUPPRESS_CONTAINMENT_OVERRIDE` (removes override logic)
- **Current version is superior** because it has tighter, data-driven pruning that reduces token waste.
- **What to preserve from fork:** The fork's approach of delegating suppression to `context_relevance.get_suppressed_sections()` is interesting but is already covered by the current relevance-adjusted budget system.
- **Risk of merging fork version:** Context quality regression, higher token usage.

### 2.4 CLI Mode Registration
- **File:** `clarvis/cli.py`
- **Why adapt:** The fork adds `clarvis.cli_mode` registration. This is correct but needs to match whatever we land in 2.1/2.2.
- **What to adapt:** Add mode subcommand registration only (1 line change).
- **Risk:** NONE.

---

## Category 3: DO NOT MERGE (premature or vanity)

### 3.1 clarvis-p Bridge Package
- **Files:** `packages/clarvis-p/` (entire package)
- **Why reject:** This is a bridge package for "extracting" the context/prompt layer into a standalone pip package. But:
  1. **No external consumer exists.** Clarvis is the only user.
  2. **The "bridge" just re-exports** from `clarvis.context.*` — adds indirection with zero benefit.
  3. **Package sprawl.** We already have 3 packages. Adding a 4th that wraps internal modules is vanity packaging.
  4. **When to reconsider:** If/when a second agent host genuinely needs context assembly as a dependency, extract then — not now.
- **Alternative:** Keep `docs/CLARVISP_API_BOUNDARY.md` as the extraction spec. When extraction is justified, build the package from the boundary doc.

### 3.2 Website v0 Deployment
- **Files:** `deploy/nginx/clarvis-v0.conf`, `docs/WEBSITE_V0_INFORMATION_ARCH.md`, `docs/WEBSITE_V0_RELEASE_RUNBOOK.md`
- **Why reject:** No dashboard server exists at port 18800 to proxy to. The nginx config points at a non-existent backend. The information architecture doc is aspirational but not actionable without the server.
- **When to reconsider:** When `dashboard_server.py` is production-ready and serving on 18800.

### 3.3 Hermes/NanoClaw Adapter Implementations
- **Files:** `clarvis/adapters/hermes.py`, `clarvis/adapters/nanoclaw.py`
- **Why reject as production code:** These hosts don't exist yet. Dead code.
- **Disposition:** Move to `docs/examples/` as reference patterns (see 2.1).

### 3.4 Host Adapter Bridge Import Tests
- **Files:** `tests/test_host_adapters_bridge_import.py`, `tests/test_host_adapters_bridge_runtime.py`
- **Why reject:** These test the `clarvis_db` / `clarvis_p` bridge import fallback chains. Since we're not merging clarvis-p, these tests verify dead paths.

### 3.5 Extraction Contract Parity Test
- **Files:** `tests/test_extraction_contract_parity.py`
- **Why reject:** Tests that clarvis-p re-exports match clarvis.context.assembly exports. Meaningless without clarvis-p.

---

## Implementation Sequencing

### Stage 1: New Metrics (Day 1) — LOW RISK
1. Add `clarvis/metrics/clr.py` ← CLR benchmark
2. Add `clarvis/metrics/trajectory.py` ← Trajectory eval
3. Add corresponding tests (5 files)
4. Register in `cli_bench.py`
5. Run full test suite → green

### Stage 2: Runtime Mode (Day 1-2) — LOW RISK
1. Add `clarvis/runtime/` directory (mode control-plane)
2. Add `clarvis/cli_mode.py`
3. Register mode in `clarvis/cli.py`
4. Add tests (2 files)
5. Create `data/runtime_mode.json` default
6. Run full test suite → green
7. **Smoke test:** `python3 -m clarvis mode show` → should show GE

### Stage 3: Adapter Foundation (Day 2-3) — MEDIUM RISK
1. Add `clarvis/adapters/` with base.py + openclaw.py only
2. Add `clarvis/compat/` with OpenClaw-only contracts
3. Add adapted tests
4. Run full test suite → green
5. **Smoke test:** Contract check passes for OpenClaw

### Stage 4: Documentation (Day 3) — NO RISK
1. Copy ADR docs → `docs/adr/`
2. Copy API boundary docs
3. Copy HOST_ADAPTER_REFERENCE.md (edit to reflect OpenClaw-only)

### Stage 5: Wire Into Cron (Day 3-4) — MEDIUM RISK
1. Wire CLR into periodic benchmark (cron slot or existing PI refresh)
2. Wire trajectory scoring into heartbeat_postflight.py
3. Wire mode checking into queue_writer.py and heartbeat_gate.py
4. Test each integration point

---

## Risk Matrix

| Component | Merge Risk | Regression Risk | Value |
|-----------|-----------|----------------|-------|
| CLR benchmark | LOW | NONE | HIGH |
| Trajectory eval | LOW | NONE | HIGH |
| Runtime mode | LOW | LOW | HIGH |
| ADR docs | NONE | NONE | MEDIUM |
| API boundary docs | NONE | NONE | MEDIUM |
| Adapters (OpenClaw only) | LOW | LOW | MEDIUM |
| Compat contracts | LOW | LOW | MEDIUM |
| assembly.py (fork ver.) | **HIGH** | **HIGH** | NEGATIVE |
| clarvis-p package | LOW | LOW | NEGATIVE (sprawl) |
| Website v0 | LOW | LOW | PREMATURE |

---

## Anti-Sprawl Guard

Before merging any new package or module, verify:
1. **At least 2 consumers exist** (or will exist within 30 days)
2. **The module has real tests** that test behavior, not just imports
3. **The module doesn't just re-export** from another module
4. **Dead adapters/hosts go to docs/examples/**, not production code

---

## Concrete Task Queue (for QUEUE.md)

```
- [ ] [FORK_MERGE_CLR 2026-03-15] Merge CLR benchmark from fork: copy clarvis/metrics/clr.py + 3 test files + register in cli_bench.py
- [ ] [FORK_MERGE_TRAJECTORY 2026-03-15] Merge trajectory eval from fork: copy clarvis/metrics/trajectory.py + 2 test files + register in cli_bench.py
- [ ] [FORK_MERGE_MODE 2026-03-15] Merge runtime mode control-plane from fork: copy clarvis/runtime/ + cli_mode.py + register in cli.py + 2 test files + create data/runtime_mode.json
- [ ] [FORK_MERGE_ADAPTERS 2026-03-15] Merge OpenClaw adapter + compat contracts from fork (adapted: OpenClaw only, no Hermes/NanoClaw)
- [ ] [FORK_MERGE_DOCS 2026-03-15] Merge ADR + API boundary docs from fork
- [ ] [FORK_WIRE_CLR_CRON 2026-03-15] Wire CLR benchmark into cron_pi_refresh.sh or dedicated CLR cron slot
- [ ] [FORK_WIRE_TRAJECTORY_POSTFLIGHT 2026-03-15] Wire trajectory scoring into heartbeat_postflight.py
- [ ] [FORK_WIRE_MODE_QUEUE 2026-03-15] Wire mode gating into queue_writer.py and heartbeat_gate.py
```

---

## Files NOT to Touch

- `clarvis/context/assembly.py` — current version is superior (2026-03-15 calibration)
- `packages/clarvis-p/` — do not create; document the boundary instead
- `deploy/` — premature; no backend exists
- Any file that would add Hermes/NanoClaw as production code
