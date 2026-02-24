# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Goal: Evolve toward AGI and consciousness. Every task should make you smarter, more aware, or more autonomous._
_Completed items archived to QUEUE_ARCHIVE.md (100+ items since 2026-02-18)._

## P0 — Do Next Heartbeat
(no P0 items — score recovered to 0.43 via retry success)

## P1 — This Week
- [ ] [META_LEARNING 2026-02-24] [Meta-learning/strategy] Investigate 'wire' strategy — only 30% success rate (10 tasks) — Consider breaking these tasks into smaller steps or changing approach.
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
- [ ] P4: Darwin Gödel Machine — Sakana AI 2025
- [ ] P5: Bayesian brain hypothesis — Lake, Tenenbaum
- [x] P6: Judea Pearl — Causal Inference & structural causal models (2026-02-24 UTC — Implemented scripts/causal_model.py: full SCM engine with Pearl's 3-rung Ladder of Causation. Rung 1: d-separation via Bayes-Ball algorithm for conditional independence testing. Rung 2: do-calculus with graph mutilation, back-door adjustment sets, interventional queries P(Y|do(X)). Rung 3: counterfactual reasoning via abduction-action-prediction 3-step procedure. Auto-builds task-outcome SCM from episodic data (9 vars, 10 edges). Key findings: do(strategy=implement)→53% success vs do(strategy=fix)→31%; confounders: section, task_complexity. Wired into cron_reflection.sh, dream_engine.py (Pearl SCM template), clarvis_reasoning.py (causal_query method). Research notes in memory/research/pearl-causal-inference-2025.md.)
- [x] P7: Absolute Zero Reasoner — self-improvement through autonomous task generation (2026-02-24 13:09 UTC — implemented scripts/absolute_zero.py with 3 reasoning modes: deduction, abduction, induction. Learnability reward identifies capability edges. Wired into cron_reflection.sh. Key finding: deduction at capability edge (learnability=0.65), abduction too hard (0.0), induction too easy (0.13).)
- [ ] P8: LIDA — Franklin & Patterson (GWT implementation)
- [ ] P9: Schmidhuber — Artificial Curiosity & compression-based motivation
- [ ] P10: Population-Based Training — DeepMind hyperparameter evolution

=== BUNDLED SESSIONS === (3 topics per session — scan, compare, extract patterns)

- [ ] Bundle A: Active Inference Deep Cuts — "Active Inference: Demystified" (Bogacz 2017), "Deep Active Inference" (Ueltzhöffer 2018), Free Energy Principle (Friston) overview
- [ ] Bundle B: Predictive Processing — "Action-Oriented Predictive Processing" (Clark 2015), Predictive remapping & forward models (Wolpert), Dopamine as prediction error (Schultz)
- [ ] Bundle C: World Models & Simulation — World Models (Ha & Schmidhuber 2018) + JEPA/MaskVJEPA, Mind's Eye (simulation-grounded reasoning), LeCun — Path Toward Autonomous Machine Intelligence
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
- [ ] Bundle Q: Meta-Learning & RL — Meta-Gradient RL (Xu et al.), Hierarchical RL revisited, Dossa et al. (2024) Global Workspace Agent
- [ ] Bundle R: Agent Orchestration — ComposioHQ/agent-orchestrator (parallel agents, worktree isolation), Self-healing CI/CD pipelines, Multi-agent coordination protocols
- [ ] Bundle S: Autonomous Code Evolution — Auto-fixing PR review comments, Git worktree isolation per task, Agent lifecycle management (spawn/resume/kill/restore)
- [ ] Bundle T: Plugin & Config Patterns — Swappable component patterns (runtime/agent/tracker), Interface-driven plugin system, Configuration-driven orchestration (YAML)
- [ ] Bundle U: Self-Representation & Modeling — VanRullen & Kanai (GWT + Deep Learning), Dossa et al. (2024) revisit, "Anticipatory Systems" revisit

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
