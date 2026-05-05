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
