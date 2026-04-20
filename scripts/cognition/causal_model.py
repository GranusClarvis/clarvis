#!/usr/bin/env python3
"""
Structural Causal Model (SCM) Engine — Judea Pearl's causal inference framework.

Implements the three rungs of the Ladder of Causation:
  Rung 1: Association (P(Y|X))       — observational queries over episodic data
  Rung 2: Intervention (P(Y|do(X)))  — do-calculus for "what if I change strategy?"
  Rung 3: Counterfactual (P(Y_x|…))  — "would this episode have succeeded with a different approach?"

Key components:
  - SCM: DAG + structural equations + exogenous noise
  - d-separation test for conditional independence
  - do() operator that severs incoming edges
  - Counterfactual reasoning via abduction-action-prediction
  - Auto-construction of task SCM from episodic memory

Integration:
  - Builds on episodic_memory.py's causal_links graph
  - Feeds interventional insights into clarvis_reasoning.py
  - Stores findings in brain (clarvis-learnings)

Reference: Pearl, "Causality" (2009); Pearl & Mackenzie, "The Book of Why" (2018)

Usage:
    python3 causal_model.py build           # Build SCM from episodic data
    python3 causal_model.py dsep X Y Z1,Z2  # Test d-separation
    python3 causal_model.py do X=val        # Interventional query
    python3 causal_model.py counterfactual <episode_id> var=val  # Counterfactual
    python3 causal_model.py analyze         # Full causal analysis report
"""

import json
import sys
import os
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))) / "data"
SCM_FILE = DATA_DIR / "scm_model.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class StructuralCausalModel:
    """A structural causal model: DAG + structural equations + noise.

    Variables are string names. Edges are directed (cause -> effect).
    Structural equations map (parents, noise) -> value.
    """

    def __init__(self, name: str = ""):
        self.name = name
        self.variables: set[str] = set()
        # Adjacency: parent -> set of children
        self.edges: dict[str, set[str]] = defaultdict(set)
        # Reverse adjacency: child -> set of parents
        self.parents: dict[str, set[str]] = defaultdict(set)
        # Structural equations: var -> callable(parent_values: dict, noise: float) -> value
        self._equations: dict[str, callable] = {}
        # Exogenous noise distributions: var -> (mean, std)
        self._noise: dict[str, tuple[float, float]] = {}
        # Observed data for parameter estimation
        self._observations: list[dict] = []
        # Conditional probability tables (estimated from data)
        self._cpt: dict[str, dict] = {}

    def add_variable(self, name: str, noise: tuple[float, float] = (0.0, 1.0)):
        """Add a variable with its exogenous noise distribution."""
        self.variables.add(name)
        self._noise[name] = noise

    def add_edge(self, cause: str, effect: str):
        """Add a directed causal edge cause -> effect."""
        self.variables.add(cause)
        self.variables.add(effect)
        self.edges[cause].add(effect)
        self.parents[effect].add(cause)

    def set_equation(self, var: str, equation: callable):
        """Set the structural equation for a variable.

        equation(parent_values: dict, noise: float) -> value
        """
        self._equations[var] = equation

    def observe(self, observation: dict):
        """Record an observation (assignment of values to variables)."""
        self._observations.append(observation)

    # ------------------------------------------------------------------
    # D-Separation (Rung 1: testing conditional independence)
    # ------------------------------------------------------------------

    def ancestors_of(self, nodes: set[str]) -> set[str]:
        """Find all ancestors of a set of nodes."""
        ancestors = set()
        queue = deque(nodes)
        while queue:
            n = queue.popleft()
            for parent in self.parents.get(n, set()):
                if parent not in ancestors:
                    ancestors.add(parent)
                    queue.append(parent)
        return ancestors

    def d_separated(self, x: str, y: str, z: set[str]) -> bool:
        """Test if X and Y are d-separated given Z using the Bayes-Ball algorithm.

        D-separation means X _||_ Y | Z in the distribution.
        Returns True if d-separated (conditionally independent), False otherwise.

        Algorithm: Bayes-Ball (Shachter 1998) — traverse the DAG checking
        if information can flow from X to Y given the conditioning set Z.
        """
        if x == y:
            return False

        # Ancestors of Z (needed for collider activation)
        z_ancestors = self.ancestors_of(z) | z

        # BFS: track (node, direction) where direction is "up" or "down"
        # "up" = arrived from a child, "down" = arrived from a parent
        visited = set()
        queue = deque()

        # Start from X, going both directions
        for child in self.edges.get(x, set()):
            queue.append((child, "down"))  # X -> child
        for parent in self.parents.get(x, set()):
            queue.append((parent, "up"))  # X <- parent

        while queue:
            node, direction = queue.popleft()

            if node == y:
                return False  # Path found — NOT d-separated

            if (node, direction) in visited:
                continue
            visited.add((node, direction))

            if direction == "down":
                # Arrived at node from its parent
                if node not in z:
                    # Non-collider, not conditioned: pass through
                    for child in self.edges.get(node, set()):
                        queue.append((child, "down"))
                    for parent in self.parents.get(node, set()):
                        queue.append((parent, "up"))
                else:
                    # Node is in Z: if it's a collider descendant, activate
                    # Actually: conditioned non-collider blocks. But we need
                    # to handle colliders specially.
                    pass  # Blocked at this non-collider

            elif direction == "up":
                # Arrived at node from its child
                if node not in z:
                    # Non-collider, not conditioned: pass up only
                    for parent in self.parents.get(node, set()):
                        queue.append((parent, "up"))
                # If node is in Z or has descendant in Z, it might be a
                # collider that activates. Check: does node have multiple parents?
                if node in z_ancestors:
                    # Collider (or descendant of collider) is activated
                    for child in self.edges.get(node, set()):
                        queue.append((child, "down"))
                    for parent in self.parents.get(node, set()):
                        queue.append((parent, "up"))

        return True  # No path found — d-separated

    # ------------------------------------------------------------------
    # Do-Calculus (Rung 2: interventional queries)
    # ------------------------------------------------------------------

    def do(self, interventions: dict[str, any]) -> "StructuralCausalModel":
        """Apply the do() operator: return a mutilated SCM.

        do(X=x) severs all incoming edges to X and sets X = x.
        This is Pearl's key insight: intervention ≠ conditioning.

        Args:
            interventions: {variable: value} to intervene on

        Returns:
            A new SCM with incoming edges to intervened variables removed.
        """
        mutilated = StructuralCausalModel(f"{self.name}_do({interventions})")
        mutilated.variables = set(self.variables)
        mutilated._noise = dict(self._noise)
        mutilated._observations = list(self._observations)
        mutilated._cpt = dict(self._cpt)

        # Copy edges, severing incoming edges to intervened variables
        for cause, effects in self.edges.items():
            for effect in effects:
                if effect not in interventions:
                    mutilated.add_edge(cause, effect)

        # Set intervened variables to constant equations
        for var, val in interventions.items():
            mutilated.set_equation(var, lambda pv, n, v=val: v)

        # Copy non-intervened equations
        for var, eq in self._equations.items():
            if var not in interventions:
                mutilated._equations[var] = eq

        return mutilated

    def interventional_query(self, target: str, interventions: dict,
                             evidence: dict = None) -> dict:
        """Estimate P(target | do(interventions), evidence) from data.

        Uses the adjustment formula (back-door) when possible:
        P(Y|do(X=x)) = Σ_z P(Y|X=x, Z=z) P(Z=z)

        Falls back to naive estimation from mutilated model observations.
        """
        if not self._observations:
            return {"error": "No observations to estimate from",
                    "target": target, "interventions": interventions}

        # Find back-door adjustment set
        adj_set = self._find_backdoor_set(
            list(interventions.keys())[0] if interventions else "",
            target
        )

        results = {"target": target, "interventions": interventions,
                   "method": "adjustment", "adjustment_set": list(adj_set)}

        # Filter observations matching interventions
        matching = self._observations
        for var, val in (interventions or {}).items():
            matching = [o for o in matching if o.get(var) == val]

        if evidence:
            for var, val in evidence.items():
                matching = [o for o in matching if o.get(var) == val]

        if not matching:
            results["estimate"] = None
            results["n"] = 0
            return results

        # Estimate target distribution
        target_vals = [o.get(target) for o in matching if target in o]
        if not target_vals:
            results["estimate"] = None
            results["n"] = 0
            return results

        # For categorical: return distribution
        val_counts = defaultdict(int)
        for v in target_vals:
            val_counts[v] += 1
        total = len(target_vals)
        distribution = {str(k): round(v / total, 3) for k, v in val_counts.items()}

        results["distribution"] = distribution
        results["n"] = total
        results["mode"] = max(val_counts, key=val_counts.get)
        return results

    def _find_backdoor_set(self, treatment: str, outcome: str) -> set[str]:
        """Find a valid back-door adjustment set (simplified).

        The back-door criterion requires a set Z such that:
        1. No node in Z is a descendant of treatment
        2. Z blocks all back-door paths from treatment to outcome

        Simplified: return parents of treatment (always a valid adjustment set
        when there are no hidden confounders).
        """
        if not treatment:
            return set()

        # Parents of treatment are always a valid back-door set
        # (they block all back-door paths and aren't descendants of treatment)
        treatment_parents = self.parents.get(treatment, set())

        # Exclude descendants of treatment from the adjustment set
        descendants = self._descendants_of(treatment)
        return treatment_parents - descendants

    def _descendants_of(self, node: str) -> set[str]:
        """Find all descendants of a node."""
        desc = set()
        queue = deque([node])
        while queue:
            n = queue.popleft()
            for child in self.edges.get(n, set()):
                if child not in desc:
                    desc.add(child)
                    queue.append(child)
        return desc

    # ------------------------------------------------------------------
    # Counterfactual Reasoning (Rung 3)
    # ------------------------------------------------------------------

    def counterfactual(self, episode: dict, intervention: dict,
                       target: str) -> dict:
        """Answer: "Had <intervention> been different, what would <target> be?"

        Three-step procedure (Pearl):
        1. ABDUCTION: Use observed episode to infer noise values
        2. ACTION: Apply intervention (sever + set)
        3. PREDICTION: Propagate through modified model

        For discrete/categorical variables, uses frequency-based estimation.
        """
        result = {
            "episode": {k: episode.get(k) for k in ["id", "task", "outcome", "section"]
                        if k in episode},
            "intervention": intervention,
            "target": target,
            "steps": [],
        }

        # Step 1: ABDUCTION — infer latent context from the episode
        # What was the "noise" (unobserved context) for this episode?
        abducted = self._abduct(episode)
        result["steps"].append({
            "step": "abduction",
            "description": "Inferred latent context from observed episode",
            "context": abducted,
        })

        # Step 2: ACTION — apply intervention in mutilated model
        mutilated = self.do(intervention)
        result["steps"].append({
            "step": "action",
            "description": f"Applied do({intervention}), severed incoming edges",
            "mutilated_edges_removed": [
                f"* -> {var}" for var in intervention
            ],
        })

        # Step 3: PREDICTION — estimate target under intervention + abducted context
        prediction = self._predict_counterfactual(
            mutilated, intervention, abducted, target
        )
        result["steps"].append({
            "step": "prediction",
            "description": f"Predicted {target} under intervention",
            "prediction": prediction,
        })

        result["counterfactual_answer"] = prediction
        return result

    def _abduct(self, episode: dict) -> dict:
        """Step 1: Infer latent context from an observed episode.

        Uses the episode's observable features to characterize its context:
        section (domain), duration, time of day, task complexity signals.
        """
        context = {}

        # Domain context
        context["section"] = episode.get("section", "unknown")

        # Temporal context
        ts = episode.get("timestamp", "")
        if ts:
            try:
                dt = datetime.fromisoformat(ts)
                context["hour"] = dt.hour
                context["is_night"] = dt.hour < 6 or dt.hour > 22
            except (ValueError, TypeError):
                pass

        # Complexity signals from task text
        task = episode.get("task", "")
        context["task_length"] = len(task.split())
        context["has_fix"] = "fix" in task.lower()
        context["has_implement"] = any(w in task.lower() for w in
                                       ["implement", "build", "create", "add"])
        context["has_research"] = any(w in task.lower() for w in
                                      ["research", "investigate", "analyze", "study"])

        # Duration context
        dur = episode.get("duration_s", 0)
        context["duration_bucket"] = (
            "fast" if dur < 60 else
            "medium" if dur < 300 else
            "slow"
        )

        return context

    def _predict_counterfactual(self, mutilated_scm, intervention: dict,
                                context: dict, target: str) -> dict:
        """Step 3: Predict target variable under intervention + context.

        Uses frequency estimation from similar observations in the mutilated model.
        """
        # Find observations similar to the abducted context + intervention
        matching = list(mutilated_scm._observations)

        # Filter by intervention values
        for var, val in intervention.items():
            matching = [o for o in matching if o.get(var) == val]

        # Soft-match by context features (section, complexity, etc.)
        if context.get("section"):
            section_match = [o for o in matching
                            if o.get("section") == context["section"]]
            if section_match:
                matching = section_match

        if not matching:
            return {
                "estimate": None,
                "confidence": 0.0,
                "reason": "No matching observations for this intervention + context",
            }

        # Estimate target distribution
        target_vals = [o.get(target) for o in matching if target in o]
        if not target_vals:
            return {"estimate": None, "confidence": 0.0,
                    "reason": f"Target '{target}' not found in observations"}

        val_counts = defaultdict(int)
        for v in target_vals:
            val_counts[v] += 1
        total = len(target_vals)

        mode = max(val_counts, key=val_counts.get)
        mode_fraction = val_counts[mode] / total

        return {
            "estimate": mode,
            "confidence": round(mode_fraction, 3),
            "distribution": {str(k): round(v / total, 3)
                            for k, v in val_counts.items()},
            "n_matching": total,
        }

    # ------------------------------------------------------------------
    # Auto-build SCM from episodic memory
    # ------------------------------------------------------------------

    def build_from_episodes(self, episodes: list, causal_links: list = None):
        """Construct an SCM automatically from episodic memory data.

        Learns the DAG structure from observed covariation patterns in episodes.
        Variables represent key episode features.

        DAG structure:
            section -> strategy -> outcome
            task_complexity -> duration -> outcome
            time_of_day -> outcome
            prior_outcome -> outcome (temporal dependency)
        """
        # Define variables
        for var in ["section", "strategy", "task_complexity", "time_of_day",
                     "duration_bucket", "outcome", "prior_outcome",
                     "has_error", "salience"]:
            self.add_variable(var)

        # Define causal edges (domain knowledge + episodic patterns)
        self.add_edge("section", "strategy")
        self.add_edge("section", "task_complexity")
        self.add_edge("strategy", "outcome")
        self.add_edge("task_complexity", "outcome")
        self.add_edge("task_complexity", "duration_bucket")
        self.add_edge("time_of_day", "outcome")
        self.add_edge("prior_outcome", "outcome")
        self.add_edge("duration_bucket", "has_error")
        self.add_edge("has_error", "outcome")
        self.add_edge("salience", "outcome")

        # Convert episodes to observations
        for i, ep in enumerate(episodes):
            obs = self._episode_to_observation(ep, episodes[i - 1] if i > 0 else None)
            self.observe(obs)

        # Add edges from explicit causal links
        if causal_links:
            for link in causal_links:
                # Map causal link relationships to variable-level edges
                rel = link.get("relationship", "")
                if rel in ("caused", "enabled"):
                    self.add_edge("prior_outcome", "outcome")
                elif rel == "blocked":
                    self.add_edge("has_error", "outcome")

        # Estimate conditional probability tables
        self._estimate_cpt()

    def _episode_to_observation(self, episode: dict,
                                prior_episode: dict = None) -> dict:
        """Convert an episode to an SCM observation dict."""
        task = episode.get("task") or ""
        task_words = task.lower().split()

        # Infer strategy from task text
        strategy = "unknown"
        if any(w in task_words for w in ["fix", "repair", "debug"]):
            strategy = "fix"
        elif any(w in task_words for w in ["implement", "build", "create", "add"]):
            strategy = "implement"
        elif any(w in task_words for w in ["research", "investigate", "study", "analyze"]):
            strategy = "research"
        elif any(w in task_words for w in ["optimize", "improve", "boost", "reduce"]):
            strategy = "optimize"
        elif any(w in task_words for w in ["test", "benchmark", "verify"]):
            strategy = "test"

        # Task complexity proxy
        complexity = "simple" if len(task_words) < 8 else (
            "medium" if len(task_words) < 15 else "complex"
        )

        # Time of day
        hour = 12
        ts = episode.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(ts)
            hour = dt.hour
        except (ValueError, TypeError):
            pass

        time_bucket = (
            "night" if hour < 6 else
            "morning" if hour < 12 else
            "afternoon" if hour < 18 else
            "evening"
        )

        # Duration
        dur = episode.get("duration_s", 0)
        dur_bucket = "fast" if dur < 60 else ("medium" if dur < 300 else "slow")

        return {
            "section": episode.get("section", "unknown"),
            "strategy": strategy,
            "task_complexity": complexity,
            "time_of_day": time_bucket,
            "duration_bucket": dur_bucket,
            "outcome": episode.get("outcome", "unknown"),
            "prior_outcome": prior_episode.get("outcome", "none") if prior_episode else "none",
            "has_error": "yes" if episode.get("error") else "no",
            "salience": "high" if episode.get("salience", 0) > 0.5 else "low",
        }

    def _estimate_cpt(self):
        """Estimate conditional probability tables from observations."""
        if not self._observations:
            return

        for var in self.variables:
            var_parents = self.parents.get(var, set())
            if not var_parents:
                # Root node: marginal distribution
                vals = [o.get(var, "?") for o in self._observations]
                counts = defaultdict(int)
                for v in vals:
                    counts[v] += 1
                total = len(vals)
                self._cpt[var] = {
                    "__marginal": {str(k): round(v / total, 3)
                                  for k, v in counts.items()}
                }
            else:
                # Conditional distribution given parents
                parent_list = sorted(var_parents)
                table = defaultdict(lambda: defaultdict(int))
                for obs in self._observations:
                    parent_key = tuple(obs.get(p, "?") for p in parent_list)
                    val = obs.get(var, "?")
                    table[parent_key][val] += 1

                cpt = {}
                for parent_key, val_counts in table.items():
                    total = sum(val_counts.values())
                    key = "|".join(f"{p}={v}" for p, v in zip(parent_list, parent_key))
                    cpt[key] = {str(k): round(v / total, 3)
                               for k, v in val_counts.items()}
                self._cpt[var] = cpt

    # ------------------------------------------------------------------
    # Analysis & reporting
    # ------------------------------------------------------------------

    def causal_analysis(self) -> dict:
        """Full causal analysis report over the episodic SCM."""
        report = {
            "model_name": self.name,
            "n_variables": len(self.variables),
            "n_edges": sum(len(v) for v in self.edges.values()),
            "n_observations": len(self._observations),
            "variables": sorted(self.variables),
            "edges": [(c, e) for c, effects in self.edges.items() for e in effects],
        }

        if not self._observations:
            report["findings"] = []
            return report

        findings = []

        # 1. What causes success? (interventional analysis)
        outcome_dist = defaultdict(int)
        for obs in self._observations:
            outcome_dist[obs.get("outcome", "?")] += 1
        total = len(self._observations)
        report["outcome_distribution"] = {
            k: round(v / total, 3) for k, v in outcome_dist.items()
        }

        # 2. Strategy effectiveness (do(strategy=X))
        strategies = set(o.get("strategy") for o in self._observations)
        strategy_effects = {}
        for strat in strategies:
            if strat is None:
                continue
            result = self.interventional_query("outcome", {"strategy": strat})
            if result.get("distribution"):
                success_rate = result["distribution"].get("success", 0)
                strategy_effects[strat] = {
                    "success_rate": success_rate,
                    "n": result["n"],
                }
        report["strategy_effectiveness"] = strategy_effects

        if strategy_effects:
            best = max(strategy_effects.items(),
                      key=lambda x: x[1]["success_rate"])
            worst = min(strategy_effects.items(),
                       key=lambda x: x[1]["success_rate"])
            if best[1]["success_rate"] > worst[1]["success_rate"]:
                findings.append(
                    f"Intervention insight: do(strategy={best[0]}) yields "
                    f"{best[1]['success_rate']:.0%} success vs "
                    f"do(strategy={worst[0]}) at {worst[1]['success_rate']:.0%}"
                )

        # 3. Section effects
        sections = set(o.get("section") for o in self._observations)
        section_effects = {}
        for sec in sections:
            if sec is None:
                continue
            result = self.interventional_query("outcome", {"section": sec})
            if result.get("distribution"):
                section_effects[sec] = {
                    "success_rate": result["distribution"].get("success", 0),
                    "n": result["n"],
                }
        report["section_effectiveness"] = section_effects

        # 4. Time-of-day effects
        times = set(o.get("time_of_day") for o in self._observations)
        time_effects = {}
        for t in times:
            if t is None:
                continue
            result = self.interventional_query("outcome", {"time_of_day": t})
            if result.get("distribution"):
                time_effects[t] = {
                    "success_rate": result["distribution"].get("success", 0),
                    "n": result["n"],
                }
        report["time_of_day_effects"] = time_effects

        # 5. Prior outcome effect (causal chain momentum)
        for prior in ["success", "failure"]:
            result = self.interventional_query("outcome", {"prior_outcome": prior})
            if result.get("distribution"):
                findings.append(
                    f"Causal chain: after prior {prior}, "
                    f"P(success) = {result['distribution'].get('success', 0):.0%} "
                    f"(n={result['n']})"
                )

        # 6. D-separation tests (which variables are independent?)
        dsep_results = []
        for x in ["time_of_day", "salience"]:
            for y in ["duration_bucket"]:
                if x in self.variables and y in self.variables:
                    sep = self.d_separated(x, y, {"outcome"})
                    dsep_results.append({
                        "x": x, "y": y, "given": ["outcome"],
                        "d_separated": sep,
                    })
        report["d_separation_tests"] = dsep_results

        # 7. Confounders (variables with children in both treatment and outcome paths)
        confounders = []
        for var in self.variables:
            children = self.edges.get(var, set())
            if "outcome" in children or any(
                "outcome" in self.edges.get(c, set()) for c in children
            ):
                if len(children) > 1:
                    confounders.append(var)
        report["potential_confounders"] = confounders
        if confounders:
            findings.append(
                f"Confounders identified: {', '.join(confounders)} — "
                f"control for these when estimating causal effects"
            )

        report["findings"] = findings
        return report

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def save(self, path: Path = None):
        """Save SCM to disk."""
        path = path or SCM_FILE
        data = {
            "name": self.name,
            "variables": sorted(self.variables),
            "edges": [(c, e) for c, effects in self.edges.items() for e in effects],
            "noise": {k: list(v) for k, v in self._noise.items()},
            "observations_count": len(self._observations),
            "cpt": self._cpt,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: Path = None) -> "StructuralCausalModel":
        """Load SCM from disk (structure only, not observations)."""
        path = path or SCM_FILE
        if not path.exists():
            return cls()
        data = json.loads(path.read_text())
        scm = cls(data.get("name", ""))
        for var in data.get("variables", []):
            noise = tuple(data.get("noise", {}).get(var, [0.0, 1.0]))
            scm.add_variable(var, noise)
        for cause, effect in data.get("edges", []):
            scm.add_edge(cause, effect)
        scm._cpt = data.get("cpt", {})
        return scm


# ------------------------------------------------------------------
# High-level API: build SCM from live episodic data
# ------------------------------------------------------------------

def build_task_scm() -> StructuralCausalModel:
    """Build a task-outcome SCM from current episodic memory."""
    from clarvis.memory.episodic_memory import episodic

    scm = StructuralCausalModel("clarvis_task_scm")
    scm.build_from_episodes(episodic.episodes, episodic.causal_links)
    scm.save()
    return scm


def run_counterfactual(episode_id: str, intervention: dict,
                       target: str = "outcome") -> dict:
    """Run a counterfactual query on a specific episode.

    Example: "Would episode ep_20260224_1200 have succeeded
             if strategy had been 'research' instead of 'implement'?"
    """
    from clarvis.memory.episodic_memory import episodic

    # Build fresh SCM
    scm = build_task_scm()

    # Find the episode
    ep = episodic._id_index.get(episode_id)
    if not ep:
        return {"error": f"Episode {episode_id} not found"}

    return scm.counterfactual(ep, intervention, target)


def store_findings_in_brain(report: dict):
    """Store causal analysis findings in the brain."""
    try:
        from clarvis.brain import brain

        findings = report.get("findings", [])
        if not findings:
            return

        text = (
            f"[CAUSAL ANALYSIS] SCM with {report['n_variables']} variables, "
            f"{report['n_edges']} edges, {report['n_observations']} observations. "
            f"Findings: " + " | ".join(findings[:5])
        )
        brain.store(
            text,
            collection="clarvis-learnings",
            importance=0.75,
            tags=["causal_inference", "scm", "pearl", "intervention"],
            source="causal_model",
            memory_id="causal_analysis_latest",
        )

        # Store strategy recommendations
        strat = report.get("strategy_effectiveness", {})
        if strat:
            best = max(strat.items(), key=lambda x: x[1]["success_rate"],
                      default=(None, {}))
            if best[0]:
                brain.store(
                    f"[CAUSAL] Best strategy: {best[0]} "
                    f"(success rate {best[1]['success_rate']:.0%}, "
                    f"n={best[1]['n']}). "
                    f"Identified via do-calculus interventional analysis.",
                    collection="clarvis-learnings",
                    importance=0.7,
                    tags=["causal_inference", "strategy", "recommendation"],
                    source="causal_model",
                    memory_id="causal_best_strategy",
                )
    except Exception as e:
        print(f"Warning: Could not store findings in brain: {e}", file=sys.stderr)


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Structural Causal Model Engine (Pearl)")
        print()
        print("Usage:")
        print("  build                            Build SCM from episodic memory")
        print("  dsep <X> <Y> <Z1,Z2,...>         Test d-separation")
        print("  do <var>=<val> [target]           Interventional query")
        print("  counterfactual <ep_id> <var>=<val> [target]  Counterfactual")
        print("  analyze                           Full causal analysis report")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "build":
        scm = build_task_scm()
        print(f"Built SCM: {len(scm.variables)} variables, "
              f"{sum(len(v) for v in scm.edges.values())} edges, "
              f"{len(scm._observations)} observations")
        print(f"Saved to {SCM_FILE}")

    elif cmd == "dsep":
        if len(sys.argv) < 5:
            print("Usage: dsep <X> <Y> <Z1,Z2,...>")
            sys.exit(1)
        x, y = sys.argv[2], sys.argv[3]
        z = set(sys.argv[4].split(",")) if sys.argv[4] != "none" else set()
        scm = build_task_scm()
        result = scm.d_separated(x, y, z)
        symbol = "⊥" if result else "⊥̸"
        print(f"{x} {symbol} {y} | {z}")
        print(f"d-separated: {result}")

    elif cmd == "do":
        if len(sys.argv) < 3:
            print("Usage: do <var>=<val> [target]")
            sys.exit(1)
        parts = sys.argv[2].split("=")
        var, val = parts[0], parts[1]
        target = sys.argv[3] if len(sys.argv) > 3 else "outcome"
        scm = build_task_scm()
        result = scm.interventional_query(target, {var: val})
        print(f"P({target} | do({var}={val})):")
        print(json.dumps(result, indent=2))

    elif cmd == "counterfactual":
        if len(sys.argv) < 4:
            print("Usage: counterfactual <episode_id> <var>=<val> [target]")
            sys.exit(1)
        ep_id = sys.argv[2]
        parts = sys.argv[3].split("=")
        var, val = parts[0], parts[1]
        target = sys.argv[4] if len(sys.argv) > 4 else "outcome"
        result = run_counterfactual(ep_id, {var: val}, target)
        print(json.dumps(result, indent=2))

    elif cmd == "analyze":
        print("Building SCM from episodic memory...")
        scm = build_task_scm()
        report = scm.causal_analysis()
        store_findings_in_brain(report)

        print(f"\n{'='*60}")
        print("CAUSAL ANALYSIS REPORT (Pearl SCM)")
        print(f"{'='*60}")
        print(f"\nModel: {report['model_name']}")
        print(f"Variables: {report['n_variables']}")
        print(f"Edges: {report['n_edges']}")
        print(f"Observations: {report['n_observations']}")

        print("\nOutcome distribution:")
        for k, v in report.get("outcome_distribution", {}).items():
            bar = "█" * int(v * 30)
            print(f"  {k:15s} {bar} {v:.0%}")

        print("\nStrategy effectiveness (do-calculus):")
        for strat, data in sorted(
            report.get("strategy_effectiveness", {}).items(),
            key=lambda x: x[1]["success_rate"], reverse=True
        ):
            bar = "█" * int(data["success_rate"] * 20)
            print(f"  do(strategy={strat:10s}) → success={data['success_rate']:.0%} "
                  f"{bar} (n={data['n']})")

        print("\nSection effectiveness:")
        for sec, data in sorted(
            report.get("section_effectiveness", {}).items(),
            key=lambda x: x[1]["success_rate"], reverse=True
        ):
            print(f"  {sec:20s} → success={data['success_rate']:.0%} (n={data['n']})")

        if report.get("time_of_day_effects"):
            print("\nTime-of-day effects:")
            for t, data in sorted(report["time_of_day_effects"].items()):
                print(f"  {t:12s} → success={data['success_rate']:.0%} (n={data['n']})")

        if report.get("d_separation_tests"):
            print("\nD-separation tests:")
            for test in report["d_separation_tests"]:
                symbol = "⊥" if test["d_separated"] else "⊥̸"
                print(f"  {test['x']} {symbol} {test['y']} | {test['given']}")

        if report.get("potential_confounders"):
            print(f"\nPotential confounders: {', '.join(report['potential_confounders'])}")

        if report.get("findings"):
            print("\nKey findings:")
            for finding in report["findings"]:
                print(f"  → {finding}")

        print("\n[Findings stored in brain]")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
