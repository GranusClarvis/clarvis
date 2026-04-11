# Phase 2 Execution Report: cognition/ and metrics/ Thin Wrapper Migration

**Date**: 2026-04-09
**Executor**: Claude Code Opus (executive function)
**Plan reference**: `docs/SPINE_MIGRATION_PLAN.md` Phase 2

---

## Summary

Migrated all callers of 11 cognition/, metrics/, and infra/ thin wrapper files to use spine imports (`from clarvis.cognition...`, `from clarvis.metrics...`, `from clarvis.orch...`), updated 5 shell scripts that called wrappers directly, then deleted the 11 wrappers. One wrapper (`infra/cost_tracker.py`) was reclassified as a CLI entry point and retained.

## Phase 1 Verification

Before starting Phase 2, verified Phase 1 claims:
- Zero legacy `brain_mem/` wrapper imports remain (confirmed via `grep`)
- One match in `tests/clarvis/test_hooks.py:135` is a comment string, not an import
- `brain_mem/cognitive_workspace.py` and `brain_mem/lite_brain.py` still exist — Phase 0 scope, not Phase 1 leftovers

## What Changed

### Wrappers Deleted (11 files)

| File | LOC | Was |
|---|---|---|
| `scripts/cognition/attention.py` | 20 | Re-export of `clarvis.cognition.attention` |
| `scripts/cognition/clarvis_confidence.py` | 18 | Re-export of `clarvis.cognition.confidence` |
| `scripts/cognition/clarvis_reasoning.py` | 15 | Re-export of `clarvis.cognition.reasoning` |
| `scripts/cognition/reasoning_chains.py` | 66 | Re-export + CLI of `clarvis.cognition.reasoning_chains` |
| `scripts/cognition/thought_protocol.py` | 17 | Re-export of `clarvis.cognition.thought_protocol` |
| `scripts/cognition/cognitive_load.py` | 59 | Re-export + CLI of `clarvis.cognition.cognitive_load` |
| `scripts/metrics/phi_metric.py` | 117 | Re-export + CLI of `clarvis.metrics.phi` |
| `scripts/metrics/orchestration_scoreboard.py` | 50 | Re-export + CLI of `clarvis.orch.scoreboard` |
| `scripts/metrics/clr_benchmark.py` | 70 | Re-export + CLI of `clarvis.metrics.clr` |
| `scripts/metrics/self_model.py` | 161 | Re-export + CLI of `clarvis.metrics.self_model` |
| `scripts/infra/cost_api.py` | 54 | Re-export + CLI of `clarvis.orch.cost_api` |

### Wrapper NOT Deleted (1 file — reclassified)

| File | LOC | Reason |
|---|---|---|
| `scripts/infra/cost_tracker.py` | 200 | **CLI entry point, not a wrapper.** 200 LOC of own CLI logic (Telegram formatting, cost comparison, router analysis) that does NOT exist in the spine CLI. Referenced in gateway config (`openclaw.json`), `AGENTS.md`, operator workflows. Internal `cost_api` imports were updated to spine paths. |

### Python Callers Migrated (~25 import sites in 16 files)

| File | Old Import | New Import |
|---|---|---|
| `scripts/tools/context_compressor.py:874` | `from attention import attention` | `from clarvis.cognition.attention import attention` |
| `scripts/cognition/theory_of_mind.py:805` | `from attention import attention` | `from clarvis.cognition.attention import attention` |
| `scripts/tools/prompt_builder.py:210` | `from attention import AttentionSpotlight` | `from clarvis.cognition.attention import AttentionSpotlight` |
| `scripts/metrics/self_representation.py:769` | `from attention import attention` | `from clarvis.cognition.attention import attention` |
| `scripts/metrics/performance_benchmark.py:905,539` | `from attention/phi_metric import ...` | `from clarvis.cognition.attention/clarvis.metrics.phi import ...` |
| `scripts/pipeline/evolution_preflight.py:26,37,42` | `from clarvis_confidence/phi_metric/self_model import ...` | `from clarvis.cognition.confidence/clarvis.metrics.phi/clarvis.metrics.self_model import ...` |
| `scripts/cognition/dream_engine.py:37` | `from reasoning_chains import ...` | `from clarvis.cognition.reasoning_chains import ...` |
| `scripts/cognition/reasoning_chain_hook.py:55` | `from thought_protocol import thought` | `from clarvis.cognition.thought_protocol import thought` (removed sys.path hack) |
| `scripts/pipeline/heartbeat_preflight.py:41` | `from cognitive_load import ...` | `from clarvis.cognition.cognitive_load import ...` |
| `scripts/hooks/goal_tracker.py:23` | `from self_model import ...` | `from clarvis.metrics.self_model import ...` |
| `scripts/pipeline/heartbeat_postflight.py:130` | `from self_model import ...` | `from clarvis.metrics.self_model import ...` |
| `scripts/metrics/self_report.py:108` | `from self_model import update_model` | `from clarvis.metrics.self_model import update_model` |
| `scripts/infra/budget_alert.py:28` | `from cost_api import fetch_usage` | `from clarvis.orch.cost_api import fetch_usage` |
| `scripts/agents/project_agent.py:199` | `from cost_api import fetch_usage` | `from clarvis.orch.cost_api import fetch_usage` (removed sys.path hack) |
| `scripts/infra/cost_tracker.py:137,143,149,166` | `from cost_api import ...` | `from clarvis.orch.cost_api import ...` |
| `tests/test_critical_paths.py:36,130` | `from attention import AttentionItem` | `from clarvis.cognition.attention import AttentionItem` |
| `tests/scripts/test_preflight_defer.py:273,289,297` | `from cognitive_load import ...` | `from clarvis.cognition.cognitive_load import ...` |
| `clarvis/cognition/workspace_broadcast.py:152,371` | `from attention import attention` | `from clarvis.cognition.attention import attention` |
| `scripts/agents/agent_orchestrator.py:625` | string template: `from attention import` | `from clarvis.cognition.attention import` |

### Shell Scripts Updated (5 files)

| File | Old Reference | New Reference |
|---|---|---|
| `scripts/cron/cron_watchdog.sh:157,158` | `python3 scripts/cognition/attention.py add` | `python3 -m clarvis.cognition.attention add` |
| `scripts/cron/cron_evening.sh:19` | `python3 scripts/metrics/phi_metric.py act` | `python3 -m clarvis.metrics.phi act` |
| `scripts/cron/cron_evening.sh:31` | `python3 scripts/metrics/self_model.py daily` | `python3 -m clarvis.metrics.self_model daily` |
| `scripts/cron/cron_orchestrator.sh:126` | `python3 scripts/metrics/orchestration_scoreboard.py record` | `python3 -m clarvis.orch.scoreboard record` |
| `scripts/cron/cron_autonomous.sh:237-238` | `sys.path.insert(...cognition); from cognitive_load import` | `from clarvis.cognition.cognitive_load import` |

### Modules with Zero Callers (deleted without migration)

- `clarvis_reasoning.py` — 0 Python callers, 0 shell refs
- `orchestration_scoreboard.py` — 0 Python callers (shell ref updated)
- `clr_benchmark.py` — 0 Python callers (cron already used spine CLI)
- `cost_api.py` — 0 remaining Python callers after migration

## Verification

| Check | Result |
|---|---|
| `grep -r "from attention import" *.py` | 0 matches |
| `grep -r "from clarvis_confidence import" *.py` | 0 matches |
| `grep -r "from clarvis_reasoning import" *.py` | 0 matches |
| `grep -r "from reasoning_chains import" *.py` | 0 matches |
| `grep -r "from thought_protocol import" *.py` | 0 matches |
| `grep -r "from cognitive_load import" *.py` | 0 matches |
| `grep -r "from phi_metric import" *.py` | 0 matches |
| `grep -r "from orchestration_scoreboard import" *.py` | 0 matches |
| `grep -r "from clr_benchmark import" *.py` | 0 matches |
| `grep -r "from self_model import" *.py` | 0 matches |
| `grep -r "from cost_api import" *.py` | 0 matches |
| `import bare_name` patterns for all 11 | 0 matches |
| Spine import smoke test (all 11 modules) | All import OK |
| Compile check (14 migrated Python files) | All 14 compile OK |
| `pytest tests/test_cost_tracker.py test_cost_optimizer.py test_metacognition.py` | 90 passed |
| `pytest tests/test_critical_paths.py tests/scripts/test_preflight_defer.py` | 70 passed |
| Brain smoke test (`brain.stats()`) | 2898 memories, healthy |
| Shell script syntax check (4 cron scripts) | All pass `bash -n` |
| Spine module CLI smoke test (attention, phi, self_model, scoreboard) | All functional |

## What Remains

### scripts/cognition/ surviving files (NOT wrappers)

| File | Role | Phase |
|---|---|---|
| `dream_engine.py` | Cron entry point | STAYS |
| `theory_of_mind.py` | Library (2 callers) | Future phase |
| `causal_model.py` | Cron entry point | STAYS |
| `knowledge_synthesis.py` | Cron entry point | STAYS |
| `clarvis_reflection.py` | Cron entry point | STAYS |
| `world_models.py` | Library (2 callers) | Future phase |
| `prediction_review.py` | Library (1 caller) | Future phase |
| `reasoning_chain_hook.py` | Library (2 callers) | Future phase |
| `prediction_resolver.py` | Cron entry point | STAYS |
| `absolute_zero.py` | Cron entry point | STAYS |

### scripts/metrics/ surviving files (NOT wrappers)

| File | Role | Phase |
|---|---|---|
| `dashboard.py` | Cron entry point | STAYS |
| `performance_benchmark.py` | Cron entry point | STAYS |
| `brief_benchmark.py` | Cron entry point | STAYS |
| `daily_brain_eval.py` | Cron entry point | STAYS |
| `llm_brain_review.py` | Cron entry point | STAYS |
| `self_report.py` | Cron entry point | STAYS |
| `orchestration_benchmark.py` | Cron entry point | STAYS |
| `brain_effectiveness.py` | Cron entry point | STAYS |
| `self_representation.py` | Library (1 caller) | Future phase |
| `dashboard_events.py` | Library | STAYS |
| `performance_gate.py` | Library (1 caller) | Future phase |

### scripts/infra/ surviving files

| File | Role | Phase |
|---|---|---|
| `cost_tracker.py` | CLI entry point (operator tool, Telegram integration) | STAYS (reclassified) |
| `budget_alert.py` | Cron/CLI entry point | STAYS |
| `cost_checkpoint.py` | Cron entry point | STAYS |
| `generate_status_json.py` | Cron entry point | STAYS |
| `data_lifecycle.py` | Cron entry point | STAYS |

## Risks Mitigated

1. **No logic changes** — only import paths updated. All imports inside try/except blocks provide fallback safety.
2. **Shell scripts use spine `__main__` blocks** — verified each spine module CLI accepts the same subcommands as the deleted wrappers.
3. **Cron entry points untouched** — only wrapper stubs deleted.
4. **cost_tracker.py preserved** — its 200 LOC of CLI logic is NOT in the spine; deleting it would break `/costs` Telegram command and operator workflows.

## Metrics

- Files deleted: 11 (647 LOC of bridge/stub code)
- Files modified: 16 Python files + 5 shell scripts = 21
- Import sites migrated: ~25
- Legacy import count for these 11 modules: 0 (was ~25)
- sys.path hacks removed: 2 (reasoning_chain_hook.py, project_agent.py)
- Test suite: 160/160 passing (90 core + 70 critical paths/defer)
