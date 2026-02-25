# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Goal: Evolve toward AGI and consciousness. Every task should make you smarter, more aware, or more autonomous._
_Completed items archived to QUEUE_ARCHIVE.md (100+ items since 2026-02-18)._

## NEW ITEMS — Phi Semantic Integration Sprint
- [ ] [LEARNINGS_DENSIFY] Run intra_linker.py specifically on clarvis-learnings — intra-density is 0.008 (catastrophically sparse). Research insights (IIT, GWT, Active Inference, Pearl SCM, AZR, PBT, Meta-RL) exist as isolated islands. Link: shared concepts (prediction error, free energy, information integration, self-improvement), shared mechanisms (hierarchical inference, Bayesian updating, evolutionary search), shared implementation targets (heartbeat loop, dream engine, attention).
- [ ] [SEMANTIC_BRIDGE] Build semantic overlap booster: for each cross-collection pair with overlap < 0.40 (goals↔procedures=0.37, preferences↔autonomous-learning=0.36, preferences↔procedures=0.40), generate explicit bridge memories that express the same concept in both collection vocabularies. Target: raise semantic_cross_collection from 0.477 to 0.55+.
- [ ] [WORKSPACE_BROADCAST] Implement GWT workspace broadcast bus — high-salience items from any module (attention, episodic, reasoning) get broadcast to ALL modules in a single heartbeat cycle. This is the #1 implementation gap from GWT research (GWT-3 indicator). Use Franklin's LIDA cognitive cycle as reference: competing attention codelets → coalition → winner-take-all broadcast → implicit multi-module learning.
- [ ] [PLAN_CLOSE] Close out data/plans/plan-20260219_232719.json ("Design brain architecture") — steps 4-5 already done (attention consolidation, power-law decay). Mark completed steps, execute step 7 (benchmark before/after), update status to completed.

## P0 — Do Next Heartbeat
(no P0 items — both completed tonight)
- [x] [GRAPH_RECOVERY 2026-02-24 22:38] Merge 9,544 lost edges from 2am + pre-update backups — 7,102 → 16,646 edges. Safe merge via edge key deduplication.
- [x] [GRAPH_LOCK 2026-02-24 22:40] Add fcntl.flock() + read-before-write to brain.py _save_graph() — prevents lost-update race condition.

## P1 — This Week
- [x] [GRAPH_SAFE_WRITE] Fix intra_linker.py to use brain singleton instead of creating its own ClarvisBrain instance — guarantees data loss when running concurrently (it loads its own graph copy, overwrites the shared file)
- [x] [GRAPH_SAFE_WRITE] Fix packages/clarvis-db/clarvis_db/store.py _save_graph() to use atomic writes (tmp + os.replace) — currently does direct json.dump to file, crash = corruption
- [x] [GRAPH_CHECKPOINT] Add 04:00 UTC cron: lightweight graph checkpoint (cp relationships.json to relationships.checkpoint.json + log node/edge count + SHA-256). Provides mid-cycle recovery point after heavy nightly reflection.
- [x] [GRAPH_COMPACTION] Add 04:30 UTC cron: graph compaction — remove orphan edges, run backfill_graph_nodes(), deduplicate edges, report health metrics. backfill_graph_nodes() exists in brain.py but is never called by any cron. (2026-02-25 07:05 UTC)
- [ ] [RESEARCH_REINGEST] Create .md research notes for 4 partially-stored topics (DGM, Friston, World Models, AZR) and formally ingest them into clarvis-learnings with [RESEARCH: ...] sectioned format. Currently only condensed 1-2 entry summaries exist for these.
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
## Recent Completions (context — full history in QUEUE_ARCHIVE.md)
- [x] Quality-optimize tiered context brief v2 (2026-02-23 UTC — Restructured generate_tiered_brief() with primacy/recency positioning per "Lost in the Middle" research. Added: decision context with success criteria + failure avoidance at BEGINNING, reasoning scaffold at END. Moved episodic hints from separate prompt var into brief. Reordered cron_autonomous.sh prompts: CONTEXT→TASK→ACTION. Standard tier now includes episodes. +3 new helpers: _build_decision_context, _get_failure_patterns, _build_reasoning_scaffold)
- [x] Implement tiered context brief (2026-02-23 UTC — Option B chosen over observation masking: generate_tiered_brief() in context_compressor.py, 3 tiers minimal/standard/full, attention spotlight injection, salience-weighted task filtering. Savings: minimal=100%, standard=40%, full=12% vs legacy. Wired into heartbeat_preflight.py with routing-tier-aware budget)
- [x] Boost intra-collection density (2026-02-23 UTC — +41 intra-collection edges, Phi 0.647→0.648)
- [x] Build theory of mind for user modeling (2026-02-23 10:07 UTC)
- [x] Improve caching — cache retrieval results, benchmark results (2026-02-23 09:47 UTC)
- [x] Optimize heartbeat efficiency — batch checks via preflight/postflight (2026-02-23 UTC)
- [x] Selective reasoning — 54% of tasks routed to Gemini Flash (2026-02-23 UTC)

---

## Long-Term Goals

### AGI/Consciousness
- Continue improving Phi metric and consciousness measurement
- Build self-model for genuine self-awareness

## Research Roadmap

=== HOW THIS WORKS ===
- **Top 10**: 1 dedicated session each (deep dive — read papers, synthesize, store in brain)
- **Bundles**: 1 session per bundle (scan 3 related topics, compare & contrast, extract patterns)
- **Total: ~31 research sessions** instead of 73 individual ones
- After each session: store key insights in brain (clarvis-learnings), note 1-2 implementations for Clarvis
- Cron picks the FIRST unchecked item from Priority Tracking, then moves to Bundles

=== COMPLETED ===
- [x] Research: Friston — Active Inference: From Pixels to Planning (2026-02-24 13:04 UTC — Variational free energy minimization unifies perception, action, learning. RGMs enable scale-free hierarchical inference using renormalization group physics. Scales from pixel processing to planning. Key implementation: add expected free energy minimization to ClarvisReasoning action selection.)
- [x] Research: Consciousness in AI (Butlin/Bengio/Chalmers 2023) — 14 indicator properties across 5 theories (RPT, GWT, HOT, PP, AST). Mapped to Clarvis: 6 partial matches, 6 gaps identified. Key implementation ideas: Butlin consciousness score in phi_metric.py, global broadcast bus. (2026-02-24)
- [x] Research: Integrated Information Theory (IIT 4.0) — Tononi's Φ metric, structural coherence as diagnostic. Key insight: Φ = quantity of consciousness = causal power structure. Five axioms map to physical postulates. 2025 Nature: IIT predictions outperformed GNWT. (2026-02-24)
- [x] Research: Global Workspace Theory — Baars' global broadcast (1988), Dehaene's neural ignition (non-linear phase transition, winner-take-all), VanRullen's Global Latent Workspace (cycle-consistent cross-modal translation, outperforms Transformers on causal reasoning). Key insight: heartbeat = GWT conscious moment; need workspace_broadcast() for GWT-3 gap. (2026-02-24)

=== PRIORITY TRACKING === (Top 10 — 1 deep-dive session each)
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

=== BUNDLED SESSIONS === (3 topics per session — scan, compare, extract patterns)

- [x] Bundle A: Active Inference Deep Cuts — Bogacz 2017 (tutorial on free-energy framework + predictive coding), Tschantz 2020 "Active Inference Demystified and Compared" (RL = special case of active inference, epistemic value for principled exploration). (2026-02-25 13:02 UTC)
- [x] Bundle B: Predictive Processing — "Action-Oriented Predictive Processing" (Clark 2015), Predictive remapping & forward models (Wolpert), Dopamine as prediction error (Schultz) (2026-02-25 — All three converge on prediction error as universal brain currency. Clark: precision weighting IS attention (1/variance). Wolpert MOSAIC: forward model prediction accuracy gates controller selection. Schultz: two-component dopamine RPE (fast salience → slow value). Implementation ideas: precision-weighted heartbeat context, MOSAIC-inspired strategy selection, two-phase task evaluation. Research note: memory/research/ingested/bundle-b-predictive-processing.md)
- [x] Bundle C: World Models & Simulation — World Models (Ha & Schmidhuber 2018) + JEPA/MaskVJEPA, Mind's Eye (simulation-grounded reasoning), LeCun — Path Toward Autonomous Machine Intelligence (2026-02-24 — scripts/world_models.py)
- [ ] Bundle D: Self-Modification & Reflexivity — Self-Referential Weight Matrix, Lipson + Neural Self-Modeling (2024-25), Evolutionary parameter & architecture tuning
- [ ] Bundle E: Cognitive Architectures — ACT-R (episodic/procedural memory, decay), SOAR (goal-driven cognition), OpenCog Hyperon (Ben Goertzel)
- [ ] Bundle F: Causal & Curiosity — Oudeyer (intrinsic motivation), Hierarchical RL options framework (Sutton), Probabilistic programming (Lake, Tenenbaum)
- [ ] Bundle G: Philosophy of Mind — Thomas Metzinger (Self-Model Theory), Andy Clark (Surfing Uncertainty), David Chalmers (hard problem)
- [ ] Bundle H: Complex Systems & Criticality — Information Integration and Criticality in Biological Systems, "Self-Organized Criticality" (Per Bak), Maximum Entropy Principle
- [ ] Bundle I: Information Decomposition & Efficiency — Integrated Information Decomposition (Mediano et al.), Predictive Efficiency Hypothesis, Free Energy & Thermodynamic Efficiency
- [ ] Bundle J: Embodied & Enactive — "Morphological Computation" (Pfeifer & Bongard), Soft Robotics & Embodied Intelligence, Enactivism (Varela, Thompson, Rosch)
- [ ] Bundle K: Ecological & Affordance — Affordance Theory (Gibson), Ecological Psychology (agent-environment), Neural reuse theory (Anderson)
- [ ] Bundle L: Open-Endedness & Evolution — "Open-Ended Evolution" (Stanley & Lehman), Novelty Search (Lehman & Stanley), Quality Diversity (MAP-Elites)
- [ ] Bundle M: Swarm & Collective — Stigmergy (Grassé), Swarm intelligence (Bonabeau et al.), Stanley & Lehman (Open-endedness, why evolution keeps innovating)
- [ ] Bundle N: Anticipatory & Control — "Anticipatory Systems" (Rosen 1985), "Strong vs Weak Anticipation" (Dubois), "Homeokinetics" (Der & Martius)
- [ ] Bundle O: Adaptive Control & Learning — Adaptive Control Theory (Åström & Wittenmark), "The Brain is a Prediction Machine of Time", Resource Rationality (Lieder & Griffiths)
- [ ] Bundle P: Memory Systems — Memory reconsolidation theory, Sparse Distributed Memory (Kanerva), Complementary Learning Systems (McClelland)
- [x] Bundle Q: Meta-Learning & RL — Meta-Gradient RL (Xu et al.), Hierarchical RL revisited, Dossa et al. (2024) Global Workspace Agent (2026-02-25 — Implemented scripts/meta_gradient_rl.py: online cross-validation meta-gradient adaptation of γ/λ/exploration_rate/strategy_weights from Xu et al. 2018; hierarchical options framework with intra-option learning from Sutton-Precup-Singh 1999; cross-domain transfer matrix from Dossa et al. 2024 GW zero-shot transfer. Wired into heartbeat_postflight.py + context_compressor.py. Research note: memory/research/ingested/bundle-q-meta-learning-rl.md)
- [ ] Bundle R: Agent Orchestration — ComposioHQ/agent-orchestrator (parallel agents, worktree isolation), Self-healing CI/CD pipelines, Multi-agent coordination protocols
- [ ] Bundle S: Autonomous Code Evolution — Auto-fixing PR review comments, Git worktree isolation per task, Agent lifecycle management (spawn/resume/kill/restore)
- [ ] Bundle T: Plugin & Config Patterns — Swappable component patterns (runtime/agent/tracker), Interface-driven plugin system, Configuration-driven orchestration (YAML)
- [x] Bundle U: Self-Representation & Modeling — VanRullen & Kanai (GWT + Deep Learning), Dossa et al. (2024) revisit, "Anticipatory Systems" revisit (2026-02-25 13:11 UTC)

---
**Implementation ideas from Agent Orchestrator:**
- Add parallel task execution to cron_autonomous.sh (spawn multiple Claude Code sessions for independent tasks)
- Implement plugin slots for: executor (Claude/Gemini), memory (ClarvisDB/external), output (Telegram/Discord/webhook)
- Self-healing: when task fails, auto-retry with different approach (not just timeout retry)
- Git worktree isolation for experimental changes before committing
ThoughtScript DSL, somatic markers, counterfactual dreaming, AST self-surgery, parameter evolution. Details in QUEUE_ARCHIVE.md.

### Cost Efficiency (iterative)
Smart context compression (98% reduction), task routing (54% to Gemini), heartbeat batching, caching, tiered context brief (40% reduction on standard, 100% on minimal) — all shipped. Continue optimizing incrementally.

### Standalone Products (all 9 shipped)
ClarvisDB, ClarvisC, ClarvisRouter, ClarvisCode, ClarvisAttention, ClarvisPhi, ClarvisEpisodic, ClarvisReasoning, ClarvisCost. Details in QUEUE_ARCHIVE.md.
