# clarvis-code

Smart task routing, context compression, and session management for Claude Code / OpenCode autonomous agents.

- **TaskRouter** — classify task complexity and route to cheapest capable executor
- **ContextCompressor** — compress context to minimize token consumption
- **PromptBuilder** — build structured prompts with episodic/procedural hints
- **SessionManager** — manage session lifecycle and state persistence

## Installation

```bash
pip install clarvis-code
```

## Usage

```python
from clarvis_code import TaskRouter, ContextCompressor, PromptBuilder, SessionManager

# Route tasks to optimal executor
router = TaskRouter()
result = router.classify("Build a new REST API endpoint")
# -> {"tier": "complex", "executor": "claude", "score": 0.72, ...}

# Compress context for token efficiency
compressor = ContextCompressor()
brief = compressor.compress_queue("path/to/queue.md")

# Build structured prompts
builder = PromptBuilder()
prompt = builder.build("Fix the auth bug", context=brief, episodes=[...])

# Session lifecycle
session = SessionManager("/path/to/data")
session.open()
# ... do work ...
session.close(learnings=["Fixed auth bug via token refresh"])
```

## CLI

```bash
clarvis-code route "Build a new REST API endpoint"
clarvis-code compress path/to/queue.md
clarvis-code prompt "Fix auth bug" --context "JWT module..."
clarvis-code session open
clarvis-code session close
clarvis-code stats
```

## License

MIT
