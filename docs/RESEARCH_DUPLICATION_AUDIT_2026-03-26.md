# Research Duplication Audit — 2026-03-26

## Why this exists
The operator flagged that Clarvis had re-researched the same IIT/Phi approximation topic many times and was likely polluting memory rather than learning. This audit records the concrete duplicate cluster, root causes, canonical keep-set, and immediate fixes.

## Root causes found

### 1. Research completion relied on Claude editing `QUEUE.md`
`cron_research.sh` instructed Claude to mark tasks done, but did not deterministically mark/archive the task itself on success.

Result:
- research items could succeed
- notes could be ingested
- but the task might remain in `QUEUE.md` or leave stale checked items behind

### 2. Discovery pause did not stop already-queued research
`RESEARCH_AUTO_REPLENISH=0` only disables discovery fallback when there are no research tasks. It does **not** prevent execution of old queued research items.

### 3. Novelty judgment was weak
The system repeatedly accepted semantically near-identical Phi/IIT summaries as new “evolved” learnings instead of recognizing them as the same conclusion.

## Duplicate cluster: Phi / IIT computation / approximations

### Repeated queue/archive tasks
- 2026-03-17 — `[RESEARCH_PHI_COMPUTATION_2026-03-17]`
- 2026-03-18 — `[RESEARCH_PHI_APPROX_VALIDITY_GAPS]`
- 2026-03-19 — `[RESEARCH_SCALABLE_PHI_PROXIES]`
- 2026-03-20 — `[RESEARCH_SCALABLE_PHI_ALGORITHMS_VALIDITY]`
- 2026-03-22 — `[RESEARCH_PHI_COMPUTATION]`
- 2026-03-22 — `[RESEARCH_PHI_COMPUTATION]` (second pass)
- 2026-03-23 — `[RESEARCH_PHI_COMPUTATION]`
- 2026-03-23 — `[RESEARCH_CONSCIOUSNESS_ARCHITECTURES_PHI_RETRIEVAL]`
- 2026-03-25 — `[RESEARCH_PHI_COMPUTATION]`
- 2026-03-25 — `[RESEARCH_IIT_CONSCIOUSNESS_ARCHITECTURES]`
- 2026-03-26 — `[RESEARCH_PHI_COMPUTATION_APPROXIMATIONS]`

### Repeated memory-evolution evidence
`data/conflict_log.jsonl` shows repeated "action=evolved" events for near-identical insights across:
- 2026-03-18
- 2026-03-19
- 2026-03-20
- 2026-03-22
- 2026-03-23
- 2026-03-25
- 2026-03-26

Common repeated conclusion:
> exact Phi is computationally intractable; approximations/proxies can be useful for ranking or trend-tracking on small systems, but are not faithful replacements for exact IIT at scale.

## Canonical keep-set

Keep these as the canonical, useful versions:

### Keep 1 — scaling + validity
`memory/research/ingested/scalable-phi-algorithms-validity-2026-03-20.md`
- Best concise statement of the two-axis lesson:
  - computational efficiency
  - conceptual soundness
- Most reusable implementation takeaway for Clarvis.

### Keep 2 — exact-vs-proxy benchmark framing
`memory/research/ingested/phi-computation.md`
- Best statement of exact Phi tractability and benchmark use.
- Good canonical source for “heuristics may rank/screen systems, not replace exact Phi.”

### Keep 3 — architecture application
`memory/research/ingested/consciousness_architectures_phi_retrieval_optimization.md`
- Distinct because it connects Phi bottlenecks to practical agent architecture and retrieval.
- Keep as a synthesis note, not as another standalone Phi-computation note.

## Retire / demote as redundant cluster members
These are not necessarily false, just redundant as active learnings:
- 2026-03-17 practical Phi computation survey
- 2026-03-18 approximation validity gaps
- 2026-03-19 scalable Phi proxies / ΦID
- 2026-03-22 repeated `RESEARCH_PHI_COMPUTATION` passes
- 2026-03-23 repeated `RESEARCH_PHI_COMPUTATION`
- 2026-03-25 repeated `RESEARCH_PHI_COMPUTATION`
- 2026-03-26 approximation summary

## Immediate fixes applied

### Fix A — deterministic queue completion in research cron
Patched `scripts/cron_research.sh` so successful research runs now:
1. mark the selected task complete in `QUEUE.md`
2. archive completed items immediately

This no longer depends on Claude remembering to edit the queue.

### Fix B — stale checked research task archived
Ran queue archive once after the fix to remove the lingering checked research item from `QUEUE.md`.

## What still needs to happen

### 1. Brain cleanup pass
We should trace the repeated Phi/IIT learnings that were ingested into `clarvis-learnings` and collapse them to canonical references rather than leaving many paraphrased variants active.

### 2. Novelty gate before research execution
Before a research task runs, Clarvis should classify it as one of:
- NEW
- REFINEMENT
- CONTRADICTION
- ALREADY KNOWN

Only NEW / substantial REFINEMENT / real CONTRADICTION should run.
ALREADY KNOWN should skip.

## Principle going forward
The fix is not a dumb string deduper. The fix is judgment:
- Do we already know this?
- Does this change a decision?
- Is there meaningful delta?
- Is it relevant to the current delivery window?

If not, skip.
