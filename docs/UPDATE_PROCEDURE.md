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
# Graceful stop (NOT kill)
pm2 stop openclaw-gateway

# Verify stopped
pm2 list
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
pm2 start openclaw-gateway

# Wait for startup
sleep 5

# Check logs
pm2 logs openclaw-gateway --lines 50
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

- [ ] Gateway is running: `pm2 list`
- [ ] Brain responds: `python3 scripts/brain.py recall "hello"`
- [ ] Config is valid: `python3 -c "import json; json.load(open('$HOME/.openclaw/openclaw.json'))"`
- [ ] Send a test message via Telegram
- [ ] Wait for next heartbeat (30min cycle) and verify it fires
- [ ] Check cron jobs still active: `crontab -l`
- [ ] Review gateway logs: `pm2 logs openclaw-gateway --lines 50`
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
pm2 stop openclaw-gateway

# 2. Reinstall old version
npm install -g openclaw@2026.2.19-2

# 3. Restore config if needed
cp ~/.openclaw/openclaw.json.pre-update ~/.openclaw/openclaw.json

# 4. Restore workspace data if needed
scripts/backup_restore.sh --latest

# 5. Restart
pm2 start openclaw-gateway

# 6. Verify
scripts/health-check.sh
```

---

## Version History

| Date | From | To | Status | Notes |
|---|---|---|---|---|
| 2026-02-21 | 2026.2.19-2 | 2026.2.21-2 | Pending | SHA-256 migration, memory fixes |

---

## Changelog Highlights: v2026.2.15 -> v2026.2.19 (current gap)

Key changes relevant to Clarvis:

1. **Memory/QMD**: Scoped collection names per agent, FTS fallback + query expansion, MMR re-ranking for hybrid search diversity, temporal decay for scoring
2. **Heartbeat/Cron**: Honor explicit topic targets, skip interval heartbeats when HEARTBEAT.md missing, preserve per-job schedule-error isolation
3. **Security**: SHA-1 -> SHA-256 sandbox hashing, session transcript permissions (0o600), many SSRF/injection hardening
4. **Agents**: 1M context beta for Opus/Sonnet, Sonnet 4.6 support, tool loop detection improvements
5. **Telegram**: Draft preview fixes, stream mode improvements, DM voice transcription
6. **Subagents**: Nested sub-agents support, context overflow guards
