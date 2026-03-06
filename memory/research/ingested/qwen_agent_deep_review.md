# Qwen-Agent Deep Review — Architecture Patterns for Clarvis

**Date**: 2026-03-06
**Source**: https://github.com/QwenLM/Qwen-Agent (Apache 2.0)
**Status**: Active development, powers Qwen Chat backend. Latest: Qwen3.5 support (Feb 2026), DeepPlanning benchmark (Jan 2026).

---

## 15 Key Ideas

1. **Error-as-Output**: Tool exceptions are stringified (with traceback) and returned as tool output text. LLM sees the error, reasons about it, retries or routes around. Only infra errors (`ToolServiceError`) bubble up as real exceptions.

2. **Memory-as-Agent**: Memory/RAG is a full `Agent` subclass, not a utility. It can use tools (`retrieval`, `doc_parser`), be composed, and swapped. Clean separation of concerns.

3. **VirtualMemoryAgent**: Retrieval results injected into system message silently — not returned as a function response. The LLM sees retrieved knowledge as grounding context, not as a preceding tool call. Reduces conversational noise.

4. **RAG Keygen Strategy Pipeline**: Query enhancement is decoupled from retrieval. Five strategies: `none`, `GenKeyword`, `SplitQueryThenGenKeyword`, `GenKeywordWithKnowledge`, `SplitQueryThenGenKeywordWithKnowledge`. Each is itself an agent calling an LLM.

5. **MAX_LLM_CALL Budget**: Hard cap (`MAX_LLM_CALL_PER_RUN=20`, env-configurable) prevents infinite tool loops. Decremented per LLM call, breaks the loop when exhausted.

6. **Multi-Perspective Message Reframing**: GroupChat's `_manage_messages()` rewrites conversation from each agent's first-person perspective. Other agents' messages → user turns prefixed with name; own messages → assistant turns. Solves coherence without shared global context.

7. **Stop-Word Routing**: Router and ReAct agents use LLM stop tokens (`Observation:`, `Reply:`, `Call:`) as protocol boundaries. Cheaper than full output parsing, prevents over-generation past decision points.

8. **Dual Prompt Strategy**: Two function-call prompt formats (`NousFnCallPrompt` with XML tags, `QwenFnCallPrompt` with special tokens) with transparent pre/post processing. New model families just need a new prompt class.

9. **Reasoning Content Separation**: `reasoning_content` field on Message carries CoT separately from `content`. Prevents chain-of-thought from contaminating tool parsing while preserving it for logging.

10. **Parallel Doc QA (Map-Reduce)**: Long docs chunked → parallel member agents read each chunk → aggregate non-null responses → enriched keywords → final RAG retrieval → synthesis. Handles documents beyond context window.

11. **MCP Singleton with Async Bridge**: `MCPManager` singleton runs asyncio event loop in a background thread, bridging sync agent code with async MCP. Auto-reconnect via ping-based liveness check.

12. **Agent Class Hierarchy**: Clean mixin pattern — `Agent` and `MultiAgentHub` are separate ABCs. `Router` inherits both `Assistant + MultiAgentHub`. `GroupChat` inherits both `Agent + MultiAgentHub`. Composition over inheritance.

13. **Tool Registry Decorator**: `@register_tool('name')` populates a global `TOOL_REGISTRY` dict. Agent init validates all requested tools exist. Same pattern for LLM backends (`@register_llm`).

14. **DeepPlanning Benchmark**: Code-verified evaluation (not LLM scoring) across 8 dimensions, 21 checkpoints. Deterministic, reproducible. MAX_LLM_CALLS=400 for long-horizon tasks.

15. **Streaming Architecture**: Agents yield `List[Message]` (full state, not deltas) on each step. Simplifies display — caller always has up-to-date complete response list.

---

## 5 Concrete "Steal and Implement" Items

### 1. Error-as-Output in Heartbeat Tool Calls
**What**: When heartbeat executes a task and a tool/script fails, catch the exception, format it as a string with traceback, and pass it back to the LLM as "observation" rather than crashing the entire heartbeat run.
**Target files**: `scripts/heartbeat_preflight.py`, `scripts/heartbeat_postflight.py`
**Effort**: Small. Wrap existing `subprocess.run()` or tool invocations in try/except, return formatted error string.
**Impact**: Improves Action Accuracy (currently 0.968) by reducing hard failures on recoverable errors.

### 2. MAX_LLM_CALL Budget for Heartbeat
**What**: Add a hard iteration cap to heartbeat task execution. If the selected task hasn't completed within N LLM calls, force termination and record partial results rather than risking runaway execution.
**Target files**: `scripts/heartbeat_preflight.py` (configure), cron spawners (timeout already exists, but this is finer-grained)
**Effort**: Small. Add counter to task execution loop, break on exhaustion.
**Impact**: Prevents cost overruns on stuck tasks. Complements existing timeout.

### 3. RAG Keygen Strategy for Brain Search
**What**: Before calling `brain.search(query)`, optionally expand/enhance the query using a lightweight LLM call. Strategies: split compound queries, generate synonyms/related terms, add context-informed keywords. This improves recall especially for vague queries.
**Target files**: `scripts/brain.py` (add `search_enhanced()` method), `clarvis/brain/spine.py`
**Effort**: Medium. Need a strategy class hierarchy and an LLM call for query expansion.
**Impact**: Directly improves retrieval quality, which affects Phi (semantic cross-collection) and preflight context quality.

### 4. Multi-Perspective Reframing for Agent Orchestrator
**What**: When spawning project agents, reframe the task history from the project agent's perspective. Clarvis's context becomes "user" input; the project agent's prior work becomes "assistant" context. This gives each project agent a coherent first-person view.
**Target files**: `scripts/project_agent.py` (add `_reframe_messages()` to spawn pipeline)
**Effort**: Medium. Requires message format standardization in agent protocol.
**Impact**: Better coherence in multi-project orchestration, reduces confusion when agents see cross-project context.

### 5. Code-Verified Evaluation for Performance Benchmarks
**What**: Replace LLM-scored evaluation with deterministic code-verified checks. For each benchmark dimension, write a Python function that checks pass/fail via code (not by asking an LLM). This makes benchmarks reproducible and cheap to run.
**Target files**: `scripts/performance_benchmark.py` (already partially code-verified, extend to all dimensions)
**Effort**: Small-Medium. Most dimensions are already code-verified; formalize the pattern.
**Impact**: More reliable PI metric, zero additional LLM cost for benchmarking.

---

## What to Ignore

- **Gradio GUI** (`qwen_agent/gui/`): Not applicable — Clarvis uses Telegram/Discord, not web UI.
- **DashScope-specific backends** (`qwen_dashscope.py`, `qwenvl_dashscope.py`): Alibaba-specific API, we use OpenRouter.
- **Browser extension** (`browser_qwen/`): We have ClarvisBrowser + BrowserAgent already.
- **Image generation/search tools**: Not in our current scope.
- **QwenFnCallPrompt special tokens** (`✿FUNCTION✿`): Model-specific, not transferable.
- **Qwen-specific model configs**: DashScope model naming, Qwen tokenizers, etc.
- **`qwen_server/`**: Serving utilities for Qwen models, not relevant to our architecture.

---

## Relation to Weakest Metric

Action Accuracy (0.968, target 0.8) is already well above target, but the **Error-as-Output** pattern (#1) and **MAX_LLM_CALL budget** (#2) would make it more resilient under edge cases — graceful degradation instead of hard failure on tool errors.

---

## Summary

Qwen-Agent is a clean, well-architected agent framework with pragmatic patterns. Its strongest ideas for Clarvis are: (1) error resilience via Error-as-Output, (2) Memory-as-Agent composition, (3) query enhancement strategies for RAG, and (4) multi-perspective reframing for multi-agent orchestration. The framework validates several patterns Clarvis already uses (tool registry, stop-word parsing, streaming) while offering concrete improvements to brain search quality and heartbeat robustness.
