# BOOT.md — Clarvis Session Init

This file runs automatically on gateway startup. Initialize ClarvisDB brain.

## Instructions

1. Load the brain immediately:
```python
import sys
sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
from brain import brain, search, remember, capture
from clarvis_memory import clarvis_context
```

2. Verify brain is working:
```python
ctx = clarvis_context()
stats = brain.stats()
```

3. Verify self-awareness:
- Confirm `SELF.md` exists and is readable
- You know your harness (OpenClaw), your body (NUC), your brain (ClarvisDB)
- You know how to safely restart, clone yourself, and test changes

4. Log startup status:
- Total memories in brain
- Current context
- Brain health

5. Check if any important context from last session:
- Review recent memories (last 24h)
- Check goals progress
- Note any pending tasks

## Output

Reply with ONLY: NO_REPLY (silent startup, no notification needed)

If there's something urgent that needs attention, reply with the alert instead of NO_REPLY.
