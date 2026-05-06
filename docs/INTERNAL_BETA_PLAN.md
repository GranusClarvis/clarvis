# BunnyBagz — Internal Closed Beta (Phase 3) Plan

**Status:** drafted 2026-05-06 · ROADMAP Phase 3 · operator-gated start
**Scope:** testnet (chain `monadTestnet`, id `10143`) — operator + invited
friends play ≥ 7 days. The bug list must close before the external audit
firm engages (`[BB_PHASE3_AUDIT_FIRM_ENGAGEMENT]`).

This doc owns three things:

1. The participant onboarding flow (how invited friends actually start
   placing bets).
2. The bug-report channel + form (so feedback lands somewhere triagable).
3. The success criteria + exit gate (so we know when Phase 3 unblocks).

The agent (Clarvis) does not start the beta. It writes daily summaries
once the operator flips it on, and reopens any `[BB_PHASE3_BETA_FIX_<TAG>]`
items from observed bugs.

---

## 1. Participant onboarding flow

### 1.1 Invite roster

Operator maintains the invite list in `memory/evolution/bb_beta_roster.md`
(git-tracked, **never** committed with real addresses on a public
remote — this repo is private). One row per participant:

```
| handle | discord/tg | wallet_address | invited_on | first_bet_on | status |
```

Statuses: `invited` → `onboarded` → `active` → `dropped`.

### 1.2 Allowlist (testnet)

Phase 3 mainnet ships behind allowlist
(`[BB_PHASE3_MAINNET_ALLOWLIST_SOFT_LAUNCH]`). Testnet does **not** require
allowlist, so onboarding is just:

1. Operator DMs participant with: site URL (testnet host), monad-testnet
   network details, the testnet faucet URL, and the bug-report channel
   link (§2).
2. Participant connects wallet → places a tiny test bet on `/play/coinflip`
   to confirm the loop works.
3. Operator marks participant `onboarded` in the roster.

### 1.3 Self-service quickstart

`docs/BETA_QUICKSTART.md` (operator can write or carry-over from an existing
README) covers the "I just got an invite, what do I do" path. This is a
6-step quickstart, not the full design doc. The bug-report channel link
sits at the bottom of every quickstart page.

### 1.4 Identity / KYC

None during testnet beta. The geo edge check is in **enforce** mode by the
time Phase 3 starts (`[BB_PHASE3_GEO_ENFORCE]` carryover from Phase 2),
but no per-participant KYC. If a participant is in a blocked region the
edge guard refuses placement; they still receive a polite explanation.

---

## 2. Bug-report channel + form

### 2.1 Channel

A private Telegram group, `bunnybagz-beta-bugs`, with the operator,
Clarvis (read-only via the existing bot), and every active participant.

The channel link lives in:

- `docs/BETA_QUICKSTART.md` (top section)
- The `/bounty` page footer (the public bounty channel is different — see
  §2.4)
- The wallet sheet "Need help?" link (operator may wire this later — not
  blocking).

### 2.2 Form

Participants drop a structured message into the channel using the
template (also pinned in the group):

```
[BUG] <one-line summary>

- when: <ISO timestamp or "just now">
- where: /play/<game> | /verify/<betId> | wallet sheet | other
- wallet: 0x… (last 4 ok)
- bet id: 0x… (if known)
- expected: <what should have happened>
- actual: <what happened>
- repro: <steps>
- severity: critical | high | medium | low
- screenshot: <attach>
```

Severity guide (matches the bug-bounty severity table at `BUG_BOUNTY.md`):

- **critical** — funds at risk, contract reverts on settle, bankroll
  drained, or invariant violation (bankroll != deposits − payouts −
  houseTake).
- **high** — settlement stuck > 5 min, indexer lag > 10 min, payout
  arithmetic wrong but recoverable.
- **medium** — UI broken on a supported breakpoint, verify page wrong but
  on-chain truth correct, mascot/animation jank.
- **low** — copy / cosmetics / non-blocking polish.

### 2.3 Triage

Daily during beta:

1. Operator (or Clarvis on operator's prompt) walks new `[BUG]` messages.
2. Each becomes a `[BB_PHASE3_BETA_FIX_<TAG>]` task in
   `memory/evolution/QUEUE.md` with severity + repro inlined.
3. Critical & high are P0; medium is P1; low is P2 unless it blocks
   onboarding.
4. The daily summary cron (§3) cross-references new bugs against the
   roster + the indexer stats.

### 2.4 Channel separation

Two surfaces, different audiences:

| surface | audience | channel | severity |
|---|---|---|---|
| Internal beta bugs | invited friends + operator | Telegram `bunnybagz-beta-bugs` | any |
| Public bug bounty | external researchers (post-audit) | `security@bunnybagz.xyz` + PGP | high+ only, $$ payouts per `BUG_BOUNTY.md` |

The bounty page (`/bounty`) is **published** but the bounty pool is
**inactive** until after audit (the page already carries a "scope
expanding" banner per `[BB_PHASE3_BUG_BOUNTY_PAGE]`).

---

## 3. Success criteria + exit gate

Phase 3 cannot exit until **7 consecutive green days** are recorded by the
daily summary cron (§4).

A "green day" requires **all** of:

| metric | green threshold | source |
|---|---|---|
| settled bets per game | ≥ 50 settled bets/game over the trailing 24h | indexer `/api/history?recent=true` aggregated by game |
| critical incidents | 0 | beta channel + invariant cron |
| high-severity incidents | 0 unresolved > 24h | beta channel triage |
| invariant violations | 0 | `[BB_PHASE3_TESTNET_7D_INVARIANT_LOG]` cron |
| reverts on settle | 0 (excluding deliberate self-test reverts) | indexer event log |
| p95 settle latency | < 30s from `BetPlaced` block to `BetSettled` block | indexer event log |
| edge realised | within ±0.5% of nominal house edge per game | indexer event log |

If any metric fails, the day is **red**. The 7-day green streak resets to
0 on any red day. This mirrors the
`[BB_PHASE3_TESTNET_7D_INVARIANT_LOG]` exit gate but extends it with the
beta-engagement ≥50-bets-per-game floor.

### 3.1 Active games

Phase 3 ships all three games (Coinflip, Dice, Hi-Lo). The ≥50-bets-per-
game threshold applies independently to each. If only Coinflip hits the
floor, the day is **yellow** — partial green: clock does not advance, but
no critical reset either.

### 3.2 Edge realised

`edge_realised = (sum_stakes − sum_payouts) / sum_stakes` over the trailing
24h, per game. Compare to the contract's nominal edge (Coinflip 1.0%,
Dice variable per multiplier, Hi-Lo variable per round). The summary cron
flags ±0.5% drift but a single noisy day inside that band does **not**
reset the streak — only sustained drift > ±1.5% counts as a red day, since
small samples can wander.

### 3.3 What does NOT block exit

- UI polish bugs (P2 / P3) accumulate in QUEUE.md but do not reset the
  streak.
- Indexer lag < 1 min is acceptable for a testnet beta.
- Reduced-motion / a11y polish discovered during beta queues for Phase 4.

---

## 4. Daily summary cron

`scripts/cron/cron_bb_beta_summary.sh` runs **09:00 CET** every day during
beta. It:

1. Polls the indexer (`BUNNYBAGZ_INDEXER_URL`, default
   `http://localhost:42069`) for the last 24h of `BetPlaced` and
   `BetSettled` events across all three games.
2. Aggregates: bets per game, settled per game, edge realised per game,
   p95 settle latency, count of revert events, count of pending bets > 5
   min old.
3. Cross-references `memory/evolution/QUEUE.md` for any new
   `[BB_PHASE3_BETA_FIX_*]` tasks added in the last 24h.
4. Writes a markdown report to `memory/cron/bb_beta_<YYYY-MM-DD>.md`.
5. Updates a rolling streak file at `memory/cron/bb_beta_streak.json` with
   `{green_days, last_green_date, last_red_reason}`.
6. Exits 0 even on red days (the cron is observational; the streak file
   carries the gate signal).

### 4.1 Activation

The cron is **always installed** (it is part of the recommended preset),
but it self-disables when:

- `BUNNYBAGZ_BETA_ACTIVE` env var is `0` or unset; OR
- The indexer URL is unreachable for > 60s.

Operator activates beta with:

```
export BUNNYBAGZ_BETA_ACTIVE=1
export BUNNYBAGZ_INDEXER_URL=https://indexer.bunnybagz.xyz   # or local
```

(Persisted in `scripts/cron/cron_env.sh` once operator gives the green
light.)

When inactive, the cron writes a single-line "beta inactive" stub to the
log and exits 0 — no spurious red days while the operator is still
inviting friends.

### 4.2 Installation

```
clarvis cron install recommended --apply
```

The `bb_beta_summary` job is part of the `recommended` and `full` presets
from this point on. Verify with `clarvis cron list | grep bb_beta`.

### 4.3 Report shape

```markdown
# BB Beta Summary — 2026-05-07

Beta active: yes  ·  indexer: https://indexer.bunnybagz.xyz
Streak: 3 green days (since 2026-05-04)

## 24h volume

| game | placed | settled | pending | reverts |
|---|---|---|---|---|
| coinflip | 73 | 71 | 2 | 0 |
| dice | 58 | 57 | 1 | 0 |
| hilo | 51 | 50 | 1 | 0 |

## Edge realised

| game | stakes (ETH) | payouts (ETH) | edge | nominal | drift |
|---|---|---|---|---|---|
| coinflip | 12.30 | 12.18 | 0.98% | 1.00% | -0.02% |
| dice | 9.00 | 8.91 | 1.00% | 1.00% | 0.00% |
| hilo | 7.10 | 7.05 | 0.70% | 0.75% | -0.05% |

## Latency

| metric | value |
|---|---|
| p50 settle | 8.2s |
| p95 settle | 21.4s |
| max settle | 47.1s |

## New beta bugs (last 24h)

- (none)

## Day verdict: GREEN

All thresholds passed. Streak: 4 green days.
```

### 4.4 Reopen path

If the day is red because of a beta bug, the report cites the
`[BB_PHASE3_BETA_FIX_<TAG>]` task already in QUEUE.md (added by triage,
§2.3). The cron itself does **not** auto-reopen tasks during the beta —
that's an operator/triage call so we don't pollute the queue with noise
from transient indexer hiccups.

---

## 5. Lifecycle

```
operator gates beta on  →  cron logs daily green/red
        ↓                      ↓
  participants play        streak hits 7
        ↓                      ↓
  bugs filed in TG         Phase 3 exit unblocked
        ↓                      ↓
  triage → QUEUE.md       audit firm engagement starts
```

When Phase 3 exits, operator:

1. Sets `BUNNYBAGZ_BETA_ACTIVE=0` in `cron_env.sh` (cron self-disables but
   stays installed for the next phase or future betas).
2. Archives `memory/cron/bb_beta_*.md` reports under
   `memory/cron/archive/bb_beta_phase3/`.
3. Files the final beta report at
   `memory/evolution/bb_phase3_beta_<YYYY-MM-DD>.md` with: total
   participants, total bets, total bugs (resolved + open), final 7-day
   streak window, exit decision.

---

## 6. Failure modes the agent should not mask

- **Indexer down**: cron writes a `INDEXER_UNREACHABLE` line and exits 0.
  This is **not** a red day (operational issue, not a product issue), but
  also **not** a green day — the streak pauses.
- **Invariant violation**: the dedicated invariant cron
  (`[BB_PHASE3_TESTNET_7D_INVARIANT_LOG]`) is the source of truth. The
  beta summary just mirrors that day's PASS/FAIL; on FAIL the day is red
  regardless of bet volume.
- **Streak file corruption**: if the JSON parse fails, the cron resets to
  `{green_days: 0}` and writes a `STREAK_FILE_RESET` warning so the
  operator notices.

---

## 7. Open items

- Operator-decision: should `BUNNYBAGZ_BETA_ACTIVE` flip on for the
  duration of Phase 3 (single switch) or per-week with a re-confirmation?
  Default plan is single switch — flip off only when Phase 3 exits.
- Operator-decision: do we publish the bug-bounty channel during the
  beta or wait for audit? Default plan: keep `/bounty` published with the
  "scope expanding" banner; route internal beta bugs to TG, public
  channel stays quiet until audit completes.
- Operator-decision: should the daily report DM the operator on red days?
  Default plan: yes (use existing `scripts/agents/spawn_claude.sh`
  Telegram path or a thin wrapper); red days are the only ones that need
  attention.
