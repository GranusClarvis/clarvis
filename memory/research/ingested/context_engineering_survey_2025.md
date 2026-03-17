# Context Engineering Survey — Li et al. 2025

**Paper**: arXiv:2507.13334, "A Survey of Context Engineering for Large Language Models"
**Scope**: 1400+ papers systematized into taxonomy of context retrieval, processing, management
**Date researched**: 2026-03-15

## Key Framework

Context engineering = systematic optimization of information payloads for LLMs.
Three foundational components: **retrieval** → **processing** → **management**.
Four system implementations: RAG, memory systems, tool-integrated reasoning, multi-agent.

Core optimization principle: maximize mutual information **I(Y*; c_know | c_query)** — select context that maximally reduces uncertainty about the correct answer under token budget constraint |C| ≤ L_max.

## 5 Actionable Insights for Clarvis

### 1. Noise Sections Destroy CR More Than Missing Sections Hurt It
- Focused 300 tokens outperforms unfocused 113k tokens (LongMemEval benchmark)
- Context rot: accuracy drops non-linearly past model-specific cliff (95% → 60%)
- **Our data**: 11/18 brief sections score < 0.15 containment (noise). Pruning them would boost CR from 0.40 → ~0.73
- Worst offenders: meta_gradient (0.056), brain_goals (0.089), failure_avoidance (0.089), metrics (0.100), synaptic (0.112)

### 2. Assembly Order Matters (Primacy/Recency Bias)
- LLMs attend disproportionately to beginning and end of context (U-shaped attention curve)
- "Lost in the middle" effect: accuracy drops from 75% to 55-60% even at 4K tokens
- **Action**: Front-load decision_context (0.28) and related_tasks (0.29) — our highest-CR sections — not bury them after noise

### 3. Role-Based Grouping > Chronological Ordering
- Tag each context element by function (goal, decision, action, error), not by source
- Semantic proximity grouping outperforms timeline-based approaches
- Tool selection accuracy improved 3x with semantic retrieval vs full enumeration
- **Action**: Brief assembly should group by task-relevance, not by pipeline stage

### 4. Binary Containment Is Wrong Metric
- Current CR formula: `referenced_sections / total_sections` with binary 0.15 threshold
- Better: weighted relevance = Σ(containment_i × weight_i) / Σ(weights), capturing partial references
- Information-theoretic scoring preferred over binary classification
- **Action**: Implement weighted scoring in `context_relevance.py` (QUEUE task: CONTAINMENT_TO_WEIGHTED_RELEVANCE)

### 5. Dynamic Context Budget Allocation
- Compression at 85-95% capacity threshold (Claude Code uses 95%)
- Hierarchical summarization > recursive > targeted > hard-coded trimming
- Just-in-time loading: maintain lightweight pointers, load data at runtime
- Progressive disclosure: let agent discover context through exploration
- **Action**: Brief assembly should dynamically allocate token budget based on task type

## Clarvis-Specific Diagnosis

Our CR = 0.387 (target: 0.75). Root causes identified:

| Problem | Evidence | Fix |
|---------|----------|-----|
| Too many sections (20) | 11 score < 0.15 containment | Prune noise (CR_NOISE_PRUNE) |
| Binary scoring hides partial value | Sections with 0.14 containment get 0 credit | Weighted scoring (CONTAINMENT_TO_WEIGHTED_RELEVANCE) |
| No ordering optimization | High-value sections buried in middle | Reorder by relevance rank |
| Static section list | Same 20 sections regardless of task type | Dynamic retrieval per task |
| No re-ranking | Raw retrieval injected without quality filter | Add re-ranking step |

**Expected impact**: Pruning alone → CR ~0.73. Pruning + weighted scoring → CR ~0.80. All fixes → CR > 0.85.

## Sources
- Li et al. 2025 — arXiv:2507.13334 (full survey)
- Anthropic — "Effective Context Engineering for AI Agents" (anthropic.com/engineering)
- FlowHunt — "Context Engineering: The Definitive 2025 Guide"
- MECW research — Maximum Effective Context Window analysis (oajaiml.com)
