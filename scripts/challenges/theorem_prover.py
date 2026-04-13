#!/usr/bin/env python3
"""Minimal resolution-based theorem prover for propositional logic.

Supports: AND, OR, NOT, IMPLIES, BICONDITIONAL
Implements: CNF conversion, resolution rule, modus ponens detection.

[EXTERNAL_CHALLENGE:coding-challenge-07]

Usage:
    python3 theorem_prover.py prove "((P IMPLIES Q) AND P) IMPLIES Q"
    python3 theorem_prover.py cnf "(P AND Q) OR (NOT R)"
    python3 theorem_prover.py demo
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


# === AST ===

class Op(Enum):
    AND = auto()
    OR = auto()
    NOT = auto()
    IMPLIES = auto()
    BICONDITIONAL = auto()


@dataclass(frozen=True)
class Var:
    name: str
    def __repr__(self): return self.name


@dataclass(frozen=True)
class Not:
    child: 'Formula'
    def __repr__(self): return f"¬{self.child}"


@dataclass(frozen=True)
class BinOp:
    op: Op
    left: 'Formula'
    right: 'Formula'
    def __repr__(self):
        syms = {Op.AND: "∧", Op.OR: "∨", Op.IMPLIES: "→", Op.BICONDITIONAL: "↔"}
        return f"({self.left} {syms[self.op]} {self.right})"


Formula = Var | Not | BinOp

# Literal: (name, positive?)
Literal = tuple[str, bool]
Clause = frozenset[Literal]


# === PARSER ===

class TokenStream:
    def __init__(self, tokens: list[str]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Optional[str]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def consume(self) -> str:
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def expect(self, t: str):
        got = self.consume()
        if got != t:
            raise ValueError(f"Expected '{t}', got '{got}'")


def tokenize(s: str) -> list[str]:
    """Tokenize a propositional logic formula."""
    tokens = []
    i = 0
    while i < len(s):
        if s[i].isspace():
            i += 1
        elif s[i] in '()':
            tokens.append(s[i])
            i += 1
        elif s[i:i+3] == 'AND':
            tokens.append('AND')
            i += 3
        elif s[i:i+2] == 'OR':
            tokens.append('OR')
            i += 2
        elif s[i:i+3] == 'NOT':
            tokens.append('NOT')
            i += 3
        elif s[i:i+7] == 'IMPLIES':
            tokens.append('IMPLIES')
            i += 7
        elif s[i:i+3] == 'IFF':
            tokens.append('IFF')
            i += 3
        elif s[i:i+13] == 'BICONDITIONAL':
            tokens.append('IFF')
            i += 13
        elif s[i] == '~' or s[i] == '!':
            tokens.append('NOT')
            i += 1
        elif s[i] == '&':
            tokens.append('AND')
            i += 1
        elif s[i] == '|':
            tokens.append('OR')
            i += 1
        elif s[i:i+2] == '->':
            tokens.append('IMPLIES')
            i += 2
        elif s[i:i+3] == '<->':
            tokens.append('IFF')
            i += 3
        elif s[i].isalpha() or s[i] == '_':
            j = i
            while j < len(s) and (s[j].isalnum() or s[j] == '_'):
                j += 1
            word = s[i:j]
            if word in ('AND', 'OR', 'NOT', 'IMPLIES', 'IFF', 'BICONDITIONAL'):
                tokens.append('IFF' if word == 'BICONDITIONAL' else word)
            else:
                tokens.append(word)
            i = j
        else:
            raise ValueError(f"Unexpected character: '{s[i]}' at position {i}")
    return tokens


def parse(s: str) -> Formula:
    """Parse a propositional logic formula string into an AST."""
    tokens = tokenize(s)
    ts = TokenStream(tokens)
    result = _parse_biconditional(ts)
    if ts.peek() is not None:
        raise ValueError(f"Unexpected token: '{ts.peek()}'")
    return result


def _parse_biconditional(ts: TokenStream) -> Formula:
    left = _parse_implies(ts)
    while ts.peek() == 'IFF':
        ts.consume()
        right = _parse_implies(ts)
        left = BinOp(Op.BICONDITIONAL, left, right)
    return left


def _parse_implies(ts: TokenStream) -> Formula:
    left = _parse_or(ts)
    # Right-associative
    if ts.peek() == 'IMPLIES':
        ts.consume()
        right = _parse_implies(ts)
        left = BinOp(Op.IMPLIES, left, right)
    return left


def _parse_or(ts: TokenStream) -> Formula:
    left = _parse_and(ts)
    while ts.peek() == 'OR':
        ts.consume()
        right = _parse_and(ts)
        left = BinOp(Op.OR, left, right)
    return left


def _parse_and(ts: TokenStream) -> Formula:
    left = _parse_not(ts)
    while ts.peek() == 'AND':
        ts.consume()
        right = _parse_not(ts)
        left = BinOp(Op.AND, left, right)
    return left


def _parse_not(ts: TokenStream) -> Formula:
    if ts.peek() == 'NOT':
        ts.consume()
        child = _parse_not(ts)
        return Not(child)
    return _parse_atom(ts)


def _parse_atom(ts: TokenStream) -> Formula:
    if ts.peek() == '(':
        ts.consume()
        expr = _parse_biconditional(ts)
        ts.expect(')')
        return expr
    t = ts.consume()
    return Var(t)


# === CNF CONVERSION ===

def eliminate_implications(f: Formula) -> Formula:
    """Remove IMPLIES and BICONDITIONAL."""
    if isinstance(f, Var):
        return f
    if isinstance(f, Not):
        return Not(eliminate_implications(f.child))
    if isinstance(f, BinOp):
        l = eliminate_implications(f.left)
        r = eliminate_implications(f.right)
        if f.op == Op.IMPLIES:
            return BinOp(Op.OR, Not(l), r)
        if f.op == Op.BICONDITIONAL:
            return BinOp(Op.AND,
                         BinOp(Op.OR, Not(l), r),
                         BinOp(Op.OR, Not(r), l))
        return BinOp(f.op, l, r)
    return f


def push_negation(f: Formula) -> Formula:
    """Push NOT inward (De Morgan's laws), eliminate double negation."""
    if isinstance(f, Var):
        return f
    if isinstance(f, Not):
        inner = f.child
        if isinstance(inner, Not):
            return push_negation(inner.child)
        if isinstance(inner, BinOp):
            if inner.op == Op.AND:
                return BinOp(Op.OR, push_negation(Not(inner.left)), push_negation(Not(inner.right)))
            if inner.op == Op.OR:
                return BinOp(Op.AND, push_negation(Not(inner.left)), push_negation(Not(inner.right)))
        if isinstance(inner, Var):
            return Not(inner)
        return Not(push_negation(inner))
    if isinstance(f, BinOp):
        return BinOp(f.op, push_negation(f.left), push_negation(f.right))
    return f


def distribute_or(f: Formula) -> Formula:
    """Distribute OR over AND to reach CNF."""
    if isinstance(f, Var) or isinstance(f, Not):
        return f
    if isinstance(f, BinOp):
        if f.op == Op.AND:
            return BinOp(Op.AND, distribute_or(f.left), distribute_or(f.right))
        if f.op == Op.OR:
            l = distribute_or(f.left)
            r = distribute_or(f.right)
            # Distribute: (A AND B) OR C => (A OR C) AND (B OR C)
            if isinstance(l, BinOp) and l.op == Op.AND:
                return distribute_or(BinOp(Op.AND,
                    BinOp(Op.OR, l.left, r),
                    BinOp(Op.OR, l.right, r)))
            if isinstance(r, BinOp) and r.op == Op.AND:
                return distribute_or(BinOp(Op.AND,
                    BinOp(Op.OR, l, r.left),
                    BinOp(Op.OR, l, r.right)))
            return BinOp(Op.OR, l, r)
    return f


def to_cnf(f: Formula) -> Formula:
    """Convert formula to Conjunctive Normal Form."""
    f = eliminate_implications(f)
    f = push_negation(f)
    f = distribute_or(f)
    return f


def extract_clauses(f: Formula) -> set[Clause]:
    """Extract set of clauses from CNF formula."""
    clauses = set()

    def _collect_conjuncts(node: Formula, acc: list):
        if isinstance(node, BinOp) and node.op == Op.AND:
            _collect_conjuncts(node.left, acc)
            _collect_conjuncts(node.right, acc)
        else:
            acc.append(node)

    conjuncts = []
    _collect_conjuncts(f, conjuncts)

    for conj in conjuncts:
        clause = set()

        def _collect_disjuncts(node: Formula):
            if isinstance(node, BinOp) and node.op == Op.OR:
                _collect_disjuncts(node.left)
                _collect_disjuncts(node.right)
            elif isinstance(node, Not) and isinstance(node.child, Var):
                clause.add((node.child.name, False))
            elif isinstance(node, Var):
                clause.add((node.name, True))
            else:
                raise ValueError(f"Non-CNF node in clause: {node}")

        _collect_disjuncts(conj)
        clauses.add(frozenset(clause))

    return clauses


# === RESOLUTION ===

def resolve(c1: Clause, c2: Clause) -> Optional[Clause]:
    """Apply resolution rule: find complementary literal and resolve.

    Returns the resolvent clause, or None if no resolution possible.
    """
    for lit in c1:
        complement = (lit[0], not lit[1])
        if complement in c2:
            # Resolve on this literal
            resolvent = (c1 - {lit}) | (c2 - {complement})
            return frozenset(resolvent)
    return None


def is_tautology(clause: Clause) -> bool:
    """Check if clause contains both P and ¬P."""
    for name, pos in clause:
        if (name, not pos) in clause:
            return True
    return False


def prove(formula_str: str, max_iterations: int = 10000) -> dict:
    """Prove a formula is a tautology using resolution refutation.

    Strategy: negate the formula, convert to CNF, apply resolution.
    If empty clause derived → original is a tautology (proved).
    If saturated → not a tautology.
    """
    formula = parse(formula_str)
    negated = Not(formula)
    cnf = to_cnf(negated)
    clauses = extract_clauses(cnf)

    # Remove tautological clauses
    clauses = {c for c in clauses if not is_tautology(c)}

    steps = []
    steps.append({"action": "negate", "formula": str(negated)})
    steps.append({"action": "cnf", "clauses": len(clauses)})

    seen = set(clauses)
    clause_list = list(clauses)
    iterations = 0

    while iterations < max_iterations:
        new_clauses = set()

        for i in range(len(clause_list)):
            for j in range(i + 1, len(clause_list)):
                resolvent = resolve(clause_list[i], clause_list[j])
                if resolvent is None:
                    continue

                iterations += 1

                if len(resolvent) == 0:
                    # Empty clause! Contradiction found → formula is a tautology
                    steps.append({
                        "action": "resolve",
                        "c1": _clause_str(clause_list[i]),
                        "c2": _clause_str(clause_list[j]),
                        "result": "□ (empty clause)",
                    })
                    return {
                        "proved": True,
                        "iterations": iterations,
                        "clauses_generated": len(seen),
                        "steps": steps,
                        "method": "resolution refutation",
                    }

                if resolvent not in seen and not is_tautology(resolvent):
                    new_clauses.add(resolvent)
                    seen.add(resolvent)

        if not new_clauses:
            # Saturated — no new clauses can be derived
            return {
                "proved": False,
                "iterations": iterations,
                "clauses_generated": len(seen),
                "steps": steps,
                "method": "resolution refutation (saturated)",
            }

        clause_list.extend(new_clauses)
        steps.append({"action": "iteration", "new_clauses": len(new_clauses), "total": len(clause_list)})

    return {
        "proved": False,
        "iterations": iterations,
        "clauses_generated": len(seen),
        "steps": steps,
        "method": "resolution refutation (max iterations)",
    }


def _clause_str(clause: Clause) -> str:
    """Pretty-print a clause."""
    if not clause:
        return "□"
    lits = []
    for name, pos in sorted(clause):
        lits.append(name if pos else f"¬{name}")
    return "{" + ", ".join(lits) + "}"


def _cnf_str(clauses: set[Clause]) -> str:
    """Pretty-print CNF clause set."""
    return " ∧ ".join(_clause_str(c) for c in sorted(clauses, key=lambda c: (len(c), str(c))))


# === MODUS PONENS DETECTOR ===

def detect_modus_ponens(clauses: set[Clause]) -> list[dict]:
    """Detect modus ponens patterns: {¬P, Q} (i.e. P→Q) + {P} ⊢ {Q}."""
    results = []
    clause_list = list(clauses)

    for i, c1 in enumerate(clause_list):
        if len(c1) != 2:
            continue
        lits = list(c1)
        for idx in range(2):
            antecedent_name, antecedent_pos = lits[idx]
            consequent_name, consequent_pos = lits[1 - idx]
            if antecedent_pos:
                continue  # Need ¬P for P→Q encoding
            # Look for unit clause {P}
            needed = frozenset({(antecedent_name, True)})
            if needed in clauses:
                conclusion = frozenset({(consequent_name, consequent_pos)})
                results.append({
                    "rule": "modus ponens",
                    "premise_implication": f"{antecedent_name} → {_clause_str(frozenset({(consequent_name, consequent_pos)}))}",
                    "premise_fact": antecedent_name,
                    "conclusion": _clause_str(conclusion),
                })

    return results


# === CLI ===

def main():
    if len(sys.argv) < 2:
        print("Usage: theorem_prover.py [prove|cnf|demo] [formula]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "demo":
        demos = [
            ("Modus Ponens", "((P IMPLIES Q) AND P) IMPLIES Q"),
            ("Contraposition", "(P IMPLIES Q) IMPLIES (NOT Q IMPLIES NOT P)"),
            ("Excluded Middle", "P OR NOT P"),
            ("De Morgan", "(NOT (P AND Q)) IFF (NOT P OR NOT Q)"),
            ("Hypothetical Syllogism", "((P IMPLIES Q) AND (Q IMPLIES R)) IMPLIES (P IMPLIES R)"),
            ("Non-tautology", "P IMPLIES Q"),
            ("Double Negation", "P IFF NOT NOT P"),
            ("Contradiction", "NOT (P AND NOT P)"),
        ]
        for name, formula in demos:
            result = prove(formula)
            status = "✓ PROVED" if result["proved"] else "✗ NOT PROVED"
            print(f"{status}  {name}: {formula}")
            print(f"         iterations={result['iterations']}, clauses={result['clauses_generated']}")
        return

    if cmd == "prove":
        if len(sys.argv) < 3:
            print("Usage: theorem_prover.py prove \"FORMULA\"")
            sys.exit(1)
        formula = " ".join(sys.argv[2:])
        result = prove(formula)
        status = "PROVED (tautology)" if result["proved"] else "NOT PROVED (not a tautology)"
        print(f"Formula: {formula}")
        print(f"Result: {status}")
        print(f"Method: {result['method']}")
        print(f"Iterations: {result['iterations']}")
        print(f"Clauses generated: {result['clauses_generated']}")

    elif cmd == "cnf":
        if len(sys.argv) < 3:
            print("Usage: theorem_prover.py cnf \"FORMULA\"")
            sys.exit(1)
        formula = " ".join(sys.argv[2:])
        f = parse(formula)
        cnf = to_cnf(f)
        clauses = extract_clauses(cnf)
        print(f"Formula: {formula}")
        print(f"CNF: {_cnf_str(clauses)}")
        mp = detect_modus_ponens(clauses)
        if mp:
            print("Detected modus ponens patterns:")
            for m in mp:
                print(f"  {m['premise_implication']} + {m['premise_fact']} ⊢ {m['conclusion']}")


if __name__ == "__main__":
    main()
