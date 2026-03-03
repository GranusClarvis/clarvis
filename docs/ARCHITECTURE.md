# Clarvis Architecture: Scaling the Codebase

_Written 2026-03-02. Living document — update as refactoring progresses._

---

## 1. The Problem: Uncontrolled Script Growth

Clarvis started as a collection of autonomous scripts and has grown to **82 Python files (53K+ LOC)** and **22 Bash scripts** in a flat `scripts/` directory. This worked when the codebase was small, but at the current scale it introduces compounding risks.

### 1.1 Measured Symptoms

| Metric | Value | Risk |
|--------|-------|------|
| Python files in `scripts/` | 82 | High cognitive load, no namespace boundaries |
| Total Python LOC | 53,065 | Large codebase with no formal module system |
| Largest file (`brain.py`) | 70KB / ~1,800 lines | God object — too much responsibility |
| Fan-in of `brain.py` | 58 modules import it | Single point of coupling |
| Fan-in of `attention.py` | 19 modules | Secondary coupling hub |
| Circular import cycle | 12 modules involved | Fragile import ordering |
| Max dependency depth | 13 levels | Deep chains amplify breakage |
| `heartbeat_postflight.py` fan-out | 25 local imports | Brittle orchestrator |
| `sys.path.insert` usage | All 82 files | No real package boundary |

### 1.2 Technical Risks

**Coupling & Circular Dependencies.**
There is one strongly connected component (SCC) of 12 modules:
```
brain <-> attention <-> episodic_memory <-> procedural_memory <->
memory_consolidation <-> hebbian_memory <-> retrieval_experiment <->
retrieval_quality <-> failure_amplifier <-> soar_engine <->
graphrag_communities <-> actr_activation
```
Any change to one of these 12 modules can break any of the others. Python resolves this through partial module objects and import-time side effects, making failures non-deterministic and load-order-dependent.

**God Object (`brain.py`).**
At 70KB, `brain.py` serves as data store, graph engine, search API, and collection manager simultaneously. 58 out of 82 modules import it. It pulls in 7 local dependencies itself (attention, hebbian_memory, memory_consolidation, etc.), which is why it's part of the SCC. Changes to brain.py are the highest-risk operation in the codebase.

**No Package Boundaries.**
Every Python file does `sys.path.insert(0, scripts_dir)` to import siblings. There are no `__init__.py` files, no namespace packages, no import contracts. Any file can import any other file — there is no enforcement of layering.

**Import-Time Side Effects.**
At least 2 modules (`cost_tracker.py`, `digest_writer.py`) execute significant logic on import (stdout writes, file I/O) without `if __name__ == "__main__"` guards. The dynamic `__import__()` in `brain_bridge.py` adds another import-time risk.

**Testing Surface.**
Only `clarvis-db` (a standalone package) has tests. The 82 scripts in `scripts/` have zero unit tests. The only validation is "does the cron job complete without crashing." Any refactoring is unsafe without a test harness.

**Cognitive Load.**
82 files in a flat directory with no grouping. A contributor must read file names to guess which subsystem they belong to. The naming convention (`clarvis_*.py`, `cron_*.py`, `heartbeat_*.py`) helps but does not enforce boundaries.

**Deployment & Rollback.**
The entire `scripts/` directory is deployed as a unit. There is no way to update the brain layer without also deploying the heartbeat layer, the browser layer, etc. Rollback is git-revert of the entire directory.

---

## 2. Target Architecture: Spine Package + Thin CLI Wrappers

### 2.1 Design Principles

1. **Incremental.** Every step must be backward-compatible. No big-bang rewrite.
2. **Zero new external dependencies.** Use Python stdlib only for the refactoring itself.
3. **Preserve autonomy.** Cron scripts, heartbeat pipeline, and CLI entrypoints must continue to work unchanged.
4. **Explicit dependency rules.** Lower layers MUST NOT import upper layers.
5. **Testable.** Each module must be importable without side effects and testable in isolation.

### 2.2 Proposed Package Layout

```
workspace/
├── clarvis/                      # New spine package (namespace)
│   ├── __init__.py               # Version, lazy imports
│   ├── brain/                    # Layer 0: Core data
│   │   ├── __init__.py           # Re-export: store, search, remember, capture
│   │   ├── store.py              # ChromaDB wrapper (from brain.py data ops)
│   │   ├── graph.py              # Graph edge/node operations
│   │   ├── search.py             # Search + retrieval logic
│   │   └── collections.py        # Collection definitions + schema
│   ├── memory/                   # Layer 1: Memory systems
│   │   ├── __init__.py
│   │   ├── episodic.py           # Episodic memory
│   │   ├── procedural.py         # Procedural memory
│   │   ├── working.py            # Working memory
│   │   ├── hebbian.py            # Hebbian learning
│   │   ├── synaptic.py           # Synaptic/STDP
│   │   ├── consolidation.py      # Memory consolidation
│   │   └── somatic.py            # Somatic markers
│   ├── cognition/                # Layer 2: Cognitive processes
│   │   ├── __init__.py
│   │   ├── attention.py          # GWT spotlight
│   │   ├── reasoning.py          # Reasoning chains + hooks
│   │   ├── confidence.py         # Confidence tracking
│   │   ├── workspace.py          # Cognitive workspace (Baddeley)
│   │   └── phi.py                # Phi metric (IIT)
│   ├── context/                  # Layer 2: Context management
│   │   ├── __init__.py
│   │   ├── compressor.py         # Context compression
│   │   ├── prompt_builder.py     # Prompt assembly
│   │   └── introspect.py         # Brain introspection
│   ├── heartbeat/                # Layer 3: Orchestration
│   │   ├── __init__.py
│   │   ├── gate.py               # Zero-LLM pre-check
│   │   ├── preflight.py          # Task selection + context assembly
│   │   └── postflight.py         # Episode encoding + metrics
│   ├── metrics/                  # Layer 2: Observability
│   │   ├── __init__.py
│   │   ├── performance.py        # Performance benchmark + PI
│   │   ├── self_model.py         # Capability assessment
│   │   └── health.py             # Health check utilities
│   └── orch/                     # Layer 3: Task routing + evolution
│       ├── __init__.py
│       ├── task_router.py        # Model selection
│       ├── task_selector.py      # Queue-based task picker
│       ├── evolution.py          # Evolution preflight/loop
│       └── project_agent.py      # Multi-project orchestration
│
├── scripts/                      # Thin CLI wrappers (kept for cron compat)
│   ├── brain.py                  # Thin wrapper: from clarvis.brain import *; main()
│   ├── heartbeat_preflight.py    # Thin wrapper: from clarvis.heartbeat import preflight
│   ├── heartbeat_postflight.py   # Thin wrapper: from clarvis.heartbeat import postflight
│   ├── ... (all existing CLIs preserved as thin wrappers)
│   ├── cron_autonomous.sh        # Unchanged bash scripts
│   └── spawn_claude.sh           # Unchanged bash scripts
│
├── packages/                     # Existing standalone packages (unchanged)
│   ├── clarvis-db/
│   ├── clarvis-cost/
│   └── clarvis-reasoning/
│
└── pyproject.toml                # New: makes workspace/ pip-installable
```

### 2.3 Layer Dependency Rules

```
Layer 0: clarvis.brain      → external only (chromadb, onnxruntime)
Layer 1: clarvis.memory      → brain
Layer 2: clarvis.cognition   → brain, memory
Layer 2: clarvis.context     → brain, memory, cognition
Layer 2: clarvis.metrics     → brain, memory, cognition
Layer 3: clarvis.heartbeat   → ALL lower layers
Layer 3: clarvis.orch        → ALL lower layers

FORBIDDEN:
  brain → memory, cognition, context, heartbeat, orch
  memory → cognition, context, heartbeat, orch
  cognition → heartbeat, orch
  scripts/ → scripts/ (no cross-script imports; import from clarvis.*)
```

### 2.4 Breaking the Circular Import

The current 12-module SCC exists because `brain.py` imports `hebbian_memory`, `memory_consolidation`, `attention`, etc., while those modules import `brain`. The fix:

1. **Split `brain.py`** into `clarvis.brain.store` (ChromaDB ops) + `clarvis.brain.graph` (graph ops) + `clarvis.brain.search` (retrieval).
2. **Move memory systems** into `clarvis.memory.*` — they import `clarvis.brain.store` (downward), never the reverse.
3. **brain/__init__.py** re-exports the public API (`search`, `remember`, `capture`, `brain`) using lazy imports so the familiar `from brain import brain` still works.
4. **Attention** moves to `clarvis.cognition.attention` — imports brain, not imported by brain.

The key insight: `brain.py` currently imports `hebbian_memory` and `memory_consolidation` to run Hebbian reinforcement and consolidation passes during certain operations. These should be **injected** via callback or called explicitly by the heartbeat postflight, not triggered internally by the brain store.

### 2.5 Thin Wrapper Pattern

Each existing script in `scripts/` becomes a thin CLI wrapper:

```python
#!/usr/bin/env python3
"""Brain CLI — thin wrapper over clarvis.brain."""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))
from clarvis.brain import main
if __name__ == "__main__":
    main(sys.argv[1:])
```

This preserves:
- All cron entrypoints (`python3 workspace/scripts/brain.py health`)
- All Bash script invocations (unchanged)
- The `sys.path.insert` convention (for backward compat until editable install)

---

## 3. Security & Safety Strategy

### 3.1 Pre-Refactor Backup

```bash
# 1. Create a git tag at the pre-refactor state
git tag -a v0.9-pre-refactor -m "Snapshot before codebase restructuring"

# 2. Create a safety branch
git checkout -b refactor/spine-package
git checkout main  # stay on main for now

# 3. Snapshot ChromaDB
cp -r data/clarvisdb/ data/clarvisdb_pre_refactor_backup/

# 4. Run existing backup
bash scripts/backup_daily.sh

# 5. Export brain state
python3 scripts/brain.py export-json > /tmp/brain_pre_refactor.json 2>/dev/null || true
```

### 3.2 Secret Scanning

Before any commit during refactor:
```bash
# Check for exposed secrets (run from workspace/)
grep -rn 'sk-or-v1\|sk-ant\|OPENROUTER_API_KEY\|password\s*=' clarvis/ scripts/ --include='*.py' | grep -v '.pyc'

# Verify .gitignore covers sensitive paths
cat .gitignore | grep -E 'auth|secret|env|credential|session'
```

Secrets inventory (must NOT move into `clarvis/` package):
- `~/.openclaw/agents/main/agent/auth.json` (API keys)
- `data/browser_sessions/default_session.json` (browser cookies)
- `data/budget_config.json` (Telegram bot token)
- Any `.env` files

### 3.3 Rollback Plan

Each refactoring step is a separate commit. Rollback any step:
```bash
git revert <commit-hash>   # Safe, creates new commit
# OR for full rollback:
git checkout v0.9-pre-refactor -- scripts/  # Restore entire scripts/ from tag
```

---

## 4. Implementation Plan (Incremental, Reversible)

### Phase 0: Safety Net (no behavior change)
1. **Tag + branch.** `git tag v0.9-pre-refactor && git checkout -b refactor/spine-package`
2. **Create `scripts/import_health.py`** — automated structural health check (circular imports, depth, fan-in/fan-out). Run it in CI equivalent (heartbeat postflight).
3. **Fix immediate hazards:**
   - Add `if __name__ == "__main__"` guards to `cost_tracker.py`, `digest_writer.py`
   - Standardize `sys.path.insert` to use `Path(__file__).resolve().parent`
4. **Commit.** Verify all cron jobs still run.

### Phase 1: Create Package Skeleton (no behavior change)
1. **Create `workspace/clarvis/__init__.py`** (empty, just `__version__`).
2. **Create subpackage dirs** with empty `__init__.py`: `brain/`, `memory/`, `cognition/`, `context/`, `metrics/`, `heartbeat/`, `orch/`.
3. **Create `workspace/pyproject.toml`** for editable install.
4. **Commit.** Nothing changes yet — old scripts still work.

### Phase 2: Extract `clarvis.brain` (highest value)
1. **Copy** (don't move) core functions from `brain.py` into `clarvis/brain/store.py`, `graph.py`, `search.py`.
2. **`clarvis/brain/__init__.py`** re-exports the same public API: `brain`, `search`, `remember`, `capture`.
3. **Test**: `python3 -c "from clarvis.brain import brain; print(brain.stats())"` — must match old output.
4. **Update `scripts/brain.py`** to delegate: import from `clarvis.brain`, keep CLI `main()`.
5. **Remove** Hebbian/consolidation imports from brain core (they become explicit calls from heartbeat postflight).
6. **Commit.** Run full heartbeat cycle to verify.

### Phase 3: Extract Memory Layer
1. Move `episodic_memory.py` → `clarvis/memory/episodic.py`
2. Move `procedural_memory.py` → `clarvis/memory/procedural.py`
3. Move `working_memory.py` → `clarvis/memory/working.py`
4. Move `hebbian_memory.py` → `clarvis/memory/hebbian.py`
5. Move `memory_consolidation.py` → `clarvis/memory/consolidation.py`
6. Update `scripts/` wrappers to import from `clarvis.memory.*`
7. **Commit after each file.** Verify heartbeat after each.

### Phase 4: Extract Cognition + Context
1. Move `attention.py` → `clarvis/cognition/attention.py`
2. Move `clarvis_reasoning.py` → `clarvis/cognition/reasoning.py`
3. Move `context_compressor.py` → `clarvis/context/compressor.py`
4. Update wrappers + verify.

### Phase 5: Extract Heartbeat + Orchestration
1. Move heartbeat pipeline into `clarvis/heartbeat/`
2. Move task routing into `clarvis/orch/`
3. Final verification: full autonomous cycle.

### Phase 6: Cleanup
1. Remove duplicated code from `scripts/` (keep only thin wrappers + bash scripts).
2. Run `import_health.py` to confirm zero circular imports, depth <= 5, no side effects.
3. Update CLAUDE.md, AGENTS.md with new import conventions.
4. `pip install -e .` the workspace package.
5. Tag `v1.0-spine-complete`.

---

## 5. Testing & Structural Benchmarks

### 5.1 Structural Health Script (`scripts/import_health.py`)

Zero-dependency Python script that checks:

| Check | Target | Current |
|-------|--------|---------|
| Circular import SCCs | 0 | 1 (12 modules) |
| Max dependency depth | <= 5 | 13 |
| Max fan-in (imports of any module) | <= 20 | 58 (brain.py) |
| Max fan-out (deps of any module) | <= 10 | 25 (heartbeat_postflight) |
| Modules with import side effects | 0 | 2-3 |
| `sys.path.insert` in clarvis/ | 0 | N/A (new) |
| Import time (brain) | < 300ms | 520ms |

### 5.2 Concrete Commands

```bash
# Circular import detection (stdlib only)
python3 scripts/import_health.py --check-cycles

# Import time measurement
python3 -X importtime -c "from clarvis.brain import brain" 2>&1 | head -20

# Dependency depth (from import_health.py)
python3 scripts/import_health.py --depth

# Full structural report
python3 scripts/import_health.py --report

# Optional: visual dependency graph (requires graphviz, NOT mandatory)
# pip install pydeps && pydeps clarvis/ --max-bacon=3

# Optional: strict import policy check (requires grimp, NOT mandatory)
# pip install grimp && python3 -c "import grimp; g=grimp.build_graph('clarvis'); print(g.find_illegal_dependencies(...))"
```

### 5.3 Integration with Heartbeat

Add to `heartbeat_postflight.py` (Phase 0):
```python
# Quick structural health check after every heartbeat
from import_health import quick_check
violations = quick_check()
if violations:
    queue_writer.add_p0(f"STRUCTURAL: {violations}")
```

---

## 6. Documentation Plan

### Files to Create/Update

| File | Content | When |
|------|---------|------|
| `docs/ARCHITECTURE.md` (this file) | Problem analysis, target architecture, dependency rules | Now |
| `clarvis/README.md` | Package overview, import conventions, layer rules | Phase 1 |
| `CLAUDE.md` § "Python Import Convention" | Update to show `from clarvis.brain import ...` pattern | Phase 2 |
| `AGENTS.md` § script references | Update script paths/imports | Phase 5 |
| `SELF.md` § architecture diagram | Update with layered diagram | Phase 5 |

### Conventions to Document

1. **Import rule**: Scripts in `scripts/` import from `clarvis.*`. Scripts NEVER import other scripts.
2. **Layer rule**: Lower layers never import upper layers. Inject upward dependencies via callbacks or explicit orchestrator calls.
3. **Side effect rule**: No module-level code that writes files, prints, or makes network calls. All such code goes in `main()` or explicit functions.
4. **Naming**: Package modules use short names (`episodic.py` not `episodic_memory.py`) since the package path provides context (`clarvis.memory.episodic`).

---

## 7. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Cron jobs break during refactor | Medium | High | Phase-by-phase, commit per file, verify after each |
| Import paths change for spawned Claude Code | Medium | Medium | Thin wrappers preserve `scripts/` entrypoints |
| ChromaDB corruption during refactor | Low | Critical | Pre-refactor backup + tag |
| Performance regression (import time) | Low | Low | Benchmark before/after each phase |
| Partial refactor stalls (50% old, 50% new) | Medium | Medium | Each phase is self-contained and functional |

---

## Appendix A: Current Import Graph Statistics

```
Total Python files:        82
Circular import SCC:       12 modules (1 cycle)
Max dependency depth:      13 (evolution_preflight, heartbeat_postflight)
Max fan-in:                58 (brain.py)
Max fan-out:               25 (heartbeat_postflight.py)
Leaf modules (no imports): 15
brain.py import time:      520ms
```

## Appendix B: The 12-Module Circular Import

```
brain → attention → (brain)
brain → hebbian_memory → (brain)
brain → memory_consolidation → episodic_memory → (brain)
brain → retrieval_quality → retrieval_experiment → (brain)
brain → graphrag_communities → (brain)
brain → actr_activation → attention → (brain)
episodic_memory → soar_engine → procedural_memory → failure_amplifier → (brain)
```

Root cause: `brain.py` imports 7 modules for optional features (Hebbian reinforcement, consolidation, ACT-R activation, GraphRAG). Those modules need brain for data access. Solution: dependency inversion — brain provides data API only, features are called by orchestrators.
