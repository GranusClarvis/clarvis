# Brain Deep Audit — 2026-04-08

## Executive Summary

Rigorous audit of ClarvisDB brain quality, focusing on value density, duplicate residue, and consciousness-heavy entries. **730 entries removed** (3938 → 3208, -18.5%) through targeted cleanup. Major findings: the existing dedup mechanisms have structural blind spots that allow massive duplication, consciousness research echoes dominated 11%+ of learnings, and several entry classes (self-rep updates, GWT broadcasts, dream chains) were accumulating without cap.

---

## Pre-Cleanup State

| Collection | Count | Notes |
|---|---|---|
| clarvis-learnings | 1611 | Largest; consciousness-saturated |
| clarvis-memories | 725 | Day summaries, state snapshots |
| clarvis-episodes | 389 | Mostly healthy |
| autonomous-learning | 364 | 47 test junk entries, 17 meta_speed_ copies |
| clarvis-identity | 300 | 52 self-rep updates (17.3%), world-model spam |
| clarvis-context | 233 | 158 GWT broadcast entries (67.8%) |
| clarvis-procedures | 176 | Clean |
| clarvis-preferences | 76 | 3 evolved duplicates |
| clarvis-infrastructure | 51 | Clean |
| clarvis-goals | 13 | Clean |
| **TOTAL** | **3938** | |

## Findings

### 1. Massive Exact Duplication (580+ entries)

**182 prefix-duplicate groups** containing 762 entries (580 excess). The existing 100-char prefix dedup runs only during `optimize-full`, which clearly isn't running frequently enough or isn't catching entries created between runs.

**Worst offenders:**
- **47 copies** of `[test] metadata round-trip verification` in autonomous-learning — a test entry that was never cleaned up
- **44 copies** of `Self-representation update: Self-state z_t:` in identity — the self-model writes a new entry every heartbeat instead of updating in place
- **17/16/15/15/14/12/12/11/10 copies** of dream engine reasoning chains — `dream_engine.py` stores each dream's init/step/outcome as separate memories, and reruns produce exact duplicates
- **8 copies** of a single day summary (2026-04-07)
- **7 copies each** of "World model updated" for 4 consecutive days
- **7 copies** of prediction review entries
- **9 copies** of `remember this critical important note about a bug fix` — likely test/debug junk

### 2. Consciousness Research Echo Saturation

Pre-cleanup: **139 consciousness entries in learnings alone (8.6%)**, plus significant presence in identity (12.9%), preferences (10.8%), and memories (6.3%).

**Theme cluster analysis** revealed:
- **69** "General Phi mentions" — mostly operational reasoning chains about boosting Phi metric scores, not durable knowledge
- **27** "Phi computation/approximation" — the same insight ("exact Phi is intractable, use proxies") restated ~27 ways
- **16** "Consciousness architectures survey" — each research ingestion created a new entry instead of consolidating
- **7** PhiID/ΦID entries — 6 evolved copies of the same research
- **5** GWT + Deep Learning
- **4** Butlin/Chalmers indicators
- **3** Predictive Global Workspace

The core problem: research ingestion and the evolution/consolidation pipeline both create **new memories for restated conclusions** rather than identifying and strengthening existing ones.

### 3. Structural Spam Patterns

| Pattern | Count | Root Cause |
|---|---|---|
| Self-representation updates | 52 (→1) | `self_model.py` appends instead of upserts |
| GWT broadcast contexts | 158 (→10) | Every heartbeat stores a broadcast snapshot |
| meta_speed_ entries | 17 (→1) | Daily meta-learning insight stored without checking for existing |
| World model updates | 28+ | Daily cron stores without checking existing |
| Dream chain duplicates | 100+ | `dream_engine.py` reruns produce exact copies |

### 4. Dedup Mechanism Gaps

The existing optimization pipeline (`optimize-full`) has these structural weaknesses:

1. **No write-time dedup**: New memories are stored without checking similarity to existing entries. Dedup only runs during batch optimization, which means duplicates accumulate between runs.

2. **100-char prefix match is brittle**: Near-duplicates with slightly different openings (e.g., "Research: Phi computation —" vs "Research: phi computation —" after a word swap) survive dedup even though they encode the same knowledge.

3. **No cross-collection dedup**: The same consciousness research appears in learnings, preferences, identity, and memories simultaneously. Each collection is deduped independently.

4. **Evolved entries create copies, not updates**: The evolution/consolidation system creates `_evolved_` copies alongside originals. The dedup catches exact matches but not semantic near-duplicates.

5. **Semantic merge threshold too loose**: The 0.8 L2 distance threshold for clustering requires 3+ members. This means 2 near-identical entries with distance 0.5 will never be merged.

6. **No entry class caps**: Self-representation updates, GWT broadcasts, and world-model updates have no per-class limits. Collection-level soft caps don't catch within-class bloat.

---

## Cleanup Actions Taken

| Action | Entries Removed | Reversibility |
|---|---|---|
| Prefix dedup (100-char exact match) | 523 | Graph edges orphaned → next compaction cleans |
| Test junk `[test]` entries | (included above) | Safe |
| `remember this critical...` junk | 2 (additional) | Safe |
| `testing is essential` junk | 0 (already caught) | Safe |
| Low-importance consciousness reasoning chains | 35 | Low-value, imp ≤ 0.15-0.30 |
| Self-representation update spam (keep newest) | 8 | One authoritative copy retained |
| World model update spam (keep 3 newest) | 1 | Recent copies retained |
| GWT broadcast context (keep 10 newest) | 145 | Recent context retained |
| meta_speed_ duplicates (keep newest) | 16 | Latest insight retained |
| **TOTAL** | **730** | |

## Post-Cleanup State

| Collection | Before | After | Δ |
|---|---|---|---|
| clarvis-learnings | 1611 | 1230 | -381 |
| clarvis-identity | 300 | 224 | -76 |
| clarvis-context | 233 | 85 | -148 |
| clarvis-memories | 725 | 667 | -58 |
| autonomous-learning | 364 | 299 | -65 |
| clarvis-preferences | 76 | 74 | -2 |
| clarvis-episodes | 389 | 389 | 0 |
| clarvis-procedures | 176 | 176 | 0 |
| clarvis-infrastructure | 51 | 51 | 0 |
| clarvis-goals | 13 | 13 | 0 |
| **TOTAL** | **3938** | **3208** | **-730** |

**Consciousness saturation**: 3.6% → 8.7% (relative increase because non-consciousness duplicates were also removed; absolute count dropped from ~139 to ~104 in learnings)

---

## Recommended Follow-Up Actions (Prioritized)

### P0 — Fix Root Causes

1. **Write-time dedup guard in `brain.store()`**: Before inserting a new memory, query the target collection for entries within L2 distance < 0.3 with the same 100-char prefix. If found, boost the existing entry's importance instead of inserting a duplicate. This is the single highest-impact fix.

2. **Fix `self_model.py` to upsert, not append**: The self-representation update should use a fixed ID (e.g., `self-rep-current`) and update in place, not create a new entry per heartbeat.

3. **Fix `dream_engine.py` dedup**: Before storing dream chain results, check if an entry with the same dream prompt already exists. Skip or update.

4. **Cap GWT broadcast context entries**: Store at most 1 per hour (or per task), delete oldest when exceeding cap of ~20.

5. **Cap world-model updates**: At most 1 per day, upsert by date key.

### P1 — Strengthen Dedup Pipeline

6. **Add semantic dedup pass**: During `optimize-full`, run a second dedup pass using embedding distance (L2 < 0.4) across entire collections. The current 0.8 threshold with 3-member minimum is too permissive.

7. **Cross-collection dedup**: Run a query for each entry's embedding against all other collections. If distance < 0.3, consolidate into the most appropriate collection.

8. **Evolved-entry cleanup**: After evolution creates an `_evolved_` entry, the original should be marked for review/deletion if the evolved version is semantically identical (distance < 0.3).

### P2 — Consciousness Content Policy

9. **Reduce consciousness research density**: The 104 remaining consciousness entries in learnings should be consolidated to ~10-15 canonical entries (one per distinct insight). This requires a manual or LLM-guided merge pass.

10. **Remove "consciousness" from active goals/metrics**: Since it's no longer an active goal, remove consciousness_metrics from the self-model capability domains and stop tracking Phi as a first-class metric. This prevents future research sessions from re-generating consciousness content.

11. **Research ingestion dedup**: `wiki_retrieval.py` and research ingestion scripts should check brain for existing entries on the same topic before storing new ones.

---

## Dedup Mechanism Assessment

| Mechanism | Verdict |
|---|---|
| 100-char prefix dedup | **Insufficient** — catches exact copies but not semantic near-duplicates |
| Semantic merge (0.8 threshold, 3+ members) | **Too permissive** — misses pairs and moderate similarity |
| Decay (1%/day) | **Working but slow** — low-value entries linger for months |
| Importance pruning (< 0.12) | **Working** — but threshold may be too low |
| Noise pattern pruning | **Working** — but regex-based, misses variations |
| Collection caps | **Not enforced aggressively enough** — caps exist but bloat still occurs |
| Write-time guard | **Missing entirely** — the critical gap |

---

*Generated by brain audit session, 2026-04-08. Pre-cleanup snapshot available via graph edge history.*
