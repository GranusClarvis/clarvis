# Marathon Stop Report

**Date:** 2026-03-05T23:42:30Z
**Batch:** 1
**Reason:** Invariants failed after 2 self-heal attempts

## Batches Completed
Batch 1: SUCCESS [CLI_BRAIN_LIVE,CLI_SUBPKG_ABSORB,CLI_BENCH_EXPAND] (5m)

## Last Invariants Output
```
[hooks] Registered 7/7 hooks
=== Invariants Check ===
  [PASS] pytest (75.2s)
  [PASS] golden-qa (7.7s)
  [PASS] graph-verify (0.0s)
  [PASS] brain-health (6.2s)
  [PASS] hook-count (0.0s)

Overall: PASS (89.1s)
{
  "ts": "2026-03-05T23:42:27.287344+00:00",
  "passed": true,
  "elapsed_s": 89.147,
  "checks": [
    {
      "name": "pytest",
      "passed": true,
      "elapsed_s": 75.215,
      "exit_code": 0,
      "summary": "106 passed in 73.99s (0:01:13)"
    },
    {
      "name": "golden-qa",
      "passed": true,
      "elapsed_s": 7.739,
      "precision_at_3": 1.0,
      "hits": 25,
      "total": 25
    },
    {
      "name": "graph-verify",
      "passed": true,
      "elapsed_s": 0.0,
      "detail": "skipped (backend=json)"
    },
    {
      "name": "brain-health",
      "passed": true,
      "elapsed_s": 6.192,
      "status": "healthy",
      "collections": 10
    },
    {
      "name": "hook-count",
      "passed": true,
      "elapsed_s": 0.0,
      "total": 7,
      "breakdown": {
        "scorers": 1,
        "boosters": 2,
        "observers": 3,
        "optimize": 1
      },
      "minimum": 5
    }
  ],
  "backend": "json"
}
```

## Action Required
1. Run `python3 scripts/invariants_check.py`
2. Fix failing checks
3. Restart marathon
