# Judea Pearl — Causal Inference & Structural Causal Models

**Key Works:**
- Pearl, "Causality: Models, Reasoning, and Inference" (Cambridge, 2000; 2nd ed. 2009)
- Pearl & Mackenzie, "The Book of Why: The New Science of Cause and Effect" (Basic Books, 2018)
- Pearl, "The Do-Calculus Revisited" (2012) — completeness proof for do-calculus
- Bareinboim et al., "On Pearl's Hierarchy and the Foundations of Causal Inference" (2022, causalai.net/r60.pdf)

---

## The Ladder of Causation (Pearl's Causal Hierarchy)

Three rungs representing strictly increasing reasoning power — no amount of data at a lower rung can answer questions at a higher rung:

1. **Association (Seeing):** P(Y|X). Observing correlations. "Patients who take the drug recover more often." All of classical statistics and current ML lives here. Sufficient for prediction, insufficient for understanding causes.

2. **Intervention (Doing):** P(Y|do(X)). What happens if we *act*? "If we *administer* the drug, will the patient recover?" Requires a causal model, not just data. The do() operator severs incoming edges to X in the causal graph — X is set by fiat, not by its usual causes. This is the key insight: conditioning (seeing X=x) is fundamentally different from intervening (setting X to x), because conditioning preserves confounding paths while intervention eliminates them.

3. **Counterfactuals (Imagining):** P(Y_x|X=x', Y=y'). What *would have* happened? "Given that the patient took the drug and recovered, would they have recovered *without* it?" Requires the full SCM with noise terms to reason about specific individuals, not just populations.

## Structural Causal Models (SCMs)

An SCM consists of three components: (1) a directed acyclic graph (DAG) encoding which variables directly cause which others, (2) structural equations specifying the functional mechanism for each variable (X_i = f_i(Parents(X_i), U_i)), and (3) exogenous noise variables U_i representing unobserved factors. The DAG encodes qualitative causal structure; the equations encode quantitative mechanisms; the noise terms enable counterfactual reasoning about specific instances.

## Do-Calculus & Identification

The do-calculus is a set of three inference rules (insertion/deletion of observations, action/observation exchange, insertion/deletion of actions) that are provably *complete*: any causal effect identifiable from a DAG can be derived using these rules. Two important special cases:

- **Back-door criterion:** If a set Z blocks all "back-door paths" (non-causal paths through common causes) between treatment X and outcome Y, then P(Y|do(X)) = sum over Z of P(Y|X,Z)P(Z). This is the formal justification for controlling for confounders.

- **Front-door criterion:** When confounders are unobserved but all causal effect flows through an observed mediator M, the causal effect is still identifiable by combining two unconfounded relationships (X→M and M→Y, with X as control for the latter).

## D-Separation

A purely graphical test for conditional independence: X and Y are d-separated by Z in a DAG if every path between them is "blocked" by Z (either a non-collider on the path is in Z, or a collider on the path has no descendant in Z). D-separation is sound and complete for conditional independence in DAG-faithful distributions.

## Counterfactual Reasoning via Twin Networks

To answer "What would Y have been if X had been x, given that we observed X=x', Y=y'?" — (1) use the observed evidence to infer the specific noise values U (abduction), (2) modify the model by setting X=x (action), (3) propagate through the modified model to compute Y (prediction). Twin networks make this concrete: duplicate the SCM graph, share noise variables, intervene in one copy while conditioning on observations in the other.

---

## Application to AI Self-Modeling

For an AI system reasoning causally about its own episodes and task outcomes:

- **Rung 1 (current):** "Tasks attempted after midnight fail more often" — pure correlation in episodic memory, useful but misleading if confounded (e.g., midnight tasks are harder).
- **Rung 2 (target):** "If I *switch* to a different strategy, will this task succeed?" — requires a causal model of task→strategy→outcome, with the do-operator cutting confounding between strategy choice and task difficulty.
- **Rung 3 (aspiration):** "Had I used chain-of-thought on that failed task, would it have succeeded?" — counterfactual over a specific episode, requiring abduction of the episode's latent factors, then propagation through an alternate action.

The back-door and front-door criteria provide principled ways to identify causal effects from the system's observational logs without needing to re-run experiments. D-separation tells the system which variables in its episodic memory are informationally redundant given others. SCMs could formalize the system's self-model: what causes task success, what are confounders, and which interventions on its own behavior would improve outcomes.
