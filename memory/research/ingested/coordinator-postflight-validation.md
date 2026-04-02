# COORDINATOR_POSTFLIGHT_VALIDATION — Worker-Type-Aware Output Validation

**Date**: 2026-04-02
**Status**: IMPLEMENTED
**Module**: `clarvis/heartbeat/worker_validation.py`
**Integration**: `scripts/heartbeat_postflight.py` §0.5

## Summary

Added worker-type-aware output validation to the heartbeat postflight pipeline. Tasks are classified into worker types (research, implementation, maintenance, general) and their output is validated against type-specific expectations. Tasks that produce output below minimum quality are downgraded from `success` to `partial_success`.

## Architecture

### Classification (3 signals, priority order)

1. **task_tag** from QUEUE.md brackets — `[RESEARCH]`, `[IMPL]`, `[MAINTENANCE]`
2. **prompt_variant_task_type** from prompt optimizer — `research`, `implementation`, `bugfix`, etc.
3. **Regex pattern matching** on task text — fallback heuristic with compiled patterns

### Validation Rules

| Worker Type | Required (pass) | Checks |
|---|---|---|
| Research | 2 of 3 checks | has_findings, has_brain_storage, has_structure |
| Implementation | has_file_changes | has_file_changes, has_tests, has_code |
| Maintenance | 1 of 2 checks | has_status, has_actions |
| General | always passes | (no validation) |

### Downgrade Behavior

- Only successful tasks are validated (failure/timeout/crash untouched)
- Failed validation sets `task_status = "partial_success"`, `error_type = "output_validation"`
- Flows through episode encoding (recognized in episodic memory taxonomy)
- Flows through trajectory scoring, digest writing, and all downstream stages

## Key Ideas

1. **Three-signal classification** avoids brittle single-pattern matching — task_tag is authoritative, regex is fallback
2. **Threshold-based research validation** (2-of-3) is lenient enough for varied research styles while catching empty/unstructured output
3. **Implementation requires file changes** as hard minimum — tests are tracked but not required (some tasks are analysis-only)
4. **Maintenance validation is loose** — either status reporting or actions taken suffices (some maintenance confirms "nothing to do")
5. **General tasks skip validation entirely** — avoids false positives on miscategorized tasks

## Bloat Score Relevance

This directly supports bloat reduction:
- Research workers that produce code instead of notes get flagged
- Implementation workers that create files without tests get flagged
- Typed validation creates feedback pressure toward cleaner output patterns
- `partial_success` episodes feed into episode success rate metrics, creating accountability

## Files Changed

- `clarvis/heartbeat/worker_validation.py` — NEW (canonical module, ~230 lines)
- `scripts/heartbeat_postflight.py` — Added §0.5 worker validation stage in `run_postflight()`

## Stored

3 brain memories in `clarvis-learnings`
