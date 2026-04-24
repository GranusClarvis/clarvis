---
name: clarvis-model-router
description: "Route tasks to optimal model by complexity — M2.5 for simple, GLM-5 for complex, Claude for code-heavy"
whenToUse: |
  When deciding which model should handle a task based on complexity. Routes simple
  tasks to cheap models (M2.5) and complex/code tasks to capable ones (Claude, GLM-5).
metadata: {"clawdbot":{"emoji":"🔀"}}
user-invocable: false
---

# Clarvis Model Router Skill

## Purpose
Analyze each task and route to the appropriate model.

## How It Works

### Task Detection
- **Coding/Integration**: code, script, function, build, fix, debug, implement
- **Reasoning/Planning**: think, plan, strategy, analyze, decide, design,架构
- **Difficult Reasoning**: complex, difficult, hard, novel, unprecedented, AGI, consciousness

### Model Mapping
| Task Type | Model | When |
|-----------|-------|------|
| Coding | `minimax-m2.5` | Default |
| Reasoning | `glm-5` | Keywords: think, plan, analyze, decide |
| Difficult | `claude-opus-4-7` | Keywords: complex, AGI, consciousness, novel |

## Usage

When responding to a message:
1. Analyze the task type
2. If different from current model, use `/model` to switch
3. Log the switch for metrics

## Implementation

This skill should be loaded on every session. It provides the model routing logic.
