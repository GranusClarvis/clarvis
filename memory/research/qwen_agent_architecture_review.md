# Research: Qwen-Agent Architecture Review

**Date**: 2026-03-06
**Source**: https://github.com/QwenLM/Qwen-Agent
**Task**: [RESEARCH_REPO_QWEN_AGENT]

## 15 Key Architecture Ideas

1. **Layered Agent Abstraction** — Clean inheritance pyramid: BaseChatModel → Agent → FnCallAgent → Assistant/ReActChat. Each layer adds one capability (LLM call → tool calling → RAG). Composable, not monolithic.

2. **Streaming-First Architecture** — All LLM interactions yield deltas as first-class citizens. Tools integrate into the streaming loop — agents can trigger tools before full LLM response completes.

3. **Function Calling as Protocol** — Tools aren't hardcoded logic; they're described via JSON schemas and the LLM decides autonomously whether/when to call them. Agent acts as a runtime, not a planner.

4. **Document-Centric Memory (not vector DB)** — Memory is file-centric retrieval with query adaptation. Agent extracts keywords, searches uploaded docs. Task-driven retrieval, not similarity-based ranking.

5. **Multi-Agent Router Pattern** — Agents don't communicate directly. A Router orchestrates by analyzing the query and delegating to specialists by name. GroupChat extends with 4 selection modes (auto/round-robin/random/manual).

6. **Auto-Router Content Analysis** — LLM-driven speaker selection: analyzes conversation context and decides which agent should respond next. Enables emergent conversation dynamics.

7. **Implicit RAG (Knowledge Integration Without Prompting)** — Assistant class retrieves docs and appends to system message transparently. No explicit "retrieve-then-answer" prompt needed. VirtualMemoryAgent iteratively fills system prompts.

8. **ReAct Protocol Made Explicit** — Thought→Action→Observation→Final Answer as a structured protocol in prompts. Agent detects delimiters to extract tool invocations. Iteration limit (MAX_LLM_CALL_PER_RUN=20) prevents infinite loops.

9. **Two-Tiered Code Execution** — PythonExecutor (fast, unsandboxed) and CodeInterpreter (Docker sandbox). Users choose safety vs speed. Both share same call protocol.

10. **Tool Schema Validation + Registry** — `@register_tool` decorator prevents naming conflicts, validates OpenAI JSON schema compliance at import time. BaseToolWithFileAccess auto-manages file downloads.

11. **Message Role Swapping** — In multi-agent simulation, each agent sees history from its own perspective (its turns as ASSISTANT, others as USER). Critical for maintaining agent self-model.

12. **Parallel Doc QA (Map-Reduce Style)** — Large document QA split into parallel member processing + summary aggregation. Workflow-based, not single LLM call.

13. **Language-Aware Prompt Templates** — Bilingual (EN/ZH) prompt selection via `has_chinese_messages()`. Single codebase serves multiple languages.

14. **Token Truncation Strategy** — Drops oldest turns entirely (not partial) when context exceeds limits. Preserves system message + recent turns. Happens automatically before LLM call.

15. **Configuration via Env Overrides** — All key parameters (max tokens, max iterations, workspace dir, RAG settings) have sensible defaults overridable via env vars.

## 5 Concrete "Steal and Implement" Items

### 1. Auto-Router for Task Delegation
**What**: LLM-driven routing that analyzes query content and delegates to the right handler.
**Target**: `scripts/task_router.py` — currently uses keyword/complexity heuristics. Add an LLM-routing mode where M2.5 analyzes the task description and picks the optimal handler (model, script, agent) from a registry.
**Effort**: Medium. Add `route_by_llm()` function that describes available routes as a JSON schema and asks M2.5 to select.

### 2. Implicit RAG in Heartbeat Context
**What**: Qwen's VirtualMemoryAgent progressively enriches system prompts with retrieved context — no explicit "search then inject" step.
**Target**: `scripts/heartbeat_preflight.py` → `context_compressor.py`. Instead of the current explicit brain search + context assembly, make context enrichment a transparent pipeline stage that auto-retrieves relevant memories based on the selected task description.
**Effort**: Small. The architecture exists; wrap the brain search + cognitive workspace context into a single `enrich_context(task)` call in preflight.

### 3. Tool Schema Registry with Validation
**What**: Centralized tool registration with JSON schema compliance checking at import time.
**Target**: `scripts/tool_maker.py` — currently creates tools but no validation registry. Add a `@register_tool` decorator pattern that validates tool schemas against a standard format and prevents naming conflicts. Integrate with `clarvis/brain/hooks.py` registration pattern.
**Effort**: Medium. Create `clarvis/tools/registry.py` with decorator + validation.

### 4. Streaming-Aware Agent Response
**What**: Progressive disclosure — agent yields partial results as they're generated.
**Target**: `scripts/spawn_claude.sh` / `scripts/project_agent.py`. Currently buffer entire output. Add streaming mode that captures output incrementally, enabling real-time progress updates to Telegram (e.g., "Step 1/3 complete...").
**Effort**: Medium. Use `--stream` or tail the output file periodically.

### 5. Parallel Document Processing for Research
**What**: Map-reduce pattern for processing large research documents.
**Target**: `scripts/cron_research.sh` — currently processes one research topic per run. Add parallel member pattern: split research into sub-queries, process in parallel threads, aggregate summaries. Reuse ThreadPoolExecutor from `agent_orchestrator.py`.
**Effort**: Small-Medium. Extract parallel worker pattern, apply to research ingestion.

## What to Ignore

- **Bilingual prompt system** — Clarvis operates in English; no need for language detection or dual prompts.
- **Docker code sandbox** — Clarvis runs on a trusted NUC with direct system access; sandboxing adds latency without security benefit for this use case.
- **DialogueSimulator** — Designed for LLM evaluation/training data generation. Clarvis doesn't train models.
- **MCP Manager tool** — Clarvis already has its own tool/skill system; MCP integration would add complexity without clear benefit at current scale.
- **Web search tool** — Clarvis already has browser + web search capabilities via clarvis_browser.py and agent-browser.
- **Image generation tool** — Not relevant to Clarvis's cognitive architecture goals.
