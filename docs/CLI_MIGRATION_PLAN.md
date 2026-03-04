# CLI Migration Plan — Unified `clarvis` CLI

_Created: 2026-03-04 · Updated: 2026-03-04 · Status: Phase 1 (console script + tests) complete_

## 1. Goal

Replace 18+ ad-hoc script CLIs (`python3 scripts/brain.py health`, `python3 scripts/performance_benchmark.py record`, etc.) with a single canonical entrypoint:

```bash
python3 -m clarvis brain health
python3 -m clarvis bench run
python3 -m clarvis heartbeat run
python3 -m clarvis queue next
```

Eventually installable as `clarvis` via `pip install -e .` (console_scripts).

## 2. Design Decisions

### Framework: Typer

| Option | Pros | Cons |
|--------|------|------|
| **Typer** | Already installed, Rich integration, auto `--help`, async-ready, type hints | Adds dependency |
| argparse | Stdlib, zero deps | Verbose, no subcommand groups, manual help formatting |
| Click | Already installed, mature | Typer wraps it — use Typer directly |

**Decision**: Typer. It's already installed (`typer==0.24.0`), gives us subcommand groups with zero boilerplate, and auto-generates `--help` from type hints.

### Package layout

```
clarvis/
├── __init__.py          # spine (exists)
├── __main__.py          # NEW: python3 -m clarvis entrypoint
├── cli.py               # NEW: root Typer app + subcommand registration
├── cli_brain.py         # NEW: clarvis brain {health,search,optimize,...}
├── cli_bench.py         # NEW: clarvis bench {run,quick,pi}
├── cli_heartbeat.py     # NEW: clarvis heartbeat {run}
├── cli_queue.py         # NEW: clarvis queue {next,archive,add,status}
├── cli_cron.py          # FUTURE: clarvis cron {run,list,status}
├── brain/               # (exists — core brain implementation)
├── memory/              # (exists — memory subsystems)
├── cognition/           # (exists — attention, confidence, thought)
├── heartbeat/           # (exists — lifecycle hooks)
├── context/             # (exists — stub)
├── metrics/             # (exists — stub)
└── orch/                # (exists — stub)
```

Each `cli_*.py` module defines a `typer.Typer()` sub-app that gets registered in `cli.py`.

### Import strategy

CLI modules use lazy imports — the heavy libraries (ChromaDB, ONNX) are only imported when a command actually runs. This keeps `python3 -m clarvis --help` fast (<200ms).

## 3. Current State (What Exists)

### Fully migrated to clarvis/ spine
- `clarvis.brain` — ClarvisBrain, singletons, hooks (5 modules)
- `clarvis.memory` — working_memory, episodic_memory, procedural_memory, hebbian_memory, memory_consolidation
- `clarvis.cognition` — attention, confidence, thought_protocol
- `clarvis.heartbeat` — hooks, adapters

### Still script-only (not in clarvis/ spine)
- `scripts/performance_benchmark.py` (1476 lines)
- `scripts/queue_writer.py` (queue operations)
- `scripts/context_compressor.py` (context compression)
- `scripts/self_model.py`, `scripts/phi_metric.py` (self-awareness)
- `scripts/clarvis_reflection.py` (reflection)
- `scripts/task_router.py` (model routing)
- `scripts/project_agent.py` (orchestrator)
- `scripts/cleanup_policy.py` (file hygiene)
- ~70 more scripts

### Existing CLI entrypoints (packages/)
- `clarvis-db` → `clarvis_db.__main__:main` (argparse)
- `clarvis-cost` → `clarvis_cost.__main__:main` (argparse)
- `clarvis-reasoning` → `clarvis_reasoning.__main__:main` (argparse)

These stay independent — they're library packages, not part of the spine CLI.

## 4. Migration Phases

### Phase 0: Skeleton ✅ (2026-03-04)
- [x] Create `clarvis/__main__.py` + `clarvis/cli.py`
- [x] Register subcommands: `brain`, `bench`, `heartbeat`, `queue`
- [x] Brain subcommands: `health`, `stats`, `search`, `optimize`, `optimize-full`, `backfill`, `recent`, `stale`, `crosslink`
- [x] Bench subcommands: `run`, `quick`, `pi`
- [x] Heartbeat subcommands: `run`, `gate`
- [x] Queue subcommands: `next`, `archive`, `add`, `status`
- [x] `python3 -m clarvis --help` works, all subcommands visible
- [x] Each command delegates to existing scripts/ logic (thin wrappers, no duplication)
- [x] Fix `queue add`/`archive` return-type mismatch (was calling `.get()` on bool/int)
- [x] Smoke-tested: `brain health`, `brain stats`, `queue status`, `queue next` all pass

### Phase 1: Console Script + Tests ✅ (2026-03-04)
- [x] Add `[project.scripts] clarvis = "clarvis.cli:main"` to `pyproject.toml`
- [x] Run `pip install -e .` so `clarvis` binary is on PATH
- [x] Write `tests/test_cli.py` — 9 tests (5 --help + 4 real invocations) via CliRunner
- [x] Gate: all tests pass, `clarvis --help` works from any directory
- [x] Gate check updated: `scripts/gate_check.sh` now runs 6 checks (added CLI pytest + queue smoke)

### Phase 2: Cron Migration
- Add `clarvis cron run <job>` subcommand that wraps `cron_autonomous.sh` etc.
- Update 1–2 cron entries to use `python3 -m clarvis cron run autonomous` instead of `cron_autonomous.sh`
- **Soak for 7 days** — compare output/success rate with old cron entries
- Gate: 7 consecutive days with no regressions before migrating more

### Phase 3: Full Cron Cutover
- Migrate remaining cron entries
- Shell wrappers (`cron_*.sh`) still exist but are marked deprecated
- Gate: all cron jobs use `clarvis cron run <name>` for 14 days

### Phase 4: Script CLI Deprecation
- Add deprecation warning to `scripts/brain.py` `__main__` block: "Use `python3 -m clarvis brain` instead"
- Same for `scripts/performance_benchmark.py`, `scripts/queue_writer.py`, etc.
- Gate: no direct script invocation in cron, skills, or CLAUDE.md for 30 days

### Phase 5: Cleanup
- Move deprecated wrapper scripts to `scripts/deprecated/`
- Update CLAUDE.md, RUNBOOK.md, AGENTS.md to reference `clarvis` CLI
- Remove sys.path hacks from scripts that only import from clarvis/

## 5. Deprecation & Soak Strategy

| Artifact | Deprecation Signal | Soak Period | Removal Condition |
|----------|-------------------|-------------|-------------------|
| `scripts/brain.py` CLI | stderr warning | 30 days | No callers in cron/skills |
| `scripts/performance_benchmark.py` CLI | stderr warning | 30 days | Same |
| `cron_*.sh` wrappers | Comment in file | 14 days | All cron uses `clarvis cron run` |
| `sys.path.insert(0, scripts/)` | None (keep working) | indefinite | Only remove when module migrated to clarvis/ |

### Dead code audit — "exercised" definition

A script is **exercised** if ANY of the following is true:
1. Referenced by system crontab (`crontab -l | grep <script>`)
2. Imported by another non-deprecated script (`grep -r "from <module> import\|import <module>"`)
3. Referenced in an OpenClaw skill (`skills/*/SKILL.md`)
4. Referenced in CLAUDE.md, AGENTS.md, RUNBOOK.md, or HEARTBEAT.md
5. Has `if __name__ == "__main__"` AND is invoked by a cron `.sh` wrapper
6. Referenced in `openclaw.json` or `cron/jobs.json`

If none of the above: candidate for `deprecated/` (7-day soak, then delete).

## 6. Testing Gates

Each phase requires:

1. **Compile check**: `python3 -m compileall clarvis/ -q` exits 0
2. **Help check**: `python3 -m clarvis --help` prints subcommands
3. **Smoke test**: At least one real command per subgroup works:
   - `python3 -m clarvis brain stats`
   - `python3 -m clarvis bench pi`
   - `python3 -m clarvis queue status`
4. **Regression test** (Phase 1+): `pytest tests/test_cli.py`
5. **Cron soak** (Phase 2+): 7 consecutive successful runs before widening

## 7. Cron Migration Detail

Current cron invocation pattern:
```bash
# In crontab
0 1 * * * /home/agent/.openclaw/workspace/scripts/cron_autonomous.sh
```

Each `cron_*.sh` script does:
1. Source `cron_env.sh` (PATH, HOME, CLARVIS_WORKSPACE, systemd bus vars)
2. Acquire lock (`/tmp/clarvis_*.lock`)
3. Build prompt file
4. `timeout 1200 env -u CLAUDECODE ... claude -p "$(cat prompt)" ...`
5. Post-process output

The `clarvis cron run <job>` command would:
1. Import the lock acquisition logic from `cron_env.sh` equivalent (Python reimplementation)
2. Build the same prompt
3. Shell out to Claude Code with same flags
4. Post-process

**Risk**: Cron scripts do significant shell-level work (lock files, trap EXIT, timeout). Reimplementing in Python must be exact. Consider keeping the shell wrapper for Claude Code spawning and only migrating the prompt-building and post-processing.

## 8. Decisions (Inverse confirmed)

These decisions are now locked in as the canonical direction:

1. **Console script name**: Canonical binary will be **`clarvis`**. (`clv` may be added later as a convenience alias, but not required.)

2. **CLI framework**: Use **Typer** (not raw Click or argparse).

3. **Package install timing**: Proceed with **`pip install -e .`** once Phase 1 gates exist (at minimum: `tests/test_cli.py` + smoke checks). Until then, `python3 -m clarvis …` remains supported.

4. **Cron migration strategy**: **Wrap first, rewrite later.** `clarvis cron run <job>` should initially shell out to existing `scripts/cron_<job>.sh` to preserve lock/env/timeout semantics. Only after a soak period + tests do we port logic into Python.

5. **Sub-package CLIs** (`clarvis-db`, `clarvis-cost`, `clarvis-reasoning`): Keep independent for now; later optionally absorb as `clarvis db|cost|reasoning …` wrappers.

6. **`scripts/brain.py` and other wrappers**: Keep wrappers during migration + soak. Only remove after dead-code audit shows zero callers (cron/skills/docs) and bulk import migration is complete.

7. **Docs cutover timing**: Update CLAUDE.md/Runbook examples after **Phase 1** (when console script + tests are in place). Prior to that, prefer `python3 -m clarvis …`.

8. **Claude model selection**: Default to Opus behavior, but make it **configurable** (CLI flag and/or config/env).
