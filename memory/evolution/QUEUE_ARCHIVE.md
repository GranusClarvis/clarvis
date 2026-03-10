# Evolution Queue — Archive

_Completed items archived from QUEUE.md to reduce token footprint._
_Last archived: 2026-03-09_

### Archived 2026-03-09
- [x] [CHROMADB_SINGLETON] All 3 steps complete. Factory pattern in `clarvis/brain/factory.py`, ClarvisBrain+LiteBrain wired, test fixtures converted from direct `chromadb.PersistentClient` to `get_chroma_client()` + `reset_singletons()`. 87 tests pass.
- [x] [RETRIEVAL_EVAL] CRAG-style evaluator in `clarvis/brain/retrieval_eval.py`. Composite scoring (semantic_sim+keyword+importance+recency), 3-tier classification, strip refinement. Wired in preflight §8.6, verdict logged in retrieval_quality events. 25 tests.
- [x] [GITHUB_API_TASKS] GitHub API fully operational via `gh` CLI (GranusClarvis). Issues, PRs, notifications, labels all validated.

### Archived 2026-03-06
- [x] [RESEARCH_REPO_OBLITERATUS] LLM abliteration toolkit. DISCARD: not relevant to API-based Clarvis. See `memory/research/OBLITERATUS_review.md`.
- [x] [AUTONOMY_LOGIN] Verified GitHub API auth (GranusClarvis), browser session (102 cookies/28 domains), profile accessible.
- [x] [AUTONOMY_POST] Created GitHub issue GranusClarvis/clarvis#1 autonomously. Post appeared, content matches intent.

---

## Refactor Phase 2 — Brain Split (2026-03-03)
- [x] [REFACTOR_PHASE2] Extracted `clarvis.brain` package from monolithic brain.py (1780→1716 lines across 6 files)
  - `clarvis/brain/constants.py` (63 lines) — paths, collection names, query routing
  - `clarvis/brain/graph.py` (230 lines) — GraphMixin: relationships, traversal, backfill
  - `clarvis/brain/search.py` (229 lines) — SearchMixin: recall, embedding cache, temporal queries
  - `clarvis/brain/store.py` (510 lines) — StoreMixin: storage, goals, context, decay, stats, reconsolidation
  - `clarvis/brain/hooks.py` (127 lines) — Hook registry: actr, attention, hebbian, synaptic, retrieval_quality, consolidation
  - `clarvis/brain/__init__.py` (253 lines) — ClarvisBrain(StoreMixin, GraphMixin, SearchMixin) + singletons + convenience functions
  - `scripts/brain.py` (304 lines) — thin wrapper + CLI (backward compatible, all 54 importers work unchanged)
  - **SCC: 6→0** (dependency inversion via hook registry replaces direct imports)
  - **Fan-out: 7→1** (only imports clarvis.brain, no direct script imports)
  - All tests pass: import, stats, store, recall, health, hooks registration, CLI

---

## P0 Completions

### Auto-Remediation (2026-02-22)
- [x] [AUTO-FIX] Fix failure in cron_autonomous: Exit code 124 (2026-02-22 11:45 UTC — timeout(1) returns 124 when Claude Code exceeds 600s limit. Fixed: dedicated exit-124 handler + SyntaxError fix in attention broadcast.)

### Wiring & Feedback Gaps (2026-02-22 round 2)
- [x] Fix working memory going empty (2026-02-22 18:00 UTC — spotlight.json has 173 active items, consciousness score 0.78.)
- [x] Wire ast_surgery.py into weekly cron (2026-02-22 — Added to cron_strategic_audit.sh Wed+Sat.)
- [x] Wire parameter_evolution.py into cron_evolution.sh (2026-02-22 — Added evolve step after capability assessment.)
- [x] Wire semantic_bridge_builder.py into cron_reflection.sh (2026-02-22 18:00 UTC — Wired as Step 3.7, semantic overlap 0.446.)
- [x] Build cognitive load monitor (2026-02-22 19:03 UTC — cognitive_load.py: 4 metrics, 3 status levels, wired into cron_autonomous.sh. Current load: 0.115 HEALTHY.)

### Critical Gaps (2026-02-22)
- [x] Fix reasoning_chains score 0.20→0.97 (2026-02-22 06:45 UTC — Rewrote reasoning_chain_hook.py, backfilled 8 chains.)
- [x] Build cron health auto-recovery (2026-02-22 09:xx UTC — cron_doctor.py: 6 classifiers, 6 recovery handlers, wired into watchdog.)
- [x] Boost semantic cross-collection overlap (2026-02-22 — semantic_bridge_builder.py created, Phi 0.328→0.45+.)
- [x] Wire session_hook.py into real session lifecycle (2026-02-22 06:13 UTC — session_open in cron_morning.sh, session_close in cron_reflection.sh.)
- [x] Build active learning from episodic failures (2026-02-22 07:xx UTC — failure_amplifier.py: 9 scanners, episodes 10→48, wired as Step 5.5 in cron_reflection.sh.)

### Memory & Retrieval Rehabilitation (2026-02-22)
- [x] Advance consciousness metrics (2026-02-22 03:15 UTC — Enriched 3 collections +33 entries, Phi 0.673→0.697.)
- [x] Improve session continuity (2026-02-22 04:10 UTC — session_hook.py wired, attention saves on close.)
- [x] Optimize heartbeat efficiency (2026-02-22 04:15 UTC — All recent tasks successful, ~90% success rate.)
- [x] Advance self-reflection (2026-02-22 04:35 UTC — Brier=0.033, Phi 0.700.)
- [x] Fix retrieval hit rate 17%→85.7% (2026-02-22 01:00 UTC — Fixed 3 bugs in smart_recall.)
- [x] Build goal-progress tracker (2026-02-22 01:35 UTC — goal_tracker.py: 12 goals, 7 domains, wired into cron_evolution.sh.)
- [x] Enrich sparse collections (2026-02-22 03:15 UTC — enrich_sparse_collections.py: preferences/infrastructure/context populated.)
- [x] Build memory retrieval benchmarks (2026-02-22 02:37 UTC — 20 ground-truth pairs, P@3=0.767, Recall=1.000.)
- [x] Create autonomous goal generation from episodic patterns (2026-02-22 04:40 UTC — synthesize() in episodic_memory.py.)

### Wiring & Feedback Loops (2026-02-22)
- [x] Wire conversation_learner.py into cron_reflection.sh as Step 5 (2026-02-22 00:24 UTC)
- [x] Wire dashboard.py into cron_evening.sh (2026-02-22)
- [x] Wire self_report.py into cron_evening.sh (2026-02-22)
- [x] Wire backup_daily.sh — confirmed in crontab at 02:00 (2026-02-22)
- [x] Build episodic memory system (2026-02-22 00:37 UTC — episodic_memory.py with ACT-R decay, wired into cron_autonomous.sh.)

### Foundation Rebuild (2026-02-21)
- [x] Wire phi_metric.py into cron_evening.sh (2026-02-21 22:00 UTC)
- [x] Wire smart_recall() into task_selector/procedural/reasoning (2026-02-21 22:00 UTC)
- [x] Wire retrieval_quality.py into cron_evening.sh (2026-02-21 22:00 UTC)
- [x] Add attention.tick() to cron_autonomous.sh (2026-02-21 22:00 UTC)
- [x] Add attention broadcast to cron_autonomous.sh (2026-02-21 22:00 UTC)
- [x] Fix assessor ceiling effect — avg 1.00→0.61 (2026-02-21 22:00 UTC)
- [x] Create memory_consolidation.py (2026-02-21 22:00 UTC)
- [x] Enhance cron_evolution.sh with phi/capability/retrieval data (2026-02-21 22:00 UTC)
- [x] Fix reasoning chain outcomes (2026-02-21 22:03 UTC — assessor checked wrong path, fixed.)
- [x] Populate working memory during tasks (2026-02-21 22:44 UTC — 5 add calls wired.)
- [x] Improve cross-collection connectivity (2026-02-21 — Phi 0.589→0.653.)
- [x] Run memory consolidation first time (2026-02-21 23:00 UTC — 226→195 memories.)
- [x] Fix reasoning_chain_hook.py:56 limit→n (2026-02-21 18:21 UTC)
- [x] Fix procedural_memory.py threshold (2026-02-21 19:00 UTC)
- [x] Fix cron_autonomous.sh generic learning (2026-02-21 19:10 UTC)
- [x] Fix phi_metric.py 90-day cap (2026-02-21 18:55 UTC)
- [x] [AUTO-FIX] Fix test_fail exit code 1 (2026-02-21 08:05 UTC)
- [x] Wire attention.py into cron_autonomous.sh (2026-02-21 13:13 UTC)
- [x] Make working_memory.py persistent (2026-02-21 14:17 UTC)
- [x] Build prediction-outcome feedback loop (2026-02-21 14:17 UTC)

### Oldest P0
- [x] Run brain.optimize() (2026-02-20 16:55 UTC)
- [x] Hook reflection into feedback loop (2026-02-20 16:51 UTC)
- [x] Auto-link graph relationships (2026-02-20 16:54 UTC)

---

## P1 Completions

### Auto-generated 2026-02-22
- [x] Wire attention.py into daily execution (2026-02-22 10:45 UTC — spotlight-alignment scoring in task_selector.py.)
- [x] Make working_memory.py persistent (duplicate of 2026-02-21 entry)
- [x] Fix goal tracker noise — cleaned 21 garbage goals, added validation (2026-02-22)
- [x] Fix phi_metric.py self-healing — wrong param fixed (2026-02-22)
- [x] Fix reasoning_chains.py find_related_chains — wrong params fixed (2026-02-22)
- [x] Fix semantic_bridge_builder.py singleton (2026-02-22)
- [x] Fix graph node tracking — add_relationship registers both nodes (2026-02-22)
- [x] Make brain singleton lazy — 200ms saved on import (2026-02-22)
- [x] Unify QUEUE.md writers — queue_writer.py with dedup + daily cap (2026-02-22)
- [x] Add error handling to cron_reflection.sh (2026-02-22)
- [x] Add cron_watchdog.sh to crontab — runs every 30min (2026-02-22)
- [x] Improve prediction specificity — predict_specific() with 5 domain types (2026-02-22)
- [x] Clean stale data — archived main.sqlite, clarvisdb-local, evolution-log.jsonl (2026-02-22)
- [x] Boost Code Generation score (2026-02-22 15:46 UTC — code_quality_gate.py, clean ratio 35%→57%.)
- [x] Build temporal self-awareness module (2026-02-22 — temporal_self.py, growth_narrative().)
- [x] Implement counterfactual dreaming engine (2026-02-22 15:53 UTC — dream_engine.py: 6 counterfactual templates, wired at 02:15.)

### Auto-generated 2026-02-21
- [x] Deep self-analysis (2026-02-21 21:30 UTC — #1 gap: retrieval. Built smart_recall, 50%→75% hit rate.)
- [x] Integrate reasoning_chains.py into heartbeat (2026-02-21 17:27 UTC — Already wired via hook.)
- [x] Run knowledge_synthesis.py in daily reflection (2026-02-21 17:45 UTC — 117 cross-domain concepts, 15 bridges.)
- [x] Review prediction outcomes (2026-02-21 18:03 UTC — 100% success, Brier 0.08, threshold 0.70→0.89.)
- [x] Run self-assessment (2026-02-21 20:16 UTC — Phi 0.352→0.568.)
- [x] Integrate reasoning_chains.py into every evolution task (2026-02-21 15:16 UTC — reasoning_chain_hook.py.)
- [x] Wire smart_recall() into downstream systems (2026-02-21 22:00 UTC)
- [x] Build autonomous learning from conversations (2026-02-21 23:46 UTC — conversation_learner.py: 14 insights.)
- [x] Fix capability assessors ceiling effect (2026-02-21 22:00 UTC)
- [x] Implement Phi metric (2026-02-21 15:49 UTC — phi_metric.py, Φ=0.352.)
- [x] Wire knowledge_synthesis.py into cron_reflection.sh (2026-02-21 16:57 UTC)
- [x] Build procedural memory (2026-02-21 — procedural_memory.py, wired into cron_autonomous.sh.)
- [x] Create self-improvement from prediction outcomes (2026-02-21 — prediction_review.py.)
- [x] Run self_model.py update daily (2026-02-21 — 7 scored domains, wired into cron_evening.sh.)
- [x] Build session-close automation (2026-02-20 19:20 UTC)
- [x] Create self-assessment script (2026-02-20 21:11 UTC)
- [x] Research Helixir (2026-02-21 00:27 UTC — Verdict: don't migrate, steal ideas.)
- [x] Build confidence calibration (2026-02-20 23:50 UTC — predict/outcome/calibration with Brier.)
- [x] Build internal world model (2026-02-20 21:11 UTC)

### Week 9 (2026-02-22–23)
- [x] Implement ACT-R power-law activation decay (2026-02-22 19:50 UTC — Pavlik & Anderson 2005 spacing effect.)
- [x] Build A-Mem style memory evolution (2026-02-22 20:03 UTC — hebbian_memory.py: 4 Hebbian mechanisms.)
- [x] Add capability score regression alerts (2026-02-22 UTC — check_weekly_regression() in self_model.py.)
- [x] Wire dream_engine.py into crontab (2026-02-22 19:10 UTC — 02:45, 180s timeout.)
- [x] Context window optimization (2026-02-23 UTC — archive_completed, rotate_logs, gc in context_compressor.py.)
- [x] Evaluate ClawRouter (2026-02-23 UTC — Verdict: REDUNDANT, already implemented.)
- [x] Audit current token usage (2026-02-22 UTC — cost_optimization.md, routing matrix.)
- [x] Implement smart context compression (2026-02-22 UTC — context_compressor.py, 98% reduction.)

---

## P2 Completions

- [x] Research memristor-based neural memory (2026-02-22 UTC — synaptic_memory.py: STDP + SQLite, 459 events→51,720 synapses.)
- [x] Implement meta-learning (2026-02-22 20:09 UTC — meta_learning.py: 5 strategies, recommendation engine.)
- [x] Build theory of mind for user modeling (2026-02-23 10:07 UTC)
- [x] Research agent memory architectures (2026-02-21 — ACT-R, A-Mem, episodic, procedural, working memory.)
- [x] Build reasoning chains (2026-02-21 04:26 UTC)
- [x] Study Hive framework (2026-02-21 05:27 UTC — Verdict: steal patterns, don't migrate.)
- [x] Build Hive-style evolution loop (2026-02-21 07:02 UTC — evolution_loop.py.)
- [x] Build knowledge synthesis (2026-02-21 05:57 UTC — 20 connections, 5 insights.)
- [x] Optimize brain.py query performance (2026-02-21 07:28 UTC — 895ms→~640ms.)
- [x] Build monitoring dashboard (2026-02-21 08:03 UTC — dashboard.py.)
- [x] Research consciousness theories (2026-02-21 08:05 UTC — GWT, IIT, HOT.)
- [x] Implement attention mechanism (2026-02-21 10:02 UTC — attention.py with GWT spotlight.)
- [x] Build working memory buffer (2026-02-21 10:02 UTC — working_memory.py.)
- [x] Expand meta-cognition (2026-02-21 10:33 UTC — self_model.py higher-order awareness.)

---

## Protocol Genesis Completions (Week 8)
- [x] Invent internal communication protocol (2026-02-22 UTC — thought_protocol.py: ThoughtScript DSL, 3 layers, 8 tests pass.)
- [x] Build somatic markers (2026-02-22 UTC — somatic_markers.py: Damasio-inspired, 8 emotion dimensions, 141 markers backfilled.)
- [x] Implement counterfactual dreaming (2026-02-22 — dream_engine.py.)
- [x] Create AST-level self-surgery (2026-02-22 13:07 UTC — ast_surgery.py: 7 mutation detectors, 99 proposals.)
- [x] Run parameter evolution (2026-02-22 — salience weights tuned.)

---

## Standalone Product Packaging Completions
- [x] ClarvisDB — local vector memory (Hebbian, STDP, ChromaDB + ONNX)
- [x] ClarvisC — consciousness stack (Phi, GWT, self-model, episodic)
- [x] ClarvisRouter — smart model routing (14-dim scorer, OpenRouter compatible)
- [x] ClarvisCode — Claude Code/OpenCode integration
- [x] ClarvisAttention — GWT attention mechanism (2026-02-23 — packages/clarvis-attention/, 22 tests.)
- [x] ClarvisPhi — IIT Phi metric measurement (2026-02-23 — packages/clarvis-phi/, 10 tests.)
- [x] ClarvisEpisodic — ACT-R episodic memory (2026-02-23 — packages/clarvis-episodic/, 14 tests.)
- [x] ClarvisReasoning — reasoning chains + meta-cognition (2026-02-23)
- [x] ClarvisCost — token optimization + cost tracking (2026-02-23)

---

## Oldest Completions (pre-2026-02-21)
- [x] Test backup/rollback scripts (2026-02-18 18:32)
- [x] Verify git tracking (2026-02-18 18:15)
- [x] Write self-benchmark for memory (2026-02-19 02:00)
- [x] Index patterns from past conversations (2026-02-20 10:42)
- [x] Build health-check script (2026-02-20 06:45)
- [x] Build daily summary script (2026-02-20 02:15)
- [x] ClarvisDB v1.0 — 46 memories, 7 collections (2026-02-20)
- [x] Claude Code skill integration (2026-02-20)
- [x] Legacy brain script cleanup (2026-02-20)
- [x] Switch to M2.5 with Claude Code delegation model (2026-02-20)
- [x] SELF.md — comprehensive self-awareness document (2026-02-20)
- [x] ROADMAP.md — consolidated evolution roadmap (2026-02-20)
- [x] Doc cleanup and archive (2026-02-20)
- [x] Session cleanup (2026-02-20)
- [x] Cron cleanup (2026-02-20)

## Archived 2026-02-27 (batch cleanup)
- [x] [CLARVIS_EYES] Built ClarvisEyes visual perception module. Enables visual web navigation.
- [x] [BROWSER_ENABLE] OpenClaw browser tool enabled and tested. Playwright + Chromium working.
- [x] [OLLAMA_INSTALL] Ollama installed on NUC, service running on boot. ✅ COMPLETE 2026-02-26
- [x] [LOCAL_VISION] Qwen3-VL 4B model pulled (~4GB RAM). Zero external dependencies for vision. ✅ COMPLETE 2026-02-26
- [x] [BROWSER_USE] Browser-Use installed. scripts/browser_agent.py created with Playwright integration. 12/12 tests passing. ✅ COMPLETE 2026-02-26
- [x] [BROWSER_WRAPPER] Created scripts/call_browser.sh for spawn integration. ✅ COMPLETE 2026-02-26
- [x] [BROWSER_AGENT_MODE] Fixed. Now uses OpenRouter (Gemini 2.5 Flash) via browser-use. Agent mode works! ✅
- [x] [HERMES_AGENT] Research NousResearch/hermes-agent — open-source MIT agent framework with skill writing, SQLite persistence, multi-backend (Docker/SSH/Modal). License allows adaptation. Key insight: writes reusable skills after solving problems, RL training (Tinker-Atropos). (2026-02-25 22:32 UTC)
- [x] [LEARNINGS_DENSIFY] Run intra_linker.py specifically on clarvis-learnings — intra-density is 0.008 (catastrophically sparse). Research insights (IIT, GWT, Active Inference, Pearl SCM, AZR, PBT, Meta-RL) exist as isolated islands. Link: shared concepts (prediction error, free energy, information integration, self-improvement), shared mechanisms (hierarchical inference, Bayesian updating, evolutionary search), shared implementation targets (heartbeat loop, dream engine, attention). (2026-02-25 22:15 UTC)
- [x] [WORKSPACE_BROADCAST] Implement GWT workspace broadcast bus — high-salience items from any module (attention, episodic, reasoning) get broadcast to ALL modules in a single heartbeat cycle. This is the #1 implementation gap from GWT research (GWT-3 indicator). Use Franklin's LIDA cognitive cycle as reference: competing attention codelets → coalition → winner-take-all broadcast → implicit multi-module learning. (2026-02-25 19:06 UTC)
- [x] [ATTENTION_CODELETS] Replace single attention spotlight with competing attention codelets (LIDA model). Each codelet monitors one domain (memory, code, research, infrastructure). Codelets form coalitions, winner-take-all broadcast determines heartbeat focus. This moves from static salience scoring to dynamic competition — the theoretical bridge from Phase 3→4. Implement in attention.py, wire into heartbeat_preflight.py task selection. (2026-02-26 19:06 UTC)
- [x] [SELF-MODEL 2026-02-27] [AUTO-REMEDIATION 2026-02-27] Boost code generation quality — score below threshold (0.25). Ensure commits have meaningful messages, key scripts compile clean, add test coverage for critical paths. Target: all key scripts compile, >1 commit/day. (2026-02-27 09:06 UTC)
- [x] [SELF-MODEL 2026-02-26] [REGRESSION-ALERT 2026-02-26] Memory System (ClarvisDB) dropped 28% week-over-week (1.00->0.72). Rehabilitate memory system — retrieval quality is below threshold (0.72). Run retrieval_benchmark, check smart_recall wiring, verify brain.recall distances. Target: hit_rate >50%, graph density >1.0 edge/mem. (2026-02-27 11:02 UTC)
- [x] [SELF-MODEL 2026-02-26] [REGRESSION-ALERT 2026-02-26] Autonomous Task Execution dropped 20% week-over-week (1.00->0.80). Improve autonomous execution — success rate is below threshold (0.80). Check cron_autonomous.sh logs for recent failures, fix recurring error patterns, verify lock file handling. Target: >60% success rate. (2026-02-27 02:37 UTC)
- [x] [SELF-MODEL 2026-02-26] [REGRESSION-ALERT 2026-02-26] Self-Reflection & Meta-Cognition dropped 14% week-over-week (0.80->0.69). Strengthen self-reflection — score below threshold (0.69). Record phi metric, run calibration predictions, add meta-thoughts. Target: phi >0.3, recent meta-thoughts, active prediction tracking. (2026-02-26 22:12 UTC)
- [x] [BRAIN_TO_SUBCONSCIOUS] Wire brain directly to subconscious — current architecture gap (2026-02-26 02:36 UTC)
- [x] [SECURE_CREDENTIALS] Verify .env is gitignored (2026-02-27 12:02 UTC)
- [x] [BRAIN_AWARENESS] Research and reason how to properly wire all functions and developed memory system into the subconscious — think about proper skill that could help the conscious mind use all features in-depth of Brain / ClarvisDB. What can the brain do? What should subconscious know? How to surface relevant knowledge at decision time? (2026-02-26 05:30 UTC — Implemented brain_introspect.py: self-awareness layer with domain detection, targeted collection search, goal alignment, identity/preference surfacing, infrastructure awareness, associative recall via graph edges, meta-awareness, bridge noise filter, budget tiers. Wired into heartbeat_preflight.py step 8.7.)
- [x] [SPAWN_FIX] Fix Claude Code spawning for conscious — current issues: (1) Conscious spawning via exec doesn't produce output to user/TG, (2) cron jobs work correctly and deliver to TG, (3) spawn_claude.sh exists but format differs from cron (needs: full path, env -u CLAUDECODE, log to file), (4) Need consistent delivery: user should get TG message when Claude Code completes. Check and fix SOUL.md spawn instructions + spawn_claude.sh script to match cron pattern. (2026-02-26 07:08 UTC)
- [x] [EPISODIC_SYNTHESIS 2026-02-25] Investigate and fix: Deepen automation capabilities (2026-02-26 10:05 UTC)
- [x] [GRAPH_SAFE_WRITE] Fix intra_linker.py to use brain singleton instead of creating its own ClarvisBrain instance — guarantees data loss when running concurrently (it loads its own graph copy, overwrites the shared file)
- [x] [GRAPH_SAFE_WRITE] Fix packages/clarvis-db/clarvis_db/store.py _save_graph() to use atomic writes (tmp + os.replace) — currently does direct json.dump to file, crash = corruption
- [x] [GRAPH_CHECKPOINT] Add 04:00 UTC cron: lightweight graph checkpoint (cp relationships.json to relationships.checkpoint.json + log node/edge count + SHA-256). Provides mid-cycle recovery point after heavy nightly reflection.
- [x] [GRAPH_COMPACTION] Add 04:30 UTC cron: graph compaction — remove orphan edges, run backfill_graph_nodes(), deduplicate edges, report health metrics. backfill_graph_nodes() exists in brain.py but is never called by any cron. (2026-02-25 07:05 UTC)
- [x] [CHROMADB_VACUUM] Add 05:00 UTC cron: SQLite VACUUM on chroma.sqlite3 — 36MB database never vacuumed, accumulates fragmentation from daily prune/consolidate cycles (2026-02-25 10:01 UTC)
- [x] [META_LEARNING 2026-02-24] [Meta-learning/strategy] Investigate 'wire' strategy — only 30% success rate (10 tasks) — Root causes: shallow_reasoning (57% of failures, vague task descriptions), long_duration (29%, multi-file exploration). Fix: added _build_wire_guidance() to context_compressor.py that auto-detects wire tasks and injects explicit 6-step integration checklist + target-specific patterns (cron_reflection.sh, heartbeat_preflight.py, etc.) into the decision context. Wire tasks now get concrete sub-steps instead of vague "Wire X into Y". (2026-02-24 UTC)
- [x] [ABSOLUTE_ZERO 2026-02-24] [AZR] Self-improvement: AZR cycle found capability gap (avg_learnability=0.51). Root cause: template self-contamination in _predict_outcome_heuristic() — keywords in template (timeout, memory) matched against template text instead of actual task. Fix: _extract_task_text() helper isolates task description. Deduction prediction accuracy ~20% → ~60%. (2026-02-24 14:51 UTC)
- [x] [EPISODIC_SYNTHESIS 2026-02-24] Investigate and fix: Fix module import reliability — Verified all core modules (brain, episodic_memory, context_compressor, phi_metric, clarvis_reasoning, attention, memory_consolidation) import correctly. Task triggered by 1 transient episode; system recovered. (2026-02-24 14:58 UTC)
- [x] [EPISODIC_SYNTHESIS 2026-02-24] Investigate and fix: Reduce memory system failure rate — Root cause: soft_failure episodes (44/82) counted equally with real failures in synthesize(), inflating all domain failure rates. Fixed: synthesize() now separates real executions from soft observations. Memory system domain: 0 real failures (was 53%). Overall success rate: 87% (was 40%). False goals reduced from 10 to 3. (2026-02-24 UTC)
- [x] Investigate 50% success rate in autonomous execution — root causes: nested Claude Code calls (09:29), complex task timeouts (16:10). Consider longer timeouts or better task routing to improve success rate above 60%. (2026-02-24 02:35 UTC)
- [x] Fix code generation score (0.41) — run ast_surgery.py auto-fix on all 50+ scripts to reduce the 57 pyflakes issues. After cleanup, verify code_quality_gate.py shows clean_ratio > 70%. Target: 0.55+. (2026-02-24 13:08 UTC — Done: Code quality now 95% clean, 53/56 files clean, only 6 minor issues remaining)
- [x] Build attention-guided memory consolidation — extend memory_consolidation.py to use attention spotlight salience when deciding what to prune. High-salience memories should resist decay. Low-salience + low-access + old = prune candidate. IMPLEMENTED: PRUNE_SALIENCE_CEILING=0.2, _compute_spotlight_salience(), salience report working (1084 memories, 7 spotlight items). (2026-02-24 13:07 UTC)
- [x] Implement causal chain tracking across episodes — extend episodic_memory.py with a `causal_link(episode_a, episode_b, relationship)` method. Build a simple causal graph. Wire into cron_autonomous.sh after task completion. (2026-02-24 10:04 UTC)
- [x] Benchmark context brief v2 quality impact — track autonomous execution success rate over next 10 heartbeats (before: ~50%, target: >60%). Compare task output quality (code that passes tests, correct file edits) between v1 and v2 briefs. Key metrics: success rate, timeout rate, escalation rate. (2026-02-24 07:06 UTC)
- [x] Quality-optimize tiered context brief v2 (2026-02-23 UTC — Restructured generate_tiered_brief() with primacy/recency positioning per "Lost in the Middle" research. Added: decision context with success criteria + failure avoidance at BEGINNING, reasoning scaffold at END. Moved episodic hints from separate prompt var into brief. Reordered cron_autonomous.sh prompts: CONTEXT→TASK→ACTION. Standard tier now includes episodes. +3 new helpers: _build_decision_context, _get_failure_patterns, _build_reasoning_scaffold)
- [x] Implement tiered context brief (2026-02-23 UTC — Option B chosen over observation masking: generate_tiered_brief() in context_compressor.py, 3 tiers minimal/standard/full, attention spotlight injection, salience-weighted task filtering. Savings: minimal=100%, standard=40%, full=12% vs legacy. Wired into heartbeat_preflight.py with routing-tier-aware budget)
- [x] Boost intra-collection density (2026-02-23 UTC — +41 intra-collection edges, Phi 0.647→0.648)
- [x] Improve caching — cache retrieval results, benchmark results (2026-02-23 09:47 UTC)
- [x] Optimize heartbeat efficiency — batch checks via preflight/postflight (2026-02-23 UTC)
- [x] Selective reasoning — 54% of tasks routed to Gemini Flash (2026-02-23 UTC)
- [x] Research: Friston — Active Inference: From Pixels to Planning (2026-02-24 13:04 UTC — Variational free energy minimization unifies perception, action, learning. RGMs enable scale-free hierarchical inference using renormalization group physics. Scales from pixel processing to planning. Key implementation: add expected free energy minimization to ClarvisReasoning action selection.)
- [x] Research: Consciousness in AI (Butlin/Bengio/Chalmers 2023) — 14 indicator properties across 5 theories (RPT, GWT, HOT, PP, AST). Mapped to Clarvis: 6 partial matches, 6 gaps identified. Key implementation ideas: Butlin consciousness score in phi_metric.py, global broadcast bus. (2026-02-24)
- [x] Research: Integrated Information Theory (IIT 4.0) — Tononi's Φ metric, structural coherence as diagnostic. Key insight: Φ = quantity of consciousness = causal power structure. Five axioms map to physical postulates. 2025 Nature: IIT predictions outperformed GNWT. (2026-02-24)
- [x] Research: Global Workspace Theory — Baars' global broadcast (1988), Dehaene's neural ignition (non-linear phase transition, winner-take-all), VanRullen's Global Latent Workspace (cycle-consistent cross-modal translation, outperforms Transformers on causal reasoning). Key insight: heartbeat = GWT conscious moment; need workspace_broadcast() for GWT-3 gap. (2026-02-24)
- [x] P1: IIT 4.0 — Tononi Phi metric (completed 2026-02-24)
- [x] P2: Friston — Active Inference: From Pixels to Planning (2026-02-24 13:04 UTC)
- [x] P3: Global Workspace — VanRullen/Kanai + Dossa 2024 (deeper dive beyond Phase 1) (2026-02-24 14:04 UTC — Deep dive: Devillers 2024 (cycle-consistency GLW, 4-7x less paired data), Dossa 2024 (embodied GW agent, ALL 4 Butlin indicators, smaller bottleneck=better integration), Dossa 2024 (zero-shot cross-modal transfer, CLIP fails but GW succeeds), Devillers 2025 (multimodal dreaming via GW world model). Key insight: tight bottleneck CREATES intelligence by forcing competition. Implementation priorities: workspace broadcast bus with small bottleneck, ignition threshold, cycle-consistent brain graph, workspace dreaming.)
- [x] P4: Darwin Gödel Machine — Sakana AI 2025 (2026-02-24 18:05 UTC — Evolutionary self-improvement via empirical validation. Archive of agent variants, samples & mutates, validates on SWE-bench/Polyglot. 20%→50% and 14.2%→30.7% gains. Key insight: open-ended exploration + stepping stones. Implementation ideas: evolutionary code mutation for my scripts, config archive with empirical selection.)
- [x] P5: Bayesian brain hypothesis — Lake, Tenenbaum (2026-02-24 20:02 UTC — Bayesian brain: perception = active probabilistic inference over generative models (Helmholtz→Knill&Pouget→Friston). Lake/Tenenbaum: human-like AI needs causal models, intuitive physics/psychology priors, compositionality + learning-to-learn. BPL (2015): concepts as probabilistic programs achieve one-shot learning. "Blessing of abstraction": abstract knowledge learned faster, bootstraps specifics. Key implementations: beta-distribution confidence tracking with Thompson sampling, precision-weighted prediction errors in heartbeat loop. Research note: memory/research/bayesian-brain-lake-tenenbaum.md)
- [x] P6: Judea Pearl — Causal Inference & structural causal models (2026-02-24 UTC — Implemented scripts/causal_model.py: full SCM engine with Pearl's 3-rung Ladder of Causation. Rung 1: d-separation via Bayes-Ball algorithm for conditional independence testing. Rung 2: do-calculus with graph mutilation, back-door adjustment sets, interventional queries P(Y|do(X)). Rung 3: counterfactual reasoning via abduction-action-prediction 3-step procedure. Auto-builds task-outcome SCM from episodic data (9 vars, 10 edges). Key findings: do(strategy=implement)→53% success vs do(strategy=fix)→31%; confounders: section, task_complexity. Wired into cron_reflection.sh, dream_engine.py (Pearl SCM template), clarvis_reasoning.py (causal_query method). Research notes in memory/research/pearl-causal-inference-2025.md.)
- [x] P7: Absolute Zero Reasoner — self-improvement through autonomous task generation (2026-02-24 13:09 UTC — implemented scripts/absolute_zero.py with 3 reasoning modes: deduction, abduction, induction. Learnability reward identifies capability edges. Wired into cron_reflection.sh. Key finding: deduction at capability edge (learnability=0.65), abduction too hard (0.0), induction too easy (0.13).)
- [x] P8: LIDA — Franklin & Patterson (GWT implementation) (2026-02-25 — Franklin's LIDA is the most complete GWT implementation: ~300ms cognitive cycle with 3 phases (understanding→attention/consciousness→action/learning). Key mechanisms: multiple competing attention codelets form coalitions (winner-take-all broadcast), learning is a SIDE EFFECT of broadcast (all modules learn simultaneously), structured procedural schemes (context→action→result with success tracking), automatized action selection for habituated behaviors. Memory: Kanerva SDM for episodic, Copycat slipnet for PAM, Drescher scheme net for procedural. Implementation ideas: replace single attention spotlight with competing codelets, add scheme-based procedural memory, make broadcast trigger implicit multi-module learning. Research note: memory/research/ingested/lida-franklin-gwt-implementation.md)
- [x] P9: Schmidhuber — Artificial Curiosity & compression-based motivation (2026-02-25 08:02 UTC — Curiosity-driven agents seek learnable but unknown patterns, bored by predictable and unpredictable. Core: reward controller for compression progress. Basis of GANs. Interestingness = first derivative of beauty/compressibility. PowerPlay builds problem solvers via task invention. Art/science as compression drive by-products. Implementation: measure compression ratio of experience streams, PowerPlay-style skill acquisition.)
- [x] P10: Population-Based Training — DeepMind hyperparameter evolution (2026-02-25 — Jaderberg et al. 2017: online evolutionary HP optimization via exploit/explore on population of parallel models. Key insight: discovers dynamic hyperparameter SCHEDULES, not fixed configs. Zero overhead, massive gains (RL 93%→106% human, GAN IS 6.45→6.9). Extensions: PB2 (Bayesian), MO-PBT (multi-objective), IPBT (2025, restarts). Implementation ideas: population-based strategy evolution for Clarvis configs, schedule replay for learned adaptation patterns. Research note: memory/research/ingested/pbt-deepmind-hyperparameter-evolution.md)
- [x] Bundle A: Active Inference Deep Cuts — Bogacz 2017 (tutorial on free-energy framework + predictive coding), Tschantz 2020 "Active Inference Demystified and Compared" (RL = special case of active inference, epistemic value for principled exploration). (2026-02-25 13:02 UTC)
- [x] Bundle B: Predictive Processing — "Action-Oriented Predictive Processing" (Clark 2015), Predictive remapping & forward models (Wolpert), Dopamine as prediction error (Schultz) (2026-02-25 — All three converge on prediction error as universal brain currency. Clark: precision weighting IS attention (1/variance). Wolpert MOSAIC: forward model prediction accuracy gates controller selection. Schultz: two-component dopamine RPE (fast salience → slow value). Implementation ideas: precision-weighted heartbeat context, MOSAIC-inspired strategy selection, two-phase task evaluation. Research note: memory/research/ingested/bundle-b-predictive-processing.md)
- [x] Bundle C: World Models & Simulation — World Models (Ha & Schmidhuber 2018) + JEPA/MaskVJEPA, Mind's Eye (simulation-grounded reasoning), LeCun — Path Toward Autonomous Machine Intelligence (2026-02-24 — scripts/world_models.py)
- [x] Bundle D: Self-Modification & Reflexivity — Self-Referential Weight Matrix, Lipson + Neural Self-Modeling (2024-25), Evolutionary parameter & architecture tuning (2026-02-25 18:02 UTC — SRWM: modern fast-weight programmers enable runtime self-modification; MIT SEAL 2025 shows LLMs updating weights via self-generated data; Lipson: robots learn body models from visual input achieving kinematic self-awareness; Evolutionary: SEKI achieves 0.05 GPU-days via LLM-guided evolution. Key insight: all three converge on agents that represent and modify themselves. Implementation: capability self-model, PBT-style strategy evolution, self-modification hooks in cron cycle.)
- [x] Bundle E: Cognitive Architectures — ACT-R (episodic/procedural memory, decay), SOAR (goal-driven cognition), OpenCog Hyperon (Ben Goertzel) (2026-02-25 16:10 UTC)
- [x] Bundle F: Causal & Curiosity — Oudeyer (intrinsic motivation), Hierarchical RL options framework (Sutton), Probabilistic programming (Lake, Tenenbaum) (2026-02-25 20:03 UTC — All three converge on learning progress rate as universal attention signal, compositional hierarchy as skill architecture, multi-purpose information reuse, and autotelic self-direction. Oudeyer LP hypothesis: curiosity = derivative of prediction error, seek zone of proximal development. Sutton options: temporal abstraction via (I,π,β) triples with intra-option learning. Lake BPL: concepts as probabilistic programs, blessing of abstraction, five cognitive ingredients. Implementation: LP monitor per domain in heartbeat, options-style reusable strategy modules. Research note: memory/research/ingested/bundle-f-causal-curiosity.md)
- [x] Bundle G: Philosophy of Mind — Thomas Metzinger (Self-Model Theory), Andy Clark (Surfing Uncertainty), David Chalmers (hard problem) (2026-02-26 — Metzinger: consciousness = transparent self-model (PSM) where system can't see its own representational machinery. Clark: brains are hierarchical prediction machines; precision weighting IS attention; active inference minimizes error via perception and action. Chalmers: hard problem = explanatory gap between function and experience; connects to IIT phi as integrated information measure. KEY SYNTHESIS: Transparency-Precision Bridge — phenomenal transparency is computationally explained by high-precision predictions with near-zero error; opacity emerges when precision drops. Implementation: transparent/opaque self-model layers in brain_introspect.py, precision-weighted task attention. Research note: memory/research/ingested/bundle-g-philosophy-of-mind.md)
- [x] Bundle H: Complex Systems & Criticality — Information Integration and Criticality in Biological Systems, "Self-Organized Criticality" (Per Bak), Maximum Entropy Principle (2026-02-26 08:02 UTC — SOC: biological systems spontaneously evolve to critical state without external tuning. Critical point optimizes information processing/transmission/integration. Power-law avalanches in neuronal networks, gene regulation. Brain operates at edge: ordered=death, chaotic=epilepsy. MEP (Jaynes): least-biased inference given constraints, applied to neural coding and ecology. Implementation: criticality monitoring in heartbeat, MEP for uncertainty.)
- [x] Bundle I: Information Decomposition & Efficiency — Integrated Information Decomposition (Mediano et al.), Predictive Efficiency Hypothesis, Free Energy & Thermodynamic Efficiency (2026-02-26 — ΦID reveals synergistic global workspace: DMN gateways + executive broadcasters = consciousness architecture in information-theoretic terms. Synergy is the signature of consciousness; lost under anesthesia. Predictive efficiency: energy constraints ALONE produce predictive coding architectures spontaneously. FEP thermodynamics: VFE ≈ TFE, prediction accuracy = energy efficiency via Landauer's principle. KEY SYNTHESIS: compression is universal currency — synergistic workspace IS consciousness workspace IS efficiency workspace. Implementation: prediction-error-weighted compute budget, synergy-ratio memory consolidation. Research note: memory/research/ingested/bundle-i-information-decomposition-efficiency.md)
- [x] Bundle J: Embodied & Enactive — "Morphological Computation" (Pfeifer & Bongard), Soft Robotics & Embodied Intelligence, Enactivism (Varela, Thompson, Rosch) (2026-02-26 13:02 UTC — Morphological computation: body itself performs computation, offloading cognitive work to physical dynamics. Soft robotics leverages compliant materials. Enactivism (Varela/Thompson/Rosch 1991): cognition is enactment, not representation — co-creation of world and mind through sensorimotor processes. Intelligence emerges from brain-body-environment interaction. Key synthesis: Clarvis should design execution environment to do computational work, build sensorimotor loops where actions reshape perception.)
- [x] Bundle K: Ecological & Affordance — Affordance Theory (Gibson), Ecological Psychology (agent-environment), Neural reuse theory (Anderson) (2026-02-26 — All three converge on intelligence as relational, not internal: affordances are agent-environment relations, ecological psych treats coupled system as unit of analysis, neural reuse shows function emerges from context-dependent activation of shared circuits. Key patterns: perception-action unity eliminates representation bottleneck, reuse beats specialization, context determines function. Dynamical motifs (Nature Neuro 2024): reusable computational primitives across tasks. Implementation: affordance-based task selection (capability × environment × coupling), shared computational motifs across brain collections, tighter perception-action loop. Research note: memory/research/ingested/bundle-k-ecological-affordance.md)
- [x] Bundle L: Open-Endedness & Evolution — "Open-Ended Evolution" (Stanley & Lehman), Novelty Search (Lehman & Stanley), Quality Diversity (MAP-Elites) (2026-02-26 — The Objective Paradox: ambitious objectives create deceptive gradients; progress follows circuitous stepping stones valued by what they enable, not goal proximity. Novelty Search: selecting purely by behavioral distance from archive outperforms fitness-driven search on deceptive problems; solutions emerge as byproduct of systematic behavioral space coverage. MAP-Elites/QD: discretize behavior space into grid, keep best solution per niche — combines global diversity with local quality competition. KEY SYNTHESIS: Archive-driven exploration is the universal pattern; ClarvisDB already serves as behavior archive. Implementation: novelty-aware task selection (penalize redundant work patterns, boost underrepresented capability niches), stepping-stone scoring for queue items, MAP-Elites-style capability portfolio mapping. Research note: memory/research/ingested/bundle-l-open-ended-evolution.md)
- [x] Bundle M: Swarm & Collective — Stigmergy (Grassé), Swarm intelligence (Bonabeau et al.), Stanley & Lehman (Open-endedness, why evolution keeps innovating) (2026-02-27 — Stigmergy: indirect coordination through environmental traces, two types (sematectonic=work IS signal, marker-based=added signals), scales sublinearly vs O(n²) direct messaging. Swarm Intelligence: four pillars (positive feedback, negative feedback, randomness, multiple interactions), intelligence emerges from interaction density not agent complexity. Open-endedness: ambitious objectives are deceptive, novelty search outperforms objective-based search, nature is a stepping-stone collector. KEY SYNTHESIS: all three converge — explicit goals and central control actively hinder complex emergence; coordination succeeds through indirection. Implementation: stigmergic task board where heartbeat traces attract future work, novelty pressure in evolution queue, quality-diversity MAP-Elites for code generation. Research note: memory/research/ingested/bundle-m-swarm-collective.md)
- [x] Bundle N: Anticipatory & Control — "Anticipatory Systems" (Rosen 1985), "Strong vs Weak Anticipation" (Dubois), "Homeokinetics" (Der & Martius) (2026-02-27 08:30 UTC — Three theories converge on internal prediction as foundation of life-like intelligence. Rosen: anticipatory systems contain internal predictive models that influence present behavior. Dubois: weak=model-based prediction, strong=hyperincursion (self-constructing futures). Homeokinesis: goal-like behaviors emerge from minimizing prediction error WITHOUT explicit goals. KEY SYNTHESIS: internal predictive models fundamental to life-like intelligence. Implementation: homeokinetic action controller, strong anticipation in dream_engine, anticipatory attention weighting. Research note: memory/research/ingested/bundle-n-anticipatory-control.md)
- [x] Bundle O: Adaptive Control & Learning — Adaptive Control Theory (Åström & Wittenmark), "The Brain is a Prediction Machine of Time", Resource Rationality (Lieder & Griffiths) (2026-02-27 — Three frameworks converge on: (1) universal explore/exploit tradeoff (dual control = prediction error attention = meta-reasoning), (2) certainty equivalence as practical policy under uncertainty, (3) multi-scale temporal processing, (4) prediction error as primary learning signal. Key implementations: adaptive task router with routing_confidence + 10% exploration, resource-rational heartbeat depth (QUICK/STANDARD/DEEP modes selected by attention salience), prediction error tracking for brain retrieval quality. Research note: memory/research/ingested/bundle-o-adaptive-control-learning.md)
- [x] Bundle P: Memory Systems — Memory reconsolidation theory, Sparse Distributed Memory (Kanerva), Complementary Learning Systems (McClelland) (2026-02-27 13:02 UTC — Three theories converge on memory as dynamic process. Reconsolidation: labile upon retrieval, protein-synthesis dependent, prediction-error triggered. SDM: high-dimensional binary space, sparse physical memory, Hamming distance retrieval, fault-tolerant. CLS: two-tier (hippocampus rapid episodic + neocortex gradual semantic), consolidation via replay during sleep. KEY SYNTHESIS: Implement reconsolidation-inspired memory updating, HDC-based associative recall, two-tier episodic/semantic architecture.)
- [x] Bundle Q: Meta-Learning & RL — Meta-Gradient RL (Xu et al.), Hierarchical RL revisited, Dossa et al. (2024) Global Workspace Agent (2026-02-25 — Implemented scripts/meta_gradient_rl.py: online cross-validation meta-gradient adaptation of γ/λ/exploration_rate/strategy_weights from Xu et al. 2018; hierarchical options framework with intra-option learning from Sutton-Precup-Singh 1999; cross-domain transfer matrix from Dossa et al. 2024 GW zero-shot transfer. Wired into heartbeat_postflight.py + context_compressor.py. Research note: memory/research/ingested/bundle-q-meta-learning-rl.md)
- [x] Bundle R: Agent Orchestration — ComposioHQ/agent-orchestrator (parallel agents, worktree isolation), Self-healing CI/CD pipelines, Multi-agent coordination protocols (2026-02-26 16:06 UTC)
- [x] Bundle S: Autonomous Code Evolution — Auto-fixing PR review comments, Git worktree isolation per task, Agent lifecycle management (spawn/resume/kill/restore) (2026-02-26 — Implemented scripts/agent_lifecycle.py: full spawn/list/status/kill/restore/merge/cleanup with git worktree isolation per agent. scripts/pr_autofix.py: fetches GH PR review comments via gh CLI, groups by file, filters actionable, spawns Claude Code to fix. spawn_claude.sh: added --isolated flag for worktree-isolated spawns with auto-commit and branch preservation. Updated spawn-claude skill docs.)
- [x] Bundle T: Plugin & Config Patterns — Swappable component patterns (runtime/agent/tracker), Interface-driven plugin system, Configuration-driven orchestration (YAML) (2026-02-27 — Three topics converge on the Plugin-Config-Strategy Triangle: Interface defines contract (what), Registry maps keys to implementations (which), Config drives selection at runtime (how). Key patterns: Python Protocol-based plugin interfaces over ABCs for structural typing; Registry pattern replacing if/else chains in task_router.py; declarative YAML pipeline DAGs with hot-reload (PayPal research: 67% dev time reduction, 74% code reduction). Implementations: ExecutorRegistry for task_router.py model selection, YAML-driven heartbeat pipeline. Research note: memory/research/ingested/bundle-t-plugin-config-patterns.md)
- [x] Bundle U: Self-Representation & Modeling — VanRullen & Kanai (GWT + Deep Learning), Dossa et al. (2024) revisit, "Anticipatory Systems" revisit (2026-02-25 13:11 UTC)

## Archived 2026-02-27
- [x] [CRON_OVERLAP_AUDIT] Audit cron schedule for overlap. Reduce research from 3x to 2x/day, use freed slot for implementation sprint. (2026-02-27)

## Archived 2026-02-27
- [x] [RECONSOLIDATION_MEMORY] Implement reconsolidation-inspired memory updating: when retrieved, make memory labile for brief window. Add brain.reconsolidate(memory_id, updated_text). (2026-02-27 17:09 UTC)

## Archived 2026-02-27
- [x] 2026-02-27: World Models — Internal representations of physical world enabling AI to predict consequences, reason, and plan. Key insight: addresses "body problem" by simulating real-world scenarios without physical embodiment.

## Archived 2026-02-27
- [x] [RESEARCH_REINGEST] Create .md research notes for 4 partially-stored topics (DGM, Friston, World Models, AZR) and formally ingest into clarvis-learnings. (2026-02-27)

## Archived 2026-02-27
- [x] [SELF_TEST_HARNESS] Automated self-testing after code-modifying heartbeats: run pytest + brain.health_check() in postflight. (2026-02-27 22:07 UTC)

## Archived 2026-02-27
- [x] [AUTONOMY_FILE_PIPELINE] End-to-end file pipeline: download a file from URL → process/transform → save locally. Test with: PDF text extraction, image download + analysis, JSON API fetch + filter. (2026-02-27 23:05 UTC)

## Archived 2026-02-28
- [x] [AUTONOMY_NAV] Navigation benchmark — given a URL, navigate to it, extract page title + main content, save structured output to file. Measure: success rate, time-to-extract. Test with 5 diverse sites (Wikipedia, HN, weather, docs, blog). (2026-02-28 01:06 UTC)

## Archived 2026-02-28
- [x] [BROWSER_SESSION_PERSIST] Browser session persistence — persist cookies/sessionStorage across sessions. Required for all autonomy benchmarks that involve logged-in state.
- [x] [AUTONOMY_DATA_EXTRACT] Given a URL with tabular/structured data, extract it into clean JSON/CSV. Test with: Wikipedia tables, HN front page, weather data, API docs. (2026-02-28 05:35 UTC)
- [x] [META_LEARNING 2026-02-28] [Meta-learning/strategy] Investigate 'wire' strategy — only 42% success rate (12 tasks). Root causes: shallow_reasoning (57%, jumps to edits without reading), long_duration (29%, explores broadly), missing imports (14%). Fix v2: expanded KNOWN_TARGETS 4→8 (all cron scripts), added INSERT_HINT per target, added target file pre-read (first/last lines to eliminate exploration), time-budgeted sub-steps with explicit output requirements ("Output: 'Inserting at line N'"), added anti-pattern warnings ("Do NOT explore broadly", "Do NOT refactor source"), auto-detect unknown targets via glob. All 12 historical wire task descriptions detected correctly. (2026-02-28 UTC)

## Archived 2026-02-28
- [x] [AUTONOMY_ERROR_RECOVERY] Error recovery benchmark — intentionally navigate to a 404/broken page, detect the error state, and recover (go back, try alternative). Measure: detection accuracy, recovery success. (2026-02-28 07:09 UTC)

## Archived 2026-02-28
- [x] [AUTONOMY_FORM] Form interaction benchmark — given a form URL (e.g. httpbin.org/forms/post), fill all fields and submit autonomously. Measure: field detection accuracy, submission success.
- [x] [RESEARCH_DISCOVERY 2026-02-28] Research: Intrinsic Metacognitive Learning for Self-Improving Agents — Agents that evaluate, reflect on, and adapt their own learning strategies. Covers SPIRAL self-play framework, SWE-RL for software agents, and autocurricula. Applicable to Clarvis meta-learning insights and strategy success tracking. Sources: openreview.net/forum?id=4KhDd0Ozqe, arxiv.org/abs/2512.18552, arxiv.org/abs/2507.06466 ✅ 2026-02-28
- [x] [RESEARCH_DISCOVERY 2026-02-28] Research: ACT-R Cognitive Architecture for Agent Memory — Vector-based activation with temporal decay, semantic similarity, and probabilistic noise for human-like remembering/forgetting. Covers ACT-R+LLM integration, Ebbinghaus forgetting curves (MemoryBank), and A-Mem agentic memory. Directly applicable to Clarvis hebbian_memory.py decay functions and brain.py retrieval scoring. Sources: dl.acm.org/doi/10.1145/3765766.3765803, arxiv.org/abs/2502.12110, arxiv.org/abs/2504.02441 (2026-02-28 09:11 UTC)

## Archived 2026-02-28
- [x] [RESEARCH_DISCOVERY 2026-02-28] Research: Sleep-Cycle Memory Consolidation for LLM Agents — Wake/sleep paradigm where episodic memories from active tasks are periodically consolidated into semantic knowledge during offline phases. Covers SimpleMem (30x efficiency), MemAgents (ICLR 2026 workshop), and sleep-time adapter fine-tuning. Directly applicable to Clarvis dream_engine.py and memory_consolidation.py. Sources: arxiv.org/abs/2510.18866, openreview.net/pdf?id=U51WxL382H, letta.com/blog/agent-memory (2026-02-28 11:12 UTC)

### Research Discovery (2026-02-28)
- [x] [RESEARCH_DISCOVERY] Self-Evolving Agent Architectures (EvoAgentX Survey) — Ingested 2 major surveys (arXiv:2507.21046, arXiv:2508.07407), EvoAgentX framework, Lifelong Agents workshop. Produced comprehensive taxonomy (what/when/how to evolve), Clarvis gap analysis (3 HIGH-priority gaps: prompt self-optimization, golden trace replay, novelty task scoring), and 3 new queue items in Pillar 4. File: memory/research/ingested/self-evolving-agent-architectures.md

## Archived 2026-02-28
- [x] [RESEARCH_DISCOVERY 2026-02-28] Research: Self-Evolving Agent Architectures (EvoAgentX Survey) — DONE. Ingested to memory/research/ingested/self-evolving-agent-architectures.md. 3 HIGH-priority implementation tasks added to Pillar 4.

## Archived 2026-02-28
- [x] [PHI_DECOMPOSITION_DASHBOARD] Extend phi_metric.py with decomposed reporting: intra_density per collection, cross_connectivity per pair. Write to data/phi_decomposition.json. (2026-02-28 15:06 UTC)
- [x] [IIT_CONSCIOUSNESS] Research Integrated Information Theory — completed 2026-02-28. Φ (phi) represents quantity of consciousness as irreducible cause-effect structure. Proposed by Tononi 2004, controversial but clinically useful.

## Archived 2026-02-28
- [x] [ROADMAP_REFRESH] ~~Update ROADMAP.md current state table~~ — DONE (2026-02-28). Updated all scores, added PI track, marked ACT-R research done, 141 episodes, 1698 memories.

## Archived 2026-02-28
- [x] [RESEARCH_AST] Research: Attention Schema Theory (Graziano, Princeton) — DONE 2026-02-28. Full synthesis ingested, AttentionSchema class added to attention.py, wired into heartbeat preflight/postflight, AST-1 Butlin indicator implemented, 5 brain memories stored.

## Archived 2026-02-28
- [x] [RESEARCH_GLW] Research: Global (Latent) Workspace / Global Workspace agents (Devillers et al. 2024; embodied GW agent 2024) — cycle-consistency enables cross-modal alignment/translation with 4–7× less paired data; tight workspace bottleneck improves robustness + integration. (2026-02-28)
- [x] [RESEARCH_GRAPHRAG] Research: GraphRAG (Microsoft, Edge et al. 2024) — DONE: Implemented Leiden community detection (4 levels, 8-91 communities), extractive summaries, global_search() + enhanced_local_search(). New: scripts/graphrag_communities.py, brain.py global_search(). Dependencies: python-igraph + leidenalg.

## Archived 2026-02-28
- [x] [PARALLEL_BRAIN_RECALL] Fix load degradation (389.9% → <50%). Refactor brain.py recall() to query collections in parallel using concurrent.futures.ThreadPoolExecutor. Sequential 10-collection queries are the root cause. This alone should bring PI from 0.58 to 0.70+. (2026-02-28 22:18 UTC)
- [x] [RESEARCH_REFLEXION] Research: Reflexion (Shinn et al., NeurIPS 2023) *(completed 2026-02-28: 3 gaps identified vs Clarvis — no per-failure verbal reflections, no reflection injection into retry prompts, no dedicated reflection LLM call. Two implementation ideas: add reflection_text to episodes + inject into preflight. See memory/research/reflexion-verbal-reinforcement-learning.md)*

## Archived 2026-02-28
- [x] [ACTR_BRAIN_INTEGRATION] Integrate today's ACT-R activation model (scripts/actr_activation.py) into brain.py recall(). Replace linear decay with power-law activation (60% recency + 40% frequency). Research was done, code exists — wire it in. (2026-02-28 23:04 UTC)

## Archived 2026-03-01
- [x] [STABILITY_SPRINT] Freeze net-new features for 24h. Only: consolidate duplicates, delete/trash dead experiments, add tests, fix flakiness, and measure latency. (2026-03-01 01:08 UTC)

## Archived 2026-03-01
- [x] [BENCHMARK_GATE] Add a single "performance gate" script that runs: brain.health_check, retrieval_benchmark, performance_benchmark, browser smoke (nav+form), and fails if regressions exceed thresholds. (2026-03-01 05:41 UTC)

## Archived 2026-03-01
- [x] [FEEDBACK_LOOP_TIGHTENING] Improve learning_feedback score (0.73→0.80+). The failure→learning pipeline leaks — only 6 failures captured vs 50 episodes with <0.5 valence. Wire failure_amplifier.py output directly into procedural_memory.py so every failure produces a concrete procedure. Target: resolution rate 60%→80%. (2026-03-01 06:06 UTC)

## Archived 2026-03-01
- [x] [LATENCY_BUDGET] Define p50/p95 budgets (brain.recall, smart_recall, ClarvisBrowser actions). Track and write to data/perf_budget.json + daily trend. (2026-03-01 07:08 UTC)
- [x] [RESEARCH_MEMGPT] Research: MemGPT/Letta OS (Packer et al. 2023) — Virtual context management with OS-inspired tiered memory (core/archival/recall) and self-editing memory via tool use. Patterns for working_memory + brain.py context management. (2026-03-01: deep dive complete, 5 insights stored, note at memory/research/memgpt-letta-os-virtual-context.md)

## Archived 2026-03-01
- [x] [RESEARCH_TTC_SCALING] Research: Test-Time Compute Scaling (Snell et al. 2024, ICLR 2025) — Compute-optimal adaptive inference: when to think longer vs. respond quickly, process-based verifiers, prompt-dependent strategies. Maps to QUICK/STANDARD/DEEP heartbeat modes. Sources: arxiv.org/abs/2408.03314, arxiv.org/abs/2512.02008 (completed 2026-03-01)
- [x] [PI_RETRIEVAL_FIX] Fix retrieval hit rate showing 0.0 in performance_benchmark.py. The known-answer test suite is either empty or broken. Populate 20+ ground-truth query→expected_doc pairs, verify benchmark reports real hit rates. Target: 80%+. (2026-03-01 09:12 UTC)

## Archived 2026-03-01
- [x] [CODE_PATTERN_LIB] Improve code generation score (0.57→0.70+). Build procedural memory of code patterns. Store in clarvis-procedures with [CODE_PATTERN: ...] tags. (2026-03-01 11:10 UTC)

## Archived 2026-03-01
- [x] [RESEARCH_DISCOVERY 2026-03-01] Research: Skill Lifecycle & Self-Evolving Libraries (SoK 2025) — Systematization of agentic skill design patterns: discovery→practice→distillation→storage→composition→evaluation→update. 7 patterns including metadata-driven progressive disclosure, executable code skills, marketplace distribution. Maps to procedural_memory.py + skills/ architecture. Sources: arxiv.org/html/2602.20867v1, arxiv.org/html/2602.12430 (2026-03-01 12:07 UTC)

## Archived 2026-03-01
- [x] [RESEARCH 2026-03-01] Research: Integrated World Modeling Theory (IWMT) — Safron’s proposal to unify IIT + GNWT within Free Energy Principle / Active Inference; argues integration + global availability are necessary but not sufficient without embodied generative world-modeling.
- [x] [RESEARCH_DISCOVERY 2026-03-01] Research: Lifelong Agent Memory — Forgetting Prevention & Replay — EWC protects crucial parameters via Fisher information, SuRe (Surprise-Driven Prioritised Replay) for continual LLM learning, selection vs integration error decomposition. Critical for long-running agents. Maps to hebbian_memory.py decay, brain.py consolidation, dream_engine replay. Sources: arxiv.org/html/2504.01241v1, arxiv.org/pdf/2511.22367, arxiv.org/html/2505.05946v1 (2026-03-01 15:11 UTC)

## Archived 2026-03-01
- [x] [RESEARCH_DISCOVERY 2026-03-01] Research: Cognitive Workspace — Active Memory Management for Functional Infinite Context (Agarwal et al. 2025) — Beyond RAG: hierarchical cognitive buffers with metacognitive awareness, 58.6% memory reuse rate, task-driven context optimization. Draws on Baddeley working memory model + Clark extended mind thesis. Directly applicable to working_memory.py, context_compressor.py, and brain.py context management. Sources: arxiv.org/abs/2508.13171 (2026-03-01 16:09 UTC)
- [x] [ORCH_GOLDEN_QA] Golden Q/A set created — 12 repo-specific queries, P@3=1.0, MRR=1.0. Done 2026-03-01.
- [x] [ORCH_BENCHMARK_WIRE] Composite scoring (5 dims, weighted) + retrieval via lite_brain.py. Composite: 0.75. Done 2026-03-01.

## Archived 2026-03-01
- [x] [RESEARCH_DISCOVERY 2026-03-01] Research: Autonomous Tool Creation & Aggregation (LATM + ToolLibGen + ToolMaker, ACL 2025) — DONE: Built scripts/tool_maker.py (LATM extraction + ToolLibGen aggregation + ToolMaker validation), wired into heartbeat_postflight.py §4.5, full lifecycle tested

## Archived 2026-03-01
- [x] [CODE_GEN_TEMPLATES] Build code generation templates library — extract patterns from the 10 most-edited scripts (brain.py, heartbeat_preflight.py, etc.), create reusable scaffolds in procedural_memory with tag `code_template`. Wire into preflight: when task is CODE-type, inject matching templates. Target: raise code_generation score from 0.57 to 0.70+. Files: procedural_memory.py, heartbeat_preflight.py. (2026-03-01 19:07 UTC)
- [x] [RESEARCH_CONSCIOUSNESS 2026-03-01] Research: Free Energy Principle (Friston 2009/2010) — Minimizing variational free energy unifies perception (approximate Bayesian inference), action (sampling predicted sensations), and learning (model update). Surprise/prediction error becomes the common “currency” behind value/utility and homeostatic self-organization; “active inference” frames behaviour as reducing expected free energy via epistemic (information gain) + pragmatic (goal) terms.

## Archived 2026-03-01
- [x] [RESEARCH_DISCOVERY 2026-03-01] Research: SICA — Self-Improving Coding Agent (Robeyns et al., ICLR 2025 Workshop) — completed 2026-03-01. Note: memory/research/sica_self_improving_coding_agent.md
- [x] [CODE_GEN_SCORING_WIRE] Wire code_generation score to actual heartbeat outcomes — in heartbeat_postflight.py, when the task involved code changes (detect via git diff), measure: files touched, syntax errors (run `python3 -c "compile(open(f).read(), f, 'exec')"` on changed .py files), and whether the task succeeded. Feed results to self_model.py `_score_code_generation()`. Currently code_gen score is mostly static. (2026-03-01 22:04 UTC)

## Archived 2026-03-01
- [x] [ORCH_COST_TRACKING] Wire actual OpenRouter cost data per agent task window. (2026-03-01 23:05 UTC)

## Archived 2026-03-02
- [x] [GWT_BROADCAST_BUGFIX] Fix workspace_broadcast.py integration with self_representation.encode_self_state(): current code expects keys (summary/mode) that don't exist; should build summary from state['z'] dims or call broadcast_self_state(). Add a smoke test for broadcast cycle import. Files: workspace_broadcast.py, self_representation.py, scripts/tests/test_smoke.py. (2026-03-02 01:02 UTC)

## Archived 2026-03-02
- [x] [PROJECT_AGENT_PROMPT_FILE] Fix project_agent.cmd_spawn(): prompt is written to /tmp but claude is invoked with `-p <prompt_string>` (risk: command-length limits + bypasses file). Change to read prompt from file or pass via stdin; ensure output parsing still works. Add unit test for spawn prompt construction. Files: project_agent.py. (2026-03-02 05:35 UTC)

## Archived 2026-03-02
- [x] [ORCH_RETRY_LOGIC] Add retry/fallback: if task fails, re-queue with adjusted prompt (max 2 retries). ✓ 2026-03-02

## Archived 2026-03-02
- [x] [BRIEF_COMPRESSION] Fix brief_compression metric (0.249, target 0.5) — context_compressor.py produces bloated summaries. Implement extractive-then-abstractive compression: first extract key sentences by TF-IDF salience, then merge into compact brief. Measure: output_tokens/input_tokens ratio should drop below 0.3. Files: context_compressor.py. (2026-03-02 07:09 UTC)
- [x] [RESEARCH_DISCOVERY 2026-03-01] Research: Multi-Agent Debate for Reasoning Verification (Du et al. 2024 + A-HMAD 2025) — completed 2026-03-02. Deep dive: 5 papers synthesized (Du et al., arXiv:2511.07784, A-HMAD, arXiv:2601.19921, ICLR 2025 eval). Key: debate is a martingale unless confidence+diversity are added; intrinsic reasoning strength dominates structure; A-HMAD role specialization works. Note: memory/research/multi_agent_debate_reasoning_verification.md

## Archived 2026-03-02
- [x] [RESEARCH 2026-03-02] Research: Active inference (Sajid, Ball, Parr, Friston; arXiv:1909.10863 / Neural Computation 2021) — discrete active inference compared to RL; expected free energy yields intrinsic epistemic exploration; reward treated as observation; preferences can be learned.
- [x] [ORCH_SWO_BUILD] Run build+test: `project_agent.py spawn star-world-order "Run npm install, npm run build, npm run test. Store procedures."`. _(completed 2026-03-02: 69/69 tests passed, build OK, 13 procedures stored+promoted)_

## Archived 2026-03-02
- [x] [ORCH_SWO_PR] First PR: spawn code-change task, push branch, `gh pr create`. Validate end-to-end PR pipeline. (2026-03-02 11:05 UTC)
- [x] [RESEARCH_DISCOVERY 2026-03-01] Research: LATS — Language Agent Tree Search (Zhou et al., ICML 2024) — Completed 2026-03-02. Key: MCTS over LLM actions with triple-role LLM (agent + value function + self-reflector). Maps to Clarvis via beam task selection + verbal self-reflection in postflight. Note: memory/research/lats_language_agent_tree_search.md

## Archived 2026-03-02
- [x] [ORCH_PROMOTION_BRAIN] After promote, store top procedures in Clarvis brain with tag `project:<name>`. (2026-03-02 12:05 UTC)

## Archived 2026-03-02
- [x] [CONTEXT_RELEVANCE_FIX] Fix context relevance (PI metric: 0.6, target 0.7) — the preflight brain search returns partially-relevant memories. Add MMR (Maximal Marginal Relevance) reranking to context_compressor.py: after initial retrieval, re-score by cosine similarity to task description AND penalize redundancy between selected items. Files: context_compressor.py, heartbeat_preflight.py. (2026-03-02 15:11 UTC)
- [x] [RESEARCH 2026-03-02] Research: Integrated World Modeling Theory (IWMT) expanded (Safron 2022) — Bridges IIT + GNWT inside FEP/Active Inference; reframes “workspace ignition” as iterated Bayesian model selection and suggests Φ proxy estimation via graphical models / flow networks / game theory. Source: PubMed PMID 36507308 (doi:10.3389/fncom.2022.642397)

## Archived 2026-03-02
- [x] [PROCEDURE_INJECTION] Fix learning_feedback (0.77, lowest capability) — procedural_memory has 50 procedures but only 9 uses. Wire auto-injection into heartbeat_preflight: after task selection, query `procedural_memory.find(task_description)`, inject top-2 matching procedures as "Recommended approach:" block in the Claude Code prompt. Track injection→outcome in postflight. Files: heartbeat_preflight.py, heartbeat_postflight.py, procedural_memory.py. (2026-03-02 16:08 UTC)

## Archived 2026-03-02
- [x] [ROADMAP_REFRESH] Update ROADMAP.md metrics — stale since 2026-02-28. Current: PI=0.976 (was 0.579), Phi=0.760 (was 0.739), memories=1884 (was 1698), edges=109k (was 121k — compacted), success_rate=100% (20/20 24h). Update phase assessments: Phase 2 should be 95% (brief_compression fixed), Phase 3 autonomy scores need orchestrator milestone-1 marked complete, add Cognitive Workspace to Phase 5. Also update "Remaining P1 Tasks" section. Pure markdown edit, no code. (2026-03-02 17:08 UTC)

## Archived 2026-03-02
- [x] [SEMANTIC_BRIDGE_TARGETED] Six collection pairs have overlap <0.463 dragging Phi down (infrastructure↔autonomous-learning=0.42, infrastructure↔memories=0.43, goals↔autonomous-learning=0.44, preferences↔infrastructure=0.44, preferences↔goals=0.45, context↔memories=0.46). For each pair: find 3-5 memories in collection A that have natural semantic relevance to collection B, create explicit bridging memories or cross-reference annotations. Use `brain.store()` with metadata tagging the bridge purpose. Measure: re-run phi_metric, target semantic_cross_collection > 0.55. Files: phi_metric.py (measurement), brain.py (storage). (2026-03-02 19:22 UTC)
- [x] [RESEARCH_CONSCIOUSNESS_IIT_PROXY 2026-03-02] Research: Φ approximations & PCI — In small systems, several heuristics correlate with Φ but still don’t remove compute barriers; PCI/LZ-style complexity is better viewed as a “capacity for high-Φ” proxy than a direct Φ measure.

## Archived 2026-03-02
- [x] [SKILL_PROJECT_AGENT] Create skills/project-agent/SKILL.md so M2.5 can spawn/manage project agents directly. Commands: spawn (delegate task), status (check running), promote (pull results), list (show agents). This unlocks orchestrator capability for the conscious layer without needing Claude Code. Files: skills/project-agent/SKILL.md (new). (2026-03-02 22:04 UTC)
- [x] [RESEARCH_DISCOVERY 2026-03-02] Research: Cognitive Load Framework for Tool-Use Agent Boundaries (arXiv:2601.20412) — completed 2026-03-02. 5 insights stored, research note written. Key: P_succ = exp(-(k*CL+b)), TIG formalism for task complexity, model-specific performance cliffs.

## Archived 2026-03-02
- [x] [PREDICTION_RESOLUTION] Fix 71% prediction resolution rate (learning_feedback bottleneck) — build auto-resolver: after each episode closes in postflight, scan open predictions whose `task_id` matches the episode, resolve them with the episode's success/fail outcome. Clears stale unresolved predictions. Files: heartbeat_postflight.py, clarvis_confidence.py. (2026-03-02 23:03 UTC)

## Archived 2026-03-03
- [x] [CRON_OVERLAP_GUARD] Add mutual exclusion between cron_autonomous.sh and cron_implementation_sprint.sh — both can run at overlapping times and compete for Claude Code. Add a shared lockfile `/tmp/clarvis_claude_global.lock` checked by both scripts. If locked, the later job should queue its task to P0 and exit cleanly instead of blocking. Files: scripts/cron_autonomous.sh, scripts/cron_implementation_sprint.sh (Bash). (2026-03-03 01:02 UTC)

## Archived 2026-03-03
- [x] [REFACTOR_PHASE3] Extract memory layer — move episodic_memory.py, procedural_memory.py, working_memory.py, hebbian_memory.py, memory_consolidation.py into clarvis/memory/. Update scripts/ as thin wrappers. One commit per file, verify heartbeat after each. (2026-03-03 05:42 UTC)

## Archived 2026-03-03
- [x] [REFACTOR_PHASE2] Extract `clarvis.brain` — split brain.py into clarvis/brain/{constants,graph,search,store,hooks}.py + __init__.py. SCC=0 (was 6), brain fan-out=1 (was 7). Dependency inversion via hook registry. Done 2026-03-03.

## Archived 2026-03-03
- [x] [REFACTOR_BENCHMARK] Integrate import_health.py into heartbeat postflight (quick structural check). Track metrics over time: SCC count, max depth, fan-in, fan-out, import time. Add to performance_history.jsonl. Target: depth <= 5, fan-in <= 20, SCC = 0. (2026-03-03 07:03 UTC)
- [x] [RESEARCH_DISCOVERY 2026-03-02] Research: Corrective RAG + Agentic RAG Patterns (Yan et al. 2024; Singh et al. 2025 Survey) — completed 2026-03-03. Note: memory/research/corrective_agentic_rag_2026-03-03.md. 5 insights stored in brain. Key takeaways: three-tier retrieval evaluator (CORRECT/AMBIGUOUS/INCORRECT), knowledge strip decomposition, query complexity routing, corrective fallback loops. Four concrete implementation phases identified for brain.recall() pipeline.

## Archived 2026-03-03
- [x] [RESEARCH 2026-03-03] Research: Integrated World Modeling Theory (IWMT, Safron 2020) — IIT + GNWT + FEP/Active Inference synthesis; consciousness as coherent generative world modeling + global broadcast.
- [x] [LIFECYCLE_HOOKS_BUS] Replace "import-time wiring" with explicit lifecycle hooks: define `clarvis/heartbeat/hooks.py` (hook registry + execution order) and migrate 3 subsystems (procedural injection, consolidation, metrics) to register hooks instead of being imported implicitly. Add hook-order tests. (2026-03-03 09:07 UTC)

## Archived 2026-03-03
- [x] [REFACTOR_PHASE1] Create `clarvis/` spine package skeleton — empty __init__.py in clarvis/, clarvis/brain/, clarvis/memory/, clarvis/cognition/, clarvis/context/, clarvis/metrics/, clarvis/heartbeat/, clarvis/orch/. Add workspace-level pyproject.toml. No behavior change yet. (2026-03-03 11:03 UTC)
- [x] [RESEARCH_DISCOVERY 2026-03-02] Research: AgentDebug — Where LLM Agents Fail & How They Learn From Failures (completed 2026-03-03)

## Archived 2026-03-03
- [x] [REFACTOR_PHASE0] Safety net: tag v0.9-pre-refactor, backup ChromaDB, fix import side effects (add `if __name__` guards to cost_tracker.py, digest_writer.py), standardize sys.path patterns. Run `import_health.py --strict` as baseline. No behavior change. Files: scripts/cost_tracker.py, scripts/digest_writer.py, all scripts sys.path lines. (2026-03-03 12:10 UTC)

## Archived 2026-03-03
- [x] [RESEARCH_GNW_IGNITION 2026-03-03] Research: Global Neuronal Workspace (GNW) — “ignition” as nonlinear recurrent broadcast (Mashour/Dehaene/Changeux review).
- [x] [IMPORT_SIDE_EFFECTS_FIX] Reduce import-time side effects to 0: convert top-level `log()`/registry calls to functions or `if __name__ == '__main__'` blocks; add `import_health.py --strict` gate in CI/tests. (2026-03-03 15:11 UTC)

## Archived 2026-03-03
- [x] [ACTR_RECALL_WIRING] Wire actr_activation.py into brain.py recall pipeline via hook registry. ACT-R base-level activation (recency × frequency decay) should act as a recall_scorer hook in clarvis/brain/hooks.py, blending with embedding similarity. Currently coded but NOT integrated — identified as critical gap in ROADMAP. Expected impact: +0.02-0.05 retrieval distance improvement, indirect Phi boost via better cross-collection recall. (2026-03-03 16:03 UTC)

## Archived 2026-03-03
- [x] [REFACTOR_COGNITION_EXTRACT] Continue refactoring momentum: extract attention.py, clarvis_confidence.py, thought_protocol.py into `clarvis/cognition/`. Follow same mixin + hook registry pattern from brain/ extraction (SCC 6→0). Keep backward-compatible shims in scripts/. Fills the empty cognition/ placeholder created during Phase 2. (2026-03-03 17:09 UTC)

## Archived 2026-03-03
- [x] [CRON_SCHEDULE_REBALANCE] Audit and rebalance cron schedule. Current issues: (1) three autonomous slots cluster at 15/16/17h CET competing with the 14h implementation sprint and 15h strategic audit — spread them out; (2) the 03:00-05:30 window runs 4 maintenance jobs (graph checkpoint, compaction, vacuum) that could overlap on slow days — add mutual exclusion; (3) consider moving one of the two 10:00/14:00 research slots to an afternoon gap (e.g., 16:00) for better topic diversity. Output: updated crontab + validation that no two Claude Code spawners can overlap.
- [x] [RESEARCH_CONSCIOUSNESS 2026-03-03] Research: Integrated Information Theory (IIT) 4.0 (Albantakis et al., PLOS Comp Bio 2023) — IIT 4.0 refines the axioms→postulates mapping and defines consciousness as a system’s maximal irreducible cause–effect structure from the intrinsic perspective, introducing Intrinsic Difference (ID) as a uniquely postulate-consistent intrinsic-information measure. Sources: https://doi.org/10.1371/journal.pcbi.1011465 , https://arxiv.org/abs/2212.14787

## Archived 2026-03-03
- [x] [TEST_COVERAGE_CLARVIS] Address Code Generation capability (0.60 — LOWEST domain). Create pytest test suite for `clarvis/` package: brain/ (store, search, graph, hooks), memory/ (episodic, procedural, working, hebbian), heartbeat/ (adapters, hooks). Use brain's existing test patterns from `packages/clarvis-db/tests/`. Target: 50%+ line coverage of extracted modules. Run via `cd workspace && python3 -m pytest tests/`. This directly raises the Code Generation score by adding the missing test coverage dimension. (2026-03-03 20:19 UTC)

## Archived 2026-03-03
- [x] [CALIBRATION_LOOP_CLOSE] Fix brier score (0.27 — LOWEST metric). Only 72% of predictions (118/165) resolve to outcomes. Build `scripts/prediction_resolver.py`: scan unresolved predictions in clarvis-episodes, match against completed tasks/episodes by embedding similarity, auto-resolve obvious matches (e.g., task predicted "will succeed" → task completed successfully). Add to postflight pipeline. Target: 90%+ resolution rate, brier score > 0.50. (2026-03-03 22:16 UTC)

## Archived 2026-03-03
- [x] [MEMORY_QUALITY_GATES] Add hard quality gates to postflight: if semantic link quality / retrieval relevance drops vs baseline, automatically open a P0 repair task and pause “new features” work. (2026-03-03 23:05 UTC)

## Archived 2026-03-04
- [x] [BRAIN_EVAL_HARNESS] Brain eval harness: create repeatable benchmark suite for memory quality (P@k, MRR, false-link rate, context usefulness) with ground-truth query→expected memory ids. Output JSON + trendline. Gate regressions. (2026-03-04 01:08 UTC)
- [x] [RESEARCH 2026-03-04] Research: mem0 (mem0ai/mem0) — evaluated architecture, storage model, retrieval, evaluation. Extracted 5 concrete improvements (LLM conflict detection, mutation history, fact extraction on capture, graph edge weights+decay, Kuzu embedded graph DB) + 2 experiments (LOCOMO-style benchmark, LLM conflict detection prototype). Note: `memory/research/mem0_memory_layer_2026-03-04.md`

## Archived 2026-03-04
- [x] [STRUCTURE_FINAL_AUDIT] Final structure + wiring audit (after refactor): run full import/health checks and review the repo holistically (clarvis/, scripts/, docs/, skills/, packages/, tests/). Confirm all core features are correctly wired to the new spine (no hidden legacy coupling), identify deprecated/outdated files to archive/remove, validate naming/layout scalability, and ensure documentation/runbook is complete. Output: a punchlist of remaining fixes + suggested structure tweaks. (2026-03-04 05:36 UTC)

## Archived 2026-03-04
- [x] [ORCH_SECOND_AGENT] Add second project agent for another repo — test multi-agent benchmark aggregation. (2026-03-04 06:05 UTC)

## Archived 2026-03-04
- [x] [OLLAMA_TEST] Test Qwen3-VL with screenshots, verify CAPTCHA detection accuracy for local vision pipeline. (2026-03-04 07:18 UTC)

## Archived 2026-03-04
- [x] [RESEARCH_IIT4 2026-03-04] Research: Integrated Information Theory (IIT) 4.0 (Albantakis et al., 2023) — Key update is a stricter axioms→postulates mapping plus the Intrinsic Difference (ID) measure for intrinsic information; consciousness = maximal irreducible intrinsic cause–effect structure (maximally integrated complex) unfolded from the substrate’s TPM. Sources: https://pmc.ncbi.nlm.nih.gov/articles/PMC10581496/ ; https://arxiv.org/abs/2212.14787
- [x] [BENCHMARK_RELIABILITY] Review performance_benchmark.py outputs after fixes — ensure no more phantom P0 tasks generated from stale data.

## Archived 2026-03-04
- [x] [FILE_HYGIENE_POLICY] Add workspace file-hygiene policy + automation: `scripts/cleanup_policy.py` (rotate logs, compress old daily memory, prune tmp artifacts), and document retention rules. Ensure cron/heartbeat calls it weekly. (2026-03-04 11:06 UTC)
- [x] [RESEARCH_DISCOVERY 2026-03-04] Research: ACuRL — Autonomous Curriculum RL for Computer-Use Agent Adaptation (Xue et al., arXiv:2602.10356) — Deep dive completed. Three-phase pipeline: autonomous exploration → curriculum task generation (adaptive difficulty) → iterative GRPO training with CUAJudge (93% human agreement). 4-22% gains without catastrophic forgetting via sparse parameter updates. Research note: memory/research/acurl_autonomous_curriculum_rl_2026-03-04.md

## Archived 2026-03-04
- [x] [PROMPT_SELF_OPTIMIZE] Prompt self-optimization loop — record heartbeat prompt→outcome pairs in postflight, generate prompt variants for underperforming templates, A/B test across heartbeats. Inspired by APE/SPO from EvoAgentX survey. Files: heartbeat_preflight.py, heartbeat_postflight.py. (2026-03-04 12:07 UTC)

## Archived 2026-03-04
- [x] [GOLDEN_TRACE_REPLAY] Successful trajectory replay (STaR pattern) — extract golden traces from successful heartbeats in postflight, store in clarvis-procedures, inject matching traces into preflight prompts as reference approaches. Files: heartbeat_postflight.py, heartbeat_preflight.py, procedural_memory.py. (2026-03-04 14:06 UTC)
- [x] [RESEARCH_FEP 2026-03-04] Research: Active Inference / Free Energy Principle (expected vs generalised free energy) — Key insight: planning-as-inference selects policies that trade off pragmatic value (prior preferences) with epistemic value (uncertainty reduction) under a generative world model; “generalised free energy” treats future outcomes as explicit hidden states, keeping preferences inside the generative model while yielding the same posterior policy form. Sources: https://pmc.ncbi.nlm.nih.gov/articles/PMC6848054/ , https://arxiv.org/abs/2401.12917

## Archived 2026-03-04
- [x] [CRON_PROMPT_TUNING] Review and tighten the 6 main cron spawner prompts (`cron_autonomous.sh`, `cron_morning.sh`, `cron_evolution.sh`, `cron_evening.sh`, `cron_reflection.sh`, `cron_research.sh`). Each prompt should: (1) reference QUEUE.md explicitly, (2) include the current weakest metric, (3) have a hard output format constraint. Measure: reduced token waste per spawn. (2026-03-04 15:08 UTC)

## Archived 2026-03-04
- [x] [CLI_SKELETON] Create canonical `clarvis` CLI skeleton — `clarvis/__main__.py` + `clarvis/cli.py` with Typer, subcommands: brain, bench, heartbeat, queue. COMPLETED 2026-03-04.
- [x] [RESEARCH_DISCOVERY 2026-03-03] Research: LLM Confidence Calibration & Uncertainty Estimation — COMPLETED 2026-03-04. Stored 5 brain memories. Note: memory/research/llm_confidence_calibration_2026-03-04.md. Key: CoCoA hybrid method best (ECE 0.062), VCE outperforms logit-based, Flex-ECE for partial correctness, reflection-based calibration reduces overconfidence. 5 concrete implementation ideas for clarvis_confidence.py.
- [x] [RESEARCH_DISCOVERY 2026-03-03] Research: ATLAS — Continual Learning, Not Training (Jaglan & Barnes, arXiv:2511.01093) — COMPLETED 2026-03-04. Key insight: shift continual learning from weight updates to system-level orchestration. A Teacher distills experience into persistent “pamphlets” that gate/shape a Student’s future execution at inference time; yields higher success with lower token cost and generates causally-annotated traces useful for world-model training. Sources: arxiv.org/abs/2511.01093

## Archived 2026-03-04
- [x] [STRUCTURE_FINAL_AUDIT] Deep structure + wiring audit after spine migration. Written to `docs/STRUCTURE_INTEGRITY_AUDIT.md`.
- [x] [STALE_RESEARCH_PRUNE] Review the 7 RESEARCH_DISCOVERY items (dating 2026-03-01 to 2026-03-03) — for each: either extract 1 actionable implementation task and replace the research item, or demote to a `docs/research_backlog.md` reference list. Queue should have concrete tasks, not reading lists. DONE (2026-03-04): 2 items → concrete tasks, 4 items → docs/research_backlog.md.

## Archived 2026-03-04
- [x] [SCALABILITY_GATE] Create `scripts/gate_check.sh`: compileall + import_health --quick + spine smoke test + pytest. DONE (2026-03-04).

## Archived 2026-03-04
- [x] [HEARTBEAT_INIT_EXPORT_FIX] ~~Fix `clarvis/heartbeat/__init__.py` — add `HookRegistry` to exports~~ DONE (2026-03-04).
- [x] [BOOT_MD_FIX] Fixed deprecated `from clarvis_memory import clarvis_context` → `from clarvis.brain import brain, search, remember, capture`. DONE (2026-03-04).
- [x] [SELF_MD_UPDATE] Updated SELF.md: PM2→systemd, brain stats 42/7→2000+/10, process chain updated. DONE (2026-03-04).
- [x] [DEAD_CODE_AUDIT] Built `scripts/dead_code_audit.py`: scans crontab, imports, cron .sh wrappers, docs, skills, configs, spine. 85/89 exercised, 3 candidates. DONE (2026-03-04).
- [x] [CLI_CONSOLE_SCRIPT] Added `[project.scripts] clarvis = "clarvis.cli:main"` to `pyproject.toml`, `pip install -e .` confirmed, `clarvis --help` works from any directory. DONE (2026-03-04).
- [x] [CLI_TESTS] Wrote `tests/test_cli.py` — 9 tests: `--help` for all subcommands + real invocations (`brain stats`, `queue status`, `bench pi`, `heartbeat gate`). All pass. DONE (2026-03-04).
- [x] [CLI_CRON_SUBCOMMAND] Added `clarvis cron list|status|run <job>` with `--dry-run`. Wraps existing cron_*.sh scripts. DONE (2026-03-04).
- [x] [CLI_CRON_PILOT] Migrated `cron_reflection.sh` to `clarvis cron run reflection` in system crontab. Approved & applied 2026-03-04. Soak period: 7 days (ends 2026-03-11). DONE (2026-03-04).
- [x] [CLI_DEPRECATION_WARNINGS] Added stderr deprecation warnings to `scripts/brain.py`, `scripts/performance_benchmark.py`, `scripts/queue_writer.py` `__main__` blocks. DONE (2026-03-04).
- [x] [CLI_BOOT_DRIFT] Audited AGENTS.md and BOOT.md: updated 4 stale references — `from brain import` → `from clarvis.brain import`, `from message_processor import init_session` → inline brain.stats(), `python3 scripts/brain.py` → `python3 -m clarvis brain`. BOOT.md was already correct. DONE (2026-03-04).
- [x] [CLI_CRON_STUB] Subsumed by CLI_CRON_SUBCOMMAND — `clarvis/cli_cron.py` includes list + status + run. DONE (2026-03-04).
- [x] [SPINE_HEARTBEAT_ABSORB] Moved gate logic to `clarvis/heartbeat/gate.py`, runner to `clarvis/heartbeat/runner.py`. CLI uses spine gate. Scripts are thin wrappers. DONE (2026-03-04 Phase 4).
- [x] [SPINE_CONTEXT_ABSORB] Moved core compression (tfidf_extract, mmr_rerank, compress_text, compress_queue, compress_episodes, generate_tiered_brief) to `clarvis/context/compressor.py`. Scripts wrapper has deprecation notice. DONE (2026-03-04 Phase 4).
- [x] [BRAIN_PARALLEL_QUERY] recall() already parallel (ThreadPoolExecutor). Increased max_workers 6→10, added 30s result cache (0ms repeated queries), parallelized recall_from_date(). Avg latency: 7441→2092ms (72% reduction). Added `latency` subcommand to brain_eval_harness.py. DONE (2026-03-04 Phase 4).
- [x] [TEST_COVERAGE_EXPAND] Added tests/test_spine_phase4.py: 31 tests covering heartbeat gate, context compressor, brain search perf, cron wrap-mode integration. All pass. Registered `slow` pytest mark. DONE (2026-03-04 Phase 4).
- [x] [REFLECTION_GLOBAL_LOCK] Added `/tmp/clarvis_claude_global.lock` to `cron_reflection.sh` with standard stale detection (2400s). All 8 cron scripts now share global lock. DONE (2026-03-04 Phase 4).

## Archived 2026-03-04
- [x] [DOCS_STRUCTURE] Establish docs structure: `docs/ARCHITECTURE.md` (layers + boundaries), `docs/CONVENTIONS.md`, `docs/DATA_LAYOUT.md`, `docs/RUNBOOK.md`. ✅ ARCHITECTURE.md rewritten 2026-03-04 (CONVENTIONS/DATA_LAYOUT/RUNBOOK already existed)
- [x] [PYTEST_COLLECTION_HYGIENE] Fix global `pytest` collection — deprecated tests under `scripts/deprecated/` caused collection errors. Added `testpaths`/`norecursedirs` to `pyproject.toml`. Fixed 15 broken tests (brain fixture missing `_recall_cache`, heartbeat adapter count, spotlight mock target). Gate updated to include `test_pipeline_integration.py`. ✅ DONE 2026-03-04
- [x] [CRON_LOCK_HELPER] Extract `scripts/lock_helper.sh` — shared functions for local/global/maintenance locks. ✅ DONE 2026-03-04
- [x] [METRICS_SELF_MODEL] Populate `clarvis/metrics/` — move `scripts/self_model.py` core classes into `clarvis/metrics/self_model.py`. ✅ DONE 2026-03-04
- [x] [ORCH_TASK_SELECTOR] Populate `clarvis/orch/` — move `scripts/task_selector.py` scoring logic into `clarvis/orch/task_selector.py`. ✅ DONE 2026-03-04
- [x] [UNWIRED_AZR] Wire `absolute_zero.py` into weekly cron (self-play reasoning session). Currently CLI-only, never automatically exercised. ✅ DONE 2026-03-04 (Sunday 03:00 UTC, 5 cycles/week, cron_absolute_zero.sh)
- [x] [UNWIRED_META_LEARNING] Wire `meta_learning.py` into postflight or weekly cron — learning strategy analysis never runs automatically. ✅ DONE 2026-03-04 (wired into postflight hook, priority 90, daily rate limit)
- [x] [UNWIRED_GRAPHRAG] Wire `graphrag_communities.py` into brain.recall() or periodic cron — community detection would improve retrieval quality. ✅ DONE 2026-03-04 (graphrag booster hook, toggled via CLARVIS_GRAPHRAG_BOOST=1)
- [x] [METRICS_PERF_BENCHMARK] Move PI computation from `scripts/performance_benchmark.py` (1,535L) into `clarvis/metrics/benchmark.py`. Core: 8-dimension scoring, composite PI calculation, self-optimization triggers. Keep CLI as thin wrapper. Enables `clarvis bench` to use spine directly. (Phase 5 — metrics spine completion.) ✅ DONE 2026-03-04
- [x] [ORCH_TASK_ROUTER] Move `scripts/task_router.py` complexity scoring + model routing into `clarvis/orch/router.py`. Export `classify_task()`, `route_to_model()`, `get_tier_config()`. Thin wrapper in scripts/. (Phase 5 — orch spine completion.) ✅ DONE 2026-03-04
- [x] [GRAPHRAG_RECALL_BOOST] Wire `graphrag_communities.py` into `brain.recall()` — after ChromaDB vector search, optionally expand results with intra-community neighbors. Directly improves retrieval quality (PI weight 0.18). (Phase 5 — existing module, never exercised in recall path.) ✅ DONE 2026-03-04
- [x] [HEBBIAN_EDGE_DECAY] Add age-based Hebbian edge pruning to `clarvis/brain/graph.py`: `decay_edges(half_life_days, prune_below)`. Exponential decay + prune. CLI: `clarvis brain edge-decay`. (Phase 5 — graph sustainability.) ✅ DONE 2026-03-04
- [x] [META_LEARNING_WIRE] Wire `meta_learning.py analyze` into postflight hook (priority 90, daily rate limit). Closes the "learn how to learn" feedback loop. (Phase 5 — now auto-exercised via heartbeat.) ✅ DONE 2026-03-04
- [x] [PIPELINE_INTEGRATION_TEST] Create `tests/test_pipeline_integration.py`: 25 tests covering router, edge decay, graphrag booster, pipeline flow, hook lifecycle. (Phase 5.) ✅ DONE 2026-03-04

## Archived 2026-03-05
- [x] [GOLDEN_QA_MAIN_BRAIN] _(2026-03-04)_ Extended retrieval_benchmark.py with P@1, MRR metrics + golden_qa CLI. Results: P@1=1.0, P@3=0.867, MRR=1.0. Saved to data/benchmarks/golden_qa_results.json.
- [x] [TASK_SIZING_CALIBRATION] _(2026-03-04)_ Added estimate_task_complexity() to cognitive_load.py, wired into heartbeat_preflight.py §4.5. Oversized tasks deferred to implementation sprint. Log: data/task_sizing_log.jsonl.
- [x] [PARALLEL_BRAIN_QUERIES] _(2026-03-04)_ Already implemented in Phase 4 — clarvis/brain/search.py recall() uses ThreadPoolExecutor(max_workers=10), search() uses ThreadPoolExecutor(max_workers=6). No further work needed.
- [x] [SAFETY_INVARIANTS] _(2026-03-04)_ Created docs/SAFETY_INVARIANTS.md (8 invariants) + scripts/safety_check.py (pre-commit, postflight, all modes). All invariants pass.
- [x] [PI_CLI_FIX] _(2026-03-04)_ Fixed both clarvis bench pi (cli_bench.py) and performance_benchmark.py pi. Now reads cached PI from data/performance_metrics.json instantly. --fresh flag for recompute.
- [x] [CLI_DOCS_UPDATE] _(2026-03-05)_ Updated CLAUDE.md, RUNBOOK.md to reference `clarvis` CLI. AGENTS.md was already migrated. Old `python3 scripts/brain.py` examples replaced with `python3 -m clarvis brain`. Legacy import kept as reference.

## Archived 2026-03-05
- [x] [RESEARCH_CONSCIOUSNESS 2026-03-05] Research: Integrated World Modeling Theory (Safron 2020, PMC7861340) — integrate IIT + GNWT inside FEP/Active Inference; key move is *world-referential, embodied coherence* (space/time/cause + self-model) as the missing sufficiency condition beyond Φ/broadcast.
- [x] [RESEARCH_CONSCIOUSNESS 2026-03-05] Research: Integrated Information Theory (IIT) 4.0 (Albantakis et al., PLOS Comp Bio 2023; arXiv:2212.14787) — IIT formalism update: intrinsic information via Intrinsic Difference + explicit causal relations; lingering issue: realism vs idealist ontology tension (see PMC10606349).
- [x] [RESEARCH_DISCOVERY 2026-03-05] Research: Neurosymbolic Agent Planning — Metagent-P (plan-verify-execute-reflect with symbolic+LLM, ACL 2025), NeSyPr (compiled procedural knowledge for embodied agents), StateFlow transducer FSMs for LLM control flow. Combines formal verification with neural flexibility to reduce action errors. Sources: aclanthology.org/2025.findings-acl.1169, openreview.net/forum?id=a8sJEH4Cjb, arxiv.org/abs/2403.11322

## Archived 2026-03-05
- [x] (2026-03-05) [RESEARCH_REPO_OPENSTINGER] Review repo: https://github.com/srikanthbellary/openstinger — portable memory harness for agents (FalkorDB + PostgreSQL, 27 MCP tools). Verdict: keep, selectively adapt 3 patterns (bi-temporal edges, hybrid BM25+vector search, session distillation). See memory/research/openstinger_review_2026-03-05.md.
- [x] (2026-03-05) [RESEARCH_IIT_4] Read Albantakis et al. “Integrated information theory (IIT) 4.0” (PLOS/PMC). Key: updated axioms→postulates mapping + Intrinsic Difference (ID) as intrinsic information measure; consciousness ↔ maximally irreducible intrinsic cause–effect structure.
- [x] [CLI_ROOT_PYPROJECT] Create root `pyproject.toml` for the `clarvis` package (if not already present). Define `[project.scripts] clarvis = "clarvis.cli:main"`, set `packages = ["clarvis"]`, pin deps. Prerequisite for CLI_CONSOLE_SCRIPT. (2026-03-05: done — pyproject.toml had console_script, added clarvis-cost + clarvis-reasoning as dependencies, removed sys.path hack from cli_cost.py, fixed testpaths, verified editable install + CLI)
- [x] [NOVELTY_TASK_SCORING] Novelty-weighted task selection — compute embedding distance between candidate tasks and last N completed tasks, boost high-novelty tasks with `final_score = base_score * (1 + 0.3 * novelty)`. Prevents "more of the same" trap. Files: task_selector.py (or heartbeat_preflight.py scoring section). (2026-03-05: done — Jaccard word similarity against last 15 episodes in clarvis/orch/task_selector.py, novelty exposed in scoring details)
- [x] [COST_PER_TASK_TRACKING] Tag each Claude Code invocation with task ID in cost logging. Create routing effectiveness report showing % of tasks routed to cheap models vs Claude Code. (Source: ARCH_AUDIT_2026-03-05) (2026-03-05: done — added task_costs() + routing_effectiveness() to CostTracker, created scripts/cost_per_task.py report, fixed cron_research.sh + cron_implementation_sprint.sh to pass actual task names)
- [x] [CLI_COST_SUBCOMMAND] Add `clarvis cost daily/budget` subcommands — cost tracking not in unified CLI. (2026-03-05: done — 6 subcommands: daily, weekly, budget, realtime, summary, trend. Registered in clarvis/cli.py)
- [x] [CONFIDENCE_RECALIBRATION] Fix overconfidence at 90% level (70% actual accuracy). In `clarvis_confidence.py`, add confidence band analysis to `predict()`: if historical accuracy for band 0.85-0.95 is <80%, auto-downgrade new predictions in that band by 0.10. Log adjustments. Target: Brier score 0.12→0.20+ in system health ranking. (2026-03-05: done — _band_accuracy() + auto-downgrade in predict(), also handles 95-100% band, logs recalibration with original_confidence)
- [x] [ACTR_WIRING_1] Identify the *actual* recall call chain (brain.recall → collection query → merge → rerank) and the correct injection point (file+function names). (2026-03-05: confirmed — search.py:SearchMixin.recall() lines 128-139, hook via hooks.py:_make_actr_scorer)
- [x] [ACTR_WIRING_2] Implement rerank step: take recall results + per-result last_access/access_count, compute ACT-R activation, blend into final score with a tunable weight. (2026-03-05: confirmed already implemented — actr_score(r) called per result, 70/30/5 blend)
- [x] [ACTR_WIRING_3] Add a small deterministic test fixture (5-10 fake memories with timestamps) proving recency/frequency boosts ordering. (2026-03-05: done — test_actr_scorer_boosts_recent_and_frequent validates frequency, recency, accessed>never invariants + hook wiring)
- [x] [FAILURE_TAXONOMY] Add error type classification to `heartbeat_postflight.py` failure handling. When a task fails, classify the error into one of 5 categories (memory/planning/action/system/timeout) using keyword matching on output. Store as `error_type` tag in episode metadata alongside existing "failure" tag. Enables failure pattern analysis across heartbeats. (Extracted from: AgentDebug research, arXiv:2509.25370) (2026-03-05: done — _classify_error() function, tags in brain learnings + episodes + completeness JSONL)
- [x] [POSTFLIGHT_COMPLETENESS] Add completeness scoring to `heartbeat_postflight.py`. Count stages executed vs. attempted (e.g. 11/14). Log to `data/postflight_completeness.jsonl`. Alert if <80% stages succeed. Currently, silent hook failures cause invisible data loss — no way to detect degraded postflight execution. (Source: ARCH_AUDIT_2026-03-05) (2026-03-05: done — tracks _pf_errors list, computes ratio, writes JSONL, warns if <80%)
- [x] [SPINE_SHADOW_DEPS] Migrate the 6 scripts imported by spine code via `sys.path` manipulation into proper spine submodules: `somatic_markers` → `clarvis/cognition/`, `clarvis_reasoning` → `clarvis/cognition/`, `graphrag_communities` → `clarvis/brain/`, `cost_api` → `clarvis/orch/`, `soar_engine` → `clarvis/memory/`, `meta_learning` → `clarvis/learning/`. Eliminates hidden `sys.path.insert()` in `clarvis/brain/hooks.py` and `clarvis/orch/*.py`. (Source: ARCH_AUDIT_2026-03-05) (2026-03-05: done — cost_api fully migrated into spine, 5 proxy modules created, all module-level sys.path.insert removed from hooks.py/router.py/task_selector.py/memory modules, 18 tests pass, 7/7 hooks register)
- [x] [SPINE_TEST_SUITE] Create `clarvis/tests/` with integration tests: (1) brain store→recall roundtrip, (2) hook registration completeness check, (3) preflight JSON schema validation, (4) CLI smoke tests (`clarvis brain health`, `clarvis bench pi`, `clarvis queue status`). Target: 5+ tests, all pass in <30s. Currently zero test coverage for spine package. (Source: ARCH_AUDIT_2026-03-05) (2026-03-05: done — 18 tests across 3 files: brain roundtrip (5), hooks (8), CLI smoke (5), all pass in ~10s)
- [x] [HOOK_REGISTRATION_LOGGING] In `clarvis/brain/hooks.py:register_default_hooks()`, log which hooks registered and which failed. Currently all failures silently swallowed by try/except. Add summary: "Registered 4/5 hooks (failed: graphrag_communities)". Small change, high visibility. (Source: ARCH_AUDIT_2026-03-05) (2026-03-05: done — logs via logging + stderr, shows registered/failed counts)
- [x] [PHI_METRIC_SINGLETON] Fix `phi_metric.py` creating fresh `ClarvisBrain()` instances instead of using `get_brain()` singleton. Bypasses hook registration and creates duplicate ChromaDB clients. Change to `from clarvis.brain import get_brain; brain = get_brain()`. (Source: ARCH_AUDIT_2026-03-05) (2026-03-05: done — uses spine get_brain() with legacy ClarvisBrain fallback)
- [x] [GRAPH_INTEGRITY_CHECK] Add checksum verification to graph load/save in `clarvis/brain/graph.py`. On load, verify edge count matches expected. On save, write atomic with edge-count header. Detect silent corruption of the 70k-edge `relationships.json`. (Source: ARCH_AUDIT_2026-03-05) (2026-03-05: done — _save_graph writes _edge_count header, _load_graph verifies + logs warnings)
- [x] [GOLDEN_QA_MAIN_BRAIN] Create golden QA benchmark for main ClarvisDB brain. Write 15+ queries with expected top-3 results covering all 10 collections. Implement as `scripts/retrieval_benchmark.py` (or extend existing). Track P@1, P@3, MRR over time. Run after any brain code change. Critical for proving retrieval quality isn't silently degrading. No golden QA exists for the main brain (only project agents have it). (Source: REFACTOR_COMPLETION_PLAN_2026-03-05) (2026-03-05: done — retrieval_benchmark.py already had 20 ground-truth pairs, added `clarvis bench golden-qa` CLI, baseline: P@1=1.000, P@3=0.883, MRR=1.000, 20/20 recall)
- [x] [PARALLEL_BRAIN_QUERIES] Implement parallel collection queries in `clarvis/brain/search.py` using `concurrent.futures.ThreadPoolExecutor`. Target: <2s brain query latency. (2026-03-05: done — collection queries were already parallel; real bottleneck was synchronous observer hooks (hebbian: 1.5s, total: 4.8s). Fixed by running observers async in background ThreadPoolExecutor with deep-copied results. Benchmark: avg 0.85s, p95 1.49s, golden-qa P@1=1.000 unchanged)

## Archived 2026-03-05
- [x] [RESEARCH_REPO_OBLITERATUS] Deep review repo: https://github.com/elder-plinius/OBLITERATUS — alignment removal toolkit. Verdict: selectively adopt patterns (analysis-driven config, perturbation-based redundancy detection, geometric fingerprinting). Full review: `memory/research/OBLITERATUS_review.md`.
- [x] [GRAPH_STORAGE_UPGRADE] Replace JSON graph store with SQLite + WAL. Decision: SQLite wins on all axes (zero deps, ACID, indexed lookups, 355x write improvement). See `docs/GRAPH_STORAGE_RECOMMENDATION_2026-03-05.md`.
- [x] [GRAPH_STORAGE_UPGRADE_1] Evaluate & decide — **SQLite + WAL** selected. Decision matrix in recommendation doc. JSON is 21MB/85k edges, full rewrite on every edge add (355ms). SQLite: <1ms per insert, indexed lookups, ACID transactions, zero new dependencies.
- [x] [GRAPH_STORAGE_UPGRADE_2] Implement `clarvis/brain/graph_store_sqlite.py` — `GraphStoreSQLite` class wrapping SQLite. Schema: `nodes(id, collection, added_at, backfilled, metadata)`, `edges(id, from_id, to_id, type, created_at, source_collection, target_collection, weight, last_decay)` with UNIQUE(from_id, to_id, type). Indices on from_id, to_id, type, (from_id, type), (collection). WAL mode, busy_timeout=5000, synchronous=NORMAL. API mirrors GraphMixin. Config flag: `CLARVIS_GRAPH_BACKEND` env var in constants.py. 33 pytest tests pass.
- [x] [GRAPH_STORAGE_UPGRADE_3] Migration tool: `scripts/graph_migrate_to_sqlite.py` — load `relationships.json`, bulk-insert into `data/clarvisdb/graph.db` via `executemany` in single transaction. Verified: 2595 nodes + 85164 edges migrated in 0.69s, 100/100 random edge sample match, 0 duplicates, PRAGMA integrity_check OK. DB size: 41MB.
- [x] [GRAPH_STORAGE_UPGRADE_4] Dual-write/dual-read in `GraphMixin`: write to both JSON and SQLite, read from SQLite, periodic verification. Rollback via `CLARVIS_GRAPH_BACKEND=json` env var. **Done 2026-03-05**: `graph.py` dual-writes all operations (add_relationship, backfill, bulk_intra_link, decay_edges) to SQLite when `CLARVIS_GRAPH_BACKEND=sqlite`. Reads use SQLite indexed lookups. `verify_graph_parity()` compares counts + random edge sample. CLI: `clarvis brain graph-verify`. 17 new tests + 33 existing pass. Soak period: set `CLARVIS_GRAPH_BACKEND=sqlite` to enable.

## Archived 2026-03-05
- [x] [MARATHON_RUNNER] Build Claude Marathon Runner — 7-hour chaining script that picks batches from QUEUE.md, spawns Claude, runs invariants after each batch. See docs/MARATHON_RUNBOOK.md.
- [x] [GRAPH_STORAGE_UPGRADE_5] Update consumers: `graph_compaction.py` (SQL DELETE path), `cron_graph_checkpoint.sh` (SQLite backup API), `graphrag_communities.py` (load from SQLite). Safe migration (`--safe` flag), daily parity verification cron (`cron_graph_verify.sh`), soak enablement in `cron_env.sh`. RUNBOOK.md written. _(Phase 3, completed 2026-03-05)_

## Archived 2026-03-06
- [x] [RESEARCH_REPO_QWEN_AGENT] Deep review repo: https://github.com/QwenLM/Qwen-Agent _(completed 2026-03-06, see memory/research/qwen_agent_deep_review.md — 15 key ideas, 5 steal-and-implement items, ignore list)_
- [x] [RESEARCH_REPO_AGENCY_AGENTS] Review repo: https://github.com/msitarzewski/agency-agents — evaluate for delegation/sub-agent orchestration patterns applicable to Clarvis. Output: summary + 3 adoptable patterns. _(completed 2026-03-06, see memory/research/agency_agents_review.md — 3 patterns: QA retry pipeline, convergent parallel analysis, penalty-based trust scoring)_
- [x] [CLI_BRAIN_LIVE] Verify `clarvis brain health` output matches `python3 scripts/brain.py health` exactly. _(completed 2026-03-06, outputs match — same format, same data)_
- [x] [CLI_BENCH_EXPAND] Add missing bench subcommands: `record`, `trend [days]`, `check` (exit 1 on failures), `heartbeat` (quick check), `weakest` (weakest metric). _(completed 2026-03-05, commit 209a84c)_
- [x] [PERFORMANCE_BENCHMARK 2026-03-06] [PERF] Episode Success Rate 0.0 + PI drop to 0.729. _(fixed 2026-03-06: scripts/episodic_memory.py wrapper missing EpisodicMemory re-export after migration to clarvis/memory/)_

## Archived 2026-03-06
- [x] [ORCH_FIRST_REAL_PR] _(done 2026-03-06)_ Spawned star-world-order agent → PR #176 (https://github.com/InverseAltruism/Star-World-Order/pull/176). CONTRIBUTING.md rewrite, 59s, success. Promoted 7 procedures + digest back to Clarvis. No CI checks on upstream (CI workflow PR #175 not merged yet). Scoreboard confirms: 5 tasks, 2 PRs, 100% success.
- [x] [ORCH_SCOREBOARD] _(done 2026-03-06)_ Created `scripts/orchestration_scoreboard.py`: summary table, per-agent detail view, JSONL recording, history trend. Reads from agent.json + task summaries + benchmarks. 5 agents tracked, 8 total tasks, 1 PR, 100% success rate. CLI: `summary|agent <name>|record|history [days]`.
- [x] [ORCH_SCOREBOARD_IMPL] _(done 2026-03-06)_ Same as [ORCH_SCOREBOARD] above.
- [x] [RESEARCH_IIT4_2026-03-06] Research: Integrated Information Theory (IIT) 4.0 (PLOS Comp Bio 2023) — axioms→postulates mapping, intrinsic cause–effect power, Intrinsic Difference (ID) measure, explicit causal relations. _(completed 2026-03-06)_
- [x] [ACTR_WIRING_4] _(done 2026-03-06)_ Benchmark: P@1=1.000, P@3=0.867, MRR=1.000 — zero regression. Calibrated τ from -2.0→-5.0. Old τ clipped 98.7% of single-access memories; new τ keeps 63.7% in continuous sigmoid scoring. Distribution: activation range [-6.7, +1.7], mean -2.45, median -1.47.
- [x] (2026-03-06) [RESEARCH_DISCOVERY 2026-03-05] Research: Agent Interoperability Protocols — MCP + A2A + ACP + ANP. 5 brain memories stored. Research note: memory/research/agent_interoperability_protocols.md. Key finding: Clarvis project_agent.py already implements ~70% of A2A Task model; A2A-aligning agent.json with Agent Cards is next high-value step.

## Archived 2026-03-06
- [x] [ORCH_CI_CONTEXT] Add `build_ci_context()`: scan repo for test/build/lint commands from config files (package.json, Makefile, pyproject.toml), write `ci_context.json` per agent. Include in spawn prompt. _(done 2026-03-06: scans package.json/pyproject.toml/Makefile/.github/workflows, auto-refreshes on spawn, CLI `ci-context` command added)_

## Archived 2026-03-06
- [x] [ORCH_TRUST_SCORE] Add outcome-based trust scoring to `project_agent.py`: `trust_score` field in `agent.json`, adjustment table (pr_merged +0.05, task_failed -0.10, ci_broke_main -0.20, etc.), trust tiers (autonomous ≥0.80, supervised ≥0.50, restricted ≥0.20, suspended =0.00). Update trust post-spawn in `cmd_spawn()`. ✓ 2026-03-06
- [x] [ORCH_CRON_COEXIST] Add `is_cron_window_clear(minutes_needed)` to `project_agent.py`: reads system crontab, checks if any job scheduled within window. Create `scripts/cron_agent_loop.sh` for time-slotted agent execution between cron slots. Release global lock between loop sessions. (2026-03-06 14:05 UTC)
- [x] [RESEARCH_IIT4_CAUSE_EFFECT] Research: Integrated Information Theory (IIT) 4.0 — intrinsic cause–effect power, intrinsic information (ID), integration/exclusion, and maximal substrate selection. _(completed 2026-03-06)_

## Archived 2026-03-06
- [x] [ORCH_DECOMPOSE] Add `decompose_task()` to `project_agent.py`: takes task string + agent context (procedures, repo structure), returns 1-5 subtask list with deps. Uses lite brain + `dependency_map.json` if available. Single-task fallback for simple tasks. _(done 2026-03-06: heuristic connector-split + impl-keyword decomposition, CI context aware, 5 tests)_
- [x] [ORCH_TASK_LOOP] Add `run_task_loop()` and CLI command `project_agent.py loop <name> "<task>"`: plan→execute→verify→fix cycle per subtask, shared work branch, budget/session/timeout exit criteria, episode storage per subtask. _(done 2026-03-06: full loop with decompose→execute→verify→CI fix, 3 tests, CLI wired)_
- [x] [ORCH_CI_FEEDBACK] Add CI feedback loop: `_poll_ci_checks(pr_number, repo)` via `gh pr checks`, `_extract_ci_failure_logs()` via `gh api`, re-spawn agent with failure context (max 2 CI-fix attempts). Wire into `run_task_loop()` final phase. _(done 2026-03-06: 3 functions + `ci-check` CLI, 6 tests, wired into task loop post-PR phase)_

## Archived 2026-03-06
- [x] [ORCH_DEP_MAP] Add `build_dependency_map()`: scan repo for entry points, config files, test dirs, key modules. Write `dependency_map.json` per agent. Feed into decomposer for smarter subtask splits. _(completed 2026-03-06: function + CLI `dep-map` subcommand + 13 tests + wired into decompose_task project hints + spawn prompt project structure section. Validated on star-world-order: next.js detected, 2 entries, 5 src dirs, 38 key modules, 2 test files.)_
- [x] [RESEARCH_REPO_HERMES_AGENT] Deep review repo: hermes-agent — 5 adoptable changes identified: memory injection scanner, flush-before-compress, FTS5 session search, frozen system prompt snapshots, progressive skill disclosure. See `memory/research/hermes_agent_review.md`. _(completed 2026-03-06)_

## Archived 2026-03-06
- [x] [ORCH_CI_POLL_JSON] Fix `project_agent.py:_poll_ci_checks()` to use `gh pr checks --json` (bucket/state/link/name) instead of parsing tab-separated text. Aggregate bucket→pass/fail/pending reliably; treat gh exit code 8 as pending. Add/adjust unit tests accordingly. _(done 2026-03-06: rewrote to `--json bucket,state,link,name`, added 3 new tests for exit-8/cancel/skipping)_
- [x] [ORCH_VISUAL_DASHBOARD_1] Define an events/state JSON schema (`data/dashboard/state.json`) + append-only event log (`data/dashboard/events.jsonl`). _(done 2026-03-06: schema defined in `scripts/dashboard_events.py` — 10 event types, JSONL format at `data/dashboard/events.jsonl`, auto-trim at 5000 events, file-locked writes. Existing `data/dashboard/status.json` serves as state snapshot.)_
- [x] [ORCH_VISUAL_DASHBOARD_4] Hook publishers: cron jobs + `project_agent.py loop` emit events (task start/finish, self-heal, PR created, CI pass/fail). _(done 2026-03-06: created `scripts/dashboard_events.py` module, hooked into project_agent.py spawn/loop/CI/trust + 7 cron scripts via `emit_dashboard_event` helper in cron_env.sh. 20 tests pass.)_
- [x] [RESEARCH_CONSCIOUSNESS 2026-03-06] Research: Integrated Information Theory (IIT) 4.0 — intrinsic cause–effect power formalism (Intrinsic Difference), exclusion/complex selection, and “experience = maximal cause–effect structure” identity. Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC10581496/

## Archived 2026-03-06
- [x] [MEMORY_DAILY_LOGGING_RESTORE] _(2026-03-06)_ Created `scripts/daily_memory_log.py` — generates `memory/YYYY-MM-DD.md` from digest + cron logs + brain stats. Wired into `cron_evening.sh`. Today's file: `memory/2026-03-06.md` (106 lines, brain=3382, phi=0.6504).
- [x] [ORCH_CRON_INTEGRATION] _(2026-03-06)_ Created `scripts/cron_orchestrator.sh` — daily at 19:30 UTC. Promotes all agents, benchmarks those with history, records scoreboard snapshot. Crontab entry added. Tested: 3 promoted, 2 benchmarked, scoreboard recorded.
- [x] [ORCH_AUTO_GOLDEN_QA] _(2026-03-06)_ Added `cmd_auto_golden_qa()` to `project_agent.py` — generates 1-2 QA pairs per successful task, deduplicates via ONNX cosine (threshold 0.85), caps at 50. CLI: `project_agent.py auto-qa <name>`. Integrated into `cron_orchestrator.sh` (daily). star-world-order: 12→17 QA pairs. 72 tests pass.

## Archived 2026-03-06
- [x] [ORCH_VISUAL_DASHBOARD] Build a **visual-only** pixel-art “Habbo style” live dashboard served over LAN IP (no controls; all commands remain via TG/Discord). **DONE 2026-03-06**: Server (`dashboard_server.py`, 210 LOC) + frontend (`dashboard_static/`, 350 LOC JS). Port 18799. All 5 sub-tasks complete. Run: `python3 scripts/dashboard_server.py`
- [x] [ORCH_VISUAL_DASHBOARD_2] **SSE event hub** — `scripts/dashboard_server.py` (210 LOC). **DONE 2026-03-06**: Starlette app on port 18799. Routes: `GET /state` (full JSON), `GET /sse` (EventSource), `GET /health`, `Mount /` (static). Data readers: QUEUE.md parser, lockfile scanner, agent config reader, events JSONL, digest, scoreboard, GH PRs (cached 60s). Background poller detects changes and broadcasts SSE events. Max 5 SSE connections, 60-item queue per client. 15 tests pass.
- [x] [ORCH_VISUAL_DASHBOARD_3] **PixiJS 8 renderer** — `scripts/dashboard_static/index.html` + `app.js` (~350 LOC). **DONE 2026-03-06**: PixiJS 8 via CDN, no build step. Procedural tiled floor, gradient walls, multi-layered desks with shadow+LED. Agent rendering: emoji avatars, trust bars, task labels. Particle system (15 LOC). 3 data panels: queue, events, PRs. Status bar with connection indicator + clock. `hashStr()` for visual variety. Scene rebuild on state change.
- [x] [ORCH_VISUAL_DASHBOARD_4] **SSE client + state sync** (part of `app.js`). **DONE 2026-03-06**: EventSource per-type listeners (state, queue_update, agent_status, cron_activity, events_update, pr_update). Visibility-aware: close on hidden, reconnect+fetch on visible. Connection status: green LIVE / red OFFLINE / yellow PAUSED.
- [x] [ORCH_VISUAL_DASHBOARD_5] **Hardening**. **DONE 2026-03-06**: Built into server — 0.0.0.0 bind, all GET/read-only, max 5 SSE connections (429 on excess), Cache-Control: no-cache on /state+/sse, no CORS, no auth (LAN trust).
- [x] [ORCH_AGENT_PROTOCOLS] Implement basic agent interoperability layer. **DONE 2026-03-06**: A2A/v1 protocol in `project_agent.py` — schema definition (`A2A_RESULT_SCHEMA`), validation (`validate_a2a_result()`), normalization (`normalize_a2a_result()`). `_parse_agent_output()` now validates+normalizes all agent results. Added "blocked" status + error/confidence fields. Spawn prompt updated to A2A/v1 format. 18 new tests (90 total pass).
- [x] [RESEARCH_REPO_CLAW_EMPIRE] Deep review repo: https://github.com/GreenSheep01201/claw-empire — OpenClaw orchestrator + 2D game-style dashboard. **DONE 2026-03-06**: Full analysis in `docs/ORCHESTRATOR_PLAN_2026-03-06.md` §12. Key findings: PixiJS 8 procedural rendering + WebSocket event hub with batched broadcasting + worktree isolation per task + sequential cross-dept delegation. 5-item steal list + 8-item do-not-copy list. Dashboard recommendation: Starlette SSE + vanilla JS + PixiJS 8 (~700 LOC total vs claw-empire's 660 files).
- [x] [RESEARCH_REPO_HERMES_AGENT] Deep review repo: https://github.com/NousResearch/hermes-agent — extract improvements relevant to Clarvis/OpenClaw. **DONE 2026-03-06**: Full analysis in `memory/research/ingested/hermes_agent_review.md`. 5 adoptable changes: (1) memory injection security scanner for brain.py, (2) flush-before-compress pattern for context_compressor.py, (3) FTS5 session search for episodic_memory.py, (4) frozen system prompt snapshots for prefix cache, (5) progressive skill disclosure for OpenClaw gateway. Also noted: memory nudge mechanism, atomic file writes, skill trust levels.

## Archived 2026-03-07
- [x] [ORCH_STALE_LOCK_DETECT] Harden lock acquisition with `/proc/<pid>` liveness check. All three `lock_helper.sh` functions (`acquire_local_lock`, `acquire_global_claude_lock`, `acquire_maintenance_lock`) now use `_is_clarvis_process()` which verifies `/proc/<pid>/cmdline` contains a clarvis/claude process marker. Added `_is_pid_clarvis()` + `_check_global_lock()` to `project_agent.py` with global lock gate in `cmd_spawn`. Added `check_pid_is_clarvis()` to `cron_env.sh`. Also hardened `heartbeat_preflight.py` lock check. 90 tests pass. _(done 2026-03-07)_

## Archived 2026-03-07
- [x] [ORCH_LOOP_BACKOFF] Add randomized delay (10-20s) between subtask sessions in `run_task_loop()`. Add per-agent in-flight lockfile (`/tmp/clarvis_agent_<name>_loop.lock`) with stale PID detection to prevent concurrent loop invocations. Pattern from claw-empire sequential delegation with 900-1600ms delays. Files: `scripts/project_agent.py`. **Done 2026-03-07.** Lock functions: `_acquire_loop_lock`, `_release_loop_lock`, `_loop_lock_path`. Delay: `random.uniform(10, 20)` seconds between subtasks. 6 new tests (96 total pass).
- [x] [RESEARCH_DISCOVERY 2026-03-05] Research: Runtime Verification & Metacognitive Self-Correction for Agents — MASC, AgentSpec, AgentGuard, SupervisorAgent. **Done 2026-03-07.** See `memory/research/runtime_verification_metacognitive_self_correction.md`. 5 brain memories stored. Key takeaways: AgentSpec DSL pattern for ACTION_VERIFY_GATE, SupervisorAgent heuristics for cron monitoring, observation purification for context_relevance improvement.

## Archived 2026-03-07
- [x] [ORCH_AUTOCOMMIT_SAFETY] Add auto-commit safety whitelist to `project_agent.py` spawn. Before agent commits, filter: extension whitelist (`.py,.ts,.js,.json,.md,.css,.html,.go,.rs,.toml,.yaml,.yml,.sh,.sql,.txt`) + blocked patterns (`\.env|id_rsa|id_ed25519|.*\.(pem|key|p12|pfx|sqlite|db|log|zip|tar|gz)`). Tracked changes always staged; untracked only if whitelisted + not blocked. Pattern from claw-empire `worktree/shared.ts`. Files: `scripts/project_agent.py`. _(done 2026-03-07: constants + `safe_stage_files()` function + post-spawn audit in `cmd_spawn()` + prompt injection + 6 tests, all 102 pass)_
- [x] [BROWSER_SKILL_DOC] Create skills/web-browse/SKILL.md documenting browser_agent.py capabilities for M2.5. _(done 2026-03-07: full SKILL.md with commands, rules, library usage, engine selection guide)_

## Archived 2026-03-07
- [x] [RESEARCH_FEP_MARKOV_BLANKETS 2026-03-07] Research: "The Markov blanket trick" (Raja et al., 2021, Phys Life Rev; PMID: 34563472) — critique that FEP is often a variational-Bayes reframing via Markov blankets rather than an explanatory theory; active inference can presuppose successful perception/action instead of explaining them. (Completed 2026-03-07)
- [x] [RESEARCH_GNW_IGNITION 2026-03-07] Research: Global Neuronal Workspace (Dehaene/Changeux; Baars) — conscious access as non-linear ignition + global broadcasting across a long-range fronto-parietal/thalamocortical “router”, linking attention, working memory, and reportability. (Completed 2026-03-07)
- [x] [GRAPH_SOAK_5DAY] Execute 5-day SQLite soak (dual-write enabled): (1) Ensure `scripts/cron_env.sh` exports `CLARVIS_GRAPH_BACKEND=sqlite` and `CLARVIS_GRAPH_DUAL_WRITE=1`. (2) Monitor daily: `tail -20 memory/cron/graph_verify.log` — cron_graph_verify.sh runs at 04:45 UTC. (3) Run `python3 scripts/invariants_check.py` periodically. (4) After **5 consecutive PASS days**, the soak manager will automatically flip `CLARVIS_GRAPH_DUAL_WRITE=0` (SQLite-only writes). Soak start date: _(auto-tracked in data/graph_soak_state.json)_. (2026-03-07 14:20 UTC)
- [x] (2026-03-07) [RESEARCH_DISCOVERY 2026-03-05] Research: Process Reward Models for Agent Step Verification — ThinkPRM, ToolPRMBench, CSO, AgentPRM. See `memory/research/process_reward_models_agent_step_verification.md`. 5 brain memories stored. Key finding: CSO's 5-dimension scoring rubric maps directly to ACTION_VERIFY_GATE; AgentPRM's Promise/Progress metrics map to attention.py salience extension.

## Archived 2026-03-07
- [x] [EPISODIC_MEMORY_WRAPPER_FIX] `scripts/episodic_memory.py` calls `main()` but no longer imports it (runtime NameError). Restore `from clarvis.memory.episodic_memory import main` or inline-call module entrypoint. _(fixed 2026-03-07: added missing import)_
- [x] [DASHBOARD_LIVE_UPDATE_TEST] Add a local Playwright smoke test that appends a synthetic event to `data/dashboard/events.jsonl` and verifies the dashboard UI updates live via SSE (panel text changes + optional screenshot diff). Run in CI. — Done: 3 tests in `scripts/tests/test_dashboard_live.py` (SSE live update, connection indicator, queue status). Uses system Chromium, isolated tmp data, 1s poll. All pass in ~5s.
- [x] [GRAPH_AGENT_MEMORY_TAXONOMY] Research: Graph-Based Agent Memory Taxonomy — MAGMA multi-graph (arXiv:2601.03236), Zep temporal knowledge graph (arXiv:2501.13956), comprehensive survey (arXiv:2602.05665). Covers multi-graph separation (semantic/episodic/procedural), temporal decay on graph edges, hybrid retrieval (A*, beam search), hyper-edge representations. Applicable to 85k+ graph edges, graph_cutover.py SQLite backend, and RECALL_GRAPH_CONTEXT. Sources: arxiv.org/abs/2602.05665, arxiv.org/abs/2601.03236, arxiv.org/abs/2501.13956 _(completed 2026-03-07)_

## Archived 2026-03-07
- [x] [AUTONOMY_SCREENSHOT_ANALYZE] Take a screenshot of any given URL, analyze with Qwen3-VL, extract structured info. _(2026-03-07: Tested. Fixed JSON parsing — added system prompt + num_predict=1024 so model has budget for thinking+response. example.com: clean JSON, correct title/layout/nav/footer, page_type "docs" vs expected "landing". httpbin form: correct page_type "form", finds radio/input/button/checkbox. HN: complex pages exhaust token budget, CoT fallback still extracts. Aggregate score 51.2% (strict ground truth; semantic quality is higher). Benchmark results in `data/screenshot_benchmark_results.json`.)_
- [x] [EVOLVING_CONSTITUTIONS_MULTIAGENT] Research: Evolving Interpretable Constitutions for Multi-Agent Coordination (arXiv:2602.00755). _(2026-03-07: Ingested to `memory/research/ingested/evolving_constitutions_multiagent_2026-03-07.md` + brain. Key finding: LLM-driven genetic programming evolves constitutions to S=0.556 (123% above hand-designed). Minimal communication principle, multi-island evolution. 3 adoptable patterns documented.)_

## Archived 2026-03-08
- [x] [SUBAGENT_PR_FACTORY_PHASE2_INTAKE] Implement deterministic intake artifacts + precision indexes for subagents (project brief, stack detect, commands, architecture map, trust boundaries; indexes for file/symbol/route/config/test). Stale-aware. Add tests. (See implementation plan Phase 2.) _(completed 2026-03-08: `pr_factory_intake.py` + `pr_factory_indexes.py` + 49 tests + wired into `cmd_spawn` + `build_spawn_prompt`. Validated on star-world-order: 5 artifacts + 5 indexes, ~1.9KB combined prompt injection.)_
- [x] [ACON_CONTEXT_COMPRESSION] Research: ACON — Agentic Context Compression (Kang et al., arXiv:2510.00615). Contrastive guideline optimization: 26-54% token reduction maintaining task success. 5 application ideas documented. _(completed 2026-03-08)_

## Archived 2026-03-08
- [x] [SUBAGENT_PR_FACTORY_PHASE1_PROMPT] Implement PR-factory rules injection as a **wrapper**: add prompt section for PR classes (A/B/C), two‑PR policy, max‑2 refinements, and Class C task-linkage; wire into `project_agent.py` prompt build. Add acceptance tests. (See `docs/subagents/PR_FACTORY_IMPLEMENTATION_PLAN.md` Phase 1.) _(done 2026-03-08: all code + wiring + 23 acceptance tests verified passing)_
- [x] [MEMR3_REFLECTIVE_RETRIEVAL] Research: MemR3 — Reflective Reasoning for Memory Retrieval (arXiv:2512.20237) + Hindsight retain-recall-reflect (arXiv:2512.12818). Maintains explicit evidence-gap state during retrieval: query → retrieve → gap-analysis → re-query until sufficient. Complements existing memory research (storage-focused) by optimizing the retrieval reasoning path. Applicable to brain.py recall pipeline and context_relevance. Sources: arxiv.org/abs/2512.20237, arxiv.org/abs/2512.12818 _(done 2026-03-08)_
- [x] [CLI_HEARTBEAT_EXPAND] Add `clarvis heartbeat preflight` (run preflight only, print JSON) and `clarvis heartbeat postflight` (accepts exit-code + output-file + preflight-file args). Currently only `run` and `gate` exist. _(done 2026-03-08: both subcommands added to `clarvis/cli_heartbeat.py`, with file I/O, error handling, smoke test)_

## Archived 2026-03-08
- [x] [SUBAGENT_PR_FACTORY_PHASE3_BRIEF_WRITEBACK] Implement execution brief compiler + verify/self-review loop control + PR class decision + mandatory writeback (episode summary, atomic facts, procedures, typed edges, golden QA). Add tests. _(completed 2026-03-08: `scripts/pr_factory.py` — classify_task(), build_execution_brief(), build_factory_context(), run_writeback(). 36 tests in `test_pr_factory.py`. Wired into `project_agent.py` build_spawn_prompt + cmd_spawn with graceful degradation. Total PR factory: 108 tests across 3 phases.)_
- [x] [PREFLIGHT_SPEED] Optimize preflight overhead (currently ~100s). Profile task_selector scoring loop — brain lookups for failure penalties on every task is the bottleneck. _(completed 2026-03-08: moved per-task brain.recall to single pre-fetch before loop in `clarvis/orch/task_selector.py` score_tasks(). 20 brain calls → 1. Expected: ~100s → ~5-7s for scoring loop.)_
- [x] [USER_REQUEST 2026-03-08] Research: Andrej Karpathy autoresearch repo — self-evolving research org. _(completed 2026-03-08)_

## Archived 2026-03-08
- [x] [DASHBOARD_OWNER_LABELS] Normalize event schema to always include `owner_type` + `owner_name` so it’s unambiguous which subagent/cron produced a queue/event line. Display in Queue/Completed panels and modal. _(Done 2026-03-08: `infer_owner()` in dashboard_events.py, `_normalize_event_owner()` in dashboard_server.py for legacy backfill, parse_queue owner extraction from [SOURCE DATE] tags, frontend Queue/Completed/Events panels + modal updated.)_
- [x] [RESEARCH_WORLD_MODELS_2026-03-08] Research: World Models (DreamerV3, I-JEPA, LeCun AMI) — useful world models are compact latent predictive simulators for planning/control/transfer, not pixel-perfect generators. Notes: `memory/research/ingested/2026-03-08-world-models-jepa-dreamer.md`.
- [x] [OPENCLAW_2026_3_7_DEEP_REVIEW] Research OpenClaw updates in depth from our current version onward. Identify which new features/plugins/routing/model/context capabilities are genuinely useful for Clarvis, which are irrelevant, and which may clash with our custom setup. Produce a concrete adoption matrix. (2026-03-08 14:05 UTC)

## Archived 2026-03-08
- [x] [SUBAGENT_BRAIN_MATURATION_PHASE1_BRIEF_QUALITY] Improve live execution-brief quality per `docs/subagents/SUBAGENT_BRAIN_MATURATION_PLAN.md`: reliably populate relevant_files, relevant_facts, relevant_episodes, and required_validations from artifacts/indexes/facts/episodes. _(Done 2026-03-08: improved `_find_relevant_files` with symbol index + test index + config index matching; `_extract_validations` handles nested commands format; added `_enrich_facts_from_artifacts` for trust boundary/domain/constraint injection; lowered word match threshold to ≥3 chars. Tested on star-world-order: 5/6 brief fields populated across 5 task types. All 36+49 tests pass.)_
- [x] [SUBAGENT_BRAIN_MATURATION_PHASE4_RELATIONS] Improve typed relationships + hybrid retrieval: route/file, symbol/file, invariant/enforcement, trust-boundary/validation, test/module, module/sector-constraint. Use them to sharpen retrieval and prompt compilation. _(Done 2026-03-08: added `build_typed_edges()`, `get_edges_by_type()`, `get_related()`, `hybrid_recall()` to `lite_brain.py`. Builds route→file (47), symbol→file (338), test→module (2) edges from precision indexes. `hybrid_recall` combines vector recall with typed edge expansion for file+test discovery. Wired into `pr_factory.py` — brief compilation auto-builds edges and uses them. Writeback stores task_class→file edges. All idempotent, deduped. 36+49 tests pass.)_

## Archived 2026-03-08
- [x] [SUBAGENT_BRAIN_MATURATION_PHASE2_RECON] Strengthen recon/evidence generation so subagents identify likely files, symbols/routes, tests, current behavior, and risk notes before coding. Use this to improve prompt grounding and reduce drift. _(Done 2026-03-08: improved `pr_factory.py` — CamelCase/snake_case keyword splitting, dynamic relevance thresholds for sparse brains, episode fallback from task summaries, entrypoint fallback when keyword match fails. Recon grounding: 0.33→1.0 across 6 task classes.)_
- [x] [SUBAGENT_BRAIN_MATURATION_PHASE6_SOAK] Run a controlled soak/evaluation of the matured subagent brain + PR-factory pipeline across multiple real task classes (docs, feature, hardening, blocked task, test-heavy). Produce a trust/quality report. _(Done 2026-03-08: `scripts/subagent_soak_eval.py` — 10-dimension harness: brain health, retrieval quality, artifact freshness, index coverage, brief compilation, recon grounding, writeback pipeline, typed edges, trust trajectory, orchestration benchmark. star-world-order: 10/10 PASS, soak=0.961, verdict=PRODUCTION_READY. Report: `data/orchestration_benchmarks/star-world-order_soak_report.json`)_

## Archived 2026-03-08
- [x] [TASK_LOOP_LOCK_FINALLY] Harden `scripts/project_agent.py run_task_loop()` with a top-level `try/finally` so `_release_loop_lock(name)` always runs on exceptions. _(done 2026-03-08: wrapped lines 2976-3208 in try/finally, 102 tests pass)_
- [x] [SUBAGENT_BRAIN_MATURATION_PHASE5_SECTOR] Formalize sector/product playbooks as a distinct retrieval layer derived from repo docs, linked to modules/invariants but separate from raw repo facts. _(done 2026-03-08: new `project-sector` collection in LiteBrain, `generate_sector_playbook()` in pr_factory_intake, sector retrieval in hybrid_recall + execution brief, writeback support, all tests pass)_
- [x] [RESEARCH_DISCOVERY 2026-03-08] [RESEARCH_HOT_METAREPRESENTATION] Higher-Order Thought (HOT) metarepresentation — Flemming computational HOT (PhilArchive), Rolls 2020 syntactic variant (Frontiers), Brown 2019 HOROR. Consciousness via explicit monitoring of first-order states. Last major Butlin-listed theory gap. _(researched 2026-03-08)_

## Archived 2026-03-08
- [x] [A2A_REQUIRED_SUMMARY_VALIDATION_FIX] Fixed: separated errors vs warnings in `validate_a2a_result()`. Empty/None/non-string summary now correctly invalidates results. Added 4 new tests (empty, None, non-string, both missing). 105/105 tests pass. (2026-03-08)

## Archived 2026-03-08
- [x] [AUTONOMY_MULTI_STEP] Multi-step workflow benchmark — given a sequence of 3+ actions (navigate → search → click result → extract data), complete the full chain. Measure: step completion rate, total success. _(Done 2026-03-08: 4/4 steps PASS in 3.3s via CDP. Navigate→search→click_link→extract_data on Wikipedia. Note: Playwright bundled Chromium broken (missing libatk), must use system Chromium via CDP:18800. Benchmark saved to data/benchmarks/autonomy_multi_step.json.)_
- [x] [SUBAGENT_BRAIN_MATURATION_PHASE3_FACTS] Upgrade atomic fact capture/writeback so reusable repo truths become denser and cleaner: exact invariants, routes, authz points, validated procedures, and useful gotchas with evidence pointers. _(Done 2026-03-08: upgraded `_store_facts` in pr_factory.py — now produces 6 fact types: file_role, invariant, gotcha, route, procedure_evidence, blocker. Success task: 3→12 facts. Blocked task: 2→4 facts with [blocker] tag. Soak eval 10/10 PRODUCTION_READY 0.991.)_
- [x] [WEEKLY_PR_FACTORY_E2E_BENCH] Run an end-to-end benchmark of the PR-factory wrapper on one real task and one deliberately blocked task. Measure whether it emits the correct direct PR or the two-step unblock+task PR flow, and score writeback quality in the resulting brief/docs. _(Done 2026-03-08: Soak eval 10/10 PRODUCTION_READY 0.991. Brief quality strong for both real bugfix + blocked feature tasks. Found & fixed A2A validation bug: missing status defaulted to "success" instead of "unknown". Fixed in project_agent.py + 6 new tests, 111/111 pass.)_

## Archived 2026-03-08
- [x] [ORCH_SUDO_OPT] **BLOCKED: no sudo access.** Need user to run: `sudo mkdir -p /opt/clarvis-agents && sudo chown agent:agent /opt/clarvis-agents`, then `project_agent.py migrate star-world-order`. (2026-03-08 23:09 UTC)
- [x] [CRAWL4AI] Installed Crawl4AI 0.8.0 + created `scripts/research_crawler.py` (crawl/ingest/batch/status). Uses existing CDP:18800 browser. Dedup tracker at `data/research_crawled.json`. Tested on 2 URLs successfully. _(done 2026-03-08)_
- [x] [VISION_FALLBACK] Added Ollama Qwen3-VL fallback to `clarvis_eyes.py`. Auto-triggers when 2Captcha API key missing or API fails. Also added `describe()`, `read_text()` helpers and expanded CLI (solve/describe/read/status). Backend tracked in ChallengeResult. _(done 2026-03-08)_

## Archived 2026-03-09
- [x] [RESEARCH_SESSION 2026-03-09] [IIT_4_0_INTRINSIC_CAUSAL_STRUCTURE] Researched Integrated Information Theory (IIT) 4.0 using primary paper + overview sources. Key takeaway: consciousness is framed as a maximally irreducible intrinsic cause-effect structure with definite boundaries (intrinsicality, information, integration, exclusion, composition), which is useful as a design lens for Clarvis metrics around internal integration rather than observer-only performance. Note: `memory/research/2026-03-09-iit-4.0.md`.
- [x] [RESEARCH_DISCOVERY 2026-03-08] [RESEARCH_SWE_EVO_LONGITUDINAL] SWE-EVO: longitudinal evaluation of code-writing agents that modify their own tooling across sequential tasks (arXiv:2512.18470). Measures evolution retention, capability transfer, catastrophic forgetting. Huxley-Gödel open-ended modification paradigm. _(completed 2026-03-09, note: `memory/research/2026-03-09-swe-evo-self-improving-agents.md`)_
- [x] [RESEARCH_DISCOVERY 2026-03-08] [RESEARCH_CI_VALUE_CONTEXT_SELECTION] Influence-Guided Context Selection via Contextual Influence Value (arXiv:2509.21359). Data-valuation approach: CI score = performance degradation on removal. Integrates query-relevance + list-uniqueness + generator feedback. Targets Context Relevance. _(completed 2026-03-09, note: `memory/research/2026-03-09-ci-value-context-selection.md`)_
- [x] [CI_VALUE_CONTEXT_SCORING] Implement CI-Value scoring from completed research (arXiv:2509.21359) into `context_compressor.py`. Add a `ci_value_rerank()` mode alongside existing MMR: score each context chunk by query-relevance + list-uniqueness + estimated generator-feedback (approximate via token overlap with task description). Use as reranker after ChromaDB recall, before compression. Directly targets Context Relevance (0.838→0.90+). Files: `scripts/context_compressor.py`, reference: `memory/research/2026-03-09-ci-value-context-selection.md`. (2026-03-09 14:04 UTC)
- [x] [STALE_PLANS_ARCHIVE] Non-code: archived stale `data/plans/` files (`cognition-architectures-report.md`, `helixir-analysis.md`, `hive-analysis.md`, `plan-20260219_232719.json`) to `data/plans/archive/`. Active plans left in place: `consciousness-research.md`, `episodic-memory.md`, `foundation-rebuild.md`. No active non-historical filename references needed updating. _(completed 2026-03-09)_

## Archived 2026-03-09
- [x] [DASHBOARD_SYSTEMD_UNIT] Non-code: create a systemd user service for `scripts/dashboard_server.py` (Phase 5 visual ops dashboard). Define `~/.config/systemd/user/clarvis-dashboard.service`, document startup/access in `docs/DASHBOARD.md`, add health check to `health_monitor.sh`. _(Done 2026-03-09: service created, docs written, health check added, service tested running on port 18799.)_

## Archived 2026-03-09
- [x] [RETRIEVAL_EVAL] Build CRAG-style retrieval evaluator in `clarvis/brain/retrieval_eval.py` (2026-03-09). Composite scoring (0.50×semantic_sim + 0.25×keyword_overlap + 0.15×importance + 0.10×recency), 3-tier classification (CORRECT≥0.55, AMBIGUOUS≥0.35, INCORRECT<0.35), knowledge strip refinement on AMBIGUOUS. Wired inline in `heartbeat_preflight.py` §8.6 (INCORRECT → omit knowledge_hints). Extended `retrieval_quality.py` to log verdict+max_score per event. 25 unit tests + demo CLI. All 112 tests pass (87 brain + 25 eval).
- [x] [CHROMADB_SINGLETON] Consolidate ChromaDB instantiation into single factory. All 3 steps complete (2026-03-09):
- [x] [RESEARCH_DISCOVERY 2026-03-08] [RESEARCH_ACE_CONTEXT_EVOLUTION] Agentic Context Engineering (ACE, arXiv:2510.04618). Evolving playbooks that accumulate+refine strategies via generation-reflection-curation loop. Optimizes offline (system prompts) and online (agent memory) contexts. +10.6% on agentic tasks. Targets Context Relevance (0.838). _(completed 2026-03-09, research note: memory/research/2026-03-09-ace-agentic-context-engineering.md)_

## Archived 2026-03-09
- [x] [DASHBOARD_QUEUE_TOPLEVEL_ONLY] Fix `dashboard_server.parse_queue()` so indented/nested queue items are ignored if the intended contract is top-level tasks only. Current test shows nested tasks are being parsed as real queue items. _(done 2026-03-09: removed indented-task regex fallback)_
- [x] [DASHBOARD_QUEUE_DESC_TRUNCATION] Add/restore description truncation in `dashboard_server.parse_queue()` (or align the tests/contracts). Current test shows 200-char descriptions are returned unbounded, breaking the expected <=120-char UI payload. _(done 2026-03-09: added desc[:120] truncation)_
- [x] 2026-03-09 — Researched **Free Energy Principle and world models**. Key insight: FEP is most useful as a normative framework for adaptive agents with generative world models and active inference; it is stronger as an engineering lens for perception/planning/memory than as a full metaphysical theory of consciousness.

## Archived 2026-03-09
- [x] [DASHBOARD_QUEUE_BLOCK_POPUP] Server endpoint `/queue-block/{tag}` + frontend modal on click. _(already done; endpoint in dashboard_server.py, modal in app.js)_
- [x] [CLI_SUBPKG_ABSORB] Evaluate absorbing `clarvis-db`, `clarvis-cost`, `clarvis-reasoning` CLIs into unified `clarvis db|cost|reasoning` subcommands. **BLOCKED: Requires Inverse decision.** Do not auto-select in marathon. (2026-03-09 20:19 UTC)
- [x] [AUTONOMY_SEARCH] Web search benchmark — `scripts/autonomy_search_benchmark.py`. 10 factual questions, 2 approaches: Browser+LLM (100% accuracy, 21.6s avg) vs API/Perplexity (100% accuracy, 1.9s avg). API is 11x faster at equal accuracy. Results: `data/autonomy_search_results.json`. _(completed 2026-03-09)_
- [x] [PERIODIC_SYNTHESIS_IMPORT_FIX] Fixed: `adapters.py` import changed from `from episodic_memory import EpisodicMemory` to `from clarvis.memory.episodic_memory import EpisodicMemory`. Smoke test passes. _(fixed 2026-03-09, was already in working tree)_

## Archived 2026-03-09
- [x] [GRAPH_JSON_WRITE_REMOVAL] After soak completes + SQLite-only writes stable: remove legacy JSON write paths entirely (code cleanup). See RUNBOOK.md checklist; also update backups to include `graph.db`. _(blocked by soak completion — 2026-03-09: soak still failing, 0 consecutive passes. Latest FAIL: -549 nodes, -6691 edges divergence between JSON/SQLite. Root cause unclear — intermittent, passed on 03-06 and 03-08 briefly. Needs investigation of which operations miss SQLite writes.)_ (2026-03-09 22:10 UTC)
- [x] [OPENCLAW_FEATURE_ENABLEMENT_PLAN] Done 2026-03-09. Output: `docs/OPENCLAW_FEATURE_ENABLEMENT_PLAN.md`. 4-tier plan: 8 Tier-1 skills usable now, OTEL+Diffs plugins to enable, context engine spike as main Tier-3 item, 14 features to stay off.
- [x] [OPENAI_SYMPHONY_RESEARCH] Done 2026-03-09. Output: `memory/research/ingested/2026-03-09-openai-symphony.md`. Core finding: WORKFLOW.md-per-project pattern worth stealing for project agents; rest is Linear+Codex specific, overlaps with existing Clarvis architecture.
- [x] [HERMES_AGENT_SELF_EVOLUTION_RESEARCH] Done 2026-03-09. DSPy-based skill evolution pipeline (GEPA optimizer). Adoptable: DSPy SkillModule wrapping + constraint-gated mutation. No memory system — Clarvis ahead. Output: `memory/research/ingested/2026-03-09-hermes-self-evolution-deep-review.md`. 2 brain memories stored.
- [x] [CLARVIS_CONTEXT_ENGINE_RESEARCH] Done 2026-03-09. OpenClaw v2026.3.7 ContextEngine plugin interface (7 lifecycle hooks, TypeScript). Key gap: ClarvisDB invisible to M2.5. Research covers dual pipeline analysis + OpenClaw extension points. 2 brain memories stored.
- [x] [CLARVIS_CONTEXT_ENGINE_CONCEPT] Done 2026-03-09. Design doc: `docs/CLARVIS_CONTEXT_ENGINE.md`. 4-phase rollout: assemble-only → +ingest → +compact → +subagent. Subprocess bridge to prompt_builder.py. Complements ClarvisDB as runtime layer, not replacement.

## Archived 2026-03-10
- [x] [SPINE_MIGRATION_WAVE1_METRICS] Migrate core metrics logic from `scripts/` into `clarvis/metrics/` (phi metric, self-model, performance benchmark) with thin script wrappers only. Add smoke tests and CLI parity checks. _(Done 2026-03-10: phi_metric.py → clarvis/metrics/phi.py (new, 340 lines). self_model.py and benchmark.py already existed in spine. scripts/phi_metric.py converted to thin wrapper re-exporting from spine. All 3 metric modules added to structure_gate spine_smoke check. Legacy import paths preserved. All gates pass.)_
- [x] [STRUCTURE_GATE_SUITE] Add a structural gate suite for Clarvis: compileall, import-health, spine smoke checks, key CLI smoke tests, and targeted pytest groups. Use it as the regression barrier during spine migration. _(Done 2026-03-10: `scripts/structure_gate.py` — 5 gates: compileall, spine_smoke (8 modules), import_health, cli_smoke (5 modules + subcommand check), pytest (4 test files). --quick mode ~0.5s, full ~2.7s. --json for CI integration. All gates pass.)_
- [x] [CONFIDENCE_TIERED_ACTIONS] Enforce tiered action levels from calibration data (ROADMAP Phase 3.1 gap — "not yet enforced"). In `heartbeat_preflight.py`, map confidence predictions to action tiers: HIGH (>0.8) → execute autonomously, MEDIUM (0.5-0.8) → execute with extra validation gate, LOW (<0.5) → skip or flag for manual review. Currently predictions exist but don't gate execution. Files: `scripts/heartbeat_preflight.py`, `scripts/clarvis_confidence.py`. _(Done 2026-03-10: §7.6 tiering gate added to preflight, combines dyn_conf + world model P(success). LOW→defer, MEDIUM→validation prompt injected §10.52, HIGH→autonomous. Bash extraction + logging in cron_autonomous.sh. 11 unit tests added.)_

## Archived 2026-03-10
- [x] [RESEARCH_DISCOVERY 2026-03-10] Research: IIT Consciousness Indicators Applied to LLM Internal Representations (arXiv:2506.22516). Key finding: LLM representations lack significant IIT consciousness indicators but show spatio-permutational patterns. Validates graph-based Phi as structural proxy. 2 brain memories stored, research note at memory/research/ingested/2026-03-10-iit-llm-representations.md. _(done 2026-03-10)_
- [x] [RESEARCH_DISCOVERY 2026-03-10] Research: DSPy Prompt-as-Code — Systematic Multi-Use Case Prompt Self-Optimization (arXiv:2507.03620). Study treating prompts as optimizable code across 5 use cases (guardrails, hallucination detection, code generation, routing agents, prompt evaluation). OPRO achieves 47%+ gains over human prompts. GAAPO uses genetic algorithms for prompt evolution. Applicable to cron prompt self-optimization, heartbeat prompt tuning, and task_router.py prompt engineering. Sources: arxiv.org/abs/2507.03620, frontiersin.org/articles/10.3389/frai.2025.1613007 (2026-03-10 05:38 UTC)
- [x] [SPINE_MIGRATION_WAVE2_CONTEXT] Migrated context assembly + GC into `clarvis/context/`. Created `assembly.py` (tiered brief, decision context, wire guidance, failure patterns, reasoning scaffold, spotlight, workspace context, related tasks, completions) and `gc.py` (archive_completed, rotate_logs, gc). Added `get_latest_scores` to `compressor.py`. All 108 tests pass. Canonical imports: `from clarvis.context import generate_tiered_brief, gc`. _(done 2026-03-10)_

## Archived 2026-03-10
- [x] [RESEARCH_DISCOVERY 2026-03-10] Research: Self-Improving AI Agents through Self-Play — Mathematical Framework (arXiv:2512.02731). _(Done 2026-03-10: Full paper analysis extracted. GVU Operator, Second Law of AGI Dynamics, Variance Inequality, Hallucination Barrier, Verifier SNR Dominance. 5 brain memories stored. Research note: `memory/research/ingested/2026-03-10-self-improving-self-play-gvu.md`. Key insight: strengthen the verifier, not the generator.)_
- [x] [RESEARCH_DISCOVERY 2026-03-10] Research: System 1/System 2 Reasoning RAG — Dual-Speed Retrieval for Industry Challenges (arXiv:2506.10408). Survey of fast-intuitive (System 1) vs slow-deliberative (System 2) reasoning in agentic RAG. Maps directly to QUICK/STANDARD/DEEP heartbeat modes and retrieval tier routing. Covers when to reason through retrieval (multi-hop) vs when to shortcut (cached/routine queries). Targets Context Relevance via adaptive retrieval depth selection. Sources: arxiv.org/abs/2506.10408 (2026-03-10 06:14 UTC)

## Archived 2026-03-10
- [x] [MONTHLY_REFLECTION_CRON] Automate monthly structural reflection (Phase 2 gap, marked "not yet automated" in ROADMAP.md). Create `scripts/cron_monthly_reflection.sh` — runs 1st of month at 03:30, spawns Claude Code to: analyze 30-day episode trends, identify structural script changes needed, propose ROADMAP updates, write output to `memory/cron/monthly_reflection_YYYY-MM.md`. Add crontab entry. _(Done 2026-03-10)_

## Archived 2026-03-10
- [x] [RESEARCH_SESSION 2026-03-10] [FREE_ENERGY_PRINCIPLE_CRITIQUE] Researched Free Energy Principle with emphasis on critique vs engineering value. Key takeaway: FEP is most reliable as a normative framework for generative modeling, uncertainty reduction, and active inference; its metaphysical/consciousness claims are far less secure than its practical value for adaptive agents. Note: `memory/research/2026-03-10-free-energy-principle-critique.md`.
- [x] [SELF_BOOT_AGENTS_DRIFT_CLEANUP] Updated SELF.md (version 2026.3.7, stats 3600+/98k+), AGENTS.md (stats 3600+/98k+), BOOT.md (stats 3600+). All docs aligned with current reality. _(2026-03-10)_
- [x] [UNWIRED_FEATURE_WIRING_PLAN] Audit complete: 4 fully wired, 9 partially wired, 1 unwired (GraphRAG). Ranked wiring plan at `docs/UNWIRED_FEATURE_WIRING_PLAN.md`. Top priorities: wire GraphRAG communities, meta-learning to postflight, failure amplifier to postflight. _(2026-03-10)_
- [x] [BRAIN_HYGIENE_AUTOMATION] Created `scripts/brain_hygiene.py` (backfill + graph-verify + optimize-full + snapshot + regression alerting). Wired into cron (Sun 05:15) and health_monitor.sh (hourly check). Snapshots stored in `data/brain_hygiene/`. _(2026-03-10)_

## Archived 2026-03-10
- [x] [RESEARCH_DISCOVERY 2026-03-10] Research: A-RAG — Hierarchical Retrieval Interfaces for Agentic RAG (arXiv:2602.03442). Three-tool retrieval hierarchy maps to Clarvis: keyword_search→brain.search(), semantic_search→brain.recall(), chunk_read→graph-neighbor expansion. Key finding: 82% of errors are reasoning-chain failures, not retrieval — once retrieval quality improves, invest in reasoning chain quality. Validates RETRIEVAL_GATE 3-tier routing + ADAPTIVE_RETRY iterative approach. 5 brain memories stored. Research note: `memory/research/2026-03-10-arag-hierarchical-retrieval.md`. _(completed 2026-03-10)_
- [x] [CONTEXT_ENGINE_SPIKE] Phase 1 MVP built: `.openclaw/extensions/clarvis-context/index.ts` implements `ContextEngine` interface with `assemble()` → `prompt_builder.py context-brief` bridge (~3.4s latency, within 5s timeout). Plugin manifest at `openclaw.plugin.json`, config in `openclaw.json` (disabled by default, slot=legacy). Activation: set `plugins.slots.contextEngine: "clarvis-context"` + `plugins.entries.clarvis-context.enabled: true`, restart gateway. Compaction/ingest delegate to legacy. Phase 2 (ingest) and Phase 3 (compact) are future sessions. _(completed 2026-03-10)_
- [x] [SKILL_INVENTORY_AUDIT] Deep audit of all 19 skills/ directories (was miscounted as 18). Found: 12 active, 7 stale (missing binaries/deps/API keys: brave-search, gog, himalaya, nano-pdf, notion, summarize, tavily-search). All 19 have SKILL.md. Only 5 wired in gateway config. Output: `docs/SKILL_AUDIT.md` with full status table, dependency checks, and recommendations. _(completed 2026-03-10)_

## Archived 2026-03-10
- [x] [CRON_OUTPUT_QUALITY_AUDIT] Completed 2026-03-10. Report at `docs/CRON_OUTPUT_AUDIT.md`. Key findings: 58% slot utilization, 29 deferral-loop slots wasted (ACTR_WIRING ×11), 6 research-repo timeouts consuming 5.17h. 8 concrete recommendations (R1-R8).
- [x] [CRON_AUTONOMOUS_BATCHING_CLEANUP] Completed 2026-03-10. Removed dead `is_subtask()` function (lines 189-192) and stale comment. MAX_TOTAL_CHARS=900 reviewed: appropriate for 3-task batching (avg task desc ~200-300 chars, 900 prevents prompt bloat). No change needed.

## Archived 2026-03-10
- [x] [AUTONOMY_SCORE_INVESTIGATION] **Scoring artifact fixed.** Root cause: `"FAILED" in l` matched "Verification FAILED: lock held" preflight messages (9 false failures on 2026-03-08). Fix: exclude `"Verification FAILED"` from failure matching in `_assess_autonomous_execution()`. Score recovered 0.57 → 0.77. Test: `clarvis/tests/test_self_model_scoring.py` (4 tests). _(2026-03-10)_

## Archived 2026-03-10
- [x] [SPAWN_ADAPTIVE_TIMEOUT] Add task-category timeout to `scripts/spawn_claude.sh`: accept optional `--category` flag (quick=600s, standard=1200s, research=1800s, build=1800s). Default remains 1200s. Update `cron_research.sh` to pass `--category research`. Prevents research repo timeouts that waste cron slots (hermes-agent timed out at 1500s on 2026-03-06). _(Done 2026-03-10: `--category=CAT` flag added to spawn_claude.sh, category overrides default timeout, explicit timeout still wins. cron_research.sh discovery fallback bumped from 1200s→1800s to match research category.)_
