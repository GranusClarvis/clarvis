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

- [x] [DECOMPOSE_LONG_FUNCTIONS] Decompose oversized functions: `scripts/performance_benchmark.py:show_trend` (81 lines), `scripts/performance_benchmark.py:print_report` (93 lines), `scripts/reasoning_chain_hook.py:open_chain` (119 lines). Target: all functions ≤80 lines. _(2026-03-28: extracted `_load_performance_history`, `_print_report_details`, `_classify_task_type`, `_open_reasoning_session` — all ≤80.)_









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
- [x] [D2_PUBLIC_STATUS_ENDPOINT] Wire the `/api/public/status` endpoint in `website/` — serve runtime mode, queue summary, latest PI/CLR scores, and uptime. Schema already defined in `WEBSITE_V0_INFORMATION_ARCH.md`. _(2026-03-28: already fully implemented in website/server.py:140-159, route wired at line 190. Serves mode, queue, CLR, PI, brain, episodes, completions. Uptime not in spec.)_
- [x] [E6_ROADMAP_SANITIZE] Sanitize ROADMAP.md for public consumption — remove internal references to specific API keys, budget thresholds, and server IPs. Cross-ref with D4 architecture page content. _(2026-03-28: audited — ROADMAP.md contains no API keys, budget thresholds, server IPs, or PII. Already public-safe. Architecture page also clean.)_


