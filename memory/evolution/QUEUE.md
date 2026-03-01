# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items auto-archived to QUEUE_ARCHIVE.md._

## P0 — Do Next Heartbeat

- [ ] [CODE_GEN_TEMPLATES] Build code generation templates library — extract patterns from the 10 most-edited scripts (brain.py, heartbeat_preflight.py, etc.), create reusable scaffolds in procedural_memory with tag `code_template`. Wire into preflight: when task is CODE-type, inject matching templates. Target: raise code_generation score from 0.57 to 0.70+. Files: procedural_memory.py, heartbeat_preflight.py.
- [ ] [CONTEXT_RELEVANCE_FIX] Fix context relevance (PI metric: 0.6, target 0.7) — the preflight brain search returns partially-relevant memories. Add MMR (Maximal Marginal Relevance) reranking to context_compressor.py: after initial retrieval, re-score by cosine similarity to task description AND penalize redundancy between selected items. Files: context_compressor.py, heartbeat_preflight.py.

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
- [ ] [RESEARCH_DISCOVERY 2026-03-01] Research: SICA — Self-Improving Coding Agent (Robeyns et al., ICLR 2025 Workshop) — Agent that iteratively edits its own codebase to improve performance, 17%→53% on SWE-bench Verified. Archive-based meta-agent selects best prior version, identifies improvements, implements them. Open-source Python framework. Directly applicable to Clarvis self-modification and cron_evolution. Sources: arxiv.org/abs/2504.15228, github.com/MaximeRobeyns/self_improving_coding_agent
- [ ] [RESEARCH_DISCOVERY 2026-03-01] Research: Cognitive Workspace — Active Memory Management for Functional Infinite Context (Agarwal et al. 2025) — Beyond RAG: hierarchical cognitive buffers with metacognitive awareness, 58.6% memory reuse rate, task-driven context optimization. Draws on Baddeley working memory model + Clark extended mind thesis. Directly applicable to working_memory.py, context_compressor.py, and brain.py context management. Sources: arxiv.org/abs/2508.13171
- [ ] [RESEARCH_DISCOVERY 2026-03-01] Research: Autonomous Tool Creation & Aggregation (LATM + ToolLibGen + ToolMaker, ACL 2025) — LLM agents that autonomously create, test, aggregate, and reuse tools from code/papers. LATM: closed-loop tool-making; ToolLibGen: multi-agent refactoring into reusable tool libraries; ToolMaker: 80% success turning papers into tools. Maps to skills/ architecture and procedural_memory.py skill lifecycle. Sources: arxiv.org/abs/2510.07768, github.com/KatherLab/ToolMaker, aclanthology.org/2025.acl-long.1266

## Pillar 3: Performance & Reliability (PI > 0.70)

- [ ] [BRIEF_COMPRESSION] Fix brief_compression metric (0.249, target 0.5) — context_compressor.py produces bloated summaries. Implement extractive-then-abstractive compression: first extract key sentences by TF-IDF salience, then merge into compact brief. Measure: output_tokens/input_tokens ratio should drop below 0.3. Files: context_compressor.py.

## Pillar 4: Self-Improvement Loop

- [ ] [PROMPT_SELF_OPTIMIZE] Prompt self-optimization loop — record heartbeat prompt→outcome pairs in postflight, generate prompt variants for underperforming templates, A/B test across heartbeats. Inspired by APE/SPO from EvoAgentX survey. Files: heartbeat_preflight.py, heartbeat_postflight.py.
- [ ] [GOLDEN_TRACE_REPLAY] Successful trajectory replay (STaR pattern) — extract golden traces from successful heartbeats in postflight, store in clarvis-procedures, inject matching traces into preflight prompts as reference approaches. Files: heartbeat_postflight.py, heartbeat_preflight.py, procedural_memory.py.
- [ ] [NOVELTY_TASK_SCORING] Novelty-weighted task selection — compute embedding distance between candidate tasks and last N completed tasks, boost high-novelty tasks with `final_score = base_score * (1 + 0.3 * novelty)`. Prevents "more of the same" trap. Files: task_selector.py (or heartbeat_preflight.py scoring section).
- [ ] [PREFLIGHT_SPEED] Optimize preflight overhead (currently ~100s). Profile task_selector scoring loop — brain lookups for failure penalties on every task is the bottleneck.
- [ ] [BENCHMARK_RELIABILITY] Review performance_benchmark.py outputs after fixes — ensure no more phantom P0 tasks generated from stale data.
- [ ] [CODE_GEN_SCORING_WIRE] Wire code_generation score to actual heartbeat outcomes — in heartbeat_postflight.py, when the task involved code changes (detect via git diff), measure: files touched, syntax errors (run `python3 -c "compile(open(f).read(), f, 'exec')"` on changed .py files), and whether the task succeeded. Feed results to self_model.py `_score_code_generation()`. Currently code_gen score is mostly static.

## Pillar 5: Agent Orchestrator (Multi-Project Command Center)

### Milestone 1: First PR Pipeline (target: this week)
- [x] [ORCH_GOLDEN_QA] Golden Q/A set created — 12 repo-specific queries, P@3=1.0, MRR=1.0. Done 2026-03-01.
- [x] [ORCH_BENCHMARK_WIRE] Composite scoring (5 dims, weighted) + retrieval via lite_brain.py. Composite: 0.75. Done 2026-03-01.
- [ ] [ORCH_SWO_BUILD] Run build+test: `project_agent.py spawn star-world-order "Run npm install, npm run build, npm run test. Store procedures."`.
- [ ] [ORCH_SWO_PR] First PR: spawn code-change task, push branch, `gh pr create`. Validate end-to-end PR pipeline.

### Milestone 2: Cron + Cost (target: next week)
- [ ] [ORCH_CRON_INTEGRATION] Add daily cron: `project_agent.py promote` + `orchestration_benchmark.py run` for active agents.
- [ ] [ORCH_COST_TRACKING] Wire actual OpenRouter cost data per agent task window.
- [ ] [ORCH_SUDO_OPT] Request sudo: `sudo mkdir -p /opt/clarvis-agents && sudo chown agent:agent /opt/clarvis-agents`, then `project_agent.py migrate star-world-order`.

### Milestone 3: Multi-Agent (target: 2 weeks)
- [ ] [ORCH_SECOND_AGENT] Add second project agent for another repo — test multi-agent benchmark aggregation.
- [ ] [ORCH_RETRY_LOGIC] Add retry/fallback: if task fails, re-queue with adjusted prompt (max 2 retries).
- [ ] [ORCH_PROMOTION_BRAIN] After promote, store top procedures in Clarvis brain with tag `project:<name>`.

## Backlog

- [ ] [CRAWL4AI] Install Crawl4AI for automated research ingestion.
- [ ] [BROWSER_TEST] Test: navigate, extract, fill forms, multi-step workflows — comprehensive browser-use capability validation.
- [ ] [OLLAMA_TEST] Test Qwen3-VL with screenshots, verify CAPTCHA detection accuracy for local vision pipeline.
- [ ] [VISION_FALLBACK] Add local vision fallback to clarvis_eyes.py — use Ollama when API vision unavailable.
- [ ] [GITHUB_API_TASKS] Given existing GitHub credentials, perform repo management via API: create issues, comment on PRs, read notifications, manage labels. No account creation — user provides PAT.
- [ ] [AUTONOMY_SEARCH] Web search benchmark — given a question, use browser to search, evaluate results, extract answer. Compare with WebSearch tool accuracy.
- [ ] [UNIVERSAL_WEB_AGENT] Any webapp operated via natural language — given credentials and a task description, complete it. Requires session persistence + multi-step + error recovery.
- [ ] [CRON_OVERLAP_GUARD] Add mutual exclusion between cron_autonomous.sh and cron_implementation_sprint.sh — both can run at overlapping times and compete for Claude Code. Add a shared lockfile `/tmp/clarvis_claude_global.lock` checked by both scripts. If locked, the later job should queue its task to P0 and exit cleanly instead of blocking. Files: scripts/cron_autonomous.sh, scripts/cron_implementation_sprint.sh (Bash).

## P1

- [ ] [RESEARCH_DISCOVERY 2026-03-01] Research: Multi-Agent Debate for Reasoning Verification (Du et al. 2024 + A-HMAD 2025) — Multiple LLM agents debate to improve factuality and reasoning. A-HMAD achieves 4-6% accuracy gains with 30% fewer factual errors. Critical finding: intrinsic reasoning strength and group diversity matter more than debate structure. Applicable to clarvis_reasoning.py confidence calibration and self-verification. Sources: arxiv.org/abs/2305.14325, arxiv.org/abs/2511.07784, link.springer.com/article/10.1007/s44443-025-00353-3
- [ ] [RESEARCH_DISCOVERY 2026-03-01] Research: LATS — Language Agent Tree Search (Zhou et al., ICML 2024) — Unifies reasoning, acting, and planning via MCTS over LLM actions with self-reflection and environment feedback. LLM serves as agent, value function, and optimizer simultaneously. 92.7% pass@1 on HumanEval. Directly applicable to heartbeat task selection and clarvis_reasoning.py planning. Sources: arxiv.org/abs/2310.04406, github.com/lapisrocks/LanguageAgentTreeSearch
- [ ] [RESEARCH_DISCOVERY 2026-03-01] Research: Neurosymbolic AI for Hybrid Agent Reasoning — Neural-symbolic integration patterns for LLM agents: Symbolic[Neural] (MCTS+neural eval like AlphaGo), Neural[Symbolic] (logical inference inside networks), and integration layers. 2025: Amazon deployed in Vulcan robots + Rufus. Addresses hallucination via symbolic grounding, enables explainable reasoning. IBM path-to-AGI framing. Applicable to clarvis_reasoning.py + brain.py knowledge graph. Sources: arxiv.org/html/2502.11269v1, sciencedirect.com/S2667305325000675, research.ibm.com/topics/neuro-symbolic-ai
- [ ] [RESEARCH_DISCOVERY 2026-03-01] Research: Tree Search + Process Reward Models for Deliberative Reasoning — Unified framework (MCTS + reward models + transition functions) for structured LLM reasoning. ReST-MCTS* combines process reward guidance with tree search for higher-quality reasoning traces. Process Reward Models evaluate intermediate reasoning steps, enabling test-time compute scaling. Directly applicable to clarvis_reasoning.py and QUICK/STANDARD/DEEP heartbeat modes. Sources: arxiv.org/html/2510.09988v1, openreview.net/forum?id=8rcFOqEud5, arxiv.org/html/2503.10814v1
- [ ] [RESEARCH_DISCOVERY 2026-03-01] Research: RAPTOR + Hierarchical RAG — Recursive Abstractive Processing for Tree-Organized Retrieval: recursively embed, cluster, summarize text into tree with multi-level abstraction. 20% improvement on complex QA via hierarchical retrieval. Recent 2025 enhancements: semantic chunking + Leiden-based adaptive graph clustering. Also covers A-RAG (agentic hierarchical retrieval interfaces). Directly applicable to brain.py retrieval quality and GraphRAG communities. Sources: arxiv.org/abs/2401.18059, arxiv.org/html/2602.03442v1, frontiersin.org/fcomp.2025.1710121