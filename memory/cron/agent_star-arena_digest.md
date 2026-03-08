# Project Agent Digest: star-arena
_Promoted 2026-03-06 20:05_

[+] t0305000711-ba88: Synced repo (fetch/prune), built REPO_MAP.md with entrypoints/modules/test commands, created data/golden_qa.json with 25 Q/A pairs covering architecture/security/trading, and added dev/ scripts (up.sh, down.sh, status.sh) wrapping the existing dev workflow. No PR or push per instructions.
  -> TODO: 1 pre-existing test failure in test_tournament_payment_flow.py
  -> TODO: 1 pre-existing error in test_tournament_api.py
  -> NEEDS: .gitignore excludes data/ — golden_qa.json was force-added

## Learned Procedures
- Test: source venv/bin/activate && pytest tests/ -q
- Dev up: ./dev/up.sh [--dashboard] [--arena]
- Dev down: ./dev/down.sh
- Dev status: ./dev/status.sh