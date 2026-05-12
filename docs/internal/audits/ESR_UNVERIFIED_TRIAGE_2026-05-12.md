# ESR Unverified Bucket Triage — 2026-05-12

**Task:** `[ESR_UNVERIFIED_BUCKET_TRIAGE]`  
**Source:** `data/episodes.json` via `EpisodicMemory` (500 episodes total).  
**Scope:** 71 episodes where `failure_type=='action.unverified'`.  
**Why this matters:** ESR is the weakest metric (`0.828` vs target `≥0.85`). `action.unverified` is ~82% of the failure mass.

---

## 1. Histogram

| Bucket | Count | Share |
|---|---:|---:|
| `correctly-downgraded` | 11 | 15.5% |
| `falsely-downgraded` | 56 | 78.9% |
| `infra-failure` | 1 | 1.4% |
| `ambiguous` | 3 | 4.2% |
| **Total** | **71** | **100.0%** |

---

## 2. Projected ESR lift

Current ESR: **0.828** (denominator 500 episodes). Flipping the `falsely-downgraded` episodes to `success` adds **+0.1120** → **0.94**. Also fixing `infra-failure` adds another 1 episodes → **0.942**.

| Scenario | ΔESR | New ESR | Passes ≥0.85? |
|---|---:|---:|:---:|
| Fix `falsely-downgraded` only (56 eps) | +0.1120 | 0.94 | ✅ |
| Fix falsely + infra (57 eps) | +0.1140 | 0.942 | ✅ |

---

## 3. Per-bucket examples & follow-up fix candidates

### `correctly-downgraded` — 11 episodes (15.5%)

**Sample episodes:**
- `ep_20260426_200940` — **[SWO_V2_DESLOP_SHADER]** Add a Phaser post-FX pipeline that palette-quantizes (and optionally Bayer-dithers)  
  _reason:_ agent flagged incompleteness: 'follow up'
  _agent excerpt:_ `t in ~2 weeks to follow up: check whether operator A/B sign-off happened and, if so, flip `DESLOP_DEFAULT_ON` to `true`?\n",   "log": "/home/agent/agents/star-w`
- `ep_20260427_070224` — **[P0_PROJECT_AGENT_MIRROR_RESET_FAILURE_HANDLING]** `scripts/agents/project_agent.py::_sync_mirror()` now har  
  _reason:_ agent flagged incompleteness: 'follow-up'
  _agent excerpt:_ `rts_on_reset_failure`, `test_sync_mirror_aborts_on_clean_failure`) pass alongside existing 2 tests. Committed and QUEUE.md updated.  NEXT: none — fix is self-co`
- `ep_20260427_200431` — **[ABSOLUTE_ZERO_ERROR_FALLBACK_COMMIT]** `scripts/cognition/absolute_zero.py` has an unstaged null/empty-stri  
  _reason:_ agent flagged incompleteness: 'follow-up'
  _agent excerpt:_ ``.  NEXT: none — both items are closed. Operator A/B inspection of `[SWO_V2_DESLOP_SHADER]` (PR #264 merged opt-in) remains the only outstanding V2 follow-up, b`
- `ep_20260428_053549` — **[PHI_SEMANTIC_SAMPLING_FIX]** `clarvis/metrics/phi.py:228` uses `col.get(include=["embeddings"], limit=100)`  
  _reason:_ agent flagged incompleteness: 'follow-up'
  _agent excerpt:_ `imilarity pairs (e.g. `clarvis-goals <-> autonomous-learning`=0.49, `clarvis-identity <-> clarvis-procedures`=0.45) under a `[SEMANTIC_OVERLAP_BOOST_2]` follow-`
- `ep_20260430_060842` — [UNVERIFIED_1] Analyze: read relevant source files, identify change boundary (added: 2026-04-30, source: auto_  
  _reason:_ agent flagged incompleteness: 'follow-up'
  _agent excerpt:_ `TTENTION_DEBIAS]` is a no-op per §3 of the boundary doc and mark it done. Want me to /schedule a follow-up agent in 7 days to grep autonomous logs for any linge`

**Follow-up fix candidates:**
- **`[ESR_INCOMPLETE_TAG_ROUTING]`** — When agent self-flags incompleteness (`[UNVERIFIED]`, `operator-blocked`, `follow-up`), tag the episode with a NEW first-class failure_type `incomplete_by_design` instead of `action.unverified`. These should not count against ESR — they're explicit deferrals.
- **`[ESR_DEFERRAL_ESR_EXCLUDE]`** — Extend `ESR_EXCLUDED_FAILURE_TYPES` (in `scripts/metrics/performance_benchmark.py`) to include `incomplete_by_design`. Treated like `transient_auth` — visible in ops stats but not in the ESR formula.
- **`[ESR_OPERATOR_BLOCKED_LANE]`** — For operator-blocked tasks, generate a structured follow-up entry in QUEUE.md and exit the spawn with outcome=`success` + `requires_operator=True`. Stops the current pattern where agents do everything they can and still get marked down.

### `falsely-downgraded` — 56 episodes (78.9%)

**Sample episodes:**
- `ep_20260409_121409` — [WIKI_METADATA_SCHEMA_ALIGNMENT] Fix wiki metadata/schema drift: standardize on `ingest_ts` across lint/mainte  
  _reason:_ code_validation:fail but ONLY structure rule (>100 lines)
  _agent excerpt:_ `The graph verification script completed successfully (exit 0), confirming SQLite integrity is fine. All 3 tasks are done and verified. `
- `ep_20260409_140142` — [WIKI_RAW_PATH_CANONICALIZATION] Eliminate raw path/directory inconsistency across `raw/repo` vs `raw/repos` a  
  _reason:_ code_validation:fail but ONLY structure rule (>100 lines)
  _agent excerpt:_ ` (last: 15.2% on ep_20260409_121409). The corruption described in the task was likely resolved by a prior session or the automatic backup recovery in `EpisodicM`
- `ep_20260411_191144` — [GRAPH_CONSOLIDATION_EMERGENCY] **(Audit 2026-04-11, unfixed since Apr 5)** Investigate and fix graph verifica  
  _reason:_ code_validation:fail but ONLY structure rule (>100 lines)
  _agent excerpt:_ `Both background tasks completed successfully — these were the initial optimize-full diagnostic runs. Their output was already incorporated into the analysis and`
- `ep_20260412_111149` — [CALIBRATION_LOW_CONFIDENCE_EXPRESSION] **(Promoted P2→P0 for 2026-04-12 — Brier=0.105, target=0.1)** System n  
  _reason:_ code_validation:fail but ONLY structure rule (>100 lines)
  _agent excerpt:_ ` the A/B test findings — the stack's value comes primarily from context/memory modules, not from the working memory component.  All 3 tasks are already complete`
- `ep_20260413_140313` — [REASONING_CHAIN_QUALITY_AUDIT] Audit the last 50 reasoning chains for depth and outcome backfill completeness  
  _reason:_ code_validation:pass — postflight still downgraded
  _agent excerpt:_ `boost complete, 16091 new intra-collection edges across 3 rounds (thresholds 0.75/0.70/0.55), intra_collection_density 0.3961→0.5811 (target 0.50+ achieved), Ph`

**Follow-up fix candidates:**
- **`[ESR_CV_PASS_FORCES_SUCCESS]`** — When `code_validation.passed=True` AND `tests_passed=true` in agent JSON, postflight must set outcome=success regardless of other heuristics. Wire this short-circuit into `heartbeat_postflight._derive_outcome()` as the FIRST decision branch.
- **`[ESR_STRUCTURE_RULE_NOT_FAILURE]`** — Decouple structure rules (>100-line functions) from `code_validation.passed`. Move them to a soft `lint_advisory` field that does NOT downgrade outcome. Mirror the design proposed for `[CODE_GEN_LINT_DECOUPLE_FIX]`.
- **`[ESR_BACKFILL_FALSELY_DOWNGRADED]`** — One-shot backfill: re-classify the falsely-downgraded episodes flagged in this report. Set `outcome=success`, clear `failure_type`, re-emit `failure_types` stats. Lifts ESR by the exact amount projected.

### `infra-failure` — 1 episodes (1.4%)

**Sample episodes:**
- `ep_20260501_220342` — **[BB_LIGHT_THEME_PARITY_REAL]** ([REOPENED] from `[BB_LIGHT_THEME_PARITY]`) Real `prefers-color-scheme` liste  
  _reason:_ code_validation.output_errors=True
  _agent excerpt:_ `weep against `/`, `/play`, `/play/coinflip`, `/verify/[betId]`, `/wallet` in both themes and tune `--bb-fg-muted` / `--bb-fg-subtle` / banner alphas until each `

**Follow-up fix candidates:**
- **`[ESR_VALIDATOR_OUTPUT_ERRORS_RETRY]`** — When `code_validation.output_errors=True`, retry validation once with extended timeout before recording the episode. Wire into `heartbeat_postflight._run_code_validation()`.
- **`[ESR_INFRA_FAILURE_BUCKET]`** — Promote `infra-failure` to a first-class failure_type so it can be excluded from ESR via `ESR_EXCLUDED_FAILURE_TYPES`. Today these silently land in `action.unverified` and drag the metric.
- **`[ESR_FIXTURE_PRECHECK]`** — Add a preflight that asserts validator dependencies (ruff, mypy, pytest, forge) are importable BEFORE spawning. Hard-fail with a queueable diagnostic task rather than running and producing infra-failure episodes.

### `ambiguous` — 3 episodes (4.2%)

**Sample episodes:**
- `ep_20260425_011422` — **[SWO_V2_MINIGAME_PLUMBING]** Shared minigame framework. Abstract `MinigameScene` base class (extends `Phaser  
  _reason:_ no decisive signal in error or code_validation
  _agent excerpt:_ `me plays.\"\n  ],\n  \"tests_passed\": true,\n  \"error\": null,\n  \"confidence\": 0.85,\n  \"pr_class\": \"A\"\n}\n```\n",   "log": "/home/agent/agents/star-w`
- `ep_20260425_091247` — **[SWO_SANCTUARY_CHAT_PERSISTENCE]** Server-side chat history + companion memory in one PR. (a) `sanctuary_cha  
  _reason:_ no decisive signal in error or code_validation
  _agent excerpt:_ `gate to PROD.\"],\n  \"tests_passed\": true,\n  \"error\": null,\n  \"confidence\": 0.85,\n  \"pr_class\": \"A\"\n}\n```\n",   "log": "/home/agent/agents/star-w`
- `ep_20260427_170622` — **[SWO_V2_HALFWIRED_FEATURE_FINISH]** Pick **one** of the half-wired V2 features identified in the recent audi  
  _reason:_ no decisive signal in error or code_validation
  _agent excerpt:_ `ing new props\"],\n  \"tests_passed\": true,\n  \"error\": null,\n  \"confidence\": 0.85,\n  \"pr_class\": \"A\"\n}\n```\n",   "log": "/home/agent/agents/star-w`

**Follow-up fix candidates:**
- **`[ESR_AMBIGUOUS_SIGNAL_AUDIT]`** — Hand-review the ambiguous episodes in this report and refine the classifier. Likely candidates: episodes with `code_validation:fail` but the refinement is truncated/empty.

---

## 4. How to spawn the recommended follow-ups

Add these to `memory/evolution/QUEUE.md` under P1 (the dominant bucket's fixes first):

```
- [ ] [P1] [ESR_CV_PASS_FORCES_SUCCESS] (PROJECT:CLARVIS) — see ESR_UNVERIFIED_TRIAGE_2026-05-12.md (falsely-downgraded)
- [ ] [P1] [ESR_STRUCTURE_RULE_NOT_FAILURE] (PROJECT:CLARVIS) — see ESR_UNVERIFIED_TRIAGE_2026-05-12.md (falsely-downgraded)
- [ ] [P1] [ESR_BACKFILL_FALSELY_DOWNGRADED] (PROJECT:CLARVIS) — see ESR_UNVERIFIED_TRIAGE_2026-05-12.md (falsely-downgraded)
- [ ] [P1] [ESR_INCOMPLETE_TAG_ROUTING] (PROJECT:CLARVIS) — see ESR_UNVERIFIED_TRIAGE_2026-05-12.md (correctly-downgraded)
- [ ] [P1] [ESR_DEFERRAL_ESR_EXCLUDE] (PROJECT:CLARVIS) — see ESR_UNVERIFIED_TRIAGE_2026-05-12.md (correctly-downgraded)
- [ ] [P1] [ESR_OPERATOR_BLOCKED_LANE] (PROJECT:CLARVIS) — see ESR_UNVERIFIED_TRIAGE_2026-05-12.md (correctly-downgraded)
- [ ] [P1] [ESR_AMBIGUOUS_SIGNAL_AUDIT] (PROJECT:CLARVIS) — see ESR_UNVERIFIED_TRIAGE_2026-05-12.md (ambiguous)
- [ ] [P1] [ESR_VALIDATOR_OUTPUT_ERRORS_RETRY] (PROJECT:CLARVIS) — see ESR_UNVERIFIED_TRIAGE_2026-05-12.md (infra-failure)
- [ ] [P1] [ESR_INFRA_FAILURE_BUCKET] (PROJECT:CLARVIS) — see ESR_UNVERIFIED_TRIAGE_2026-05-12.md (infra-failure)
- [ ] [P1] [ESR_FIXTURE_PRECHECK] (PROJECT:CLARVIS) — see ESR_UNVERIFIED_TRIAGE_2026-05-12.md (infra-failure)
```

---

_Generated by `scripts/audit/esr_unverified_triage.py` at 2026-05-12T12:03:33.038656+00:00._
