# Clarvis Context Engine — Concept & Design Doc

**Date:** 2026-03-09
**Status:** Design — ready for [CONTEXT_ENGINE_SPIKE] implementation
**Dependencies:** OpenClaw v2026.3.7 ContextEngine plugin interface, ClarvisDB, prompt_builder.py
**Queue items:** [CLARVIS_CONTEXT_ENGINE_CONCEPT], [CLARVIS_CONTEXT_ENGINE_RESEARCH], [CONTEXT_ENGINE_SPIKE]

---

## 1. Goals

### Primary
Make ClarvisDB's intelligence (2200+ memories, 85k+ graph edges, episodic chains, somatic markers, cognitive workspace) **automatically available to every M2.5 conversation turn** — not just subconscious heartbeats.

### Secondary
1. **Unify context assembly** — Replace the two parallel pipelines (heartbeat_preflight.py 18-stage + prompt_builder.py 9-section) with one canonical context engine
2. **Close the conscious-layer feedback loop** — M2.5 conversations currently don't feed back into episodic memory or cognitive workspace
3. **Replace lossy compaction** — Store conversation summaries in ClarvisDB instead of OpenClaw's sliding-window discard
4. **Enable subagent context sharing** — Project agents receive parent context at spawn time

### Non-Goals
- Replace ClarvisDB — the context engine is a **runtime layer over** ClarvisDB, not a replacement
- Replace heartbeat pipeline — subconscious heartbeats continue using the cron flow; the context engine serves conscious-layer conversations
- Build a new memory system — uses existing brain.recall(), episodic_memory, cognitive_workspace, somatic_markers

---

## 2. Architecture

### 2.1 Overview

```
                  User Message (Telegram/Discord)
                            │
                  ┌─────────▼─────────┐
                  │  OpenClaw Gateway  │
                  │  (v2026.3.7)      │
                  └─────────┬─────────┘
                            │
              ┌─────────────▼─────────────┐
              │  ClarvisContextEngine      │
              │  (TypeScript plugin)       │
              ├────────────────────────────┤
              │  assemble()  → brain brief │  ← Every turn
              │  ingest()    → capture()   │  ← Every message
              │  afterTurn() → episode     │  ← Turn completion
              │  compact()   → summarize   │  ← Token overflow
              └──────┬──────┬──────┬──────┘
                     │      │      │
           ┌─────────▼──┐ ┌▼────┐ ┌▼──────────┐
           │ Python      │ │ CDB │ │ Cognitive  │
           │ Bridge      │ │     │ │ Workspace  │
           │ (subprocess)│ │     │ │            │
           └─────────────┘ └─────┘ └────────────┘
```

### 2.2 Plugin Registration

The plugin registers via OpenClaw's `ContextEngine` interface:

```typescript
// clarvis-context-engine/index.ts
import type { OpenClawPlugin, PluginAPI } from "openclaw/plugin-sdk";
import { ClarvisContextEngine } from "./src/engine";

const plugin: OpenClawPlugin = {
  definition: {
    id: "clarvis-context",
    name: "Clarvis Context Engine",
    kind: "context-engine",
    version: "0.1.0",
  },
  activate(api: PluginAPI) {
    api.registerContextEngine("clarvis-context", () => new ClarvisContextEngine(api));
  },
};

export default plugin;
```

Configuration in `openclaw.json`:
```json
{
  "plugins": {
    "slots": { "contextEngine": "clarvis-context" },
    "entries": {
      "clarvis-context": {
        "enabled": true,
        "config": {
          "contextTier": "standard",
          "maxTokenBudget": 600,
          "pythonBridge": "subprocess",
          "ingestUserMessages": true,
          "ingestMinLength": 50
        }
      }
    }
  }
}
```

### 2.3 Component Design

#### Python Bridge

The TypeScript plugin calls Python via subprocess. This reuses existing proven code with no new Python dependencies.

```typescript
// src/bridge.ts
import { execFile } from "child_process";

export async function callPython(script: string, ...args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    execFile("python3", [script, ...args], {
      cwd: "/home/agent/.openclaw/workspace/scripts",
      timeout: 5000,
      env: { ...process.env, PYTHONPATH: "/home/agent/.openclaw/workspace/scripts" },
    }, (err, stdout, stderr) => {
      if (err) reject(new Error(`${script} failed: ${stderr}`));
      else resolve(stdout.trim());
    });
  });
}
```

#### assemble() — Context Injection

The core method. Called on every model turn. Injects ClarvisDB context as a `systemPromptAddition`.

```typescript
async assemble(params: AssembleParams): Promise<AssembleResult> {
  const { messages, tokenBudget } = params;

  // Extract latest user message as the "task" for brain introspection
  const lastUserMsg = messages.filter(m => m.role === "user").pop();
  const query = extractText(lastUserMsg) || "";

  // Skip brain context for very short messages (greetings, acks)
  if (query.length < 20) {
    return { messages, estimatedTokens: countTokens(messages) };
  }

  // Call prompt_builder.py for a compact brain brief
  const tier = this.config.contextTier || "standard";
  const brief = await callPython(
    "prompt_builder.py", "context-brief",
    "--task", query,
    "--tier", tier
  );

  return {
    messages,
    estimatedTokens: countTokens(messages) + estimateTokens(brief),
    systemPromptAddition: brief ? `\n\n--- BRAIN CONTEXT ---\n${brief}\n---` : undefined,
  };
}
```

**Latency budget:** `prompt_builder.py context-brief` takes ~300ms (brain recall ~7.5s is NOT called here — prompt_builder uses a lighter introspection path at ~250-400ms). For a conversational UX, 300ms is acceptable.

#### ingest() — Message Capture

Every user message of sufficient length gets stored in ClarvisDB with auto-importance scoring.

```typescript
async ingest(params: IngestParams): Promise<IngestResult> {
  const { message, isHeartbeat } = params;
  if (isHeartbeat) return { stored: false };

  if (message.role === "user" && extractText(message).length >= this.config.ingestMinLength) {
    await callPython("brain.py", "capture", extractText(message));
    return { stored: true };
  }
  return { stored: false };
}
```

#### afterTurn() — Episodic Encoding + Workspace Update

After each conversation turn, encode an episodic entry and update the cognitive workspace.

```typescript
async afterTurn(params: AfterTurnParams): Promise<void> {
  const { messages, sessionId } = params;
  const lastUser = messages.filter(m => m.role === "user").pop();
  const lastAssistant = messages.filter(m => m.role === "assistant").pop();

  if (!lastUser || !lastAssistant) return;

  // Lightweight episodic capture (task + outcome)
  const userText = extractText(lastUser).slice(0, 200);
  const assistantText = extractText(lastAssistant).slice(0, 200);
  await callPython(
    "cognitive_workspace.py", "ingest",
    `Conversation: ${userText} → ${assistantText}`,
    "--tier", "working",
    "--source", "m2.5-conversation"
  );
}
```

#### compact() — ClarvisDB-Backed Summarization

Instead of sliding-window discard, summarize the conversation into ClarvisDB.

```typescript
async compact(params: CompactParams): Promise<CompactResult> {
  const { messages, tokenBudget, sessionId } = params;

  // Extract the portion of messages that would be compacted
  const compactionWindow = messages.slice(0, -10); // Keep last 10 turns
  if (compactionWindow.length < 4) {
    return { messages, compacted: false };
  }

  // Build summary text from compaction window
  const summaryText = compactionWindow
    .map(m => `[${m.role}] ${extractText(m).slice(0, 100)}`)
    .join("\n");

  // Store summary in ClarvisDB as a context memory
  await callPython("brain.py", "remember", summaryText,
    "--importance", "0.6",
    "--collection", "clarvis-context",
    "--metadata", JSON.stringify({ type: "conversation_summary", session: sessionId })
  );

  // Return trimmed messages (keep recent + summary reference)
  const summaryMsg = {
    role: "system" as const,
    content: `[Earlier conversation summarized and stored in brain. ${compactionWindow.length} turns compressed.]`,
  };

  return {
    messages: [summaryMsg, ...messages.slice(-10)],
    compacted: true,
    compactedTurns: compactionWindow.length,
  };
}
```

---

## 3. Data Flow

### 3.1 Per-Turn Flow (assemble)

```
User message arrives
  → OpenClaw calls assemble()
  → Extract user text as query
  → Call prompt_builder.py context-brief --task "query" --tier standard
    → brain_introspect.py: domain detection → targeted vector recall → graph traversal
    → brain goals + context + working memory
    → episodic memory (similar episodes, failure chains)
    → somatic markers (failure avoidance)
    → cognitive workspace (active + working buffers)
  → Return ~600 token systemPromptAddition
  → M2.5 sees brain context prepended to system prompt
```

### 3.2 Per-Message Flow (ingest)

```
User message arrives
  → OpenClaw calls ingest()
  → If message.length >= 50:
    → Call brain.capture(text) — auto-importance scoring
    → Stored in clarvis-memories collection
  → If assistant response:
    → Feed to cognitive_workspace.ingest(summary, tier="working")
```

### 3.3 Compaction Flow (compact)

```
Token budget exceeded
  → OpenClaw calls compact()
  → Extract old messages for compaction
  → Build text summary of compaction window
  → Call brain.remember(summary, importance=0.6, collection=clarvis-context)
  → Replace old messages with system-note reference
  → Return trimmed message array
```

---

## 4. Integration Points

### 4.1 What Changes

| Component | Change | Risk |
|-----------|--------|------|
| `openclaw.json` | Add `plugins.slots.contextEngine` + `plugins.entries["clarvis-context"]` | Low — reversible config |
| New: `clarvis-context-engine/` | TypeScript plugin directory (outside workspace) | Low — isolated npm package |
| `prompt_builder.py` | No changes — already has `context-brief` CLI | None |
| `brain.py` | No changes — already has `capture`/`remember` CLI | None |
| `cognitive_workspace.py` | No changes — already has `ingest` CLI | None |

### 4.2 What Does NOT Change

- Heartbeat pipeline — subconscious layer continues using `cron_autonomous.sh` → `heartbeat_preflight.py`
- ClarvisDB — remains the persistent substrate; context engine is a consumer
- Brain hook architecture — recall hooks (ACT-R, Hebbian, synaptic) continue operating
- Existing scripts — no script changes needed for Phase 1

### 4.3 Dependency Chain

```
Phase 1 (MVP):     assemble() only      → immediate value, lowest risk
Phase 2 (Capture): + ingest()           → closes feedback loop
Phase 3 (Memory):  + compact()          → replaces lossy compaction
Phase 4 (Agents):  + prepareSubagent()  → project agent context sharing
```

---

## 5. Rollout Plan

### Phase 1: MVP — assemble() Only (1 session)

**Goal:** M2.5 sees brain context in every conversation turn.

1. Create `clarvis-context-engine/` directory at `/home/agent/.openclaw/plugins/clarvis-context/`
2. Implement `engine.ts` with `assemble()` only (delegates to `prompt_builder.py context-brief`)
3. Implement `bridge.ts` with subprocess execution
4. Add plugin entry to `openclaw.json`
5. Test: send a Telegram message, verify brain context appears in M2.5's system prompt
6. **Validation**: check that M2.5 references ClarvisDB knowledge it didn't have before

**Rollback**: Set `plugins.slots.contextEngine` to `"legacy"` or remove it (restores default).

### Phase 2: Capture — + ingest() (1 session)

**Goal:** User messages automatically stored in ClarvisDB.

1. Add `ingest()` to engine — calls `brain.capture()` for user messages
2. Add message-length threshold (50 chars minimum)
3. Add heartbeat-message filtering (skip internal heartbeat turns)
4. Test: chat with M2.5, verify messages appear in `clarvis-memories` collection

### Phase 3: Memory — + compact() + afterTurn() (1-2 sessions)

**Goal:** Conversations summarized into ClarvisDB instead of discarded.

1. Implement `compact()` — summarize compaction window → `brain.remember()`
2. Implement `afterTurn()` — feed to cognitive workspace
3. Test: have a long conversation, verify summaries stored in `clarvis-context`
4. Validate: recall a conversation topic from a previous compacted session

### Phase 4: Subagents — + prepareSubagentSpawn() (future)

**Goal:** Project agents receive parent context at spawn time.

1. Implement `prepareSubagentSpawn()` — serialize relevant brain context
2. Implement `onSubagentEnded()` — promote agent learnings to parent brain
3. Wire into `project_agent.py` spawn flow

---

## 6. How This Complements ClarvisDB

| Concern | ClarvisDB | Context Engine |
|---------|-----------|----------------|
| **Persistence** | Long-term storage (ChromaDB, 10 collections) | No persistence — assembles from ClarvisDB on demand |
| **Retrieval** | Vector search + ACT-R + graph expansion | Delegates to ClarvisDB recall pipeline |
| **Learning** | Hebbian weights, synaptic STDP, episodic encoding | Feeds new data INTO ClarvisDB via ingest/compact |
| **Scope** | All data, all time | Per-turn context window assembly |
| **Audience** | Subconscious (heartbeat) + API callers | Conscious layer (M2.5 conversations) |

The context engine is a **consumer + feeder** of ClarvisDB, not a parallel system. It reads from the brain to build per-turn context, and writes back conversation insights.

---

## 7. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Subprocess latency (Python cold start) | `prompt_builder.py` import time ~200ms; cache process pool in future |
| Brain recall adds 7.5s latency | prompt_builder uses light introspection (~300ms), NOT full recall |
| Noisy context hurts M2.5 | Start with tier=standard (~600 tokens); adjustable via config |
| Double-counting (ingest duplicates) | Brain's dedup (cosine >0.95) prevents exact duplicates |
| Plugin crashes block gateway | ContextEngine has `dispose()` + OpenClaw falls back to legacy |
| Compaction loses important context | compact() stores to ClarvisDB before trimming; net improvement over sliding-window |

---

## 8. Metrics & Success Criteria

| Metric | Current | Target | How to Measure |
|--------|---------|--------|----------------|
| M2.5 brain-awareness | 0% turns | >80% turns | Check systemPromptAddition is non-empty |
| Context Relevance | 0.838 | >0.85 | Post-turn relevance scoring in afterTurn() |
| Conversation→ClarvisDB feedback | 0 memories/day | >5 memories/day | Count ingest() calls from conscious layer |
| Compaction memory retention | 0% (sliding-window) | >60% | Recall test on compacted session topics |

---

## 9. Alternative: before_prompt_build Hook (Minimal Viable Path)

If a full ContextEngine plugin is too heavy for the first iteration, a simpler hook-based approach provides 80% of the value:

```typescript
// In an existing plugin or as a lightweight hook:
api.on("before_prompt_build", async (event) => {
  const brief = await callPython("prompt_builder.py", "context-brief",
    "--task", event.prompt, "--tier", "standard");
  return { prependSystemContext: brief };
});
```

This gives M2.5 automatic brain context without lifecycle management (no ingest, no compact, no subagent sharing). Good for validation before committing to the full plugin architecture.

---

## 10. Relationship to Existing Queue Items

| Queue Item | Relationship |
|------------|-------------|
| [CONTEXT_ENGINE_SPIKE] | This doc IS the design input for the spike |
| [SPINE_MIGRATION_WAVE2_CONTEXT] | Migrating `context_compressor.py` → `clarvis/context/` creates the canonical module the plugin calls |
| [CONTEXT_RELEVANCE_FEEDBACK] | afterTurn() is the natural hook point for relevance tracking |
| [CONTEXT_ADAPTIVE_MMR_TUNING] | Per-task-category MMR lambda can be selected in assemble() |
| [RETRIEVAL_GATE] | assemble() can skip brain recall for short/greeting messages (gate logic) |
| ACE Playbook (research) | Playbook structure maps to systemPromptAddition format |

---

## Appendix: OpenClaw ContextEngine Interface (v2026.3.7)

Types discovered at: `/home/agent/.npm-global/lib/node_modules/openclaw/dist/plugin-sdk/context-engine/types.d.ts`

Key methods:
- `bootstrap(sessionId, sessionFile)` → session initialization
- `ingest(sessionId, message, isHeartbeat?)` → per-message ingestion
- `ingestBatch(sessionId, messages, isHeartbeat?)` → batch ingestion
- `afterTurn(sessionId, sessionFile, messages, prePromptMessageCount, ...)` → post-turn lifecycle
- `assemble(sessionId, messages, tokenBudget?)` → context assembly → `{messages, estimatedTokens, systemPromptAddition?}`
- `compact(sessionId, sessionFile, tokenBudget?, force?, ...)` → compaction → `{messages, compacted}`
- `prepareSubagentSpawn(parentSessionKey, childSessionKey, ttlMs?)` → subagent context
- `onSubagentEnded(childSessionKey, reason)` → subagent cleanup
- `dispose()` → cleanup

Registration: `api.registerContextEngine(id, factory)` in plugin `activate()`.
Config slot: `plugins.slots.contextEngine` in `openclaw.json`.
