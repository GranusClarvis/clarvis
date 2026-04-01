---
name: iteration
description: On-demand fast-track of Clarvis research evolution. Use when the user asks for /iteration1, /iteration2, /iteration3, or /iteration4 to run 1–4 back-to-back research cycles like the scheduled research-cycle cron job.
whenToUse: |
  When the user asks for /iteration or wants to fast-track research evolution cycles.
  Runs 1-4 back-to-back research cycles on demand.
---

# Iteration (Fast-Track Evolution)

When the user requests:
- `/iteration1` → run 1 evolution cycle
- `/iteration2` → run 2 cycles back-to-back
- `/iteration3` → run 3 cycles back-to-back
- `/iteration4` → run 4 cycles back-to-back

## How to execute

Create a **one-shot** Gateway cron job via the `cron` tool:
- `sessionTarget: "isolated"`
- `payload.kind: "agentTurn"`
- `schedule.kind: "at"` set to now (+5–10s)
- `timeoutSeconds: 700 * N`
- `delivery.mode: "announce"` to the current Telegram chat

## Payload prompt (required behavior)
In ONE job, run N sequential cycles by invoking the same bash entrypoint used by scheduled evolution:

- Run: `bash /home/agent/.openclaw/workspace/scripts/cron_autonomous.sh`
- Wait for completion
- Repeat until N cycles completed

This preserves the exact preflight → Claude Code → postflight pipeline, queue selection, episode encoding, and metrics.

## Examples

**User says:** `/iteration2`

The skill creates a Gateway cron job that runs 2 back-to-back evolution cycles:

```
[09:15:01] Iteration 1/2 — acquiring global lock...
[09:15:02] Preflight: selected task [ASSEMBLY_DECOMPOSE] (score=0.38)
[09:15:03] Context brief: 580 tokens (standard tier)
[09:27:44] Postflight: episode encoded, confidence=0.85
[09:27:45] Iteration 1/2 complete (762s)

[09:27:46] Iteration 2/2 — acquiring global lock...
[09:27:47] Preflight: selected task [SKILL_DOCS_EXAMPLES] (score=0.36)
[09:27:48] Context brief: 420 tokens (standard tier)
[09:35:12] Postflight: episode encoded, confidence=0.90
[09:35:13] Iteration 2/2 complete (447s)

All 2 iterations complete. Total: 1209s.
```

## Guardrails
- Respect the global Claude lock used by cron scripts (the script already enforces it).
- If a run is skipped due to lock conflict, stop the chain (don’t spin).
- Keep user-facing output minimal: just “Iteration k/N complete” plus any critical failures.
