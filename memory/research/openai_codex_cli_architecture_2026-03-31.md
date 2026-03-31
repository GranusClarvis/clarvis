# OpenAI Codex CLI — Architectural Deep Dive

**Date**: 2026-03-31
**Purpose**: Detailed comparison reference vs Claude Code harness
**Sources**: GitHub repo (openai/codex), official developer docs, changelog

---

## 1. Runtime Model

| Aspect | Detail |
|--------|--------|
| **Language** | Rust (primary, `codex-rs/` monorepo with 60+ crates), Node.js wrapper (`codex-cli/` — thin shim, `bin/codex.js`) |
| **Build system** | Bazel (`.bazelrc`, `MODULE.bazel`) + Cargo workspace |
| **Default model** | `o4-mini` (configurable, supports any Responses API-compatible model) |
| **Current models** | GPT-5-codex, GPT-5.4, GPT-4.1, o4-mini, o3, o3-pro, etc. |
| **Execution** | Local CLI process, API calls to cloud models |
| **API protocol** | OpenAI Responses API (streaming SSE, optional WebSocket) |
| **Wire format** | `wire_api = "responses"` (only supported value) |
| **Auth** | "Sign in with ChatGPT" (OAuth, recommended) or API key (`OPENAI_API_KEY`) |
| **Provider support** | OpenAI, OpenRouter, Azure, Gemini, Ollama, Mistral, DeepSeek, xAI, Groq, ArceeAI, LM Studio, any OpenAI-compatible |
| **OSS mode** | `--oss` flag with `oss_provider` config (ollama, lmstudio) |
| **Node requirement** | Node.js 16+ (20 LTS recommended) for the npm wrapper |
| **System reqs** | 4GB RAM min (8GB rec), Git 2.23+, macOS 12+ / Ubuntu 20.04+ / Win11 WSL2 |

### Rust Crate Architecture (60+ crates)
Key crates in `codex-rs/`:
- `cli` — CLI entry point and argument parsing
- `core` — Central agent loop, model interaction
- `tui` — Full-screen terminal UI (Ratatui-based)
- `exec` — Command execution engine
- `exec-server` — PTY-backed execution server
- `sandboxing` — Cross-platform sandbox abstraction
- `linux-sandbox` — Linux-specific sandbox (iptables, namespaces)
- `windows-sandbox-rs` — Windows sandbox
- `process-hardening` — Process-level security
- `network-proxy` — Network proxy for controlled egress
- `config` — Configuration loading (TOML)
- `state` — Session state management
- `tools` — Built-in tool definitions
- `core-skills` — Built-in skill implementations
- `skills` — Skill system framework
- `mcp-server` — MCP server integration
- `rmcp-client` — MCP client (RMCP protocol)
- `connectors` — App/connector integration
- `plugin` — Plugin system
- `app-server` — App-server backend (for IDE extensions)
- `app-server-protocol` — JSON-RPC protocol (v1, v2)
- `app-server-client` — App-server client library
- `backend-client` — Backend API client
- `instructions` — AGENTS.md loading and merging
- `execpolicy` — Execution policy engine
- `hooks` — Lifecycle hooks
- `analytics` — Telemetry/analytics
- `otel` — OpenTelemetry integration
- `login` / `chatgpt` — Authentication
- `git-utils` — Git operations
- `file-search` — File search tool
- `shell-command` — Shell command tool
- `apply-patch` — Patch application tool
- `code-mode` — Code generation mode
- `rollout` — Feature flag/rollout system
- `features` — Feature toggles
- `secrets` — Secret detection/filtering
- `feedback` — User feedback submission
- `keyring-store` — OS keychain integration
- `v8-poc` — V8 JavaScript engine PoC (for safe eval?)

---

## 2. Tool Permissions & Approval Model

### Three Approval Policies

| Policy | Behavior |
|--------|----------|
| **`untrusted`** | Only known-safe read ops run automatically. Mutations/external execution require approval. |
| **`on-request`** | Asks approval for edits outside workspace or network-accessing commands. |
| **`never`** | No approval prompts (via `--ask-for-approval never` or `-a never`) |

### Granular Approval (per-category toggles)
```toml
[approval_policy.granular]
sandbox_approval = true        # Allow sandbox escalation prompts
rules = true                   # Allow execpolicy prompt-rule approvals
mcp_elicitations = true        # Surface MCP elicitation prompts
request_permissions = true     # Allow permission request prompts
skill_approval = true          # Allow skill-script approval prompts
```

### Legacy 3-Tier Model (from README)
- **Suggest** (default): reads allowed, writes/commands need approval
- **Auto Edit**: reads + writes allowed, commands need approval
- **Full Auto**: everything allowed, network disabled, confined to CWD + tmp

### Destructive Tool Rules
- Destructive app/MCP tool calls **always** require approval when the tool advertises a `destructive` annotation
- App connectors that advertise side effects trigger approvals for non-shell operations

### Smart Approvals (experimental)
- `features.smart_approvals = true` — routes approvals through a "guardian reviewer" model

---

## 3. Sandbox Model

### Three Sandbox Modes

| Mode | Behavior |
|------|----------|
| **`read-only`** | File reading only; modifications require approval |
| **`workspace-write`** | File edits + commands within workspace; `.git/`, `.agents/`, `.codex/` read-only |
| **`danger-full-access`** | No sandbox, no approvals (via `--yolo` flag) |

### Platform-Specific Implementation

**macOS 12+:**
- Apple Seatbelt via `sandbox-exec`
- Read-only jail except writable roots: `$PWD`, `$TMPDIR`, `~/.codex`
- Outbound network fully blocked by default

**Linux:**
- Custom sandbox (dedicated `linux-sandbox` Rust crate)
- `iptables`/`ipset` firewall denying egress except OpenAI API
- Docker container recommended for full isolation
- Minimal container image with repo mounted read/write

**Windows:**
- Dedicated `windows-sandbox-rs` crate
- `unelevated` or `elevated` modes
- Private desktop option (`windows.sandbox_private_desktop = true`)
- Proxy-only networking with OS-level egress rules (as of v0.118.0)

### Sandbox Configuration
```toml
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
exclude_slash_tmp = false
exclude_tmpdir_env_var = false
network_access = false          # Outbound network access
writable_roots = ["/path/to/other/dir"]
```

### Permissions Profiles (advanced)
```toml
[permissions.my_profile]
[permissions.my_profile.filesystem]
[permissions.my_profile.filesystem.":project_roots".src]
# "read" | "write" | "none" — scoped to detected project roots

[permissions.my_profile.network]
enabled = true
mode = "limited"               # "limited" | "full"
allowed_domains = ["api.example.com"]
denied_domains = ["evil.com"]
allow_unix_sockets = ["/var/run/docker.sock"]
allow_local_binding = false
enable_socks5 = false
```

### Network Proxy Architecture
- Dedicated `network-proxy` crate
- SOCKS5 support (with optional UDP)
- Upstream proxy chaining
- Domain allowlists/denylists enforced at proxy level
- Web search defaults to **cached mode** (OpenAI's indexed results) to reduce prompt injection risk

---

## 4. Context Compaction & Memory

### Context Window Management
- `model_context_window` — override detected context size
- `model_auto_compact_token_limit` — token threshold triggering **automatic history compaction**
- `/compact` slash command — manual compaction (summarizes visible conversation to free tokens)
- `compact_prompt` — custom compaction prompt override
- `experimental_compact_prompt_file` — load compaction prompt from file

### Reasoning Control
- `model_reasoning_effort`: `minimal | low | medium | high | xhigh`
- `model_reasoning_summary`: `auto | concise | detailed | none`
- `model_verbosity`: `low | medium | high` (GPT-5 Responses API)

### Session Persistence
- **History file**: `~/.codex/history.jsonl` — stores full transcripts
- `history.persistence`: `save-all | none`
- `history.max_bytes`: cap file size (e.g., 104857600 for 100 MiB); oldest entries dropped
- `/resume` command — session picking, directory scoping, session ID targeting
- `/fork` — clone current conversation into new thread

### AGENTS.md System (Contextual Memory)
Three-tier merge, loaded top-down:
1. `~/.codex/AGENTS.md` — global personal guidance
2. Repository root `AGENTS.md` — shared project notes
3. Current directory `AGENTS.md` — sub-folder specifics

Controls:
- `--no-project-doc` flag or `CODEX_DISABLE_PROJECT_DOC=1` to disable
- `project_doc_max_bytes` — cap bytes read per AGENTS.md
- `project_doc_fallback_filenames` — alternative filenames

### State Storage
- `sqlite_home` — SQLite state database directory
- `CODEX_HOME` — root state dir (defaults `~/.codex`)
- `auth.json` or OS keychain for credentials

### Shell Environment Snapshot
- `features.shell_snapshot = true` (default) — snapshots shell environment
- `shell_environment_policy.inherit`: `all | core | none`
- Auto-excludes vars matching KEY/SECRET/TOKEN patterns

---

## 5. Multi-Agent / Subagents

### Coordinator-Worker Pattern
- Main agent orchestrates specialized subagents in parallel
- Waits until all results available, returns consolidated response
- Subagents spawned **only when explicitly requested**

### Configuration
```toml
[agents]
max_threads = 6                # Max concurrent agent threads (default: 6)
max_depth = 1                  # Max nesting depth (prevents recursive spawning)
job_max_runtime_seconds = 1800 # Per-worker timeout for CSV jobs

[agents.my_worker]
description = "Role guidance for agent selection"
config_file = "path/to/role.toml"
nickname_candidates = ["alpha", "beta"]
```

### Built-in Agent Types
- `default` — general-purpose fallback
- `worker` — execution-focused for implementation
- `explorer` — read-heavy for codebase analysis

### Custom Agents
Three mandatory fields: `name`, `description`, `developer_instructions`

### Inter-Agent Communication (v0.117.0+)
- Readable path-based addresses: `/root/agent_a`
- Structured inter-agent messaging
- `/agent` slash command to switch between active threads

### Batch Processing
- `spawn_agents_on_csv` tool — fan-out work across CSV rows
- Each worker calls `report_agent_job_result` exactly once
- Results merge into exported CSV with metadata
- Workers that exit without reporting are marked with error

### Sandbox Inheritance
- Subagents inherit parent's sandbox policy
- Approval requests surface from inactive threads
- Parent's live runtime overrides reapplied when spawning children
- Project-profile layering, persisted host approvals, and symlinked writable roots inherited

---

## 6. Packaging & Distribution

| Method | Command |
|--------|---------|
| **npm** | `npm install -g @openai/codex` |
| **Homebrew** | `brew install --cask codex` |
| **Binary** | GitHub Releases (platform-specific) |

- Package: `@openai/codex` (npm), version `0.0.0-dev` (rolling)
- License: Apache-2.0
- Package manager: pnpm@10.29.3 (for development)
- Module type: ES modules
- Shipped files: `bin/` + `vendor/` (pre-compiled Rust binaries)
- Update check: `check_for_update_on_startup` config toggle

### Build Pipeline
- Rust compilation via Bazel + Cargo
- Platform targets: macOS (arm64, x86_64), Linux (x86_64, arm64), Windows
- Code signing: macOS (notarized), Linux, Windows (separate workflows)
- Zsh completion: separate release artifact

---

## 7. Developer Ergonomics

### CLI Modes
- **Interactive REPL**: `codex` — full-screen TUI
- **Initial prompt**: `codex "fix lint errors"`
- **Quiet/non-interactive**: `codex -q --json "explain utils.ts"`
- **Exec mode**: `codex exec` — non-interactive, pipes to stdout
- **CI mode**: `CODEX_QUIET_MODE=1` for GitHub Actions

### IDE Integration
- App-server architecture (`app-server` crate) — JSON-RPC v2 protocol
- SDKs: TypeScript (`sdk/typescript/`) and Python (`sdk/python/`)
- `file_opener` config: `vscode | cursor | windsurf | vscode-insiders | none`
- App-server TUI: now default (v0.118.0), replaces legacy CLI TUI

### 30+ Slash Commands
Key commands: `/model`, `/fast`, `/personality`, `/clear`, `/new`, `/fork`, `/resume`, `/plan`, `/permissions`, `/status`, `/diff`, `/ps`, `/compact`, `/mention`, `/review`, `/init`, `/apps`, `/agent`, `/plugins`, `/title`, `/theme`, `/mcp`, `/copy`, `/feedback`

### Configuration Model
- **Format**: TOML (`config.toml`)
- **Locations**: `~/.codex/config.toml` (user) + `.codex/config.toml` (project, trusted only)
- **Profiles**: `[profiles.<name>]` — named config sets, switchable via `--profile`
- **CLI overrides**: `-c key=value` (TOML syntax, dot notation for nesting)
- **Environment**: `.env` auto-loaded, `<PROVIDER>_API_KEY` convention

### Skills System
- `SKILL.md` files in `.codex/skills/<name>/`
- Per-skill enablement: `skills.config[].enabled`, `skills.config[].path`
- Skill-script approval: controllable via `approval_policy.granular.skill_approval`
- Auto-install MCP dependencies: `features.skill_mcp_dependency_install = true`
- Example skills in repo: `babysit-pr` (with agents, references, scripts), `remote-tests`, `test-tui`

### MCP Integration
```toml
[mcp_servers.my_server]
enabled = true
command = "npx"
args = ["-y", "@my/mcp-server"]
cwd = "."
env = { API_KEY = "..." }
required = true
startup_timeout_sec = 10
tool_timeout_sec = 60
enabled_tools = ["tool_a"]
disabled_tools = ["tool_b"]
```
- STDIO and streaming HTTP transports
- OAuth support (device code flow, scopes, resource params)
- Auto-launched at session start

### Hooks (experimental)
- `hooks.json` alongside config layers
- Lifecycle events: `conversation_starts`, `api_request`, `tool_decision`, `tool_result`
- Notify scripts receive JSON payload with `type`, `thread-id`, `turn-id`, `cwd`, messages

### Multi-File Operations
- `--add-dir` flag for exposing multiple writable roots
- Cross-project coordination
- Image input: `-i` flag (PNG/JPEG)

---

## 8. Safety & Security

### Data Retention
- Zero Data Retention (ZDR) supported for enterprise
- Local history in `history.jsonl` (configurable)
- `otel.log_user_prompt` — opt-in prompt export
- Sensitive pattern filtering in history config

### Secret Protection
- Dedicated `secrets` crate for detection/filtering
- `shell_environment_policy` auto-excludes KEY/SECRET/TOKEN patterns
- `history.sensitivePatterns` array for custom filtering

### Process Hardening
- Dedicated `process-hardening` crate
- Protected paths: `.git/`, `.agents/`, `.codex/` always read-only
- Project trust levels: `projects.<path>.trust_level = "trusted" | "untrusted"`
- Project-scoped configs only load for trusted projects

### Observability
- OpenTelemetry integration (OTLP HTTP/gRPC)
- Structured events with batching and async flush
- Anonymous usage metrics (no PII, disablable)
- Debug mode: `DEBUG=true` for full API request/response logging

---

## Key Differences vs Claude Code (Summary Table)

| Dimension | Codex CLI | Claude Code |
|-----------|-----------|-------------|
| **Language** | Rust + Node.js shim | TypeScript (Node.js) |
| **Model** | OpenAI models (GPT-5, o4-mini) + any compatible | Claude (Opus, Sonnet) |
| **Sandbox** | OS-native (Seatbelt/iptables/Windows) per-crate | `--dangerously-skip-permissions` flag |
| **Approval** | 3 policies + granular per-category | Per-tool approval or skip-all |
| **Context** | Auto-compact at token limit + manual `/compact` | Conversation-level, configurable |
| **Multi-agent** | Built-in coordinator-worker (max 6 threads) | Single agent (no built-in multi-agent) |
| **Memory** | AGENTS.md 3-tier + history.jsonl + SQLite state | CLAUDE.md + conversation context |
| **Config** | TOML (profiles, providers, permissions) | JSON (settings.json) |
| **Distribution** | npm + Homebrew + binary releases | npm (`@anthropic-ai/claude-code`) |
| **MCP** | Native STDIO + HTTP, OAuth, per-tool config | MCP support via config |
| **Skills** | SKILL.md files + scripts + agents per skill | Custom slash commands |
| **Network** | Proxy-based allowlist/denylist per profile | No built-in network control |
| **IDE** | App-server (JSON-RPC v2) + TS/Python SDKs | VS Code extension |

---

## Recent Evolution (Changelog)

**v0.118.0 (2026-03-31)**:
- Windows sandbox: proxy-only networking with OS-level egress
- Dynamic bearer token refresh for custom providers
- App-server device code flow for ChatGPT sign-in
- Linux sandbox and MCP startup reliability improvements

**v0.117.0 (2026-03-26)**:
- Plugins as first-class workflow (sync, browse, install/remove)
- Sub-agent path-based addresses (`/root/agent_a`) + structured messaging
- App-server TUI enabled by default
- Legacy `read_file` and `grep_files` tools retired
- Image workflows improved
