# Changelog — clarvis-cost

All notable changes to this package will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] — 2026-02-15

### Added
- `CostTracker` — per-call token and cost logging with `log()` (estimated) and `log_real()` (actual API cost)
- `PromptCache` — hash-based prompt deduplication to avoid redundant LLM calls
- `ContextBudgetPlanner` — token budget allocation across context sections
- CLI entry point (`clarvis-cost`) with `report`, `summary`, `reset` commands
- Test suite covering core tracking, optimizer, and CLI
