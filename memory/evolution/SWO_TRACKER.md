# Star World Order — Project Tracker

_Dedicated tracker for SWO/Sanctuary project work. Separated from main QUEUE.md per PROJECT_LANES.md governance._
_Project lane: SWO | Status: ACTIVE | Operator-directed._

## Delivery Criteria

Each item must produce a **PR or working feature branch** in the SWO repo.
Planning docs, queue items, and brand positioning do NOT count as delivery.

## Current Sprint — Foundation PRs

| # | Task | Branch | PR | Status |
|---|------|--------|----|--------|
| 1 | [SANCTUARY_ACTIVE_COMPANION_API] Active companion endpoints | feat/sanctuary-companion-panel | #178 | Done |
| 2 | [SANCTUARY_BOOTSTRAP_STATE] First-time bootstrap path | feat/sanctuary-companion-panel | #178 | Done |
| 3 | [SANCTUARY_TEST_FIXTURES] Test fixtures/seeds | feat/sanctuary-companion-panel | #178 | Done |
| 4 | [SANCTUARY_SUBSITE_SHELL] `/sanctuary` route shell | ec216e3 (dev) | — | Done |
| 5 | [SANCTUARY_COMPANION_PANEL] V1 companion dashboard | feat/sanctuary-companion-panel | #178 | Done |

## Completed PRs

| # | PR | Title | Date |
|---|-----|-------|------|
| 1 | #175 | ci: add test workflow | 2026-03-02 |
| 2 | #178 | feat: V1 companion dashboard with quick actions | 2026-04-16 |
| 3 | #182 | fix: replace 14 `any` types with narrow sanctuary row types | 2026-04-17 |

## Pending PRs

| # | PR | Title | State | Last Checked |
|---|-----|-------|-------|--------------|
| 1 | #177 | fix: verify governance voting power server-side | OPEN, MERGEABLE, CLEAN (no reviews) | 2026-04-18 — revalidated against e22cd21, vuln persists, 0 conflicts, verdict REVIVE |
| 2 | #179 | fix(api): verify wallet signature on chat/messages/presence writes (P0) | OPEN | 2026-04-16 — closes SWO_FIX_CHAT_AUTH/DM/PRESENCE; follow-up commits 037066c/952e3fd/43ce164 also close SWO_FIX_VOICE_AUTH, SWO_FIX_RAFFLE_BONUSES, SWO_HARDEN_CRON_AUTH |
| 3 | #180 | fix(adminAuth): persist used nonces in SQLite to prevent replay (P1) | OPEN | 2026-04-16 — closes SWO_ADMIN_NONCE_PERSIST; SQLite-backed nonce table + 8 vitest cases |
| 4 | #181 | chore(contracts): archive StarForge V1-V4 + Testing_casino, add DEPLOYED.md (P2) | OPEN | 2026-04-16 — closes SWO_CONTRACT_ARCHIVE |

## Delivered Artifacts (non-PR)

| Date | Commit | Description |
|------|--------|-------------|
| 2026-04-16 | audit  | Security threat-surface audit: `memory/audits/swo_security_threat_surface_2026-04-16.md` (16 findings, 6 P0, 5-PR plan) |
| 2026-04-10 | 378d7a1 | Website redesign — gold palette, Press Start 2P font |
| 2026-04-05 | a5479fd | SWO ecosystem positioning doc |
| 2026-04-03 | 09b0598 | SWO brand integration doc + LLM prompt evaluator |

## Notes

- Fork workflow: GranusClarvis has pull-only on InverseAltruism repo. Push to fork, PR targets upstream.
- Agent root: `/opt/clarvis-agents/star-world-order/` or `/home/agent/agents/star-world-order/`
- SWO repo: `GranusClarvis/Star-World-Order` (fork of `InverseAltruism/Star-World-Order`)
