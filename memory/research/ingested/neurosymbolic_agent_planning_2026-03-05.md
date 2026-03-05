# Research: Neurosymbolic Agent Planning

**Date**: 2026-03-05
**Topic**: Combining symbolic verification with neural LLM flexibility to reduce agent action errors
**Sources**: Metagent-P (ACL 2025), NeSyPr (arXiv:2510.19429), StateFlow (arXiv:2403.11322)

---

## 1. Metagent-P — Plan-Verify-Execute-Reflect

**Paper**: Wang et al., "Metagent-P: A Neuro-Symbolic Planning Agent with Metacognition for Open Worlds", ACL 2025 Findings
**URL**: https://aclanthology.org/2025.findings-acl.1169/

**Architecture**: Four components — Planner, Verifier, Controller, Reflector — forming a planning-verification-execution-reflection cycle.

**Key mechanism — Hierarchical Neuro-Symbolic Verifier**:
- **Top layer**: Explicit symbolic rules check action prerequisites (e.g., "need iron pickaxe before mining diamond")
- **Bottom layer**: LLM handles cases not covered by symbolic rules (implicit world knowledge)
- Verifier checks action feasibility *before* execution, preventing wasted steps

**Metacognitive Reflector**: Monitors execution, compares observations against expectations, triggers re-planning when divergence detected. Experience pool grows as agent explores (rules + episodes accumulate).

**Results** (Minecraft):
- 34% fewer replanning episodes (fewer wasted execution cycles)
- 18.96% above average human success rate
- Significant improvement over SOTA on long-horizon tasks

**Clarvis relevance**: The hierarchical verifier pattern (symbolic rules first, LLM fallback) directly maps to adding a verification step between heartbeat preflight and Claude Code execution. Could prevent spawning Claude Code for infeasible tasks.

---

## 2. NeSyPr — Compiled Procedural Knowledge

**Paper**: Choi et al., "NeSyPr: Neurosymbolic Proceduralization For Efficient Embodied Reasoning"
**URL**: https://openreview.net/forum?id=a8sJEH4Cjb, https://arxiv.org/abs/2510.19429

**Core idea**: Compile multi-step symbolic reasoning into single-step LM inference, analogous to human "knowledge compilation" (Anderson's ACT-R skill acquisition).

**Technical approach**:
1. **Vector-Quantized Procedural Memory**: Production rules encoded as discrete procedure-units in a codebook C = {c₁...c_K}. Working memory chunks mapped to nearest codebook entries via Euclidean distance.
2. **Gated integration**: Runtime procedure R integrated into hidden states via `H_l = FFN(E_work + g_out ⊙ α(R))` with learned gating.
3. **Contrastive Planning**: Dual banks — M⁺ (success procedures) and M⁻ (failure procedures). Decoding score: `S(x_i) = log p⁺(x_i) - log p⁻(x_i)` suppresses failure patterns while boosting proven sequences.

**Results**:
- PDDLGym (Minecraft): +13.6% CSR over LongMem
- VirtualHome: +12.4% CSR over DT-Mem
- ALFWorld: +10.6% CSR over Optimus-2
- 83.6% CSR with 3B params vs 80.5% with 8B (PlaSma)
- Under 5s time constraints: 50.6% CSR where symbolic planners need >10s

**Clarvis relevance**: Maps directly to `procedural_memory.py` + `tool_maker.py` pipeline. Instead of multi-step brain lookups for known procedures, compiled procedures could bypass the search chain entirely. The success/failure bank pattern maps to episode-based task scoring (already partially implemented).

---

## 3. StateFlow — FSM-Controlled LLM Execution

**Paper**: Wu et al., "StateFlow: Enhancing LLM Task-Solving through State-Driven Workflows"
**URL**: https://arxiv.org/abs/2403.11322

**Core idea**: Model agent task-solving as a transducer FSM. Separate "process grounding" (state machine) from "sub-task solving" (LLM actions within states).

**FSM formalism**: Six-tuple (S, s₀, F, Ω, δ, Γ*) where:
- States S = process phases (Init, Observe, Solve, Verify, Error, End)
- Transitions δ = heuristic rules or LLM decisions
- Output functions Ω = LLM calls + tool invocations per state
- Context history Γ* = cumulative interaction record

**Key innovation**: Unlike ReAct which relies on LLM to judge task status and error handling, StateFlow enforces structured workflows through explicit states. Error state handles failures explicitly; Verify state checks output before submission.

**SF_Agent variant**: Each state gets a separate agent with its own instructions, preventing prompt accumulation. Different LLMs can serve different states.

**Results**:
- InterCode SQL: +13% over ReAct, 5x cost reduction ($3.82 vs $17.73)
- ALFWorld: +28% over ReAct, 3x cost reduction
- InterCode Bash: +7.5% over ReAct, 4.2x cost reduction
- Ablation: removing Observe, Error, or Verify states each degrades performance

**Clarvis relevance**: The heartbeat pipeline (gate→preflight→execute→postflight) is already an implicit FSM. Formalizing it with explicit state definitions, transition rules, and an Error/Retry state could improve error recovery and prevent cascading failures. The SF_Agent pattern (different LLMs per state) maps to task_router.py model selection.

---

## Synthesis: Three Complementary Approaches to Action Accuracy

| Approach | When it helps | Error type prevented | Clarvis mapping |
|----------|--------------|---------------------|-----------------|
| Symbolic verification (Metagent-P) | Pre-execution | Infeasible action attempts | preflight verifier |
| Compiled procedures (NeSyPr) | Planning phase | Multi-step reasoning errors | procedural_memory.py |
| FSM control flow (StateFlow) | Execution control | Skipped steps, poor error handling | heartbeat pipeline |

**Combined pattern**: Use FSM to control the overall flow, symbolic rules to verify each planned action before execution, and compiled procedures for known task types to bypass expensive multi-step reasoning.

---

## Ideas for Clarvis Application

1. **Heartbeat FSM formalization**: Define explicit states for the heartbeat pipeline with transition rules. Add Error state with retry logic and Verify state before marking tasks complete. Low effort, high impact on reliability.

2. **Preflight symbolic verifier**: Before spawning Claude Code, check task feasibility against symbolic rules (e.g., "file X must exist", "service Y must be running", "dependency Z installed"). Catches infeasible tasks without LLM cost. Maps to Action Accuracy improvement.

3. **Procedure compilation for common tasks**: For frequently-executed task types (brain optimization, research, implementation), compile proven step sequences into procedural templates that bypass full preflight reasoning. Relates to existing `tool_maker.py` LATM pipeline.

4. **Contrastive episode scoring**: Implement NeSyPr-style success/failure banks for task selection — weight candidate tasks by similarity to past successes vs failures. Extends existing episode-based scoring.

5. **SF_Agent-style model routing**: Already implemented in task_router.py — validate that state-based routing outperforms uniform model assignment.

---

## Weakest Metric Note

Action Accuracy (0.968, target 0.8) is already well above target, but these approaches would further reduce the remaining 3.2% error rate:
- Symbolic pre-verification catches structurally infeasible actions
- FSM control flow prevents execution-order errors
- Compiled procedures reduce novel-reasoning errors for known task types
