#!/usr/bin/env python3
"""
ClarvisReasoning — Multi-step reasoning chains with meta-cognitive monitoring.

Goes beyond simple thought logging to provide:
  1. Sub-problem decomposition — break complex tasks into reasoning sub-steps
  2. Reasoning quality evaluation — detect shallow, circular, or dead-end reasoning
  3. Meta-cognitive monitoring — track confidence, coherence, depth across chains
  4. Outcome tracking with calibration — predict outcomes, compare to actuals
  5. Cross-chain learning — find patterns across historical reasoning chains

This is the "standalone reasoning engine" that can be used by any Clarvis subsystem.

Usage:
    from clarvis_reasoning import reasoner

    # Start a reasoning session for a task
    session = reasoner.begin("Implement user auth system")

    # Decompose into sub-problems
    session.decompose(["Design auth flow", "Choose token strategy", "Implement endpoints"])

    # Reason through each sub-problem
    session.step("Design auth flow", thought="OAuth2 with PKCE for security",
                 evidence=["industry standard", "no server-side secret needed"],
                 confidence=0.85)

    session.step("Choose token strategy", thought="JWT with short-lived access tokens",
                 evidence=["stateless verification", "refresh token rotation"],
                 confidence=0.8)

    # Meta-cognitive check — is our reasoning sound?
    quality = session.evaluate()
    # -> {depth: 3, coherence: 0.82, confidence_spread: 0.05, quality_grade: "good"}

    # Complete with outcome
    session.complete(outcome="success", summary="Auth system implemented with OAuth2+JWT")

CLI:
    python3 clarvis_reasoning.py begin "task description"
    python3 clarvis_reasoning.py step <session_id> "thought" [--confidence 0.8] [--evidence "e1,e2"]
    python3 clarvis_reasoning.py evaluate <session_id>
    python3 clarvis_reasoning.py complete <session_id> success|failure "summary"
    python3 clarvis_reasoning.py diagnose             # Meta-cognitive health check
    python3 clarvis_reasoning.py stats                 # Reasoning statistics
    python3 clarvis_reasoning.py repair                # Fix chains with missing outcomes
"""

import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DATA_DIR = Path("/home/agent/.openclaw/workspace/data/reasoning_chains")
DATA_DIR.mkdir(parents=True, exist_ok=True)
SESSIONS_DIR = DATA_DIR / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
META_FILE = DATA_DIR / "reasoning_meta.json"


class ReasoningStep:
    """A single step in a reasoning chain."""

    __slots__ = ("step_num", "thought", "evidence", "confidence",
                 "timestamp", "outcome", "sub_problem", "quality_flags")

    def __init__(self, step_num: int, thought: str, sub_problem: str = "",
                 evidence: list = None, confidence: float = 0.5):
        self.step_num = step_num
        self.thought = thought
        self.sub_problem = sub_problem
        self.evidence = evidence or []
        self.confidence = max(0.0, min(1.0, confidence))
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.outcome = None
        self.quality_flags = []  # e.g., ["shallow", "unsupported", "circular"]

    def to_dict(self) -> dict:
        return {
            "step_num": self.step_num,
            "thought": self.thought,
            "sub_problem": self.sub_problem,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "outcome": self.outcome,
            "quality_flags": self.quality_flags,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ReasoningStep":
        step = cls(d["step_num"], d["thought"], d.get("sub_problem", ""),
                   d.get("evidence", []), d.get("confidence", 0.5))
        step.timestamp = d.get("timestamp", step.timestamp)
        step.outcome = d.get("outcome")
        step.quality_flags = d.get("quality_flags", [])
        return step


class ReasoningSession:
    """A full reasoning session for a task — multiple steps with meta-cognition."""

    def __init__(self, session_id: str, task: str):
        self.session_id = session_id
        self.task = task
        self.created = datetime.now(timezone.utc).isoformat()
        self.steps: list[ReasoningStep] = []
        self.sub_problems: list[str] = []
        self.predicted_outcome: Optional[str] = None
        self.predicted_confidence: float = 0.0
        self.actual_outcome: Optional[str] = None
        self.summary: str = ""
        self.meta_observations: list[dict] = []  # meta-cognitive notes
        self.completed = False

    def decompose(self, sub_problems: list[str]):
        """Break the task into sub-problems to reason through."""
        self.sub_problems = sub_problems
        self._meta_observe("decomposed",
                          f"Task decomposed into {len(sub_problems)} sub-problems: "
                          f"{'; '.join(sub_problems[:5])}")

    def step(self, thought: str, sub_problem: str = "",
             evidence: list = None, confidence: float = 0.5) -> ReasoningStep:
        """Add a reasoning step."""
        step_num = len(self.steps)
        rs = ReasoningStep(step_num, thought, sub_problem, evidence, confidence)

        # Quality check: detect shallow reasoning
        flags = self._check_step_quality(rs)
        rs.quality_flags = flags

        self.steps.append(rs)
        self._save()
        return rs

    def predict(self, outcome: str, confidence: float):
        """Record a prediction about the outcome before it happens."""
        self.predicted_outcome = outcome
        self.predicted_confidence = max(0.0, min(1.0, confidence))
        self._meta_observe("prediction",
                          f"Predicted outcome: {outcome} (confidence: {confidence:.2f})")
        self._save()

    def complete(self, outcome: str, summary: str = ""):
        """Complete the session with the actual outcome."""
        self.actual_outcome = outcome
        self.summary = summary
        self.completed = True

        # Record calibration data
        if self.predicted_outcome:
            hit = 1 if self.predicted_outcome == outcome else 0
            self._meta_observe("calibration",
                              f"Predicted {self.predicted_outcome} "
                              f"(conf={self.predicted_confidence:.2f}), "
                              f"got {outcome}. Hit={hit}")

        # Final meta-cognitive evaluation
        evaluation = self.evaluate()
        self._meta_observe("final_evaluation", json.dumps(evaluation))

        self._save()

        # Store in brain if available
        self._store_in_brain(outcome, summary, evaluation)

    def evaluate(self) -> dict:
        """Meta-cognitive evaluation of reasoning quality."""
        if not self.steps:
            return {"depth": 0, "quality_grade": "empty",
                    "coherence": 0.0, "issues": ["no_steps"]}

        depth = len(self.steps)
        confidences = [s.confidence for s in self.steps]
        avg_confidence = sum(confidences) / len(confidences)
        confidence_spread = max(confidences) - min(confidences) if len(confidences) > 1 else 0

        # Evidence coverage: what fraction of steps have evidence?
        evidence_coverage = sum(1 for s in self.steps if s.evidence) / depth

        # Sub-problem coverage: what fraction of declared sub-problems were addressed?
        if self.sub_problems:
            addressed = set()
            for s in self.steps:
                if s.sub_problem:
                    for sp in self.sub_problems:
                        if s.sub_problem.lower() in sp.lower() or sp.lower() in s.sub_problem.lower():
                            addressed.add(sp)
            sub_problem_coverage = len(addressed) / len(self.sub_problems)
        else:
            sub_problem_coverage = 1.0  # No decomposition = vacuously covered

        # Quality flags across all steps
        all_flags = []
        for s in self.steps:
            all_flags.extend(s.quality_flags)
        flag_counts = Counter(all_flags)

        # Coherence: are thoughts building on each other or disjointed?
        coherence = self._compute_coherence()

        # Issues
        issues = []
        if depth < 2:
            issues.append("shallow_reasoning")
        if evidence_coverage < 0.3:
            issues.append("low_evidence")
        if flag_counts.get("circular", 0) > 0:
            issues.append("circular_reasoning")
        if flag_counts.get("unsupported", 0) > 1:
            issues.append("many_unsupported_claims")
        if avg_confidence > 0.95:
            issues.append("overconfident")
        if sub_problem_coverage < 0.5 and self.sub_problems:
            issues.append("incomplete_decomposition")
        if not self.actual_outcome and not self.predicted_outcome:
            issues.append("no_prediction")

        # Grade
        score = 0.0
        score += min(0.25, depth * 0.05)           # depth: up to 0.25 for 5+ steps
        score += evidence_coverage * 0.25            # evidence: up to 0.25
        score += coherence * 0.25                    # coherence: up to 0.25
        score += sub_problem_coverage * 0.15         # decomposition: up to 0.15
        score += (0.1 if self.predicted_outcome else 0)  # prediction: 0.1

        # Penalty for issues
        score -= len(issues) * 0.05
        score = max(0.0, min(1.0, score))

        if score >= 0.7:
            grade = "good"
        elif score >= 0.45:
            grade = "adequate"
        elif score >= 0.2:
            grade = "shallow"
        else:
            grade = "poor"

        return {
            "depth": depth,
            "avg_confidence": round(avg_confidence, 3),
            "confidence_spread": round(confidence_spread, 3),
            "evidence_coverage": round(evidence_coverage, 3),
            "sub_problem_coverage": round(sub_problem_coverage, 3),
            "coherence": round(coherence, 3),
            "quality_score": round(score, 3),
            "quality_grade": grade,
            "issues": issues,
            "flag_counts": dict(flag_counts),
        }

    def _check_step_quality(self, step: ReasoningStep) -> list[str]:
        """Check a single step for quality issues."""
        flags = []
        thought_lower = step.thought.lower()

        # Shallow: very short thought with no evidence
        if len(step.thought) < 30 and not step.evidence:
            flags.append("shallow")

        # Unsupported: high confidence with no evidence
        if step.confidence > 0.8 and not step.evidence:
            flags.append("unsupported")

        # Circular: repeating earlier thoughts
        for prev in self.steps:
            # Simple word overlap detection
            prev_words = set(prev.thought.lower().split())
            step_words = set(thought_lower.split())
            if len(prev_words) >= 5 and len(step_words) >= 5:
                overlap = len(prev_words & step_words) / max(1, len(prev_words | step_words))
                if overlap > 0.7:
                    flags.append("circular")
                    break

        # Hedge words: detect waffling
        hedges = ["maybe", "perhaps", "might", "could possibly", "not sure", "i think"]
        hedge_count = sum(1 for h in hedges if h in thought_lower)
        if hedge_count >= 2:
            flags.append("hedging")

        return flags

    def _compute_coherence(self) -> float:
        """Measure how well reasoning steps build on each other.

        Uses word overlap between consecutive steps as a proxy.
        Higher overlap between consecutive steps = more coherent chain.
        """
        if len(self.steps) < 2:
            return 0.5  # neutral for single step

        overlaps = []
        for i in range(1, len(self.steps)):
            prev_words = set(self.steps[i - 1].thought.lower().split())
            curr_words = set(self.steps[i].thought.lower().split())
            # Remove stop words
            stop = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                    "to", "of", "in", "for", "on", "with", "at", "by", "from",
                    "and", "or", "but", "not", "this", "that", "it"}
            prev_words -= stop
            curr_words -= stop
            if prev_words and curr_words:
                overlap = len(prev_words & curr_words) / max(1, len(prev_words | curr_words))
                overlaps.append(overlap)

        if not overlaps:
            return 0.5
        # Ideal coherence: moderate overlap (0.1-0.4) — too high means repetition
        avg_overlap = sum(overlaps) / len(overlaps)
        # Bell curve: peak at 0.25 overlap
        coherence = 1.0 - 4.0 * (avg_overlap - 0.25) ** 2
        return max(0.0, min(1.0, coherence))

    def _meta_observe(self, observation_type: str, content: str):
        """Record a meta-cognitive observation."""
        self.meta_observations.append({
            "type": observation_type,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def _store_in_brain(self, outcome: str, summary: str, evaluation: dict):
        """Store reasoning session summary in brain for cross-session learning."""
        try:
            from brain import brain
            grade = evaluation.get("quality_grade", "unknown")
            depth = evaluation.get("depth", 0)
            text = (f"Reasoning session [{self.session_id}]: {self.task[:100]}. "
                    f"Outcome: {outcome}. Grade: {grade}. Depth: {depth} steps. "
                    f"{summary[:200]}")
            brain.store(
                text,
                collection="clarvis-learnings",
                importance=0.6 if grade in ("good", "adequate") else 0.4,
                tags=["clarvis_reasoning", self.session_id, grade],
                source="clarvis_reasoning",
                memory_id=f"reasoning_{self.session_id}",
            )
        except Exception:
            pass

    def _save(self):
        """Persist session to disk."""
        data = {
            "session_id": self.session_id,
            "task": self.task,
            "created": self.created,
            "steps": [s.to_dict() for s in self.steps],
            "sub_problems": self.sub_problems,
            "predicted_outcome": self.predicted_outcome,
            "predicted_confidence": self.predicted_confidence,
            "actual_outcome": self.actual_outcome,
            "summary": self.summary,
            "meta_observations": self.meta_observations,
            "completed": self.completed,
        }
        path = SESSIONS_DIR / f"{self.session_id}.json"
        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, session_id: str) -> "ReasoningSession":
        """Load a session from disk."""
        path = SESSIONS_DIR / f"{session_id}.json"
        if not path.exists():
            # Try legacy chain format
            legacy = DATA_DIR / f"{session_id}.json"
            if legacy.exists():
                return cls._from_legacy(session_id, json.loads(legacy.read_text()))
            raise FileNotFoundError(f"Session {session_id} not found")

        data = json.loads(path.read_text())
        session = cls(data["session_id"], data["task"])
        session.created = data.get("created", session.created)
        session.steps = [ReasoningStep.from_dict(s) for s in data.get("steps", [])]
        session.sub_problems = data.get("sub_problems", [])
        session.predicted_outcome = data.get("predicted_outcome")
        session.predicted_confidence = data.get("predicted_confidence", 0.0)
        session.actual_outcome = data.get("actual_outcome")
        session.summary = data.get("summary", "")
        session.meta_observations = data.get("meta_observations", [])
        session.completed = data.get("completed", False)
        return session

    @classmethod
    def _from_legacy(cls, chain_id: str, data: dict) -> "ReasoningSession":
        """Convert a legacy reasoning chain to a session."""
        session = cls(chain_id, data.get("title", ""))
        session.created = data.get("created", session.created)
        for s in data.get("steps", []):
            rs = ReasoningStep(
                s.get("step", 0),
                s.get("thought", ""),
                confidence=0.5,
            )
            rs.timestamp = s.get("timestamp", rs.timestamp)
            rs.outcome = s.get("outcome")
            session.steps.append(rs)
        # If any step has a "Chain complete:" outcome, mark completed
        for s in session.steps:
            if s.outcome and "Chain complete:" in str(s.outcome):
                session.completed = True
                session.actual_outcome = "success" if "success" in str(s.outcome) else "failure"
                break
        return session


class ClarvisReasoner:
    """Main reasoning engine with meta-cognitive monitoring."""

    def __init__(self):
        self._meta = self._load_meta()

    def _load_meta(self) -> dict:
        if META_FILE.exists():
            try:
                return json.loads(META_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {
            "total_sessions": 0,
            "calibration": {"hits": 0, "misses": 0, "total": 0},
            "grade_distribution": {},
            "avg_depth": 0.0,
            "last_diagnosis": None,
        }

    def _save_meta(self):
        META_FILE.write_text(json.dumps(self._meta, indent=2))

    def begin(self, task: str) -> ReasoningSession:
        """Begin a new reasoning session."""
        session_id = f"rs_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        session = ReasoningSession(session_id, task)
        self._meta["total_sessions"] = self._meta.get("total_sessions", 0) + 1
        self._save_meta()
        session._save()
        return session

    def causal_query(self, treatment: str, treatment_val: str,
                     target: str = "outcome") -> Optional[dict]:
        """Run a Pearl do-calculus interventional query.

        Answers: P(target | do(treatment=treatment_val))
        Uses the SCM built from episodic memory.

        Returns the interventional query result, or None if SCM unavailable.
        """
        try:
            from causal_model import build_task_scm
            scm = build_task_scm()
            return scm.interventional_query(target, {treatment: treatment_val})
        except Exception:
            return None

    def load_session(self, session_id: str) -> ReasoningSession:
        """Load an existing session."""
        return ReasoningSession.load(session_id)

    def list_sessions(self, limit: int = 20) -> list[dict]:
        """List recent reasoning sessions."""
        sessions = []
        for f in sorted(SESSIONS_DIR.glob("rs_*.json"), reverse=True)[:limit]:
            try:
                data = json.loads(f.read_text())
                sessions.append({
                    "session_id": data["session_id"],
                    "task": data["task"][:80],
                    "steps": len(data.get("steps", [])),
                    "completed": data.get("completed", False),
                    "outcome": data.get("actual_outcome"),
                    "created": data.get("created", ""),
                })
            except (json.JSONDecodeError, KeyError):
                continue
        return sessions

    def diagnose(self) -> dict:
        """Meta-cognitive health check across all reasoning.

        Returns a diagnostic report covering:
        - Overall reasoning depth
        - Quality grade distribution
        - Common quality issues
        - Calibration accuracy
        - Recommendations
        """
        sessions = []
        legacy_chains = []

        # Load all new-format sessions
        for f in SESSIONS_DIR.glob("rs_*.json"):
            try:
                s = ReasoningSession.load(f.stem)
                sessions.append(s)
            except Exception:
                continue

        # Load legacy chains for backward compat
        for f in DATA_DIR.glob("chain_*.json"):
            try:
                data = json.loads(f.read_text())
                legacy_chains.append(data)
            except Exception:
                continue

        total_reasoning = len(sessions) + len(legacy_chains)
        if total_reasoning == 0:
            return {"status": "no_data", "recommendations": ["Start using reasoner.begin() for tasks"]}

        # Evaluate all new-format sessions
        evaluations = []
        all_issues = []
        depths = []
        for s in sessions:
            ev = s.evaluate()
            evaluations.append(ev)
            all_issues.extend(ev.get("issues", []))
            depths.append(ev["depth"])

        # Legacy chain stats
        for chain in legacy_chains:
            steps = chain.get("steps", [])
            depth = len(steps)
            depths.append(depth)
            has_outcome = any(s.get("outcome") for s in steps)
            if depth < 2:
                all_issues.append("shallow_reasoning")
            if not has_outcome:
                all_issues.append("no_outcome")

        # Grade distribution
        grade_dist = Counter(ev.get("quality_grade", "unknown") for ev in evaluations)

        # Issue frequency
        issue_freq = Counter(all_issues)

        # Calibration from completed sessions
        cal_hits = 0
        cal_total = 0
        for s in sessions:
            if s.completed and s.predicted_outcome:
                cal_total += 1
                if s.predicted_outcome == s.actual_outcome:
                    cal_hits += 1

        # Depth statistics
        avg_depth = sum(depths) / len(depths) if depths else 0
        deep_chains = sum(1 for d in depths if d >= 3)
        shallow_chains = sum(1 for d in depths if d < 2)

        # Recommendations
        recommendations = []
        if avg_depth < 2.5:
            recommendations.append("Increase reasoning depth — most chains are too shallow. "
                                  "Use decompose() to break tasks into sub-problems.")
        if issue_freq.get("low_evidence", 0) > len(sessions) * 0.3:
            recommendations.append("Add evidence to reasoning steps — too many unsupported claims.")
        if issue_freq.get("circular_reasoning", 0) > 2:
            recommendations.append("Circular reasoning detected — diversify thought approaches.")
        if issue_freq.get("no_prediction", 0) > len(sessions) * 0.5:
            recommendations.append("Use predict() before task execution to improve calibration.")
        if shallow_chains > total_reasoning * 0.4:
            recommendations.append(f"{shallow_chains}/{total_reasoning} chains are shallow (<2 steps). "
                                  f"The reasoning_chain_hook should add more substantive steps.")
        if issue_freq.get("no_outcome", 0) > 5:
            recommendations.append(f"{issue_freq['no_outcome']} legacy chains have no outcomes. "
                                  f"Run 'python3 clarvis_reasoning.py repair' to fix.")

        # Legacy-specific stats
        legacy_no_outcome = sum(
            1 for c in legacy_chains
            if not any(s.get("outcome") for s in c.get("steps", []))
        )

        report = {
            "status": "analyzed",
            "total_reasoning_chains": total_reasoning,
            "new_format_sessions": len(sessions),
            "legacy_chains": len(legacy_chains),
            "legacy_without_outcomes": legacy_no_outcome,
            "avg_depth": round(avg_depth, 2),
            "deep_chains_3plus": deep_chains,
            "shallow_chains_lt2": shallow_chains,
            "grade_distribution": dict(grade_dist),
            "top_issues": dict(issue_freq.most_common(5)),
            "calibration": {
                "hits": cal_hits,
                "total": cal_total,
                "accuracy": round(cal_hits / cal_total, 3) if cal_total > 0 else None,
            },
            "recommendations": recommendations,
        }

        self._meta["last_diagnosis"] = datetime.now(timezone.utc).isoformat()
        self._meta["avg_depth"] = report["avg_depth"]
        self._meta["grade_distribution"] = report["grade_distribution"]
        self._meta["calibration"] = report["calibration"]
        self._save_meta()

        return report

    def repair_legacy_chains(self) -> dict:
        """Fix legacy chains that have missing outcomes.

        For chains where close_chain was never called, infer outcome from
        the chain's context and mark them as completed.
        """
        fixed = 0
        skipped = 0
        for f in DATA_DIR.glob("chain_*.json"):
            try:
                chain = json.loads(f.read_text())
                steps = chain.get("steps", [])
                has_outcome = any(s.get("outcome") for s in steps)

                if not has_outcome and steps:
                    # Mark the last step with an inferred outcome
                    steps[-1]["outcome"] = "inferred:no_close_chain_called"
                    f.write_text(json.dumps(chain, indent=2))
                    fixed += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1

        return {"fixed": fixed, "skipped": skipped}

    def get_reasoning_score(self) -> tuple[float, list[str]]:
        """Get a 0-1 score for reasoning quality — used by self_model.py.

        Improved version that scores on quality, not just existence.

        Returns:
            (score, evidence_list)
        """
        score = 0.0
        evidence = []

        # Count all sessions + legacy
        session_files = list(SESSIONS_DIR.glob("rs_*.json"))
        legacy_files = list(DATA_DIR.glob("chain_*.json"))
        total = len(session_files) + len(legacy_files)
        evidence.append(f"{total} total reasoning artifacts ({len(session_files)} sessions, {len(legacy_files)} legacy)")

        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        today_count = 0
        today_with_outcomes = 0

        # Score new-format sessions
        good_sessions = 0
        deep_sessions = 0  # sessions with 4+ steps (beyond minimum bar)
        for f in session_files:
            try:
                s = ReasoningSession.load(f.stem)
                ev = s.evaluate()
                if ev["quality_grade"] in ("good", "adequate"):
                    good_sessions += 1
                if len(s.steps) >= 4 and s.completed:
                    deep_sessions += 1
                if today in s.created:
                    today_count += 1
                    if s.completed:
                        today_with_outcomes += 1
            except Exception:
                continue

        # Score legacy chains
        hq_legacy = 0
        deep_legacy = 0  # legacy chains with 4+ steps
        for f in legacy_files:
            try:
                chain = json.loads(f.read_text())
                steps = chain.get("steps", [])
                has_outcome = any(s.get("outcome") for s in steps)
                if len(steps) >= 2 and has_outcome:
                    hq_legacy += 1
                if len(steps) >= 4 and has_outcome:
                    deep_legacy += 1
                if today in f.name:
                    today_count += 1
                    if has_outcome:
                        today_with_outcomes += 1
            except Exception:
                continue

        # Logarithmic quality score — diminishing returns, ~100 chains for full 0.35
        quality_count = good_sessions + hq_legacy
        quality_score = min(0.35, math.log1p(quality_count) / math.log1p(100) * 0.35)
        score += quality_score
        if quality_count > 0:
            evidence.append(f"{quality_count} quality chains (log scale) (+{quality_score:.2f})")

        # Chain depth — rewards chains that go beyond the 2-step minimum
        deep_count = deep_sessions + deep_legacy
        depth_score = min(0.15, deep_count / max(quality_count, 1) * 0.15)
        score += depth_score
        if deep_count > 0:
            evidence.append(f"{deep_count}/{quality_count} deep chains (4+ steps) (+{depth_score:.2f})")

        # Today's quality ratio (0-0.3) — require at least 3 chains for full score
        if today_count > 0:
            today_score = min(0.3, (today_with_outcomes / max(3, today_count)) * 0.3)
            score += today_score
            evidence.append(f"today: {today_with_outcomes}/{today_count} with outcomes (need 3+) (+{today_score:.2f})")
            # Freshness bonus
            score += 0.15
            evidence.append("active today (+0.15)")

        # Hook exists (minimal)
        hook = Path("/home/agent/.openclaw/workspace/scripts/reasoning_chain_hook.py")
        if hook.exists():
            score += 0.05
            evidence.append("reasoning hook exists (+0.05)")

        return max(0.0, min(1.0, score)), evidence


# Singleton (lazy — no I/O until first access)
_reasoner = None

def get_reasoner():
    global _reasoner
    if _reasoner is None:
        _reasoner = ClarvisReasoner()
    return _reasoner

class _LazyReasoner:
    def __getattr__(self, name):
        real = get_reasoner()
        global reasoner
        reasoner = real
        return getattr(real, name)
    def __repr__(self):
        return "<LazyReasoner (not yet initialized)>"

reasoner = _LazyReasoner()


# =================================================================
# CLI
# =================================================================

def _print_evaluation(ev: dict):
    """Pretty-print an evaluation."""
    grade_colors = {"good": "32", "adequate": "33", "shallow": "31", "poor": "31", "empty": "37"}
    grade = ev.get("quality_grade", "unknown")
    color = grade_colors.get(grade, "37")
    print(f"  Quality: \033[{color}m{grade.upper()}\033[0m (score: {ev['quality_score']:.3f})")
    print(f"  Depth: {ev['depth']} steps")
    print(f"  Avg confidence: {ev['avg_confidence']:.3f} (spread: {ev['confidence_spread']:.3f})")
    print(f"  Evidence coverage: {ev['evidence_coverage']:.0%}")
    print(f"  Coherence: {ev['coherence']:.3f}")
    if ev.get("sub_problem_coverage", 1.0) < 1.0:
        print(f"  Sub-problem coverage: {ev['sub_problem_coverage']:.0%}")
    if ev.get("issues"):
        print(f"  Issues: {', '.join(ev['issues'])}")
    if ev.get("flag_counts"):
        print(f"  Step flags: {ev['flag_counts']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("ClarvisReasoning — Multi-step reasoning with meta-cognition")
        print()
        print("Usage:")
        print("  begin <task>                          Start reasoning session")
        print("  step <id> <thought> [--conf N] [--ev e1,e2]  Add reasoning step")
        print("  decompose <id> sub1,sub2,sub3         Decompose into sub-problems")
        print("  predict <id> success|failure <conf>    Record outcome prediction")
        print("  evaluate <id>                         Evaluate reasoning quality")
        print("  complete <id> success|failure [summary]  Complete session")
        print("  diagnose                              Meta-cognitive health check")
        print("  stats                                 Show reasoning statistics")
        print("  list                                  List recent sessions")
        print("  repair                                Fix legacy chains")
        print("  score                                 Get reasoning score (for self_model)")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "begin":
        task = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "unnamed task"
        session = reasoner.begin(task)
        print(session.session_id)

    elif cmd == "step":
        session_id = sys.argv[2] if len(sys.argv) > 2 else ""
        thought = sys.argv[3] if len(sys.argv) > 3 else ""
        confidence = 0.5
        evidence = []
        # Parse optional flags
        args = sys.argv[4:]
        i = 0
        while i < len(args):
            if args[i] in ("--conf", "--confidence") and i + 1 < len(args):
                confidence = float(args[i + 1])
                i += 2
            elif args[i] in ("--ev", "--evidence") and i + 1 < len(args):
                evidence = [e.strip() for e in args[i + 1].split(",")]
                i += 2
            else:
                i += 1

        if not session_id or not thought:
            print("Usage: step <session_id> <thought> [--conf N] [--ev e1,e2]", file=sys.stderr)
            sys.exit(1)

        session = reasoner.load_session(session_id)
        step = session.step(thought, evidence=evidence, confidence=confidence)
        print(f"Step {step.step_num} added to {session_id}", file=sys.stderr)
        if step.quality_flags:
            print(f"  Quality flags: {', '.join(step.quality_flags)}", file=sys.stderr)

    elif cmd == "decompose":
        session_id = sys.argv[2] if len(sys.argv) > 2 else ""
        subs_raw = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
        subs = [s.strip() for s in subs_raw.split(",") if s.strip()]
        if not session_id or not subs:
            print("Usage: decompose <session_id> sub1,sub2,sub3", file=sys.stderr)
            sys.exit(1)
        session = reasoner.load_session(session_id)
        session.decompose(subs)
        session._save()
        print(f"Decomposed into {len(subs)} sub-problems", file=sys.stderr)

    elif cmd == "predict":
        session_id = sys.argv[2] if len(sys.argv) > 2 else ""
        outcome = sys.argv[3] if len(sys.argv) > 3 else ""
        conf = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5
        if not session_id or not outcome:
            print("Usage: predict <session_id> success|failure <confidence>", file=sys.stderr)
            sys.exit(1)
        session = reasoner.load_session(session_id)
        session.predict(outcome, conf)
        print(f"Prediction recorded: {outcome} (conf={conf:.2f})", file=sys.stderr)

    elif cmd == "evaluate":
        session_id = sys.argv[2] if len(sys.argv) > 2 else ""
        if not session_id:
            print("Usage: evaluate <session_id>", file=sys.stderr)
            sys.exit(1)
        session = reasoner.load_session(session_id)
        ev = session.evaluate()
        print(f"\nEvaluation for {session_id} ({session.task[:60]}):")
        _print_evaluation(ev)

    elif cmd == "complete":
        session_id = sys.argv[2] if len(sys.argv) > 2 else ""
        outcome = sys.argv[3] if len(sys.argv) > 3 else ""
        summary = " ".join(sys.argv[4:]) if len(sys.argv) > 4 else ""
        if not session_id or not outcome:
            print("Usage: complete <session_id> success|failure [summary]", file=sys.stderr)
            sys.exit(1)
        session = reasoner.load_session(session_id)
        session.complete(outcome, summary)
        print(f"Session {session_id} completed: {outcome}", file=sys.stderr)

    elif cmd == "diagnose":
        report = reasoner.diagnose()
        print(f"\n{'='*60}")
        print("CLARVIS REASONING — META-COGNITIVE DIAGNOSIS")
        print(f"{'='*60}")
        print(f"\n  Total reasoning chains: {report['total_reasoning_chains']}")
        print(f"  New-format sessions: {report['new_format_sessions']}")
        print(f"  Legacy chains: {report['legacy_chains']}")
        if report.get("legacy_without_outcomes", 0) > 0:
            print(f"  Legacy without outcomes: {report['legacy_without_outcomes']}")
        print(f"\n  Avg depth: {report['avg_depth']:.2f} steps")
        print(f"  Deep chains (3+): {report['deep_chains_3plus']}")
        print(f"  Shallow chains (<2): {report['shallow_chains_lt2']}")
        if report.get("grade_distribution"):
            print(f"\n  Grade distribution: {report['grade_distribution']}")
        if report.get("top_issues"):
            print(f"  Top issues: {report['top_issues']}")
        cal = report.get("calibration", {})
        if cal.get("total", 0) > 0:
            print(f"\n  Calibration: {cal['hits']}/{cal['total']} correct ({cal['accuracy']:.0%})")
        if report.get("recommendations"):
            print("\n  Recommendations:")
            for r in report["recommendations"]:
                print(f"    - {r}")

    elif cmd == "stats":
        meta = reasoner._meta
        print("ClarvisReasoning Statistics:")
        print(f"  Total sessions created: {meta.get('total_sessions', 0)}")
        print(f"  Last diagnosis: {meta.get('last_diagnosis', 'never')}")
        print(f"  Avg depth: {meta.get('avg_depth', 0):.2f}")
        cal = meta.get("calibration", {})
        if cal.get("total", 0) > 0:
            print(f"  Calibration: {cal['accuracy']:.0%} ({cal['total']} predictions)")
        if meta.get("grade_distribution"):
            print(f"  Grade distribution: {meta['grade_distribution']}")

    elif cmd == "list":
        sessions = reasoner.list_sessions()
        if not sessions:
            print("No reasoning sessions found.")
        else:
            print(f"Recent reasoning sessions ({len(sessions)}):")
            for s in sessions:
                status = "done" if s["completed"] else "open"
                outcome = f" [{s['outcome']}]" if s.get("outcome") else ""
                print(f"  {s['session_id']}  {s['steps']} steps  {status}{outcome}  {s['task']}")

    elif cmd == "repair":
        result = reasoner.repair_legacy_chains()
        print(f"Repaired {result['fixed']} chains, skipped {result['skipped']}")

    elif cmd == "score":
        score, evidence = reasoner.get_reasoning_score()
        print(f"Reasoning score: {score:.3f}")
        for e in evidence:
            print(f"  {e}")

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
