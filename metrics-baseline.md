# Metrics Baseline — Auto-Updated

This file tracks key Clarvis metrics with actual values to prevent documentation drift.
Updated automatically via cron job.

**Last Updated:** 2026-03-13

## Brain Metrics

| Metric | Current Value | Last Updated | Source |
|--------|---------------|--------------|--------|
| Total Memories | `python3 -c "from brain import brain; print(brain.stats()['total_memories'])"` | 2026-03-13 | brain.stats() |
| Graph Edges | `python3 -c "from brain import brain; print(brain.stats()['graph_edges'])"` | 2026-03-13 | brain.stats() |
| Graph Nodes | `python3 -c "from brain import brain; print(brain.stats()['graph_nodes'])"` | 2026-03-13 | brain.stats() |
| Collections | `python3 -c "from brain import brain; import json; print(json.dumps(brain.stats()['collections']))"` | 2026-03-13 | brain.stats() |
| Brain Query Speed (avg) | `python3 scripts/performance_benchmark.py quick` | 2026-03-13 | benchmark |

## Performance Index

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| PI | See `data/performance_metrics.json` | >0.70 | RUN BENCHMARK |
| Brain Query Avg | 740ms | <800ms | TIGHT |
| Brain Query P95 | 1289ms | <1500ms | TIGHT |
| Retrieval Hit Rate | 1.0 | >0.85 | EXCELLENT |
| Episode Success | 91.2% | >85% | EXCELLENT |
| Phi | 0.83 | >0.70 | EXCELLENT |

## Infrastructure

| Metric | Value | Source |
|--------|-------|--------|
| Gateway Port | 18789 | openclaw.json |
| Model | minimax-m2.5 | openclaw.json |
| Node | clarvis (NUC) | IDENTITY.md |

## Key Targets (Honest Scoring)

Updated 2026-03-13 based on audit findings. Previous targets were too soft:
- Brain query: was 8000ms, now 800ms (10x harder)
- Retrieval hit: was 0.80, now 0.85
- Episode success: was 0.70, now 0.85
- Phi: was 0.50, now 0.70

## Quality Metrics (New)

Added 2026-03-13 to address "88% success could mean 88% mediocre":
- `task_quality_score` — outcome quality, not just completion
- `code_quality_score` — lint, imports, security for generated code

## Commands

```bash
# Run full benchmark
python3 scripts/performance_benchmark.py record

# Quick check
python3 scripts/performance_benchmark.py quick

# Show trends
python3 scripts/performance_benchmark.py trend 30
```