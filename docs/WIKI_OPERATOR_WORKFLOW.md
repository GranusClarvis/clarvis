# Wiki Operator Workflow

The Clarvis wiki is a source-grounded knowledge vault. The operator interacts with it through six actions, all exposed via `clarvis wiki <action>`.

## Actions

### 1. Drop a source

```bash
clarvis wiki drop <file-or-url> [--type paper|web|repo|transcript] [--title "..."]
```

Accepts a file path, URL, or GitHub repo URL. Ingests the source into `knowledge/raw/`, deduplicates by content hash and URL, then auto-compiles it into a wiki page under `knowledge/wiki/`. The operator's intent to drop is the promotion gate — no further qualification needed.

**Examples:**
```bash
clarvis wiki drop https://arxiv.org/pdf/2508.13171.pdf --title "Cognitive Workspace"
clarvis wiki drop ~/papers/scaling-laws.pdf --type paper
clarvis wiki drop https://github.com/anthropics/claude-code --type repo
clarvis wiki drop notes.md --type transcript
```

### 2. Ask a question

```bash
clarvis wiki query "What is IIT and how does it relate to consciousness?"
clarvis wiki query "Compare episodic vs semantic memory" --type synthesis
```

Searches wiki pages and raw sources, gathers context, and saves a structured answer as an artifact in `knowledge/wiki/questions/` (or `syntheses/` with `--type synthesis`). Answers are citation-grounded — every claim links back to a source.

**Browse answers:**
```bash
clarvis wiki list-answers           # List all saved Q&A artifacts
clarvis wiki show <slug>            # Display a specific answer
```

### 3. Promote an answer

```bash
clarvis wiki promote <slug> [--section concepts|syntheses|procedures] [--dry-run]
```

Takes a saved answer, synthesis, memo, or plan and promotes it into a permanent canonical wiki page. The slug comes from `list-answers` or `render-list`. Default target section is `syntheses/`.

**Example flow:**
```bash
clarvis wiki query "How does Hebbian learning work in ClarvisDB?"
clarvis wiki list-answers
clarvis wiki promote how-does-hebbian-learning-work --section concepts --dry-run
clarvis wiki promote how-does-hebbian-learning-work --section concepts
```

### 4. Open in Obsidian

```bash
clarvis wiki obsidian                    # Open vault root
clarvis wiki obsidian <slug>             # Open a specific page
clarvis wiki obsidian wiki/concepts/iit  # Open by path
```

Opens the wiki page in Obsidian (if installed), or prints the `obsidian://` URI and file path for manual use. The `knowledge/` directory is the Obsidian vault root — all wiki pages, raw sources, and outputs are browsable as a connected graph in Obsidian.

### 5. Generate slides / rendered output

```bash
clarvis wiki render slides "Clarvis architecture overview"
clarvis wiki render memo "Compare episodic vs semantic memory"
clarvis wiki render plan "Add adaptive RAG pipeline"
clarvis wiki render markdown "What is IIT?"
```

Renders wiki content into a presentation format. Output is saved to `knowledge/outputs/{answers,memos,plans,slides}/`. Slides use Marp format for PDF/PPTX export.

**Browse outputs:**
```bash
clarvis wiki render-list              # List all rendered outputs
clarvis wiki render-formats           # Show available formats
```

### 6. Lint / fix wiki

```bash
clarvis wiki lint                     # Full 9-check health report
clarvis wiki lint --check orphans     # Single check
clarvis wiki lint --json              # Machine-readable output
clarvis wiki lint-summary             # Quick issue counts
clarvis wiki maintenance full         # Auto-fix: lint + drift + promote
clarvis wiki maintenance lint         # Lint-only maintenance
clarvis wiki maintenance drift        # Detect stale/thin/uncompiled pages
clarvis wiki maintenance promote      # Promote research sources to wiki
```

Lint checks: orphan pages, broken links, missing citations, duplicates, stale pages, oversized pages, underspecified pages, uncovered sources, tag taxonomy violations.

## Quick Reference

| I want to...              | Command                                          |
|---------------------------|--------------------------------------------------|
| Add a paper/URL/file      | `clarvis wiki drop <source>`                     |
| Ask the wiki a question   | `clarvis wiki query "question"`                  |
| Promote an answer to wiki | `clarvis wiki promote <slug>`                    |
| Browse in Obsidian        | `clarvis wiki obsidian [page]`                   |
| Generate a slide deck     | `clarvis wiki render slides "topic"`             |
| Check wiki health         | `clarvis wiki lint`                              |
| See vault stats           | `clarvis wiki status`                            |
| Auto-fix issues           | `clarvis wiki maintenance full`                  |
| Sync wiki to brain        | `clarvis wiki sync`                              |

## Data Flow

```
Operator drops source
  → knowledge/raw/{type}/{id}.md        (raw source + metadata)
  → knowledge/logs/sources.jsonl        (registry entry)
  → knowledge/wiki/{section}/{slug}.md  (compiled wiki page)

Operator asks question
  → wiki search + raw evidence gather
  → knowledge/wiki/questions/{slug}.md  (saved answer artifact)

Operator promotes answer
  → knowledge/wiki/{section}/{slug}.md  (canonical wiki page)

Operator renders output
  → knowledge/outputs/{format}/{slug}.md (presentation artifact)
```

## Automation

The wiki also self-maintains via cron:
- `wiki_hooks.py` auto-ingests research outputs from heartbeat tasks
- `wiki_maintenance.py` runs lint, drift detection, and source promotion
- `wiki_brain_sync.py` syncs wiki pages to ClarvisDB for retrieval
- All automation is fail-safe — exceptions never break the caller pipeline
