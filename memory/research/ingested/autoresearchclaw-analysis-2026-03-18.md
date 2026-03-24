# AutoResearchClaw Analysis — Change Boundary for Clarvis Adaptation

Date: 2026-03-18
Source: https://github.com/aiming-lab/AutoResearchClaw
Task: [RESEARCH_REPO_AUTORESEARCHCLAW_1]

## What AutoResearchClaw Does

Fully autonomous 22-stage research pipeline: topic → literature discovery → hypothesis → experiment → analysis → paper. Key patterns:

- **Phased pipeline** (8 phases, 22 stages) with gate stages requiring approval
- **PROCEED/REFINE/PIVOT decision** at Stage 15 — autonomous evaluation of results that can loop back
- **MetaClaw Bridge** — cross-run learning: captures failure lessons, converts to reusable skills via LLM, injects into subsequent runs (+18.3% robustness)
- **Skill effectiveness tracking** — JSONL store correlating skills with stage outcomes, computing success rates
- **Multi-agent debate** — hypothesis generation and peer review use multi-perspective agents

## What's Useful for Clarvis (vs. over-engineering)

### High Value — Adapt Now

1. **Research-to-Action Output Format**: Clarvis research currently produces free-form notes in `memory/research/`. AutoResearchClaw's structured output pattern should be adapted so every research session produces:
   - Findings summary (what was learned)
   - Clarvis relevance assessment (how does this help?)
   - Concrete implementation steps (what to build/change)
   - Estimated effort (S/M/L)
   - Queue items (auto-propose via `queue_writer.py`)
   - Decision: APPLY (queue implementation) / ARCHIVE (store for reference) / DISCARD

2. **Cross-Run Lesson Store**: MetaClaw's `lesson_to_skill.py` + `skill_feedback.py` pattern maps directly to Clarvis's research pipeline. Track which research topics led to successful implementations vs. dead ends. Feed this back into future research prompt construction.

3. **Decision Gate Pattern**: The PROCEED/REFINE/PIVOT at a simpler scale — after research completes, auto-evaluate: did we learn something actionable? Should we queue follow-up research? Should we discard and move on?

### Medium Value — Later

4. **Skill effectiveness correlation**: Track which research-derived queue items actually get completed successfully. Feeds back to improve research topic selection.

5. **Multi-agent debate for synthesis**: `knowledge_synthesis.py` already does cross-domain connection finding. Could add a debate/critic step for higher-quality synthesis.

### Low Value — Skip

6. **Full 22-stage pipeline**: Clarvis doesn't write papers. The pipeline complexity is unnecessary.
7. **Sandbox experiment execution**: Clarvis already has Claude Code for code execution.
8. **Citation verification**: Not applicable — Clarvis doesn't produce academic papers.

## Change Boundary — Files to Modify/Create

### Modify (existing)

| File | Change | Why |
|------|--------|-----|
| `scripts/cron_research.sh` | Update RESEARCH_PROMPT (both bundle and deep-dive) to require structured JSON-like output with findings, relevance, implementation_steps, effort, queue_items, decision | Currently free-form; structured output enables automated research-to-action |
| `scripts/cron_research.sh` | Add post-research phase: parse output, auto-queue items via `queue_writer.py` if decision=APPLY | Currently no automated research-to-action bridge |

### Create (new, minimal)

| File | Purpose | Size |
|------|---------|------|
| `scripts/research_lesson_store.py` | JSONL-backed store tracking research outcomes (topic, decision, queue_items_generated, items_completed). CLI: `record`, `query`, `stats`, `inject` (returns lessons for prompt injection) | ~150 lines |

### No Change Needed

| File | Reason |
|------|--------|
| `scripts/queue_writer.py` | Already has the right API (`add_task()`) — just needs to be called from research postflight |
| `scripts/knowledge_synthesis.py` | Cross-domain synthesis is orthogonal; can be enhanced later |
| `scripts/research_crawler.py` | URL crawling is a separate concern; works fine as-is |
| `clarvis/brain/` | Brain storage API is sufficient |

## Implementation Plan (for tasks 2-4)

### Task 2 — Implement: Core Logic

1. Create `scripts/research_lesson_store.py`:
   - `ResearchLessonStore` class with JSONL backend at `data/research_lessons.jsonl`
   - `record(topic, decision, findings_summary, queue_items, outcome)`
   - `get_recent_lessons(n=5)` — returns formatted text for prompt injection
   - `stats()` — success rate, most productive topics, dead-end patterns

2. Update `scripts/cron_research.sh` research prompts:
   - Add structured output requirement (FINDINGS / RELEVANCE / STEPS / EFFORT / QUEUE_ITEMS / DECISION)
   - Add lesson injection: `PAST_LESSONS=$(python3 scripts/research_lesson_store.py inject)`
   - Add post-execution phase: parse output, call `queue_writer.py` for APPLY decisions, record lesson

### Task 3 — Test

- Unit test for `research_lesson_store.py` (record, query, stats, inject)
- Verify cron_research.sh prompt changes are syntactically valid (shellcheck)

### Task 4 — Verify

- Run existing tests (`packages/clarvis-db`)
- Dry-run research prompt extraction to confirm no regressions

## Risk Assessment

- **Duration risk**: Similar research tasks have timed out (1500s). Mitigate by keeping implementation focused on the lesson store + prompt changes only.
- **Shell quoting**: Injecting lesson text into bash prompts needs careful escaping. Use file-based prompt construction (already the pattern in `cron_research.sh`).
- **Context Relevance improvement**: Structured research output with explicit Clarvis-relevance assessment should improve context quality by ensuring research notes contain actionable content rather than pure knowledge dumps. This directly addresses the weakest metric (Context Relevance=0.387).
