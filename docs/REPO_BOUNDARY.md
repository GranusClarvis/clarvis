# Repository Boundary — What Belongs Where

This document defines what belongs in the git repository vs. local/private storage.
It ensures the repo stays clean for open-source distribution while keeping
install-specific data where it belongs.

## In the Repository (tracked by git)

These are **code, configuration templates, and documentation** — things that are
the same across every Clarvis installation:

| Category | Examples | Why tracked |
|----------|----------|-------------|
| Scripts | `scripts/**/*.py`, `scripts/**/*.sh` | Core logic, reproducible |
| Spine modules | `clarvis/**/*.py` | Package code |
| Skills | `skills/*/SKILL.md`, skill scripts | Skill definitions |
| Tests | `tests/**/*.py` | Regression safety |
| Docs | `docs/*.md` | Architecture, guides |
| Templates | `.env.example`, `*.example` | Show structure without secrets |
| Identity examples | `SOUL.md.example`, `USER.md.example`, etc. | Public-safe scaffolding |
| Config templates | `openclaw.json` (sanitized) | Gateway config structure |
| Identity docs | `SOUL.md`, `USER.md`, `IDENTITY.md`, `AGENTS.md` | Agent identity (PII-sanitized) |
| Evolution docs | `ROADMAP.md`, `SELF.md`, `HEARTBEAT.md` | Architecture and protocol |
| .gitignore | `.gitignore` | Exclusion rules |
| Worker templates | `scripts/worker_templates/*.txt` | Cron prompt templates |

## NOT in the Repository (local/private, gitignored)

These are **runtime data, personal artifacts, and install-specific state** — things
that differ per installation or contain sensitive/noisy data:

| Category | Path(s) | Why excluded |
|----------|---------|--------------|
| **Secrets** | `.env`, `*.key`, `*.pem`, `*credentials*` | Security — never version secrets |
| **Vector DB** | `data/clarvisdb/` | Runtime brain state, instance-specific |
| **Episodes/chains** | `data/episodes/`, `data/reasoning_chains/` | Runtime cognitive data |
| **Cost logs** | `data/costs/`, `data/budget_config.json` | Install-specific usage data |
| **Browser sessions** | `data/browser_sessions/` | Auth cookies, session state |
| **Daily logs** | `memory/YYYY-MM-DD.md` | Personal daily notes |
| **Cron digests** | `memory/cron/digest.md`, `memory/cron/*.log` | Instance-specific cron output |
| **Queue archive** | `memory/evolution/QUEUE_ARCHIVE.md` | Historical task completions |
| **Research notes** | `memory/research/` | Instance-specific research output |
| **Long-term memory** | `MEMORY.md` | Curated personal memory |
| **Monitoring** | `monitoring/` | Health logs, alerts, watchdog state |
| **Metrics data** | `data/performance_*.json`, `data/calibration/` | Instance benchmarks |
| **Cognitive state** | `data/cognitive_workspace/` | Working memory buffers |
| **Agent workspaces** | `/opt/clarvis-agents/*/` | Project agent isolated data |
| **Instance state** | `DELIVERY_BOARD.md`, `metrics-baseline.md` | Runtime state documents |
| **Backup files** | `*.bak`, `*.backup` | Temporary recovery files |

## Rules for New Files

1. **Scripts and code** → always tracked. Keep them deterministic (no hardcoded paths;
   use `CLARVIS_WORKSPACE` env var).
2. **Configuration** → track the `.example` template, gitignore the live version.
3. **Runtime data** → never tracked. If a script generates data files, ensure the
   output path is under `data/`, `memory/`, or `monitoring/`.
4. **Documentation** → tracked if it describes the system generically. NOT tracked if
   it contains instance-specific metrics, personal notes, or operator data.
5. **Research output** → NOT tracked. Research scripts are tracked; their output goes
   to `memory/research/` (gitignored).
6. **Queue history** → `QUEUE.md` (active queue) is tracked. `QUEUE_ARCHIVE.md`
   (completed history) is NOT tracked — it's instance-specific noise.

## Verification

Check that no private data is tracked:
```bash
# Should return nothing:
git ls-files | grep -iE '(\.env$|secret|token|\.key$|\.pem$|credential)'

# Should return nothing (runtime dirs):
git ls-files | grep -E '^(data/|monitoring/|memory/)'
```
