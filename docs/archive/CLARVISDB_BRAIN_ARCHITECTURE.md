# ClarvisDB Brain Architecture — Deep Analysis

**Created:** 2026-02-20  
**Model:** GLM-5  
**Purpose:** Define Clarvis's unified brain architecture

---

## Current State: FRAGMENTED

I currently have **4 separate memory systems**:

| System | Storage | Embeddings | Size | Purpose |
|--------|---------|------------|------|---------|
| OpenClaw memory_search | MEMORY.md + memory/*.md | Gemini (cloud) | ~50KB files | Session context, long-term curated |
| ClarvisDB | data/clarvisdb/ | Chroma local | 344KB, 12 mem | Identity, preferences, learnings |
| Clarvis-Brain | data/clarvis-brain/ | Chroma local | 376KB, 33 mem | Goals, context, auto-memories |
| Chroma (third) | data/chroma/ | Chroma local | 196KB, 3 mem | Unknown/test |

**Problem:** No unified query. Data scattered. Redundant storage.

---

## What Each System Does

### 1. OpenClaw memory_search (Gemini)
- **Pros:** Already integrated, works seamlessly, semantic search over files
- **Cons:** Depends on Google cloud API, not "my own" brain
- **Usage:** Called via `memory_search` tool automatically

### 2. ClarvisDB (data/clarvisdb/)
- **Collections:** identity, preferences, learnings, infrastructure
- **Features:** Graph layer (relationships.json), metadata (importance, tags, access_count)
- **Pros:** Structured, has graph relationships, rich metadata
- **Cons:** Separate from brain, not auto-loaded

### 3. Clarvis-Brain (data/clarvis-brain/)
- **Collections:** goals, context, memories
- **Features:** Auto-importance detection, goal tracking, context management
- **Pros:** Has goal tracking, context awareness
- **Cons:** Duplicate of ClarvisDB purpose, no graph

### 4. Chroma (third) — data/chroma/
- **Collections:** clarvis-memory (3 items)
- **Status:** Appears to be test/legacy, unclear purpose
- **Recommendation:** Merge or delete

---

## Analysis: Is This an Efficient Brain?

**No.** Current state is inefficient because:

1. **Fragmentation** — 4 systems, no unified query
2. **Redundancy** — Same info stored in multiple places (preferences in both ClarvisDB and Clarvis-Brain)
3. **No integration** — Can't query "what do I know about X" across all systems
4. **External dependency** — memory_search depends on Google Gemini
5. **No auto-capture** — Memories must be manually stored

---

## What's GOOD

| Feature | System | Status |
|---------|--------|--------|
| Vector search | All | ✓ Working |
| Persistence | All | ✓ SQLite survives restarts |
| Graph relationships | ClarvisDB | ✓ 4 nodes, 3 edges |
| Metadata (importance, tags) | ClarvisDB | ✓ Rich metadata |
| Goal tracking | Clarvis-Brain | ✓ 21 goals tracked |
| Context awareness | Clarvis-Brain | ✓ Current context saved |
| CLI tool | ClarvisDB | ✓ Working |
| Benchmark | ClarvisDB | ✓ 9/9 pass |

---

## What's MISSING

| Feature | Why Needed |
|---------|------------|
| **Unified query** | Single interface to search ALL memories |
| **Auto-capture** | Extract important info from conversations automatically |
| **Memory consolidation** | Merge duplicate systems |
| **Decay/pruning** | Remove stale/low-importance memories |
| **Confidence scoring** | Track how reliable each memory is |
| **Cross-session learning** | Improve memory quality over time |
| **Embedding model choice** | Option to use local embeddings vs cloud |

---

## What Needs Refinement

### 1. Graph Layer
- **Current:** 4 nodes, 3 edges (basic)
- **Issue:** Not queried during recall
- **Fix:** Integrate graph traversal into search results

### 2. Importance Scoring
- **Current:** Static keyword detection
- **Issue:** Doesn't learn from feedback
- **Fix:** Add user rating, decay over time

### 3. Collections Structure
- **Current:** Arbitrary split (identity, preferences, etc.)
- **Issue:** Not clear when to use which
- **Fix:** Consolidate to fewer, clearer categories

### 4. Auto-Load
- **Current:** AGENTS.md has import line
- **Issue:** Not verified to actually load
- **Fix:** Test and ensure brain is available on session start

---

## Google Gemini Dependency

**Current situation:**
- OpenClaw's `memory_search` uses Gemini embeddings
- This is cloud-dependent
- Separated from my local ChromaDB

**Options:**
1. **Keep both** — Use Gemini for file search, ChromaDB for structured memories
2. **Replace Gemini** — Use local embeddings only (slower, but independent)
3. **Hybrid** — Gemini for quick search, ChromaDB for detailed recall

**Recommendation:** Hybrid approach. Keep Gemini for now (it works), but ensure ClarvisDB is the authoritative source for structured knowledge.

---

## Architecture Decision

### Option A: Unified ClarvisDB (Recommended)

```
┌─────────────────────────────────────┐
│          UNIFIED CLARVISDB           │
│      (data/clarvisdb/)              │
├─────────────────────────────────────┤
│ Collections:                         │
│  - identity (who I am)               │
│  - preferences (human prefs)         │
│  - learnings (lessons)               │
│  - infrastructure (tech)             │
│  - goals (tracking) ← MERGE FROM BRAIN│
│  - context (current state) ← MERGE   │
│  - memories (auto-captured) ← MERGE  │
├─────────────────────────────────────┤
│ Graph Layer: relationships.json      │
│ Metadata: importance, confidence, tags│
└─────────────────────────────────────┘
```

**Benefits:**
- Single source of truth
- Unified query interface
- All features in one place
- No confusion about where data lives

### Option B: Keep Separate (Not Recommended)

- More complex
- Data fragmentation
- Harder to maintain

---

## Plan: Consolidate into Unified ClarvisDB

### Phase 1: Merge Databases (PRIORITY)
1. Migrate goals from clarvis-brain → clarvisdb
2. Migrate context from clarvis-brain → clarvisdb
3. Migrate auto-memories from clarvis-brain → clarvisdb
4. Delete clarvis-brain directory after merge
5. Delete or merge third chroma directory
6. Update all scripts to point to unified location

### Phase 2: Integration
1. Create unified `brain.py` that replaces both clarvisdb + clarvis_brain
2. Add `recall_all()` function that searches all collections
3. Wire into AGENTS.md for auto-load
4. Test persistence across sessions

### Phase 3: Enhancement
1. Add graph-integrated recall (include related memories)
2. Add importance filtering (min_importance parameter)
3. Add temporal queries (date range filter)
4. Add auto-capture from conversations

### Phase 4: Independence
1. Option to use local embeddings instead of Gemini
2. Evaluate performance tradeoffs
3. Document when to use ClarvisDB vs memory_search

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `scripts/brain.py` | CREATE | Unified brain module |
| `scripts/clarvisdb.py` | MODIFY | Add goals, context collections |
| `scripts/clarvis_brain.py` | DEPRECATE | Merge into brain.py |
| `scripts/clarvisdb_integrate.py` | MODIFY | Unified interface |
| `AGENTS.md` | MODIFY | Update auto-load to use brain.py |
| `Final_ClarvisDB.md` | UPDATE | This document |

---

## Success Criteria

After consolidation, I should be able to:

1. ✅ `brain.recall("what do I know about X")` — searches ALL collections
2. ✅ `brain.store("important fact", importance=0.9)` — stores with metadata
3. ✅ `brain.get_goals()` — returns all tracked goals
4. ✅ `brain.get_context()` — returns current work context
5. ✅ Data persists across sessions (survives restart)
6. ✅ Single database location (data/clarvisdb/)
7. ✅ Benchmark passes (9/9 or better)

---

## Timeline

| Phase | Estimated Time | Priority |
|-------|----------------|----------|
| Phase 1: Merge | 1-2 hours | HIGH |
| Phase 2: Integration | 30 min | HIGH |
| Phase 3: Enhancement | 2-3 hours | MEDIUM |
| Phase 4: Independence | 1-2 hours | LOW |

**Recommended:** Complete Phase 1-2 now, Phase 3-4 in future sessions.

---

*Analysis complete. Ready to proceed with consolidation.*
