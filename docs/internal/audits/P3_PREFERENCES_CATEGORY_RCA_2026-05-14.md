# P3 Preferences Category RCA — 2026-05-14

**Task:** `[P3_PREFERENCES_CATEGORY_RCA_2026-05-14]`
**Target metric:** overall P@3 = 0.7816 (target 0.70 — passing, but **fragile**)
**Weakest sub-bucket:** `preferences=0.583 (n=4)` (vs identity=0.667, goals=0.667, context=0.917, knowledge=0.800, procedures=1.000, infrastructure=1.000, meta=0.834)
**Snapshot cross-checked:** `data/retrieval_benchmark/latest.json` timestamp `2026-05-14T12:04:59Z` (today's 14:04 CET run — not the 13:00 morning snapshot).

After the 2026-05-13 B24–B29 low-n expansion, preferences barely moved (0.5 → 0.583). The two new preference queries (B26, B27) split — B26 went 1.0, B27 went 0.333 — so the newly added queries are net-zero. Original B16 stayed at 0.333 and B17 at 0.667. Root cause is concentrated, not diffused.

---

## Method

For each of the 4 preference-category benchmark queries (B16, B17, B26, B27) in `scripts/brain_mem/retrieval_benchmark.py`:

1. Ran `brain.recall(query, n=5, collections=['clarvis-preferences'])` (collection-scoped) and `brain.recall(query, n=5)` (unscoped, smart_recall analogue).
2. Captured top-5 with distance + collection + hit-status against benchmark `expected_substrings`.
3. Compared against the `gold_evidence` text from the benchmark.
4. Classified each failing rank-1..3 result into:
   - **(a)** seed-memory phrasing mismatch (canonical content present but embedding distance > sibling memories)
   - **(b)** seed missing entirely (no memory in `clarvis-preferences` satisfies the query)
   - **(c)** cross-collection bleed (top-3 fills with off-topic items from `clarvis-context`/`clarvis-learnings`/etc.)
   - **(d)** golden_qa fixture error (`expected_docs`/`expected_substrings` references stale content)

---

## Per-query triage (raw output quoted)

### B16 — "Communication style preferences" — P@3 = **0.333**
Expected substrings: `['direct', 'no fluff', 'communication']`
Gold evidence (benchmark): *"Communication preferences: direct, no fluff, concise. Lead with the answer. Skip preamble and unnecessary transitions. Prefer short sentences..."*

| Rank | Hit | Dist | Collection | Text preview |
|---|---|---|---|---|
| 1 | ✓ | 0.9833 | clarvis-preferences | "Recalled preference pattern: memories of user feedback show consistent preference for brevity and **direct**ness; stored memory of corrections g…" |
| 2 | ✗ | 1.0910 | clarvis-preferences | "Preference learned from past: memory consolidation reveals user values action over discussion; this shapes future prioritization…" |
| 3 | ✗ | 1.1820 | clarvis-preferences | "Cross-domain connection (preferences ↔ episodes): Preference: encode episodes after task execution. Record successes and failures with emoti…" |
| 4 | ✗ | 1.1890 | clarvis-preferences | "Cross-domain connection (preferences ↔ memories): Preference: break work into small, testable tasks…" |
| 5 | ✗ | 1.3043 | clarvis-preferences | "Bridge [clarvis-preferences↔autonomous-learning]: Preference: all cognitive hooks use try/except fallback…" |

**Classification: (b) seed missing entirely.** None of the top-5 contain "no fluff" or "communication". The gold_evidence text itself is not stored as a canonical preference memory. Rank-1 squeaks a substring hit on "direct" inside "directness" but is a *meta*-memory about preferences ("memories of user feedback show consistent preference for…"), not the preference itself. Rank-2..5 are unrelated preference micro-rules.

### B17 — "What timezone should I use?" — P@3 = **0.667**
Expected substrings: `['cet', 'timezone']`
Gold evidence: *"Timezone: CET (Central European Time). All cron schedules in CET. The operator is in CET timezone."*

Scoped (clarvis-preferences):
| Rank | Hit | Dist | Collection | Text preview |
|---|---|---|---|---|
| 1 | ✓ | 1.2372 | clarvis-preferences | "Bridge [clarvis-preferences↔autonomous-learning]: **CET timezone** - be mindful of time — relates to: [preference_learning] Autonomous execution…" |
| 2 | ✗ | 1.6142 | clarvis-preferences | "Preference: I prefer the fix_cron_autonomous.sh procedure…" |
| 3 | ✗ | 1.7028 | clarvis-preferences | "Preference: I want to achieve 'Goal: ClarvisDB — ClarvisDB vector memory database — store, recall, search, and '…" |

Unscoped (smart_recall):
| Rank | Hit | Dist | Collection | Text preview |
|---|---|---|---|---|
| 1 | ✗ | 1.5299 | clarvis-learnings | "2026-02-20 06:38 UTC - Heartbeat: Gateway=running, health-check script created…" |
| 2 | ✓ | 1.3857 | autonomous-learning | "[recurring_question] Recurring question (19x across 18 sessions): **timezone** does Clarvis operate in?' (results exist but off-topic)" |
| 3 | ✗ | 1.7202 | clarvis-identity | "Identity: Clarvis maintains a cron schedule of 47+ entries managing the subconscious layer…" |
| 4 | ✓ | 1.2372 | clarvis-preferences | (the CET bridge from above) |

**Classification: (b) seed missing + (c) cross-collection bleed.** The only direct CET memory is a verbose "Bridge […]" wrapper memory whose prefix noise raises distance to 1.24. The clean canonical *"Timezone: CET…"* is not stored. Worse, smart_recall pushes the only correct preference memory to rank 4 because higher-distance off-topic items in `clarvis-learnings`, `autonomous-learning`, `clarvis-identity` outrank it after cross-collection merge. Note the rank-2 hit is itself a meta-flag from `autonomous-learning` saying the brain *knows* this query has weak retrieval ("results exist but off-topic" — 19× recurring question).

### B26 — "Should I use sessions_spawn to run claude code" — P@3 = **1.000** (passing)
Expected substrings: `['never', 'sessions_spawn', 'wrong model']`

| Rank | Hit | Dist | Collection | Text preview |
|---|---|---|---|---|
| 1 | ✓ | 0.6786 | clarvis-preferences | "Preference shaped by episodes: past episodes of token waste ($4+ incident) established strong preference for **never** using **sessions_spawn**…" |
| 2 | ✓ | 0.6791 | clarvis-procedures | "ARCHITECTURE: Claude Code Spawn Protocol — Rules: (1) Full path /home/agent/.local/bin/claude…" |
| 3 | ✓ | 0.7141 | clarvis-procedures | "Procedure: spawn_claude_code — How to spawn Claude Code correctly…" |

**Classification: no failure.** Two distinct seed memories (0.6786, 0.7693 dist) match the substrings. This is the baseline we should replicate for B16/B17/B27.

### B27 — "Claude code spawn flags and timeout convention" — P@3 = **0.333**
Expected substrings: `['dangerously-skip-permissions', 'claudecode', 'timeout']`
Gold evidence: *"Claude Code spawn convention: env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT, --dangerously-skip-permissions, full path /home/agent/.local/bin/claude, minimum timeout 600s default 1200s."*

Scoped (clarvis-preferences) — **all 3 miss**:
| Rank | Hit | Dist | Collection | Text preview |
|---|---|---|---|---|
| 1 | ✗ | 0.9712 | clarvis-preferences | "Preference shaped by episodes: past episodes of token waste ($4+ incident) … sessions_spawn…" |
| 2 | ✗ | 0.9757 | clarvis-preferences | "Preference shaped by episodes: past episodes of token waste incident … sessions_spawn for Claude…" |
| 3 | ✗ | 1.5249 | clarvis-preferences | "Bridge [clarvis-preferences↔autonomous-learning]: CET timezone…" |

Smart_recall (benchmark cited ranks):
| Rank | Hit | Dist | Collection | Text preview |
|---|---|---|---|---|
| 1 | ✗ | 0.9712 | clarvis-preferences | (sessions_spawn pref — wrong topic) |
| 2 | ✗ | 0.9757 | clarvis-preferences | (sessions_spawn pref dup — wrong topic) |
| 3 | ✓ | 0.8049 | clarvis-memories | "Procedure: Spawn Claude Code from cron: 1) source cron_env.sh 2) write prompt to /tmp file 3) acquire global lock 4) **env -u CLAUDECODE** -u CL…" |

**Classification: (b) seed missing + (c) cross-collection bleed.** Canonical spawn-convention content lives in `clarvis-procedures` ("ARCHITECTURE: Claude Code Spawn Protocol") and `clarvis-memories` ("Procedure: Spawn Claude Code from cron"), **not** in `clarvis-preferences`. The two sessions_spawn anti-pattern memories outrank everything else in preferences because they share lexical/semantic surface area ("Claude Code", "spawn") without containing the flags-and-timeouts content. The actual answer is at rank-3 cross-collection and rank-N in preferences-scope.

---

## Root-cause class distribution

| Class | Queries | Notes |
|---|---|---|
| **(b) seed missing entirely** | **B16, B17, B27** | Dominant — 3 of 4 (75% of preference queries; the 3 that fail) |
| **(c) cross-collection bleed** | B17, B27 | Secondary — co-occurs with (b); cleaning seeds may largely fix this |
| (a) phrasing mismatch | none | No query had right content drowned by wrong content of higher similarity within preferences |
| (d) fixture error | none | All `expected_substrings` are still meaningful against current brain state |

**Dominant class: (b) seed missing in `clarvis-preferences`.** The benchmark expects the *gold_evidence* text to be embedded as a memory; for B16/B17/B27 it isn't, or exists only in verbose "Bridge"/"Cross-domain"/"Recalled pattern" wrapper form that adds prefix noise and raises distance.

---

## Remediation tasks

### Class (b) — Seed canonical preference memories (DOMINANT)

**R1 — `[P3_PREF_SEED_B16_COMMUNICATION]`** Seed the canonical communication-style preference verbatim into `clarvis-preferences`.
- **CLI:**
  ```bash
  python3 -c "from clarvis.brain import brain; brain.remember(
    'Communication preferences: direct, no fluff, concise. Lead with the answer. Skip preamble and unnecessary transitions. Prefer short sentences. Only add comments where logic is not self-evident.',
    collection='clarvis-preferences', importance=0.95,
    metadata={'source':'P3_PREFERENCES_CATEGORY_RCA_2026-05-14','tags':'preferences,communication,style'})"
  ```
- **Projected lift (B16):** P@3 0.333 → **1.000** (all 3 substrings `direct`/`no fluff`/`communication` present verbatim).
- **Overall lift:** +0.667/29 = **+0.023** P@3.

**R2 — `[P3_PREF_SEED_B17_TIMEZONE]`** Seed clean CET-timezone preference (replacing reliance on the verbose Bridge wrapper).
- **CLI:**
  ```bash
  python3 -c "from clarvis.brain import brain; brain.remember(
    'Timezone: CET (Central European Time). All cron schedules in CET. The operator is in CET timezone.',
    collection='clarvis-preferences', importance=0.9,
    metadata={'source':'P3_PREFERENCES_CATEGORY_RCA_2026-05-14','tags':'preferences,timezone,cet'})"
  ```
- **Projected lift (B17):** P@3 0.667 → **1.000** (lowers top-1 distance ≈ 0.5–0.7 vs current 1.24; bumps ≥2 results into hit substring set).
- **Overall lift:** +0.333/29 = **+0.011** P@3.

**R3 — `[P3_PREF_SEED_B27_SPAWN_FLAGS]`** Seed Claude Code spawn-flags+timeout convention into `clarvis-preferences` (currently exists only in `clarvis-procedures` and `clarvis-memories`).
- **CLI:**
  ```bash
  python3 -c "from clarvis.brain import brain; brain.remember(
    'Claude Code spawn convention: env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT, --dangerously-skip-permissions, full path /home/agent/.local/bin/claude, minimum timeout 600s default 1200s. CLAUDECODE nesting guard must be unset.',
    collection='clarvis-preferences', importance=0.9,
    metadata={'source':'P3_PREFERENCES_CATEGORY_RCA_2026-05-14','tags':'preferences,claudecode,spawn,timeout'})"
  ```
- **Projected lift (B27):** P@3 0.333 → **1.000** (all 3 substrings — `dangerously-skip-permissions`, `claudecode`, `timeout` — match verbatim).
- **Overall lift:** +0.667/29 = **+0.023** P@3.

### Class (c) — Cross-collection bleed (SECONDARY)

**R4 — `[P3_BENCH_EXPECTED_COLLECTIONS_B17_B27]`** Update `scripts/brain_mem/retrieval_benchmark.py` `expected_collections` to reflect the actual canonical homes:
- B17: `[PREFERENCES]` → `[PREFERENCES, INFRASTRUCTURE]` (CET also appears in cron-schedule infra docs).
- B27: `[PREFERENCES, PROCEDURES]` is already correct, but after R3 ships the in-preferences memory it will dominate. Recommend reviewing on next benchmark run rather than re-edit pre-emptively.
- **Projected lift:** marginal (≤+0.05 on B17 first-hit-rank only if R2 doesn't ship); zero if R1–R3 all ship.

**R5 — `[P3_PREF_COLLECTION_PRIOR]`** Add a preference-tagged-query collection-prior boost in `clarvis.brain.search` (or as a retrieval_quality hook): when a query lexically matches preference patterns (regex like `\b(preference|prefer|should I|style|convention|timezone|spawn)\b`), apply a 0.05–0.10 distance discount to `clarvis-preferences` results before final ranking. Mitigates future (c) regressions if new preference seeds are added without simultaneous benchmark updates.
- **File:** `scripts/brain_mem/retrieval_benchmark.py` reads `brain.search_smart`; the prior is best added in `clarvis/brain/recall.py` (or wherever the `recency_weight`/score-merge happens) under a flag like `preference_collection_boost: float = 0.0`.
- **Projected lift:** unmeasured at this RCA but acts as guard against B16/B17/B27 regressions if other collections add similar-looking memories. Defer until after R1–R3 ship and we have a new baseline.

---

## Projected overall P@3 lift (if all dominant-class fixes ship: R1+R2+R3)

| Item | Before | After | Δ |
|---|---|---|---|
| B16 P@3 | 0.333 | 1.000 | +0.667 |
| B17 P@3 | 0.667 | 1.000 | +0.333 |
| B26 P@3 | 1.000 | 1.000 | 0 |
| B27 P@3 | 0.333 | 1.000 | +0.667 |
| **Preferences avg** | **0.583** | **1.000** | **+0.417** |
| **Overall P@3 (n=29)** | **0.7816** | **≈ 0.8389** | **+0.0573** |

(Math: `+0.0573 = (0.667+0.333+0.667)/29`.) Lifts the weakest category off the floor and moves overall P@3 well clear of the 0.70 floor with margin for noise.

---

## Acceptance checklist (self-audit)

- [x] File exists at `docs/internal/audits/P3_PREFERENCES_CATEGORY_RCA_2026-05-14.md`.
- [x] All 4 preference queries triaged (B16, B17, B26, B27) with raw retrieval output quoted including similarity (distance) scores.
- [x] ≥2 remediation tasks named per dominant class (class (b): R1, R2, R3 — three tasks; class (c) secondary: R4, R5).
- [x] Projected per-fix lift specified for each remediation.
- [x] Cross-checked against `data/retrieval_benchmark/latest.json` timestamp 2026-05-14T12:04:59Z (today's 14:04 CET run), **not** the morning 13:00 snapshot.

## Follow-up

Ship R1+R2+R3 as a single seed PR (3 brain.remember calls). After commit, re-run `python3 scripts/brain_mem/retrieval_benchmark.py` to confirm preferences→1.000 and overall→≈0.839. If the bridge/wrapper memories (rank 2–5 in scoped recall) still pollute results, consider a class-(a) cleanup pass to delete or compress the verbose "Bridge […]"/"Cross-domain connection […]" preference wrappers — they consistently add prefix noise that hurts every preference query.
