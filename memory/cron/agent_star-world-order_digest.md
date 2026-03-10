# Project Agent Digest: star-world-order
_Promoted 2026-03-08 19:30_

[+] t0307205741-64ac: No-op concurrency smoke test completed. Repo is clean on branch clarvis/star-world-order/t0307205741-64ac with no pending changes.

[+] t0307212611-c8a8: Fixed critical governance voting power spoofing vulnerability. The vote endpoint previously accepted client-supplied votingPower without verification, allowing any voter to claim arbitrary voting power. Now verifies actual Star Skrumpey NFT ownership on-chain via checkStarOwnershipBatched(). Also added Star holder gate for proposal creation.
  PR: https://github.com/InverseAltruism/Star-World-Order/pull/177
  -> TODO: Add wallet auth to /api/chat POST (message spoofing vulnerability)
  -> TODO: Add wallet auth to /api/messages POST (DM spoofing vulnerability)
  -> TODO: Add auth to /api/presence and /api/voice endpoints
  -> TODO: Fix TOCTOU race condition in claimQuestReward (lib/db.ts) - wrap in transaction
  -> TODO: Fix non-atomic addUserXP - use SQL increment instead of read-modify-write
  -> TODO: Server-side verify engagementBonus/discordBonus in raffle entry
  -> TODO: Add content length limits to forum thread/reply creation
  -> NEEDS: Comprehensive API route test coverage (currently 0%)

## Learned Procedures
- Build: npm run build
- Test: npm run test
- Type check: npm run type-check
- Lint: npm run lint