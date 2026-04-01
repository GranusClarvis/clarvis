"""Tests for clarvis.metrics.cot_evaluator — chain-of-thought self-evaluation."""

import json
import os
import tempfile
from pathlib import Path

import pytest

# Ensure cot_evaluator uses a temp workspace for tests
_tmp = tempfile.mkdtemp()
os.environ.setdefault("CLARVIS_WORKSPACE", _tmp)

from clarvis.metrics.cot_evaluator import (
    _compute_step_coherence,
    _detect_backtracking,
    _extract_key_terms,
    _measure_conclusion_support,
    _score_backtracking,
    _score_depth,
    evaluate_cot,
    evaluate_recent,
    record_cot_score,
    score_episode_cot,
    summarize_cot,
)


# --- Depth scoring ---

class TestScoreDepth:
    def test_zero_steps(self):
        assert _score_depth(0) == 0.0

    def test_single_step(self):
        assert _score_depth(1) == 0.2

    def test_two_steps(self):
        assert _score_depth(2) == 0.5

    def test_mid_range(self):
        assert _score_depth(3) == 0.75
        assert _score_depth(4) == 0.75

    def test_high_range(self):
        assert _score_depth(5) == 0.9
        assert _score_depth(7) == 0.9

    def test_deep_chain(self):
        assert _score_depth(8) == 1.0
        assert _score_depth(15) == 1.0


# --- Backtracking detection ---

class TestDetectBacktracking:
    def test_no_backtracking(self):
        steps = [
            {"thought": "First I will analyze the requirements"},
            {"thought": "The data model needs three tables"},
        ]
        bt = _detect_backtracking(steps)
        assert bt["backtrack_count"] == 0
        assert bt["correction_count"] == 0
        assert bt["has_self_correction"] is False

    def test_backtracking_detected(self):
        steps = [
            {"thought": "I'll use a simple array"},
            {"thought": "Actually, wait — a hash map is better for O(1) lookup"},
            {"thought": "The hash map approach works well"},
        ]
        bt = _detect_backtracking(steps)
        assert bt["backtrack_count"] >= 1
        assert len(bt["backtrack_steps"]) >= 1

    def test_correction_detected(self):
        steps = [
            {"thought": "The previous approach was incorrect"},
            {"thought": "Fixed the algorithm to handle edge cases"},
        ]
        bt = _detect_backtracking(steps)
        assert bt["correction_count"] >= 1
        assert bt["has_self_correction"] is True

    def test_empty_steps(self):
        bt = _detect_backtracking([])
        assert bt["backtrack_count"] == 0


# --- Backtracking scoring ---

class TestScoreBacktracking:
    def test_short_chain_no_bt(self):
        bt = {"backtrack_count": 0, "has_self_correction": False}
        assert _score_backtracking(bt, 1) == 0.5  # too short

    def test_long_chain_no_bt_suspicious(self):
        bt = {"backtrack_count": 0, "has_self_correction": False}
        assert _score_backtracking(bt, 6) == 0.6  # suspicious

    def test_healthy_self_correction(self):
        bt = {"backtrack_count": 1, "has_self_correction": True}
        assert _score_backtracking(bt, 5) == 1.0  # ratio=0.2 ≤ 0.3

    def test_excessive_thrashing(self):
        bt = {"backtrack_count": 4, "has_self_correction": True}
        score = _score_backtracking(bt, 5)
        assert score <= 0.5  # ratio=0.8 — too much

    def test_bt_without_correction(self):
        bt = {"backtrack_count": 1, "has_self_correction": False}
        score = _score_backtracking(bt, 5)
        assert 0.5 <= score <= 0.8


# --- Key term extraction ---

class TestExtractKeyTerms:
    def test_filters_stop_words(self):
        terms = _extract_key_terms("the quick brown fox jumps over the lazy dog")
        assert "the" not in terms
        # "over" is 4 chars and not in stop list — that's fine
        assert "quick" in terms
        assert "brown" in terms
        assert "jumps" in terms

    def test_min_length(self):
        terms = _extract_key_terms("a ab abc abcd abcde", min_len=4)
        assert "abc" not in terms
        assert "abcd" in terms

    def test_empty_text(self):
        assert _extract_key_terms("") == set()


# --- Conclusion support ---

class TestConclusionSupport:
    def test_no_steps(self):
        assert _measure_conclusion_support([], None, None) == 0.0

    def test_well_supported(self):
        steps = [
            {"thought": "The database schema requires indexing on user_id column"},
            {"thought": "Adding composite index on user_id and created_at improves query performance"},
        ]
        score = _measure_conclusion_support(
            steps, "success", "Database indexing on user_id and created_at improved performance"
        )
        assert score > 0.5  # High overlap between reasoning and conclusion

    def test_unsupported_conclusion(self):
        steps = [
            {"thought": "The frontend layout uses flexbox for alignment"},
        ]
        score = _measure_conclusion_support(
            steps, "success", "Completely unrelated database migration was successful"
        )
        # Some overlap from shared terms like "layout"/"successful" — just verify it's not max
        assert score < 1.0

    def test_no_conclusion(self):
        steps = [{"thought": "Analysis complete"}]
        # No outcome or summary — should handle gracefully
        score = _measure_conclusion_support(steps, None, None)
        assert 0.0 <= score <= 1.0


# --- Step coherence ---

class TestStepCoherence:
    def test_single_step(self):
        assert _compute_step_coherence([{"thought": "one"}]) == 0.5

    def test_coherent_chain(self):
        steps = [
            {"thought": "analyze the authentication module security"},
            {"thought": "the authentication module has a vulnerability in token validation"},
            {"thought": "fix the token validation to check expiration properly"},
        ]
        score = _compute_step_coherence(steps)
        assert 0.3 <= score <= 1.0  # Moderate overlap = coherent

    def test_empty_steps(self):
        assert _compute_step_coherence([]) == 0.5


# --- Main evaluator ---

class TestEvaluateCot:
    def test_empty_chain(self):
        result = evaluate_cot(chain_data={"steps": [], "title": "test"})
        assert result["num_steps"] == 0
        assert result["cot_score"] < 0.35  # poor grade threshold
        assert result["cot_grade"] == "poor"

    def test_single_step_chain(self):
        chain = {
            "title": "Simple task",
            "steps": [{"thought": "Just do it", "step": 0}],
            "outcome": "success",
        }
        result = evaluate_cot(chain_data=chain)
        assert result["num_steps"] == 1
        assert result["cot_score"] > 0.0
        assert "single_step_only" in result["issues"]

    def test_rich_session(self):
        session = {
            "task": "Implement user authentication",
            "steps": [
                {
                    "step_num": 0,
                    "thought": "First analyze the existing authentication infrastructure",
                    "evidence": ["auth.py exists", "no token validation"],
                    "confidence": 0.8,
                },
                {
                    "step_num": 1,
                    "thought": "Design token-based authentication with JWT validation",
                    "evidence": ["JWT is industry standard", "existing endpoints need auth headers"],
                    "confidence": 0.85,
                },
                {
                    "step_num": 2,
                    "thought": "Actually, wait — OAuth2 would be more appropriate for this use case",
                    "evidence": ["multiple third-party integrations need OAuth"],
                    "confidence": 0.9,
                },
                {
                    "step_num": 3,
                    "thought": "Implemented OAuth2 authentication with token refresh",
                    "evidence": ["tests passing", "integration verified"],
                    "confidence": 0.95,
                },
            ],
            "actual_outcome": "success",
            "summary": "Implemented OAuth2 authentication with token refresh for all endpoints",
        }
        result = evaluate_cot(session_data=session)
        assert result["num_steps"] == 4
        assert result["cot_score"] >= 0.5  # Should be at least adequate
        assert result["cot_grade"] in ("strong", "adequate")
        assert result["backtracking_detail"]["count"] >= 1  # "wait" detected
        assert result["components"]["evidence_density"] > 0.5  # All steps have evidence

    def test_session_preferred_over_chain(self):
        chain = {"steps": [{"thought": "a"}], "title": "test"}
        session = {
            "steps": [
                {"thought": "analysis step one", "step_num": 0},
                {"thought": "design step two", "step_num": 1},
            ],
            "task": "test",
        }
        result = evaluate_cot(chain_data=chain, session_data=session)
        assert result["num_steps"] == 2  # Session steps preferred (more)

    def test_from_file(self, tmp_path):
        chain_file = tmp_path / "chain_test.json"
        chain_file.write_text(json.dumps({
            "title": "File test",
            "steps": [
                {"thought": "Step one analysis", "step": 0},
                {"thought": "Step two implementation", "step": 1},
            ],
            "outcome": "success",
        }))
        result = evaluate_cot(chain_path=chain_file)
        assert result["num_steps"] == 2

    def test_components_present(self):
        chain = {
            "steps": [{"thought": "think"}, {"thought": "more thinking"}],
            "title": "t",
        }
        result = evaluate_cot(chain_data=chain)
        assert "depth" in result["components"]
        assert "backtracking" in result["components"]
        assert "conclusion_support" in result["components"]
        assert "evidence_density" in result["components"]
        assert "coherence" in result["components"]

    def test_score_bounded(self):
        chain = {"steps": [{"thought": f"step {i}"} for i in range(20)], "title": "t"}
        result = evaluate_cot(chain_data=chain)
        assert 0.0 <= result["cot_score"] <= 1.0

    def test_issues_detected(self):
        chain = {
            "steps": [{"thought": "x"}],  # single step, no evidence
            "title": "t",
            "outcome": "completely unrelated outcome text about quantum physics",
        }
        result = evaluate_cot(chain_data=chain)
        assert "single_step_only" in result["issues"]
        assert "low_evidence" in result["issues"]


# --- score_episode_cot ---

class TestScoreEpisodeCot:
    def test_by_chain_id_file(self, tmp_path, monkeypatch):
        import clarvis.metrics.cot_evaluator as mod
        monkeypatch.setattr(mod, "CHAINS_DIR", tmp_path)
        monkeypatch.setattr(mod, "SESSION_MAP", tmp_path / "session_map.json")
        monkeypatch.setattr(mod, "SESSIONS_DIR", tmp_path / "sessions")

        chain_file = tmp_path / "chain_test123.json"
        chain_file.write_text(json.dumps({
            "title": "Test chain",
            "steps": [
                {"thought": "Analysis of the problem space", "step": 0},
                {"thought": "Implementation approach selected", "step": 1},
                {"thought": "Verification of the solution", "step": 2},
            ],
            "outcome": "success",
        }))
        result = score_episode_cot(chain_id="chain_test123")
        assert result["num_steps"] == 3


# --- record_cot_score ---

class TestRecordCotScore:
    def test_appends_to_history(self, tmp_path, monkeypatch):
        import clarvis.metrics.cot_evaluator as mod
        history_file = tmp_path / "cot_history.jsonl"
        monkeypatch.setattr(mod, "COT_HISTORY", history_file)

        result = {"cot_score": 0.75, "cot_grade": "strong", "num_steps": 4}
        payload = record_cot_score(result)
        assert "ts" in payload

        lines = history_file.read_text().strip().split("\n")
        assert len(lines) == 1
        assert json.loads(lines[0])["cot_score"] == 0.75


# --- summarize_cot ---

class TestSummarizeCot:
    def test_empty(self):
        s = summarize_cot([])
        assert s["episodes"] == 0
        assert s["avg_cot_score"] is None

    def test_basic_summary(self):
        results = [
            {"cot_score": 0.8, "cot_grade": "strong", "components": {
                "depth": 0.9, "backtracking": 0.7, "conclusion_support": 0.8,
                "evidence_density": 0.6, "coherence": 0.7,
            }, "issues": ["low_evidence"]},
            {"cot_score": 0.5, "cot_grade": "adequate", "components": {
                "depth": 0.5, "backtracking": 0.5, "conclusion_support": 0.5,
                "evidence_density": 0.3, "coherence": 0.5,
            }, "issues": ["low_evidence", "single_step_only"]},
        ]
        s = summarize_cot(results)
        assert s["episodes"] == 2
        assert s["avg_cot_score"] == 0.65
        assert s["grade_distribution"]["strong"] == 1
        assert s["grade_distribution"]["adequate"] == 1
        assert s["common_issues"]["low_evidence"] == 2
