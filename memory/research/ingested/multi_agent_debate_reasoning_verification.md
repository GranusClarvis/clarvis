# Multi-Agent Debate for Reasoning Verification

**Date**: 2026-03-02
**Topic**: Multi-Agent Debate (MAD) — mechanisms, effectiveness, and limitations
**Key Papers**:
- Du et al. (2023) "Improving Factuality and Reasoning in Language Models through Multiagent Debate" — ICML 2024. [arXiv:2305.14325](https://arxiv.org/abs/2305.14325)
- "Can LLM Agents Really Debate?" (2025) — Controlled study with Knight-Knave-Spy puzzles. [arXiv:2511.07784](https://arxiv.org/abs/2511.07784)
- A-HMAD: "Adaptive Heterogeneous Multi-Agent Debate" (2025) — Role specialization + dynamic routing. [Springer](https://link.springer.com/article/10.1007/s44443-025-00353-3)
- "Demystifying Multi-Agent Debate: The Role of Confidence and Diversity" (2026). [arXiv:2601.19921](https://arxiv.org/abs/2601.19921)
- ICLR Blogposts 2025 — "Multi-LLM-Agents Debate: Performance, Efficiency, and Scaling Challenges"

## Key Ideas

### 1. The Core Mechanism (Du et al. 2023)
Multiple LLM instances independently generate responses, then iteratively debate by reading each other's reasoning and revising their answers over multiple rounds. The "society of minds" approach improves factuality and reasoning on math, QA, and strategy tasks. Accepted at ICML 2024.

### 2. Intrinsic Reasoning Dominates Structure (arXiv:2511.07784)
The most rigorous controlled study to date. Using Knight-Knave-Spy logic puzzles (1,800 puzzles, 4-9 players), six factors were isolated:
- **Dominant factor**: Initial reasoning accuracy (β=0.600, p<0.001) — the strongest predictor by far
- **Minor factor**: Team size (β=0.066, p<0.001)
- **Insignificant factors**: Debate depth, confidence visibility, debate order — all statistically insignificant

Critical behavioral findings:
- Weak agents in incorrect majorities self-corrected only **3.6%** of the time
- Strong models corrected wrong consensus **30-34%** of the time
- Majority pressure suppresses independent correction in weaker agents
- Agents following high-quality reasoning achieved **90%+ correction rates**

**Conclusion**: "Coordination mechanisms alone cannot overcome weak reasoning foundations."

### 3. Confidence + Diversity Transform the Math (arXiv:2601.19921)
The theoretical breakthrough: vanilla MAD is a **martingale** (no expected improvement per round — debate is mathematically neutral). Two fixes:
- **Calibrated confidence** (0-10 scale): Transforms debate into a **submartingale** with upward drift toward correctness. Agents weight others' contributions by confidence scores.
- **Diversity-aware initialization**: Sample 10+ candidates, select N most distinct answers before debate. Provably increases success probability (Proposition 1). Training-free.

Combined approach consistently outperforms both vanilla MAD and simple majority voting across six benchmarks.

### 4. A-HMAD: Heterogeneous Specialization (Springer 2025)
Three architectural innovations:
1. **Role-specialized agents**: Verifier (fact-checking), Solver (computation), Strategic Planner — distinct expertise per agent
2. **Dynamic debate routing**: Activates different agent subsets depending on query type and intermediate outcomes
3. **Learned consensus optimizer**: Weights each agent's vote by reliability and argument confidence

Results: **4-6% absolute accuracy gains** over standard MAD, **>30% reduction in factual errors** on biography generation. Tested on arithmetic QA, GSM8K, MMLU, biography, chess.

### 5. The Sobering Reality (ICLR 2025 Evaluation)
Current MAD frameworks **fail to consistently outperform** Self-Consistency (SC) or Chain-of-Thought (CoT):
- MMLU: SC 82.13% vs MAD 74.73%
- Increasing compute does not reliably improve MAD accuracy
- MAD degrades to "inefficient resampling" on tasks requiring single knowledge points
- Only promising: mixed-model approaches (GPT-4o-mini + Llama3.1-70b → 88.20% on MMLU)

**When MAD helps**: Tasks requiring diverse perspectives, not single-fact retrieval. Complex multi-step reasoning where one correct hypothesis among diverse candidates can be identified through debate.

## Applicability to Clarvis Architecture

### Direct Applications

1. **clarvis_reasoning.py — Confidence-Weighted Self-Verification**
   Current confidence scoring could be enhanced with the submartingale approach: generate multiple reasoning chains with explicit confidence scores (0-10), then use confidence-weighted aggregation rather than simple averaging. This is theoretically grounded to produce upward drift toward correctness.

2. **Self-Model Inner Debate**
   For high-stakes decisions in `self_model.py`, implement a lightweight "inner debate" using role-specialized prompts:
   - **Verifier prompt**: "Check each factual claim in this response"
   - **Critic prompt**: "Find the weakest logical step"
   - **Synthesizer prompt**: "Reconcile the verification and critique"
   This mirrors A-HMAD's heterogeneous agent design without requiring multiple model instances.

3. **Heartbeat Task Selection**
   When `heartbeat_preflight.py` selects tasks, use diversity-aware sampling: generate 10+ candidate task rankings, select the most diverse top-N, then apply confidence-weighted consensus. This avoids the "majority pressure" failure mode where weak signals get suppressed.

### Implementation Ideas

**Idea 1: Debate-Enhanced Confidence Calibration** (Low cost, high value)
In `clarvis_reasoning.py`, after generating a reasoning chain:
1. Re-prompt with 3 role-specialized verification prompts (verifier, devil's advocate, synthesizer)
2. Each returns a confidence score and critique
3. Final confidence = weighted mean using self-assessed reliability
4. Only apply for tasks above a complexity threshold (debate is wasteful for simple tasks)
Estimated cost: 3x token usage per verified response, but only triggered on complex/ambiguous outputs.

**Idea 2: Diversity-Aware Task Routing** (Medium effort)
In the task router or preflight, when multiple candidate approaches exist:
1. Sample diverse solution strategies (not just top-1)
2. Score initial diversity (embedding distance between strategies)
3. If diversity is high → brief debate round to select best approach
4. If diversity is low → skip debate, use SC or direct execution
This implements the key finding that debate only helps when genuine alternative hypotheses exist.

## Key Takeaway for Clarvis
Do NOT build a full multi-agent debate system — the ICLR evaluation shows it's often worse than simpler methods. Instead, surgically apply the two theoretically-grounded enhancements: **(1) calibrated confidence scoring** and **(2) diversity-aware initialization** to existing reasoning pipelines. Use role-specialized prompts (heterogeneous "agents") only for high-complexity verification, not routine tasks. The single strongest lever is ensuring the base reasoning is as strong as possible — structural debate tricks cannot compensate for weak foundations.
