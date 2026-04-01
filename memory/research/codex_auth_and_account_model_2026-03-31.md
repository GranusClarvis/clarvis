# Codex Auth & Account Model — Lessons for Clarvis

**Date**: 2026-03-31
**Task**: [CODEX_AUTH_AND_ACCOUNT_MODEL]

---

## Codex Auth Model

### Two Auth Paths

| Method | Flow | UX | Use Case |
|--------|------|-----|----------|
| **ChatGPT Sign-in** | OAuth device code flow → browser redirect → token stored in keychain | 1-click, no API key management | Consumer/individual developers |
| **API Key** | `OPENAI_API_KEY` env var or `auth.json` file | Manual, requires key generation | Enterprise, CI/CD, custom providers |

### Auth Implementation (from source)
- Dedicated `login` and `chatgpt` Rust crates handle auth
- `keyring-store` crate for OS keychain integration (macOS Keychain, Linux secret-service, Windows Credential Manager)
- App-server supports device code flow for ChatGPT sign-in (v0.118.0)
- Multi-provider: `<PROVIDER>_API_KEY` convention (e.g., `OPENROUTER_API_KEY`, `AZURE_OPENAI_API_KEY`)
- `.env` auto-loaded from project root

### Account State Impact on UX
- ChatGPT auth ties to user's subscription tier (Plus, Team, Enterprise) → model availability
- API key auth → pay-per-use, no tier restrictions on model access
- No persistent "account state" in the local agent — auth token is the only state
- Token refresh handled transparently (dynamic bearer token refresh since v0.118.0)

### Trust & Configuration
- `projects.<path>.trust_level = "trusted" | "untrusted"` — per-project trust
- Trusted projects can load project-scoped config; untrusted cannot
- Enterprise: managed permission policies override user settings

---

## OpenClaw ACP Auth Model (Current)

| Aspect | OpenClaw/Clarvis | Gap vs Codex |
|--------|-----------------|--------------|
| **Auth Method** | API key in `agents/main/agent/auth.json` (OpenRouter `sk-or-v1-...`) | No OAuth, no device flow |
| **Key Storage** | Plain JSON file on disk | No keychain integration |
| **Provider** | OpenRouter (multi-model proxy) | Similar to Codex's multi-provider, but single key |
| **Claude Code Auth** | `ANTHROPIC_API_KEY` env var (via `cron_env.sh`) | Standard approach |
| **Trust Model** | Binary: `--dangerously-skip-permissions` or interactive | No per-project trust levels |
| **Refresh** | Manual key rotation | No auto-refresh |

---

## Comparison & Lessons

### What Codex Does Better
1. **Zero-friction onboarding**: "Sign in with ChatGPT" gets a developer running in seconds. No API key generation, no env var setup, no config files. Clarvis requires manual key placement in `auth.json`.
2. **OS keychain**: Secrets stored in platform-native secure storage, not plain JSON files. Our `auth.json` is readable by any process with file access.
3. **Multi-provider convention**: `<PROVIDER>_API_KEY` is predictable. Our env setup in `cron_env.sh` is custom and undocumented for external users.
4. **Token refresh**: Dynamic bearer refresh means no manual intervention on token expiry. Our keys are long-lived but if revoked, require manual replacement.

### What OpenClaw Already Does Well
1. **OpenRouter as single gateway**: One API key accesses 200+ models. Codex needs per-provider configuration for non-OpenAI models.
2. **No account dependency**: Clarvis works with any OpenRouter-compatible key. No subscription tier gating.
3. **Task routing**: `task_router.py` automatically selects optimal model per task type. Codex requires manual model selection.

### Where It Doesn't Matter
- OAuth/device flow: Clarvis has one operator (Patrick). No need for multi-user auth.
- OS keychain: Single VPS, single user. Attack surface is already the entire machine.
- Per-project trust: Clarvis operates in its own workspace. No untrusted project loading.

---

## Actionable Lessons for Reducing Setup Friction

### For Clarvis Agent Flows (P2)
1. **Document the key setup**: Create a `docs/SETUP.md` that explains exactly where to put API keys and what format. Currently tribal knowledge.
2. **Env var convention**: Standardize on `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY` as the canonical env vars. Document in `cron_env.sh` header.
3. **Key validation on boot**: Add a quick API key validation check to `health_monitor.sh` — catch expired/invalid keys before they cause silent failures in heartbeats.

### For Project Agents (P3)
1. **Agent key isolation**: When spawning project agents, consider per-agent API keys (or at minimum, per-agent cost tracking with the same key). Currently all agents share one OpenRouter key.
2. **`.env` auto-load**: Add `.env` file support to `cron_env.sh` for local development/testing without modifying the script itself.

### Not Worth Adopting
- OAuth/device flow — single-operator system
- OS keychain — single VPS, would add complexity without security benefit
- Per-project trust levels — Clarvis trusts itself by design

---

## Success Criteria Met
- [x] Studied Codex auth model: ChatGPT OAuth vs API key, keychain storage, device code flow
- [x] Analyzed how user/account state affects local-agent UX (subscription tiers, trust levels)
- [x] Compared against OpenClaw ACP auth/runtime assumptions (single key, plain JSON, no OAuth)
- [x] Identified lessons for reducing setup friction (documented setup, env convention, key validation)
