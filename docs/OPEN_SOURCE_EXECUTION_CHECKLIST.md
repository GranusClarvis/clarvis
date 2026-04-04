# Open-Source Execution Checklist

> **Note (2026-04-03):** The `packages/` directory (clarvis-db, clarvis-cost, clarvis-reasoning) has been
> consolidated into the `clarvis/` spine module. References to standalone packages below are historical.
> See `clarvis/brain/`, `clarvis/orch/cost_tracker.py`, `clarvis/cognition/metacognition.py`.


**Derived from:** `SPINE_CLEANUP_PLAN.md` Phases 0-4
**Deadline:** 2026-03-31 (delivery window)
**Method:** Day-by-day ordering with preconditions, validation, and rollback for each step

---

## Phase 0: Documentation & Labeling (Zero Risk)

**Target:** Days 1-2 (by 2026-03-25)
**Preconditions:** None
**Rollback:** `git revert` (only doc/comment changes)
**Validation:** `git diff --stat` shows only `.md` and comment-only `.py` changes

- [x] Create `docs/DO_NOT_TOUCH_REGISTRY.md` from "Do Not Touch Yet" section
- [x] Create this execution checklist (`docs/OPEN_SOURCE_EXECUTION_CHECKLIST.md`)
- [x] Add `# BRIDGE:` header comment to each of the 8 thin wrapper scripts: _(verified 2026-04-03, all present)_
  - [x] `scripts/attention.py` — callers: heartbeat_preflight, heartbeat_postflight, 13+ others
  - [x] `scripts/clarvis_confidence.py` — callers: heartbeat_preflight, heartbeat_postflight, 2 others
  - [x] `scripts/episodic_memory.py` — callers: heartbeat_preflight, dream_engine, 10+ others
  - [x] `scripts/hebbian_memory.py` — callers: cron_reflection.sh
  - [x] `scripts/memory_consolidation.py` — callers: brain.py CLI, cron_reflection.sh, 1 other
  - [x] `scripts/procedural_memory.py` — callers: heartbeat_preflight, heartbeat_postflight, 2 others
  - [x] `scripts/thought_protocol.py` — callers: reasoning_chain_hook, 1 other
  - [x] `scripts/working_memory.py` — callers: safe_update.sh (existence check)
- [x] Add `# STATUS: confirmed-dead, no production callers` to 4 dead scripts — all DELETED in Phase 1 _(verified 2026-04-03)_
  - [x] `scripts/universal_web_agent.py` — DELETED in Phase 1
  - [x] `scripts/public_feed.py` — DELETED in Phase 1
  - [x] `scripts/retrieval_quality_report.py` — DELETED in Phase 1
  - [x] `scripts/generate_dashboard.py` — DELETED in Phase 1
- [x] Add `# STATUS: production-wired via heartbeat` to 8 misclassified scripts: _(verified 2026-04-03, all present)_
  - [x] `scripts/cognitive_load.py`
  - [x] `scripts/workspace_broadcast.py`
  - [x] `scripts/hyperon_atomspace.py`
  - [x] `scripts/somatic_markers.py`
  - [x] `scripts/automation_insights.py`
  - [x] `scripts/theory_of_mind.py`
  - [x] `scripts/actr_activation.py`
  - [x] `scripts/brain_bridge.py`
- [x] Add ERRATA section to top of `docs/SPINE_USAGE_AUDIT.md` linking to SPINE_CLEANUP_PLAN.md _(done 2026-04-03)_
- [ ] Archive completed one-time docs to `docs/archive/`:
  - [ ] Identify candidates: `REFACTOR_COMPLETION_PLAN.md`, `POST_MIGRATION_GAP_REPORT.md`, etc.
  - [ ] `mkdir -p docs/archive && git mv docs/<file> docs/archive/`

---

## Phase 1: Confirmed Dead Code Removal (Very Low Risk)

**Target:** Day 2 (2026-03-25)
**Preconditions:** Phase 0 complete
**Rollback:** `git revert`
**Validation:**
- [ ] `python3 -m clarvis brain health` passes
- [ ] Manual heartbeat trigger succeeds: `python3 scripts/heartbeat_preflight.py --dry-run` (or equivalent)
- [ ] `cd packages/clarvis-db && python3 -m pytest tests/` passes

- [x] Delete 4 confirmed-dead scripts + 1 test — **DONE 2026-03-23**
  - [x] `scripts/universal_web_agent.py` (647L)
  - [x] `scripts/public_feed.py` (279L)
  - [x] `scripts/retrieval_quality_report.py` (314L)
  - [x] `scripts/generate_dashboard.py` (351L)
  - [x] `tests/scripts/test_universal_web_agent.py` (164L)
- [x] Verify NOT deleted: `prompt_optimizer.py`, `prediction_review.py`, `gate_check.sh`

---

## Phase 2: Legacy Import Migration — Bridge Wrappers (Medium Risk)

**Target:** Days 3-7 (2026-03-25 to 2026-03-29)
**Preconditions:** Phase 1 complete. Tests pass. One full day of clean autonomous operation.
**Rollback:** `git revert <commit>` for any migration that breaks
**Validation (per script migrated):**
- [ ] Run the migrated script standalone
- [ ] Verify the cron job that calls it runs successfully
- [ ] Check logs next day for import errors

### Step 2a: High-traffic hub migration (Day 3-4)
Migrate imports in `heartbeat_preflight.py` and `heartbeat_postflight.py`:
- [ ] Map all `from <module> import` → `from clarvis.<pkg>.<module> import` for each legacy import
- [ ] Verify each spine module exports the same symbols
- [ ] Migrate `heartbeat_preflight.py` imports (one commit per batch of 5)
- [ ] Migrate `heartbeat_postflight.py` imports (one commit per batch of 5)
- [ ] Run 2 full heartbeat cycles. Check `memory/cron/digest.md` for errors.

### Step 2b: Cron-called scripts (Day 5)
- [ ] For `cron_reflection.sh` calls to `episodic_memory.py`, `hebbian_memory.py`, `memory_consolidation.py`:
  - Option A: Add `__main__` block delegating to spine CLI
  - Option B: Update `cron_reflection.sh` to call `python3 -m clarvis <subcommand>`
- [ ] Test the 21:00 reflection pipeline manually

### Step 2c: Remaining legacy imports (Days 6-7)
- [ ] Work through remaining 87 legacy-import scripts in batches of 5-10
- [ ] For each batch: migrate, test, commit
- [ ] After all callers for a bridge wrapper are migrated, verify zero remaining callers, then delete wrapper

---

## Phase 3: Context Engine Consolidation (Medium-High Risk)

**Target:** Days 7-9 (2026-03-29 to 2026-03-31)
**Preconditions:** Phase 2 heartbeat imports migrated. Function-level diff complete.
**Rollback:** `git revert` + restore old import in heartbeat_preflight.py
**Validation:**
- [ ] Run 2-3 full heartbeat cycles
- [ ] Compare context output before/after (save preflight context to temp file)

- [ ] Produce function-by-function diff: `scripts/context_compressor.py` vs `clarvis/context/assembly.py` + `clarvis/context/compressor.py`
  - [ ] Functions unique to scripts/ (need migration to spine)
  - [ ] Functions unique to spine (already migrated)
  - [ ] Functions in both (check for divergence)
- [ ] Migrate remaining unique functions from scripts/ to spine
- [ ] Update `heartbeat_preflight.py` to import from `clarvis.context`
- [ ] Keep `scripts/context_compressor.py` as bridge wrapper during transition
- [ ] Test end-to-end context generation

---

## Phase 4: Public-Facing Open-Source Restructuring (Low-Medium Risk)

**Target:** Day 9-10 (2026-03-31)
**Preconditions:** Phases 0-2 complete. Secret scan (E2) and fresh clone test (E3) complete.
**Rollback:** `git revert`
**Validation:**
- [ ] Fresh clone from GitHub → `python3 -m clarvis brain health` passes
- [ ] No secrets in git history (`git log -p | grep -i "sk-or-v1\|api_key\|password"` clean)
- [ ] README, ARCHITECTURE docs reflect current state

- [ ] Create `experimental/` directory if needed
- [ ] Move fully-decoupled scripts there (only those with zero remaining callers post-Phase 2)
- [ ] Add `experimental/README.md` explaining purpose and experimental status
- [ ] Clean up `docs/`:
  - [ ] Completed plans → `docs/archive/`
  - [ ] Outdated references removed
- [ ] Update `CLAUDE.md` script categories and counts
- [ ] Update main `README.md` for public audience
- [ ] Verify `ARCHITECTURE.md` matches actual current state
- [ ] Final secret scan: no API keys, tokens, or credentials in committed files

---

## Pre-Launch Checklist (Day 10)

- [ ] All Phase 0-4 items marked complete
- [ ] `python3 -m clarvis brain health` → OK
- [ ] `cd packages/clarvis-db && python3 -m pytest tests/` → all pass
- [ ] Fresh clone test passes
- [ ] Secret scan clean
- [ ] Website live and accurate
- [ ] README compelling for external visitors
- [ ] Git history clean (no accidental secret commits)
- [ ] License file present (MIT)

---

## Notes

- **Do not rush Phase 2.** Each import migration must be individually verified. A broken heartbeat pipeline is worse than an ugly import.
- **Phase 3 is optional for launch.** The split-brain context engine works — it's messy but functional. Consolidation is a quality improvement, not a launch blocker.
- **Phase 4 is the public-facing one.** This is what visitors see. Prioritize README, docs accuracy, and secret cleanliness over internal code beauty.
- Consult `docs/DO_NOT_TOUCH_REGISTRY.md` before moving/deleting any file.
