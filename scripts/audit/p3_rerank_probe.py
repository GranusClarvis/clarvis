#!/usr/bin/env python3
"""P3 Cross-Encoder Rerank Probe — measurement-only.

Tests whether a small cross-encoder reranker (Nogueira & Cho 2019) lifts
Precision@3 on the canonical retrieval ground-truth fixtures. For each
query: (a) baseline ChromaDB retrieve top-10 (sorted by distance), score
P@3 of top-3, (b) cross-encoder predicts (query, doc) relevance scores
for the top-10 candidates, reorder, score new P@3 of the new top-3.

Distinct from `[P3_HYDE_QUERY_REFORMULATION_PROBE]`: HyDE rewrites the
query *before* retrieval; rerank reorders the candidate set *after*
retrieval. Different stage, often additive.

No production code is changed. Outputs an audit report under
docs/internal/audits/. Cost capped to free (local cross-encoder) or
<$0.10 (LLM fallback path).

Usage:
    python3 scripts/audit/p3_rerank_probe.py            # full run
    python3 scripts/audit/p3_rerank_probe.py --limit 5  # smoke test
    python3 scripts/audit/p3_rerank_probe.py --reranker llm   # force LLM fallback
"""

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

from clarvis.brain import brain  # noqa: E402
from clarvis._script_loader import load as _load_script  # noqa: E402

_rb = _load_script("retrieval_benchmark", "brain_mem")

CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# LLM fallback: MiniMax M2.5 via OpenRouter (pairwise prompt). Used only when
# sentence-transformers / cross-encoder model cannot be loaded.
MODEL_OPENROUTER = "minimax/minimax-m2.5"
INPUT_PRICE = 0.30 / 1_000_000
OUTPUT_PRICE = 1.20 / 1_000_000
COST_CAP_USD = 0.10

REPORT_PATH = os.path.join(WORKSPACE, "docs/internal/audits/P3_RERANK_PROBE_2026-05-07.md")
RAW_RESULTS_PATH = os.path.join(WORKSPACE, "data/audit/p3_rerank_probe_2026-05-07.json")

CANDIDATE_K = 10  # top-N candidates to rerank
SCORE_K = 3      # P@K we report
LATENCY_BUDGET_MS = 100.0  # p95 added latency above which rerank is "not worth it"


def _normalize_pairs():
    """Combine retrieval_benchmark BENCHMARK_PAIRS (20) + data/golden_qa.json (25)
    into a single substring-matched list so both feed identical evaluation."""
    pairs = []
    for p in _rb.BENCHMARK_PAIRS:
        pairs.append({
            "id": p["id"],
            "query": p["query"],
            "expected_substrings": p["expected_substrings"],
            "expected_collections": p.get("expected_collections", []),
            "category": p.get("category", "uncategorized"),
            "source": "retrieval_benchmark",
        })
    extra_path = os.path.join(WORKSPACE, "data/golden_qa.json")
    if os.path.exists(extra_path):
        with open(extra_path) as f:
            extra = json.load(f)
        for i, q in enumerate(extra):
            coll = q.get("collection")
            pairs.append({
                "id": f"G{i+1:02d}",
                "query": q["query"],
                "expected_substrings": q.get("expected_docs", []),
                "expected_collections": [coll] if coll else [],
                "category": coll.replace("clarvis-", "") if coll else "uncategorized",
                "source": "data/golden_qa.json",
            })
    return pairs


def _check_hit(doc_text, expected_substrings):
    if not doc_text or not expected_substrings:
        return False
    d = doc_text.lower()
    for sub in expected_substrings:
        if sub and sub.lower() in d:
            return True
    return False


def _precision_at_k(results, expected_substrings, k=SCORE_K):
    top = results[:k]
    if not top:
        return 0.0
    hits = sum(1 for r in top if _check_hit(r.get("document", ""), expected_substrings))
    return hits / float(k)


def _retrieve_top_n(query, n=CANDIDATE_K):
    """brain.recall returns per-collection top-N concatenated and unsorted.
    Sort by distance ascending and take the global top-N."""
    raw = brain.recall(query, n=n, caller="p3_rerank_probe")
    raw_sorted = sorted(raw, key=lambda r: float(r.get("distance") or 999.0))
    return raw_sorted[:n]


def _load_cross_encoder():
    try:
        from sentence_transformers import CrossEncoder  # noqa: WPS433
    except ImportError:
        return None, "sentence_transformers not installed"
    try:
        model = CrossEncoder(CROSS_ENCODER_MODEL, device="cpu")
        return model, None
    except Exception as exc:  # network / model load failure
        return None, str(exc)


def _rerank_local(model, query, candidates):
    """Returns (reordered_candidates, added_latency_ms, score_list)."""
    if not candidates:
        return [], 0.0, []
    pairs = [(query, (c.get("document") or "")[:512]) for c in candidates]
    t0 = time.perf_counter()
    scores = model.predict(pairs)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    indexed = sorted(zip(candidates, scores), key=lambda kv: float(kv[1]), reverse=True)
    reordered = [c for c, _ in indexed]
    score_list = [float(s) for _, s in indexed]
    return reordered, elapsed_ms, score_list


def _api_key():
    k = os.environ.get("OPENROUTER_API_KEY")
    if k:
        return k
    auth_file = os.path.join(
        os.environ.get("OPENCLAW_HOME", os.path.expanduser("~/.openclaw")),
        "agents/main/agent/auth-profiles.json",
    )
    try:
        with open(auth_file) as f:
            auth = json.load(f)
        return auth.get("profiles", {}).get("openrouter:default", {}).get("key")
    except Exception:
        return None


_LLM_RERANK_PROMPT = (
    "You are a relevance-ranking judge. Rank these candidate documents for "
    "the query, from most to least relevant. Reply with ONLY a comma-"
    "separated list of candidate indices (e.g. `3,1,5,2,...`).\n\n"
    "Query: {query}\n\nCandidates:\n{candidates}\n\nRanking (indices only):"
)


def _rerank_llm(api_key, query, candidates, timeout=25):
    """LLM batch-ranking fallback. Returns (reordered, added_latency_ms, in_tokens, out_tokens)."""
    import requests
    cand_text = "\n".join(
        f"[{i}] {(c.get('document') or '')[:200]}" for i, c in enumerate(candidates)
    )
    prompt = _LLM_RERANK_PROMPT.format(query=query, candidates=cand_text)
    t0 = time.perf_counter()
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://clarvis.local",
            "X-Title": "Clarvis P3 Rerank Probe",
        },
        json={
            "model": MODEL_OPENROUTER,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 80,
            "temperature": 0.0,
        },
        timeout=timeout,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    resp.raise_for_status()
    body = resp.json()
    content = body["choices"][0]["message"]["content"].strip()
    usage = body.get("usage", {}) or {}
    in_tok = int(usage.get("prompt_tokens", 0))
    out_tok = int(usage.get("completion_tokens", 0))
    # Parse "3, 1, 5, ..." → list of ints
    raw_ids = []
    for tok in content.replace(";", ",").replace(" ", ",").split(","):
        tok = tok.strip().strip("[]()")
        if tok.isdigit():
            n = int(tok)
            if 0 <= n < len(candidates) and n not in raw_ids:
                raw_ids.append(n)
    # Append any missing indices in original order
    for i in range(len(candidates)):
        if i not in raw_ids:
            raw_ids.append(i)
    reordered = [candidates[i] for i in raw_ids]
    return reordered, elapsed_ms, in_tok, out_tok


def _per_collection(query_results):
    by = {}
    for q in query_results:
        cats = q.get("expected_collections") or [q.get("category", "uncategorized")]
        for c in cats:
            by.setdefault(c, {"n": 0, "base_p3": 0.0, "rerank_p3": 0.0,
                              "rerank_lat_ms": []})
            by[c]["n"] += 1
            by[c]["base_p3"] += q["baseline_p3"]
            by[c]["rerank_p3"] += q["rerank_p3"]
            by[c]["rerank_lat_ms"].append(q["rerank_latency_ms"])
    out = {}
    for c, v in by.items():
        n = v["n"]
        lats = v["rerank_lat_ms"]
        out[c] = {
            "n": n,
            "baseline_p3": round(v["base_p3"] / n, 4),
            "rerank_p3": round(v["rerank_p3"] / n, 4),
            "delta": round((v["rerank_p3"] - v["base_p3"]) / n, 4),
            "rerank_p50_ms": round(statistics.median(lats), 2) if lats else 0.0,
            "rerank_p95_ms": round(_pctl(lats, 95), 2) if lats else 0.0,
        }
    return out


def _pctl(xs, p):
    if not xs:
        return 0.0
    s = sorted(xs)
    idx = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return s[idx]


def _agg(query_results, key):
    if not query_results:
        return 0.0
    return round(sum(q[key] for q in query_results) / len(query_results), 4)


def run(limit=None, reranker="auto"):
    pairs = _normalize_pairs()
    if limit is not None:
        pairs = pairs[:limit]
    if len(pairs) > 50:
        pairs = pairs[:50]

    # Pick reranker path
    chosen = reranker
    model = None
    api_key = None
    init_err = None
    if chosen in ("auto", "local"):
        model, init_err = _load_cross_encoder()
        if model is not None:
            chosen = "local"
        elif chosen == "auto":
            chosen = "llm"

    if chosen == "llm":
        api_key = _api_key()
        if not api_key:
            raise RuntimeError("LLM rerank fallback selected but no OpenRouter key found.")

    print(f"[init] reranker path: {chosen} "
          f"({'cross-encoder/ms-marco-MiniLM-L-6-v2' if chosen == 'local' else MODEL_OPENROUTER})", flush=True)
    if init_err and chosen == "llm":
        print(f"[init] local cross-encoder unavailable: {init_err}", flush=True)

    query_results = []
    total_in_tokens = 0
    total_out_tokens = 0
    started = time.time()

    for idx, p in enumerate(pairs, 1):
        q = p["query"]
        print(f"[{idx}/{len(pairs)}] {p['id']:>5s} {q[:60]}", flush=True)

        # (a) Baseline retrieve top-10
        try:
            t0 = time.perf_counter()
            cands = _retrieve_top_n(q, n=CANDIDATE_K)
            retrieval_ms = (time.perf_counter() - t0) * 1000.0
        except Exception as exc:
            print(f"   baseline retrieval error: {exc}", flush=True)
            cands = []
            retrieval_ms = 0.0
        base_p3 = _precision_at_k(cands, p["expected_substrings"], k=SCORE_K)

        # (b) Rerank
        rerank_err = None
        in_tok = out_tok = 0
        cost_so_far = (total_in_tokens * INPUT_PRICE + total_out_tokens * OUTPUT_PRICE)
        try:
            if not cands:
                reordered = []
                rerank_ms = 0.0
                ce_scores = []
            elif chosen == "local":
                reordered, rerank_ms, ce_scores = _rerank_local(model, q, cands)
            else:
                if cost_so_far > COST_CAP_USD:
                    rerank_err = f"cost cap reached ({cost_so_far:.4f} > {COST_CAP_USD})"
                    reordered = cands  # fall back to baseline order
                    rerank_ms = 0.0
                    ce_scores = []
                else:
                    reordered, rerank_ms, in_tok, out_tok = _rerank_llm(api_key, q, cands)
                    total_in_tokens += in_tok
                    total_out_tokens += out_tok
                    ce_scores = []
        except Exception as exc:
            rerank_err = str(exc)
            print(f"   rerank error: {exc}", flush=True)
            reordered = cands
            rerank_ms = 0.0
            ce_scores = []

        rerank_p3 = _precision_at_k(reordered, p["expected_substrings"], k=SCORE_K)

        query_results.append({
            "id": p["id"],
            "query": q,
            "category": p["category"],
            "expected_collections": p["expected_collections"],
            "expected_substrings": p["expected_substrings"],
            "source": p["source"],
            "n_candidates": len(cands),
            "baseline_p3": round(base_p3, 4),
            "rerank_p3": round(rerank_p3, 4),
            "delta": round(rerank_p3 - base_p3, 4),
            "retrieval_latency_ms": round(retrieval_ms, 2),
            "rerank_latency_ms": round(rerank_ms, 2),
            "rerank_in_tokens": in_tok,
            "rerank_out_tokens": out_tok,
            "rerank_error": rerank_err,
            "baseline_top3": [
                {"id": r.get("id"), "collection": r.get("collection"),
                 "distance": round(float(r.get("distance") or 999), 4),
                 "preview": (r.get("document", "") or "")[:120]}
                for r in cands[:SCORE_K]
            ],
            "rerank_top3": [
                {"id": r.get("id"), "collection": r.get("collection"),
                 "distance": round(float(r.get("distance") or 999), 4),
                 "rerank_score": round(ce_scores[i], 4) if i < len(ce_scores) else None,
                 "preview": (r.get("document", "") or "")[:120]}
                for i, r in enumerate(reordered[:SCORE_K])
            ],
        })

    elapsed = round(time.time() - started, 2)
    if chosen == "llm":
        cost_usd = round(total_in_tokens * INPUT_PRICE + total_out_tokens * OUTPUT_PRICE, 6)
    else:
        cost_usd = 0.0

    rerank_lats = [q["rerank_latency_ms"] for q in query_results if q["rerank_latency_ms"] > 0]
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reranker_path": chosen,
        "model": CROSS_ENCODER_MODEL if chosen == "local" else MODEL_OPENROUTER,
        "candidate_k": CANDIDATE_K,
        "score_k": SCORE_K,
        "latency_budget_ms": LATENCY_BUDGET_MS,
        "num_queries": len(query_results),
        "elapsed_seconds": elapsed,
        "baseline_p3": _agg(query_results, "baseline_p3"),
        "rerank_p3": _agg(query_results, "rerank_p3"),
        "delta_p3": round(
            _agg(query_results, "rerank_p3") - _agg(query_results, "baseline_p3"), 4
        ),
        "queries_with_lift": sum(1 for q in query_results if q["delta"] > 0),
        "queries_with_drop": sum(1 for q in query_results if q["delta"] < 0),
        "queries_unchanged": sum(1 for q in query_results if q["delta"] == 0),
        "rerank_latency_p50_ms": round(statistics.median(rerank_lats), 2) if rerank_lats else 0.0,
        "rerank_latency_p95_ms": round(_pctl(rerank_lats, 95), 2) if rerank_lats else 0.0,
        "rerank_latency_mean_ms": round(sum(rerank_lats) / len(rerank_lats), 2) if rerank_lats else 0.0,
        "rerank_latency_max_ms": round(max(rerank_lats), 2) if rerank_lats else 0.0,
        "by_collection": _per_collection(query_results),
        "tokens_in": total_in_tokens,
        "tokens_out": total_out_tokens,
        "cost_usd": cost_usd,
        "details": query_results,
    }
    return summary


def write_report(summary, path=REPORT_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    base = summary["baseline_p3"]
    rerank = summary["rerank_p3"]
    delta = summary["delta_p3"]
    rel = (delta / base * 100.0) if base > 0 else 0.0
    p95_lat = summary["rerank_latency_p95_ms"]
    n = max(summary["num_queries"], 1)
    pos = summary["queries_with_lift"]
    pos_rate = pos / n

    # Decision rule:
    # - SHIP if (Δ P@3 ≥ +0.05 absolute) AND (≥60% of queries improved)
    #          AND (added p95 latency < LATENCY_BUDGET_MS).
    # - DO NOT SHIP otherwise.
    quality_ok = (delta >= 0.05) and (pos_rate >= 0.6)
    latency_ok = (p95_lat < LATENCY_BUDGET_MS)
    ship = quality_ok and latency_ok
    rec = "SHIP" if ship else "DO NOT SHIP"

    reranker_path = summary["reranker_path"]
    model_label = (
        f"local cross-encoder `{summary['model']}` (CPU)"
        if reranker_path == "local"
        else f"`{summary['model']}` via OpenRouter (pairwise prompt)"
    )

    lines = []
    lines.append("# P3 Cross-Encoder Rerank Probe — 2026-05-07")
    lines.append("")
    lines.append("**Task:** `[P3_CROSS_ENCODER_RERANK_PROBE]` — measurement-only audit, no production code change.")
    lines.append(
        f"**Reranker:** {model_label}. **Candidate pool:** top-{summary['candidate_k']} from "
        f"`brain.recall()`. **Scoring:** P@{summary['score_k']} via case-insensitive "
        "substring match against expected docs (same rule as `[P3_HYDE_QUERY_REFORMULATION_PROBE]`)."
    )
    lines.append(
        f"**Queries:** {summary['num_queries']}. **Wall time:** {summary['elapsed_seconds']}s. "
        f"**Cost incurred:** ${summary['cost_usd']:.6f} (cap was <${COST_CAP_USD})."
    )
    lines.append(
        "**Distinct from HyDE:** HyDE rewrites the *query* before retrieval; rerank reorders "
        "the *candidate set* after retrieval. Different stage; the two can stack."
    )
    lines.append("")

    lines.append("## Headline")
    lines.append("")
    lines.append("| Metric | Baseline | Rerank | Delta |")
    lines.append("|---|---:|---:|---:|")
    lines.append(f"| **P@{summary['score_k']} (mean)** | {base:.4f} | {rerank:.4f} | {delta:+.4f} ({rel:+.1f}%) |")
    lines.append(f"| Queries with lift | — | — | {summary['queries_with_lift']} / {n} |")
    lines.append(f"| Queries with drop | — | — | {summary['queries_with_drop']} / {n} |")
    lines.append(f"| Queries unchanged | — | — | {summary['queries_unchanged']} / {n} |")
    lines.append("")
    lines.append("**Added rerank latency** (per query, on top of baseline retrieval):")
    lines.append("")
    lines.append("| Stat | Value |")
    lines.append("|---|---:|")
    lines.append(f"| p50 | {summary['rerank_latency_p50_ms']:.2f} ms |")
    lines.append(f"| p95 | {summary['rerank_latency_p95_ms']:.2f} ms |")
    lines.append(f"| mean | {summary['rerank_latency_mean_ms']:.2f} ms |")
    lines.append(f"| max | {summary['rerank_latency_max_ms']:.2f} ms |")
    lines.append(f"| Latency budget (p95 < X) | {LATENCY_BUDGET_MS:.0f} ms |")
    lines.append("")
    lines.append(f"**Recommendation: {rec}** as a runtime path.")
    lines.append("")

    # Reasoning block
    lines.append("### Reasoning")
    lines.append("")
    bullets = []
    if quality_ok:
        bullets.append(
            f"- Quality gate **PASS** — Δ P@3 = {delta:+.4f} (≥ +0.05 threshold) and "
            f"{pos}/{n} = {pos_rate*100:.0f}% of queries improved (≥ 60% threshold)."
        )
    else:
        if delta < 0:
            bullets.append(
                f"- Quality gate **FAIL** — Net P@3 dropped ({delta:+.4f}). The reranker "
                "promoted documents that scored worse on the substring ground truth than the "
                "baseline distance ordering."
            )
        elif delta < 0.05:
            bullets.append(
                f"- Quality gate **FAIL** — P@3 lift ({delta:+.4f}) is below the +0.05 "
                "absolute threshold. Inside the noise floor of a 45-query benchmark."
            )
        if pos_rate < 0.6:
            bullets.append(
                f"- Distribution gate **FAIL** — Only {pos}/{n} ({pos_rate*100:.0f}%) queries "
                "improved. Lift is not broadly distributed; gains on some queries offset by drops on others."
            )
    if latency_ok:
        bullets.append(
            f"- Latency gate **PASS** — p95 added latency {p95_lat:.1f} ms < {LATENCY_BUDGET_MS:.0f} ms budget. "
            "Cheap enough to run in the hot path."
        )
    else:
        bullets.append(
            f"- Latency gate **FAIL** — p95 added latency {p95_lat:.1f} ms ≥ {LATENCY_BUDGET_MS:.0f} ms budget. "
            "Even with a positive quality delta, this added cost would push retrieval past the "
            "<800ms PI target on 5%+ of queries. Acceptable only as an offline reranker (e.g. "
            "during dream cycles or precomputed for canned questions), not online recall."
        )
    if reranker_path == "llm":
        bullets.append(
            "- LLM-rerank path adds an extra LLM round-trip (1–3s typical). Not viable in the "
            "online recall path; included here only because the local cross-encoder couldn't "
            "be loaded in this environment."
        )
    lines.extend(bullets)
    lines.append("")

    if not ship:
        lines.append("**Alternative leverage** for the same 0.683 → 0.7 P@3 push:")
        lines.append("")
        lines.append(
            "- Per-query failure triage (`[P3_PER_QUERY_FAILURE_TRIAGE]`) — fixes the *content* "
            "of the candidate pool rather than re-sorting the same items."
        )
        lines.append(
            "- Chunk granularity audit (`[P3_CHUNK_GRANULARITY_AUDIT]`) — addresses why expected "
            "substrings aren't in the embedded chunks at all on the failing queries."
        )
        lines.append(
            "- HyDE probe (`[P3_HYDE_QUERY_REFORMULATION_PROBE]`) — already measured "
            "independently; see that report for the complementary upstream rewrite path."
        )
        lines.append("")

    lines.append("## Per-collection breakdown")
    lines.append("")
    lines.append("| Collection | n | Baseline P@3 | Rerank P@3 | Δ | Rerank p50 ms | Rerank p95 ms |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for c, v in sorted(summary["by_collection"].items(), key=lambda kv: -kv[1]["n"]):
        lines.append(
            f"| `{c}` | {v['n']} | {v['baseline_p3']:.4f} | {v['rerank_p3']:.4f} | "
            f"{v['delta']:+.4f} | {v['rerank_p50_ms']:.1f} | {v['rerank_p95_ms']:.1f} |"
        )
    lines.append("")

    lines.append("## Methodology")
    lines.append("")
    lines.append(
        "- **Fixture:** combined `BENCHMARK_PAIRS` from `scripts/brain_mem/retrieval_benchmark.py` "
        "(20 queries, the canonical source of the published 0.683 P@3) plus `data/golden_qa.json` "
        "(25 queries). Same scoring rule as the HyDE probe so deltas across the two probes are "
        "apples-to-apples."
    )
    lines.append(
        f"- **Baseline:** `clarvis.brain.brain.recall(query, n={CANDIDATE_K})` then sort by "
        "ascending distance and keep the global top-N. (`brain.recall` returns per-collection "
        "top-N concatenated and unsorted; the sort step matters.)"
    )
    if reranker_path == "local":
        lines.append(
            f"- **Rerank:** `sentence-transformers` `CrossEncoder('{summary['model']}')` on CPU. "
            "Predicts a relevance score per `(query, document)` pair (truncated to 512 chars "
            "per doc), reorders descending by score, scores P@3 on the new top-3."
        )
    else:
        lines.append(
            f"- **Rerank:** `{summary['model']}` via OpenRouter, single pairwise-batch prompt "
            "per query (asks for an index permutation; max 80 output tokens; temperature 0.0). "
            "Cost capped at $0.10."
        )
    lines.append(
        f"- **Decision rule:** SHIP iff (Δ P@3 ≥ +0.05 absolute) AND (≥60% of queries improved) "
        f"AND (added p95 latency < {LATENCY_BUDGET_MS:.0f} ms). All three gates must pass."
    )
    lines.append(
        "- **Latency:** measured per query around the rerank step only (cross-encoder.predict "
        "or LLM call), not including the baseline ChromaDB recall, so the number is the "
        "*added* online cost of inserting the reranker into the hot path."
    )
    lines.append("")

    lines.append("## Top movers")
    lines.append("")
    movers = sorted(summary["details"], key=lambda d: d["delta"], reverse=True)
    biggest_lifts = [d for d in movers if d["delta"] > 0][:5]
    biggest_drops = [d for d in movers[::-1] if d["delta"] < 0][:5]
    if biggest_lifts:
        lines.append("**Biggest lifts (rerank helped):**")
        lines.append("")
        for d in biggest_lifts:
            lines.append(f"- `{d['id']}` Δ{d['delta']:+.3f} — {d['query'][:90]}")
        lines.append("")
    if biggest_drops:
        lines.append("**Biggest drops (rerank hurt):**")
        lines.append("")
        for d in biggest_drops:
            lines.append(f"- `{d['id']}` Δ{d['delta']:+.3f} — {d['query'][:90]}")
        lines.append("")

    lines.append("## Stacking with HyDE")
    lines.append("")
    lines.append(
        "HyDE and rerank operate at different pipeline stages (query rewrite vs candidate "
        "reorder). In principle they stack: HyDE first to broaden the candidate pool, rerank "
        "second to focus the top-K. This probe deliberately holds the upstream query fixed so "
        "any delta is attributable to the rerank stage alone. A `HyDE+rerank` joint probe is a "
        "natural follow-up if either stage shows a positive ship signal in isolation."
    )
    lines.append("")

    lines.append("## Artifacts")
    lines.append("")
    lines.append("- Probe script: `scripts/audit/p3_rerank_probe.py`")
    lines.append(f"- Raw per-query results: `data/audit/p3_rerank_probe_2026-05-07.json`")
    lines.append("")

    lines.append("## Limitations")
    lines.append("")
    lines.append(
        "- N=45 queries is small. P@3 deltas of ±0.02 are inside sampling noise; the "
        "decision rule's ±0.05 threshold accounts for this."
    )
    lines.append(
        "- Substring-based hit checking is permissive (any expected substring in the document "
        "text counts). A reranker that pushes a *better* answer above a baseline-substring-"
        "matching one would *appear* to drop P@3 even though the result improved. Stricter "
        "`expected_id` matching is out of scope for a measurement-only probe."
    )
    lines.append(
        "- Latency is measured on a CPU-only host with no model warmup amortization between "
        "queries. The p95 is realistic for a long-running daemon; first-query cold start would "
        "be ~5–7s extra (model load), which is one-time and not counted here."
    )
    lines.append(
        "- `cross-encoder/ms-marco-MiniLM-L-6-v2` is trained on MSMARCO web passages. The "
        "Clarvis corpus is much narrower (internal KB about a single AI agent); the reranker "
        "may be slightly out-of-distribution. A domain-tuned reranker is a separate project; "
        "this probe answers only whether the off-the-shelf model is worth shipping."
    )

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="Cap queries (default: all, hard-capped at 50)")
    ap.add_argument("--out", default=REPORT_PATH)
    ap.add_argument("--reranker", default="auto", choices=["auto", "local", "llm"],
                    help="Reranker backend (default: auto — local cross-encoder if available, else LLM)")
    args = ap.parse_args()

    summary = run(limit=args.limit, reranker=args.reranker)

    os.makedirs(os.path.dirname(RAW_RESULTS_PATH), exist_ok=True)
    with open(RAW_RESULTS_PATH, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    path = write_report(summary, args.out)
    print()
    print("=" * 60)
    print(f"  Reranker:      {summary['reranker_path']} ({summary['model']})")
    print(f"  Baseline P@3:  {summary['baseline_p3']:.4f}")
    print(f"  Rerank   P@3:  {summary['rerank_p3']:.4f}")
    print(f"  Delta:         {summary['delta_p3']:+.4f}")
    print(f"  Rerank p50/p95: {summary['rerank_latency_p50_ms']:.1f} / {summary['rerank_latency_p95_ms']:.1f} ms")
    print(f"  Cost:          ${summary['cost_usd']:.6f}")
    print(f"  Report:        {path}")
    print(f"  Raw results:   {RAW_RESULTS_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
