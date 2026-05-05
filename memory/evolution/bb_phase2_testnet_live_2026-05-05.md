# BunnyBagz Phase 2 — testnet live (2026-05-05)

Closure of `[BB_PHASE2_TESTNET_DEPLOY_DICE_HILO_LIVE]`. The full Phase 2 stack
(Bankroll + Coinflip + Dice + HiLo) is deployed on **MegaETH testnet (chain
6343)** via the existing `script/Deploy.s.sol` CREATE3 deploy. All four
contracts have non-zero code, all three games are registered on the bankroll
with non-zero allowance, and the wagmi address book in
`packages/chain/src/addresses.generated.ts` already wires `apps/web` to the
live addresses.

## On-chain state (verified `cast call` against `https://carrot.megaeth.com/rpc`)

| contract | address | code (bytes) | bankroll.isGame | bankroll.allowanceOf (wei) |
|---|---|---:|---|---:|
| BunnyBagzBankroll | `0x33C5B6a95e71611F5dC821A74DDAD0F746fF2dFf` | 2839 | — | — |
| BunnyBagzCoinflip | `0x064b8bfc03b23D2b525deD9d3969090347A21983` | 5416 | true | 1_000_000_000_000_000 (1e15) |
| BunnyBagzDice     | `0xAC023542A8168465EE4A1b3e8Ae0f58F36A6d84B` | 5480 | true | 1_000_000_000_000_000 (1e15) |
| BunnyBagzHiLo     | `0xd9B9b6c37ad4f3D5b07ae76dE261c5C865600d6e` | 7153 | true | 1_000_000_000_000_000 (1e15) |

- Bankroll ETH balance: **2_000_000_000_000_000 wei (2e15 / 0.002 ETH)** — matches `BB_INITIAL_DEPOSIT` from the deploy script.
- Bankroll owner: `0xb29e6735629539cEd64F0d6f0c476Fe92539fD7B` (deployer wallet).
- Each game's `bankroll()` pointer resolves to `0x33C5B6a95e71611F5dC821A74DDAD0F746fF2dFf` ✓.
- Dice + HiLo `minBet=1e15`, `maxBet=2e15` — matches deploy params; HiLo `owner()` = deployer.
- CREATE3 prediction matches actuals — same `(deployer, salt)` pair will produce these exact addresses on mainnet when Phase 3 ships.

## Deploy transactions (broadcast snapshot from `broadcast/Deploy.s.sol/6343/run-latest.json`)

| step | tx hash | block | nonce |
|---|---|---:|---:|
| CREATE3 → Bankroll (salt `0xBB01`) | `0x7318982c2126ab697eb58359c56def1878c754cc7460e3a1cc643f561b243676` | 18211111 | 11 |
| CREATE3 → Coinflip (salt `0xBBC1`) | `0x074a8eb80f95825248ecfa967766753ae894d544099e3c41f9626ea8ed385866` | — | 12 |
| CREATE3 → Dice (salt `0xBBD1`)     | `0xe30c1cfa0805b9c2ffd8e7193773e36d30617fa5a188154a9943b1e28ff141aa` | — | 13 |
| CREATE3 → HiLo (salt `0xBBA1`)     | `0x51c926ff1417d4e188e81052cddd64e70c4cc14b5e4aad3e93dd06ad601355eb` | — | 14 |
| `registerGame(coinflip, 1e15)`     | `0x952a50b582be7b50823dee4ccc0425c03e20f17bb06e3385e295f033eeede600` | 18211115 | 15 |
| `registerGame(dice, 1e15)`         | `0x5d900eb3ae2cba56db461676f81d2e2157921ef98fa3d03329cea23aad929137` | — | 16 |
| `registerGame(hilo, 1e15)`         | `0xf607e06e2020cafc6bf331715c1ed82e401871b9ae2a2d749598966a09c535d8` | — | 17 |
| `deposit{value: 2e15}()`           | `0xe08409fb89afdc84c0c489791c0941968c2c3655590295b21af29740cfc54691` | 18211118 | 18 |

`from = 0xb29e6735629539cEd64F0d6f0c476Fe92539fD7B`, `chainId = 6343`,
`effectiveGasPrice ≈ 1 gwei` (testnet floor 0.001 gwei × 1e6).

## Explorer links (MegaETH Blockscout v2 — `https://megaeth-testnet-v2.blockscout.com`)

- Bankroll  → https://megaeth-testnet-v2.blockscout.com/address/0x33C5B6a95e71611F5dC821A74DDAD0F746fF2dFf
- Coinflip  → https://megaeth-testnet-v2.blockscout.com/address/0x064b8bfc03b23D2b525deD9d3969090347A21983
- Dice      → https://megaeth-testnet-v2.blockscout.com/address/0xAC023542A8168465EE4A1b3e8Ae0f58F36A6d84B
- HiLo      → https://megaeth-testnet-v2.blockscout.com/address/0xd9B9b6c37ad4f3D5b07ae76dE261c5C865600d6e
- Deploy tx → https://megaeth-testnet-v2.blockscout.com/tx/0x7318982c2126ab697eb58359c56def1878c754cc7460e3a1cc643f561b243676

## apps/web wiring (lobby goes `live` for all three)

`packages/chain/src/addresses.generated.ts` already exports the four addresses
under `ADDRESSES_GENERATED[6343]`. The lobby card resolver at
`apps/web/src/app/play/page.tsx:74` flips `status: addr[g.addressKey] ?
"live" : "phase2"` — with Coinflip, Dice and HiLo all addressed, the three
cards render as `live` against testnet and the lobby gets the `allLive` copy
("All three game surfaces are live on testnet …", `play/page.tsx:88`).

## Acceptance walk

| criterion | status | evidence |
|---|---|---|
| (a) operator funds deployer | ✅ | `eth_getBalance(0xb29e…fD7B)` = 996_626_807_760_845_750 wei (≈ 0.997 ETH) |
| (b) `deploy-testnet.sh` ran | ✅ | broadcast at block 18211111 (nonces 11–18); script is idempotent — re-running today shows "already deployed at" for every contract |
| (c) `cast call` non-zero code at Dice + HiLo | ✅ | Dice 5480 bytes, HiLo 7153 bytes (table above) |
| (d) `bankroll.allowanceOf(dice/hilo)` non-zero | ✅ | both `1_000_000_000_000_000` wei |
| (e) `apps/web` lobby cards `live` against testnet RPC | ✅ (wiring) | `addresses.generated.ts` populated → `play/page.tsx:74` resolves all three to `live`. **Live in-browser bet round-trip is left as a follow-up `[BB_PHASE2_TESTNET_BET_SMOKE]`** because the host has no GUI to render `next dev` and the funded deployer wallet is the only key on this box (`useAccount` mock only flips on in `NEXT_PUBLIC_E2E_MOCK_WALLET=1` testing) — operator can drive the smoke from a desktop wallet. |
| (f) write `bb_phase2_testnet_live_<DATE>.md` | ✅ | this file |

## Follow-ups filed

- `[BB_PHASE2_TESTNET_BET_SMOKE]` (P1, autonomous-doable for operator-driven verification): operator connects MetaMask to chain 6343, places one ETH bet on each of `/play/coinflip`, `/play/dice`, `/play/hilo`, captures explorer links to settled `BetSettled` (or game-specific) events, and appends them to this doc as a "smoke" appendix. Once that lands, Phase 2 ROADMAP exit gate (e) is fully closed end-to-end.

---

## Appendix — Smoke runbook (operator) — scaffolded 2026-05-05

> Status: **NOT YET RUN.** Agent host has no GUI, so the operator drives this from a desktop with MetaMask. Estimated wall time once started: ~10 minutes (≤2 minutes per game once the wallet is on-network, plus 4 minutes of one-time setup).
>
> When you finish each step, paste the tx hashes inline (slots marked `<TX_*>`) and either commit this file directly or report them to the agent which will commit + close `[BB_PHASE2_TESTNET_BET_SMOKE]` in the queue.

### A. One-time MetaMask setup

Add the MegaETH testnet network if you haven't already:

| Field | Value |
|---|---|
| Network name | `MegaETH Testnet` |
| RPC URL | `https://carrot.megaeth.com/rpc` |
| Chain ID | `6343` |
| Currency symbol | `ETH` |
| Block explorer URL | `https://megaeth-testnet-v2.blockscout.com` |

Faucet (gates the API with Cloudflare Turnstile, browser-only): https://testnet.megaeth.com/

Smoke needs ≈ `0.005 ETH` per wallet (3 × 1e15 stakes + ~30k gas/tx × 1 gwei ≈ negligible). The deployer wallet `0xb29e6735629539cEd64F0d6f0c476Fe92539fD7B` already has ≈ 0.997 ETH but is the **owner** key — prefer betting from a **fresh** wallet so the smoke exercises the player path, not the owner path. Drip the fresh wallet from the faucet first.

### B. Bring up the web app locally

```bash
cd ~/agents/mega-house/workspace   # or your local checkout
pnpm install                       # if not already
pnpm --filter @bunnybagz/web dev   # serves on http://localhost:3000
```

The address book at `packages/chain/src/addresses.generated.ts` is already populated for chain 6343, so `/play/coinflip`, `/play/dice`, `/play/hilo` will all render `live` once the wallet is connected.

> If `pnpm --filter @bunnybagz/web dev` is awkward (e.g. running on the agent host without forwarding), the alternative is to deploy a Vercel preview from this branch and have the operator browse to that. Either path works for the smoke — the contracts are the same.

### C. Per-game smoke checklist

For each game: navigate to the page, type the minimum stake (`0.001 ETH` = `1e15` wei), submit the bet, wait for the seed-manager to settle (single block, ~10 ms), confirm the UI flips to `Won` / `Lost` / `Cashed out` / `Pushed`, then paste the on-chain tx hashes.

Block explorer base URL: `https://megaeth-testnet-v2.blockscout.com`

#### C.1 — `/play/coinflip` (Coinflip)

- Contract: `0x064b8bfc03b23D2b525deD9d3969090347A21983`
- Min bet: `1e15` wei (0.001 ETH); pick Heads or Tails
- Expected events: `BetPlaced` (when you submit), `BetSettled` (when keeper reveals)

| step | action | tx hash slot | explorer link |
|---|---|---|---|
| 1 | placeBet | `<TX_COINFLIP_PLACE>` | `https://megaeth-testnet-v2.blockscout.com/tx/<TX_COINFLIP_PLACE>` |
| 2 | settleBet | `<TX_COINFLIP_SETTLE>` | `https://megaeth-testnet-v2.blockscout.com/tx/<TX_COINFLIP_SETTLE>` |

Verify the `BetSettled` log on the settle tx page (event signature):
- `BetSettled(uint256 betId, address player, uint8 outcome, bool won, uint256 payout, bytes32 serverReveal)`

#### C.2 — `/play/dice` (Dice / Roll-Under)

- Contract: `0xAC023542A8168465EE4A1b3e8Ae0f58F36A6d84B`
- Min bet: `1e15` wei (0.001 ETH); pick a `rollUnder` in `[2, 98]` — recommend `50` for an even-money smoke
- Expected events: `BetPlaced`, `BetSettled`

| step | action | tx hash slot | explorer link |
|---|---|---|---|
| 1 | placeBet | `<TX_DICE_PLACE>` | `https://megaeth-testnet-v2.blockscout.com/tx/<TX_DICE_PLACE>` |
| 2 | settleBet | `<TX_DICE_SETTLE>` | `https://megaeth-testnet-v2.blockscout.com/tx/<TX_DICE_SETTLE>` |

Verify the `BetSettled` log:
- `BetSettled(uint256 betId, address player, uint8 rollUnder, uint8 roll, bool won, uint256 payout, bytes32 serverReveal)`

#### C.3 — `/play/hilo` (HiLo)

- Contract: `0xd9B9b6c37ad4f3D5b07ae76dE261c5C865600d6e`
- Min bet: `1e15` wei (0.001 ETH); play one step (Higher or Lower) then **Cash out** so the session terminates with `SessionCashedOut`
- Expected events: `SessionOpened`, `StepPlayed`, `SessionCashedOut` (or `SessionPushed` on tie / `SessionLost` on loss — note which path you took)

| step | action | tx hash slot | explorer link |
|---|---|---|---|
| 1 | openSession | `<TX_HILO_OPEN>` | `https://megaeth-testnet-v2.blockscout.com/tx/<TX_HILO_OPEN>` |
| 2 | playStep | `<TX_HILO_STEP>` | `https://megaeth-testnet-v2.blockscout.com/tx/<TX_HILO_STEP>` |
| 3 | cashOut | `<TX_HILO_CASHOUT>` | `https://megaeth-testnet-v2.blockscout.com/tx/<TX_HILO_CASHOUT>` |

Verify the terminal event on the final tx page (one of):
- `SessionCashedOut(uint256 sessionId, address player, uint256 multiplier, uint256 payout)` — happy path
- `SessionPushed(uint256 sessionId, address player, uint8 card)` — tie on a step
- `SessionLost(uint256 sessionId, address player, uint8 card)` — wrong direction

### D. Closing the loop

Once the six (Coinflip 2, Dice 2, HiLo 2–3) tx hashes are pasted in, the smoke is captured. To close `[BB_PHASE2_TESTNET_BET_SMOKE]`:

1. Replace every `<TX_*>` slot above with the real hash.
2. Add a one-paragraph "Smoke result" block under each game noting which side won/lost (e.g. "Coinflip: Heads bet, Tails rolled, lost 0.001 ETH; bankroll +1e15"). This is the operator's eyes-on confirmation that the front-end → contract → indexer → UI loop closed.
3. Mark the queue task `[x]` in `memory/evolution/QUEUE.md` with date.
4. Phase 2 ROADMAP exit gate (e) is then fully closed end-to-end.

### E. (Optional) Chain-layer fallback if the browser path is too costly today

If for any reason the browser UI is not available right now (operator on the road, host with no display, etc.) **and** all you want is signal that the deployed contracts respond to the documented bet flow on-chain, the **deploy-testnet.sh wrapper already exercises every code path against `https://carrot.megaeth.com/rpc`** during dry-run, and the `BetSettled` / `SessionCashedOut` event shapes are covered by the 119+ forge tests + the wallet-mocked Playwright connected suite (`apps/web/e2e/{coinflip,dice,hilo}.connected.spec.ts`). That CI signal is **not equivalent to the browser smoke** — it does not prove the live front-end's wagmi config wires to the right addresses on a real wallet click — but it is what we have until the operator runs section C.

A `cast`-based player smoke from the deployer key is **deliberately not run by the agent** because:
1. It would not exercise the browser → wagmi → wallet → contract path the smoke actually validates;
2. It would burn the unique commit/reveal seed on three real bets that the operator's smoke bets must then avoid colliding with;
3. The deployer is the **owner** key — betting from the owner is unrepresentative of the player path the smoke is meant to cover.
