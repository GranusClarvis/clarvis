"""Tests for CSP solver with AC-3 + backtracking."""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import _paths  # noqa: F401,E402

from csp_solver import (
    CSP, BinaryConstraint, SolverStats,
    ac3, solve, verify_solution,
    puzzle_easy, puzzle_medium, puzzle_hard,
)
from copy import deepcopy


# ── Puzzle solution tests ────────────────────────────────

class TestPuzzleEasy:
    def test_has_solution(self):
        csp = puzzle_easy()
        sol, stats = solve(csp)
        assert sol is not None

    def test_solution_valid(self):
        csp = puzzle_easy()
        sol, _ = solve(csp)
        assert verify_solution(csp, sol)

    def test_stats_reasonable(self):
        csp = puzzle_easy()
        _, stats = solve(csp)
        assert stats.nodes_explored >= 1
        assert stats.solve_time_ms >= 0


class TestPuzzleMedium:
    def test_has_solution(self):
        csp = puzzle_medium()
        sol, stats = solve(csp)
        assert sol is not None

    def test_solution_valid(self):
        csp = puzzle_medium()
        sol, _ = solve(csp)
        assert verify_solution(csp, sol)

    def test_more_backtracks_than_easy(self):
        _, easy_stats = solve(puzzle_easy())
        _, med_stats = solve(puzzle_medium())
        assert med_stats.arc_revisions >= easy_stats.arc_revisions


class TestPuzzleHard:
    def test_has_solution(self):
        csp = puzzle_hard()
        sol, stats = solve(csp)
        assert sol is not None

    def test_solution_valid(self):
        csp = puzzle_hard()
        sol, _ = solve(csp)
        assert verify_solution(csp, sol)

    def test_constraint_count(self):
        csp = puzzle_hard()
        assert len(csp.constraints) == 12


# ── AC-3 tests ───────────────────────────────────────────

class TestAC3:
    def test_reduces_domains(self):
        csp = CSP(
            variables=["X", "Y"],
            domains={"X": [1, 2, 3], "Y": [1, 2, 3]},
            constraints=[BinaryConstraint("X", "Y", lambda x, y: x < y)],
        )
        domains = deepcopy(csp.domains)
        stats = SolverStats()
        assert ac3(csp, domains, stats)
        assert 3 not in domains["X"]
        assert 1 not in domains["Y"]

    def test_detects_inconsistency(self):
        csp = CSP(
            variables=["X", "Y"],
            domains={"X": [1], "Y": [1]},
            constraints=[BinaryConstraint("X", "Y", lambda x, y: x != y)],
        )
        domains = deepcopy(csp.domains)
        stats = SolverStats()
        assert not ac3(csp, domains, stats)

    def test_no_constraints_no_change(self):
        csp = CSP(
            variables=["X", "Y"],
            domains={"X": [1, 2], "Y": [3, 4]},
            constraints=[],
        )
        domains = deepcopy(csp.domains)
        stats = SolverStats()
        assert ac3(csp, domains, stats)
        assert domains == {"X": [1, 2], "Y": [3, 4]}


# ── Solver edge cases ────────────────────────────────────

class TestSolverEdgeCases:
    def test_single_variable(self):
        csp = CSP(variables=["X"], domains={"X": [42]}, constraints=[])
        sol, _ = solve(csp)
        assert sol == {"X": 42}

    def test_unsatisfiable(self):
        csp = CSP(
            variables=["X", "Y"],
            domains={"X": [1], "Y": [1]},
            constraints=[BinaryConstraint("X", "Y", lambda x, y: x > y)],
        )
        sol, stats = solve(csp)
        assert sol is None

    def test_all_different_3vars(self):
        csp = CSP(
            variables=["A", "B", "C"],
            domains={"A": [1, 2, 3], "B": [1, 2, 3], "C": [1, 2, 3]},
            constraints=[
                BinaryConstraint("A", "B", lambda a, b: a != b),
                BinaryConstraint("B", "C", lambda b, c: b != c),
                BinaryConstraint("A", "C", lambda a, c: a != c),
            ],
        )
        sol, _ = solve(csp)
        assert sol is not None
        assert len(set(sol.values())) == 3


# ── Verify solution ──────────────────────────────────────

class TestVerifySolution:
    def test_valid(self):
        csp = CSP(
            variables=["X", "Y"],
            domains={"X": [1, 2], "Y": [1, 2]},
            constraints=[BinaryConstraint("X", "Y", lambda x, y: x != y)],
        )
        assert verify_solution(csp, {"X": 1, "Y": 2})

    def test_invalid_constraint(self):
        csp = CSP(
            variables=["X", "Y"],
            domains={"X": [1, 2], "Y": [1, 2]},
            constraints=[BinaryConstraint("X", "Y", lambda x, y: x != y)],
        )
        assert not verify_solution(csp, {"X": 1, "Y": 1})

    def test_missing_variable(self):
        csp = CSP(
            variables=["X", "Y"],
            domains={"X": [1], "Y": [1]},
            constraints=[],
        )
        assert not verify_solution(csp, {"X": 1})

    def test_value_not_in_domain(self):
        csp = CSP(
            variables=["X"],
            domains={"X": [1, 2]},
            constraints=[],
        )
        assert not verify_solution(csp, {"X": 99})
