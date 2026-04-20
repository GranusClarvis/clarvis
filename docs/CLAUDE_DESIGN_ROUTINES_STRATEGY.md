# Claude Design & Routines — Cross-Project Operating Model

_Created 2026-04-20. Strategy for integrating Claude Design and Claude Code Routines into Clarvis's workflow, applicable to Clarvis itself and project work (SWO, future repos)._

---

## 1. Feature Summary

### Claude Design (launched 2026-04-17)
- AI-powered visual design tool on claude.ai — generates interactive prototypes, mockups, wireframes, pitch decks from natural language
- **Handoff bundle**: packages design specs, brand tokens, component structure → feeds directly into Claude Code for pixel-perfect implementation
- **Design system extraction**: reads your codebase to auto-generate consistent design system (colors, typography, components)
- **Export**: PDF, PPTX, Canva, HTML, shareable URLs, ZIP
- **Limits**: Weekly allowance per plan tier (Pro/Max/Team). No standalone API — automation is through the handoff-to-Code pipeline
- **Key constraint**: UI tool only, no headless/API automation. Operator-driven.

### Claude Code Routines (launched 2026-04-14)
- Saved Claude Code configurations that run on Anthropic's cloud (no laptop required)
- **Triggers**: scheduled (cron, min 1h interval), API endpoint (POST with bearer token), GitHub webhooks (PR events, releases)
- **Limits**: Pro 5/day, Max 15/day, Team/Enterprise 25/day. Shared pool with interactive usage.
- **Capabilities**: full shell, MCP connectors (Slack, Linear, etc.), fresh repo clone per run, pushes to `claude/*` branches by default
- **Key constraint**: no local filesystem access (fresh clone each time), no permission prompts, min 1h interval for scheduled

---

## 2. Current Clarvis Automation Landscape

| Capability | Current Solution | Runs/day |
|---|---|---|
| Autonomous evolution | crontab → cron_autonomous.sh → Claude Code | 12 |
| PR creation | spawn_claude.sh (local) | ad-hoc |
| Code review | Manual or spawned Claude session | ad-hoc |
| Health monitoring | health_monitor.sh (no LLM) | 96 (every 15m) |
| Visual dashboard | PixiJS dashboard (port 18799) | live SSE |
| Design/UI work | None automated | — |
| Post-merge checks | None | — |
| Docs drift | None | — |

**Key insight**: Clarvis already has a mature local cron system (52 jobs). Routines don't replace it — they complement it for tasks that benefit from cloud execution, GitHub-event triggers, or MCP connectors.

---

## 3. General Strategy: When to Use What

### Decision Framework

```
Is it a visual/UI design task?
  ├─ YES: Does it need interactive iteration with operator?
  │   ├─ YES → Claude Design (operator-driven session)
  │   └─ NO → Code-first (Claude Code generates UI from specs/components)
  └─ NO: Is it triggered by a GitHub event (PR, release)?
      ├─ YES → Claude Code Routine (GitHub webhook trigger)
      └─ NO: Does it need local filesystem, brain, or ChromaDB?
          ├─ YES → Local cron (existing system)
          └─ NO: Is it a scheduled review/audit of a remote repo?
              ├─ YES → Claude Code Routine (scheduled trigger)
              └─ NO → Local cron or ad-hoc spawn
```

### The Three Lanes

| Lane | Tool | When | Examples |
|---|---|---|---|
| **Design Lane** | Claude Design | Operator wants to explore UI concepts, iterate on layouts, create design systems, prepare handoff bundles | SWO sanctuary UI redesign, new dashboard layout, marketing assets, pitch decks |
| **Event Lane** | Routines (webhook) | React to GitHub events autonomously | PR review on open, post-merge smoke check, release changelog, label triage |
| **Schedule Lane** | Routines (cron) or local cron | Recurring maintenance/review tasks | Weekly docs drift check, nightly issue triage, dependency audit |

### Design Lane Policy

1. **Claude Design is operator-initiated** — never automate design generation. The operator opens a Design session when they want to explore UI directions.
2. **Handoff protocol**: Operator produces design in Claude Design → exports handoff bundle → feeds to Claude Code (or Routine) for implementation.
3. **Design system extraction**: For each project repo, run Design's codebase analysis once to generate a design system. Store the resulting token file in the repo (`design/tokens.json` or equivalent). Update when major UI changes land.
4. **When NOT to use Design**: Internal Clarvis scripts, CLI tools, backend APIs, data pipelines. Design is for user-facing UI only.

### Event Lane Policy (Routines — Webhook Triggers)

Best-fit use cases for Routines, ranked by value:

1. **PR Review** (HIGH VALUE) — Trigger on PR opened/ready_for_review. Routine checks code quality, security patterns, test coverage, CLAUDE.md compliance. Posts inline comments + summary.
2. **Post-Merge Verification** (HIGH VALUE) — Trigger on PR merged to main/dev. Routine clones, builds, runs tests, reports failures to Slack/Telegram.
3. **Issue Triage** (MEDIUM VALUE) — Trigger on issue opened. Routine labels, assigns priority, links to related code.
4. **Release Notes** (MEDIUM VALUE) — Trigger on release created. Routine generates changelog from commits since last tag.

### Schedule Lane Policy (Routines — Cron Triggers)

Best-fit use cases:

1. **Docs Drift Detection** (HIGH VALUE) — Weekly. Routine compares API code with docs, flags stale references, opens update PRs.
2. **Dependency Audit** (MEDIUM VALUE) — Weekly. Check for outdated/vulnerable deps, open PR if safe updates available.
3. **Visual Regression Baseline** (MEDIUM VALUE) — After significant UI merges. Routine builds, screenshots key pages, compares against baseline.
4. **Stale Branch Cleanup** (LOW VALUE) — Monthly. List branches with no activity >30 days, notify.

### What Stays Local (Not Routines)

These tasks need local state (ChromaDB, brain, memory files, graph DB) and stay on local cron:

- All heartbeat/autonomous evolution cycles
- Brain maintenance (compaction, hygiene, vacuum)
- Performance benchmarking (needs local ChromaDB)
- Dashboard event emission
- Cost tracking (reads local API logs)
- Dream engine, reflection, cognitive workspace

---

## 4. Project Adaptation Pattern

### Generic Template (per-repo)

Each project that Clarvis manages gets a **Routine manifest** — a small config defining which Routines to create:

```yaml
# .clarvis/routines.yaml (lives in project repo)
project: star-world-order
routines:
  pr-review:
    trigger: github_webhook
    events: [pull_request.opened, pull_request.ready_for_review]
    filter:
      base_branch: [dev, main]
    prompt: |
      Review this PR for: security issues, type safety, test coverage,
      and compliance with project conventions in CLAUDE.md.
      Post inline comments for issues. Post a summary comment.
    connectors: [github]

  post-merge-verify:
    trigger: github_webhook
    events: [pull_request.closed]
    filter:
      merged: true
      base_branch: [dev, main]
    prompt: |
      Clone the repo, install deps, run the full test suite.
      If tests fail, open an issue with the failure details.
      If tests pass, post a checkmark comment on the merged PR.
    connectors: [github]

  docs-drift:
    trigger: schedule
    cron: "0 9 * * 1"  # Monday 9am
    prompt: |
      Compare API route handlers with docs/API.md.
      Flag any endpoints missing from docs or docs referencing removed endpoints.
      Open a PR if drift found.
    connectors: [github]

  weekly-triage:
    trigger: schedule
    cron: "0 10 * * 5"  # Friday 10am
    prompt: |
      Review all open issues. Add priority labels based on severity.
      Close issues that reference merged PRs. Post a triage summary.
    connectors: [github]
```

### SWO-Specific Adaptations

Given SWO's current state (9 merged PRs, 4 pending PRs, 7 open security findings):

| Routine | SWO-specific customization |
|---|---|
| PR review | Add: check for wallet auth patterns (SWO audit finding H-4), verify no `any` types (PR #182 pattern), check raffle randomness isn't using Math.random() |
| Post-merge verify | Add: `npm run build && npm test` + check that Supabase migrations are consistent |
| Security scan | Add: weekly scan for the specific vulnerability patterns from the 2026-04-19 audit (C-1, H-2, M-1, M-3, M-5, L-3) |
| Docs drift | Add: check `docs/DEPLOYED.md` against actual contract addresses on-chain |

### Clarvis-Internal Adaptations

For the Clarvis repo itself, Routines add value for:

| Routine | Purpose |
|---|---|
| Self-PR review | When Clarvis opens PRs against its own repo (rare but happens during audit phases) — Routine provides independent review |
| Spine test gate | Trigger on PR to `clarvis/` spine — run `pytest tests/` and report |
| QUEUE.md hygiene | Weekly scheduled — check for stale items, cap violations, missing source references |

---

## 5. Clarvis-Level Framework: Design vs Code-First vs Pixel-Art

| Scenario | Recommended Tool | Rationale |
|---|---|---|
| New UI feature exploration | Claude Design | Interactive iteration, multiple directions, operator decides |
| Implementing a designed UI | Claude Code (with handoff bundle) | Pixel-perfect from design specs |
| Internal dashboard changes | Code-first (Claude Code) | PixiJS dashboard is code-driven, no visual design phase needed |
| Marketing assets, pitch decks | Claude Design | Export to PDF/PPTX, no code needed |
| Pixel-art game assets (SWO) | Dedicated pixel-art tools (Aseprite/Piskel) or Claude Design for concepts | Design can explore directions; dedicated tools for final pixel art |
| API/backend work | Claude Code only | No visual component |
| CI/CD, infra, scripts | Claude Code or local cron | No visual component |

---

## 5b. Design Bridge Tool (Implemented)

Clarvis has an operational bridge tool for Claude Design:

```bash
# Decide whether a task needs Claude Design, code-first, or pixel-art tools
clarvis design decide --task "explore new homepage layouts"

# Generate a handoff pack (paste into Claude Design session)
clarvis design pack --project swo --task "redesign sanctuary staking page"

# Process a Design export back for implementation
clarvis design ingest --export /path/to/export.html --project swo

# List available project profiles
clarvis design projects
```

**Workflow:**
1. Operator or Clarvis runs `clarvis design decide` to classify the task
2. If Claude Design recommended: run `clarvis design pack` to generate the brief
3. Operator pastes the pack into a Claude Design session on claude.ai
4. Operator iterates in Design, then exports the handoff bundle
5. Run `clarvis design ingest` to analyze the export and flag off-palette colors
6. Claude Code implements from the ingested spec

**Module:** `clarvis/context/design_bridge.py` — profiles for SWO and Clarvis built-in, custom profiles via `data/design_bridge/profiles/<name>.json`.

---

## 6. Implementation Recommendations

### Phase 1: Immediate (this week)

**A. Set up SWO PR Review Routine** — highest immediate value. SWO has 4 open PRs (#177, #179, #180, #181) that need review, and future PRs will benefit from automated first-pass review.

**B. Set up SWO Post-Merge Verification Routine** — second highest value. Catches build/test regressions automatically.

### Phase 2: Near-term (next 2 weeks)

**C. Create the `.clarvis/routines.yaml` spec** — document the manifest format so any project Clarvis manages can declare its Routines.

**D. Set up Clarvis self-repo spine test Routine** — trigger on PRs touching `clarvis/`.

**E. First Claude Design session for SWO** — operator-driven exploration of Sanctuary UI direction, producing a design system + handoff bundle.

### Phase 3: Medium-term (month)

**F. Docs drift Routine for SWO** — weekly check of API docs vs actual routes.

**G. Weekly QUEUE.md hygiene Routine** — scheduled scan of queue health.

**H. Integration script** — `scripts/infra/routine_manager.py` that reads `.clarvis/routines.yaml` from a project repo and provisions Routines via the API (`POST /v1/claude_code/routines/{id}/fire`).

---

## 7. Budget & Capacity Analysis

### Routine Run Budget

Assuming Max plan (15 runs/day shared with interactive):

| Allocation | Runs/day | Purpose |
|---|---|---|
| Interactive Claude Code | 8 | Operator sessions, spawned tasks |
| SWO PR review | 2-3 | Triggered by PR events |
| SWO post-merge | 1-2 | Triggered by merges |
| Clarvis spine test | 0-1 | Rare, only on spine PRs |
| Scheduled (docs/triage) | 1 | Weekly, amortized ~0.14/day |
| **Buffer** | **2-3** | Headroom for spikes |

This fits within 15/day with comfortable margin. On light PR days, more budget available for interactive use.

### Design Budget

Weekly allowance (Max plan = 5x base). Reserve for:
- 1 major design exploration session per project per week
- Ad-hoc mockups as needed
- No automation drain (Design is operator-only)

---

## 8. What NOT to Do

1. **Don't migrate local cron to Routines** — Clarvis's 52 local cron jobs need ChromaDB, brain, local filesystem. Routines clone fresh repos with no local state. The local cron system is well-tuned and battle-tested.

2. **Don't automate Claude Design** — It's an interactive tool. Trying to script it defeats the purpose (operator iteration). Use it when you want to explore visual directions, not as a CI step.

3. **Don't over-provision Routines** — Start with 2-3 per project. Each run costs against the daily cap. Only add Routines when there's a clear, recurring need.

4. **Don't duplicate review logic** — If a Routine does PR review, don't also have local cron doing the same review. One authoritative reviewer per trigger.

5. **Don't use Routines for brain-dependent tasks** — Anything needing ChromaDB search, memory consolidation, or graph queries must stay local.
