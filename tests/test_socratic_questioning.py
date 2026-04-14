"""Tests for Socratic self-questioning in reasoning chains."""

import json
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))

from clarvis.cognition.reasoning_chains import (
    _generate_socratic_question,
    _detect_weakness,
    _DEFAULT_QUESTION,
    REASONING_DIR,
    create_chain,
    add_step,
    get_chain,
)


class TestSocraticQuestionGeneration(unittest.TestCase):
    def test_assumption_trigger(self):
        q = _generate_socratic_question("We assume the database is always available")
        assert "assumption" in q.lower() or "evidence" in q.lower()

    def test_causation_trigger(self):
        q = _generate_socratic_question("Performance dropped because of the new index")
        assert "cause" in q.lower() or "correlation" in q.lower()

    def test_generalization_trigger(self):
        q = _generate_socratic_question("All cron jobs always succeed")
        assert "always" in q.lower() or "exceptions" in q.lower()

    def test_certainty_trigger(self):
        q = _generate_socratic_question("This is clearly the correct fix")
        assert "change our mind" in q.lower() or "counter" in q.lower()

    def test_should_trigger(self):
        q = _generate_socratic_question("We should refactor the entire module")
        assert "opposite" in q.lower() or "trade-off" in q.lower()

    def test_complexity_trigger(self):
        q = _generate_socratic_question("This is a simple change with no side effects")
        assert "oversimplif" in q.lower() or "complexity" in q.lower()

    def test_default_question(self):
        q = _generate_socratic_question("Proceed with step two of the plan")
        assert q == _DEFAULT_QUESTION


class TestWeaknessDetection(unittest.TestCase):
    def test_weakness_detected(self):
        result = _detect_weakness(
            "This might work but the approach is fragile",
            "What could go wrong?"
        )
        assert result is not None
        assert "Weakness detected" in result

    def test_no_weakness(self):
        result = _detect_weakness(
            "The implementation follows the established pattern",
            "What could go wrong?"
        )
        assert result is None


class TestAddStepSocratic(unittest.TestCase):
    @patch("clarvis.cognition.reasoning_chains.brain")
    def test_add_step_includes_socratic_question(self, mock_brain):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("clarvis.cognition.reasoning_chains.REASONING_DIR", type(REASONING_DIR)(tmpdir)):
                chain_id = "chain_test_socratic"
                chain_file = type(REASONING_DIR)(tmpdir) / f"{chain_id}.json"
                chain_file.write_text(json.dumps({
                    "id": chain_id,
                    "title": "Test Chain",
                    "created": "2026-04-14T00:00:00",
                    "steps": [{"step": 0, "thought": "init", "timestamp": "2026-04-14T00:00:00", "outcome": None}]
                }))

                step_num = add_step(chain_id, "We assume the cache is always warm")
                assert step_num == 1

                chain = json.loads(chain_file.read_text())
                step = chain["steps"][1]
                assert "socratic_question" in step
                assert len(step["socratic_question"]) > 10

    @patch("clarvis.cognition.reasoning_chains.brain")
    def test_add_step_socratic_disabled(self, mock_brain):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("clarvis.cognition.reasoning_chains.REASONING_DIR", type(REASONING_DIR)(tmpdir)):
                chain_id = "chain_test_nosocratic"
                chain_file = type(REASONING_DIR)(tmpdir) / f"{chain_id}.json"
                chain_file.write_text(json.dumps({
                    "id": chain_id,
                    "title": "Test Chain",
                    "created": "2026-04-14T00:00:00",
                    "steps": [{"step": 0, "thought": "init", "timestamp": "2026-04-14T00:00:00", "outcome": None}]
                }))

                add_step(chain_id, "Some thought", socratic=False)
                chain = json.loads(chain_file.read_text())
                assert "socratic_question" not in chain["steps"][1]

    @patch("clarvis.cognition.reasoning_chains.brain")
    def test_add_step_with_weakness_gets_refinement(self, mock_brain):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("clarvis.cognition.reasoning_chains.REASONING_DIR", type(REASONING_DIR)(tmpdir)):
                chain_id = "chain_test_weakness"
                chain_file = type(REASONING_DIR)(tmpdir) / f"{chain_id}.json"
                chain_file.write_text(json.dumps({
                    "id": chain_id,
                    "title": "Test Chain",
                    "created": "2026-04-14T00:00:00",
                    "steps": [{"step": 0, "thought": "init", "timestamp": "2026-04-14T00:00:00", "outcome": None}]
                }))

                add_step(chain_id, "This might work but it's a fragile hack")
                chain = json.loads(chain_file.read_text())
                step = chain["steps"][1]
                assert "socratic_refinement" in step
                assert "Weakness detected" in step["socratic_refinement"]


if __name__ == "__main__":
    unittest.main()
