# SWO Server Trust Boundary Audit — 2026-04-17

## Summary

Audited all SWO API routes in `/home/agent/agents/star-world-order/workspace/app/api/`.
The codebase has two solid auth primitives (`verifyWalletAccess` via EIP-191, `verifyAdminAccess` via admin nonce) but several routes either skip auth entirely or trust client-supplied values for authorization decisions.

**Findings: 2 CRITICAL, 5 HIGH, 2 MEDIUM, 3 LOW**

## CRITICAL

### 1. Raffle: Client-Supplied `discordBonus` / `engagementBonus` (Spoofable)
- **File:** `app/api/raffle/route.ts:378,470-477`
- **Issue:** `discordBonus` and `engagementBonus` booleans accepted from request body and used to grant +1 raffle entry each. Server checks `discord_bonus_enabled` on the raffle config but never verifies the user actually has Discord connected (even though `checkSocialConnections()` exists and is called nearby for the `require_discord` gate).
- **Impact:** Any authenticated wallet claims both bonus entries on every raffle by sending `{discordBonus: true, engagementBonus: true}`.
- **Fix:** Call `checkSocialConnections(walletAddress)` and use `hasDiscord` result instead of trusting client boolean. For engagement bonus, require server-verified tweet interaction or remove the feature.

### 2. Governance: Client-Supplied `votingPower` (Spoofable)
- **File:** `app/api/governance/route.ts:418,545-549`
- **Issue:** `votingPower` read from request body and passed to `castGovernanceVote`. The EIP-712/191 signature does NOT cover `votingPower`, so a user can send any integer.
- **Impact:** A voter can set `votingPower: 999999` and it's stored in the DB. Governance outcomes entirely manipulable.
- **Fix:** Remove `votingPower` from request body. Compute server-side from on-chain NFT balance or holder records. If kept, include in signed typed data.

## HIGH

### 3. Chat: No Auth on POST (`senderAddress` spoofable)
- **File:** `app/api/chat/route.ts:148-190`
- **Issue:** No `verifyWalletAccess` call. `senderAddress` accepted from body. Any client can impersonate any wallet in chat.
- **Fix:** Add `verifyWalletAccess`, verify authenticated wallet matches `senderAddress`.

### 4. Presence: No Auth on POST/DELETE (wallet + Star status spoofable)
- **File:** `app/api/presence/route.ts:35-106`
- **Issue:** No auth. `walletAddress`, `starVariant`, `nftTokenId` all accepted from body. Chat system uses presence data for Star-holder badge.
- **Fix:** Add `verifyWalletAccess`. Compute `starVariant`/`nftTokenId` server-side.

### 5. Messages: No Auth on POST (DM sender spoofable)
- **File:** `app/api/messages/route.ts:103-180`
- **Issue:** No `verifyWalletAccess` on POST (though PATCH/DELETE correctly use it). `senderAddress` from body.
- **Fix:** Add `verifyWalletAccess`, verify authenticated wallet matches `senderAddress`.

### 6. Quests: `complete` Action Lacks Objective Verification
- **File:** `app/api/quests/route.ts:163-169`
- **Issue:** Auth present but quest completion accepted without verifying the wallet actually performed the quest activity. Any authenticated wallet can complete any quest instantly.
- **Fix:** Add server-side objective verification or remove client-triggered completion.

### 7. Voice: No Auth on Any Endpoint
- **File:** `app/api/voice/route.ts:50-194`
- **Issue:** No `verifyWalletAccess` on any handler. `walletAddress` accepted from body. Anyone can join/create sessions as any wallet, mute others, end sessions.
- **Fix:** Add `verifyWalletAccess` to all handlers.

## MEDIUM

### 8. Raffle GET: Unauthenticated Privacy Leak
- **File:** `app/api/raffle/route.ts:86-116,198-267`
- **Issue:** `address` query param returns raffle entries, wins, social connections without auth.
- **Fix:** Strip social connection data from unauthenticated responses.

### 9. Presence: `starVariant`/`nftTokenId` Not Verified On-Chain
- **File:** `app/api/presence/route.ts:38,60-65`
- **Issue:** Even with auth, these are accepted from client. Should be computed server-side.

## LOW

### 10. Admin Notification Lookup — expected admin behavior, noted for completeness
### 11. Cron Dev Bypass — `NODE_ENV=development` skips auth
### 12. Profile `isDemoMode` — client flag only adds restrictions, design is fragile but not exploitable

## Route Summary

| Route | Auth | Status |
|---|---|---|
| POST /api/raffle (enter) | verifyWalletAccess | **CRITICAL**: bonus entries spoofable |
| POST /api/governance (vote) | Signature verified | **CRITICAL**: votingPower spoofable |
| POST /api/chat | **NONE** | HIGH: sender spoofable |
| POST/DELETE /api/presence | **NONE** | HIGH: wallet+status spoofable |
| POST /api/messages | **NONE** | HIGH: sender spoofable |
| POST /api/quests (complete) | verifyWalletAccess | HIGH: no objective check |
| ALL /api/voice | **NONE** | HIGH: wallet spoofable |
| GET /api/raffle | **NONE** | MEDIUM: privacy leak |
| POST /api/profile | verifyWalletAccess | LOW |
| POST /api/user-xp | verifyAdminAccess | SECURE |
| ALL /api/admin | verifyAdminAccess | SECURE |
| ALL /api/forum | verifyWalletAccess | SECURE |
| ALL /api/notifications | verifyWalletAccess | SECURE |
| POST /api/friends | verifyWalletAccess | SECURE |
| POST /api/starforge/* | verifyWalletAccess | SECURE |
| GET /api/members,metadata,etc | No auth (public read) | ACCEPTABLE |

## Remediation Priority

1. **Immediate**: Fix CRITICAL findings 1 & 2 (raffle bonus + votingPower)
2. **Urgent**: Add `verifyWalletAccess` to chat, presence, messages, voice (findings 3-5, 7)
3. **Important**: Quest objective verification (finding 6), presence field verification (finding 9)
