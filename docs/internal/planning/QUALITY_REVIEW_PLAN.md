# Clarvis Quality Review Plan

**Created**: 2026-04-08
**Scope**: Full system — spine, scripts, tests, data, docs, CLI, wiki, agents, cron, metrics
**Codebase size**: ~50.7K lines spine + ~75K lines scripts + ~23K lines tests = ~149K lines total

---

## 1. Review Framework

### 1.1 Phases

The review proceeds in four phases, each building on findings from the previous:

| Phase | Name | Focus | Duration estimate |
|-------|------|-------|-------------------|
| **P1** | Structural Integrity | Does it build, import, run? Are boundaries clean? | 1–2 sessions |
| **P2** | Runtime Correctness | Do the hot paths produce correct results? | 3–5 sessions |
| **P3** | Architecture & Design | Is complexity justified? Where is debt? | 2–3 sessions |
| **P4** | Operational Fitness | Observability, failure modes, scale limits | 1–2 sessions |

Each phase produces a findings document in `docs/review/` with severity ratings:
- **CRITICAL**: Broken functionality, data loss risk, silent corruption
- **HIGH**: Incorrect behavior under realistic conditions, scaling wall
- **MEDIUM**: Tech debt, maintainability drag, unnecessary complexity
- **LOW**: Style, naming, minor inefficiency

### 1.2 Review Method

For each component under review:

1. **Read the code** — understand intent, not just shape.
2. **Trace the call graph** — follow data from entry point to storage/output.
3. **Run it** — execute the path with real or synthetic data; observe actual behavior.
4. **Check the tests** — are the tests testing what matters, or just what's easy?
5. **Assess against quality dimensions** (§3).
6. **Record findings** with file:line references, severity, and a concrete recommendation.

### 1.3 Anti-Noise Principles

- **Don't review bridge stubs** — the 17 micro-stubs in scripts/ are pure re-exports; delete them, don't audit them.
- **Don't review formatting** — linting is a tool's job. Focus on logic and architecture.
- **Don't review historical docs** — stale docs aren't a code quality issue.
- **Depth over breadth** — a thorough review of 3 hot paths beats a shallow scan of 20 modules.
- **Test by running** — reading code catches 60% of issues; running it catches 90%.

---

## 2. Component Inventory

### 2.1 Spine Core (`clarvis/`, 50.7K lines, 119 files)

#### 2.1.1 Brain (`clarvis/brain/`, 8.9K lines, 19 files)

| Component | File(s) | Lines | What to inspect |
|-----------|---------|-------|-----------------|
| ClarvisBrain composition | `__init__.py` | ~400 | Mixin assembly, singleton lifecycle, hook registration order |
| StoreMixin | `store.py` | 1,017 | Write paths: `remember()`, `capture()`, `propose()`/`commit()`. Conflict detection. Decay logic. Goal CRUD. Reconsolidation triggers. |
| SearchMixin | `search.py` | 1,132 | `recall()` hot path (parallel collection queries, embedding cache, result merging). `synthesize()` LLM call. Temporal queries. |
| GraphMixin | `graph.py` | 770 | Edge creation/traversal. Community detection integration. Backfill correctness. |
| GraphStoreSQLite | `graph_store_sqlite.py` | ~500 | WAL mode, index coverage, concurrent access safety, edge decay SQL |
| ACT-R activation | `actr_activation.py` | ~300 | Base-level activation formula, decay parameter sensitivity, score normalization |
| Retrieval eval | `retrieval_eval.py` | ~400 | Evaluation metrics, ground-truth handling |
| GraphRAG | `graphrag.py` | ~400 | Community summarization, global search path |
| SPR | `spr.py` | ~300 | Encode/decode fidelity, compression ratio |
| Hooks | `hooks.py` | ~200 | Hook ordering, exception handling in hooks, hook chain short-circuiting |
| LLM rerank | `llm_rerank.py` | ~200 | Prompt construction, model call error handling, fallback behavior |
| Result budgeting | `result_budgeting.py` | ~200 | Token budget adherence, truncation strategy |
| Secret redaction | `secret_redaction.py` | ~150 | Regex coverage (API keys, passwords, tokens), false positive rate |
| Factory | `factory.py` | ~150 | ChromaDB client singleton, ONNX embedding initialization |
| Constants | `constants.py` | ~80 | Collection names, path definitions |
| Memory evolution | `memory_evolution.py` | ~200 | Scheduled evolution triggers, memory lifecycle |
| Retrieval quality | `retrieval_quality.py` | ~200 | Quality tracking, feedback loop |
| Retrieval feedback | `retrieval_feedback.py` | ~200 | Feedback capture, scoring adjustment |
| Retrieval gate | `retrieval_gate.py` | ~200 | Quality threshold enforcement |

**Key questions**:
- Does `recall()` actually produce the most relevant results? Run golden-query benchmarks.
- Is graph SQLite migration complete and JSON fully dead-path?
- Do hooks fail silently or propagate errors?
- Is the embedding cache bounded? What happens under memory pressure?

#### 2.1.2 Cognition (`clarvis/cognition/`, 7.2K lines, 12 files)

| Component | File(s) | Lines | What to inspect |
|-----------|---------|-------|-----------------|
| AttentionSpotlight | `attention.py` | 1,263 | Salience scoring formula, codelet competition, attention schema theory implementation, broadcast cycle |
| ThoughtProtocol | `thought_protocol.py` | 952 | ThoughtScript DSL parsing, signal vector construction, frame building |
| ClarvisReasoner | `reasoning.py` | 926 | Decision frame construction, step tracking, relation graph |
| ConfidenceTracker | `confidence.py` | ~400 | Brier score calibration, prediction/outcome tracking, dynamic confidence |
| ContextRelevance | `context_relevance.py` | ~500 | Section scoring, suppression logic, staleness detection |
| WorkspaceBroadcast | `workspace_broadcast.py` | 545 | LIDA cycle: collect→coalesce→compete→broadcast. Coalition formation. |
| SomaticMarkers | `somatic_markers.py` | 463 | Emotional valence assignment, marker decay, decision influence |
| CognitiveLoad | `cognitive_load.py` | ~200 | Load estimation, task deferral thresholds |
| IntrinsicAssessment | `intrinsic_assessment.py` | ~300 | Failure pattern detection, autocurriculum generation |
| Metacognition | `metacognition.py` | ~400 | Quality checks, coherence scoring |
| ReasoningChains | `reasoning_chains.py` | ~400 | Chain creation, step logging, persistence |

**Key questions**:
- Is AttentionSpotlight actually influencing task selection, or is it decorative?
- Does confidence calibration converge? Check Brier score trend.
- Are somatic markers read anywhere downstream, or write-only?
- Is the LIDA broadcast cycle completing, or does it short-circuit?

#### 2.1.3 Memory (`clarvis/memory/`, 7.9K lines, 9 files)

| Component | File(s) | Lines | What to inspect |
|-----------|---------|-------|-----------------|
| EpisodicMemory | `episodic_memory.py` | 1,245 | Episode encoding fidelity, session boundaries, recall accuracy, `episodes.json` schema stability |
| HebbianMemory | `hebbian_memory.py` | 963 | Co-activation weight updates, consolidation trigger conditions, weight overflow |
| SynapticMemory | `synaptic_memory.py` | 1,010 | STDP timing windows, plasticity parameters, weight normalization |
| CognitiveWorkspace | `cognitive_workspace.py` | 717 | Buffer capacity enforcement, dormant reactivation, demotion cascade |
| SOAREngine | `soar.py` | 827 | Operator selection, goal stack management, chunk learning |
| MemoryConsolidation | `memory_consolidation.py` | 1,937 | `deduplicate()` correctness, `enhanced_decay()` formula, `prune_noise()` threshold, `archive_stale()` criteria, `sleep_consolidate()` timing |
| ProcedureLibrary | `procedural_memory.py` | 1,131 | Procedure storage/retrieval, composition logic, staleness retirement |
| WorkingMemory | `working_memory.py` | ~300 | Buffer size limits, eviction policy |

**Key questions**:
- Is `episodes.json` growing without bound? What's the current size and growth rate?
- Does `deduplicate()` actually remove near-duplicates or just exact matches?
- Are Hebbian weights normalized? Can they overflow to NaN/Inf?
- Is SOAR engine used in production paths or experimental-only?
- Does `sleep_consolidate()` run reliably in the 02:45 cron slot?

#### 2.1.4 Metrics (`clarvis/metrics/`, 10.3K lines, 18 files)

| Component | File(s) | Lines | What to inspect |
|-----------|---------|-------|-----------------|
| SelfModel | `self_model.py` | 1,575 | 7-domain assessment accuracy, staleness of self-assessment |
| CLR-Internal | `clr.py` | 1,005 | `compute_clr()` formula, trend computation, recording |
| Ablation V3 | `ablation_v3.py` | 944 | Ablation sweep correctness, component isolation |
| LongMemEval | `longmemeval.py` | 758 | Evaluation task design, scoring rubric |
| BEAM | `beam.py` | 757 | Assembly quality measurement, scoring |
| Quality | `quality.py` | 650 | Code quality scoring, task quality scoring |
| CLR Benchmark | `clr_benchmark.py` | 388 | Gate evaluation, stability scoring |
| COT Evaluator | `cot_evaluator.py` | 530 | Episode COT scoring, recording |
| Evidence Scoring | `evidence_scoring.py` | 420 | Evidence quality assessment |
| Phi | `phi.py` | 616 | IIT proxy computation, decomposition |
| Trajectory | `trajectory.py` | ~300 | Trajectory evaluation |
| Code Validation | `code_validation.py` | ~300 | Python file validation |
| Memory Audit | `memory_audit.py` | ~200 | Audit reporting |
| Benchmark | `benchmark.py` | ~300 | PI computation |
| CLR Reports | `clr_reports.py` | ~200 | Report formatting |
| CLR Perturbation | `clr_perturbation.py` | ~200 | Perturbation testing |
| MemBench | `membench.py` | 441 | Memory benchmark quadrants |

**Key questions**:
- Is CLR actually measuring what it claims? Validate the formula against documented intent.
- Are ablation results reproducible, or do they drift with brain state?
- Is the self-model assessment grounded in evidence, or does it self-congratulate?
- Which metrics are actively consumed by downstream decisions vs. write-only telemetry?

#### 2.1.5 Orchestration (`clarvis/orch/`, 3.7K lines, 12 files)

| Component | File(s) | Lines | What to inspect |
|-----------|---------|-------|-----------------|
| Task Router | `router.py` | ~400 | Classification accuracy, model selection logic, cost implications |
| CostTracker | `cost_tracker.py` | 531 | Cost estimation accuracy vs actual API spend, drift |
| CostOptimizer | `cost_optimizer.py` | ~300 | Prompt caching, waste detection effectiveness |
| PR Factory | `pr_intake.py`, `pr_indexes.py`, `pr_rules.py` | ~800 | Index building correctness, rule matching |
| TaskSelector | `task_selector.py` | ~300 | Scoring formula, attention alignment, existing-system bias |
| Scoreboard | `scoreboard.py` | ~200 | Recording accuracy, data integrity |
| QueueEngine | `queue_engine.py` | ~500 | State machine transitions, retry logic, race conditions |
| QueueWriter | `queue_writer.py` | ~300 | Task injection, dedup, daily cap enforcement |
| CostAPI | `cost_api.py` | ~100 | API wrapper correctness |

**Key questions**:
- Does the task router actually save money vs. always using Opus?
- Is the queue engine's state machine sound? Can tasks get stuck in liminal states?
- Are cost estimates within 20% of actual API spend?

#### 2.1.6 Context (`clarvis/context/`, 3.7K lines, 8 files)

| Component | File(s) | Lines | What to inspect |
|-----------|---------|-------|-----------------|
| Assembly | `assembly.py` | ~800 | Context assembly pipeline, section ordering, budget allocation |
| Compressor | `compressor.py` | ~500 | Compression algorithms, fidelity preservation |
| DYCP | `dycp.py` | ~400 | Dynamic context protocol, containment |
| Budgets | `budgets.py` | ~300 | Token budget calculation, allocation strategy |
| Adaptive MMR | `adaptive_mmr.py` | ~300 | Max-marginal relevance reranking |
| Knowledge Synthesis | `knowledge_synthesis.py` | ~300 | Cross-source synthesis |
| GC | `gc.py` | ~200 | Context garbage collection |

**Key questions**:
- Does context assembly actually fit within the target token budget?
- Is compression losing critical information? Compare compressed vs. uncompressed retrieval quality.
- Is GC running and actually reclaiming resources?

#### 2.1.7 Heartbeat (`clarvis/heartbeat/`, 1.7K lines, 10 files)

| Component | File(s) | Lines | What to inspect |
|-----------|---------|-------|-----------------|
| Gate | `gate.py` | ~200 | Gate decision logic, false-positive/negative rate |
| HookRegistry | `hooks.py` | ~200 | Hook execution order, error isolation |
| BrainBridge | `brain_bridge.py` | ~200 | Brain integration for preflight context |
| BrainStore | `brain_store.py` | ~200 | Postflight brain storage |
| Adapters | `adapters.py` | ~200 | Output adaptation |
| Runner | `runner.py` | ~200 | Execution coordination |
| WorkerValidation | `worker_validation.py` | ~200 | Output classification and validation |
| ErrorClassifier | `error_classifier.py` | ~150 | Error categorization |
| EpisodeEncoder | `episode_encoder.py` | ~150 | Episode serialization |

**Key questions**:
- Does the gate correctly suppress heartbeats during active conversations?
- Are hook failures isolated (one bad hook doesn't kill the pipeline)?
- Is episode encoding lossy? Compare encoded episodes to raw output.

#### 2.1.8 Queue (`clarvis/queue/`, 1.8K lines, 3 files)

| Component | File(s) | Lines | What to inspect |
|-----------|---------|-------|-----------------|
| Engine | `engine.py` | ~1,000 | QUEUE.md parsing, task state machine, selection logic |
| Writer | `writer.py` | ~700 | Task injection, dedup, archive, daily cap |

**Key questions**:
- Can QUEUE.md parsing break on malformed entries?
- Is dedup reliable (semantic similarity threshold)?
- Can the daily cap be circumvented?

#### 2.1.9 Remaining Spine Modules

| Module | Lines | What to inspect |
|--------|-------|-----------------|
| `learning/meta_learning.py` | 1,152 | Learning pipeline, is it called? |
| `runtime/mode.py` | 337 | Runtime mode transitions, state persistence |
| `adapters/` | 100 | Host adapter abstraction, completeness |
| `compat/contracts.py` | 73 | Contract definitions, are they enforced? |

#### 2.1.10 CLI Surface (`clarvis/cli*.py`, 3.7K lines, 19 files)

| CLI Module | Lines | What to inspect |
|------------|-------|-----------------|
| `cli_cron.py` | ~800 | Preset install correctness, crontab manipulation safety |
| `cli_wiki.py` | 278 | Command→script delegation, argument passing |
| `cli_brain.py` | ~300 | Brain command correctness |
| `cli_bench.py` | ~200 | Benchmark invocation |
| `cli_doctor.py` | ~200 | Health check completeness |
| All others | ~2,100 | Argument validation, error handling, help text accuracy |

**Key questions**:
- Does `clarvis cron install` produce correct crontab entries?
- Do all CLI commands handle missing data gracefully (fresh install)?
- Is help text accurate to actual behavior?

### 2.2 Scripts Layer (`scripts/`, ~75K lines, 126 files)

#### 2.2.1 Wiki Subsystem (12 scripts, 7.0K lines)

| Script | Lines | What to inspect |
|--------|-------|-----------------|
| `wiki_ingest.py` | 1,281 | Source registration, metadata extraction, duplicate handling |
| `wiki_compile.py` | 816 | Template rendering, YAML frontmatter, promotion logic |
| `wiki_canonical.py` | 734 | Alias resolution, dedup correctness |
| `wiki_render.py` | 666 | Output format fidelity, backlink generation |
| `wiki_lint.py` | 609 | Lint rule completeness, false positive rate |
| `wiki_brain_sync.py` | 519 | Bidirectional sync correctness, conflict handling |
| `wiki_index.py` | 499 | Index generation completeness |
| `wiki_query.py` | 459 | Query accuracy, source attribution |
| `wiki_eval.py` | 413 | Evaluation metric validity |
| `wiki_retrieval.py` | 387 | Retrieval integration correctness |
| `wiki_backfill.py` | 337 | Backfill completeness, idempotency |
| `wiki_maintenance.py` | 300 | Job orchestration, error handling |

**Key questions**:
- Is the metadata schema consistent across all wiki scripts? (Known P0 issue: `ingest_ts` vs `ingested_at` drift)
- Are raw paths canonicalized or do scripts use inconsistent path formats? (Known P0 issue)
- Does wiki_brain_sync handle conflicts or silently overwrite?

#### 2.2.2 Pipeline (5 scripts, 4.5K lines)

| Script | Lines | What to inspect |
|--------|-------|-----------------|
| `heartbeat_preflight.py` | 1,541 | 15+ subprocess consolidation correctness, context assembly |
| `heartbeat_postflight.py` | 2,007 | Outcome recording completeness, episode encoding |
| `heartbeat_gate.py` | 353 | Gate decision accuracy |
| `evolution_preflight.py` | 259 | Metrics batch collection |
| `execution_monitor.py` | 333 | Process monitoring, timeout handling |

**Key questions**:
- Are preflight/postflight atomically consistent? What if postflight crashes mid-write?
- Does execution_monitor correctly detect hung processes?

#### 2.2.3 Cognition Scripts (21 scripts, 10.5K lines)

| Group | Key scripts | What to inspect |
|-------|------------|-----------------|
| Advanced reasoning | `absolute_zero.py`, `causal_model.py`, `world_models.py`, `dream_engine.py`, `theory_of_mind.py` | Are these producing value? Are outputs consumed downstream? |
| Learning | `conversation_learner.py`, `knowledge_synthesis.py`, `prediction_resolver.py` | Learning loop closure — do lessons actually improve future behavior? |
| Reflection | `clarvis_reflection.py`, `prediction_review.py` | Reflection quality, actionability of insights |

**Key questions**:
- Is `absolute_zero.py` (AZR self-play) producing learnings that surface in task execution?
- Is `dream_engine.py` counterfactual output consumed or just logged?
- Which of these 21 scripts are actually in the cron schedule vs. dormant?

#### 2.2.4 Hooks (14 scripts, 7.3K lines)

| Script | Lines | What to inspect |
|--------|-------|-----------------|
| `directive_engine.py` | 1,407 | Classification accuracy, instruction enforcement, expiry logic |
| `obligation_tracker.py` | 881 | Promise tracking completeness, fulfillment detection |
| `hyperon_atomspace.py` | 850 | Hypergraph correctness, is it actually used? |
| `goal_tracker.py` | 390 | Goal→action linkage accuracy |
| `goal_hygiene.py` | 443 | Stale goal detection, lifecycle transitions |
| `canonical_state_refresh.py` | 443 | ROADMAP.md update correctness |
| `temporal_self.py` | 276 | Autobiographical tracking accuracy |

**Key questions**:
- Is `hyperon_atomspace.py` actually integrated or experimental-only?
- Does the obligation tracker have any callers in the hot path?
- Is directive_engine classification correct? What's the error rate?

#### 2.2.5 Metrics Scripts (19 scripts, 10.7K lines)

| Group | Key scripts | What to inspect |
|-------|------------|-----------------|
| Performance | `performance_benchmark.py` (1.7K), `performance_gate.py` | PI computation accuracy, gate threshold calibration |
| Brief quality | `benchmark_brief.py`, `brief_benchmark.py`, `ab_comparison_benchmark.py` | Complementary or duplicative? |
| Brain quality | `daily_brain_eval.py`, `llm_brain_review.py`, `brain_effectiveness.py` | Are deterministic + LLM evals aligned? |
| Self-model | `self_representation.py` (987), `self_model.py`, `self_report.py` | Evidence grounding of self-assessment |
| Dashboard | `dashboard.py`, `dashboard_server.py`, `dashboard_events.py` | Is the dashboard running/accessible? |

**Key questions**:
- Are brief benchmarks (3 scripts) justified as separate, or should they consolidate?
- Is the dashboard server actually deployed, or dead code?
- Does `self_representation.py` (987 lines) overlap with the spine `self_model.py` (1,575 lines)?

#### 2.2.6 Evolution (14 scripts, 8.9K lines)

| Script | Lines | What to inspect |
|--------|-------|-----------------|
| `meta_gradient_rl.py` | 1,024 | Hyperparameter tuning effectiveness, convergence |
| `research_novelty.py` | 1,017 | Topic dedup accuracy, novelty classification |
| `evolution_loop.py` | 670 | Failure→Evolve cycle completeness |
| `parameter_evolution.py` | 786 | Weight tuning from empirical data |
| `research_to_queue.py` | 609 | Research→queue bridge correctness |
| `failure_amplifier.py` | 495 | Soft failure surfacing accuracy |

**Key questions**:
- Does `meta_gradient_rl.py` actually improve outcomes over time? Check empirical evidence.
- Is `parameter_evolution.py` tuning parameters that matter?
- Does `research_novelty.py` correctly prevent topic re-research?

#### 2.2.7 Agents (4 scripts, 6.1K lines)

| Script | Lines | What to inspect |
|--------|-------|-----------------|
| `project_agent.py` | 3,557 | Spawn isolation, A2A protocol, promotion pipeline, secret filtering |
| `agent_orchestrator.py` | 764 | DAG execution, parallel coordination |
| `agent_lifecycle.py` | 477 | Worktree management, cleanup |
| `pr_factory.py` | 908 | Artifact indexing, PR context building |

**Key questions**:
- Is project agent isolation truly hard? Can a spawned agent read Clarvis brain?
- Is the A2A protocol validated on receive, or trusted blindly?
- Does `pr_factory.py` artifact indexing handle large repos?

#### 2.2.8 Tools (11 scripts, 8.4K lines)

| Script | Lines | What to inspect |
|--------|-------|-----------------|
| `context_compressor.py` | 1,547 | Compression quality, token budget adherence |
| `clarvis_browser.py` | 1,227 | Browser engine selection, session management |
| `browser_agent.py` | 1,084 | CDP connection, page interaction reliability |
| `tool_maker.py` | 1,023 | Tool extraction quality, validation |
| `ast_surgery.py` | 965 | Self-modification safety, rollback on failure |
| `prompt_builder.py` | 540 | Prompt construction, brain context inclusion |

**Key questions**:
- Does `ast_surgery.py` have adequate rollback? Can it corrupt its own source?
- Is `tool_maker.py` producing usable tools, or mostly noise?
- Is browser session management robust to cookie expiry?

#### 2.2.9 Infrastructure (9 scripts, 3.9K lines)

| Script | Lines | What to inspect |
|--------|-------|-----------------|
| `cleanup_policy.py` | 606 | File retention policy, accidental data loss risk |
| `import_health.py` | 466 | AST health check completeness |
| `graph_cutover.py` | 431 | Migration completeness, rollback safety |
| `budget_alert.py` | 246 | Alert threshold accuracy, Telegram delivery |
| `cost_tracker.py` | 200 | Cost tracking vs. actual API spend |

#### 2.2.10 Cron Orchestrators (Shell scripts, not in scripts/)

The cron shell scripts (`cron_autonomous.sh`, `cron_morning.sh`, etc.) orchestrate Claude Code spawning. Review:
- Lock acquisition/release correctness (global lock, maintenance lock, PID locks)
- Timeout handling
- Environment bootstrap via `cron_env.sh`
- Error handling when Claude Code hangs or crashes

### 2.3 Tests (`tests/`, ~23K lines, 56+ files)

| Test Category | Files | What to inspect |
|---------------|-------|-----------------|
| Brain tests | 11 files | Coverage of write paths, graph operations, retrieval accuracy |
| Memory tests | `test_clarvis_memory.py` (3.7K) | Consolidation, dedup, episode encoding |
| Cognition tests | 3 files | Attention, confidence, context relevance |
| Metrics tests | 8+ files | CLR, ablation, COT, code quality |
| Heartbeat tests | 4 files | Pipeline integration, hook order |
| Queue tests | 2 files | Engine state machine, writer |
| Integration tests | 5+ files | End-to-end paths |
| Wiki tests | 3 files | Canonical, eval, render |
| Agent tests | 2 files | Spawn, isolation, promotion |

**Key questions**:
- What's the actual test pass rate right now? Run `pytest` and see.
- Are tests using real ChromaDB or mocks? (Answer: hash-based embeddings via conftest, not real ONNX)
- Are there tests for error paths, or only happy paths?
- Which critical paths have zero test coverage?

### 2.4 Data Layer (`data/`, 98+ directories)

| Data Store | What to inspect |
|------------|-----------------|
| `clarvisdb/chroma.sqlite3` | Size, collection health, embedding consistency |
| `episodes.json` | Growth rate, schema stability, corruption risk (known P0 issue) |
| `hebbian/coactivation.json` | Weight distribution, NaN/Inf check |
| `somatic_markers.json` (406K) | Growth rate, is it ever pruned? |
| `thought_log.jsonl` (690K) | Growth rate, rotation policy |
| `reasoning_chains/` | Accumulation, archival policy |
| `cognitive_workspace/` | State file freshness |
| `performance_history.jsonl` | Trend continuity, gap detection |
| `budget_config.json` | Threshold accuracy |
| `router_decisions.jsonl` (187K) | Growth, rotation |

**Key questions**:
- Which data files are growing unbounded?
- Is `episodes.json` actually corrupted? (Known P0 issue)
- Are JSONL files being rotated by the Sunday cleanup?
- Is `somatic_markers.json` (406K) being pruned?

---

## 3. Quality Dimensions

Every reviewed component is judged on these eight dimensions:

| # | Dimension | What it means | How to assess |
|---|-----------|---------------|---------------|
| 1 | **Correctness** | Does it do what it claims? | Run it. Compare output to intent. Check edge cases. |
| 2 | **Architecture** | Is the abstraction level right? Are boundaries clean? | Trace call graphs. Check coupling. Count the number of modules that would break if this changes. |
| 3 | **Maintainability** | Can a future session understand and modify this? | Read the code cold. How long to understand? Are names clear? Is control flow linear? |
| 4 | **Scale Risk** | Will it break at 2x, 5x, 10x current load? | Check data structure sizes, O(n) operations, unbounded growth, lock contention. |
| 5 | **Duplication** | Is there redundant logic that could diverge? | Search for similar function names, similar patterns, overlapping responsibilities. |
| 6 | **Observability** | Can you tell what it did and whether it worked? | Check logging, error messages, metric emission. Can you diagnose a failure from logs alone? |
| 7 | **Safety** | Can it corrupt data, leak secrets, or fail destructively? | Check write paths, secret handling, rollback behavior, concurrent access. |
| 8 | **Value** | Is this component earning its complexity cost? | Is it consumed by downstream systems? Does removing it change outcomes? |

**Scoring**: Each dimension gets a grade per component:
- **A**: Excellent — no issues found
- **B**: Good — minor issues, low priority
- **C**: Adequate — notable issues, worth addressing
- **D**: Poor — significant issues, should be prioritized
- **F**: Failing — broken, dangerous, or actively harmful

---

## 4. Prioritization Method

### 4.1 Triage Formula

For each component, compute a **review priority score**:

```
Priority = (Blast Radius × 3) + (Change Frequency × 2) + (Complexity × 1) + (Known Issues × 4)
```

| Factor | Scale | Definition |
|--------|-------|------------|
| **Blast Radius** | 1–5 | How many other components break if this is wrong? (5 = everything depends on it) |
| **Change Frequency** | 1–5 | How often is this code modified? (5 = touched weekly) |
| **Complexity** | 1–5 | How hard is it to understand? (5 = requires deep domain knowledge) |
| **Known Issues** | 0–5 | Are there open P0/P1 bugs? (5 = critical known issue) |

### 4.2 Priority Tiers

| Tier | Score Range | Action |
|------|-------------|--------|
| **TIER 1** | 30+ | Review immediately. These are high-blast, high-risk. |
| **TIER 2** | 20–29 | Review in first pass. Important but not urgent. |
| **TIER 3** | 10–19 | Review if time permits. Lower risk. |
| **TIER 4** | <10 | Skip unless a specific concern arises. |

### 4.3 Pre-Computed Priority Assignments

| Component | Blast | Freq | Cmplx | Known | Score | Tier |
|-----------|-------|------|-------|-------|-------|------|
| Brain SearchMixin (`recall()`) | 5 | 4 | 4 | 0 | 27 | T2 |
| Brain StoreMixin (write paths) | 5 | 3 | 3 | 0 | 24 | T2 |
| Episodes.json integrity | 5 | 5 | 2 | 5 | 37 | **T1** |
| GraphStoreSQLite | 4 | 3 | 3 | 5 | 35 | **T1** |
| MemoryConsolidation | 4 | 3 | 4 | 0 | 22 | T2 |
| QUEUE.md parsing/engine | 4 | 5 | 3 | 0 | 25 | T2 |
| Heartbeat pipeline (pre+post) | 4 | 4 | 4 | 0 | 24 | T2 |
| Wiki metadata schema | 3 | 3 | 2 | 5 | 31 | **T1** |
| CLR computation | 3 | 3 | 4 | 5 | 33 | **T1** |
| CostTracker accuracy | 3 | 2 | 2 | 0 | 15 | T3 |
| AttentionSpotlight | 3 | 2 | 5 | 0 | 19 | T3 |
| Cron lock management | 4 | 2 | 3 | 0 | 19 | T3 |
| Project agent isolation | 3 | 1 | 3 | 0 | 14 | T3 |
| Dashboard server | 1 | 1 | 2 | 0 | 7 | T4 |
| Bridge stubs | 1 | 0 | 1 | 0 | 4 | T4 |
| SOAR engine | 2 | 1 | 4 | 0 | 14 | T3 |
| Hyperon atomspace | 2 | 1 | 4 | 0 | 14 | T3 |

---

## 5. Likely Hotspots and Probable Weak Areas

### 5.1 CRITICAL Hotspots (Fix before they bite)

1. **`episodes.json` corruption** (P0 in queue) — Episodic memory is a core data store used by preflight, postflight, reflection, and consolidation. If corrupted, episode encoding fails silently or crashes. Risk: data loss, broken learning loop.

2. **Graph verification failure** (P0 in queue, blocking since Apr 5) — Graph consolidation has been blocked for 3 days. If graph integrity checks fail, community detection, backfill, and GraphRAG all degrade. Risk: graph drift, orphan accumulation.

3. **CLR ablation regression** (P0 in queue) — If CLR is miscalculating, all downstream quality assessments (stability gate, benchmark, trend analysis) are unreliable. Risk: false confidence in system health.

4. **Wiki metadata drift** (P0 in queue) — `ingest_ts` vs `ingested_at` inconsistency across wiki scripts means lint, maintenance, and dedup may silently skip records. Risk: wiki quality degradation.

### 5.2 HIGH-Probability Weak Areas

5. **Unbounded data growth** — `somatic_markers.json` (406K), `thought_log.jsonl` (690K), `router_decisions.jsonl` (187K) are large and growing. The Sunday cleanup may not be keeping pace. Risk: disk fill, slow reads.

6. **Write-only subsystems** — Several cognitive modules (somatic markers, SOAR engine, Hyperon atomspace, theory of mind, world models) may be writing state that nothing reads. If so, they're consuming compute and storage for zero value. Risk: wasted cycles, code rot.

7. **80 scripts with legacy imports** — `sys.path.insert(0, ...)` hacks bypass Python's module system. Import order bugs, shadowing, and stale references are likely lurking. Risk: subtle import bugs.

8. **Self-model accuracy** — The self-model (1,575 lines) assesses 7 capability domains. If the assessment is based on stale data or circular reasoning (brain assesses brain), it provides false confidence. Risk: planning decisions based on inaccurate self-knowledge.

9. **Consolidation correctness** — `memory_consolidation.py` (1,937 lines) runs decay, dedup, prune, archive, and sleep consolidation. Each operation modifies brain state. If any is subtly wrong, valuable memories are lost or junk accumulates. Risk: memory quality degradation.

10. **Hook chain resilience** — The hook registry pattern is used extensively (brain, heartbeat, metrics). If one hook throws an exception, does it kill the chain or isolate the failure? Unhandled hook errors could silently break pipelines. Risk: silent pipeline failures.

### 5.3 MEDIUM-Risk Areas

11. **Cron lock contention** — 20+ cron entries share global and maintenance locks. If a long-running task holds the lock, subsequent tasks are skipped. Lock stale-detection may have race conditions. Risk: missed heartbeats, delayed evolution.

12. **Context assembly budget accuracy** — If token budget calculations are off, context gets truncated or bloated. This affects every heartbeat task. Risk: degraded task performance.

13. **Project agent brain isolation** — Claimed to be "hard isolation" but worth verifying. If a project agent can accidentally read/write to the main Clarvis brain, cross-contamination occurs. Risk: memory pollution.

14. **AST surgery safety** — `ast_surgery.py` (965 lines) modifies its own codebase. If rollback fails, it can corrupt source files. Risk: code corruption (low probability but high impact).

15. **17 bridge stubs + 4 deprecated wrappers** — These exist for backward compatibility but create confusion about the canonical import path. Risk: maintainability drag, new code using wrong imports.

---

## 6. Conducting the Review Without Drowning in Noise

### 6.1 Principles

1. **Follow the data, not the code** — Start from what the system produces (brain memories, episodes, queue tasks, metrics) and trace backward to the code that writes it. This reveals whether the system is actually working, not just compiling.

2. **Test the hot paths first** — The heartbeat pipeline (gate→preflight→execute→postflight) runs 12x/day. Review it before reviewing dream_engine.py which runs once at 02:45.

3. **Use the system's own metrics** — Run `python3 -m clarvis brain health`, `clarvis metrics`, `clarvis bench`. If these are healthy, the core is likely sound. Focus review on areas where metrics are missing or failing.

4. **Ignore the bridge stubs entirely** — The 17 micro-stubs and 4 deprecated wrappers in scripts/ are not worth reviewing. Delete them (or create a task to delete them) and move on.

5. **Sample, don't exhaustively read** — For the 18 metrics files, pick the 3 most consumed (CLR, self-model, PI benchmark) and review deeply. The rest can be spot-checked.

6. **Use git blame for change frequency** — `git log --since="2026-03-01" --name-only` shows what's been actively developed. Stable code that hasn't changed in weeks is lower priority.

### 6.2 Tooling

| Tool | Purpose |
|------|---------|
| `python3 -m pytest tests/ -x --tb=short` | Run all tests; first failure stops. Establishes baseline. |
| `python3 -m clarvis brain health` | Brain store/recall smoke test. |
| `python3 -m clarvis doctor` | Post-install health verification. |
| `python3 scripts/infra/import_health.py` | Structural import health (AST-based). |
| `git log --since="2026-03-01" --format="%h %s" --name-only` | Recent change frequency by file. |
| `wc -l data/episodes.json data/somatic_markers.json` | Data file sizes. |
| `python3 -c "from clarvis.brain import brain; print(brain.stats())"` | Quick brain stats. |
| `crontab -l` | Verify actual cron schedule. |
| `ls -la /tmp/clarvis_*.lock` | Check for stale locks. |

### 6.3 What to Skip

- **Docs quality** — Doc staleness is a known issue; don't burn review time on it.
- **Shell script style** — The cron shell scripts work; reviewing their bash style isn't productive.
- **Individual memory entries** — Don't review brain contents; review the code that writes/reads them.
- **Third-party code** — ChromaDB, ONNX, Typer internals are not in scope.
- **Browser engine details** — `clarvis_browser.py` and `browser_agent.py` are stable and infrequently used.

---

## 7. Execution Plan

### Pass 1: Establish Baseline (1–2 sessions)

**Objective**: Know what works and what's broken right now.

| # | Action | Expected output |
|---|--------|-----------------|
| 1.1 | Run `python3 -m pytest tests/ -x --tb=short 2>&1 | tail -50` | Test pass/fail count, first failure |
| 1.2 | Run `python3 -m clarvis brain health` | Brain store/recall status |
| 1.3 | Run `python3 -m clarvis doctor` | System health report |
| 1.4 | Run `python3 scripts/infra/import_health.py` | Import graph health |
| 1.5 | Check data file sizes: episodes.json, somatic_markers.json, thought_log.jsonl | Growth status |
| 1.6 | Check stale locks: `ls -la /tmp/clarvis_*.lock` | Lock hygiene |
| 1.7 | Verify cron schedule: `crontab -l | grep -v "^#"` | Actual vs documented schedule |
| 1.8 | Review the 4 known P0 issues from QUEUE.md | Current blockers |

**Deliverable**: `docs/review/pass1_baseline.md` — system health snapshot, blocking issues, test results.

### Pass 2: Tier 1 Deep Dives (2–3 sessions)

**Objective**: Resolve or understand the highest-priority issues.

| # | Component | Action |
|---|-----------|--------|
| 2.1 | **Episodes corruption** | Read `data/episodes.json`, check schema, attempt load. If corrupted, trace write path in `episodic_memory.py` and `heartbeat_postflight.py`. |
| 2.2 | **Graph verification** | Run `clarvis brain optimize-full`, trace the failure. Read `graph_store_sqlite.py` graph integrity checks. |
| 2.3 | **CLR ablation** | Run `compute_clr()` and `run_ablation_v3()`. Compare results to documented expected values. Read the formula. |
| 2.4 | **Wiki metadata** | Grep for `ingest_ts` and `ingested_at` across all wiki scripts. Map the inconsistency. Propose a fix. |
| 2.5 | **Brain recall() hot path** | Trace a search query through `SearchMixin.recall()` → parallel collection queries → result merging → ACT-R scoring → return. Time each stage. |

**Deliverable**: `docs/review/pass2_tier1.md` — findings per component, severity, fix recommendations.

### Pass 3: Architecture & Design Review (2–3 sessions)

**Objective**: Assess structural health and identify unnecessary complexity.

| # | Focus | Action |
|---|-------|--------|
| 3.1 | **Value audit** — identify write-only subsystems | For each cognitive module (SOAR, Hyperon, somatic markers, world models, theory of mind, dream engine), trace whether their output is read by any downstream consumer. |
| 3.2 | **Duplication audit** — spine vs scripts | Compare `clarvis/metrics/self_model.py` (1,575L) vs `scripts/metrics/self_representation.py` (987L). Compare `clarvis/context/knowledge_synthesis.py` vs `scripts/cognition/knowledge_synthesis.py`. Map all overlaps. |
| 3.3 | **Import modernization assessment** | Categorize the 80 legacy-import scripts: which are cron-called (must keep working), which are dead, which can migrate. |
| 3.4 | **Data growth projection** | For each major data file, compute growth rate (bytes/day) from git history or file timestamps. Project 30/90/180 day sizes. Flag unbounded growers. |
| 3.5 | **Hook chain audit** | Read the hook registry in `clarvis/brain/hooks.py` and `clarvis/heartbeat/hooks.py`. Test what happens when a hook throws an exception. |
| 3.6 | **Consolidation deep-dive** | Read `memory_consolidation.py` (1,937L) end to end. Run `deduplicate()` on a test brain. Verify it preserves high-value memories and removes actual duplicates. |
| 3.7 | **Queue engine state machine** | Map all possible state transitions in `queue/engine.py`. Check for stuck states, missing transitions, race conditions with concurrent writers. |

**Deliverable**: `docs/review/pass3_architecture.md` — value map, duplication inventory, growth projections, design recommendations.

### Pass 4: Operational Fitness (1–2 sessions)

**Objective**: Verify the system is observable, recoverable, and safe under failure.

| # | Focus | Action |
|---|-------|--------|
| 4.1 | **Cron failure recovery** | Simulate a cron job failure (kill during execution). Verify `cron_doctor.py` detects and recovers. Check lock cleanup. |
| 4.2 | **Secret redaction** | Run `secret_redaction.py` against a corpus with embedded API keys, passwords, tokens. Check for false negatives. |
| 4.3 | **Concurrent access** | Verify GraphStoreSQLite handles concurrent reads/writes (WAL mode). Stress test with parallel brain writes. |
| 4.4 | **Error propagation** | Trace what happens when ChromaDB is unavailable. Does the system degrade gracefully or crash? |
| 4.5 | **Backup integrity** | Verify `backup_daily.sh` produces restorable backups. Attempt a restore to a temp directory. |
| 4.6 | **Cost tracking accuracy** | Compare `cost_tracker.py telegram` output against actual OpenRouter billing for the last 7 days. |

**Deliverable**: `docs/review/pass4_operational.md` — failure mode inventory, recovery gaps, safety findings.

### Pass 5: Synthesis and Recommendations (1 session)

**Objective**: Produce a final assessment with prioritized action items.

| # | Action |
|---|--------|
| 5.1 | Aggregate all findings from passes 1–4. |
| 5.2 | Score each reviewed component on the 8 quality dimensions (§3). |
| 5.3 | Produce a scorecard matrix: component × dimension. |
| 5.4 | Rank the top 10 improvement opportunities by impact. |
| 5.5 | Identify 3–5 areas that work well and should be preserved. |
| 5.6 | Determine whether any major architectural change is warranted (vs. incremental fixes). |
| 5.7 | Write final report with executive summary, scorecard, and prioritized action plan. |

**Deliverable**: `docs/review/FINAL_REVIEW.md` — the definitive quality assessment.

---

## Appendix A: File Counts by Subsystem

| Subsystem | Spine (lines) | Scripts (lines) | Tests (lines) | Total |
|-----------|--------------|-----------------|---------------|-------|
| Brain | 8,900 | 5,800 | 4,500 | 19,200 |
| Cognition | 7,200 | 10,500 | 2,800 | 20,500 |
| Memory | 7,900 | — | 3,700 | 11,600 |
| Metrics | 10,300 | 10,700 | 3,200 | 24,200 |
| Heartbeat | 1,700 | 4,500 | 2,400 | 8,600 |
| Orchestration | 3,700 | — | 1,500 | 5,200 |
| Context | 3,700 | 1,500 | 800 | 6,000 |
| Queue | 1,800 | — | 600 | 2,400 |
| Wiki | — | 7,000 | 700 | 7,700 |
| Agents | — | 6,100 | 1,400 | 7,500 |
| Tools | — | 8,400 | — | 8,400 |
| Hooks | — | 7,300 | 400 | 7,700 |
| Evolution | — | 8,900 | 1,000 | 9,900 |
| Infrastructure | — | 3,900 | — | 3,900 |
| CLI | 3,700 | — | 200 | 3,900 |
| **TOTAL** | **~48,900** | **~74,600** | **~23,200** | **~146,700** |

## Appendix B: Known P0 Issues at Review Start

1. `[FIX_GRAPH_VERIFICATION]` — Graph verification failure blocking consolidation since Apr 5
2. `[FIX_CLR_ASSEMBLY_QUALITY]` — CLR ablation regression
3. `[FIX_EPISODES_CORRUPTION]` — Corrupted episodes.json
4. `[WIKI_METADATA_SCHEMA_ALIGNMENT]` — `ingest_ts` vs `ingested_at` drift
5. `[WIKI_RAW_PATH_CANONICALIZATION]` — Inconsistent raw path handling

## Appendix C: Dead Code Candidates

| Category | Count | Total Lines | Action |
|----------|-------|-------------|--------|
| Bridge stubs (pure re-exports) | 17 | ~200 | Delete after caller migration |
| Deprecated wrappers | 4 | ~220 | Delete after verifying no active callers |
| Write-only subsystems (TBD) | ? | ? | Audit in Pass 3 value review |

## Appendix D: Review Output Structure

```
docs/review/
├── pass1_baseline.md          — System health snapshot
├── pass2_tier1.md             — Tier 1 deep dive findings
├── pass3_architecture.md      — Architecture & design assessment
├── pass4_operational.md       — Operational fitness findings
└── FINAL_REVIEW.md            — Synthesis, scorecard, action plan
```
