# LLM Confidence Calibration & Uncertainty Estimation

**Date**: 2026-03-04
**Sources**: Shoham et al. ICLR 2025 ("Do LLMs Estimate Uncertainty Well"), Heo et al. 2024 ("Do LLMs estimate uncertainty well in instruction-following?"), Vashurin et al. 2025 (CoCoA), arXiv:2510.20460 (Systematic Evaluation), Amazon 2025 (Calibrated Reflection), ADVICE framework (arXiv:2510.10913)

## Taxonomy of Uncertainty Methods

Four families, ranked by general reliability:

1. **Verbalized Confidence (VCE)**: Prompt model to self-report confidence 0-100. Simple, works with black-box APIs. Single-sample is severely overconfident (97.6% reported vs 86.8% actual on SQuAD). Multi-sample aggregation cuts overconfidence by 20-50pp.

2. **Logit-based (MSP)**: Negative log-likelihood of output sequence. Best discrimination/ranking (AUROC 0.841 on TriviaQA). Requires token probabilities (not always available via API). Normalized p(true) — `p(A)/(p(A)+p(B))` for binary choice — is a reliable second-best.

3. **Multi-sample Consistency**: Generate k answers via stochastic decoding, measure pairwise similarity (embedding cosine + NLI entailment). Reveals uncertainty even when probabilities are overconfident. Cost: k model calls.

4. **Probing-based**: Linear classifiers on internal representations. Best on simple tasks (AUROC 0.72-0.79) but requires white-box access. Not feasible for API-only models.

## Key Findings

### CoCoA — Best Hybrid Method (Vashurin 2025)
- Multiplicative: `U_CoCoA = u(y*|x) * U_cons(y*|x)`
- Combines sequence log-prob (information) with semantic dissimilarity (consistency)
- Uses RoBERTa-large cross-encoder for similarity
- ECE: 0.062 (SQuAD), 0.081 (GSM8K) — best calibration across benchmarks
- Selective prediction: threshold >0.8 → +26.3pp accuracy on TriviaQA (52.8% coverage)
- Minimum Bayes Risk framework provides theoretical grounding

### Flex-ECE — Better Calibration Metric
- Replaces binary correctness with semantic similarity to ground truth
- Accounts for partial correctness (critical for open-ended generation)
- Post-hoc calibration reduces Flex-ECE to 0.1-4.1%
- **Clarvis application**: Current `calibration()` uses strict `actual.lower() == expected.lower()` — this misses partial matches

### Reflection-Based Calibration
- **FaR (Fact-and-Reflection)**: Generate answer → reflect on reasoning → update confidence. Improves ECE and MacroCE.
- **ADVICE**: Answer-independence is primary overconfidence driver. Confidence must be conditioned on the specific answer, not just the question.
- **Reasoning models** (o1/o3-style chain-of-thought) are inherently better calibrated — slow thinking dynamically adjusts confidence.

### No Single Winner
- MSP: best discrimination (AUROC) on knowledge-heavy tasks
- CoCoA: best calibration (ECE) overall
- VCE: best for simple tasks with black-box models
- Probing: best when white-box access available
- Task structure strongly shapes which estimator is most useful

### RLHF Worsens Calibration
- RLHF-trained models show greater verbalized overconfidence than base models
- PPO-M and PPO-C (reward calibration methods) can partially correct this

## Quantitative Reference Table

| Task | Method | ECE | AUROC | Notes |
|------|--------|-----|-------|-------|
| SQuAD | CoCoA | 0.062 | 0.844 | Best calibration |
| SQuAD | MSP | 0.122 | 0.836 | Good discrimination |
| TriviaQA | MSP | 0.147 | 0.841 | Best AUROC |
| GSM8K | CoCoA | 0.081 | 0.786 | Math reasoning |
| BoolQ | CoCoA | 0.160 | 0.687 | Binary QA |

## Clarvis Application — 5 Concrete Ideas

### 1. Multi-Sample Confidence (addresses CONFIDENCE_RECALIBRATION queue item)
Current `dynamic_confidence()` uses historical calibration + Bayesian shrinkage (single-method). Add consistency dimension: when making a prediction, generate 2-3 varied phrasings and check agreement. Disagreement → lower confidence.

### 2. Flex-ECE for `calibration()`
Replace strict string equality `actual.lower() == expected.lower()` with semantic similarity (can use ONNX MiniLM embeddings already available in brain.py). Threshold at cosine >0.75 for "correct", use continuous score for Flex-ECE calculation.

### 3. Answer-Dependent Confidence
Current `predict()` takes confidence as input parameter — it's not conditioned on the actual predicted answer. Refactor: generate prediction first, then score confidence *based on* the specific prediction content (ADVICE pattern).

### 4. Reflection Loop for High-Stakes Predictions
For predictions with confidence >0.85, add a reflection step: re-examine the prediction with counter-evidence, adjust downward if warranted. This directly addresses the overconfidence at 90% level flagged in QUEUE.md.

### 5. Selective Prediction Threshold
Implement CoCoA-style threshold: only act on predictions with confidence >0.8. Below threshold, flag for human review or additional evidence gathering. This maps to heartbeat_gate.py's wake/skip decision.

## Relation to Action Accuracy (0.968)

Action Accuracy is already well above target (0.8). The calibration research suggests this could indicate measurement overconfidence rather than true accuracy. Flex-ECE's partial-correctness scoring would provide more nuanced measurement — actions could be "75% correct" rather than binary pass/fail, revealing subtle accuracy gaps hidden by lenient evaluation.
