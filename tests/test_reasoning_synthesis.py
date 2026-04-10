"""Tests for reasoning synthesis loop and deliberate practice."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from clarvis.cognition.reasoning import ClarvisReasoner, ReasoningSession


@pytest.fixture
def tmp_reasoning(tmp_path):
    """Create a reasoning engine with temporary data directory."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    with patch("clarvis.cognition.reasoning.SESSIONS_DIR", sessions_dir), \
         patch("clarvis.cognition.reasoning.DATA_DIR", tmp_path), \
         patch("clarvis.cognition.reasoning.META_FILE", tmp_path / "reasoning_meta.json"):
        r = ClarvisReasoner()
        yield r, sessions_dir


def _make_completed_session(reasoner, task, steps, outcome="success"):
    """Helper to create a completed session with given steps."""
    session = reasoner.begin(task)
    for s in steps:
        session.step(
            thought=s.get("thought", "test thought"),
            sub_problem=s.get("sub_problem", ""),
            evidence=s.get("evidence", ["test evidence"]),
            confidence=s.get("confidence", 0.7),
        )
    session.predict("success", 0.8)
    session.complete(outcome, f"Completed: {task}")
    return session


class TestSynthesizeLoop:
    def test_insufficient_data(self, tmp_reasoning):
        r, _ = tmp_reasoning
        report = r.synthesize()
        assert report["status"] == "insufficient_data"

    def test_basic_synthesis(self, tmp_reasoning):
        r, _ = tmp_reasoning
        # Create 5 completed sessions
        for i in range(5):
            _make_completed_session(
                r, f"task_{i}",
                [{"thought": f"Analyze problem {i}", "evidence": ["fact A"]},
                 {"thought": f"Design solution {i}", "evidence": ["reference B"]},
                 {"thought": f"Implement solution {i}", "evidence": ["test result"]}],
                outcome="success" if i < 4 else "failure",
            )

        report = r.synthesize()
        assert report["status"] == "analyzed"
        assert report["sessions_analyzed"] == 5
        assert report["success_rate"] == 0.8
        assert report["depth"]["avg"] == 3.0
        assert report["calibration"]["total_predictions"] == 5

    def test_synthesis_detects_shallow(self, tmp_reasoning):
        r, _ = tmp_reasoning
        # All shallow 2-step sessions
        for i in range(5):
            _make_completed_session(
                r, f"shallow_{i}",
                [{"thought": f"Quick thought {i}", "evidence": ["e"]},
                 {"thought": f"Done {i}", "evidence": ["e"]}],
            )

        report = r.synthesize()
        assert report["depth"]["max"] <= 2
        # Should generate insight about shallow chains
        assert any("shallow" in ins.lower() or "deep" in ins.lower()
                   for ins in report.get("insights", []))

    def test_synthesis_persists_report(self, tmp_reasoning):
        r, _ = tmp_reasoning
        for i in range(4):
            _make_completed_session(r, f"t{i}",
                [{"thought": "a", "evidence": ["e"]},
                 {"thought": "b", "evidence": ["e"]},
                 {"thought": "c", "evidence": ["e"]}])

        report = r.synthesize()
        # Check that synthesis_report.json was written
        synth_file = Path(str(_.parent)) / "synthesis_report.json"
        # The file should exist in DATA_DIR which is tmp_path
        from clarvis.cognition import reasoning
        actual_file = Path(str(reasoning.DATA_DIR)) / "synthesis_report.json"
        assert actual_file.exists()
        saved = json.loads(actual_file.read_text())
        assert saved["sessions_analyzed"] == report["sessions_analyzed"]


class TestDeliberatePractice:
    def test_basic_practice_session(self, tmp_reasoning):
        r, _ = tmp_reasoning
        session = r.deliberate_practice(
            problem="Test problem",
            sub_problems=["Part A", "Part B"],
            solutions=[
                {"sub_problem": "Part A", "thought": "Solution for A with details",
                 "evidence": ["fact 1", "fact 2"], "confidence": 0.8},
                {"sub_problem": "Part B", "thought": "Solution for B with more details",
                 "evidence": ["fact 3"], "confidence": 0.75},
            ],
        )

        assert len(session.steps) >= 3  # decompose + 2 solutions
        assert session.sub_problems == ["Part A", "Part B"]
        assert session.predicted_outcome == "success"
        assert not session.completed  # not completed yet

    def test_practice_produces_deep_chain(self, tmp_reasoning):
        r, _ = tmp_reasoning
        session = r.deliberate_practice(
            problem="Complex problem",
            sub_problems=["A", "B", "C", "D"],
            solutions=[
                {"sub_problem": "A", "thought": "Analysis of sub-problem A in depth",
                 "evidence": ["ref1"], "confidence": 0.8},
                {"sub_problem": "B", "thought": "Design approach for B considering constraints",
                 "evidence": ["ref2", "ref3"], "confidence": 0.75},
                {"sub_problem": "C", "thought": "Implementation of C using pattern X",
                 "evidence": ["ref4"], "confidence": 0.85},
                {"sub_problem": "D", "thought": "Verification of D against requirements",
                 "evidence": ["ref5"], "confidence": 0.9},
            ],
        )
        session.complete("success", "All sub-problems solved")

        ev = session.evaluate()
        assert ev["depth"] >= 4
        assert ev["quality_grade"] in ("good", "adequate")
        assert ev["evidence_coverage"] == 1.0

    def test_practice_session_evaluates_well(self, tmp_reasoning):
        r, _ = tmp_reasoning
        session = r.deliberate_practice(
            problem="Hard problem",
            sub_problems=["Design", "Implement", "Test"],
            solutions=[
                {"sub_problem": "Design", "thought": "Architectural design with trade-off analysis",
                 "evidence": ["prior art", "benchmark data"], "confidence": 0.85},
                {"sub_problem": "Implement", "thought": "Core implementation following the design",
                 "evidence": ["type safety", "test coverage"], "confidence": 0.8},
                {"sub_problem": "Test", "thought": "Comprehensive testing strategy with edge cases",
                 "evidence": ["50 test cases", "property-based tests"], "confidence": 0.9},
            ],
        )
        session.complete("success", "Done")

        ev = session.evaluate()
        assert ev["quality_score"] > 0.6
        assert ev["sub_problem_coverage"] == 1.0


class TestThompsonNFA:
    """Smoke test that the Thompson NFA challenge implementation works."""

    def test_import_and_basic_match(self):
        import sys
        sys.path.insert(0, "scripts/challenges")
        from thompson_nfa import match
        assert match("abc", "abc")
        assert not match("abc", "abd")
        assert match("a*", "aaa")
        assert match("[a-z]+", "hello")
        sys.path.pop(0)
