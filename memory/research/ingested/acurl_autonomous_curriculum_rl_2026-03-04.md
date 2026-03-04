# ACuRL: Autonomous Curriculum RL for Computer-Use Agent Adaptation

**Paper**: Xue, Liao, Shi, Wang, Zhang, Song, Su, Sun (OSU NLP Group + UC Berkeley)
**Year**: 2025 (arXiv:2602.10356)
**Code**: https://github.com/OSU-NLP-Group/ACuRL

## Core Problem

Computer-use agents (CUAs) face distribution shift when deployed to new or updated environments. Continual learning is essential but bottlenecked by expensive human annotation. ACuRL eliminates this dependency entirely.

## Key Ideas

### 1. Three-Phase Autonomous Training Pipeline
1. **Exploration**: Agent freely interacts with target environment, collecting trajectories. Concurrently performs "context review" — crawling real-world artifacts (docs, emails) to ground tasks in realistic scenarios.
2. **Curriculum Task Generation**: Synthesizes training tasks calibrated to current agent capability using accumulated exploration data + performance feedback from prior iteration.
3. **Iterative RL Training**: GRPO-based optimization over N iterations, each with x steps. CUAJudge provides automated reward signal.

### 2. Adaptive Difficulty Calibration
Tasks classified by agent success rate:
- **Easy** (success > δ_high): Complexity increased via additional skill requirements
- **Medium** (δ_low ≤ success ≤ δ_high): Maintain diversity, preserve learnability
- **Hard** (success < δ_low): Hierarchical decomposition into subtasks

This prevents curriculum stagnation — tasks always match the agent's learning frontier.

### 3. CUAJudge — Automated Evaluation (93% Human Agreement)
Extends WebJudge with:
- **State-difference analysis**: Compares initial vs final environment states
- **Evidence-grounded verification**: Requires concrete screenshots/actions for each decision point
- Precision: 94.5%, Recall: 93.8% across iterations

Key insight: reliable automated evaluation unlocks unlimited autonomous training signal.

### 4. Sparse Parameter Updates Prevent Catastrophic Forgetting
~80% of parameters show negligible change during adaptation:
- LLM backbone: Uniform sparsity in layers 3-27, very high in early layers
- Vision encoder: Opposite — substantial updates concentrated in early layers

This explains why agents preserve old skills while learning new environments.

### 5. Performance Results
**Intra-environment** (LibreOffice Impress/Calc/Writer, Thunderbird, Celestia, KAlgebra):
- 4-22% absolute improvement, 29-44% relative gains
- Example: Writer 10.8% → 15.6% (+44% relative)

**Cross-environment continual learning**:
- Sequential adaptation (Impress→KAlgebra→Calc) achieves 24.7% overall
- Non-target environment performance preserved or improved (positive transfer)

## Related Work
- **SEAgent** (arXiv:2508.04700): Specialist-to-generalist strategy, 11.3%→34.5% on OS-World
- **WebRL** (ICLR 2025): Self-evolving online curriculum for web agents, 4.8%→42.4%
- All three converge on: explore → generate tasks → GRPO training → evaluate → iterate

## Applicability to Clarvis

### Direct Relevance
ACuRL's framework maps cleanly onto Clarvis's autonomous browser skill acquisition goals:
- **Exploration phase** ≈ ClarvisBrowser autonomous exploration of target websites
- **Curriculum generator** ≈ Dynamic task selection from QUEUE.md based on difficulty
- **CUAJudge** ≈ Automated success/failure evaluation for browser tasks
- **Iterative improvement** ≈ Heartbeat loop with procedural memory updates

### Concrete Implementation Ideas

**1. Browser Task Curriculum Generator**
Build `scripts/browser_curriculum.py` that:
- Takes a target website/webapp as input
- Uses autonomous exploration to map available interactions (forms, buttons, navigation)
- Generates a curriculum of tasks from simple (navigate to page) to complex (multi-step workflows)
- Difficulty adapts based on ClarvisBrowser success rates tracked in episodic memory
- Tasks feed into QUEUE.md as AUTONOMY_* items with difficulty labels

**2. Automated Task Evaluator for Browser Actions**
Build `scripts/browser_task_judge.py` inspired by CUAJudge:
- Compare screenshots before/after task execution (using local Qwen3-VL)
- Define success criteria per task type (e.g., "form submitted" = confirmation page visible)
- Log success/failure to episodic memory with confidence scores
- Use as automated reward signal for procedural memory updates — successful procedures get Hebbian strengthening, failed ones get weakened
- This closes the loop: explore → attempt → evaluate → learn → attempt harder tasks

**3. Sparse Update Principle for Brain**
Apply the sparse-update insight to ClarvisDB: when learning from new domains, track which collections/memories change. If too many memories are being modified simultaneously, throttle to prevent "catastrophic forgetting" of existing knowledge. The memory_consolidation pipeline could implement this via a change-rate limiter.
