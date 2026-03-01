# Sleep-Cycle Memory Consolidation for LLM Agents

**Ingested**: 2026-02-28
**Sources**: arXiv 2510.18866 (LightMem), arXiv 2504.13171 (Letta Sleep-time Compute), ICLR 2026 (MemAgent)

## Key Papers

### LightMem (arXiv 2510.18866)
- **3-tier memory**: sensory (rapid filter) → short-term (topic-aware) → long-term (offline consolidation)
- **Offline sleep-time consolidation**: decouples consolidation from online inference
- **Results**: 38x token reduction, 30x fewer API calls, 7.7% QA accuracy gain on LongMemEval
- **Key insight**: topic-aware grouping before consolidation prevents information loss

### Letta Sleep-time Compute (arXiv 2504.13171)
- **Core mechanism**: `rethink_memory` function transforms raw context → learned context offline
- **Pipeline**: S(c) → c′ (sleep transforms context), then T_b(q, c′) → a (test-time with smaller budget)
- **Results**: 5x test-time compute reduction, +13% accuracy (Stateful GSM-Symbolic), +18% (AIME)
- **Key insight**: most effective when queries are predictable from context (pre-compute answers)
- **Implementation**: up to 10 rethink_memory calls per sleep cycle

### MemAgent (ICLR 2026 Oral)
- **Fixed-size memory panel** with overwrite strategy (RL-learned what to keep/discard)
- **Segmented read→write→aggregate**: O(N) complexity vs O(N²) full attention
- **Results**: 8K training → 3.5M extrapolation with <5% degradation, 95%+ on 512K RULER
- **Training**: Extended DAPO algorithm for multi-conversation RL
- **Key insight**: bounded memory forces efficient information compression

## Clarvis Implementation

### Changes Made
1. **`memory_consolidation.py`** — Added Section 7: Sleep-Cycle Episodic→Semantic Consolidation
   - `sleep_consolidate()`: clusters episodes by theme, synthesizes semantic learnings
   - Integrated as Phase 6.5 in `run_consolidation()` pipeline
   - CLI: `memory_consolidation.py sleep [--dry-run]`, `memory_consolidation.py sleep-stats`
   - Log file: `data/sleep_consolidation_log.json`
   - Idempotent: tracks consolidated episode IDs, skips on re-run

2. **`dream_engine.py`** — Added `rethink_memory()` function
   - Letta-inspired: extracts positive learned patterns from successful episodes
   - Groups by task category, synthesizes generalized capability assessments
   - CLI: `dream_engine.py rethink [n]`, `dream_engine.py sleep [n]` (dream + rethink)
   - Deduplicates against existing brain learnings before storing

### Architecture Mapping
| Research Concept | Clarvis Implementation |
|---|---|
| LightMem offline consolidation | `sleep_consolidate()` in nightly cron |
| Letta rethink_memory | `rethink_memory()` in dream engine |
| MemAgent fixed window | Last 100 episodes as working set |
| MemAgent overwrite | Dedup check prevents redundant learnings |
| Topic-aware grouping | Domain keyword extraction per episode |
| Sleep/wake separation | Runs at 02:45 (sleep slot), not during active tasks |

### Quantitative Impact
- First run: 100 episodes → 7 themes → 5 new semantic learnings (2 deduped)
- Idempotent: second run correctly skips all consolidated episodes
- No additional API calls or LLM inference needed (rule-based synthesis)
