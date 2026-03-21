# Benchmark Scorecard Strategy

_Maps every major Clarvis goal to a measurable benchmark dimension, ensuring
every significant addition has an evaluation lane._

_Created: 2026-03-19 | Owner: autonomous evolution_

---

## Design Principles

1. **Every goal has a metric lane** — no work lands without a way to measure impact.
2. **Daily-lite / Weekly-full** — daily CLR-lite for trend detection, weekly full benchmark for diagnostics.
3. **Regression gates** — a merge/addition that drops any dimension below its floor blocks further autonomous work until triaged.
4. **Delta tracking** — before/after CLR snapshots bracket every autonomous task so we can answer "did this actually help?"

---

## Goal → Benchmark Mapping

| # | Goal | Primary Metric(s) | Benchmark Dimension | Target | Current | Cadence |
|---|------|--------------------|----------------------|--------|---------|---------|
| 1 | **Session Continuity** | BOOT.md load success, daily memory file exists, session_hook open/close | PI: accuracy (episode success rate) | ≥0.90 | 0.924 | Daily PI |
| 2 | **Heartbeat Efficiency** | Heartbeat completion rate, preflight latency, postflight episode encode | PI: brain_query_speed, efficiency | avg <800ms, overhead <15% | 240ms avg | Daily PI |
| 3 | **Self-Reflection** | Reflection pipeline completion, insight-to-brain ratio, dream yield | CLR: autonomy, integration_dynamics | autonomy ≥0.60, integration ≥0.70 | autonomy=TBD | Weekly CLR |
| 4 | **CLR (overall)** | Composite CLR score, value-add over baseline | CLR: all 7 dimensions | CLR ≥0.55, value_add ≥0.10 | baseline ~0.215 | Weekly CLR |
| 5 | **Context Quality** | context_relevance (14-day mean), brief compression ratio | CLR: prompt_context; PI: context_relevance | relevance ≥0.75, compression ≥0.55 | 0.688 / 0.674 | Daily PI + Weekly CLR |
| 6 | **Phi / Integration** | Phi composite (4 sub-metrics), cross-collection bridges | CLR: integration_dynamics; Phi metric | Phi ≥0.80, cross-coll ≥0.70 | Phi=0.794 | Weekly Phi |
| 7 | **Memory Quality** | Brain population, graph density, recall hit rate | CLR: memory_quality | ≥0.80 | ~0.89 | Weekly CLR |
| 8 | **Retrieval Precision** | Retrieval eval verdict, noise ratio, adaptive retry rate | CLR: retrieval_precision | ≥0.70 | TBD | Weekly CLR |
| 9 | **Task Success** | Episode success rate, avg valence, reasoning chain depth | CLR: task_success | ≥0.80 | 0.924 success | Daily PI |
| 10 | **Cost Efficiency** | Daily API cost, cost per successful task | CLR: efficiency | <$3/day avg | varies | Daily cost_tracker |

---

## Sub-Metric Deep Dive: Weakest Areas

### Context Relevance (0.688, target 0.75) — PRIORITY
| Sub-Metric | Source | Current | Target | Action |
|-----------|--------|---------|--------|--------|
| related_tasks section relevance | context_relevance.jsonl | 0.304 | ≥0.50 | Enrich with task dependencies from QUEUE.md |
| episodes section relevance | context_relevance.jsonl | 0.273 | ≥0.40 | Surface failure-avoidance patterns inline |
| decision_context relevance | context_relevance.jsonl | 0.267 | ≥0.40 | Inject success criteria keywords |
| DyCP pruning accuracy | assembly.py | — | false-positive <5% | Monitor section restoration rate |

### Phi Cross-Collection (0.607, target 0.70)
| Sub-Metric | Source | Current | Target | Action |
|-----------|--------|---------|--------|--------|
| proc↔learn overlap | phi.py | 0.600 | ≥0.65 | Add procedure-learning bridge memories |
| ctx↔goals overlap | phi.py | 0.644 | ≥0.70 | Cross-reference goal context |
| ep↔infra overlap | phi.py | 0.555 | ≥0.60 | Add infrastructure episode summaries |

### Brier / Confidence Calibration (0.10, target 0.50)
| Sub-Metric | Source | Current | Target | Action |
|-----------|--------|---------|--------|--------|
| Domain accuracy | clarvis_confidence.py | 0.10 | ≥0.40 | Audit stale predictions, prune >30d |
| Over/under-confidence | confidence_log.jsonl | — | bias <0.10 | Recalibrate domain thresholds |

---

## Benchmark Instruments

| Instrument | What it measures | Frequency | Script/Module |
|-----------|-----------------|-----------|---------------|
| **PI (Performance Index)** | 8 operational dimensions | Every heartbeat (quick) + weekly (full) | `clarvis/metrics/benchmark.py` |
| **CLR (Clarvis Rating)** | 7 cognitive dimensions vs bare baseline | Weekly (full) + on-demand | `clarvis/metrics/clr.py` |
| **Phi (Φ)** | Brain integration quality (4 sub-metrics) | Weekly | `clarvis/metrics/phi.py` |
| **Context Relevance** | Per-section relevance scoring | Every heartbeat (postflight) | `clarvis/brain/retrieval_eval.py` |
| **Brier Score** | Confidence prediction calibration | Weekly | `scripts/clarvis_confidence.py` |
| **Episode Stats** | Success rate, valence, duration trends | Daily (postflight) | `clarvis/memory/episodic_memory.py` |
| **Cost Tracker** | API spend, cost per task | Daily digest | `scripts/cost_tracker.py` |
| **CLR Perturbation** | Ablation deltas per context module | Weekly | `clarvis/metrics/clr_perturbation.py` |

---

## Evaluation Lane Protocol

When adding a new capability or making a significant change:

1. **Before**: Run `python3 -m clarvis brain clr` to snapshot current CLR.
2. **Implement**: Make the change.
3. **After**: Run CLR again. Record delta in `data/clr_history.jsonl`.
4. **Gate check**: If any CLR dimension drops below its floor (see GATE_THRESHOLDS in clr.py), the change must be investigated before further autonomous work.
5. **Perturbation**: For context-assembly changes, run `python3 clarvis/metrics/clr_perturbation.py` to verify the module contributes positively.

---

## Weekly Review Checklist

- [ ] PI trend: any dimension degraded >5% from last week?
- [ ] CLR composite: above 0.40 minimum? Value-add positive?
- [ ] Context relevance: trending toward 0.75?
- [ ] Phi: stable above 0.80? Any cross-collection pair dropped?
- [ ] Episode success rate: above 85%?
- [ ] Cost: within daily budget?
- [ ] Perturbation harness: any module showing negative delta?

---

## Mapping to P0 Milestones (2026-03-31 Deadline)

| Milestone | Gate Metrics | Pass Criteria |
|-----------|-------------|---------------|
| A: Foundation Freeze (03-19) | PI ≥0.90, all cron stable | PI=0.986 ✓ |
| B: Brain/Context Quality (03-23) | context_relevance ≥0.73, CLR ≥0.45 | In progress |
| C: Repo/Open-Source (03-26) | Code quality ≥0.90, no secrets in repo | TBD |
| D: Public Surface (03-29) | Website up, benchmark dashboard visible | TBD |
| E: Final Validation (03-31) | CLR ≥0.55, Phi ≥0.80, all gates pass | TBD |
