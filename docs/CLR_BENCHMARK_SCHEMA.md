# CLR-Benchmark Public Schema v1.0

> Open schema for memory-enabled agent evaluation tasks and results.

CLR-Benchmark evaluates how well an agent remembers, retrieves, and reasons over accumulated knowledge. This schema defines the canonical format for **tasks** (what to evaluate) and **results** (what happened), enabling reproducible benchmarks across different agent systems.

---

## Task Schema

Each task is a single evaluation item — a question or instruction that tests a specific memory ability.

```jsonc
{
  // ── Identity ──
  "task_id": "lme-TR-042",               // Unique identifier (prefix with benchmark source)
  "benchmark": "longmemeval",            // Source benchmark: longmemeval | membench | beam | clarvis
  "version": "1.0",                      // Schema version

  // ── Classification ──
  "domain": "personal",                  // Domain: personal | professional | factual | procedural | mixed
  "ability_tags": [                      // What memory abilities this tests (from taxonomy below)
    "temporal_reasoning",
    "multi_session_reasoning"
  ],
  "difficulty": "medium",                // easy | medium | hard (optional, benchmark-specific)

  // ── Scenario ──
  "context_length": 12,                  // Number of prior sessions/messages/documents in context
  "scenario": "User mentioned moving to Berlin in session 3, then to Tokyo in session 9. Q: Where does the user currently live?",
  "query": "Where does the user currently live?",

  // ── Gold Standard ──
  "gold_answer": "Tokyo",                // Expected correct answer
  "gold_evidence": [                     // Evidence spans that support the answer
    {"session": 9, "text": "I just moved to Tokyo last month."}
  ],
  "abstention_expected": false,          // Should the agent refuse to answer?

  // ── Metadata ──
  "source_file": "longmemeval/tasks/TR/042.json",  // Optional: origin file
  "tags": ["location", "update"],        // Optional: free-form tags for filtering
  "created": "2026-03-24"
}
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | string | Unique task identifier |
| `benchmark` | string | Source benchmark name |
| `domain` | string | Knowledge domain |
| `ability_tags` | string[] | Memory abilities tested (see taxonomy) |
| `context_length` | int | Number of context items (sessions, documents, messages) |
| `scenario` | string | Full task description including context summary |
| `query` | string | The specific question or instruction |
| `gold_answer` | string | Expected correct answer |
| `gold_evidence` | object[] | Supporting evidence spans |
| `abstention_expected` | bool | Whether abstention is the correct response |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `version` | string | Schema version (default: "1.0") |
| `difficulty` | string | Task difficulty level |
| `source_file` | string | Origin file path within benchmark dataset |
| `tags` | string[] | Free-form tags for filtering and analysis |
| `created` | string | ISO date when the task was created |

---

## Result Schema

Each result records what happened when an agent attempted a task.

```jsonc
{
  // ── Identity ──
  "task_id": "lme-TR-042",               // Must match a task_id
  "run_id": "run-20260324-001",          // Unique run identifier
  "agent": "clarvis",                    // Agent system name
  "agent_version": "0.9.2",             // Agent version or commit SHA
  "timestamp": "2026-03-24T14:30:00Z",  // ISO 8601 UTC

  // ── Scores ──
  "answer_score": 1.0,                  // 0.0-1.0: correctness of the answer
  "abstention_score": 1.0,              // 0.0-1.0: correctness of abstention decision
  "evidence_score": 0.85,               // 0.0-1.0: quality of retrieved evidence

  // ── Performance ──
  "latency_ms": 2340,                   // End-to-end latency in milliseconds
  "token_cost": 1842,                   // Total tokens consumed (input + output)
  "retrieval_count": 5,                 // Number of memory retrievals performed

  // ── Agent Output ──
  "answer": "Tokyo",                    // The agent's answer
  "retrieved_evidence": [               // What the agent actually retrieved
    {"source": "clarvis-context", "text": "User moved to Tokyo last month", "score": 0.91}
  ],

  // ── Diagnostics ──
  "diagnostics": {
    "failure_stage": null,              // null if success, else: retrieval | evidence_quality | reasoning | answer
    "retrieval_hit": true,              // Did retrieval find relevant evidence?
    "evidence_sufficient": true,        // Was retrieved evidence sufficient for correct answer?
    "reasoning_correct": true,          // Did the agent reason correctly over evidence?
    "notes": ""                         // Free-form diagnostic notes
  },

  // ── Retrieval Mode ──
  "retrieval_mode": "full-history"      // full-history | oracle | no-retrieval
}
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | string | References the task being evaluated |
| `run_id` | string | Unique identifier for this evaluation run |
| `agent` | string | Name of the agent system |
| `timestamp` | string | ISO 8601 UTC timestamp |
| `answer_score` | float | Answer correctness (0.0-1.0) |
| `abstention_score` | float | Abstention correctness (0.0-1.0) |
| `latency_ms` | int | End-to-end latency in milliseconds |
| `retrieval_count` | int | Number of retrievals performed |
| `answer` | string | The agent's response |
| `diagnostics` | object | Stage-separated failure diagnostics |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `agent_version` | string | Agent version or commit SHA |
| `evidence_score` | float | Quality of retrieved evidence (0.0-1.0) |
| `token_cost` | int | Total tokens consumed |
| `retrieved_evidence` | object[] | What the agent retrieved |
| `retrieval_mode` | string | Retrieval mode used |
| `diagnostics.notes` | string | Free-form diagnostic notes |

---

## Ability Taxonomy

Standardized ability tags used across all benchmarks.

### Core Retrieval

| Ability | Description | Benchmarks |
|---------|-------------|------------|
| `information_extraction` | Retrieve explicitly stated facts | LongMemEval (IE), MemBench |
| `multi_session_reasoning` | Combine info across sessions | LongMemEval (MR) |
| `knowledge_update` | Handle updated/overwritten facts | LongMemEval (KU) |
| `temporal_reasoning` | Reason about time and event order | LongMemEval (TR) |
| `abstention` | Refuse when info is unavailable | LongMemEval (ABS) |

### Reflective

| Ability | Description | Benchmarks |
|---------|-------------|------------|
| `reflective_memory` | Infer preferences from interactions | MemBench |
| `observation_factual` | Store facts from observed data | MemBench |
| `observation_reflective` | Infer patterns from observed data | MemBench |

### Advanced (New — v1.1)

| Ability | Description | Benchmarks |
|---------|-------------|------------|
| `contradiction_resolution` | Detect and resolve conflicting facts | BEAM |
| `event_ordering` | Reconstruct correct temporal sequence | BEAM |
| `persistent_instruction` | Follow instructions across sessions | BEAM |

---

## Failure Stage Diagnostics

Every result includes a `diagnostics` object that identifies *where* a failure occurred in the retrieval-to-answer pipeline:

```
retrieval → evidence_quality → reasoning → answer
```

| Stage | Failure Meaning |
|-------|----------------|
| `retrieval` | Agent failed to retrieve any relevant evidence |
| `evidence_quality` | Retrieved evidence was insufficient or noisy |
| `reasoning` | Evidence was sufficient but reasoning was incorrect |
| `answer` | Reasoning was correct but answer formatting was wrong |
| `null` | No failure (task succeeded) |

This decomposition enables targeted improvement: if most failures are at `retrieval`, improve the memory system; if at `reasoning`, improve the LLM prompt or chain-of-thought.

---

## Aggregate Report Schema

A run-level aggregate produced by `CLR-Benchmark`:

```jsonc
{
  "benchmark": "clr-benchmark",
  "version": "1.0",
  "timestamp": "2026-03-24T14:30:00Z",
  "mode": "full-history",                    // full-history | oracle
  "total_tasks": 45,
  "abilities_evaluated": 8,
  "abilities_total": 11,
  "aggregate_effectiveness": 0.756,          // Weighted average across abilities
  "aggregate_precision_at_1": 0.689,         // Top-1 retrieval precision
  "by_ability": {                            // Per-ability breakdown
    "information_extraction": {
      "label": "Information Extraction",
      "effectiveness": 0.850,
      "precision_at_1": 0.800,
      "n": 12,
      "source_count": 2,
      "sources": ["longmemeval", "membench"]
    }
    // ... one entry per evaluated ability
  },
  "stage_diagnostics": {                     // Aggregate failure stages
    "n": 45,
    "retrieval_rate": 0.889,
    "evidence_quality_avg": 0.756,
    "answer_rate": 0.756,
    "by_stage": {
      "retrieval": 5,
      "evidence_quality": 3,
      "reasoning": 2,
      "answer": 1
    }
  },
  "adapter_reports": {                       // Per-adapter raw results
    "longmemeval": { "effectiveness": 0.800, "precision_at_1": 0.750, "total_tasks": 25 },
    "membench": { "effectiveness": 0.700, "precision_at_1": 0.620, "total_tasks": 20 }
  }
}
```

---

## File Conventions

| Path | Contents |
|------|----------|
| `data/benchmarks/tasks/<benchmark>/*.json` | Task files (one per task or batched) |
| `data/benchmarks/results/<run_id>.jsonl` | Result records (one JSON per line) |
| `data/benchmarks/clr_benchmark_latest.json` | Latest aggregate report |
| `data/benchmarks/clr_benchmark_history.jsonl` | Historical aggregate summaries |

---

## Extending the Schema

To add a new benchmark source:

1. Create an **adapter** in `clarvis/metrics/` that reads the benchmark's native format
2. Map its abilities to the taxonomy (add new abilities if needed, with `v1.x` tag)
3. Output results conforming to the Result Schema above
4. Register the adapter in `clr_benchmark.py:compute_clr_benchmark()`

To add a new ability:

1. Add it to `ABILITY_TAXONOMY` in `clr_benchmark.py` with label, description, and sources
2. Add the mapping in the relevant adapter's `_map_*_to_abilities()` function
3. Document it in this schema under the appropriate category

---

*Schema version 1.0 — 2026-03-24*
