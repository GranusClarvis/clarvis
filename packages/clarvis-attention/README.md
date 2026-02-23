# clarvis-attention

GWT attention spotlight: capacity-limited workspace with salience competition, decay, and broadcast hooks.

Based on Baars' Global Workspace Theory. Items compete for limited broadcast slots via salience scoring (importance, recency, relevance, access frequency, and external boost).

## Installation

```bash
pip install clarvis-attention
```

## Usage

```python
from clarvis_attention import AttentionSpotlight

spotlight = AttentionSpotlight(capacity=7)
spotlight.submit("important task", source="user", importance=0.9)
spotlight.submit("background noise", source="system", importance=0.2)
spotlight.tick()               # Run competition cycle

focus = spotlight.focus()       # Top-K conscious items
summary = spotlight.broadcast() # Push to registered hooks
```

### Spreading Activation

```python
results = spotlight.spreading_activation("memory architecture")
```

### Persistence

```python
# Export/import state
state = spotlight.to_dict()
restored = AttentionSpotlight.from_dict(state)
```

## CLI

```bash
clarvis-attention submit "important task" --source user --importance 0.9
clarvis-attention focus                    # Show current spotlight
clarvis-attention tick                     # Run competition cycle
clarvis-attention broadcast                # Show broadcast summary
clarvis-attention query "memory"           # Find relevant items
clarvis-attention activate "reasoning"     # Spreading activation
clarvis-attention stats                    # Statistics
clarvis-attention clear                    # Reset
clarvis-attention export                   # Export state JSON
clarvis-attention import state.json        # Import state
```

Environment variables:
- `ATTENTION_DATA_DIR` — persistence directory (default: `./data/attention`)
- `ATTENTION_CAPACITY` — spotlight capacity (default: 7)

## License

MIT
