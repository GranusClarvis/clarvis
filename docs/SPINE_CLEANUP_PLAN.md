# Spine Cleanup Plan — Conservative, Verified

**Date:** 2026-03-23
**Based on:** Second-pass verification of `docs/SPINE_USAGE_AUDIT.md` against actual codebase
**Method:** `grep -rl` caller tracing, crontab cross-reference, systemd check, file counts
**Safety:** This document is analysis/planning only. No code was modified.

---

## Executive Summary

The SPINE_USAGE_AUDIT (2026-03-23) provides a useful structural map but **its deletion recommendations are dangerously wrong**. The audit's two headline claims — "8 thin wrappers with zero callers" and "13 research prototypes with zero callers" — are both incorrect. All 8 "thin wrappers" have active legacy callers (many in the heartbeat pipeline). 8 of 13 "research prototypes" are imported by production scripts. Following the audit's Phase 1/Phase 2 recommendations blindly would **break the heartbeat pipeline, cron reflection, watchdog, and autonomous execution**.

The audit's structural classification (what is core, what is spine, the subsystem map) is largely correct. Its error is in caller analysis — it appears to have searched for direct cron entries and CLI usage but missed `import` statements within intermediate scripts like `heartbeat_preflight.py` and `heartbeat_postflight.py`, which are the main import hubs.

**Actual safe deletions identified: 4 scripts (~1,591 lines), not the claimed 21 scripts (~12,000 lines).** (prompt_optimizer.py was wrongly classified as dead — it has active heartbeat callers.)

---

## Confidence in Audit

### HIGH confidence (structural claims — trust these)

- Subsystem map (§1): Cron → orchestrator shells → heartbeat pipeline → spine. Correct.
- Brain & Memory classification (§2.1): All core live. Correct.
- Heartbeat pipeline (§2.2): Scripts are the real runtime, spine heartbeat/ is infrastructure. Correct.
- Cron orchestrators (§2.7): All core live. Correct.
- Maintenance & infrastructure (§2.8): All core live. Correct.
- Website (§2.9): Core live, port 18801. Correct.
- Skills (§2.10): 20 skills, all active. Correct.
- Packages (§2.11): All 3 core live. Correct.
- Script count: 139. Correct.
- Legacy sys.path import count: 87. Correct.
- DO NOT REMOVE registry (§5): Mostly correct (brain.py, context_compressor.py, cognitive_workspace.py, directive_engine.py, dream_engine.py, lock_helper.sh, data/clarvisdb/ — all verified critical).

### MEDIUM confidence (partially correct — verify before acting)

- Context engine "split-brain" claim (§2.3): The audit says spine is an "incomplete subset" of scripts/context_compressor.py. **Actually, spine `assembly.py` (2,044L) is now larger than scripts/ version (1,499L).** The spine header says "Migrated from scripts/context_compressor.py." The scripts version may still be authoritative at runtime (heartbeat imports it), but the spine is not incomplete — it may be the more complete version now. Needs function-by-function diff.
- Cognition classification (§2.4): Mostly correct but `thought_protocol.py` wrapper has 2 callers (not zero).
- Orchestration (§2.6): task_selector.py claim that "heartbeat_preflight imports it" is wrong — preflight imports from spine directly. But test files import the wrapper.
- soar_engine.py: Contradictorily listed in both "DO NOT REMOVE" (§5) and "experimental/move" (§7). The DO NOT REMOVE classification is correct — it has 3 confirmed importers.
- Spine module count: Audit says 77, actual is **65** (overstated by 12).
- Crontab entries: Audit says 52, actual is **47** (overstated by 5).
- Spine import count: Audit says 38, actual is **44** (understated by 6).

### LOW confidence (wrong — do NOT follow these recommendations)

- **"8 thin wrappers with zero callers, safe to delete" (§3.1): WRONG.** All 8 have active callers:

  | Wrapper | Actual callers | Most critical |
  |---------|---------------|---------------|
  | attention.py | 15+ scripts, cron_watchdog.sh | heartbeat_preflight, heartbeat_postflight |
  | clarvis_confidence.py | 4 scripts | heartbeat_preflight, heartbeat_postflight |
  | episodic_memory.py | 12+ scripts, cron_reflection.sh | heartbeat_preflight, dream_engine |
  | hebbian_memory.py | cron_reflection.sh | Daily 21:00 cron |
  | memory_consolidation.py | 2 scripts, cron_reflection.sh | brain.py CLI, cron_reflection |
  | procedural_memory.py | 4 scripts | heartbeat_preflight, heartbeat_postflight |
  | thought_protocol.py | 2 scripts | reasoning_chain_hook |
  | working_memory.py | safe_update.sh (existence check) | Update health gate |

  **Deleting ANY of these breaks production.** They are thin wrappers, yes, but they are the bridge between 87 legacy-import scripts and the spine. They cannot be removed until every legacy `from <module> import` is migrated to `from clarvis.<pkg>.<module> import`.

- **"13 research prototypes with zero callers" (§3.2): MOSTLY WRONG.** Only 4 are truly dead (prompt_optimizer and prediction_review have active callers):

  | Script | Audit says | Actually |
  |--------|-----------|----------|
  | theory_of_mind.py | zero callers | session_hook.py → daily cron |
  | actr_activation.py | zero callers | clarvis/brain/hooks.py import |
  | hyperon_atomspace.py | zero callers | heartbeat_postflight import |
  | workspace_broadcast.py | zero callers | heartbeat_preflight + postflight |
  | cognitive_load.py | zero callers | heartbeat_preflight + cron_autonomous |
  | somatic_markers.py | zero callers | heartbeat_preflight (try/except) |
  | automation_insights.py | zero callers | heartbeat_preflight |
  | universal_web_agent.py | zero callers | **Confirmed dead** |
  | prompt_optimizer.py | zero callers | **NOT dead** — heartbeat_preflight:127 + heartbeat_postflight:191 |
  | public_feed.py | zero callers | **Confirmed dead** |
  | retrieval_quality_report.py | zero callers | **Confirmed dead** |
  | prediction_review.py | zero callers | **NOT dead** — evolution_preflight.py:31 imports review_domains |
  | generate_dashboard.py | zero callers | **Confirmed dead** |

- **brain_bridge.py classified as "weakly wired" (§3.3): WRONG.** It is imported by both heartbeat_preflight and heartbeat_postflight — core production pipeline, runs 12+x/day.

- **reasoning_chains.py classified as "weakly wired": UNDERSTATED.** Has 3 callers including reasoning_chain_hook (heartbeat postflight path) and dream_engine (daily cron).

- **dashboard_server.py "0 callers, retire": INCOMPLETE.** It's a standalone service with its own systemd unit (`clarvis-dashboard.service`), test suite (15 tests), and companion frontend. Not a library — it's an application.

---

## Phased Cleanup Plan

### Phase 0: Documentation & Labeling (Zero Risk)
**Preconditions:** None
**Validation:** `git diff --stat` shows only doc changes
**Rollback:** `git revert`

Tasks:
1. Add a header comment to each of the 8 thin wrapper scripts:
   ```python
   # BRIDGE: Thin re-export wrapper for legacy sys.path imports.
   # Safe to delete ONLY after all callers migrate to: from clarvis.<pkg>.<module> import ...
   # Known callers: [list them]
   ```
2. Add `# STATUS: research-prototype, no production callers` to the 5 confirmed-dead scripts (universal_web_agent, prompt_optimizer, public_feed, retrieval_quality_report, generate_dashboard).
3. Add `# STATUS: production-wired via heartbeat` to the 8 misclassified "research" scripts that are actually imported by heartbeat (cognitive_load, workspace_broadcast, hyperon_atomspace, somatic_markers, automation_insights, theory_of_mind, actr_activation, brain_bridge).
4. Fix the audit itself: update SPINE_USAGE_AUDIT.md §3.1 and §3.2 with corrections, or add a prominent "ERRATA" section at the top linking to this plan.
5. Archive dated/completed docs to `docs/archive/`:
   - REFACTOR_COMPLETION_PLAN.md
   - POST_MIGRATION_GAP_REPORT.md
   - ARCH_AUDIT_2026-03-05.md (if exists)
   - MARATHON_STOP_REPORT.md (if exists)
   - Any other completed one-time plans

**Why safe:** Comments and doc moves don't affect runtime.

### Phase 1: Confirmed Dead Code Removal (Very Low Risk)
**Preconditions:** Phase 0 complete. Verify each file one more time with `grep -rl <filename> scripts/ clarvis/ skills/` before deleting.
**Validation:** Run `python3 -m clarvis brain health` + trigger one heartbeat cycle manually + run test suite
**Rollback:** `git revert`

Tasks:
1. ~~Delete 4 confirmed-dead scripts (total ~1,591 lines):~~ **DONE 2026-03-23**
   - ~~`scripts/universal_web_agent.py` (647L) — clarvis_browser.py supersedes it~~ DELETED
   - ~~`scripts/public_feed.py` (279L) — never wired into cron~~ DELETED
   - ~~`scripts/retrieval_quality_report.py` (314L) — CLI-only, never automated~~ DELETED
   - ~~`scripts/generate_dashboard.py` (351L) — recently created, never wired~~ DELETED
   - ~~`tests/scripts/test_universal_web_agent.py` (164L)~~ DELETED
2. **DO NOT delete** `scripts/prompt_optimizer.py` — imported by heartbeat_preflight:127 and heartbeat_postflight:191. Original plan was wrong.
3. **DO NOT delete** `scripts/prediction_review.py` — imported by evolution_preflight.py:31 (`review_domains`).
4. **DO NOT delete** `scripts/gate_check.sh` — actively referenced in docs/ARCHITECTURE.md, tests/test_spine_phase4.py, and multiple doc files. Has spine wrapper in `clarvis/heartbeat/runner.py`.

**Why safe:** These scripts have zero Python importers, zero cron entries, and zero shell callers. The audit got these 5 right.

### Phase 2: Legacy Import Migration — Bridge Wrappers (Medium Risk, High Prerequisite Value)
**Preconditions:** Phase 1 complete. Tests pass. One full day of autonomous operation with no errors.
**Validation:** For each migrated script: run it standalone, verify the cron job that calls it, check logs next day.
**Rollback:** `git revert` the migration commit for any script that breaks.

This phase is the **prerequisite** for all future cleanup. The 8 bridge wrappers cannot be removed, and the "87 legacy imports" create ongoing maintenance risk. Migrate incrementally.

Tasks (in priority order):
1. **High-traffic first:** Migrate imports in `heartbeat_preflight.py` and `heartbeat_postflight.py` from `from attention import ...` to `from clarvis.cognition.attention import ...` (and similarly for all other legacy imports). These two files are the hub — fixing them removes 20+ bridge dependencies.
2. **Cron-called scripts next:** `cron_reflection.sh` calls `episodic_memory.py`, `hebbian_memory.py`, `memory_consolidation.py` directly as `python3 scripts/<name>.py <subcommand>`. These need the script to exist as a CLI entry point, not just as an import bridge. Options:
   - Keep the wrapper but add a `__main__` block that delegates to the spine CLI, OR
   - Update `cron_reflection.sh` to call `python3 -m clarvis <subcommand>` directly
3. **Remaining scripts:** Work through the 87 legacy-import scripts in batches of 5-10, migrating `sys.path.insert + from <module>` to `from clarvis.<pkg>.<module>`.
4. After all callers for a bridge wrapper are migrated, the wrapper becomes truly zero-caller and can be deleted.

**Why this ordering:** Preflight/postflight are the most-imported files. Fixing them cascades to remove the most bridge dependencies in one change.

### Phase 3: Context Engine Consolidation (Medium-High Risk, High Value)
**Preconditions:** Phase 2 at least partially complete (heartbeat imports migrated). Full understanding of which functions are unique to each version.
**Validation:** Run 2-3 full heartbeat cycles. Compare context output before/after.
**Rollback:** `git revert` + restore old import in heartbeat_preflight.py.

Tasks:
1. **Function-by-function diff** of `scripts/context_compressor.py` (1,499L) vs `clarvis/context/assembly.py` (2,044L) + `clarvis/context/compressor.py` (386L). Determine:
   - Functions unique to scripts/ (need migration to spine)
   - Functions unique to spine (already migrated)
   - Functions in both (determine if diverged or identical)
2. Migrate any remaining unique functions from scripts/ to spine.
3. Update `heartbeat_preflight.py` to import from `clarvis.context` instead of `context_compressor`.
4. Keep `scripts/context_compressor.py` as a bridge wrapper during transition (same pattern as Phase 2).
5. Test end-to-end context generation.

**Why this matters:** This is the real "split-brain" in the codebase. The audit identified it correctly but got the relative sizes wrong (spine may already be the superset).

### Phase 4: Public-Facing Open-Source Restructuring (Low-Medium Risk)
**Preconditions:** Phases 0-2 complete. E2 (secret scan) and E3 (fresh clone setup) from the delivery queue complete.
**Validation:** Fresh clone test (E3). `python3 -m clarvis brain health`.
**Rollback:** `git revert`.

Tasks:
1. Create `experimental/` directory.
2. Move the 5 confirmed-dead scripts there (if not deleted in Phase 1) plus any scripts that have been fully decoupled by Phase 2 migration.
3. Do NOT move scripts that still have production callers (cognitive_load, workspace_broadcast, etc.) even if they "feel" experimental.
4. Add `experimental/README.md` explaining purpose.
5. Clean up `docs/` — move completed plans to `docs/archive/`.
6. Ensure CLAUDE.md, README, ARCHITECTURE docs reflect actual current state.

### Phase 5: Optional Deeper Architectural Cleanup (Higher Risk, Long-Term)
**Preconditions:** Phases 0-3 complete. System stable for 1+ week.
**Validation:** Full test suite + 48h autonomous operation.
**Rollback:** Git branch + revert.

Tasks (each independently optional):
1. Consolidate heartbeat gate: make `scripts/heartbeat_gate.py` call `clarvis.heartbeat.gate` (verify logic matches first).
2. Promote `cognitive_workspace.py` into spine (`clarvis/memory/workspace.py` or `clarvis/context/workspace.py`).
3. Audit the PR subsystem (pr_intake, pr_indexes, pr_rules, pr_factory) — classify as experimental or promote.
4. Evaluate whether `dashboard_server.py` should be revived, retired, or merged into website/server.py.
5. Consider consolidating `scripts/soar_engine.py` into spine (it has 3+ production callers).

---

## Do Not Touch Yet

These modules/subsystems **must not** be restructured, moved, or deleted without extensive verification:

| Module | Reason |
|--------|--------|
| `scripts/heartbeat_preflight.py` (1,347L) | THE runtime entry point. Imports 20+ modules. Any change cascades. |
| `scripts/heartbeat_postflight.py` (1,991L) | Runs after every task. Dense import web. |
| `scripts/context_compressor.py` (1,499L) | May still be authoritative runtime; needs function-level diff vs spine first. |
| `scripts/brain.py` (306L) | ~45 legacy importers. Bridge wrapper but essential. |
| All 8 "thin wrapper" scripts | Active legacy callers. Must not delete until Phase 2 migration complete. |
| `scripts/cognitive_load.py` (573L) | Imported by heartbeat_preflight, cron_autonomous. NOT dead. |
| `scripts/workspace_broadcast.py` (650L) | Imported by both heartbeat pre/postflight. NOT dead. |
| `scripts/hyperon_atomspace.py` (846L) | Imported by heartbeat_postflight. NOT dead. |
| `scripts/soar_engine.py` (827L) | 3+ production callers. Contradictorily classified in audit. |
| `scripts/brain_bridge.py` (287L) | Core heartbeat pipeline (both pre and post). Audit wrongly classified as "weakly wired". |
| `scripts/directive_engine.py` (1,327L) | Heartbeat pipeline. |
| `scripts/obligation_tracker.py` (880L) | Heartbeat pipeline + directive engine. |
| `data/clarvisdb/` (415MB) | The brain. |
| `scripts/cron_env.sh` + `lock_helper.sh` | Sourced by every cron script. |
| `clarvis/brain/` (entire directory) | Core singleton. |

---

## Need Manual Verification

These items have uncertain status that grep alone cannot resolve:

| Item | What's uncertain | How to verify |
|------|-----------------|---------------|
| `scripts/context_compressor.py` vs `clarvis/context/assembly.py` | Which functions are unique to each? Has spine diverged or caught up? | Function-by-function diff |
| `scripts/actr_activation.py` | Imported by `clarvis/brain/hooks.py` but is the hook actually called at runtime? | Add logging to the hook, run a brain store, check logs |
| `scripts/somatic_markers.py` | Imported by heartbeat_preflight in try/except — does the except path silently ignore its absence? | Read the try/except block; test with the file renamed |
| `scripts/theory_of_mind.py` | Imported by session_hook.py — but is the ToM function actually called, or just imported defensively? | Read session_hook.py call sites |
| `scripts/automation_insights.py` | Imported by heartbeat_preflight — but is the function call guarded/optional? | Read the call site in preflight |
| `clarvis/heartbeat/gate.py` vs `scripts/heartbeat_gate.py` | Do they have the same logic? Can spine gate replace scripts/ gate? | Diff the two files |
| `clarvis/cognition/thought_protocol.py` | Large module (1,200L) — is it called beyond CLI and reasoning_chain_hook? | Deeper caller trace |
| `clarvis/metrics/trajectory.py` | "Partially wired" per audit. Does anything write to its data? | Check data files for trajectory records |
| `scripts/dashboard_server.py` | Has systemd unit. Is it intended to be revived or truly superseded by website/? | Ask project owner |
| `scripts/self_report.py` | Not classified in audit. What calls it? | `grep -rl self_report scripts/ clarvis/` |
| `scripts/execution_monitor.py` | Not classified in audit. What calls it? | `grep -rl execution_monitor scripts/ clarvis/` |
| `scripts/marathon_task_selector.py` | Not classified in audit. What calls it? | `grep -rl marathon_task_selector scripts/ clarvis/` |
| `scripts/claude_marathon.sh` | Not classified in audit. What calls it? | `grep -rl claude_marathon scripts/ clarvis/` + crontab check |

---

## Recommended Execution Order

**Week 1 (this week):**
- Phase 0 (labeling/docs) — 1-2 hours, zero risk
- Phase 1 (delete 5 confirmed-dead scripts) — 30 min, very low risk
- Begin verification of "Need Manual Verification" items

**Week 2:**
- Phase 2 start: Migrate heartbeat_preflight.py and heartbeat_postflight.py imports (the highest-impact migration)
- Phase 3 prereq: Produce the context_compressor function-level diff

**Week 3:**
- Phase 2 continued: Migrate cron-called scripts (reflection pipeline)
- Phase 3: Context engine consolidation if diff is clear

**Week 4+ (post-delivery):**
- Phase 2 tail: Remaining legacy import migrations
- Phase 4: Open-source restructuring
- Phase 5: Optional deeper cleanup

---

## Key Corrections to SPINE_USAGE_AUDIT.md

For the record, these are the factual errors found:

1. **§3.1 "8 thin wrappers with zero callers"**: All 8 have active callers. `attention.py` alone has 15+.
2. **§3.2 "13 research prototypes with zero callers"**: Only 5 are truly dead. 8 are imported by production heartbeat scripts.
3. **§3.3 brain_bridge.py "weakly wired"**: Core heartbeat pipeline (both pre and post). Not weak.
4. **§2.3 context_compressor.py "spine is incomplete subset"**: Spine assembly.py is now 2,044L vs scripts 1,499L. Spine may be the superset.
5. **§5 soar_engine.py**: Listed in both "DO NOT REMOVE" and "experimental/move" — contradictory.
6. **Spine module count**: 65, not 77 (overstated by 12).
7. **Crontab entries**: 47, not 52 (overstated by 5).
8. **Spine import count**: 44, not 38 (understated by 6).
9. **§5 task_selector.py**: Audit says "heartbeat_preflight imports it" — actually preflight uses spine directly.
10. **§5 soar_engine.py "5 callers"**: Actual is 3 (inflated).
11. **dashboard_server.py**: Has its own systemd unit — it's an application, not just "0 callers."

---

## Appendix: Verified Deletion Safety Matrix

| Script | Safe to delete now? | Why / Why not |
|--------|-------------------|---------------|
| universal_web_agent.py | **YES** | 0 importers, 0 cron, superseded by clarvis_browser |
| prompt_optimizer.py | **NO** | heartbeat_preflight:127 + heartbeat_postflight:191 import it |
| public_feed.py | **YES** | 0 importers, 0 cron |
| retrieval_quality_report.py | **YES** | 0 importers, 0 cron |
| generate_dashboard.py | **YES** | 0 importers, 0 cron, recently created |
| prediction_review.py | **NO** | evolution_preflight.py:31 imports review_domains |
| gate_check.sh | **NO** | Active: ARCHITECTURE.md, test_spine_phase4.py, clarvis/heartbeat/runner.py |
| attention.py | **NO** | 15+ legacy importers |
| clarvis_confidence.py | **NO** | 4 legacy importers in heartbeat |
| episodic_memory.py | **NO** | 12+ legacy importers + cron_reflection.sh |
| hebbian_memory.py | **NO** | cron_reflection.sh calls it directly |
| memory_consolidation.py | **NO** | cron_reflection.sh + brain.py CLI |
| procedural_memory.py | **NO** | 4 legacy importers in heartbeat |
| thought_protocol.py | **NO** | reasoning_chain_hook imports it |
| working_memory.py | **NO** | safe_update.sh existence check |
| theory_of_mind.py | **NO** | session_hook.py imports it |
| cognitive_load.py | **NO** | heartbeat_preflight + cron_autonomous |
| workspace_broadcast.py | **NO** | heartbeat pre+postflight |
| hyperon_atomspace.py | **NO** | heartbeat_postflight |
| somatic_markers.py | **NO** | heartbeat_preflight (verify try/except) |
| automation_insights.py | **NO** | heartbeat_preflight |
| actr_activation.py | **NO** | clarvis/brain/hooks.py |
| brain_bridge.py | **NO** | heartbeat pre+postflight |
| soar_engine.py | **NO** | 3 production importers |
| dashboard_server.py | **NO** | Has systemd unit, needs decision |
