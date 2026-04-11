# Clarvis Master Improvement Plan — Path to A/A+

**Date**: 2026-04-09
**Author**: Claude Code Opus (executive function)
**Source material**: Quality Review Plan, Phases 1–4, Second-Pass Validation, Remediation Report (2026-04-08/09), plus current-state verification
**Status**: Active — replaces all prior remediation tracking

---

## 0. Current State Summary

### What the review cycle found (2026-04-08)

Four review phases produced **53 raw findings**. The second-pass validation reduced these to **68 validated findings** (after splitting compound ones) and reclassified 7 as false positives, 11 as overstated, and 3 as already fixed during review. A same-day remediation session (2026-04-09) then fixed 6 more high-impact items.

### What has been fixed (as of 2026-04-09)

| # | Fix | Source Finding | Verified |
|---|-----|---------------|----------|
| 1 | Lazy episodic singleton (breaks import cascade) | F1.F2/F5 | Yes — `import clarvis.memory` succeeds |
| 2 | Post-cutover test alignment (15/15 pass) | F1.F4 | Yes |
| 3 | Atomic episode writes (tempfile + os.replace + backup) | F2.1a-f | Yes |
| 4 | cli_brain.py import path fix | F2.2b | Yes |
| 5 | Wiki metadata field fix (ingested_at → ingest_ts) | F2.4a-b | Yes |
| 6 | Secret redaction moved to StoreMixin.store() boundary | F4.2.1-2 | Yes — all 14+ write paths covered |
| 7 | Expanded redaction patterns (sk-proj-, db URLs, password, Bearer case) | F4.2.5-7 | Yes |
| 8 | Watchdog `--alert` enabled in crontab | F4.1.4 | Yes — confirmed in crontab |
| 9 | Synaptic consolidation unstalled (cli_context.py sys.path fix) | F3.4a | Yes — 7/7 hooks register |
| 10 | Cost double-counting removed (impl sprint + research) | F4.6.2 | Yes |
| 11 | Cost path resolution fixed (single canonical costs.jsonl) | F4.6.3 | Yes |
| 12 | Backup SQLite WAL fix (sqlite3 .backup API) | F4.5.1 | Yes |
| 13 | Ablation HARD_SUPPRESS bypass fixed (patches dycp directly) | F2.3a | Yes — needs runtime verification |
| 14 | ChromaDB degraded mode (per-collection isolation) | F4.4.1 | Yes — 496 tests pass |
| 15 | _LazyBrain circuit breaker (3-failure/60s cooldown) | F4.4.2 | Yes |
| 16 | Store fallback on failed collection | F4.4.1 | Yes |

### What was reclassified as not-a-problem

| # | Original Claim | Verdict | Why |
|---|---------------|---------|-----|
| 1 | "31 dead scripts" | Overstated | Only 5–8 confirmed dead. Analysis missed crontab/shell/CLI/dynamic callers. |
| 2 | "Dream Engine is decorative" | False positive | Stores to clarvis-learnings with ONNX embeddings; brain vector search surfaces them in preflight. Retrieval gate explicitly recognizes dream content. |
| 3 | "Workspace Broadcast receivers skip" | False positive | Broadcast text injected directly into Claude Code context brief every heartbeat. Skip is intentional dedup. |
| 4 | "Competing self-model implementations" | Overstated | self_model (capability scoring) and self_representation (latent vectors) are complementary layers with zero data overlap. |
| 5 | "Synaptic weights have NO decay" | Overstated | Decay/pruning/caps exist in SynapticMemory.consolidate(). Real issue was stalled cron (now fixed). |
| 6 | "Knowledge synthesis name collision" | False positive | No runtime collision. Different import paths. |
| 7 | "Hebbian coactivation not in cleanup" | Overstated | Brain CLI `clarvis brain decay` + weekly brain_hygiene covers it. |
| 8 | "Ablation has zero effect" | Overstated | HARD_SUPPRESS was a no-op, but budget zeroing + section stripping worked. Partial bypass, not total. Now fixed. |

### What should NOT be changed (avoid cleanup theater)

| Item | Reason |
|------|--------|
| Bridge stubs in scripts/ | Intentional during spine migration. Delete individually as callers migrate, not en masse. |
| sys.path.insert in 90 scripts | Consequence of migration being in progress. Resolves naturally as spine migration advances. |
| No __init__.py in scripts/ subdirs | scripts/ is not a Python package by design. Adding them would be misleading. |
| Self-model vs self-representation coexistence | Complementary by design (capability scoring vs latent vectors). Consider renaming for clarity, not merging. |
| ACT-R weight sum 1.05 | Masked by [0,1] clamp. Cosmetic. |
| Result budgeting not in recall() | Design choice — external callers handle budgeting. |
| Backward-compat shims in clarvis/orch/ | Documented, intentional, low-risk. |

---

## 1. Current Ratings by Dimension

| Dimension | Rating | Key Strengths | Key Gaps |
|-----------|--------|--------------|----------|
| **Architecture** | B | Strong brain core, hook design, queue engine | Spine migration 16% complete; 60 legacy-import scripts |
| **Runtime Correctness** | B+ | Core paths work; episodes atomic; graph healthy | CLR stuck at 0.87 with no dynamic range; episodes data empty |
| **Operational Fitness** | C+ | Lock system strong; watchdog alerting now enabled | Monitoring covers 12/25+ jobs; cost data 99% estimated; cron_morning hardcodes success |
| **Data Hygiene** | B- | Cleanup infra excellent; synaptic decay unstalled | 36 MB stale backups; sidecar never pruned; episodes data lost |
| **Resilience** | B | ChromaDB degraded mode added; circuit breaker added | No hook timeouts; merge_clusters no undo; no ChromaDB repair in doctor |
| **Observability** | C | Watchdog alerts enabled; dashboard exists | 13+ jobs missing from doctor; cost accuracy poor; cron_morning lies |
| **Value / Signal Quality** | B- | Most cognitive modules confirmed active | CLR retrieval_precision always 1.0; working_memory ablation unmeasurable; Thought Protocol disk output decorative |

**Composite: B- (aiming for A/A+)**

---

## 2. Phased Roadmap (7 Phases)

### Phase 1: Operational Truthfulness (Quick Wins)
**Goal**: Make monitoring/alerting/status honest. No more silent failures or false-positive dashboards.
**Effort**: 1 session. **Risk**: Low. **Mode**: Clarvis direct.

| Task | Finding | Acceptance Criteria | Payoff |
|------|---------|-------------------|--------|
| 1.1 Fix cron_doctor JOBS paths (`scripts/` → `scripts/infra/`) | F4.1.1 | `cron_doctor.py` recovery succeeds for health_monitor, backup_daily, backup_verify | Ops +0.5 |
| 1.2 Add 13 missing jobs to cron_doctor JOBS dict | F4.1.2 | Doctor covers all 25+ scheduled jobs | Ops +1.0 |
| 1.3 Add missing jobs to watchdog check list | F4.1.5 | Watchdog monitors all scheduled jobs | Obs +1.0 |
| 1.4 Fix cron_morning.sh to check Claude exit code | F4.4.5 | `--status` reflects actual exit code | Obs +0.5 |
| 1.5 Fix cron_morning.sh MONITORED_EXIT check | F4.4.10 | Morning postflight conditional on success | Ops +0.3 |
| 1.6 Update CLAUDE.md stale numbers | F1.F11 | Numbers match reality (2912 memories, 93k edges, 165 scripts, 48 cron, 20 skills) | Hygiene +0.3 |
| 1.7 Create/fix cutover doc reference | F1.F6 | `docs/GRAPH_SQLITE_CUTOVER_2026-03-29.md` exists or CLAUDE.md reference is corrected | Hygiene +0.1 |

**Phase 1 rating impact**: Ops C+ → B-, Obs C → C+

---

### Phase 2: Measurement Integrity
**Goal**: Make CLR, ablation, and cost tracking produce real signal.
**Effort**: 2 sessions. **Risk**: Moderate (measurement changes need before/after validation). **Mode**: Claude-assisted.

| Task | Finding | Dep | Acceptance Criteria | Payoff |
|------|---------|-----|-------------------|--------|
| 2.1 Replace trivial CLR retrieval_precision queries with discriminative ones | F2.3c | None | retrieval_precision < 1.0 on at least 1 of 5 queries; score differentiates good vs bad retrieval | Value +1.0 |
| 2.2 Add dynamic-range evaluation to CLR dimensions | F2.3e | None | At least 5/7 CLR dimensions use real data (not fallback defaults) | Value +0.5 |
| 2.3 Validate ablation results post-HARD_SUPPRESS fix | F2.3a | Fix #13 | graph_expansion ablation shows net_score ≠ 0.0 | Value +0.5 |
| 2.4 Fix working_memory ablation (remap spotlight budget key) | F2.3d | 2.3 | working_memory ablation shows ≠ all ties | Value +0.3 |
| 2.5 Wire log_real() into more execution paths | F4.6.1 | None | >20% of cost entries have `estimated: false` within 7 days | Ops +0.5 |
| 2.6 Add budget kill switch (flag file checked by spawners) | F4.6.5 | None | Spawners skip launch when `/tmp/clarvis_budget_freeze` exists | Ops +0.3 |

**Phase 2 rating impact**: Value B- → B+, Ops C+ → B

---

### Phase 3: Data Integrity & Backup
**Goal**: Fix data losses, backup gaps, and growth risks.
**Effort**: 1–2 sessions. **Risk**: Low-moderate. **Mode**: Mixed.

| Task | Finding | Dep | Acceptance Criteria | Payoff |
|------|---------|-----|-------------------|--------|
| 3.1 Rebuild episodes data from brain EPISODES collection | F1.F1 | None | episodes.json has >0 entries; episodic recall returns results | Runtime +0.5 |
| 3.2 Add ~/.openclaw/ config files to backup scope | F4.5.2 | None | openclaw.json, auth.json, budget_config.json in backup output | Resilience +0.5 |
| 3.3 Add .env to backup (encrypted or separate secure store) | F4.5.3 | 3.2 | API keys recoverable from backup | Resilience +0.3 |
| 3.4 Fix CLARVIS_WORKSPACE unbound-variable bug in backup_daily.sh | F4.5.6 | None | No backup gaps from variable error | Ops +0.3 |
| 3.5 Implement sidecar pruning (removed >30d, succeeded >90d) | F3.7b | None | Sidecar entries have bounded growth | Hygiene +0.2 |
| 3.6 Delete 36 MB stale pre-migration backups | F3.4c | None | data/archived/ cleaned | Hygiene +0.1 |
| 3.7 Delete 5 confirmed dead scripts | F3.3c (validated) | None | lockfree_ring_buffer, dashboard_server, ab_comparison_benchmark, wiki_eval, wiki_render removed | Hygiene +0.1 |

**Phase 3 rating impact**: Resilience B → B+, Hygiene B- → B

---

### Phase 4: Safety Hardening
**Goal**: Close the remaining resilience gaps — hook timeouts, merge safety, lock safety, error propagation.
**Effort**: 2 sessions. **Risk**: Moderate (touches hot paths). **Mode**: Claude-assisted.

| Task | Finding | Dep | Acceptance Criteria | Payoff |
|------|---------|-----|-------------------|--------|
| 4.1 Add per-hook timeout (500ms brain, 10s heartbeat) | F3.5a | None | Hung hook does not block recall() or postflight beyond timeout | Resilience +0.5 |
| 4.2 Add hook circuit breaker (disable after 3 consecutive failures) | F3.5c | 4.1 | Repeatedly-failing hook auto-disables; logs warning | Resilience +0.3 |
| 4.3 Archive originals before merge_clusters() deletion | F3.6a | None | Merged memories recoverable from archive JSON | Resilience +0.3 |
| 4.4 Add 30s lock timeout to queue engine fcntl.flock | F3.7a | None | Crashed-process lock does not block queue selection indefinitely | Resilience +0.3 |
| 4.5 Cap _labile_memories dict (TTL or max-size 500) | F2.5a | None | Dict size bounded; old entries evicted | Runtime +0.1 |
| 4.6 Add cross-collection dedup to recall() merge path | F2.5b | None | Same memory text in 2 collections appears once in results | Runtime +0.2 |
| 4.7 Rewrite brain health orphan check for SQLite graph | F2.2a | None | Orphan check queries SQLite, not empty in-memory dict | Obs +0.2 |
| 4.8 Add ChromaDB repair step to cron_doctor | F4.4.7 | None | Doctor can attempt `.recover` or backup restore on ChromaDB failure | Resilience +0.3 |

**Phase 4 rating impact**: Resilience B+ → A-, Runtime B+ → A-

---

### Phase 5: Spine Migration (Batch 1 — High-Impact Scripts)
**Goal**: Migrate the 6 most-called cron scripts from legacy imports to spine imports. Establish the migration pattern.
**Effort**: 2–3 sessions. **Risk**: Moderate (must not break cron). **Mode**: Claude-assisted, with per-script testing.

| Task | Finding | Dep | Acceptance Criteria | Payoff |
|------|---------|-----|-------------------|--------|
| 5.1 Migrate `tools/daily_memory_log.py` (3 cron callers) | F3.3a-b | None | Uses `from clarvis.` imports; all 3 cron jobs succeed | Arch +0.3 |
| 5.2 Migrate `tools/digest_writer.py` (4 cron callers) | F3.3a-b | None | Uses spine imports; 4 cron jobs succeed | Arch +0.3 |
| 5.3 Migrate `metrics/performance_benchmark.py` (2 callers) | F3.3a-b | None | Uses spine imports; pi_refresh succeeds | Arch +0.2 |
| 5.4 Migrate `hooks/session_hook.py` (2 callers) | F3.3a-b | None | Uses spine imports; morning/reflection cron succeed | Arch +0.2 |
| 5.5 Migrate `cognition/absolute_zero.py` (2 callers) | F3.3a-b | None | Uses spine imports; absolute_zero cron succeeds | Arch +0.2 |
| 5.6 Migrate `brain_mem/brain.py` (2 callers) | F3.3a-b | None | Uses spine imports; research/strategic_audit succeed | Arch +0.2 |
| 5.7 Delete bridge stubs for migrated scripts | F3.3a | 5.1-5.6 | No bridge stubs remain for migrated scripts | Arch +0.1 |

**Phase 5 rating impact**: Arch B → B+

---

### Phase 6: Observability & Recovery Completeness
**Goal**: Close monitoring gaps, add outer timeouts, fix error propagation.
**Effort**: 1–2 sessions. **Risk**: Low. **Mode**: Mixed.

| Task | Finding | Dep | Acceptance Criteria | Payoff |
|------|---------|-----|-------------------|--------|
| 6.1 Add set_script_timeout to all major spawners | F4.1.8 | None | autonomous, morning, evolution, research, impl_sprint all have outer timeout | Ops +0.5 |
| 6.2 Fix watchdog post-recovery recheck (sleep 2 → 30) | F4.1.10 | None | Recovery recheck allows adequate startup time | Ops +0.1 |
| 6.3 Add cron_morning.sh dream_engine to watchdog+doctor | F4.1.3 | Phase 1 | Dream engine failures detected and recoverable | Ops +0.1 |
| 6.4 Fix cron_report inline PID locks (add /proc/cmdline guard) | F4.1.9 | None | Report scripts resilient to PID recycling | Ops +0.1 |
| 6.5 Add redaction min-length reduction (20 → 8 for passwords/keys) | F4.2.5-7 | None | Short real secrets caught; false-positive rate < 1% | Resilience +0.2 |
| 6.6 Add Stripe/Slack/JWT patterns to redaction | F4.2.8 | None | sk_live_, xoxb-, JWT patterns matched | Resilience +0.1 |
| 6.7 Wire Thought Protocol disk output to consumer OR remove disk logging | F3.1b | Decide | thought_log.jsonl either consumed or not written | Value +0.1 |
| 6.8 Use UTC for daily task cap boundary | F3.7c | None | No midnight race condition | Ops +0.1 |

**Phase 6 rating impact**: Ops B → B+, Obs C+ → B

---

### Phase 7: Spine Migration (Batch 2) + Polish
**Goal**: Continue spine migration, update docs, reach A- across all dimensions.
**Effort**: 3–5 sessions (can be spread over time). **Risk**: Low-moderate. **Mode**: Claude-assisted.

| Task | Finding | Dep | Acceptance Criteria | Payoff |
|------|---------|-----|-------------------|--------|
| 7.1 Migrate next 10 highest-impact scripts to spine imports | F3.3a | Phase 5 | 10 more scripts use `from clarvis.` imports | Arch +0.5 |
| 7.2 Verify and delete 3 likely-dead scripts | F3.3c | None | graphrag_communities, wiki_retrieval, graph_cutover removed after caller verification | Hygiene +0.1 |
| 7.3 Add full-chain incremental restore to backup_restore.sh | F4.5.5 | Phase 3 | Restore chains incrementals correctly | Resilience +0.2 |
| 7.4 Add offsite git push to backup | F4.5.9 | None | Weekly automated `git push` to GitHub | Resilience +0.2 |
| 7.5 Add concurrent-access retry wrapper to graph_store_sqlite.py | F4.3.4 | None | OperationalError retried 2-3x with backoff | Resilience +0.1 |
| 7.6 Increase busy_timeout during maintenance windows | F4.3.5 | None | Maintenance operations use 15s timeout | Resilience +0.1 |
| 7.7 Add pre-consolidation snapshot | F3.6b | None | Affected collection IDs dumped before consolidation; restorable on crash | Resilience +0.1 |
| 7.8 Full docs refresh (CLAUDE.md, SELF.md version, AGENTS.md) | F1.F11 | All phases | All doc claims match current reality | Hygiene +0.2 |

**Phase 7 rating impact**: Arch B+ → A-, Resilience A- → A, Hygiene B → B+

---

## 3. Projected Ratings After Full Execution

| Dimension | Current | After Ph 1-2 | After Ph 3-4 | After Ph 5-7 | Target |
|-----------|---------|-------------|-------------|-------------|--------|
| **Architecture** | B | B | B | A- | A |
| **Runtime** | B+ | B+ | A- | A- | A |
| **Ops** | C+ | B | B | B+ | A- |
| **Hygiene** | B- | B- | B | B+ | A- |
| **Resilience** | B | B | A- | A | A |
| **Observability** | C | C+ | C+ | B | B+ |
| **Value/Signal** | B- | B+ | B+ | B+ | A- |
| **Composite** | **B-** | **B** | **B+** | **A-** | **A** |

**Note**: Reaching A+ requires additional work beyond this plan — particularly completing spine migration to >60% (currently 16%), adding integration tests for cron pipelines, and establishing automated regression detection. Those are natural follow-ons after this plan is executed.

---

## 4. Execution Guidelines

### Clarvis Direct vs Claude-Assisted

| Mode | When | Examples |
|------|------|---------|
| **Clarvis direct** | Config edits, crontab changes, doc updates, script deletion, file moves | Phases 1, 3.6-3.7, 6.3 |
| **Claude-assisted** | Code changes to hot paths, new mechanisms, migration with testing | Phases 2, 4, 5, 6.5-6.6, 7.1 |

### Dependencies

```
Phase 1 (standalone — do first)
Phase 2 (standalone — can parallel with Phase 1)
Phase 3 (standalone — can parallel with Phase 2)
Phase 4 (after Phase 1 for doctor coverage)
Phase 5 (standalone — can start after Phase 1)
Phase 6 (after Phases 1 + 4)
Phase 7 (after Phases 5 + 6)
```

### Verification Protocol

After each phase:
1. Run `python3 -m pytest tests/ -x -q` — no new failures
2. Run `python3 -m clarvis brain health` — healthy status
3. Run `python3 -m clarvis brain stats` — numbers sane
4. For cron changes: verify with `crontab -l` and `cron_doctor.py --dry-run`
5. For measurement changes: compare before/after CLR/ablation output

---

## 5. What Remains Truly Critical (6 items)

These are the only items that could cause data loss or silent corruption if not addressed:

1. **Episodes data empty** — episodic memory has zero historical entries. Rebuild from brain EPISODES collection. (Phase 3.1)
2. **Secret redaction min-length gap** — patterns require 20+ char values. Short real secrets pass through. Mitigated by the fact that no actual secrets have been found in brain data. (Phase 6.5)
3. **Gateway config not backed up** — machine loss = manual reconstruction. (Phase 3.2)
4. **CLARVIS_WORKSPACE unbound variable** — causes periodic total backup failures. (Phase 3.4)
5. **No hook timeouts** — hung hook blocks recall() or postflight indefinitely. (Phase 4.1)
6. **merge_clusters() deletes originals with no undo** — could lose nuanced knowledge. (Phase 4.3)

---

## Appendix A: Complete Finding Status Tracker

### FIXED (16 items) ✓

| ID | Description | Fixed By | Verified |
|----|------------|----------|----------|
| F1.F2 | Episodic singleton at import time | Phase 1 review | ✓ |
| F1.F4 | Dual-write tests stale | Phase 1 review | ✓ |
| F1.F5 | clarvis.memory import cascade | Phase 1 review | ✓ |
| F2.1a-f | Episodes non-atomic writes | Phase 2 review | ✓ |
| F2.2b | cli_brain.py import path | Phase 2 review | ✓ |
| F2.4a-b | Wiki metadata field mismatch | Phase 2 review | ✓ |
| F4.2.1-2 | Secret redaction bypass (14+ paths) | Phase 4 review | ✓ |
| F4.2.5-7 | Redaction pattern gaps (partial) | Phase 4 review | ✓ |
| F4.1.4 | Watchdog --alert not enabled | Remediation Q1 | ✓ |
| F3.4a | Synaptic consolidation stalled | Remediation Q6 | ✓ |
| F4.6.2 | Cost double-counting | Remediation Q10 | ✓ |
| F4.6.3 | Two costs.jsonl files | Remediation T11 | ✓ |
| F4.5.1 | Backup SQLite WAL corruption | Remediation T6 | ✓ |
| F2.3a | Ablation HARD_SUPPRESS bypass | Remediation T2 | Needs runtime verify |
| F4.4.1 | No ChromaDB degraded mode | Remediation S1 | ✓ |
| F4.4.2 | _LazyBrain no circuit breaker | Remediation T5 | ✓ |

### FALSE POSITIVE / NOT-A-PROBLEM (9 items) ✗

| ID | Original Claim | Why Not a Problem |
|----|---------------|-------------------|
| F3.1a | Dream Engine decorative | Consumed via brain vector search + retrieval gate |
| F3.1c | Workspace Broadcast skips | Core heartbeat component; skip is intentional dedup |
| F3.2a | Competing self-model impls | Complementary by design, zero data overlap |
| F3.2b | Knowledge synthesis collision | No runtime collision; different import paths |
| F3.3c | 31 dead scripts | Only 5-8 confirmed; analysis missed many callers |
| F3.4b | Hebbian not in cleanup | Brain CLI decay + weekly hygiene covers it |
| F2.5c | Cache eviction O(n) | Harmless at n=50 |
| F2.5d | ACT-R weights 1.05 | Masked by clamp; cosmetic |
| F2.5e | Result budgeting not in recall() | Design choice; external callers handle it |

### OPEN — Assigned to Phases (37 items)

| ID | Description | Phase | Priority |
|----|------------|-------|----------|
| F4.1.1 | cron_doctor JOBS wrong paths | 1 | Quick win |
| F4.1.2 | 13+ jobs absent from doctor | 1 | Quick win |
| F4.1.5 | Watchdog monitors only 12/25+ | 1 | Quick win |
| F4.4.5 | cron_morning hardcodes success | 1 | Quick win |
| F4.4.10 | cron_morning no MONITORED_EXIT check | 1 | Quick win |
| F1.F11 | CLAUDE.md stale numbers | 1 | Quick win |
| F1.F6 | Missing cutover doc reference | 1 | Quick win |
| F2.3c | CLR retrieval_precision stuck 1.0 | 2 | High |
| F2.3e | CLR insufficient dynamic range | 2 | High |
| F2.3d | Working memory ablation unmeasurable | 2 | Medium |
| F4.6.1 | 99% cost entries estimated | 2 | Medium |
| F4.6.5 | No budget kill switch | 2 | Medium |
| F1.F1 | Episodes data empty (was corrupted) | 3 | Critical |
| F4.5.2 | Gateway config not backed up | 3 | Critical |
| F4.5.3 | .env not backed up | 3 | High |
| F4.5.6 | CLARVIS_WORKSPACE unbound variable | 3 | High |
| F3.7b | Sidecar entries never pruned | 3 | Medium |
| F3.4c | 36 MB stale backups | 3 | Low |
| F3.3c | 5 confirmed dead scripts | 3 | Low |
| F3.5a | No hook timeout | 4 | High |
| F3.5c | No hook circuit breaker | 4 | Medium |
| F3.6a | merge_clusters no undo | 4 | High |
| F3.7a | Queue engine no lock timeout | 4 | High |
| F2.5a | _labile_memories unbounded | 4 | Medium |
| F2.5b | No cross-collection dedup | 4 | Medium |
| F2.2a | Orphan check silent no-op | 4 | Low |
| F4.4.7 | No ChromaDB repair in doctor | 4 | Medium |
| F3.3a | 60 scripts legacy imports (batch 1) | 5 | Medium |
| F4.1.8 | No outer timeout on spawners | 6 | High |
| F4.1.10 | Watchdog recheck too short | 6 | Low |
| F4.1.3 | Dream engine not in watchdog/doctor | 6 | Low |
| F4.1.9 | Report PID locks no /proc guard | 6 | Low |
| F4.2.5-7 | Redaction min-length still 20 | 6 | Medium |
| F4.2.8 | Stripe/Slack/JWT not matched | 6 | Low |
| F3.1b | Thought Protocol disk output decorative | 6 | Low |
| F3.7c | Daily cap midnight race | 6 | Low |
| F3.3a | Spine migration batch 2 (10 scripts) | 7 | Medium |

---

## Appendix B: Queue-Ready Task Blocks

These tasks can be added to QUEUE.md systematically. Format matches the existing queue convention.

```
## P0 — Current Sprint

- [ ] [FIX_CRON_DOCTOR_PATHS] Fix cron_doctor JOBS dict: wrong paths for health_monitor, backup_daily, backup_verify (scripts/ → scripts/infra/). Add all 13 missing jobs. Acceptance: doctor --dry-run succeeds for all 25+ jobs. [cron, doctor, monitoring]
- [ ] [FIX_WATCHDOG_COVERAGE] Expand watchdog check list to cover all 25+ scheduled jobs (impl_sprint, strategic_audit, orchestrator, monthly_reflection, graph_*, chromadb_vacuum, absolute_zero, llm_brain_review, brain_eval). [cron, watchdog, monitoring]
- [ ] [FIX_MORNING_STATUS] Fix cron_morning.sh: check Claude exit code instead of hardcoding --status success; add MONITORED_EXIT check. [cron, morning, ops]
- [ ] [REBUILD_EPISODES_DATA] Rebuild episodes.json from brain EPISODES collection (367 entries in clarvis-episodes). Verify episodic recall returns results after rebuild. [episodes, data, memory]

## P1 — Next Sprint

- [ ] [CLR_DYNAMIC_RANGE] Replace trivial CLR retrieval_precision queries with discriminative test queries. Ensure ≥5/7 CLR dimensions use real data. Target: retrieval_precision < 1.0 and CLR score has measurable variance. [clr, metrics, measurement]
- [ ] [ABLATION_RUNTIME_VERIFY] Run full ablation cycle after HARD_SUPPRESS fix. Verify graph_expansion shows differentiated net_score. Fix working_memory spotlight budget key. [ablation, metrics, measurement]
- [ ] [BACKUP_SCOPE_EXPANSION] Add ~/.openclaw/ config files (openclaw.json, auth.json, budget_config.json) to backup scope. Fix CLARVIS_WORKSPACE unbound-variable bug. Add .env to encrypted backup. [backup, config, resilience]
- [ ] [HOOK_TIMEOUT_CIRCUIT_BREAKER] Add per-hook timeout (500ms brain, 10s heartbeat). Add circuit breaker: disable hook after 3 consecutive failures with logged warning. [hooks, safety, resilience]
- [ ] [MERGE_CLUSTERS_SAFETY] Archive original memories before merge_clusters() deletion. Write originals to archive JSON, then delete. [consolidation, safety, data]
- [ ] [QUEUE_LOCK_TIMEOUT] Add 30s lock timeout to queue engine fcntl.flock with fallback (skip selection rather than hang). [queue, locks, resilience]
- [ ] [SPAWNER_OUTER_TIMEOUT] Add set_script_timeout to all major spawners (autonomous, morning, evolution, research, impl_sprint). [cron, timeout, ops]

## P2 — Planned

- [ ] [SPINE_MIGRATION_BATCH1] Migrate 6 highest-impact scripts to spine imports: daily_memory_log, digest_writer, performance_benchmark, session_hook, absolute_zero, brain.py. Test each cron caller. [spine, migration, architecture]
- [ ] [COST_REAL_DATA] Wire log_real() into execution paths where OpenRouter returns actual cost. Add budget kill switch flag file. Target: >20% real entries in 7 days. [cost, tracking, ops]
- [ ] [CHROMADB_REPAIR_IN_DOCTOR] Add ChromaDB repair step to cron_doctor (sqlite3 .recover, backup restore fallback). [doctor, chromadb, resilience]
- [ ] [BRAIN_HEALTH_SQLITE_ORPHAN] Rewrite brain health orphan check to query SQLite graph store instead of empty in-memory dict. Add verify_referential_integrity() to GraphStoreSQLite. [brain, health, sqlite]
- [ ] [RECALL_DEDUP_LABILE_CAP] Add cross-collection dedup to recall() merge path. Cap _labile_memories at 500 entries with TTL eviction. [brain, recall, memory]
- [ ] [REDACTION_MIN_LENGTH] Reduce redaction min-length from 20 to 8 chars for password/key patterns. Add Stripe/Slack/JWT patterns. Verify false-positive rate < 1%. [redaction, security]
- [ ] [DEAD_SCRIPT_CLEANUP] Delete 5 confirmed dead scripts (lockfree_ring_buffer, dashboard_server, ab_comparison_benchmark, wiki_eval, wiki_render). Verify 3 likely-dead (graphrag_communities, wiki_retrieval, graph_cutover). [cleanup, hygiene]
- [ ] [SIDECAR_PRUNING] Implement sidecar pruning: remove 'removed' entries >30d, 'succeeded' >90d. [queue, cleanup, hygiene]
```

---

## Appendix C: What Gets Us from A- to A+

After executing Phases 1–7, the system will be at A-. To reach A/A+:

1. **Spine migration >60%** — Continue migrating scripts in batches of 10. At current pace, ~30 sessions to reach 60%.
2. **Integration tests for cron pipelines** — Each cron job should have a test that exercises its full path (preflight → execute → postflight) with mocked Claude output.
3. **Automated regression detection** — CLR/ablation history should trigger alerts when scores drop >0.05 between runs.
4. **Offsite backup** — Weekly `git push` + encrypted DB snapshots to remote storage.
5. **Full incremental restore chain** — `backup_restore.sh` correctly chains incrementals.
6. **Observability dashboard** — Real-time cron status, brain health, cost tracking in one view (the `generate_status_json.py` foundation exists).

These are stretch goals. The 7-phase plan above covers everything needed for A-.
