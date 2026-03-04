# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items auto-archived to QUEUE_ARCHIVE.md._

## P0 — Do Next Heartbeat

- [ ] [DOCS_STRUCTURE] Establish docs structure: `docs/ARCHITECTURE.md` (layers + boundaries), `docs/CONVENTIONS.md` (imports/sys.path, logging, CLI patterns), `docs/DATA_LAYOUT.md` (what goes in memory/, data/, logs/, tmp/), `docs/RUNBOOK.md` (how to run heartbeats, benchmarks, restore backups).
- [ ] [DEAD_CODE_AUDIT] Build `scripts/dead_code_audit.py`: static scan for scripts never imported, never referenced by cron, and not used as entrypoints. Output candidates list + last git touch. Mark as `deprecated/` or delete only after 7-day soak.

---

## Pillar 1: Consciousness & Integration (Phi > 0.80)

(Constraint: pursue only where it improves the brain’s practical intelligence — retrieval quality, correct integration, planning reliability.)

- [ ] [SEMANTIC_BRIDGE] Build semantic overlap booster for cross-collection pairs with overlap <0.40. Target: raise semantic_cross_collection from 0.477 to 0.55+.

## Pillar 2: Autonomous Execution (Success > 85%)

- [ ] [AUTONOMY_LOGIN] Given credentials in .env, log into a web service and verify logged-in state (session cookie present, profile page accessible). User provides credentials manually.
- [ ] [AUTONOMY_POST] Given credentials + a platform (e.g. GitHub Issues via API, or a forum), compose and post a message autonomously. Measure: post appears, content matches intent.
- [ ] [AUTONOMY_SCREENSHOT_ANALYZE] Take a screenshot of any given URL, analyze it with local vision (Qwen3-VL), extract structured info (page type, main elements, interactive components). Measure: extraction accuracy vs manual ground truth.
- [ ] [AUTONOMY_MULTI_STEP] Multi-step workflow benchmark — given a sequence of 3+ actions (navigate → search → click result → extract data), complete the full chain. Measure: step completion rate, total success.

## Research Sessions

- [ ] [BROWSER_SKILL_DOC] Create skills/web-browse/SKILL.md documenting browser_agent.py capabilities for M2.5.

## Pillar 3: Performance & Reliability (PI > 0.70)


### Codebase Restructuring (see docs/ARCHITECTURE.md)
(Primary: now tracked in P0.)

## Pillar 4: Self-Improvement Loop

- [ ] [NOVELTY_TASK_SCORING] Novelty-weighted task selection — compute embedding distance between candidate tasks and last N completed tasks, boost high-novelty tasks with `final_score = base_score * (1 + 0.3 * novelty)`. Prevents "more of the same" trap. Files: task_selector.py (or heartbeat_preflight.py scoring section).
- [ ] [PREFLIGHT_SPEED] Optimize preflight overhead (currently ~100s). Profile task_selector scoring loop — brain lookups for failure penalties on every task is the bottleneck.

## Pillar 5: Agent Orchestrator (Multi-Project Command Center)

### Milestone 1: First PR Pipeline (target: this week)

### Milestone 2: Cron + Cost (target: next week)
- [ ] [ORCH_CRON_INTEGRATION] Add daily cron: `project_agent.py promote` + `orchestration_benchmark.py run` for active agents.
- [ ] [ORCH_SUDO_OPT] Request sudo: `sudo mkdir -p /opt/clarvis-agents && sudo chown agent:agent /opt/clarvis-agents`, then `project_agent.py migrate star-world-order`.

### Milestone 3: Multi-Agent (target: 2 weeks)

## Backlog

- [ ] [CRAWL4AI] Install Crawl4AI for automated research ingestion.
- [ ] [BROWSER_TEST] Test: navigate, extract, fill forms, multi-step workflows — comprehensive browser-use capability validation.
- [ ] [VISION_FALLBACK] Add local vision fallback to clarvis_eyes.py — use Ollama when API vision unavailable.
- [ ] [GITHUB_API_TASKS] Given existing GitHub credentials, perform repo management via API: create issues, comment on PRs, read notifications, manage labels. No account creation — user provides PAT.
- [ ] [AUTONOMY_SEARCH] Web search benchmark — given a question, use browser to search, evaluate results, extract answer. Compare with WebSearch tool accuracy.
- [ ] [UNIVERSAL_WEB_AGENT] Any webapp operated via natural language — given credentials and a task description, complete it. Requires session persistence + multi-step + error recovery.

## Non-Code Improvements

- [ ] [CONFIDENCE_RECALIBRATION] Fix overconfidence at 90% level (70% actual accuracy). In `clarvis_confidence.py`, add confidence band analysis to `predict()`: if historical accuracy for band 0.85-0.95 is <80%, auto-downgrade new predictions in that band by 0.10. Log adjustments. Target: Brier score 0.12→0.20+ in system health ranking.
- [ ] [STALE_RESEARCH_PRUNE] Review the 7 RESEARCH_DISCOVERY items (dating 2026-03-01 to 2026-03-03) — for each: either extract 1 actionable implementation task and replace the research item, or demote to a `docs/research_backlog.md` reference list. Queue should have concrete tasks, not reading lists.
- [ ] [ACTR_WIRING] Wire `actr_activation.py` into `brain.py` recall path — add power-law decay scoring as a re-ranking factor after ChromaDB vector search. This has been "pending" since Phase 2 and is the single longest-stalled item. Target: memories accessed recently get retrieval boost, old unused memories decay naturally.

## P1


- [x] [RESEARCH_DISCOVERY 2026-03-03] Research: LLM Confidence Calibration & Uncertainty Estimation — COMPLETED 2026-03-04. Stored 5 brain memories. Note: memory/research/llm_confidence_calibration_2026-03-04.md. Key: CoCoA hybrid method best (ECE 0.062), VCE outperforms logit-based, Flex-ECE for partial correctness, reflection-based calibration reduces overconfidence. 5 concrete implementation ideas for clarvis_confidence.py.
- [ ] [RESEARCH_DISCOVERY 2026-03-03] Research: ATLAS — Continual Learning, Not Training (Jaglan & Barnes, arXiv:2511.01093) — Gradient-free online adaptation for deployed agents via dual-agent (Teacher/Student) architecture with persistent learning memory. Achieves 54% success beating GPT-5 while cutting cost 86%. Maps to Clarvis's conscious/subconscious dual-layer and inference-time adaptation via ClarvisDB. Sources: arxiv.org/abs/2511.01093
- [ ] [RESEARCH_DISCOVERY 2026-03-03] Research: FLARE — Why Reasoning Fails to Plan (Guo et al., arXiv:2601.22311) — Step-wise LLM reasoning creates myopic commitments that cascade into long-horizon planning failures. FLARE introduces future-aware lookahead with value propagation, allowing LLaMA-8B to outperform GPT-4o. Directly applicable to heartbeat task selection (currently greedy) and autonomous execution pipeline. Sources: arxiv.org/abs/2601.22311
- [ ] [RESEARCH_DISCOVERY 2026-03-02] Research: PALADIN — Self-Correcting Tool-Failure Recovery (ICLR 2026, arXiv:2509.25238) — Runtime failure detection, diagnosis, and recovery for tool-augmented agents. Systematic failure injection generates 50k+ recovery-annotated trajectories; taxonomy-driven retrieval of 55+ failure exemplars at inference. Addresses cascading reasoning errors from API timeouts/exceptions. Applicable to cron_doctor.py self-healing, heartbeat pipeline resilience, and autonomous task robustness. Sources: arxiv.org/abs/2509.25238 (UIUC, arXiv:2509.25370) — First systematic error taxonomy for LLM agents (memory/reflection/planning/action/system), AgentErrorBench dataset of 500+ annotated failure trajectories, and AgentDebug framework for root-cause isolation with corrective feedback (+24% accuracy). Directly applicable to Clarvis episodic failure tracking, postflight error analysis, and building active learning from failures. Sources: arxiv.org/abs/2509.25370, github.com/ulab-uiuc/AgentDebug
- [ ] [RESEARCH_DISCOVERY 2026-03-01] Research: Neurosymbolic AI for Hybrid Agent Reasoning — Neural-symbolic integration patterns for LLM agents: Symbolic[Neural] (MCTS+neural eval like AlphaGo), Neural[Symbolic] (logical inference inside networks), and integration layers. 2025: Amazon deployed in Vulcan robots + Rufus. Addresses hallucination via symbolic grounding, enables explainable reasoning. IBM path-to-AGI framing. Applicable to clarvis_reasoning.py + brain.py knowledge graph. Sources: arxiv.org/html/2502.11269v1, sciencedirect.com/S2667305325000675, research.ibm.com/topics/neuro-symbolic-ai
- [ ] [RESEARCH_DISCOVERY 2026-03-01] Research: Tree Search + Process Reward Models for Deliberative Reasoning — Unified framework (MCTS + reward models + transition functions) for structured LLM reasoning. ReST-MCTS* combines process reward guidance with tree search for higher-quality reasoning traces. Process Reward Models evaluate intermediate reasoning steps, enabling test-time compute scaling. Directly applicable to clarvis_reasoning.py and QUICK/STANDARD/DEEP heartbeat modes. Sources: arxiv.org/html/2510.09988v1, openreview.net/forum?id=8rcFOqEud5, arxiv.org/html/2503.10814v1
- [ ] [RESEARCH_DISCOVERY 2026-03-01] Research: RAPTOR + Hierarchical RAG — Recursive Abstractive Processing for Tree-Organized Retrieval: recursively embed, cluster, summarize text into tree with multi-level abstraction. 20% improvement on complex QA via hierarchical retrieval. Recent 2025 enhancements: semantic chunking + Leiden-based adaptive graph clustering. Also covers A-RAG (agentic hierarchical retrieval interfaces). Directly applicable to brain.py retrieval quality and GraphRAG communities. Sources: arxiv.org/abs/2401.18059, arxiv.org/html/2602.03442v1, frontiersin.org/fcomp.2025.1710121