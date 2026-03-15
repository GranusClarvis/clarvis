# PeerRank — Autonomous LLM Self-Evaluation via Peer Review

**Paper**: arXiv:2602.02589
**Ingested**: 2026-03-14
**Relevance**: self_model.py capability scoring, clarvis_confidence.py calibration, endogenous quality loops

## Core Idea

Fully autonomous evaluation framework where models generate tasks, answer with web grounding, judge peers, and aggregate scores — no human supervision or gold references needed. Tested across 12 commercial models with 420 autonomously generated questions.

## PeerRank Scoring Formula

```
Pj = E[i≠j, q][s_{i,j,q}]
```

Mean peer score for model j, excluding self-ratings. Scores s ∈ {1,...,10} with rubric:
- 10: Correct + complete + well-justified
- 7-9: Mostly correct, minor omissions
- 4-6: Mixed correctness, unclear reasoning
- 1-3: Mostly incorrect/hallucinated

Priority rule: "Correctness/faithfulness over eloquence. Penalize confident-sounding unsupported specifics."

## Bias Control Mechanisms (Key for Clarvis)

Three controlled evaluation regimes isolate systematic bias effects:

1. **Shuffle-only**: Randomized answer order, visible model identities
2. **Blind-only**: Fixed order, hidden identities
3. **Shuffle+blind**: Randomized order + hidden identities (baseline)

Bias metrics computed via cross-regime comparison:
- **Self bias**: Δself = E[s_{j,j,q}] − Pj (self-rating vs peer average)
- **Name bias**: Δname = Pj^shuffle − Pj (identity visibility effect)
- **Position bias**: Δpos = Pj^blind − Pj (answer order effect)

Finding: Position bias produces +0.39 score lift for first position vs -0.12 for position 9.

## Task Generation Protocol

- 12 models × 35 questions = 420 total across 5 categories:
  - Factual knowledge, Reasoning/logic, Current events, Creative/open-ended, Practical how-to
- No filtering or deduplication — task distribution is fully endogenous
- Web grounding enabled only for "Current Events" during answering; disabled during judging

## Validation Results

- **TruthfulQA**: Peer score vs ground truth accuracy: Pearson r=0.904 (p=0.0004)
- **GSM8K**: Peer score vs exact-match: Pearson r=0.873 (p=0.0002)
- **Critical finding**: Peer evaluation (r=0.905) vastly outperforms self-evaluation (r=0.538)
- Judge agreement: Average pairwise Pearson r̄=0.609 across 66 judge pairs
- Elo correlation: Pearson r=0.844, Spearman ρ=0.755

## Adoptable Patterns for Clarvis

### 1. Bias-Controlled Self-Assessment for self_model.py

**Current gap**: `_assess_*` functions in self_model.py score capabilities without controlling for self-serving bias. The model assessing itself tends to over-rate (PeerRank showed self-eval correlation with truth is only r=0.538 vs peer r=0.905).

**Pattern**: Implement "temporal peer review" — compare current session's self-assessment against:
- Historical evidence (past episode outcomes act as "peer judges")
- Cross-domain consistency checks (if code_generation scores 1.0 but autonomous_execution fails, flag inconsistency)
- Mandatory 8-20 word justification per score (prevents vague high scores)

**Concrete change**: Add `bias_check()` to self_model.py that computes Δself = current_score - evidence_based_score for each domain, flagging domains where Δself > 0.15 as potentially self-biased.

### 2. Endogenous Quality Loop for clarvis_confidence.py

**Current gap**: Confidence calibration uses simple bucket accuracy and Brier score but doesn't generate its own evaluation tasks.

**Pattern**: Implement "self-generated calibration challenges":
- Each `predict()` call stores both the prediction AND a verifiable test criterion
- `auto_resolve()` already matches outcomes but doesn't cross-validate
- Add: when Brier score exceeds 0.15, generate 5 domain-specific predictions with known-difficulty tasks to recalibrate

### 3. Position/Order Bias Awareness

**Current gap**: When self_model.py reads autonomous.log, results from early entries may be weighted differently than later ones (temporal position bias).

**Pattern**: Shuffle or reverse evaluation order when computing daily success rates. PeerRank's +0.39 position-1 bias suggests first-seen results may get disproportionate weight.
