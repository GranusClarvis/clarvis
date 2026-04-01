# HARNESS_SESSION_PERSISTENCE — JSONL Transcript Persistence & Resume Flow

**Date**: 2026-04-01
**Source**: Claude Code harness (`sessionStorage.ts`, `conversationRecovery.ts`), web research, Clarvis codebase audit
**Decision**: APPLY

---

## 1. How Claude Code Persists Sessions

### JSONL Append-Only Format
- Location: `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`
- One JSON object per line — append-only, no rewrite, no corruption risk
- Each entry typed: `session`, `model_change`, `thinking_level_change`, `message`, `tool_use`, `tool_result`
- UUID parent chain: every entry has `id` + `parentId` forming a linked list
- Global index: `~/.claude/history.jsonl` (prompt text, timestamp, project, sessionId)
- Session index: `sessions-index.json` (auto-summaries, message counts, git branches)

### Message Schema (simplified)
```json
{"type":"message","id":"<uuid>","parentId":"<uuid>","timestamp":"<iso8601>","message":{"role":"user|assistant","content":[{"type":"text","text":"..."}]}}
{"type":"tool_use","id":"<uuid>","parentId":"<uuid>","timestamp":"<iso8601>","tool":"Read","input":{...}}
{"type":"tool_result","id":"<uuid>","parentId":"<uuid>","timestamp":"<iso8601>","result":"..."}
```

### Why JSONL Works Well
- **Crash-safe**: partial writes corrupt only the last line, not the file
- **Streamable**: tail -f for live monitoring; no parsing overhead for append
- **Auditable**: complete record of every tool call, result, and reasoning step
- **Resumable**: load from any point by reading forward from line N

## 2. Conversation Recovery (`conversationRecovery.ts`)

### Resume Flow
1. Deserialize JSONL messages sequentially
2. **Filter unresolved tool uses**: if a `tool_use` has no matching `tool_result`, remove it
3. **Filter orphaned thinking blocks**: incomplete assistant turns trimmed
4. **Detect mid-turn interruptions**: incomplete assistant response → append synthetic continuation prompt
5. **UUID parent chain validation**: ensures no message orphaning during reconstruction

### Known Failure Modes (from GitHub issues)
- **Interrupt during tool execution** (Ctrl+C mid-tool): can create API sync errors (tool_use without tool_result) that corrupt the session permanently
- **Context limit exhaustion**: `--resume` fails to restore state after "usage limit reached"
- **No partial recovery**: either full resume succeeds or the session is lost

### Resume CLI
- `claude --continue` — resume most recent session
- `claude --resume <session-id>` — resume specific session
- Permissions are NOT restored (re-granted per new session)

## 3. Compaction & Cleanup Strategy

Claude Code uses graduated compaction when approaching context limits:
1. **Microcompact**: trim tool results, collapse long outputs
2. **Context collapse**: summarize old turns into a brief
3. **History snip**: remove oldest turns entirely
4. **Full autocompact**: LLM-generated session summary replaces history

Sessions managed by age:
- Recent: full transcript retained
- Older: may be compacted/trimmed
- Very old: eventually removed

## 4. Clarvis Gap Analysis

### What Clarvis Has Today
| Layer | What's Stored | Format | Retention |
|-------|--------------|--------|-----------|
| Episodes | task, outcome, duration, error | JSON (500 cap) | FIFO rotation |
| Daily logs | 200-char task summaries | Markdown | Permanent |
| Digest | 1000-char entries | Markdown | Overwritten daily |
| Cron logs | Last 2000 chars of output | Text | Log rotation |
| Reasoning chains | Step metadata, no content | JSON | Permanent |

### What's Missing
1. **No full transcript persistence** — Claude Code output written to `/tmp`, read into RAM, then deleted
2. **No input-output pairing** — prompt sent to Claude Code not stored alongside its response
3. **No session grouping** — tasks within a heartbeat/cron cycle aren't linked
4. **No UUID chain** — no way to trace message lineage
5. **No resume capability** — interrupted tasks are simply lost
6. **conversation_learner.py starved** — only gets 200-char snippets from daily logs, not full transcripts

### Where the Transcript Dies
```
cron_autonomous.sh → spawn Claude Code → output to /tmp/file
  → heartbeat_postflight.py reads full output into RAM
  → extracts snippets (200-2000 chars) → writes to downstream stores
  → /tmp/file DELETED → full transcript lost forever
```

## 5. Proposed Solution: Session Transcript Logger

### Design: JSONL Transcript Append in Postflight

**New file**: `data/session_transcripts/YYYY-MM-DD.jsonl` (one file per day, append-only)

**Schema per entry**:
```json
{
  "ts": "2026-04-01T07:30:00Z",
  "session_id": "heartbeat_20260401_073000",
  "task_id": "chain_20260401_073000",
  "task_source": "cron_autonomous",
  "prompt_hash": "sha256:abc123...",
  "prompt_brief": "first 500 chars of prompt",
  "exit_code": 0,
  "duration_s": 847,
  "output_tokens_est": 12000,
  "output_hash": "sha256:def456...",
  "full_output_path": "data/session_transcripts/raw/heartbeat_20260401_073000.txt",
  "outcome": "success",
  "episode_id": "ep_20260401_073847",
  "chain_id": "chain_20260401_073000"
}
```

**Raw output**: stored in `data/session_transcripts/raw/<session_id>.txt` (full Claude Code output, gzipped after 7 days)

### Integration Points
1. **heartbeat_postflight.py**: Before deleting temp file, append JSONL entry + copy raw output
2. **cron_autonomous.sh**: Pass temp file path to postflight instead of deleting immediately
3. **conversation_learner.py**: Read from `session_transcripts/` instead of memory/*.md — full content available
4. **Cleanup**: `cron_cleanup.sh` compresses raw files >7 days, deletes >90 days

### Bloat Mitigation (relevant to Bloat Score=0.400)
- Daily JSONL index: ~50KB/day (lightweight metadata)
- Raw transcripts: ~2-5MB/day (12 heartbeats × 200-400KB each)
- Compression after 7 days: ~10x reduction
- 90-day retention: ~15GB max before rotation
- **Net bloat impact**: Moderate but manageable with lifecycle policy. The JSONL index itself is tiny; raw files need the same rotation already applied to logs.

## 6. Conversation Recovery for Clarvis

### What We Can Borrow
- **Append-only JSONL**: proven crash-safe pattern, trivial to implement
- **UUID chain**: link prompt→execution→postflight as a single trace
- **Orphan filtering**: detect incomplete runs (no postflight entry) for retry/alerting

### What We Don't Need
- **Full resume flow**: our tasks are one-shot spawns, not interactive sessions
- **Mid-turn interrupt detection**: Claude Code processes run to completion or timeout
- **Permission restoration**: we use `--dangerously-skip-permissions`

### Unique Clarvis Advantage
We can do something the harness can't: **cross-session learning**. By persisting full transcripts, `conversation_learner.py` can:
- Compare prompts that succeeded vs failed for similar tasks
- Extract tool-use patterns across hundreds of sessions
- Feed Hebbian learning with richer outcome data
- Build a "prompt cookbook" from high-quality sessions

## 7. Implementation Plan

| Step | Effort | Description |
|------|--------|-------------|
| 1 | S | Create `data/session_transcripts/` dir + JSONL schema |
| 2 | S | Modify postflight to append JSONL + save raw output |
| 3 | S | Modify cron_autonomous.sh to not delete temp file prematurely |
| 4 | M | Upgrade conversation_learner.py to ingest full transcripts |
| 5 | S | Add rotation to cron_cleanup.sh (compress >7d, delete >90d) |
| 6 | M | Add orphan detection (JSONL entries without postflight close) |

**Total effort**: M (medium) — core logging is S, learning integration is M
