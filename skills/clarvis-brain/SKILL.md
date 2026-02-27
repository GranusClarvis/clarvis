# ClarvisBrain Skill

## Purpose
Unified memory system for Clarvis. This IS my brain — powered by ClarvisDB with local ONNX embeddings.

## Architecture

### Three Layers
1. **brain.py** — Core memory (store, recall, graph, goals, context)
2. **brain_bridge.py** — Connects brain to subconscious (heartbeat preflight/postflight)
3. **brain_introspect.py** — Self-awareness layer (domain detection, goal alignment, knowledge mapping)

### 10 Collections (1175+ memories)
| Collection | Count | Purpose | Query When |
|---|---|---|---|
| clarvis-learnings | 567 | Research, experiments, failures, insights | Any task (primary) |
| clarvis-memories | 138 | Conversations, events, decisions | Broad context |
| autonomous-learning | 100 | Self-discovered patterns | Self-improvement, meta-cognition |
| clarvis-episodes | 98 | Task outcomes with context | Learning from experience |
| clarvis-identity | 56 | Personality, constraints, core values | Identity/ethical decisions |
| clarvis-infrastructure | 46 | Servers, APIs, configs | Infrastructure/deployment tasks |
| clarvis-context | 45 | Working memory | Continuity between heartbeats |
| clarvis-procedures | 45 | Step-by-step procedures | Execution planning |
| clarvis-preferences | 44 | Work style, tool preferences | Implementation choices |
| clarvis-goals | 36 | Active objectives with progress | Task prioritization |

### 48k+ Graph Edges
- `similar_to`: same-collection similarity links
- `cross_collection`: cross-collection semantic links
- Enables associative recall: follow edges to find connected knowledge

## Usage

### Core Operations
```python
from brain import brain, search, remember, capture

# Semantic search
results = search("what do I know about X")

# High-importance store
remember("Inverse hates verbose responses", importance=0.9)

# Auto-capture (assess importance, store if >= 0.6)
capture("important insight from conversation")

# Targeted recall with filters
results = brain.recall("active inference",
    collections=["clarvis-learnings", "clarvis-memories"],
    n=5, min_importance=0.3,
    include_related=True,  # follow graph edges
    attention_boost=True,  # boost spotlight-matching results
)

# Goals
brain.get_goals()  # all goals with progress
brain.set_goal("Self-awareness", 60, subtasks={"current": "introspection"})

# Context (working memory)
brain.set_context("working on brain introspection")
brain.get_context()  # → current context string

# Stats
brain.stats()  # → {total_memories, graph_edges, collections: {...}}

# Optimize (daily)
brain.optimize(full=True)  # decay + prune + dedup + noise clean
```

### Introspection (Self-Awareness)
```python
from brain_introspect import introspect_for_task, format_manifest_for_prompt, build_knowledge_map

# Full task introspection — what do I know? what aligns with my goals?
result = introspect_for_task("Build a self-awareness module", budget="standard")
# Returns: domain_knowledge, goal_alignment, identity_context,
#          infrastructure, associative_memories, meta_awareness

# Capability manifest — what can the brain do?
manifest = format_manifest_for_prompt(compact=True)

# Knowledge map — what domains am I strong/weak in?
kmap = build_knowledge_map()
```

### Subconscious Integration (Heartbeat)
- **Preflight**: brain_bridge queries goals + context + knowledge; brain_introspect adds domain-aware recall, goal alignment, identity, infrastructure, associative memories
- **Postflight**: brain_bridge records outcomes and updates context

## Design Principles

1. **Auto, not manual** — Store on important events, recall at decision time
2. **Domain-aware** — Select collections based on task type, not blanket search
3. **Self-aware** — Know what I know, identify knowledge gaps
4. **Graph-connected** — Follow relationships for associative reasoning
5. **Fully local** — ONNX embeddings, no cloud dependency
6. **Noise-filtered** — Bridge metadata excluded from recall results
