"""Tests for research_to_queue.py — scan, classify, format, inject pipeline.

Covers: _extract_actionable_sections, classify_disposition, _score_proposal,
_is_covered, _word_overlap, format_queue_item, scan_papers, _extract_paper_title,
_extract_paper_source.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import _paths  # noqa: F401,E402
from research_to_queue import (
    _extract_actionable_sections,
    _extract_paper_source,
    _extract_paper_title,
    _extract_queue_items,
    _is_covered,
    _score_proposal,
    _word_overlap,
    _word_set,
    classify_disposition,
    format_queue_item,
    scan_papers,
)


# --- _word_set / _word_overlap ---


class TestWordOverlap:
    def test_identical_texts(self):
        assert _word_overlap("implement brain search", "implement brain search") == 1.0

    def test_disjoint_texts(self):
        assert _word_overlap("implement brain search", "deploy server config") == 0.0

    def test_partial_overlap(self):
        score = _word_overlap("implement brain search recall", "brain search optimization")
        assert 0.3 < score < 1.0

    def test_empty_text(self):
        assert _word_overlap("", "something") == 0.0
        assert _word_overlap("something", "") == 0.0

    def test_stopwords_excluded(self):
        words = _word_set("the a an is are to of in for with")
        assert len(words) == 0

    def test_short_words_excluded(self):
        words = _word_set("go do if be")
        assert len(words) == 0

    def test_meaningful_words_kept(self):
        words = _word_set("implement brain search recall optimization")
        assert "implement" in words
        assert "brain" in words


# --- _extract_paper_title / _extract_paper_source ---


class TestPaperExtraction:
    def test_title_from_h1(self):
        content = "# SParC-RAG: Sequential-Parallel Scaling\n\nSome text."
        assert _extract_paper_title(content) == "SParC-RAG: Sequential-Parallel Scaling"

    def test_title_unknown_if_missing(self):
        assert _extract_paper_title("No heading here") == "Unknown"

    def test_source_arxiv(self):
        content = "Paper on arXiv:2602.00083 describes..."
        assert _extract_paper_source(content) == "arXiv:2602.00083"

    def test_source_with_bold_label(self):
        content = "**Source**: https://example.com/paper"
        assert _extract_paper_source(content) == "https://example.com/paper"

    def test_source_empty_if_missing(self):
        assert _extract_paper_source("No source info") == ""


# --- _extract_queue_items ---


class TestExtractQueueItems:
    def test_extracts_checked_and_unchecked(self):
        content = "- [ ] Task A\n- [x] Task B\n- [~] Task C\n"
        items = _extract_queue_items(content)
        assert len(items) == 3

    def test_ignores_non_task_lines(self):
        content = "## Heading\nSome text\n- [ ] Real task\n"
        items = _extract_queue_items(content)
        assert len(items) == 1

    def test_lowercases_items(self):
        items = _extract_queue_items("- [ ] UPPERCASE TASK")
        assert items[0] == "uppercase task"


# --- _extract_actionable_sections ---


class TestExtractActionableSections:
    def test_extracts_from_improvement_proposals(self):
        content = """# Paper Title

## Background
Some background text.

## Improvement Proposals

1. **Query Rewriter**: Add diversity-aware query expansion to brain search (40+ chars here)
2. **Context Manager**: Implement cross-round evidence consolidation in assembly.py

## Conclusion
End.
"""
        proposals = _extract_actionable_sections(content)
        assert len(proposals) >= 2
        assert any("Query Rewriter" in p for p in proposals)

    def test_extracts_from_application_to_clarvis(self):
        content = """# Paper

## Application to Clarvis

- **Pruning module**: Add task-aware context pruning before assembly step (reduces tokens significantly)
"""
        proposals = _extract_actionable_sections(content)
        assert len(proposals) >= 1

    def test_ignores_non_actionable_sections(self):
        content = """# Paper

## Related Work
- Some related work item about something or other

## Methodology
1. First we do this important step of the research
"""
        proposals = _extract_actionable_sections(content)
        assert len(proposals) == 0

    def test_skips_short_items(self):
        content = """# Paper
## Improvement Proposals
- Short
- **X**: tiny
"""
        proposals = _extract_actionable_sections(content)
        assert len(proposals) == 0  # all under 20 chars

    def test_multiple_actionable_sections(self):
        content = """# Paper
## Key Insights
1. **Insight A**: This is a detailed insight about improving retrieval quality (40+ chars)
## Actionable Patterns
1. **Pattern B**: Another detailed pattern about context management and filtering (40+ chars)
"""
        proposals = _extract_actionable_sections(content)
        assert len(proposals) >= 2


# --- classify_disposition ---


class TestClassifyDisposition:
    def test_covered_is_discard(self):
        disp, reason = classify_disposition("implement brain search recall optimization", covered=True)
        assert disp == "discard"
        assert "already covered" in reason

    def test_short_is_discard(self):
        disp, _ = classify_disposition("too short", covered=False)
        assert disp == "discard"

    def test_theoretical_is_discard(self):
        disp, reason = classify_disposition(
            "theoretical conceptual framework for future work and speculative ideas about philosophy",
            covered=False,
        )
        assert disp == "discard"
        assert "theory-only" in reason

    def test_benchmark_keywords(self):
        disp, _ = classify_disposition(
            "measure retrieval quality metric score and latency threshold improvements",
            covered=False,
        )
        assert disp == "benchmark_target"

    def test_code_change_keywords(self):
        disp, _ = classify_disposition(
            "modify search.py function to implement new recall() method with integration",
            covered=False,
        )
        assert disp == "code_change"

    def test_general_actionable_is_queue_item(self):
        disp, _ = classify_disposition(
            "a reasonably long proposal about adding something useful to the system that doesn't match other categories",
            covered=False,
        )
        assert disp == "queue_item"

    def test_all_dispositions_are_valid(self):
        from research_to_queue import DISPOSITIONS
        test_cases = [
            ("short", False),
            ("implement brain search.py function recall method module class integration", False),
            ("measure metric benchmark score latency threshold improvements", False),
            ("covered already", True),
            ("a reasonably long generic proposal about doing something useful and meaningful", False),
        ]
        for text, covered in test_cases:
            disp, _ = classify_disposition(text, covered)
            assert disp in DISPOSITIONS, f"Invalid disposition {disp} for '{text}'"


# --- _score_proposal ---


class TestScoreProposal:
    def test_base_score(self):
        score = _score_proposal("a reasonable proposal about some change")
        assert 0.4 <= score <= 0.6

    def test_high_impact_boosts(self):
        base = _score_proposal("a reasonable proposal about some change")
        boosted = _score_proposal("a high impact proposal about some change")
        assert boosted > base

    def test_code_quality_boosts(self):
        base = _score_proposal("a reasonable proposal about some change")
        boosted = _score_proposal("a reasonable proposal about code quality improvement")
        assert boosted > base

    def test_short_penalty(self):
        score = _score_proposal("short")
        assert score < 0.5

    def test_score_clamped(self):
        score = _score_proposal("high impact code quality directly low effort amazing")
        assert score <= 1.0
        score2 = _score_proposal("x")
        assert score2 >= 0.0


# --- _is_covered ---


class TestIsCovered:
    def test_covered_by_exact_match(self):
        items = ["implement brain search recall optimization"]
        assert _is_covered("implement brain search recall optimization", items)

    def test_not_covered_by_unrelated(self):
        items = ["deploy kubernetes cluster monitoring"]
        assert not _is_covered("implement brain search recall", items)

    def test_threshold_behavior(self):
        items = ["implement brain search recall optimization module"]
        # Similar enough
        assert _is_covered("implement brain search recall improvements", items)


# --- format_queue_item ---


class TestFormatQueueItem:
    def test_basic_format(self):
        result = {
            "paper": "SParC-RAG Paper",
            "paper_file": "sparc_rag.md",
            "source": "arXiv:2602.00083",
            "proposal": "Add query rewriting to brain search",
            "score": 0.7,
            "disposition": "code_change",
        }
        formatted = format_queue_item(result)
        assert "[RESEARCH_SPARC_RAG]" in formatted
        assert "[CODE]" in formatted
        assert "SParC-RAG Paper" in formatted
        assert "arXiv:2602.00083" in formatted

    def test_benchmark_label(self):
        result = {
            "paper": "Test", "paper_file": "test.md", "source": "",
            "proposal": "Something", "score": 0.5, "disposition": "benchmark_target",
        }
        assert "[BENCH]" in format_queue_item(result)

    def test_queue_item_label(self):
        result = {
            "paper": "Test", "paper_file": "test.md", "source": "",
            "proposal": "Something", "score": 0.5, "disposition": "queue_item",
        }
        assert "[TASK]" in format_queue_item(result)

    def test_long_proposal_truncated(self):
        result = {
            "paper": "Test", "paper_file": "test.md", "source": "",
            "proposal": "X" * 250, "score": 0.5, "disposition": "code_change",
        }
        formatted = format_queue_item(result)
        assert "..." in formatted
        assert len(formatted) < 400

    def test_long_tag_truncated(self):
        result = {
            "paper": "Test", "paper_file": "a_very_long_filename_that_exceeds_thirty_characters_total.md",
            "source": "", "proposal": "Something", "score": 0.5, "disposition": "code_change",
        }
        formatted = format_queue_item(result)
        # Tag should be at most 30 chars
        import re
        tag_match = re.search(r"\[RESEARCH_([A-Z_]+)\]", formatted)
        assert tag_match
        assert len(tag_match.group(1)) <= 30

    def test_bold_markdown_stripped(self):
        result = {
            "paper": "Test", "paper_file": "test.md", "source": "",
            "proposal": "**Bold** proposal text", "score": 0.5, "disposition": "code_change",
        }
        formatted = format_queue_item(result)
        assert "**" not in formatted


# --- scan_papers (integration) ---


class TestScanPapers:
    def test_scan_with_temp_dir(self, tmp_path, monkeypatch):
        """Scan a temporary directory with a synthetic paper."""
        ingested = tmp_path / "ingested"
        ingested.mkdir()

        paper = ingested / "test_paper.md"
        paper.write_text("""# Test Paper on RAG Improvements

## Abstract
A paper about retrieval augmented generation improvements.

## Improvement Proposals

1. **Context Pruning**: Add task-aware context pruning to assembly.py to reduce irrelevant tokens before LLM (more than 20 chars here)
2. **Query Expansion**: Implement diversity-aware query expansion in brain search.py recall function (more than 20 chars)

## Conclusion
This concludes our paper.
""")

        queue = tmp_path / "QUEUE.md"
        queue.write_text("- [ ] Some unrelated task\n")
        archive = tmp_path / "ARCHIVE.md"
        archive.write_text("")

        monkeypatch.setattr("research_to_queue.INGESTED_DIR", str(ingested))
        monkeypatch.setattr("research_to_queue.QUEUE_FILE", str(queue))
        monkeypatch.setattr("research_to_queue.ARCHIVE_FILE", str(archive))

        results = scan_papers()
        assert len(results) >= 2
        # Should be sorted: actionable first
        assert results[0]["disposition"] != "discard" or all(
            r["disposition"] == "discard" for r in results
        )

    def test_scan_empty_dir(self, tmp_path, monkeypatch):
        ingested = tmp_path / "empty"
        ingested.mkdir()
        monkeypatch.setattr("research_to_queue.INGESTED_DIR", str(ingested))
        results = scan_papers()
        assert results == []

    def test_scan_missing_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("research_to_queue.INGESTED_DIR", str(tmp_path / "nonexistent"))
        results = scan_papers()
        assert results == []
