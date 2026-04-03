#!/usr/bin/env python3
"""
BEIR-style Retrieval Benchmark for ClarvisDB.

Evaluates ClarvisDB retrieval quality using standard IR metrics on 55 query-document
pairs with graded relevance judgments (0-3). Compares MiniLM embedding search against
a BM25 baseline on the same corpus.

Metrics:
  - nDCG@10: Normalized Discounted Cumulative Gain (graded relevance)
  - MAP:     Mean Average Precision (binary, threshold >= 2)
  - Recall@k for k in {1, 3, 5, 10}

Usage:
    python3 beir_benchmark.py run           # Full benchmark (ClarvisDB + BM25)
    python3 beir_benchmark.py run --k 5     # Custom cutoff (default 10)
    python3 beir_benchmark.py trend [N]     # Show last N runs (default 10)
    python3 beir_benchmark.py bm25-only     # BM25 baseline only (no ClarvisDB)
"""

import json
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from brain import brain
from clarvis.brain.constants import (
    ALL_COLLECTIONS, IDENTITY, PREFERENCES, LEARNINGS, INFRASTRUCTURE,
    GOALS, CONTEXT, MEMORIES, PROCEDURES, AUTONOMOUS_LEARNING, EPISODES,
)

# === PATHS ===
_WS = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
DATA_DIR = os.path.join(_WS, "data", "beir_benchmark")
HISTORY_FILE = os.path.join(DATA_DIR, "history.jsonl")
LATEST_FILE = os.path.join(DATA_DIR, "latest.json")
os.makedirs(DATA_DIR, exist_ok=True)

MAX_HISTORY = 400


# ============================================================================
# BENCHMARK QUERIES — 55 query-document pairs with graded relevance
# ============================================================================
# relevance: 3=highly relevant, 2=relevant, 1=marginally relevant, 0=irrelevant
# expected_docs: list of {substring, relevance} — a result matching any substring
#   at that relevance level counts. Multiple relevance tiers per query allow nDCG
#   to distinguish "good" from "perfect" retrieval.

BENCHMARK_QUERIES = [
    # ── Identity (5 queries) ──
    {
        "id": "Q01", "query": "Who created Clarvis?",
        "category": "identity",
        "expected_docs": [
            {"substrings": ["operator", "granus", "creator"], "relevance": 3},
            {"substrings": ["clarvis", "identity", "agent"], "relevance": 1},
        ],
    },
    {
        "id": "Q02", "query": "What capabilities does Clarvis have?",
        "category": "identity",
        "expected_docs": [
            {"substrings": ["capability", "capabilities", "can do"], "relevance": 3},
            {"substrings": ["code", "git", "web search", "browser"], "relevance": 2},
            {"substrings": ["clarvis", "agent"], "relevance": 1},
        ],
    },
    {
        "id": "Q03", "query": "What is Clarvis's purpose and mission?",
        "category": "identity",
        "expected_docs": [
            {"substrings": ["purpose", "mission", "north star", "evolve"], "relevance": 3},
            {"substrings": ["agi", "consciousness", "cognitive"], "relevance": 2},
        ],
    },
    {
        "id": "Q04", "query": "Clarvis personality and communication style",
        "category": "identity",
        "expected_docs": [
            {"substrings": ["personality", "style", "communication", "direct", "concise"], "relevance": 3},
            {"substrings": ["no fluff", "preference"], "relevance": 2},
        ],
    },
    {
        "id": "Q05", "query": "What models does Clarvis use?",
        "category": "identity",
        "expected_docs": [
            {"substrings": ["minimax", "m2.5", "claude", "opus"], "relevance": 3},
            {"substrings": ["openrouter", "model", "gateway"], "relevance": 2},
            {"substrings": ["conscious", "subconscious"], "relevance": 1},
        ],
    },

    # ── Goals (6 queries) ──
    {
        "id": "Q06", "query": "What are Clarvis's current goals?",
        "category": "goals",
        "expected_docs": [
            {"substrings": ["goal", "objective", "target"], "relevance": 3},
            {"substrings": ["north star", "agi", "evolve"], "relevance": 2},
        ],
    },
    {
        "id": "Q07", "query": "Progress on session continuity",
        "category": "goals",
        "expected_docs": [
            {"substrings": ["session continuity", "cross-session"], "relevance": 3},
            {"substrings": ["memory", "persistence", "workspace"], "relevance": 1},
        ],
    },
    {
        "id": "Q08", "query": "AGI and consciousness goal progress",
        "category": "goals",
        "expected_docs": [
            {"substrings": ["agi", "consciousness"], "relevance": 3},
            {"substrings": ["phi", "iit", "gwt", "self-model"], "relevance": 2},
        ],
    },
    {
        "id": "Q09", "query": "Performance tracking objectives",
        "category": "goals",
        "expected_docs": [
            {"substrings": ["performance", "benchmark", "pi "], "relevance": 3},
            {"substrings": ["metric", "tracking", "dimension"], "relevance": 2},
        ],
    },
    {
        "id": "Q10", "query": "Agent orchestration goals and delegation",
        "category": "goals",
        "expected_docs": [
            {"substrings": ["orchestrat", "agent", "delegat"], "relevance": 3},
            {"substrings": ["project agent", "star-world-order"], "relevance": 2},
        ],
    },
    {
        "id": "Q11", "query": "Memory quality improvement targets",
        "category": "goals",
        "expected_docs": [
            {"substrings": ["memory quality", "retrieval quality", "brain quality"], "relevance": 3},
            {"substrings": ["dedup", "prune", "hygiene", "bloat"], "relevance": 2},
        ],
    },

    # ── Infrastructure (7 queries) ──
    {
        "id": "Q12", "query": "What is the gateway address and port?",
        "category": "infrastructure",
        "expected_docs": [
            {"substrings": ["18789", "gateway"], "relevance": 3},
            {"substrings": ["127.0.0.1", "localhost", "openclaw"], "relevance": 2},
        ],
    },
    {
        "id": "Q13", "query": "ClarvisDB architecture and storage backend",
        "category": "infrastructure",
        "expected_docs": [
            {"substrings": ["chromadb", "clarvisdb", "sqlite"], "relevance": 3},
            {"substrings": ["onnx", "minilm", "embedding", "collection"], "relevance": 2},
        ],
    },
    {
        "id": "Q14", "query": "How is the cron schedule organized?",
        "category": "infrastructure",
        "expected_docs": [
            {"substrings": ["cron", "schedule", "crontab"], "relevance": 3},
            {"substrings": ["heartbeat", "autonomous", "morning", "evening"], "relevance": 2},
        ],
    },
    {
        "id": "Q15", "query": "Graph database backend and migration",
        "category": "infrastructure",
        "expected_docs": [
            {"substrings": ["graph", "sqlite", "json", "cutover"], "relevance": 3},
            {"substrings": ["wal", "backend", "migration"], "relevance": 2},
        ],
    },
    {
        "id": "Q16", "query": "Backup and disaster recovery procedures",
        "category": "infrastructure",
        "expected_docs": [
            {"substrings": ["backup", "recovery", "restore"], "relevance": 3},
            {"substrings": ["daily", "incremental", "verify"], "relevance": 2},
        ],
    },
    {
        "id": "Q17", "query": "Security rules and credential management",
        "category": "infrastructure",
        "expected_docs": [
            {"substrings": ["security", "credential", "auth.json"], "relevance": 3},
            {"substrings": ["permission", "policy", "api key"], "relevance": 2},
        ],
    },
    {
        "id": "Q18", "query": "Systemd service management for Clarvis",
        "category": "infrastructure",
        "expected_docs": [
            {"substrings": ["systemd", "systemctl", "service"], "relevance": 3},
            {"substrings": ["gateway", "openclaw", "user service"], "relevance": 2},
        ],
    },

    # ── Knowledge / Learnings (10 queries) ──
    {
        "id": "Q19", "query": "How does the attention mechanism work?",
        "category": "knowledge",
        "expected_docs": [
            {"substrings": ["attention", "gwt", "global workspace"], "relevance": 3},
            {"substrings": ["spotlight", "salience", "codelet", "broadcast"], "relevance": 2},
        ],
    },
    {
        "id": "Q20", "query": "Difference between brain.search and memory_search",
        "category": "knowledge",
        "expected_docs": [
            {"substrings": ["brain.search", "memory_search"], "relevance": 3},
            {"substrings": ["clarvisdb", "deprecated"], "relevance": 2},
        ],
    },
    {
        "id": "Q21", "query": "When to act autonomously vs ask the operator",
        "category": "knowledge",
        "expected_docs": [
            {"substrings": ["autonomy", "act first", "ask first"], "relevance": 3},
            {"substrings": ["reversible", "irreversible", "risk"], "relevance": 2},
        ],
    },
    {
        "id": "Q22", "query": "Phi metric and integrated information theory",
        "category": "knowledge",
        "expected_docs": [
            {"substrings": ["phi", "iit", "integrated information"], "relevance": 3},
            {"substrings": ["consciousness", "metric", "graph"], "relevance": 2},
        ],
    },
    {
        "id": "Q23", "query": "Lessons about wiring ClarvisDB into consumers",
        "category": "knowledge",
        "expected_docs": [
            {"substrings": ["wire", "integration", "consumer", "built but didn't"], "relevance": 3},
            {"substrings": ["clarvisdb", "connect", "preflight"], "relevance": 2},
        ],
    },
    {
        "id": "Q24", "query": "Cost tracking and budget management",
        "category": "knowledge",
        "expected_docs": [
            {"substrings": ["cost", "budget", "spending"], "relevance": 3},
            {"substrings": ["openrouter", "api", "tracker"], "relevance": 2},
        ],
    },
    {
        "id": "Q25", "query": "Episodic memory and experience encoding",
        "category": "knowledge",
        "expected_docs": [
            {"substrings": ["episodic", "episode", "experience"], "relevance": 3},
            {"substrings": ["encoding", "postflight", "causal"], "relevance": 2},
        ],
    },
    {
        "id": "Q26", "query": "Self-model and capability domains",
        "category": "knowledge",
        "expected_docs": [
            {"substrings": ["self-model", "self_model", "capability domain"], "relevance": 3},
            {"substrings": ["self-aware", "introspect"], "relevance": 2},
        ],
    },
    {
        "id": "Q27", "query": "Hebbian learning in memory systems",
        "category": "knowledge",
        "expected_docs": [
            {"substrings": ["hebbian", "co-activation", "strengthen"], "relevance": 3},
            {"substrings": ["memory", "learning", "edge", "weight"], "relevance": 2},
        ],
    },
    {
        "id": "Q28", "query": "Context compression techniques",
        "category": "knowledge",
        "expected_docs": [
            {"substrings": ["context compress", "compression", "compressor"], "relevance": 3},
            {"substrings": ["token", "brief", "summariz"], "relevance": 2},
        ],
    },

    # ── Procedures (7 queries) ──
    {
        "id": "Q29", "query": "How to fix cron_autonomous when it fails",
        "category": "procedures",
        "expected_docs": [
            {"substrings": ["cron_autonomous", "fix", "lockfile"], "relevance": 3},
            {"substrings": ["stale", "lock", "recovery", "doctor"], "relevance": 2},
        ],
    },
    {
        "id": "Q30", "query": "Procedure for reasoning chain outcomes",
        "category": "procedures",
        "expected_docs": [
            {"substrings": ["reasoning chain", "outcome", "close_chain"], "relevance": 3},
            {"substrings": ["postflight", "confidence", "status"], "relevance": 2},
        ],
    },
    {
        "id": "Q31", "query": "How to spawn Claude Code from a script",
        "category": "procedures",
        "expected_docs": [
            {"substrings": ["spawn", "claude", "spawn_claude"], "relevance": 3},
            {"substrings": ["dangerously-skip", "timeout", "nesting"], "relevance": 2},
        ],
    },
    {
        "id": "Q32", "query": "Brain optimization and maintenance steps",
        "category": "procedures",
        "expected_docs": [
            {"substrings": ["optimize", "maintenance", "vacuum", "compaction"], "relevance": 3},
            {"substrings": ["dedup", "prune", "decay", "archive"], "relevance": 2},
        ],
    },
    {
        "id": "Q33", "query": "How to run health checks",
        "category": "procedures",
        "expected_docs": [
            {"substrings": ["health", "monitor", "health_monitor", "health check"], "relevance": 3},
            {"substrings": ["watchdog", "doctor", "diagnostic"], "relevance": 2},
        ],
    },
    {
        "id": "Q34", "query": "Safe update procedure for the system",
        "category": "procedures",
        "expected_docs": [
            {"substrings": ["safe_update", "update", "rollback"], "relevance": 3},
            {"substrings": ["backup", "health check", "upgrade"], "relevance": 2},
        ],
    },
    {
        "id": "Q35", "query": "How to add a new memory collection",
        "category": "procedures",
        "expected_docs": [
            {"substrings": ["collection", "add", "create", "new collection"], "relevance": 3},
            {"substrings": ["chromadb", "constants", "brain"], "relevance": 2},
        ],
    },

    # ── Preferences (4 queries) ──
    {
        "id": "Q36", "query": "Communication style preferences",
        "category": "preferences",
        "expected_docs": [
            {"substrings": ["direct", "no fluff", "concise", "communication"], "relevance": 3},
            {"substrings": ["style", "preference"], "relevance": 1},
        ],
    },
    {
        "id": "Q37", "query": "What timezone should Clarvis use?",
        "category": "preferences",
        "expected_docs": [
            {"substrings": ["cet", "timezone", "central european"], "relevance": 3},
        ],
    },
    {
        "id": "Q38", "query": "Preferred code conventions and import style",
        "category": "preferences",
        "expected_docs": [
            {"substrings": ["import", "convention", "from clarvis", "spine"], "relevance": 3},
            {"substrings": ["style", "python", "prefer"], "relevance": 1},
        ],
    },
    {
        "id": "Q39", "query": "Commit message and git workflow preferences",
        "category": "preferences",
        "expected_docs": [
            {"substrings": ["commit", "git", "workflow"], "relevance": 3},
            {"substrings": ["push", "branch", "pr"], "relevance": 1},
        ],
    },

    # ── Context / Episodic (8 queries) ──
    {
        "id": "Q40", "query": "What happened in the last heartbeat?",
        "category": "context",
        "expected_docs": [
            {"substrings": ["heartbeat", "last heartbeat", "verified"], "relevance": 3},
            {"substrings": ["brain healthy", "task", "episode"], "relevance": 2},
        ],
    },
    {
        "id": "Q41", "query": "Recent evolution tasks completed",
        "category": "context",
        "expected_docs": [
            {"substrings": ["evolution", "completed", "task"], "relevance": 3},
            {"substrings": ["autonomous", "sprint", "implemented"], "relevance": 2},
        ],
    },
    {
        "id": "Q42", "query": "What bugs were fixed recently?",
        "category": "context",
        "expected_docs": [
            {"substrings": ["bug", "fix", "fixed"], "relevance": 3},
            {"substrings": ["error", "resolved", "issue"], "relevance": 2},
        ],
    },
    {
        "id": "Q43", "query": "Success rate across sessions",
        "category": "context",
        "expected_docs": [
            {"substrings": ["success rate", "accuracy"], "relevance": 3},
            {"substrings": ["session", "trailing", "episode"], "relevance": 2},
        ],
    },
    {
        "id": "Q44", "query": "Recurring themes in autonomous sessions",
        "category": "context",
        "expected_docs": [
            {"substrings": ["theme", "recurring", "pattern"], "relevance": 3},
            {"substrings": ["session", "synthesis", "autonomous"], "relevance": 2},
        ],
    },
    {
        "id": "Q45", "query": "Morning planning outcomes",
        "category": "context",
        "expected_docs": [
            {"substrings": ["morning", "planning", "plan"], "relevance": 3},
            {"substrings": ["priority", "today", "schedule"], "relevance": 2},
        ],
    },
    {
        "id": "Q46", "query": "Evening assessment summary",
        "category": "context",
        "expected_docs": [
            {"substrings": ["evening", "assessment", "review"], "relevance": 3},
            {"substrings": ["completed", "summary", "day"], "relevance": 2},
        ],
    },
    {
        "id": "Q47", "query": "Research topics investigated",
        "category": "context",
        "expected_docs": [
            {"substrings": ["research", "investigat", "paper", "arXiv"], "relevance": 3},
            {"substrings": ["ingestion", "topic", "study"], "relevance": 2},
        ],
    },

    # ── Cross-domain / Hard queries (8 queries) ──
    {
        "id": "Q48", "query": "How does the heartbeat pipeline work end to end?",
        "category": "cross-domain",
        "expected_docs": [
            {"substrings": ["heartbeat", "pipeline", "gate", "preflight", "postflight"], "relevance": 3},
            {"substrings": ["attention", "task selection", "episode"], "relevance": 2},
        ],
    },
    {
        "id": "Q49", "query": "Task routing and model selection strategy",
        "category": "cross-domain",
        "expected_docs": [
            {"substrings": ["task_router", "routing", "model selection"], "relevance": 3},
            {"substrings": ["minimax", "claude", "complexity", "simple", "complex"], "relevance": 2},
        ],
    },
    {
        "id": "Q50", "query": "Dream engine and counterfactual reasoning",
        "category": "cross-domain",
        "expected_docs": [
            {"substrings": ["dream", "counterfactual"], "relevance": 3},
            {"substrings": ["night", "imagination", "scenario"], "relevance": 2},
        ],
    },
    {
        "id": "Q51", "query": "Cognitive workspace and buffer management",
        "category": "cross-domain",
        "expected_docs": [
            {"substrings": ["cognitive workspace", "buffer", "baddeley"], "relevance": 3},
            {"substrings": ["active", "working", "dormant", "reactivat"], "relevance": 2},
        ],
    },
    {
        "id": "Q52", "query": "Tool maker and procedural extraction",
        "category": "cross-domain",
        "expected_docs": [
            {"substrings": ["tool_maker", "tool maker", "latm", "extract"], "relevance": 3},
            {"substrings": ["procedural", "toollib", "validation"], "relevance": 2},
        ],
    },
    {
        "id": "Q53", "query": "Browser automation and web browsing capabilities",
        "category": "cross-domain",
        "expected_docs": [
            {"substrings": ["browser", "playwright", "agent-browser"], "relevance": 3},
            {"substrings": ["cdp", "chromium", "snapshot", "clarvis_browser"], "relevance": 2},
        ],
    },
    {
        "id": "Q54", "query": "Spine module migration progress",
        "category": "cross-domain",
        "expected_docs": [
            {"substrings": ["spine", "migration", "clarvis/"], "relevance": 3},
            {"substrings": ["module", "promoted", "migrated", "wave"], "relevance": 2},
        ],
    },
    {
        "id": "Q55", "query": "Absolute zero reasoning and self-play",
        "category": "cross-domain",
        "expected_docs": [
            {"substrings": ["absolute zero", "azr", "self-play"], "relevance": 3},
            {"substrings": ["reasoning", "no llm", "cycle"], "relevance": 2},
        ],
    },
]


# ============================================================================
# BM25 BASELINE
# ============================================================================

class BM25:
    """Simple BM25 implementation for baseline comparison.

    Operates over a flat corpus of (doc_id, text, collection) tuples dumped
    from ClarvisDB. Uses standard BM25 with k1=1.5, b=0.75.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus = []       # [(doc_id, text, collection, metadata)]
        self.doc_freqs = {}    # term -> doc count
        self.doc_lens = []     # per-doc token count
        self.avg_dl = 0.0
        self.N = 0
        self._tf_cache = []    # per-doc term frequencies

    @staticmethod
    def _tokenize(text: str) -> list:
        """Simple whitespace + punctuation tokenizer."""
        return re.findall(r'\w+', text.lower())

    def index(self, corpus: list):
        """Index a corpus of (doc_id, text, collection, metadata) tuples."""
        self.corpus = corpus
        self.N = len(corpus)
        self._tf_cache = []
        self.doc_lens = []
        self.doc_freqs = Counter()

        for _, text, _, _ in corpus:
            tokens = self._tokenize(text)
            self.doc_lens.append(len(tokens))
            tf = Counter(tokens)
            self._tf_cache.append(tf)
            for term in tf:
                self.doc_freqs[term] += 1

        self.avg_dl = sum(self.doc_lens) / self.N if self.N > 0 else 1.0

    def search(self, query: str, n: int = 10) -> list:
        """Return top-n results ranked by BM25 score."""
        query_tokens = self._tokenize(query)
        scores = []

        for i in range(self.N):
            score = 0.0
            dl = self.doc_lens[i]
            tf_doc = self._tf_cache[i]
            for term in query_tokens:
                if term not in tf_doc:
                    continue
                tf = tf_doc[term]
                df = self.doc_freqs.get(term, 0)
                idf = math.log((self.N - df + 0.5) / (df + 0.5) + 1.0)
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * dl / self.avg_dl)
                score += idf * numerator / denominator
            scores.append((i, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        results = []
        for idx, sc in scores[:n]:
            doc_id, text, collection, metadata = self.corpus[idx]
            results.append({
                "document": text,
                "id": doc_id,
                "collection": collection,
                "distance": round(1.0 / (1.0 + sc), 4) if sc > 0 else 2.0,
                "metadata": metadata or {},
                "_bm25_score": round(sc, 4),
            })
        return results


def _load_corpus() -> list:
    """Dump all ClarvisDB documents into a flat corpus for BM25 indexing."""
    corpus = []
    for coll_name in ALL_COLLECTIONS:
        try:
            coll = brain.collections.get(coll_name)
            if coll is None:
                continue
            data = coll.get(include=["documents", "metadatas"])
            ids = data.get("ids", [])
            docs = data.get("documents", [])
            metas = data.get("metadatas", [])
            for j in range(len(ids)):
                doc = docs[j] if j < len(docs) else ""
                meta = metas[j] if j < len(metas) else {}
                if doc:
                    corpus.append((ids[j], doc, coll_name, meta))
        except Exception:
            continue
    return corpus


# ============================================================================
# IR METRICS
# ============================================================================

def _relevance_for_result(result: dict, query_spec: dict) -> int:
    """Determine graded relevance of a single result for a query spec.

    Returns highest matching relevance level (0 if no match).
    """
    doc = result.get("document", "").lower()
    best = 0
    for tier in query_spec["expected_docs"]:
        rel = tier["relevance"]
        for sub in tier["substrings"]:
            if sub.lower() in doc:
                best = max(best, rel)
                break  # found match in this tier, check next
    return best


def ndcg_at_k(relevances: list, k: int) -> float:
    """Compute nDCG@k from a list of graded relevance scores."""
    relevances = relevances[:k]
    if not relevances or max(relevances) == 0:
        return 0.0

    # DCG
    dcg = 0.0
    for i, rel in enumerate(relevances):
        dcg += (2 ** rel - 1) / math.log2(i + 2)

    # Ideal DCG
    ideal = sorted(relevances, reverse=True)
    idcg = 0.0
    for i, rel in enumerate(ideal):
        idcg += (2 ** rel - 1) / math.log2(i + 2)

    return round(dcg / idcg, 4) if idcg > 0 else 0.0


def average_precision(relevances: list, threshold: int = 2) -> float:
    """Compute average precision from graded relevances (binary at threshold)."""
    binary = [1 if r >= threshold else 0 for r in relevances]
    if sum(binary) == 0:
        return 0.0
    ap = 0.0
    hits = 0
    for i, b in enumerate(binary):
        if b:
            hits += 1
            ap += hits / (i + 1)
    return round(ap / hits, 4)


def recall_at_k(relevances: list, k: int, threshold: int = 2) -> float:
    """Binary recall@k: 1 if any result at position <= k has relevance >= threshold."""
    for r in relevances[:k]:
        if r >= threshold:
            return 1.0
    return 0.0


# ============================================================================
# BENCHMARK RUNNER
# ============================================================================

def _evaluate_query(query_spec: dict, search_fn, k: int) -> dict:
    """Evaluate a single query against a search function."""
    query = query_spec["query"]
    t0 = time.time()
    results = search_fn(query, n=k)
    latency_ms = round((time.time() - t0) * 1000, 1)

    relevances = [_relevance_for_result(r, query_spec) for r in results]

    # Pad to k if fewer results returned
    while len(relevances) < k:
        relevances.append(0)

    return {
        "id": query_spec["id"],
        "query": query,
        "category": query_spec["category"],
        "ndcg_at_10": ndcg_at_k(relevances, 10),
        "ndcg_at_k": ndcg_at_k(relevances, k),
        "ap": average_precision(relevances),
        "recall_at_1": recall_at_k(relevances, 1),
        "recall_at_3": recall_at_k(relevances, 3),
        "recall_at_5": recall_at_k(relevances, 5),
        "recall_at_10": recall_at_k(relevances, 10),
        "relevances": relevances[:k],
        "latency_ms": latency_ms,
        "n_results": len(results),
    }


def _aggregate(query_results: list) -> dict:
    """Aggregate per-query results into summary metrics."""
    n = len(query_results)
    if n == 0:
        return {}

    metrics = {
        "ndcg_at_10": round(sum(q["ndcg_at_10"] for q in query_results) / n, 4),
        "map": round(sum(q["ap"] for q in query_results) / n, 4),
        "recall_at_1": round(sum(q["recall_at_1"] for q in query_results) / n, 4),
        "recall_at_3": round(sum(q["recall_at_3"] for q in query_results) / n, 4),
        "recall_at_5": round(sum(q["recall_at_5"] for q in query_results) / n, 4),
        "recall_at_10": round(sum(q["recall_at_10"] for q in query_results) / n, 4),
        "avg_latency_ms": round(sum(q["latency_ms"] for q in query_results) / n, 1),
        "num_queries": n,
    }

    # Per-category breakdown
    by_cat = defaultdict(list)
    for q in query_results:
        by_cat[q["category"]].append(q)

    cat_metrics = {}
    for cat, qs in sorted(by_cat.items()):
        nc = len(qs)
        cat_metrics[cat] = {
            "count": nc,
            "ndcg_at_10": round(sum(q["ndcg_at_10"] for q in qs) / nc, 4),
            "map": round(sum(q["ap"] for q in qs) / nc, 4),
            "recall_at_5": round(sum(q["recall_at_5"] for q in qs) / nc, 4),
        }
    metrics["by_category"] = cat_metrics

    # Failure analysis (queries with no relevant results in top 10)
    failures = [q for q in query_results if q["recall_at_10"] == 0]
    metrics["failures"] = [{"id": f["id"], "query": f["query"]} for f in failures]
    metrics["failure_rate"] = round(len(failures) / n, 4)

    return metrics


def run_benchmark(k: int = 10, run_bm25: bool = True) -> dict:
    """Run full BEIR-style benchmark. Compare ClarvisDB vs BM25 baseline."""
    print(f"BEIR Benchmark: {len(BENCHMARK_QUERIES)} queries, k={k}")

    # --- ClarvisDB (MiniLM embeddings) ---
    print("  Running ClarvisDB (MiniLM) retrieval...")

    def clarvis_search(query, n=10):
        return brain.recall(query, n=n, caller="beir_benchmark")

    clarvis_results = []
    for qs in BENCHMARK_QUERIES:
        clarvis_results.append(_evaluate_query(qs, clarvis_search, k))

    clarvis_agg = _aggregate(clarvis_results)
    print(f"  ClarvisDB: nDCG@10={clarvis_agg['ndcg_at_10']}, "
          f"MAP={clarvis_agg['map']}, R@5={clarvis_agg['recall_at_5']}")

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "k": k,
        "num_queries": len(BENCHMARK_QUERIES),
        "clarvisdb": {**clarvis_agg, "method": "MiniLM-L6-v2 (ONNX)", "details": clarvis_results},
    }

    # --- BM25 baseline ---
    if run_bm25:
        print("  Loading corpus for BM25 baseline...")
        corpus = _load_corpus()
        print(f"  Corpus: {len(corpus)} documents")
        bm25 = BM25()
        bm25.index(corpus)

        print("  Running BM25 retrieval...")
        bm25_results = []
        for qs in BENCHMARK_QUERIES:
            bm25_results.append(_evaluate_query(qs, bm25.search, k))

        bm25_agg = _aggregate(bm25_results)
        print(f"  BM25:      nDCG@10={bm25_agg['ndcg_at_10']}, "
              f"MAP={bm25_agg['map']}, R@5={bm25_agg['recall_at_5']}")

        report["bm25"] = {**bm25_agg, "method": "BM25 (k1=1.5, b=0.75)",
                          "corpus_size": len(corpus), "details": bm25_results}

        # --- Comparison ---
        delta = {
            "ndcg_at_10": round(clarvis_agg["ndcg_at_10"] - bm25_agg["ndcg_at_10"], 4),
            "map": round(clarvis_agg["map"] - bm25_agg["map"], 4),
            "recall_at_5": round(clarvis_agg["recall_at_5"] - bm25_agg["recall_at_5"], 4),
            "recall_at_10": round(clarvis_agg["recall_at_10"] - bm25_agg["recall_at_10"], 4),
        }
        report["delta_clarvis_minus_bm25"] = delta

        # Per-query comparison
        per_query_delta = []
        for cv, bm in zip(clarvis_results, bm25_results):
            d = round(cv["ndcg_at_10"] - bm["ndcg_at_10"], 4)
            if abs(d) > 0.1:  # Only report significant differences
                per_query_delta.append({
                    "id": cv["id"], "query": cv["query"][:60],
                    "clarvis_ndcg": cv["ndcg_at_10"], "bm25_ndcg": bm["ndcg_at_10"],
                    "delta": d, "winner": "clarvis" if d > 0 else "bm25",
                })
        report["notable_differences"] = per_query_delta

    return report


def save_report(report: dict):
    """Save report to latest.json and append summary to history.jsonl."""
    with open(LATEST_FILE, "w") as f:
        json.dump(report, f, indent=2)

    # Compact summary for history
    summary = {
        "timestamp": report["timestamp"],
        "k": report["k"],
        "num_queries": report["num_queries"],
        "clarvisdb_ndcg10": report["clarvisdb"]["ndcg_at_10"],
        "clarvisdb_map": report["clarvisdb"]["map"],
        "clarvisdb_recall5": report["clarvisdb"]["recall_at_5"],
        "clarvisdb_recall10": report["clarvisdb"]["recall_at_10"],
    }
    if "bm25" in report:
        summary["bm25_ndcg10"] = report["bm25"]["ndcg_at_10"]
        summary["bm25_map"] = report["bm25"]["map"]
        summary["bm25_recall5"] = report["bm25"]["recall_at_5"]

    # Append to history, rotate if needed
    lines = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            lines = f.readlines()
    lines.append(json.dumps(summary) + "\n")
    if len(lines) > MAX_HISTORY:
        lines = lines[-MAX_HISTORY:]
    with open(HISTORY_FILE, "w") as f:
        f.writelines(lines)


def show_trend(n: int = 10):
    """Print recent benchmark trend."""
    if not os.path.exists(HISTORY_FILE):
        print("No history yet. Run `beir_benchmark.py run` first.")
        return

    with open(HISTORY_FILE) as f:
        lines = f.readlines()

    entries = []
    for line in lines[-n:]:
        try:
            entries.append(json.loads(line.strip()))
        except json.JSONDecodeError:
            continue

    if not entries:
        print("No valid history entries.")
        return

    print(f"\n{'Date':<12} {'nDCG@10':>8} {'MAP':>6} {'R@5':>5} {'R@10':>5} {'BM25 nDCG':>10}")
    print("-" * 52)
    for e in entries:
        ts = e.get("timestamp", "")[:10]
        cn = e.get("clarvisdb_ndcg10", 0)
        cm = e.get("clarvisdb_map", 0)
        cr5 = e.get("clarvisdb_recall5", 0)
        cr10 = e.get("clarvisdb_recall10", 0)
        bn = e.get("bm25_ndcg10", "-")
        bn_str = f"{bn:.4f}" if isinstance(bn, (int, float)) else bn
        print(f"{ts:<12} {cn:>8.4f} {cm:>6.4f} {cr5:>5.2f} {cr10:>5.2f} {bn_str:>10}")


def print_report(report: dict):
    """Pretty-print benchmark report to stdout."""
    print("\n" + "=" * 60)
    print("  BEIR-STYLE RETRIEVAL BENCHMARK — ClarvisDB")
    print("=" * 60)

    cv = report["clarvisdb"]
    print(f"\n  ClarvisDB (MiniLM-L6-v2 ONNX)")
    print(f"    nDCG@10:    {cv['ndcg_at_10']:.4f}")
    print(f"    MAP:        {cv['map']:.4f}")
    print(f"    Recall@1:   {cv['recall_at_1']:.4f}")
    print(f"    Recall@3:   {cv['recall_at_3']:.4f}")
    print(f"    Recall@5:   {cv['recall_at_5']:.4f}")
    print(f"    Recall@10:  {cv['recall_at_10']:.4f}")
    print(f"    Avg Latency: {cv['avg_latency_ms']:.1f}ms")

    if "bm25" in report:
        bm = report["bm25"]
        print(f"\n  BM25 Baseline (k1=1.5, b=0.75)")
        print(f"    nDCG@10:    {bm['ndcg_at_10']:.4f}")
        print(f"    MAP:        {bm['map']:.4f}")
        print(f"    Recall@1:   {bm['recall_at_1']:.4f}")
        print(f"    Recall@3:   {bm['recall_at_3']:.4f}")
        print(f"    Recall@5:   {bm['recall_at_5']:.4f}")
        print(f"    Recall@10:  {bm['recall_at_10']:.4f}")
        print(f"    Corpus:     {bm['corpus_size']} documents")

        d = report.get("delta_clarvis_minus_bm25", {})
        print(f"\n  Delta (ClarvisDB - BM25)")
        print(f"    nDCG@10:    {d.get('ndcg_at_10', 0):+.4f}")
        print(f"    MAP:        {d.get('map', 0):+.4f}")
        print(f"    Recall@5:   {d.get('recall_at_5', 0):+.4f}")
        print(f"    Recall@10:  {d.get('recall_at_10', 0):+.4f}")

    # Category breakdown
    print(f"\n  Category Breakdown (ClarvisDB)")
    print(f"    {'Category':<16} {'nDCG@10':>8} {'MAP':>6} {'R@5':>5} {'n':>3}")
    print(f"    {'-'*38}")
    for cat, stats in sorted(cv.get("by_category", {}).items()):
        print(f"    {cat:<16} {stats['ndcg_at_10']:>8.4f} {stats['map']:>6.4f} "
              f"{stats['recall_at_5']:>5.2f} {stats['count']:>3}")

    # Failures
    failures = cv.get("failures", [])
    if failures:
        print(f"\n  Failures ({len(failures)} queries with no relevant results in top 10):")
        for f in failures:
            print(f"    - {f['id']}: {f['query']}")

    # Notable differences
    notable = report.get("notable_differences", [])
    if notable:
        print(f"\n  Notable Differences (|delta| > 0.1):")
        for nd in notable[:10]:
            winner = nd["winner"].upper()
            print(f"    {nd['id']}: {winner} wins ({nd['delta']:+.4f}) — {nd['query']}")

    print("\n" + "=" * 60)


# ============================================================================
# CLI
# ============================================================================

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "run":
        k = 10
        if "--k" in sys.argv:
            idx = sys.argv.index("--k")
            if idx + 1 < len(sys.argv):
                k = int(sys.argv[idx + 1])
        no_bm25 = "--no-bm25" in sys.argv

        report = run_benchmark(k=k, run_bm25=not no_bm25)
        print_report(report)
        save_report(report)
        print(f"\n  Saved to {LATEST_FILE}")

    elif cmd == "bm25-only":
        k = 10
        report = run_benchmark(k=k, run_bm25=True)
        # Only show BM25 results
        if "bm25" in report:
            bm = report["bm25"]
            print(f"\nBM25 Only: nDCG@10={bm['ndcg_at_10']}, MAP={bm['map']}, "
                  f"R@5={bm['recall_at_5']}, R@10={bm['recall_at_10']}")

    elif cmd == "trend":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        show_trend(n)

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
