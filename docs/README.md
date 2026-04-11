# Documentation

Public documentation for the Clarvis project.

## Structure

| File | Purpose |
|------|---------|
| `ARCHITECTURE.md` | System architecture overview |
| `INSTALL.md` | Installation guide (all supported paths) |
| `INSTALL_MATRIX.md` | Validation criteria for install paths |
| `INSTALL_FRICTION_REPORT.md` | Known install friction points |
| `RUNBOOK.md` | Operator runbook |
| `USER_GUIDE_OPENCLAW.md` | OpenClaw runtime guide |
| `USER_GUIDE_HERMES.md` | Hermes runtime guide |
| `CONVENTIONS.md` | Code conventions |
| `STYLEGUIDE.md` | Style guide |
| `DATA_LAYOUT.md` | Data directory layout |
| `SAFETY_INVARIANTS.md` | System invariants and safety guarantees |
| `REPO_BOUNDARY.md` | Repository boundaries and anti-sprawl policy |
| `GRAPH_SQLITE_CUTOVER_2026-03-29.md` | Graph backend migration reference |
| `UPDATE_PROCEDURE.md` | Update procedure |
| `WHAT_IS_CLARVIS.md` | Project overview / positioning |
| `LAUNCH_PACKET.md` | Launch checklist |
| `DASHBOARD.md` | Dashboard specification |
| `DO_NOT_TOUCH_REGISTRY.md` | Protected files registry |
| `RESEARCH_REOPEN_POLICY.md` | Research reopen policy |

## Internal Docs

`internal/` contains operator-only and historical documents not intended for the public repo surface:

- `internal/planning/` - Strategy, migration plans, execution checklists
- `internal/execution-reports/` - Spine migration and phase execution reports
- `internal/audits/` - One-off audit artifacts, queue triage, investigations
- `internal/swo/` - SWO brand integration planning
- `internal/review/` - Quality review passes
- `internal/subagents/` - Sub-agent specifications

These files are kept for historical reference but should not clutter the root docs surface.
