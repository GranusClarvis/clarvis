# Data Layout

_Last updated: 2026-03-04. Living document._

Where persistent data lives in the workspace. All paths relative to `$CLARVIS_WORKSPACE/`.

---

## `data/` — Runtime State & Databases

The primary data directory (~98 entries). Contains all persistent state that scripts read/write.

### ClarvisDB (Vector Brain)
| Path | Purpose |
|------|---------|
| `data/clarvisdb/` | ChromaDB vector store (10 collections, 3400+ memories, 134k+ graph edges) |
| `data/clarvisdb/chroma.sqlite3` | ChromaDB backing store |
| `data/clarvisdb/relationships.json` | Graph edges (entity relationships) |
| `data/clarvisdb/communities.json` | GraphRAG community detection output |
| `data/clarvisdb-local/` | Lite brain instances for project agents |
| `data/brain.db` | Legacy SQLite brain (pre-ChromaDB) |

### Memory Subsystems
| Path | Purpose |
|------|---------|
| `data/episodes.json` | Full episodic memory (task episodes with context/outcome/valence) |
| `data/hebbian/` | Hebbian learning state (`coactivation.json`, `fisher_importance.json`, `stats.json`) |
| `data/synaptic/` | Synaptic STDP state (`stats.json`) |
| `data/synaptic_memory.db` | Synaptic memory SQLite store |
| `data/soar/` | SOAR cognitive architecture (`chunks.json`, `goal_stack.json`, `decision_history.jsonl`) |
| `data/working_memory.json` | Working memory buffer state |
| `data/working_memory_state.json` | Working memory persistence |
| `data/cognitive_workspace/` | Baddeley workspace (`workspace_state.json`, `reuse_log.jsonl`) |
| `data/somatic_markers.json` | Emotional valence markers for decisions |
| `data/causal_links.json` | Causal chain tracking across episodes |
| `data/sleep_consolidation_log.json` | Memory consolidation during "sleep" phases |
| `data/dream_log.json` | Counterfactual dreaming output |

### Cognitive & Self-Model
| Path | Purpose |
|------|---------|
| `data/self_model.json` | 7-domain capability self-assessment |
| `data/capability_history.json` | Capability score history |
| `data/meta_cognition.json` | Meta-cognitive state |
| `data/meta_learning/` | Meta-learning (`analysis.json`, `recommendations.json`, `history.jsonl`) |
| `data/phi_decomposition.json` | IIT Phi metric decomposition |
| `data/phi_history.json` | Phi score history |
| `data/attention/` | GWT attention state |
| `data/broadcast/` | Global workspace theory broadcasts |
| `data/self_representation/` | Self-model representations |

### Performance & Metrics
| Path | Purpose |
|------|---------|
| `data/performance_metrics.json` | Current performance benchmark results |
| `data/performance_history.jsonl` | Historical performance (append-only) |
| `data/performance_alerts.jsonl` | Auto-generated P0/P1 alerts from benchmark |
| `data/perf_budget.json` | Latency budgets (p50/p95) |
| `data/retrieval_quality/` | Retrieval quality benchmarks |
| `data/retrieval_benchmark/` | Retrieval benchmark data |
| `data/retrieval_errors.jsonl` | Retrieval failure log |
| `data/code_quality_history.json` | Code generation quality tracking |
| `data/code_gen_outcomes.jsonl` | Code generation outcome log |
| `data/structural_health_history.jsonl` | Import health history |

### Reasoning & Decisions
| Path | Purpose |
|------|---------|
| `data/reasoning_chains/` | Individual reasoning chain JSON files |
| `data/thought_log.jsonl` | Thought protocol log |
| `data/thought_patterns.json` | Recurring thought patterns |
| `data/router_decisions.jsonl` | Task router model selection log |

### Cost & Budget
| Path | Purpose |
|------|---------|
| `data/costs.jsonl` | Estimated cost log (**stale** — use `cost_tracker.py` for real API data) |
| `data/budget_config.json` | Budget thresholds + Telegram credentials |
| `data/budget_alert_state.json` | Alert state (last notification) |

### Evolution & Planning
| Path | Purpose |
|------|---------|
| `data/evolution/` | Evolution loop state |
| `data/plans/` | Generated plans |
| `data/task-graph.json` | Task dependency graph |
| `data/task_retries.json` | Task retry counter |
| `data/goal_tracker_state.json` | Goal progress state |
| `data/growth_narrative.json` | Long-term growth narrative |

### Agents
| Path | Purpose |
|------|---------|
| `data/agents/` | Project agent metadata |
| `data/orchestration_benchmarks/` | Agent orchestration benchmark results |

### Other
| Path | Purpose |
|------|---------|
| `data/browser_sessions/` | Browser cookie/session state (**sensitive**) |
| `data/downloads/` | Browser downloads |
| `data/tool_library/` | LATM-extracted tool library |
| `data/tool_outputs/` | Cached tool execution outputs |
| `data/experiments/` | Experimental data |
| `data/calibration/` | Confidence calibration data |
| `data/world_model/` | World model state |
| `data/theory_of_mind/` | Theory of mind predictions |
| `data/dashboard/` | Dashboard rendered data |
| `data/prompt_optimization/` | Prompt tuning data |

---

## `memory/` — Human-Readable Logs & Queues

Curated content meant for human review and cross-session continuity.

| Path | Purpose |
|------|---------|
| `memory/YYYY-MM-DD.md.gz` | Compressed daily memory logs (auto-rotated) |
| `memory/YYYY-MM-DD-HHMM.md` | Active daily log (current day) |
| `memory/clarvis.db` | Memory-layer SQLite |
| `memory/cron/` | Cron job outputs (see below) |
| `memory/evolution/` | Evolution queue and archives |
| `memory/research/` | Research ingestion pipeline |
| `memory/summaries/` | Generated summaries |
| `memory/business/` | Business-related notes |

### `memory/cron/` — Cron Output Logs
| File | Source |
|------|--------|
| `digest.md` | Daily digest for conscious layer (M2.5 reads this) |
| `autonomous.log` | `cron_autonomous.sh` output |
| `morning.log` | `cron_morning.sh` output |
| `evening.log` | `cron_evening.sh` output |
| `evolution.log` | `cron_evolution.sh` output |
| `reflection.log` | `cron_reflection.sh` output |
| `research.log` | `cron_research.sh` output |
| `implementation_sprint.log` | `cron_implementation_sprint.sh` output |
| `strategic_audit.log` | `cron_strategic_audit.sh` output |
| `doctor.log` | `cron_doctor.py` output |
| `dream.log` | `dream_engine.py` output |
| `graph_checkpoint.log` | Graph checkpoint output |
| `graph_compaction.log` | Graph compaction output |
| `chromadb_vacuum.log` | ChromaDB vacuum output |
| `backup.log` | Daily backup output |
| `backup_verify.log` | Backup verification output |
| `watchdog.log` | Watchdog alerts |
| `agent_*.md` | Project agent digests |

### `memory/evolution/` — Task Queue
| File | Purpose |
|------|---------|
| `QUEUE.md` | Active task queue (P0/P1/P2 items picked by heartbeat) |
| `QUEUE_ARCHIVE.md` | Completed/dropped tasks |
| `QUEUE.md.lock` | Queue write lock |
| `tasks.md` | Additional task tracking |
| `README.md` | Queue format documentation |

### `memory/research/ingested/` — Research Papers
Markdown summaries of ingested research papers, named `<topic>_YYYY-MM-DD.md`.

---

## `monitoring/` — Health & Security Logs

| File | Purpose |
|------|---------|
| `health.log` | Health monitor output (every 15 min) |
| `watchdog.log` | Watchdog alerts (every 30 min) |
| `alerts.log` | Budget and threshold alerts |
| `security.log` | Security-relevant events |

---

## `/tmp/clarvis_*` — Temporary Runtime Files

| Pattern | Purpose |
|---------|---------|
| `/tmp/clarvis_claude_global.lock` | Global Claude Code mutual exclusion |
| `/tmp/clarvis_maintenance.lock` | Maintenance window lock |
| `/tmp/clarvis_*.lock` | Per-script PID locks |
| `/tmp/claude_task.txt` | Prompt buffer for Claude spawning |
| `/tmp/claude_output.txt` | Claude Code output capture |

These files are ephemeral and cleaned on reboot. The `cron_cleanup.sh` (Sunday 05:30) also rotates stale temp files.

---

## Sensitive Paths (DO NOT commit)

| Path | Contains |
|------|----------|
| `~/.openclaw/agents/main/agent/auth.json` | API keys (OpenRouter `sk-or-v1-...`) |
| `data/browser_sessions/default_session.json` | Browser cookies |
| `data/budget_config.json` | Telegram bot token |
| Any `.env` files | Environment secrets |
