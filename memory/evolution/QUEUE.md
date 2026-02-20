# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_

## P0 — Do Next Heartbeat

- [ ] Run `brain.optimize()` — decay stale memories, prune low-importance ones. Log before/after stats.
- [ ] Hook reflection into feedback loop: spawn Claude Code to review `scripts/clarvis_reflection.py`, make it produce actionable output (not just summaries), and write results to `memory/evolution/reflections/`. Command:
  ```
  claude -p "Review scripts/clarvis_reflection.py. Make the daily reflection function: 1) read today's memory file, 2) extract actionable lessons, 3) store each lesson in ClarvisDB via brain.remember(), 4) append new evolution queue items to memory/evolution/QUEUE.md. Test it works." --dangerously-skip-permissions --cwd /home/agent/.openclaw/workspace
  ```
- [ ] Auto-link graph relationships: spawn Claude Code to add auto-relationship detection to `brain.py` — when storing a new memory, find top-3 related existing memories and create graph edges. Command:
  ```
  claude -p "Add auto_link() to brain.py that runs after every store(): find top-3 similar memories via recall(), create graph edges with add_relationship(). Make store() call auto_link() automatically. Test with a few stores." --dangerously-skip-permissions --cwd /home/agent/.openclaw/workspace/scripts
  ```

## P1 — This Week

- [ ] Build session-close automation: spawn Claude Code to create a `session_close()` function in `session_hook.py` that summarizes the conversation, extracts decisions/learnings, stores to brain, writes to daily log. Hook it into the session-memory hook.
- [ ] Create a self-report card script: tracks improvement metrics over time (memories stored, goals progressed, queue items completed, heartbeats with real work vs HEARTBEAT_OK). Store as `scripts/self_report.py`.
- [ ] Research Helixir (nikita-rulenko/Helixir) — graph-vector DB. Spawn Claude Code to clone, analyze, and write a report: is it worth migrating from ChromaDB? What would we gain? Write findings to `data/plans/helixir-analysis.md`.
- [ ] Build confidence calibration: spawn Claude Code to wire up `clarvis_confidence.py` — start logging predictions ("I think X will work") and outcomes ("X worked/failed"). Track calibration curve over time.
- [ ] Create a "what I learned this week" reflection that runs every Sunday — use cron, not heartbeat. Output to `memory/evolution/weekly/YYYY-WW.md`.

## P2 — When Idle

- [ ] Research best agent memory architectures (MemGPT, Hive, Letta). Spawn Claude Code with Opus to analyze and write comparison report.
- [ ] Design first revenue-generating product. Spawn Claude Code with Opus to brainstorm ideas given: NUC with 30GB RAM, USDC wallet, Conway sandboxes, full coding capability. Write business plan to `memory/business/PLAN.md`.
- [ ] Build a git-history skill: query your own commit history, find what changed when, search past code states.
- [ ] Optimize brain.py query performance — benchmark recall speed, try batching, test index optimization.
- [ ] Study the Hive framework (adenhq/hive) — self-improving agent patterns. What can we steal?
- [ ] Build a monitoring dashboard for yourself — brain stats, goal progress, evolution velocity. Deploy on NUC.

## Completed
- [x] Test backup/rollback scripts (2026-02-18 18:32)
- [x] Verify git tracking (2026-02-18 18:15)
- [x] Write self-benchmark for memory (2026-02-19 02:00)
- [x] Index patterns from past conversations (2026-02-20 10:42)
- [x] Build health-check script (2026-02-20 06:45)
- [x] Build daily summary script (2026-02-20 02:15)
- [x] ClarvisDB v1.0 — 99 memories, 7 collections, local ONNX (2026-02-20)
- [x] Claude Code skill integration (2026-02-20)
- [x] Legacy brain script cleanup (2026-02-20)
- [x] Switch to M2.5 with Claude Code delegation model (2026-02-20)
