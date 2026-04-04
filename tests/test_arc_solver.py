"""Tests for ARC-AGI pattern completion solver."""
import sys
import pytest

sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
from arc_solver import (
    solve, evaluate, run_all, PUZZLES,
    rotate_90, rotate_180, rotate_270, flip_h, flip_v, transpose,
    grid_eq, grid_shape, scale_grid, crop_nonzero, apply_color_map,
    find_enclosed_regions,
)


# ── Grid utility tests ──────────────────────────────────────────────

class TestGridUtils:
    def test_grid_eq_same(self):
        assert grid_eq([[1, 2], [3, 4]], [[1, 2], [3, 4]])

    def test_grid_eq_diff(self):
        assert not grid_eq([[1, 2]], [[1, 3]])

    def test_grid_eq_diff_shape(self):
        assert not grid_eq([[1, 2]], [[1, 2], [3, 4]])

    def test_grid_shape(self):
        assert grid_shape([[1, 2, 3], [4, 5, 6]]) == (2, 3)

    def test_rotate_90(self):
        assert rotate_90([[1, 2], [3, 4]]) == [[3, 1], [4, 2]]

    def test_rotate_180(self):
        g = [[1, 2], [3, 4]]
        assert rotate_180(g) == [[4, 3], [2, 1]]

    def test_rotate_270(self):
        g = [[1, 2], [3, 4]]
        assert rotate_270(g) == [[2, 4], [1, 3]]

    def test_rotate_360_identity(self):
        g = [[1, 2, 3], [4, 5, 6]]
        assert grid_eq(rotate_90(rotate_90(rotate_90(rotate_90(g)))), g)

    def test_flip_h(self):
        assert flip_h([[1, 2, 3]]) == [[3, 2, 1]]

    def test_flip_v(self):
        assert flip_v([[1], [2], [3]]) == [[3], [2], [1]]

    def test_transpose(self):
        assert transpose([[1, 2], [3, 4], [5, 6]]) == [[1, 3, 5], [2, 4, 6]]

    def test_scale_grid_2x(self):
        result = scale_grid([[1, 2]], 2)
        assert result == [[1, 1, 2, 2], [1, 1, 2, 2]]

    def test_crop_nonzero(self):
        g = [[0, 0, 0], [0, 1, 2], [0, 3, 0]]
        assert crop_nonzero(g) == [[1, 2], [3, 0]]

    def test_apply_color_map(self):
        g = [[1, 2], [3, 1]]
        assert apply_color_map(g, {1: 9, 2: 8}) == [[9, 8], [3, 9]]

    def test_find_enclosed(self):
        g = [[0, 0, 0],
             [0, 1, 0],  # not enclosed (open)
             [0, 0, 0]]
        # No cell is truly enclosed here
        result = find_enclosed_regions(g, 1, 3, 0)
        assert result == g  # nothing changes — not enclosed

    def test_find_enclosed_box(self):
        g = [[1, 1, 1],
             [1, 0, 1],
             [1, 1, 1]]
        result = find_enclosed_regions(g, 1, 5, 0)
        assert result == [[1, 1, 1], [1, 5, 1], [1, 1, 1]]


# ── Puzzle solver tests ─────────────────────────────────────────────

class TestSolver:
    @pytest.mark.parametrize("name", list(PUZZLES.keys()))
    def test_builtin_puzzle(self, name):
        result = evaluate(PUZZLES[name])
        assert result["score"] == 1.0, f"Puzzle {name} failed"

    def test_all_puzzles_pass(self):
        summary = run_all()
        assert summary["accuracy"] == 1.0

    def test_unknown_pattern_returns_input(self):
        """Fallback: if no rule matches, return input unchanged."""
        puzzle = {
            "train": [
                {"input": [[1, 2], [3, 4]], "output": [[9, 9], [9, 9]]},
            ],
            "test": [{"input": [[5, 6], [7, 8]]}],
        }
        results = solve(puzzle)
        assert grid_eq(results[0], [[5, 6], [7, 8]])

    def test_color_swap_custom(self):
        puzzle = {
            "train": [
                {"input": [[0, 1], [1, 0]], "output": [[0, 2], [2, 0]]},
                {"input": [[1, 1], [0, 0]], "output": [[2, 2], [0, 0]]},
            ],
            "test": [{"input": [[1, 0], [0, 1]], "output": [[2, 0], [0, 2]]}],
        }
        result = evaluate(puzzle)
        assert result["score"] == 1.0

    def test_evaluate_no_expected(self):
        puzzle = {
            "train": [{"input": [[1, 2], [3, 4]], "output": [[3, 1], [4, 2]]}],
            "test": [{"input": [[5, 6], [7, 8]]}],
        }
        result = evaluate(puzzle)
        assert result["results"][0]["correct"] is None
