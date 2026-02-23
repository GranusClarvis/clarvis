# clarvis-reasoning

Meta-cognitive reasoning quality assessment. Pure functions with zero dependencies.

Implements reasoning evaluation based on Flavell (1979) metacognition and Dunlosky & Metcalfe (2009):

- **Step quality checking** — detects shallow, circular, unsupported, and hedging reasoning
- **Coherence measurement** — word overlap between consecutive steps (optimal: moderate)
- **Session-level scoring** — composite quality grades (good/adequate/shallow/poor)
- **Calibration tracking** — Brier score for prediction accuracy
- **Multi-session diagnostics** — aggregate analysis with recommendations

## Installation

```bash
pip install clarvis-reasoning
```

## Usage

### Check a single reasoning step

```python
from clarvis_reasoning import check_step_quality

flags = check_step_quality(
    thought="Maybe perhaps this might work",
    evidence=[],
    confidence=0.9,
    previous_thoughts=[]
)
# flags: ["unsupported", "hedging"]
```

### Evaluate a full reasoning session

```python
from clarvis_reasoning import evaluate_session

result = evaluate_session(
    steps=[
        {"thought": "Database is slow due to missing index",
         "evidence": ["EXPLAIN shows full scan"], "confidence": 0.8,
         "sub_problem": "diagnosis", "quality_flags": []},
        {"thought": "Adding index on user_id will fix it",
         "evidence": ["high cardinality column"], "confidence": 0.85,
         "sub_problem": "fix", "quality_flags": []},
    ],
    sub_problems=["diagnosis", "fix"],
    predicted_outcome="success",
    actual_outcome="success",
)
print(result["quality_grade"])  # "good"
print(result["quality_score"])  # 0.85
```

### Diagnose across sessions

```python
from clarvis_reasoning import diagnose_sessions

report = diagnose_sessions(sessions)
print(report["recommendations"])
print(report["calibration"]["brier_score"])
```

### Coherence measurement

```python
from clarvis_reasoning import compute_coherence

score = compute_coherence([
    "The database query is slow",
    "Adding an index should speed up the query",
    "After indexing, verify with EXPLAIN"
])
# score: ~0.85 (good progressive flow)
```

## CLI

```bash
clarvis-reasoning check "Maybe this might work" 0.9
clarvis-reasoning coherence "thought one" "thought two" "thought three"
clarvis-reasoning demo
```

## License

MIT
