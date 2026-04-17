#!/usr/bin/env python3
"""Benchmark four retrieval routes on representative tasks.

Routes:
  1. Raw brain: direct brain.recall() with no enrichment
  2. Wiki-first: wiki canonical lookup → brain enrichment
  3. Combined: full brain_preflight_context() (brain + MMR + enrichment)
  4. Minimal direct: task text only, no brain search

Metrics: latency, result count, avg distance, content coverage (unique tokens).
"""

import json
import os
import sys
import time

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE",
                           "/home/agent/.openclaw/workspace")
sys.path.insert(0, WORKSPACE)

# Representative tasks spanning different domains
TASKS = [
    {
        "id": "code_fix",
        "text": "Fix the votingPower spoofing vulnerability in SWO governance endpoint",
        "domain": "code",
    },
    {
        "id": "brain_maintenance",
        "text": "Run brain health check and optimize graph compaction for orphan edges",
        "domain": "infrastructure",
    },
    {
        "id": "research",
        "text": "Research Absolute Zero Reasoner self-play training and its applicability to our metacognition module",
        "domain": "research",
    },
    {
        "id": "reflection",
        "text": "Reflect on recent task outcomes and identify patterns in failure modes",
        "domain": "memory",
    },
    {
        "id": "project_delivery",
        "text": "Create PR for Star Sanctuary companion panel with wallet-gated access",
        "domain": "code",
    },
]


def unique_tokens(text):
    """Count unique lowercase tokens (rough content diversity metric)."""
    if not text:
        return 0
    return len(set(text.lower().split()))


def route_raw_brain(task_text, n=5):
    """Route 1: Raw brain.recall() — no enrichment, no MMR."""
    from clarvis.brain import get_brain
    from clarvis.brain.constants import LEARNINGS, MEMORIES, EPISODES

    b = get_brain()
    t0 = time.monotonic()
    results = b.recall(task_text, collections=[LEARNINGS, MEMORIES, EPISODES],
                       n=n, min_importance=0.3)
    elapsed = time.monotonic() - t0

    texts = []
    distances = []
    for r in (results or []):
        texts.append(r.get("document", "")[:160])
        distances.append(r.get("distance", 1.0))

    combined_text = "\n".join(texts)
    return {
        "route": "raw_brain",
        "latency_ms": round(elapsed * 1000, 1),
        "result_count": len(results or []),
        "avg_distance": round(sum(distances) / len(distances), 4) if distances else None,
        "min_distance": round(min(distances), 4) if distances else None,
        "unique_tokens": unique_tokens(combined_text),
        "text_preview": combined_text[:300],
    }


def route_wiki_first(task_text, n=5):
    """Route 2: Wiki canonical lookup then brain enrichment."""
    from clarvis.wiki.canonical import CanonicalResolver
    from clarvis.brain import get_brain
    from clarvis.brain.constants import LEARNINGS, MEMORIES, EPISODES

    t0 = time.monotonic()

    # Step 1: Wiki lookup
    wiki_hits = []
    try:
        resolver = CanonicalResolver()
        # Extract key terms from task for wiki lookup
        terms = [w for w in task_text.lower().split()
                 if len(w) > 3 and w not in {"with", "from", "that", "this", "have",
                                              "been", "will", "should", "could", "would",
                                              "their", "there", "about", "after", "before"}]
        for term in terms[:8]:
            slug = resolver.resolve(term)
            if slug:
                wiki_hits.append(slug)
    except Exception:
        pass

    wiki_text = ""
    if wiki_hits:
        wiki_dir = os.path.join(WORKSPACE, "knowledge", "wiki")
        for slug in wiki_hits[:3]:
            # Try to find the wiki page
            for subdir in ["concepts", "projects", "procedures", "people"]:
                path = os.path.join(wiki_dir, subdir, f"{slug}.md")
                if os.path.exists(path):
                    try:
                        with open(path) as f:
                            content = f.read()
                        # Take first 200 chars after frontmatter
                        if "---" in content:
                            parts = content.split("---", 2)
                            if len(parts) >= 3:
                                content = parts[2]
                        wiki_text += content[:200] + "\n"
                    except Exception:
                        pass

    # Step 2: Brain recall (enriched query if wiki found anything)
    b = get_brain()
    enriched_query = task_text
    if wiki_text:
        enriched_query = f"{task_text}\n\nRelated wiki context: {wiki_text[:200]}"
    results = b.recall(enriched_query, collections=[LEARNINGS, MEMORIES, EPISODES],
                       n=n, min_importance=0.3)

    elapsed = time.monotonic() - t0

    texts = []
    distances = []
    for r in (results or []):
        texts.append(r.get("document", "")[:160])
        distances.append(r.get("distance", 1.0))
    if wiki_text:
        texts.insert(0, wiki_text[:160])

    combined_text = "\n".join(texts)
    return {
        "route": "wiki_first",
        "latency_ms": round(elapsed * 1000, 1),
        "result_count": len(results or []) + len(wiki_hits),
        "wiki_hits": len(wiki_hits),
        "avg_distance": round(sum(distances) / len(distances), 4) if distances else None,
        "min_distance": round(min(distances), 4) if distances else None,
        "unique_tokens": unique_tokens(combined_text),
        "text_preview": combined_text[:300],
    }


def route_combined(task_text):
    """Route 3: Full brain_preflight_context (brain + MMR + enrichment + budgeting)."""
    from clarvis.heartbeat.brain_bridge import brain_preflight_context

    t0 = time.monotonic()
    ctx = brain_preflight_context(task_text, n_knowledge=5, graph_expand=False)
    elapsed = time.monotonic() - t0

    combined_text = "\n".join(filter(None, [
        ctx.get("goals_text", ""),
        ctx.get("context", ""),
        ctx.get("knowledge_hints", ""),
        ctx.get("working_memory", ""),
    ]))

    return {
        "route": "combined",
        "latency_ms": round(elapsed * 1000, 1),
        "has_goals": bool(ctx.get("goals_text")),
        "has_context": bool(ctx.get("context")),
        "has_knowledge": bool(ctx.get("knowledge_hints")),
        "has_working_memory": bool(ctx.get("working_memory")),
        "unique_tokens": unique_tokens(combined_text),
        "brain_timings": ctx.get("brain_timings", {}),
        "text_preview": combined_text[:300],
    }


def route_minimal(task_text):
    """Route 4: Minimal direct — task text only, no brain search."""
    t0 = time.monotonic()
    # Simulate minimal tier: just task text + queue status
    queue_file = os.path.join(WORKSPACE, "memory", "evolution", "QUEUE.md")
    queue_snippet = ""
    try:
        with open(queue_file) as f:
            lines = f.readlines()
        # Extract just the first few P0 items
        in_p0 = False
        p0_lines = []
        for line in lines[:60]:
            if "## P0" in line:
                in_p0 = True
            elif "## P1" in line:
                break
            elif in_p0 and line.strip().startswith("- ["):
                p0_lines.append(line.strip()[:100])
        queue_snippet = "\n".join(p0_lines[:5])
    except Exception:
        pass

    elapsed = time.monotonic() - t0

    combined_text = f"TASK: {task_text}\nQUEUE:\n{queue_snippet}"
    return {
        "route": "minimal",
        "latency_ms": round(elapsed * 1000, 1),
        "unique_tokens": unique_tokens(combined_text),
        "text_preview": combined_text[:300],
    }


def run_benchmark():
    """Run all routes on all tasks and report."""
    print("=" * 70)
    print("BRAIN/WIKI CONTEXT ROUTE BENCHMARK")
    print("=" * 70)

    all_results = []

    for task in TASKS:
        print(f"\n--- Task: {task['id']} ({task['domain']}) ---")
        print(f"  Query: {task['text'][:80]}")

        task_results = {"task": task["id"], "domain": task["domain"]}

        for route_fn, name in [
            (lambda t: route_raw_brain(t), "raw_brain"),
            (lambda t: route_wiki_first(t), "wiki_first"),
            (lambda t: route_combined(t), "combined"),
            (lambda t: route_minimal(t), "minimal"),
        ]:
            try:
                r = route_fn(task["text"])
                task_results[name] = r
                latency = r.get("latency_ms", "?")
                tokens = r.get("unique_tokens", 0)
                count = r.get("result_count", "-")
                dist = r.get("avg_distance") or r.get("min_distance") or "-"
                print(f"  {name:12s}: {latency:>7}ms | tokens={tokens:>4} | results={count} | dist={dist}")
            except Exception as e:
                task_results[name] = {"error": str(e)}
                print(f"  {name:12s}: ERROR — {e}")

        all_results.append(task_results)

    # Summary
    print("\n" + "=" * 70)
    print("AGGREGATE SUMMARY")
    print("=" * 70)

    for route_name in ["raw_brain", "wiki_first", "combined", "minimal"]:
        latencies = []
        token_counts = []
        for tr in all_results:
            r = tr.get(route_name, {})
            if "error" not in r:
                latencies.append(r.get("latency_ms", 0))
                token_counts.append(r.get("unique_tokens", 0))

        if latencies:
            avg_lat = sum(latencies) / len(latencies)
            avg_tok = sum(token_counts) / len(token_counts)
            print(f"  {route_name:12s}: avg_latency={avg_lat:>7.1f}ms | avg_tokens={avg_tok:>5.1f} | samples={len(latencies)}")

    # Save results
    out_path = os.path.join(WORKSPACE, "data", "benchmarks",
                            "brain_wiki_route_bench.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        # Strip text_preview for compact storage
        clean = []
        for tr in all_results:
            c = {"task": tr["task"], "domain": tr["domain"]}
            for rn in ["raw_brain", "wiki_first", "combined", "minimal"]:
                r = dict(tr.get(rn, {}))
                r.pop("text_preview", None)
                c[rn] = r
            clean.append(c)
        json.dump({"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "results": clean}, f, indent=2)
    print(f"\n  Results saved to: {out_path}")


if __name__ == "__main__":
    run_benchmark()
