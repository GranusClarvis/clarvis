# Memory Taxonomy Proposal: Harness 4-Type vs Clarvis 10-Collection

**Date**: 2026-04-01
**Task**: [HARNESS_MEMORY_TAXONOMY]
**Source**: Claude Code harness analysis (`memory/research/claude_harness_architecture_2026-03-31.md`)

---

## 1. Taxonomy Mapping

| Harness Type | Purpose | Clarvis Collection(s) | Fit Quality |
|---|---|---|---|
| **user** | Role, preferences, knowledge | `clarvis-identity` + `clarvis-preferences` | **Good** — Clarvis splits this into two, which is finer-grained |
| **feedback** | Corrections & confirmations | `clarvis-learnings` (mixed in) | **Gap** — no dedicated storage; feedback buried in 1244-item collection |
| **project** | Ongoing work, goals, deadlines | `clarvis-context` + `clarvis-goals` | **Good** — Clarvis splits temporal context from durable goals |
| **reference** | Pointers to external systems | `clarvis-infrastructure` | **Good** — direct match |

### Unmapped Clarvis collections (no harness equivalent)

| Collection | Count | Why it exists | Harness equivalent |
|---|---|---|---|
| `clarvis-memories` | 494 | General catch-all | None — harness has no misc bucket |
| `clarvis-procedures` | 190 | Step-by-step how-tos | Harness uses skills/docs, not memory |
| `clarvis-episodes` | 363 | Task execution records | Harness uses JSONL transcripts |
| `autonomous-learning` | 303 | Auto-extracted insights | Harness Dream task feeds into 4 types |

**Assessment**: Clarvis's 10-collection model is richer than the harness's 4-type model. The harness optimizes for simplicity (human-managed markdown files). Clarvis optimizes for machine recall (vector search across specialized stores). Both are valid designs.

---

## 2. The Feedback Gap

### Problem

The `clarvis-learnings` collection (1244 items) is the largest by far. It mixes:
- **Corrections** from user/operator (source=`feedback`, `manual`, `conversation`) — "never do X", "always use Y"
- **Factual insights** from research, reasoning chains, dream engine
- **Historical observations** from reflection loops

Source breakdown of learnings:
```
 504  conversation       (mix of feedback + factual)
 133  brain_bridge       (auto-generated)
 131  clarvis_reasoning  (auto-generated)
 116  research_ingest    (auto-generated)
  93  evolution          (auto-generated)
  66  dream_engine       (auto-generated)
  52  reflection_loop    (auto-generated)
  48  manual             (operator-entered, likely feedback)
```

Only ~50 items (manual + explicit feedback source) are clearly operator feedback. The rest are machine-generated insights. When Clarvis needs to recall "what did the operator tell me not to do?", it's searching through 1200+ machine-generated items to find ~50 human corrections.

### Why feedback deserves separation

1. **Authority**: User corrections override machine-generated insights. A dedicated collection lets us weight feedback higher during recall without boosting all learnings.
2. **Persistence**: Feedback should resist decay longer — "never use sessions_spawn" is valid forever; a research summary from 2026-02-20 may not be.
3. **Retrieval pattern**: Feedback is retrieved by *action similarity* ("I'm about to spawn Claude Code" → recall spawn-related corrections), not by *topic similarity* like research insights.
4. **The harness gets this right**: Separating feedback from general knowledge is the harness's most distinctive design choice. It even distinguishes corrections from confirmations, recording *why* so edge cases can be judged.

---

## 3. Proposal: Add `clarvis-feedback` Collection

### 3.1 Collection Definition

Add to `clarvis/brain/constants.py`:
```python
FEEDBACK = "clarvis-feedback"
```

Add to `ALL_COLLECTIONS` and `DEFAULT_COLLECTIONS`.

### 3.2 Schema

Memories in `clarvis-feedback` use existing metadata fields plus:
- `source`: `"operator"` (user-given) or `"self"` (self-discovered correction)
- `tags`: include `"correction"` or `"confirmation"` to distinguish
- `importance`: starts at 0.7 (higher than default 0.5 — feedback is authoritative)
- New optional metadata: `reason` (why the correction was given — enables edge-case judgment)

### 3.3 Query Routing

Add routing pattern in `constants.py`:
```python
(re.compile(r'\b(avoid|never|always|don.t|must not|should not|rule|correction|feedback)\b', re.I), [FEEDBACK, LEARNINGS]),
```

### 3.4 Migration

One-time migration script to move feedback-type items from `clarvis-learnings` to `clarvis-feedback`:
- Items with `source="feedback"` or `source="manual"` → move
- Items with `source="conversation"` containing correction patterns ("never", "don't", "must", "always") → review and move
- Estimated: ~50-80 items migrate, learnings drops to ~1170

### 3.5 Integration Points

| System | Change |
|---|---|
| `heartbeat_preflight.py` | Always include top-3 feedback results in context (high-authority recall) |
| `conversation_learner.py` | Route extracted corrections to `clarvis-feedback` instead of `clarvis-learnings` |
| `brain.py` CLI | Add `feedback` as a recognized collection in help/stats |
| `dream_engine.py` | No change — dreams are insights, not feedback |
| `clarvis_reflection.py` | Route self-discovered corrections to feedback with `source="self"` |

### 3.6 Bloat Impact

This change **reduces effective bloat** by:
- Shrinking `clarvis-learnings` from 1244 → ~1170 items (removing non-learning content)
- Creating a focused 50-80 item collection with high signal-to-noise ratio
- Improving retrieval precision — fewer false matches when searching for corrections

### 3.7 What NOT to do

- **Don't split further**: 10→11 collections is fine. Don't create per-topic sub-collections.
- **Don't add harness frontmatter format**: Clarvis uses ChromaDB metadata, not markdown frontmatter. The harness format is optimized for human-edited files; ours is optimized for machine retrieval.
- **Don't adopt the MEMORY.md index pattern**: We already have this in our `memory/MEMORY.md` for the auto-memory system. Brain collections don't need a separate index — ChromaDB handles that.

---

## 4. Implementation Plan

| Step | Effort | Description |
|---|---|---|
| 1 | 5 min | Add `FEEDBACK` constant and routing to `constants.py` |
| 2 | 5 min | Update `ALL_COLLECTIONS`, `DEFAULT_COLLECTIONS` |
| 3 | 15 min | Write migration script (`scripts/migrate_feedback.py`) |
| 4 | 10 min | Run migration, verify counts |
| 5 | 10 min | Wire `conversation_learner.py` to route corrections → feedback |
| 6 | 5 min | Update preflight context injection to always include feedback |
| 7 | 5 min | Update brain CLI help/stats |

**Total**: ~55 min implementation. Can be done in one heartbeat session.

---

## 5. Decision

**Recommendation**: Implement `clarvis-feedback` collection. It's the single highest-value takeaway from the harness memory analysis — a small structural change that improves retrieval precision for the most authoritative class of memories.

**Priority**: P1 — queue after current sprint. Not urgent but high-leverage for recall quality.
