# Research Review: msitarzewski/agency-agents

**Date**: 2026-03-06
**Repo**: https://github.com/msitarzewski/agency-agents
**Purpose**: Evaluate delegation/sub-agent orchestration patterns for Clarvis

## Summary

A collection of 55+ specialized AI agent personality definitions organized across 9 functional divisions (Engineering, Design, Marketing, Product, Project Management, Testing, Support, Spatial Computing, Specialized). Each agent is a structured markdown file defining identity, mission, workflows, deliverables, and success metrics. Designed for Claude Code — agents are loaded as personality/instruction files.

Key files examined:
- `/specialized/agents-orchestrator.md` — central orchestration agent (15.6KB)
- `/specialized/agentic-identity-trust.md` — cryptographic trust architecture (17.5KB)
- `/examples/nexus-spatial-discovery.md` — 8-agent parallel orchestration example (40.7KB)

## 3 Adoptable Patterns

### Pattern 1: Four-Phase Pipeline with Quality Gates & Bounded Retry

The orchestrator defines a rigid pipeline: **Planning → Architecture → Dev-QA Loop → Integration**. Each task must pass a quality gate before advancing. Failed tasks enter a bounded retry loop (max 3) with QA feedback fed back to the developer. After 3 failures, tasks are marked "blocked" — preventing infinite loops.

```
Phase 1: PM → task list
Phase 2: Architect → technical foundation
Phase 3: For each task:
           Developer(task) → EvidenceQA(result)
             PASS → next task
             FAIL → retry with feedback (max 3)
             3 FAILS → mark blocked, continue
Phase 4: Integration testing (all tasks must pass)
```

**Clarvis adaptation**: Add a `verify` phase after `project_agent.py` spawns — run automated checks (tests, lint, PR mergeable). On failure, re-spawn with failure feedback appended, up to 3 times. Track attempt count + last failure in agent's `data/`. Add `blocked` status alongside `success`/`failure`.

### Pattern 2: Convergent Independent Analysis with Cross-Agent Synthesis

Multiple specialized agents deployed **in parallel** on the same problem, each within its domain. A synthesis step identifies convergence points (high confidence), divergences (need human judgment), and unique insights.

The Nexus example deployed 8 agents simultaneously. Synthesis documented:
- 5 convergence points (e.g., "every agent independently arrived at 2D-first")
- 4 unresolved tensions presented as structured disagreements
- Unique domain insights only one specialist could produce

**Clarvis adaptation**: Add `parallel_analysis` mode. Spawn N agents with different role prompts against the same question. Each writes to `memory/parallel/<session-id>/<role>.json`. A `parallel_synthesis.py` reads all outputs, identifies convergence/divergence/unique insights. Valuable for `cron_evolution.sh` and `cron_strategic_audit.sh` — 3-4 parallel perspectives instead of one deep analysis.

### Pattern 3: Penalty-Based Trust Scoring with Outcome Verification

Agents maintain a quantitative trust score (starts 1.0, only decreases). Trust is never self-reported — computed exclusively from observable outcomes. Trust levels map to authorization tiers.

- Base score: 1.0
- Penalties: outcome failure (-0.4 × rate), scope violation (-0.3), timeout (-0.1)
- Tiers: HIGH (≥0.9, full autonomy), MODERATE (≥0.5, conditional), LOW (>0.0, review required)
- Slow recovery: +0.05 per success, capped at 1.0

**Clarvis adaptation**: Add `trust_score` to each project agent's metadata. After each spawn, apply penalties based on outcomes. Map trust to autonomy tiers (can push autonomously vs needs review). Log changes to `data/agent_trust_log.jsonl`.

## Verdict

Repository is primarily a prompt/personality library, not a framework. But the orchestration patterns (quality gates, parallel synthesis, trust scoring) are directly applicable to `project_agent.py`. Pattern 1 (retry with QA feedback) is the highest-impact adoption for Clarvis's agent orchestrator.
