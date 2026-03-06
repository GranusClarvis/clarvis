# Marathon Stop Report

**Date:** 2026-03-06T00:03:57Z
**Batch:** 1
**Reason:** invariants_check.py could not be parsed as PASS after 2 self-heal attempts

## Batches Completed
Batch 1: SUCCESS [CLI_BRAIN_LIVE,CLI_SUBPKG_ABSORB,CLI_BENCH_EXPAND] (6m)

## Last Invariants Output
```
[hooks] Registered 7/7 hooks
=== Invariants Check ===
  [PASS] pytest (73.0s)
  [PASS] golden-qa (7.4s)
  [PASS] graph-verify (0.0s)
  [PASS] brain-health (11.1s)
  [PASS] hook-count (0.0s)

Overall: PASS (91.5s)
{
  "ts": "2026-03-06T00:03:54.531402+00:00",
  "passed": true,
  "elapsed_s": 91.477,
  "checks": [
    {
      "name": "pytest",
      "passed": true,
      "elapsed_s": 72.953,
      "exit_code": 0,
      "summary": "106 passed in 71.69s (0:01:11)"
    },
    {
      "name": "golden-qa",
      "passed": true,
      "elapsed_s": 7.443,
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
      "elapsed_s": 11.081,
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
