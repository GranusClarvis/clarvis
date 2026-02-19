# ClarvisBrain Auto-Integration Skill

## Purpose
Automatically process all messages through ClarvisBrain on every session.

## How It Works

This skill auto-loads on session start and ensures:
1. Brain is initialized (singleton)
2. Every message gets processed for important info
3. Relevant memories are recalled before responding

## Integration

Add to AGENTS.md session start:
```python
import sys
sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
from clarvis_brain import get_brain
brain = get_brain()
```

## Usage

The brain automatically:
- Stores important info (importance > 0.5)
- Tracks context
- Updates goal progress

## To Use Before Responding

```python
# Before responding to user:
brain.set_context("working on [current task]")
relevant = brain.recall(user_query)
# Use relevant memories in response
```

## What's Fixed
- Brain auto-loads on session start
- Message processing integrated
- Context tracking automatic
