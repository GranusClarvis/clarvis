#!/usr/bin/env python3
"""
Thompson NFA Regex Engine — Deliberate Practice Challenge

Implements a regex engine using Thompson's NFA construction.
Supports: concatenation, alternation (|), Kleene star (*), plus (+),
optional (?), and character classes [a-z].

This was built as a deliberate practice exercise for Clarvis's reasoning
capability sprint — deep multi-step reasoning on a hard algorithmic problem.

Usage:
    from scripts.challenges.thompson_nfa import match, compile_regex

    assert match("a(b|c)*d", "abcbcd")
    assert not match("a(b|c)*d", "abced")
    assert match("[a-z]+", "hello")
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ── NFA State ──────────────────────────────────────────────────────

@dataclass(eq=False)
class State:
    """A single NFA state. Transitions are on a character or epsilon (None).
    Uses identity-based hashing (each state is unique)."""
    transitions: dict[str | None, list[State]] = field(default_factory=dict)
    is_accept: bool = False

    def add(self, char: str | None, target: "State"):
        self.transitions.setdefault(char, []).append(target)

    def __hash__(self):
        return id(self)


@dataclass
class NFA:
    """An NFA fragment with a start state and a single accept state."""
    start: State
    accept: State


# ── Parser: regex string → token list ─────────────────────────────

def _tokenize(pattern: str) -> list[str]:
    """Convert regex pattern to token list, inserting explicit concat operators."""
    tokens: list[str] = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == '[':
            # Character class: consume until ]
            j = i + 1
            while j < len(pattern) and pattern[j] != ']':
                j += 1
            tokens.append(pattern[i:j + 1])  # e.g., "[a-z]"
            i = j + 1
        elif ch == '\\' and i + 1 < len(pattern):
            tokens.append(pattern[i:i + 2])  # escaped char
            i += 2
        else:
            tokens.append(ch)
            i += 1
    return tokens


def _insert_concat(tokens: list[str]) -> list[str]:
    """Insert explicit concatenation operator (.) between tokens that need it."""
    result: list[str] = []
    for i, tok in enumerate(tokens):
        result.append(tok)
        if i + 1 < len(tokens):
            next_tok = tokens[i + 1]
            # After a token that produces a value (literal, ), *, +, ?, ])
            # and before a token that consumes a value (literal, (, [)
            left_is_value = tok not in ('(', '|')
            right_is_value = next_tok not in (')', '|', '*', '+', '?')
            if left_is_value and right_is_value:
                result.append('.')
    return result


def _to_postfix(tokens: list[str]) -> list[str]:
    """Convert infix token list to postfix using shunting-yard.

    Precedence: * + ? (3) > . concat (2) > | alternation (1)
    """
    precedence = {'|': 1, '.': 2, '*': 3, '+': 3, '?': 3}
    output: list[str] = []
    ops: list[str] = []

    for tok in tokens:
        if tok == '(':
            ops.append(tok)
        elif tok == ')':
            while ops and ops[-1] != '(':
                output.append(ops.pop())
            if ops:
                ops.pop()  # remove '('
        elif tok in precedence:
            while (ops and ops[-1] != '(' and
                   ops[-1] in precedence and
                   precedence[ops[-1]] >= precedence[tok]):
                output.append(ops.pop())
            ops.append(tok)
        else:
            # Literal, character class, or escaped char
            output.append(tok)

    while ops:
        output.append(ops.pop())

    return output


# ── NFA Construction (Thompson's Construction) ────────────────────

def _char_matches(char_token: str, ch: str) -> bool:
    """Check if a character matches a token (literal, class, or escaped)."""
    if char_token == '.':
        # In our grammar '.' is concat — for wildcard use \\. explicitly
        # Treat single '.' literal as matching any char (not used as operator here)
        return True
    if char_token.startswith('[') and char_token.endswith(']'):
        # Character class: [a-z], [abc], [a-zA-Z0-9]
        inner = char_token[1:-1]
        negate = inner.startswith('^')
        if negate:
            inner = inner[1:]
        i = 0
        matched = False
        while i < len(inner):
            if i + 2 < len(inner) and inner[i + 1] == '-':
                # Range: a-z
                if inner[i] <= ch <= inner[i + 2]:
                    matched = True
                i += 3
            else:
                if inner[i] == ch:
                    matched = True
                i += 1
        return matched != negate
    if char_token.startswith('\\') and len(char_token) == 2:
        return ch == char_token[1]
    # Plain literal
    return ch == char_token


def _build_nfa(postfix: list[str]) -> NFA:
    """Build NFA from postfix token list using Thompson's construction."""
    stack: list[NFA] = []

    for tok in postfix:
        if tok == '.':
            # Concatenation
            right = stack.pop()
            left = stack.pop()
            left.accept.is_accept = False
            left.accept.add(None, right.start)  # epsilon from left.accept → right.start
            stack.append(NFA(left.start, right.accept))

        elif tok == '|':
            # Alternation
            right = stack.pop()
            left = stack.pop()
            start = State()
            accept = State(is_accept=True)
            start.add(None, left.start)
            start.add(None, right.start)
            left.accept.is_accept = False
            left.accept.add(None, accept)
            right.accept.is_accept = False
            right.accept.add(None, accept)
            stack.append(NFA(start, accept))

        elif tok == '*':
            # Kleene star
            nfa = stack.pop()
            start = State()
            accept = State(is_accept=True)
            start.add(None, nfa.start)
            start.add(None, accept)  # zero occurrences
            nfa.accept.is_accept = False
            nfa.accept.add(None, nfa.start)  # loop back
            nfa.accept.add(None, accept)
            stack.append(NFA(start, accept))

        elif tok == '+':
            # One or more (a+ = aa*)
            nfa = stack.pop()
            start = State()
            accept = State(is_accept=True)
            start.add(None, nfa.start)
            nfa.accept.is_accept = False
            nfa.accept.add(None, nfa.start)  # loop back
            nfa.accept.add(None, accept)
            stack.append(NFA(start, accept))

        elif tok == '?':
            # Optional (zero or one)
            nfa = stack.pop()
            start = State()
            accept = State(is_accept=True)
            start.add(None, nfa.start)
            start.add(None, accept)  # skip
            nfa.accept.is_accept = False
            nfa.accept.add(None, accept)
            stack.append(NFA(start, accept))

        else:
            # Literal or character class
            start = State()
            accept = State(is_accept=True)
            start.add(tok, accept)
            stack.append(NFA(start, accept))

    if not stack:
        # Empty pattern: matches empty string
        s = State(is_accept=True)
        return NFA(s, s)
    return stack[-1]


# ── NFA Simulation ────────────────────────────────────────────────

def _epsilon_closure(states: set[State]) -> set[State]:
    """Compute epsilon closure of a set of states."""
    closure = set(states)
    worklist = list(states)
    while worklist:
        state = worklist.pop()
        for target in state.transitions.get(None, []):
            if target not in closure:
                closure.add(target)
                worklist.append(target)
    return closure


def _step(states: set[State], ch: str) -> set[State]:
    """Advance NFA states by one character."""
    next_states: set[State] = set()
    for state in states:
        for token, targets in state.transitions.items():
            if token is not None and _char_matches(token, ch):
                next_states.update(targets)
    return _epsilon_closure(next_states)


def _simulate(nfa: NFA, text: str) -> bool:
    """Simulate NFA on input text. Returns True if the NFA accepts."""
    current = _epsilon_closure({nfa.start})
    for ch in text:
        current = _step(current, ch)
        if not current:
            return False
    return any(s.is_accept for s in current)


# ── Public API ────────────────────────────────────────────────────

def compile_regex(pattern: str) -> NFA:
    """Compile a regex pattern into an NFA."""
    tokens = _tokenize(pattern)
    tokens = _insert_concat(tokens)
    postfix = _to_postfix(tokens)
    return _build_nfa(postfix)


def match(pattern: str, text: str) -> bool:
    """Test if a regex pattern matches the entire text."""
    nfa = compile_regex(pattern)
    return _simulate(nfa, text)


# ── Tests ─────────────────────────────────────────────────────────

def _run_tests():
    """Comprehensive test suite for the Thompson NFA engine."""
    passed = 0
    failed = 0

    def check(pat, text, expected, label=""):
        nonlocal passed, failed
        result = match(pat, text)
        if result == expected:
            passed += 1
        else:
            failed += 1
            print(f"  FAIL: match({pat!r}, {text!r}) = {result}, expected {expected} [{label}]")

    # Basic literals
    check("a", "a", True, "single char")
    check("a", "b", False, "single char mismatch")
    check("abc", "abc", True, "concatenation")
    check("abc", "ab", False, "concat too short")
    check("abc", "abcd", False, "concat too long")

    # Alternation
    check("a|b", "a", True, "alt left")
    check("a|b", "b", True, "alt right")
    check("a|b", "c", False, "alt miss")
    check("a|b|c", "c", True, "triple alt")

    # Kleene star
    check("a*", "", True, "star empty")
    check("a*", "a", True, "star one")
    check("a*", "aaa", True, "star many")
    check("a*", "b", False, "star wrong char")
    check("(ab)*", "", True, "group star empty")
    check("(ab)*", "ababab", True, "group star many")
    check("(ab)*", "aba", False, "group star incomplete")

    # Plus
    check("a+", "", False, "plus empty")
    check("a+", "a", True, "plus one")
    check("a+", "aaaa", True, "plus many")
    check("(ab)+", "ab", True, "group plus one")
    check("(ab)+", "abab", True, "group plus many")
    check("(ab)+", "", False, "group plus empty")

    # Optional
    check("a?", "", True, "optional empty")
    check("a?", "a", True, "optional present")
    check("a?b", "b", True, "optional skip")
    check("a?b", "ab", True, "optional use")
    check("a?b", "aab", False, "optional too many")

    # Character classes
    check("[abc]", "a", True, "class match a")
    check("[abc]", "b", True, "class match b")
    check("[abc]", "d", False, "class miss")
    check("[a-z]", "m", True, "range match")
    check("[a-z]", "A", False, "range case")
    check("[a-z]+", "hello", True, "range plus")
    check("[a-zA-Z]+", "Hello", True, "multi range")
    check("[0-9]+", "42", True, "digit range")
    check("[0-9]+", "abc", False, "digit range miss")
    check("[^a-z]", "A", True, "negated class")
    check("[^a-z]", "a", False, "negated class miss")

    # Combinations
    check("a(b|c)*d", "ad", True, "combo star skip")
    check("a(b|c)*d", "abcd", True, "combo star use")
    check("a(b|c)*d", "abcbcd", True, "combo star many")
    check("a(b|c)*d", "aed", False, "combo star wrong")
    check("(a|b)+c", "abc", True, "alt plus concat")
    check("[a-z][0-9]+", "x42", True, "class concat")
    check("[a-z][0-9]+", "42", False, "class missing alpha")

    # Nested groups
    check("((a|b)c)+", "ac", True, "nested one")
    check("((a|b)c)+", "acbc", True, "nested multi")
    check("((a|b)c)+", "ad", False, "nested miss")

    # Edge cases
    check("", "", True, "empty pattern")
    check("a", "", False, "empty text, non-empty pattern")

    print(f"\n  Thompson NFA Tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        pattern = sys.argv[1]
        text = sys.argv[2]
        result = match(pattern, text)
        print(f"match({pattern!r}, {text!r}) = {result}")
    else:
        print("Thompson NFA Regex Engine — Deliberate Practice Challenge")
        print("Running test suite...")
        success = _run_tests()
        sys.exit(0 if success else 1)
