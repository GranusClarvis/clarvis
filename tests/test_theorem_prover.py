"""Tests for resolution-based theorem prover.

[EXTERNAL_CHALLENGE:coding-challenge-07]
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "challenges"))

from theorem_prover import (
    parse, to_cnf, extract_clauses, prove, resolve, is_tautology,
    detect_modus_ponens, Var, Not, BinOp, Op, _clause_str,
)


class TestParser:
    def test_simple_var(self):
        assert isinstance(parse("P"), Var)
        assert parse("P").name == "P"

    def test_not(self):
        f = parse("NOT P")
        assert isinstance(f, Not)
        assert isinstance(f.child, Var)

    def test_and(self):
        f = parse("P AND Q")
        assert isinstance(f, BinOp)
        assert f.op == Op.AND

    def test_or(self):
        f = parse("P OR Q")
        assert isinstance(f, BinOp)
        assert f.op == Op.OR

    def test_implies(self):
        f = parse("P IMPLIES Q")
        assert isinstance(f, BinOp)
        assert f.op == Op.IMPLIES

    def test_biconditional(self):
        f = parse("P IFF Q")
        assert isinstance(f, BinOp)
        assert f.op == Op.BICONDITIONAL

    def test_nested(self):
        f = parse("(P AND Q) OR R")
        assert isinstance(f, BinOp)
        assert f.op == Op.OR

    def test_complex(self):
        f = parse("((P IMPLIES Q) AND P) IMPLIES Q")
        assert isinstance(f, BinOp)

    def test_symbolic_operators(self):
        f = parse("P & Q | ~R")
        assert isinstance(f, BinOp)

    def test_arrow_operator(self):
        f = parse("P -> Q")
        assert isinstance(f, BinOp)
        assert f.op == Op.IMPLIES


class TestCNF:
    def test_simple_var_cnf(self):
        f = to_cnf(parse("P"))
        assert isinstance(f, Var)

    def test_implies_elimination(self):
        f = to_cnf(parse("P IMPLIES Q"))
        clauses = extract_clauses(f)
        # P→Q becomes ¬P∨Q, which is one clause
        assert len(clauses) == 1

    def test_de_morgan(self):
        f = to_cnf(parse("NOT (P AND Q)"))
        clauses = extract_clauses(f)
        # ¬(P∧Q) becomes ¬P∨¬Q
        assert len(clauses) == 1

    def test_distribution(self):
        f = to_cnf(parse("(P AND Q) OR R"))
        clauses = extract_clauses(f)
        # (P∧Q)∨R becomes (P∨R)∧(Q∨R) = 2 clauses
        assert len(clauses) == 2

    def test_biconditional_cnf(self):
        f = to_cnf(parse("P IFF Q"))
        clauses = extract_clauses(f)
        # P↔Q = (¬P∨Q)∧(¬Q∨P) = 2 clauses
        assert len(clauses) == 2


class TestResolution:
    def test_resolve_complementary(self):
        c1 = frozenset({("P", True), ("Q", True)})    # {P, Q}
        c2 = frozenset({("P", False), ("R", True)})   # {¬P, R}
        result = resolve(c1, c2)
        assert result is not None
        assert result == frozenset({("Q", True), ("R", True)})  # {Q, R}

    def test_resolve_to_empty(self):
        c1 = frozenset({("P", True)})
        c2 = frozenset({("P", False)})
        result = resolve(c1, c2)
        assert result == frozenset()  # Empty clause

    def test_no_resolution(self):
        c1 = frozenset({("P", True)})
        c2 = frozenset({("Q", True)})
        result = resolve(c1, c2)
        assert result is None

    def test_tautology_detection(self):
        assert is_tautology(frozenset({("P", True), ("P", False)}))
        assert not is_tautology(frozenset({("P", True), ("Q", True)}))


class TestProver:
    def test_modus_ponens(self):
        result = prove("((P IMPLIES Q) AND P) IMPLIES Q")
        assert result["proved"] is True

    def test_contraposition(self):
        result = prove("(P IMPLIES Q) IMPLIES (NOT Q IMPLIES NOT P)")
        assert result["proved"] is True

    def test_excluded_middle(self):
        result = prove("P OR NOT P")
        assert result["proved"] is True

    def test_de_morgan(self):
        result = prove("(NOT (P AND Q)) IFF (NOT P OR NOT Q)")
        assert result["proved"] is True

    def test_hypothetical_syllogism(self):
        result = prove("((P IMPLIES Q) AND (Q IMPLIES R)) IMPLIES (P IMPLIES R)")
        assert result["proved"] is True

    def test_double_negation(self):
        result = prove("P IFF NOT NOT P")
        assert result["proved"] is True

    def test_contradiction_law(self):
        result = prove("NOT (P AND NOT P)")
        assert result["proved"] is True

    def test_non_tautology(self):
        result = prove("P IMPLIES Q")
        assert result["proved"] is False

    def test_simple_non_tautology(self):
        result = prove("P")
        assert result["proved"] is False

    def test_absorption(self):
        result = prove("(P IMPLIES (P OR Q))")
        assert result["proved"] is True

    def test_conjunction_introduction(self):
        # This is not a tautology: P AND Q is not always true
        result = prove("P AND Q")
        assert result["proved"] is False


class TestModusPonens:
    def test_detect_mp(self):
        # {¬P, Q} (encoding of P→Q) and {P}
        clauses = {
            frozenset({("P", False), ("Q", True)}),  # ¬P ∨ Q = P→Q
            frozenset({("P", True)}),                  # P
        }
        results = detect_modus_ponens(clauses)
        assert len(results) >= 1
        assert results[0]["rule"] == "modus ponens"
