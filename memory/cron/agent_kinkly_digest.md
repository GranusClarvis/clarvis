# Project Agent Digest: kinkly
_Promoted 2026-03-09 19:30_

[+] t0308225802-9895: Wired end-to-end payment rails for subscriptions (monthly $9.99, yearly $49.99) and coin packs (100/300/500/1000/5000) via NOWPayments. Fixed IPN signature verification to use sorted-JSON HMAC per docs, added combined cart checkout with items array, token-grant tracking endpoints, and invoice API support. Only production NOWPayments credentials need to be set in env vars for go-live.
  PR: https://github.com/InverseAltruism/kinkly/pull/11
  -> TODO: Set NOWPAYMENTS_API_KEY, NOWPAYMENTS_IPN_SECRET, NOWPAYMENTS_IPN_CALLBACK_URL in production env
  -> TODO: Manual end-to-end test with NOWPayments sandbox before production
  -> TODO: Consider server-side token balance persistence (currently localStorage-only)
  -> TODO: Add frontend token-grant polling (auto-credit tokens after coin purchase confirmation)

## Learned Procedures
- Build: npm run build
- Test: npm run test
- Lint: npm run lint