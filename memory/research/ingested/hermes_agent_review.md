# Hermes-Agent Deep Review (NousResearch)

**Date**: 2026-03-06
**Source**: https://github.com/NousResearch/hermes-agent
**Task**: RESEARCH_REPO_HERMES_AGENT

## What It Is

Self-improving, multi-surface AI agent built on OpenAI-compatible tool-calling loop. Model-agnostic (OpenRouter, OpenAI, local). Runs locally, Docker, SSH, or serverless. Core is a single `AIAgent` class (~6000 lines in `run_agent.py`) owning conversation loop, tool dispatch, memory, session DB, and context compression.

## Architecture Comparison: Hermes vs Clarvis

| Aspect | Hermes | Clarvis |
|--------|--------|---------|
| Memory | 2 flat files (MEMORY.md, USER.md), char-bounded (2200/1375), `§` delimited | ChromaDB + graph (3323 memories, 92k edges), unbounded |
| System prompt | Frozen snapshot at session start, rebuilt only after compression | Rebuilt per heartbeat/preflight |
| Context mgmt | 85% threshold → compress middle, keep head/tail turns | context_compressor.py + cognitive_workspace.py |
| Session store | SQLite WAL + FTS5 on all messages | Episodic memory (ChromaDB), no FTS |
| Skills | YAML frontmatter, progressive disclosure (4 tiers), security scanned | SKILL.md per skill, flat loading |
| Security | Regex gauntlet on memory writes + context files, skill trust levels | No injection scanning currently |
| Self-improvement | Agent creates/edits skills via tool, nudge mechanism triggers creation | Evolution queue + cron-driven |
| User modeling | Honcho integration (dialectic cross-session user model) | USER.md equivalent absent |

## 5 Concrete Adoptable Changes

### 1. Memory Injection Security Scanner
**What**: Regex gauntlet scanning all content before system prompt injection — detects prompt injection, role hijack, exfiltration, invisible unicode (17 chars), secrets exposure.
**Why**: Clarvis has zero injection protection on `brain.py remember()` or context file loading. Any compromised input could poison the brain.
**Target files**: `scripts/brain.py` (add scan in `remember()`/`capture()`), `scripts/context_compressor.py` (scan loaded context files)
**Effort**: Small — pure regex, ~50 patterns, runs at write time.
**Context Relevance impact**: Prevents poisoned memories from degrading context quality.

### 2. Flush-Before-Compress Pattern
**What**: Before context compression, run one isolated LLM call (cheap model, only memory tool available) to persist unsaved knowledge. Strip flush artifacts via sentinel key.
**Why**: Clarvis's context_compressor.py and cognitive_workspace.py lose information during compression. The flush pattern preserves it cheaply.
**Target files**: `scripts/context_compressor.py` (add flush step before compression), `scripts/cognitive_workspace.py` (flush active buffer before task close)
**Effort**: Medium — needs auxiliary model call infrastructure (could use task_router.py SIMPLE tier).
**Context Relevance impact**: Directly improves context quality by retaining knowledge across compressions.

### 3. FTS5 Session Search
**What**: SQLite FTS5 virtual table over all episodic/session messages. Returns snippets + 1-message context window. Full query syntax.
**Why**: Clarvis stores episodes in ChromaDB (semantic search only). FTS5 adds exact-match/keyword search, boolean queries, and fast prefix matching — complementary to vector search.
**Target files**: `scripts/episodic_memory.py` (add FTS5 table alongside ChromaDB), or new `scripts/session_search.py`
**Effort**: Medium — SQLite schema + sync triggers + search API.
**Context Relevance impact**: Better episode retrieval → more relevant context in preflight briefs.

### 4. Frozen System Prompt Snapshots (Prefix Cache Stability)
**What**: Build system prompt once per session, cache it. Memory writes update disk but NOT the in-session prompt. Only rebuild after compression events.
**Why**: Clarvis rebuilds context each heartbeat preflight. With Anthropic's prefix caching, a stable prompt prefix could reduce costs ~50-75%.
**Target files**: `scripts/heartbeat_preflight.py` (cache system prompt across turns), `scripts/context_compressor.py` (invalidate cache on compress)
**Effort**: Small-Medium — mainly architectural discipline. Clarvis's cron-based model (each heartbeat = fresh session) already partially achieves this, but within-session turns could benefit.

### 5. Progressive Skill Disclosure
**What**: 4-tier progressive disclosure — categories → names+descriptions → full SKILL.md → linked files. Only load full skill content when agent requests it.
**Why**: Clarvis loads all 18 SKILL.md files into M2.5's context via OpenClaw. Progressive disclosure would cut token waste significantly.
**Target files**: OpenClaw gateway `openclaw.json` (skill loading config), `skills/*/SKILL.md` (add YAML frontmatter with name+description)
**Effort**: Medium — requires OpenClaw gateway changes or a skill index builder script.
**Context Relevance impact**: Directly reduces irrelevant skill content in prompts → higher context relevance score.

## Additional Notable Patterns (Not Prioritized)

- **Memory nudge mechanism**: Every N turns, silently append "[System: consider saving memories]" to user message. Resets when memory tool is used. Could help Clarvis's M2.5 conscious layer surface learnings.
- **Atomic file writes**: `tempfile.mkstemp()` + `os.replace()` instead of open-write-close. Eliminates truncate-before-lock race. Relevant to Clarvis's JSON graph writes.
- **Skill trust levels**: builtin/trusted/community/agent-created with escalating restrictions. Relevant when Clarvis's skill hub opens to external skills.
- **Honcho user modeling**: Dialectic cross-session user model via external service. Clarvis could build similar from episodic patterns.
- **Tool-conditional guidance**: Only inject MEMORY_GUIDANCE, SKILLS_GUIDANCE etc. when those tools are loaded. Keeps prompt clean.

## Relevance to Context Relevance Metric (0.838)

Three of the 5 adoptable changes directly impact context relevance:
1. **Injection scanner** prevents poisoned memories from degrading retrieval
2. **Flush-before-compress** retains knowledge that would otherwise be lost
3. **Progressive skill disclosure** reduces irrelevant content in prompts
4. **FTS5 search** adds complementary retrieval for better episode matching

Combined, these could push context relevance above 0.85.
