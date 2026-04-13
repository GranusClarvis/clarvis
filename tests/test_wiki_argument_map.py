"""Tests for wiki argument mapper."""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "wiki"))
from wiki_argument_map import (
    ArgumentNode,
    ArgumentEdge,
    ArgumentGraph,
    RelationType,
    _extract_sections,
    _classify_claim_role,
    _detect_relation,
    extract_argument_graph,
    render_ascii,
)


# ── Section extraction tests ─────────────────────────────────────

class TestExtractSections:
    def test_extracts_key_claims(self):
        content = """## Key Claims

- Neural networks can approximate any function
- Deep learning requires large datasets

## Evidence

- **[Source]**: Some paper
"""
        sections = _extract_sections(content)
        assert "Key Claims" in sections
        assert len(sections["Key Claims"]) == 2

    def test_skips_placeholders(self):
        content = """## Key Claims

- _Claims pending extraction._

## Evidence
"""
        sections = _extract_sections(content)
        assert sections.get("Key Claims", []) == []

    def test_extracts_multiple_sections(self):
        content = """## Key Claims

- Claim one here is valid

## Evidence

- **[Paper]**: Source reference here

## Limitations

- Limited to small datasets only
"""
        sections = _extract_sections(content)
        assert len(sections["Key Claims"]) == 1
        assert len(sections["Evidence"]) == 1
        assert len(sections["Limitations"]) == 1


# ── Claim role classification tests ──────────────────────────────

class TestClassifyClaimRole:
    def test_conclusion_signal(self):
        assert _classify_claim_role("Therefore, the model is effective") == "conclusion"
        assert _classify_claim_role("This demonstrates clear improvement") == "conclusion"

    def test_premise_signal(self):
        assert _classify_claim_role("Because the data is clear") == "premise"
        assert _classify_claim_role("Since the sample size is large enough") == "premise"

    def test_qualifier_signal(self):
        assert _classify_claim_role("Unless the sample size is too small") == "qualifier"
        assert _classify_claim_role("Only if conditions are met") == "qualifier"

    def test_generic_claim(self):
        assert _classify_claim_role("Attention mechanisms improve performance") == "claim"


# ── Relation detection tests ─────────────────────────────────────

class TestDetectRelation:
    def test_rebuttal_detected(self):
        rel, conf = _detect_relation(
            "Models are effective",
            "However this contradicts prior work"
        )
        assert rel == RelationType.REBUTS

    def test_qualifier_detected(self):
        rel, conf = _detect_relation(
            "The method works",
            "Only if the dataset is clean"
        )
        assert rel == RelationType.QUALIFIES

    def test_default_supports(self):
        rel, conf = _detect_relation(
            "Data shows improvement",
            "Performance increased by 10%"
        )
        assert rel == RelationType.SUPPORTS


# ── Argument graph construction tests ────────────────────────────

class TestExtractArgumentGraph:
    def test_basic_graph(self):
        content = """---
title: Test
slug: test
---

## Key Claims

- Neural networks can learn representations
- Deep learning scales with data

## Evidence

- **[Paper]**: Original paper demonstrates this claim

## Limitations

- However, this requires massive compute resources
"""
        graph = extract_argument_graph("test", "Test", content, use_embeddings=False)
        assert len(graph.nodes) >= 3  # 2 claims + 1 evidence + 1 limitation
        assert len(graph.edges) >= 1

    def test_empty_page(self):
        content = """---
title: Empty
slug: empty
---

## Key Claims

- _No claims yet._

## Evidence
"""
        graph = extract_argument_graph("empty", "Empty", content, use_embeddings=False)
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0

    def test_evidence_supports_claims(self):
        content = """## Key Claims

- Model accuracy improves with more data

## Evidence

- **[Study]**: Large scale experiments confirm this finding
"""
        graph = extract_argument_graph("test", "Test", content, use_embeddings=False)
        support_edges = [e for e in graph.edges if e.relation == RelationType.SUPPORTS]
        assert len(support_edges) >= 1

    def test_limitations_rebut_claims(self):
        content = """## Key Claims

- The approach generalizes well

## Limitations

- However, performance degrades on out-of-domain data
"""
        graph = extract_argument_graph("test", "Test", content, use_embeddings=False)
        rebut_edges = [e for e in graph.edges if e.relation == RelationType.REBUTS]
        assert len(rebut_edges) >= 1

    def test_conclusion_identification(self):
        content = """## Key Claims

- Data shows consistent improvement
- Therefore the method is effective

## Evidence

- **[Experiment]**: Controlled trials show 15% gain
"""
        graph = extract_argument_graph("test", "Test", content, use_embeddings=False)
        conclusions = [n for n in graph.nodes if n.role == "conclusion"]
        assert len(conclusions) >= 1


# ── ASCII rendering tests ────────────────────────────────────────

class TestRenderAscii:
    def test_empty_graph(self):
        graph = ArgumentGraph(page_slug="test", page_title="Test")
        result = render_ascii(graph)
        assert "No argument structure" in result

    def test_renders_nodes(self):
        graph = ArgumentGraph(page_slug="test", page_title="Test Page")
        graph.add_node(ArgumentNode("c0", "Claim one", "claim"))
        graph.add_node(ArgumentNode("e0", "Evidence one", "premise"))
        graph.add_edge(ArgumentEdge("e0", "c0", RelationType.SUPPORTS, 0.5))
        result = render_ascii(graph)
        assert "Test Page" in result
        assert "Claim one" in result
        assert "Evidence one" in result
        assert "Nodes: 2" in result
        assert "supports: 1" in result

    def test_renders_rebuts(self):
        graph = ArgumentGraph(page_slug="t", page_title="T")
        graph.add_node(ArgumentNode("c0", "Main claim", "claim"))
        graph.add_node(ArgumentNode("l0", "But limitation", "qualifier"))
        graph.add_edge(ArgumentEdge("l0", "c0", RelationType.REBUTS, 0.4))
        result = render_ascii(graph)
        assert "rebuts:" in result


# ── ArgumentGraph data structure tests ───────────────────────────

class TestArgumentGraph:
    def test_to_dict(self):
        graph = ArgumentGraph(page_slug="test", page_title="Test")
        graph.add_node(ArgumentNode("n1", "Node 1", "claim"))
        graph.add_edge(ArgumentEdge("n1", "n2", RelationType.SUPPORTS, 0.5))
        d = graph.to_dict()
        assert d["page_slug"] == "test"
        assert len(d["nodes"]) == 1
        assert len(d["edges"]) == 1
        assert d["edges"][0]["relation"] == "supports"

    def test_node_short(self):
        node = ArgumentNode("n1", "A" * 100, "claim")
        assert len(node.short(60)) == 63  # 60 + "..."
        short_node = ArgumentNode("n2", "Short", "claim")
        assert short_node.short(60) == "Short"
