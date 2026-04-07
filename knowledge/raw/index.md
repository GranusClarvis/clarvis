# Raw Sources

_Layer 1 — immutable source evidence. Files here are append-only once ingested._

## Subdirectories

- **[papers/](papers/)** — PDFs and extracted markdown from academic papers
- **[web/](web/)** — Web page snapshots (markdown + metadata)
- **[repos/](repos/)** — Repo analyses, README extracts, structure summaries
- **[images/](images/)** — Diagrams, screenshots, figures referenced by wiki pages
- **[transcripts/](transcripts/)** — Meeting notes, conversation excerpts

## Naming Convention

Raw files use deterministic slugs: `{date}-{type}-{hash8}.md`
Example: `2026-04-07-paper-a3f1c2d0.md`

## Deletion Policy

Archive to `raw/.archive/`, never delete.
