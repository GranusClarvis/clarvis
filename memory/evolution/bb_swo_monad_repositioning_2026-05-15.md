# BB → SWO repositioning & Monad migration plan — 2026-05-15

> **Status:** PLAN (operator-bound decisions called out). Replaces the
> independent "BunnyBagz on MegaETH" direction. MegaETH is treated as a
> failed experiment; the BB stack is repositioned as the **casino layer of
> Star World Order on Monad**.

## TL;DR

1. **MegaETH is dead** for BB. The deployed Phase-2 stack on chain 6343
   (Bankroll + Coinflip + Dice + HiLo, deployed 2026-05-05) is frozen
   in place as a reference but does **not** continue receiving feature
   work. No mainnet 4326 deploy ever happens.
2. **BB is dissolved as a standalone product brand.** The contracts and
   game engine are retained — wholesale — and ported to **Monad** as the
   on-chain layer powering the existing SWO `/casino` tab. The
   "BunnyBagz" name is retired in favor of an SWO-aligned mark (proposal:
   **Cosmic Casino** — already the page title in
   `app/casino/page.tsx:metadata`).
3. **Tab placement.** Keep the URL `/casino` (already exists in SWO,
   already wired into `CasinoContent.tsx`). Add **`CASINO`** to the SWO
   header nav (currently casino has no nav entry — it's an unlinked
   page). Gate exactly the same as `/dao` / `/sanctuary` —
   `AccessGate` for Star-Skrumpey holders only.
4. **Monad is fully EVM-compatible** at Cancun. BB contracts compile at
   Solidity ^0.8.24 and use no MegaETH-specific opcodes or precompiles.
   The migration is **mostly config**: chain IDs, RPC URLs, deploy
   scripts, foundry.toml, the address book.
5. **Funding blocker.** Deployer `0xb29e6735629539cEd64F0d6f0c476Fe92539fD7B`
   has 0 MON on Monad testnet (10143). `faucet.monad.xyz` is captcha-gated
   behind a Vercel Security Checkpoint and can't be drained programmatically.
   **Operator must claim once** (or fund the wallet from another address).

---

## 1. Why MegaETH is treated as a failed experiment

The product premise of BunnyBagz depended on MegaETH's 10ms blocks for the
"30 seconds to bet" UX target. The chain itself never reached the user
density that would make a casino there commercially viable, and the
ecosystem (Fluffle, Pepe rabbits) has stalled. The Phase-2 testnet deploy
worked (see `memory/evolution/bb_phase2_testnet_live_2026-05-05.md` for the
on-chain verification), but the next phase — audit + mainnet — costs real
money and produces a casino on a chain nobody plays on.

The operator's call (recorded in this doc): **take the working contract
stack to where the user base actually exists** — namely, the Skrumpey
holders on Monad who are already the SWO audience.

## 2. SWO casino current state (audit, 2026-05-15)

`/casino` already exists in `/home/agent/agents/star-world-order/workspace/app/casino/`:

- `page.tsx` — title "Cosmic Casino | Star World Order", description
  "Provably fair games on Monad blockchain".
- `CasinoContent.tsx` — 496 lines, four game cards rendered:
  1. **Star Forge Slots** — `status: 'live'`, path `/casino/slots` (slot game implemented separately at `/casino/slots`).
  2. **Cosmic Flip** — `status: 'coming_soon'`, path `/casino/coinflip`. RTP 98%, min 10 MON / max 1000 MON.
  3. **Nebula Roulette** — `status: 'coming_soon'`, path `/casino/roulette`. RTP 97.3%.
  4. **Gravity Dice** — `status: 'coming_soon'`, path `/casino/dice`. RTP 99%, min 5 MON / max 500 MON.
- Gating: wrapped in `AccessGate` (Skrumpey holders only).
- **Not in header nav.** `components/Header.tsx` has no `/casino` link.

The `coming_soon` cards on Cosmic Flip, Gravity Dice are the natural
destinations for BB's existing `BunnyBagzCoinflip` + `BunnyBagzDice`.
**HiLo has no SWO equivalent yet** and needs a new SWO-aligned name +
card.

## 3. Naming & branding (operator-binding proposal)

| BB contract / surface     | SWO-aligned name (proposed)              | Rationale |
|---------------------------|------------------------------------------|-----------|
| `BunnyBagzCoinflip`       | **Cosmic Flip** (existing SWO card)      | Already on the casino page; keep contract symbol `COSMIC_FLIP_V1`. |
| `BunnyBagzDice`           | **Gravity Dice** (existing SWO card)     | Already on the casino page. |
| `BunnyBagzHiLo`           | **Constellation Climb** (new)            | SWO-native: "climb the constellation" maps cleanly to Hi-Lo's streak mechanic. Alternates considered: *Stargate Hi-Lo*, *Cosmic Ladder*. |
| `BunnyBagzBankroll`       | `CasinoBankroll` (internal-only)         | Never user-visible; rename for clarity in code. |
| `BunnyBagzRandomness`     | `CommitRevealRandomness` (library)       | Generic library; drop the BB prefix. |
| `BunnyBagzAllowlist`      | `CasinoAllowlist`                        | Generic. |
| `BunnyBagzTreasury`       | `CasinoTreasury`                         | Generic. |
| `BunnyBagzVersion`        | drop (or fold into a `Versions.sol`)     | One-line constants file. |
| Mascot (`BunnyBagz` rabbit) | **Star Skrumpey dealer** (existing IP)    | Reuse the Skrumpey mascot system from SWO instead of introducing a new rabbit. |
| Brand surface             | **Cosmic Casino** (sub-brand of SWO)     | Matches `<title>` already on `/casino`. |
| Tagline                   | "the order plays, the stars decide"      | Aligns with SWO's "chosen by the stars" voice. |
| Domain                    | `starworldorder.com/casino`              | No standalone `bunnybagz.xyz` purchase. |

**Header placement.** Add a `CASINO` link to `components/Header.tsx`
alongside `DAO / GALLERY / HANGOUT / SANCTUARY / RAFFLE / STARFORGE`.
Position: between **STARFORGE** and **RAFFLE** (slots fits with games,
raffle fits with casino-adjacent).

**Color tokens.** Drop BB's gold/carrot-orange palette. Inherit SWO's
existing `#ffd700` gold + `#9966ff` purple + neon casino accents from
`CasinoContent.tsx` (cyan `#00ffff` for flip, magenta `#ff00ff` for
roulette, green `#44ff88` for dice). The BB `BRAND.md` palette is **not**
ported.

## 4. Monad compatibility audit (does BB work on Monad?)

**Verdict: Yes, with config changes only.** No Solidity changes required.

| Concern | Monad behavior | BB impact |
|---------|----------------|-----------|
| EVM target | Cancun-compatible, all opcodes incl. PUSH0 supported. | `solc 0.8.24` (BB's pin) is fine; no opcode strip needed. |
| Chain ID | mainnet `143`, testnet `10143`. | Replaces `4326`/`6343` in `packages/chain/src/index.ts`, `foundry.toml`, deploy scripts. |
| Native gas token | `MON` (18 decimals). | Game contracts already use native `msg.value` — no token swap needed. |
| Block time | ~500ms testnet (vs MegaETH 10ms). | BB uses `BLOCKHASH(block.number - N)` for last-256 horizon; 256 blocks = ~2 min on Monad vs ~2.5s on MegaETH. **Functionally safe** (commit-reveal doesn't need short horizon), but UX copy referencing "~25s commit window" must update. |
| Block hash availability | Standard 256-block window. | Same as Ethereum mainnet; no change. |
| Gas accounting | Monad charges `gasLimit`, not `gasUsed`, for async exec. | Fee estimation in the UI (`apps/web` if ported) must use `gasLimit` for cost display. Not a contract change. |
| Contract size limit | 128 KB on Monad (vs 24.5 KB Ethereum). | BB contracts are all <10 KB; no impact. |
| Min base fee | 100 MON-gwei (testnet) | Trivially cheap; bankroll seed sizes can drop by ~3 orders of magnitude vs the MegaETH 1 gwei floor. |
| Stablecoin (USDm) | No canonical Monad USDm exists. | **Remove** the USDM code path from `packages/chain` and BB UI. MVP is MON-only; USDC-on-Monad considered post-launch. |
| CREATE3 deployer (`0xba5Ed099...ba5Ed`) | Deployed on Monad as part of the standard pcaversaccio CreateX rollout. | **Verify before deploy** with `cast code 0xba5Ed099633D3B313e4D5F7bdc1305d3c28ba5Ed --rpc-url https://testnet-rpc.monad.xyz`. If absent, etch via `CreateXScript.setUp()` like the local-anvil path already does. |
| Multicall3 | Canonical `0xcA11bde05977b3631167028862bE2a173976CA11` (per `contracts/DEPLOYED.md` in SWO repo). | Reuse SWO's existing chain config. |
| OpenZeppelin Defender | Defender supports Monad as of 2026-Q1. | Reconfigure monitors after redeploy; addresses change. |

**Code locations that touch MegaETH and need edits** (audited 2026-05-15):

```
packages/chain/src/index.ts                              chain defs (4326/6343 → 143/10143)
packages/chain/src/addresses.generated.ts                regen after Monad deploy
packages/contracts/foundry.toml                          [rpc_endpoints] + [etherscan] sections
packages/contracts/script/Deploy.s.sol                   NatSpec mentions of MegaETH only
packages/contracts/script/deploy-mainnet.sh              RPC URL + chain name
packages/contracts/script/deploy-testnet.sh              RPC URL + chain name
packages/contracts/script/wait-for-funding.sh            RPC URL
packages/contracts/test/DeployDeterministic.t.sol        chain-id reference in test
packages/contracts/src/BunnyBagzCoinflip.sol             NatSpec: "256 ≈ ~25s on MegaETH" → "256 blocks (~2 min on Monad)"
packages/contracts/src/BunnyBagzDice.sol                 same NatSpec line
packages/contracts/src/BunnyBagzHiLo.sol                 same NatSpec line
packages/contracts/src/BunnyBagzTreasury.sol             NatSpec mention only
packages/contracts/defender/monitors/*.json              `network: "megaeth-testnet"` → `"monad-testnet"`
packages/contracts/defender/actions/telegram-forwarder.ts comments + chain alias map
packages/contracts/defender/scripts/deploy-monitors.ts   chain alias arg
packages/contracts/deployments/6343.json                 historical, keep but tag as "deprecated-megaeth"
packages/invariants/src/cli.ts                           CLI default RPC URL
packages/invariants/src/harness.ts                       RPC URL
README.md / docs/*.md                                    rebrand pass (separate doc tracker)
```

## 5. SWO repo changes (where the casino actually lives)

The SWO frontend (`/home/agent/agents/star-world-order/workspace/`) is
where the new casino UI runs. The BB `apps/web` Next.js casino app is
**not ported** — its components are extracted as a package, dropped into
SWO, and the BB monorepo's `apps/web` is archived.

Concrete SWO changes:

```
app/casino/CasinoContent.tsx           keep cards; flip status to 'live' as games go live
app/casino/coinflip/page.tsx           NEW: extract from BB apps/web/app/coinflip
app/casino/dice/page.tsx               NEW: extract from BB apps/web/app/dice
app/casino/hilo/page.tsx               NEW (Constellation Climb) — extract from BB apps/web/app/hilo
components/Header.tsx                  add CASINO link between STARFORGE and RAFFLE
lib/wagmi.ts                           already Monad — no change
lib/casino/                            NEW: thin chain client + ABI imports + bet hooks (port from BB packages/chain + packages/verify)
contracts/DEPLOYED.md                  add new casino contract rows under "Monad Mainnet" + "Monad Testnet" tables
contracts/CasinoBankroll.sol           NEW (port of BunnyBagzBankroll, renamed)
contracts/CasinoCoinflip.sol           NEW (port of BunnyBagzCoinflip)
contracts/CasinoDice.sol               NEW (port of BunnyBagzDice)
contracts/ConstellationClimb.sol       NEW (port of BunnyBagzHiLo, renamed)
contracts/CommitRevealRandomness.sol   NEW (port of BunnyBagzRandomness, renamed)
contracts/CasinoAllowlist.sol          NEW (port of BunnyBagzAllowlist)
scripts/casino/deploy-testnet.sh       NEW (Monad-targeted Foundry deploy)
TESTNET.md                             add Cosmic Casino deployment section
```

The contract **source** is moved into SWO so the SWO repo is the single
deployable artifact. The BB repo (`mega-house`) gets a `STATUS.md` flagging
it as archived, plus a pointer to the SWO casino.

## 6. Deployment plan (Monad testnet → mainnet)

### Phase A — Funding & smoke (1 session)

- [ ] **Operator: claim faucet** at https://faucet.monad.xyz to the
      deployer `0xb29e6735629539cEd64F0d6f0c476Fe92539fD7B` (or any
      newly-generated deployer; see ownership note below).
      Alternative: Alchemy faucet (no-auth, 24h cooldown).
      Target: ≥0.5 MON for testnet deploy + register + seed.
- [ ] Smoke RPC: `cast block-number --rpc-url https://testnet-rpc.monad.xyz`
      (already verified working, block ~31_924_117 at 2026-05-15).

### Phase B — Contract port (1–2 sessions)

- [ ] Copy BB `src/*.sol` → SWO `contracts/` with the renames in the
      branding table.
- [ ] Mechanical find/replace: contract names, library names, event
      names. Solidity body unchanged.
- [ ] Port BB Foundry test suite into SWO `test/casino/` (currently SWO
      uses Hardhat + Vitest; add a Foundry subproject under `contracts/`
      or convert critical invariants to Hardhat. **Recommend Foundry**
      for parity with the audit-validated BB suite).
- [ ] CI: add `forge test` job in `.github/workflows/`.

### Phase C — Testnet deploy via CREATE3 (1 session)

- [ ] Verify CreateX presence on Monad testnet (cast code call).
- [ ] Pick distinct salts (or reuse BB's `0xBB01/0xBBC1/0xBBD1/0xBBA1/0xBBAA`
      — they don't collide with anything Monad-side).
- [ ] Run port of `script/Deploy.s.sol` against `--rpc-url
      https://testnet-rpc.monad.xyz --chain 10143`.
- [ ] Verify the four contract addresses match CREATE3 prediction.
- [ ] Register the three games on the bankroll, seed the bankroll with
      ~0.1 MON (Monad is cheap; testnet limits will require a small seed).
- [ ] Generate `lib/casino/addresses.generated.ts` in SWO.

### Phase D — UI wiring (2–3 sessions)

- [ ] Port the Coinflip/Dice/HiLo pages from BB `apps/web` into
      `app/casino/<game>/page.tsx`. Rebrand microcopy.
- [ ] Replace BB mascot art with Star Skrumpey art (already in SWO repo
      at `app/casino/`, `public/` Skrumpey assets).
- [ ] Update `CasinoContent.tsx` card statuses to `'live'` as each game
      ships.
- [ ] Add `CASINO` to header nav.
- [ ] E2E happy path: connect wallet → land on `/casino` → click Cosmic
      Flip → place 0.001 MON bet → see settled result.

### Phase E — Mainnet (operator gate — DO NOT auto-execute)

- [ ] Audit firm pick (open from BB's `DECISIONS.md`).
- [ ] Multisig migration before any mainnet seed.
- [ ] Final geo block list review (Monad's user base differs from
      MegaETH's; revisit the OFAC + 9-country list).
- [ ] Deploy via CREATE3 with the **same salts** as testnet → identical
      addresses on chain 143 vs 10143 (assuming same deployer).
- [ ] Initial bankroll seed: open question for operator (suggested
      ≈10–50 MON, sized by current MON valuation — much smaller in
      USD terms than the BB MegaETH plan because MON is testnet-volatile).

## 7. Open items requiring operator decision

These block the migration moving past Phase A/B if unresolved:

1. **Ownership / multisig.** Reuse the existing BB deployer key
   (`0xb29e6735629539cEd64F0d6f0c476Fe92539fD7B`)? Or generate a fresh
   Monad-only key now and migrate ownership? Same key gives the same
   CREATE3 addresses on every chain (a feature). Different key avoids
   any blast-radius from a hypothetical MegaETH key compromise.
2. **Branding ratification.** Confirm or veto:
   - Sub-brand name **Cosmic Casino**.
   - Game names **Cosmic Flip / Gravity Dice / Constellation Climb**.
   - HiLo rename: keep the existing two-letter brand or pick from
     `Constellation Climb / Stargate Hi-Lo / Cosmic Ladder`.
3. **Header slot.** Confirm `CASINO` lives in main header nav. Alternative
   is to nest under `STARFORGE` (Star Forge already routes into `/casino`).
4. **Bankroll seed size on testnet.** Default proposal: 0.1 MON
   (testnet faucet realistically only gives ~0.5/day).
5. **Audit firm.** Carry over the BB `DECISIONS.md` open item — Spearbit,
   ToB, Cyfrin, or ChainSecurity?
6. **Geo policy.** BB had a strict 9-country + OFAC block. Carry over
   verbatim or relax for Monad's audience? (Recommend: carry over
   verbatim. Monad's user base is global crypto-native; same risk
   profile.)
7. **Standalone `bunnybagz.xyz` domain.** The BB plan called for a
   purchase. **Recommend: don't buy.** All traffic comes from
   `starworldorder.com/casino`.

## 8. Cleanup of the BB lane

- `[BB_*]` queue tasks tagged for Phase 3 (audit + mainnet on MegaETH)
  are **cancelled** (not "done" — explicitly killed). Add a sweep task
  to grep `[BB_PHASE3` / `[BB_PHASE4` / `[BB_PHASE5` from
  `memory/evolution/QUEUE.md` and either close-as-cancelled or migrate
  to `[SWO_CASINO_*]` lane.
- `memory/evolution/SWO_TRACKER.md` gets a new section "Cosmic Casino
  (BB merge-in)" with the Phase-A through Phase-E checklist above.
- BB repo (`/home/agent/agents/mega-house/workspace/`): write
  `STATUS_ARCHIVED.md` at root with a one-paragraph "this repo is frozen
  as of 2026-05-15; active work lives at
  `GranusClarvis/star-world-order` under `/casino`."

## 9. References (verified 2026-05-15)

- Monad docs index: https://docs.monad.xyz/
- Monad mainnet info: https://docs.monad.xyz/developer-essentials/network-information (chain 143, native MON, 5 RPC providers)
- Monad testnet chain settings: https://chainlist.org/chain/10143 (chain 10143, RPC `https://testnet-rpc.monad.xyz`)
- Faucet: https://faucet.monad.xyz (captcha-gated, requires 10 MON mainnet or 0.001 ETH on L1/L2 for unlock; max 1 claim / 6h)
- Alternative faucets: Alchemy (no-auth, 24h cooldown), QuickNode (0.5–2 MON), thirdweb (0.01 MON/day), Owlto (0.1 MON one-time).
- EVM behavior: https://docs.monad.xyz/guides/evm-resources/evm-behavior (Cancun-compatible, PUSH0 supported, opcode pricing differs).
- Gas pricing: https://docs.monad.xyz/developer-essentials/gas-pricing (min base fee 100 MON-gwei; gasLimit charged not gasUsed).
- Solidity resources: https://docs.monad.xyz/guides/evm-resources/solidity-resources (recommended `solc ≥0.8.20` for PUSH0).
- BB Phase 2 testnet deploy (frozen): `memory/evolution/bb_phase2_testnet_live_2026-05-05.md`.
- SWO casino page: `/home/agent/agents/star-world-order/workspace/app/casino/CasinoContent.tsx` (4 cards, 1 live).
- SWO Monad config: `lib/wagmi.ts`, `lib/voteSignature.ts` (chain 143 default).
- SWO contracts ledger: `contracts/DEPLOYED.md`.
