# Queue Tidy & Fast-Track Report — 2026-04-10

## Queue Cleanup Summary

### Removed / Reworked

1. **[DEAD_CODE_PURGE] — Reworked to [DEAD_CODE_TARGETED_AUDIT]**
   - **Why:** The original task claimed "93% of scripts/ is dead code" and called for deleting 40+ scripts across entire subdirectories (`evolution/*.py`, `agents/*.py`, `tools/*.py`, `hooks/*.py`, `cognition/*.py`, `metrics/*.py`). This was dangerously over-aggressive.
   - **Evidence:** `scripts/evolution/` has 13 .py files, 3 of which are directly called by `cron_reflection.sh` (`failure_amplifier.py`, `meta_learning.py`, `research_to_queue.py`). `scripts/tools/` contains actively used modules (`browser_agent.py`, `context_compressor.py`, `clarvis_browser.py`, `tool_maker.py`). `scripts/hooks/` has `canonical_state_refresh.py` and `goal_hygiene.py` referenced by cron. `scripts/cognition/` has `dream_engine.py` used by cron. Prior purges (2026-04-02, 04-03) already removed ~16 genuinely dead scripts.
   - **Action:** Replaced with `DEAD_CODE_TARGETED_AUDIT` — grep-driven, per-file audit, no bulk directory deletion.

2. **[LLM_BRAIN_REVIEW 2026-04-08] — Merged (duplicate)**
   - **Why:** Identical to `[LLM_BRAIN_REVIEW 2026-04-09]` in P1 Strategic Audit section. Both say "add temporal/recency-boosted retrieval for time-signal queries".
   - **Action:** Removed from SWO section, kept the P1 version.

3. **5 empty P0 section headers removed** (Evening Code Review Bugs, Strategic Audit Emergency Fixes, Evening Code Review Follow-up, Research Pipeline Simplification, LLM Wiki / Obsidian Knowledge Layer). All had their tasks completed/archived but the headers lingered.

4. **3 empty P1 section headers removed** (Queue Architecture v2, Runtime Bootstrap / Path Hygiene, Context/Prompt Pipeline). Same pattern — completed, empty headers.

5. **3 empty P2 section headers removed** (Spine Migration low priority, Benchmarking, Agent Orchestrator).

6. **[SWO_REPO_JUNK_SWEEP] — Updated description**
   - `website/__pycache__/` is NOT git-tracked (already in `.gitignore`). Updated task to remove the misleading reference and focus on actual tracked junk (dead duplicate docs, stale audit artifacts).

### Kept (still valid)

- **[LLM_BRAIN_REVIEW 2026-04-09]** — Temporal indexing gap is real; Probe 6 still returns zero relevant results for recency queries.
- **[DEAD_CODE_TARGETED_AUDIT]** (replacement) — There are likely some genuinely unused scripts remaining, but they need per-file verification.
- **[REASONING_CAPABILITY_SPRINT]** — Last 20 commits are infrastructure; reasoning work is primed but not started.
- **All SWO tasks** — README, website, docs prune, example audit, private file detracking, repo surface audit all remain valid. 80 files in `docs/` (15 execution reports, 8 audits), and real operator files (SOUL.md, USER.md, IDENTITY.md, AGENTS.md) are tracked alongside their `.example` variants.
- **All Fresh-Install / E2E tasks** — Untouched, still valid validation work.
- **All Install Docs tasks** — Untouched, still valid consolidation work.
- **All P2 tasks** — Calibration, CLR autonomy, RAG, cron hygiene, episode recovery, task quality, PI anomaly alert — all still valid.
- **External Challenges** — Kept in Partial Items section.

### New / Refined Tasks

- No new tasks added. The queue was already well-structured; the only needed change was defanging the DEAD_CODE_PURGE.

## Fast-Tracked / Completed Items

### 1. [FIX_BENCHMARK_EPISODE_MEASUREMENT] — DONE

- **What:** The stored `episode_success_rate` was 0.0 in `performance_metrics.json` after a corrupt episodes.json caused EpisodicMemory init to fail during the 05:45 PI refresh.
- **Current state:** Already self-healed — PI=0.9994, episode_success_rate=0.941, action_accuracy=0.967 (377 episodes). A later PI refresh overwrote the bad values.
- **Fix applied:** Changed `benchmark_episodes()` exception handler in `scripts/metrics/performance_benchmark.py:335` to return `{"error": str(e)}` instead of `{"success_rate": 0.0, "action_accuracy": 0.0}`. This ensures the refresh merge preserves previous stored values when EpisodicMemory init fails, instead of overwriting with zeros that tank PI.

### 2. [EPISODE_CORRUPTION_RESILIENCE] — DONE

- **What:** Episodic memory init already had a try/except with `.bak` fallback, but silently swallowed corruption without preserving evidence.
- **Fix applied:** In `clarvis/memory/episodic_memory.py:_load()`:
  - On JSONDecodeError, copies corrupt file to `.corrupt.bak` for forensics before trying recovery.
  - Prints a WARNING to stderr with the error details.
  - Prints recovery count when successfully loading from `.bak`.
- **Tested:** `EpisodicMemory()` loads 377 episodes cleanly. `benchmark_episodes()` returns success_rate=0.942.

## Queue Health After Cleanup

| Metric | Before | After |
|--------|--------|-------|
| P0 tasks | 0 (5 empty headers) | 0 (headers removed) |
| P1 tasks | 46 | 44 (merged 1 duplicate, reworked 1) |
| P2 tasks | 18 | 18 (2 marked done) |
| Partial items | 6 | 6 |
| Empty section headers | 11 | 0 |
| Over-aggressive tasks | 1 (DEAD_CODE_PURGE) | 0 |
| Duplicate tasks | 1 | 0 |

Net effect: queue is leaner, more honest, and two defensive guards are now in place to prevent the PI-collapse failure mode from recurring.
