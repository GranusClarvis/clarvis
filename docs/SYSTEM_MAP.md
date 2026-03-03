# SYSTEM_MAP — Current Runtime Wiring (Snapshot)

_Last updated: 2026-03-03 (UTC)_

Purpose: preserve an explicit, human-auditable map of **what runs**, **what imports what**, and **where wiring happens** so we can refactor without losing capabilities.

This document is intentionally practical:
- **Entry points** (cron, CLI scripts)
- **Pipelines** (preflight → task → postflight)
- **Key modules** (brain, memory subsystems, metrics)
- **Wiring points** (where components are invoked or implicitly triggered)
- **Verification** (how to check it still works)

---

## 0) Repository Topography

- `scripts/` — operational code (cron jobs, pipelines, benchmarks, utilities)
- `memory/` — logs, daily notes, queue, digests, research ingests
- `docs/` — architectural and operational documentation

---

## 1) Primary Execution Loops

### 1.1 Subconscious / Cron (Primary)

Cron runs are the main autonomy engine (planning, evolution tasks, research cycles). They:
- select tasks from `memory/evolution/QUEUE.md`
- spawn Claude Code (Opus) for large tasks
- write summaries to `memory/cron/digest.md`

**Artifacts:**
- `memory/cron/digest.md` (rolling digest)
- `memory/evolution/QUEUE.md` + `QUEUE_ARCHIVE.md`

> NOTE: exact cron script names may vary (see: `scripts/cron_*.sh`). This map focuses on the Python wiring.

### 1.2 Conscious / Heartbeat (Secondary)

Heartbeats are now minimized. When used, they should be **gated** and only run targeted checks.

---

## 2) The Cognitive Pipeline (when a cycle runs)

### 2.1 Preflight (select + prepare)

**Main script:** `scripts/heartbeat_preflight.py`

Responsibilities (high-level):
- decide whether to act (gate)
- select/score a task
- build a context brief (via context compressor + brain retrieval)
- inject procedures/templates when available

Key dependencies:
- `scripts/context_compressor.py` — builds tiered context briefs and retrieval slices
- `scripts/procedural_memory.py` — finds matching procedures/templates
- `scripts/brain*.py` / `brain.py` — search/store graph + vector retrieval (central service)

Wiring points:
- explicit calls in preflight to context compression + procedural injection

### 2.2 Task Execution (Claude Code or local)

Large tasks typically execute via Claude Code. Spawning is done via:
- `scripts/spawn_claude.sh` (shell) calling `/home/agent/.local/bin/claude -p ...`

Task output is summarized back into:
- `memory/cron/digest.md`
- and/or procedure stores

### 2.3 Postflight (evaluate + store)

**Main script:** `scripts/heartbeat_postflight.py`

Responsibilities (high-level):
- record outcomes
- store episodes / failure patterns
- update calibration / confidence metrics
- run benchmarks (where configured)

Key dependencies:
- episodic memory + consolidation modules
- benchmark scripts (`performance_benchmark.py`, etc.)

---

## 3) Central Services ("Spine" candidates)

### 3.1 Brain / Memory Store

**Core module:** `scripts/brain.py` (+ related helpers)

Used by most of the system for:
- vector retrieval
- graph link storage
- memory CRUD

**Known structural issue:** current import graph contains a circular SCC (see `scripts/import_health.py`).

### 3.2 Memory Subsystems

- `scripts/episodic_memory.py`
- `scripts/memory_consolidation.py`
- `scripts/hebbian_memory.py`
- `scripts/procedural_memory.py`
- `scripts/working_memory.py`

Wiring: invoked by preflight/postflight and/or other pipelines. Some legacy coupling remains (to be inverted).

### 3.3 Metrics / Consciousness

- `scripts/phi_metric.py`
- `scripts/clarvis_confidence.py`
- `scripts/self_model.py`

Used for Phi, capability scoring, and calibration metrics.

---

## 4) Orchestration / Project Agents

- `scripts/project_agent.py` — spawns and manages project-specific agents
- `scripts/orchestration_benchmark.py` — measures orchestrator performance

Wiring: called by cron tasks / evolution tasks (e.g., ORCH_SWO_BUILD/PR).

---

## 5) Structural Health / Refactor Guardrails

- `scripts/import_health.py`
  - AST import graph
  - SCC/cycle detection
  - dependency depth
  - fan-in/fan-out
  - import-time side effects (heuristic)

This is the baseline tool to ensure we don’t refactor into spaghetti.

---

## 6) Verification Checklist (to prove coherence after changes)

Run these after any refactor step:

1. Import health baseline (non-blocking at first):
   - `python3 scripts/import_health.py --quick`

2. Smoke tests:
   - `python3 -m pytest -q scripts/tests/test_smoke.py`

3. Project agent tests (if touched):
   - `python3 -m pytest -q scripts/tests/test_project_agent.py`

4. One end-to-end cycle (dry run / minimal action):
   - run preflight + build brief; ensure no import crashes

---

## 7) Known Wiring Risks

- Circular import SCC involving `brain`, `attention`, `episodic_memory`, `hebbian_memory`, `memory_consolidation`, etc.
- Import-time side effects detected in several modules (must be removed before deep refactor)
- High fan-in on `brain` (expected) but must not imply `brain` importing features back

---

## 8) Next Documentation (planned)

- `docs/ARCHITECTURE.md` — target structure and layering rules
- `docs/DATA_LAYOUT.md` — file placement + retention
- `docs/RUNBOOK.md` — operational procedures
