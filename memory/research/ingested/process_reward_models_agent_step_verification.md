# Process Reward Models for Agent Step Verification

**Date**: 2026-03-07
**Queue Tag**: RESEARCH_DISCOVERY 2026-03-05
**Relevance**: Directly improves action accuracy via step-level error detection before execution commits

## Core Concept

Process Reward Models (PRMs) score **each intermediate step** in an agent's trajectory, rather than only the final outcome. This enables early error detection, better credit assignment, and guided search over action spaces. Four papers define the frontier:

## Paper Summaries

### 1. ThinkPRM — Generative CoT Verification (arXiv:2504.16828)

**Key insight**: Fine-tune a reasoning model on ~1K synthetic verification CoTs, filtered using only ~8K process labels (1% of PRM800K). The resulting generative verifier outperforms discriminative PRMs trained on 100x more labels.

- **Method**: Generate long chain-of-thought verification traces, filter by correctness using minimal process labels, fine-tune QwQ-32B-Preview (4.5h on single A100)
- **Results**: +8% OOD on GPQA-Diamond, +4.5% on LiveCodeBench vs full-data discriminative PRMs. +7.2% vs LLM-as-Judge under same token budget
- **Why it matters**: Generative verification scales test-time compute more effectively. You can allocate more tokens to verification and get monotonically better results, unlike discriminative scoring which is fixed-cost

### 2. Critical Step Optimization (arXiv:2602.03412)

**Key insight**: Focus preference learning on **verified critical steps** — decision points where swapping the action demonstrably flips the trajectory from failure to success.

- **Method**: (1) Collect failed policy trajectories, (2) PRM scores each step on 5 dimensions: code correctness (35%), task relevance (25%), logical progression (20%), info utilization (15%), thought quality (5%), (3) Steps scoring <0.45 with expert alternatives scoring >0.65 are critical, (4) Expert (Claude-3.7-Sonnet) proposes k=5 alternatives, (5) Policy continues from alternative — only verified-successful alternatives become DPO training data
- **Results**: 37% and 26% relative improvement over SFT on GAIA-Text-103 and XBench-DeepSearch. Supervision at only 16% of trajectory steps
- **Why it matters**: Identifies the exact decision points that matter. Most steps are fine — optimization effort concentrates on the few that determine success/failure

### 3. AgentPRM — Promise & Progress (arXiv:2511.08325)

**Key insight**: Redefine step rewards as **Promise** (Q-value: expected future success probability) and **Progress** (advantage: improvement over baseline state). Use TD-estimation + GAE instead of expensive Monte Carlo rollouts.

- **Method**: TD residuals δ(s_t, a_t) = r_t + γQ(s_{t+1}) - Q(s_t), combined via GAE: Â = Σ(γλ)^k δ_{t+k}. Trains actor-critic on agent trajectories
- **Results**: 8x compute efficiency vs Monte Carlo baselines. 3B models surpass GPT-4o on WebShop. +20 points over Process Value Models with beam search
- **Why it matters**: Makes PRM training practical at scale. TD+GAE requires only the sampled trajectories themselves — no expensive re-rollouts per step

### 4. ToolPRMBench — Tool-Use PRM Evaluation (arXiv:2601.12294)

**Key insight**: General PRMs underperform on tool-use tasks. Specialized tool PRMs are needed.

- **Method**: Constructs step-level test cases from agent trajectories: interaction history + correct action + plausible incorrect alternative + tool metadata. Uses offline sampling (isolated single-step errors) and online sampling (realistic multi-step failures from full rollouts). Multi-LLM verification pipeline reduces label noise
- **Results**: Clear differences between general and tool-specialized PRMs. Tool-specialized PRMs significantly better for tool-use verification
- **Why it matters**: Validates that tool-use (browser, API, code execution) requires domain-specific reward models, not just general reasoning PRMs

## Clarvis Application Ideas

### Idea 1: ACTION_VERIFY_GATE Enhancement (connects to QUEUE item)
The existing `[ACTION_VERIFY_GATE]` queue task can adopt CSO's 5-dimension scoring rubric. Before heartbeat commits a selected task to Claude Code:
- Score the proposed action on: correctness likelihood, task relevance, logical progression from current state, information utilization, thought quality
- Threshold: proceed only if score > 0.65; reconsider if < 0.45
- This maps directly to `heartbeat_preflight.py`'s attention scoring pipeline

### Idea 2: Promise/Progress for Task Selection
Extend `attention.py` salience scoring with AgentPRM-style Promise/Progress:
- **Promise**: Given current system state + proposed task, estimate probability of successful completion
- **Progress**: How much does completing this task advance toward long-term goals vs current baseline?
- Use historical episode outcomes as training signal (episodic_memory.py has success/failure records)

### Idea 3: Generative Verification in Reasoning Chains
ThinkPRM's approach maps to `reasoning_chain_hook.py`:
- Instead of scoring reasoning steps discriminatively, generate a verification CoT that checks each step
- Minimal label overhead: ~1K verified examples would suffice
- Could use existing `clarvis_reasoning.py` confidence scores as weak labels

### Idea 4: Tool-Specific Verification for Browser/API Actions
ToolPRMBench validates the need for specialized tool PRMs. For Clarvis:
- Browser actions (click, fill, navigate) need different verification than code generation
- API calls need schema/parameter validation separate from reasoning quality
- `tool_maker.py` could incorporate tool-specific step verification

### Context Relevance Connection
**Weakest metric note**: Context Relevance (0.838) could improve via PRM-style scoring of context selection. Currently `context_compressor.py` selects context by relevance scoring — adding a step-level verification of "does this context item actually help the current task?" would be a PRM-style intervention. The CSO rubric's "information utilization" dimension (15% weight) directly measures this.

## Implementation Priority

1. **Immediate** (low effort): Add CSO 5-dimension scoring to ACTION_VERIFY_GATE design
2. **Medium-term**: Promise/Progress estimation in attention.py using episode history
3. **Longer-term**: Generative verification CoTs via reasoning_chain_hook.py
4. **Research**: Collect tool-specific action trajectories for future specialized PRM training
