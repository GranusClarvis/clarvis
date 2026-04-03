# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items auto-archived to QUEUE_ARCHIVE.md._

## P0 — Current Sprint

- [ ] [LLM_BRAIN_REVIEW 2026-04-03] [LLM_BRAIN_REVIEW] Delete or archive the two 'Clarvis demo memory' entries (stored 2026-04-02) that contain no useful content — These zero-content memories appear in results for probes 6 and 8, displacing potentially useful results. They are pure noise.
_(P0 delivery window 2026-03-31 completed. Reset for next sprint.)_

### Open-Source Release Blockers (2026-04-03 deep audit)
- [ ] [OSR_MEMORY_DIR_PURGE] Remove `memory/` from git tracking. 241 files contain PII, private repo URLs, execution logs. Steps: add `memory/` to `.gitignore`, run `git rm -r --cached memory/`, then scrub history with `git filter-repo` before public push.
- [ ] [OSR_PII_ANONYMIZE] Anonymize personal identity in committed files. "Patrick"/"Inverse"/"InverseAltruism" appears in USER.md, SOUL.md, AGENTS.md, HEARTBEAT.md, IDENTITY.md, MEMORY.md, and 24+ other tracked files. Replace with configurable placeholders or gitignore the identity files.
- [ ] [OSR_SECRETS_IN_DOCS] Remove wallet address from SOUL.md, internal IPs from SELF.md/IDENTITY.md, bot handles from IDENTITY.md. These are in committed files and would be public on release.
- [ ] [OSR_GIT_HISTORY_SCRUB] Run BFG/git-filter-repo to scrub secrets from git history before public push. Previous audits confirmed secrets were removed from HEAD but may exist in history.

---

## P1 — This Week

### Spine Migration Gaps (2026-04-03 deep audit)
- [ ] [SPINE_PROXY_REPLACEMENT] Replace 5 proxy modules that inject scripts/ via sys.path with real implementations: `clarvis/cognition/reasoning.py`, `clarvis/cognition/somatic_markers.py`, `clarvis/memory/soar.py`, `clarvis/learning/meta_learning.py`, `clarvis/brain/graphrag.py`. Move full implementations from scripts/ into spine; convert scripts to BRIDGE wrappers.
- [ ] [SPINE_HOOK_DEPS_MIGRATE] Migrate 3 hook dependencies from scripts/ into spine: `actr_activation.py` → `clarvis/brain/actr_activation.py`, `retrieval_quality.py` → `clarvis/brain/retrieval_quality.py`, `synaptic_memory.py` → `clarvis/memory/synaptic_memory.py`. Currently imported via sys.path injection in `brain/hooks.py`.
- [ ] [SPINE_COGNITIVE_WORKSPACE] Migrate `scripts/cognitive_workspace.py` (Baddeley working memory model) to `clarvis/memory/cognitive_workspace.py`. Core module used by preflight, postflight, and context_compressor — has no spine presence at all.

### Documentation Accuracy (2026-04-03 deep audit)
- [ ] [DOCS_GAP_AUDIT_REFRESH] Update `docs/OPEN_SOURCE_GAP_AUDIT.md` — marks LICENSE, CONTRIBUTING.md, and CI as missing but all exist now.

### Code Quality (2026-04-03 deep audit)
- [ ] [DEAD_CODE_KNOWLEDGE_SYNTHESIS] Consolidate `scripts/knowledge_synthesis.py` — completely different implementation from `clarvis/context/knowledge_synthesis.py`. The scripts version is imported only by one test. Either remove or unify.
- [ ] [CRON_CANONICAL_REMAINING] Add 3 remaining CLI commands to `cli_maintenance.py` for: `dream_engine.py` → `clarvis maintenance dream`, `brief_benchmark.py` → `clarvis bench brief`, `generate_status_json.py` → `clarvis maintenance status-json`. Then migrate crontab entries.

### Queue Process (2026-04-03 deep audit)
- [ ] [QUEUE_AUTO_ARCHIVE] The queue header says "auto-archived" but archival is manual and 7+ days stale. Either implement a script that moves [x] items to QUEUE_ARCHIVE.md, or change the header to reflect manual cadence.

### Execution Reliability (2026-04-03 cron failure follow-up)
- [x] [CRON_AUTONOMOUS_PROMPT_ASSEMBLY_FIX] Fixed 2026-04-03: replaced unquoted heredocs with printf+quoted-heredoc pattern across 6 scripts; switched prompt delivery from `-p "$(cat)"` to stdin `< file`; added PROMPT_GUARD empty-file check.
- [x] [AUTOMATION_INSIGHTS_NONNULL_GUARD] Fixed 2026-04-03: null-guarded `_extract_action_verb()` in automation_insights.py + null-guarded `.lower()` calls in meta_learning.py, meta_gradient_rl.py, episodic_memory.py. Also repaired null-task episode #394 in episodes.json.
- [x] [CLAUDE_ROUTE_PARITY_AUDIT] Fixed 2026-04-03: audited all 10 Claude-spawning scripts. Fixed unquoted heredocs in cron_autonomous, cron_evening, cron_evolution, cron_implementation_sprint, cron_research. Added PROMPT_GUARD to cron_env.sh run_claude_monitored().
- [x] [CLAUDE_SPAWN_SMOKE_MATRIX] Done 2026-04-03: `scripts/smoke_test_prompt_assembly.sh` — 5-section test covering syntax, unquoted heredoc detection, prompt-guard presence, prompt assembly simulation with special chars, Python null-safety.
- [ ] [MONTHLY_REFLECTION_HEREDOC_FIX] `cron_monthly_reflection.sh` line 67 still uses unquoted `<< ENDDYNAMIC` for variable injection. Low risk (simple vars) but should be migrated to printf pattern for consistency.

---

## P2 — When Idle

### Spine Migration (continued)
- [~] [SPINE_MIGRATION_WAVE3_ORCH] Migrate orchestrator logic from `scripts/` into `clarvis/orch/`. _(Phase 1 done 2026-03-10. Phase 2: scoreboard.py migrated 2026-04-03. Remaining: `pr_factory.py` (905L), `project_agent.py` (3492L), `agent_orchestrator.py` (763L), `orchestration_benchmark.py` (468L). All actively called from cron — large, not trivially wrappable. 2/4 already import clarvis.orch spine modules; the other 2 are standalone. Parking — each is a multi-hour refactor with risk.)_
- [~] [CRON_CANONICAL_ENTRYPOINTS] Migrate cron paths from direct `python3 scripts/X.py` to `python3 -m clarvis ...`. _(2026-04-03: 5 canonical entries now. 3 remaining direct-python entries need new CLI subcommands. ~40 shell-script entries unchanged — those invoke bash orchestrators, not migration candidates.)_
- [ ] [SPINE_REMAINING_LIBRARY_MODULES] ~20 scripts with reusable library logic still in scripts/: cognitive_load, brain_bridge, workspace_broadcast, theory_of_mind, temporal_self, world_models, causal_model, reasoning_chains, failure_amplifier, parameter_evolution, tool_maker, etc. Each is a separate migration task. Low priority — spine is functional without these.

### Benchmarking
- CLR Benchmark implementation from fork: `clarvis/metrics/clr.py` (672 lines, schema v1.0 frozen, 6 dimensions).
- A/B Comparison Benchmark: fix `ab_comparison_benchmark.py` — temp file prompts, 10+ pairs, measure success/quality/duration.

### Agent Orchestrator
- Pillar 2 Phase 5 — Visual Ops Dashboard _(PixiJS-based ops visualization. Design in `docs/CLAW_EMPIRE_VISUALS_NOTES_2026-03-06.md`.)_

### Adaptive RAG Pipeline
_Design: `docs/ADAPTIVE_RAG_PLAN.md` — 4-phase rollout (GATE → EVAL → RETRY → FEEDBACK). Each phase independently useful. Demoted: not needed for delivery._

### Roadmap Gaps (2026-04-03 audit — items from ROADMAP.md with no queue entry)
- [ ] [ROADMAP_CLONE_TEST_VERIFY] Implement clone → test → verify for code changes (ROADMAP Phase 3.2).
- [ ] [ROADMAP_MULTI_AGENT_PARALLEL] Multi-agent parallel execution (ROADMAP Phase 3.4).
- [ ] [ROADMAP_MEMORY_EVOLUTION] A-Mem style memory evolution — supersession, contradiction detection (ROADMAP Phase 5.1). _(Partially implemented in `brain/memory_evolution.py` — verify coverage.)_
- [ ] [ROADMAP_WORKSPACE_PERSISTENCE] Cross-session workspace persistence (ROADMAP Phase 5.5).

---

## Partial Items (tracked, not actively worked)
- [~] [WORKTREE_AUTO_ENABLE] In `cron_autonomous.sh`, auto-detect code-modifying tasks and enable `--isolated` worktree mode. _(Partial 2026-04-03: detection logic added. Full worktree isolation requires restructuring — follow-up needed.)_

---

## NEW ITEMS

### External Challenges
