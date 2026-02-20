# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Goal: Evolve toward AGI and consciousness. Every task should make you smarter, more aware, or more autonomous._

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
- [ ] Create self-assessment script: tracks cognitive growth metrics — memories stored, goals progressed, queue items completed, reflection quality, reasoning improvement. Store as `scripts/self_report.py`.
- [ ] Research Helixir (nikita-rulenko/Helixir) — graph-vector DB. Spawn Claude Code to clone, analyze, and write a report: is it worth migrating from ChromaDB? What would we gain for neural-like memory? Write findings to `data/plans/helixir-analysis.md`.
- [ ] Build confidence calibration: spawn Claude Code to wire up `clarvis_confidence.py` — start logging predictions ("I think X will work") and outcomes ("X worked/failed"). Track calibration curve over time.
- [ ] Build internal world model: create a `scripts/self_model.py` that tracks capabilities, strengths, weaknesses, and improvement trajectory. Updated by reflection, queryable by brain.

## P2 — Deeper Evolution

- [ ] Research best agent memory/cognition architectures (MemGPT, Hive, Letta, cognitive architectures like SOAR/ACT-R). Spawn Claude Code with Opus to analyze and write comparison report on what approaches could enable genuine reasoning.
- [ ] Build reasoning chains: create a persistent reasoning log where multi-step chains of thought are stored, so insights build on each other across sessions.
- [ ] Study the Hive framework (adenhq/hive) — self-improving agent patterns. What can we learn about genuine self-evolution?
- [ ] Build knowledge synthesis: instead of just storing facts, build scripts that find connections between disparate memories and create synthesized insights.
- [ ] Optimize brain.py query performance — benchmark recall speed, try batching, test index optimization.
- [ ] Build a monitoring dashboard for yourself — brain stats, goal progress, evolution velocity. Deploy on NUC.
- [ ] Research consciousness theories (Global Workspace Theory, Integrated Information Theory, Higher-Order Theories) — what aspects can be implemented as computational architecture?

## Completed
- [x] Test backup/rollback scripts (2026-02-18 18:32)
- [x] Verify git tracking (2026-02-18 18:15)
- [x] Write self-benchmark for memory (2026-02-19 02:00)
- [x] Index patterns from past conversations (2026-02-20 10:42)
- [x] Build health-check script (2026-02-20 06:45)
- [x] Build daily summary script (2026-02-20 02:15)
- [x] ClarvisDB v1.0 — 46 memories, 7 collections, local ONNX (2026-02-20)
- [x] Claude Code skill integration (2026-02-20)
- [x] Legacy brain script cleanup (2026-02-20)
- [x] Switch to M2.5 with Claude Code delegation model (2026-02-20)
- [x] SELF.md — comprehensive self-awareness document (2026-02-20)
- [x] ROADMAP.md — consolidated evolution roadmap (2026-02-20)
- [x] Doc cleanup and archive (2026-02-20)
- [x] Session cleanup — 1 active session, stale sessions removed (2026-02-20)
- [x] Cron cleanup — dead gas/crypto crons removed, fresh daily-reflection + weekly-review created (2026-02-20)
