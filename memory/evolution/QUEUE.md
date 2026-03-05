# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items auto-archived to QUEUE_ARCHIVE.md._

## P0 — Do Next Heartbeat

_(empty — no urgent bugs)_

---

## Pillar 1: Consciousness & Integration (Phi > 0.80)

(Constraint: pursue only where it improves the brain’s practical intelligence — retrieval quality, correct integration, planning reliability.)

- [ ] [SEMANTIC_BRIDGE] Build semantic overlap booster for cross-collection pairs with overlap <0.50. Current: semantic_cross_collection=0.568 (Phi=0.708). Target: raise to 0.65+ to push Phi toward 0.80.

## Pillar 2: Autonomous Execution (Success > 85%)

- [ ] [AUTONOMY_LOGIN] Given credentials in .env, log into a web service and verify logged-in state (session cookie present, profile page accessible). User provides credentials manually.
- [ ] [AUTONOMY_POST] Given credentials + a platform (e.g. GitHub Issues via API, or a forum), compose and post a message autonomously. Measure: post appears, content matches intent.
- [ ] [AUTONOMY_SCREENSHOT_ANALYZE] Take a screenshot of any given URL, analyze it with local vision (Qwen3-VL), extract structured info (page type, main elements, interactive components). Measure: extraction accuracy vs manual ground truth.
- [ ] [AUTONOMY_MULTI_STEP] Multi-step workflow benchmark — given a sequence of 3+ actions (navigate → search → click result → extract data), complete the full chain. Measure: step completion rate, total success.

## Research Sessions

- [x] [RESEARCH_REPO_OBLITERATUS] Deep review repo: https://github.com/elder-plinius/OBLITERATUS — alignment removal toolkit. Verdict: selectively adopt patterns (analysis-driven config, perturbation-based redundancy detection, geometric fingerprinting). Full review: `memory/research/OBLITERATUS_review.md`.
- [ ] [RESEARCH_REPO_AGENCY_AGENTS] Review repo: https://github.com/msitarzewski/agency-agents — evaluate for delegation/sub-agent orchestration patterns applicable to Clarvis. Output: summary + 3 adoptable patterns.
- [ ] [BROWSER_SKILL_DOC] Create skills/web-browse/SKILL.md documenting browser_agent.py capabilities for M2.5.

## Pillar 3: Performance & Reliability (PI > 0.70)

- [x] [GRAPH_STORAGE_UPGRADE] Replace JSON graph store with SQLite + WAL. Decision: SQLite wins on all axes (zero deps, ACID, indexed lookups, 355x write improvement). See `docs/GRAPH_STORAGE_RECOMMENDATION_2026-03-05.md`.
  - [x] [GRAPH_STORAGE_UPGRADE_1] Evaluate & decide — **SQLite + WAL** selected. Decision matrix in recommendation doc. JSON is 21MB/85k edges, full rewrite on every edge add (355ms). SQLite: <1ms per insert, indexed lookups, ACID transactions, zero new dependencies.
  - [x] [GRAPH_STORAGE_UPGRADE_2] Implement `clarvis/brain/graph_store_sqlite.py` — `GraphStoreSQLite` class wrapping SQLite. Schema: `nodes(id, collection, added_at, backfilled, metadata)`, `edges(id, from_id, to_id, type, created_at, source_collection, target_collection, weight, last_decay)` with UNIQUE(from_id, to_id, type). Indices on from_id, to_id, type, (from_id, type), (collection). WAL mode, busy_timeout=5000, synchronous=NORMAL. API mirrors GraphMixin. Config flag: `CLARVIS_GRAPH_BACKEND` env var in constants.py. 33 pytest tests pass.
  - [x] [GRAPH_STORAGE_UPGRADE_3] Migration tool: `scripts/graph_migrate_to_sqlite.py` — load `relationships.json`, bulk-insert into `data/clarvisdb/graph.db` via `executemany` in single transaction. Verified: 2595 nodes + 85164 edges migrated in 0.69s, 100/100 random edge sample match, 0 duplicates, PRAGMA integrity_check OK. DB size: 41MB.
  - [x] [GRAPH_STORAGE_UPGRADE_4] Dual-write/dual-read in `GraphMixin`: write to both JSON and SQLite, read from SQLite, periodic verification. Rollback via `CLARVIS_GRAPH_BACKEND=json` env var. **Done 2026-03-05**: `graph.py` dual-writes all operations (add_relationship, backfill, bulk_intra_link, decay_edges) to SQLite when `CLARVIS_GRAPH_BACKEND=sqlite`. Reads use SQLite indexed lookups. `verify_graph_parity()` compares counts + random edge sample. CLI: `clarvis brain graph-verify`. 17 new tests + 33 existing pass. Soak period: set `CLARVIS_GRAPH_BACKEND=sqlite` to enable.
  - [ ] [GRAPH_STORAGE_UPGRADE_5] Update consumers: `graph_compaction.py` (use DELETE WHERE instead of list filtering), `cron_graph_checkpoint.sh` (use `conn.backup()`), `graphrag_communities.py` (load from SQLite). Bench: load, add_edge, get_related, bulk_link before/after.
  - [ ] [GRAPH_STORAGE_UPGRADE_6] Cutover: remove JSON write paths, archive `relationships.json` for 30 days, update RUNBOOK.md + ARCHITECTURE.md + CLAUDE.md references.

### AGI-Readiness (from 2026-03-04 audit, see docs/AGI_READINESS_ARCHITECTURE_AUDIT.md)

- [ ] [CHROMADB_SINGLETON] Consolidate 5 different ChromaDB instantiation patterns (main brain, local brain, lite brain, VectorStore, deprecated) into a single factory function. Identified by ARCH_AUDIT_2026-03-05: multiple singletons cause embedding model loaded multiple times, inconsistent collection access, and silent divergence. Target: single `get_brain()` entry point for all callers.

### CLI Migration (see docs/CLI_MIGRATION_PLAN.md)

- [ ] [CLI_BRAIN_LIVE] Verify `clarvis brain health` output matches `python3 scripts/brain.py health` exactly. Fix any discrepancies. Run both and diff.
- [ ] [CLI_SUBPKG_ABSORB] Evaluate absorbing `clarvis-db`, `clarvis-cost`, `clarvis-reasoning` CLIs into unified `clarvis db|cost|reasoning` subcommands. Requires Inverse decision.
- [ ] [CLI_DEAD_SCRIPT_SWEEP] After CLI migration complete: audit which scripts/ `__main__` blocks have zero callers. Move to `scripts/deprecated/`.
- [ ] [CLI_BENCH_EXPAND] Add missing bench subcommands: `record`, `trend [days]`, `check` (exit 1 on failures), `heartbeat` (quick check), `weakest` (weakest metric). All delegate to `scripts/performance_benchmark.py`.
- [ ] [CLI_HEARTBEAT_EXPAND] Add `clarvis heartbeat preflight` (run preflight only, print JSON) and `clarvis heartbeat postflight` (accepts exit-code + output-file + preflight-file args). Currently only `run` and `gate` exist.

### Codebase Restructuring (see docs/ARCHITECTURE.md)
(Primary: now tracked in P0.)

## Pillar 4: Self-Improvement Loop

- [ ] [PREFLIGHT_SPEED] Optimize preflight overhead (currently ~100s). Profile task_selector scoring loop — brain lookups for failure penalties on every task is the bottleneck.

## Pillar 5: Agent Orchestrator (Multi-Project Command Center)

### Milestone 1: First PR Pipeline (target: this week)

### Milestone 2: Cron + Cost (target: next week)
- [ ] [ORCH_CRON_INTEGRATION] Add daily cron: `project_agent.py promote` + `orchestration_benchmark.py run` for active agents.
- [ ] [ORCH_SUDO_OPT] Request sudo: `sudo mkdir -p /opt/clarvis-agents && sudo chown agent:agent /opt/clarvis-agents`, then `project_agent.py migrate star-world-order`.

### Milestone 3: Multi-Agent (target: 2 weeks)

## Backlog

- [ ] [CRAWL4AI] Install Crawl4AI for automated research ingestion.
- [ ] [BROWSER_TEST] Test: navigate, extract, fill forms, multi-step workflows — comprehensive browser-use capability validation.
- [ ] [VISION_FALLBACK] Add local vision fallback to clarvis_eyes.py — use Ollama when API vision unavailable.
- [ ] [GITHUB_API_TASKS] Given existing GitHub credentials, perform repo management via API: create issues, comment on PRs, read notifications, manage labels. No account creation — user provides PAT.
- [ ] [AUTONOMY_SEARCH] Web search benchmark — given a question, use browser to search, evaluate results, extract answer. Compare with WebSearch tool accuracy.
- [ ] [UNIVERSAL_WEB_AGENT] Any webapp operated via natural language — given credentials and a task description, complete it. Requires session persistence + multi-step + error recovery.

## Non-Code Improvements

- [ ] [ACTR_WIRING] Wire `actr_activation.py` into `brain.py` recall path — add power-law decay scoring as a re-ranking factor after ChromaDB vector search. Hook registration exists in `clarvis/brain/hooks.py` and scoring path works end-to-end. Remaining: calibration of RETRIEVAL_TAU (memories with <3 accesses get clipped to floor score). (Phase 5 priority #10.)
  - [ ] [ACTR_WIRING_4] Run real-world smoke benchmark: before/after on a fixed query set; ensure no regression in precision@3. Calibrate RETRIEVAL_TAU (current -2.0 clips single-access memories).

## P1

- [ ] [RESEARCH_DISCOVERY 2026-03-05] Research: Agent Interoperability Protocols — MCP + A2A + ACP + ANP Survey (arxiv.org/abs/2505.02279). MCP (Anthropic→Linux Foundation AAIF) standardizes tool/data access; A2A (Google→LF, 100+ enterprises) enables secure agent delegation; ACP + ANP for discovery/routing. Directly applicable to project_agent.py orchestration architecture. Maps Clarvis agent protocol to industry standards. Sources: arxiv.org/abs/2505.02279, onereach.ai/blog/guide-choosing-mcp-vs-a2a-protocols
- [ ] [RESEARCH_DISCOVERY 2026-03-05] Research: Runtime Verification & Metacognitive Self-Correction for Agents — MASC (step-level anomaly detection via next-execution reconstruction, ICLR 2026), AgentSpec (DSL for runtime constraint enforcement, 90%+ unsafe action prevention, ICSE 2026), AgentGuard (dynamic probabilistic assurance), SupervisorAgent (agent interaction monitoring). Improves action accuracy through real-time execution guards and self-correction loops. Sources: arxiv.org/abs/2510.14319, arxiv.org/abs/2503.18666, arxiv.org/abs/2509.23864, arxiv.org/abs/2510.26585
- [ ] [RESEARCH_DISCOVERY 2026-03-05] Research: Process Reward Models for Agent Step Verification — ThinkPRM (generative CoT verification, 1% labels, +8% OOD), ToolPRMBench (tool-use PRM evaluation), Critical Step Optimization (verified decision-point preference learning), AgentPRM (actor-critic Monte Carlo). Directly improves action accuracy via step-level error detection before execution commits. Sources: arxiv.org/abs/2504.16828, arxiv.org/abs/2601.12294, arxiv.org/abs/2602.03412, arxiv.org/abs/2502.10325
- [ ] [RECALL_GRAPH_CONTEXT] In `brain.py` recall/search methods, optionally expand results with 1-hop graph neighbors. When a memory is retrieved, also fetch memories connected via existing graph edges and include them as lower-weight "context" entries. No new clustering needed — uses existing 85k+ graph edges. Target: improve complex query recall by providing related context automatically. **Depends on**: [GRAPH_STORAGE_UPGRADE] — indexed SQLite lookups make per-recall graph expansion feasible (<0.1ms vs 4ms per hop). (Extracted from: RAPTOR/Hierarchical RAG research, arXiv:2401.18059)

## NEW ITEMS (2026-03-05 evolution session)

- [ ] [INTRA_DENSITY_BOOST] Improve intra_collection_density from 0.38 → 0.55+. In `brain.py` or a new script, for each collection with density < 0.40, run pairwise similarity on stored memories and auto-link pairs with cosine > 0.65 as intra-collection graph edges. Currently only cross-collection edges exist (109k+), intra-collection linking is sparse. This is the lowest Phi sub-metric and directly blocks Phi > 0.80. Files: `scripts/brain.py`, `clarvis/brain/graph.py`.
- [ ] [ACTION_VERIFY_GATE] Add pre-execution action verification to `heartbeat_preflight.py`. Before committing a selected task to Claude Code, verify: (1) task description parses to concrete steps, (2) required files/scripts referenced in the task exist, (3) no conflicting lock held. Log verification result. Reject tasks that fail verification and fall through to next candidate. Targets action accuracy (0.968 → 0.98+) by preventing ill-defined tasks from consuming heartbeat slots. Draws on Process Reward Models research in queue.
- [ ] [MONTHLY_REFLECTION_CRON] Automate monthly structural reflection (Phase 2 gap, marked "not yet automated" in ROADMAP.md). Create `scripts/cron_monthly_reflection.sh` — runs 1st of month at 03:30, spawns Claude Code to: analyze 30-day episode trends, identify structural script changes needed, propose ROADMAP updates, write output to `memory/cron/monthly_reflection_YYYY-MM.md`. Add crontab entry.
- [ ] [SKILL_INVENTORY_AUDIT] Non-code audit: check all 18 skills/ directories for (1) missing SKILL.md, (2) stale/broken tool references in skill config, (3) skills not referenced by any agent or cron job. Output a markdown table to `docs/SKILL_AUDIT.md` with status per skill (active/stale/undocumented). Identifies dead weight and documentation gaps. No Python required — shell + manual inspection.

## P1 — Added by Refactor Completion Audit (2026-03-05)


## P2 — Reclassified

- [ ] [CRON_AUTONOMOUS_BATCHING_CLEANUP] (was P0 CRON_AUTONOMOUS_BATCHING_BUG — reclassified after investigation: the `<<'PY'` heredoc + `NEXT_TASK` env var mechanism is correct, NOT a bug). Remaining cleanup: remove dead `is_subtask()` function (~lines 186-189), review `MAX_TOTAL_CHARS=900` limit. Low priority.