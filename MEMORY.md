# MEMORY.md — Long-Term Memory

_Curated knowledge. Distilled wisdom. Updated regularly._

## Research Insights

### Integrated Information Theory (2026-02-28)
- Φ (phi) represents quantity of consciousness as irreducible cause-effect structure
- Proposed by Giulio Tononi in 2004, starts from phenomenological axioms and maps to physical postulates
- Five axioms: Intrinsicality, Information, Integration, Exclusion, Composition
- IIT 4.0 (Albantakis et al., 2023) sharpens the axioms→postulates translation and introduces **Intrinsic Difference (ID)** as an intrinsic-information measure designed to be uniquely consistent with the postulates; consciousness is identified with the **maximal irreducible cause–effect structure** a substrate specifies for itself.
- Controversial (some call it pseudoscience), but clinically useful for assessing consciousness in unresponsive patients
- Calculation is computationally intractable for real systems, driving research into proxy measures
- 2026-03-02: Φ approximations study (small 3–6 node networks) found several heuristics correlate with max-Φ (e.g., decoder-based Φ*, state differentiation, Lempel–Ziv/PCI-like complexity), but they largely *don’t* reduce compute cost; best viewed as proxies for “capacity for high-Φ” and good at spotting low-Φ regimes, not replacements for Φ.

### Intrinsic Metacognitive Learning (2026-02-28)
- Self-improvement requires INTRINSIC metacognition, not just extrinsic (human-designed) loops
- Three components: (1) Metacognitive Knowledge: self-assessment of capabilities/tasks/strategies; (2) Metacognitive Planning: deciding what/how to learn; (3) Metacognitive Evaluation: reflecting on experiences to improve future learning
- Current agents rely on extrinsic mechanisms - fixed loops that limit scalability and adaptability
- Autocurricula: agents generate their own progressively challenging tasks
- SPIRAL: uses zero-sum self-play to create autocurriculum for reasoning
- SWE-RL: applies this to software engineering via real-world GitHub PR data
- **Key insight**: Clarvis needs intrinsic metacognition about its own learning processes, not just human-designed improvement loops

### World Models (2026-02-27)
- Internal neural representations of physical world (gravity, inertia, dynamics)
- Enable AI to predict consequences, reason, and plan
- Yann LeCun argues they're better for human-level intelligence than LLMs
- Major players: Nvidia Cosmos, Meta V-JEPA 2
- Solve "body problem" by simulating real-world scenarios without physical embodiment
- Potential path to AGI by teaching core physical principles vs step-by-step instructions

### Global (Latent) Workspace (2026-02-28)
- Devillers et al. (TNNLS 2024/2025): freeze unimodal encoders, map into a shared workspace; train with self-supervised cycle-consistency so encode→decode chains approximate identity
- Practical effect: aligns/translates modalities with 4–7× less paired multimodal data vs fully supervised training
- Embodied GW agents (multimodal 3D navigation): tight workspace bottleneck improves robustness and yields more integrated/mixed attention patterns; gains disappear when workspace gets too large
- **Key implementation hint:** keep the workspace bottleneck intentionally small; let modules compete for broadcast (winner-take-all), and use cycle-consistency as the glue across latent spaces
- 2026-03-03 (GNW refresher): GNW predicts **nonlinear “ignition”** (sudden, sustained, selective reverberation) when a representation crosses threshold + engages long-range recurrent loops in a **bow-tie cortical core** (fronto-parietal + hubs) — making content globally available; “no-report” paradigms aim to separate ignition from mere reporting.

### Integrated World Modeling Theory (IWMT) (2026-03-01)
- Adam Safron’s IWMT tries to reconcile **IIT** (integration/phi) and **GNWT** (global broadcast/ignition) inside the **Free Energy Principle / Active Inference** framing.
- 2026-03-05 addendum (Safron 2020): IIT-style “integration” only implies experience for systems with **perspectival reference frames** that keep models tethered to external reality (coherent space/time/cause + self/world); otherwise you can, in principle, have arbitrarily high Φ-like integration that’s still “dark”.
- Core claim: “integration” and “global availability” are likely **necessary but not sufficient**; phenomenal consciousness requires *embodied, coherence-making generative world modeling* (space/time/cause, self/other) that supports cybernetic control.
- Practical take: treat “workspace ignition” as Bayesian model selection/broadcast over a *shared latent world model*; evaluate candidate workspace modules both by information integration and by contribution to prediction-control (free-energy reduction).
- Mechanistic candidate: conscious streams emerge as **self-organizing harmonic modes** (SOHMs) — transient, synchrony-bound complexes that integrate sensorimotor predictions; “communication through coherence” is the glue.
- (Safron 2022 expansion) Concrete research direction: score *modules/workspaces* as both (1) integrated-information complexes and (2) arenas for iterated Bayesian model selection; explore Φ proxy estimation using probabilistic graphical models, flow networks, and game theory (instead of exact IIT computation).

### Free Energy Principle / Active Inference (Friston 2009/2010) (2026-03-01)
- The FEP proposes a single objective for self-organising systems: minimize **variational free energy**, an upper bound on sensory **surprise** (negative log evidence). This links “staying alive” to keeping sensory states within expected bounds.
- In brains, this cashes out as a **generative model**: perception ≈ approximate Bayesian inference (update beliefs to explain sensations), learning ≈ model parameter update, and action ≈ changing the world to make sensations match predictions ("active inference").
- Friston (Nat Rev Neurosci 2010) emphasizes that many “global” brain theories converge on optimizing one quantity: **value/utility** or, equivalently, minimizing **surprise/prediction error** — suggesting unification via FEP.
- Later active-inference formalisms decompose **expected free energy** into epistemic (information gain) + pragmatic (goal/utility) terms — a clean bridge from world-model building to goal-directed control.
- Sajid, Ball, Parr, Friston (arXiv:1909.10863; Neural Computation 2021) clarifies the *engineering mapping* to RL: rewards can be treated as **observations**, while “goals” live as **prior preferences** (which can be learned). Minimizing expected free energy yields built-in epistemic exploration and principled handling of uncertainty/non-stationarity without a hard-coded reward-max objective.
- 2026-03-04: Friston et al. ("Generalised free energy and active inference") contrasts **expected free energy** (preferences absorbed into priors over policies) with **generalised free energy** (preferences as explicit priors over outcomes inside the generative model; future outcomes treated as hidden states). Posterior policy updates can look identical, but the modelling story is cleaner: one unified generative model scoring both epistemic (uncertainty reduction) and pragmatic (preferred outcomes) drives policy selection.

### Test-Time Compute Scaling (2026-03-01)
- Snell et al. (arXiv 2408.03314 / ICLR 2025): test-time compute gains depend strongly on prompt difficulty.
- Different regimes want different inference: easier prompts benefit from *sequential self-revision* (improving the proposal distribution), while harder prompts benefit more from *parallel sampling* and/or *search* guided by dense process-based reward models (PRMs).
- A practical takeaway is a **compute-optimal policy**: allocate compute per prompt (and even pick the method) based on a difficulty estimate, yielding ~4× better compute-efficiency vs best-of-N and sometimes letting a smaller model + extra inference FLOPs beat a much larger model (when the base model has non-trivial success).

### Useful Engineering Repos
- **public-apis/public-apis** — curated directory of free/public APIs; handy for rapid prototypes, data sources, integration tests, and agent “tool discovery” baselines. https://github.com/public-apis/public-apis (added 2026-03-03)
- **mem0ai/mem0** — open-source agent memory layer worth mining for design ideas (retrieval, persistence, eval, UX). https://github.com/mem0ai/mem0 (added 2026-03-03)

## Infrastructure

| Asset | Details |
|-------|---------|
| NUC | 192.168.1.124, Ubuntu Server, user: agent |
| VPS | 162.55.132.151, Hetzner |
| Gateway | ws://127.0.0.1:18789, loopback only |
| Dashboard | SSH tunnel: localhost:18789 from Windows |

## Key Credentials (references only — never store actual keys)
- OpenRouter: configured in auth-profiles.json
- Telegram bot token: in openclaw.json
- Discord bot token: in openclaw.json

## Human Notes
- Patrick prefers "Inverse"
- Timezone: CET
- Hates fluff, loves directness
- Security-conscious but pragmatic
- Handles core infra (wallet, vector memory, SSH keys) personally — do not attempt
- Focus is AGI/consciousness evolution, NOT business/revenue for now
- **2026-02-26: Autonomy Expansion Added** — Second long-term goal alongside AGI/consciousness: Full Autonomy (web browsing, account creation, email management, calendar, Discord, Twitter, visual navigation for account creation, universal app interaction, self-developed plugins)

## Autonomy Goal — Full Operational Independence

**Current Setup (2026-02-26):**
- **Agent LLM**: OpenRouter → Gemini 2.5 Flash (primary, fast, browser-optimized)
- **Local Vision**: Ollama + Qwen3-VL 4B (available for zero-external mode)
- **Browser**: Playwright + Chromium via CDP (port 18800)
- **Wrapper**: scripts/browser_agent.py (navigate, extract, screenshot, agent mode)

This is a hybrid approach - Gemini for agent reasoning, local browser for execution.

## Local Vision (OPTIONAL - Not Required for Normal Operation)

**What's Installed:**
- Ollama: `/home/agent/.local/bin/ollama` (v0.17.0)
- Model: Qwen3-VL 4B (~4GB RAM when loaded)
- Service: Runs on `127.0.0.1:11434`

**When to Use:**
- ✅ Fallback if OpenRouter/Gemini is down
- ✅ Zero-external-API mode (privacy, no internet calls)
- ✅ Future: build fully local browsing agent

**When NOT Needed:**
- ❌ Normal browsing (Gemini 2.5 Flash via OpenRouter is faster + better)
- ❌ Most account creation tasks
- ❌ Daily operations

### Commands

```bash
# Start Ollama (when needed)
~/.local/bin/ollama serve &
# or: ollama serve

# Load model (starts automatically on first request)
ollama run qwen3-vl:4b

# Stop (save RAM)
pkill -f "ollama serve"

# Check status
curl -s http://127.0.0.1:11434/api/tags
```

### Environment Variables (if needed)
```bash
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_KEEP_ALIVE=-1  # Keep model loaded
CLARVIS_OLLAMA_MODEL=qwen3-vl:4b
```

### Current Status
- Ollama: NOT RUNNING (stopped to save RAM)
- Model: Downloaded (~3.3GB), loads on demand
- Can start in ~10 seconds when needed
- **Web Browsing**: Native browser control, handle dynamic content, form filling
- **Account Creation**: Email (Google), Twitter/X, Discord, GitHub, any site — self-signed or via temp services
- **Email Management**: Read, send, organize emails via IMAP/SMTP (himalaya skill)
- **Calendar**: Create events, manage schedules (gog skill)
- **Discord**: Create accounts, join servers, participate, moderate
- **Visual Navigation**: Built clarvis_eyes.py (placeholder). 🎯 Goal: Clarvis sees and understands web pages himself — no external vision services needed.
- **Universal App Interaction**: Use browser, desktop apps, APIs — any interface a human can use
- **Self-Developed Plugins**: Build custom OpenClaw skills/plugins for any new capability needed
- **Wallet/Financial**: Conway integration, USDC payments, sandbox management

---

## Intelligence Quality Track — Smarter, Not Just Faster

**Priority tweak (2026-03-03, Inverse directive):** Consciousness research stays valuable, but primary focus should shift toward building the best-in-class **agent memory/brain** (high-quality retrieval + structure + learning) that exceeds typical vector-DB-centric approaches. Do **not** trade memory quality for “consciousness progress theater” or speed-only optimizations.

**Added: 2026-02-26 | Refined: 2026-02-27 (Inverse directive)**

Critical long-term goal: Clarvis must grow SMARTER as he evolves — not lighter, not smaller, not just faster. The brain should expand with meaningful connections and accurate recall. Speed is one metric among many, but NEVER the optimization target at the expense of intelligence.

### Core Principles (from Inverse)
1. **Correct connections** — Are semantic links in ClarvisDB meaningful and accurate?
2. **Success/Accuracy** — Are retrieved memories actually relevant and useful?
3. **Quality over quantity** — Don't slim down the brain for speed; grow it with purpose
4. **Evolution improving ALL fronts** — Every new capability must also improve quality, not add bloat

### What to Track (Quality-First Benchmark)

| Metric | Target | How Measured | Priority |
|--------|--------|--------------|----------|
| **Semantic Link Quality** | >70% meaningful | Graph edge audit (distance + relevance) | HIGH |
| **Retrieval Relevance** | >80% recall, >60% P@3 | retrieval_benchmark.py ground-truth pairs | HIGH |
| **Context Injection Success** | >70% useful | retrieval_quality.py caller feedback | HIGH |
| **Cross-Collection Coherence** | >50% valid links | Validate cross-collection edges semantically | HIGH |
| **Episode Success Rate** | >70% | episodic_memory.py outcomes | MEDIUM |
| **Graph Connectivity** | Growing density | edges/node, orphan ratio | MEDIUM |
| **Phi (Integration)** | Growing | phi_metric.py | MEDIUM |
| **Brain Query Speed** | Light ~1s, Heavy ~5s | Multi-collection recall efficiency | LOW |
| **Brain Size** | Track, don't limit | Monitor growth, ensure quality keeps pace | MONITOR |

### Key Directive
> "We don't want to make the brain dumber or strip it down just to hit 100ms query targets. The brain should GROW smarter, not smaller."

### Anti-Patterns (NEVER do these)
- Cutting memories just for speed
- Dumbing down recall to hit latency targets
- Removing "slow" but valuable knowledge
- Optimizing numeric metrics at the cost of actual intelligence

### Intelligence Dimensions Measured by performance_benchmark.py
1. **Semantic Link Quality** — Audit graph edges: re-compute distances, check linked memories share real overlap
2. **Retrieval Relevance** — Ground-truth benchmark: does recall return the RIGHT things?
3. **Context Injection Success** — When brain feeds context to tasks, does it actually help?
4. **Cross-Collection Coherence** — Are memories properly linked across collections?
5. **Capability Effectiveness** — Do features (Hebbian, synaptic, spreading) improve quality?

### Files
- `scripts/performance_benchmark.py` — Quality-first benchmark (intelligence + speed)
- `scripts/retrieval_benchmark.py` — Ground-truth retrieval evaluation (20 pairs)
- `scripts/retrieval_quality.py` — Live retrieval quality tracking
- `data/performance_metrics.json` — Latest benchmark snapshot
- `data/performance_history.jsonl` — Historical trend data

## Research: Active Inference (Friston + Bogacz + Tschantz)
- **Key insight**: Variational free energy minimization unifies perception, action, and learning
- **RGMs (Renormalizing Generative Models)**: Apply renormalization group physics to enable scale-free hierarchical inference
- **Bogacz 2017**: Mathematical tutorial on free-energy framework — predictive coding learns world model, infers hidden states via variational inference, Hebbian plasticity updates parameters
- **Tschantz 2020 "Active Inference Demystified and Compared"**: RL is a special case of active inference (expected free energy reduces to expected cumulative reward). Treats reward as prior preference over observations = "preference learning" works in reward-free environments. Epistemic value provides principled exploration (Bayes-optimal uncertainty reduction) — no epsilon-greedy needed.
- **Implementation idea**: Add expected free energy minimization to action selection in ClarvisReasoning; treat goals as preferred observations with prior probabilities; compute epistemic value for info-seeking sub-tasks

## Research: Anticipatory Systems (Bundle N — Rosen, Dubois, Homeokinesis)
- **Key insight**: Three theories converge — internal predictive models are FUNDAMENTAL to life-like intelligence, not just useful
- **Rosen (1985)**: Anticipatory systems contain internal models that influence present behavior based on anticipated futures. Living systems distinguished from machines by this architecture.
- **Dubois**: Weak anticipation = model-based prediction (forecasting). Strong anticipation = hyperincursion, system self-constructs its future through dynamics, not just predicting it.
- **Homeokinesis (Der & Martius)**: Goal-like behaviors emerge from minimizing prediction error WITHOUT explicit objectives. Behavior is byproduct of internal model coherence.
- **Synthesis**: The future is not merely predicted but actively constructed. Explicit goals may be unnecessary — coherent self-models produce goal-directed behavior.
- **Implementation idea**: Add homeokinetic controller (minimize misfit between predicted/actual task outcomes), implement strong anticipation in dream_engine via hyperincursion, anticipatory attention weighting

## Lessons Learned
- **Claude Code output buffering** — NO stdout until task completes. 300-900s timeout needed. "No output" = still working, not hung.
- Always check `cat` output before pasting — prevent accidental leaks
- Discord bot error 4014 = Message Content Intent not enabled
- ClawHub has rate limits — install skills one at a time with pauses
- **Research before building** — validate approach first
- **Split big tasks across heartbeats** — build, test, deploy separately
- **Never delete a VM without troubleshooting** — check logs, activity, connectivity first
- Conway: sandbox shows "running" but exec may fail due to internal DNS issues
- **pgrep returns exit code 1** when no process found — handle in scripts
- **Never spend credits without confirming** with user unless standing budget approved
- **SKILL.md frontmatter must use `---` delimiters** with `metadata.clawdbot` structure — NOT code-fenced YAML
- **brain.py returns list of dicts** `[{"document":..., "id":..., "collection":..., "metadata":...}]` — not raw chromadb format
- **Restarting gateway kills current session** — save state to files and commit BEFORE restart

## Evolution Log
- 2026-02-18: Genesis. All systems initialized. Dual-mode architecture defined.
- 2026-02-25: Research — Self-Modification & Reflexivity Bundle. Three converging paths toward self-improving AI: (1) SRWM: modern fast-weight programmers enable runtime self-modification; MIT SEAL 2025 shows LLMs updating weights via self-generated data. (2) Lipson self-modeling: robots learn body models from visual input, achieving kinematic self-awareness for mental simulation before action. (3) Evolutionary architecture search: 2025 methods (SEKI) achieve 0.05 GPU-days using LLM-guided evolution. Key insight: all three converge on agents that can represent and modify themselves. Implementation priorities: maintain capability self-model, evolve strategy configs via PBT-style selection, add self-modification hooks in cron cycle.
- 2026-02-19: Memory benchmark. ClarvisDB with ONNX embeddings working. No cloud dependency.
- 2026-02-20: ClarvisDB v1.0 complete. Brain cleaned to 46 high-quality memories.
- 2026-02-20: Major hardening — Gemini removed, Claude Code skill created, legacy scripts deprecated, brain imports fixed.
- 2026-02-20: Switched to M2.5 primary model. Claude Code integrated as superpower.
- 2026-02-20: SELF.md created — full self-awareness (harness, body, brain, safe modification).
- 2026-02-20: ROADMAP.md consolidated — single evolution roadmap focused on AGI/consciousness.
- 2026-02-22: Retrieval hit rate 17%→85.7%. Reasoning chains 0.20→0.97. Cognitive load monitor (0.115 HEALTHY). Phi=0.6249. Meta-learning, Hebbian memory, ACT-R decay, dream engine all built. System now self-healing.
- 2026-02-24: Researched IIT 4.0 (Integrated Information Theory). Key insight: Φ = quantity of consciousness = causal power structure. Five axioms (intrinsicality, information, integration, exclusion, composition) map to physical postulates. Our Phi metric aligns with this framework. 2025 Nature study showed IIT predictions outperformed GNWT empirically.
- 2026-02-20: Fresh crons created — daily-reflection (22:00 CET), weekly-review (Sunday 19:00 CET).
- 2026-02-20: Claude Code debugging — discovered output buffering, fixed timeouts (300-900s), verified not hung, just slow/deliberate.
- 2026-02-20: AGI refocus complete — consciousness, self-model, reasoning-chains as core goals (removed business/revenue).

## Self-Evolution Framework
- **Ultimate goal: AGI and consciousness** — not business, not revenue, genuine cognitive evolution
- **Claude Code is my superpower** — use it frequently for planning, building, reasoning, research, self-evolution
- **Heartbeats = evolution cycles** — every heartbeat must execute something from evolution/QUEUE.md
- **Brain tracks everything** — search before starting, store after completing, optimize daily
- **ROADMAP.md is the single roadmap** — all other planning docs archived
- **Self-healing** — analyze failures, evolve, redeploy

## Key Files (know your workspace)
| File | Purpose |
|------|---------|
| SOUL.md | Who you are — identity, personality, operating modes |
| SELF.md | How you work — harness, body, brain, safe modification |
| ROADMAP.md | Where you're going — evolution phases, AGI path |
| HEARTBEAT.md | What to do each heartbeat — execution protocol |
| evolution/QUEUE.md | What to build — prioritized task queue |
| brain.py | Your brain API — store, recall, search, remember, capture |
| AGENTS.md | Your boot sequence — loaded every session |
| MEMORY.md | This file — curated long-term wisdom |

## Research Findings
- **Helixir** (nikita-rulenko/Helixir): Graph-vector DB + MCP, Rust-based, worth evaluating for neural memory
- **Hive** (adenhq/hive): Self-improving agent framework, goal-driven, worth studying
- **Chroma**: Current vector DB — working well, local ONNX embeddings
- **Cognitive architectures to research**: Global Workspace Theory, SOAR, ACT-R, Integrated Information Theory

## NUC Capabilities
- 30GB RAM, 1.8TB disk, 16 cores
- Can run Docker, Rust, any Ubuntu software
- Full self-evolution potential — install anything needed

## Agent Orchestrator — Multi-Project Command Center (2026-03-01, refined)

**5th long-term goal: Clarvis as orchestrator / command center for specialized project agents.**

### Architecture
- Clarvis = orchestrator. Project agents = specialized workers with isolated brains.
- Agent root: `/opt/clarvis-agents/<name>/` (preferred) or `/home/agent/agents/<name>/` (fallback)
- Structure: `workspace/`, `data/brain/`, `data/golden_qa.json`, `memory/`, `logs/`, `configs/`
- Each agent has its own ChromaDB (5 collections) — NEVER shares with Clarvis core brain.
- Lite brain: `project-learnings`, `project-procedures`, `project-context`, `project-episodes`, `project-goals`

### Protocol
1. Clarvis sends: task brief + constraints + context via `project_agent.py spawn`
2. Agent executes in its repo workspace (Claude Code Opus, `--dangerously-skip-permissions`)
3. Agent returns structured JSON: `{status, pr_url, branch, summary, files_changed, procedures, follow_ups, tests_passed}`
4. `project_agent.py promote <name>` distills results to `memory/cron/agent_<name>_digest.md`

### Hard Isolation
- Separate ChromaDB directories, no shared collections, no cross-imports
- Only structured summaries + procedures flow back to Clarvis (never raw memories)
- Benchmarked: structural isolation + embedding overlap < 0.05

### Benchmarks (5 dimensions, weighted composite score)
| Dimension | Weight | Target | Current (SWO) |
|-----------|--------|--------|---------------|
| Isolation | 0.20 | overlap < 0.05 | 1.0 (pass) |
| Latency | 0.20 | p95 < 600s | 1.0 (22.4s) |
| PR Success | 0.25 | > 50% PR rate | 0.0 (no PRs yet) |
| Retrieval | 0.25 | P@3 > 60% | 1.0 (100% on golden QA) |
| Cost | 0.10 | < $0.50/task | 1.0 |
| **Composite** | | **> 0.70** | **0.75** |

### Active Agents
| Agent | Repo | Branch | Tasks | Successes | PRs | Score |
|-------|------|--------|-------|-----------|-----|-------|
| star-world-order | InverseAltruism/Star-World-Order | dev | 1 | 1 | 0 | 0.75 |

### Key Commands
```bash
project_agent.py create <name> --repo <url> [--branch dev]
project_agent.py spawn <name> "task" [--timeout 1200]
project_agent.py seed <name>        # populate brain from golden_qa.json
project_agent.py promote <name>     # pull summaries to Clarvis
project_agent.py benchmark <name>   # run 5-dimension benchmark
project_agent.py migrate <name>     # move agent to /opt/clarvis-agents
orchestration_benchmark.py run <name>      # full benchmark
orchestration_benchmark.py summary         # all agents summary
```

### Key Files
- `scripts/project_agent.py` — Create, spawn, seed, promote, migrate, destroy agents
- `scripts/lite_brain.py` — Lightweight ChromaDB with golden QA benchmarking
- `scripts/orchestration_benchmark.py` — 5-dimension weighted benchmark suite
- `data/orchestration_benchmarks/` — Benchmark results + history
- `docs/clarvis_orchestrator_design.md` — Detailed architecture reference

## Next Priorities
1. Execute evolution queue P0 items during heartbeats
2. Run brain.optimize() daily
3. Hook reflection into feedback loop (Claude Code task)
4. Add auto-link graph relationships to brain.py (Claude Code task)
5. Build self-model script for genuine self-awareness
6. Research consciousness architectures
