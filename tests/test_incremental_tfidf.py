"""Tests for incremental TF-IDF index (clarvis.cognition.incremental_tfidf)."""

import pytest

from clarvis.cognition.incremental_tfidf import IncrementalTFIDF, tokenize


# -- Tokenizer tests -------------------------------------------------------

class TestTokenize:
    def test_basic(self):
        tokens = tokenize("Hello World")
        assert "hello" in tokens
        assert "world" in tokens

    def test_stop_words_removed(self):
        tokens = tokenize("this is a test of the system")
        assert "test" in tokens
        assert "system" in tokens
        assert "this" not in tokens
        assert "is" not in tokens

    def test_punctuation_stripped(self):
        tokens = tokenize("hello, world! foo-bar baz.")
        assert "hello" in tokens
        assert "world" in tokens
        assert "foo" in tokens
        assert "bar" in tokens

    def test_short_tokens_removed(self):
        # Single chars should be filtered out
        tokens = tokenize("I a b c hello")
        assert "hello" in tokens
        assert len([t for t in tokens if len(t) == 1]) == 0


# -- Core index tests ------------------------------------------------------

class TestIncrementalTFIDF:
    def test_add_and_search(self):
        idx = IncrementalTFIDF()
        idx.add("d1", "machine learning algorithms for classification")
        idx.add("d2", "deep learning neural networks")
        idx.add("d3", "cooking recipes for healthy meals")

        results = idx.search("learning algorithms", k=3)
        assert len(results) > 0
        # d1 should rank highest (has both "learning" and "algorithms")
        assert results[0]["doc_id"] == "d1"

    def test_empty_index_returns_empty(self):
        idx = IncrementalTFIDF()
        assert idx.search("anything") == []

    def test_doc_count(self):
        idx = IncrementalTFIDF()
        assert idx.doc_count == 0
        idx.add("d1", "hello world")
        assert idx.doc_count == 1
        idx.add("d2", "foo bar")
        assert idx.doc_count == 2

    def test_vocab_grows(self):
        idx = IncrementalTFIDF()
        idx.add("d1", "hello world")
        v1 = idx.vocab_size
        idx.add("d2", "quantum physics experiment")
        assert idx.vocab_size > v1

    def test_remove(self):
        idx = IncrementalTFIDF()
        idx.add("d1", "hello world")
        idx.add("d2", "foo bar")
        assert idx.doc_count == 2
        assert idx.remove("d1") is True
        assert idx.doc_count == 1
        assert idx.remove("nonexistent") is False

    def test_remove_cleans_df(self):
        idx = IncrementalTFIDF()
        idx.add("d1", "unique term xylophone")
        assert "xylophone" in idx._df
        idx.remove("d1")
        assert "xylophone" not in idx._df

    def test_update_via_readd(self):
        idx = IncrementalTFIDF()
        idx.add("d1", "old content about cats")
        idx.add("d1", "new content about dogs")
        assert idx.doc_count == 1
        results = idx.search("dogs")
        assert len(results) > 0
        assert results[0]["doc_id"] == "d1"

    def test_search_returns_text(self):
        idx = IncrementalTFIDF()
        idx.add("d1", "The quick brown fox jumps over the lazy dog")
        results = idx.search("quick fox", k=1)
        assert len(results) == 1
        assert "quick brown fox" in results[0]["text"]

    def test_search_k_limits_results(self):
        idx = IncrementalTFIDF()
        for i in range(20):
            idx.add(f"d{i}", f"document about topic {i} and machine learning")
        results = idx.search("machine learning", k=5)
        assert len(results) == 5

    def test_no_match_returns_empty(self):
        idx = IncrementalTFIDF()
        idx.add("d1", "hello world")
        results = idx.search("xylophone kazoo")
        assert results == []

    def test_stats(self):
        idx = IncrementalTFIDF()
        idx.add("d1", "hello world foo bar")
        idx.add("d2", "baz qux quux")
        s = idx.stats
        assert s["doc_count"] == 2
        assert s["vocab_size"] > 0
        assert s["avg_doc_length"] > 0


# -- Persistence tests -----------------------------------------------------

class TestPersistence:
    def test_save_and_load(self, tmp_path):
        path = tmp_path / "index.json"
        idx1 = IncrementalTFIDF(persist_path=path)
        idx1.add("d1", "machine learning is powerful")
        idx1.add("d2", "natural language processing")

        idx2 = IncrementalTFIDF(persist_path=path)
        assert idx2.doc_count == 2
        results = idx2.search("machine learning")
        assert len(results) > 0
        assert results[0]["doc_id"] == "d1"


# -- Accuracy comparison against sklearn -----------------------------------

class TestSklearnComparison:
    """Compare ranking accuracy against sklearn's TfidfVectorizer."""

    @pytest.fixture
    def corpus(self):
        return [
            "Machine learning algorithms for text classification",
            "Deep learning and neural networks for image recognition",
            "Natural language processing with transformers",
            "Database optimization and query performance tuning",
            "Web development frameworks and REST API design",
            "Statistical methods for data analysis and visualization",
            "Reinforcement learning in robotics and game AI",
            "Computer vision using convolutional neural networks",
            "Distributed systems and microservices architecture",
            "Cybersecurity and network intrusion detection",
        ]

    @pytest.fixture
    def queries(self):
        return [
            "machine learning classification",
            "neural networks deep learning",
            "language processing text",
            "database query optimization",
            "web API development",
        ]

    def test_top1_agreement(self, corpus, queries):
        """Check that top-1 result agrees with sklearn at least 60% of the time."""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
        except ImportError:
            pytest.skip("sklearn not installed")

        # Build sklearn index
        vectorizer = TfidfVectorizer(stop_words="english")
        tfidf_matrix = vectorizer.fit_transform(corpus)

        # Build incremental index
        idx = IncrementalTFIDF()
        for i, doc in enumerate(corpus):
            idx.add(f"d{i}", doc)

        agreements = 0
        for query in queries:
            # sklearn top-1
            query_vec = vectorizer.transform([query])
            sk_scores = cosine_similarity(query_vec, tfidf_matrix)[0]
            sk_top1 = int(sk_scores.argmax())

            # Our top-1
            results = idx.search(query, k=1)
            if results:
                our_top1 = int(results[0]["doc_id"].replace("d", ""))
                if our_top1 == sk_top1:
                    agreements += 1

        agreement_rate = agreements / len(queries)
        assert agreement_rate >= 0.6, (
            f"Top-1 agreement with sklearn: {agreement_rate:.0%} "
            f"(expected >= 60%)"
        )

    def test_top3_overlap(self, corpus, queries):
        """Check that top-3 results overlap with sklearn at least 50%."""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
        except ImportError:
            pytest.skip("sklearn not installed")

        vectorizer = TfidfVectorizer(stop_words="english")
        tfidf_matrix = vectorizer.fit_transform(corpus)

        idx = IncrementalTFIDF()
        for i, doc in enumerate(corpus):
            idx.add(f"d{i}", doc)

        total_overlap = 0
        for query in queries:
            query_vec = vectorizer.transform([query])
            sk_scores = cosine_similarity(query_vec, tfidf_matrix)[0]
            sk_top3 = set(int(i) for i in np.argsort(sk_scores)[-3:])

            results = idx.search(query, k=3)
            our_top3 = set(int(r["doc_id"].replace("d", "")) for r in results)

            overlap = len(sk_top3 & our_top3)
            total_overlap += overlap

        avg_overlap = total_overlap / (len(queries) * 3)
        assert avg_overlap >= 0.5, (
            f"Top-3 overlap with sklearn: {avg_overlap:.0%} (expected >= 50%)"
        )
