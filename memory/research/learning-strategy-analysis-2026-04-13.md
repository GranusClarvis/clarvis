# Learning Strategy Analysis — Implementation Note

**Date**: 2026-04-13
**Type**: Implementation (internal tooling)
**Status**: APPLY

## What Was Built

Added a `learning-strategy` CLI mode to `scripts/cognition/knowledge_synthesis.py` that performs weekly meta-learning analysis over the brain's memory stores.

### How It Works

1. **Time-windowed scan**: Queries all brain collections, filters to memories with `created_epoch` within the past N days (default: 7).
2. **Source classification**: Maps each memory's `source` metadata and `tags` into 5 buckets: episodes, research, reflection, coding, system.
3. **Quality scoring**: Computes a composite quality score per memory: `0.4 * importance + 0.35 * log_access + 0.25 * log_recall_success`.
4. **Strategy generation**: Identifies highest/lowest quality sources, detects imbalances (>70% from single source), writes a 1-paragraph strategy adjustment.
5. **Output**: Writes strategy to `memory/cron/digest.md` via digest_writer + stores insight in `clarvis-learnings`.

### Cron Schedule

- **When**: Sunday 05:25 CET (after `brain_hygiene` at 05:15, before `cron_cleanup` at 05:30)
- **Entry**: `. scripts/cron/cron_env.sh && python3 scripts/cognition/knowledge_synthesis.py learning-strategy`
- **Log**: `memory/cron/learning_strategy.log`

## Key Findings (First Run)

- 96 new memories in 7 days
- **Coding** (40.6%): highest volume, avg quality 0.411
- **Research** (2.1%): highest quality (0.535) but lowest volume
- **Reflection** (38.5%): high volume but lowest quality (0.260)
- Strategy: research sessions produce the best memories but are underutilized

## Clarvis Application

1. **Learning compounding**: Weekly analysis makes learning effectiveness measurable — can now track whether strategy adjustments improve memory quality week-over-week.
2. **Source rebalancing**: The first run revealed research is high-quality but rare (2.1%), while reflection is high-volume but low-quality. This suggests increasing research slots or improving reflection's memory-storage criteria.
3. **Phi improvement potential**: Better learning sources → higher-quality memories → stronger cross-collection connections → improved integration (Phi). This addresses the weakest metric (Phi=0.619, target 0.65).

## Next Steps

- Monitor weekly reports for trend changes
- Consider adding episode-level quality tracking (success vs failure episodes)
- Investigate why reflection memories score low — are they too generic?
