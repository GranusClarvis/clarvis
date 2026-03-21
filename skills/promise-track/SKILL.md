---
name: promise-track
description: "Record a promise/obligation when you commit to doing something going forward. Usage: /promise_track 'description'. Enforces Rule 4: speech = state transition."
metadata: {"clawdbot":{"emoji":"🤝"}}
user-invocable: true
---

# /promise_track — Record Durable Obligation

**When to use:** Any time you (Clarvis) say "I will do X going forward", "from now on I'll...",
"I'll handle that automatically", or make any commitment about future behavior.

**Rule 4 enforcement:** Speech without state transition is a bug. This skill records the
obligation durably so the heartbeat pipeline can enforce it.

## Usage

When invoked with a description:
```bash
python3 /home/agent/.openclaw/workspace/scripts/obligation_tracker.py add "$ARGUMENTS" --freq daily
```

When invoked without arguments, show current obligations:
```bash
python3 /home/agent/.openclaw/workspace/scripts/obligation_tracker.py status
```

## Auto-Detection Guidance

You MUST call this skill whenever your response contains any of these patterns:
- "I will ... going forward"
- "from now on I'll ..."
- "I'll make sure to ... automatically"
- "I'll handle that every ..."
- "I'll always/never ..."
- Any commitment to recurring future behavior

If you cannot enforce the promise (too vague, no check mechanism), tell the user
explicitly rather than making an empty promise.

## Response Format

After recording, confirm briefly:
> Recorded obligation: "[description]" (checked [frequency]).
> Heartbeat will enforce this automatically.
