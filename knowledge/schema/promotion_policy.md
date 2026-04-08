# Wiki Promotion Policy

_Created 2026-04-08. Defines what content earns a wiki page and what stays excluded._

---

## Purpose

The wiki (Layer 2) is the **curated, durable knowledge surface**. Not everything Clarvis produces belongs here. This policy defines promotion criteria so the wiki stays high-signal and the compile engine can auto-enforce quality gates.

---

## Promotable Content Types

### 1. Research Notes → `concept` or `paper` pages

**Promote when:**
- The note covers a distinct concept, technique, or finding (not just a task log)
- At least one cited source exists (paper, URL, or raw artifact)
- The content is self-contained — understandable without reading the originating task context
- The finding has durable relevance (useful beyond the current sprint)

**Typical sources:** `memory/research/runs/*/`, `memory/research/ingested/`

### 2. Paper Summaries → `paper` pages

**Promote when:**
- A paper was read and summarized with: title, authors, key claims, relevance to Clarvis
- At least 3 key claims are extracted and cited
- The paper is from a credible venue or has clear technical merit

**Typical sources:** PDFs in `knowledge/raw/papers/`, arXiv links

### 3. Durable Procedures → `procedure` pages

**Promote when:**
- The procedure has been validated (executed at least once successfully)
- It describes a repeatable workflow, not a one-off fix
- Steps are concrete and actionable (commands, file paths, expected outputs)
- It is not already documented in `CLAUDE.md`, `AGENTS.md`, or inline code comments

**Typical sources:** `memory/cron/`, operator instructions, postmortem action items

### 4. Repository Analyses → `repo` pages

**Promote when:**
- The repo is actively relevant to Clarvis (dependency, reference implementation, or project)
- Analysis includes: purpose, architecture summary, notable files, and Clarvis relationship
- Not a drive-by mention — the repo was actually examined

**Typical sources:** `knowledge/raw/repos/`, GitHub exploration artifacts

### 5. High-Value Operator Q&A → `question` pages

**Promote when:**
- The question required non-trivial research or synthesis to answer
- The answer is reusable (someone might ask this again)
- The answer draws on multiple sources or wiki pages
- The operator confirmed the answer was useful (explicit or implicit)

**Typical sources:** conversation logs, Telegram interactions, spawn task results

### 6. Cross-Cutting Syntheses → `synthesis` pages

**Promote when:**
- The synthesis connects 3+ existing wiki pages or concepts
- It identifies a pattern, contradiction, or gap not visible from individual pages
- It has clear architectural or strategic implications

---

## Excluded Content (Never Promote)

These content types are **explicitly excluded** from wiki promotion:

| Category | Examples | Why Excluded |
|----------|----------|--------------|
| **Heartbeat noise** | Preflight/postflight logs, attention scores, gate results | Transient operational telemetry; belongs in `data/` and episode logs |
| **Routine cron output** | Digest summaries, watchdog alerts, health check logs | Operational exhaust; belongs in `memory/cron/` and `monitoring/` |
| **Transient task logs** | Queue execution records, sprint logs, evolution attempts | Work-in-progress artifacts; valuable for episodes, not for wiki |
| **Cost/budget data** | Cost reports, budget alerts, token counts | Time-series operational data; lives in `data/costs/` |
| **Raw conversation logs** | Unprocessed chat transcripts, M2.5 session dumps | Unfiltered; extract insights as Q&A or concept pages instead |
| **Debugging artifacts** | Error traces, one-off diagnostic scripts, tmp files | Ephemeral by nature |
| **Duplicate/near-duplicate content** | Same concept already covered by existing page | Merge into canonical page per schema_rules.md |
| **Low-confidence speculation** | Untested hypotheses without supporting evidence | Wait until evidence exists; park in `## Open Questions` on related pages |
| **Configuration snapshots** | Crontab dumps, env exports, JSON config copies | These change constantly; document the *why* not the *what* |
| **Performance metrics** | Benchmark results, PI scores, Brier calibration data | Time-series data for `data/`; only promote if analysis reveals a durable insight |

---

## Promotion Criteria (Quality Gates)

Every candidate for promotion must pass these gates:

### Gate 1: Atomicity
- **One concept per page.** If the note covers multiple unrelated topics, split before promoting.
- Target: 20-800 lines after frontmatter (per schema_rules.md size thresholds).

### Gate 2: Source Citation
- **At least one verifiable source.** Every `## Key Claims` entry must cite a source.
- Self-citations and circular references don't count.
- Raw source must exist in `knowledge/raw/` or be a valid external URL.

### Gate 3: Self-Containment
- **Understandable without originating context.** A reader who didn't see the research task, conversation, or cron run should grasp the page.
- No dangling references to "the task above" or "as discussed."

### Gate 4: Durability
- **Still relevant in 30+ days?** If the content is likely stale within a month, it doesn't belong.
- Time-bound content (event recaps, dated comparisons) must have lasting analytical value.

### Gate 5: Non-Duplication
- **No existing page covers this.** Check aliases, tags, and search before creating.
- If a related page exists: update it rather than creating a new one.

### Gate 6: Minimum Substance
- **Paper pages**: ≥3 key claims extracted.
- **Concept pages**: ≥2 sentences summary + ≥1 key claim.
- **Procedure pages**: ≥3 concrete steps.
- **Repo pages**: purpose + architecture summary + Clarvis relationship.
- **Question pages**: both question and answer present (even if partial).

---

## Promotion Workflow

```
Source Material
    │
    ▼
[Ingest into knowledge/raw/]
    │
    ▼
[Apply Quality Gates 1-6]
    │
    ├── FAIL any gate → Stay in raw/, log reason
    │                    Flag for future re-evaluation if close
    │
    └── PASS all gates
         │
         ▼
    [Compile into wiki page]
         │
         ├── Existing page? → Update + merge claims + add source
         │
         └── New concept? → Create page from template
              │
              ▼
         [Sync to ClarvisDB]
         [Update backlinks]
         [Update indexes]
```

### Status Lifecycle

New wiki pages enter as `draft`, then progress:

1. **`draft`** — Created from raw source, may be incomplete. Acceptable for initial promotion.
2. **`active`** — Reviewed, multi-sourced, backlinked. The target state.
3. **`stale`** — No update in >90 days. Flagged by lint for review or archival.
4. **`archived`** — No longer relevant. Kept for provenance but excluded from indexes and embeddings.

---

## Automated Enforcement

The compile engine and lint engine should enforce these rules:

| Check | Enforcement |
|-------|-------------|
| Missing source citation | Lint error — block promotion |
| Duplicate slug or alias collision | Lint error — require merge |
| Below minimum substance | Lint warning — allow as `draft` only |
| Above 800 lines | Lint warning — suggest split |
| Below 20 lines | Lint warning — suggest merge |
| Stale (>90 days unchanged) | Lint warning — flag for review |
| Excluded content type detected | Compile engine rejects — log reason |

---

## Edge Cases

### Research that partially qualifies
If a research note contains both promotable insights and transient exhaust, extract the promotable portion into a wiki page and leave the rest in `memory/research/`.

### Operator override
The operator can force-promote any content with an explicit command. Force-promoted pages should still have frontmatter and follow the schema, but can skip the durability gate. Mark with tag `operator/force-promoted`.

### Evolving confidence
A page can be promoted at `confidence: low` if it meets all other gates. The compile engine should upgrade confidence when additional corroborating sources are added (2+ sources → `medium`, 3+ independent sources → `high`).

### Calibration/metrics insights
While raw benchmark data is excluded, if analysis of metrics reveals a **durable architectural insight** (e.g., "SQLite graph queries are O(n) on unindexed edges — always index"), that insight qualifies as a `concept` or `procedure` page. The Brier score threshold observation (0.105 vs target 0.1) does NOT qualify on its own — it's a time-series data point. Only promote if the investigation reveals *why* calibration drifts and *how* to fix it.

---

## Relation to Other Policies

- **schema_rules.md**: Defines page structure, frontmatter, and naming. This policy defines *what earns a page*.
- **source_registry (sources.jsonl)**: Tracks all ingested raw material. Promotion policy decides which raw entries get compiled forward.
- **Archive policy (in schema_rules.md)**: Governs end-of-life. This policy governs beginning-of-life.
- **WIKI_COMPILE_ENGINE**: The compile engine implements these gates programmatically.
- **WIKI_LINT_ENGINE**: The lint engine verifies ongoing compliance.
