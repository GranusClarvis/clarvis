"""Tests for CLR Outcome Ablation Harness v3."""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Ensure workspace scripts are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import _paths  # noqa: F401,E402
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestTaskCoverage(unittest.TestCase):
    """Verify task set diversity and completeness."""

    def test_at_least_20_tasks(self):
        from clarvis.metrics.ablation_v3 import ALL_TASKS
        self.assertGreaterEqual(len(ALL_TASKS), 20,
                                "v3 requires 20+ diverse test tasks")

    def test_exactly_24_tasks(self):
        from clarvis.metrics.ablation_v3 import ALL_TASKS
        self.assertEqual(len(ALL_TASKS), 24)

    def test_six_categories(self):
        from clarvis.metrics.ablation_v3 import TASK_CATEGORIES
        self.assertEqual(len(TASK_CATEGORIES), 6)

    def test_four_tasks_per_category(self):
        from clarvis.metrics.ablation_v3 import TASK_CATEGORIES
        for cat, tasks in TASK_CATEGORIES.items():
            self.assertEqual(len(tasks), 4, f"Category {cat} should have 4 tasks")

    def test_all_tasks_have_category(self):
        from clarvis.metrics.ablation_v3 import ALL_TASKS
        for t in ALL_TASKS:
            self.assertIn("task", t)
            self.assertIn("category", t)
            self.assertTrue(len(t["task"]) > 20, "Tasks should be descriptive")

    def test_no_duplicate_tasks(self):
        from clarvis.metrics.ablation_v3 import ALL_TASKS
        task_texts = [t["task"] for t in ALL_TASKS]
        self.assertEqual(len(task_texts), len(set(task_texts)), "No duplicate tasks")


class TestDeterministicScoring(unittest.TestCase):
    """Test offline deterministic scoring logic."""

    def test_empty_brief_scores_zero(self):
        from clarvis.metrics.ablation_v3 import _score_brief_deterministic
        self.assertEqual(_score_brief_deterministic("", "some task"), 0.0)

    def test_error_brief_scores_zero(self):
        from clarvis.metrics.ablation_v3 import _score_brief_deterministic
        self.assertEqual(
            _score_brief_deterministic("[ASSEMBLY ERROR: oops]", "task"), 0.0
        )

    def test_rich_brief_scores_higher(self):
        from clarvis.metrics.ablation_v3 import _score_brief_deterministic

        sparse_brief = "Some context about the task."
        rich_brief = (
            "## EPISODIC RECALL\nPast task: similar fix applied in episode-42.\n"
            "## BRAIN CONTEXT\nKNOWLEDGE: ChromaDB uses ONNX embeddings.\n"
            "## REASONING APPROACH\nStep 1: Identify root cause. Step 2: Fix. "
            "Step 3: Verify.\n"
            "## SUCCESS CRITERIA\nMust avoid breaking existing episode format.\n"
            "## FAILURE patterns\nPrevious attempt failed due to missing constraint.\n"
            "## WORKING MEMORY SPOTLIGHT\nRecent change to postflight encoding.\n"
            "This task involves ChromaDB connection retry with exponential backoff. "
            "Ensure the retry decorator handles transient errors properly."
        )
        task = "Add a retry decorator with exponential backoff to brain search"

        sparse_score = _score_brief_deterministic(sparse_brief, task)
        rich_score = _score_brief_deterministic(rich_brief, task)

        self.assertGreater(rich_score, sparse_score,
                           "Rich brief should score higher than sparse")
        self.assertGreater(rich_score, 0.5, "Rich brief should score above 0.5")

    def test_score_in_range(self):
        from clarvis.metrics.ablation_v3 import _score_brief_deterministic
        score = _score_brief_deterministic("Some reasonable context brief.", "a task")
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


class TestJudgeResponseParsing(unittest.TestCase):
    """Test LLM judge response parsing edge cases."""

    @patch("clarvis.metrics.ablation_v3._get_api_key")
    def test_no_api_key_returns_tie(self, mock_key):
        from clarvis.metrics.ablation_v3 import _call_judge
        mock_key.return_value = None
        result = _call_judge("task", "brief a", "brief b")
        self.assertEqual(result["winner"], "TIE")
        self.assertIn("error", result)


class TestUniformityAnalysis(unittest.TestCase):
    """Test uniformity pattern detection."""

    def test_uniform_when_all_neutral(self):
        from clarvis.metrics.ablation_v3 import _analyze_uniformity

        rankings = [
            {"module": "m1", "net_score": 0.01, "verdict": "NEUTRAL",
             "category_deltas": {"c1": 0.0, "c2": 0.0}},
            {"module": "m2", "net_score": 0.02, "verdict": "NEUTRAL",
             "category_deltas": {"c1": 0.0, "c2": 0.0}},
        ]
        result = _analyze_uniformity(rankings)
        self.assertEqual(result["pattern"], "FLAT_NEUTRAL")

    def test_non_uniform_with_variance(self):
        from clarvis.metrics.ablation_v3 import _analyze_uniformity

        rankings = [
            {"module": "m1", "net_score": 0.3, "verdict": "CRITICAL",
             "category_deltas": {"c1": 0.5, "c2": -0.1}},
            {"module": "m2", "net_score": -0.1, "verdict": "HARMFUL",
             "category_deltas": {"c1": -0.2, "c2": 0.3}},
        ]
        result = _analyze_uniformity(rankings)
        self.assertEqual(result["pattern"], "NON_UNIFORM")

    def test_specializations_detected(self):
        from clarvis.metrics.ablation_v3 import _analyze_uniformity

        rankings = [
            {"module": "episodic_recall", "net_score": 0.2, "verdict": "CRITICAL",
             "category_deltas": {"debugging": 0.5, "code_implementation": 0.0}},
        ]
        result = _analyze_uniformity(rankings)
        specs = result["specializations"]
        self.assertTrue(len(specs) >= 1)
        self.assertEqual(specs[0]["module"], "episodic_recall")
        self.assertEqual(specs[0]["category"], "debugging")


class TestDryRun(unittest.TestCase):
    """Test dry-run mode doesn't execute anything."""

    def test_dry_run_returns_plan(self):
        from clarvis.metrics.ablation_v3 import run_ablation_v3
        result = run_ablation_v3(dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["tasks"], 24)


class TestResultPersistence(unittest.TestCase):
    """Test save/load cycle."""

    def test_save_and_load(self):
        from clarvis.metrics.ablation_v3 import _save_results, RESULTS_FILE

        with tempfile.TemporaryDirectory() as tmpdir:
            test_results = os.path.join(tmpdir, "results.json")
            test_history = os.path.join(tmpdir, "history.jsonl")

            # Patch file paths
            import clarvis.metrics.ablation_v3 as mod
            orig_rf = mod.RESULTS_FILE
            orig_hf = mod.HISTORY_FILE
            mod.RESULTS_FILE = test_results
            mod.HISTORY_FILE = test_history

            try:
                result = {
                    "timestamp": "2026-04-02T00:00:00",
                    "schema_version": "3.0",
                    "mode": "offline",
                    "task_count": 24,
                    "rankings": [
                        {"module": "test", "net_score": 0.1, "verdict": "HELPFUL",
                         "win_rate": 0.6}
                    ],
                    "uniformity_analysis": {"pattern": "NON_UNIFORM"},
                    "total_duration_s": 10.0,
                }
                _save_results(result)

                self.assertTrue(os.path.exists(test_results))
                with open(test_results) as f:
                    loaded = json.load(f)
                self.assertEqual(loaded["schema_version"], "3.0")

                self.assertTrue(os.path.exists(test_history))
                with open(test_history) as f:
                    lines = f.readlines()
                self.assertEqual(len(lines), 1)
                entry = json.loads(lines[0])
                self.assertEqual(entry["uniformity_pattern"], "NON_UNIFORM")
            finally:
                mod.RESULTS_FILE = orig_rf
                mod.HISTORY_FILE = orig_hf


if __name__ == "__main__":
    unittest.main()
