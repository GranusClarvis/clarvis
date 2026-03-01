# Skill Lifecycle & Self-Evolving Libraries (SoK 2025)

**Sources**: arxiv.org/html/2602.20867v1, arxiv.org/html/2602.12430
**Ingested**: 2026-03-01

## 7-Stage Skill Lifecycle
1. **Discovery** — Identify recurring patterns (curriculum-driven, plan decomposition, user demos)
2. **Practice/Refinement** — Iterative improvement via trial-and-error + reflection
3. **Distillation** — Extract stable procedures as skill tuple S = (C, π, T, R)
4. **Storage** — Persist with embeddings, versioning, metadata for retrieval
5. **Retrieval/Composition** — Semantic match + hierarchical composition
6. **Execution** — Run within sandboxed action loops with permissions
7. **Evaluation/Update** — Monitor performance, detect drift, retire or refine

## Formal Skill Tuple: S = (C, π, T, R)
- **C (Applicability)**: Preconditions — when should this skill activate?
- **π (Policy)**: The step sequence (procedure itself)
- **T (Termination)**: Success criteria — how to verify completion
- **R (Interface)**: Name, params, tags, dependencies — for programmatic invocation

## 7 Design Patterns
1. **Metadata-Driven Progressive Disclosure** — Two-phase: compact metadata first, full steps on selection. Scales to 100s of skills.
2. **Code-as-Skill** — Executable programs (Python/Bash). Deterministic, testable, composable.
3. **Workflow Enforcement** — Hard-gated sequences (TDD, systematic debugging). Reliability over flexibility.
4. **Self-Evolving Libraries** — Auto quality assessment + maintenance. KEY FINDING: Self-generated skills average -1.3pp vs baseline without quality gates.
5. **Hybrid NL+Code Macros** — Markdown instructions + code blocks (like OpenClaw SKILL.md).
6. **Meta-Skills** — Skills that create/modify other skills. Risk: recursive error amplification.
7. **Plugin/Marketplace Distribution** — Versioned packages with governance metadata.

## Critical Findings
- Curated skills raise agent pass rates by **+16.2pp** on average
- Self-generated skills **degrade** performance by -1.3pp (only 1/5 configs improved)
- Quality gates are essential: verification before library admission
- Most systems combine median 2 patterns (range 1-4)
- Skills provide max value where pretraining data is sparse

## Implementation Applied (procedural_memory.py)
- Added formal skill tuple fields: preconditions, termination_criteria, dependencies
- Quality tier lifecycle: candidate → verified (3+ uses, >60% success) → stale (>30 days unused or <30% success)
- `retire_stale()` — prunes skill debt (stale >60 days → deleted)
- `compose_procedures()` — hierarchical composition with sub-procedure flattening
- `library_stats()` — health metrics: tier distribution, completeness, utilization
- Tier shown in CLI list output: [V]erified, [C]andidate, [S]tale

## Gaps Remaining
- No progressive disclosure in preflight (loads full procedure every time)
- No meta-skill (procedure that generates procedures) — learn_from_failures is closest
- No explicit applicability predicate (C) — relies on embedding similarity
- Preconditions/termination_criteria not yet populated by heartbeat pipeline
