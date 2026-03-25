# Delivery Burndown — Clarvis Open-Source Push

_Target: 2026-03-31. Updated: 2026-03-22._

## Critical Path (must ship, in order)

| # | Task | Milestone | Status | Blocker | Validation |
|---|------|-----------|--------|---------|------------|
| 1 | **C1: Remove hardcoded secrets** | C | DONE | — | `git grep '8076973521\|REDACTED_CHAT_ID\|REDACTED_GROUP_ID\|clarvis420@gmail' -- ':!.env' ':!memory/' ':!CLAUDE.md' ':!.claude/'` returns nothing (re-verified 2026-03-25) |
| 2 | **C2: Purge ChromaDB credentials** | C | DONE | — | `python3 -c "from clarvis.brain import search; r=search('telegram bot token password'); print(r)"` returns no creds |
| 3 | **C3: Verify gitignore / tracked data** | C | DONE | — | `git ls-files data/ monitoring/` returns empty (verified 2026-03-25) |
| 4 | **C6: Root README** | C | DONE | — | `README.md` exists, covers: what/why/arch/quickstart/status/repo-boundaries |
| 5 | **D1: Website v0 scaffold** | D | TODO | — | `npm run build` succeeds, index page loads |
| 6 | **D6: Domain + deployment** | D | TODO | D1 | Site reachable at public URL |
| 7 | **E2: Secret scan pass** | E | TODO | C1+C2 | `tests/test_open_source_smoke.py` passes |
| 8 | **E3: Fresh clone setup** | E | TODO | C6 | `git clone && ./bootstrap.sh` works on clean machine |
| 9 | **E5: README matches reality** | E | TODO | C6 | Manual review post-freeze |

## Important (should ship)

| # | Task | Milestone | Status | Validation |
|---|------|-----------|--------|------------|
| 10 | **C5: Consolidate tests** | C | TODO | `pytest tests/` runs all tests from one dir |
| 11 | **C11: clarvis-db extraction plan** | C | TODO | `docs/CLARVIS_DB_EXTRACTION.md` exists |
| 12 | **D2: Public status endpoint** | D | TODO | `curl /api/status` returns JSON |
| 13 | **D3: CLR on website** | D | TODO | CLR score visible on site |
| 14 | **D4: Architecture page** | D | TODO | No internal IDs/paths in public arch page |
| 15 | **D5: Repos page** | D | TODO | Repos/boundaries listed |
| 16 | **E4: Website live** | E | TODO | Public URL returns 200 |
| 17 | **E6: Sanitize ROADMAP** | E | TODO | No chat IDs, internal details in ROADMAP.md |

## Remaining Pre-Publish Actions (not in queue but required)

- [ ] **Rotate Telegram bot token** — current token was in git history. Must rotate via @BotFather before going public.
- [ ] **`git filter-branch` or BFG** — scrub secrets from git history (bot token, chat IDs appeared in past commits). Required before any public push.
- [ ] **B8: Semantic bridges** — blocked on compute; can ship without.

## ChromaDB Scrub Procedure (for future reference)

```bash
# 1. Scrub community_summaries.json (text replacement)
python3 -c "
raw = open('data/clarvisdb/community_summaries.json').read()
raw = raw.replace('OLD_EMAIL', '<REDACTED_EMAIL>').replace('OLD_PASS', '<REDACTED>')
open('data/clarvisdb/community_summaries.json', 'w').write(raw)
"

# 2. Purge from ChromaDB collections (updates documents in-place, re-embeds)
python3 -c "
from clarvis.brain import brain
for name, col in brain.collections.items():
    result = col.get(include=['documents'])
    for i, doc in enumerate(result['documents']):
        if 'CREDENTIAL_PATTERN' in doc:
            clean = doc.replace('OLD', 'REDACTED')
            col.update(ids=[result['ids'][i]], documents=[clean])
"

# 3. Verify
python3 -c "from clarvis.brain import search; print(search('credentials password email', n=10))"
```

## Daily Targets

| Date | Tasks to Complete |
|------|-------------------|
| Mar 22 (today) | C1 (done), C2 (done), C3 |
| Mar 23 | C6 (README), C5 (tests) |
| Mar 24-25 | D1 (website scaffold), C11 |
| Mar 26 | D2+D3+D4+D5 (website content) |
| Mar 27-28 | D6 (deploy), E6 (sanitize roadmap) |
| Mar 29 | E2 (secret scan), E3 (fresh clone) |
| Mar 30-31 | E4+E5 (final validation), token rotation, history scrub |
