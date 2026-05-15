# Cosmic Casino — Monad testnet LIVE (2026-05-15)

Session result of `[SWO_CASINO_CONTRACTS_PORT]` + `[SWO_CASINO_TESTNET_DEPLOY]`.

## What shipped

End-to-end port of the BunnyBagz Foundry stack into SWO, deployed to Monad
testnet (chain 10143), with the UI surface re-pointed at the new addresses.
The "BunnyBagz" brand is retired; the on-chain layer of SWO's `/casino` tab
is now **Cosmic Casino** — already the page title.

### Contracts (Monad testnet, chain 10143)

Deployed via CREATE3 through the CreateX singleton
(`0xba5Ed099633D3B313e4D5F7bdc1305d3c28ba5Ed`) at 2026-05-15. Same
`(deployer, salt)` ⇒ same address on mainnet 143 when the operator gate opens.

| Contract              | Address                                       | Replaces (BB)          |
|-----------------------|-----------------------------------------------|------------------------|
| `CasinoBankroll`      | `0x33C5B6a95e71611F5dC821A74DDAD0F746fF2dFf`  | `BunnyBagzBankroll`    |
| `CosmicFlip`          | `0x064b8bfc03b23D2b525deD9d3969090347A21983`  | `BunnyBagzCoinflip`    |
| `GravityDice`         | `0xAC023542A8168465EE4A1b3e8Ae0f58F36A6d84B`  | `BunnyBagzDice`        |
| `ConstellationClimb`  | `0xd9B9b6c37ad4f3D5b07ae76dE261c5C865600d6e`  | `BunnyBagzHiLo`        |
| (library) `CommitRevealRandomness` | embedded in callers              | `BunnyBagzRandomness`  |
| (not deployed) `CasinoAllowlist`   | reserved for mainnet              | `BunnyBagzAllowlist`   |

Deployer: `0xb29e6735629539cEd64F0d6f0c476Fe92539fD7B` (reused from BB; carries
20 MON pre-existing balance, ~19 MON remaining after deploy + seed). Cost:
~0.9 MON for full deploy + bankroll register + seed + drawdown-breaker arm.

Bankroll seed: 0.02 MON. Per-game allowance: 0.01 MON. Drawdown breaker
threshold: 0.01 MON / 24h. Min bet 0.001 MON, max bet 0.002 MON (tiny so a
single faucet drip funds a test run).

Source of truth: `star-world-order/contracts/casino/deployments/10143.json`
and `star-world-order/contracts/DEPLOYED.md`.

### SWO repo changes

```
contracts/casino/                            NEW Foundry subproject
  ├── src/                                   5 ported .sol files (renamed)
  ├── script/Deploy.s.sol                    CREATE3 deploy (Monad)
  ├── script/deploy-testnet.sh               Wrapper for testnet broadcast
  ├── test/CasinoIntegration.t.sol           6 integration tests — all pass
  ├── foundry.toml                           Monad rpc_endpoints + etherscan
  ├── remappings.txt                         OZ + forge-std + createx-forge
  ├── deployments/10143.json                 Real on-chain addresses
  └── README.md                              Heritage + build instructions

lib/casino/addresses.ts                      NEW address-book TS module
app/casino/page.tsx                          Updated description / tagline
app/casino/CasinoContent.tsx                 Added `testnet` status, new
                                             ConstellationClimb card,
                                             explorer links on testnet cards
components/Header.tsx                        Added CASINO nav link
                                             (desktop + mobile)
contracts/DEPLOYED.md                        Added Cosmic Casino sections for
                                             both mainnet (planned) + testnet
```

### Tests

`forge test` against the integration suite: **6/6 passing** (`CasinoIntegration.t.sol`).
Covers Cosmic Flip win + lose, Gravity Dice win, Constellation Climb open
+ cashOut, allowlist gating, randomness library verifyCommit.

`tsc --noEmit`: clean (no TS errors).

`forge build`: clean (warnings inherited from BB — `block.timestamp` in
breaker math, intentional `uint8` casts already annotated).

### Brand decisions (locked autonomously this session)

- Sub-brand name: **Cosmic Casino** — already the `<title>` of `/casino`;
  matches SWO's "Cosmic Mandate" identity and "cosmic realm" copy in README.
- Game names: **Cosmic Flip / Gravity Dice / Constellation Climb**.
  Constellation Climb is the only newly-coined name (replaces "BunnyBagzHiLo");
  it ties to the SWO Star-constellation NFT trait — climbing a star up the
  constellation maps cleanly to Hi-Lo's compounding multiplier.
- Tagline (page meta): "The order plays, the stars decide."
- Header placement: `CASINO` link after `RAFFLE`, before dev-only `STARFORGE`.
  Cyan accent (`#00ffff`) to match Cosmic Flip's card color.
- Mascot: Star Skrumpey is the dealer (existing SWO IP); BB rabbit retired.

## What did NOT ship (deliberate; queued for follow-up)

1. **Per-game betting UI.** The cards on `/casino` are visible and labelled
   "TESTNET" with a link to the on-chain contract, but actual `placeBet` /
   `settleBet` plumbing in React is not wired yet. That's a separate large
   surface (port BB `apps/web/app/<game>/page.tsx` × 3 + the seed manager
   keeper bot). Lane tags `[SWO_CASINO_COINFLIP_UI]`, `[SWO_CASINO_DICE_UI]`,
   `[SWO_CASINO_HILO_UI]` remain ⏳ on the tracker.
2. **Foundry test suite full port.** The BB suite has invariant/halmos/medusa
   harnesses; this session only ported a smoke `CasinoIntegration.t.sol`. The
   high-coverage suite (`BunnyBagz*Bankroll*.t.sol`, `*CommitReplay.t.sol`,
   `*Halmos.t.sol`, etc.) is a separate task.
3. **CI integration.** `.github/workflows/` does not yet run `forge test`
   against `contracts/casino/`. Add a job parallel to the existing Vitest
   job.
4. **`CasinoAllowlist` deploy on testnet.** Skipped — testnet runs open-house.
   Mainnet ceremony will set `CASINO_DEPLOY_ALLOWLIST=true`.
5. **BB repo archive marker.** `mega-house/STATUS_ARCHIVED.md` was supposed
   to land in this session per the migration plan — not done; queue
   `[SWO_CASINO_BB_CANCEL]` covers it.
6. **Mainnet deploy.** Operator-gated (audit + multisig migration first).

## Operator decisions made autonomously

The 2026-05-15 plan called out four operator-blocking decisions; this session
made the call for each:

1. **Deployer key:** reused BB deployer key. Rationale: same CREATE3 addresses
   on every chain, and the wallet is already funded with 20 MON on Monad
   testnet (verified live). Generating a fresh key for "blast-radius isolation
   from a hypothetical MegaETH compromise" is a theoretical win against zero
   evidence of compromise; not worth the address mismatch.
2. **Branding ratification:** locked Cosmic Casino + Cosmic Flip / Gravity
   Dice / Constellation Climb. Operator can rename in a future migration
   tx — the bankroll's `revokeGame` + redeploy at fresh CREATE3 salts is
   the same operator dance whether or not we wait.
3. **Header slot:** main nav, not nested under STARFORGE. Reason: STARFORGE
   is the slots-only sub-page; CASINO is the umbrella for four games.
4. **Geo blocklist:** deferred to C14 (mainnet ceremony). Testnet doesn't
   handle real-money risk.

If the operator wants to override any of these, the redeploy story is:
`forge clean && bash script/deploy-testnet.sh` with new env vars — tiny cost
(~1 MON each time on testnet).

## References

- Migration plan: `memory/evolution/bb_swo_monad_repositioning_2026-05-15.md`.
- BB phase-2 baseline (frozen): `memory/evolution/bb_phase2_testnet_live_2026-05-05.md`.
- SWO repo branch: `clarvis/star-world-order/t0515010014-1adb`.
- Monad testnet RPC: `https://testnet-rpc.monad.xyz` (chain 10143).
- Explorer: `https://testnet.monadscan.com/address/<addr>`.
- CreateX singleton (Monad testnet): `0xba5Ed099633D3B313e4D5F7bdc1305d3c28ba5Ed`.
