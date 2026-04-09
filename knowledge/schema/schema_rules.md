# Wiki Schema Rules

_Created 2026-04-07. Canonical schema for `knowledge/wiki/` pages._

---

## Page Types

Each wiki page belongs to exactly one type, determined by its directory and frontmatter `type:` field.

| Type | Directory | Purpose |
|------|-----------|---------|
| `concept` | `wiki/concepts/` | A topic, technique, framework, or idea |
| `paper` | `wiki/concepts/` | An academic paper or technical report |
| `repo` | `wiki/projects/` | A software repository or project |
| `person` | `wiki/people/` | A person or organization |
| `question` | `wiki/questions/` | A research question with evolving answers |
| `synthesis` | `wiki/syntheses/` | Cross-cutting analysis combining multiple sources |
| `timeline` | `wiki/timelines/` | Chronological sequence of events |
| `procedure` | `wiki/procedures/` | A durable how-to guide or workflow |
| `index` | `wiki/indexes/` | Auto-generated navigation page (no manual edits) |

---

## Required YAML Frontmatter

Every wiki page (except `index` type) must include this frontmatter block:

```yaml
---
title: "Human-readable page title"
slug: "kebab-case-canonical-slug"
type: concept|paper|repo|person|question|synthesis|timeline|procedure
created: 2026-04-07
updated: 2026-04-07
status: draft|active|stale|archived
tags:
  - category/subcategory
aliases:
  - "Alternative Name"
  - "Abbreviation"
sources:
  - raw/paper/2026-04-07-paper-a3f1c2d0.md
  - https://arxiv.org/abs/2508.13171
confidence: high|medium|low
---
```

### Field Definitions

| Field | Required | Description |
|-------|----------|-------------|
| `title` | Yes | Display title. Sentence case. |
| `slug` | Yes | Canonical identifier. Kebab-case. Must be unique across the entire wiki. |
| `type` | Yes | One of the defined page types. |
| `created` | Yes | ISO date of page creation. |
| `updated` | Yes | ISO date of last significant edit. |
| `status` | Yes | `draft` (incomplete), `active` (maintained), `stale` (>90 days without update), `archived` (no longer relevant). |
| `tags` | Yes | At least one tag from the taxonomy. |
| `aliases` | No | Alternative names that resolve to this page. Used for dedup and search. |
| `sources` | Yes | At least one source: relative path to `knowledge/raw/` file or external URL. |
| `confidence` | No | Overall confidence in page content. Default: `medium`. |

### Additional Fields by Type

**`paper` type** adds:
```yaml
authors: ["Last, First", "Last, First"]
year: 2026
venue: "Conference or Journal"
arxiv: "2508.13171"
```

**`repo` type** adds:
```yaml
repo_url: "https://github.com/org/repo"
language: ["Python", "TypeScript"]
maintained: true|false
```

**`person` type** adds:
```yaml
affiliation: "Organization"
role: "Researcher|Engineer|Founder"
```

**`question` type** adds:
```yaml
answer_status: open|partial|resolved
priority: high|medium|low
```

**`timeline` type** adds:
```yaml
date_range: "2025-01 to 2026-04"
```

---

## Tag Taxonomy

Tags use a two-level hierarchy: `category/topic`. A page should have 1-5 tags.

### Categories

| Category | Covers |
|----------|--------|
| `ai/` | AI/ML techniques, models, benchmarks |
| `memory/` | Memory systems, retrieval, knowledge management |
| `cognition/` | Cognitive architectures, reasoning, attention |
| `infra/` | Infrastructure, deployment, tooling |
| `project/` | Specific projects and repositories |
| `research/` | Research methodology, findings, open questions |
| `web3/` | Blockchain, smart contracts, DeFi |
| `agent/` | Agent architectures, orchestration, tool use |

### Example Tags

- `ai/retrieval-augmented-generation`
- `memory/episodic`
- `cognition/global-workspace-theory`
- `infra/chromadb`
- `project/clarvis`
- `research/survey`
- `agent/multi-agent`

New subcategories can be added freely. New top-level categories require updating this document.

---

## Naming Conventions

### File Names

- **Format**: `{slug}.md` where slug matches the frontmatter `slug:` field.
- **Style**: kebab-case, lowercase, ASCII only.
- **Length**: 3-60 characters.
- **Examples**: `integrated-information-theory.md`, `chromadb.md`, `arxiv-2508-13171.md`

### Canonical Slug Policy

- Each concept/entity has exactly one canonical slug.
- The `aliases:` frontmatter field lists alternative names.
- If two pages cover the same concept, they must be merged (see Merge/Split Policy).
- Slugs are permanent once assigned. Renaming creates a redirect file:
  ```yaml
  ---
  redirect: "new-slug"
  ---
  ```

---

## Citation Rules

### Internal Citations

Link to other wiki pages using relative markdown links:

```markdown
See [Integrated Information Theory](../concepts/integrated-information-theory.md) for details.
```

### Source Citations

Reference raw sources or external URLs in the `## Evidence` section:

```markdown
## Evidence

- **[Source 1]**: Description of claim. [raw/paper/2026-04-07-paper-a3f1c2d0.md]
- **[Source 2]**: Description of claim. [https://arxiv.org/abs/2508.13171]
```

### Citation Requirements

- Every factual claim in `## Key Claims` must have at least one citation.
- Uncited claims are flagged by the lint engine.
- Self-referential citations (citing the same wiki page) are not valid sources.

---

## Backlink Expectations

- If page A links to page B, page B should list A in its `## Related Pages` section.
- Backlinks are maintained by the compile engine and verified by lint.
- Missing backlinks generate lint warnings, not errors.

---

## Page Size Thresholds

| Threshold | Action |
|-----------|--------|
| < 20 lines (excluding frontmatter) | **Merge candidate** — consider folding into a parent page. |
| 20-800 lines | **Normal range** — no action needed. |
| > 800 lines | **Split candidate** — extract subsections into sub-pages and link from a summary page. |

Line counts exclude frontmatter and blank lines.

---

## Merge/Split Policy

### Merge (Combine Pages)

Trigger: Two pages cover the same concept, or a page is below the minimum size threshold.

Process:
1. Choose the page with the better slug as canonical.
2. Merge content, deduplicate claims, combine source lists.
3. Replace the non-canonical page with a redirect.
4. Update all backlinks.
5. Log the merge in `## Update History` of the surviving page.

### Split (Break Apart)

Trigger: A page exceeds 800 lines or covers multiple distinct concepts.

Process:
1. Extract coherent subsections into new pages with their own frontmatter.
2. Replace extracted content with a summary + link in the parent page.
3. Ensure all sources are distributed to the appropriate child pages.
4. Log the split in `## Update History`.

---

## Archive Policy

### When to Archive

- The concept/project is no longer active or relevant.
- Information has been superseded by a newer page.
- Source material has been retracted or discredited.

### How to Archive

1. Set `status: archived` in frontmatter.
2. Add an archive note at the top of the page body:
   ```markdown
   > **Archived 2026-04-07**: Reason for archival.
   ```
3. Archived pages remain in their original directory (not moved).
4. Archived pages are excluded from index generation but remain linkable.
5. Archived pages are not synced to ClarvisDB (removed from embeddings on next sync).

---

## Page Structure (All Types)

Every wiki page follows this section order after frontmatter:

1. **Title** (H1) — matches frontmatter `title:`
2. **Summary** — 2-4 sentence overview
3. **Key Claims** — Bulleted list of main assertions, each cited
4. **Evidence** — Sources with descriptions
5. _(Type-specific sections — see templates)_
6. **Related Pages** — Links to other wiki pages (including backlinks)
7. **Open Questions** — Unresolved issues or follow-ups
8. **Update History** — Dated log of significant changes

Sections may be empty but should not be omitted (keeps structure consistent for LLM parsing).
