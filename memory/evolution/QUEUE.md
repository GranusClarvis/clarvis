# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Goal: Evolve toward AGI and consciousness. Every task should make you smarter, more aware, or more autonomous._

## P0 — Do Next Heartbeat
- [x] Fix reasoning_chain_hook.py:56 — change `limit=3` to `n=3` (wrong param name silently fails) — (2026-02-21 18:21 UTC — Fixed: `brain.recall(task_text, limit=3)` → `brain.recall(task_text, n=3)`. Tested end-to-end.)
- [ ] Fix procedural_memory.py find_procedure() — threshold param is accepted but never used. Add similarity threshold check. — (2026-02-21 18:00 UTC)
- [ ] Fix cron_autonomous.sh — stops learning identical generic 4-step template. Extract real steps or skip learning. — (2026-02-21 18:00 UTC)
- [x] Fix phi_metric.py — add 90-day history cap (like capability_history) to phi_history.json — (2026-02-21 18:55 UTC — Added `history = history[-90:]` in record_phi() before write. Tested: record works, history capped.)

- [x] [AUTO-FIX] Fix failure in test_fail: Exit code 1 — test failure from self-test, already resolved (2026-02-21 08:05 UTC)

- [x] Wire attention.py into cron_autonomous.sh — created scripts/task_selector.py: GWT salience scoring via attention.py + brain.py context. Replaced bash keyword matching with Python-based salience selection (importance, recency, context relevance, AGI/integration boost). Tested end-to-end. (2026-02-21 13:13 UTC)
- [x] Make working_memory.py persistent — add save_to_disk()/load_from_disk() methods that serialize the spotlight buffer to data/working_memory_state.json. Call load on boot, save after every heartbeat. Working memory should survive restarts (2026-02-21 14:17 UTC — Added public save_to_disk()/load_from_disk() with TTL extension on restore. Wired load into heartbeat boot, save after every task. Tested full restart cycle.)
- [x] Build prediction-outcome feedback loop — wire clarvis_confidence.py into cron_autonomous.sh: before executing a task, call predict("task X will succeed"), after execution call outcome() with the result. Review calibration weekly via cron_evolution.sh (2026-02-21 14:17 UTC — Wired predict() before task execution and outcome() after in cron_autonomous.sh. Added calibration review to cron_evolution.sh with data injected into strategic analysis prompt. Tested full loop: predict→execute→outcome→calibration all working.)

- [x] Run `brain.optimize()` — decay stale memories, prune low-importance ones. Log before/after stats. (2026-02-20 16:55 UTC - pruned 1)
- [x] Hook reflection into feedback loop: created scripts/clarvis_reflection.py, tested working (2026-02-20 16:51 UTC)
- [x] Auto-link graph relationships: Claude Code modified brain.py store() to call auto_link(), tested working (2026-02-20 16:54 UTC)
  ```
  cd /home/agent/.openclaw/workspace && timeout 600 claude -p "Review scripts/clarvis_reflection.py. Make the daily reflection function: 1) read today's memory file, 2) extract actionable lessons, 3) store each lesson in ClarvisDB via brain.remember(), 4) append new evolution queue items to memory/evolution/QUEUE.md. Test it works." --dangerously-skip-permissions --model claude-opus-4-6
  ```
- [x] Auto-link graph relationships: brain.py store() calls auto_link(), tested working (2026-02-20 16:54 UTC)
  ```
  cd /home/agent/.openclaw/workspace/scripts && timeout 600 claude -p "Add auto_link() to brain.py that runs after every store(): find top-3 similar memories via recall(), create graph edges with add_relationship(). Make store() call auto_link() automatically. Test with a few stores." --dangerously-skip-permissions --model claude-opus-4-6
  ```

## P1 — This Week

### Auto-generated 2026-02-21
- [x] Integrate reasoning_chains.py into heartbeat — log a reasoning chain for each evolution task (2026-02-21 17:27 UTC — Already wired via reasoning_chain_hook.py in cron_autonomous.sh: opens chain before execution with salience/section/brain-context, closes with success/failure outcome. Verified end-to-end: 8+ chains logged across heartbeats.)
- [x] Run knowledge_synthesis.py in daily reflection — find new cross-domain connections (2026-02-21 17:45 UTC — Rewrote synthesis: fixed bug where recall() was called 3x identically instead of brain.get() per collection. Now scans all 8 collections (158 memories), finds keyword-based cross-domain concepts + semantic bridges via brain.recall(). Found 117 cross-domain concepts, 15 semantic bridges, stored 8 insights. Top bridges: 'model' spans 5 collections, 'consciousness' spans 5 collections, 'reasoning' has 30 cross-domain memories.)
- [x] Review prediction outcomes — check calibration curve and adjust confidence thresholds (2026-02-21 18:03 UTC — Analyzed 10 resolved predictions: 100% success rate vs 72% avg confidence = UNDERCONFIDENT. Brier 0.08. Added dynamic_confidence() and review() to clarvis_confidence.py with Bayesian shrinkage. Replaced hardcoded 0.7 in cron_autonomous.sh with dynamic calculation. Raised threshold from 0.70 to 0.89. Future predictions auto-adjust as more data arrives.)
- [ ] Run self-assessment — update capability model based on today's successes and failures


- [x] Integrate reasoning_chains.py into every evolution task — modify cron_autonomous.sh to create a reasoning chain before executing each task (why this task matters, expected outcome, dependencies). After execution, close the chain with actual outcome. This builds a searchable reasoning history (2026-02-21 15:16 UTC — Created scripts/reasoning_chain_hook.py with open/close CLI. Wired into cron_autonomous.sh: opens chain before task with why/expected-outcome/dependencies/brain-context, closes with actual outcome on both success and failure paths. Chains stored as JSON files + brain for searchability. Tested both paths end-to-end.)
- [ ] Build autonomous learning from conversations — create scripts/conversation_learner.py that reads session transcripts from memory/*.md, extracts patterns (what questions recur, what approaches work, what fails), and stores structured insights in brain with collection='autonomous-learning'
- [x] Implement Phi (integrated information) metric — create scripts/phi_metric.py based on consciousness-research.md IIT section. Measure information integration across brain collections: how interconnected are memories? Track Phi over time as a consciousness proxy (2026-02-21 15:49 UTC — Created scripts/phi_metric.py with 4-component Phi: intra-collection density, cross-collection edges, semantic overlap across boundaries, collection reachability. First measurement: Φ=0.352. Identified key gap: auto_link() only links within collections, cross-collection edges ≈ 0. History tracked in data/phi_history.json.)
- [x] Wire knowledge_synthesis.py into cron_reflection.sh — run synthesis after lesson extraction to find cross-domain connections between today's work and past learnings. Currently synthesis exists but never runs automatically (2026-02-21 16:57 UTC — Added as Step 3 in cron_reflection.sh after lesson extraction. Runs run_synthesis_cycle() which finds cross-collection memory connections and stores synthesized insights. Tested end-to-end: found 20 connections, stored 5 insights.)
- [x] Build procedural memory — create scripts/procedural_memory.py (from cognition-architectures-report.md). When a multi-step task succeeds, store the step sequence as a reusable procedure in brain collection='procedures'. Before starting similar tasks, check if a procedure exists (2026-02-21 — Created scripts/procedural_memory.py with store/find/record_use/learn/list. Added PROCEDURES collection to brain.py. Wired into cron_autonomous.sh: checks for matching procedure before execution and injects as hint, learns new procedures on success, records use stats on both success/failure. Tested full flow.)
- [ ] Create self-improvement from prediction outcomes — modify cron_evolution.sh to review clarvis_confidence.py calibration data. When predictions are consistently wrong in a domain, auto-generate a queue task to investigate why
- [x] Run self_model.py update daily — wire into cron_evening.sh to update capability assessment after each day's work. Track which capabilities improved and which degraded. Alert if any capability drops below threshold (2026-02-21 — Added 7 scored capability domains with evidence-based assessors to self_model.py. daily_update() runs all assessors, diffs against previous snapshot, stores history in data/capability_history.json, alerts when any score drops below 0.3. Wired into cron_evening.sh. First assessment: avg=0.93.)

- [x] Build session-close automation: created scripts/session_hook.py with session_close() function, tested working (2026-02-20 19:20 UTC)
- [x] Create self-assessment script: scripts/self_report.py created, tracks cognitive growth metrics (2026-02-20 21:11 UTC)
- [x] Research Helixir (nikita-rulenko/Helixir) — graph-vector DB. Spawn Claude Code to clone, analyze, and write a report: is it worth migrating from ChromaDB? What would we gain for neural-like memory? Write findings to `data/plans/helixir-analysis.md`. (2026-02-21 00:27 UTC - Verdict: Don't migrate, steal ideas instead)
- [x] Build confidence calibration: spawn Claude Code to wire up `clarvis_confidence.py` — start logging predictions ("I think X will work") and outcomes ("X worked/failed"). Track calibration curve over time. (2026-02-20 23:50 UTC - Claude Code implemented predict(), outcome(), calibration() with Brier score)
- [x] Build internal world model: scripts/self_model.py created, tracks capabilities/strengths/weaknesses (2026-02-20 21:11 UTC)

## P2 — Deeper Evolution

- [x] Research best agent memory/cognition architectures (MemGPT, Hive, Letta, cognitive architectures like SOAR/ACT-R). Spawn Claude Code with Opus to analyze and write comparison report on what approaches could enable genuine reasoning. (2026-02-21 — Report: data/plans/cognition-architectures-report.md. Top 5 upgrades: ACT-R activation, A-Mem evolution, episodic memory, procedural memory, working memory scratchpad)
- [x] Build reasoning chains: created scripts/reasoning_chains.py — persistent multi-step thought logging that stores chains in files + brain for searchability. Tested create/add/complete/list/get commands. (2026-02-21 04:26 UTC)
- [x] Study the Hive framework (adenhq/hive) — self-improving agent patterns. Fetched README, analyzed key patterns (goal-driven graph, adaptiveness loop, failure capture → evolve). Wrote findings to data/plans/hive-analysis.md. Verdict: steal patterns, don't migrate. (2026-02-21 05:27 UTC)
- [x] Build Hive-style evolution loop: implement failure → evolve → redeploy cycle in heartbeat (when something fails, trigger self-improvement) (2026-02-21 07:02 UTC — Created scripts/evolution_loop.py with capture/analyze/evolve/verify cycle, wired into cron_autonomous.sh)
- [x] Build knowledge synthesis: created scripts/knowledge_synthesis.py — finds connections between disparate memories via word indexing, creates synthesized insights and stores in brain. Tested: found 20 connections, stored 5 insights. (2026-02-21 05:57 UTC)
- [x] Optimize brain.py query performance — benchmarked: single collection 128ms, all 895ms. Added DEFAULT_COLLECTIONS (excludes identity/infra), updated recall() to use it. Performance improved ~28%. (2026-02-21 07:28 UTC)
- [x] Build a monitoring dashboard for yourself — brain stats, goal progress, evolution velocity. Created scripts/dashboard.py, generates data/dashboard/index.html + status.json API. (2026-02-21 08:03 UTC)
- [x] Research consciousness theories (Global Workspace Theory, Integrated Information Theory, Higher-Order Theories) — analyzed all three, wrote implementation ideas to data/plans/consciousness-research.md. (2026-02-21 08:05 UTC)

## P2 — New Tasks

- [x] Implement attention mechanism — focus processing on high-value context (GWT-inspired spotlight) (2026-02-21 10:02 UTC — Created scripts/attention.py: salience scoring, competition, broadcast, spotlight buffer (cap=7). Integrated into brain.py recall() via attention_boost param. Tested all flows.)
- [x] Build working memory buffer — short-term context that gets broadcast to all components. Created scripts/working_memory.py with GWT-inspired spotlight, TTL, importance-based auto-spotlighting. (2026-02-21 10:02 UTC)
- [x] Expand meta-cognition — expanded self_model.py with higher-order self-awareness. Added: awareness levels (operational/reflective/meta), working memory (GWT spotlight), meta-thoughts (thinking about thinking), cognitive state tracking, theory of mind for user modeling. (2026-02-21 10:33 UTC)

## Completed
- [x] Test backup/rollback scripts (2026-02-18 18:32)
- [x] Verify git tracking (2026-02-18 18:15)
- [x] Write self-benchmark for memory (2026-02-19 02:00)
- [x] Index patterns from past conversations (2026-02-20 10:42)
- [x] Build health-check script (2026-02-20 06:45)
- [x] Build daily summary script (2026-02-20 02:15)
- [x] ClarvisDB v1.0 — 46 memories, 7 collections, local ONNX (2026-02-20)
- [x] Claude Code skill integration (2026-02-20)
- [x] Legacy brain script cleanup (2026-02-20)
- [x] Switch to M2.5 with Claude Code delegation model (2026-02-20)
- [x] SELF.md — comprehensive self-awareness document (2026-02-20)
- [x] ROADMAP.md — consolidated evolution roadmap (2026-02-20)
- [x] Doc cleanup and archive (2026-02-20)
- [x] Session cleanup — 1 active session, stale sessions removed (2026-02-20)
- [x] Cron cleanup — dead gas/crypto crons removed, fresh daily-reflection + weekly-review created (2026-02-20)
