# Private vs Public Audit — 2026-04-06

**707 tracked files** total. The `.gitignore` already lists `memory/`, `data/`, `monitoring/`, `MEMORY.md` — but **244 files** under those paths are still tracked (added before the rules existed). They will remain in git history and be served to cloners until explicitly untracked.

---

## 1. Path Classification

### A. UNTRACK — Instance data, must `git rm --cached`

These 244+ files are gitignored *in rules* but still tracked. A fresh installer should never receive them.

| Path/Pattern | Count | Content Type | Risk |
|---|---|---|---|
| `memory/YYYY-MM-DD.md` + `.md.gz` | 39 | Daily conversation/operation logs | **PII** — contains operator names, task history, Telegram refs |
| `memory/cron/digest.md` | 1 | Live subconscious digest | Instance runtime state |
| `memory/cron/autonomous.log.1`, `reflection.log.*` | 3 | Rotated cron logs | Instance logs |
| `memory/cron/crontab_backup_*.txt` | 1 | Full crontab with hardcoded `/home/agent/` paths | Machine-specific |
| `memory/cron/digest.md.lock` | 1 | Lock file | Transient state |
| `memory/cron/monthly_reflection_2026-04.md` | 1 | Monthly reflection | Instance journal |
| `memory/cron/agent_*_digest.md` | 5 | Sub-agent digests | Instance state |
| `memory/business/LEDGER.md` | 1 | Wallet balance, resource allocation | **Financial PII** |
| `memory/business/README.md` | 1 | Business memory readme | Could template |
| `memory/deep_system_audit_2026-03-12.md` | 1 | Instance audit results | Instance state |
| `memory/summaries/2026-02-20.md` | 1 | Daily summary | Instance state |
| `memory/evolution/QUEUE.md` | 1 | Live task queue | **Instance runtime state** |
| `memory/evolution/QUEUE_ARCHIVE.md` | 1 | Completed task archive | Instance history |
| `memory/evolution/tasks.md` | 1 | Task tracking | Instance state |
| `memory/evolution/weekly/2026-*.md` | 5 | Weekly evolution summaries | Instance journal |
| `memory/evolution/2026-02-*.md` | 2 | Dated evolution notes | Instance journal |
| `memory/evolution/claude-*.md`, `continuous-evolution.md` | 3 | Evolution strategy notes | Could template |
| `memory/research/*.md` | ~20 | Research notes (top-level) | Reusable knowledge, but instance-generated |
| `memory/research/ingested/*.md` | ~120 | Ingested paper summaries | Reusable knowledge, but instance-generated |
| `data/challenge_feed_state.json` | 1 | Which challenges completed | Instance runtime state |
| `data/challenge_feed.json` | 1 | Challenge definitions | **Keep — reusable seed data** |
| `data/prompt_eval/*.json` | 2 | Eval taskset + results | Taskset is reusable; results are instance state |
| `docs/status.json` | 1 | Dashboard metrics snapshot | Instance runtime state (auto-generated) |
| `metrics-baseline.md` | 1 | Auto-updated metrics | Instance runtime state |

**Total to untrack: ~240 files** (the bulk is `memory/` — already gitignored in rules, just still tracked).

### B. KEEP COMMITTED — Project source code and documentation

| Path/Pattern | Count | Notes |
|---|---|---|
| `clarvis/**/*.py` | ~140 | Spine modules — core project code |
| `scripts/**/*` | ~130 | Brain, cron, cognition, evolution scripts |
| `skills/**/*` | ~40 | OpenClaw skills |
| `config/profiles/*.env.template` | 4 | Already use placeholders — safe |
| `docs/*.md` (most) | ~20 | Architecture, install, conventions docs |
| `docs/*.html`, `docs/style.css` | 6 | Website assets |
| `tests/**` | var | Test files |
| `.github/workflows/ci.yml` | 1 | CI config |
| `pyproject.toml`, `Dockerfile`, `docker-compose.yml` | 3 | Build/deploy config |
| `CONTRIBUTING.md`, `LICENSE`, `README.md` | 3 | Standard OSS files |
| `.gitignore`, `.gitleaks.toml`, `.dockerignore` | 3 | Repo config |

### C. CONVERT TO TEMPLATE — Instance docs that have reusable structure

| File | Current State | Recommendation |
|---|---|---|
| `SOUL.md` | Uses `<see-env>` placeholders for secrets. Branding should reference Clarvis / Star World Order only. | Keep aligned with current public identity. |
| `USER.md` | Already anonymized with `<operator>`, `<operator-alias>` placeholders | **Safe — keep as template** |
| `IDENTITY.md` | Contains agent identity | Review for instance-specifics |
| `SELF.md` | Hardware specs (Intel i7-1260P, 30GB RAM), hostname "clarvis" | Replace with `<hardware>`, `<hostname>` placeholders or move to `SELF.md.example` |
| `DELIVERY_BOARD.md` | Dated delivery sprint (2026-03-17 → 2026-03-31) | Untrack — instance project management |
| `DELIVERY_LOCK.md` | Sprint lock state | Untrack — instance project management |
| `HEARTBEAT.md` | Protocol doc | Keep — reusable |
| `AGENTS.md` | Boot sequence doc | Keep — reusable |
| `ROADMAP.md` | Evolution roadmap | Keep — reusable (review for instance-specific dates) |
| `RUNBOOK.md` | Ops runbook | Keep — reusable |
| `TOOLS.md` | Tool inventory | Keep — reusable |
| `memory/evolution/README.md` | Explains queue format | Convert to `docs/QUEUE_FORMAT.md` or keep in-repo |
| `data/challenge_feed.json` | Reusable challenge definitions | Keep — good seed data |
| `data/prompt_eval/taskset.json` | Reusable eval taskset | Keep — good test fixture |

### D. INSTANCE STATE — Already gitignored, confirming correct

| Path | Status |
|---|---|
| `data/clarvisdb/` (ChromaDB) | Already gitignored via `data/` |
| `data/performance_*.json` | Already gitignored via `data/` |
| `data/budget_config.json` | Already gitignored via `data/` |
| `monitoring/` | Already gitignored |
| `MEMORY.md` | Already gitignored |
| `.pi/` | Already gitignored |

---

## 2. Proposed .gitignore Additions

The existing `.gitignore` is mostly good. Additions needed:

```gitignore
# --- Instance state documents ---
DELIVERY_BOARD.md
DELIVERY_LOCK.md
metrics-baseline.md

# --- Generated dashboard state ---
docs/status.json
```

No other additions needed — `memory/`, `data/`, `monitoring/` rules already cover the rest; the problem is solely that files were tracked before the rules existed.

---

## 3. Concrete Untrack Commands

**Phase 1 — Bulk untrack `memory/` (240 files)**
```bash
git rm --cached -r memory/
```

**Phase 2 — Untrack stale `data/` files**
```bash
git rm --cached data/challenge_feed_state.json
git rm --cached data/prompt_eval/eval_results.json
# KEEP: data/challenge_feed.json (seed data)
# KEEP: data/prompt_eval/taskset.json (test fixture)
```

**Phase 3 — Untrack instance state docs**
```bash
git rm --cached docs/status.json
git rm --cached metrics-baseline.md
git rm --cached DELIVERY_BOARD.md DELIVERY_LOCK.md
```

**Phase 4 — Move reusable seed data out of gitignored paths**
```bash
# These are useful for fresh installs but live under data/ which is gitignored
mkdir -p seed/
git mv data/challenge_feed.json seed/challenge_feed.json
git mv data/prompt_eval/taskset.json seed/prompt_eval_taskset.json
```

**Phase 5 — Template conversion for SELF.md**
Replace hardware-specific values with placeholders (or create `SELF.md.example`).

---

## 4. Research Notes Decision

The `memory/research/` tree (140+ files) contains valuable paper summaries and analysis. Options:

| Option | Pros | Cons |
|---|---|---|
| **A. Untrack all** (recommended) | Clean install, no instance baggage | Knowledge lost from repo (still in brain DB) |
| **B. Move to `docs/research/`** | Preserves reusable knowledge | 140+ files of one instance's reading list |
| **C. Keep select foundational ones** | Best papers stay accessible | Curation effort, subjective |

**Recommendation**: Option A. Research is instance-generated knowledge. A fresh installer will build their own. The papers are summarized in the brain DB and can be re-ingested. If specific research is architecturally important, reference it in docs instead.

---

## 5. Risks & Tradeoffs

| Risk | Mitigation |
|---|---|
| `git rm --cached` doesn't rewrite history — files remain in past commits | Acceptable for now; use `git filter-repo` before true public release if needed |
| `memory/evolution/QUEUE.md` is actively written by cron | After untracking, file stays on disk (gitignored). Cron unaffected. |
| Seed data under `data/` will be gitignored by wildcard | Move to `seed/` directory (Phase 4) |
| `docs/status.json` is consumed by `docs/*.html` website | Generate on deploy or ship a `status.json.example` |
| DELIVERY_BOARD/LOCK are active project management | These are sprint-specific; new users won't have them |
| Research untracking loses git-blame provenance | Acceptable — research is reference material, not source code |

---

## 6. Summary

| Category | File Count | Action |
|---|---|---|
| Untrack (memory/) | 240 | `git rm --cached -r memory/` |
| Untrack (data/ instance state) | 2 | `git rm --cached` specific files |
| Untrack (docs/root instance state) | 4 | `git rm --cached` specific files |
| Move to seed/ | 2 | `git mv` to escape `data/` gitignore |
| Template conversion | 1-2 | SELF.md hardware placeholders |
| .gitignore additions | 4 lines | DELIVERY_BOARD, DELIVERY_LOCK, metrics-baseline, docs/status.json |
| Already correct | ~460 | No action needed |

**Net result**: 707 tracked → ~460 tracked. All instance state, daily logs, PII-containing files, and runtime state removed from tracking. Fresh cloner gets clean code + docs + templates.
