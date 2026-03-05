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

- [x] (2026-03-05) [RESEARCH_REPO_OPENSTINGER] Review repo: https://github.com/srikanthbellary/openstinger — portable memory harness for agents (FalkorDB + PostgreSQL, 27 MCP tools). Verdict: keep, selectively adapt 3 patterns (bi-temporal edges, hybrid BM25+vector search, session distillation). See memory/research/openstinger_review_2026-03-05.md.
- [ ] [RESEARCH_REPO_OBLITERATUS] Deep review repo: https://github.com/elder-plinius/OBLITERATUS — what it is, core mechanisms, threat model (if any), and whether any components/patterns should be integrated into Clarvis (memory, autonomy, safety, orchestration). Output: 10 bullets + 3 concrete integration ideas or "discard" with reason.
- [x] (2026-03-05) [RESEARCH_IIT_4] Read Albantakis et al. “Integrated information theory (IIT) 4.0” (PLOS/PMC). Key: updated axioms→postulates mapping + Intrinsic Difference (ID) as intrinsic information measure; consciousness ↔ maximally irreducible intrinsic cause–effect structure.
- [ ] [BROWSER_SKILL_DOC] Create skills/web-browse/SKILL.md documenting browser_agent.py capabilities for M2.5.

## Pillar 3: Performance & Reliability (PI > 0.70)

### AGI-Readiness (from 2026-03-04 audit, see docs/AGI_READINESS_ARCHITECTURE_AUDIT.md)


### CLI Migration (see docs/CLI_MIGRATION_PLAN.md)

- [ ] [CLI_BRAIN_LIVE] Verify `clarvis brain health` output matches `python3 scripts/brain.py health` exactly. Fix any discrepancies. Run both and diff.
- [ ] [CLI_SUBPKG_ABSORB] Evaluate absorbing `clarvis-db`, `clarvis-cost`, `clarvis-reasoning` CLIs into unified `clarvis db|cost|reasoning` subcommands. Requires Inverse decision.
- [ ] [CLI_DEAD_SCRIPT_SWEEP] After CLI migration complete: audit which scripts/ `__main__` blocks have zero callers. Move to `scripts/deprecated/`.
- [ ] [CLI_BENCH_EXPAND] Add missing bench subcommands: `record`, `trend [days]`, `check` (exit 1 on failures), `heartbeat` (quick check), `weakest` (weakest metric). All delegate to `scripts/performance_benchmark.py`.
- [ ] [CLI_HEARTBEAT_EXPAND] Add `clarvis heartbeat preflight` (run preflight only, print JSON) and `clarvis heartbeat postflight` (accepts exit-code + output-file + preflight-file args). Currently only `run` and `gate` exist.
- [ ] [CLI_ROOT_PYPROJECT] Create root `pyproject.toml` for the `clarvis` package (if not already present). Define `[project.scripts] clarvis = "clarvis.cli:main"`, set `packages = ["clarvis"]`, pin deps. Prerequisite for CLI_CONSOLE_SCRIPT.

### Codebase Restructuring (see docs/ARCHITECTURE.md)
(Primary: now tracked in P0.)

## Pillar 4: Self-Improvement Loop

- [x] [NOVELTY_TASK_SCORING] Novelty-weighted task selection — compute embedding distance between candidate tasks and last N completed tasks, boost high-novelty tasks with `final_score = base_score * (1 + 0.3 * novelty)`. Prevents "more of the same" trap. Files: task_selector.py (or heartbeat_preflight.py scoring section). (2026-03-05: done — Jaccard word similarity against last 15 episodes in clarvis/orch/task_selector.py, novelty exposed in scoring details)
- [ ] [PREFLIGHT_SPEED] Optimize preflight overhead (currently ~100s). Profile task_selector scoring loop — brain lookups for failure penalties on every task is the bottleneck.

## Pillar 5: Agent Orchestrator (Multi-Project Command Center)

### Milestone 1: First PR Pipeline (target: this week)

### Milestone 2: Cron + Cost (target: next week)
- [ ] [ORCH_CRON_INTEGRATION] Add daily cron: `project_agent.py promote` + `orchestration_benchmark.py run` for active agents.
- [ ] [ORCH_SUDO_OPT] Request sudo: `sudo mkdir -p /opt/clarvis-agents && sudo chown agent:agent /opt/clarvis-agents`, then `project_agent.py migrate star-world-order`.

### Milestone 3: Multi-Agent (target: 2 weeks)

## Backlog

- [x] [COST_PER_TASK_TRACKING] Tag each Claude Code invocation with task ID in cost logging. Create routing effectiveness report showing % of tasks routed to cheap models vs Claude Code. (Source: ARCH_AUDIT_2026-03-05) (2026-03-05: done — added task_costs() + routing_effectiveness() to CostTracker, created scripts/cost_per_task.py report, fixed cron_research.sh + cron_implementation_sprint.sh to pass actual task names)
- [x] [CLI_COST_SUBCOMMAND] Add `clarvis cost daily/budget` subcommands — cost tracking not in unified CLI. (2026-03-05: done — 6 subcommands: daily, weekly, budget, realtime, summary, trend. Registered in clarvis/cli.py)
- [ ] [CRAWL4AI] Install Crawl4AI for automated research ingestion.
- [ ] [BROWSER_TEST] Test: navigate, extract, fill forms, multi-step workflows — comprehensive browser-use capability validation.
- [ ] [VISION_FALLBACK] Add local vision fallback to clarvis_eyes.py — use Ollama when API vision unavailable.
- [ ] [GITHUB_API_TASKS] Given existing GitHub credentials, perform repo management via API: create issues, comment on PRs, read notifications, manage labels. No account creation — user provides PAT.
- [ ] [AUTONOMY_SEARCH] Web search benchmark — given a question, use browser to search, evaluate results, extract answer. Compare with WebSearch tool accuracy.
- [ ] [UNIVERSAL_WEB_AGENT] Any webapp operated via natural language — given credentials and a task description, complete it. Requires session persistence + multi-step + error recovery.

## Non-Code Improvements

- [x] [CONFIDENCE_RECALIBRATION] Fix overconfidence at 90% level (70% actual accuracy). In `clarvis_confidence.py`, add confidence band analysis to `predict()`: if historical accuracy for band 0.85-0.95 is <80%, auto-downgrade new predictions in that band by 0.10. Log adjustments. Target: Brier score 0.12→0.20+ in system health ranking. (2026-03-05: done — _band_accuracy() + auto-downgrade in predict(), also handles 95-100% band, logs recalibration with original_confidence)
- [ ] [ACTR_WIRING] Wire `actr_activation.py` into `brain.py` recall path — add power-law decay scoring as a re-ranking factor after ChromaDB vector search. Longest-stalled item. Hook registration exists in `clarvis/brain/hooks.py` but scoring path needs testing + calibration. Target: recently-accessed memories get retrieval boost, old unused memories decay. (Phase 5 priority #10.)
  - [ ] [ACTR_WIRING_1] Identify the *actual* recall call chain (brain.recall → collection query → merge → rerank) and the correct injection point (file+function names).
  - [ ] [ACTR_WIRING_2] Implement rerank step: take recall results + per-result last_access/access_count, compute ACT-R activation, blend into final score with a tunable weight.
  - [ ] [ACTR_WIRING_3] Add a small deterministic test fixture (5-10 fake memories with timestamps) proving recency/frequency boosts ordering.
  - [ ] [ACTR_WIRING_4] Run real-world smoke benchmark: before/after on a fixed query set; ensure no regression in precision@3.

## P1

- [ ] [RESEARCH_DISCOVERY 2026-03-05] Research: Agent Interoperability Protocols — MCP + A2A + ACP + ANP Survey (arxiv.org/abs/2505.02279). MCP (Anthropic→Linux Foundation AAIF) standardizes tool/data access; A2A (Google→LF, 100+ enterprises) enables secure agent delegation; ACP + ANP for discovery/routing. Directly applicable to project_agent.py orchestration architecture. Maps Clarvis agent protocol to industry standards. Sources: arxiv.org/abs/2505.02279, onereach.ai/blog/guide-choosing-mcp-vs-a2a-protocols
- [ ] [RESEARCH_DISCOVERY 2026-03-05] Research: Runtime Verification & Metacognitive Self-Correction for Agents — MASC (step-level anomaly detection via next-execution reconstruction, ICLR 2026), AgentSpec (DSL for runtime constraint enforcement, 90%+ unsafe action prevention, ICSE 2026), AgentGuard (dynamic probabilistic assurance), SupervisorAgent (agent interaction monitoring). Improves action accuracy through real-time execution guards and self-correction loops. Sources: arxiv.org/abs/2510.14319, arxiv.org/abs/2503.18666, arxiv.org/abs/2509.23864, arxiv.org/abs/2510.26585
- [ ] [RESEARCH_DISCOVERY 2026-03-05] Research: Process Reward Models for Agent Step Verification — ThinkPRM (generative CoT verification, 1% labels, +8% OOD), ToolPRMBench (tool-use PRM evaluation), Critical Step Optimization (verified decision-point preference learning), AgentPRM (actor-critic Monte Carlo). Directly improves action accuracy via step-level error detection before execution commits. Sources: arxiv.org/abs/2504.16828, arxiv.org/abs/2601.12294, arxiv.org/abs/2602.03412, arxiv.org/abs/2502.10325
- [x] [FAILURE_TAXONOMY] Add error type classification to `heartbeat_postflight.py` failure handling. When a task fails, classify the error into one of 5 categories (memory/planning/action/system/timeout) using keyword matching on output. Store as `error_type` tag in episode metadata alongside existing "failure" tag. Enables failure pattern analysis across heartbeats. (Extracted from: AgentDebug research, arXiv:2509.25370) (2026-03-05: done — _classify_error() function, tags in brain learnings + episodes + completeness JSONL)
- [ ] [RECALL_GRAPH_CONTEXT] In `brain.py` recall/search methods, optionally expand results with 1-hop graph neighbors. When a memory is retrieved, also fetch memories connected via existing graph edges and include them as lower-weight "context" entries. No new clustering needed — uses existing 47k+ graph edges. Target: improve complex query recall by providing related context automatically. (Extracted from: RAPTOR/Hierarchical RAG research, arXiv:2401.18059)
- [x] [POSTFLIGHT_COMPLETENESS] Add completeness scoring to `heartbeat_postflight.py`. Count stages executed vs. attempted (e.g. 11/14). Log to `data/postflight_completeness.jsonl`. Alert if <80% stages succeed. Currently, silent hook failures cause invisible data loss — no way to detect degraded postflight execution. (Source: ARCH_AUDIT_2026-03-05) (2026-03-05: done — tracks _pf_errors list, computes ratio, writes JSONL, warns if <80%)
- [x] [SPINE_SHADOW_DEPS] Migrate the 6 scripts imported by spine code via `sys.path` manipulation into proper spine submodules: `somatic_markers` → `clarvis/cognition/`, `clarvis_reasoning` → `clarvis/cognition/`, `graphrag_communities` → `clarvis/brain/`, `cost_api` → `clarvis/orch/`, `soar_engine` → `clarvis/memory/`, `meta_learning` → `clarvis/learning/`. Eliminates hidden `sys.path.insert()` in `clarvis/brain/hooks.py` and `clarvis/orch/*.py`. (Source: ARCH_AUDIT_2026-03-05) (2026-03-05: done — cost_api fully migrated into spine, 5 proxy modules created, all module-level sys.path.insert removed from hooks.py/router.py/task_selector.py/memory modules, 18 tests pass, 7/7 hooks register)
- [x] [SPINE_TEST_SUITE] Create `clarvis/tests/` with integration tests: (1) brain store→recall roundtrip, (2) hook registration completeness check, (3) preflight JSON schema validation, (4) CLI smoke tests (`clarvis brain health`, `clarvis bench pi`, `clarvis queue status`). Target: 5+ tests, all pass in <30s. Currently zero test coverage for spine package. (Source: ARCH_AUDIT_2026-03-05) (2026-03-05: done — 18 tests across 3 files: brain roundtrip (5), hooks (8), CLI smoke (5), all pass in ~10s)
- [x] [HOOK_REGISTRATION_LOGGING] In `clarvis/brain/hooks.py:register_default_hooks()`, log which hooks registered and which failed. Currently all failures silently swallowed by try/except. Add summary: "Registered 4/5 hooks (failed: graphrag_communities)". Small change, high visibility. (Source: ARCH_AUDIT_2026-03-05) (2026-03-05: done — logs via logging + stderr, shows registered/failed counts)
- [x] [PHI_METRIC_SINGLETON] Fix `phi_metric.py` creating fresh `ClarvisBrain()` instances instead of using `get_brain()` singleton. Bypasses hook registration and creates duplicate ChromaDB clients. Change to `from clarvis.brain import get_brain; brain = get_brain()`. (Source: ARCH_AUDIT_2026-03-05) (2026-03-05: done — uses spine get_brain() with legacy ClarvisBrain fallback)
- [x] [GRAPH_INTEGRITY_CHECK] Add checksum verification to graph load/save in `clarvis/brain/graph.py`. On load, verify edge count matches expected. On save, write atomic with edge-count header. Detect silent corruption of the 70k-edge `relationships.json`. (Source: ARCH_AUDIT_2026-03-05) (2026-03-05: done — _save_graph writes _edge_count header, _load_graph verifies + logs warnings)

## NEW ITEMS (2026-03-05 evolution session)

- [ ] [INTRA_DENSITY_BOOST] Improve intra_collection_density from 0.38 → 0.55+. In `brain.py` or a new script, for each collection with density < 0.40, run pairwise similarity on stored memories and auto-link pairs with cosine > 0.65 as intra-collection graph edges. Currently only cross-collection edges exist (109k+), intra-collection linking is sparse. This is the lowest Phi sub-metric and directly blocks Phi > 0.80. Files: `scripts/brain.py`, `clarvis/brain/graph.py`.
- [ ] [ACTION_VERIFY_GATE] Add pre-execution action verification to `heartbeat_preflight.py`. Before committing a selected task to Claude Code, verify: (1) task description parses to concrete steps, (2) required files/scripts referenced in the task exist, (3) no conflicting lock held. Log verification result. Reject tasks that fail verification and fall through to next candidate. Targets action accuracy (0.968 → 0.98+) by preventing ill-defined tasks from consuming heartbeat slots. Draws on Process Reward Models research in queue.
- [ ] [MONTHLY_REFLECTION_CRON] Automate monthly structural reflection (Phase 2 gap, marked "not yet automated" in ROADMAP.md). Create `scripts/cron_monthly_reflection.sh` — runs 1st of month at 03:30, spawns Claude Code to: analyze 30-day episode trends, identify structural script changes needed, propose ROADMAP updates, write output to `memory/cron/monthly_reflection_YYYY-MM.md`. Add crontab entry.
- [ ] [SKILL_INVENTORY_AUDIT] Non-code audit: check all 18 skills/ directories for (1) missing SKILL.md, (2) stale/broken tool references in skill config, (3) skills not referenced by any agent or cron job. Output a markdown table to `docs/SKILL_AUDIT.md` with status per skill (active/stale/undocumented). Identifies dead weight and documentation gaps. No Python required — shell + manual inspection.

## P1 — Added by Refactor Completion Audit (2026-03-05)

- [x] [GOLDEN_QA_MAIN_BRAIN] Create golden QA benchmark for main ClarvisDB brain. Write 15+ queries with expected top-3 results covering all 10 collections. Implement as `scripts/retrieval_benchmark.py` (or extend existing). Track P@1, P@3, MRR over time. Run after any brain code change. Critical for proving retrieval quality isn't silently degrading. No golden QA exists for the main brain (only project agents have it). (Source: REFACTOR_COMPLETION_PLAN_2026-03-05) (2026-03-05: done — retrieval_benchmark.py already had 20 ground-truth pairs, added `clarvis bench golden-qa` CLI, baseline: P@1=1.000, P@3=0.883, MRR=1.000, 20/20 recall)

## P2 — Reclassified

- [ ] [CRON_AUTONOMOUS_BATCHING_CLEANUP] (was P0 CRON_AUTONOMOUS_BATCHING_BUG — reclassified after investigation: the `<<'PY'` heredoc + `NEXT_TASK` env var mechanism is correct, NOT a bug). Remaining cleanup: remove dead `is_subtask()` function (~lines 186-189), review `MAX_TOTAL_CHARS=900` limit. Low priority.
- [ ] [PARALLEL_BRAIN_QUERIES] Implement parallel collection queries in `clarvis/brain/search.py` using `concurrent.futures.ThreadPoolExecutor`. Currently queries 10 collections sequentially (~7.5s avg). ONNX runtime is thread-safe. Merge and re-rank after parallel fetch. Target: <2s brain query latency. (Source: REFACTOR_COMPLETION_PLAN_2026-03-05, AGI_READINESS audit)