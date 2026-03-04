# Research Backlog

## Repos to evaluate
- https://github.com/rtk-ai/rtk — suggested by Inverse (2026-03-04). **Evaluated 2026-03-04.**
  RTK = Rust CLI proxy that compresses tool output by 60-90% for LLM sessions. 2,651 stars, MIT, v0.24.0, very active.
  **Verdict: Borrow patterns, don't adopt.** Only 24% of Clarvis bash calls are RTK-compressible (60% are `python3 scripts/`). Estimated 5-15% token savings for automated sessions. Worth installing for interactive Claude Code sessions (Patrick). Test output compression pattern worth borrowing for project_agent.py spawns. Full analysis in `docs/AGI_READINESS_ARCHITECTURE_AUDIT.md`.

_Demoted from QUEUE.md — interesting research that didn't yield immediate actionable tasks. Revisit when a related task arises naturally._

## Planning & Reasoning

- **FLARE — Why Reasoning Fails to Plan** (Guo et al., arXiv:2601.22311, reviewed 2026-03-03)
  Step-wise LLM reasoning creates myopic commitments that cascade into long-horizon planning failures. FLARE introduces future-aware lookahead with value propagation. Potentially applicable to task_selector.py if greedy selection becomes a bottleneck.

- **Tree Search + Process Reward Models for Deliberative Reasoning** (reviewed 2026-03-01)
  Unified framework: MCTS + reward models + transition functions. ReST-MCTS* combines process reward guidance with tree search. Potentially applicable to clarvis_reasoning.py QUICK/STANDARD/DEEP modes if reasoning quality needs improvement.
  Sources: arxiv.org/html/2510.09988v1, openreview.net/forum?id=8rcFOqEud5, arxiv.org/html/2503.10814v1

## Error Recovery & Resilience

- **PALADIN — Self-Correcting Tool-Failure Recovery** (ICLR 2026, arXiv:2509.25238, reviewed 2026-03-02)
  Runtime failure detection, diagnosis, and recovery for tool-augmented agents. Systematic failure injection generates 50k+ recovery-annotated trajectories; taxonomy-driven retrieval of 55+ failure exemplars at inference. Related: cron_doctor.py already handles basic recovery; revisit if failure patterns become more complex.

## Architecture & Retrieval

- **Neurosymbolic AI for Hybrid Agent Reasoning** (reviewed 2026-03-01)
  Neural-symbolic integration patterns: Symbolic[Neural] (MCTS+neural eval), Neural[Symbolic] (logical inference inside networks). IBM path-to-AGI framing. Potentially applicable to clarvis_reasoning.py + brain.py knowledge graph if hallucination becomes a problem.
  Sources: arxiv.org/html/2502.11269v1, sciencedirect.com/S2667305325000675, research.ibm.com/topics/neuro-symbolic-ai
