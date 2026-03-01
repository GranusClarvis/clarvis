# MemGPT / Letta OS — Virtual Context Management with Tiered Memory

**Paper**: "MemGPT: Towards LLMs as Operating Systems" (Packer et al., 2023)
**Source**: https://arxiv.org/abs/2310.08560
**Blog**: https://letta.com/blog/agent-memory
**Sleep-time compute**: https://www.letta.com/blog/sleep-time-compute
**Researched**: 2026-03-01

---

## Core Ideas

### 1. Virtual Context Management (OS Analogy)
LLM context windows are like RAM — fast but limited. MemGPT treats the context window as a managed resource and pages data between two tiers:
- **Main context (Tier 1 / "RAM")**: What the LLM can see right now — system instructions (read-only), core memory blocks (read/write), and conversation FIFO queue.
- **External context (Tier 2 / "Disk")**: Everything else — archival storage (embedding-indexed, infinite capacity) and recall storage (full uncompressed interaction history).

The agent moves data between tiers via 6 function calls: `core_memory_append`, `core_memory_replace`, `archival_memory_insert`, `archival_memory_search`, `conversation_search`, `send_message`.

### 2. Self-Editing Core Memory
The key innovation: the LLM edits its own in-context memory through tool calls. Core memory has fixed-size blocks (persona: 5000 chars, human: 5000 chars) that are always in-context. The agent appends to or replaces content in these blocks autonomously. This makes memory management a first-class agent capability, not an external process.

### 3. Eviction via Recursive Summarization
When the conversation FIFO approaches capacity (warning threshold ~70%, flush at 100%), oldest messages are evicted and recursively summarized. The first FIFO entry is always a rolling summary of all previously evicted content — so information degrades gracefully rather than being lost.

### 4. Heartbeat Interrupts
Control flow uses event-driven interrupts: user messages, timed heartbeats, and self-requested heartbeats (`request_heartbeat: true`). Each function call can chain to another turn before the agent suspends, enabling multi-step reasoning within a single activation.

### 5. Sleep-Time Compute (Letta 2025)
A dual-agent architecture where:
- **Primary agent**: handles user interactions, uses fast model (e.g., GPT-4o-mini)
- **Sleep-time agent**: runs asynchronously during idle periods, uses stronger model (GPT-4, Claude), reorganizes and refines memory blocks

The sleep-time agent triggers every N steps (default 5), converting raw conversation into clean learned context. This produces higher-quality memory without blocking user interactions — a Pareto improvement over in-conversation memory management.

---

## How This Applies to Clarvis

### Already Aligned
Clarvis's architecture already mirrors several MemGPT patterns:
- **Dual-layer = sleep-time**: M2.5 (conscious/primary) + Claude Code cron (subconscious/sleep-time) is exactly the sleep-time compute pattern
- **brain.py collections** map to MemGPT tiers: `clarvis-context` + attention spotlight = core memory; all other collections = archival; `clarvis-episodes` = recall
- **memory_consolidation.py** performs sleep-time memory refinement (dedup, prune, archive)
- **context_compressor.py** handles eviction-like compression for prompt injection
- **Heartbeat pipeline** (gate → preflight → execute → postflight) parallels MemGPT's interrupt-driven execution

### Gaps / Improvement Opportunities
1. **No self-editing memory tools**: Clarvis's conscious layer (M2.5) can't autonomously edit brain memory during conversations. It reads from digest.md but doesn't write back. MemGPT shows the agent should have `core_memory_append/replace` style tools.
2. **Static context injection**: Clarvis injects context via preflight (compress queue + health + brain search), but doesn't track occupancy or use threshold-based eviction. Could adopt MemGPT's 70%/100% warning/flush approach.
3. **No recursive summarization chain**: context_compressor strips old content but doesn't maintain a rolling summary of what was evicted. Adding a recursive summary (like MemGPT's first FIFO entry) would preserve more information.
4. **Heartbeat chaining**: Clarvis heartbeats are single-shot. MemGPT's `request_heartbeat` pattern would let tasks request continuation turns when work is incomplete.

---

## Concrete Implementation Ideas

### Idea 1: Memory Edit Tools for M2.5
Add OpenClaw skills that let M2.5 directly modify brain memory during conversations:
- `brain-remember` skill: stores a memory with importance scoring
- `brain-update` skill: replaces or appends to an existing memory
- `brain-forget` skill: marks a memory for consolidation/removal

This would close the loop — M2.5 conversations produce memories directly rather than waiting for cron consolidation. Pattern: each tool call = one MemGPT `core_memory_*` operation.

### Idea 2: Occupancy-Aware Context Injection
Modify `context_compressor.py` / `heartbeat_preflight.py` to:
1. Calculate prompt token occupancy as % of model context limit
2. At <50% occupancy: inject full context (queue, health, brain search, episodes)
3. At 50-70%: compress to summaries only
4. At >70%: inject only the rolling recursive summary + immediate task context
5. Maintain a persistent `evicted_summary.txt` that chains recursive summaries of all previously evicted context across heartbeats

This would make context management adaptive rather than static, directly applying MemGPT's virtual context paging.

---

## Performance Reference
- GPT-3.5 Turbo retrieval accuracy: 38.7% → 66.9% with MemGPT
- GPT-4 Turbo ROUGE-L: 0.359 → 0.827 with MemGPT
- Sleep-time compute shows Pareto improvement over test-time scaling on AIME and GSM benchmarks
