# ClarvisBrain Skill

## Purpose
Auto-operating memory system for Clarvis. This IS my brain - it runs automatically on every message.

## How It Works

### Auto-Import
```python
import sys
sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
from clarvis_brain import get_brain

# Get brain instance (singleton)
brain = get_brain()
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
# In any response handler:
brain = get_brain()

# Set what I'm doing
brain.set_context("fixing bug in crypto alerts")

# Process incoming message - auto-stores important stuff
brain.process(message_text, source="telegram")

# Recall relevant memories
relevant = brain.recall("what does Inverse prefer about error handling")

# Update progress
brain.track_goal("ClarvisDB", 50, {"phase": "integration"})
```

## Design Principles

1. **Auto, not manual** - Never need to manually call "store"
2. **Importance detection** - Rules-based (can be ML later)
3. **Context aware** - Knows current topic/goal
4. **Goal tracking** - Always know progress toward AGI
5. **Persistent** - Chroma backend, survives restarts
