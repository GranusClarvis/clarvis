# Research Memo — LongMemEval, MemBench, BEAM, and CLR v2

**Date:** 2026-03-22
**Purpose:** Evaluate three external long-term memory benchmarks (LongMemEval, MemBench, BEAM) for applicability to Clarvis; identify design changes needed to evolve CLR from an internal health/composite metric into a sound, open-sourceable benchmark framework.

---

## Executive Summary

All three benchmarks are useful, but in different ways:

- **LongMemEval** is the best immediate fit for Clarvis. It targets persistent chat-assistant memory over long multi-session histories and directly measures abilities we care about now: information extraction, multi-session reasoning, temporal reasoning, knowledge updates, and abstention.
- **MemBench** broadens evaluation beyond factual recall by adding **reflective memory**, **participation vs observation scenarios**, and explicit multi-metric evaluation of **effectiveness, efficiency, and capacity**. This is highly relevant for Clarvis as an agent, not merely a chatbot.
- **BEAM** is the strongest benchmark-design reference. It expands coverage to ten abilities, multiple domains, and conversation lengths up to **10M tokens**. It is the clearest signal that a publishable benchmark cannot remain narrowly personal-chat + fact-recall oriented.

### Main conclusion

**CLR in its current form is valuable internally but not yet suitable as an open benchmark.**

It should be split into:
1. **CLR-Internal** — architecture / health / operational composite for Clarvis itself
2. **CLR-Benchmark** — external-task benchmark framework with dataset adapters, shared ability taxonomy, and comparable scoring across systems

---

## Benchmark 1 — LongMemEval

**Paper:** *LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory*  
**arXiv:** 2410.10813 / ICLR 2025  
**Code/Data:** github.com/xiaowu0162/LongMemEval

### What it measures
LongMemEval evaluates five core long-term memory abilities of chat assistants:
- **Information Extraction**
- **Multi-Session Reasoning**
- **Knowledge Updates**
- **Temporal Reasoning**
- **Abstention**

### Dataset structure
- **500 evaluation questions**
- Two standard settings:
  - **LongMemEval-S**: ~115k tokens, ~40 history sessions
  - **LongMemEval-M**: ~500 sessions, roughly **1.5M tokens**
- Also provides **oracle retrieval** variant with only evidence sessions
- Each instance includes:
  - question id/type
  - answer
  - question date
  - session ids + timestamps
  - full session content
  - evidence session ids
  - turn-level `has_answer` labels for recall evaluation

### Why it matters for Clarvis
This is the closest match to Clarvis’s current product reality:
- long-running assistant memory
- multi-session user interaction
- personal/task-oriented context
- explicit update and abstention behavior

It is a direct test of whether our memory system actually helps a persistent assistant answer correctly after sustained interactions.

### Strong design ideas worth borrowing
1. **Ability-specific tasks** instead of a monolithic “memory score”
2. **Oracle retrieval split** to separate retrieval failures from reasoning/reading failures
3. **Timestamped histories** to force temporal reasoning rather than bag-of-facts lookup
4. **Scalable haystack generation** so difficulty can increase without changing task family

### Known limitations
- Primarily still a **chat-assistant** benchmark, not a full agent benchmark
- More personal-assistant domain than multi-domain reasoning benchmark
- Does not cover contradiction resolution or persistent instruction following as strongly as BEAM

### What Clarvis should do with it
- Build an adapter and run Clarvis on **LongMemEval-S** first
- Use **oracle retrieval** to isolate whether failures come from:
  - indexing
n  - retrieval
  - reading / synthesis
  - answer formatting / abstention
- Compare retrieval granularities:
  - raw sessions
  - round-level decomposition
  - extracted facts
  - graph-linked episodic slices
  - summary memories

### Source highlights
- Five abilities from paper abstract and HTML text
- 500 questions, 115k and 1.5M-token settings, oracle format, and dataset fields from project README

---

## Benchmark 2 — MemBench

**Paper:** *MemBench: Towards More Comprehensive Evaluation on the Memory of LLM-based Agents*  
**arXiv:** 2506.21605 / ACL 2025 Findings  
**Code/Data:** github.com/import-myself/Membench

### What it adds beyond earlier benchmarks
MemBench explicitly argues that prior benchmarks under-cover:
- **memory levels**
- **interactive scenarios**
- **evaluation dimensions**

It introduces:
- **Factual memory** (explicitly stated information)
- **Reflective memory** (higher-level inferred user profile / preferences / tendencies)
- **Participation scenario** (first-person agent interaction)
- **Observation scenario** (third-person observer recording user information)
- Multi-metric evaluation across:
  - **accuracy / effectiveness**
  - **recall**
  - **capacity**
  - **temporal efficiency**

### Why it matters for Clarvis
Clarvis is not just a chat assistant; it operates as an agent that:
- stores explicit facts
- builds abstracted preferences / procedures / self-knowledge
- sometimes participates directly, sometimes ingests from observation/log streams

MemBench is particularly relevant because it pressures us to evaluate **reflective** and **scenario-sensitive** memory rather than treating memory as simple fact retrieval.

### Strong design ideas worth borrowing
1. **Memory-level distinction**: factual vs reflective
2. **Scenario distinction**: participation vs observation
3. **Explicit efficiency/capacity metrics**, not just answer correctness
4. **Noise extension mechanism** to lengthen dialogues while preserving benchmark shape

### Known limitations
- More limited than BEAM in domain breadth and ability coverage
- Still relatively centered on personal/user-style memory settings
- Public README is lighter on exact evaluation detail than LongMemEval

### What Clarvis should do with it
- Build an adapter for its four data quadrants:
  - Participation-Factual
  - Participation-Reflective
  - Observation-Factual
  - Observation-Reflective
- Add reflective-memory evaluation to CLR-Benchmark:
  - can Clarvis infer preferences/tendencies from sparse evidence?
  - can it maintain that abstraction after updates/noise?
- Add scenario-aware scorecards to detect if Clarvis is strong when actively conversing but weak when passively observing logs/events

### Source highlights
- Factual vs reflective memory and participation vs observation from paper abstract/intro and HTML text
- Data quadrants and noise-extension details from project README

---

## Benchmark 3 — BEAM

**Paper:** *Beyond a Million Tokens: Benchmarking and Enhancing Long-Term Memory in LLMs*  
**arXiv:** 2510.27246  
**Code/Data:** github.com/mohammadtavakoli78/BEAM

### Why BEAM matters most strategically
BEAM is the clearest sign that a serious long-term memory benchmark must expand beyond:
- personal-life chat only
- simple recall questions
- relatively short context windows

It contributes:
- **100 conversations** and **2,000 validated questions**
- lengths at **128K, 500K, 1M, and 10M tokens**
- **multi-domain coverage** including coding, math, health, finance, personal, etc.
- **10 memory abilities**:
  - Abstention
  - Contradiction Resolution
  - Event Ordering
  - Information Extraction
  - Instruction Following
  - Knowledge Update
  - Multi-Session Reasoning
  - Preference Following
  - Summarization
  - Temporal Reasoning

### Why it matters for Clarvis
This benchmark exposes exactly the areas where internal metrics can become self-serving:
- domain narrowness
- overfitting to one memory workflow
- lack of contradiction stress tests
- lack of instruction persistence tests
- no robust long-scale degradation curves

### Strong design ideas worth borrowing
1. **Ability breadth** — especially contradiction resolution, event ordering, instruction following, summarization
2. **Length scaling curves** — not one fixed benchmark size
3. **Multi-domain scope** — coding + math + personal + general domains
4. **Automatic benchmark generation framework** — not just a frozen static set
5. **Separation of benchmark from enhancement framework** (BEAM vs LIGHT)

### Known limitations
- Potentially heavier to run than we need initially
- Less directly aligned with Clarvis’s present personal-assistant usage than LongMemEval
- Benchmark generation complexity may be overkill for immediate adoption

### What Clarvis should do with it
- Mine BEAM first as a **benchmark-design blueprint**, even before full-scale execution
- Prioritize adopting BEAM-inspired dimensions that CLR currently lacks:
  - contradiction resolution
  - event ordering
  - instruction following persistence
  - summarization / abstraction
  - cross-domain robustness
- Eventually run a **small representative subset** before attempting full-scale evaluation

### Source highlights
- 100 conversations / 2,000 questions / 128K–10M token scale from abstract and README
- 10 ability taxonomy from paper HTML and README comparison table

---

## Comparison — What each benchmark is best for

| Benchmark | Best Use for Clarvis | Main Strength | Main Weakness |
|---|---|---|---|
| LongMemEval | First external evaluation target | Closest to persistent assistant memory | Narrower ability/domain scope |
| MemBench | Agent-memory extension | Reflective memory + participation/observation + multi-metric scoring | Less broad than BEAM |
| BEAM | Benchmark-design reference and later stress test | Breadth: domains, lengths, ability taxonomy | Heavier and more complex to adopt immediately |

---

## Inspection of Current CLR

**File inspected:** `clarvis/metrics/clr.py`

### Current CLR dimensions
CLR currently combines seven weighted dimensions:
1. **Memory Quality**
2. **Retrieval Precision**
3. **Prompt/Context**
4. **Task Success**
5. **Autonomy**
6. **Efficiency**
7. **Integration Dynamics**

### What CLR currently does well
- It is **multi-dimensional**, not a vanity scalar with no decomposition
- It includes **value-add over baseline**, which is sensible
- It has **gates** for minimum quality
- It captures architecture-level strengths that ordinary task benchmarks miss

### Why CLR is not yet ready as an open benchmark
#### 1) It mixes benchmarking with system-health telemetry
Examples:
- total memory count
- graph density
- digest freshness
- autonomous log rate
- cost files
- internal section-reference heuristics

These are useful **internal operations metrics**, but they are not externally comparable memory-benchmark measures.

#### 2) It is tightly coupled to Clarvis internals
Examples:
- `clarvis.brain`
- Clarvis collections and retrieval evaluators
- Clarvis episodic and cron logs
- a baseline defined as “bare Claude Code”

This makes it unsuitable as a neutral benchmark framework for others.

#### 3) It does not cleanly separate failure stages
LongMemEval’s design suggests we should separately score:
- indexing / memory writing
- retrieval
- reasoning over retrieved evidence
- answer quality / abstention

Current CLR mostly entangles these.

#### 4) It under-covers several benchmark-critical abilities
Missing or weak relative to BEAM/MemBench:
- contradiction resolution
- event ordering
- instruction persistence
- reflective memory
- observation-mode memory
- summarization quality as memory behavior
- domain robustness curves
- length scaling curves

#### 5) Some dimensions are architecture-specific by design
For example, `integration_dynamics` is useful for Clarvis research, but it should be published as an **internal cognitive-architecture metric**, not as a universal memory benchmark dimension.

---

## Recommended CLR split

### A. CLR-Internal (keep and improve)
Purpose:
- health monitoring
- trend detection
- regression alarms
- architecture evaluation for Clarvis itself

Keep dimensions like:
- memory quality
- retrieval precision
- prompt/context quality
- task success
- autonomy
- efficiency
- integration dynamics

But label this honestly as an **internal composite score**, not a universal benchmark.

### B. CLR-Benchmark (new, open-source candidate)
Purpose:
- evaluate memory-enabled assistants/agents on external tasks
- compare across systems fairly
- provide reproducible, dataset-backed results

#### Recommended public ability taxonomy
At minimum:
1. Retrieval accuracy
2. Multi-hop / multi-session reasoning
3. Temporal reasoning
4. Knowledge update / overwrite handling
5. Abstention / uncertainty calibration
6. Reflective memory
7. Observation-mode memory
8. Contradiction resolution
9. Event ordering
10. Instruction persistence
11. Summarization / compression fidelity
12. Efficiency (latency / token cost / retrieval count)
13. Capacity / degradation curves vs context length
14. Evidence attribution / support traceability

---

## Proposed implementation architecture for CLR-Benchmark

### Layer 1 — Dataset adapters
Build adapters for:
- **LongMemEval**
- **MemBench**
- **BEAM** (subset first)

Each adapter should normalize samples into a common schema:
- `task_id`
- `benchmark`
- `domain`
- `ability_tags[]`
- `context_length`
- `scenario` (participation / observation / etc.)
- `question`
- `gold_answer`
- `gold_evidence`
- `metadata`

### Layer 2 — Runner protocol
Define a benchmark runner interface that can evaluate any memory system via a stable contract:
- `ingest(turn/session)`
- `answer(question, metadata)`
- optional `retrieve(query)` diagnostics hook

This lets Clarvis benchmark:
- raw long-context baseline
- retrieval-only pipeline
- graph-augmented memory
- summary memory
- hybrid systems

### Layer 3 — Evaluation modules
Separate scorers for:
- answer correctness
- abstention correctness
- evidence recall / precision
- latency
- token cost
- retrieval volume
- update correctness
- contradiction handling

### Layer 4 — Reports
Produce:
- overall benchmark score
- per-benchmark score
- per-ability score
- per-domain score
- per-length score
- error breakdown by stage (retrieve vs reason vs answer)

---

## Concrete design lessons to import immediately

### From LongMemEval
- Add **oracle-retrieval evaluation mode**
- Add **timestamp-aware tasks** as a first-class benchmark family
- Add **update tasks** and explicit **abstention scoring**

### From MemBench
- Add **reflective-memory** tasks
- Add **participation vs observation** split
- Add **capacity** and **temporal efficiency** as explicit outputs, not side notes

### From BEAM
- Add **contradiction resolution**
- Add **event ordering**
- Add **instruction-following persistence**
- Add **multi-domain support**
- Add **length scaling curves** rather than single fixed-size evaluation

---

## Recommended execution order

### Phase 1 — Run external reality check
1. Implement **LongMemEval adapter**
2. Run Clarvis on LongMemEval-S
3. Add oracle mode and failure-stage breakdown

### Phase 2 — Expand memory taxonomy
4. Implement **MemBench adapter**
5. Add reflective vs factual and participation vs observation score splits

### Phase 3 — Make CLR benchmarkable
6. Split CLR into **CLR-Internal** and **CLR-Benchmark**
7. Define public benchmark schema + runner interface

### Phase 4 — Stress and generalize
8. Add **BEAM subset adapter**
9. Add contradiction / event-ordering / instruction-persistence task families
10. Add length and domain robustness plots

---

## Recommended queue items

1. `CLR_SPLIT_INTERNAL_VS_BENCHMARK`
2. `LONGMEMEVAL_ADAPTER_AND_BASELINE_RUN`
3. `CLR_ORACLE_RETRIEVAL_MODE`
4. `MEMBENCH_ADAPTER_REFLECTIVE_OBSERVATION`
5. `BEAM_SUBSET_ADAPTER_AND_ABILITY_GAP_AUDIT`
6. `CLR_PUBLIC_SCHEMA_V1`
7. `CLR_FAILURE_STAGE_BREAKDOWN`
8. `CLR_CONTRADICTION_EVENT_INSTRUCTION_TASKS`
9. `CLR_EVIDENCE_ATTRIBUTION_SCORING`
10. `CLR_LENGTH_DOMAIN_ROBUSTNESS_REPORTS`

---

## Bottom line

- **LongMemEval** should be adopted first.
- **MemBench** should shape the next layer of agent-memory evaluation.
- **BEAM** should guide benchmark breadth and open-source credibility.
- **CLR should not be open-sourced in its current form as a universal benchmark.**
- The correct path is to preserve current CLR as **CLR-Internal** and build a new external-task framework as **CLR-Benchmark**.
