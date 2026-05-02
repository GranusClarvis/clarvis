"""Tests for clarvis.cognition.metacognition — quality checks, coherence, Brier score.

Migrated from packages/clarvis-reasoning/tests/test_metacognition.py.
"""

import pytest

from clarvis.cognition.metacognition import (
    brier_score,
    check_step_quality,
    classify_episode_failure,
    compute_coherence,
    compute_episode_success_rate,
    diagnose_sessions,
    ESR_EXCLUDED_FAILURE_TYPES,
    evaluate_session,
    GRADE_GOOD,
    GRADE_ADEQUATE,
    GRADE_SHALLOW,
)


# ── check_step_quality ────────────────���─────────────────────────────

class TestCheckStepQuality:
    def test_good_step_no_flags(self):
        flags = check_step_quality(
            thought="The database query is slow because the index is missing on the users table.",
            evidence=["EXPLAIN shows full table scan on users (1.2M rows)."],
            confidence=0.85,
            previous_thoughts=[],
        )
        assert flags == []

    def test_shallow_flag(self):
        flags = check_step_quality(
            thought="It's slow",  # < 30 chars, no evidence
            evidence=[],
            confidence=0.5,
            previous_thoughts=[],
        )
        assert "shallow" in flags

    def test_unsupported_flag(self):
        flags = check_step_quality(
            thought="The root cause is definitely a memory leak in the connection pool.",
            evidence=[],  # no evidence but high confidence
            confidence=0.95,
            previous_thoughts=[],
        )
        assert "unsupported" in flags

    def test_circular_flag(self):
        prev = ["database query slow missing index table scan performance"]
        flags = check_step_quality(
            thought="missing index database query slow table scan performance",
            evidence=[],
            confidence=0.5,
            previous_thoughts=prev,
        )
        assert "circular" in flags

    def test_hedging_flag(self):
        flags = check_step_quality(
            thought="Maybe it could possibly be a network issue, perhaps, I think not sure.",
            evidence=[],
            confidence=0.3,
            previous_thoughts=[],
        )
        assert "hedging" in flags

    def test_multiple_flags(self):
        flags = check_step_quality(
            thought="Maybe slow",  # short + hedging (needs 2 hedge words)
            evidence=[],
            confidence=0.9,  # high confidence + no evidence = unsupported
            previous_thoughts=[],
        )
        # shallow (< 30 chars, no evidence) + unsupported (> 0.8 conf, no evidence)
        assert len(flags) >= 2

    def test_evidence_prevents_shallow(self):
        flags = check_step_quality(
            thought="It's slow",  # short but has evidence
            evidence=["Latency p99 = 12s"],
            confidence=0.5,
            previous_thoughts=[],
        )
        assert "shallow" not in flags


# ── compute_coherence ────────────────���──────────────────────────────

class TestComputeCoherence:
    def test_empty_list(self):
        assert compute_coherence([]) == 0.5

    def test_single_thought(self):
        assert compute_coherence(["Just one thought"]) == 0.5

    def test_related_thoughts_high_coherence(self):
        thoughts = [
            "The database query takes 2 seconds on the users table.",
            "The users table has no index on the email column.",
            "Adding an index on users.email should reduce the query time.",
        ]
        score = compute_coherence(thoughts)
        assert 0.0 <= score <= 1.0
        assert score > 0.3  # related thoughts should be somewhat coherent

    def test_unrelated_thoughts_lower_coherence(self):
        thoughts = [
            "The sky is blue because of Rayleigh scattering.",
            "Python was created by Guido van Rossum in 1991.",
            "The mitochondria is the powerhouse of the cell.",
        ]
        score = compute_coherence(thoughts)
        assert 0.0 <= score <= 1.0

    def test_identical_thoughts_penalized(self):
        # Identical thoughts = 100% overlap, far from optimal 0.25
        thoughts = ["same words here"] * 5
        score = compute_coherence(thoughts)
        assert score < 0.8  # should be penalized for too much overlap


# ── evaluate_session ────────────────────────────────────────────────

class TestEvaluateSession:
    def _make_step(self, thought, evidence="", confidence=0.7):
        return {"thought": thought, "evidence": evidence, "confidence": confidence}

    def test_good_session(self):
        steps = [
            self._make_step("Identified the slow query in the API endpoint.", "Logs show 2s latency", 0.8),
            self._make_step("Found missing index on users.email column.", "EXPLAIN output attached", 0.85),
            self._make_step("Adding index reduced query to 15ms.", "Benchmark result: 15ms avg", 0.9),
            self._make_step("Deployed the fix and verified in production.", "Grafana dashboard confirms", 0.95),
        ]
        result = evaluate_session(
            steps=steps,
            sub_problems=["identify bottleneck", "find root cause", "implement fix"],
            predicted_outcome="Index addition will fix the latency",
            actual_outcome="Latency reduced from 2s to 15ms",
        )
        assert result["quality_grade"] in ("good", "adequate")
        assert result["quality_score"] >= GRADE_ADEQUATE
        assert result["depth"] == 4
        assert result["coherence"] > 0

    def test_shallow_session(self):
        steps = [self._make_step("Dunno", "", 0.3)]
        result = evaluate_session(
            steps=steps,
            sub_problems=["a", "b", "c"],
            predicted_outcome="",
            actual_outcome="",
        )
        assert result["quality_score"] < GRADE_GOOD
        assert len(result["issues"]) > 0

    def test_empty_session(self):
        result = evaluate_session(
            steps=[],
            sub_problems=[],
            predicted_outcome="",
            actual_outcome="",
        )
        assert result["depth"] == 0
        assert result["quality_score"] <= GRADE_SHALLOW

    def test_no_prediction_flagged(self):
        steps = [
            self._make_step("Analysis done.", "evidence here", 0.7),
            self._make_step("Conclusion reached.", "more evidence", 0.8),
        ]
        result = evaluate_session(
            steps=steps,
            sub_problems=[],
            predicted_outcome="",
            actual_outcome="",
        )
        assert "no_prediction" in result["issues"]

    def test_session_returns_expected_keys(self):
        steps = [self._make_step("A step.", "ev", 0.5)]
        result = evaluate_session(steps=steps, sub_problems=[], predicted_outcome="", actual_outcome="")
        expected_keys = {"depth", "coherence", "quality_score", "quality_grade", "issues"}
        assert expected_keys.issubset(set(result.keys()))


# ── brier_score ─────────────────────────────────────────────────────

class TestBrierScore:
    def test_perfect_calibration(self):
        predictions = [
            ("outcome_a", 1.0, "outcome_a"),
            ("outcome_b", 1.0, "outcome_b"),
        ]
        score = brier_score(predictions)
        assert score == 0.0

    def test_worst_calibration(self):
        predictions = [
            ("outcome_a", 1.0, "outcome_b"),
            ("outcome_b", 1.0, "outcome_a"),
        ]
        score = brier_score(predictions)
        assert score == 1.0

    def test_random_calibration(self):
        predictions = [
            ("a", 0.5, "a"),
            ("b", 0.5, "c"),
        ]
        score = brier_score(predictions)
        assert score == pytest.approx(0.25, abs=0.01)

    def test_empty_predictions(self):
        assert brier_score([]) is None

    def test_none_predictions(self):
        assert brier_score(None) is None

    def test_mixed_calibration(self):
        predictions = [
            ("a", 0.9, "a"),
            ("b", 0.1, "c"),
            ("c", 0.8, "d"),
        ]
        score = brier_score(predictions)
        assert 0.0 < score < 1.0

    def test_single_correct_prediction(self):
        score = brier_score([("x", 0.7, "x")])
        assert score == pytest.approx(0.09, abs=0.01)

    def test_single_wrong_prediction(self):
        score = brier_score([("x", 0.7, "y")])
        assert score == pytest.approx(0.49, abs=0.01)


# ── diagnose_sessions ──────────────────────────────────────────────

class TestDiagnoseSessions:
    def _make_session(self, steps, sub_problems=None, predicted="", actual=""):
        return {
            "steps": steps,
            "sub_problems": sub_problems or [],
            "predicted_outcome": predicted,
            "actual_outcome": actual,
        }

    def _step(self, thought, evidence="", confidence=0.7):
        return {"thought": thought, "evidence": evidence, "confidence": confidence}

    def test_empty_sessions(self):
        result = diagnose_sessions([])
        assert result["status"] == "no_data"
        assert len(result["recommendations"]) > 0

    def test_single_good_session(self):
        session = self._make_session(
            steps=[
                self._step("Identified the issue in the auth module.", "Stack trace attached", 0.8),
                self._step("Root cause is expired token validation.", "Code review shows bug", 0.85),
                self._step("Fixed the token check and added regression test.", "Test passes", 0.9),
            ],
            predicted="Fix will resolve auth failures",
            actual="Auth failures resolved",
        )
        result = diagnose_sessions([session])
        assert result["total_sessions"] == 1
        assert result["avg_depth"] == 3

    def test_multiple_sessions_grade_distribution(self):
        good = self._make_session(
            steps=[
                self._step("Deep analysis of the problem.", "Detailed evidence", 0.8),
                self._step("Found the root cause.", "More evidence", 0.85),
                self._step("Implemented a comprehensive fix.", "Test results", 0.9),
                self._step("Verified in staging.", "Monitoring data", 0.95),
            ],
            sub_problems=["diagnose", "fix"],
            predicted="a", actual="a",
        )
        shallow = self._make_session(
            steps=[self._step("Quick look", "", 0.3)],
        )
        result = diagnose_sessions([good, shallow])
        assert result["total_sessions"] == 2
        assert "grade_distribution" in result

    def test_recommendations_generated(self):
        sessions = [
            self._make_session(
                steps=[self._step("Step.", "ev", 0.5)],
                predicted="", actual="result",
            )
            for _ in range(5)
        ]
        result = diagnose_sessions(sessions)
        assert isinstance(result.get("recommendations", []), list)

    def test_calibration_stats(self):
        sessions = [
            self._make_session(
                steps=[self._step("Analysis.", "ev", 0.8)],
                predicted="outcome_a", actual="outcome_a",
            ),
            self._make_session(
                steps=[self._step("Analysis.", "ev", 0.6)],
                predicted="outcome_b", actual="outcome_c",
            ),
        ]
        result = diagnose_sessions(sessions)
        if "calibration" in result:
            cal = result["calibration"]
            assert "brier_score" in cal or "accuracy" in cal


# ── Grade Constants ─────────────────────────────────────────────────

class TestGradeConstants:
    def test_ordering(self):
        assert GRADE_GOOD > GRADE_ADEQUATE > GRADE_SHALLOW

    def test_values(self):
        assert GRADE_GOOD == 0.70
        assert GRADE_ADEQUATE == 0.45
        assert GRADE_SHALLOW == 0.20


# ── classify_episode_failure / ESR exclusion ─────────────────────────

class TestClassifyEpisodeFailure:
    def test_401_status_classified_transient(self):
        assert classify_episode_failure("API Error: 401 unauthorized") == "transient_auth"

    def test_authenticate_keyword(self):
        msg = 'Failed to authenticate. API Error: 401 {"type":"error","error":{"type":"authentication_error"}}'
        assert classify_episode_failure(msg) == "transient_auth"

    def test_invalid_api_key(self):
        assert classify_episode_failure("invalid_api_key returned by upstream") == "transient_auth"

    def test_unauthorized_keyword(self):
        assert classify_episode_failure("HTTP 401 Unauthorized: token expired") == "transient_auth"

    def test_non_auth_failure_returns_none(self):
        assert classify_episode_failure("AssertionError: expected 1 got 2") is None

    def test_empty_input_returns_none(self):
        assert classify_episode_failure(None) is None
        assert classify_episode_failure("") is None

    def test_output_text_also_scanned(self):
        assert classify_episode_failure(
            error_msg="task exited",
            output_text="...\nclaude.api.AuthenticationError: 401\n...",
        ) == "transient_auth"


class TestComputeEpisodeSuccessRate:
    def test_no_failures(self):
        rate = compute_episode_success_rate({"success": 10}, {})
        assert rate == 1.0

    def test_real_failures_count(self):
        rate = compute_episode_success_rate(
            {"success": 8, "failure": 2},
            {"action": 2},
        )
        assert rate == 0.8

    def test_soft_failures_excluded(self):
        # soft_failure outcomes are observational, never count
        rate = compute_episode_success_rate(
            {"success": 8, "soft_failure": 2},
            {},
        )
        assert rate == 1.0

    def test_transient_auth_excluded_from_denominator(self):
        # 8 success + 2 transient_auth → 8/8 = 1.0 (auth doesn't pull ESR down)
        rate = compute_episode_success_rate(
            {"success": 8, "failure": 2},
            {"transient_auth": 2},
        )
        assert rate == 1.0

    def test_transient_can_be_kept_when_disabled(self):
        rate = compute_episode_success_rate(
            {"success": 8, "failure": 2},
            {"transient_auth": 2},
            exclude_transient=False,
        )
        assert rate == 0.8

    def test_constant_membership(self):
        assert "transient_auth" in ESR_EXCLUDED_FAILURE_TYPES


def test_auth_failure_excluded_from_esr():
    """Acceptance test for ESR_AUTH_TRANSIENT_RECLASSIFY.

    A synthetic 401-classified episode injected into an otherwise all-success
    sample must NOT pull the rolling Episode Success Rate below the gate
    (≥0.85). Raw counts in `outcomes`/`failure_types` are preserved for ops
    visibility.
    """
    # Baseline: 17 successes, 0 failures → ESR = 1.0, well above the 0.85 gate
    baseline_outcomes = {"success": 17}
    baseline_failure_types: dict = {}
    baseline_esr = compute_episode_success_rate(baseline_outcomes, baseline_failure_types)
    assert baseline_esr == 1.0

    # Inject a synthetic 401 episode the way EpisodicMemory.encode would:
    # outcome=failure, classified by metacognition as transient_auth.
    err = 'API Error: 401 {"type":"error","error":{"type":"authentication_error"}}'
    assert classify_episode_failure(err) == "transient_auth"

    polluted_outcomes = {"success": 17, "failure": 1}
    polluted_failure_types = {"transient_auth": 1}

    # With exclusion ON (production behaviour): auth episode is removed from
    # the ESR denominator, so the rate stays at 1.0 — matches acceptance
    # criterion that a synthetic 401 does not pull ESR down.
    esr = compute_episode_success_rate(polluted_outcomes, polluted_failure_types)
    assert esr >= 0.85, f"ESR {esr} below 0.85 gate after auth episode"
    assert esr == baseline_esr, "transient_auth should not affect ESR"

    # With exclusion OFF (legacy behaviour): the failure does pull ESR down,
    # confirming the exclusion is the mechanism, not a coincidence.
    legacy_esr = compute_episode_success_rate(
        polluted_outcomes, polluted_failure_types, exclude_transient=False,
    )
    assert legacy_esr < baseline_esr

    # Raw counts preserved (ops visibility): the dicts the helper consumes
    # are untouched by the call.
    assert polluted_outcomes == {"success": 17, "failure": 1}
    assert polluted_failure_types == {"transient_auth": 1}


def test_encode_overrides_upstream_external_dep_to_transient_auth(tmp_path, monkeypatch):
    """Postflight's error_classifier matches a 401 as `external_dep` (3+ keyword
    hits: "401" + "api error" + "authentication_error"). Without the override,
    `EpisodicMemory.encode(failure_type="external_dep")` would persist
    "external_dep" and the auth episode would still pull ESR down.

    This test pins the override: when the error_msg matches the metacognitive
    transient_auth pattern, encode() must promote the failure_type to
    "transient_auth" regardless of the upstream classification.
    """
    import clarvis.memory.episodic_memory as em

    monkeypatch.setattr(em, "EPISODES_FILE", tmp_path / "episodes.json")
    monkeypatch.setattr(em, "CAUSAL_LINKS_FILE", tmp_path / "causal_links.json")

    memory = em.EpisodicMemory()
    err = 'API Error: 401 {"type":"error","error":{"type":"authentication_error"}}'
    memory.encode(
        task_text="some task",
        section="P1",
        salience=0.5,
        outcome="failure",
        duration_s=12.0,
        error_msg=err,
        failure_type="external_dep",  # what postflight would pass for a 401
        output_text=err,
    )

    assert memory.episodes, "encode should append an episode"
    assert memory.episodes[-1]["failure_type"] == "transient_auth"
