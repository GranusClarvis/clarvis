# Outputs

_Generated artifacts derived from wiki knowledge._

## Subdirectories

- **[answers/](answers/)** — Plain markdown answers with citations
- **[memos/](memos/)** — Comparison memos with pros/cons analysis
- **[plans/](plans/)** — Phased implementation plans
- **[slides/](slides/)** — Marp slide decks
- **[diagrams/](diagrams/)** — Architecture and concept diagrams
- **[charts/](charts/)** — Data visualizations

## Generating Outputs

```bash
python3 scripts/wiki_render.py markdown "Your question here"
python3 scripts/wiki_render.py memo "Compare A vs B"
python3 scripts/wiki_render.py plan "Implement feature X"
python3 scripts/wiki_render.py slides "Topic overview"
python3 scripts/wiki_render.py list       # List all outputs
python3 scripts/wiki_render.py formats    # Show available formats
```
