"""Tests for A* 15-puzzle solver.

[EXTERNAL_CHALLENGE:coding-challenge-10]
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "challenges"))

from astar_15puzzle import (
    State, GOAL, manhattan_distance, linear_conflict, corner_tiles_heuristic,
    astar, is_solvable, random_solvable, HEURISTICS,
)


class TestState:
    def test_goal_state(self):
        s = State(GOAL)
        assert s.is_goal()

    def test_non_goal(self):
        board = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 0, 15)
        s = State(board)
        assert not s.is_goal()

    def test_neighbors(self):
        s = State(GOAL)  # blank at position 15 (bottom-right)
        neighbors = s.neighbors()
        assert len(neighbors) == 2  # can only go up or left from bottom-right

    def test_neighbors_center(self):
        # Blank in center (position 5)
        board = list(GOAL)
        board[5], board[15] = board[15], board[5]
        s = State(tuple(board))
        neighbors = s.neighbors()
        assert len(neighbors) == 4  # can go all 4 directions


class TestHeuristics:
    def test_manhattan_goal(self):
        assert manhattan_distance(State(GOAL)) == 0

    def test_manhattan_one_move(self):
        # Swap 15 and blank (adjacent) - should be 1
        board = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 0, 15)
        assert manhattan_distance(State(board)) == 1

    def test_linear_conflict_goal(self):
        assert linear_conflict(State(GOAL)) == 0

    def test_linear_conflict_ge_manhattan(self):
        """Linear conflict should always be >= Manhattan distance."""
        for _ in range(20):
            puzzle = random_solvable(moves=30)
            md = manhattan_distance(puzzle)
            lc = linear_conflict(puzzle)
            assert lc >= md, f"LC={lc} < MD={md}"

    def test_corner_tiles_ge_linear_conflict(self):
        """Corner tiles heuristic should always be >= linear conflict."""
        for _ in range(20):
            puzzle = random_solvable(moves=30)
            lc = linear_conflict(puzzle)
            ct = corner_tiles_heuristic(puzzle)
            assert ct >= lc, f"CT={ct} < LC={lc}"

    def test_all_heuristics_admissible(self):
        """All heuristics must be admissible (never overestimate).

        Test by solving easy puzzles and comparing h to actual cost.
        """
        for _ in range(5):
            puzzle = random_solvable(moves=10)
            result = astar(puzzle, manhattan_distance, max_nodes=100000)
            if result["solved"]:
                actual = result["length"]
                for name, hfn in HEURISTICS.items():
                    h = hfn(puzzle)
                    assert h <= actual, (
                        f"{name} overestimates: h={h} > actual={actual}"
                    )


class TestSolvability:
    def test_goal_solvable(self):
        assert is_solvable(GOAL)

    def test_swap_makes_unsolvable(self):
        # Swapping two adjacent non-blank tiles changes parity
        board = list(GOAL)
        board[0], board[1] = board[1], board[0]  # swap 1 and 2
        assert not is_solvable(tuple(board))

    def test_random_solvable(self):
        for _ in range(10):
            puzzle = random_solvable(moves=50)
            assert is_solvable(puzzle.board)


class TestAStar:
    def test_solve_goal(self):
        """Goal state should be solved in 0 moves."""
        result = astar(State(GOAL), manhattan_distance)
        assert result["solved"]
        assert result["length"] == 0
        assert result["nodes_expanded"] == 0

    def test_solve_one_move(self):
        """One move from goal."""
        board = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 0, 15)
        result = astar(State(board), manhattan_distance)
        assert result["solved"]
        assert result["length"] == 1

    def test_solve_easy_puzzle(self):
        """Solve an easy random puzzle."""
        puzzle = random_solvable(moves=15)
        for name, hfn in HEURISTICS.items():
            result = astar(puzzle, hfn, max_nodes=200000)
            assert result["solved"], f"{name} failed to solve easy puzzle"
            assert result["length"] > 0

    def test_all_heuristics_find_optimal(self):
        """All heuristics should find the same optimal solution length."""
        puzzle = random_solvable(moves=10)
        lengths = {}
        for name, hfn in HEURISTICS.items():
            result = astar(puzzle, hfn, max_nodes=200000)
            if result["solved"]:
                lengths[name] = result["length"]

        # All solved lengths should be equal (A* with admissible heuristic = optimal)
        values = list(lengths.values())
        if values:
            assert all(v == values[0] for v in values), (
                f"Heuristics found different lengths: {lengths}"
            )

    def test_better_heuristic_expands_fewer_nodes(self):
        """On average, stronger heuristics should expand fewer nodes."""
        total_manhattan = 0
        total_lc = 0
        n_solved = 0

        for _ in range(5):
            puzzle = random_solvable(moves=20)
            r_md = astar(puzzle, manhattan_distance, max_nodes=200000)
            r_lc = astar(puzzle, linear_conflict, max_nodes=200000)
            if r_md["solved"] and r_lc["solved"]:
                total_manhattan += r_md["nodes_expanded"]
                total_lc += r_lc["nodes_expanded"]
                n_solved += 1

        if n_solved > 0:
            # Linear conflict should generally expand fewer or equal nodes
            assert total_lc <= total_manhattan * 1.1, (
                f"LC expanded more nodes than Manhattan: {total_lc} vs {total_manhattan}"
            )
