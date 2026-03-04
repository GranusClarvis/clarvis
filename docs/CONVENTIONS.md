# Conventions

_Last updated: 2026-03-04. Living document._

---

## 1. Python Import Convention

### Scripts (`scripts/`)

All scripts use explicit `sys.path.insert` to resolve sibling imports. The canonical pattern:

```python
import sys
sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
from brain import brain, search, remember, capture
```

Scripts that have been refactored into `clarvis/` use the wrapper pattern:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from clarvis.memory.episodic import EpisodicMemory  # from spine package
```

**Rules:**
- Scripts NEVER import other scripts directly (they import from `clarvis.*` or use the `sys.path` convention).
- Lower layers (`clarvis.brain`) MUST NOT import upper layers (`clarvis.memory`, `clarvis.cognition`).
- No module-level side effects (file I/O, stdout, network). All such code goes inside `main()` or explicit functions.

### Packages (`packages/`)

Standalone pip-installable packages (`clarvis-db`, `clarvis-cost`, `clarvis-reasoning`). Each has its own `pyproject.toml`. These are **not** pip-installed on the system — scripts import them via `sys.path.insert`.

### Spine Package (`clarvis/`)

New namespace package being extracted from `scripts/`. Layer rules enforced by `import_health.py`:

```
Layer 0: clarvis.brain      → external only (chromadb, onnxruntime)
Layer 1: clarvis.memory      → brain
Layer 2: clarvis.cognition   → brain, memory
Layer 2: clarvis.context     → brain, memory, cognition
Layer 2: clarvis.metrics     → brain, memory, cognition
Layer 3: clarvis.heartbeat   → ALL lower layers
Layer 3: clarvis.orch        → ALL lower layers
```

---

## 2. CLI Pattern

Scripts use raw `sys.argv` parsing (no argparse). The standard pattern:

```python
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: script.py <command> [args]")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "health":
        ...
    elif cmd == "stats":
        ...
```

Common CLI verbs: `health`, `stats`, `record`, `update`, `report`, `status`, `pi`, `context`, `buffers`.

Example invocations:
```bash
python3 scripts/brain.py health          # Brain health report
python3 scripts/brain.py recall "query"  # Search memories
python3 scripts/brain.py store "text"    # Quick store
python3 scripts/brain.py remember "text" --importance 0.9 --collection clarvis-learnings
python3 scripts/performance_benchmark.py record   # Full benchmark
python3 scripts/performance_benchmark.py pi        # PI score only
python3 scripts/self_model.py update               # Capability assessment
python3 scripts/cognitive_workspace.py stats        # Workspace buffers
```

---

## 3. Logging

Most scripts use simple `print()` to stdout — output is captured by cron log redirection (`>> log 2>&1`).

Browser-related modules use Python `logging`:
```python
import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
```

Cron scripts redirect output to `memory/cron/<name>.log`:
```bash
exec >> "$LOG" 2>&1
```

**Convention:** Use `print()` for scripts. Use `logging` only for long-lived modules with multiple severity levels (browser, agent orchestrator).

---

## 4. Locking

### Global Claude Lock
All Claude Code spawners acquire `/tmp/clarvis_claude_global.lock` via `flock` for mutual exclusion — only one Claude Code process runs at a time.

### Maintenance Lock
Maintenance jobs (04:00–05:00 CET: graph checkpoint, compaction, vacuum) share `/tmp/clarvis_maintenance.lock`.

### Script-Level Locks
Individual scripts use PID-based lockfiles: `/tmp/clarvis_<name>.lock`. Pattern:
```bash
LOCKFILE="/tmp/clarvis_autonomous.lock"
exec 200>"$LOCKFILE"
flock -n 200 || { echo "Already running"; exit 0; }
echo $$ >&200
trap 'rm -f "$LOCKFILE"' EXIT
```

Stale lock detection: scripts check if the PID in the lockfile is still alive.

---

## 5. Environment Bootstrap

All cron scripts source `scripts/cron_env.sh` first:
```bash
source "$HOME/.openclaw/workspace/scripts/cron_env.sh"
```

This sets: `PATH`, `HOME`, `CLARVIS_WORKSPACE`, unsets `CLAUDECODE`/`CLAUDE_CODE_ENTRYPOINT` (nesting guard), exports systemd bus vars (`XDG_RUNTIME_DIR`, `DBUS_SESSION_BUS_ADDRESS`).

---

## 6. Spawning Claude Code

Required flags when spawning from any script:
```bash
env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT \
  /home/agent/.local/bin/claude -p "$(cat /tmp/task.txt)" \
  --dangerously-skip-permissions --model claude-opus-4-6
```

- Always use full path to claude binary
- Always unset nesting guard env vars
- Always use `--dangerously-skip-permissions` (or it hangs waiting for input)
- Write prompts to `/tmp` file first (avoids shell quoting issues)
- Minimum timeout: 600s, default: 1200s, large builds: 1800s

---

## 7. Data File Formats

| Format | Used For | Examples |
|--------|----------|---------|
| `.json` | State snapshots, configuration | `self_model.json`, `goal_tracker_state.json` |
| `.jsonl` | Append-only logs/history | `performance_history.jsonl`, `costs.jsonl` |
| `.md` | Human-readable reports, digests | `digest.md`, `QUEUE.md` |
| `.log` | Cron output logs | `memory/cron/*.log` |
| `.db` | SQLite databases | `clarvis.db`, `synaptic_memory.db` |
| ChromaDB | Vector store (directory) | `data/clarvisdb/` |

---

## 8. Naming Conventions

| Pattern | Category | Examples |
|---------|----------|---------|
| `cron_*.sh` | Cron job orchestrators | `cron_autonomous.sh`, `cron_morning.sh` |
| `cron_*.py` | Python cron utilities | `cron_doctor.py` |
| `clarvis_*.py` | Core Clarvis modules | `clarvis_browser.py`, `clarvis_reasoning.py` |
| `heartbeat_*.py` | Heartbeat pipeline | `heartbeat_gate.py`, `heartbeat_preflight.py` |
| `*_memory.py` | Memory subsystems | `episodic_memory.py`, `hebbian_memory.py` |

Spine package uses short names since the package path provides context: `clarvis.memory.episodic` (not `clarvis.memory.episodic_memory`).
