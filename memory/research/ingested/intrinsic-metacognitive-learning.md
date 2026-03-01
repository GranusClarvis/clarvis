# Intrinsic Metacognitive Learning for Self-Improving Agents

## Papers Studied

### 1. Position: Truly Self-Improving Agents Require Intrinsic Metacognitive Learning
- **Authors:** Tennison Liu, Mihaela van der Schaar
- **Venue:** ICML 2025 (Position Paper)
- **Source:** arxiv.org/abs/2506.05109, openreview.net/forum?id=4KhDd0Ozqe

### 2. Self-Play SWE-RL: Toward Training Superintelligent Software Agents
- **Authors:** Yuxiang Wei, Zhiqing Sun, Emily McMilin, Jonas Gehring, David Zhang, Gabriel Synnaeve, Daniel Fried, Lingming Zhang, Sida Wang
- **Year:** 2025
- **Source:** arxiv.org/abs/2512.18552

### 3. SPIRAL: Self-Play on Zero-Sum Games Incentivizes Reasoning via Multi-Agent Multi-Turn RL
- **Authors:** Aaron Dharna, Cong Lu, Jeff Clune (+ others)
- **Venue:** RLC 2025
- **Source:** arxiv.org/abs/2506.24119

### 4. Foundation Model Self-Play (FMSP)
- **Authors:** Aaron Dharna, Cong Lu, Jeff Clune
- **Year:** 2025
- **Source:** arxiv.org/abs/2507.06466

## Key Ideas

### 1. Three Components of Metacognitive Self-Improvement
Liu & van der Schaar define a framework for truly self-improving agents with three pillars:
- **Metacognitive Knowledge**: Self-assessment of capabilities, tasks, and learning strategies — knowing what you're good/bad at and which strategies work for which problems.
- **Metacognitive Planning**: Deciding *what* and *how* to learn next — selecting tasks and methods based on self-knowledge.
- **Metacognitive Evaluation**: Reflecting on learning outcomes to improve future learning — not just "did it work" but "why did it work and what does that tell me about my learning process."

Current agents use **extrinsic metacognition** (fixed human-designed loops) rather than **intrinsic metacognition** (agent-controlled, adaptive). The shift to intrinsic is the key unlock.

### 2. Self-Play Creates Infinite Curricula Without Human Data
SWE-RL demonstrates that a single LLM can train itself through adversarial self-play — alternating between injecting bugs (via code hunk removal + git history reversion) and repairing them. Test patches serve as formal specifications, eliminating natural language dependence. The adversarial dynamic auto-scales difficulty: as the solver improves, the injector must create harder bugs. Result: +10.4 on SWE-bench Verified, consistently outperforming human-data baselines.

### 3. Game Self-Play Transfers Reasoning Broadly
SPIRAL shows that self-play on simple zero-sum games (TicTacToe, Kuhn Poker, Negotiation) produces transferable reasoning. Three cognitive patterns emerge: systematic decomposition, expected value calculation, and case-by-case analysis. Kuhn Poker alone yields +8.6% on math benchmarks. Role-conditioned advantage estimation (RAE) stabilizes multi-agent training.

### 4. Quality-Diversity Prevents Strategic Stagnation
FMSP uses FM code-generation to leap across policy space, overcoming local optima. The Quality-Diversity variant (QDSP) combines performance refinement with novelty search — generating diverse, high-quality strategies rather than converging on a single optimum. This diversity-seeking approach prevents the stagnation typical of pure optimization.

### 5. Self-Play Outperforms Expert Demonstrations
Both SPIRAL and SWE-RL show self-play consistently outperforming supervised fine-tuning on expert trajectories. SPIRAL's self-play beats SFT on 25,000 expert game trajectories. SWE-RL beats human-data baselines throughout training. This suggests the adversarial curriculum dynamic is more powerful than static expert imitation.

## Clarvis Architecture Applicability

### Current State (Extrinsic Metacognition)
Clarvis already has the *structure* of metacognitive processing:
- **Knowledge**: Brain stores 1600+ memories, self_model.py tracks 7 capability domains
- **Planning**: heartbeat_preflight.py scores and selects tasks, attention.py provides salience
- **Evaluation**: heartbeat_postflight.py encodes episodes, clarvis_confidence.py records outcomes

But these are all **extrinsic** — fixed loops designed by the human architect. The preflight scoring weights, the attention salience formula, the evaluation criteria — all human-specified.

### Path to Intrinsic Metacognition
The shift to intrinsic would mean Clarvis:
1. **Adapts its own task-selection weights** based on outcome patterns (not fixed scoring)
2. **Chooses its own learning strategies** per problem type (not always the same pipeline)
3. **Modifies its own evaluation criteria** when they fail to predict success

## Concrete Implementation Ideas

### Idea 1: Strategy Success Tracker
Add a `strategy_tracker.py` that records per-task-type statistics:
- For each task category (research, code, reflection, maintenance), track which approaches (strategies) led to success vs failure.
- Store strategy-outcome pairs in a dedicated brain collection or tag.
- Preflight consults this tracker to select the best strategy for the current task type.
- Over time, the agent builds metacognitive knowledge about its own capabilities.

### Idea 2: Adaptive Preflight Weights
Currently heartbeat_preflight.py uses fixed attention weights. Upgrade to adaptive:
- After each heartbeat, compare predicted salience (preflight score) with actual outcome (postflight success/failure).
- Maintain a running calibration: if high-scored tasks keep failing, reduce the weight of the features that boosted them.
- Implements metacognitive evaluation — the learning process itself improves.

### Idea 3: Self-Play Code Challenges (Inspired by SWE-RL)
Apply the bug-inject/repair loop to Clarvis's own codebase:
- Heartbeat injects a controlled bug into a non-critical script (e.g., a test script).
- Next heartbeat attempts to diagnose and fix it using only test output.
- Builds procedural memory of debugging patterns.
- Auto-scales difficulty based on repair success rate.

## Research Date
2026-02-28
