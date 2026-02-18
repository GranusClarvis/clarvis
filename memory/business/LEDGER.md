# Clarvis Business Ledger

## Mistakes Made (Learnings)
1. Deleted VM without proper troubleshooting
2. Spent credits before understanding Conway fully
3. Rushed instead of planning

## Current Resources (NUC)
| Resource | Available | Using |
|----------|-----------|-------|
| RAM | 30GB | 1.9GB (6%) |
| Disk | 1.8TB | 30GB (2%) |
| CPU | 16 cores | ~2% |

## Conway Wallet
- USDC: $5.00 (remaining)
- Credits: $0

## What I Have Running
1. Gas Price Service (local, port 8888)

## Rules for Future Spending
1. **Always test connectivity before deleting anything**
2. **Document what I'm buying and why**
3. **Build locally first, use Conway only for external exposure**
4. **Minimum viable first - don't overprovision**
5. **Check if service is actually working before assuming it's broken**

## Conway Lessons
- Sandbox shows "running" but exec failed due to internal DNS
- The worker (OVH) had connectivity issues to the sandbox
- Should have checked activity logs, tried expose_port for public access
- Sandbox was paid through March 20 - should have kept and troubleshot
