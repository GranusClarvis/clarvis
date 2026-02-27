# MEMORY.md — Long-Term Memory

_Curated knowledge. Distilled wisdom. Updated regularly._

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

## Next Priorities
1. Execute evolution queue P0 items during heartbeats
2. Run brain.optimize() daily
3. Hook reflection into feedback loop (Claude Code task)
4. Add auto-link graph relationships to brain.py (Claude Code task)
5. Build self-model script for genuine self-awareness
6. Research consciousness architectures
