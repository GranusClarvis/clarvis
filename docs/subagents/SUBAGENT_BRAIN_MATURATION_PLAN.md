# Subagent Brain & PR-Factory Maturation Plan

_Status: Draft working plan_

## Goal

Evolve subagents from "isolated coding workers that can open PRs" into **repo-native technical specialists** that:
- understand their repo at file/module/test/invariant level,
- understand the product/domain the repo lives in,
- produce higher-quality PRs with less drift,
- and become measurably better across repeated runs.

This plan builds on the current working orchestrator and PR-factory wrapper. It does **not** replace the existing system.

---

## 1. Current honest state

### What already works
- Isolated agent workspaces and brains
- Real PR creation through the orchestrator
- Deterministic intake artifacts exist
- Precision indexes exist
- PR-factory wrapper exists and is tested
- Execution brief + writeback exist

### What is still weak
- Execution briefs are still underfilled on live runs (`relevant_files`, `relevant_facts`, `relevant_episodes`, `required_validations` can be sparse/empty)
- Repo knowledge is present but not yet consistently rich
- Atomic fact storage is not yet the dominant retrieval substrate
- Typed relationships exist but are not yet exploited enough for retrieval and prompt compilation
- Episodic memory exists, but selection/ranking is not yet strong enough to consistently improve future work
- Sector/domain knowledge is not yet formalized enough as a distinct layer

### Core diagnosis
The orchestrator structure is now mostly correct. The next leap in quality will come from improving the **knowledge compilation layer**, not from more ad-hoc prompting.

---

## 2. Design principles

1. **Build on the current orchestrator**
   - additive upgrades only
   - no rewrite

2. **Deterministic beats implicit**
   - machine-generated repo artifacts and indexes should be the first source of truth

3. **Small exact facts beat large vague summaries**
   - atomic fact cards should become the dominant reusable unit

4. **Hybrid retrieval beats vector-only retrieval**
   - indexes + artifacts + facts + relationships + episodes

5. **Episodes should improve future work, not just log history**
   - retrieve only the right past runs, not all of them

6. **Sector knowledge must be separate from repo knowledge**
   - linked, but distinct

7. **Every run should either improve task output or improve future capability**
   - no empty loops

---

## 3. Target architecture

### Layer A — Deterministic repo artifacts
Purpose: machine-generated, refreshable, source-grounded understanding.

Required artifacts:
- `project_brief`
- `stack_detect`
- `commands`
- `architecture_map`
- `trust_boundaries`
- `dependency_snapshot`
- later: `roadmap_signals`, `ci_map`, `risk_map`

These should become richer and more reliable over time.

### Layer B — Precision indexes
Purpose: exact grounding for where things live.

Required indexes:
- file index
- symbol index
- route index
- config/env index
- test index
- db/schema index (when applicable)
- later: authz enforcement index / dataflow index

### Layer C — Atomic factual memory
Purpose: compact reusable truths.

Fact classes:
- FACT
- INVARIANT
n- ROUTE
- SYMBOL
- AUTHZ
- PROCEDURE
- GOTCHA
- VALIDATION

Each fact should ideally have:
- type
- text
- source
- confidence
- tags
- evidence pointer
- freshness marker

### Layer D — Episodic memory
Purpose: retain what happened during real runs.

Best use:
- previous blockers
- previous successes on same files/modules
- flaky or non-obvious repo behavior
- prior validated procedures

Episodes should be ranked, not blindly injected.

### Layer E — Sector / product playbook ✅ (implemented 2026-03-08)
Purpose: knowledge of the repo's domain and intended product behavior.

Examples:
- DAO / governance constraints
- trading-agent risk/control constraints
- NSFW chatbot memory/safety/product boundaries

This should be derived from repo docs and linked to modules/invariants.

**Implementation:**
- New `project-sector` collection in LiteBrain (6th collection)
- `LiteBrain.store_sector()` / `LiteBrain.sector_recall()` — dedicated sector storage/retrieval
- `generate_sector_playbook()` in `pr_factory_intake.py` — scans README, CLAUDE.md, docs/ for constraints
- `seed_sector_to_brain()` — populates project-sector from playbook artifact
- `hybrid_recall()` now includes `sector_constraints` in results
- `build_execution_brief()` adds sector constraints to every brief
- `format_brief_for_prompt()` renders sector as "Sector/domain constraints" section
- Writeback: `_store_sector_insights()` captures domain knowledge discovered during tasks
- Sector playbook registered as artifact in `refresh_artifacts()` with staleness tracking

### Layer F — Typed relationships
Purpose: make retrieval sharper and more compositional.

Key relationships:
- route -> file
- symbol -> file
- invariant -> enforcement point
- trust boundary -> validation point
- test -> module
- module -> sector constraint
- procedure -> succeeded in episode
- vulnerability -> fixed by PR
- fact -> source artifact

---

## 4. Main improvement themes

### Theme 1 — Fill the execution brief properly
Current weakness: the brief exists, but can be sparse on real runs.

Target:
- `relevant_files` populated from index retrieval + grep heuristics
- `required_validations` derived from commands + stack + task class
- `relevant_facts` selected from atomic facts by module/task/domain
- `relevant_episodes` selected from similar prior tasks

This is the highest-leverage immediate improvement.

### Theme 2 — Improve recon / evidence quality
The evidence bundle should become a real pre-coding intelligence pass.

Target output:
- likely files
- likely symbols/routes
- likely tests
- current behavior summary
- likely change points
- risks/constraints

If recon quality improves, PR quality improves downstream.

### Theme 3 — Improve writeback quality
Writeback should optimize for future usefulness, not quantity.

Keep:
- exact new truths
- validated procedures
- useful gotchas
- meaningful episode summaries
- 1–3 golden QA additions when earned

Avoid:
- fluffy summaries
- repeated generic notes
- low-value facts

### Theme 4 — Strengthen hybrid retrieval
Move retrieval priority toward:
1. precision indexes
2. atomic facts
3. deterministic artifacts
4. typed edge expansion
5. episodic memory

This should reduce guesswork and improve minute-detail grounding.

### Theme 5 — Add real soak evaluation
The current wrapper is tested and works in practice, but it needs repeated real-task validation.

Run controlled tasks across:
- docs
- bugfix
- feature
- security/hardening
- blocked task
- test-heavy task

Measure:
- task fidelity
- PR scope quality
- validation completeness
- writeback usefulness
- improvement across repeated runs

---

## 5. Implementation order

### Phase 1 — Execution brief quality
- improve brief population
- improve evidence bundle generation
- improve validation command derivation

### Phase 2 — Brain quality
- enrich deterministic artifacts
- strengthen indexes
- improve fact card storage
- improve typed edges

### Phase 3 — Retrieval quality
- better ranking across facts/indexes/episodes
- better task-to-module grounding
- better sector-context injection

### Phase 4 — Evaluation and hardening
- real soak tasks
- trust report
- compare runs before/after maturation changes

---

## 6. Concrete success criteria

We should consider the maturation successful when:

1. A real run's `execution_brief.json` is meaningfully populated:
   - relevant files present
   - validations present
   - facts present when available
   - episodes present when relevant

2. Subagents repeatedly produce PRs that are:
   - on-task
   - tightly scoped
   - better grounded in repo structure
   - supported by real validations

3. Writeback produces higher future performance, visible in repeated tasks.

4. Repo-specific expertise becomes visible:
   - agents can answer minute-detail questions better
   - they pick safer and smarter implementation points
   - they avoid re-learning the same repo facts every run

---

## 7. Guiding principle in one line

The next step is to make subagent intelligence come less from "the model improvising well" and more from a **structured technical knowledge compiler** built from repo artifacts, indexes, atomic facts, typed relationships, and selectively retrieved episodes.
