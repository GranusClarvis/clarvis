# Clarvis Website v0 — Information Architecture & Data Contracts

_Status: executable v0 plan (pre-domain, IP-first deployment)._
_Adapted from fork (2026-03-15). Aligned with repo consolidation plan._

## 1) Goals for v0

1. Explain what Clarvis is (architecture + mission).
2. Show current operating mode and live status.
3. Show roadmap and linked repos.
4. Show benchmark signal (CLR) in a public-safe way.

v0 is intentionally minimal: correctness + clarity over visual complexity.

---

## 2) Page map (v0)

### `/` Home

- One-paragraph identity statement (from SOUL.md, sanitized)
- Current mode badge (`ge` / `architecture` / `passive`)
- Queue activity summary (pending/in-progress/done counts only — no task descriptions)
- Latest CLR snapshot (score + value_add + gate_pass)
- Latest 5 task completions (tag + status only, no internal details)

### `/architecture`

- Clarvis (harness/orchestration) — the autonomous evolution runtime
- ClarvisDB (memory/retrieval substrate) — ChromaDB + graph + embedding pipeline
- Context layer (context assembly, prompt building) — internal module, not a separate package
- Runtime modes and invariants

**Note:** The context/prompt layer (`clarvis.context.*`) is an internal module within the main `clarvis` package. It is NOT exposed as a separate package (`clarvis-p` was explicitly rejected — see REPO_CONSOLIDATION_PLAN).

### `/repos`

- Links + short purpose for:
  - **clarvis** — main repo: spine, runtime, CLI, metrics, orchestration
  - **clarvis-db** — standalone brain package: ChromaDB vector memory with Hebbian learning
- Extraction status labels: `internal`, `stabilizing`, `public-ready`
- No reference to clarvis-p, clarvis-cost, or clarvis-reasoning (internal-only)

### `/benchmarks`

- Latest CLR score + value_add + gate_pass
- Short description of dimensions and why gate pass matters
- PI (Performance Index) snapshot — operational health composite

### `/roadmap`

- Near-term phases and current active phase
- Recently completed milestones
- No internal QUEUE.md task descriptions (privacy risk)

---

## 3) Public feed contract

Endpoint (implemented in dashboard server):

- `GET /api/public/status`

Schema:

```json
{
  "mode": {
    "mode": "ge",
    "pending_mode": null,
    "updated_at": "2026-03-15T15:00:00+00:00"
  },
  "queue": {
    "pending": 12,
    "in_progress": 1,
    "done": 54
  },
  "benchmarks": {
    "clr": {
      "timestamp": "2026-03-15T14:00:00+00:00",
      "clr": 0.72,
      "baseline_clr": 0.48,
      "value_add": 0.24,
      "gate_pass": true,
      "schema_version": "1.0"
    },
    "pi": {
      "timestamp": "2026-03-15T14:00:00+00:00",
      "pi": 0.71,
      "dimensions": 8
    }
  },
  "recent_completions": [
    {
      "ts": "2026-03-15T14:32:12+00:00",
      "status": "success",
      "tag": "TASK_TAG"
    }
  ],
  "updated_at": "2026-03-15T15:00:10+00:00"
}
```

### Public-safe constraints (HARD RULES)

- **No private memory dumps** — no brain search results, no episodic content
- **No secret-bearing config** — no API keys, tokens, chat IDs, email addresses
- **No raw cron command strings** — expose only schedule summary, not commands
- **No internal file paths** — no `/home/agent/...` paths in any payload
- **No task descriptions** — only tag names and counts (descriptions may contain IP)
- **No switch_history in mode** — only current mode + updated_at (history may reveal strategy)
- **No active_tasks detail** — only counts (task descriptions may contain IP)

### Leakage gates (from Open-Source Readiness Audit)

Before ANY public exposure:
1. Run `git ls-files '*.pyc'` — must return empty
2. Verify `data/`, `monitoring/` are NOT tracked
3. Search payload for Telegram bot token pattern `[0-9]+:AA[A-Za-z0-9_-]+` — must be clean
4. Search payload for chat ID pattern — must be clean
5. Search payload for email pattern — must be clean
6. Verify no `memory/` daily log content in payload
7. Feed must be stable (no crashes/schema changes) for 7 consecutive days

---

## 4) Rendering strategy (v0)

- Server: Starlette-backed with static assets (reuse existing dashboard_server.py foundation)
- Frontend: polls `/api/public/status` every 15–30s
- If feed unavailable: show stale timestamp + degraded badge
- No client-side JavaScript that calls internal APIs

---

## 5) Deployment progression

1. **IP-hosted preview** (same machine as dashboard server, port 18800)
2. **Leakage audit** — all 7 gates above must pass
3. **Feed stability** — 7 consecutive days without schema change or crash
4. **Domain binding** once content and feed are stable
5. **Cache/CDN** once endpoint schema is frozen

---

## 6) Exit criteria for v0 release

1. `/api/public/status` stable for 7 consecutive days
2. Mode + queue + CLR + PI render correctly from live data
3. No private/internal leakage in rendered payloads (all 7 leakage gates pass)
4. Open-source readiness audit critical items resolved (secrets → env vars)
5. README.md + LICENSE file exist at repo root
