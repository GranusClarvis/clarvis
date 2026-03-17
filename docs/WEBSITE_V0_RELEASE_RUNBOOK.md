# Website v0 Release Runbook (IP-first, domain-ready)

_Adapted from fork (2026-03-15). Aligned with leakage gates and repo consolidation._

## 1) Pre-launch checklist

Before starting the server for the first time:

- [ ] Verify no secrets in source files: `grep -rn 'AAF-' scripts/ clarvis/ docs/ | grep -v '.pyc'`
- [ ] Verify no tracked binary data: `git ls-files '*.pyc' '*.egg-info'` → empty
- [ ] Verify `data/` and `monitoring/` not tracked: `git ls-files data/ monitoring/` → empty
- [ ] Verify runtime mode file exists: `cat data/runtime_mode.json`
- [ ] Verify CLR benchmark has run at least once: `ls data/clr_history.jsonl`

## 2) Local/IP launch

From repo root:

```bash
CLARVIS_WORKSPACE=/home/agent/.openclaw/workspace ./scripts/start_website_v0.sh 18800
```

Endpoints:

- Dashboard UI: `http://<ip>:18800/` (private, internal ops)
- Public website v0: `http://<ip>:18800/public`
- Public-safe API feed: `http://<ip>:18800/api/public/status`

## 3) Health checks

```bash
curl -s http://127.0.0.1:18800/health | jq
curl -s http://127.0.0.1:18800/api/public/status | jq
```

Expected:

- `/health` returns `{"status":"ok",...}`
- `/api/public/status` returns mode/queue/CLR/PI payload matching schema in WEBSITE_V0_INFORMATION_ARCH.md

## 4) Leakage verification (MANDATORY before domain binding)

```bash
# Check API payload for secret patterns
curl -s http://127.0.0.1:18800/api/public/status | python3 -c "
import sys, json, re
data = sys.stdin.read()
checks = [
    ('telegram_token', r'[0-9]+:AA[A-Za-z0-9_-]{30,}'),
    ('chat_id', r'REDACTED_CHAT_ID'),
    ('email', r'clarvis420'),
    ('home_path', r'/home/agent'),
    ('api_key', r'sk-or-v1'),
]
clean = True
for name, pattern in checks:
    if re.search(pattern, data):
        print(f'LEAK: {name} found in payload')
        clean = False
if clean:
    print('CLEAN: no leakage detected')
"
```

All checks must return CLEAN before proceeding to domain binding.

## 5) Feed stability soak

Run the feed stability check daily for 7 days:

```bash
# Add to cron or run manually
curl -sf http://127.0.0.1:18800/api/public/status | jq -e '.mode.mode' > /dev/null \
    && echo "$(date -Iseconds) STABLE" >> /tmp/website_v0_soak.log \
    || echo "$(date -Iseconds) FAIL" >> /tmp/website_v0_soak.log
```

Exit criterion: 7 consecutive days with no FAIL entries.

## 6) Domain-ready reverse proxy

Use a reverse proxy (nginx/caddy) in front of the app:

- Map `/` to `http://127.0.0.1:18800/public`
- Map `/api/public/status` to backend unchanged
- Keep ops dashboard at private/authenticated path only
- Enable HTTPS (Let's Encrypt / Cloudflare)

## 7) Post-launch monitoring

- Watch `/api/public/status` response times (should be <500ms)
- Alert if payload size suddenly increases (may indicate data leak)
- Review payload content weekly for any newly-exposed internal details
- If any leakage detected: take site offline immediately, fix, re-soak
