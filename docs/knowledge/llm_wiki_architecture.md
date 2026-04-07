# LLM Wiki Architecture — Three-Layer Knowledge Model

_Created 2026-04-07. Canonical spec for the Clarvis knowledge layer._

---

## Purpose

Clarvis already has a strong memory system (ClarvisDB: ChromaDB vectors + graph edges). But memory stores **fragments** — embeddings of episodic events, learned procedures, and contextual notes. It excels at recall ("what did I learn about X?") but not at **compiled knowledge** ("what is the current state of knowledge on X, with sources?").

The wiki layer adds durable, citable, human-readable knowledge pages that sit *between* raw source evidence and the vector/graph substrate. It does not replace ClarvisDB — it complements it by providing a structured compilation layer that ClarvisDB can index and retrieve from.

---

## Three Layers

```
┌──────────────────────────────────────────────────────────────┐
│  Layer 3: ClarvisDB + Graph Memory                           │
│  (retrieval & reasoning substrate)                           │
│  ChromaDB embeddings, graph edges, episodic/procedural mem   │
│  ← indexes Layer 2 pages + Layer 1 raw artifacts             │
├──────────────────────────────────────────────────────────────┤
│  Layer 2: knowledge/wiki/                                    │
│  (compiled markdown pages — the "wiki")                      │
│  Concept pages, paper summaries, syntheses, timelines        │
│  ← compiled FROM Layer 1 raw sources                         │
├──────────────────────────────────────────────────────────────┤
│  Layer 1: knowledge/raw/                                     │
│  (source evidence — immutable once ingested)                 │
│  PDFs, web snapshots, repo analyses, transcripts, images     │
└──────────────────────────────────────────────────────────────┘
```

### Layer 1 — Raw Sources (`knowledge/raw/`)

**What**: Original source artifacts, stored as-is or converted to markdown.

**Subdirectories**:
- `raw/papers/` — PDFs and extracted markdown from academic papers
- `raw/web/` — Web page snapshots (markdown + metadata)
- `raw/repos/` — Repo analyses, README extracts, structure summaries
- `raw/images/` — Diagrams, screenshots, figures referenced by wiki pages
- `raw/transcripts/` — Meeting notes, conversation excerpts

**Invariants**:
- Raw files are **append-only** — once ingested, the file content does not change.
- Each raw file has a corresponding entry in the source registry (`knowledge/logs/sources.jsonl`).
- Raw files are identified by a deterministic slug: `{date}-{type}-{hash8}.md` (e.g., `2026-04-07-paper-a3f1c2d0.md`).
- Deletion is by archive (move to `raw/.archive/`), not by removal.

### Layer 2 — Wiki Pages (`knowledge/wiki/`)

**What**: Compiled, structured markdown pages that synthesize raw sources into durable knowledge.

**Subdirectories**:
- `wiki/concepts/` — Concept/topic pages (one canonical page per concept)
- `wiki/projects/` — Project overviews and status
- `wiki/people/` — Person/org profiles
- `wiki/syntheses/` — Cross-cutting synthesis documents
- `wiki/questions/` — Research questions with current best answers
- `wiki/timelines/` — Chronological event sequences
- `wiki/indexes/` — Auto-generated navigation pages
- `wiki/procedures/` — Durable how-to guides

**Invariants**:
- **One canonical page per concept** — aliases and redirects, not duplicates.
- Every claim should cite a Layer 1 source or an external reference.
- Pages have required YAML frontmatter (see `knowledge/schema/`).
- Pages include an `## Update History` section tracking significant changes.
- **Backlinks are mandatory** — if page A references page B, page B should list A.
- Maximum recommended page size: 800 lines. Split into sub-pages beyond that.
- Minimum useful page size: 20 lines (below that, merge into a parent page).

### Layer 3 — ClarvisDB + Graph Memory

**What**: The existing vector + graph memory system. Unchanged architecturally. Gains a new data source (wiki pages).

**New behavior with wiki layer**:
- When a wiki page is created or updated, its content is embedded into ClarvisDB (collection: `clarvis-learnings` or a dedicated `wiki-pages` collection).
- Graph edges are created for typed relations extracted from wiki pages: `mentions`, `supports`, `contradicts`, `derived_from`, `extends`, `about_project`, `about_person`.
- The retrieval pipeline gains a **wiki-first path**: for research queries, prefer wiki page hits, then expand through linked raw sources and graph neighbors.

**What does NOT change**:
- Existing episodic, procedural, and identity memories remain in their current collections.
- The heartbeat/postflight pipeline continues to store episodes as before.
- Graph compaction, decay, and maintenance operate normally.

---

## Data Flow

```
  Source (URL, PDF, repo, note)
       │
       ▼
  ┌─────────────┐
  │   INGEST     │  Store raw artifact → knowledge/raw/
  │              │  Register in sources.jsonl
  │              │  Extract entities, concepts, claims
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │   COMPILE    │  Create or update wiki page → knowledge/wiki/
  │              │  Add citations, backlinks, frontmatter
  │              │  Resolve canonical page (dedup)
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │    SYNC      │  Embed wiki page into ClarvisDB
  │              │  Create/update graph edges
  │              │  Index for retrieval
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │  RETRIEVE    │  Query hits wiki page first
  │              │  Expand via graph neighbors + raw sources
  │              │  Return cited, structured answer
  └─────────────┘
```

### Ingest → Compile → Sync → Retrieve

1. **Ingest**: A source enters via CLI (`clarvis wiki ingest <url|path>`). The raw artifact is stored, checksummed, and registered. Entities and concepts are extracted (heuristic or LLM-assisted).

2. **Compile**: The compile engine checks if relevant wiki pages exist. If yes, it proposes updates. If no, it creates a new page from the template matching the source type. All changes are logged in the page's update history.

3. **Sync**: On page save, the sync hook embeds the page content into ClarvisDB and creates graph edges for all typed relations found in the page. This makes the wiki page discoverable through the standard `brain.search()` pathway.

4. **Retrieve**: When answering a research question, the retrieval pipeline checks wiki pages first (high-quality compiled knowledge), then expands through graph neighbors and raw sources for supporting evidence. Answers cite specific wiki pages and raw sources.

---

## Why This Complements ClarvisDB (Not Replaces It)

| Dimension | ClarvisDB | Wiki Layer |
|-----------|-----------|------------|
| **Unit of storage** | Embedding chunk (~200 tokens) | Full page (50-800 lines) |
| **Update model** | Append + decay | Edit in place + history |
| **Citation** | Implicit (embedding proximity) | Explicit (source links) |
| **Readability** | Machine-first | Human-readable markdown |
| **Structure** | Flat collections + graph edges | Hierarchical dirs + typed pages |
| **Best for** | Fast associative recall | Compiled reference knowledge |
| **Maintenance** | Automated (decay, compaction) | Semi-automated (lint, compile) |

ClarvisDB is the **fast associative memory** — it answers "what do I vaguely remember about X?" in milliseconds. The wiki is the **compiled reference** — it answers "what is the authoritative, cited summary of X?" with structure and provenance.

Together:
- ClarvisDB provides the retrieval substrate (search finds wiki pages via embeddings).
- Wiki provides the knowledge quality (structured, cited, deduplicated, maintained).
- Raw sources provide the evidence chain (original artifacts for verification).

---

## Invariants (System-Wide)

1. **No orphan wiki pages**: Every wiki page must cite at least one source (Layer 1 raw file or external URL).
2. **No orphan raw files**: Every raw file should be linked from at least one wiki page within 30 days of ingest (lint warning, not hard error).
3. **Single source of truth**: One canonical wiki page per concept. Aliases resolve via frontmatter `aliases:` field.
4. **Audit trail**: Every ingest and compile event is logged to `knowledge/logs/sources.jsonl`.
5. **Separation of concerns**: Raw files are evidence (immutable). Wiki pages are synthesis (editable). ClarvisDB is index (auto-maintained).
6. **Graceful degradation**: If the wiki layer is empty or broken, ClarvisDB continues to function normally. The wiki is additive.

---

## File Layout

```
knowledge/
├── raw/                        # Layer 1: Source evidence
│   ├── papers/
│   ├── web/
│   ├── repos/
│   ├── images/
│   ├── transcripts/
│   └── .archive/               # Soft-deleted raw files
├── wiki/                       # Layer 2: Compiled pages
│   ├── concepts/
│   ├── projects/
│   ├── people/
│   ├── syntheses/
│   ├── questions/
│   ├── timelines/
│   ├── indexes/
│   └── procedures/
├── schema/                     # Page type definitions & templates
│   ├── schema_rules.md         # Frontmatter, naming, policies
│   └── templates/              # Page templates by type
│       ├── concept.md
│       ├── paper.md
│       ├── repo.md
│       ├── person.md
│       ├── question.md
│       ├── synthesis.md
│       ├── timeline.md
│       └── procedure.md
├── outputs/                    # Generated artifacts
│   ├── slides/
│   ├── diagrams/
│   └── charts/
├── logs/                       # Operational logs
│   ├── sources.jsonl           # Source registry
│   └── lint-log.md             # Lint/health reports
└── index.md                    # Vault root navigation
```

---

## Integration Points

| System | Integration |
|--------|-------------|
| **Brain search** | Wiki pages embedded into ClarvisDB; retrievable via `brain.search()` |
| **Graph** | Typed edges extracted from wiki page relations |
| **Heartbeat** | Postflight can promote high-value task outputs to wiki |
| **Research cron** | Research pipeline outputs ingested as raw sources, compiled to wiki pages |
| **Operator** | Obsidian opens `knowledge/` as vault for browsing/editing |
| **CLI** | `clarvis wiki ingest|query|lint|rebuild-index|backfill` |

---

## Design Decisions

**Why markdown, not a database?** Markdown is LLM-native (tokenizes efficiently), human-editable, git-trackable, and Obsidian-compatible. ClarvisDB already handles the database role.

**Why separate raw and wiki?** Raw sources are immutable evidence. Wiki pages are living syntheses. Mixing them creates provenance ambiguity — you can't tell if a statement is original source or Clarvis's interpretation.

**Why not just stuff everything into ClarvisDB?** Embedding chunks lose structure, citation chains, and human readability. A 3000-word concept page with sections, citations, and history is more useful than 15 disconnected 200-token chunks in a vector store.

**Why Obsidian-compatible?** The operator can browse, search, and edit the knowledge base with a mature tool. Graph view shows concept relationships. No custom UI needed for the MVP.
