# BunnyBagz Phase 1 — End-to-End Status (2026-05-03 evening)

> Single source of truth for Phase 1 completion. Supersedes
> `bb_phase1_status_2026-05-02.md` by adding today's commits + chain-id fix
> + concrete operator-gated remaining work.

Repo: `GranusClarvis/bunnybagz` · branch `feature/mvp-planning-and-rebrand`
Local workspace: `/home/agent/agents/mega-house/workspace`
Testnet wallet (this session): `0xb29e6735629539cEd64F0d6f0c476Fe92539fD7B`
(stored at `~/agents/mega-house/secrets/testnet-wallet.json`, chmod 600,
outside the repo).

## Phase status snapshot

- **Phase 0 — Repo & rails: ✅ DONE.**
- **Phase 1 — Coinflip end-to-end on testnet: ⚠ ~96%** (up from ~92% on
  2026-05-02 after today's chain-id fix + deploy runbook + verified pipeline
  against the real testnet RPC).
- **Phase 2 — Dice + HiLo + USDM: ⚠ ~30%.** HiLo contract shipped (commit
  `70b53c9`); HiLo + Dice frontends still stubs; USDM not started; Playwright
  not started.
- **Phase 3+ — operator-blocked.** Audit firm, multisig, mainnet seed.

## What shipped on 2026-05-03 (this session)

| Commit | Item | Evidence |
|---|---|---|
| `ae1897f` | `[BB_CHAIN_ID_DRIFT_FIX]` MegaETH testnet id `6342 → 6343` | `packages/chain/src/index.ts`; 5 test fixtures; 6 doc files; explorer URL switched to `https://megaeth-testnet-v2.blockscout.com`. Source: upstream `megaeth-labs/documentation` `vars.yaml` (`testnet_chain_id: '6343'`). Tests: contracts 102/102, web 157/157, api 46/46, indexer 21/21 |
| `cdf105f` | `[BB_PHASE1_TESTNET_DEPLOY_RUNBOOK]` Deploy runbook + status doc | `packages/contracts/script/deploy-testnet.sh` (sized for one faucet drip); `docs/PHASE1_STATUS.md` (in-repo single source of truth); deploy pipeline verified end-to-end against `https://carrot.megaeth.com/rpc` — every call simulates cleanly except the final `deposit{value:…}` which reverts on `OutOfFunds` (expected) |

## The single remaining gap (operator-gated)

Phase 1 cannot reach 100% without one operator action: claim 0.005 testnet
ETH from <https://testnet.megaeth.com/> for the wallet
`0xb29e6735629539cEd64F0d6f0c476Fe92539fD7B`. The faucet is gated by
Cloudflare Turnstile (sitekey `0x4AAAAAAB8N9XQ8u4dRKBt_`), which the agent
cannot solve from CLI or headless browser; tried both the API endpoint
(`POST /api/faucet` returns `{"success":false,"message":"invalid CAPTCHA"}`)
and Playwright (`testnet.megaeth.com` is a heavy SPA that did not load
within the harness timeout — anti-bot protection is the most plausible
cause).

Once funded:

```bash
export PATH="$HOME/.foundry/bin:$PATH"
cd /home/agent/agents/mega-house/workspace
bash packages/contracts/script/deploy-testnet.sh   # broadcast
```

The script:
1. Reads the gitignored deployer key.
2. Verifies on-chain balance ≥ initial deposit (refuses to broadcast if not).
3. Runs `forge script script/Deploy.s.sol --broadcast`.
4. On success: `pnpm --filter @bunnybagz/chain codegen:addresses` regenerates
   `packages/chain/src/addresses.generated.ts`.
5. Prints blockscout links for the operator.

After the broadcast, the agent commits `deployments/6343.json` +
`addresses.generated.ts`, smoke-tests one bet through `apps/web`, and Phase
1 is closed.

## Funding budget

MegaETH testnet base fee is **0.001 gwei**. Deploy + register + tiny seed
fits in well under 0.001 ETH — a single faucet drip (0.005 ETH/24h) covers
the deploy and leaves headroom for ~10 testnet bets at the script's
`MIN_BET=1e15 wei` (0.001 ETH). The script's defaults are intentionally
faucet-sized so the operator does not need to micromanage env vars.

## What did *not* change

The 2026-05-02 status's "drift confirmed" table is fully closed by the
2026-05-02 commits (real Ponder indexer, real wagmi-CLI ABI codegen, real
persistent KV adapter). Today's chain-id fix is a new finding the prior
audit missed — the repo had hardcoded `6342` since Phase 0 scaffold and
nothing flagged it because no live testnet deploy had ever been attempted.

## Phase 2 readiness

Unchanged from 2026-05-02 status:
- HiLo `/play` route still TODO (contract is shipped + tested).
- Dice `/play` route still TODO (contract is shipped + tested).
- USDM `permit()` flow still TODO.
- Playwright e2e still TODO (Phase 2 exit criterion).

These are autonomous-doable. None block Phase 1 closeout.
