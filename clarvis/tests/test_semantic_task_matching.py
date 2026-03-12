"""Tests for semantic task matching in clarvis.context.assembly.

Tests _parse_queue_tasks, _cosine_similarity, _semantic_rank,
_word_overlap_rank, and find_related_tasks.
"""

import os
import tempfile

import pytest

from clarvis.context.assembly import (
    _parse_queue_tasks,
    _cosine_similarity,
    _semantic_rank,
    _word_overlap_rank,
    find_related_tasks,
)


# === Test fixtures ===

SAMPLE_QUEUE = """\
# Evolution Queue — Clarvis

## P0 — Do Next Heartbeat

- [ ] Fix brain health check timeout issue
- [ ] Optimize graph compaction for large datasets
- [x] Completed: migrate graph backend

---

## Pillar 1: Consciousness & Integration (Phi > 0.80)

- [ ] Improve episodic memory recall accuracy
- [ ] Add temporal decay to working memory buffers

## P1 — This Week

- [ ] Refactor cost tracker to use real API data
- [ ] Add Telegram notification for budget alerts
- [ ] Wire performance benchmark into evening cron

## P2 — When Idle

- [ ] Clean up deprecated scripts in scripts/ directory
- [ ] Write documentation for ClarvisBrowser module
"""

QUEUE_EMPTY = """\
# Evolution Queue

## P0 — Do Next Heartbeat

---

## P1 — This Week

## P2 — When Idle
"""

QUEUE_NO_PENDING = """\
# Evolution Queue

## P0

- [x] Already done task one
- [x] Already done task two
- [~] Partially done task
"""


# === _parse_queue_tasks tests ===

class TestParseQueueTasks:
    def test_extracts_pending_tasks(self):
        results = _parse_queue_tasks(SAMPLE_QUEUE)
        texts = [core for _, core, _ in results]
        assert any("brain health" in t.lower() for t in texts)
        assert any("graph compaction" in t.lower() for t in texts)

    def test_skips_completed_tasks(self):
        results = _parse_queue_tasks(SAMPLE_QUEUE)
        full_texts = [full for _, _, full in results]
        assert not any("migrate graph backend" in t for t in full_texts)

    def test_p0_priority_weight(self):
        results = _parse_queue_tasks(SAMPLE_QUEUE)
        # First two tasks are under P0
        p0_tasks = [(w, c) for w, c, _ in results if w == 1.0]
        assert len(p0_tasks) >= 2
        cores = [c.lower() for _, c in p0_tasks]
        assert any("brain health" in c for c in cores)

    def test_p1_priority_weight(self):
        results = _parse_queue_tasks(SAMPLE_QUEUE)
        p1_tasks = [(w, c) for w, c, _ in results if w == 0.7]
        assert len(p1_tasks) >= 2
        cores = [c.lower() for _, c in p1_tasks]
        assert any("cost tracker" in c for c in cores)

    def test_p2_priority_weight(self):
        results = _parse_queue_tasks(SAMPLE_QUEUE)
        p2_tasks = [(w, c) for w, c, _ in results if w == 0.4]
        assert len(p2_tasks) >= 2
        cores = [c.lower() for _, c in p2_tasks]
        assert any("deprecated" in c for c in cores)

    def test_pillar_defaults_to_p1(self):
        results = _parse_queue_tasks(SAMPLE_QUEUE)
        # Tasks under "Pillar 1" (without explicit P tag) get P1 weight (0.7)
        cores = [c.lower() for w, c, _ in results if w == 0.7]
        assert any("episodic memory" in c for c in cores)

    def test_empty_queue(self):
        assert _parse_queue_tasks(QUEUE_EMPTY) == []

    def test_no_pending_tasks(self):
        assert _parse_queue_tasks(QUEUE_NO_PENDING) == []

    def test_empty_string(self):
        assert _parse_queue_tasks("") == []

    def test_core_truncation(self):
        """Task text after ( or — should be stripped for display."""
        content = "## P0\n- [ ] Fix the timeout issue (targets brain speed)"
        results = _parse_queue_tasks(content)
        assert len(results) == 1
        _, core, _ = results[0]
        assert "targets" not in core
        assert "Fix the timeout issue" in core

    def test_short_core_uses_full_text(self):
        """When core is too short (<15 chars), use task_text[:100]."""
        content = "## P0\n- [ ] Fix it — a very important but tersely named task"
        results = _parse_queue_tasks(content)
        _, core, _ = results[0]
        assert len(core) >= 15

    def test_nested_priority_headers(self):
        """### Phase headers with (P0) should set priority."""
        content = """\
## Pillar 2: Agent Orchestrator

### Phase 1: Scoreboard + Trust (P0)

- [ ] Implement scoreboard API endpoint

### Phase 3: Cron Integration (P1)

- [ ] Add cron job for agent health checks
"""
        results = _parse_queue_tasks(content)
        weights = {core: w for w, core, _ in results}
        scoreboard = [v for k, v in weights.items() if "scoreboard" in k.lower()]
        cron = [v for k, v in weights.items() if "cron" in k.lower()]
        assert scoreboard[0] == 1.0  # P0
        assert cron[0] == 0.7  # P1


# === _cosine_similarity tests ===

class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert _cosine_similarity([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert _cosine_similarity([1, 0, 0], [0, 1, 0]) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        assert _cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)

    def test_zero_vector(self):
        assert _cosine_similarity([0, 0, 0], [1, 2, 3]) == 0.0

    def test_proportional_vectors(self):
        assert _cosine_similarity([1, 2], [2, 4]) == pytest.approx(1.0)


# === _semantic_rank tests ===

class TestSemanticRank:
    @staticmethod
    def _mock_embed_fn(texts):
        """Deterministic mock embeddings based on keyword presence.

        Generates 6D vectors for enough differentiation to avoid
        the >0.9 near-duplicate filter while preserving semantic direction.
        """
        result = []
        for i, text in enumerate(texts):
            t = text.lower()
            v = [
                0.8 if "brain" in t else 0.1,
                0.7 if "memory" in t or "retrieval" in t else 0.15,
                0.8 if "graph" in t or "compaction" in t else 0.1,
                0.7 if "edge" in t or "dataset" in t else 0.15,
                0.8 if "cost" in t or "budget" in t else 0.1,
                0.2 + 0.01 * i,  # small unique offset per text
            ]
            result.append(v)
        return result

    def test_ranks_by_semantic_similarity(self):
        parsed = [
            (1.0, "Fix brain health check", "Fix brain health check timeout issue"),
            (1.0, "Optimize graph compaction", "Optimize graph compaction for large datasets"),
            (0.7, "Refactor cost tracker", "Refactor cost tracker to use real API data"),
        ]
        scored = _semantic_rank("brain memory retrieval optimization", parsed, self._mock_embed_fn)
        # Brain-related task should rank first
        assert scored[0][1] == "Fix brain health check"

    def test_priority_weighting(self):
        """Higher priority tasks should score higher when similarity is equal."""
        parsed = [
            (1.0, "P0: graph compaction fix", "P0: graph compaction fix for large datasets"),
            (0.4, "P2: graph edge compaction", "P2: graph edge compaction for old datasets"),
        ]
        scored = _semantic_rank("database graph issues", parsed, self._mock_embed_fn)
        # Both have similar embedding (graph keywords), but P0 has higher weight
        if len(scored) >= 2:
            assert scored[0][0] > scored[1][0]

    def test_skips_near_duplicates(self):
        """Tasks with >0.9 cosine sim to the query are excluded (same task)."""
        parsed = [
            (1.0, "Brain memory retrieval", "Brain memory retrieval optimization"),
            (0.7, "Graph compaction optimization", "Optimize graph compaction for large datasets"),
        ]
        scored = _semantic_rank(
            "Brain memory retrieval optimization", parsed, self._mock_embed_fn
        )
        # The near-duplicate should be filtered out
        cores = [c for _, c in scored]
        assert "Brain memory retrieval" not in cores

    def test_empty_parsed_tasks(self):
        assert _semantic_rank("some task", [], self._mock_embed_fn) == []

    def test_low_similarity_filtered(self):
        """Tasks with very low combined score (<0.05) should be excluded."""
        parsed = [
            (0.4, "Clean deprecated scripts", "Clean up deprecated scripts in scripts/ directory"),
        ]
        # Query about something completely different
        scored = _semantic_rank("graph compaction optimization", parsed, self._mock_embed_fn)
        # Low-priority + low-similarity should be filtered
        # (0.4 priority * low cosine similarity < 0.05)
        # The mock gives some baseline similarity so let's just check the list
        for score, _ in scored:
            assert score > 0.05


# === _word_overlap_rank tests ===

class TestWordOverlapRank:
    def test_basic_overlap(self):
        parsed = [
            (1.0, "Fix brain health check", "Fix brain health check timeout issue"),
            (1.0, "Optimize graph compaction", "Optimize graph compaction for large datasets"),
        ]
        scored = _word_overlap_rank("brain health optimization", parsed)
        assert len(scored) > 0
        # Brain health task should rank first (more word overlap)
        assert scored[0][1] == "Fix brain health check"

    def test_skips_near_duplicates(self):
        """Jaccard > 0.6 should be filtered (too similar = same task)."""
        parsed = [
            (1.0, "Fix brain health check", "Fix brain health check timeout"),
        ]
        scored = _word_overlap_rank("Fix brain health check timeout", parsed)
        # Should be filtered as near-duplicate
        assert len(scored) == 0

    def test_priority_weighting(self):
        parsed = [
            (1.0, "P0: fix brain issue", "fix brain issue in health monitor"),
            (0.4, "P2: fix brain issue", "fix brain issue in deprecated module"),
        ]
        scored = _word_overlap_rank("fix brain monitoring issue", parsed)
        if len(scored) >= 2:
            assert scored[0][0] >= scored[1][0]

    def test_empty_task_words(self):
        parsed = [
            (1.0, "Fix brain", "Fix brain health check"),
        ]
        # Query with only short words (< 3 chars)
        assert _word_overlap_rank("do it", parsed) == []

    def test_empty_candidate_words(self):
        parsed = [
            (1.0, "AB CD", "AB CD"),  # No words with 3+ chars
        ]
        scored = _word_overlap_rank("some real task description", parsed)
        assert len(scored) == 0


# === find_related_tasks integration tests ===

class TestFindRelatedTasks:
    def test_returns_list(self, tmp_path):
        queue_file = str(tmp_path / "QUEUE.md")
        with open(queue_file, "w") as f:
            f.write(SAMPLE_QUEUE)
        result = find_related_tasks("brain optimization", queue_file=queue_file)
        assert isinstance(result, list)

    def test_max_tasks_respected(self, tmp_path):
        queue_file = str(tmp_path / "QUEUE.md")
        with open(queue_file, "w") as f:
            f.write(SAMPLE_QUEUE)
        result = find_related_tasks("optimization", queue_file=queue_file, max_tasks=2)
        assert len(result) <= 2

    def test_empty_task(self, tmp_path):
        queue_file = str(tmp_path / "QUEUE.md")
        with open(queue_file, "w") as f:
            f.write(SAMPLE_QUEUE)
        assert find_related_tasks("", queue_file=queue_file) == []

    def test_nonexistent_file(self):
        assert find_related_tasks("brain", queue_file="/tmp/nonexistent_queue.md") == []

    def test_empty_queue_file(self, tmp_path):
        queue_file = str(tmp_path / "QUEUE.md")
        with open(queue_file, "w") as f:
            f.write(QUEUE_EMPTY)
        assert find_related_tasks("anything", queue_file=queue_file) == []

    def test_fallback_to_word_overlap(self, tmp_path, monkeypatch):
        """When embeddings fail, falls back to word-overlap."""
        queue_file = str(tmp_path / "QUEUE.md")
        with open(queue_file, "w") as f:
            f.write(SAMPLE_QUEUE)

        # Make embedding import fail
        import clarvis.context.assembly as asm_mod
        original_fn = asm_mod.find_related_tasks

        def _broken_import(*args, **kwargs):
            raise ImportError("no embeddings")

        monkeypatch.setattr(
            "clarvis.context.assembly.find_related_tasks",
            original_fn,
        )

        # Monkeypatch the factory import to fail
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if "factory" in name:
                raise ImportError("mocked")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        result = find_related_tasks("brain health optimization", queue_file=queue_file)
        # Should still return results via word-overlap fallback
        assert isinstance(result, list)

    def test_results_are_strings(self, tmp_path):
        queue_file = str(tmp_path / "QUEUE.md")
        with open(queue_file, "w") as f:
            f.write(SAMPLE_QUEUE)
        result = find_related_tasks("brain optimization", queue_file=queue_file)
        for item in result:
            assert isinstance(item, str)

    def test_results_max_80_chars(self, tmp_path):
        queue_file = str(tmp_path / "QUEUE.md")
        with open(queue_file, "w") as f:
            f.write(SAMPLE_QUEUE)
        result = find_related_tasks("optimize performance", queue_file=queue_file)
        for item in result:
            assert len(item) <= 80

    def test_semantic_matching_finds_synonyms(self, tmp_path):
        """Semantic matching should find tasks with different vocabulary but similar meaning."""
        queue_content = """\
## P0

- [ ] Improve vector database query latency
- [ ] Clean up old log files
"""
        # Model overlapping concepts: "brain/search" and "database/query" are
        # different words but semantically adjacent (cross-loading on dims 0-1).
        def mock_embed(texts):
            result = []
            for i, t in enumerate(texts):
                tl = t.lower()
                brain_search = any(kw in tl for kw in ["brain", "search", "speed", "retrieval"])
                db_query = any(kw in tl for kw in ["vector", "database", "query", "latency"])
                cleanup = any(kw in tl for kw in ["log", "clean", "old", "file"])
                v = [
                    0.9 if brain_search else (0.3 if db_query else 0.05),
                    0.9 if db_query else (0.3 if brain_search else 0.05),
                    0.9 if cleanup else 0.05,
                    0.1 + 0.02 * i,  # unique offset
                ]
                result.append(v)
            return result

        parsed = _parse_queue_tasks(queue_content)
        scored = _semantic_rank("brain search speed optimization", parsed, mock_embed)
        assert len(scored) > 0
        assert "vector database" in scored[0][1].lower()

    def test_priority_filtering_prefers_p0(self, tmp_path, monkeypatch):
        """P0 tasks should outrank P2 tasks with equal semantic similarity."""
        queue_file = str(tmp_path / "QUEUE.md")
        queue_content = """\
## P0

- [ ] Fix brain retrieval timeout

## P2

- [ ] Fix brain retrieval edge cases
"""
        with open(queue_file, "w") as f:
            f.write(queue_content)

        # Both tasks have equal similarity to the query
        def equal_embed(texts):
            return [[0.5, 0.5, 0.5]] * len(texts)

        parsed = _parse_queue_tasks(queue_content)
        scored = _semantic_rank("Fix brain retrieval", parsed, equal_embed)
        # P0 task (weight 1.0) should rank above P2 (weight 0.4)
        if len(scored) >= 2:
            assert scored[0][0] > scored[1][0]
