# LLM-Based Code Generation Agent Survey

**Paper**: arXiv:2508.00083 (Dong et al., July 2025, revised Sep 2025)
**Title**: A Survey on Code Generation with LLM-based Agents
**Scope**: 447 papers (2022-2025), distilled to 100 core references across ICSE/ASE/FSE/ISSTA/ACL/ICML/ICLR/AAAI
**Date Ingested**: 2026-03-13

## Core Taxonomy

### Three Defining Features of Code Generation Agents
1. **Autonomy**: Independent workflow management from task decomposition to debugging
2. **Expanded Scope**: Full SDLC coverage, not just code snippets
3. **Engineering Practicality**: System reliability, process management, tool integration

### Single-Agent Techniques
- **Planning & Reasoning**: Self-Planning, CodeChain, GIF-MCTS, PlanSearch, CodeTree, DARS
- **Tool Integration & RAG**: CodeAgent (5 tools), ToolGen, RepoHyper, CodeNav, cAST
- **Reflection & Self-Improvement**: Self-Refine, Self-Debug, Self-Edit, ROCODE

### Multi-Agent Workflow Patterns (4 types)
1. **Pipeline Labor Division**: Sequential stages with handoffs (Self-Collaboration, AgentCoder)
2. **Hierarchical Planning-Execution**: Senior agents decompose, subordinates implement (PairCoder, FlowGen)
3. **Self-Negotiation Circular Optimization**: Iterative evaluate-refine loops (MapCoder, CodeCoR, AutoSafeCoder)
4. **Self-Evolving Structural Updates**: Dynamic workflow reorganization (SEW, EvoMAC)

## Key Findings

### Planning: Multi-Path > Linear
- MCTS/tree-structured approaches consistently outperform linear Self-Planning
- GIF-MCTS: Monte Carlo Tree Search with execution feedback scoring
- PlanSearch: Explicit search over candidate plans with parallel evaluation
- DARS: 47% Pass@1 on SWE-Bench Lite (best reported)
- CodeAct: All actions as executable Python code with interpreter feedback

### Self-Repair Mechanisms
- **Self-Refine**: Generate → self-evaluate → revise (no training, strong generality)
- **Self-Debug**: Rubber-duck debugging via line-by-line explanation
- **ROCODE**: Closed-loop error detection + adaptive backtracking + static analysis for minimal modifications
- PyCapsule pattern: Exponential decay caps (max 3-5 debug iterations, R²≈1.0)

### Multi-Agent Coordination
- **Blackboard model**: Shared memory for flexible inter-agent communication (vs unidirectional messaging)
- **L2MAC**: Von Neumann architecture with decoupled instruction registers and file storage
- **SyncMind**: 3-dimension evaluation addressing out-of-sync states in shared codebases
- **CANDOR**: Group discussion generating consensus through coordinator planners + reviewers

### Context Management
- **Cogito**: 3-stage cognition-memory-growth (short-term, long-term KB, evolutionary growth units)
- **SoA**: Self-organizing agents scaling count by task complexity
- **Knowledge graph retrieval**: 10% improvement in project-level generation

### Benchmark Results Summary
| Benchmark | Best Agent | Score |
|-----------|-----------|-------|
| SWE-Bench Lite | DARS | 47% Pass@1 |
| HumanEval | MapCoder | 93.9% |
| GitHub Issues | MAGIS | 13.94% resolution |
| Defects4J | RepairAgent | 164 automatic repairs |
| SecurityEval | AutoSafeCoder | 13% vulnerability reduction |

## SDLC Coverage Map

| Phase | Key Agents | Technique |
|-------|-----------|-----------|
| Requirements | ClarifyGPT, TiCoder, InterAgent | Ambiguity detection, clarification generation |
| Planning | Self-Planning, PlanSearch, CodeTree | Multi-path exploration, hierarchical decomposition |
| Implementation | ChatDev, MetaGPT, AgileCoder | Role-based multi-agent, agile simulation |
| Testing | QualityFlow, TestPilot, CANDOR | Test generation → compliance imagination → execution |
| Debugging | Self-Refine, RepairAgent, SWE-Agent | Iterative repair, GitHub issue resolution |
| Optimization | MARCO, AIDE, LASSI-EE | Multi-round diagnosis-optimization cycles |

## Clarvis Gap Analysis (vs Survey Taxonomy)

### What Clarvis Has (mapped to survey)
- **Pipeline pattern**: Heartbeat = preflight→execute→postflight (Pipeline Labor Division)
- **Code validation**: PyCapsule-inspired deterministic pre-processing in `code_validation.py`
- **Multi-dimensional quality scoring**: `quality.py` with task/code/semantic/efficiency dimensions
- **Tiered memory**: Cognitive workspace (Active/Working/Dormant buffers) ≈ Cogito's 3-stage model
- **Tool extraction**: tool_maker.py ≈ ToolGen pattern (but without execution validation)

### What Clarvis Lacks (highest-impact gaps)
1. **Multi-path planning**: Heartbeat uses linear planning. Adding PlanSearch (generate k candidate plans, evaluate in parallel, pick best) would directly improve Code Generation Quality (0.655→0.75)
2. **Self-Refine loop**: No structured self-repair step between execution and postflight. Adding generate→self-evaluate→revise before postflight recording would catch errors iteratively
3. **Circular optimization**: No self-negotiation pattern. CodeCoR's reflection agents between stages (score/locate problems, feed back to preceding stage) is missing
4. **Requirements disambiguation**: QUEUE tasks lack structured ambiguity detection. TiCoder pattern: generate clarification tests before implementation
5. **Pre-execution test generation**: QualityFlow generates tests → imagines compliance → then executes. Clarvis generates code without pre-generating validation criteria

### Cross-Reference with Prior Research
- **SICA** (arXiv:2504.15228): Archive-based selection aligns with survey's "Self-Evolving Structural Updates" pattern. SICA's utility function (benchmark+cost+time) is a concrete implementation
- **AgentEvolver** (arXiv:2511.10395): Self-Questioning maps to survey's "Curiosity-Driven" exploration; Self-Navigating maps to "Retrieval Enhancement" with structured experience
- **SAGE** (arXiv:2512.17102): Skill library maps to survey's "Tool Integration" + sequential rollout ≈ Pipeline pattern with compounding skill accumulation
- **PyCapsule** (arXiv:2502.02928): Deterministic pre-processing is already implemented in Clarvis code_validation.py; debug caps + plan-derived debugging match survey patterns
- **AgentDebug** (arXiv:2509.25370): Root-cause tracing and counterfactual analysis not covered in this survey but complement it — the survey focuses on what patterns exist, AgentDebug on why they fail

## Concrete Improvement Proposals for Code Generation Quality

### P1: Multi-Path Planning in Heartbeat (Impact: HIGH)
Modify `heartbeat_preflight.py` to generate 2-3 candidate task approaches (plans), score each via lightweight heuristic (feasibility, scope, tool availability), select highest-scoring plan. This replaces linear single-plan approach.

### P2: Self-Refine Loop Post-Execution (Impact: HIGH)
After Claude Code executes a task, before postflight, add a validation step: (1) check if output compiles/parses, (2) if validation fails, generate self-evaluation text, (3) re-execute with evaluation context (max 2 iterations with exponential decay cap).

### P3: Pre-Execution Test Specification (Impact: MEDIUM)
Before code generation, generate 3-5 test assertions describing expected behavior (TiCoder/QualityFlow pattern). Pass these to the code generation prompt. Validate output against tests post-execution.

### P4: Circular Optimization via Reflection (Impact: MEDIUM)
Add a lightweight reflection step in postflight that scores the output across 3 dimensions (correctness, completeness, code quality) and, if below threshold, queues a refinement task for the next heartbeat cycle.

## Open Problems (from survey)
- Agent adaptation to private codebases with custom build processes and internal APIs
- Cost efficiency of multi-agent systems vs single-agent
- Cross-paradigm flexibility (waterfall, TDD, agile, Scrum)
- Comprehensive benchmarks covering full SDLC (not just function-level)
- Trust and verification mechanisms for generated code
