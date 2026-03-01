# Project Agent Digest: star-world-order
_Promoted 2026-03-01 13:37_

[+] t0301133649-82a5: Explored the Star World Order codebase by reading README.md and package.json. SWO is a Next.js 16 / React 19 / TypeScript dApp on Monad blockchain serving as an exclusive Sub-DAO for 333 Star Skrumpey NFT holders, featuring governance, OTC marketplace, staking, social hangout, and raffle systems. Testing is available via Vitest (unit) and Playwright (e2e).
  -> Run npm run test to verify unit test suite passes
  -> Run npm run build to verify production build succeeds
  -> Explore lib/db.ts for database operations (3500+ lines, central to the app)
  -> Review smart contracts in contracts/ directory for deployment readiness

## Learned Procedures
- Build: npm run build
- Dev server: npm run dev (port 3000)
- Type check: npm run type-check
- Lint: npm run lint
- Unit tests: npm run test (vitest)
- E2E tests: Playwright available in devDependencies
- Network test: npm run test:network
- DB init: npm run db:init
- Compile contracts: npm run compile
- All PRs target dev branch, not main