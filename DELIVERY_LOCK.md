# Delivery Lock — Active

**Window**: 2026-03-17 → 2026-03-31
**Purpose**: All autonomous evolution, heartbeats, and task selection MUST prioritize delivery work only.

## Allowed Work Categories
- `DLV_*` — Delivery-tagged tasks
- Cleanup, consolidation, dead code removal
- Wiring, testing, bug fixes
- Context quality / brain quality improvements
- Website / open-source readiness
- Documentation for external presentation

## Blocked Work Categories
- New feature expansion (unless required for delivery)
- Research sessions on unrelated topics
- New cognitive architecture experiments
- New package extractions
- Orchestrator feature additions (Phase 2+)

## Enforcement
- `clarvis/orch/task_selector.py` applies a scoring penalty to non-delivery tasks during lock window
- Heartbeat preflight checks this file exists and is active
- Cron autonomous respects this constraint via task scoring

## Exit Criteria
- Date passes 2026-03-31, OR
- All Milestone E items are [x] in QUEUE.md, OR
- User explicitly removes this file
