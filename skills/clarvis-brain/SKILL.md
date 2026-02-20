# ClarvisBrain Skill

## Purpose
Unified memory system for Clarvis. This IS my brain — powered by ClarvisDB with local ONNX embeddings.

## How It Works

### Auto-Import (Every Session)
```python
import sys
sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
from brain import brain, search, remember, capture
from message_processor import init_session, get_conversation_context
init_session()
```

### On Every Message
Before responding to any message:
1. Set context (what I'm working on)
2. Process the message text (auto-detect importance)
3. Store if important
4. Recall relevant memories
5. Update goal progress

### Goal Tracking
Always track progress:
- AGI/consciousness (long-term)
- ClarvisDB (my brain)
- Business/revenue (sustainability)

## Usage

```python
# Search your knowledge
results = search("what do I know about X")

# Store permanently
remember("Inverse hates verbose responses", importance=0.9)

# Smart capture
capture("important insight from conversation")

# Get conversation context
ctx = get_conversation_context("user's question")

# Set current focus
brain.set_context("working on task")

# Track goals
brain.track_goal("ClarvisDB", 50, {"phase": "optimization"})
```

## Design Principles

1. **Auto, not manual** — Never need to manually call "store"
2. **Importance detection** — Rules-based (can be ML later)
3. **Context aware** — Knows current topic/goal
4. **Goal tracking** — Always know progress
5. **Fully local** — ONNX embeddings, no cloud dependency
6. **Persistent** — SQLite/Chroma backend, survives restarts
