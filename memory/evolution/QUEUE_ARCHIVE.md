# Evolution Queue — Archive

_Completed items archived from QUEUE.md to reduce token footprint._
_Last archived: 2026-03-03_

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
