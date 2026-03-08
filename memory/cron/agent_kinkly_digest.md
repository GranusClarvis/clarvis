# Project Agent Digest: kinkly
_Promoted 2026-03-06 20:05_

[+] t0305000728-74dc: Synced repo, built REPO_MAP.md with full architecture documentation, created data/golden_qa.json with 25 Q/A pairs covering all major subsystems, and created dev/ scripts (up.sh, down.sh, status.sh) wrapping the existing start/stop lifecycle.
  -> TODO: Add dev/ and data/ to .gitignore if these should stay local-only
  -> TODO: Validate golden_qa.json against actual API responses once DB is seeded

[+] t0305002611-9f6e: Created TRAINING_CHECK.txt with current branch name and git status summary. File is local-only, not committed or pushed.

## Learned Procedures
- Dev start: dev/up.sh
- Dev stop: dev/down.sh
- Dev status: dev/status.sh
- Frontend test: npm run test
- Backend test: cd server && npm test
- Lint: npm run lint
- Migrate: cd server && npm run migrate