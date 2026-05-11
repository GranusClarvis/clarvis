# Goal-stack realignment — 2026-05-10 (week of 2026-W19)

## What this document is

A non-Python, **read-only** triage of every entry currently surfaced by
`brain.get_goals()` (29 records as of 2026-05-11 05:30 UTC). It groups
each entry into one of **keep / deprecate / merge / promote**, explicitly
flags the SWO-overweight vs BunnyBagz-underweight representation drift
called out in the 2026-W18 weekly review, and proposes the canonical
active goal set for **2026-W19** (week of 2026-05-10 → 2026-05-16).

No brain mutation happens here. This file names the exact goal IDs and
title substrings that a follow-up mutating script (or operator-approved
hygiene pass) must touch. See **§5 Follow-up script contract** for the
deterministic targets.

## 1. Inventory snapshot

| # | Goal ID | Title substring | Tags | Importance | Source | Lifecycle markers |
|---|---------|-----------------|------|-----------:|--------|-------------------|
| 0 | `Session Continuity` | "Maintain persistent context and memory across…" | — | 0.498 | (legacy) | `superseded_by: clarvis-goals_evolved_20260413_200020`, progress 86 |
| 1 | `Self-Reflection` | "Develop deep self-awareness — model own capabilities…" | — | 0.495 | (legacy) | progress 85 |
| 2 | `Feedback Loop` | "Build prediction-outcome feedback loops…" | — | 0.264 | (legacy) | **deprecated_at 2026-05-10T05:10:03** |
| 3 | `seed-goals-005` | "Learn and grow through experience…" | goal, core | 0.497 | seed | progress 0 — never advanced |
| 4 | `seed-goals-006` | "Maintain brain health…" | goal, maintenance | 0.929 | seed | `superseded_by: clarvis-goals_evolved_20260413_200019` |
| 5 | `clarvis-goals_20260417_150900` | "Maintain operational excellence (cron / cost / backup / health)" | infrastructure, operations | 0.495 | density_boost | progress 0 |
| 6 | `clarvis-goals_20260417_150901` | "Deliver code and PRs for **Star World Order** project…" | project, swo, delivery | **0.950** | density_boost | progress 0 (SWO no longer active) |
| 7 | `clarvis-goals_20260417_150902` | "Achieve and sustain **Phi (Integration) ≥ 0.65**…" | phi, integration, metric | 0.906 | density_boost | (queue/roadmap already demote Phi to passive obs) |
| 8 | `clarvis-goals_20260417_150903` | "Maintain calibrated confidence (Brier < 0.10)…" | calibration, brier | 0.494 | density_boost | **deprecated_at 2026-05-10T05:10:03** |
| 9 | `clarvis-goals_20260417_150904` | "Reduce operational costs…" | cost, efficiency, routing | 0.271 | density_boost | **deprecated_at 2026-05-10T05:10:03** |
| 10 | `clarvis-goals_20260417_150905` | "Strengthen autonomous execution (heartbeats end-to-end)…" | autonomy, heartbeat | 0.490 | density_boost | progress 0 |
| 11 | `clarvis-goals_20260417_150906` | "Build robust test coverage across spine modules…" | testing, quality, spine | 0.907 | density_boost | progress 0 |
| 12 | `clarvis-goals_20260417_150908` | "Evolve research capability to produce actionable findings…" | research, execution | 0.911 | density_boost | progress 0 |
| 13 | `clarvis-goals_20260418_090146` | "Zero-secret-leak posture…" | infrastructure, security | 0.408 | goal_expansion_2026-04-18 | progress 0 |
| 14 | `clarvis-goals_20260418_090147` | "Backup integrity verified…" | infrastructure, backup | 0.490 | goal_expansion_2026-04-18 | progress 0 |
| 15 | `clarvis-goals_20260418_090148` | "Maintain gateway stability…" | infrastructure, gateway | 0.497 | goal_expansion_2026-04-18 | progress 0 |
| 16 | `clarvis-goals_20260418_090149` | "Optimize cron schedule efficiency (47 entries)…" | infrastructure, cron | 0.852 | goal_expansion_2026-04-18 | progress 0 |
| 17 | `clarvis-goals_20260418_090150` | "Deepen self-model accuracy (7 domains)…" | identity, self-model | 0.950 | goal_expansion_2026-04-18 | progress 0 |
| 18 | `clarvis-goals_20260418_090151` | "Strengthen agent identity coherence (SOUL/SELF/identity)…" | identity, coherence | 0.893 | goal_expansion_2026-04-18 | progress 0 |
| 19 | `clarvis-goals_20260418_090152` | "Improve theory-of-mind modeling (operator intent)…" | identity, theory-of-mind | 0.499 | goal_expansion_2026-04-18 | progress 0 |
| 20 | `clarvis-goals_20260418_090153` | "Improve learning retention rate (consolidate cron findings)…" | learning, retention | 0.494 | goal_expansion_2026-04-18 | progress 0 |
| 21 | `clarvis-goals_20260418_090154` | "Build cross-domain knowledge bridges (Phi-recovery framing)…" | learning, integration, phi | 0.257 | goal_expansion_2026-04-18 | **deprecated_at 2026-05-10T05:10:03** |
| 22 | `clarvis-goals_20260418_090155` | "Research-to-execution pipeline maturity (48h)…" | learning, research, execution | 0.496 | goal_expansion_2026-04-18 | progress 0 |
| 23 | `clarvis-goals_20260418_090156` | "Maintain dream engine quality (dream-to-implementation)…" | learning, dreams | 0.494 | goal_expansion_2026-04-18 | **deprecated_at 2026-05-10T05:10:03** |
| 24 | `clarvis-goals_20260420_093712` | _bridge memory_ "Goals + preferences are tightly coupled…" | bridge, phi-recovery | 0.501 | phi_pair_bridge | bridge, not a goal |
| 25 | `clarvis-goals_20260420_093713` | _bridge memory_ "Infrastructure knowledge feeds goal feasibility…" | bridge, phi-recovery | 0.577 | phi_pair_bridge | bridge, not a goal |
| 26 | `clarvis-goals_20260428_010220` | "Preserve identity continuity across model updates…" | bridge, identity | 0.946 | phi_bridging_memory | progress 0 |
| 27 | `clarvis-goals_20260428_010226` | "Autonomous-learning loop must produce actionable findings…" | bridge, goals, autonomous-learning | 0.950 | phi_bridging_memory | progress 0 |
| 28 | `clarvis-goals_evolved_20260510_200017` | **(MISFILE)** "Day summary 2026-05-10…" | — | 0.950 | evolution_contradiction | This is an **episode**, not a goal |

## 2. Representation drift (the headline finding)

The 29-record stack is dominated by three patterns that no longer match
actual delivery:

1. **SWO overweight, BunnyBagz absent.**
   - `clarvis-goals_20260417_150901` ("Deliver code and PRs for **Star
     World Order**…") still carries importance **0.950** and is the
     only project-delivery goal in the brain.
   - The W18 review documents the actual delivery this week:
     BunnyBagz Phase 1 closeout + Phase 2 dice/HiLo + QA harness
     work. SWO V3 is **DEFERRED** (per
     `memory/evolution/swo_sanctuary_v3_deferred_2026-04-26.md`) and
     V2 is in Track-B polish only.
   - There is **zero `BUNNYBAGZ` tag** anywhere in `brain.get_goals()`
     — the brain still thinks the operator's project is SWO.
2. **Phi-forward goals over-represented despite passive-observability
   demotion.**
   - `clarvis-goals_20260417_150902` (Phi ≥ 0.65, importance 0.906)
     plus the two `phi_pair_bridge` bridge memories
     (`20260420_093712`, `20260420_093713`) plus the
     deprecated-but-still-surfaced cross-domain bridge goal
     (`20260418_090154`) total 4 records anchoring Phi as a strategic
     target. The roadmap and QUEUE policy have already demoted Phi to
     passive observability (see `PHI_DEEMPHASIS_AUDIT`,
     `PHI_AUTO_INJECTION_REMOVAL`, `PHI_EVOLUTION_PROMPT_DEEMPHASIS`).
3. **Stale / superseded / mistyped survivors.**
   - `Session Continuity` carries an explicit
     `superseded_by: clarvis-goals_evolved_20260413_200020` and the
     successor record is not in the goal stack — supersession is
     decorative.
   - `seed-goals-006` (`Maintain brain health`) is similarly
     `superseded_by: clarvis-goals_evolved_20260413_200019` with the
     successor again absent.
   - `seed-goals-005` has been at progress 0 since 2026-03 and is
     pure flavor text.
   - `clarvis-goals_evolved_20260510_200017` is a day-summary that
     was misclassified into `clarvis-goals` by the evolution
     contradiction pass — it should be in `clarvis-episodes`, not
     here.
   - Five records already carry `deprecated_at 2026-05-10T05:10:03`
     (Feedback Loop, Brier calibration, cost reduction,
     cross-domain knowledge bridges, dream-engine quality) but
     `get_goals()` still returns them.

## 3. Triage — keep / deprecate / merge / promote

### KEEP (operational, still load-bearing for 2026-W19)
- `clarvis-goals_20260417_150900` — Operational excellence (cron /
  cost / backup / health). Anchors infra cron lane.
- `clarvis-goals_20260417_150906` — Spine test coverage. Directly
  supported by recent BB QA harness work + ongoing spine tests.
- `clarvis-goals_20260417_150905` — Strengthen autonomous execution
  end-to-end. Maps onto the
  `[QUEUE_LANE_MINIMUM_AUTOFILL]` / `[TASK_SELECTOR_MULTI_LANE_BOOST]`
  / verification-record lineage.
- `clarvis-goals_20260418_090147` — Backup integrity.
- `clarvis-goals_20260418_090148` — Gateway stability.
- `clarvis-goals_20260418_090146` — Zero-secret-leak posture (still
  active via weekly `secret_sweep`).
- `clarvis-goals_20260418_090150` — Self-model accuracy.
- `clarvis-goals_20260418_090151` — Identity coherence.
- `clarvis-goals_20260428_010220` — Identity continuity across
  mutations.
- `clarvis-goals_20260428_010226` — Autonomous-learning loop must
  produce actionable findings.

### DEPRECATE (already marked, or no longer load-bearing)
_These should be archived from the active goal surface. Some already
carry `deprecated_at`; the rest are recommended new deprecations._
- `Feedback Loop` — already `deprecated_at 2026-05-10` → archive.
- `clarvis-goals_20260417_150903` (Brier < 0.10) — already
  `deprecated_at 2026-05-10` → archive.
- `clarvis-goals_20260417_150904` (cost reduction) — already
  `deprecated_at 2026-05-10` → archive.
- `clarvis-goals_20260418_090154` (cross-domain bridges) — already
  `deprecated_at 2026-05-10` → archive.
- `clarvis-goals_20260418_090156` (dream engine quality) — already
  `deprecated_at 2026-05-10` → archive.
- `clarvis-goals_20260417_150902` (Phi ≥ 0.65) — **recommend new
  deprecation**; Phi is passive observability per roadmap, not a
  target.
- `seed-goals-005` (generic "learn and grow") — **recommend new
  deprecation**; covered by autonomous-learning goal and never
  advanced.
- `seed-goals-006` (brain health) — **recommend new deprecation**;
  has explicit successor `clarvis-goals_evolved_20260413_200019`.
- `Session Continuity` — **recommend new deprecation**; has explicit
  successor `clarvis-goals_evolved_20260413_200020`, successor
  missing from current stack so a fresh `Continuity hygiene`
  promotion (§4) replaces it.
- `clarvis-goals_evolved_20260510_200017` — **misfile**;
  it is a day-summary episode. Should be **moved** out of
  `clarvis-goals` into `clarvis-episodes` (treat deprecation here as
  "remove from goal surface").

### MERGE
- The two `phi_pair_bridge` records (`clarvis-goals_20260420_093712`
  and `_093713`) are *bridge memories*, not goals. They should be
  moved out of the `clarvis-goals` collection into
  `clarvis-memories` (or dropped if Phi is demoted). Treat as
  "merge into the bridging-memory surface, remove from goal
  surface."
- `clarvis-goals_20260418_090152` (theory-of-mind) and
  `clarvis-goals_20260418_090150` (self-model accuracy) and
  `clarvis-goals_20260418_090151` (identity coherence) overlap
  significantly — they should be merged into a single
  **self-model / operator-modeling** goal once §4 promotion lands.
  Until then, all three are KEEP.
- `clarvis-goals_20260418_090153` (learning retention) and
  `clarvis-goals_20260418_090155` (research-to-execution pipeline)
  collapse into the new **Autonomous-learning → action conversion**
  goal in §4 (promote-and-merge).

### PROMOTE (the new BunnyBagz-centered + continuity-hygiene goals)
_These do not yet exist in `clarvis-goals` and are the missing
representation that this realignment proposes to add._
- **`bunnybagz-delivery-2026-Q2`** — _"Deliver BunnyBagz Phase 1
  closeout and Phase 2 game wiring (dice + HiLo + USDM) with a
  green test inventory and operator-demo polish."_ See §4 for the
  exact text and tags.
- **`continuity-hygiene-2026-W19`** — _"Maintain weekly goal-stack
  hygiene and daily-log continuity so `brain.get_goals()` reflects
  actual delivery within ±1 week."_ See §4.

## 4. Canonical active goals proposed for 2026-W19

These are the **3 to 5 canonical goals** the operator-facing goal
surface should resolve to once the follow-up mutation runs. Each is
written as the literal `document` text the brain-store hook expects.

### G1 — BunnyBagz delivery (project) **[NEW, BUNNYBAGZ-CENTERED]**
- **ID (proposed):** `clarvis-goals_2026W19_bunnybagz_delivery`
- **document:** `Goal: Deliver BunnyBagz Phase 1 closeout and Phase 2 game wiring (dice + HiLo + USDM) on testnet with a green test inventory across contracts/web/api/indexer, operator-demo polish on /play surfaces, and trust-surface (footer + audit + bounty + verify) shipping with every route. BunnyBagz is the current value-producing project.`
- **tags:** `["goal", "project", "bunnybagz", "delivery", "phase-1", "phase-2"]`
- **importance:** `0.95`
- **superseding:** `clarvis-goals_20260417_150901` (the SWO project
  goal — see §5 mutation contract).

### G2 — Autonomous execution & queue health (Clarvis) **[KEEP, REWORDED]**
- **ID (proposed):** keep `clarvis-goals_20260417_150905`
- **document:** `Goal: Strengthen autonomous execution end-to-end — heartbeat selects, completes, and verifies tasks without false-DONE marks; queue lane minimums are honored; archive only happens when a verification record exists. Measured weekly by lane-minimum honor rate, [UNVERIFIED] → verified conversion rate, and zero-eligible incident count.`
- **tags:** `["goal", "autonomy", "heartbeat", "execution", "queue-health"]`
- **importance:** `0.90` (raise from 0.49)

### G3 — Brain & test-coverage quality **[KEEP, MERGED]**
- **ID (proposed):** keep `clarvis-goals_20260417_150906` (spine
  test coverage) and treat as canonical brain/test goal.
- **document:** `Goal: Sustain spine test coverage and brain quality. Spine modules ship with regression tests before reaching cron; brain quality eval, CLR benchmark, and retrieval Precision@3 stay above their weekly thresholds; failing-query triage runs weekly.`
- **tags:** `["goal", "testing", "quality", "spine", "brain"]`
- **importance:** `0.90`

### G4 — Self-model / operator-modeling **[MERGE-PROMOTE]**
- **ID (proposed):** keep `clarvis-goals_20260418_090150` and
  rewrite as the merged self/identity/operator goal. Mark
  `_090151` (identity coherence) and `_090152` (theory-of-mind) as
  `merged_into: clarvis-goals_20260418_090150` once the mutation
  runs.
- **document:** `Goal: Keep the self-model and operator-model calibrated. The 7-domain self-model tracks actual performance; SOUL.md / SELF.md / clarvis-identity stay consistent with capability; theory-of-mind for the operator stays current with stated preferences, lane discipline, and active project (BunnyBagz this week).`
- **tags:** `["goal", "identity", "self-model", "operator-modeling"]`
- **importance:** `0.90`

### G5 — Continuity hygiene (NEW, **CONTINUITY-HYGIENE GOAL**)
- **ID (proposed):** `clarvis-goals_2026W19_continuity_hygiene`
- **document:** `Goal: Maintain weekly continuity hygiene. Daily memory files exist for every day in the review window; brain.get_goals() reflects actual delivery within ±1 week; deprecated goals are archived off the active surface; misfiled records (episodes, bridge memories) live in their correct collection. Hygiene runs every Sunday and produces a goals/realignment_<date>.md if drift > 3 records.`
- **tags:** `["goal", "continuity", "hygiene", "goal-stack", "weekly"]`
- **importance:** `0.85`

## 5. Follow-up script contract

This file is **markdown only**. No brain mutation happens here. A
follow-up script (or operator-approved hygiene pass) consuming this
document should:

### 5a. Records to **archive off the active goal surface** (mark `archived: true` on the metadata, or move to a `clarvis-goals-archive` collection)
Exact IDs (verbatim from `brain.get_goals()`):
- `Feedback Loop`
- `clarvis-goals_20260417_150903`  _(Brier < 0.10)_
- `clarvis-goals_20260417_150904`  _(cost reduction)_
- `clarvis-goals_20260418_090154`  _(cross-domain knowledge bridges)_
- `clarvis-goals_20260418_090156`  _(dream engine quality)_
- `clarvis-goals_20260417_150902`  _(Phi ≥ 0.65)_
- `seed-goals-005`
- `seed-goals-006`
- `Session Continuity`
- `clarvis-goals_20260417_150901`  _(SWO project delivery)_ — supersede by **G1**

### 5b. Records to **move to a different collection** (do **not** delete document; reclassify)
- `clarvis-goals_evolved_20260510_200017` → `clarvis-episodes`
  (it is a day-summary; title substring _"Day summary 2026-05-10"_).
- `clarvis-goals_20260420_093712` → `clarvis-memories`
  (bridge memory; title substring _"Goals and preferences are tightly coupled"_).
- `clarvis-goals_20260420_093713` → `clarvis-memories`
  (bridge memory; title substring _"Infrastructure knowledge feeds goal feasibility"_).

### 5c. Records to **merge** (set `merged_into: <target>` on source, keep target as canonical)
- `clarvis-goals_20260418_090151` → merged_into `clarvis-goals_20260418_090150` (identity coherence into self-model G4).
- `clarvis-goals_20260418_090152` → merged_into `clarvis-goals_20260418_090150` (theory-of-mind into self-model G4).
- `clarvis-goals_20260418_090153` → merged_into `clarvis-goals_20260418_090155` (learning retention into research-to-execution).

### 5d. Records to **promote (add new)** to the active goal surface
- New goal **G1** (`clarvis-goals_2026W19_bunnybagz_delivery`).
- New goal **G5** (`clarvis-goals_2026W19_continuity_hygiene`).

### 5e. Records to **reword in-place** (keep ID, update document + importance)
- `clarvis-goals_20260417_150905` → reword as **G2**, importance 0.90.
- `clarvis-goals_20260417_150906` → reword as **G3**, importance 0.90.
- `clarvis-goals_20260418_090150` → reword as **G4**, importance 0.90.

### 5f. Required safety properties for the script
1. **Dry-run by default.** The follow-up mutating script must print
   the full plan and require `--apply` to write. Mirrors
   `clarvis cron install` UX.
2. **Single transaction per record.** Each archive / move / merge /
   reword writes one brain record; failures abort and roll back, not
   half-apply.
3. **Audit sidecar.** Every mutation appends one JSONL line to
   `data/audit/goal_hygiene/2026-05-10.jsonl` with `{ts, action,
   target_id, source_id?, old_doc_hash, new_doc_hash}`.
4. **No automatic invocation.** The script is operator-triggered
   (e.g. `python3 -m clarvis brain goals realign --plan
   memory/evolution/goals/realignment_2026-05-10.md --apply`). It
   does not run from cron.
5. **Reversibility.** Reword + supersede operations keep the prior
   document hash in the sidecar so the change can be replayed in
   reverse.

## 6. Acceptance check (against the task contract)

- [x] File exists at `memory/evolution/goals/realignment_2026-05-10.md`.
- [x] Groups every current goal-stack entry into
      keep / deprecate / merge / promote (§3 + §5).
- [x] Explicitly flags SWO-overweight vs BunnyBagz-underweight
      drift (§2 finding 1) and Phi-overweight drift (§2 finding 2).
- [x] Proposes 3–5 canonical active goals for the next week (§4,
      exactly 5: G1–G5).
- [x] Includes at least one BunnyBagz-centered canonical goal (G1).
- [x] Includes at least one continuity-hygiene goal (G5).
- [x] Names the exact goal IDs / title substrings the follow-up
      mutating script must touch (§5a–§5e).
- [x] No brain mutation occurred automatically (this file is
      markdown only; mutation is gated on §5f operator trigger).
