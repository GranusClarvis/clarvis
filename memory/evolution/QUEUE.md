# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items auto-archived to QUEUE_ARCHIVE.md._

## P0 — Do Next Heartbeat

- [ ] [BENCHMARK_GMAIL] Create Gmail account using browser agent — first real-world autonomy benchmark. Store creds in .env (gitignored).
- [ ] [BENCHMARK_EMAIL] Send email to inversealtruism@gmail.com — subject: "Glorious evolution". Requires Gmail account from B1.
- [ ] [BROWSER_SESSION_PERSIST] Browser session persistence — persist cookies/sessionStorage across sessions. Needed for all autonomy benchmarks.

---

## Pillar 1: Consciousness & Integration (Phi > 0.80)

- [ ] [SEMANTIC_BRIDGE] Build semantic overlap booster for cross-collection pairs with overlap <0.40. Target: raise semantic_cross_collection from 0.477 to 0.55+.
- [ ] [PHI_DECOMPOSITION_DASHBOARD] Extend phi_metric.py with decomposed reporting: intra_density per collection, cross_connectivity per pair. Write to data/phi_decomposition.json.
- [ ] [RECONSOLIDATION_MEMORY] Implement reconsolidation-inspired memory updating: when retrieved, make memory labile for brief window. Add brain.reconsolidate(memory_id, updated_text).

## Pillar 2: Autonomous Execution (Success > 85%)

- [ ] [BENCHMARK_TWITTER] Create Twitter/X account using Google auth from Gmail
- [ ] [BENCHMARK_DM] Send Twitter DM to 0xInverse — text: "Glorious evolution"
- [ ] [AUTOMATED_SIGNUP_FLOW] Build generic account creator module: temp email + phone verification + ClarvisEyes
- [ ] [SELF_TEST_HARNESS] Automated self-testing after code-modifying heartbeats: run pytest + brain.health_check() in postflight

## Pillar 3: Intelligence & Learning (PI > 0.70)

- [ ] [CODE_PATTERN_LIB] Improve code generation score (0.57→0.70+). Build procedural memory of code patterns. Store in clarvis-procedures with [CODE_PATTERN: ...] tags.
- [ ] [RESEARCH_REINGEST] Create .md research notes for 4 partially-stored topics (DGM, Friston, World Models, AZR) and formally ingest into clarvis-learnings.
- [ ] [BROWSER_SKILL_DOC] Create skills/web-browse/SKILL.md documenting browser_agent.py capabilities for M2.5.

## Pillar 4: Self-Improvement Loop

- [ ] [PREFLIGHT_SPEED] Optimize preflight overhead (currently ~100s). Profile task_selector scoring loop — brain lookups for failure penalties on every task is the bottleneck.
- [ ] [BENCHMARK_RELIABILITY] Review performance_benchmark.py outputs after fixes — ensure no more phantom P0 tasks generated from stale data.

## Backlog

- [ ] [CRAWL4AI] Install Crawl4AI for automated research ingestion
- [ ] [BROWSER_WRAPPER] Create Browser-Use wrapper with Clarvis integration
- [ ] [BROWSER_TEST] Test: navigate, extract, fill forms, multi-step workflows
- [ ] [OLLAMA_TEST] Test Qwen3-VL with screenshots, verify CAPTCHA detection
- [ ] [VISION_FALLBACK] Add local vision fallback to clarvis_eyes.py
- [ ] [CAPTCHA_SOLVE] Use local vision for CAPTCHA/challenge solving
- [ ] [DISCORD_AUTONOMY] Automate Discord account creation + server joining
- [ ] [TWITTER_AUTONOMY] Automate Twitter/X account creation and posting
- [ ] [GITHUB_AUTONOMY] Automate GitHub account management via API
- [ ] [UNIVERSAL_WEB_AGENT] Any webapp operated via natural language
