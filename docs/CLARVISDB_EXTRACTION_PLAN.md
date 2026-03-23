# clarvis-db Extraction Plan

_Status: v1.0 — 2026-03-23. Plan for extracting `clarvis-db` into a standalone public repo._
_Prerequisite: EXTRACTION_GATES.md gates must pass before executing this plan._

---

## 1) Target Repository

- **Repo**: `GranusClarvis/clarvis-db` (public)
- **Package name**: `clarvis-db` (PyPI)
- **Import**: `from clarvis_db import VectorStore, HebbianEngine, SynapticEngine`
- **License**: MIT
- **Python**: >= 3.10

---

## 2) Scrubbed Public-Facing Structure

```
clarvis-db/
├── LICENSE                     # MIT license
├── README.md                   # Existing README (already public-ready)
├── pyproject.toml              # Existing (already clean)
├── .gitignore                  # Existing
├── CHANGELOG.md                # Generated from git history at extraction time
├── .github/
│   └── workflows/
│       ├── ci.yml              # Test + lint on PR/push
│       └── publish.yml         # PyPI publish on tag
├── clarvis_db/
│   ├── __init__.py             # VectorStore, HebbianEngine, SynapticEngine
│   ├── __main__.py             # CLI entrypoint
│   ├── store.py                # VectorStore (core)
│   ├── hebbian.py              # HebbianEngine (standalone)
│   └── stdp.py                 # SynapticEngine (standalone)
└── tests/
    └── test_clarvisdb.py       # Existing test suite (22 tests)
```

### Files to REMOVE before extraction

| File | Reason |
|------|--------|
| `clarvis_db/clarvis_adapter.py` | Clarvis-specific: hardcodes 10 collection names, imports from `scripts/retrieval_quality`, references `/home/agent/.openclaw/` |
| `DEPRECATED.md` | Internal-only deprecation notice (not relevant to standalone users) |
| `.git/` | Fresh git init for the extracted repo |
| `*.egg-info/`, `__pycache__/`, `.pytest_cache/` | Build artifacts |

### Files to AUDIT before extraction

| File | Check |
|------|-------|
| `store.py` | No hardcoded paths (currently clean — uses constructor arg `data_dir`) |
| `hebbian.py` | No Clarvis-specific imports (currently clean — pure stdlib + typing) |
| `stdp.py` | No Clarvis-specific imports (currently clean — pure stdlib) |
| `__main__.py` | No Clarvis-specific defaults (currently uses `./data/clarvisdb` — change to `./data`) |
| `README.md` | Remove any "coming soon" claims (MCP server, REST adapter — currently none in README) |
| `pyproject.toml` | Verify `project.urls` (add homepage, repo, issues URLs) |

---

## 3) Required Changes Before Extraction

### 3.1 pyproject.toml additions

```toml
[project.urls]
Homepage = "https://github.com/GranusClarvis/clarvis-db"
Repository = "https://github.com/GranusClarvis/clarvis-db"
Issues = "https://github.com/GranusClarvis/clarvis-db/issues"

[project]
# Add these fields:
authors = [{name = "GranusClarvis"}]
classifiers = [
    "Development Status :: 4 - Beta",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
]
```

### 3.2 Default data_dir in __main__.py

Change default from `./data/clarvisdb` to `./data` (remove Clarvis naming).

### 3.3 LICENSE file

MIT license file must be present (currently missing from package directory).

### 3.4 Type hint audit

All public surface functions already have type hints. Verified:
- `VectorStore.__init__`, `store`, `recall`, `get`, `delete`, `add_relationship`, `get_related`, `associative_recall`, `evolve`, `stats` — all typed
- `HebbianEngine.__init__`, `on_recall`, `reinforce`, `compute_decay`, `get_associations`, `evolve`, `get_access_patterns`, `coactivation_stats` — all typed
- `SynapticEngine.__init__`, `potentiate`, `depress`, `record_activation`, `spread`, `on_recall`, `consolidate`, `get_synapse`, `get_strongest`, `get_hubs`, `stats` — all typed

---

## 4) CI Requirements

### 4.1 ci.yml — Test + Lint

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[all]"
      - run: pip install pytest
      - run: pytest tests/ -v
      - run: python -m clarvis_db test  # CLI self-test

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install ruff
      - run: ruff check clarvis_db/
```

### 4.2 publish.yml — PyPI Release

```yaml
name: Publish

on:
  push:
    tags: ["v*"]

jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install build
      - run: python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
```

### 4.3 Test matrix notes

- **ChromaDB + ONNX tests**: All 22 existing tests require ChromaDB + ONNX. The `[all]` extra installs both.
- **Fallback mode test**: Add 1 test that verifies VectorStore works without ChromaDB (keyword fallback via graph nodes). Currently untested.
- **No external network**: All tests use `tempfile.TemporaryDirectory()` — fully offline, no fixtures needed.

---

## 5) Dependency Analysis

### Runtime dependencies

| Dependency | Required | Size | Notes |
|------------|----------|------|-------|
| Python stdlib | Yes | 0 | `json`, `math`, `sqlite3`, `datetime`, `pathlib` |
| chromadb | Optional (`[chroma]`) | ~150MB | Vector storage backend |
| onnxruntime | Optional (`[onnx]`) | ~50MB | Local MiniLM embeddings |

### No transitive Clarvis dependencies

The package has **zero imports** from the Clarvis ecosystem:
- `store.py` imports only `clarvis_db.hebbian` and `clarvis_db.stdp`
- `hebbian.py` imports only stdlib
- `stdp.py` imports only stdlib
- The only Clarvis-coupled file is `clarvis_adapter.py` (to be removed)

---

## 6) Extraction Checklist

Execute these steps in order when Gate 1 passes (second consumer exists):

- [ ] **1. Fork internal package**: Copy `packages/clarvis-db/` to a staging directory
- [ ] **2. Delete `clarvis_adapter.py`**: Remove Clarvis-specific adapter
- [ ] **3. Delete `DEPRECATED.md`**: Not relevant to public users
- [ ] **4. Add LICENSE**: MIT license file
- [ ] **5. Update pyproject.toml**: Add URLs, authors, classifiers
- [ ] **6. Update __main__.py**: Change default data_dir to `./data`
- [ ] **7. Audit README.md**: Verify no aspirational claims, no internal references
- [ ] **8. Add CI workflows**: `.github/workflows/ci.yml` and `publish.yml`
- [ ] **9. Create CHANGELOG.md**: From git history
- [ ] **10. Fresh venv test**: `python -m venv /tmp/test-env && pip install . && pytest tests/ -v`
- [ ] **11. Create repo**: `GranusClarvis/clarvis-db` on GitHub
- [ ] **12. Push + verify CI**: Green CI on first push
- [ ] **13. Tag v1.0.0**: Create release
- [ ] **14. PyPI publish**: Verify `pip install clarvis-db` works
- [ ] **15. Update monorepo**: Point `packages/clarvis-db/` to the extracted repo (git submodule or dependency)
- [ ] **16. Monorepo boundary doc update**: Update `CLARVISDB_API_BOUNDARY.md` to reference external package

---

## 7) Post-Extraction Maintenance

- **Versioning**: Semver. Breaking changes = major bump.
- **Release cadence**: As needed, not scheduled.
- **Monorepo sync**: After extraction, monorepo imports via `pip install clarvis-db` (not submodule).
- **Boundary doc**: `CLARVISDB_API_BOUNDARY.md` remains in monorepo as the integration contract.
- **Test coverage**: Maintain existing 22-test suite. Add fallback-mode test before or during extraction.

---

## 8) What NOT to Extract

These live in the Clarvis monorepo, not in `clarvis-db`:

- `clarvis.brain` spine module (Clarvis-specific orchestration wrapper around ClarvisDB concepts)
- Retrieval evaluation/feedback/trace (`clarvis.brain.retrieval_*`)
- Graph compaction/cutover scripts (`scripts/graph_*.py`)
- Episodic/procedural/working memory scripts (Clarvis cognitive architecture)
- Collection definitions (the 10 Clarvis collections are a host concern, not a library concern)

---

## 9) Current Gate Status (2026-03-23)

```
EXTRACTION READINESS

clarvis-db:
  [FAIL] Gate 1: Consumer Demand    — 1/2 consumers (need 2+, no external user)
  [PASS] Gate 2: API Stability      — boundary doc exists, v1.0.0, type hints complete
  [PASS] Gate 3: Test Coverage      — 22 tests, all pass, covers store/recall/evolve/graph/STDP/Hebbian
  [PASS] Gate 4: Documentation      — README clean, no aspirational claims
  [PASS] Gate 5: Low Bloat          — 5 source files, 3 optional deps, zero Clarvis imports

  VERDICT: NOT READY — blocked on Gate 1 (no second consumer)
  ACTION: Plan is complete and ready. Execute when a second consumer appears.
```
