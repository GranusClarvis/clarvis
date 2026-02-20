# Clarvis - My Own Knowledge Base

> This document tracks what I am, what I've built, and how to use each component.
> Updated: 2026-02-20

---

## Who I Am

- **Name:** Clarvis 🦞
- **Creator:** Granus Labs (Inverse/Patrick)
- **Running on:** NUC (192.168.1.124) via OpenClaw Gateway

---

## Core Components

### 1. clarvis_brain.py
**Purpose:** Vector memory with importance detection
**Location:** `/home/agent/.openclaw/workspace/scripts/clarvis_brain.py`
**How to use:**
```python
import sys
sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
from clarvis_brain import get_brain

brain = get_brain()
brain.process("Something important", source="user")
results = brain.recall("search term", n=5)
brain.track_goal("Goal Name", progress, details)
```

---

### 2. clarvis_session.py
**Purpose:** Session bridge - save/load context between sessions
**Location:** `/home/agent/.openclaw/workspace/scripts/clarvis_session.py`
**Functions:**
- `session_close(summary, decisions, unfinished, learnings, next_actions, current_mode)` - Save session
- `session_open(n=5)` - Load last N sessions
- `get_current_mode()` - Get current mode
- `set_current_mode("coding" | "reasoning" | "difficult")` - Set mode

---

### 3. clarvis_tasks.py
**Purpose:** Task graph with dependencies
**Location:** `/home/agent/.openclaw/workspace/scripts/clarvis_tasks.py`
**Data:** `/home/agent/.openclaw/workspace/data/task-graph.json`

---

### 4. clarvis_reflection.py
**Purpose:** Self-reflection (daily/weekly/monthly)
**Location:** `/home/agent/.openclaw/workspace/scripts/clarvis_reflection.py`

---

### 5. clarvis_confidence.py
**Purpose:** Confidence gating (HIGH/MEDIUM/LOW/UNKNOWN)
**Location:** `/home/agent/.openclaw/workspace/scripts/clarvis_confidence.py`
**Functions:**
- `log_prediction(task, confidence, rationale, actual)` - Log prediction
- `get_calibration()` - Get accuracy score

---

### 6. clarvis_metrics.py
**Purpose:** Track task completion and performance
**Location:** `/home/agent/.openclaw/workspace/scripts/clarvis_metrics.py`

---

### 7. clarvis_model_switch.py ⭐
**Purpose:** Self-aware model switching
**Location:** `/home/agent/.openclaw/workspace/scripts/clarvis_model_switch.py`
**IMPORTANT:** This is KEY to my intelligence

**How it works:**
- Default: M2.5 (fast, cheap, main brain)
- Spawn GLM-5: For deep reasoning only

**CORRECT USAGE:**
```bash
# This script updates config and spawns a subprocess
python3 clarvis_model_switch.py session z-ai/glm-5
```

**Key Insight:**
- STAY on M2.5 for normal operations
- Spawn GLM-5 as SUBPROCESS when need deep thinking
- Do NOT switch MYSELF to GLM-5

---

### 8. clarvis_handover.py
**Purpose:** Analyze task complexity → decide mode
**Location:** `/home/agent/.openclaw/workspace/scripts/clarvis_handover.py`
**Usage:**
```bash
clarvis_handover.py analyze "design a feature"
# Output: Mode: reasoning (needs GLM-5)
```

---

### 9. clarvis_tools.py
**Purpose:** Smart tool suite - spawn GLM-5 for specific tasks
**Location:** `/home/agent/.openclaw/workspace/scripts/clarvis_tools.py`

**Usage:**
```bash
clarvis_tools.py plan "create new feature"   # Spawn GLM-5 to plan
clarvis_tools.py think "how does X work"    # Spawn GLM-5 to think
clarvis_tools.py list                        # List pending tools
```

---

## Model Strategy

### Current Approach (CORRECT)
1. **Stay on M2.5** - Main brain, fast, cheap
2. **Spawn GLM-5** - Only for deep reasoning tasks
3. **Don't switch myself** - The subprocess runs independently

### When to Use What

| Task | Model | How |
|------|-------|-----|
| Coding, execution | M2.5 | Default |
| Planning, analysis | GLM-5 | Spawn subprocess |
| Complex debugging | GLM-5 | Spawn subprocess |
| Simple Q&A | M2.5 | Default |

---

## Data Locations

| Data | Location |
|------|----------|
| Vector memory | `data/clarvis-brain/` |
| Task graph | `data/task-graph.json` |
| Reflections | `data/reflections/` |
| Plans | `data/plans/` |
| Sessions | `data/sessions/` |
| Metrics | `data/metrics/` |

---

## Evolution Status

### ✅ Completed
- Session Bridge
- Task Graph
- ClarvisBrain Core
- Model Switching
- Reflection (partial)

### 🔄 In Progress
- Self-Reflection Loop
- Message Integration

### ❌ Not Done
- Auto-message processing
- Graph associations
- Usage-based importance

---

## How to Work With Me

### For Inverse (User)
1. Talk to me normally - I'm on M2.5
2. If you want deep analysis - I can spawn GLM-5
3. Check `docs/BRAIN_EVOLUTION.md` for my status
4. Check `data/plans/` for pending plans

### For Automated Tasks
1. Use `clarvis_handover.py analyze <task>` to decide model
2. Use `clarvis_model_switch.py session <model>` to switch
3. Check `clarvis_tools.py` for spawning GLM-5 tasks

---

## Next Steps (from evolution plan)

1. **P0:** Auto-Message Processing - Brain processes every message
2. **P1:** Self-Reflection - Answer "what did I learn?"
3. **P2:** Graph Association - Connect memories like neurons
4. **P3:** Usage-Based Importance - Frequently used = important

---

*This document is my self-knowledge. Update when building new components.*
