# ClarvisEpisodic

ACT-R inspired episodic memory system with power-law decay and emotional valence scoring.

## Features

- **ACT-R Activation Decay** — Pavlik & Anderson (2005) spacing model. Decay rate adapts based on inter-retrieval lag: spaced repetitions slow forgetting, massed repetitions speed it up.
- **Emotional Valence** — Negativity bias (failures more memorable), novelty detection, salience weighting.
- **Keyword + Semantic Recall** — Falls back to keyword matching when ChromaDB is unavailable.
- **Episode Synthesis** — Analyzes patterns across episodes: outcome rates, error types, section performance.
- **Zero Dependencies** — Core runs on stdlib only. ChromaDB is optional for semantic search.

## Quick Start

```python
from clarvis_episodic import EpisodicStore

store = EpisodicStore("/tmp/my-episodes")

# Encode episodes
store.encode("Fixed auth bug", section="bugs", salience=0.8, outcome="success")
store.encode("Deploy timeout", section="ops", salience=0.9, outcome="failure",
             error_msg="Connection refused")

# Recall by keyword
episodes = store.recall("auth bug")

# Get failures (sorted by activation — most accessible first)
failures = store.failures()

# Statistics
stats = store.stats()

# Pattern synthesis
report = store.synthesize()
```

## CLI

```bash
# Encode
python -m clarvis_episodic encode "Fixed auth bug" bugs 0.8 success

# Recall
python -m clarvis_episodic recall "auth"

# Failures
python -m clarvis_episodic failures

# Stats
python -m clarvis_episodic stats

# Synthesis report
python -m clarvis_episodic synthesize

# Export/import
python -m clarvis_episodic export episodes.json
python -m clarvis_episodic import episodes.json
```

Set `EPISODIC_DATA_DIR` to control storage location (default: `./data`).

## ACT-R Model

Activation follows the Pavlik & Anderson (2005) spacing model:

```
A(i) = ln(sum(t_j^(-d_j)))
d_j = c * lag_j^(-1/gamma)
```

Where:
- `t_j` = age of the j-th access
- `lag_j` = inter-retrieval interval (hours)
- `c = 0.5` (base decay)
- `gamma = 1.6` (spacing strength)

The adaptive decay captures the **spacing effect**: memories reinforced at longer intervals decay more slowly than cramming.

## API

### `EpisodicStore(data_dir, max_episodes=500, chroma_collection=None, on_encode=None, on_recall=None)`

### `store.encode(task, section, salience, outcome, duration_s, error_msg, steps, metadata) -> episode`

### `store.recall(query, n=5) -> [episodes]`

### `store.failures(n=5) -> [episodes]`

### `store.stats() -> dict`

### `store.synthesize() -> dict`

### `store.forget(episode_id) -> bool`

### `store.export(path=None) -> str`

### `store.import_episodes(path, merge=True) -> int`

## Pure Functions

```python
from clarvis_episodic import compute_activation, compute_valence

# Activation from access timestamps
activation = compute_activation([1708700000, 1708750000, 1708800000])

# Emotional valence
valence = compute_valence("failure", salience=0.9, is_novel_error=True)
```
