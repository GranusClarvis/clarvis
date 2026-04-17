# Brain/Wiki Context Route Benchmark — 2026-04-17

## Methodology
Ran 4 retrieval routes on 5 representative tasks (code_fix, brain_maintenance, research, reflection, project_delivery). Measured latency, unique tokens (content diversity), result count, and avg semantic distance.

## Results

| Route | Avg Latency | Avg Tokens | Notes |
|-------|------------|-----------|-------|
| raw_brain | 189.7ms | 188.2 | Direct brain.recall(), no enrichment |
| wiki_first | 9.4ms | 188.2 | Wiki found 0/40 term matches → fell through to cached brain |
| combined | 122.8ms | 138.0 | Full pipeline: goals + context + knowledge + working memory + MMR + pruning |
| minimal | 1.0ms | 37.0 | Task text + queue snippet only |

## Key Findings

### 1. Wiki route adds no value currently
Wiki canonical resolver matched 0 of ~40 queried terms across 5 tasks. The 32 wiki pages don't cover the terminology in typical heartbeat tasks. Wiki_first is faster than raw_brain only because brain's 30-second result cache kicks in (wiki always runs after raw_brain in the benchmark loop).

**Recommendation:** Don't invest in wiki-first routing until wiki coverage reaches >100 pages with aliases for common task terms. The postflight wiki ingest pipeline is working (32 pages accumulated) but coverage is too sparse for preflight retrieval value.

### 2. Combined route is best quality-per-token
Combined (brain_preflight_context) returns fewer tokens (138 vs 188) but with better quality:
- Distance pruning removes low-relevance hits (median+0.20 cutoff)
- MMR reranking reduces redundancy
- Adds goals, working context, and working memory (richer signal)
- Budget enforcement prevents oversized results

The 122.8ms latency is acceptable (vs raw_brain's 189.7ms — actually faster because pruning reduces downstream processing).

### 3. Minimal route is fast but low-signal
1.0ms latency, 37 tokens. Suitable only for simple/routing tasks where brain context would be noise. The "minimal" tier correctly skips brain search for openrouter/gemini executors.

### 4. Raw brain has caching gaps
First call (code_fix) took 151ms; reflection task took 162ms with 75 results (over-retrieval). No distance pruning means noisy results with avg_distance up to 1.52 (poor relevance). Raw brain should not be used without at least distance pruning.

## Recommended Defaults

| Task Type | Route | Why |
|-----------|-------|-----|
| Code/project tasks | combined | Best quality, acceptable latency |
| Infrastructure/maintenance | combined | Needs goals + context for safe ops |
| Research | combined | MMR prevents redundant research hits |
| Reflection | combined | Distance pruning critical (75→~10 results) |
| Simple routing | minimal | Skip brain entirely |

**Verdict: Combined route (brain_preflight_context) should remain the default.** No route change needed. Wiki-first is not ready for preflight use.

## Raw Data
See `brain_wiki_route_bench.json` in this directory.
