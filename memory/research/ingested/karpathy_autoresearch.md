# Karpathy Autoresearch — Deep Dive (2026-03-08)

**Source**: [github.com/karpathy/autoresearch](https://github.com/karpathy/autoresearch) (~3k stars, released March 2026)
**Context**: User-requested research. Andrej Karpathy's autonomous ML experimentation framework.

## What It Is

An AI agent autonomously experiments on LLM training code overnight. The agent modifies `train.py` (a ~630-line GPT training script), trains for exactly 5 minutes, evaluates validation bits-per-byte (val_bpb), keeps improvements, discards regressions, and repeats. ~12 experiments/hour, ~100 overnight on a single GPU.

## Architecture (3 files)

| File | Role | Modified by |
|------|------|-------------|
| `prepare.py` | Data prep, tokenizer, eval utilities | Nobody (fixed) |
| `train.py` | GPT model + Muon/AdamW optimizers + training loop | Agent |
| `program.md` | Human instructions defining research strategy | Human |

**Key constraint**: Agent can only touch `train.py`. Evaluation harness (`prepare.py`) is immutable. This prevents drift and ensures fair comparison.

## Core Design Patterns

### 1. Markdown-as-Source-Code
`program.md` is not documentation — it IS the source code of the research organization. Humans "program the program" by writing markdown that defines exploration strategy, constraints, and objectives. The agent interprets and executes. This is meta-programming: you don't write Python to orchestrate, you write prose to guide.

### 2. Fixed Time-Budget Experiments
Every experiment gets exactly 5 minutes of wall-clock training time (excluding startup/compilation). This makes all experiments directly comparable regardless of what the agent changes — architecture, tokenizer, hyperparameters. The time budget IS the normalization.

### 3. Single-Metric Keep/Discard
val_bpb (validation bits-per-byte) is the only metric. Lower = better. Vocabulary-size independent, so even tokenizer swaps are fairly compared. The agent commits improvements to a git feature branch and reverts regressions. No human review needed for the keep/discard decision.

### 4. Constraint Architecture
The deliberate constraints (single file, single GPU, single metric, fixed time) may be more important than the autonomy itself. Constraints make automated evaluation tractable, prevent uncontrolled drift, and enable meaningful comparison.

## Multi-Agent Experiment (8 agents)

Karpathy ran a separate experiment: 8 agents (4 Claude, 4 Codex) each with own GPU, same problem (remove logit softcap without regression). Key findings:

- **Parallelism works**: Infrastructure, git isolation, concurrent execution — all solid.
- **Scientific judgment fails**: Agents are strong implementers but weak at creative hypothesis generation, experiment design, controlling confounds, and recognizing spurious results.
- **Trivial rediscovery**: Agents "discovered" that larger networks improve loss — a confound, not insight.
- **Core bottleneck**: Not execution speed but upstream decision-making — deciding which experiments merit running.

## Ideas for Clarvis (5)

### 1. Formal Keep/Discard Loop for Autonomous Evolution
Currently Clarvis heartbeat executes tasks but has no automated revert mechanism for regressions. Autoresearch pattern: work on git branch, define success metric, auto-revert if metric degrades. Could apply to PI score, brain health, or task-specific metrics after heartbeat tasks.

### 2. Fixed Time Budgets for Fair Task Comparison
Clarvis heartbeat tasks vary wildly in duration. Standardizing time budgets per task category (like autoresearch's 5-min window) would make task outcomes comparable and enable automated performance tracking across evolution sessions.

### 3. Program.md Pattern for Agent Orchestrator
Clarvis already uses CLAUDE.md/AGENTS.md similarly — markdown defines agent behavior. But autoresearch takes it further: the markdown is iterated on as the primary development artifact. For project agents, the agent's instruction file could be the thing that evolves, not just the code.

### 4. Strengthen Upstream Decision-Making
Karpathy's multi-agent finding directly applies: Clarvis's agent orchestrator should invest more in task selection and experiment design (what to try) than in execution mechanics (how to try it). The heartbeat preflight attention scoring is already doing this — it's the right focus area.

### 5. Constraint Architecture for Reliability
Adding more constraints to autonomous execution could improve reliability more than adding capabilities. E.g., immutable evaluation harness per task category, single success metric, fixed scopes. This relates to context_relevance (0.838) — tighter constraints produce more relevant context.

## Context Relevance Connection

The program.md approach is fundamentally about context relevance — giving agents exactly the right context to make good decisions, nothing more. Autoresearch achieves this by constraining the agent's world to 3 files and 1 metric. Clarvis's context_relevance metric (0.838, target 0.7) could benefit from similar constraint thinking: tighter task scoping produces more relevant briefs.

## Sources

- [GitHub: karpathy/autoresearch](https://github.com/karpathy/autoresearch)
- [Karpathy X announcement](https://x.com/karpathy/status/2030371219518931079)
- [TopAIProduct analysis](https://topaiproduct.com/2026/03/07/autoresearch-karpathys-overnight-ai-researcher-that-runs-100-experiments-while-you-sleep/)
- [Glen Rhodes: Multi-agent experiment](https://glenrhodes.com/karpathys-multi-agent-research-org-experiment-parallelism-works-scientific-judgment-doesnt-yet/)
- [OpenFlows analysis](https://openflows.org/currency/currents/autoresearch-karpathy/)
