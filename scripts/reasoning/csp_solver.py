#!/usr/bin/env python3
"""Constraint Satisfaction Problem (CSP) solver with AC-3 + backtracking.

Solves 5-variable CSPs with domain reduction via arc consistency (AC-3)
before and during backtracking search.

Usage:
    python3 scripts/reasoning/csp_solver.py [--puzzle easy|medium|hard|all]
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Callable


Constraint = Callable[[dict[str, int]], bool]


@dataclass
class BinaryConstraint:
    var1: str
    var2: str
    test: Callable[[int, int], bool]
    description: str = ""

    def satisfied(self, assignment: dict[str, int]) -> bool:
        if self.var1 not in assignment or self.var2 not in assignment:
            return True
        return self.test(assignment[self.var1], assignment[self.var2])


@dataclass
class CSP:
    variables: list[str]
    domains: dict[str, list[int]]
    constraints: list[BinaryConstraint] = field(default_factory=list)

    def neighbors(self, var: str) -> list[str]:
        result = []
        for c in self.constraints:
            if c.var1 == var and c.var2 not in result:
                result.append(c.var2)
            elif c.var2 == var and c.var1 not in result:
                result.append(c.var1)
        return result

    def constraints_between(self, v1: str, v2: str) -> list[BinaryConstraint]:
        return [c for c in self.constraints
                if (c.var1 == v1 and c.var2 == v2) or
                   (c.var1 == v2 and c.var2 == v1)]


@dataclass
class SolverStats:
    nodes_explored: int = 0
    arc_revisions: int = 0
    domain_wipeouts: int = 0
    backtracks: int = 0
    solve_time_ms: float = 0.0


def ac3(csp: CSP, domains: dict[str, list[int]], stats: SolverStats,
        arcs: deque | None = None) -> bool:
    """Enforce arc consistency. Returns False if a domain is wiped out."""
    if arcs is None:
        arcs = deque()
        for c in csp.constraints:
            arcs.append((c.var1, c.var2, c))
            arcs.append((c.var2, c.var1, c))

    while arcs:
        xi, xj, constraint = arcs.popleft()
        stats.arc_revisions += 1
        if revise(domains, xi, xj, constraint):
            if not domains[xi]:
                stats.domain_wipeouts += 1
                return False
            for neighbor in csp.neighbors(xi):
                if neighbor != xj:
                    for c in csp.constraints_between(xi, neighbor):
                        arcs.append((neighbor, xi, c))
    return True


def revise(domains: dict[str, list[int]], xi: str, xj: str,
           constraint: BinaryConstraint) -> bool:
    """Remove values from domains[xi] that have no support in domains[xj]."""
    revised = False
    to_remove = []
    for val_i in domains[xi]:
        has_support = False
        for val_j in domains[xj]:
            if xi == constraint.var1:
                if constraint.test(val_i, val_j):
                    has_support = True
                    break
            else:
                if constraint.test(val_j, val_i):
                    has_support = True
                    break
        if not has_support:
            to_remove.append(val_i)
            revised = True
    for v in to_remove:
        domains[xi].remove(v)
    return revised


def select_unassigned(csp: CSP, assignment: dict[str, int],
                      domains: dict[str, list[int]]) -> str:
    """MRV heuristic: pick variable with smallest remaining domain."""
    unassigned = [v for v in csp.variables if v not in assignment]
    return min(unassigned, key=lambda v: len(domains[v]))


def order_domain_values(csp: CSP, var: str,
                        domains: dict[str, list[int]]) -> list[int]:
    """LCV heuristic: order values by how many options they leave for neighbors."""
    def lcv_score(val: int) -> int:
        count = 0
        for neighbor in csp.neighbors(var):
            for c in csp.constraints_between(var, neighbor):
                for nval in domains[neighbor]:
                    if var == c.var1:
                        if not c.test(val, nval):
                            count += 1
                    else:
                        if not c.test(nval, val):
                            count += 1
        return count

    return sorted(domains[var], key=lcv_score)


def backtrack(csp: CSP, assignment: dict[str, int],
              domains: dict[str, list[int]], stats: SolverStats) -> dict[str, int] | None:
    """Backtracking search with AC-3 inference (MAC)."""
    if len(assignment) == len(csp.variables):
        return dict(assignment)

    stats.nodes_explored += 1
    var = select_unassigned(csp, assignment, domains)

    for value in order_domain_values(csp, var, domains):
        assignment[var] = value
        saved_domains = deepcopy(domains)
        domains[var] = [value]

        # MAC: run AC-3 on arcs from neighbors of var
        arcs = deque()
        for neighbor in csp.neighbors(var):
            for c in csp.constraints_between(var, neighbor):
                arcs.append((neighbor, var, c))

        if ac3(csp, domains, stats, arcs):
            result = backtrack(csp, assignment, domains, stats)
            if result is not None:
                return result

        stats.backtracks += 1
        del assignment[var]
        domains.update(deepcopy(saved_domains))

    return None


def solve(csp: CSP) -> tuple[dict[str, int] | None, SolverStats]:
    """Solve a CSP. Returns (solution, stats)."""
    stats = SolverStats()
    domains = deepcopy(csp.domains)

    t0 = time.monotonic()
    if not ac3(csp, domains, stats):
        stats.solve_time_ms = (time.monotonic() - t0) * 1000
        return None, stats

    result = backtrack(csp, {}, domains, stats)
    stats.solve_time_ms = (time.monotonic() - t0) * 1000
    return result, stats


def verify_solution(csp: CSP, solution: dict[str, int]) -> bool:
    """Check that a solution satisfies all constraints."""
    for c in csp.constraints:
        if not c.satisfied(solution):
            return False
    for var in csp.variables:
        if var not in solution:
            return False
        if solution[var] not in csp.domains[var]:
            return False
    return True


# ── Test Puzzles ─────────────────────────────────────────────

def puzzle_easy() -> CSP:
    """Easy: 5 variables, domains 1-5, 3 constraints. Multiple solutions."""
    variables = ["A", "B", "C", "D", "E"]
    domains = {v: list(range(1, 6)) for v in variables}
    constraints = [
        BinaryConstraint("A", "B", lambda a, b: a != b, "A ≠ B"),
        BinaryConstraint("B", "C", lambda b, c: b < c, "B < C"),
        BinaryConstraint("D", "E", lambda d, e: d + e == 5, "D + E = 5"),
    ]
    return CSP(variables, domains, constraints)


def puzzle_medium() -> CSP:
    """Medium: 5 variables, domains 1-5, 7 constraints. Few solutions."""
    variables = ["A", "B", "C", "D", "E"]
    domains = {v: list(range(1, 6)) for v in variables}
    constraints = [
        BinaryConstraint("A", "B", lambda a, b: a != b, "A ≠ B"),
        BinaryConstraint("A", "C", lambda a, c: a != c, "A ≠ C"),
        BinaryConstraint("B", "C", lambda b, c: b < c, "B < C"),
        BinaryConstraint("C", "D", lambda c, d: c != d, "C ≠ D"),
        BinaryConstraint("D", "E", lambda d, e: d > e, "D > E"),
        BinaryConstraint("A", "E", lambda a, e: a + e <= 5, "A + E ≤ 5"),
        BinaryConstraint("B", "D", lambda b, d: abs(b - d) >= 2, "|B - D| ≥ 2"),
    ]
    return CSP(variables, domains, constraints)


def puzzle_hard() -> CSP:
    """Hard: 5 variables, domains 1-7, 12 constraints. Unique or near-unique solution."""
    variables = ["A", "B", "C", "D", "E"]
    domains = {v: list(range(1, 8)) for v in variables}
    constraints = [
        BinaryConstraint("A", "B", lambda a, b: a != b, "A ≠ B"),
        BinaryConstraint("A", "C", lambda a, c: a != c, "A ≠ C"),
        BinaryConstraint("A", "D", lambda a, d: a != d, "A ≠ D"),
        BinaryConstraint("B", "C", lambda b, c: b != c, "B ≠ C"),
        BinaryConstraint("B", "D", lambda b, d: b != d, "B ≠ D"),
        BinaryConstraint("C", "D", lambda c, d: c != d, "C ≠ D"),
        BinaryConstraint("A", "B", lambda a, b: a + b == 7, "A + B = 7"),
        BinaryConstraint("C", "D", lambda c, d: c * d <= 12, "C × D ≤ 12"),
        BinaryConstraint("D", "E", lambda d, e: d < e, "D < E"),
        BinaryConstraint("A", "E", lambda a, e: a != e, "A ≠ E"),
        BinaryConstraint("B", "E", lambda b, e: b != e, "B ≠ E"),
        BinaryConstraint("C", "E", lambda c, e: c + e >= 6, "C + E ≥ 6"),
    ]
    return CSP(variables, domains, constraints)


PUZZLES = {"easy": puzzle_easy, "medium": puzzle_medium, "hard": puzzle_hard}


def run_puzzle(name: str, csp: CSP) -> bool:
    """Run and display a puzzle solution. Returns True if solved."""
    print(f"\n{'='*50}")
    print(f"Puzzle: {name.upper()}")
    print(f"Variables: {csp.variables}")
    print(f"Domain sizes: {[len(csp.domains[v]) for v in csp.variables]}")
    print(f"Constraints ({len(csp.constraints)}):")
    for c in csp.constraints:
        print(f"  {c.description}")

    solution, stats = solve(csp)

    print(f"\nStats:")
    print(f"  Nodes explored: {stats.nodes_explored}")
    print(f"  Arc revisions:  {stats.arc_revisions}")
    print(f"  Backtracks:     {stats.backtracks}")
    print(f"  Domain wipeouts:{stats.domain_wipeouts}")
    print(f"  Time:           {stats.solve_time_ms:.2f}ms")

    if solution:
        print(f"\nSolution: {solution}")
        valid = verify_solution(csp, solution)
        print(f"Valid: {valid}")
        return valid
    else:
        print("\nNo solution found.")
        return False


def main():
    parser = argparse.ArgumentParser(description="CSP solver with AC-3 + backtracking")
    parser.add_argument("--puzzle", default="all", choices=["easy", "medium", "hard", "all"])
    args = parser.parse_args()

    puzzles = PUZZLES if args.puzzle == "all" else {args.puzzle: PUZZLES[args.puzzle]}
    results = {}
    for name, factory in puzzles.items():
        results[name] = run_puzzle(name, factory())

    print(f"\n{'='*50}")
    print("Summary:", {k: "PASS" if v else "FAIL" for k, v in results.items()})
    return all(results.values())


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
