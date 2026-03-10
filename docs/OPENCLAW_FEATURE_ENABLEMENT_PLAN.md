# OpenClaw Feature Enablement Plan

_Created: 2026-03-09. Based on OpenClaw 2026.3.7 (42a1394) audit._
_Source: deep review of `/home/agent/.openclaw/openclaw.json`, plugin inventory, skill catalog, ORCHESTRATOR_PLAN §12._

## Current State

- **Version**: 2026.3.7 (42a1394)
- **Plugins loaded**: 7 of 38 available
- **Skills ready**: 29 of 63 available
- **Channels**: Telegram (primary) + Discord (secondary)
- **Models**: GPT-5.4 (OpenAI) primary, M2.5 (OpenRouter) fallback
- **Auto-update**: Disabled (correct — manual via `safe_update.sh`)

---

## Tier 1: Use Immediately (no config changes, zero risk)

These features are already available and just need to be used.

| Feature | How | Benefit |
|---------|-----|---------|
| **`ddg-search` skill** | Already ready. Use in chat: "search for X" | Free web search (no API key), complements Brave/Tavily |
| **`summarize` skill** | Already ready. "Summarize this URL/file" | Quick summarization of long docs, audio, video |
| **`nano-pdf` skill** | Already ready. "Edit this PDF" | PDF manipulation without external tools |
| **`oracle` skill** | Already ready. "Best practices for X" | Prompt patterns + coding best practices |
| **`healthcheck` skill** | Already ready. "Run a security check" | Security hardening + risk assessment |
| **`iteration` skill** | Already ready. "Run 3 research cycles on X" | Back-to-back research without re-prompting |
| **`queue-clarvis` skill** | Already ready. "Show evolution queue" | Quick QUEUE.md status from chat |
| **`clawhub` skill** | Already ready. "List available skills" | Browse + install skills from catalog |

**Action**: No action needed. These work now. Document in `AGENTS.md` for conscious-layer awareness.

---

## Tier 2: Enable with Config Change (low risk, reversible)

| Feature | Config Change | Risk | Benefit |
|---------|---------------|------|---------|
| **Diagnostics/OTEL plugin** | Add `diagnostics-otel` to loaded plugins in `openclaw.json` | Low — read-only tracing | Export structured traces for debugging gateway issues. Useful when investigating message routing problems. |
| **Diffs plugin** | Add `diffs` to loaded plugins | Low — read-only | Shows diff viewer for agent code changes in chat. Helpful for reviewing Claude Code output. |
| **Memory LanceDB plugin** | Add `memory-lancedb` to loaded plugins | Low — alternative memory provider | Vector DB memory as alternative/complement to ClarvisDB. Worth testing for gateway-side recall without hitting ClarvisDB. |
| **Stale process detection** | Add to `scripts/cron_env.sh` `_acquire_lock()` | Low — improves reliability | Check `/proc/<pid>/cmdline` before honoring lockfiles. Prevents stale locks from crashed cron jobs blocking heartbeats. (From claw-empire steal list §12.4.3) |
| **Sequential delegation delays** | Add `time.sleep(random.uniform(10, 20))` in `project_agent.py` loop | Low — minor delay | Prevent API burst when running multi-task loops. (From claw-empire steal list §12.4.4) |

**Action**: Enable OTEL + Diffs plugins first (zero-risk observability). Stale process detection is a code change — do in a future heartbeat.

### Config patch for OTEL + Diffs:
```json
// In openclaw.json, add to plugins array:
"diagnostics-otel", "diffs"
```

---

## Tier 3: Needs Testing Before Enabling (medium effort)

| Feature | What's Needed | Risk | Benefit |
|---------|---------------|------|---------|
| **Context Engine Plugin** | Build Clarvis-specific plugin per OpenClaw 2026.3.7 interface. Design doc at [CLARVIS_CONTEXT_ENGINE_CONCEPT]. | Medium — new code path for context assembly | Runtime context from ClarvisDB + session summary + graph neighbors. Replaces ad-hoc brief construction. Already a P1 queue item. |
| **Auto-commit safety whitelist** | Implement `SAFE_EXTENSIONS` + `BLOCKED_PATTERNS` in `project_agent.py` per steal list §12.4.2 | Low code risk, needs soak | Prevents agents from staging secrets (.env, .pem, .key) or binaries. Critical for multi-agent safety. |
| **Lobster (approval workflows)** | Enable plugin + configure approval triggers | Medium — changes execution flow | Human-in-loop gates for high-risk operations (e.g., confirm before force-push, approve PR merge). Useful when agents get more autonomy. |
| **`acp-router` multi-model routing** | Test routing rules via ACP skill | Medium — model selection logic | Route queries to optimal model (Pi for quick Q&A, Claude for code, Gemini for search). Complements existing `task_router.py`. |
| **Phoenix/LiveView dashboard** | Not applicable — this is Symphony's approach, but our dashboard uses Starlette + PixiJS | N/A | Listed for completeness. Our dashboard approach is correct. |

**Action**: Context engine plugin is the highest-value item here. Start with [CONTEXT_ENGINE_SPIKE] (already in QUEUE). Auto-commit safety whitelist is a quick win — implement in next code heartbeat.

---

## Tier 4: Stay Off (not needed, risky, or wrong fit)

| Feature | Why Off |
|---------|---------|
| **Additional channel plugins** (Slack, WhatsApp, Signal, Matrix, IRC, LINE, etc.) | Single user, two channels sufficient. Each channel adds maintenance + message routing complexity. |
| **BlueBubbles / iMessage** | macOS only. System runs on Linux NUC. |
| **macOS skills** (Apple Notes, Reminders, Bear, Things, Peekaboo) | Wrong platform. |
| **Voice Call plugin** | No voice use case. Chat-only interaction model. |
| **Tailscale/Bonjour/CoreDNS** | Gateway is loopback-only (correct). No need for WAN exposure. |
| **Copilot Proxy plugin** | Adds Microsoft dependency. OpenRouter already routes to all needed models. |
| **Multi-factor auth** | Single-user system with token auth on loopback. MFA adds friction with no security gain. |
| **Full Express+React dashboard** (claw-empire style) | Over-engineered. 660+ files vs our ~700 LOC. Starlette+PixiJS is correct. (Per steal list §12.5) |
| **27-table SQLite schema** | Flat-file approach (agent.json + JSONL) is sufficient for 5 agents. (Per §12.5) |
| **Multi-round review meetings** | Single-user system. PR review is human-on-GitHub. (Per §12.5) |
| **Workflow packs** | One workflow: decompose → spawn → verify → promote. Template proliferation adds maintenance. (Per §12.5) |
| **i18n** | Single user, single language. |
| **CEO WASD movement** | Fun but pointless for a monitoring dashboard. |
| **OAuth multi-account rotation** | Single OpenRouter key. Unnecessary complexity. (Per §12.5) |
| **Rate limiting per channel** | No abuse risk — allowlist-only channels, single user. |

---

## Priority Implementation Order

1. **Now**: Document Tier 1 skills in `AGENTS.md` (zero effort, instant value)
2. **Next heartbeat**: Enable OTEL + Diffs plugins (config change only)
3. **This week**: Auto-commit safety whitelist in `project_agent.py` (steal list item, high safety value)
4. **This week**: Stale process detection in `cron_env.sh` (reliability improvement)
5. **Next sprint**: Context Engine Spike (P1, already queued as [CONTEXT_ENGINE_SPIKE])
6. **Later**: Lobster approval workflows (when agent autonomy increases)

---

## Validation Checklist

- [ ] Tier 1 skills documented and accessible via chat
- [ ] OTEL plugin enabled, traces visible in logs
- [ ] Diffs plugin enabled, diff viewer working in Telegram
- [ ] Auto-commit safety whitelist tested with project agent
- [ ] Stale lock detection verified with killed process scenario
- [ ] Context engine spike produces working prototype
