# Codex Comparative Research — Bundle 9

**Date**: 2026-04-03
**Task**: CODEX_RELEASE_AND_DISTRIBUTION, CODEX_LOCAL_AGENT_EXPERIENCE, CODEX_IDE_INTEGRATION_RESEARCH, CODEX_TOOLING_AND_SANDBOX_REVIEW, CODEX_PORTABILITY_PATTERN_EXTRACTION, CODEX_CROSS_VENDOR_AGENT_BENCH
**Sources**: `github.com/openai/codex` (v0.118.0, 2026-03-31), prior Clarvis research (`codex_vs_harness_comparison_2026-03-31.md`, `harness_runtime_architecture_2026-04-03.md`), Clarvis workspace state as of 2026-04-03.

---

## 1. CODEX_RELEASE_AND_DISTRIBUTION — Release & Distribution Model

### What Codex Does

Codex distributes via **three channels**:

1. **npm** (`npm i -g @openai/codex`): Node.js shim (~zero dependencies) auto-downloads platform-specific Rust binary from optional npm packages (`@openai/codex-linux-x64`, `@openai/codex-darwin-arm64`, etc.). The shim is ~50 lines of JS that resolves the correct binary and `execFileSync`s it.
2. **Homebrew** (`brew install --cask codex`): macOS-native experience.
3. **Direct binary**: musl-static Linux, macOS universal, Windows MSVC from GitHub Releases.

Key design choices:
- The npm package has **zero runtime JS dependencies** — it's purely a binary launcher.
- Platform binaries are published as `optionalDependencies` so npm only downloads the matching platform.
- Bazel + Cargo dual build ensures reproducible cross-platform compilation.
- Nix flake for developer reproducibility, but not for end-user distribution.

### Clarvis Current State

- **Git clone** into `/home/agent/.openclaw/workspace/` → manual `cron_env.sh` setup → systemd services + system crontab.
- Python packages (`clarvis`, `clarvis-db`, `clarvis-cost`, `clarvis-reasoning`) installed via `pip install -e .` or wheel.
- Docker quickstart exists (contributor-oriented, not production).
- No npm/Homebrew/binary distribution — Clarvis is a **deployed system**, not a distributed tool.

### Comparative Assessment

| Aspect | Codex | Clarvis | Gap? |
|--------|-------|---------|------|
| Install command | `npm i -g @openai/codex` | git clone + manual setup | Yes — but different use case |
| Platform binaries | Cross-compiled Rust | Pure Python, no compilation | N/A |
| Multi-channel | npm + brew + binary | git + pip + Docker | Moderate |
| Zero-dep launcher | Yes | N/A | N/A |
| Update mechanism | `npm update -g` | `safe_update.sh` (7-phase) | Clarvis wins on safety |

### Verdict: **Defer**

Codex's multi-channel distribution makes sense for a developer tool targeting millions. Clarvis is a **single-operator cognitive agent** — it has one deployment, not thousands. The ROI of packaging Clarvis as an npm/brew installable is near zero right now.

**What's actually useful**: Clarvis's `safe_update.sh` is already superior to Codex's update story (which is just `npm update`). The Docker quickstart covers contributor onboarding. PyPI publication of sub-packages (`clarvis-db` especially) is already queued and makes sense for library extraction, but that's a different goal than distribution.

**No action needed.** Existing `OSR_PYPI_CHANGELOGS` and `OSR_DOCKER_CI` queue items cover the useful parts.

---

## 2. CODEX_LOCAL_AGENT_EXPERIENCE — Local Agent Positioning

### What Codex Does

Codex positions heavily on "runs locally on your computer":
- All file reads, tool execution, and sandbox enforcement happen locally.
- Only API calls go to the cloud (model inference).
- **Ghost snapshots**: filesystem state captured before changes, enabling undo.
- **Rollout recording**: every session persisted to local SQLite for memory extraction and debugging.
- **Secret redaction**: dedicated Rust crate scans for KEY/SECRET/TOKEN patterns before anything leaves the machine.
- `codex exec` for headless/programmatic mode (CI/CD integration).

The trust model is: **your code never leaves your machine** (only prompts/responses traverse the network). This is a strong privacy/compliance pitch.

### Clarvis Current State

- **Also fully local** — all execution happens on the agent's host.
- Brain (ChromaDB + SQLite graph) is local, no cloud sync.
- Session transcripts persist locally (`data/session_transcripts/`).
- No ghost snapshots — but git worktree isolation (`spawn_claude.sh --isolated`) covers the undo case for code changes.
- No secret redaction layer — `.env` is gitignored, but no automatic scanning of brain content or prompts for leaked secrets.
- OpenRouter API calls send prompts to cloud models (inherent, same as Codex).

### Comparative Assessment

| Aspect | Codex | Clarvis | Gap? |
|--------|-------|---------|------|
| Local execution | Yes | Yes | No |
| Local storage | SQLite state DB | ChromaDB + SQLite graph + JSONL | No |
| Secret redaction | Dedicated crate, env auto-filtering | gitignore only | **Yes** |
| Undo / rollback | Ghost snapshots (filesystem-level) | Git worktree isolation | Different approach, both valid |
| Headless/CI mode | `codex exec` | `spawn_claude.sh` + `run_claude_monitored()` | Functionally equivalent |
| Session recording | Rollout SQLite | JSONL transcripts + raw output | Equivalent |

### Verdict: **Adopt one small win, defer the rest**

Clarvis is already local-first by architecture. The meaningful gap is **secret redaction**: Clarvis stores memories, procedures, and transcripts without scanning for accidentally captured secrets (API keys, tokens). This is a real risk — a `brain search` could surface a key that was in a log file.

**Adopt now**: Add a lightweight secret scanner to `brain.remember()` — regex check for common patterns (AWS keys, API tokens, Bearer headers, private keys) before storing. Can be wired through the existing `BRAIN_PRE_STORE` hook (added in Bundle 8).

**Defer**: Ghost snapshots (git worktree covers the same ground), headless mode packaging (spawn_claude.sh works).

**Follow-up task queued**: `BRAIN_SECRET_REDACTION` — see §7.

---

## 3. CODEX_IDE_INTEGRATION_RESEARCH — IDE Integration

### What Codex Does

- **VS Code extension** (`openai.chatgpt`): communicates via `codex app-server`, a JSON-RPC 2.0 server over stdio.
- **Protocol**: thread lifecycle, approvals, skills, apps (connectors), auth, config read/write. Also supports WebSocket transport with health probes.
- **Desktop app**: `codex app` launches standalone experience.
- `codex-mcp` crate: full MCP client for connecting to external tool servers.
- Codex can also **act as an MCP server** (`mcp-server` crate), meaning other tools can invoke it.

The pattern: Codex is a **protocol-first runtime** with multiple UI frontends (CLI, TUI, VS Code, desktop, MCP). The agent logic is decoupled from presentation.

### Clarvis Current State

- **No IDE integration** — Clarvis operates via Telegram chat (conscious layer) and cron (subconscious layer).
- OpenClaw gateway (port 18789) provides the chat API surface.
- Claude Code has its own VS Code extension, but Clarvis doesn't hook into it.
- Project agents (`project_agent.py`) work on git repos but have no IDE awareness.
- No MCP server — Clarvis can't be invoked by external tools.

### Comparative Assessment

| Aspect | Codex | Clarvis | Gap? |
|--------|-------|---------|------|
| IDE extension | VS Code + Cursor/Windsurf | None | Yes — but different UX model |
| Protocol server | JSON-RPC 2.0 (stdio + WebSocket) | OpenClaw gateway (HTTP, port 18789) | Different protocol |
| MCP client | Full MCP client crate | None | Yes |
| MCP server | Can be invoked as MCP server | None | Yes |
| Desktop app | `codex app` | Telegram bot | Different approach |

### Verdict: **Defer IDE, prototype MCP server**

IDE integration is wrong for Clarvis. Codex is a **developer tool in the editor**. Clarvis is an **autonomous cognitive agent** that runs independently. Building a VS Code extension would be cargo-culting — the operator (Patrick) interacts via Telegram, not an editor.

**What IS useful**: An MCP server interface for Clarvis would let it be invoked by other agents or tools. This aligns with the existing agent orchestrator architecture. A minimal MCP server that exposes `brain search`, `brain remember`, `heartbeat run`, and `spawn task` would make Clarvis composable.

**Prototype next**: Design a `clarvis-mcp-server` (Python, ~200 LOC) exposing core brain operations over MCP. Low effort, high composability upside. But not urgent — queue as P2.

**Follow-up task queued**: `CLARVIS_MCP_SERVER_DESIGN` — see §7.

---

## 4. CODEX_TOOLING_AND_SANDBOX_REVIEW — Tooling & Sandbox

### What Codex Does

**Three-layer sandbox**:

1. **OS-level filesystem isolation**: bubblewrap (Linux), Seatbelt (macOS), restricted tokens (Windows). Read-only by default, writable roots layered explicitly. `.git` and `.codex` always read-only.
2. **Network sandbox**: `--unshare-net` + managed TCP→UDS→TCP proxy. Seccomp blocks new socket creation after bridge is live.
3. **Execution policy**: Starlark-based rule engine (`prefix_rule()`, `host_executable()`) with `allow/prompt/forbidden` decisions. Unit-test-like validation at load time.

**Guardian subagent**: GPT-5.4-powered auto-approver that assesses risk (0-100 score, fail-closed at ≥80). 90-second timeout, 10K token transcript limit.

**Secret filtering**: Dedicated Rust crate, env auto-excludes patterns matching KEY/SECRET/TOKEN.

### Clarvis Current State (post-Bundle 8)

- **No OS-level sandbox** — same UID, no cgroups/namespaces/seccomp. Verdict from HARNESS_SANDBOX_MODEL: impractical without root.
- **3-tier locking**: global Claude lock + maintenance lock + per-job PID locks with stale detection.
- **Worktree isolation**: `spawn_claude.sh --isolated` creates git worktree for code-modifying tasks.
- **No execution policy** — `--dangerously-skip-permissions` is all-or-nothing.
- **No network restrictions** — full outbound access.
- **No guardian/auto-approver** — tasks run without approval gates.

### Comparative Assessment

| Aspect | Codex | Clarvis | Practical Gap? |
|--------|-------|---------|----------------|
| Filesystem sandbox | OS-native (bwrap/Seatbelt) | Worktree isolation | **Moderate** — worktree covers code, not data |
| Network sandbox | Seccomp + managed proxy | None | **Low** — single operator, trusted environment |
| Execution policy | Starlark rules engine | None | **Moderate** — but Clarvis spawns specific tasks, not arbitrary commands |
| Auto-approver | Guardian subagent (GPT-5.4) | None | **Low** — autonomous agent, no interactive approval flow |
| Secret filtering | Dedicated crate | None | **Real gap** — see §2 |
| Protected paths | .git/.codex always RO | .git protected via worktree | Adequate |

### Verdict: **Adopt secret filtering, defer sandboxing**

The HARNESS_SANDBOX_MODEL verdict (defer) still holds. Clarvis operates in a single-operator trusted environment. The meaningful Codex pattern to extract is **not the sandbox itself** but the **principle of defense in depth at storage boundaries**.

Specifically:
1. **Secret redaction before brain storage** — prevents accidental persistence of credentials (adopt now via hook).
2. **Protected paths in worktree mode** — already covered by git worktree design.
3. **Execution policy** — overkill for Clarvis's task-spawning model (tasks are written by trusted orchestrators, not user-supplied commands).
4. **Guardian subagent** — interesting concept but wrong fit (Clarvis doesn't have an interactive approval flow; its "approval" is the queue curation process).

**No new implementation needed** beyond the secret redaction hook from §2.

---

## 5. CODEX_PORTABILITY_PATTERN_EXTRACTION — Portable Ideas

### Patterns Worth Extracting

After detailed comparison, these are the Codex patterns that materially improve Clarvis:

#### 5.1 Two-Phase Memory Pipeline — **Prototype Next**

Codex runs asynchronous memory extraction:
- **Phase 1**: Per-rollout extraction — claims recent sessions, filters for memory-relevant content, extracts in parallel with bounded concurrency. Automatic secret redaction.
- **Phase 2**: Global consolidation — single-writer serialization, top-N ranking by usage_count + last_usage, diff vs previous selection, syncs to disk.

**Clarvis comparison**: `conversation_learner.py` does one-pass extraction from transcripts. No usage-count ranking, no incremental consolidation, no single-writer serialization.

**What to adopt**: The two-phase pattern is clean. Phase 1 (parallel extraction per session) already works in Clarvis via `extract_session_patterns()`. Phase 2 (consolidation with usage ranking + dedup) would improve the `distill_procedures()` pipeline added in Bundle 8.

**Concrete next step**: Add `usage_count` and `last_used` metadata to procedures stored via `distill_procedures()`. On consolidation runs, rank by usage and deduplicate near-duplicates (cosine > 0.92). This is ~50 lines in `conversation_learner.py`.

#### 5.2 Rollout Slugs for Session Naming — **Adopt Now (trivial)**

Codex generates short descriptive slugs for sessions (e.g., `fix-auth-middleware`). Clarvis session transcripts are named by timestamp only (`2026-04-03.jsonl`). Adding a slug derived from the task name would make transcript browsing much easier.

**Concrete**: In `session_transcript_logger.py`, derive a slug from the task title (lowercase, strip non-alphanum, truncate to 50 chars) and include it in the JSONL metadata. Zero-cost improvement.

#### 5.3 Ghost Snapshots → Pre-Task Diff Check — **Already Covered**

Codex captures filesystem state before changes. Clarvis uses git worktree isolation, which is stronger (full git history, clean branch). The Bundle 8 `WORKTREE_AUTO_ENABLE` queue item covers auto-enabling this for code-modifying tasks. No additional work needed.

#### 5.4 Notify Command — **Adopt Now (trivial)**

Codex has a configurable `notify` command that fires when a task completes. Clarvis's `spawn_claude.sh` already sends Telegram notifications, but `cron_autonomous.sh` (the main executor) does not. The `CRON_TELEGRAM_NOTIFY` queue item from Bundle 8 covers this exactly.

#### 5.5 Commit Attribution — **Already Done**

Codex has `commit_attribution` config for co-author trailers. Clarvis already uses `Co-Authored-By: Claude Opus 4.6` in commits. No gap.

#### 5.6 Starlark-Based Policy — **Defer**

Interesting engineering but wrong fit. Clarvis doesn't need a programmable policy engine for its trusted, orchestrated execution model. The complexity cost outweighs the benefit.

### Patterns to Explicitly Skip

- **Ratatui TUI**: Wrong UX model for Clarvis (Telegram is the primary interface).
- **Guardian subagent**: No interactive approval flow to guard.
- **Platform-specific sandbox crates**: No root, single OS, single operator.
- **OAuth/device-code auth**: Clarvis uses API keys via OpenRouter — simpler and sufficient.
- **Profiles system**: Single operator, single deployment.
- **Plugin system**: Clarvis already has skills + hook system.

---

## 6. CODEX_CROSS_VENDOR_AGENT_BENCH — Cross-Vendor Best Practices

### Converged Best Practices: Codex × Claude Harness × OpenClaw × Clarvis

| Dimension | Codex (v0.118) | Claude Harness | OpenClaw | Clarvis | Best Practice |
|-----------|---------------|----------------|----------|---------|---------------|
| **Permissions** | Starlark rules + Guardian subagent | 6 modes, LLM classifier, 8 priority sources | ACP thread-bound | `--dangerously-skip-permissions` | **Graduated permissions with fail-closed default.** Clarvis should add at minimum: protected-path enforcement in worktree mode + secret redaction at storage boundary. |
| **Memory** | Two-phase pipeline (extract→consolidate), SQLite state, watermark-incremental | File-based `MEMORY.md` + project memories | Cron-based digest | ChromaDB 10 collections + SQLite graph + conversation learner | **Usage-ranked consolidation with secret redaction.** Clarvis has the richest memory system; add usage tracking + redaction. |
| **Compaction** | Token-threshold auto-compaction | DyCP + microcompact + collapse | N/A | TF-IDF + MMR, graduated pipeline designed | **Multi-tier compaction with zero-LLM first pass.** Clarvis's graduated design (Bundle 8) aligns with industry direction. Implement Tier 0 PRUNE. |
| **Sandbox** | OS-native (bwrap/Seatbelt), network proxy | Process-level sandbox runtime | None | Lockfiles + worktree | **OS-level where possible, defense-in-depth otherwise.** Clarvis correctly deferred true sandboxing; worktree + locks is pragmatic. |
| **Orchestration** | Hierarchical threads (max_depth, max_concurrency) | Single-process | M2.5 thread sessions | Cron-driven + project agents + global lock | **Bounded concurrency with depth limits.** Clarvis's global lock is coarse; consider per-task-type concurrency slots. |
| **Session Persistence** | Rollout SQLite + slug naming | Auto-compressed conversation | Thread transcripts | JSONL transcripts + raw output | **Structured session records with searchable metadata.** Clarvis's transcript logger is good; add slugs and usage tracking. |
| **Updates** | `npm update -g` | Auto-update with config toggle | `openclaw update` | 7-phase `safe_update.sh` | **Clarvis wins.** Safe update with backup + rollback + health checks is the gold standard. |
| **Hooks** | Lifecycle hooks crate | File-based hook system (pre/post commands) | Cron jobs as hooks | 4 brain phases + reasoning chain hooks | **Event-driven hooks at operation boundaries.** Clarvis's hook system (Bundle 8) is well-designed. Expand to spawn lifecycle. |
| **Cost Control** | Token tracking per-session | In-process token counting | API cost via OpenRouter | `clarvis-cost` package + budget alerts | **Per-task cost tracking with anomaly detection.** Implement BUDGET_TRACKING_JSON_OUTPUT from Bundle 8. |

### Architecture Direction Memo

**Clarvis's strategic position**: Clarvis is neither a developer tool (Codex) nor a general-purpose CLI agent (Claude Code). It is an **autonomous cognitive agent** with a unique dual-layer architecture. The right moves are:

1. **Strengthen storage boundaries** — secret redaction before brain storage (from Codex), quality gates on remember() (already hooked).
2. **Add usage-ranked memory consolidation** — two-phase pattern from Codex applied to conversation_learner.py.
3. **Implement graduated compaction** — Tier 0 PRUNE already designed in Bundle 8, just needs implementation.
4. **Complete per-task cost accounting** — `--output-format json` switch from Bundle 8 follow-up.
5. **Expose brain via MCP** — makes Clarvis composable without building IDE integrations.

**What NOT to do**: Don't build a TUI, don't build an IDE extension, don't build OS-level sandboxing, don't build a Starlark policy engine. These are the right answers for different products.

---

## 7. New Queue Items

### From This Research

- `[BRAIN_SECRET_REDACTION]` **(P1)**: Add regex-based secret scanner as `BRAIN_PRE_STORE` hook. Patterns: AWS keys (`AKIA[0-9A-Z]{16}`), generic API keys (`sk-[a-zA-Z0-9]{20,}`), Bearer tokens, private key blocks. Reject or redact before storage. ~40 lines, wire through existing hook system.

- `[SESSION_SLUG_NAMING]` **(P2)**: In `session_transcript_logger.py`, derive a slug from task title and include in JSONL metadata. Trivial, improves transcript browsability.

- `[MEMORY_USAGE_TRACKING]` **(P2)**: Add `usage_count` and `last_used` metadata to procedures in `distill_procedures()`. On consolidation, rank by usage, deduplicate near-duplicates (cosine > 0.92). ~50 lines in `conversation_learner.py`.

- `[CLARVIS_MCP_SERVER_DESIGN]` **(P2)**: Design doc for minimal MCP server exposing `brain search`, `brain remember`, `heartbeat run`, `spawn task`. Python, ~200 LOC. Makes Clarvis composable.

### Already Queued (Bundle 8, confirmed still relevant)
- `BUDGET_TRACKING_JSON_OUTPUT` — per-task cost accounting
- `GRADUATED_COMPACTION_PROTOTYPE` — Tier 0 PRUNE implementation
- `CRON_TELEGRAM_NOTIFY` — notification on autonomous task completion
- `WORKTREE_AUTO_ENABLE` — auto-detect code-modifying tasks

---

## 8. Summary Table

| Queue Item | Verdict | Rationale |
|-----------|---------|-----------|
| CODEX_RELEASE_AND_DISTRIBUTION | **Defer** | Wrong product shape — Clarvis is deployed, not distributed |
| CODEX_LOCAL_AGENT_EXPERIENCE | **Adopt one win** | Already local-first; secret redaction is the real gap |
| CODEX_IDE_INTEGRATION_RESEARCH | **Defer IDE, P2 MCP** | IDE is wrong UX; MCP server adds composability |
| CODEX_TOOLING_AND_SANDBOX_REVIEW | **Defer sandbox, adopt redaction** | OS sandbox impractical; defense at storage boundary is right |
| CODEX_PORTABILITY_PATTERN_EXTRACTION | **2 trivial wins + 1 prototype** | Slugs, notify (already queued), usage-ranked consolidation |
| CODEX_CROSS_VENDOR_AGENT_BENCH | **Direction memo produced** | Clarvis's unique position identified; 5 concrete next moves |
