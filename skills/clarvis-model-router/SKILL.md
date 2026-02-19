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
| Difficult | `claude-opus-4-6` | Keywords: complex, AGI, consciousness, novel |

## Usage

When responding to a message:
1. Analyze the task type
2. If different from current model, use `/model` to switch
3. Log the switch for metrics

## Implementation

This skill should be loaded on every session. It provides the model routing logic.
