# ~~Spine & Scripts Architecture Audit~~ — SUPERSEDED

> **SUPERSEDED (2026-04-10):** This audit was a pre-migration snapshot from 2026-03-23. The 10-phase spine migration is now complete. For the current architecture, see `docs/ARCHITECTURE.md` and `docs/SPINE_MIGRATION_COMPLETE.md`. Retained for historical reference only.

> **ERRATA (2026-04-03):** Some classifications in this audit were corrected in `docs/SPINE_CLEANUP_PLAN.md` — 8 scripts initially classified as dead/unused are actually production-wired via heartbeat, and 4 confirmed-dead scripts have since been deleted. See the cleanup plan for authoritative status.

**Date:** 2026-03-23
**Auditor:** Claude Code Opus (executive function)
**Scope:** clarvis/, scripts/, docs/, website/, skills/, packages/, data/, cron wiring
**Method:** Static analysis of imports, crontab cross-reference, call-site tracing, recent commit history
**Safety:** Read-only audit. No code was modified or deleted.

---

> **⚠ ERRATA (2026-03-23):** This audit's deletion recommendations in §3.1 and §3.2 are
> **dangerously incorrect**. All 8 "thin wrappers with zero callers" have active legacy callers
> (many in the heartbeat pipeline). 8 of 13 "research prototypes" are imported by production scripts.
> Following §3.1/§3.2 blindly would break heartbeat, cron reflection, watchdog, and autonomous execution.
> **See `docs/SPINE_CLEANUP_PLAN.md` for the verified second-pass analysis and safe phased cleanup plan.**
> The structural classification (subsystem map, core/live ratings) is largely correct — the errors
> are in caller analysis (missed `import` statements in intermediate scripts like heartbeat_preflight.py).

---

## Executive Summary

Clarvis has **77 spine modules** (clarvis/) and **139 scripts** (scripts/). The spine is well-structured with clean module boundaries. However, scripts/ contains significant bloat: **~8,600 lines of genuinely dead code** (no callers, no cron, no CLI), **8 pure re-export wrappers** that serve no purpose since the spine migration, and **~10 research/cognitive-modeling scripts** that were never wired into production.

The heartbeat pipeline (`heartbeat_preflight.py` + `heartbeat_postflight.py`, 3,338 lines) is the real runtime workhorse — it's where brain, attention, memory, and metrics converge. The `context_compressor.py` (1,499 lines) in scripts/ is a **superset** of `clarvis/context/compressor.py` (386 lines) — the script has unique functions not yet migrated to spine.

**Key findings:**
1. **Core live systems** (brain, heartbeat, context, cron orchestrators, metrics, website) are solid and well-wired
2. **10+ cognitive-modeling scripts** (theory_of_mind, soar_engine, hyperon, etc.) are research prototypes with zero production callers
3. **8 thin wrappers** in scripts/ can be safely deleted — nothing imports them
4. **context_compressor.py** needs spine migration — it's the de facto context engine, not the spine version
5. **87 scripts still use legacy sys.path imports** (vs 38 using spine)
6. **20 skills** are all active and properly wired
7. **52 docs** include ~15 dated audit/plan files that could be archived

**Recommended cleanup would retire ~12,000 lines** without losing any production functionality.

---

## 1. Subsystem Map

```
┌─────────────────────────────────────────────────────────────────┐
│                        CRON SCHEDULE (52 entries)               │
│  cron_autonomous(12x) morning research evolution sprint         │
│  strategic_audit evening reflection reports monitors            │
│  maintenance(backup/graph/vacuum) weekly(hygiene/bench/cleanup) │
└───────────────────────────┬─────────────────────────────────────┘
                            │ spawns
┌───────────────────────────▼─────────────────────────────────────┐
│                    ORCHESTRATOR SHELLS (.sh)                     │
│  cron_env.sh → lock_helper.sh → spawn_claude.sh                │
│  prompt_builder.py → heartbeat_gate.py → Claude Code           │
└───────────────────────────┬─────────────────────────────────────┘
                            │ executes
┌───────────────────────────▼─────────────────────────────────────┐
│                    HEARTBEAT PIPELINE                            │
│  heartbeat_preflight.py (1347L) → Claude Code → postflight.py  │
│  (attention, task selection, context, brain search, episodes)   │
└───────────────────────────┬─────────────────────────────────────┘
                            │ imports
┌───────────────────────────▼─────────────────────────────────────┐
│                    CLARVIS SPINE (77 modules)                    │
│  brain/    memory/    context/   cognition/   metrics/          │
│  heartbeat/ orch/    runtime/   adapters/     compat/           │
└─────────────────────────────────────────────────────────────────┘
                            │ serves
┌───────────────────────────▼─────────────────────────────────────┐
│              WEBSITE (port 18801) + PUBLIC API                   │
│  /api/public/status → reads CLR, PI, queue metrics              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Subsystem Classification

### 2.1 Brain & Memory (Core)

| Module | Location | Classification | Evidence |
|--------|----------|----------------|----------|
| ClarvisBrain (ChromaDB) | clarvis/brain/ (13 files, ~5000L) | **Core live** | Singleton used by ALL other modules. 10 collections, 3400+ memories. Import count: 30+ scripts |
| brain.py (scripts/) | scripts/brain.py (306L) | **Thin wrapper** | Re-exports clarvis.brain. Used by 10+ legacy scripts via sys.path |
| GraphRAG | clarvis/brain/graphrag.py (586L) | **Core live** | Community detection + global search. Registered as brain hook |
| Graph dual-backend | clarvis/brain/graph.py + graph_store_sqlite.py | **Core live** | JSON default + SQLite (CLARVIS_GRAPH_BACKEND). Soak-tested daily |
| Retrieval gate/eval/feedback | clarvis/brain/retrieval_*.py (3 files) | **Core live** | Pre-query filtering + post-query confidence. Wired in brain recall() |
| Memory evolution | clarvis/brain/memory_evolution.py (217L) | **Core live** | Contradiction detection in remember(). Called on every store |
| Episodic memory | clarvis/memory/episodic_memory.py (1150L) | **Core live** | ACT-R episodes. Used by heartbeat, context assembly |
| Procedural memory | clarvis/memory/procedural_memory.py (1400L) | **Core live** | 7-stage skill library. Used by heartbeat, context assembly, tool_maker |
| Hebbian memory | clarvis/memory/hebbian_memory.py (1000L) | **Core live** | Co-activation hooks registered in brain. Used by consolidation |
| Working memory | clarvis/memory/working_memory.py (120L) | **Partially wired** | Baddeley buffer. Referenced by context but lightweight use |
| Memory consolidation | clarvis/memory/memory_consolidation.py (2500L) | **Core live** | Dedup + prune + archive. Called by brain_hygiene.py (weekly cron) |
| lite_brain.py | scripts/lite_brain.py (578L) | **Core live** | Isolated brain for project agents. Used by project_agent.py |

**Deletion risk:** NONE of the brain/memory modules are safe to remove. The thin wrapper `scripts/brain.py` is still imported by 10+ legacy scripts — removing it requires migrating those imports first.

**Recommendation:**
- brain.py wrapper: **keep until legacy imports migrated**, then archive
- All spine brain/: **keep as-is**
- lite_brain.py: **keep as-is**

---

### 2.2 Heartbeat Pipeline

| Module | Location | Classification | Evidence |
|--------|----------|----------------|----------|
| heartbeat_preflight.py | scripts/ (1347L) | **Core live** | Called by cron_autonomous.sh 12x/day. Batches 15+ operations |
| heartbeat_postflight.py | scripts/ (1991L) | **Core live** | Called after every Claude Code execution. Episode encoding, metrics |
| heartbeat_gate.py | scripts/ (359L) | **Core live** | Zero-LLM gate check. Called by cron_autonomous.sh |
| clarvis/heartbeat/ | clarvis/heartbeat/ (5 files, ~1000L) | **Partially wired** | Hook registry + gate module. gate.py duplicates heartbeat_gate.py logic |
| evolution_preflight.py | scripts/ (245L) | **Core live** | Called by cron_evolution.sh, cron_orchestrator.sh |
| session_hook.py | scripts/ (179L) | **Core live** | Called by cron_morning.sh, cron_evening.sh |
| daily_memory_log.py | scripts/ (208L) | **Core live** | Called by cron_autonomous.sh, cron_morning.sh |

**Key finding:** The scripts/ heartbeat files (preflight + postflight + gate) are the **real runtime**, not the spine heartbeat/ module. The spine heartbeat/ provides hook registry infrastructure but the actual execution logic lives in scripts/.

**Deletion risk:** HIGH — heartbeat_preflight.py and heartbeat_postflight.py are the system's core execution pipeline. Do not touch.

**Recommendation:**
- scripts/ heartbeat files: **keep as-is** (they ARE the runtime)
- clarvis/heartbeat/: **promote** — migrate gate logic from scripts/heartbeat_gate.py into spine; the hook registry is already clean
- Consolidate: scripts/heartbeat_gate.py should become a thin caller of clarvis.heartbeat.gate

---

### 2.3 Context & Retrieval

| Module | Location | Classification | Evidence |
|--------|----------|----------------|----------|
| context_compressor.py | scripts/ (1499L) | **Core live (superset of spine)** | Called by heartbeat_preflight.py. Has 24 functions including generate_tiered_brief, gc, archive_completed |
| clarvis/context/ | clarvis/context/ (6 files, ~3500L) | **Core live (subset)** | compressor.py (386L) only has tfidf/mmr/compress. assembly.py (2500L) has tiered brief etc. |
| cognitive_workspace.py | scripts/ (678L) | **Core live** | Baddeley hierarchical buffers. Called by heartbeat_preflight + postflight |
| knowledge_synthesis.py | scripts/ (250L) | **Partially wired** | Called in learning pipeline but unclear cron trigger |

**Key finding:** There's a **split-brain** situation between `scripts/context_compressor.py` and `clarvis/context/`. The scripts/ version is what actually runs in production (imported by heartbeat_preflight.py via sys.path). The spine version (`clarvis/context/assembly.py`) contains SOME of the same functions but the scripts/ version is authoritative. This is the **#1 consolidation priority**.

**Deletion risk:** CRITICAL — `scripts/context_compressor.py` is called on every heartbeat cycle. Removing it breaks the system.

**Recommendation:**
- context_compressor.py: **migrate into spine** — merge unique functions into clarvis/context/assembly.py
- clarvis/context/: **keep and expand** to absorb context_compressor
- cognitive_workspace.py: **promote into spine** (clarvis/context/workspace.py or clarvis/memory/workspace.py)

---

### 2.4 Cognition & Attention

| Module | Location | Classification | Evidence |
|--------|----------|----------------|----------|
| clarvis/cognition/attention.py | spine (1400L) | **Core live** | GWT spotlight. Imported by brain hooks, thought_protocol, context assembly |
| clarvis/cognition/confidence.py | spine (1200L) | **Core live** | Bayesian calibration. Used by heartbeat postflight |
| clarvis/cognition/context_relevance.py | spine (700L) | **Core live** | Section relevance scoring. Has cron entry (02:40 daily refresh) |
| clarvis/cognition/thought_protocol.py | spine (1200L) | **Good idea, partially wired** | ThoughtScript DSL. Large module but unclear runtime callers beyond CLI |
| clarvis/cognition/intrinsic_assessment.py | spine (420L) | **Core live** | Wired into heartbeat adapters |
| clarvis/cognition/reasoning.py | spine (21L) | **Stub** | Empty marker file |
| clarvis/cognition/somatic_markers.py | spine (16L) | **Stub** | Empty marker file (scripts/ version has 461L but no callers) |

**Recommendation:**
- attention, confidence, context_relevance, intrinsic_assessment: **keep as-is**
- thought_protocol: **keep** but audit actual usage — it's architecturally important even if under-called
- reasoning.py, somatic_markers.py (stubs): **keep** (zero-cost stubs, useful for future)

---

### 2.5 Metrics & Self-Awareness

| Module | Location | Classification | Evidence |
|--------|----------|----------------|----------|
| clarvis/metrics/phi.py | spine (500L) | **Core live** | IIT consciousness proxy. Called by CLI, benchmarks |
| clarvis/metrics/benchmark.py (PI) | spine (380L) | **Core live** | 8-dimension Performance Index. Weekly cron (Sun 06:00) |
| clarvis/metrics/clr.py | spine (1250L) | **Core live** | 7-dimension learning rate. Weekly cron (Sun 06:30). Feeds /api/public/status |
| clarvis/metrics/self_model.py | spine (1700L) | **Core live** | 7-domain capability assessment. Used by CLR, CLI |
| clarvis/metrics/quality.py | spine (700L) | **Core live** | Code + task quality scoring. Used by self_model |
| clarvis/metrics/code_validation.py | spine (280L) | **Core live** | Pre-LLM AST validation. Used by heartbeat |
| clarvis/metrics/memory_audit.py | spine (400L) | **Core live** | Memory quality audit. CLI accessible |
| clarvis/metrics/trajectory.py | spine (370L) | **Partially wired** | Task success tracking. Data exists but unclear active callers |
| performance_benchmark.py | scripts/ (1550L) | **Core live** | Full PI benchmark. Weekly cron. Contains unique logic beyond spine |
| clr_benchmark.py | scripts/ (68L) | **Core live** | Thin CLI for CLR benchmark. Weekly cron |
| brief_benchmark.py | scripts/ (370L) | **Core live** | Brief compression benchmark. Monthly cron |
| daily_brain_eval.py | scripts/ (533L) | **Core live** | Daily deterministic brain evaluation. Daily cron (06:00) |
| llm_brain_review.py | scripts/ (652L) | **Core live** | LLM-judged brain review. Daily cron (06:15) |

**Recommendation:** All core. Keep as-is. trajectory.py is low-risk to keep.

---

### 2.6 Orchestration & Task Routing

| Module | Location | Classification | Evidence |
|--------|----------|----------------|----------|
| clarvis/orch/router.py | spine (450L) | **Core live** | 14-dimension complexity scorer. Used by task_selector |
| clarvis/orch/task_selector.py | spine (800L) | **Core live** | Evolutionary task selection. Used by heartbeat_preflight |
| clarvis/orch/pr_intake.py | spine (700L) | **Partially wired** | PR rule extraction. PR factory experimental |
| clarvis/orch/pr_indexes.py | spine (600L) | **Partially wired** | PR rule indexing. Paired with pr_intake |
| clarvis/orch/pr_rules.py | spine (120L) | **Partially wired** | PR classification constants |
| clarvis/orch/cost_api.py | spine (150L) | **Core live** | OpenRouter cost wrapper |
| project_agent.py | scripts/ (3380L) | **Core live** | Multi-agent management. Cron orchestrator uses it |
| agent_orchestrator.py | scripts/ (763L) | **Core live** | Multi-agent coordination. Cron autonomous uses it |
| task_selector.py | scripts/ (98L) | **Thin wrapper** | Wraps clarvis.orch.task_selector. Called by heartbeat_preflight |
| task_router.py | scripts/ (84L) | **Partially wired** | Simple model router. Unclear if actively used |
| pr_factory.py | scripts/ (905L) | **Experimental** | Autonomous PR generation. No active cron caller |

**Recommendation:**
- router, task_selector, cost_api: **keep as-is**
- PR subsystem (intake/indexes/rules + pr_factory): **keep but mark experimental** — not production-critical yet
- project_agent.py: **keep as-is** (validates with star-world-order agent)
- scripts/task_selector.py: **archive** after migrating heartbeat_preflight to use spine directly

---

### 2.7 Cron Orchestrators

| Script | Classification | Evidence |
|--------|----------------|----------|
| cron_autonomous.sh (472L) | **Core live** | 12x/day main executor. THE heartbeat driver |
| cron_morning.sh (44L) | **Core live** | Daily 08:00 planning |
| cron_evening.sh (131L) | **Core live** | Daily 18:00 assessment |
| cron_reflection.sh (124L) | **Core live** | Daily 21:00 reflection |
| cron_evolution.sh (103L) | **Core live** | Daily 13:00 deep analysis |
| cron_research.sh (365L) | **Core live** | 2x/day research execution |
| cron_implementation_sprint.sh (188L) | **Core live** | Daily 14:00 implementation |
| cron_strategic_audit.sh (336L) | **Core live** | Wed/Sat 17:00 strategic audit |
| cron_orchestrator.sh (86L) | **Core live** | Daily 19:30 agent sweep |
| cron_report_morning.sh (327L) | **Core live** | Daily 09:30 Telegram digest |
| cron_report_evening.sh (273L) | **Core live** | Daily 22:30 Telegram digest |
| cron_env.sh (135L) | **Core live** | Sourced by ALL cron scripts |
| lock_helper.sh (226L) | **Core live** | Sourced by ALL cron scripts |
| spawn_claude.sh (207L) | **Core live** | Claude Code spawner (M2.5 /spawn) |

**Recommendation:** All core. Keep as-is.

---

### 2.8 Maintenance & Infrastructure

| Script | Classification | Evidence |
|--------|----------------|----------|
| backup_daily.sh (334L) | **Core live** | Daily 02:00 |
| backup_verify.sh (285L) | **Core live** | Daily 02:30 |
| health_monitor.sh (224L) | **Core live** | Every 15 min |
| cron_watchdog.sh (188L) | **Core live** | Every 30 min |
| cron_doctor.py (698L) | **Core live** | Auto-recovery. Called by health_monitor |
| cron_graph_checkpoint.sh (71L) | **Core live** | Daily 04:00 |
| cron_graph_compaction.sh (25L) | **Core live** | Daily 04:30 |
| cron_graph_verify.sh (60L) | **Core live** | Daily 04:45 |
| cron_chromadb_vacuum.sh (101L) | **Core live** | Daily 05:00 |
| ~~cron_graph_soak_manager.sh~~ | ~~Core live~~ | _(Deleted 2026-04-02, commit 5745f39)_ |
| cron_pi_refresh.sh (36L) | **Core live** | Daily 05:45 |
| graph_compaction.py (416L) | **Core live** | Called by cron_graph_compaction.sh |
| graph_cutover.py (430L) | **Core live** | Manual JSON→SQLite migration tool |
| cleanup_policy.py (335L) | **Core live** | Weekly Sun 05:30 |
| goal_hygiene.py (442L) | **Core live** | Weekly Sun 05:10 |
| brain_hygiene.py (301L) | **Core live** | Weekly Sun 05:15 |
| safe_update.sh (913L) | **Core live** | Manual update with rollback |
| backup_restore.sh (322L) | **Keep (manual emergency)** | Manual-only but essential for disaster recovery |

**Recommendation:** All core operational. Keep as-is.

---

### 2.9 Website & Public Surface

| Module | Location | Classification | Evidence |
|--------|----------|----------------|----------|
| website/server.py | website/ | **Core live** | Starlette server on port 18801. systemd service running |
| website/static/ | website/static/ | **Core live** | 5 HTML pages + CSS |
| /api/public/status | website/server.py | **Core live** | Live JSON endpoint (CLR, PI, queue) |

**Recommendation:** Keep as-is. Pending: D4 (architecture page sanitization).

---

### 2.10 Skills

All 20 skills have SKILL.md files and are properly wired into OpenClaw.

| Category | Skills | Classification |
|----------|--------|----------------|
| System | clarvis-brain, clarvis-cognition, clarvis-model-router, claude-code | **Core live** |
| User-invocable | spawn-claude, queue-clarvis, project-agent, promise-track, web-browse | **Core live** |
| Tool | brave-search, ddg-web-search, tavily-search, session-logs, gog, himalaya, notion, mcporter, nano-pdf, summarize | **Core live** |
| Internal | iteration | **Core live** |

**Recommendation:** Keep all. No dead skills found.

---

### 2.11 Packages

| Package | Classification | Evidence |
|---------|----------------|----------|
| clarvis-db (1.0.0) | **Core live** | ChromaDB wrapper. Installed editable. Has tests |
| clarvis-cost (1.0.0) | **Core live** | Imported by cost_tracker.py, heartbeat_postflight.py |
| clarvis-reasoning (1.0.0) | **Core live** | Imported by reasoning_chain_hook.py, self_model.py |

**Recommendation:** Keep all. These are the extraction-ready public packages.

---

## 3. Dead / Orphaned Code

### 3.1 Thin Wrappers (Safe to Delete)

These 8 scripts are pure re-exports of spine modules with **zero callers anywhere in the codebase**:

| File | Lines | Re-exports | Callers |
|------|-------|------------|---------|
| scripts/attention.py | 16 | clarvis.cognition.attention | **None** |
| scripts/clarvis_confidence.py | 14 | clarvis.cognition.confidence | **None** |
| scripts/episodic_memory.py | 10 | clarvis.memory.episodic_memory | **None** |
| scripts/hebbian_memory.py | 9 | clarvis.memory.hebbian_memory | **None** |
| scripts/memory_consolidation.py | 16 | clarvis.memory.memory_consolidation | **None** |
| scripts/procedural_memory.py | 14 | clarvis.memory.procedural_memory | **None** |
| scripts/thought_protocol.py | 13 | clarvis.cognition.thought_protocol | **None** |
| scripts/working_memory.py | 9 | clarvis.memory.working_memory | **None** |

**Total: 101 lines. Safe to delete.** No import will break.

### 3.2 Research / Cognitive Modeling (Never Wired)

These scripts implement interesting cognitive science concepts but have **no production callers, no cron entry, and no CLI wiring**:

| File | Lines | Concept | Callers |
|------|-------|---------|---------|
| scripts/theory_of_mind.py | 966 | Agent mental state modeling | **None** |
| scripts/actr_activation.py | 650 | ACT-R spreading activation | **None** (brain hooks reference exists but commented/optional) |
| scripts/hyperon_atomspace.py | 846 | Symbolic pattern matching | **None** |
| scripts/workspace_broadcast.py | 650 | GWT global broadcast | **None** |
| scripts/cognitive_load.py | 573 | Token budget tracking | **None** (latency_budget.py used instead) |
| scripts/somatic_markers.py | 461 | Emotion-as-decision-bias | **None** (spine stub exists, 16L) |
| scripts/universal_web_agent.py | 647 | Web navigation agent | **None** (clarvis_browser.py used instead) |
| scripts/prompt_optimizer.py | 462 | Prompt tuning | **None** |
| scripts/automation_insights.py | 360 | Task analytics | **None** |
| scripts/public_feed.py | 279 | Public API feed generation | **None** |
| scripts/retrieval_quality_report.py | 314 | Retrieval reports | **None** |
| scripts/prediction_review.py | 279 | Prediction calibration review | **None** |
| scripts/generate_dashboard.py | 351 | Summary dashboard | **None** |

**Total: 6,838 lines.** These are research prototypes. Recommend moving to `experimental/` rather than deleting — they contain intellectual work that may be valuable later.

### 3.3 Weakly Wired (1-2 callers, optional)

| File | Lines | Status | Callers |
|------|-------|--------|---------|
| scripts/conversation_learner.py | 537 | Called by cron_reflection.sh only | 1 caller |
| scripts/agent_lifecycle.py | 477 | Called by agent_orchestrator.py only | 1 caller |
| scripts/reasoning_chains.py | 177 | Called by clarvis_reflection.py only | 1 caller |
| scripts/retrieval_experiment.py | 525 | Called by parameter_evolution.py + spine | 2 callers |
| scripts/graph_migrate_to_sqlite.py | 339 | Called by graph_cutover.py + cron_env.sh | 2 callers (migration tool) |
| scripts/brain_bridge.py | 287 | Legacy bridge | Unclear |

**Recommendation:** Keep these — they have real callers, even if few. Mark as low-priority for future review.

---

## 4. Script vs Spine Duplication Analysis

### 4.1 Functions Split Across Boundaries

| Function | scripts/ location | spine location | Authoritative? |
|----------|-------------------|----------------|----------------|
| `generate_tiered_brief()` | context_compressor.py | clarvis/context/assembly.py | **scripts/** (heartbeat imports it) |
| `compress_queue()` | context_compressor.py | clarvis/context/compressor.py | **scripts/** |
| `compress_episodes()` | context_compressor.py | clarvis/context/compressor.py | **scripts/** |
| `gc()` | context_compressor.py | clarvis/context/gc.py | **scripts/** |
| `archive_completed()` | context_compressor.py | clarvis/context/gc.py | **scripts/** |
| `rotate_logs()` | context_compressor.py | clarvis/context/gc.py | **scripts/** |
| `mmr_rerank()` | context_compressor.py | clarvis/context/compressor.py | **both** (same logic) |
| `tfidf_extract()` | context_compressor.py | clarvis/context/compressor.py | **both** (same logic) |

**Impact:** The spine context/ module was partially migrated. The scripts/ version is what runs in production. The spine version may have drifted.

### 4.2 Import Migration Status

| Pattern | Count | Notes |
|---------|-------|-------|
| `from clarvis.*` (spine imports) | 38 scripts | Modern, preferred |
| `sys.path.insert` (legacy imports) | 87 scripts | Legacy, works but fragile |
| Both patterns in same file | ~15 scripts | Transitional |

---

## 5. DO NOT REMOVE — Deletion Risk Registry

These items might look like candidates for cleanup but are **critical production dependencies**:

| Item | Why it looks removable | Why it's critical |
|------|------------------------|-------------------|
| scripts/brain.py (306L) | "Just a wrapper" | 10+ scripts import it via sys.path. Remove = break heartbeat |
| scripts/context_compressor.py (1499L) | "Duplicates spine" | It IS the runtime. Spine version is incomplete subset |
| scripts/task_selector.py (98L) | "Thin wrapper" | heartbeat_preflight.py imports it |
| scripts/cognitive_workspace.py (678L) | "Research concept" | Actively called by heartbeat pre/postflight |
| scripts/prompt_builder.py (543L) | "Could be in spine" | Called by 3 cron orchestrators |
| scripts/directive_engine.py (1327L) | "Complex, seems over-engineered" | Called by heartbeat_postflight, goal tracking |
| scripts/clarvis_reasoning.py (926L) | "Cognitive research" | Called by heartbeat_postflight |
| scripts/reasoning_chain_hook.py (312L) | "Hook, maybe unused" | Called by heartbeat_postflight |
| scripts/soar_engine.py (827L) | "Academic concept" | 5 callers incl. heartbeat_postflight, clarvis/memory/soar.py, episodic_memory |
| data/clarvisdb/ (415MB) | "Large directory" | THE brain. Deleting = total amnesia |
| dream_engine.py (742L) | "Seems experimental" | Has active cron entry (02:45 daily) |
| lock_helper.sh (226L) | "Just a helper" | Sourced by every cron script. Remove = race conditions |

---

## 6. Script Bloat vs Real Runtime Value

### By the numbers

| Category | Files | Lines | Runtime Value |
|----------|-------|-------|---------------|
| Core live (cron + heartbeat + brain) | ~45 | ~18,000 | **HIGH** — system stops without these |
| Core live (spine) | 77 | ~30,000 | **HIGH** — all modules properly wired |
| Maintenance & monitoring | ~18 | ~4,500 | **HIGH** — keeps system healthy |
| Benchmarks & metrics scripts | ~8 | ~4,000 | **MEDIUM** — weekly/monthly measurement |
| Orchestration (project agents) | ~3 | ~4,600 | **MEDIUM** — active but niche |
| Thin wrappers (dead) | 8 | 101 | **ZERO** — no callers |
| Research prototypes (dead) | 13 | 6,838 | **ZERO** — never wired |
| Weakly wired | 6 | 2,342 | **LOW** — 1-2 callers each |

**Bloat ratio:** ~7,000 lines (10%) are genuinely dead code. Another ~2,300 lines (3.5%) are weakly wired.

---

## 7. Proposed Clean Public-Facing Structure

For open-source release, the following structure hides internal complexity while exposing useful architecture:

```
clarvis/                          # The spine (keep as-is, it's clean)
  brain/                          # Vector memory + graph
  memory/                         # Episodic, procedural, hebbian, working
  context/                        # Context assembly, compression, GC
  cognition/                      # Attention, confidence, thought protocol
  metrics/                        # Phi, PI, CLR, self-model, quality
  heartbeat/                      # Lifecycle hooks + gate
  orch/                           # Task routing, selection, cost
  runtime/                        # Mode control
  cli.py                          # Root CLI entrypoint

scripts/                          # Operational scripts (curated)
  # Core heartbeat pipeline
  heartbeat_preflight.py
  heartbeat_postflight.py
  heartbeat_gate.py

  # Cron orchestrators
  cron_autonomous.sh
  cron_morning.sh
  cron_evening.sh
  cron_reflection.sh
  cron_evolution.sh
  cron_research.sh
  cron_implementation_sprint.sh
  cron_strategic_audit.sh
  cron_orchestrator.sh
  cron_report_morning.sh
  cron_report_evening.sh

  # Infrastructure
  cron_env.sh
  lock_helper.sh
  spawn_claude.sh

  # Maintenance
  backup_daily.sh
  backup_verify.sh
  health_monitor.sh
  cron_watchdog.sh
  cron_doctor.py
  cleanup_policy.py
  brain_hygiene.py
  goal_hygiene.py
  graph_compaction.py
  graph_cutover.py
  safe_update.sh

  # Maintenance cron wrappers
  cron_graph_checkpoint.sh
  cron_graph_compaction.sh
  cron_graph_verify.sh
  cron_chromadb_vacuum.sh
  # cron_graph_soak_manager.sh — deleted 2026-04-02
  cron_pi_refresh.sh
  cron_brain_eval.sh
  cron_llm_brain_review.sh
  cron_absolute_zero.sh
  cron_monthly_reflection.sh
  cron_cleanup.sh
  cron_clr_benchmark.sh

  # Brain & memory tools
  brain.py                        # Keep until legacy migration done
  lite_brain.py
  brain_introspect.py
  context_compressor.py           # Migrate to spine eventually
  cognitive_workspace.py

  # Cognitive pipeline
  clarvis_reasoning.py
  reasoning_chain_hook.py
  directive_engine.py
  prompt_builder.py
  dream_engine.py
  clarvis_reflection.py

  # Metrics & benchmarks
  performance_benchmark.py
  clr_benchmark.py
  brief_benchmark.py
  daily_brain_eval.py
  llm_brain_review.py
  retrieval_benchmark.py
  retrieval_quality.py

  # Agents
  project_agent.py
  agent_orchestrator.py

  # Evolution
  evolution_loop.py
  evolution_preflight.py
  parameter_evolution.py
  meta_learning.py
  absolute_zero.py

  # Cost & budget
  cost_tracker.py
  cost_api.py
  budget_alert.py

  # Utilities
  digest_writer.py
  queue_writer.py
  goal_tracker.py
  daily_memory_log.py
  session_hook.py
  latency_budget.py
  performance_gate.py
  self_model.py
  self_representation.py
  temporal_self.py
  tool_maker.py
  extract_steps.py

  # Web / browser
  clarvis_browser.py
  browser_agent.py

experimental/                     # Moved from scripts/ — research prototypes
  theory_of_mind.py
  soar_engine.py
  actr_activation.py
  hyperon_atomspace.py
  workspace_broadcast.py
  cognitive_load.py
  somatic_markers.py
  universal_web_agent.py
  world_models.py
  meta_gradient_rl.py
  failure_amplifier.py
  causal_model.py
  ast_surgery.py
  graphrag_communities.py

# DELETED (thin wrappers with zero callers):
#   attention.py, clarvis_confidence.py, episodic_memory.py,
#   hebbian_memory.py, memory_consolidation.py, procedural_memory.py,
#   thought_protocol.py, working_memory.py

# DELETED (dead utilities):
#   prompt_optimizer.py, automation_insights.py, public_feed.py,
#   retrieval_quality_report.py, prediction_review.py,
#   generate_dashboard.py, gate_check.sh, graph_migrate_to_sqlite.py
```

---

## 8. Prioritized Action Plan

### Phase 1: Safe Deletions (Zero Risk)
**Effort:** 15 min | **Impact:** Remove 101 lines of dead wrappers

1. Delete 8 thin wrapper scripts (attention.py, clarvis_confidence.py, episodic_memory.py, hebbian_memory.py, memory_consolidation.py, procedural_memory.py, thought_protocol.py, working_memory.py)
2. Verify with `grep -r` that nothing imports them (already confirmed: zero callers)

### Phase 2: Move Research Prototypes to experimental/ (Low Risk)
**Effort:** 30 min | **Impact:** Move ~10,000 lines to experimental/, clear scripts/ clutter

1. Create `experimental/` directory
2. Move 14 research scripts (see §3.2 + world_models, meta_gradient_rl, failure_amplifier, causal_model, ast_surgery, graphrag_communities)
3. Move dead utilities (prompt_optimizer, automation_insights, public_feed, retrieval_quality_report, prediction_review, generate_dashboard)
4. Add `experimental/README.md` explaining these are research prototypes

### Phase 3: Context Engine Consolidation (Medium Risk, High Value)
**Effort:** 2-3 hours | **Impact:** Resolve the split-brain context problem

1. Diff `scripts/context_compressor.py` against `clarvis/context/` modules
2. Identify functions unique to scripts/ version
3. Migrate unique functions into spine (clarvis/context/assembly.py or new submodule)
4. Update heartbeat_preflight.py to import from spine
5. Keep scripts/context_compressor.py as thin re-export wrapper during transition
6. Test heartbeat cycle end-to-end

### Phase 4: Legacy Import Migration (Medium Risk, Long-Term)
**Effort:** 4-6 hours | **Impact:** Move 87 scripts from sys.path to spine imports

1. Prioritize scripts called by cron (highest runtime impact)
2. Change `sys.path.insert(0, ...)` → `from clarvis.*` imports
3. Test each migrated script individually
4. Once brain.py has zero legacy callers, archive it

### Phase 5: Doc Cleanup (Zero Risk)
**Effort:** 1 hour | **Impact:** Archive ~15 dated plan/audit docs

1. Create `docs/archive/` (already exists partially)
2. Move completed plans: REFACTOR_COMPLETION_PLAN, POST_MIGRATION_GAP_REPORT, ARCH_AUDIT_2026-03-05, MARATHON_STOP_REPORT, etc.
3. Keep live docs: ARCHITECTURE, CLARVISDB, CONVENTIONS, RUNBOOK, SAFETY_INVARIANTS, DELIVERY_CHECKLIST, DELIVERY_BURNDOWN

### Phase 6: Heartbeat Gate Consolidation (Low Risk)
**Effort:** 1 hour | **Impact:** Unify gate logic between scripts/ and spine

1. Verify `clarvis/heartbeat/gate.py` logic matches `scripts/heartbeat_gate.py`
2. Make scripts/heartbeat_gate.py a thin caller of spine gate
3. Update cron_autonomous.sh if needed

---

## Appendix A: Cron Schedule (Actual, from crontab -l)

52 entries total. Schedule matches CLAUDE.md with these additions not in CLAUDE.md:
- ~~`05:05` daily — cron_graph_soak_manager.sh~~ _(deleted 2026-04-02)_
- `06:00` daily — cron_brain_eval.sh (deterministic)
- `06:15` daily — cron_llm_brain_review.sh (LLM-judged)
- `02:40` daily — clarvis cognition context-relevance refresh
- `@reboot` — pm2 resurrect + chromium start

## Appendix B: Import Dependency Graph (Simplified)

```
crontab
  └→ cron_autonomous.sh (+ 11 other orchestrators)
       └→ heartbeat_gate.py
       └→ heartbeat_preflight.py
            ├→ brain.py → clarvis.brain (ChromaDB)
            ├→ context_compressor.py (1499L, AUTHORITATIVE)
            ├→ cognitive_workspace.py
            ├→ clarvis.cognition.attention
            ├→ clarvis.orch.task_selector
            └→ latency_budget.py, performance_gate.py
       └→ Claude Code execution
       └→ heartbeat_postflight.py
            ├→ brain.py → clarvis.brain
            ├→ clarvis.memory.episodic_memory
            ├→ clarvis.cognition.confidence
            ├→ clarvis_reasoning.py
            ├→ reasoning_chain_hook.py
            ├→ directive_engine.py
            ├→ tool_maker.py
            ├→ self_representation.py
            ├→ temporal_self.py
            └→ prediction_resolver.py
```

## Appendix C: Uncertainty Register (Resolved 2026-03-23)

Updated with caller evidence from `grep -rl` across scripts/ and clarvis/:

| Item | Classification | Evidence |
|------|---------------|----------|
| scripts/soar_engine.py (827L) | **Partially wired** | 5 callers: heartbeat_postflight, clarvis/memory/soar.py, clarvis/memory/episodic_memory, clarvis/metrics/quality.py. Hyperon+workspace_broadcast are dead but soar itself is wired |
| scripts/conversation_learner.py (537L) | **Partially wired** | 2 callers: cron_reflection.sh (active daily cron), clarvis/metrics/memory_audit.py |
| scripts/brain_bridge.py (287L) | **Core live** | 4 callers: heartbeat_preflight, heartbeat_postflight, brain_introspect, clarvis/metrics/quality.py. Part of heartbeat pipeline |
| clarvis/learning/meta_learning.py | **Partially wired** | Spine module exists (migrated from scripts/meta_learning.py), scripts/ wrapper still active |
| clarvis/adapters/ | **Architectural scaffold** | OpenClaw adapter (openclaw.py) active. Base class for future adapter pattern |
| scripts/obligation_tracker.py (880L) | **Core live** | 4 callers: directive_engine, heartbeat_postflight, heartbeat_preflight, cron_autonomous.sh. Central to compliance pipeline |
| scripts/dashboard_server.py (488L) | **Retire** | 0 callers. Website (server.py on port 18801) supersedes it |
| scripts/intra_linker.py (258L) | **Partially wired** | 3 callers: cron_reflection.sh, clarvis/cli_brain.py (intralink cmd), clarvis/metrics/memory_audit.py |
