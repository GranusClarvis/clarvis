# Codex Runtime Surfaces — Adoption Matrix for Clarvis/OpenClaw

**Date**: 2026-03-31
**Task**: [CODEX_RUNTIME_SURFACES]

---

## Codex Surface Split

| Surface | Implementation | User Flow |
|---------|---------------|-----------|
| **CLI REPL** | `codex` — full-screen Ratatui TUI | Developer opens terminal, interacts with agent directly |
| **CLI One-Shot** | `codex "fix lint errors"` | Single prompt, output to terminal |
| **CLI Exec** | `codex exec` — non-interactive, pipes to stdout | CI/CD integration, scripted workflows |
| **CLI Quiet** | `codex -q --json "explain utils.ts"` | Machine-readable output for toolchains |
| **App-Server** | `codex app-server` — JSON-RPC v2 over stdin/stdout | IDE/app backend — not user-facing |
| **IDE (VS Code)** | Extension using app-server protocol | Inline code assistance within editor |
| **IDE (Other)** | TypeScript + Python SDKs for custom integrations | JetBrains, custom IDEs |
| **Desktop App** | App-server TUI (default since v0.118.0) | Standalone desktop experience |
| **CI Mode** | `CODEX_QUIET_MODE=1` | GitHub Actions, automated pipelines |

---

## Adoption Matrix: Relevance to Clarvis/OpenClaw

| Surface | Relevant? | Why / Why Not | Adoption Priority |
|---------|-----------|---------------|-------------------|
| **CLI One-Shot** | **YES** | Exactly how we spawn Claude Code (`spawn_claude.sh`). Same pattern. | Already have |
| **CLI Exec** | **YES** | Maps to our cron pipeline spawns. Non-interactive, stdout capture. | Already have |
| **App-Server Protocol** | **MEDIUM** | JSON-RPC thread management could replace our raw subprocess model. Would enable: thread resume, turn interruption, proper session state. | P2 — evaluate |
| **CI Mode** | **YES** | Maps to our cron-driven heartbeat pipeline. Quiet, machine-parseable. | Already have |
| **CLI REPL** | **LOW** | Clarvis has no interactive terminal user. Telegram chat serves this role. | Skip |
| **IDE Integration** | **LOW** | Clarvis is server-side autonomous. No developer IDE in the loop. | Skip |
| **Desktop App** | **LOW** | No desktop operator. Telegram + web dashboard are our surfaces. | Skip |
| **SDK (TypeScript)** | **MEDIUM** | Could be useful if OpenClaw gateway wanted to orchestrate Codex agents alongside Claude Code. Cross-vendor agent support. | P3 — future |
| **SDK (Python)** | **MEDIUM** | Same — Python SDK could integrate into our scripts for hybrid agent orchestration. | P3 — future |

---

## Surface Mapping: Codex → Clarvis Equivalents

| Codex Surface | Clarvis Equivalent | Gap |
|---------------|-------------------|-----|
| CLI REPL | Telegram chat (via M2.5 conscious layer) | Different paradigm — chat vs terminal |
| CLI One-Shot | `spawn_claude.sh "task" 1200` | Equivalent |
| CLI Exec | Cron pipeline (`cron_autonomous.sh` etc.) | Equivalent |
| App-Server | No equivalent | **Gap**: no structured session protocol |
| IDE Extension | No equivalent | Not needed for autonomous agent |
| CI Mode | Heartbeat pipeline (gate→preflight→exec→postflight) | Equivalent (more sophisticated) |
| `/resume` | No equivalent | **Gap**: no session continuity |
| `/compact` | `context_compressor.py` | Partial (single-tier vs progressive) |
| `/fork` | No equivalent | **Gap**: no conversation branching |

---

## Recommendations

### Already Covered (No Action)
- CLI one-shot, exec, and CI-mode patterns — our spawn/cron pipeline covers these
- Terminal TUI — Telegram chat serves our operator interaction needs

### Worth Evaluating (P2)
1. **App-Server Protocol Pattern**: The JSON-RPC thread/turn model is cleaner than our raw subprocess model. If we ever need session continuity across heartbeats, adopting a similar protocol (even with Claude Code) would be the right abstraction.
2. **`/fork` Concept**: When a heartbeat discovers a task needs branching (e.g., implementation + research), forking the conversation could be more efficient than starting two fresh Claude Code spawns.

### Not Relevant
- IDE integration, desktop app, SDKs — Clarvis is autonomous, not developer-assisting
- Multi-platform distribution — Clarvis runs on a single VPS

---

## Success Criteria Met
- [x] Studied Codex surface split: CLI (REPL, one-shot, exec, quiet), IDE (app-server, extensions), desktop, CI
- [x] Mapped which surfaces are relevant to Clarvis/OpenClaw (CLI exec/one-shot/CI: yes; IDE/desktop: no)
- [x] Identified redundant surfaces (IDE, desktop, REPL — different paradigm)
- [x] Produced adoption matrix with priorities
