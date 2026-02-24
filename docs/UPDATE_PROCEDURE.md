# OpenClaw Update Procedure

## Quick Reference

```bash
# Check what's available (safe, no changes)
scripts/safe_update.sh --check

# Full update with backup + health checks
scripts/safe_update.sh

# Update to a specific version
scripts/safe_update.sh --target 2026.2.21-2

# Emergency rollback
scripts/safe_update.sh --rollback
```

---

## Update Assessment: v2026.2.19-2 -> v2026.2.21

### Upgrade Benefits

| Feature | Impact on Clarvis | Priority |
|---|---|---|
| SHA-1 -> SHA-256 for sandbox IDs | Low (we run local mode, no sandbox) | Low |
| Owner-ID obfuscation HMAC | Security improvement for gateway auth | Medium |
| Memory/QMD fixes (collection scoping, FTS fallback) | Could improve brain operations | High |
| Gemini 3.1 model support | New model option for fallbacks | Medium |
| Discord voice improvements | If using Discord voice | Low |
| Telegram streaming fixes | Better message delivery | Medium |
| Security hardening (many patches) | General safety | High |
| Heartbeat/Cron fixes | Directly affects autonomous loops | High |

### Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Config format changes | Low | npm preserves openclaw.json; we back it up |
| Bundled skill changes | Low | Workspace skills are separate from npm skills |
| ClarvisDB corruption | Very Low | Update doesn't touch workspace/data/ |
| Custom script breakage | Very Low | Scripts are in workspace, not in npm package |
| Gateway startup failure | Medium | Rollback script handles this |
| Cron/heartbeat regression | Medium | Health check + manual verification list |

### Recommendation

**UPGRADE RECOMMENDED.** The memory/QMD fixes and heartbeat/cron improvements directly benefit the cognitive architecture. Security patches are substantial. Risk to brain data is near-zero since the update only replaces `~/.npm-global/lib/node_modules/openclaw/`.

---

## What Gets Updated vs What's Safe

### UPDATED by `npm install -g openclaw`:
```
~/.npm-global/lib/node_modules/openclaw/    # Application code
  ├── skills/                                # Bundled skills (54+)
  ├── CHANGELOG.md
  ├── package.json
  └── ... (all npm package files)
```

### NOT TOUCHED (safe):
```
~/.openclaw/workspace/
  ├── data/clarvisdb/         # Brain vector memory
  ├── data/clarvisdb-local/   # Local embeddings
  ├── data/working_memory*    # GWT attention buffer
  ├── data/reasoning_chains/  # Chain logs
  ├── data/evolution/         # Evolution loop data
  ├── data/self_model.json    # Capability scores
  ├── scripts/                # ALL custom scripts (brain.py, etc.)
  ├── memory/                 # Working memory + evolution queue
  ├── skills/                 # Workspace-level skills
  ├── SOUL.md, SELF.md, etc.  # Identity documents
  └── config/                 # App configs

~/.openclaw/openclaw.json     # Main configuration (preserved by npm)
```

---

## Full Update Procedure (Manual)

If you prefer to run manually instead of using the script:

### Phase 1: Pre-Backup Verification
```bash
# Check current state
scripts/health-check.sh

# Verify brain is healthy
python3 scripts/brain.py stats

# Check git state
cd ~/.openclaw/workspace && git status
```

### Phase 2: Create Backup
```bash
# Full workspace backup
scripts/backup_daily.sh --full

# Backup config separately
cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.pre-update

# Record current version
npm list -g openclaw --depth=0
```

### Phase 3: Stop Gateway
```bash
# Graceful stop via systemd (preferred)
systemctl --user stop openclaw-gateway.service

# Verify stopped (port should not be listening)
ss -tlnp | grep ":18789 "

# Fallback if systemd unavailable:
# pm2 stop openclaw-gateway
```

### Phase 4: Update
```bash
# Update to latest
npm install -g openclaw

# Or to specific version
npm install -g openclaw@2026.2.21-2
```

### Phase 5: Post-Update Migration
```bash
# Run OpenClaw's built-in doctor
openclaw doctor --fix --non-interactive --yes
```

### Phase 6: Restart
```bash
# Start via systemd (preferred)
systemctl --user start openclaw-gateway.service

# Wait for startup and verify port
sleep 5
ss -tlnp | grep ":18789 "

# Check logs
journalctl --user -u openclaw-gateway.service --since "5 min ago" --no-pager

# Fallback if systemd unavailable:
# pm2 start openclaw-gateway
# pm2 logs openclaw-gateway --lines 50
```

### Phase 7: Verify
```bash
# Health check
scripts/health-check.sh

# Brain check
python3 scripts/brain.py recall "test query"

# Gateway API
curl -s http://127.0.0.1:18789/ | head -5

# Check version
openclaw --version 2>/dev/null || npm list -g openclaw --depth=0
```

---

## Post-Update Checklist

After any update, verify these manually:

- [ ] Gateway port listening: `ss -tlnp | grep ":18789 "`
- [ ] Systemd service active: `systemctl --user status openclaw-gateway.service`
- [ ] Brain responds: `python3 scripts/brain.py recall "hello"`
- [ ] Config is valid: `python3 -c "import json; json.load(open('$HOME/.openclaw/openclaw.json'))"`
- [ ] Send a test message via Telegram
- [ ] Wait for next heartbeat (30min cycle) and verify it fires
- [ ] Check cron jobs still active: `crontab -l`
- [ ] Review gateway logs: `journalctl --user -u openclaw-gateway.service --since "30 min ago" --no-pager`
- [ ] Verify working memory: `python3 -c "import json; print(json.load(open('data/working_memory_state.json')).keys())"`
- [ ] Test reasoning chain hook: `python3 scripts/reasoning_chain_hook.py open "update test" --why "testing post-update"`

---

## Rollback Procedure

### Automatic (Recommended)
```bash
scripts/safe_update.sh --rollback
```

### Manual
```bash
# 1. Stop gateway
systemctl --user stop openclaw-gateway.service

# 2. Reinstall old version
npm install -g openclaw@2026.2.21-2

# 3. Restore config if needed
cp ~/.openclaw/openclaw.json.pre-update ~/.openclaw/openclaw.json

# 4. Restore workspace data if needed
scripts/backup_restore.sh --latest

# 5. Restart
systemctl --user start openclaw-gateway.service

# 6. Verify port is listening
ss -tlnp | grep ":18789 "
```

---

## Version History

| Date | From | To | Status | Notes |
|---|---|---|---|---|
| 2026-02-24 | 2026.2.21-2 | 2026.2.23 | **Done** | Migrated PM2→systemd, self-decapitation fix, auto-updater disabled |
| 2026-02-21 | 2026.2.19-2 | 2026.2.21-2 | Done | SHA-256 migration, memory fixes |

---

## Important Notes

### Auto-Updater (Disabled)
OpenClaw 2026.2.23+ has a built-in auto-updater that checks npm on gateway start. We disable this because we manage updates manually via `safe_update.sh` with backups and health checks.

Config settings (in `openclaw.json`):
```json
"update": {
  "checkOnStart": false,
  "auto": { "enabled": false }
}
```

### Gateway Management: Systemd (since 2026-02-24)
The gateway runs as a **systemd user service** (`openclaw-gateway.service`), not PM2.
- Linger is enabled (survives logout, starts on boot)
- Auto-restart on crash (`Restart=always`, `RestartSec=5`)
- Installed via: `openclaw gateway install`
- Managed via: `systemctl --user {start|stop|restart|status} openclaw-gateway.service`
- Logs: `journalctl --user -u openclaw-gateway.service`
- Required env vars (set in `cron_env.sh`): `XDG_RUNTIME_DIR`, `DBUS_SESSION_BUS_ADDRESS`

### Self-Decapitation Prevention
`safe_update.sh` detects if it's running inside the gateway process tree (e.g. when M2.5 invokes it). If so, it re-launches itself as a detached process via `nohup setsid` and also spawns a watchdog that will restart the gateway if the update script dies unexpectedly.

---

## Changelog Highlights: v2026.2.15 -> v2026.2.19 (current gap)

Key changes relevant to Clarvis:

1. **Memory/QMD**: Scoped collection names per agent, FTS fallback + query expansion, MMR re-ranking for hybrid search diversity, temporal decay for scoring
2. **Heartbeat/Cron**: Honor explicit topic targets, skip interval heartbeats when HEARTBEAT.md missing, preserve per-job schedule-error isolation
3. **Security**: SHA-1 -> SHA-256 sandbox hashing, session transcript permissions (0o600), many SSRF/injection hardening
4. **Agents**: 1M context beta for Opus/Sonnet, Sonnet 4.6 support, tool loop detection improvements
5. **Telegram**: Draft preview fixes, stream mode improvements, DM voice transcription
6. **Subagents**: Nested sub-agents support, context overflow guards
