# Contributing to Clarvis

Thank you for your interest in contributing to Clarvis! This guide covers setup, coding standards, testing, and pull request expectations.

## Prerequisites

- Python >= 3.10
- ChromaDB >= 0.4.0 and ONNX Runtime >= 1.15.0 (for brain features)
- Git

## Setup

```bash
# Clone the repo
git clone https://github.com/GranusClarvis/clarvis.git
cd clarvis

# Guided installer (recommended — installs dev extras + runs verification)
bash scripts/install.sh --profile standalone --dev

# Or manual install
pip install -e packages/clarvis-cost
pip install -e packages/clarvis-reasoning
pip install -e packages/clarvis-db
pip install -e ".[all]"
bash scripts/verify_install.sh
```

See [docs/INSTALL.md](docs/INSTALL.md) for the full walkthrough and profile options.

## Docker Quickstart (alternative)

```bash
bash scripts/install.sh --profile docker
# Or manually:
docker compose build
docker compose run clarvis pytest -m "not slow"    # Run tests
docker compose run clarvis                         # Interactive shell
```

Brain data persists in a Docker volume between runs. This is for development/exploration only — production runs systemd-native.

## Repository Layout

| Path | What |
|------|------|
| `clarvis/` | Spine package — brain, heartbeat, cognition, metrics, CLI |
| `packages/` | Extracted packages: `clarvis-db`, `clarvis-cost`, `clarvis-reasoning` |
| `scripts/` | 130+ operational scripts (cron, maintenance, cognitive architecture) |
| `tests/` | Open-source smoke tests |
| `data/` | Runtime data (ChromaDB, episodes, costs) — not committed |

## Coding Standards

### Style

- **Linter**: [Ruff](https://docs.astral.sh/ruff/) — runs in CI
- **Line length**: 120 characters
- **Target**: Python 3.10+
- **Rules enforced**: `E9`, `F63`, `F7`, `F82` (critical errors). More rules will be added over time.

Run the linter locally before pushing:

```bash
ruff check clarvis/ packages/ tests/
```

### Imports

Prefer the spine module for new code:

```python
from clarvis.brain import brain, search, remember, capture
```

Legacy `scripts/` imports (`from brain import ...`) still work but should not be used in new contributions.

### General Guidelines

- Keep functions under 80 lines where practical.
- Avoid adding dependencies without discussion — this runs on a constrained NUC.
- No hardcoded secrets or credentials in committed files.
- Prefer editing existing files over creating new ones.

## Testing

### Running Tests

```bash
# All tests
python3 -m pytest

# Specific suites
python3 -m pytest packages/clarvis-db/tests/ -v    # clarvis-db
python3 -m pytest clarvis/tests/ -v                 # spine tests
python3 -m pytest tests/test_open_source_smoke.py -v # smoke tests

# Skip slow tests (ChromaDB-dependent)
python3 -m pytest -m "not slow"
```

### Writing Tests

- Place spine tests in `clarvis/tests/`.
- Place package tests in `packages/<pkg>/tests/`.
- Place integration/smoke tests in `tests/`.
- Mark ChromaDB-dependent tests with `@pytest.mark.slow`.
- Tests must pass in CI (GitHub Actions) before merge.

## Pull Requests

### Before Submitting

1. Run `ruff check clarvis/ packages/ tests/` — no errors.
2. Run `python3 -m pytest` — all tests pass.
3. Verify your change doesn't break `python3 -c "from clarvis.brain import brain"`.

### PR Expectations

- **Branch from `main`**, target `main`.
- **Keep PRs focused** — one logical change per PR.
- **Write a clear title** (under 70 chars) and description explaining *why*, not just *what*.
- **Include test coverage** for new functionality where feasible.
- **No secrets, credentials, or personal data** in committed files.
- CI must pass (lint + tests) before review.

### What Gets Reviewed

- Correctness and clarity of the change.
- Impact on existing brain/memory operations (regressions).
- Token and resource efficiency (this system runs 24/7 on limited hardware).
- Whether the change fits the project direction (see `ROADMAP.md`).

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
