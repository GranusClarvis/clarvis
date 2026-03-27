# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items auto-archived to QUEUE_ARCHIVE.md._

## P0 — 14-Day Delivery Window (Deadline: 2026-03-31)


### Delivery Goal
Presentable Clarvis by 2026-03-31:
- open-source-ready main repo
- working/public-ready website v0
- clean repo boundaries and consolidation plan
- stronger Clarvis brain / recall / context quality
- reliable orchestration and benchmarks
- clearly wired, tested, maintainable structure

### March 24 audit note
_Queue audited on 2026-03-24 evening. Removed 3 completed items (A5_A7, TEMPORAL_RETRIEVAL_FIX, BACKFILL_SENTINEL_FIX). Demoted 2 items (postflight import cleanup, semantic bridges) to P1 — functional via bridges, not release-blocking. 7 items remain on the critical path._

### Milestone C — Repo / Open-Source Readiness (by 2026-03-26) ✅ COMPLETE

### Milestone D — Public Surface (by 2026-03-29)

### Milestone E — Final Validation (by 2026-03-31)


---

## P1 — This Week









### Demoted from P0 (2026-03-24 audit)

### Episode Success Rate Hardening

### Code Quality

### Phi / Benchmarking

---

## P2 — When Idle (Demoted 2026-03-17)

### Spine Migration
- [~] [SPINE_MIGRATION_WAVE3_ORCH] Migrate orchestrator logic from `scripts/` into `clarvis/orch/`. _(Phase 1 done 2026-03-10. Remaining: `pr_factory.py`, `project_agent.py`, `agent_orchestrator.py`, benchmarks/scoreboard.)_
- [~] [LEGACY_SCRIPT_WRAPPER_REDUCTION] Audit high-value Python scripts and convert mature ones into thin wrappers over canonical `clarvis.*` modules. _(2026-03-10: 3 scripts wrapped. Remaining: context_compressor, heartbeat_{pre,post}flight.)_
- [~] [CRON_CANONICAL_ENTRYPOINTS] Migrate cron paths from direct `python3 scripts/X.py` to `python3 -m clarvis ...`. _(3 done. Next: context_compressor gc.)_

### Code Quality

### Agent Orchestrator
- Pillar 2 Phase 5 — Visual Ops Dashboard _(PixiJS-based ops visualization. Design in `docs/CLAW_EMPIRE_VISUALS_NOTES_2026-03-06.md`.)_

### Benchmarking
- CLR Benchmark implementation from fork: `clarvis/metrics/clr.py` (672 lines, schema v1.0 frozen, 6 dimensions).
- A/B Comparison Benchmark: fix `ab_comparison_benchmark.py` — temp file prompts, 10+ pairs, measure success/quality/duration.

### Adaptive RAG Pipeline
_Design: `docs/ADAPTIVE_RAG_PLAN.md` — 4-phase rollout (GATE → EVAL → RETRY → FEEDBACK). Each phase independently useful. Demoted: not needed for 2026-03-31 delivery._

### Research Sessions
_(Completed items archived.)_

---

## NEW ITEMS

### P0 — Found in 2026-03-27 evening scan

- [ ] [BRIEF_COMPRESSION_BOOST] Improve brief compression ratio from 0.503→0.55+ by adding MMR-based redundancy removal to `compress_text()` in `context_compressor.py`. The MMR reranker (lines 75-151) already exists but isn't wired into brief generation — integrate it as a post-extraction dedup pass, and tighten `tfidf_extract` ratio from 0.3 to 0.25 for tiered briefs. _Weakest metric fix._
- [ ] [D2_PUBLIC_STATUS_ENDPOINT] Wire the `/api/public/status` endpoint in `website/` — serve runtime mode, queue summary, latest PI/CLR scores, and uptime. Schema already defined in `WEBSITE_V0_INFORMATION_ARCH.md`. Last greenfield delivery item before 2026-03-31 deadline.
- [x] [CRONTAB_DOCS_DRIFT] Sync CLAUDE.md cron table with actual crontab — added 3 missing entries (brain_eval 06:00, llm_brain_review 06:15, relevance_refresh 02:40), updated date to 2026-03-27.
- [ ] [E6_ROADMAP_SANITIZE] Sanitize ROADMAP.md for public consumption — remove internal references to specific API keys, budget thresholds, and server IPs. Cross-ref with D4 architecture page content. Delivery checklist E6 blocker.
- [x] [BARE_EXCEPT_AUDIT] Fixed 52 silent `except Exception: pass` blocks across 3 priority files: heartbeat_postflight.py (18), performance_benchmark.py (29), reasoning_chain_hook.py (5). All now log via `logging.debug()`. 50 files total have this pattern; remaining are lower priority.


