# Runtime Verification & Metacognitive Self-Correction for Agents

**Date**: 2026-03-07
**Queue Tag**: RESEARCH_DISCOVERY 2026-03-05
**Sources**: arxiv.org/abs/2510.14319, arxiv.org/abs/2503.18666, arxiv.org/abs/2509.23864, arxiv.org/abs/2510.26585

## Papers Reviewed

### 1. MASC — Metacognitive Self-Correction (ICLR 2026)
- **Core idea**: Step-level anomaly detection via *next-execution reconstruction*. Given interaction history, predict the embedding of the next expected step. Deviation from prototype = anomaly.
- **Prototype-Guided Enhancement**: Learns a prior over normal-step embeddings to stabilize scoring under sparse context (early steps).
- **Correction**: When anomaly flagged, a correction agent revises the acting agent's output *before* it flows downstream, breaking error cascades.
- **Results**: +8.47% AUC-ROC on step-level error detection (Who&When benchmark). Consistent end-to-end gains across diverse MAS architectures.
- **Key insight**: Treat agent steps as causally reconstructable from history — enables unsupervised, real-time error detection without labeled failure data.

### 2. AgentSpec — Runtime Constraint DSL (ICSE 2026)
- **Core idea**: Lightweight domain-specific language for declarative safety rules. Structure: `rule @id → trigger Event → check Predicate* → enforce Action+`.
- **Four enforcement types**: stop (terminate), user_inspection (human review), invoke_action (corrective), llm_self_examination (self-reflect with violation observation).
- **Integration**: Hooks into LangChain's `iter_next_step` at AgentAction/AgentStep/AgentFinish decision points. Framework-agnostic (also AutoGen, Apollo ADS).
- **Results**: >90% unsafe code prevention, 100% hazardous embodied action elimination, 100% AV compliance. Millisecond overhead (~1.4ms parse + ~2.8ms predicate eval).
- **Key insight**: Declarative rules are more robust and interpretable than model-based safeguards. Users define "what not to do" and the system enforces it at runtime.

### 3. AgentGuard — Dynamic Probabilistic Assurance (ASE 2025)
- **Core idea**: Shift from binary pass/fail verification to *probabilistic guarantees*. Question: "What is the probability of failure within given constraints?"
- **Pipeline**: Observe raw I/O → abstract into formal events → online-learn MDP model → probabilistic model checking for quantitative properties.
- **Instrumentation**: Logging-style Python API — single function call for code instrumentation. Framework-agnostic.
- **Key insight**: Agent behavior is emergent and unpredictable — model it as a stochastic process (MDP) and reason about failure probabilities rather than trying to enumerate all failure modes.

### 4. SupervisorAgent — LLM-Free Adaptive Supervision (ICLR 2026)
- **Core idea**: Heuristic-triggered supervision without altering base agent architecture. LLM-free filter detects three risk signals:
  1. **Errors** in tool use or code execution
  2. **Inefficient patterns** (repetitive actions, loops)
  3. **Excessive observation length** (bloated/noisy outputs)
- **Three interaction types**: agent-agent (hallucination propagation), agent-tool (corrupted external data), agent-memory (stale memory poisoning)
- **Interventions**: correct_observation, provide_guidance, run_verification (context-dependent selection)
- **Observation purification**: Refine noisy observations to improve signal-to-noise ratio, but balances against over-aggressive filtering that removes useful structural cues.
- **Results**: -29.68% token consumption on GAIA (Smolagent), -35% cost + -63% variance on GAIA Level 2. Only 15.45% supervisor overhead. No success rate degradation.
- **Key insight**: Most intervention decisions can be made with simple heuristics (no LLM needed for the *trigger*), saving the LLM budget for the *correction* itself.

## Clarvis Application Ideas

### Immediate (maps to existing queue tasks)

1. **ACTION_VERIFY_GATE** (queue task): Implement AgentSpec-style declarative rules in `heartbeat_preflight.py`. Before committing a task to Claude Code, evaluate it against safety predicates:
   - Extension whitelist for file modifications (maps to ORCH_AUTOCOMMIT_SAFETY)
   - Path restrictions (no /etc, no credentials, no .openclaw/agents/*/auth*)
   - Action type constraints (no destructive git ops during autonomous runs)
   - Enforcement: stop or require human inspection via Telegram

2. **Cron output monitoring** (SupervisorAgent pattern): Add heuristic filter to `heartbeat_postflight.py`:
   - Detect excessive output length (>50KB = bloated, trigger summarization)
   - Detect error patterns in Claude Code output (exception traces, permission denied)
   - Detect repetitive patterns (same action attempted 3+ times = loop)
   - Log detections to `monitoring/supervision_events.jsonl`

3. **Context relevance improvement** (weakest metric: 0.838): SupervisorAgent's observation purification directly relates — noisy/excessive context injected into preflight briefs reduces relevance. Apply signal-to-noise filtering to context_compressor.py output.

### Medium-term

4. **MASC-style step reconstruction**: For multi-step autonomous workflows, embed each step's output and compare against expected trajectory. Could improve the brief_benchmark by detecting when context briefs deviate from expected information profiles.

5. **AgentGuard MDP modeling**: Model cron execution patterns as MDP (states: idle/running/error/success, transitions: cron trigger → preflight → execute → postflight). Online-learn transition probabilities. Alert when P(error) exceeds threshold. Natural extension of existing `performance_benchmark.py`.

### Low priority

6. **Prototype library**: Build a library of "normal step prototypes" from successful autonomous runs (MASC pattern). Use for future anomaly detection without labeled failure data.

## Taxonomy of Approaches

| Approach | Detection | Correction | LLM Cost | Overhead | Best For |
|----------|-----------|------------|----------|----------|----------|
| MASC | Embedding reconstruction | Correction agent | Medium | Medium | Multi-agent error cascades |
| AgentSpec | Declarative rules | Stop/inspect/correct/reflect | Low-None | Milliseconds | Known safety constraints |
| AgentGuard | MDP model checking | Probability alerts | None | Low | Behavioral drift detection |
| SupervisorAgent | Heuristic filter | Context-dependent | Low | ~15% tokens | Efficiency + error prevention |

## Relationship to Weakest Metric (Context Relevance = 0.838)

SupervisorAgent's observation purification and AgentSpec's predicate-based filtering both directly address context relevance:
- Purification reduces noise in agent observations → cleaner context
- Predicate filtering can gate what gets included in preflight briefs
- BRIEF_BENCHMARK_REFRESH task should incorporate signal-to-noise scoring inspired by SupervisorAgent
