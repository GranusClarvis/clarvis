# Contributing to Clarvis

## Setup

```bash
git clone git@github.com:GranusClarvis/clarvis.git
cd clarvis
bash scripts/infra/setup.sh --dev --verify
python3 -m pytest -m "not slow"
```

## Code Structure

All shared library logic lives in the `clarvis/` spine package. Scripts in `scripts/`
are operational entry points that import from `clarvis.*`.

```
clarvis/          # Spine package — all core logic
scripts/          # Cron jobs, CLI wrappers, tools
tests/            # pytest suite
```

### Import Conventions

**Spine imports** (all code uses these):
```python
from clarvis.brain import brain, search, remember
from clarvis.cognition.attention import attention
from clarvis.orch.cost_tracker import log as cost_log
```

**Cross-script imports** use the script loader (no sys.path hacks):
```python
from clarvis._script_loader import load as _load_script
wiki_hooks = _load_script("wiki_hooks", "wiki")
```

### Layer Rules

```
Layer 0: clarvis.brain       → external only (chromadb, onnxruntime)
Layer 1: clarvis.memory      → brain
Layer 2: clarvis.cognition   → brain, memory
Layer 2: clarvis.context     → brain, memory, cognition
Layer 3: clarvis.heartbeat   → all lower layers
Layer 3: clarvis.orch        → all lower layers

Lower layers never import upper layers.
```

Brain uses **dependency inversion** via hook registries — external modules register
scoring/boosting/observer hooks instead of being imported by brain directly.

## Testing

```bash
python3 -m pytest                     # Full suite
python3 -m pytest -m "not slow"       # Fast subset
python3 -m pytest tests/test_cli.py   # CLI smoke tests
bash scripts/infra/verify_install.sh  # Post-install verification
```

## Conventions

- **CLI**: `clarvis` uses Typer with lazy subcommand registration for fast startup
- **Locking**: Claude Code spawners use `/tmp/clarvis_claude_global.lock` (flock)
- **Cron**: All cron scripts source `scripts/cron/cron_env.sh` for env bootstrap
- **Data formats**: `.json` for state, `.jsonl` for append-only logs, `.md` for human-readable
- **Logging**: `print()` for scripts, `logging` module for long-lived services
