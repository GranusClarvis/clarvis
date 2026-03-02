# SICA: A Self-Improving Coding Agent

**Authors:** Maxime Robeyns, Martin Szummer, Laurence Aitchison (University of Bristol)
**Venue:** ICLR 2025 Workshop on Scaling Self-Improving Foundation Models (SSI-FM)
**arXiv:** [2504.15228](https://arxiv.org/abs/2504.15228)
**Code:** [github.com/MaximeRobeyns/self_improving_coding_agent](https://github.com/MaximeRobeyns/self_improving_coding_agent)

## Key Ideas

### 1. Unified Meta-Agent / Target-Agent
SICA eliminates the distinction between the meta-agent (that proposes improvements) and the target agent (that gets improved). The best-performing archived version IS the meta-agent. This is the first truly self-referential coding agent — it modifies its own Python codebase, not a separate DSL or prompt template.

### 2. Archive-Based Selection with Multi-Objective Utility
Each iteration is archived with full metrics. Selection uses a utility function:
```
U = 0.5 * benchmark_score + 0.25 * (1 - min(1, cost/$10)) + 0.25 * (1 - min(1, time/300s))
```
This prevents over-optimizing accuracy at the expense of cost/speed. Failed iterations don't get selected — providing natural regression protection.

### 3. Emergent Tool Development
Starting from a minimal base agent (file open/close, shell exec, calculator), SICA autonomously developed 14 cumulative improvements over 15 iterations:
- SmartEditor → Diff-Enhanced editing → Quick Overwrite (token reduction)
- CodeContextSummarizer (ripgrep-based exploration)
- AST Symbol Locator → Hybrid Symbol Locator (ripgrep + AST)
- Context-Sensitive Diff Minimization (AST-aware)
- File Size Thresholding (100KB cap)

Pattern: agents naturally evolve better file editing and code navigation first — these are highest-leverage for coding tasks.

### 4. Safety via Observability + Overseer
- Asynchronous LLM-based overseer runs every 30s, can cancel pathological behavior
- Docker isolation (agent executes shell commands)
- No weight updates — only scaffolding/prompt changes
- Interactive web dashboard for human observability

### 5. Results
- SWE-Bench Verified: **17% → 53%** (50-problem random subset)
- LiveCodeBench: **65% → 71%**
- File editing: **82% → 91%**
- Symbol location: **35% → 40%**
- Cost: ~$7,000 over 15 iterations using Claude 3.5 Sonnet v2
- Reasoning tasks (AIME/GPQA): marginal gains — scaffolding can disrupt native chain-of-thought

## Comparison with Prior Work

| System | Meta/Target Split | Modifies | Benchmarks | Truly Self-Improving |
|--------|------------------|----------|------------|---------------------|
| ADAS (Hu et al.) | Fixed meta-agent | DSL forward() | Search/reasoning | No |
| Gödel Agent | Separate logic | action_adjust_logic | Non-coding | Partial |
| **SICA** | **Unified** | **Full Python codebase** | **SWE-bench, LiveCodeBench** | **Yes** |

## Known Limitations
- **Path dependency**: Early improvements bias later iterations toward variations on the same theme
- **Benchmark saturation**: ~60+ iterations needed to exhaust improvements on static benchmarks; automated benchmark curation needed
- **Reasoning disruption**: Scaffolding overhead can degrade pure-reasoning model performance (o3-mini on AIME/GPQA)
- **Scalability**: Archive grows linearly; no discussion of pruning strategies at scale

## Application to Clarvis Architecture

### What We Already Have (Partial Analogs)
- **Modifiable codebase**: `scripts/` directory (~90 scripts) IS our agent code, directly editable
- **Evolution loop**: `cron_autonomous.sh` (12x/day) + `cron_evolution.sh` already implements iterative self-modification
- **Regression detection**: `heartbeat_postflight.py` tracks confidence, encodes episodes
- **Task scoring**: `heartbeat_gate.py` + `attention.py` provide task selection
- **Performance tracking**: `performance_benchmark.py` with PI composite score

### What We're Missing (SICA Gaps)
1. **No formal archive**: We don't snapshot agent code + benchmark scores per iteration. Our git history partially serves this role, but we lack structured retrieval of "which version scored best on what."
2. **No utility function**: We lack a multi-objective scoring function combining task success, cost, and time per evolution iteration.
3. **No archive-guided meta-improvement**: Evolution tasks are selected from QUEUE.md (human-curated priorities), not from failure analysis of archived iterations.
4. **No automated benchmark suite**: We don't systematically re-test the agent on a fixed problem set after modifications.

### Concrete Implementation Ideas

**Idea 1: Evolution Archive (`data/evolution_archive/`)**
After each `cron_evolution.sh` or `cron_autonomous.sh` execution:
- Snapshot modified files (git diff hash)
- Record metrics: task success (yes/no), time, token cost, confidence delta
- Store in JSONL: `{iteration, git_sha, task_id, utility_score, files_changed, metrics}`
- Before proposing new evolution: query archive for patterns — "which types of changes produced highest utility gains?"
- Select best-scoring recent iteration's approach as basis for next improvement

**Idea 2: Self-Improvement Benchmarks**
Create a small fixed benchmark suite (10-20 tasks) that tests core capabilities:
- Brain store/recall accuracy (existing in brain.py health)
- Script execution success rate
- Context compression quality
- Heartbeat task completion rate
- Add to `performance_benchmark.py` as a "regression suite"
- Run automatically after any script modification in `cron_evolution.sh`

These two additions would give Clarvis SICA-style evaluation-driven self-improvement without the full $7K API cost — leveraging our existing 12x/day heartbeat loop as the iteration mechanism.
