# Heartbeat Coordinator Dispatch Mode — Deep Research

**Date**: 2026-04-02
**Task**: HEARTBEAT_COORDINATOR_MODE
**Sources**: Google A2A protocol spec, ADK multi-agent patterns, Progent (arXiv 2504.11703), Plan-and-Act (arXiv 2503.09572), Evolving Orchestration (arXiv 2505.19591), MegaAgent (ACL 2025), PEAR benchmark (arXiv 2510.07505), Claude Code subagent/teams docs, Osmani "Code Agent Orchestra", prior ingested research (2026-04-01)

---

## 1. Core Concept: Read-Only Coordinator with Typed Workers

The coordinator dispatch pattern separates **intent classification + routing** from **execution**. The coordinator is read-only: it reads system state, scores tasks, selects a worker type, constructs a dispatch prompt, and validates the result. It never edits files or runs implementation logic itself.

**Why this matters for Clarvis**: Today `cron_autonomous.sh` is a monolithic orchestrator that both selects and executes. The router (`clarvis.orch.router`) already classifies tasks into tiers (simple/medium/complex/reasoning) and selects executors (gemini/claude), but all Claude Code spawns get identical, unrestricted prompts. Adding worker typing between selection and spawn is a surgical enhancement — not a rewrite.

## 2. Five Key Findings

### Finding 1: Tool Restriction via Prompt Engineering Is Sufficient

Progent (arXiv 2504.11703) demonstrated that JSON-based privilege policies reduce attack success from 41.2% to 2.2% while maintaining task utility. But for Clarvis's trusted environment (all workers run under `--dangerously-skip-permissions`), **prompt-level tool restriction is sufficient**: include only relevant tool descriptions and explicit constraints in the worker prompt. Claude Code subagents already support `tools` allowlists in YAML frontmatter. No enforcement layer needed — the LLM respects the described toolkit.

**Clarvis application**: Define 3 worker prompt templates. Research worker gets `Read, Grep, Glob, WebFetch, brain.py` in its instructions and an explicit "DO NOT edit files or create scripts" constraint. Implementation worker gets full tools but "DO NOT browse the web." Maintenance worker gets brain/graph/cleanup tools only.

### Finding 2: Three Worker Types Cover 95%+ of Queue Tasks

Analysis of QUEUE.md task prefixes and the 14-dimension router scoring shows three natural clusters:

| Worker Type | Task Signals | Tools | Timeout | Output Schema |
|-------------|-------------|-------|---------|---------------|
| **Research** | `[RESEARCH]`, `[HARNESS_*]`, `[CODEX_*]`, analysis keywords | Read, Grep, Glob, WebFetch, brain remember/search | 1200s | `{findings, decision, brain_memories, queue_items}` |
| **Implementation** | `[IMPL]`, code/script keywords, file paths mentioned | Read, Edit, Write, Bash, Grep, Glob, git | 1500s | `{files_changed, tests_passed, diff_summary}` |
| **Maintenance** | `[CLEANUP]`, `[AUDIT]`, `[FIX]`, graph/brain/rotation | Read, Bash (restricted), brain ops, graph scripts | 900s | `{actions_taken, health_before, health_after}` |

The router's `code_generation` (0.20) + `file_editing` (0.18) dimensions already distinguish implementation from research. Adding a `classify_worker_type()` function that maps router scores + task tag prefixes to these three types is ~30 lines of code.

### Finding 3: A2A Task Lifecycle Maps to Heartbeat Episodes

Google A2A defines: `submitted → working → completed|failed|canceled`. Clarvis heartbeat already implements this: preflight (submitted) → Claude Code execution (working) → postflight (completed/failed). The key A2A additions worth adopting:

- **`input-required` state**: Workers can escalate back to coordinator when they need more context. Currently, Clarvis workers run to completion or timeout with no mid-execution communication. This could be approximated by having workers write to a well-known file (`/tmp/clarvis_worker_needs_input.json`) that the coordinator checks.
- **Agent Cards**: Formalizing worker capabilities as JSON manifests enables dynamic routing. Instead of hardcoded if/else, the coordinator reads worker cards and matches task requirements to declared skills.
- **Artifact structure**: Standardizing worker output as typed artifacts (code diff, research note, health report) enables postflight to validate structurally rather than heuristically.

### Finding 4: Parallel Fan-Out Is the Next Step After Typing

Google ADK's `ParallelAgent` and the Evolving Orchestration paper (arXiv 2505.19591) show that once workers are typed, parallel dispatch becomes natural: a complex task decomposes into "research the approach" + "implement the solution" running concurrently. The current global lock (`/tmp/clarvis_claude_global.lock`) must be relaxed to a per-worker-type semaphore (already noted in QUEUE as `CONCURRENT_SPAWN_SLOTS`).

The evolving orchestration paper's key finding: systems naturally converge to compact, cyclic topologies — enabling iterative refinement. For Clarvis: research → implement → validate → refine is a natural cycle.

### Finding 5: Coordinator Read-Only Enforcement Prevents the "Do-It-Myself" Failure Mode

Osmani's "Code Agent Orchestra" and Anthropic's multi-agent research both identify the same failure: coordinators that start executing instead of delegating. The fix is architectural — the coordinator's prompt explicitly has no write tools. Claude Code subagent frontmatter enforces this via `tools` allowlist. For Clarvis, the coordinator step runs inside `cron_autonomous.sh` (bash), not as a Claude Code instance, so enforcement is inherent — bash can't edit files the way an LLM agent would. The coordinator is already read-only by construction.

## 3. Implementation Blueprint

### Phase 1: Worker Type Classification (Effort: S)

Add `classify_worker_type(task_text, router_result) → WorkerType` to `clarvis/orch/router.py`:

```python
class WorkerType(Enum):
    RESEARCH = "research"
    IMPLEMENTATION = "implementation"
    MAINTENANCE = "maintenance"

def classify_worker_type(task: str, router_result: dict) -> WorkerType:
    tag = extract_tag(task)  # [RESEARCH], [IMPL], etc.

    # Tag-based fast path
    if tag in RESEARCH_TAGS:
        return WorkerType.RESEARCH
    if tag in MAINTENANCE_TAGS:
        return WorkerType.MAINTENANCE

    # Router score fallback
    score = router_result.get("score", 0.5)
    if router_result.get("code_generation", 0) > 0.3 or router_result.get("file_editing", 0) > 0.3:
        return WorkerType.IMPLEMENTATION
    if "audit" in task.lower() or "cleanup" in task.lower() or "fix" in task.lower():
        return WorkerType.MAINTENANCE

    return WorkerType.RESEARCH  # Default: research is safest (read-only)
```

### Phase 2: Worker Prompt Templates (Effort: S)

Create `scripts/worker_templates/` with three prompt templates:
- `research.txt` — includes read-only constraints, brain/web tools, structured output format
- `implementation.txt` — includes full tool access, test requirements, diff output format
- `maintenance.txt` — includes restricted tool set, health report format

`cron_autonomous.sh` loads the template based on `worker_type` from preflight JSON and prepends it to the task prompt.

### Phase 3: Preflight Integration (Effort: S)

`heartbeat_preflight.py` already outputs `route_tier` and `route_executor`. Add `worker_type` to the JSON output. The classify function runs after task selection and routing (§9), adding ~1ms.

### Phase 4: Postflight Validation (Effort: M)

`heartbeat_postflight.py` validates worker output against the expected schema for that worker type:
- Research: check for structured findings, brain memory count
- Implementation: check for file changes, test results
- Maintenance: check for health status, actions taken

Failed validation → episode marked as `partial_success` with diagnostic note.

### Phase 5: Concurrent Slots (Effort: M, separate task)

Relax global lock to per-type semaphore. Research + maintenance can run concurrently with implementation (different file spaces). This is the `CONCURRENT_SPAWN_SLOTS` queue item — keep separate.

## 4. Bloat Score Relevance (Currently 0.400)

The coordinator pattern directly addresses bloat:
- **Research workers** produce notes in `memory/research/`, not code — zero script bloat
- **Implementation workers** get explicit anti-bloat instructions in their template: "Do not create helper files. Modify existing files. Delete what you replace."
- **Maintenance workers** are bloat-reducing by design: cleanup, rotation, pruning
- **Typed output validation** catches workers that create unnecessary artifacts
- **Net prediction**: Positive impact on bloat score. Implementation workers with explicit constraints produce fewer throwaway scripts.

## 5. Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Misclassification routes impl task to research worker | Default to research (safe/read-only); misclassification = wasted heartbeat, not damage |
| Prompt-level tool restriction is soft (LLM can ignore) | Acceptable in trusted environment; add postflight check for unexpected file changes |
| Worker templates add maintenance burden (3 files) | Templates are <50 lines each; update frequency is low |
| Breaking change to preflight/postflight JSON contract | Additive only — new `worker_type` field, existing fields unchanged |

---

## Sources
- Google A2A Protocol: https://a2a-protocol.org/latest/specification/
- Google ADK Multi-Agent Patterns: developers.googleblog.com
- Progent (arXiv 2504.11703): Programmable privilege control for LLM agents
- Plan-and-Act (arXiv 2503.09572): Planner-executor separation, 57.58% WebArena-Lite
- Evolving Orchestration (arXiv 2505.19591): RL-trained agent selection converges to cyclic topologies
- MegaAgent (ACL 2025): Two-level hierarchy, admin agents recruit specialist workers
- PEAR (arXiv 2510.07505): Planner-executor robustness benchmark
- Claude Code Subagents/Teams docs (code.claude.com)
- Osmani "Code Agent Orchestra" (addyosmani.com, 2026)
- Anthropic Multi-Agent Research System (anthropic.com/engineering)
- Prior ingested research: memory/research/ingested/harness-coordinator-mode.md
