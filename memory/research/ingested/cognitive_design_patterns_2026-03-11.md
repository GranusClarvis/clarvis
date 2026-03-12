# Research: Cognitive Design Patterns for LLM Agents

**Paper**: Wray, Kirk & Laird (2025). "Applying Cognitive Design Patterns to General LLM Agents." arXiv:2505.07087. AGI25 (oral).
**Date**: 2026-03-11
**Focus**: Systematization of recurring cognitive patterns from classical architectures (ACT-R, SOAR, LIDA, BDI) mapped to modern LLM agent systems.

## Paper Summary

10 cognitive design patterns identified across pre-transformer architectures that recur in modern LLM agent systems. Key insight: different research groups independently converged on similar patterns. This is a *pattern catalog with implementation guidance*, not a taxonomy (cf. CoALA 2023).

## The 10 Patterns → Clarvis Mapping

| # | Pattern | Classical Source | Clarvis Implementation | Coverage |
|---|---------|----------------|----------------------|----------|
| 1 | **Observe-Decide-Act** | BDI, Soar | heartbeat_gate → preflight → Claude Code → postflight | **Full** |
| 2 | **Three-Stage Memory Commitment** | BDI, Soar | brain.remember() is direct assertion — no candidate→select→reconsider | **Weak** |
| 3 | **Hierarchical Decomposition** | BDI HTN, Soar | Auto-split in preflight (ensure_subtasks_for_tag), QUEUE.md hierarchy | **Present** |
| 4 | **Short-Term Context Memory** | ACT-R buffers, Soar WM | cognitive_workspace.py: Active(5)/Working(12)/Dormant(30) buffers | **Full** |
| 5 | **Ahistorical Knowledge (Semantic)** | ACT-R, Soar | ClarvisDB 10 collections, ONNX embeddings, activation-mediated recall | **Full** |
| 6 | **Historical Knowledge (Episodic)** | Soar | episodic_memory.py: encode, recall_similar, causal_link, spreading_activation | **Strong** |
| 7 | **Procedural Knowledge** | ACT-R, Soar, BDI | procedural_memory.py: S=(C,π,T,R) tuples, quality tiers, retirement | **Full** |
| 8 | **Knowledge Compilation/Chunking** | ACT-R, Soar | tool_maker.py (LATM), learn_from_task, compose_procedures | **Partial** |
| 9 | **Commitment & Reconsideration** | BDI, Soar | mark_task_in_progress prevents re-selection; no mid-execution reconsideration | **Weak** |
| 10 | **Step-Wise Reflection** | LLM-native | cron_reflection.sh (8-step pipeline), clarvis_reflection.py | **Full** |

**Scoreboard**: 5 Full, 1 Strong, 1 Present, 1 Partial, 2 Weak = **7.5/10 patterns realized**

## Detailed Gap Analysis

### GAP 1: Commitment & Reconsideration (Pattern 9) — MOST SIGNIFICANT

The paper notes: "Chat-focused LLMs tend to resist major redirection in the trajectory of their token generation." Clarvis confirms this — once Claude Code is spawned for a task, there is no mechanism to:
- Reconsider the task choice mid-execution
- Abort gracefully if conditions change
- Redirect to a higher-priority task that emerges

**In Soar**: Impasses naturally trigger subgoaling → reconsideration. **In BDI**: Explicit reconsideration policy evaluates whether current intentions still serve desires.

**Clarvis workaround**: Timeout-based kill + retry. But this is a blunt instrument vs. principled reconsideration.

**Actionable**: Add a reconsideration gate — if a heartbeat detects a running task has exceeded 50% of timeout with zero stdout, surface a "reconsider?" flag. Or: track task progress via intermediate file writes and reconsider if progress stalls.

### GAP 2: Three-Stage Memory Commitment (Pattern 2)

Paper describes: (1) Generate candidate beliefs/desires, (2) Select/commit, (3) Reconsider (remove/reaffirm).

Clarvis's `brain.remember()` directly asserts memories. No:
- Candidate generation stage (what *should* be remembered?)
- Commitment gate (is this memory worth the storage/retrieval cost?)
- Reconsideration (does this memory still hold? contradicted by new evidence?)

**Partial existing work**: `cleanup_policy.py` does post-hoc pruning (stage 3 only). `memory_consolidation.py` does some merging. But no principled pre-commit evaluation.

**Actionable**: Add `brain.propose(text, importance)` → returns candidate with estimated utility → `brain.commit(candidate_id)` to persist. Could improve memory quality by filtering low-utility memories before storage.

### GAP 3: Online Knowledge Compilation (Pattern 8)

Paper identifies: "Caches the results of reasoning steps into a more compact representation, essentially amortizing the cost of expensive reasoning."

Clarvis does this **offline** (postflight: learn_from_task, tool_maker extraction). But NOT during execution. Classical architectures compile production rules *while solving problems*.

**Actionable**: Stream Claude Code output for mid-execution extraction of reusable patterns. Could use a lightweight parser on buffered output to identify tool-call sequences worth compiling into procedures.

### GAP 4: Episodic Segmentation (Pattern 6)

Paper notes Generative Agents uses "static periods" not true event-boundary segmentation. Clarvis's episodic_memory uses keyword overlap + temporal proximity (20-episode window) for auto-linking — better than static but still not perceptual-shift detection.

**Low priority**: Current approach works well enough (strong rating). True segmentation would require real-time perceptual monitoring during execution.

## Heartbeat Pipeline Validation

Paper's Observe-Decide-Act maps cleanly to Clarvis heartbeat:

```
OBSERVE:  heartbeat_gate.py (environment sensing — locks, load, schedule)
          + preflight §1 (attention tick + codelet competition — LIDA pattern)
          + preflight §2-§8 (task scoring, brain search, episodic recall)
DECIDE:   preflight task selection with defer-fallback loop + confidence tiers
          + cognitive load check + task sizing
ACT:      Claude Code execution (spawned with context brief)
REFLECT:  postflight (episode encoding, confidence recording, reasoning chain close)
```

The heartbeat already implements a richer cycle than basic ReAct (which the paper criticizes for lacking explicit commitment). Clarvis adds:
- LIDA-style codelet competition (attention.py) — not in paper's LLM examples
- Somatic markers (somatic_markers.py) — implicit commitment weighting
- ACT-R activation decay (actr_activation.py) — matches paper's Pattern 5 exactly
- Spreading activation in episodic recall — Soar-aligned

## Key Findings from Paper

1. **ReAct lacks commitment**: Observation→Action loop skips the decide/commit stage. Clarvis's preflight task selection + confidence tiers address this.
2. **Episodic memory in LLM agents is incomplete**: Most systems use semantic similarity for recall; true episodic memory requires encoding specificity (context-dependent retrieval). Clarvis partially addresses this with causal linking and activation tracking.
3. **Non-monotonic reasoning is hard for LLMs**: Token generation resists backtracking. Clarvis works around this by externalizing reconsideration to the heartbeat layer (between executions, not within).
4. **Knowledge compilation utility problem**: Deciding *what* to compile is as hard as the original problem. Clarvis's procedural_memory quality tiers (CANDIDATE→VERIFIED→STALE) address this with usage-based evaluation.

## Suggested QUEUE Items

1. `[RECONSIDER_GATE]` Add mid-execution progress monitoring — check for stalled tasks and enable graceful abort + re-queue. Addresses Pattern 9 gap.
2. `[MEMORY_PROPOSAL_STAGE]` Add brain.propose() → brain.commit() two-stage memory pipeline. Addresses Pattern 2 gap.
3. `[ACTR_WIRING]` (already in QUEUE) — Wire actr_activation.py into recall path. Directly validates Pattern 5 implementation.

## References

- Wray, Kirk & Laird (2025). arXiv:2505.07087
- Sumers et al. (2023). CoALA: Cognitive Architectures for Language Agents. arXiv:2309.02427
- Yao et al. (2023). ReAct. ICLR 2023.
- Laird (2012). The Soar Cognitive Architecture.
- Anderson et al. (2004). ACT-R Theory of Cognition.
