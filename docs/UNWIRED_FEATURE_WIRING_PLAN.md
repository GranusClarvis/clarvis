# Unwired Feature Wiring Plan

_Audit date: 2026-03-10. Produced by autonomous evolution heartbeat._

## Summary

14 cognitive features audited. **4 fully wired**, **9 partially wired** (daily reflection only), **1 unwired** (dormant).

## Wiring Status

| Feature | File | Integration | Freq | Status |
|---------|------|-------------|------|--------|
| AZR | `absolute_zero.py` | cron_absolute_zero.sh (Sun) + cron_reflection.sh | Weekly+daily | FULLY WIRED |
| ACT-R Activation | `actr_activation.py` | brain_bridge.py + context_compressor.py | Every heartbeat | FULLY WIRED |
| Procedural Memory | `procedural_memory.py` | heartbeat_preflight.py + postflight.py | Every heartbeat | FULLY WIRED |
| Self Model | `self_model.py` | cron_evening.sh + evolution_preflight.py | Daily+evolution | FULLY WIRED |
| Meta-learning | `meta_learning.py` | cron_reflection.sh only | 1x/day | PARTIALLY WIRED |
| Failure Amplifier | `failure_amplifier.py` | cron_reflection.sh only | 1x/day | PARTIALLY WIRED |
| Conversation Learner | `conversation_learner.py` | cron_reflection.sh only | 1x/day | PARTIALLY WIRED |
| Intra-linker | `intra_linker.py` | cron_reflection.sh only | 1x/day | PARTIALLY WIRED |
| Knowledge Synthesis | `knowledge_synthesis.py` | cron_reflection.sh only | 1x/day | PARTIALLY WIRED |
| Temporal Self | `temporal_self.py` | cron_reflection.sh only | 1x/day | PARTIALLY WIRED |
| Memory Consolidation | `memory_consolidation.py` | cron_reflection.sh + postflight (light) | 1x/day | PARTIALLY WIRED |
| Tool Maker | `tool_maker.py` | heartbeat_postflight.py (success only) | Per-heartbeat | PARTIALLY WIRED |
| Hebbian Memory | `hebbian_memory.py` | cron_reflection.sh only | 1x/day | PARTIALLY WIRED |
| **GraphRAG Communities** | `graphrag_communities.py` | **NONE (manual CLI only)** | 0x/day | **UNWIRED** |

## Ranked Wiring Plan

### Tier 1: INTEGRATE (high value, low risk)

1. **[GRAPHRAG_COMMUNITY_WIRE]** — Wire `graphrag_communities.py` into brain recall path.
   - **Why**: 622 LOC fully built, zero automation. Leiden community detection + map-reduce global search could improve abstract query recall.
   - **How**: (a) Add periodic community re-detection to cron_reflection.sh (weekly, ~30s). (b) Add community-aware expansion in `brain_bridge.py` for low-confidence queries (score < 0.6).
   - **Risk**: Low — read-only enhancement, no writes to brain.
   - **Priority**: P1

2. **[META_LEARNING_POSTFLIGHT]** — Wire meta-learning analysis into heartbeat_postflight.py.
   - **Why**: Currently only daily in reflection. Strategy success rates should update after every task, not once/day.
   - **How**: After episode encoding, call `meta_learning.record_outcome(strategy, success)` (~5 lines).
   - **Risk**: Low — append-only to analysis data.
   - **Priority**: P1

3. **[FAILURE_AMPLIFIER_POSTFLIGHT]** — Wire failure amplifier into heartbeat_postflight on failure.
   - **Why**: Failed tasks should immediately trigger amplification (root cause extraction), not wait for nightly reflection.
   - **How**: On `exit_code != 0`, call `failure_amplifier.amplify(task, output)` (~5 lines).
   - **Risk**: Low — only fires on failures.
   - **Priority**: P2

### Tier 2: DEFER (working fine at current frequency)

4. **Conversation Learner** — Daily reflection is sufficient. Learning from conversations doesn't need real-time processing.
5. **Intra-linker** — Daily with `--cap 5` is appropriate. More frequent would add redundant edges.
6. **Knowledge Synthesis** — Daily synthesis captures enough. Higher frequency would produce shallow insights.
7. **Temporal Self** — Daily temporal snapshot is the right granularity.
8. **Hebbian Memory** — Daily evolution pass is sufficient for synaptic weight updates.
9. **Memory Consolidation** — Already has light postflight integration. Daily deep pass is appropriate.
10. **Tool Maker** — Success-only gate is correct design. No change needed.

### Tier 3: RETIRE (candidates for deprecation review)

_None currently — all features provide measurable value at their current frequency._

## Bottleneck: Reflection Pipeline

`cron_reflection.sh` runs 9 features sequentially at 21:00. This is a cognitive bottleneck — if any feature fails or hangs, downstream features are skipped. Consider:
- Adding `timeout 60` wrappers around each feature call
- Logging per-feature timing to identify slow features
- Moving high-value features (meta-learning, failure amplifier) closer to task execution (postflight)

## Next Actions

- [ ] Wire GraphRAG community detection into weekly reflection
- [ ] Wire meta-learning outcome recording into heartbeat_postflight.py
- [ ] Wire failure amplifier into heartbeat_postflight.py (failure path)
- [ ] Add per-feature timeout wrappers in cron_reflection.sh
