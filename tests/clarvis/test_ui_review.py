"""Tests for the 7-axis UI review rubric (clarvis.cognition.ui_review)."""

import json
import tempfile
import unittest
from pathlib import Path

from clarvis.cognition.ui_review import (
    AXES,
    AXIS_BY_ID,
    PASSING_MIN_AXIS,
    PASSING_OVERALL,
    RUBRIC_VERSION,
    render_card,
    review_ui_artifact,
    schema,
)


class TestRubricShape(unittest.TestCase):
    def test_seven_axes_exact(self):
        self.assertEqual(len(AXES), 7)
        ids = [a.axis_id for a in AXES]
        self.assertEqual(
            set(ids),
            {
                "visual_hierarchy",
                "thumb_zone_cta",
                "color_contrast",
                "type_rhythm",
                "whitespace_breathing",
                "brand_consistency",
                "accessibility_surface",
            },
        )
        # No duplicate ids.
        self.assertEqual(len(ids), len(set(ids)))

    def test_axes_carry_rule_and_needs(self):
        for spec in AXES:
            self.assertTrue(spec.rule)
            self.assertTrue(spec.needs)
            self.assertGreater(spec.weight, 0)

    def test_schema_round_trip(self):
        s = schema()
        self.assertEqual(s["rubric_version"], RUBRIC_VERSION)
        self.assertEqual(len(s["axes"]), 7)
        json.dumps(s)  # must be JSON-serialisable


class TestReviewWithoutEvidence(unittest.TestCase):
    def test_missing_sidecar_marks_all_needs_review(self):
        with tempfile.TemporaryDirectory() as td:
            shot = Path(td) / "shot.png"
            plan = Path(td) / "ux.md"
            review = review_ui_artifact(str(shot), str(plan))
        self.assertEqual(review["scored_count"], 0)
        self.assertEqual(len(review["needs_review"]), 7)
        self.assertEqual(review["overall"], 0.0)
        self.assertFalse(review["passing"])
        for axis_id, axis in review["axes"].items():
            self.assertEqual(axis["score"], 0)
            self.assertIn("needs_review", axis["evidence"])


class TestReviewWithSidecar(unittest.TestCase):
    def _write_sidecar(self, shot: Path, payload: dict) -> None:
        Path(str(shot) + ".evidence.json").write_text(json.dumps(payload))

    def test_partial_evidence_scores_subset_only(self):
        with tempfile.TemporaryDirectory() as td:
            shot = Path(td) / "shot.png"
            plan = Path(td) / "ux.md"
            self._write_sidecar(
                shot,
                {
                    "visual_hierarchy": {"score": 4, "evidence": "Title 1.5rem, single CTA"},
                    "color_contrast": {"score": 5, "evidence": "0/22 axe violations"},
                },
            )
            review = review_ui_artifact(str(shot), str(plan))
        self.assertEqual(review["scored_count"], 2)
        self.assertEqual(len(review["needs_review"]), 5)
        self.assertEqual(review["axes"]["visual_hierarchy"]["score"], 4)
        self.assertEqual(review["axes"]["color_contrast"]["score"], 5)
        # Overall should be the weighted mean of the *scored* axes only.
        # weights: vh=1.5, cc=1.25 -> (4*1.5 + 5*1.25)/(1.5+1.25) = 12.25/2.75 ≈ 4.45
        self.assertAlmostEqual(review["overall"], 4.45, places=2)
        # Not passing: only 2/7 axes scored.
        self.assertFalse(review["passing"])

    def test_full_evidence_pass_path(self):
        with tempfile.TemporaryDirectory() as td:
            shot = Path(td) / "shot.png"
            plan = Path(td) / "ux.md"
            self._write_sidecar(
                shot,
                {axis.axis_id: {"score": 4, "evidence": "ok"} for axis in AXES},
            )
            review = review_ui_artifact(str(shot), str(plan))
        self.assertEqual(review["scored_count"], 7)
        self.assertEqual(review["needs_review"], [])
        self.assertEqual(review["overall"], 4.0)
        self.assertTrue(review["passing"])

    def test_one_axis_below_min_blocks_pass(self):
        with tempfile.TemporaryDirectory() as td:
            shot = Path(td) / "shot.png"
            plan = Path(td) / "ux.md"
            scores = {axis.axis_id: {"score": 5, "evidence": "ok"} for axis in AXES}
            scores["accessibility_surface"] = {"score": 2, "evidence": "no focus rings"}
            self._write_sidecar(shot, scores)
            review = review_ui_artifact(str(shot), str(plan))
        # Overall is high but a single axis below PASSING_MIN_AXIS blocks pass.
        self.assertGreaterEqual(review["overall"], PASSING_OVERALL)
        self.assertFalse(review["passing"])

    def test_overrides_replace_sidecar(self):
        with tempfile.TemporaryDirectory() as td:
            shot = Path(td) / "shot.png"
            plan = Path(td) / "ux.md"
            self._write_sidecar(
                shot,
                {"visual_hierarchy": {"score": 1, "evidence": "from sidecar"}},
            )
            review = review_ui_artifact(
                str(shot),
                str(plan),
                evidence_overrides={
                    "visual_hierarchy": {"score": 5, "evidence": "from override"},
                },
            )
        self.assertEqual(review["axes"]["visual_hierarchy"]["score"], 5)
        self.assertEqual(review["axes"]["visual_hierarchy"]["evidence"], "from override")

    def test_invalid_axis_id_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            shot = Path(td) / "shot.png"
            plan = Path(td) / "ux.md"
            self._write_sidecar(
                shot,
                {"made_up_axis": {"score": 5, "evidence": "x"}},
            )
            review = review_ui_artifact(str(shot), str(plan))
        self.assertEqual(review["scored_count"], 0)

    def test_score_clamped_to_range(self):
        with tempfile.TemporaryDirectory() as td:
            shot = Path(td) / "shot.png"
            plan = Path(td) / "ux.md"
            self._write_sidecar(
                shot,
                {
                    "visual_hierarchy": {"score": 99, "evidence": "huge"},
                    "color_contrast": {"score": -3, "evidence": "negative"},
                    "type_rhythm": {"score": "not-an-int", "evidence": "junk"},
                },
            )
            review = review_ui_artifact(str(shot), str(plan))
        self.assertEqual(review["axes"]["visual_hierarchy"]["score"], 5)
        # Negative and junk both fall to 0 (needs_review).
        self.assertEqual(review["axes"]["color_contrast"]["score"], 0)
        self.assertEqual(review["axes"]["type_rhythm"]["score"], 0)


class TestRenderCard(unittest.TestCase):
    def test_card_lists_seven_rows(self):
        review = review_ui_artifact("shot.png", "ux.md")
        md = render_card(review, title="Test card")
        self.assertIn("# Test card", md)
        for spec in AXES:
            self.assertIn(spec.name, md)
        self.assertIn("Rubric version: `" + RUBRIC_VERSION + "`", md)

    def test_pipe_in_evidence_is_escaped(self):
        review = review_ui_artifact(
            "shot.png",
            "ux.md",
            evidence_overrides={
                "visual_hierarchy": {"score": 4, "evidence": "title | subtitle"},
            },
        )
        md = render_card(review)
        # The literal pipe must be escaped so the markdown table stays valid.
        self.assertIn(r"title \| subtitle", md)


class TestAxisByIdHelper(unittest.TestCase):
    def test_lookup_consistency(self):
        for spec in AXES:
            self.assertIs(AXIS_BY_ID[spec.axis_id], spec)


if __name__ == "__main__":
    unittest.main()
