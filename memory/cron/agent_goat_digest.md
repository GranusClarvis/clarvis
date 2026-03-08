# Project Agent Digest: goat
_Promoted 2026-03-06 20:04_

[+] t0305000722-0192: Synced repo, created REPO_MAP.md with full entrypoint/module/API/test reference, data/golden_qa.json with 25 Q/A pairs, and dev/ wrapper scripts (up.sh, down.sh, status.sh). Committed locally, no push.
  -> TODO: Add data/golden_qa.json to .gitignore exceptions if it should be tracked long-term
  -> TODO: Consider adding dev/test.sh once unit test framework is chosen

## Learned Procedures
- Dev server: dev/up.sh or cd admin-suite && npm run dev
- Build: cd admin-suite && npm run build
- Lint: cd admin-suite && npm run lint
- Typecheck: cd admin-suite && npm run typecheck
- Status: dev/status.sh