# Population-Based Training of Neural Networks

**Authors:** Max Jaderberg, Valentin Dalibard, Simon Osindero, Wojciech M. Czarnecki, Jeff Donahue, Ali Razavi, Oriol Vinyals, Tim Green, Iain Dunning, Karen Simonyan, Chrisantha Fernando, Koray Kavukcuoglu
**Year:** 2017 (arXiv:1711.09846)
**Affiliation:** DeepMind

## Key Ideas

1. **Online evolutionary hyperparameter optimization**: PBT maintains a population of models training in parallel. Periodically, underperformers EXPLOIT (copy weights + hyperparameters from a better member) then EXPLORE (perturb hyperparameters by 0.8x/1.2x or 25% resample from prior). This is Lamarckian evolution — inherited weights carry learned knowledge, not just genetic code.

2. **Schedule discovery > fixed tuning**: The core insight is that optimal hyperparameters change during training. A learning rate that works at epoch 1 is wrong at epoch 100. PBT discovers dynamic hyperparameter *schedules* automatically, which is fundamentally superior to grid/random/Bayesian search for a single fixed configuration.

3. **Zero overhead, massive gains**: PBT uses the same compute budget as training N independent models (which you'd do with random search anyway), but redirects compute from poor performers to promising ones. DeepMind Lab RL: 93% → 106% human normalized performance. GAN Inception Score: 6.45 → 6.9. Machine translation: matched hand-tuned BLEU automatically.

4. **Asynchronous & decentralized**: No central coordinator. Each worker independently decides when to check the population and whether to exploit/explore. The `perturbation_interval` controls check frequency — critical meta-hyperparameter (too frequent = instability, too rare = missed opportunities).

5. **Diversity-selection balance**: Too much exploitation = premature convergence (population collapses to one solution). Too much exploration = wasted compute. The `quantile_fraction` (what % counts as "top performer") mediates this tradeoff.

## Extensions (2020-2025)

- **PB2** (Population-Based Bandits, 2020): Bayesian optimization guides explore step → works with fewer agents
- **BG-PBT**: Bayesian generational approach for mixed hyperparameter types (continuous + categorical + ordinal)
- **MO-PBT** (2023): Multi-objective PBT — natural Pareto front from population
- **FIRE-PBT**: Addresses greediness issue (PBT can get stuck in local optima due to greedy exploitation)
- **IPBT** (2025): Task-agnostic restarts + time-varying BO — matches or beats all previous PBT variants on 8 tasks
- **MF-PBT**: Multiple perturbation frequencies to mitigate greediness

## How This Applies to Clarvis

Clarvis already has the building blocks for PBT-style self-improvement:
- **Multiple strategies** with tracked success rates (implement=53%, fix=31%, research, wire)
- **Meta-gradient RL** (meta_gradient_rl.py) doing online adaptation of γ/λ/exploration
- **Episodic memory** tracking task outcomes with full context
- **Configuration parameters** that could be population-evolved: context compression level, reasoning depth, tool selection weights, timeout thresholds, strategy routing weights

The key PBT insight for Clarvis: **optimal configurations change over time**. A strategy mix that works during heavy research sessions differs from one during code-heavy implementation sprints. PBT's schedule discovery would automatically adapt to these phase transitions.

## Implementation Ideas

### 1. Population-Based Strategy Evolution
Maintain a population of N=5 strategy configurations (each is a dict of: `{compression_tier, reasoning_model, timeout_ms, strategy_weights, exploration_rate}`). Each heartbeat, one config is active. After K heartbeats, score each config by its success rate, exploit top performer, explore by perturbing weights. Store winning schedules for replay.

```python
# Conceptual PBT for Clarvis
class StrategyPopulation:
    def __init__(self, pop_size=5):
        self.configs = [random_config() for _ in range(pop_size)]
        self.scores = [0.0] * pop_size
        self.active_idx = 0

    def exploit_explore(self):
        """Called every N heartbeats"""
        best = argmax(self.scores)
        worst = argmin(self.scores)
        # Exploit: copy best config to worst slot
        self.configs[worst] = deepcopy(self.configs[best])
        # Explore: perturb the copied config
        for key in self.configs[worst]:
            if random() < 0.25:
                self.configs[worst][key] = resample_from_prior(key)
            else:
                self.configs[worst][key] *= choice([0.8, 1.2])
```

### 2. Schedule Replay
Once PBT discovers that "high exploration early, low exploration late" works, save that schedule. On future similar task sequences, replay the schedule deterministically without the population overhead. This is the PBT Replay pattern from Ray Tune.

## Connection to Prior Research
- **Darwin Gödel Machine** (P4): PBT is the hyperparameter-level analog of DGM's code-level evolution. DGM mutates agent code; PBT mutates agent configuration. Both use empirical validation as fitness.
- **Schmidhuber's PowerPlay** (P9): PBT's perturbation-based exploration mirrors PowerPlay's skill invention — both maintain diversity to avoid convergence.
- **Meta-Gradient RL** (Bundle Q): meta_gradient_rl.py already does single-agent online adaptation. PBT would extend this to a population, providing diversity and robustness against local optima.
- **Absolute Zero Reasoner** (P7): AZR finds capability edges; PBT could evolve the AZR's own parameters (task difficulty, mode weights) via population selection.
