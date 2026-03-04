# AgentDebug: Where LLM Agents Fail and How They Learn From Failures

**Paper**: "Where LLM Agents Fail and How They can Learn From Failures"
**Authors**: Kunlun Zhu, Zijia Liu, Bingxuan Li, Muxun Tian, et al. (18 authors, UIUC + Stanford)
**Published**: arXiv:2509.25370, September 2025
**Code**: https://github.com/ulab-uiuc/AgentDebug

## Core Contributions

### 1. AgentErrorTaxonomy — 5 Module Failure Categories

| Module | Frequency | Subcategories | Cascade Rate |
|--------|-----------|--------------|--------------|
| **Memory** | 31% | Hallucination, retrieval failure, false recall, constraint forgetting | 82% → Planning (4.2 avg chain) |
| **Planning** | 27% | Impossible actions, constraint ignorance, incoherent subgoals, inefficient plans | 89% → Action (3.8 avg chain) |
| **Action** | 19% | Malformed outputs, incorrect parameters, format errors, outdated info | — |
| **Reflection** | 18% | Progress misjudgment, outcome misinterpretation, causal misattribution, loop blindness | — |
| **System** | 5% | Step limits, tool crashes, API mismatches, token exhaustion | 95% → Termination |

**Key finding**: Cascading failures are the dominant failure mode. A single root-cause error propagates through subsequent decisions — debugging symptoms is futile without tracing to root cause.

### 2. AgentErrorBench — Annotated Failure Dataset

- 200 failed trajectories (ALFWorld 100, GAIA 50, WebShop 50)
- 10 expert annotators, inter-annotator κ = 0.55
- Step-level annotations: root cause identification + propagation paths + severity + remediation hints
- Larger evaluation sets: ALFWorld 1,847, GAIA 2,103, WebShop 1,756 trajectories

### 3. AgentDebug — 3-Stage Debugging Pipeline

**Stage 1: Fine-Grained Analysis** — Step-by-step trajectory analysis classifying errors per module using the taxonomy. Maps each decision point to potential error patterns.

**Stage 2: Critical Error Detection** — Counterfactual testing identifies the *earliest* critical error that caused final failure. Uses causal inference to distinguish symptoms from root causes (87% accuracy). Key question: "If this step had been different, would the task have succeeded?"

**Stage 3: Targeted Feedback + Re-Rollout** — Generates specific, actionable corrective feedback addressing the root cause (not symptoms). Re-executes from the failure point, not from scratch. Iterative: each failure teaches the next attempt.

### Results

| Metric | Baseline | AgentDebug | Improvement |
|--------|----------|-----------|-------------|
| All-Correct Accuracy | 42.3% | 52.5% | +24% |
| Step Accuracy | 67.8% | 79.3% | +17% |
| Error Recovery Rate | 12.1% | 38.7% | +220% |
| Cascade Prevention | 8.4% | 43.2% | +414% |
| Avg errors/task (iter 5) | 3.7 | 1.9 | -49% |

### Targeted Remediation by Module

- **Memory**: Structured schemas + periodic consolidation → 71% prevention
- **Reflection**: Explicit state verification checkpoints (expected vs actual) → 63% correction
- **Planning**: Multi-plan generation + constraint validation → 78% prevention
- **Action**: Pre-action parameter validation + rollback → 85% prevention
- **System**: Resource monitoring + adaptive throttling → 92% mitigation

## Relevance to Clarvis

### Direct Architectural Mapping

Clarvis already has modular equivalents for each failure category:
- **Memory** → `brain.py`, `episodic_memory.py`, `working_memory.py`, `cognitive_workspace.py`
- **Planning** → `heartbeat_preflight.py` (task selection), `attention.py` (salience)
- **Action** → heartbeat execution (Claude Code task dispatch)
- **Reflection** → `clarvis_reflection.py`, `heartbeat_postflight.py`
- **System** → `cron_watchdog.sh`, `health_monitor.sh`, timeout/lockfile management

### Current Gaps This Research Addresses

1. **No backward causal tracing**: When tasks fail, postflight records the failure but doesn't trace backward to find the root cause. The episodic system stores episodes but doesn't analyze propagation chains.
2. **No counterfactual analysis**: Clarvis never asks "if this decision had been different, would the outcome change?"
3. **No failure-specific feedback injection**: When re-attempting failed tasks, preflight doesn't inject corrective lessons from prior failure analysis.
4. **Memory consolidation lacks verification checkpoints**: We consolidate but don't periodically verify constraints are still accessible.

## Concrete Implementation Ideas

### Idea 1: Failure Trajectory Logger (Low effort, high value)

Extend `heartbeat_postflight.py` to capture step-level decision traces when tasks fail:
```python
if task_failed:
    trajectory = {
        "task": task_description,
        "preflight_decisions": preflight_context,  # what was selected and why
        "execution_steps": claude_output_parsed,     # step-by-step from output
        "failure_point": detected_failure,
        "module_classification": classify_error(failure),  # memory/planning/action/reflection/system
        "timestamp": now
    }
    store_failure_trajectory(trajectory)  # data/failure_trajectories.jsonl
```

### Idea 2: Root Cause Tracer for Episodic Memory (Medium effort)

Add backward analysis to episodic recall when similar tasks appear:
```python
def get_failure_lessons(current_task):
    """When preflight selects a task, check if similar tasks failed before."""
    similar_failures = search_failure_trajectories(current_task)
    if similar_failures:
        root_causes = [trace_root_cause(f) for f in similar_failures]
        return format_corrective_feedback(root_causes)
    return None
```

Inject the corrective feedback into the Claude Code prompt during heartbeat execution. This is the core AgentDebug insight: targeted feedback from prior failures dramatically improves success rates.

### Idea 3: Decreasing-Hazard Transform (Strategic)

The paper's key theoretical result: AgentDebug transforms agents from constant-hazard (failure rate stays flat) to decreasing-hazard (reliability improves with experience). Clarvis's episodic memory + procedural memory already provide the substrate — what's missing is the systematic failure→lesson→prevention loop. Building this would directly boost the Autonomous Execution pillar (success > 85% target).
