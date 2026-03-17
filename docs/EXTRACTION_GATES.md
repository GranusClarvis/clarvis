# Extraction Gates — clarvis-db & clarvis-p

_When are these packages truly ready to live in their own repos?_
_Status: v1.0 — 2026-03-16. Review quarterly or when a gate turns green._

## Philosophy

Extraction is expensive (split repos, CI, versioning, release process, cross-repo bugs).
The cost is only justified when **real demand** exists. These gates prevent premature extraction
driven by architectural enthusiasm rather than actual need.

---

## Gate Definitions

### Gate 1: Consumer Demand (HARD — must pass)

| Criterion | clarvis-db | clarvis-p |
|-----------|-----------|-----------|
| **2+ independent consumers** exist or are committed (30-day horizon) | NO — only `clarvis` main repo imports `clarvis.brain` | NO — only `clarvis` main repo imports `clarvis.context.assembly` |
| At least 1 consumer is **not controlled by us** (external project, community user, or distinct team) | NO | NO |

**How to verify:** `grep -r "from clarvis.brain import\|from clarvis_db import" --include="*.py"` across all known consumer repos. Count distinct repo roots.

**Why this gate:** A package with one consumer is just indirection. Two consumers prove the API is general enough to be worth the maintenance burden.

---

### Gate 2: API Stability (HARD — must pass)

| Criterion | clarvis-db | clarvis-p |
|-----------|-----------|-----------|
| Public surface documented in boundary doc | YES — `docs/CLARVISDB_API_BOUNDARY.md` | YES — `docs/CLARVISP_API_BOUNDARY.md` |
| No breaking changes to public surface in last 30 days | CHECK — audit git log | CHECK — audit git log |
| All public symbols have type hints | CHECK | CHECK |
| No `# TODO` or `# HACK` in public surface functions | CHECK | CHECK |
| Version follows semver, currently >= 1.0.0 | YES (clarvis-db 1.0.0) | NO (no package exists) |

**How to verify:** `scripts/extraction_gate_check.py --gate api-stability`

**Why this gate:** Extracting an unstable API means constant cross-repo breakage. Wait until the API has been stable for a month.

---

### Gate 3: Test Coverage (HARD — must pass)

| Criterion | clarvis-db | clarvis-p |
|-----------|-----------|-----------|
| Smoke tests for all public surface functions exist and pass | PARTIAL — `packages/clarvis-db/tests/` exists | NO — no dedicated test suite |
| Contract parity tests (boundary doc symbols vs actual exports) match | YES — `test_fork_merge_smoke.py §9` | YES — `test_fork_merge_smoke.py §9` |
| Host compatibility contract check passes | YES — `test_fork_merge_smoke.py §4` | YES — via assembly ops check |
| Round-trip integration test (store → recall → verify) | CHECK — needs explicit extraction-context test | N/A |
| No test uses `# noqa`, `pytest.skip`, or `@pytest.mark.skip` on public surface tests | CHECK | CHECK |

**How to verify:** `scripts/extraction_gate_check.py --gate tests`

**Why this gate:** If we can't prove the extracted package works in isolation, extraction will break things silently.

---

### Gate 4: Documentation Honesty (SOFT — should pass)

| Criterion | clarvis-db | clarvis-p |
|-----------|-----------|-----------|
| README exists with install + quickstart + API reference | YES — `packages/clarvis-db/README.md` | NO |
| README does not claim features that don't exist (MCP server, REST adapter) | CHECK — boundary doc mentions "planned" adapters | N/A |
| No "coming soon" or "planned" items in public-facing docs | CHECK | N/A |
| CHANGELOG exists or commit history is clean enough to generate one | CHECK | N/A |

**How to verify:** Manual review + `scripts/extraction_gate_check.py --gate docs`

**Why this gate:** Publishing a package with aspirational docs erodes trust. Ship what exists.

---

### Gate 5: Low Bloat (SOFT — should pass)

| Criterion | clarvis-db | clarvis-p |
|-----------|-----------|-----------|
| Package has < 15 Python files (excluding tests) | YES — 6 files | N/A (0 files) |
| No internal-only modules exposed in public surface | CHECK — `clarvis_adapter.py` is internal | N/A |
| No dead code (functions defined but never called from public surface) | CHECK | N/A |
| Dependencies are minimal (< 5 runtime deps) | CHECK — chromadb, onnxruntime, numpy | N/A |
| Package installs cleanly in a fresh venv with `pip install .` | CHECK | N/A |

**How to verify:** `scripts/extraction_gate_check.py --gate bloat`

**Why this gate:** A bloated extracted package is worse than a monorepo module. Keep it lean.

---

## Gate Summary Dashboard

```
EXTRACTION READINESS — 2026-03-16

clarvis-db:
  [FAIL] Gate 1: Consumer Demand    — 1/2 consumers (need 2+)
  [PASS] Gate 2: API Stability      — boundary doc exists, v1.0.0
  [PART] Gate 3: Test Coverage      — tests exist, need extraction-isolation test
  [PART] Gate 4: Documentation      — README exists, audit for aspirational claims
  [PASS] Gate 5: Low Bloat          — 6 files, 3 deps

  VERDICT: NOT READY — blocked on Gate 1 (no second consumer)

clarvis-p:
  [FAIL] Gate 1: Consumer Demand    — 1/2 consumers (need 2+)
  [FAIL] Gate 2: API Stability      — no package exists yet
  [FAIL] Gate 3: Test Coverage      — no dedicated tests
  [FAIL] Gate 4: Documentation      — no README
  [N/A]  Gate 5: Low Bloat          — nothing to measure

  VERDICT: NOT READY — blocked on Gates 1-4 (package doesn't exist)
```

---

## Decision Rules

1. **All HARD gates must pass** before extraction begins.
2. **SOFT gates should pass** but can be fixed during extraction if the HARD gates are green.
3. **Gate 1 is the primary blocker.** Do not extract a package that has only one consumer.
4. **Re-evaluate quarterly** or when a new consumer appears.
5. **Anti-sprawl policy** (see `ANTI_PACKAGE_SPRAWL_GUARD`): if Gate 1 fails, the package stays as a module in the monorepo. The boundary doc serves as the extraction spec for when demand materializes.

---

## What To Do Instead of Extracting

While gates are red, keep the code in the monorepo and:
- Maintain the API boundary docs as the single source of truth for the stable surface.
- Keep the smoke tests green (`test_fork_merge_smoke.py`).
- Treat the boundary doc functions as a contract — don't break them without updating the doc.
- When a second consumer appears, run `scripts/extraction_gate_check.py` and proceed if green.

---

## Appendix: Gate Check Script

Machine-readable gate verification:

```bash
python3 scripts/extraction_gate_check.py           # Full report
python3 scripts/extraction_gate_check.py --gate consumer-demand  # Single gate
python3 scripts/extraction_gate_check.py --package clarvis-db    # Single package
python3 scripts/extraction_gate_check.py --json     # JSON output for CI
```
