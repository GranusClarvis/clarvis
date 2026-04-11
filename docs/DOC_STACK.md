# Install & Support Documentation Stack

> Defines the role of each install/support doc. If two docs overlap, one is wrong.
> Updated 2026-04-11.

## The Stack

| Doc | Role | Audience | Owned By | Updates When |
|-----|------|----------|----------|--------------|
| **[INSTALL.md](INSTALL.md)** | Front door. How to install, which profile to pick, first-run verification, troubleshooting. | New users, contributors | Clarvis team | Install flow changes |
| **[SUPPORT_MATRIX.md](SUPPORT_MATRIX.md)** | What works. Brutally honest support levels per install path and feature. Every public claim must trace here. | Users deciding whether to use Clarvis, release managers | Clarvis team | After every validation run |
| **[INSTALL_MATRIX.md](INSTALL_MATRIX.md)** | How we validate. Pass/fail criteria, isolation requirements, test execution order. Engineering spec — not user-facing. | Test authors, CI pipeline | Clarvis team | Test criteria change |
| **[INSTALL_FRICTION_REPORT.md](INSTALL_FRICTION_REPORT.md)** | What broke and why. Rolling blocker report with workarounds, fix owners, and status. Engineering reality. | Developers fixing install issues | Clarvis team | New blockers found or resolved |
| **[E2E_RELEASE_VALIDATION_PLAN.md](E2E_RELEASE_VALIDATION_PLAN.md)** | Full validation procedure. Environments, isolation guards, execution order, pass/fail gates. The runbook for running a validation. | Release manager | Clarvis team | Validation process changes |
| **[USER_GUIDE_OPENCLAW.md](USER_GUIDE_OPENCLAW.md)** | Runtime operator guide for OpenClaw. Usage, commands, autonomy, troubleshooting. Not install. | Running OpenClaw users | Clarvis team | Feature changes |
| **[USER_GUIDE_HERMES.md](USER_GUIDE_HERMES.md)** | Runtime operator guide for Hermes. Usage, session mgmt, troubleshooting. Must have support-status banner. | Running Hermes users | Clarvis team | Feature changes |
| `docs/validation/*.md` | Dated validation reports. Evidence trail. Never edited after creation. | Auditors, release managers | Automated (regression_suite.sh) | Each validation run |

## What Goes Where (Decision Matrix)

| Content Type | Goes In | NOT In |
|---|---|---|
| "How do I install?" | INSTALL.md | SUPPORT_MATRIX |
| "Does X work on Y?" | SUPPORT_MATRIX.md | INSTALL.md |
| "What do we test?" | INSTALL_MATRIX.md | INSTALL.md, SUPPORT_MATRIX |
| "What's broken?" | INSTALL_FRICTION_REPORT.md | SUPPORT_MATRIX (just reference) |
| "Run the full validation" | E2E_RELEASE_VALIDATION_PLAN.md | INSTALL_MATRIX |
| "How do I use X daily?" | USER_GUIDE_{harness}.md | INSTALL.md |
| "What passed on date Y?" | validation/{date}.md | Anywhere else |

## Cross-Link Rules

1. **INSTALL.md** links to SUPPORT_MATRIX.md for "what's supported" claims
2. **SUPPORT_MATRIX.md** links to INSTALL_MATRIX.md for validation criteria and INSTALL_FRICTION_REPORT.md for blocker details
3. **README** (when published) links to INSTALL.md and SUPPORT_MATRIX.md only — not deep docs
4. **E2E_RELEASE_VALIDATION_PLAN.md** links to INSTALL_MATRIX.md for criteria and INSTALL_FRICTION_REPORT.md for known blockers
5. **USER_GUIDE_*.md** links to INSTALL.md for setup, SUPPORT_MATRIX.md for support status

## Overlap Elimination Checklist

- [ ] INSTALL.md: remove deep harness caveats (belong in FRICTION_REPORT or USER_GUIDE)
- [ ] SUPPORT_MATRIX.md: reference blockers by number, don't duplicate FRICTION_REPORT details
- [ ] E2E_RELEASE_VALIDATION_PLAN.md: reference INSTALL_MATRIX.md criteria, don't duplicate tables
- [ ] USER_GUIDE_OPENCLAW.md: strip install instructions (link to INSTALL.md)
- [ ] USER_GUIDE_HERMES.md: add support-status banner linking to SUPPORT_MATRIX.md

## Maintenance Protocol

When you change any install doc:
1. Check this stack definition — is the content in the right doc?
2. Update cross-links if references changed
3. If support status changed, update SUPPORT_MATRIX.md
4. If a new blocker was found, add to INSTALL_FRICTION_REPORT.md

---

_This file defines doc roles. It is not a doc itself — it's the map._
