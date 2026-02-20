# Final_ClarvisDB.md — Clarvis Persistent Memory System

**Created:** 2026-02-20  
**Status:** Core DONE, Enhancement opportunities exist

---

## Executive Summary

ClarvisDB is Clarvis's persistent memory system combining:
- **Vector search** (ChromaDB) for semantic recall
- **Graph relationships** for linked memories
- **Metadata layer** for importance, confidence, access tracking

**Current State:** Core functionality working (9/9 benchmarks pass). System stores and retrieves memories across sessions.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ClarvisDB System                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐    ┌─────────────────┐               │
│  │   clarvisdb    │    │ clarvis_brain   │               │
│  │  (Phase 2-3)   │    │  (auto-brain)   │               │
│  └────────┬────────┘    └────────┬────────┘               │
│           │                       │                         │
│           ▼                       ▼                         │
│  ┌─────────────────────────────────────────┐               │
│  │          ChromaDB (Vector)              │               │
│  │  - clarvis-identity (1 mem)             │               │
│  │  - clarvis-preferences (3 mem)           │               │
│  │  - clarvis-learnings (3 mem)             │               │
│  │  - clarvis-infrastructure (1 mem)        │               │
│  │  - clarvis-memories (brain)             │               │
│  │  - clarvis-context (brain)               │               │
│  │  - clarvis-goals (brain)                 │               │
│  └─────────────────────────────────────────┘               │
│                         │                                    │
│                         ▼                                    │
│  ┌─────────────────────────────────────────┐               │
│  │     Graph Layer (relationships.json)    │               │
│  │     4 nodes, 3 edges                   │               │
│  └─────────────────────────────────────────┘               │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  Integration Layer (clarvisdb_integrate.py)                │
│  - store_important()                                       │
│  - recall()                                                │
├─────────────────────────────────────────────────────────────┤
│  CLI (clarvisdb_cli.py)                                   │
│  Skill (~/.openclaw/skills/clarvisdb/)                     │
└─────────────────────────────────────────────────────────────┘
```

---

## What's DONE ✓

| Component | Status | Notes |
|-----------|--------|-------|
| Vector DB (Chroma) | ✓ | Persistent SQLite storage |
| Collections | ✓ | 4 collections for different memory types |
| Graph Layer | ✓ | relationships.json with nodes/edges |
| Metadata | ✓ | importance, confidence, tags, access_count |
| Integration Layer | ✓ | store_important(), recall() functions |
| CLI Tool | ✓ | clarvisdb_cli.py for quick access |
| Skill Doc | ✓ | ~/.openclaw/skills/clarvisdb/SKILL.md |
| Auto-Load | ✓ | Loaded in AGENTS.md session init |
| Session Persistence | ✓ | Data survives restarts |

**Benchmark: 9/9 PASS**

---

## What's MISSING ✗

| Feature | Priority | Why It Matters |
|---------|----------|----------------|
| **Unified brain** | HIGH | Two separate systems (clarvisdb + clarvis_brain) - confusing |
| **Auto-import** | HIGH | Not automatically loading on session start |
| **Importance-based recall** | MEDIUM | Can't filter by importance threshold |
| **Temporal queries** | MEDIUM | Can't query "what did I learn yesterday" |
| **Embedding model config** | MEDIUM | Using default, not optimized for recall |
| **Memory decay/importance update** | LOW | Access count tracked but not used for pruning |
| **MCP exposure** | LOW | Not exposing as tool to OpenClaw |

---

## What's GOOD but could be BETTER

### 1. **Two DB Instances = Confusion**
- `data/clarvisdb/` and `data/clarvis-brain/` are separate
- clarvisdb has structure (identity, preferences, etc.)
- clarvis_brain has goals + context
- **Recommendation:** Consolidate into ONE database

### 2. **Graph layer disconnected**
- relationships.json exists but not queried during recall
- Graph provides context but isn't used in results
- **Recommendation:** Integrate graph into recall path

### 3. **Importance scoring is static**
- Rules-based (keyword detection)
- Doesn't learn from user feedback
- **Recommendation:** Allow manual importance override

### 4. **No auto-capture**
- Memories must be explicitly stored via CLI/import
- Not listening to conversation automatically
- **Recommendation:** Wire into message processing

### 5. **Bootstrap is manual**
- Only runs when explicitly called
- First-time setup requires running `python clarvisdb.py bootstrap`
- **Recommendation:** Auto-bootstrap on first run

---

## Roadmap (Prioritized)

### Phase 1: Consolidation (Do First)
1. **Merge DBs** — Move clarvis_brain collections into clarvisdb
2. **Fix auto-load** — Actually load clarvisdb on session start
3. **Auto-bootstrap** — Run bootstrap if collections empty

### Phase 2: Enhancement
4. **Importance filtering** — Add `min_importance` param to recall
5. **Temporal queries** — Add date range filters
6. **Graph-integrated recall** — Include related memories in results

### Phase 3: Intelligence
7. **Feedback loop** — User can rate memories ("remember this better")
8. **Auto-capture** — Hook into message processing
9. **Memory decay** — Prune low-importance, old memories

---

## Integration Points

### OpenClaw
- Currently NOT wired into message processing
- Could be exposed as tool: `clarvis_recall`, `clarvis_store`
- MCP server optional but not critical

### Clarvis Session
- AGENTS.md configured to load on startup
- BUT: Not actually executing the import in current session
- **FIX NEEDED:** Actually call the import in session init

### File Memory
- Daily memory files still primary for raw logs
- ClarvisDB supplements with semantic search
-两者互补 — ClarvisDB for "what did I learn about X", files for "what happened today"

---

## Files Reference

| File | Purpose |
|------|---------|
| `scripts/clarvisdb.py` | Core vector DB layer |
| `scripts/clarvisdb_graph.py` | Graph relationship layer |
| `scripts/clarvisdb_integrate.py` | High-level API |
| `scripts/clarvisdb_cli.py` | Command-line tool |
| `scripts/clarvis_brain.py` | **SEPARATE** brain system (needs merge) |
| `data/clarvisdb/` | Vector DB storage |
| `data/clarvis-brain/` | **SEPARATE** brain storage (needs merge) |
| `skills/clarvisdb/SKILL.md` | Documentation |
| `scripts/clarvisdb_benchmark.py` | Test suite |

---

## Action Items

1. [ ] **Test auto-load** — Verify AGENTS.md import actually runs
2. [ ] **Consolidate databases** — Merge clarvisdb + clarvis_brain
3. [ ] **Add importance filter** — `recall(query, min_importance=0.7)`
4. [ ] **Wire into messages** — Auto-capture important info from chats

---

*Generated: 2026-02-20 — Clarvis Memory System Analysis*
