# Lightpanda — Headless Browser for Machine Consumption

**Date**: 2026-03-12
**Source**: github.com/lightpanda-io/browser, lightpanda.io
**Relevance**: Browser automation stack — potential replacement/supplement for clarvis_browser.py

## Overview

Open-source headless browser built from scratch in **Zig** (v0.15.2). Not Chromium-based — entirely novel implementation. Skips CSS rendering, image loading, layout, and GPU compositing. Only processes DOM, JavaScript (V8), and network.

- **Stars**: 12.4k | **License**: AGPL-3.0 (copyleft) | **Team**: 2 primary devs
- **Protocol**: CDP WebSocket server (16 domains implemented)
- **Deployment**: Static binary (Linux x86_64, macOS aarch64), Docker, cloud WSS

## Performance

Benchmarked on AWS EC2 m5.large, 100 pages via Puppeteer:
- **Memory**: ~24 MB vs ~207 MB for Chrome (9x less)
- **Speed**: ~2.3s vs ~25.2s for Chrome (11x faster)
- **Startup**: Instant (no Chromium launch overhead)

Caveat: benchmarks on simple pages. Complex SPAs narrow the gap since V8 execution time is constant.

## Key Capabilities

**Implemented**: JS execution (V8), DOM APIs (partial), XHR/Fetch, click/form input, cookies, custom headers, proxy, network interception, robots.txt compliance, multi-client CDP connections.

**Not implemented**: CSS rendering, screenshots (no visual rendering), localStorage in storageState (#1550 — crashes), file uploads over CDP (#1203), full SPA support uncertain (#1798).

## Stability Assessment — NOT PRODUCTION-READY

Critical issues:
- **Frequent segfaults**: #1304 ("crashing every 2-3 scraping attempts"), #1738, #1283, #1480
- **Playwright connectOverCDP broken**: #1800 (frame ID mismatch, filed 2026-03-12)
- **storageState crashes**: #1550 (timeout + crash)
- **Navigation failures**: #1401 (click/submit on Amazon doesn't trigger navigation)

Pattern: individual websites trigger crashes that get fixed one at a time.

## Comparison to Clarvis Current Stack

| Capability | Clarvis Stack | Lightpanda |
|-----------|--------------|------------|
| Token efficiency | Agent-Browser snapshot/refs (93% fewer tokens) | No equivalent |
| Session persistence | Full (storageState, cookies) | Cookies only, storageState crashes |
| File uploads | Playwright file chooser | Not supported |
| Screenshots | Yes (Playwright) | No (no CSS rendering) |
| SPA support | Full (real Chromium) | Uncertain |
| Memory | ~200-300 MB (Chromium) | ~24 MB |
| Startup | 2-5 seconds | Instant |
| Browser pool | Single Chromium on port 18800 | No built-in pool |
| Stability | Production-grade | Beta, frequent segfaults |
| Multi-session context sharing | Cookie injection per session | Not available (#1672 unanswered) |

## Verdict: DO NOT MIGRATE

**Blocking gaps**:
1. No snapshot/refs system — would lose 93% token efficiency (cost-critical)
2. storageState crashes — session persistence is a hard requirement
3. File uploads not supported
4. SPA support uncertain
5. Stability insufficient for autonomous operation
6. Playwright connectOverCDP has active bugs

**What we'd gain**: 9x less memory (~24 MB vs 200-300 MB), instant startup — compelling on NUC hardware.

**What we'd lose**: Token efficiency, session persistence, file uploads, screenshots, SPA compatibility, stability.

## Recommendation

**Monitor and reassess in 6-12 months.** Watch for:
1. storageState fix (#1550)
2. Playwright CDP stability (#1800)
3. Segfault frequency drop (#1304)
4. SPA maturity (#1798)
5. File upload support (#1203)

Most realistic future integration: **third engine** in `clarvis_browser.py` for lightweight fetch/extract, not a replacement. Keep Playwright+Chromium for auth-heavy, SPA, and upload workflows. Keep Agent-Browser for token-efficient interaction.

## Brain Memories

- Lightpanda: Zig-based headless browser, 9x less memory, 11x faster, but beta stability
- AGPL-3.0 license: safe as separate CDP process, problematic if embedded as library
- No snapshot/refs equivalent — cannot replace Agent-Browser token efficiency
- storageState crashes (#1550) — cannot persist auth sessions
- Reassess in 6-12 months when stability and Playwright compat mature
