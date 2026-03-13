# Research-Implementation Bridge

**Date:** 2026-03-13
**Script:** `scripts/research_to_queue.py`

## What It Does

Automated pipeline that scans `memory/research/ingested/` for papers with actionable findings, cross-references QUEUE.md + QUEUE_ARCHIVE.md to avoid duplicates, and surfaces candidate queue items for unimplemented research.

## How It Works

1. **Scan**: Reads all `.md` files in ingested/, identifies actionable sections by heading patterns (e.g., "Application to Clarvis", "Improvement Proposals", "Gap Analysis", "Actionable Patterns")
2. **Extract**: Pulls bullet/numbered items and sub-headings from actionable sections (min 20 chars, filters table rows)
3. **Score**: Ranks proposals by impact signals — "high impact" (+0.2), "code generation/quality" (+0.15), "low effort" (+0.1), "directly" (+0.05)
4. **Deduplicate**: Word-overlap matching (threshold 0.45) against all QUEUE + ARCHIVE items
5. **Output**: Sorted list of uncovered proposals with formatted QUEUE tags

## Key Findings (First Run)

- **19 papers** scanned with actionable sections
- **352 proposals** extracted total
- **218 uncovered** (new) — not yet in QUEUE
- **134 covered** — correctly deduplicated against existing queue items
- **Top candidate** (score 0.70): Multi-path planning via PlanSearch — directly targets Code Generation Quality 0.655→0.75

## Top 5 Uncovered Proposals

1. **Multi-path planning** (code_generation_agent_survey): PlanSearch generates k candidate plans, evaluates in parallel, picks best. Replaces linear single-plan heartbeat approach.
2. **Verification co-production** (veriguard_ticoder): Generate code + verification tests together (correct-by-construction). +45.97% pass@1 via iterative refinement.
3. **Pre-execution test specification** (code_generation_agent_survey): QualityFlow pattern — generate test assertions before code, validate after.
4. **Circular optimization** (code_generation_agent_survey): CodeCoR reflection between stages — score/locate problems, feed back to preceding stage.
5. **Deterministic pre-processing** (self_debugging_architectures): PyCapsule error classification + relevance filtering before LLM debug. 1.38 API calls/problem avg.

## Clarvis Application

- **Code Generation Quality (0.655→0.75)**: Proposals #1-#3 directly target the weakest metric. Multi-path planning has highest individual impact.
- **Monthly cadence**: Run via `cron_reflection.sh` to catch new papers and surface unimplemented research before it goes stale.
- **Injection mode**: `python3 research_to_queue.py inject --max 3` adds top candidates to QUEUE.md P1 via queue_writer.

## Integration Point

Add to `cron_reflection.sh` as a monthly step (run on 1st of each month).
