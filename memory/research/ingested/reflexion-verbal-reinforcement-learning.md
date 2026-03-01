# Reflexion: Language Agents with Verbal Reinforcement Learning

**Authors:** Noah Shinn, Federico Cassano, Edward Berman, Ashwin Gopinath, Karthik Narasimhan, Shunyu Yao
**Venue:** NeurIPS 2023
**Paper:** https://arxiv.org/abs/2303.11366
**Code:** https://github.com/noahshinn/reflexion (3.1k stars)

## Core Idea

Reflexion replaces traditional RL weight updates with **verbal self-reflection**. After a failed attempt, an LLM generates a natural language reflection ("I should have done X instead of Y because Z") and stores it in an episodic memory buffer. On the next attempt, these reflections are injected into the prompt, giving the agent a "semantic gradient" — concrete verbal direction for improvement without any parameter updates.

## Architecture (3 Components)

1. **Actor** — LLM agent that executes tasks, conditioned on observations + episodic memory buffer
2. **Evaluator** — Scores trajectories (exact match, heuristic rules, or LLM-based); produces scalar success/failure signal
3. **Self-Reflection Model** — Takes (trajectory, reward) as input; outputs verbal feedback identifying root causes and suggesting alternatives. This "amplifies" a sparse scalar reward into rich semantic guidance

**Trial Loop:** attempt → evaluate → if failed: self-reflect → store reflection → retry with reflections in context → repeat until success or max trials

## Key Results

| Benchmark | Baseline | Reflexion | Improvement |
|-----------|----------|-----------|-------------|
| HumanEval (Python) | 80.1% (GPT-4) | **91.0%** | +10.9pp (new SOTA) |
| AlfWorld (decision-making) | ~81% (ReAct) | **97%** (130/134) | +22% abs over 12 trials |
| HotPotQA (reasoning) | 61% (CoT) | **75%** | +14pp |
| LeetcodeHard (Python) | 7.5% (GPT-4) | **15.0%** | +7.5pp (2x) |

## Critical Findings

1. **Reflection > Trajectory Replay**: Self-reflection summaries give +8% absolute over raw episodic memory (trajectory history alone). Distilled insights beat raw experience.
2. **Both components needed**: Ablation on HumanEval Rust shows removing either test generation OR self-reflection eliminates the improvement. Neither alone suffices.
3. **Evaluator quality is the bottleneck**: MBPP has 16.3% false positive rate (incorrect code passes tests) vs HumanEval's 1.4%. Higher false positives → worse Reflexion performance. Bad evaluation → bad reflections → no learning.
4. **Fails on high-exploration tasks**: WebShop (e-commerce browsing) showed zero improvement — tasks requiring diverse strategies rather than targeted correction resist this approach.
5. **Requires strong base models**: StarChat-beta (weaker model) showed no improvement from Reflexion. It's an emergent capability of larger, stronger models.
6. **Bounded memory is sufficient**: Only 1-3 prior reflections needed (not full history). AlfWorld: 3 reflections, HotPotQA: 3, coding: 1.

## Mapping to Clarvis Architecture

### What Clarvis Already Has (Partial Reflexion)
- **Episodic memory** (`episodic_memory.py`): Episodes with outcome, valence, causal links — similar to Reflexion's trajectory storage
- **Failure amplifier** (`failure_amplifier.py`): Detects 9 types of soft failures — acts as an enhanced Evaluator
- **Synthesize** (`episodic_memory.synthesize()`): Extracts aggregate patterns (domain failure rates, action verb analysis) — partial Self-Reflection
- **Auto-linking** (`_auto_link()`): Detects RETRY/FIX/BLOCKED causal relationships — richer than Reflexion's memory
- **Retry with context** (`heartbeat_preflight.py`): Recalls similar past episodes on retry — partial in-context learning
- **Confidence calibration** (`clarvis_confidence.py`): Metacognitive prediction-outcome tracking — beyond Reflexion

### The 3 Gaps

**GAP 1 — No Per-Failure Verbal Reflection:**
Clarvis `synthesize()` generates aggregate statistics ("domain X has 35% failure rate") but NOT specific verbal reflections per failure ("I failed because I imported the wrong module; next time I should check sys.path first"). Reflexion's power comes from failure-specific, actionable verbal feedback.

**GAP 2 — Reflections Not Injected Into Retry Prompts:**
When preflight selects a retry task, it recalls similar episodes but doesn't inject structured "what went wrong and how to fix it" text. The actor (Claude Code) doesn't see a curated verbal reflection — just raw episode metadata.

**GAP 3 — No Dedicated Reflection LLM Call:**
Reflexion uses a separate LLM invocation specifically for generating the reflection. Clarvis's reflection is rule-based pattern extraction, not LLM-generated verbal reasoning about why a specific failure occurred.

## Concrete Implementation Ideas

### Idea 1: Verbal Reflection Field in Episodes
Add a `reflection_text` field to episode schema. After each failure, generate a 2-3 sentence verbal reflection:
```
"Task '{fix module imports}' failed with ImportError. Root cause: brain.py was imported without
sys.path setup. Next attempt should ensure scripts/ is on sys.path before any import. The error
was in line 3 — the import runs before path setup."
```
This can be generated cheaply by the postflight script from the error output, or via a quick LLM call.

### Idea 2: Reflection Injection in Preflight
When `heartbeat_preflight.py` selects a task that has prior failed episodes:
1. Retrieve failed episodes for this task (via causal links: RETRY relationship)
2. Extract their `reflection_text` fields
3. Inject into the Claude Code prompt as: "PRIOR ATTEMPT REFLECTIONS: [reflection_text]"
4. Limit to last 2-3 reflections (bounded, per Reflexion findings)

This directly closes the Reflexion loop: fail → reflect → store → recall on retry → succeed.

### Priority and Effort
- **Idea 1** (reflection field): Low effort. Modify `episodic_memory.encode()` + `heartbeat_postflight.py`. Can start with template-based reflections from error messages, upgrade to LLM-generated later.
- **Idea 2** (preflight injection): Medium effort. Modify `heartbeat_preflight.py` prompt construction. Requires Idea 1 as prerequisite.
- **Expected impact**: Based on Reflexion's +8% boost from verbal reflection over raw episodic memory, this should meaningfully improve Clarvis's retry success rate.

## Key Takeaway

Reflexion's core insight is that **verbal self-reflection is a form of gradient descent in language space**. The "loss function" is the evaluator, the "gradient" is the verbal reflection, and the "weight update" is storing the reflection in episodic memory for future conditioning. Clarvis has the memory infrastructure but lacks the verbal reflection generation step — adding it should be high-value and architecturally clean.

---
*Researched: 2026-02-28 | Ingestion pending*
