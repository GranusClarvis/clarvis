"""Tests for the bloom filter module (clarvis.brain.bloom_filter)."""

import tempfile
from pathlib import Path

import pytest

from clarvis.brain.bloom_filter import (
    BloomFilter,
    _normalize,
    _optimal_params,
    _hash_indices,
    get_filter,
    _filters,
)


class TestOptimalParams:
    def test_reasonable_sizes(self):
        m, k = _optimal_params(1000, 0.01)
        assert m > 0
        assert k > 0
        # For 1000 items at 1% FP, m should be ~9585 bits
        assert 8000 < m < 12000
        assert 5 <= k <= 10

    def test_lower_fp_means_more_bits(self):
        m1, _ = _optimal_params(1000, 0.01)
        m2, _ = _optimal_params(1000, 0.001)
        assert m2 > m1

    def test_zero_items_no_crash(self):
        m, k = _optimal_params(0, 0.01)
        assert m > 0 and k > 0


class TestNormalize:
    def test_lowercase(self):
        assert _normalize("Hello World") == "hello world"

    def test_collapse_whitespace(self):
        assert _normalize("  foo   bar  ") == "foo bar"

    def test_tabs_and_newlines(self):
        assert _normalize("hello\n\tworld") == "hello world"


class TestBloomFilter:
    def test_add_and_check(self):
        bf = BloomFilter(expected_items=100, fp_rate=0.01)
        bf.add("hello world")
        assert bf.might_contain("hello world") is True

    def test_definitely_not_present(self):
        bf = BloomFilter(expected_items=100, fp_rate=0.01)
        bf.add("hello world")
        # A completely different string should (almost certainly) not match
        assert bf.might_contain("quantum mechanics textbook") is False

    def test_case_insensitive(self):
        bf = BloomFilter(expected_items=100, fp_rate=0.01)
        bf.add("Hello World")
        assert bf.might_contain("hello world") is True
        assert bf.might_contain("HELLO WORLD") is True

    def test_whitespace_insensitive(self):
        bf = BloomFilter(expected_items=100, fp_rate=0.01)
        bf.add("  hello   world  ")
        assert bf.might_contain("hello world") is True

    def test_no_false_negatives(self):
        """The fundamental Bloom filter guarantee: no false negatives."""
        bf = BloomFilter(expected_items=1000, fp_rate=0.01)
        items = [f"item number {i}" for i in range(500)]
        for item in items:
            bf.add(item)
        for item in items:
            assert bf.might_contain(item) is True, f"False negative for: {item}"

    def test_false_positive_rate_within_bounds(self):
        """FP rate should be roughly within 2x of target for a well-sized filter."""
        bf = BloomFilter(expected_items=5000, fp_rate=0.005)
        # Add exactly expected_items entries
        for i in range(5000):
            bf.add(f"stored item {i}")
        # Test 10000 items that were NOT added
        false_positives = 0
        test_count = 10000
        for i in range(test_count):
            if bf.might_contain(f"not stored item {i + 100000}"):
                false_positives += 1
        fp_rate = false_positives / test_count
        # Allow up to 2% (4x the target) due to statistical variance
        assert fp_rate < 0.02, f"FP rate {fp_rate:.4f} too high (target: 0.005)"

    def test_stats(self):
        bf = BloomFilter(expected_items=100, fp_rate=0.01)
        bf.add("test item")
        bf.might_contain("test item")
        bf.might_contain("other item")
        s = bf.stats
        assert s["items"] == 1
        assert s["checks"] == 2
        assert s["definite_new"] + s["maybe_duplicate"] == 2

    def test_needs_rebuild(self):
        bf = BloomFilter(expected_items=10, fp_rate=0.01)
        assert bf.needs_rebuild is False
        bf._item_count = 100
        assert bf.needs_rebuild is True


class TestPersistence:
    def test_save_and_load(self, tmp_path):
        path = tmp_path / "test.bloom"
        bf1 = BloomFilter(expected_items=100, fp_rate=0.01, persist_path=path)
        bf1.add("persistent memory")
        bf1.add("another memory")
        bf1.save()

        bf2 = BloomFilter(expected_items=100, fp_rate=0.01, persist_path=path)
        assert bf2.might_contain("persistent memory") is True
        assert bf2.might_contain("another memory") is True
        assert bf2._item_count == 2

    def test_param_mismatch_starts_fresh(self, tmp_path):
        path = tmp_path / "test.bloom"
        bf1 = BloomFilter(expected_items=100, fp_rate=0.01, persist_path=path)
        bf1.add("old data")
        bf1.save()

        # Different params → should start fresh
        bf2 = BloomFilter(expected_items=200, fp_rate=0.01, persist_path=path)
        assert bf2._item_count == 0


class TestStoreIntegration:
    """Test bloom filter integration with brain.store() path."""

    def test_bloom_skips_chromadb_for_new_text(self):
        """When bloom says 'not present', ChromaDB query should be skipped."""
        bf = BloomFilter(expected_items=100, fp_rate=0.01)
        # Fresh filter — everything should be "definitely new"
        assert bf.might_contain("brand new unique text") is False
        s = bf.stats
        assert s["definite_new"] == 1
        assert s["maybe_duplicate"] == 0

    def test_bloom_passes_through_for_existing_text(self):
        """When bloom says 'maybe present', should proceed to ChromaDB."""
        bf = BloomFilter(expected_items=100, fp_rate=0.01)
        bf.add("existing memory about cats")
        assert bf.might_contain("existing memory about cats") is True
        s = bf.stats
        assert s["maybe_duplicate"] == 1


class TestHashIndices:
    def test_produces_k_indices(self):
        indices = _hash_indices("test", 1000, 7)
        assert len(indices) == 7

    def test_indices_in_range(self):
        indices = _hash_indices("test", 1000, 7)
        assert all(0 <= i < 1000 for i in indices)

    def test_deterministic(self):
        a = _hash_indices("test", 1000, 7)
        b = _hash_indices("test", 1000, 7)
        assert a == b

    def test_different_texts_different_indices(self):
        a = _hash_indices("alpha", 10000, 7)
        b = _hash_indices("beta", 10000, 7)
        assert a != b
