# Do Not Touch Registry

**Purpose:** Lists high-risk modules that must NOT be moved, renamed, deleted, or refactored without extensive verification. Derived from `SPINE_CLEANUP_PLAN.md` (2026-03-23) verified caller analysis.

**Rule:** Before touching any file listed here, you MUST:
1. Run `grep -rl <filename> scripts/ clarvis/ skills/` to confirm current callers
2. Check `crontab -l | grep <filename>` for direct cron references
3. Verify no heartbeat pipeline imports depend on the file
4. Get explicit approval in QUEUE.md with a migration plan

---

## Category 1: Heartbeat Runtime (CRITICAL)

These files ARE the autonomous execution pipeline. Breaking any of them stops all cron-driven evolution.

| File | Lines | Why untouchable |
|------|-------|-----------------|
| `scripts/heartbeat_preflight.py` | 1,347 | THE runtime entry point. Imports 20+ modules. Every autonomous task flows through this. |
| `scripts/heartbeat_postflight.py` | 1,991 | Runs after every task. Episode encoding, confidence, metrics, digest. Dense import web. |
| `scripts/heartbeat_gate.py` | — | Zero-LLM pre-check. Gate for all autonomous execution. Has spine equivalent but not yet verified identical. |

## Category 2: Bridge Wrappers (8 scripts)

Thin re-export wrappers sitting between 87 legacy `sys.path` imports and the `clarvis.*` spine. Deleting any one breaks production importers. **Safe to remove ONLY after Phase 2 migration completes for ALL their callers.**

| Wrapper | Known callers | Most critical caller |
|---------|--------------|---------------------|
| `scripts/attention.py` | 15+ scripts, `cron_watchdog.sh` | `heartbeat_preflight`, `heartbeat_postflight` |
| `scripts/clarvis_confidence.py` | 4 scripts | `heartbeat_preflight`, `heartbeat_postflight` |
| `scripts/episodic_memory.py` | 12+ scripts, `cron_reflection.sh` | `heartbeat_preflight`, `dream_engine` |
| `scripts/hebbian_memory.py` | `cron_reflection.sh` | Daily 21:00 cron |
| `scripts/memory_consolidation.py` | 2 scripts, `cron_reflection.sh` | `brain.py` CLI, `cron_reflection` |
| `scripts/procedural_memory.py` | 4 scripts | `heartbeat_preflight`, `heartbeat_postflight` |
| `scripts/thought_protocol.py` | 2 scripts | `reasoning_chain_hook` |
| `scripts/working_memory.py` | `safe_update.sh` (existence check) | Update health gate |

## Category 3: Context Engine (Split-Brain Risk)

| File | Lines | Why untouchable |
|------|-------|-----------------|
| `scripts/context_compressor.py` | 1,499 | May still be authoritative runtime (heartbeat imports it). Spine `assembly.py` (2,044L) may be superset but needs function-level diff first. |
| `clarvis/context/assembly.py` | 2,044 | Spine context assembly. Possibly the more complete version now. Cannot consolidate until diff is done. |
| `clarvis/context/compressor.py` | 386 | Spine compressor component. Part of the split-brain. |

## Category 4: Brain Wrappers

| File | Lines | Why untouchable |
|------|-------|-----------------|
| `scripts/brain.py` | 306 | ~45 legacy importers. The most-imported bridge wrapper. |
| `scripts/brain_bridge.py` | 287 | Imported by both `heartbeat_preflight` and `heartbeat_postflight`. Audit wrongly classified as "weakly wired." |
| `clarvis/brain/` | (dir) | Core singleton. The brain. |
| `data/clarvisdb/` | 415MB | The brain's data. ChromaDB + graph store. |

## Category 5: Misclassified "Research" Scripts (Actually Production-Wired)

These were marked as "research prototypes with zero callers" in the SPINE_USAGE_AUDIT — that classification is **wrong**. All have active heartbeat-pipeline importers.

| Script | Lines | Actual caller |
|--------|-------|--------------|
| `scripts/cognitive_load.py` | 573 | `heartbeat_preflight`, `cron_autonomous` |
| `scripts/workspace_broadcast.py` | 650 | `heartbeat_preflight` + `heartbeat_postflight` |
| `scripts/hyperon_atomspace.py` | 846 | `heartbeat_postflight` |
| `scripts/somatic_markers.py` | — | `heartbeat_preflight` (try/except — verify if absence is tolerated) |
| `scripts/automation_insights.py` | — | `heartbeat_preflight` |
| `scripts/theory_of_mind.py` | — | `session_hook.py` → daily cron |
| `scripts/actr_activation.py` | — | `clarvis/brain/hooks.py` |
| `scripts/soar_engine.py` | 827 | 3 production importers. Contradictorily classified in audit. |

## Category 6: Cron Infrastructure

| File | Why untouchable |
|------|-----------------|
| `scripts/cron_env.sh` | Sourced by EVERY cron script. Env bootstrap (PATH, HOME, CLARVIS_WORKSPACE, systemd bus vars). |
| `scripts/lock_helper.sh` | Sourced by cron scripts for mutex locking. |
| All `scripts/cron_*.sh` | Cron orchestrator shells. Each spawns Claude Code with task prompts. |

## Category 7: Other Protected Modules

| File | Lines | Why untouchable |
|------|-------|-----------------|
| `scripts/directive_engine.py` | 1,327 | Heartbeat pipeline. Drives obligation tracking and directive execution. |
| `scripts/obligation_tracker.py` | 880 | Heartbeat pipeline + directive engine integration. |
| `scripts/cognitive_workspace.py` | — | Active Baddeley-inspired buffer manager. Integrated into preflight/postflight/context_compressor. |
| `scripts/dream_engine.py` | — | Daily 02:45 cron. Imports episodic_memory, reasoning_chains. |
| `scripts/prompt_optimizer.py` | — | Imported by `heartbeat_preflight:127` and `heartbeat_postflight:191`. NOT dead. |
| `scripts/prediction_review.py` | — | Imported by `evolution_preflight.py:31`. NOT dead. |

---

## Verification Quick-Reference

```bash
# Check if a script has Python importers
grep -rl "from <module> import\|import <module>" scripts/ clarvis/ skills/

# Check if a script is called from cron
crontab -l | grep <filename>

# Check if a script is sourced from shell
grep -rl "<filename>" scripts/*.sh

# Check heartbeat pipeline dependencies specifically
grep -n "import" scripts/heartbeat_preflight.py | head -40
grep -n "import" scripts/heartbeat_postflight.py | head -40
```

---

## Change Log

| Date | Change |
|------|--------|
| 2026-03-23 | Initial registry created from SPINE_CLEANUP_PLAN.md verified analysis |
