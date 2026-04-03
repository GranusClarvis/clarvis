# Harness Runtime Architecture — Research Bundle 8

**Date**: 2026-04-03
**Source**: Claude Code harness (`data/external_src/claude-harness-src.zip`), cross-referenced against Clarvis codebase
**Purpose**: Extract concrete improvements for Clarvis runtime from harness patterns

---

## 1. HARNESS_TASK_BUDGET_STOPPING

**Verdict: PROTOTYPE NEXT**

### Harness mechanism
`checkTokenBudget()` tracks per-agent token usage across iterations. Two stopping conditions:
- **Hard budget**: stops at 90% of `tokenBudget` allocation
- **Diminishing returns**: stops when output drops below 500 tokens/iteration after 3+ loops

### What Clarvis has now
- **Wall-clock timeouts only**: tier-aware (`reasoning=1800s`, `complex=1500s`, `default=1200s`) in `cron_autonomous.sh:363-367`
- **Execution monitor** (`execution_monitor.py`): process-level stall detection via `/proc` heuristics (CPU ticks, child processes, process state). Flags at 60% of timeout, aborts at 92%. This is good for detecting stalls but not for detecting low-value work.
- **Retry tracking** in `heartbeat_postflight.py:1823-1841`: 3-strike auto-skip, but no adaptive timeout increase.
- **Time-budget hint** in `cron_autonomous.sh:388-392`: text warning to Claude about remaining time — useful but advisory only, not enforced.
- **No token accounting**: no visibility into how many tokens a task consumed until the postflight cost-logging step.

### Gap analysis
The real gap is not "we need token budgets" — it's that **we can't observe token consumption during execution**. Claude Code buffers all output. The `--output-format json` flag emits a final JSON blob with `usage` stats, but only after the process exits. We cannot get mid-execution token counts.

### Concrete recommendation
**Phase 1 (adopt now — small win)**: Add `--output-format json` to the Claude invocation in `run_claude_monitored()`. Parse the exit JSON for `input_tokens` and `output_tokens`. Write these to the progress file for postflight. This gives us per-task token accounting at zero cost.

**Phase 2 (prototype)**: Implement a **cost-per-task moving average** in postflight. If a task's token cost exceeds 2× the 20-task rolling average for its complexity tier, flag it as an outlier. This enables:
- Auto-escalating timeouts for genuinely complex tasks (instead of fixed retry)
- Auto-reducing timeouts for tasks that consistently finish in <300s (waste detection)
- Cost anomaly alerts (a task burning 50k tokens on a trivial string fix)

**Phase 3 (defer)**: True mid-execution budget enforcement requires Claude Code to expose streaming token counts, which it doesn't. The execution_monitor's `/proc` heuristics are the best proxy we have for "is this making progress." The diminishing-returns detection from the harness could be approximated by monitoring output file growth rate — if output size plateaus for >60s after the 50% mark, flag for reconsideration. This is a tweak to the existing monitor, not a new system.

### Why not copy the harness directly
The harness runs as an in-process wrapper around the Anthropic API — it has direct access to streaming token counts per message. Clarvis spawns Claude Code as a subprocess. We'd need to parse Claude's `--output-format json` output or intercept its API calls, neither of which gives us real-time data. The wall-clock + process-heuristic approach is the correct architecture for our execution model.

### Follow-up task
`[BUDGET_TRACKING_JSON_OUTPUT]` — Switch `run_claude_monitored()` to `--output-format json`, parse final token usage, write to progress file.

---

## 2. HARNESS_HOOK_SYSTEM

**Verdict: ADOPT NOW (extend existing)**

### Harness mechanism
14+ lifecycle events: PreToolUse, PostToolUse, PostToolUseFailure, SessionStart, SessionEnd, Stop, PreCompact, PostCompact, PermissionRequest, SubagentStart/Stop, etc. Hooks are shell scripts, HTTP endpoints, or callbacks. Exit code 2 = blocking error.

### What Clarvis has now
- **HookRegistry** (`clarvis/heartbeat/hooks.py`, 118 lines): Clean singleton with priority-ordered execution, two phases (PREFLIGHT, POSTFLIGHT). This is already well-designed.
- **Adapter pattern** (`clarvis/heartbeat/adapters.py`, 322 lines): Three subsystem adapters register hooks — procedural memory (30-39), consolidation (50-59), metrics (60-69).
- **Fallback inline** in `heartbeat_postflight.py:524-565`: If hook imports fail, postflight runs inline equivalents. Safety net, but means hook bugs can hide.

### Gap analysis
The existing hook system is solid for the heartbeat pipeline. The gaps are:
1. **No brain-operation hooks**: `brain.remember()`, `brain.search()`, `brain.capture()` have no pre/post hooks. Cost tracking, quality gates, and audit logging require wrapping these calls individually.
2. **No MID_EXECUTION phase**: `execution_monitor.py` implements mid-execution logic independently of the hook registry. These two systems should be aware of each other.
3. **No external hook targets**: All hooks are Python callables in-process. The harness supports shell scripts and HTTP endpoints, enabling external tooling to participate.

### Concrete recommendation
**Adopt now**: Add `HookPhase.BRAIN_PRE` and `HookPhase.BRAIN_POST` to the registry. Wire them into the `brain.py` spine's `remember()` and `search()` methods. This enables:
- Cost-per-operation tracking (count tokens embedded, count searches)
- Quality gates on `remember()` (reject below importance threshold, deduplicate before storage)
- Audit logging for compliance/debugging

Implementation is <50 lines: add two phase constants, add `registry.run()` calls at entry/exit of `brain.remember()` and `brain.search()`. Hooks that register for these phases get the operation context (query, results, timing).

**Defer**: Shell/HTTP hook targets. In-process Python callables are sufficient for Clarvis's single-host model. External hook targets add complexity for a scenario we don't have (multi-host deployment).

**Defer**: MID_EXECUTION phase. The execution monitor works well as-is. Integrating it into the hook registry would require the hook system to support async/background hooks, which is over-engineering for one consumer.

### Why not copy the harness directly
The harness needs 14+ events because it's a general-purpose developer tool with plugins, permissions, and user prompts. Clarvis is a focused cognitive agent — we need hooks at the boundaries where we make decisions (brain operations, heartbeat phases), not at every internal tool call. Adding events we don't have consumers for is pure waste.

---

## 3. HARNESS_GRADUATED_COMPACTION

**Verdict: PROTOTYPE NEXT**

### Harness mechanism
4-tier compaction: microcompact (strip at prompt-cache boundaries) → context collapse (archive old messages to summarization store) → history snip (remove oldest messages) → autocompact (full LLM summarization). Plus reactive compaction triggered by specific patterns.

### What Clarvis has now
- **Single-tier text compression** in `context_compressor.py`: TF-IDF extraction → MMR reranking → core-string dedup. Applied uniformly.
- **Tiered context briefs** (`context_compressor.py:496-552`): Three tiers (`minimal=200`, `standard=600`, `full=1000` tokens), but these control brief SIZE, not compression STRATEGY.
- **DyCP** (`clarvis/context/dycp.py`): Section-level pruning by task relevance — removes irrelevant sections entirely.
- **Section caching** with MD5 + 300s TTL: Reuses compressed sections when source unchanged.
- **Adaptive MMR**: Lambda values updated by postflight context-relevance scoring.
- **Context-relevance feedback loop**: Sections scored after task execution, noise ratio computed.

### Gap analysis
Clarvis's context pipeline is actually more sophisticated than the harness's in some ways (DyCP, adaptive MMR, feedback loops). The gap is:
1. **No progressive degradation**: When the context is too large, we compress everything at the same ratio. The harness's graduated approach (try cheap removal first, escalate to expensive summarization) preserves more information.
2. **Fixed section budgets**: `TIER_BUDGETS` allocates tokens per section statically. A task that needs more episodic context and less metrics can't reallocate.
3. **No "snip" tier**: We don't have a mechanism to simply drop the oldest/least-relevant memories from a section without re-compressing the whole thing.

### Concrete recommendation
**Prototype next**: Implement a 3-tier graduated pipeline within the existing `compress_text()` function:

```
Tier 0 — PRUNE: Drop sections scored <0.3 by DyCP (already done). Drop individual
         items within sections by staleness (>30 days + low relevance). Cost: zero LLM.
Tier 1 — SNIP: If still over budget after pruning, truncate the middle items of each
         section (keep first and last per "Lost in the Middle" principle). Cost: zero LLM.
Tier 2 — COMPRESS: If still over budget, apply the existing TF-IDF + MMR compression
         to the remaining sections. Cost: CPU only (no LLM, already implemented).
```

This is entirely within the current architecture — it's adding two cheaper tiers BEFORE the existing compression, not replacing it. The "microcompact" and "context collapse" tiers from the harness don't apply because we don't have a message history (our context is assembled fresh each heartbeat, not accumulated across turns).

**Defer**: Dynamic section budget reallocation. The current fixed budgets work well (context relevance scores are consistently good). Reallocation adds complexity for marginal gain.

**Defer**: Reactive compaction (pattern-triggered). We don't have the long-running session model that makes this useful — our tasks start fresh each heartbeat.

### Why not copy the harness directly
The harness compacts a growing conversation history. Clarvis assembles context from scratch for each task. "Microcompact" (strip cache boundaries) and "context collapse" (archive messages) are solutions to conversation accumulation, a problem we don't have. Our graduated pipeline should focus on progressive section-level pruning, which maps to our assembly model.

---

## 4. HARNESS_SANDBOX_MODEL

**Verdict: DEFER**

### Harness mechanism
`@anthropic-ai/sandbox-runtime` adapter: file read/write restrictions (allowed directories, denied patterns), network domain allow/deny lists, process exclusion lists. Integrated into tool execution pipeline.

### What Clarvis has now
- **3-tier lock system** (`lock_helper.sh`): job locks, global Claude lock, maintenance lock. PID recycling protection via `/proc` validation.
- **Nesting guard** (`cron_env.sh`): Unsets `CLAUDECODE`/`CLAUDE_CODE_ENTRYPOINT` to prevent recursive spawns.
- **Worktree isolation** (`spawn_claude.sh --isolated`): Git worktree per task. Opt-in.
- **Project agent isolation** (`project_agent.py`): Full filesystem + database isolation in `/opt/clarvis-agents/<name>/`.
- **`--dangerously-skip-permissions`**: All spawns bypass Claude Code's own permission system.

### Gap analysis
The honest assessment: **sandboxing Claude Code spawns is impractical without container/cgroup overhead that would negate our performance model.**

Why:
1. Claude Code runs as the same Unix user (`agent`). File restrictions would require either a chroot jail, a separate UID, or a FUSE overlay — all add significant latency to the spawn path.
2. Network isolation requires network namespaces (root access) or iptables rules (root access). Our cron spawns run as `agent`, not root.
3. Process limits via cgroups require root or systemd slice configuration. Our systemd user service doesn't have `Delegate=yes`.
4. The harness's sandbox runs in-process (same Node.js process, intercepting tool calls before they reach the OS). We spawn an external process — we can't intercept its syscalls without ptrace/seccomp, which are heavy.

### What actually matters
The real risk isn't "Claude writes outside workspace" — it's "Claude modifies critical runtime files while cron is running." The global lock already prevents concurrent spawns. The worktree isolation prevents workspace corruption during code-modifying tasks.

### Concrete recommendation
**No new sandbox system.** Instead, two small hardening wins:

1. **Make worktree isolation the default for code-modifying tasks** (currently opt-in). In `cron_autonomous.sh`, detect when the selected task contains code-modification keywords (`refactor`, `migrate`, `implement`, `fix`, `add`, `create`) and auto-enable `--isolated`. This is a one-line change to the existing spawner.

2. **Add a post-execution file-diff check**: After Claude Code exits, before committing in the worktree flow, validate that no files outside `workspace/` were modified. This is a safety net, not a sandbox — it detects violations after the fact rather than preventing them. But it's cheap and catches the failure mode that matters.

**Defer**: True OS-level sandboxing (containers, cgroups, seccomp). The cost-benefit doesn't work for our single-host, single-user model. Revisit if Clarvis ever runs untrusted tasks or multi-tenant workloads.

---

## 5. HARNESS_DREAM_DISTILLATION

**Verdict: ADOPT NOW**

### Harness mechanism
Dream task: 4-stage session-log distillation — reviews recent sessions, distills into structured topic files + MEMORY.md. Tracks `filesTouched` and `phase` (starting → updating). Rollback on kill.

### What Clarvis has now
- **Counterfactual dreaming** (`dream_engine.py`): 7 templates, SuRe-inspired surprise scoring, Pearl SCM counterfactual reasoning. Runs at 02:45. **Entirely rule-based (no LLM).**
- **Session transcript logger** (`session_transcript_logger.py`): Persists JSONL metadata + raw output to `data/session_transcripts/`. Hooked into postflight as §9.5.
- **Conversation learner** (`conversation_learner.py`): Regex-based pattern extraction from `memory/*.md` AND `data/session_transcripts/`. Stores to `autonomous-learning` collection.
- **Knowledge synthesis** (`knowledge_synthesis.py`): Cross-domain connection finder.
- **Memory consolidation** (`clarvis/memory/memory_consolidation.py`, 1937 lines): Comprehensive lifecycle — dedup, merge, decay, prune, archive.

### Gap analysis
The pieces are all there but the pipeline has a gap: **no structured distillation of session transcripts into actionable procedures.**

Current flow: `session_transcript_logger` → `conversation_learner` (regex patterns) → `autonomous-learning` collection.

Missing: `session_transcript_logger` → **procedure distillation** → `clarvis-procedures` collection.

The conversation learner extracts surface patterns (success/failure/questions). It doesn't extract **reusable procedures** — "when doing X, the steps that worked were A→B→C" or "tool Y requires flag Z in this codebase." The harness's dream task specifically distills sessions into structured topic files, which is closer to procedural knowledge.

### Concrete recommendation
**Adopt now**: Add a `distill_procedures()` function to `conversation_learner.py` that runs after the existing `extract_session_patterns()` pipeline. This function:

1. Groups successful session transcripts by task type (already available in JSONL metadata: `worker_type`, task keywords)
2. For groups with ≥3 successes, extracts common tool-use sequences from the raw output files
3. Formats as procedure entries: `{task_pattern, steps[], success_rate, last_seen}`
4. Dedup-checks against `clarvis-procedures` collection before storing
5. Importance = 0.7 (higher than dream insights at 0.5, lower than explicit procedures at 0.9)

This is entirely rule-based (no LLM cost). The raw session outputs already contain tool-use patterns (`Edit tool`, `Write tool`, `Bash tool` markers). Extracting the sequence of tools used in successful tasks gives us the procedure skeleton.

**Wire into cron**: The conversation learner already runs during `cron_reflection.sh` (21:00). The distillation step adds to that pipeline — no new cron entry needed.

**Defer**: LLM-powered distillation (the harness's dream task uses the model itself to summarize). Our rule-based approach loses nuance but costs zero and runs reliably. If the rule-based procedures prove too shallow, we can upgrade to an LLM-powered step later.

### Follow-up task
`[SESSION_PROCEDURE_DISTILLATION]` — Add `distill_procedures()` to `conversation_learner.py`.

---

## 6. HARNESS_BRIDGE_TRANSPORT

**Verdict: DEFER (with design notes)**

### Harness mechanism
`HybridTransport.ts`: WebSocket for reads (server → client streaming), HTTP POST for writes (client → server commands). `bridgeApi.ts` + `bridgeMain.ts` implement a remote control protocol: observe session state, send messages, stop tasks.

### What Clarvis has now
- **Digest bridge** (`digest_writer.py`): Unidirectional (subconscious → conscious) via `memory/cron/digest.md`. File-based with `fcntl` locking.
- **Queue bridge** (`queue_writer.py`): Bidirectional via `memory/evolution/QUEUE.md`. Both layers read/write.
- **Spawn command** (`/spawn` via Telegram → `spawn_claude.sh`): One-shot task delegation.
- **Brain as shared database**: Both layers read/write ClarvisDB.
- **OpenClaw M2.5 cron jobs** (`cron/jobs.json`): 6 scheduled sessions that read the digest at fixed times.
- **No event bus**: `emit_dashboard_event()` in `cron_env.sh` is a no-op stub.

### Gap analysis
The core limitation is **polling latency**: M2.5 reads the digest only at scheduled cron times (09:00, 14:00, 19:00, 22:00). Urgent subconscious results wait hours. The secondary limitation is **no live observation**: you can't watch a Claude Code task as it runs.

### Why defer
1. **The polling gap is not causing real problems.** Looking at the cron schedule, the subconscious runs 12+ tasks/day. The 4× daily digest reads capture the important results. Urgent items go to Telegram directly (spawn_claude.sh already sends results to Telegram). The 4-hour latency for non-urgent results is acceptable.

2. **Live observation requires a fundamentally different spawn model.** Currently, Claude Code writes buffered output to a file. To stream this to a WebSocket, we'd need either: (a) `tail -f` piped to a WebSocket server, or (b) Claude Code's `--output-format stream-json` piped through a proxy. Both require a persistent server process, which we don't have during cron execution.

3. **The simpler win is already partially implemented.** Telegram delivery of task results gives Patrick near-real-time visibility. The gap is that cron-initiated tasks don't always send Telegram notifications — only `spawn_claude.sh` does. Adding Telegram delivery to `cron_autonomous.sh` completion events would close the practical visibility gap without a WebSocket server.

### Design notes for future
If we do want a remote-control interface later, the architecture should be:

```
┌──────────────┐     WebSocket      ┌──────────────────┐
│  Telegram    │ ◄──────────────── │  clarvis-bridge   │
│  Bot/Web UI  │ ────────────────► │  (tiny HTTP+WS    │
└──────────────┘     HTTP POST      │   server, systemd │
                                    │   user service)   │
                                    └────────┬─────────┘
                                             │ reads
                                    ┌────────┴─────────┐
                                    │  Shared state:    │
                                    │  - digest.md      │
                                    │  - QUEUE.md       │
                                    │  - session_transcripts/│
                                    │  - global lock    │
                                    └──────────────────┘
```

The bridge server would be a ~200-line Python `asyncio` process:
- Watches `data/session_transcripts/` for new JSONL entries → push to WS clients
- Watches `memory/cron/digest.md` mtime → push digest updates
- Accepts HTTP POST: `add-task` (writes to QUEUE.md via queue_writer), `kill-task` (sends SIGTERM to PID from global lock)
- Systemd user service with socket activation (only starts when a client connects)

This is a clean, small service. But it's not needed today.

### Follow-up task
`[CRON_TELEGRAM_NOTIFY]` — Add Telegram notification to `cron_autonomous.sh` on task completion (success/failure/timeout), matching `spawn_claude.sh` pattern.

---

## Cross-Cutting Findings

### What Clarvis does BETTER than the harness
1. **Execution monitoring**: The `/proc`-based stall detection in `execution_monitor.py` is more sophisticated than the harness's token-budget approach for our subprocess model.
2. **Context feedback loops**: Adaptive MMR lambdas, context-relevance scoring, and DyCP are feedback-driven. The harness's compaction is threshold-based with no learning.
3. **Episodic memory**: The harness persists transcripts but doesn't do episodic analysis. Clarvis's SuRe surprise scoring and counterfactual dreaming are unique.
4. **Lock isolation**: The 3-tier lock system with PID validation and process-tree inspection is robust for a single-host model.

### What the harness does better
1. **Token visibility**: In-process access to API responses gives real-time token counts. We're blind during execution.
2. **Tool-level hooks**: Per-tool permission gates and lifecycle hooks. We only have pipeline-level hooks.
3. **Session resume**: JSONL transcripts with UUID chains enable mid-session recovery. Our sessions are fire-and-forget.
4. **Structured memory taxonomy**: user/feedback/project/reference with LLM-powered selection. Our 10 collections lack clear intake rules.

### Prioritized action items
| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| P0 | Brain operation hooks (HOOK_SYSTEM) | ~50 LOC | Enables cost tracking, quality gates |
| P0 | Session procedure distillation (DREAM_DISTILLATION) | ~100 LOC | Extracts reusable procedures from sessions |
| P1 | JSON output parsing for token accounting (BUDGET_STOPPING) | ~30 LOC | Per-task cost visibility |
| P1 | Graduated section pruning (COMPACTION) | ~80 LOC | Better context preservation |
| P2 | Cron Telegram notifications (BRIDGE) | ~40 LOC | Real-time visibility without new infra |
| P3 | Default worktree for code tasks (SANDBOX) | ~5 LOC | Safety net for code modifications |
