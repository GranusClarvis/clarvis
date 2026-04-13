#!/usr/bin/env python3
"""Git-diff semantic analyzer — classifies hunks by change type.

Reads a git diff and classifies each hunk as: bugfix, feature, refactor,
test, docs, or config. Uses heuristics (file paths, changed line patterns,
commit message) — no LLM calls.

Usage:
    python3 scripts/challenges/git_diff_analyzer.py analyze [<commit>]
    python3 scripts/challenges/git_diff_analyzer.py batch [--last N]
    python3 scripts/challenges/git_diff_analyzer.py test
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Classification types
# ---------------------------------------------------------------------------

CATEGORIES = ["bugfix", "feature", "refactor", "test", "docs", "config"]


@dataclass
class Hunk:
    """A single diff hunk with metadata."""
    file_path: str
    added_lines: list[str] = field(default_factory=list)
    removed_lines: list[str] = field(default_factory=list)
    header: str = ""
    classification: str = ""
    confidence: float = 0.0
    signals: list[str] = field(default_factory=list)


@dataclass
class CommitAnalysis:
    """Analysis of a single commit."""
    sha: str
    message: str
    hunks: list[Hunk] = field(default_factory=list)
    overall_classification: str = ""
    category_counts: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Heuristic signals
# ---------------------------------------------------------------------------

# File path signals
PATH_SIGNALS = {
    "test": [
        r"tests?/", r"test_\w+\.py", r"_test\.py$", r"_test\.go$",
        r"\.test\.(js|ts|tsx)$", r"__tests__/", r"spec/",
    ],
    "docs": [
        r"\.md$", r"docs?/", r"README", r"CHANGELOG", r"LICENSE",
        r"\.rst$", r"\.txt$", r"CONTRIBUTING",
    ],
    "config": [
        r"\.json$", r"\.ya?ml$", r"\.toml$", r"\.ini$", r"\.cfg$",
        r"\.env", r"Makefile$", r"Dockerfile$", r"\.lock$",
        r"requirements.*\.txt$", r"package\.json$", r"setup\.py$",
        r"pyproject\.toml$", r"\.gitignore$", r"\.eslintrc",
        r"crontab", r"systemd", r"\.service$",
    ],
}

# Commit message signals
MESSAGE_SIGNALS = {
    "bugfix": [
        r"\bfix(es|ed|ing)?\b", r"\bbug\b", r"\bpatch\b", r"\bhotfix\b",
        r"\bresolve[sd]?\b", r"\bcorrect\b", r"\brepair\b", r"\bregression\b",
    ],
    "feature": [
        r"\badd(s|ed|ing)?\b", r"\bfeat(ure)?:", r"\bimplement\b",
        r"\bnew\b", r"\bintroduce\b", r"\bcreate\b", r"\bbuild\b",
        r"\bwire\b", r"\benable\b",
    ],
    "refactor": [
        r"\brefactor\b", r"\bclean\s*up\b", r"\brestructure\b",
        r"\brename\b", r"\bmove\b", r"\bmigrate\b", r"\bconsolidate\b",
        r"\bsimplif\b", r"\breorganize\b", r"\bextract\b",
    ],
    "test": [
        r"\btest\b", r"\bspec\b", r"\bcoverage\b", r"\bassert\b",
    ],
    "docs": [
        r"\bdocs?\b", r"\bdocument\b", r"\breadme\b", r"\bcomment\b",
        r"\bdiagram\b", r"\bmermaid\b",
    ],
    "config": [
        r"\bconfig\b", r"\bci\b", r"\bci/cd\b", r"\bcron\b",
        r"\bdeploy\b", r"\binfra\b", r"\bsetup\b", r"\bchore\b",
    ],
}

# Content signals (in added/removed lines)
CONTENT_SIGNALS = {
    "bugfix": [
        r"\bif .+ is None\b", r"\btry:", r"\bexcept\b", r"\braise\b",
        r"!=\s*None", r"\bassert\b", r"# ?fix", r"# ?bug",
        r"\bfallback\b", r"\bguard\b", r"\bdefault\b",
    ],
    "feature": [
        r"\bdef \w+", r"\bclass \w+", r"\bimport\b", r"\bfrom .+ import\b",
        r"\basync def\b", r"\bprint\(", r"\blogger\.",
    ],
    "refactor": [
        r"# ?(removed|deprecated|legacy|old)", r"\bpass$",
    ],
    "test": [
        r"\bdef test_", r"\bassert\w*\(", r"@pytest", r"\bmock\b",
        r"\bfixture\b", r"assertEqual", r"assertTrue",
    ],
    "docs": [
        r'"""', r"'''", r"^#\s+", r"\bTODO\b", r"\bNOTE\b",
    ],
    "config": [
        r'"[^"]+"\s*:', r"\bversion\b", r"\bdependenc", r"\bscript\b",
    ],
}


def _score_patterns(text: str, patterns: list[str]) -> int:
    """Count how many patterns match in text."""
    score = 0
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE | re.MULTILINE):
            score += 1
    return score


# ---------------------------------------------------------------------------
# Diff parsing
# ---------------------------------------------------------------------------

def parse_diff(diff_text: str) -> list[Hunk]:
    """Parse unified diff text into Hunk objects."""
    hunks = []
    current_file = ""
    current_hunk = None

    for line in diff_text.split("\n"):
        # New file
        if line.startswith("diff --git"):
            match = re.search(r"b/(.+)$", line)
            if match:
                current_file = match.group(1)

        # Hunk header
        elif line.startswith("@@"):
            if current_hunk and (current_hunk.added_lines or current_hunk.removed_lines):
                hunks.append(current_hunk)
            current_hunk = Hunk(file_path=current_file, header=line)

        # Added line
        elif line.startswith("+") and not line.startswith("+++"):
            if current_hunk:
                current_hunk.added_lines.append(line[1:])

        # Removed line
        elif line.startswith("-") and not line.startswith("---"):
            if current_hunk:
                current_hunk.removed_lines.append(line[1:])

    if current_hunk and (current_hunk.added_lines or current_hunk.removed_lines):
        hunks.append(current_hunk)

    return hunks


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_hunk(hunk: Hunk, commit_message: str = "") -> Hunk:
    """Classify a single hunk using heuristic signals."""
    scores = {cat: 0.0 for cat in CATEGORIES}
    signals = []

    # 1. File path signals (strong weight)
    for cat, patterns in PATH_SIGNALS.items():
        for pat in patterns:
            if re.search(pat, hunk.file_path, re.IGNORECASE):
                scores[cat] += 3.0
                signals.append(f"path:{cat}")
                break

    # 2. Commit message signals (medium weight)
    if commit_message:
        for cat, patterns in MESSAGE_SIGNALS.items():
            msg_score = _score_patterns(commit_message, patterns)
            if msg_score > 0:
                scores[cat] += msg_score * 2.0
                signals.append(f"msg:{cat}({msg_score})")

    # 3. Content signals (from added + removed lines)
    all_content = "\n".join(hunk.added_lines + hunk.removed_lines)
    for cat, patterns in CONTENT_SIGNALS.items():
        content_score = _score_patterns(all_content, patterns)
        if content_score > 0:
            scores[cat] += content_score * 1.0
            signals.append(f"content:{cat}({content_score})")

    # 4. Structural heuristics
    n_added = len(hunk.added_lines)
    n_removed = len(hunk.removed_lines)

    # Pure additions suggest feature
    if n_added > 0 and n_removed == 0:
        scores["feature"] += 1.5
        signals.append("struct:pure_add")

    # Balanced add/remove suggests refactor
    if n_added > 0 and n_removed > 0:
        ratio = min(n_added, n_removed) / max(n_added, n_removed)
        if ratio > 0.5:
            scores["refactor"] += 1.0
            signals.append("struct:balanced")

    # Small targeted changes suggest bugfix
    if 0 < (n_added + n_removed) <= 5:
        scores["bugfix"] += 0.5
        signals.append("struct:small_change")

    # Pick the winner
    best_cat = max(scores, key=scores.get)
    total = sum(scores.values())
    confidence = scores[best_cat] / total if total > 0 else 0.0

    # Default to "feature" if nothing matched
    if total == 0:
        best_cat = "feature"
        confidence = 0.3

    hunk.classification = best_cat
    hunk.confidence = round(confidence, 2)
    hunk.signals = signals

    return hunk


def analyze_commit(sha: str = "HEAD") -> CommitAnalysis:
    """Analyze a single commit's diff."""
    # Get commit message
    msg_result = subprocess.run(
        ["git", "log", "-1", "--format=%s", sha],
        capture_output=True, text=True, cwd="."
    )
    message = msg_result.stdout.strip()

    # Get diff
    diff_result = subprocess.run(
        ["git", "diff", f"{sha}~1..{sha}", "--unified=3"],
        capture_output=True, text=True, cwd="."
    )
    diff_text = diff_result.stdout

    if not diff_text:
        # Might be initial commit
        diff_result = subprocess.run(
            ["git", "diff", "--root", sha, "--unified=3"],
            capture_output=True, text=True, cwd="."
        )
        diff_text = diff_result.stdout

    hunks = parse_diff(diff_text)
    for hunk in hunks:
        classify_hunk(hunk, message)

    # Overall classification = most common hunk category
    counts = Counter(h.classification for h in hunks)
    overall = counts.most_common(1)[0][0] if counts else "unknown"

    return CommitAnalysis(
        sha=sha,
        message=message,
        hunks=hunks,
        overall_classification=overall,
        category_counts=dict(counts),
    )


def analyze_batch(last_n: int = 20) -> list[CommitAnalysis]:
    """Analyze the last N commits."""
    result = subprocess.run(
        ["git", "log", f"--max-count={last_n}", "--format=%H"],
        capture_output=True, text=True, cwd="."
    )
    shas = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]

    analyses = []
    for sha in shas:
        try:
            analysis = analyze_commit(sha)
            analyses.append(analysis)
        except Exception as e:
            print(f"  Error analyzing {sha[:8]}: {e}")

    return analyses


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test():
    """Run test suite."""
    print("Git-diff semantic analyzer — test suite\n")
    passed = 0
    failed = 0

    def check(name, condition):
        nonlocal passed, failed
        if condition:
            passed += 1
        else:
            failed += 1
            print(f"  FAIL: {name}")

    # Test diff parsing
    sample_diff = """diff --git a/tests/test_foo.py b/tests/test_foo.py
--- a/tests/test_foo.py
+++ b/tests/test_foo.py
@@ -1,3 +1,5 @@
+import pytest
+
 def test_basic():
-    assert True
+    assert foo() == 42
+    assert foo(None) is None
"""
    hunks = parse_diff(sample_diff)
    check("parse_diff returns hunks", len(hunks) == 1)
    check("parse_diff file path", hunks[0].file_path == "tests/test_foo.py")
    check("parse_diff added lines", len(hunks[0].added_lines) == 4)
    check("parse_diff removed lines", len(hunks[0].removed_lines) == 1)

    # Test classification: test file
    classify_hunk(hunks[0], "add test for foo")
    check("classify test file as test", hunks[0].classification == "test")

    # Test classification: config file
    config_hunk = Hunk(
        file_path="pyproject.toml",
        added_lines=['"numpy>=1.24"', '"version": "2.0.0"'],
        removed_lines=['"numpy>=1.23"'],
    )
    classify_hunk(config_hunk, "chore: bump numpy version")
    check("classify config file as config", config_hunk.classification == "config")

    # Test classification: docs
    doc_hunk = Hunk(
        file_path="README.md",
        added_lines=["# New Section", "Documentation for the feature"],
        removed_lines=[],
    )
    classify_hunk(doc_hunk, "docs: update readme")
    check("classify docs file as docs", doc_hunk.classification == "docs")

    # Test classification: bugfix
    fix_hunk = Hunk(
        file_path="src/handler.py",
        added_lines=["    if value is None:", "        return default"],
        removed_lines=["    return value.process()"],
    )
    classify_hunk(fix_hunk, "fix: handle None value in handler")
    check("classify bugfix", fix_hunk.classification == "bugfix")

    # Test classification: feature (new function)
    feat_hunk = Hunk(
        file_path="src/api.py",
        added_lines=[
            "def get_user(user_id):",
            "    from database import query",
            "    return query('SELECT * FROM users WHERE id = ?', user_id)",
        ],
        removed_lines=[],
    )
    classify_hunk(feat_hunk, "add user lookup endpoint")
    check("classify feature", feat_hunk.classification == "feature")

    # Test classification: refactor (balanced add/remove)
    refactor_hunk = Hunk(
        file_path="src/utils.py",
        added_lines=["def compute(x): return x * 2", "def transform(x): return compute(x) + 1"],
        removed_lines=["def old_compute(x): return x * 2", "def old_transform(x): return old_compute(x) + 1"],
    )
    classify_hunk(refactor_hunk, "refactor: rename utility functions")
    check("classify refactor", refactor_hunk.classification == "refactor")

    # Test empty hunk
    empty_hunk = Hunk(file_path="unknown.xyz", added_lines=[], removed_lines=[])
    # Should not crash
    parse_result = parse_diff("")
    check("empty diff returns empty list", len(parse_result) == 0)

    # Test multi-file diff
    multi_diff = """diff --git a/src/a.py b/src/a.py
@@ -1,1 +1,2 @@
+import os
 x = 1
diff --git a/tests/test_b.py b/tests/test_b.py
@@ -1,1 +1,2 @@
+def test_b(): pass
 pass
"""
    multi_hunks = parse_diff(multi_diff)
    check("multi-file parse", len(multi_hunks) == 2)
    check("multi-file path 1", multi_hunks[0].file_path == "src/a.py")
    check("multi-file path 2", multi_hunks[1].file_path == "tests/test_b.py")

    # Test analyze on real commits
    print("\n  Testing against real commits...")
    try:
        analyses = analyze_batch(last_n=20)
        check("batch analysis returns results", len(analyses) > 0)

        # Print summary
        all_cats = Counter()
        for a in analyses:
            all_cats.update(a.category_counts)
            print(f"    {a.sha[:8]} [{a.overall_classification:8s}] {a.message[:60]}")

        print(f"\n  Category distribution across {len(analyses)} commits:")
        for cat, count in all_cats.most_common():
            print(f"    {cat:10s}: {count} hunks")

        check("all categories are valid",
              all(cat in CATEGORIES for a in analyses for cat in a.category_counts))
    except Exception as e:
        print(f"    Skipped real commit analysis: {e}")

    print(f"\n  Results: {passed} passed, {failed} failed")
    return failed == 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: git_diff_analyzer.py analyze [<commit>] | batch [--last N] | test")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "test":
        success = test()
        sys.exit(0 if success else 1)

    elif cmd == "analyze":
        sha = sys.argv[2] if len(sys.argv) > 2 else "HEAD"
        analysis = analyze_commit(sha)
        print(f"Commit: {analysis.sha[:8]} — {analysis.message}")
        print(f"Overall: {analysis.overall_classification}")
        print(f"Hunks: {len(analysis.hunks)}")
        for h in analysis.hunks:
            print(f"  [{h.classification:8s}] ({h.confidence:.0%}) {h.file_path}")
            if h.signals:
                print(f"             signals: {', '.join(h.signals)}")

    elif cmd == "batch":
        n = 20
        if "--last" in sys.argv:
            idx = sys.argv.index("--last")
            if idx + 1 < len(sys.argv):
                n = int(sys.argv[idx + 1])
        analyses = analyze_batch(last_n=n)
        cats = Counter()
        for a in analyses:
            cats.update(a.category_counts)
            print(f"  {a.sha[:8]} [{a.overall_classification:8s}] {a.message[:70]}")
        print(f"\nDistribution ({sum(cats.values())} hunks):")
        for cat, count in cats.most_common():
            pct = count / sum(cats.values()) * 100
            print(f"  {cat:10s}: {count:3d} ({pct:.0f}%)")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
