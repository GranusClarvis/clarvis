# Project Agent Digest: clarvis-db
_Promoted 2026-03-08 19:30_

[+] t0308121212-8ae1: Added a Development section to README.md documenting install, test, lint, typecheck, and build commands. All commands were validated against the repo before documenting. 25/25 tests pass.
  PR: https://github.com/GranusClarvis/clarvis-db/pull/1

## Learned Procedures
- Test: python3 tests/test_clarvisdb.py
- Lint: ruff check clarvis_db/
- Typecheck: mypy clarvis_db/ --ignore-missing-imports
- Build: python3 -m build