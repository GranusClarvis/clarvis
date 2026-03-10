# Deep Review: NousResearch/hermes-agent-self-evolution

**Repo**: https://github.com/NousResearch/hermes-agent-self-evolution
**Date reviewed**: 2026-03-09
**Stars**: 71 | **Created**: 2026-03-09 (same day!) | **Language**: Python (69.7KB)
**License**: MIT (core) + AGPL v3 (Darwinian Evolver integration, planned)
**Dependencies**: DSPy >= 3.0, OpenAI >= 1.0, PyYAML, Click, Rich; optional: pytest, darwinian-evolver

---

## 1. Executive Summary

Hermes Agent Self-Evolution is a standalone optimization pipeline that sits *outside*
the Hermes Agent codebase and systematically improves its text-based artifacts (skills,
tool descriptions, system prompts, code) through evolutionary search using LLM API calls.
No GPU training is involved. The entire system operates by mutating text, evaluating
results against rubric-based fitness functions, and selecting the best variants through
constraint-gated evolution.

Key result from Phase 1 validation: +39.5% improvement on a held-out eval example for
the "arxiv" skill using DSPy BootstrapFewShot with only 3 training examples, completing
in under 60 seconds at a cost of approximately $0.50.

The repo is brand new (all 5 commits on 2026-03-09), with only Phase 1 (Skill Evolution)
implemented. Phases 2-5 (tool descriptions, system prompts, code evolution, continuous
loop) are planned but exist only as placeholder __init__.py files.

---

## 2. Architecture Overview

### 2.1 Repository Structure

```
hermes-agent-self-evolution/
  evolution/                  # Main package
    __init__.py               # v0.1.0
    core/                     # Shared infrastructure
      __init__.py             # Re-exports EvolutionConfig
      config.py               # EvolutionConfig dataclass + repo discovery
      constraints.py          # ConstraintValidator — 5 hard gates
      dataset_builder.py      # SyntheticDatasetBuilder + GoldenDatasetLoader
      fitness.py              # LLMJudge + skill_fitness_metric heuristic
    skills/                   # Phase 1: Skill evolution (IMPLEMENTED)
      __init__.py
      skill_module.py         # SkillModule (DSPy Module wrapper) + load/find/reassemble
      evolve_skill.py         # Main orchestrator — 10-step evolution pipeline
    tools/                    # Phase 2: Tool description evolution (PLACEHOLDER)
    prompts/                  # Phase 3: System prompt evolution (PLACEHOLDER)
    code/                     # Phase 4: Code evolution via Darwinian Evolver (PLACEHOLDER)
    monitor/                  # Phase 5: Continuous monitoring (PLACEHOLDER)
  datasets/                   # Eval datasets (gitkeep, populated at runtime)
    skills/.gitkeep
    tools/.gitkeep
  tests/
    core/test_constraints.py  # 14 test cases for constraint validators
    skills/test_skill_module.py  # 8 test cases for skill parsing/reassembly
  reports/
    phase1_validation_report.pdf
  generate_report.py          # ReportLab PDF generator (24.5KB — the largest file)
  pyproject.toml
  PLAN.md                     # 40.7KB detailed plan document
  README.md
```

Total code: ~69.7KB Python. The `generate_report.py` (PDF builder) is 24.5KB alone,
making the actual evolution logic approximately 45KB across 6 meaningful source files.

### 2.2 Key Source Files by Importance

| File | Size | Purpose |
|------|------|---------|
| `evolution/skills/evolve_skill.py` | 13.2KB | **Main orchestrator** — 10-step evolution pipeline |
| `evolution/core/dataset_builder.py` | 7.4KB | Eval dataset generation (synthetic + golden) |
| `evolution/core/constraints.py` | 6.2KB | 5 constraint validators + test suite runner |
| `evolution/core/fitness.py` | 5.6KB | LLM-as-judge scorer + heuristic fitness metric |
| `evolution/skills/skill_module.py` | 4.0KB | DSPy module wrapper for SKILL.md files |
| `evolution/core/config.py` | 2.2KB | EvolutionConfig dataclass |

### 2.3 Dependencies and Their Roles

- **DSPy >= 3.0**: The backbone. Provides `dspy.Module`, `dspy.Signature`, `dspy.ChainOfThought`,
  `dspy.GEPA`, `dspy.MIPROv2`, `dspy.BootstrapFewShot`. The skill text becomes a DSPy parameter
  that optimizers can mutate.
- **OpenAI >= 1.0**: LLM API access (used via DSPy's `dspy.LM()` abstraction, supports OpenRouter)
- **Click**: CLI interface for `evolve_skill.py`
- **Rich**: Console output formatting (tables, panels, colored text)
- **darwinian-evolver** (optional, planned for Phase 4): Imbue's code evolution framework

---

## 3. Self-Evolution Loop Design

### 3.1 The 10-Step Pipeline (evolve_skill.py)

The core evolution loop in `evolve_skill.py` follows this exact sequence:

1. **Find and load skill** — Locates SKILL.md in the hermes-agent repo by name or fuzzy match.
   Parses YAML frontmatter (name, description, metadata) from markdown body.

2. **Build or load eval dataset** — Either generates synthetic test cases via LLM (reads
   the skill text and generates realistic task/expected_behavior pairs) or loads golden
   datasets from JSONL files.

3. **Validate baseline constraints** — Runs all 5 constraint validators on the original skill
   to establish baseline compliance. Proceeds even if baseline fails (with warning).

4. **Configure DSPy + GEPA optimizer** — Sets up the LLM backend, wraps the skill body as a
   `SkillModule` (DSPy Module where `skill_text` is the optimizable parameter), prepares
   train/val splits as DSPy Examples.

5. **Run GEPA optimization** — Calls `dspy.GEPA(metric=skill_fitness_metric, max_steps=N)`,
   falls back to `dspy.MIPROv2` if GEPA is unavailable. The optimizer mutates the skill text
   across iterations, evaluating each variant against the fitness metric.

6. **Extract evolved skill text** — Reads `optimized_module.skill_text` to get the mutated
   skill body.

7. **Validate evolved skill** — Runs all constraints on the evolved variant INCLUDING growth
   check against baseline. If constraints fail, saves as `evolved_FAILED.md` and aborts.

8. **Evaluate on holdout set** — Scores both baseline and evolved modules on held-out examples
   that were never seen during optimization.

9. **Report results** — Rich table comparing baseline vs. evolved scores, sizes, timing.

10. **Save output** — Writes evolved skill, baseline, and metrics JSON to timestamped output
    directory.

### 3.2 What GEPA Actually Does Under the Hood

GEPA (Genetic-Pareto Prompt Evolution, ICLR 2026 Oral) works differently from traditional
evolutionary search:

- **Trace-aware mutations**: GEPA reads full execution traces (reasoning steps, tool calls,
  tool outputs) to understand *why* things failed, then proposes targeted text mutations.
  This is fundamentally different from random perturbation.

- **Pareto-frontier exploration**: Instead of optimizing a single scalar, GEPA maintains a
  Pareto frontier of candidate prompts across multiple objectives. It combines complementary
  lessons from different frontier members.

- **Reflective analysis**: Each iteration includes a reflection step where the LLM analyzes
  what worked and what didn't, proposing specific edits rather than blind mutations.

- **Few training examples needed**: Works with as few as 3 training examples (demonstrated
  in the Phase 1 validation).

Performance claims: outperforms GRPO by +6% avg (up to +20%) with 35x fewer rollouts,
outperforms MIPROv2 by +10% (e.g., +12% on AIME-2025).

### 3.3 Loop Frequency and Triggering

Currently: **manual only**. The repo has no automation, no cron, no CI triggers.
Phase 5 (planned) would add continuous monitoring that detects regressions and auto-triggers
optimization runs, but this is entirely unimplemented.

---

## 4. Retrieval/Memory Strategy

### 4.1 Short Answer: There Is No Memory System

This is a critical finding. The hermes-agent-self-evolution repo has **zero** memory,
retrieval, or knowledge persistence infrastructure. Specifically:

- No vector database (no ChromaDB, no FAISS, no embeddings)
- No episodic memory of past evolution runs
- No knowledge graph or relational storage
- No session history or conversation memory
- No caching of evaluation results across runs
- No learning from past optimization successes/failures

### 4.2 What It Does Have (Data Persistence)

The system saves artifacts to disk:
- `output/<skill_name>/<timestamp>/evolved_skill.md` — The evolved variant
- `output/<skill_name>/<timestamp>/baseline_skill.md` — Original for comparison
- `output/<skill_name>/<timestamp>/metrics.json` — Scores, timings, config
- `datasets/skills/<name>/train.jsonl, val.jsonl, holdout.jsonl` — Eval datasets

But there is no mechanism to:
- Query past evolution runs ("what worked before for similar skills?")
- Accumulate knowledge across multiple evolution cycles
- Learn from evaluation failures to improve future mutations
- Build a corpus of successful mutation patterns

### 4.3 Eval Dataset Sources

Three planned sources (only 2 implemented):

1. **Synthetic generation** (IMPLEMENTED): LLM reads the artifact text and generates
   (task_input, expected_behavior) pairs using `dspy.ChainOfThought`. The LLM is asked
   to produce diverse test cases with difficulty levels and categories.

2. **Golden datasets** (IMPLEMENTED): Hand-curated JSONL files with known-good test cases.
   `GoldenDatasetLoader` handles single-file or pre-split datasets.

3. **SessionDB mining** (PLANNED, NOT IMPLEMENTED): Would extract real usage patterns from
   Hermes Agent's conversation logs and score them with LLM-as-judge. This is listed in the
   data sources but no code exists.

---

## 5. Task Generation

### 5.1 How Eval Tasks Are Generated

The `SyntheticDatasetBuilder` uses a DSPy Signature called `GenerateTestCases`:

```python
class GenerateTestCases(dspy.Signature):
    artifact_text: str = dspy.InputField()   # Full skill/tool text
    artifact_type: str = dspy.InputField()   # "skill", "tool_description", "prompt_section"
    num_cases: int = dspy.InputField()       # How many to generate
    test_cases: str = dspy.OutputField()     # JSON array of test cases
```

Each generated test case has:
- `task_input`: A realistic user request
- `expected_behavior`: A rubric describing what a good response should contain
- `difficulty`: easy/medium/hard
- `category`: What aspect of the skill is being tested

The generator uses `config.judge_model` (defaults to gpt-4.1) for generation.

### 5.2 Dataset Splitting

Generated examples are shuffled and split by ratio:
- 50% train (used by optimizer)
- 25% validation (used during optimization for early stopping)
- 25% holdout (used only for final evaluation)

Default size: 20 examples total (configurable).

### 5.3 No Self-Directed Task Generation

Importantly, the system does not generate improvement *tasks* for itself. It does not
decide "I should improve the github-code-review skill next" or "tool descriptions need
work." All evolution targets are manually specified via CLI (`--skill arxiv`). Phase 5
would add performance monitoring to identify weak areas, but this is unimplemented.

---

## 6. Eval/Selection Criteria

### 6.1 Fitness Functions (Two Tiers)

**Tier 1 — Heuristic (fast, used during optimization)**:
```python
def skill_fitness_metric(example, prediction, trace=None) -> float:
    # Base 0.5 for non-empty output
    # + keyword overlap between expected_behavior and agent_output
    score = 0.3 + 0.7 * (|expected_words & output_words| / |expected_words|)
```
This is intentionally crude — a fast proxy for semantic similarity that avoids expensive
LLM calls during the inner optimization loop.

**Tier 2 — LLM-as-Judge (expensive, for final evaluation)**:
Multi-dimensional scoring via `LLMJudge`:
- `correctness` (0-1, weight 0.5): Did the response correctly address the task?
- `procedure_following` (0-1, weight 0.3): Did it follow the expected procedure?
- `conciseness` (0-1, weight 0.2): Appropriately concise?
- `length_penalty` (0-0.3): Ramps from 0 at 90% of max size to 0.3 at 100%+
- `feedback`: Textual feedback for GEPA's reflective analysis

Composite = 0.5 * correctness + 0.3 * procedure_following + 0.2 * conciseness - length_penalty

### 6.2 Constraint Gates (Hard Rejection)

Five mandatory constraints — ANY failure means immediate rejection:

1. **Size limit**: Skills <= 15KB, tool descriptions <= 500 chars, param descriptions <= 200 chars
2. **Growth limit**: Max +20% over baseline size
3. **Non-empty**: Artifact must have non-whitespace content
4. **Structural integrity** (skills only): Valid YAML frontmatter with `name:` and `description:`
5. **Test suite** (optional, `--run-tests`): Full pytest must pass 100% (2550+ tests in hermes-agent)

### 6.3 Selection Strategy

The selection is entirely delegated to DSPy's optimizer:
- **GEPA**: Maintains a Pareto frontier, selects based on multi-objective dominance
- **MIPROv2**: Instruction optimization with meta-prompt tuning
- **BootstrapFewShot** (fallback): Selects best execution traces as few-shot demos

After optimization, the system does a final holdout evaluation comparing baseline vs.
evolved scores. However, there is no automatic deployment — the evolved skill is saved
to disk for human review.

---

## 7. What Is Genuinely Novel

### 7.1 The DSPy-as-Optimization-Substrate Pattern
Wrapping a text artifact (SKILL.md) as a DSPy Module where the text content becomes the
optimizable parameter is elegant. DSPy's optimizer ecosystem (GEPA, MIPROv2, BootstrapFewShot)
becomes available for free. This is the key architectural insight.

### 7.2 Separation of Concerns
The evolution system lives in a separate repo and never modifies the target codebase directly.
All changes flow through git branches and PRs. This is good engineering for safety-critical
self-modification.

### 7.3 Constraint-Gated Evolution
Hard constraints (size, growth, structure, test suite) act as non-negotiable gates before
any variant can be considered. This prevents degradation.

### 7.4 Multi-Source Eval Datasets
The design for synthetic + golden + SessionDB eval sources is sound, even if only 2/3 are
implemented. The rubric-based expected behavior (not exact text matching) is the right
approach for evaluating text generation.

---

## 8. What Is Hype or Scaffolding

### 8.1 Extreme Early Stage
The repo has 5 commits, all from the same day (2026-03-09). Only Phase 1 is implemented.
4 of 5 planned packages are empty placeholders. The "continuous improvement loop" (Phase 5)
is entirely vaporware.

### 8.2 Keyword Overlap as "Fitness"
The actual fitness function used during optimization is crude keyword overlap:
`score = 0.3 + 0.7 * (word intersection / expected words)`. The LLM-as-Judge is defined
but appears to not be used in the main optimization loop (only for offline analysis).
This means the optimizer is guided by a very weak signal.

### 8.3 No Memory = No Compounding
Without persistent memory of what worked/failed across runs, each evolution run starts
from scratch. There is no compounding of knowledge, no transfer learning between skills,
no accumulation of successful mutation patterns.

### 8.4 The Report Generator Is Bigger Than the Evolution Code
`generate_report.py` (24.5KB ReportLab PDF builder) is nearly as large as the entire
evolution logic combined. This suggests the project prioritized presentation over substance.

### 8.5 GEPA Integration Is Fragile
The code has a try/except that falls back to MIPROv2 if GEPA is not available in the
installed DSPy version. GEPA requires DSPy >= 3.0 which may not be widely available yet.

### 8.6 No Automation
Everything is manual CLI invocation. No cron, no CI/CD integration, no webhooks, no
scheduled runs. For a system named "self-evolution," there is no autonomous loop.

---

## 9. Comparison to Clarvis Architecture

| Capability | Hermes Self-Evolution | Clarvis |
|------------|----------------------|---------|
| **Memory** | None (filesystem only) | ChromaDB 10 collections, 2200+ memories, 85k+ graph edges |
| **Retrieval** | None | ONNX MiniLM embeddings, semantic search, Hebbian learning |
| **Evolution loop** | Manual CLI only | 12x/day cron_autonomous.sh + 20+ scheduled jobs |
| **Task selection** | Manual (--skill flag) | Attention-based salience scoring (attention.py) |
| **Eval pipeline** | Synthetic + keyword overlap | Performance benchmark (8 dimensions), golden QA, PI score |
| **Knowledge persistence** | metrics.json per run | Episodic memory, procedural memory, learning curves |
| **Self-awareness** | None | self_model.py (7 domains), phi_metric.py, confidence tracking |
| **Constraint gates** | 5 validators | Health monitor, watchdog, budget alerts, test suite |
| **Optimization engine** | DSPy GEPA/MIPROv2 | Queue-based (QUEUE.md) + heartbeat pipeline |
| **Autonomy** | Zero | Full autonomous operation via cron + heartbeat |

---

## 10. Adoptable Patterns for Clarvis

### Pattern 1: DSPy-Wrapped Skill Evolution (HIGH VALUE)

**What**: Wrap Clarvis skill files (SKILL.md) as DSPy modules and use GEPA to evolve them.

**Why valuable**: Clarvis has 15 OpenClaw skills that are currently static text. GEPA can
evolve these using Clarvis's own usage data as eval signal, potentially improving skill
quality without manual rewriting.

**Implementation notes**:
- Install `dspy >= 3.0` on the NUC
- Create `scripts/evolve_skill.py` that:
  1. Loads a SKILL.md from `workspace/skills/<name>/SKILL.md`
  2. Generates eval dataset from episodic memory (not synthetic — Clarvis has real episodes)
  3. Wraps as SkillModule, runs GEPA with `--iterations 5` (keep short for cost)
  4. Validates constraints (size, structure, test pass)
  5. If improved, writes to QUEUE.md for human review
- Trigger: Weekly cron slot (e.g., Sunday autonomous) or when skill usage drops
- Cost estimate: $2-5 per skill per run at OpenRouter rates
- **Key advantage over Hermes approach**: Clarvis can mine episodic memory for real
  eval data instead of synthetic generation, giving much stronger fitness signal

### Pattern 2: Constraint-Gated Self-Modification (HIGH VALUE)

**What**: Formalize hard constraints that any self-modification must pass before acceptance.

**Why valuable**: Clarvis already does self-modification (scripts modify other scripts,
queue items get implemented autonomously) but lacks formalized constraint gates.

**Implementation notes**:
- Create `scripts/evolution_constraints.py` with validators:
  1. Size growth limit (max +20% per modification)
  2. Test suite must pass (existing pytest tests)
  3. Health monitor must pass after change
  4. Brain health check (store/recall) must pass
  5. Performance benchmark must not regress beyond threshold
- Integrate into `heartbeat_postflight.py` — after any code modification task, run
  constraint validation before marking the task as successful
- Add to `pr_factory.py` — validate constraints before creating PR

### Pattern 3: Rubric-Based Fitness Scoring (MEDIUM VALUE)

**What**: Use LLM-as-judge with multi-dimensional rubrics to evaluate task outputs.

**Why valuable**: Clarvis's current confidence scoring (`clarvis_confidence.py`) is
single-dimensional. The multi-dimensional rubric approach (correctness, procedure-following,
conciseness) provides richer signal for learning what works.

**Implementation notes**:
- Extend `heartbeat_postflight.py` to score task outputs on 3 dimensions:
  1. `goal_achievement` (0-1): Did the task achieve its stated goal?
  2. `procedure_quality` (0-1): Was the approach sound and well-structured?
  3. `efficiency` (0-1): Was it done without unnecessary steps/cost?
- Store as structured metadata in episodic memory
- Use composite score for Hebbian weight updates (replace simple pass/fail)
- Feed rubric scores back to attention.py for better task selection

### Pattern 4: Synthetic Dataset Generation for Self-Testing (MEDIUM VALUE)

**What**: Use an LLM to generate test cases for Clarvis's own capabilities.

**Why valuable**: Clarvis has `golden_qa.json` for project agents but not for its own
brain retrieval quality. Synthetic generation could create regression test suites for
skills, procedures, and brain retrieval.

**Implementation notes**:
- Create `scripts/generate_self_tests.py` that:
  1. Reads each SKILL.md and generates 5-10 realistic test inputs with expected behaviors
  2. Saves as `data/self_tests/<skill_name>.jsonl`
  3. Can be run periodically to detect skill degradation
- Integrate with `retrieval_quality.py` to generate retrieval test queries from stored
  memories (synthetic golden QA for brain search)
- Cost: ~$0.50 per skill using gpt-4.1-mini

### Pattern 5: Artifact Versioning with Baseline Comparison (LOW-MEDIUM VALUE)

**What**: Always save baseline + evolved + metrics when modifying text artifacts.

**Why valuable**: Clarvis currently modifies files in-place during autonomous evolution.
Saving before/after with metrics enables rollback and trend analysis.

**Implementation notes**:
- In `heartbeat_postflight.py`, when the task involved modifying a script or skill:
  1. Git diff the changes
  2. Save diff + metrics to `data/evolution_history/<date>/<task_id>.json`
  3. Track improvement/regression over time
- Already partially done via git commits, but structured metrics are missing

### Pattern 6: Execution Trace-Aware Mutation (HIGH VALUE, HARD TO IMPLEMENT)

**What**: GEPA's core insight — reading full execution traces to understand *why* things
failed, then proposing targeted mutations rather than blind changes.

**Why valuable**: Clarvis's current evolution loop (queue_writer identifies tasks,
cron_autonomous executes them) does not systematically analyze *why* previous attempts
failed. Adding trace analysis would make evolution more directed.

**Implementation notes**:
- Extend episodic memory to store full execution traces (not just outcomes)
- In `cron_evolution.sh`, when analyzing past failures:
  1. Retrieve episodes where tasks failed or underperformed
  2. Extract the execution trace (what was tried, what went wrong)
  3. Use LLM to analyze patterns across multiple failure traces
  4. Generate targeted improvement tasks based on failure analysis
- This is the hardest pattern to implement but has the highest potential ROI

---

## 11. Patterns to AVOID Adopting

### Anti-Pattern 1: Keyword Overlap as Fitness
The `skill_fitness_metric` using word intersection is too crude for meaningful optimization.
Clarvis should use either full LLM-as-judge scoring or semantic similarity (which it already
has via ONNX embeddings) rather than keyword counting.

### Anti-Pattern 2: No-Memory Evolution
Running each optimization from scratch without learning from past runs is wasteful. Clarvis
already has the memory infrastructure to avoid this — always store what worked/failed and
query it before starting new evolution cycles.

### Anti-Pattern 3: Synthetic-Only Eval Data
Generating test cases purely from LLM imagination produces weaker signal than using real
usage data. Clarvis has 2200+ memories and episodic history — mine those for eval datasets.

### Anti-Pattern 4: Manual-Only Triggering
A "self-evolution" system that requires manual CLI invocation is not self-evolving. Clarvis's
cron-based autonomous loop is already superior to this approach.

---

## 12. Key Takeaways

1. **The DSPy wrapping pattern is the most reusable idea**. Turning text artifacts into
   optimizable DSPy parameters and leveraging GEPA's trace-aware evolution is genuinely
   powerful. This is worth implementing for Clarvis skills.

2. **Constraint gates are essential for safe self-modification**. The 5 validators in
   `constraints.py` are simple but effective. Clarvis should formalize similar gates.

3. **The repo is 90% scaffolding, 10% substance**. Only Phase 1 works, and even that uses
   a crude fitness function. The detailed PLAN.md (40KB) dwarfs the actual code.

4. **Clarvis is architecturally ahead in every dimension except the DSPy optimization
   substrate**. Memory, retrieval, autonomy, self-awareness, task selection — Clarvis has
   all of these. What Clarvis lacks is a principled prompt/skill optimization engine,
   which GEPA could provide.

5. **The estimated cost is reasonable**. At $2-10 per optimization run, running GEPA on
   Clarvis's 15 skills weekly would cost $30-150/month, well within typical API budgets.

6. **Phase 5 (continuous loop) is the only truly interesting unimplemented part**. If
   implemented, it would monitor performance, detect regressions, auto-triage weak areas,
   and schedule optimization runs. This is exactly what Clarvis already does with its
   heartbeat + cron architecture.

---

## Sources

- Repository: https://github.com/NousResearch/hermes-agent-self-evolution
- GEPA paper: https://arxiv.org/abs/2507.19457 (ICLR 2026 Oral)
- GEPA in DSPy: https://dspy.ai/api/optimizers/GEPA/overview/
- Darwinian Evolver: https://github.com/imbue-ai/darwinian_evolver
- Imbue research post: https://imbue.com/research/2026-02-27-darwinian-evolver/
- Darwin Godel Machine: https://arxiv.org/abs/2505.22954
