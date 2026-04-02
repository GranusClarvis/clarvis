# Worker Prompt Templates — Implementation

**Date**: 2026-04-02
**Task**: COORDINATOR_PROMPT_TEMPLATES
**Decision**: APPLY (implemented)

## What Was Done

Created 3 worker-type-specific prompt templates and wired them into the autonomous execution pipeline.

### Files Created
- `scripts/worker_templates/research.txt` — Deep-dive research protocol with structured RESEARCH_RESULT output format, brain storage requirements, and citation expectations.
- `scripts/worker_templates/implementation.txt` — Build/ship protocol with diff-focused output, test requirements, and scope-creep prevention rules.
- `scripts/worker_templates/maintenance.txt` — Housekeeping protocol with before/after measurement, safety-first approach, and bloat-awareness.

### Wiring Changes (cron_autonomous.sh)
1. **Preflight JSON parsing** (line ~141): Added `classify_worker_type()` call using task_text + prompt_variant_task_type from preflight JSON. Imports from `clarvis.heartbeat.worker_validation` with graceful fallback to "general".
2. **Template loading** (line ~298): Before `run_claude_code()`, loads template file from `scripts/worker_templates/{WORKER_TYPE}.txt` if it exists. Falls back to original "You are Clarvis's executive function." prompt for general/unknown types.
3. **Observability**: Added `worker=$WORKER_TYPE` to the EXECUTING log line for traceability.

### Classification Flow
```
preflight JSON → {task, prompt_variant_task_type}
       ↓
classify_worker_type() [3 signals: tag, optimizer type, regex]
       ↓
WORKER_TYPE = research|implementation|maintenance|general
       ↓
Load scripts/worker_templates/{WORKER_TYPE}.txt
       ↓
Prepend to Claude Code prompt (replaces generic header)
```

## Key Design Decisions

1. **Classification at parse time, not in preflight**: Adding classification to the bash JSON parsing avoids modifying heartbeat_preflight.py. The function is already available in worker_validation.py, used by postflight — now both ends share the same classification.

2. **Template replaces header, not appends**: The template substitutes "You are Clarvis's executive function." entirely. This keeps prompt size constant (no bloat from layering). The rest of the prompt (context_brief, proc_hint, tasks, rules) is preserved unchanged.

3. **Graceful degradation**: If classification fails (import error) or template file missing, falls back to the original generic prompt. No breakage path.

## Bloat Score Relevance

This change is bloat-neutral (3 small text files added, no code duplication). However, the templates should improve output quality, which indirectly helps bloat by reducing partial_success retries that generate redundant artifacts.

## Next Steps

- Monitor postflight validation pass rates by worker_type to measure template effectiveness
- Consider adding a `general.txt` template or tuning the fallback prompt
- The prompt_optimizer's Thompson sampling could be extended to A/B test template variants per type
