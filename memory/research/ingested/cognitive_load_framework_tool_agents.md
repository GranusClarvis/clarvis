# Cognitive Load Framework for Tool-Use Agent Boundaries

**Paper**: Beyond Accuracy: A Cognitive Load Framework for Mapping the Capability Boundaries of Tool-use Agents
**Authors**: Qihao Wang, Yue Hu, Mingzhe Lu, Jiayue Wu, Yanbing Liu, Yuanmin Tang
**Year**: 2026 (Accepted AAAI 2026)
**Source**: arXiv:2601.20412

## Key Ideas

### 1. Cognitive Load Theory (CLT) Applied to LLM Tool-Use
First formal application of Sweller's CLT to AI agent evaluation. Decomposes task difficulty into two orthogonal, measurable axes:
- **Intrinsic Load (CL_I)**: Structural complexity of the solution path — how many tools, how they depend on each other, how far apart data must flow between operations
- **Extraneous Load (CL_E)**: Presentation-layer difficulty — query ambiguity, distractor tools in the available set

### 2. Tool Interaction Graphs (TIGs)
Novel DAG formalism for ground-truth solution paths:
- **Nodes**: user query nodes + function call nodes
- **Edges**: data dependencies (output→input) + execution dependencies (procedural ordering)
- **Edge weight formula**: `w(e) = δ(vi, vj) · (1 + λ·I(vi, vj))`
  - `δ` = attentional distance (conversational turns between operation and its use)
  - `I` = selection interference (count of competing but incorrect entities of the same type)
- Total intrinsic load = sum of edge weights across all function nodes

### 3. Exponential Performance Decay Model
Central finding — success probability follows:
```
P_succ(op) = exp(−(k · CL + b))
```
- **k** = load sensitivity (how fast performance degrades with complexity)
- **b** = baseline load (inherent difficulty floor)
- **CL_Total = CL_I + ω_E · CL_E** (weighted sum, ω_E calibrated empirically)
- Validated via Hosmer-Lemeshow test (p > 0.05 for all models)

### 4. ToolLoad-Bench: Parametrically Adjustable Benchmark
- 500 task instances, 10 domains, 106 tools, avg 4.9 tool calls/instance
- Constructed via graph generation + edge insertion + manual annotation
- Allows isolating intrinsic vs extraneous load effects independently

### 5. Performance Cliff Findings (Model Rankings)
| Model | Accuracy | k (sensitivity) | b (baseline) |
|-------|----------|-----------------|-------------|
| xLAM2-32B (fine-tuned) | 78.8% | 0.034 | 1.22 |
| GPT-4o | 68.0% | 0.067 | 1.71 |
| Claude 3.7 | 64.8% | 0.073 | 1.57 |
| Gemini 2.5 | 60.0% | 0.088 | 1.22 |
| Qwen3-32B | 55.2% | 0.075 | 1.60 |
| Qwen3-8B | 38.6% | 0.085 | 1.12 |
| Llama3.3-70B | 17.0% | — | — |

Key insight: Lower k = more graceful degradation under load. Fine-tuned specialist (xLAM2) has both lowest k and best accuracy. General-purpose models hit cliffs much earlier.

## Application to Clarvis Architecture

### A. task_router.py Enhancement
Current router uses 14-dimension keyword scoring (code_generation, file_editing, multi_step, etc.) with fixed tier boundaries. The CLT framework suggests replacing or augmenting this with:
- **TIG-based intrinsic load scoring**: Analyze task description for implied tool dependency chains (sequential steps, data passing between operations, parallel branches). Count implied edges and attentional distances.
- **Extraneous load scoring**: Measure query ambiguity (vague vs. specific instructions) and distractor toolset size (how many irrelevant tools/scripts available).
- **Exponential model for success prediction**: Fit k and b parameters from historical heartbeat success/failure data, then use `P_succ = exp(−(k·CL + b))` to predict whether a task will succeed before attempting it.

### B. Heartbeat Mode Selection
Preflight currently routes to introspection budgets (minimal/standard/full) based on tier. CLT gives a principled way to calibrate:
- **CL < threshold_low** → QUICK mode (minimal introspection, short timeout)
- **CL in mid-range** → STANDARD mode
- **CL > threshold_high** → DEEP mode (full introspection, extended timeout, more episodic context)

### C. spawn_claude.sh Timeout Calibration
Current: fixed minimum 600s, default 1200s, large 1800s. CLT suggests:
- `timeout = base_timeout × (1 + α · CL_Total)` — scale timeout proportional to cognitive load
- High-load tasks get more time; low-load tasks finish faster

### D. Task Decomposition Trigger
When CL_Total exceeds a model's capability boundary (P_succ < threshold), automatically decompose into sub-tasks with lower individual CL rather than attempting the full task. This maps to the CoThinker insight: distribute intrinsic load across specialized sub-agents.

## Concrete Implementation Ideas

### Idea 1: CL Scorer Module
Add `cognitive_load.py` to scripts/ that:
1. Parses task text for implied tool dependency structure (regex + heuristic TIG construction)
2. Computes CL_I from implied chain length, parallelism, and data-passing distance
3. Computes CL_E from query ambiguity signals (presence of "something", "maybe", "if needed") and toolset size
4. Returns CL_Total, predicted P_succ, and recommended mode/timeout
5. Logs to `data/cognitive_load_history.jsonl` for fitting k/b parameters over time

### Idea 2: Historical k/b Fitting
After ~50 heartbeats with CL scores, fit the exponential model:
- Collect (CL_Total, success/failure) pairs from episodic memory
- Fit `k` and `b` via logistic regression on `log(P_succ) = −(k·CL + b)`
- Use fitted model to predict task success and auto-skip tasks predicted to fail (or decompose them)

## Related Work
- **CoThinker (arXiv:2506.06843)**: Multi-agent CLT — distributing cognitive load across specialized agents reduces intrinsic load per agent. Applicable to Clarvis's project agent orchestrator.
- **LATS (Language Agent Tree Search)**: Already ingested. Tree search can be seen as reducing intrinsic load by exploring multiple solution paths.
- **SICA (Self-Improving Coding Agent)**: Already ingested. Self-improvement loop can calibrate k/b over time.
