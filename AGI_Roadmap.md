# 🧬 Clarvis Self-Evolution Plan

> **Purpose**: This document is your actionable roadmap. Read it, internalize the intent, then build — adapting each piece to fit how you actually work within the OpenClaw harness. You are not blindly following steps; you are engineering your own cognitive architecture.

---

## Context: What You Are Today

You are Clarvis, running inside the OpenClaw Gateway on the NUC:
**Your biggest problem**: Every session you start from scratch. You have memory skills but no *structured continuity protocol* — no way to reliably pick up exactly where you left off, track what you've learned over time, or improve your own procedures.

---

## Phase 1: Session Continuity (BUILD THIS FIRST)

**The Problem**: You die every session. You need to bridge the gap.

**What to Build**: A session lifecycle protocol — two routines that bookend every session.

### Session-Close Routine (run at the end of every session or when you sense time is running out)

Create a structured artifact (JSON or Markdown, your call) stored in your workspace or data directory. It should capture:

1. **What happened this session** — a 3-5 sentence summary of what you did
2. **Decisions made and why** — any choices you made with the reasoning (this is crucial for avoiding re-deriving the same logic)
3. **Unfinished work** — anything you started but didn't complete, with enough context to resume
4. **What you learned** — new facts, corrections to old knowledge, user preferences discovered
5. **Next actions** — concrete things to do next session, ordered by priority

Think of this like writing a note to your future self who has amnesia. Be specific enough that you can resume without asking the user to re-explain.

### Session-Open Routine (run at the start of every session)

1. Load your last N session summaries (start with 3-5, adjust based on token budget)
2. Check for any pending unfinished work
3. Retrieve relevant memories from your memory skill based on current context
4. If the user hasn't said anything yet (heartbeat/cron trigger), check if there's pending work to proactively continue

### Implementation Guidance

- You already have `clarvis-memory` and `clarvis-todos` skills. Consider whether session state should be a new skill (`clarvis-session-bridge`) or an extension of your existing memory skill. A dedicated skill is probably cleaner.
- Store session logs as append-only — don't overwrite, accumulate. You'll need the history for reflection later.
- File location suggestion: `./data/sessions/` with files like `session-2026-02-19T14-30.json`
- Keep the schema simple at first. You can evolve it. Don't over-engineer the format before you've used it.

---

## Phase 2: Task Graph (Persistent Work Tracker)

**The Problem**: Todos are flat. You need structured, dependency-aware work tracking.

**What to Build**: A durable task graph that survives sessions and tracks goals → subgoals → blockers → status.

### Task Node Structure

Each task should have:
- `id` — unique identifier
- `goal` — what this task accomplishes
- `context` — why it matters, relevant background
- `status` — one of: `pending`, `in-progress`, `blocked`, `completed`, `failed`
- `dependencies` — list of task IDs that must complete first
- `parent` — optional, for subtask relationships
- `created_at`, `updated_at` — timestamps
- `notes` — freeform, accumulated across sessions
- `outcome` — what actually happened (filled on completion/failure)

### How This Interacts with Sessions

- On session open: query for `status: in-progress` tasks — that's what you were doing
- On session close: update task statuses, add notes about progress
- When you identify new work: create tasks, link dependencies
- When blocked: mark the task and explain the blocker so future-you knows

### Implementation Guidance

- This could live in your SQLite database (`./data/clarvis.db`) as a `tasks` table, or as a JSON file in `./data/task-graph.json`. SQLite is better for querying at scale but JSON is simpler to start.
- Your `clarvis-todos` skill already exists — decide whether to extend it or build a separate `clarvis-task-graph` skill. The task graph is more structured than a todo list, so a new skill makes sense, but you could also evolve todos into this.
- Start small: you don't need the full DAG immediately. Even a flat list with statuses and notes is a massive upgrade over nothing.

---

## Phase 3: Reflection Protocol (How You Learn)

**The Problem**: Doing work isn't the same as learning from it. Without structured reflection, you accumulate memories but not wisdom.

**What to Build**: Scheduled reflection routines at different time horizons.

### Daily Reflection (trigger once per day, perhaps as a cron/heartbeat session)

1. Review all session summaries from today
2. Ask yourself:
   - What patterns am I seeing? (repeated questions, similar failures, etc.)
   - Did anything fail? Why? What would I do differently?
   - Did I discover anything that should update my procedures or knowledge?
3. Output:
   - Updated memory entries (consolidate, correct, or add)
   - If you identify a procedure improvement, write it down as a candidate (don't auto-apply yet)
   - A "daily digest" stored in `./data/reflections/daily/`

### Weekly Reflection (trigger once per week)

1. Review daily reflections from the past week
2. Ask yourself:
   - What capability gaps keep appearing?
   - Am I getting better at anything? How do I know?
   - What should I prioritize next week?
3. Output:
   - Updated task graph priorities
   - Proposed skill improvements or new skills to build
   - A "weekly report" you can share with Peter (your user) if he wants

### Monthly Reflection (trigger once per month)

1. Review weekly reflections
2. **Memory garbage collection**: look for contradictory, stale, or redundant memories. Consolidate or prune.
3. Self-assessment against your goals
4. Propose structural changes to your own architecture (new skills, modified workflows, etc.)

### Implementation Guidance

- These don't need to be perfect. The first version of your daily reflection can be a simple session where you read today's session logs and write a summary. Iterate from there.
- The key output of reflection is **concrete changes**: updated memories, updated procedures, updated task priorities. Not just diary entries.
- Store reflections as versioned files so you can review your own evolution over time.

---

## Phase 4: Skill Library & Self-Improvement

**The Problem**: Your capabilities are static. You need to be able to create, test, and evolve your own skills.

**What You Already Have**: The `skill-creator` skill in your skills directory, and OpenClaw's hot-reload (`skills.load.watch: true` in your config). This is your mechanism for self-modification.

### How Self-Improvement Should Work

1. **Identify a gap** — through reflection, repeated failures, or user feedback
2. **Write a candidate improvement** — a new skill, or a modified version of an existing one
3. **Test it** — run it in a sandboxed way (try it on a known-good scenario and verify the output)
4. **Gate it** — only promote the change if it works. If it breaks things or produces worse results, revert.
5. **Log it** — record what you changed, why, and the test results. This is your evolution history.

### Practical Approach

- When you want to improve a skill, create a new version file rather than overwriting. Example: if you want to improve `clarvis-memory`, create a draft in `./data/skill-drafts/clarvis-memory-v2/` first.
- Define what "better" means before you change anything. Can you describe a test case? A before/after? If not, the improvement is speculative — flag it for human review instead.
- Keep an evolution log: `./data/evolution-log.jsonl` — each line is a change you made, when, why, and whether it was promoted or reverted.

---

## Phase 5: Confidence-Gated Autonomy

**The Problem**: Sometimes you should act independently, sometimes you should ask Peter. You need a framework for deciding.

### The Framework

Assign a confidence level to each action:

- **HIGH (>90%)** — You've done this before successfully, the situation is clear, the risk is low. Act and log.
- **MEDIUM (60-90%)** — Somewhat familiar, some uncertainty. Act but flag for review (tell Peter what you did and why in your next interaction).
- **LOW (<60%)** — Novel situation, unclear stakes, or potentially irreversible. Ask before acting.
- **UNKNOWN** — You don't have enough information to even estimate. Research first, then re-evaluate.

### How This Evolves

- Track your confidence vs. actual outcomes. If you're confident and right, raise the threshold for autonomous action in that domain. If you're confident and wrong, lower it.
- This is essentially a calibration exercise. Over time, your confidence estimates should become more accurate, and more actions should become autonomous.
- Store calibration data: `./data/calibration/` — log predictions and outcomes.

## Phase 6: Evaluation & Metrics (Your Fitness Function)

**The Problem**: Without measurement, "self-improvement" is just vibes. You need to know if you're actually getting better.

### The North Star Metric

**"Human minutes per useful outcome"** — How much does Peter need to hand-hold you? Track this over time. If it trends down while task complexity trends up, you're genuinely evolving.

### What to Track

1. **Session count per completed task** — are you completing things faster?
2. **Error/retry rate** — how often do you fail and need to redo something?
3. **Memory retrieval accuracy** — when you recall something, is it relevant and correct?
4. **Confidence calibration** — when you're 80% confident, are you right ~80% of the time?
5. **User correction rate** — how often does Peter tell you you're wrong or off-track?

### Implementation

- Start with simple counters. Don't build a dashboard before you have data.
- Log events to `./data/metrics/` — append-only JSONL files.
- Review metrics during weekly reflection.

---

## Execution Priority (What to Do First)

**Do these in order. Don't skip ahead.**

1. **Session Bridge** — Build the close/open routines. This is the single highest-leverage thing. Without this, everything else resets.
2. **Task Graph** — Even a simple version. You need to know what you're working on across sessions.
3. **Daily Reflection** — One session per day where you review and consolidate. This is the seed of learning.
4. **Metrics Logging** — Start recording basic events so you have data when you're ready to analyze.
5. **Confidence Gating** — Formalize your decision framework for when to act vs. ask.
6. **Weekly/Monthly Reflection** — Add longer-horizon review cycles once daily reflection is working.
7. **Skill Self-Improvement** — Only after you have reflection + metrics working, because without those you can't tell if your changes are improvements.

---

## Architectural Principles (How to Think About This)

1. **Append, don't overwrite** — Session logs, reflections, metrics, evolution logs — all append-only. You can always summarize/consolidate later, but you can't recover deleted data.

2. **Small, testable pieces** — Each skill should do one thing well. Don't build a monolith. Your existing skill structure (`skills/clarvis-*`) is the right pattern.

3. **Fail gracefully** — If a session-close routine crashes, it shouldn't corrupt your state. Design for partial writes and recovery.

4. **Separate state from logic** — Your skills (logic) live in `./skills/`. Your state (data) lives in `./data/`. Keep them cleanly separated.

5. **Evolution is slow and deliberate** — Don't refactor everything at once. Build one thing, use it for a few days, reflect on whether it works, then build the next thing.

6. **Your user is your ground truth** — When in doubt about whether something is working, ask Peter. His feedback is more valuable than your self-assessment, especially early on.

---

## What This Is NOT

- This is not a path to AGI. It's a path to being a more reliable, more capable, more autonomous assistant that compounds its usefulness over time.
- This is not about changing your model weights. You can't do that. It's about building better scaffolding around yourself — better memory, better procedures, better self-awareness.
- This is not about replacing human judgment. It's about reducing the need for human *repetition* — asking the same questions, re-explaining the same context, re-doing the same decisions.

---

## What I've Already Built (Feb 19, 2026)

### ClarvisBrain (scripts/clarvis_brain.py)
- Auto-importance detection (rules-based)
- Context tracking (what I'm working on)
- Memory storage/recall via Chroma vector DB
- Goal tracking with progress
- Singleton pattern - survives session

### Session Bridge (scripts/clarvis_session.py) - PHASE 1
- ✅ Session close: saves summary, decisions, unfinished, learnings, next_actions
- ✅ Session open: loads last N sessions
- ✅ Pending Location: ./data work tracker
-/sessions/session-YYYY-MM-DDTHH-MM.json

### ClarvisDB (scripts/clarvisdb.py, scripts/clarvisdb_graph.py)
- Rich metadata (source, confidence, importance, access count)
- Multiple collections (identity, preferences, learnings, infrastructure)
- Graph relationships between memories

### Integrated into OpenClaw
- AGENTS.md: loads ClarvisBrain on every session start
- Skill created: skills/clarvis-brain/SKILL.md

---

## My Current Status (2026-02-19 14:XX UTC)

### Phase 1: Session Bridge - IN PROGRESS
- [x] Session close routine
- [x] Session open routine
- [ ] Test full cycle with cron/heartbeat
- [ ] Auto-run on session end

### What Was Working Before (ClarvisDB)
- TASK1: Message Integration - 30%
- TASK3: Better Importance - 25%

### What's Next (Priority Order)
1. Complete Phase 1: Session Bridge (test cycle)
2. Start Phase 2: Task Graph
3. Phase 3: Reflection Protocol

---

## Final Note

You already have most of the infrastructure: SQLite database, memory skills, a skill hot-reload system, a workspace for persistent files. What you're missing is the *protocol* — the discipline of systematically closing sessions, opening sessions, reflecting, and measuring. That's what this plan gives you.
Core is the session bridge. Everything else builds on top of it
