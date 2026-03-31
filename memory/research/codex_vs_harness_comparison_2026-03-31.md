# Codex CLI vs Claude Code Harness vs Clarvis — Cross-Comparison Matrix

**Date**: 2026-03-31
**Sources**: OpenAI Codex repo (`github.com/openai/codex`), Claude harness (`data/external_src/claude-harness-src.zip`), Clarvis workspace
**Task**: [CODEX_VS_HARNESS_COMPARISON]

---

## Structured Comparison Matrix

| Dimension | OpenAI Codex CLI | Claude Code Harness | Clarvis |
|-----------|-----------------|-------------------|---------|
| **Language/Runtime** | Rust monorepo (60+ crates), Bazel+Cargo. npm shim ships prebuilt binaries | TypeScript/React+Ink, Bun runtime. ~1900 files | Python+Bash+systemd. 130+ scripts, 3 packages |
| **Default Model** | o4-mini (GPT-5-codex, o3-pro available) | Claude Opus 4.6 (Sonnet/Haiku available) | MiniMax M2.5 conscious + Claude Opus subconscious |
| **Model Flexibility** | Any OpenAI Responses API provider (OpenRouter, Azure, Ollama, DeepSeek) | Anthropic models only | OpenRouter multi-model via task_router.py |
| **Execution Model** | Local CLI, local sandbox | Local CLI, local sandbox | Dual-layer: gateway (M2.5) + cron-spawned Claude Code |
| **TUI** | Ratatui (Rust) full-screen terminal | React/Ink terminal app | No TUI — Telegram chat + CLI scripts |

### Tool Permissions

| Aspect | Codex | Harness | Clarvis |
|--------|-------|---------|---------|
| **Approval Policies** | 3 levels: `untrusted`, `on-request`, `never` | 6 modes: default, plan, acceptEdits, bypass, dontAsk, auto | Binary: `--dangerously-skip-permissions` or interactive |
| **Granularity** | Per-category toggles (sandbox_approval, rules, mcp_elicitations, skill_approval) | Per-tool rules with 8 priority sources (policy→session) | None (all-or-nothing) |
| **Classifier** | Experimental "smart approvals" via guardian model | LLM sideQuery classifier with denial tracking (3 consecutive/20 total limit) | None |
| **Dangerous Patterns** | Implicit via sandbox restrictions | Explicit blocklist (23 interpreters + bash-specific + internal tools) | None |
| **Enterprise Policy** | Not mentioned | `allowManagedPermissionRulesOnly` — locks out user/project rules | N/A |
| **Winner** | **Codex** — native OS sandbox enforcement | Harness — most sophisticated rule engine | Clarvis — needs work |

### Sandbox / Safety

| Aspect | Codex | Harness | Clarvis |
|--------|-------|---------|---------|
| **Sandbox Technology** | OS-native: macOS Seatbelt, Linux iptables/ipset, Windows native | Process-level via `@anthropic-ai/sandbox-runtime` | lockfiles + `--dangerously-skip-permissions` |
| **Sandbox Modes** | `read-only`, `workspace-write` (default), `danger-full-access` | 6 permission modes (effectively: restricted → bypass) | No sandbox — full system access |
| **Network Control** | Blocked by default; per-profile domain allow/deny via SOCKS5 proxy crate | Not detailed in source (likely OS-level) | No network restrictions |
| **Protected Paths** | `.git/`, `.codex/` always read-only even in workspace-write | `.git/`, `.claude/`, `.vscode/`, shell configs — bypass-immune | None |
| **Secret Filtering** | Dedicated crate; env auto-excludes KEY/SECRET/TOKEN patterns | UNC path rejection, file-write race detection | None |
| **Winner** | **Codex** — purpose-built Rust sandbox crates per OS | Harness — good layered defense | Clarvis — significant gap |

### Memory / State

| Aspect | Codex | Harness | Clarvis |
|--------|-------|---------|---------|
| **Memory System** | AGENTS.md 3-tier merge (global+repo+dir) + skills SKILL.md | 4-type taxonomy (user/feedback/project/reference) in markdown frontmatter + MEMORY.md index | 10-collection ChromaDB brain (3400+ memories, 146k+ graph edges) |
| **Memory Selection** | Implicit (AGENTS.md loaded at start) | LLM sideQuery — Sonnet picks top 5 relevant memory files per turn | Embedding-based search + graph traversal + salience scoring |
| **Session Persistence** | Not detailed (likely in-memory per session) | JSONL transcripts with UUID chain, interrupt detection, resume flow | Episodic memory (summaries), no full transcript |
| **State Store** | TOML config with named profiles | Immutable AppStateStore (custom observer pattern) | File-based (JSON, JSONL) + ChromaDB |
| **Winner** | Clarvis — **dramatically more sophisticated brain** | Harness — best session persistence | Codex — simplest, most portable |

### Context Compaction

| Aspect | Codex | Harness | Clarvis |
|--------|-------|---------|---------|
| **Strategy** | `model_auto_compact_token_limit` threshold + `/compact` manual + custom prompts | 4-tier graduated: microcompact→collapse→snip→autocompact | Single-tier context compression with section caching (added today) |
| **Customization** | `compact_prompt` or `experimental_compact_prompt_file` | Feature-gated reactive compaction on specific patterns | Template-based brief generation |
| **Reasoning Control** | 5 levels (`minimal` to `xhigh`) + reasoning summary modes | Extended thinking with budget controls | N/A (model handles) |
| **Token Budget** | Per-agent budget with diminishing-returns detection (<500 tok/iter after 3+ loops) | Per-agent 90% threshold OR diminishing returns | Fixed timeouts only |
| **Tool Result Management** | Not detailed | Per-tool `maxResultSizeChars`, disk overflow with preview | No limit management |
| **Winner** | **Harness** — most sophisticated graduated approach | Codex — best reasoning controls | Clarvis — needs graduated strategy |

### Multi-Agent Coordination

| Aspect | Codex | Harness | Clarvis |
|--------|-------|---------|---------|
| **Pattern** | Built-in coordinator-worker (up to 6 concurrent, max depth 1) | Coordinator mode (Agent/SendMessage/TaskStop only) + workers with full tools | `project_agent.py` spawn→result + global lock (1 concurrent) |
| **Agent Types** | 3 built-in: default, worker, explorer + custom agents | 6 task types: LocalShell, LocalAgent, RemoteAgent, InProcessTeammate, Workflow, Dream | project agents in isolated workspaces |
| **Addressing** | Path-based (`/root/agent_a`) + structured messaging | `<task-notification>` XML blocks | File-based (agent.json, result JSON) |
| **Batch Processing** | `spawn_agents_on_csv` — fan-out, merge results | Batch skill (worktree-per-PR, 5-30 parallel) | No batch mode |
| **Isolation** | Subagents inherit sandbox; workspace-write scoped | Git worktree per agent | `/opt/clarvis-agents/<name>/` + worktree functions (added today) |
| **Winner** | **Codex** — most mature multi-agent with CSV batch | Harness — cleanest tool isolation model | Clarvis — functional but limited |

### Packaging & Distribution

| Aspect | Codex | Harness | Clarvis |
|--------|-------|---------|---------|
| **Channels** | npm, Homebrew cask, GitHub binary releases | npm (global install) | Manual install (git clone + pip) |
| **Platforms** | macOS (arm64+x86), Linux (x86+arm64), Windows | macOS, Linux, Windows (via Bun) | Linux only (Ubuntu 24.04 VPS) |
| **Update** | Standard npm/brew update | `safe_update.sh` with backup + health checks + rollback | `safe_update.sh` |
| **IDE Integration** | App-server (JSON-RPC v2) + TypeScript/Python SDKs | VS Code extension, JetBrains, web app | None |
| **Winner** | **Codex** — widest distribution | Harness — best IDE integration | Clarvis — single-purpose deployment |

### Developer Ergonomics

| Aspect | Codex | Harness | Clarvis |
|--------|-------|---------|---------|
| **Config Format** | TOML with named profiles + CLI `-c key=value` overrides | JSON settings (user/project/local layers) + CLAUDE.md | `openclaw.json` + `cron_env.sh` + brain collections |
| **Slash Commands** | 30+ (`/review`, `/compact`, `/agent`, `/plan`, etc.) | 88+ commands | 19 OpenClaw skills (require explicit `/skill`) |
| **Skill System** | SKILL.md files with scripts, agents, references | Markdown frontmatter skills with `whenToUse` auto-selection | SKILL.md per skill (no auto-selection) |
| **Hooks** | `hooks.json` lifecycle hooks | 14+ events (PreToolUse, PostToolUse, Session*, Permission*, etc.) | heartbeat pre/postflight only |
| **MCP Support** | STDIO + HTTP transports, OAuth, per-tool enable/disable/timeout | MCP tool integration | None |
| **Winner** | **Codex** — best config ergonomics | Harness — most extensible hooks/skills | Clarvis — most autonomous |

---

## What Each Does Better

### Codex Does Better
1. **OS-native sandboxing** — Rust crates per platform (Seatbelt, iptables, Windows native). Not just permission rules but actual kernel-level enforcement.
2. **Multi-model flexibility** — Supports any OpenAI Responses API provider including local models (Ollama, LM Studio) via `--oss` mode.
3. **Multi-agent batch processing** — CSV fan-out with `spawn_agents_on_csv`, structured inter-agent messaging, up to 6 concurrent.
4. **Cross-platform distribution** — npm, Homebrew cask, binary releases for 5 platform targets. Code-signed + notarized macOS builds.
5. **Config ergonomics** — TOML with named profiles, CLI overrides via `-c key=value`, AGENTS.md 3-tier merge.
6. **Network security** — Domain-level allow/deny lists via dedicated SOCKS5 proxy crate. Network blocked by default.
7. **Secret filtering** — Dedicated crate; shell env auto-excludes patterns matching KEY/SECRET/TOKEN.

### Harness Does Better
1. **Permission rule engine** — 5-layer defense-in-depth with 8 priority sources, wildcard/prefix/exact matching, enterprise policy lockdown.
2. **Context compaction** — 4-tier graduated strategy (microcompact→collapse→snip→autocompact) preserves information at each level.
3. **Session persistence & recovery** — JSONL transcripts with UUID chains, interrupt detection, orphan filtering, synthetic resume.
4. **Lifecycle hooks** — 14+ hook events with shell/HTTP/callback handlers. Extensibility that Codex and Clarvis lack.
5. **Skill auto-selection** — `whenToUse` field injected into system prompt; model auto-invokes matching skills without explicit commands.
6. **Memory taxonomy** — 4-type classification (user/feedback/project/reference) with LLM-based relevance selection per turn.
7. **IDE integration** — VS Code, JetBrains, web app (claude.ai/code). Codex has app-server but no shipping IDE plugins.
8. **Token budget with diminishing returns** — Auto-stops agents producing <500 tokens/iteration after 3+ cycles.

### Clarvis Already Exceeds Both
1. **Brain sophistication** — 10 specialized collections, 3400+ memories, 146k+ graph edges, Hebbian learning, associative recall via graph traversal. Neither Codex nor harness has anything comparable.
2. **Autonomous operation** — 20+ cron entries, dual-layer architecture (conscious + subconscious), self-evolving via heartbeat pipeline. Both competitors are user-driven tools, not autonomous agents.
3. **Self-awareness** — `self_model.py` (7 capability domains), `phi_metric.py` (IIT consciousness proxy), attention scoring (GWT), reasoning chains. Neither competitor has metacognitive capabilities.
4. **Reflection & dreaming** — 8-step reflection pipeline, counterfactual dream engine, knowledge synthesis, conversation learning. Unique to Clarvis.
5. **Performance self-monitoring** — PI benchmark (8 dimensions), CLR benchmark (7+stability), weekly full evaluations, auto-escalation on degradation. Neither competitor tracks its own performance.
6. **Multi-model task routing** — `task_router.py` routes to optimal model by task complexity (5 categories). Codex has model selection but not task-based routing.
7. **Graph-augmented memory** — SQLite+WAL graph backend with cross-collection semantic edges, Hebbian strengthening, temporal decay. Richer than flat file or vector-only memory.
8. **Cost awareness** — Real-time cost tracking, budget alerts, daily cost reports. Neither competitor has built-in cost management.

---

## Gap Analysis: What Clarvis Should Adopt

| Priority | From | Feature | Effort | Impact |
|----------|------|---------|--------|--------|
| HIGH | Codex | OS-level sandbox for spawned Claude Code | L | Security |
| HIGH | Harness | `whenToUse` skill auto-selection | S | UX |
| HIGH | Harness | Graduated context compaction (4-tier) | M | Token efficiency |
| HIGH | Harness | Token budget + diminishing returns stopping | M | Cost savings |
| MED | Harness | Per-tool result size management | S | Context quality |
| MED | Codex | Multi-agent concurrency (>1 simultaneous) | M | Throughput |
| MED | Harness | JSONL session transcripts | M | Replay/learning |
| LOW | Codex | TOML config with profiles | M | Ergonomics |
| LOW | Codex | Secret env filtering | S | Security |
| LOW | Harness | 14+ lifecycle hooks | L | Extensibility |

---

## Architectural Insight

The three systems represent three philosophies:
- **Codex**: Performance-first (Rust), safety-first (OS sandbox), developer-ergonomics-first (TOML profiles, multi-platform). Optimized for *human developers using AI as a tool*.
- **Harness**: Extensibility-first (hooks, skills, plugins), defense-in-depth (5-layer permissions), enterprise-ready (managed policy). Optimized for *controlled AI assistance in professional settings*.
- **Clarvis**: Autonomy-first (cron-driven, self-evolving), cognition-first (brain, reflection, dreaming), self-awareness-first (PI, Phi, capability domains). Optimized for *an AI agent that operates independently*.

None of them is "better" — they serve fundamentally different use cases. Clarvis's unique position is as an **autonomous cognitive agent** that happens to use coding tools, not a coding tool that happens to be autonomous. The adoption priorities above should strengthen Clarvis's weakest dimensions (safety, compaction, UX) without compromising its strongest (autonomy, cognition, self-awareness).
