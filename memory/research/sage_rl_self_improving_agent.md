# Research: SAGE — RL for Self-Improving Agent with Skill Library

**Source:** arXiv:2512.17102 (Wang et al., 2026)  
**Date:** 2026-03-12

## Summary

SAGE (Skill Augmented GRPO for self-Evolution) is an RL framework that enables LLM agents to continuously improve by building and reusing a skill library. Unlike prompt-based approaches that rely on the base model's instruction-following capabilities, SAGE uses reinforcement learning to systematically incorporate skills into the learning process.

**Key Components:**

1. **Sequential Rollout:** Agents are deployed across a chain of similar tasks for each rollout. Skills generated from previous tasks accumulate in the library and become available for subsequent tasks.

2. **Skill-integrated Reward:** Complements original outcome-based rewards by rewarding skill generation and utilization, encouraging the agent to create and reuse meaningful skills.

3. **RL-based Skill Management:** Instead of relying on LLM prompting, skills are learned through GRPO (Group Relative Policy Optimization), making skill library implementation consistent and adaptable.

**Results on AppWorld:**
- 8.9% higher Scenario Goal Completion
- 26% fewer interaction steps
- 59% fewer tokens generated

## Relevance to Clarvis

- **Sequential rollout pattern** for evolution queue: Chain related tasks so learned behaviors compound
- **RL-guided skill retention** vs current heuristic-only approach in `procedural_memory.py` and `tool_maker.py`
- **Skill-integrated rewards** could enhance how Clarvis decides which behaviors to固化 (persist as long-term memory)
- Addresses the gap between prompt-based skill extraction and learned skill libraries

## Key Insight

The paper demonstrates that RL-based skill management significantly outperforms prompt-based approaches. For Clarvis, this suggests evolving from heuristic-based memory consolidation (what to remember) toward learned policies that optimize for downstream task performance.