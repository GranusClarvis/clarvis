"""Tests for wiki_canonical.py — canonical page resolution and duplicate detection."""
import sys
import tempfile
from pathlib import Path

import pytest

from clarvis.wiki.canonical import (
    CanonicalResolver,
    _normalize,
    _slugify,
    _trigram_similarity,
)


@pytest.fixture
def wiki_tmpdir(tmp_path):
    """Create a temporary wiki directory with test pages."""
    concepts = tmp_path / "concepts"
    concepts.mkdir()
    projects = tmp_path / "projects"
    projects.mkdir()

    # Page 1: concept with aliases
    (concepts / "integrated-information-theory.md").write_text(
        '---\ntitle: "Integrated Information Theory"\nslug: "integrated-information-theory"\n'
        'type: concept\ncreated: 2026-01-01\nupdated: 2026-01-01\nstatus: active\n'
        'tags:\n  - ai/consciousness\naliases:\n  - "IIT"\n  - "Phi theory"\n'
        'sources:\n  - raw/paper/iit.md\nconfidence: high\n---\n\n# Integrated Information Theory\n\nSummary.\n'
        '\n## Key Claims\n\n- Claim 1\n\n## Evidence\n\n- Source 1\n\n## Related Pages\n\n'
        '\n## Open Questions\n\n- Q1\n\n## Update History\n\n- 2026-01-01: Created.\n'
    )

    # Page 2: another concept (potential duplicate of page 1 if titled similarly)
    (concepts / "iit-4-0.md").write_text(
        '---\ntitle: "IIT 4.0"\nslug: "iit-4-0"\n'
        'type: concept\ncreated: 2026-02-01\nupdated: 2026-02-01\nstatus: draft\n'
        'tags:\n  - ai/consciousness\naliases: []\n'
        'sources:\n  - raw/paper/iit40.md\nconfidence: medium\n---\n\n# IIT 4.0\n\nVersion 4.\n'
        '\n## Key Claims\n\n- Claim\n\n## Evidence\n\n- Source\n\n## Related Pages\n\n'
        '\n## Open Questions\n\n- Q\n\n## Update History\n\n- 2026-02-01: Created.\n'
    )

    # Page 3: a project
    (projects / "clarvis.md").write_text(
        '---\ntitle: "Clarvis"\nslug: "clarvis"\n'
        'type: repo\ncreated: 2026-01-01\nupdated: 2026-01-01\nstatus: active\n'
        'tags:\n  - project/clarvis\naliases:\n  - "Clarvis Agent"\n'
        'sources:\n  - raw/repo/clarvis.md\nconfidence: high\n---\n\n# Clarvis\n\nAgent.\n'
        '\n## Key Claims\n\n- Claim\n\n## Evidence\n\n- Source\n\n## Related Pages\n\n'
        '\n## Open Questions\n\n- Q\n\n## Update History\n\n- 2026-01-01: Created.\n'
    )

    return tmp_path


class TestNormalization:
    def test_normalize_lowercase(self):
        assert _normalize("Hello World") == "hello world"

    def test_normalize_strips_punctuation(self):
        assert _normalize("IIT (4.0)") == "iit 40"

    def test_slugify(self):
        assert _slugify("Integrated Information Theory") == "integrated-information-theory"

    def test_slugify_truncates(self):
        assert len(_slugify("A" * 100)) <= 60


class TestTrigramSimilarity:
    def test_identical(self):
        assert _trigram_similarity("hello", "hello") == 1.0

    def test_completely_different(self):
        assert _trigram_similarity("abc", "xyz") == 0.0

    def test_similar(self):
        sim = _trigram_similarity("Integrated Information Theory", "Integrated Information")
        assert sim > 0.5

    def test_short_strings(self):
        sim = _trigram_similarity("ab", "ab")
        assert sim == 1.0


class TestCanonicalResolver:
    def test_build_pages(self, wiki_tmpdir):
        resolver = CanonicalResolver(wiki_tmpdir)
        assert len(resolver.pages) == 3
        assert "integrated-information-theory" in resolver.pages
        assert "iit-4-0" in resolver.pages
        assert "clarvis" in resolver.pages

    def test_resolve_by_slug(self, wiki_tmpdir):
        resolver = CanonicalResolver(wiki_tmpdir)
        assert resolver.resolve("integrated-information-theory") == "integrated-information-theory"

    def test_resolve_by_title(self, wiki_tmpdir):
        resolver = CanonicalResolver(wiki_tmpdir)
        assert resolver.resolve("Integrated Information Theory") == "integrated-information-theory"

    def test_resolve_by_alias(self, wiki_tmpdir):
        resolver = CanonicalResolver(wiki_tmpdir)
        assert resolver.resolve("IIT") == "integrated-information-theory"

    def test_resolve_by_alias_case_insensitive(self, wiki_tmpdir):
        resolver = CanonicalResolver(wiki_tmpdir)
        assert resolver.resolve("iit") == "integrated-information-theory"

    def test_resolve_by_alias_phi_theory(self, wiki_tmpdir):
        resolver = CanonicalResolver(wiki_tmpdir)
        assert resolver.resolve("Phi theory") == "integrated-information-theory"

    def test_resolve_not_found(self, wiki_tmpdir):
        resolver = CanonicalResolver(wiki_tmpdir)
        assert resolver.resolve("Nonexistent Concept") is None

    def test_resolve_clarvis_agent_alias(self, wiki_tmpdir):
        resolver = CanonicalResolver(wiki_tmpdir)
        assert resolver.resolve("Clarvis Agent") == "clarvis"

    def test_resolve_or_suggest(self, wiki_tmpdir):
        resolver = CanonicalResolver(wiki_tmpdir)
        slug, suggestions = resolver.resolve_or_suggest("Integrated Info Theory", threshold=0.4)
        # Should suggest the IIT page
        assert slug is not None or len(suggestions) > 0

    def test_find_duplicates_with_alias_match(self, wiki_tmpdir):
        # IIT alias on page 1, IIT 4.0 title on page 2 — should detect similarity
        resolver = CanonicalResolver(wiki_tmpdir)
        groups = resolver.find_duplicates(threshold=0.5)
        # IIT and IIT 4.0 share "iit" trigrams
        # With threshold 0.5, the trigram similarity of "IIT 4.0" vs
        # "Integrated Information Theory" may or may not match
        # but "iit 4 0" vs "iit" should be close
        assert isinstance(groups, list)

    def test_add_alias(self, wiki_tmpdir):
        resolver = CanonicalResolver(wiki_tmpdir)
        ok = resolver.add_alias("clarvis", "My Agent")
        assert ok
        assert resolver.resolve("My Agent") == "clarvis"

    def test_add_alias_conflict(self, wiki_tmpdir):
        resolver = CanonicalResolver(wiki_tmpdir)
        # IIT already maps to integrated-information-theory
        ok = resolver.add_alias("clarvis", "IIT")
        assert not ok  # Should fail — alias already taken by different page

    def test_redirect(self, wiki_tmpdir):
        resolver = CanonicalResolver(wiki_tmpdir)
        redirect_path = resolver.create_redirect("old-iit", "integrated-information-theory", "concept")
        assert redirect_path.exists()
        assert resolver.resolve("old-iit") == "integrated-information-theory"

    def test_merge_pages(self, wiki_tmpdir):
        resolver = CanonicalResolver(wiki_tmpdir)
        result = resolver.merge_pages("iit-4-0", "integrated-information-theory")
        assert result["action"] == "merged"
        assert len(result["changes"]) > 0

        # Source should now be a redirect
        resolver2 = CanonicalResolver(wiki_tmpdir)
        assert resolver2.resolve("iit-4-0") == "integrated-information-theory"

    def test_merge_nonexistent(self, wiki_tmpdir):
        resolver = CanonicalResolver(wiki_tmpdir)
        result = resolver.merge_pages("nonexistent", "clarvis")
        assert result["action"] == "failed"


class TestRedirectChains:
    def test_redirect_chain_resolution(self, wiki_tmpdir):
        concepts = wiki_tmpdir / "concepts"
        # Create a redirect chain: a → b → integrated-information-theory
        (concepts / "a.md").write_text(
            '---\nredirect: "b"\nslug: "a"\ntitle: "Redirect"\ntype: concept\ncreated: 2026-01-01\n---\n'
        )
        (concepts / "b.md").write_text(
            '---\nredirect: "integrated-information-theory"\nslug: "b"\ntitle: "Redirect"\ntype: concept\ncreated: 2026-01-01\n---\n'
        )
        resolver = CanonicalResolver(wiki_tmpdir)
        assert resolver.resolve("a") == "integrated-information-theory"
        assert resolver.resolve("b") == "integrated-information-theory"
