# Self-Debugging Code Generation Architectures

**Research Date:** 2026-03-13
**Sources:** arXiv:2502.02928 (PyCapsule), arXiv:2405.11403 (MapCoder), arXiv:2501.12793 (Self-Generated Tests)

## Paper Summaries

### PyCapsule: Two-Agent Pipeline (+24.4% BigCodeBench)
- **Architecture**: Programmer Agent (LLM) + Executor Agent (Docker, deterministic)
- **Key innovation**: 3 deterministic error pre-processing steps BEFORE LLM sees errors:
  1. Error type analysis (classify contextually)
  2. Relevance filtering (focus on target file, discard framework noise)
  3. Critical error truncation (RecursionError stack traces → compact)
- **Debug cap**: Max 5 attempts. Effectiveness follows exponential decay (R²≈1.0). GPT-4 plateaus at 3 attempts.
- **Token efficiency**: Avg 1.38 API calls/problem, 484 tokens/problem (GPT-4 HumanEval)
- **History**: Markov — only most recent problem+solution pair retained, older iterations discarded
- **Results**: HumanEval 96.5% (GPT-4), BigCodeBench +24.4% (Qwen-7B)

### MapCoder: 4-Agent Recall-Plan-Generate-Debug (93.9% HumanEval)
- **Architecture**: Retrieval → Planning → Coding → Debugging agents
- **Key innovation**: Debugging agent receives original PLAN alongside errors (architectural intent)
- **Multi-plan fallback**: k plans ranked by confidence; if debug fails after t attempts on plan_i, try plan_{i+1}
- **Traversal**: For each plan: code → test → [debug×t] → next plan. Max k*(1+t) API calls.
- **Test oracle**: Only sample I/O pairs — explicitly avoids AI-generated tests ("8% HumanEval failures from invalid AI tests")
- **Token-heavy**: Acknowledged weakness — accuracy over efficiency
- **Results**: HumanEval 93.9%, MBPP 83.1%, CodeContests +132.8%

### In-Execution Self-Debugging: Runtime State Analysis
- **Critical finding**: Post-execution debugging with self-generated tests HURTS performance (-3.1% to -7.3%)
  - Self-generated test accuracy: only 89.77% per test (GPT-4o), 44-59% full suite validity
  - False negatives break working code; false positives mask bugs
- **Solution**: Bypass test verdicts. Capture variable state snapshots at basic block boundaries.
- **Architecture**: Parse → basic blocks → execute block-by-block → capture variable states → LLM reasons from intermediate computation
- **Debug cap**: Max 2 iterations
- **Results**: HumanEval 93.3% (GPT-4o, +1.2% from base), key finding is that post-exec self-debug DECREASES performance

## 5 Actionable Patterns for Clarvis Heartbeat

### Pattern 1: Deterministic Pre-Processing Before LLM Debug (PyCapsule)
- Run syntax check, import verification, type hints, test execution DETERMINISTICALLY
- Only escalate to LLM if deterministic checks fail
- Feed LLM refined error context, not raw stderr
- **Implementation**: Add validation step between heartbeat execution (step 3) and postflight (step 4)

### Pattern 2: Exponential Decay Caps (PyCapsule)
- Hard-cap debug iterations at 2-3 (diminishing returns proven)
- Track decay curve in metrics
- If first fix fails, switch strategy rather than retry same approach

### Pattern 3: Plan-Derived Debugging (MapCoder)
- Record task plan during preflight; pass plan+errors to debug iteration
- If same-plan debugging fails after 2 attempts, re-run preflight with alternative strategy instruction
- Plan provides "why" context that pure error messages lack

### Pattern 4: Runtime State Over Test Verdicts (In-Exec Self-Debug)
- Don't rely solely on "do tests pass?" especially for agent-generated tests
- Add intermediate assertions/logging at key computation points
- Provide execution traces to LLM debugger, not just pass/fail
- Especially important when test suites are incomplete or agent-authored

### Pattern 5: Markov History Pruning (PyCapsule)
- Keep only current task + most recent code + most recent refined error in context
- Store full attempt history in episodic memory (ClarvisDB), don't load into LLM context
- Maps to context_compressor: compress aggressively for retry iterations

## Priority Implementation Order
| # | Pattern | Impact | Effort | Files |
|---|---------|--------|--------|-------|
| 1 | Deterministic pre-processing | High | Low | quality.py, heartbeat_postflight.py |
| 2 | Debug iteration caps | High | Low | heartbeat config |
| 3 | Plan-derived debugging | Medium | Medium | heartbeat_preflight.py, context assembly |
| 4 | Runtime state analysis | Medium | Medium | postflight episode encoding |
| 5 | Markov history pruning | High | Low | context_compressor.py |

## Cross-References
- VeriGuard + TiCoder research: `memory/research/veriguard_ticoder.md`
- Code quality metrics: `clarvis/metrics/quality.py`
- Benchmark targets: `clarvis/metrics/benchmark.py`
