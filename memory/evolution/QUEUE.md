# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items auto-archived to QUEUE_ARCHIVE.md._

## P0 — Do Next Heartbeat


---

## Pillar 1: Consciousness & Integration (Phi > 0.80)

- [ ] [SEMANTIC_BRIDGE] Build semantic overlap booster for cross-collection pairs with overlap <0.40. Target: raise semantic_cross_collection from 0.477 to 0.55+.

## Pillar 2: Autonomous Execution (Success > 85%)

- [ ] [AUTONOMY_LOGIN] Given credentials in .env, log into a web service and verify logged-in state (session cookie present, profile page accessible). User provides credentials manually.
- [ ] [AUTONOMY_POST] Given credentials + a platform (e.g. GitHub Issues via API, or a forum), compose and post a message autonomously. Measure: post appears, content matches intent.
- [ ] [AUTONOMY_SCREENSHOT_ANALYZE] Take a screenshot of any given URL, analyze it with local vision (Qwen3-VL), extract structured info (page type, main elements, interactive components). Measure: extraction accuracy vs manual ground truth.
- [ ] [AUTONOMY_MULTI_STEP] Multi-step workflow benchmark — given a sequence of 3+ actions (navigate → search → click result → extract data), complete the full chain. Measure: step completion rate, total success.

## Research Sessions

- [ ] [BROWSER_SKILL_DOC] Create skills/web-browse/SKILL.md documenting browser_agent.py capabilities for M2.5.

## Pillar 3: Performance & Reliability (PI > 0.70)


## Pillar 4: Self-Improvement Loop

- [ ] [PROMPT_SELF_OPTIMIZE] Prompt self-optimization loop — record heartbeat prompt→outcome pairs in postflight, generate prompt variants for underperforming templates, A/B test across heartbeats. Inspired by APE/SPO from EvoAgentX survey. Files: heartbeat_preflight.py, heartbeat_postflight.py.
- [ ] [GOLDEN_TRACE_REPLAY] Successful trajectory replay (STaR pattern) — extract golden traces from successful heartbeats in postflight, store in clarvis-procedures, inject matching traces into preflight prompts as reference approaches. Files: heartbeat_postflight.py, heartbeat_preflight.py, procedural_memory.py.
- [ ] [NOVELTY_TASK_SCORING] Novelty-weighted task selection — compute embedding distance between candidate tasks and last N completed tasks, boost high-novelty tasks with `final_score = base_score * (1 + 0.3 * novelty)`. Prevents "more of the same" trap. Files: task_selector.py (or heartbeat_preflight.py scoring section).
- [ ] [PREFLIGHT_SPEED] Optimize preflight overhead (currently ~100s). Profile task_selector scoring loop — brain lookups for failure penalties on every task is the bottleneck.
- [ ] [BENCHMARK_RELIABILITY] Review performance_benchmark.py outputs after fixes — ensure no more phantom P0 tasks generated from stale data.

## Pillar 5: Agent Orchestrator (Multi-Project Command Center)

### Milestone 1: First PR Pipeline (target: this week)

### Milestone 2: Cron + Cost (target: next week)
- [ ] [ORCH_CRON_INTEGRATION] Add daily cron: `project_agent.py promote` + `orchestration_benchmark.py run` for active agents.
- [ ] [ORCH_SUDO_OPT] Request sudo: `sudo mkdir -p /opt/clarvis-agents && sudo chown agent:agent /opt/clarvis-agents`, then `project_agent.py migrate star-world-order`.

### Milestone 3: Multi-Agent (target: 2 weeks)
- [ ] [ORCH_SECOND_AGENT] Add second project agent for another repo — test multi-agent benchmark aggregation.

## Backlog

- [ ] [CRAWL4AI] Install Crawl4AI for automated research ingestion.
- [ ] [BROWSER_TEST] Test: navigate, extract, fill forms, multi-step workflows — comprehensive browser-use capability validation.
- [ ] [OLLAMA_TEST] Test Qwen3-VL with screenshots, verify CAPTCHA detection accuracy for local vision pipeline.
- [ ] [VISION_FALLBACK] Add local vision fallback to clarvis_eyes.py — use Ollama when API vision unavailable.
- [ ] [GITHUB_API_TASKS] Given existing GitHub credentials, perform repo management via API: create issues, comment on PRs, read notifications, manage labels. No account creation — user provides PAT.
- [ ] [AUTONOMY_SEARCH] Web search benchmark — given a question, use browser to search, evaluate results, extract answer. Compare with WebSearch tool accuracy.
- [ ] [UNIVERSAL_WEB_AGENT] Any webapp operated via natural language — given credentials and a task description, complete it. Requires session persistence + multi-step + error recovery.
- [ ] [CRON_OVERLAP_GUARD] Add mutual exclusion between cron_autonomous.sh and cron_implementation_sprint.sh — both can run at overlapping times and compete for Claude Code. Add a shared lockfile `/tmp/clarvis_claude_global.lock` checked by both scripts. If locked, the later job should queue its task to P0 and exit cleanly instead of blocking. Files: scripts/cron_autonomous.sh, scripts/cron_implementation_sprint.sh (Bash).

## Non-Code Improvements


## P1

- [ ] [RESEARCH_DISCOVERY 2026-03-02] Research: Corrective RAG + Agentic RAG Patterns (Yan et al. 2024; Singh et al. 2025 Survey) — Self-corrective retrieval: lightweight evaluator scores document relevance, triggers corrective actions (web search fallback, query refinement, decompose-recompose filtering). Agentic RAG survey covers reflection/planning/tool-use/multi-agent patterns for RAG pipelines. Directly applicable to brain.py retrieval quality scoring, context_compressor.py relevance filtering, and CONTEXT_RELEVANCE_FIX P0 task. Sources: arxiv.org/abs/2401.15884, arxiv.org/abs/2501.09136
- [ ] [RESEARCH_DISCOVERY 2026-03-02] Research: AgentDebug — Where LLM Agents Fail & How They Learn From Failures
- [ ] [RESEARCH_DISCOVERY 2026-03-02] Research: PALADIN — Self-Correcting Tool-Failure Recovery (ICLR 2026, arXiv:2509.25238) — Runtime failure detection, diagnosis, and recovery for tool-augmented agents. Systematic failure injection generates 50k+ recovery-annotated trajectories; taxonomy-driven retrieval of 55+ failure exemplars at inference. Addresses cascading reasoning errors from API timeouts/exceptions. Applicable to cron_doctor.py self-healing, heartbeat pipeline resilience, and autonomous task robustness. Sources: arxiv.org/abs/2509.25238 (UIUC, arXiv:2509.25370) — First systematic error taxonomy for LLM agents (memory/reflection/planning/action/system), AgentErrorBench dataset of 500+ annotated failure trajectories, and AgentDebug framework for root-cause isolation with corrective feedback (+24% accuracy). Directly applicable to Clarvis episodic failure tracking, postflight error analysis, and building active learning from failures. Sources: arxiv.org/abs/2509.25370, github.com/ulab-uiuc/AgentDebug
- [ ] [RESEARCH_DISCOVERY 2026-03-01] Research: Neurosymbolic AI for Hybrid Agent Reasoning — Neural-symbolic integration patterns for LLM agents: Symbolic[Neural] (MCTS+neural eval like AlphaGo), Neural[Symbolic] (logical inference inside networks), and integration layers. 2025: Amazon deployed in Vulcan robots + Rufus. Addresses hallucination via symbolic grounding, enables explainable reasoning. IBM path-to-AGI framing. Applicable to clarvis_reasoning.py + brain.py knowledge graph. Sources: arxiv.org/html/2502.11269v1, sciencedirect.com/S2667305325000675, research.ibm.com/topics/neuro-symbolic-ai
- [ ] [RESEARCH_DISCOVERY 2026-03-01] Research: Tree Search + Process Reward Models for Deliberative Reasoning — Unified framework (MCTS + reward models + transition functions) for structured LLM reasoning. ReST-MCTS* combines process reward guidance with tree search for higher-quality reasoning traces. Process Reward Models evaluate intermediate reasoning steps, enabling test-time compute scaling. Directly applicable to clarvis_reasoning.py and QUICK/STANDARD/DEEP heartbeat modes. Sources: arxiv.org/html/2510.09988v1, openreview.net/forum?id=8rcFOqEud5, arxiv.org/html/2503.10814v1
- [ ] [RESEARCH_DISCOVERY 2026-03-01] Research: RAPTOR + Hierarchical RAG — Recursive Abstractive Processing for Tree-Organized Retrieval: recursively embed, cluster, summarize text into tree with multi-level abstraction. 20% improvement on complex QA via hierarchical retrieval. Recent 2025 enhancements: semantic chunking + Leiden-based adaptive graph clustering. Also covers A-RAG (agentic hierarchical retrieval interfaces). Directly applicable to brain.py retrieval quality and GraphRAG communities. Sources: arxiv.org/abs/2401.18059, arxiv.org/html/2602.03442v1, frontiersin.org/fcomp.2025.1710121