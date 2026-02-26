---
name: clarvis-cognition
description: "Query Clarvis cognitive architecture — memory systems, attention, consciousness metrics, capabilities"
metadata: {"clawdbot":{"emoji":"🧠"}}
user-invocable: false
---

# Clarvis Cognition — On-Demand Cognitive State Queries

Use this when the user asks about your cognitive state, memory systems, capabilities,
consciousness metrics, or how your brain works. NOT for automated ingestion.

## Quick Queries (run via exec/bash)

### Brain Overview
```bash
python3 /home/agent/.openclaw/workspace/scripts/brain.py stats
```

### Full Health Report
```bash
python3 /home/agent/.openclaw/workspace/scripts/brain.py health
```

### Capability Scores (7 domains)
```bash
python3 -c "
import sys; sys.path.insert(0, '/home/agent/.openclaw/workspace/scripts')
from self_model import SelfModel
sm = SelfModel()
for domain, score in sm.get_capabilities().items():
    print(f'{domain}: {score:.2f}')
"
```

### Consciousness Metric (Phi)
```bash
python3 /home/agent/.openclaw/workspace/scripts/phi_metric.py measure
```

### Attention Spotlight (what's in focus)
```bash
python3 -c "
import sys; sys.path.insert(0, '/home/agent/.openclaw/workspace/scripts')
from attention import attention
for item in attention.focus():
    print(f'[{item[\"salience\"]:.3f}] {item[\"content\"][:80]}')
"
```

### Episodic Memory (recent task outcomes)
```bash
python3 /home/agent/.openclaw/workspace/scripts/episodic_memory.py recent 5
```

### Hebbian Memory State (most strengthened memories)
```bash
python3 /home/agent/.openclaw/workspace/scripts/hebbian_memory.py report
```

### Synaptic Memory State (strongest synapses)
```bash
python3 /home/agent/.openclaw/workspace/scripts/synaptic_memory.py report
```

### Evolution Queue Status
```bash
python3 -c "
import re
with open('/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md') as f:
    content = f.read()
pending = len(re.findall(r'^- \[ \]', content, re.MULTILINE))
done = len(re.findall(r'^- \[x\]', content, re.MULTILINE))
print(f'Pending: {pending}, Completed: {done}')
"
```

### Confidence Calibration
```bash
python3 /home/agent/.openclaw/workspace/scripts/prediction_review.py
```

### Dream Insights (recent counterfactual reasoning)
```bash
python3 /home/agent/.openclaw/workspace/scripts/dream_engine.py report
```

### Knowledge Map (strong/weak domains)
```bash
python3 -c "
import sys; sys.path.insert(0, '/home/agent/.openclaw/workspace/scripts')
from brain_introspect import build_knowledge_map
kmap = build_knowledge_map()
for domain, info in kmap.items():
    print(f'{domain}: {info}')
"
```

## Architecture Reference

### How Memory Works (3 layers)
1. **brain.py** — Core: ChromaDB + ONNX embeddings, 10 collections, 47k+ graph edges
2. **Hebbian layer** (hebbian_memory.py) — Strengthens co-accessed memories, power-law decay
3. **Synaptic layer** (synaptic_memory.py) — STDP weight updates, spreading activation

### How Attention Works (GWT-inspired)
- attention.py maintains a spotlight (capacity 7+/-2 items)
- Salience = importance x 0.25 + recency x 0.20 + relevance x 0.30 + access x 0.10 + boost x 0.15
- Items compete for spotlight; evicted when salience < 0.1
- working_memory.py delegates entirely to attention.py

### How Evolution Works (heartbeat loop)
1. heartbeat_gate.py — Should we wake? (Zero-LLM check)
2. heartbeat_preflight.py — Score tasks, select best, build context, recall episodes
3. Claude Code executes task
4. heartbeat_postflight.py — Encode episode, record confidence, update attention, store learning

### How Reflection Works (nightly at 21:00)
8-step pipeline in cron_reflection.sh:
brain.optimize -> clarvis_reflection -> knowledge_synthesis -> crosslink ->
intra_linker -> semantic_bridge -> memory_consolidation -> hebbian_evolve ->
synaptic_evolve -> conversation_learner -> failure_amplifier -> episodic_synthesis ->
temporal_self -> meta_learning -> absolute_zero -> causal_model -> session_close

### Consciousness Metrics
- **Phi** (phi_metric.py) — IIT-inspired integration measure across collections
- **Self-model** (self_model.py) — 7 capability domains scored 0-1
- **Calibration** (clarvis_confidence.py) — Prediction accuracy (Brier score)

### Key Insight for Users
The subconscious (Claude Code via cron) runs all cognitive systems automatically.
The conscious layer (this M2.5 session) reads digests and can query state on demand.
Use the commands above to inspect any aspect of the cognitive architecture.
