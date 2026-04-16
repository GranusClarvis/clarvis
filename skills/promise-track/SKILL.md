---
name: promise-track
description: "Record a promise/obligation with smart classification (scope, confidence, emotional dampening). Usage: /promise_track 'description'. Enforces Rule 4: speech = state transition."
whenToUse: |
  When Clarvis makes a commitment like "I will do X", "from now on", "I'll handle
  that automatically", or any promise about future behavior. Auto-invoke to record
  the directive so the heartbeat pipeline can enforce it.
metadata: {"clawdbot":{"emoji":"🤝"}}
user-invocable: true
---

# /promise_track — Record Durable Directive

**When to use:** Any time you (Clarvis) say "I will do X going forward", "from now on I'll...",
"I'll handle that automatically", or make any commitment about future behavior.

**Rule 4 enforcement:** Speech without state transition is a bug. This skill records the
directive with smart classification so the heartbeat pipeline can enforce it appropriately.

## What it does

The directive engine automatically classifies instructions by:
- **Scope**: standing (permanent), window (temporary), one_shot (single use), session (conversation only)
- **Confidence**: how certain the classification is (0.0-1.0)
- **Literalness**: how literally to apply — emotional/hyperbolic wording is dampened (0.0-1.0)
- **Expiry**: window/one-shot directives auto-expire; standing ones sunset after 90d without reference

## Usage

When invoked with a description, include surrounding conversation context for better classification:
```bash
python3 $CLARVIS_WORKSPACE/scripts/hooks/directive_engine.py ingest "$ARGUMENTS" --source user --context "$CONTEXT"
```

**$CONTEXT**: Include 1-3 sentences of conversation context surrounding the promise — what the user said, what prompted the commitment, the emotional tone. This helps the directive engine classify scope and detect emotional dampening. If no clear context is available, omit the `--context` flag.

You may also specify priority: `--priority P0|P1|P2|P3` (default: P2).

When invoked without arguments, show current directive status:
```bash
python3 $CLARVIS_WORKSPACE/scripts/hooks/directive_engine.py status
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
> Recorded directive: "[description]" (scope: [scope], checked [frequency]).
> Heartbeat will enforce this — [standing/window/one-shot] with [literalness] literalness.

## Notes

- **Emotional dampening**: If the user's wording is angry/hyperbolic, the directive is still recorded
  but with lower literalness and confidence. It won't become a rigid permanent rule.
- **Window directives**: "This week..." or "for the next 3 days..." auto-expire after the specified period.
- **Discretion retained**: The reasoning layer can soften, decline, or supersede any directive.
  Directives guide behavior — they don't build a jail.
