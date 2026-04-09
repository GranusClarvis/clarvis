"""
Context Compressor — core compression functions (canonical spine module).

Provides TF-IDF extractive compression, MMR reranking, queue compression,
and tiered context brief generation.

Usage:
    from clarvis.context.compressor import (
        tfidf_extract, mmr_rerank, compress_text,
        compress_queue, compress_episodes, generate_tiered_brief,
    )
"""

import json
import math
import os
import re
from collections import Counter
from datetime import datetime, timezone

WORKSPACE = os.environ.get(
    "CLARVIS_WORKSPACE", os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
)
QUEUE_FILE = os.path.join(WORKSPACE, "memory/evolution/QUEUE.md")
CAPABILITY_HISTORY = os.path.join(WORKSPACE, "data/capability_history.json")
PHI_HISTORY = os.path.join(WORKSPACE, "data/phi_history.json")

# Stopwords for TF-IDF
_STOPWORDS = frozenset(
    "a an the is are was were be been being have has had do does did will would "
    "shall should may might can could to of in for on with at by from as into "
    "through during before after above below between under again further then "
    "once here there when where why how all each every both few more most other "
    "some such no nor not only own same so than too very and but if or because "
    "until while that this these those it its he she they them their what which "
    "who whom".split()
)


# Per-category TF-IDF extraction ratios
_CATEGORY_RATIOS = {
    "code": 0.35,
    "research": 0.30,
    "maintenance": 0.30,
    "default": 0.25,
}

_CATEGORY_PATTERNS = {
    "code": re.compile(
        r'(?:implement|refactor|fix|add.*test|pytest|coverage|bug|regex|extract|'
        r'module|function|class|import|endpoint|api|cli|parser)', re.I),
    "research": re.compile(
        r'(?:research|analyze|investigate|survey|literature|paper|study|compare|'
        r'explore|evaluate|benchmark|audit)', re.I),
    "maintenance": re.compile(
        r'(?:health|monitor|backup|cleanup|compact|vacuum|watchdog|cron|rotate|'
        r'verify|check|status|report|graph.*compaction|dedup)', re.I),
}


def _classify_task_category(task_text):
    """Classify task into code/research/maintenance category."""
    if not task_text:
        return "default"
    for category, pattern in _CATEGORY_PATTERNS.items():
        if pattern.search(task_text):
            return category
    return "default"


def _extract_task_keywords(task_text):
    """Extract critical keywords from task description for pinning."""
    if not task_text:
        return set()
    keywords = set()
    for m in re.finditer(r'\[([A-Z][A-Z0-9_]+)\]', task_text):
        tag = m.group(1).lower()
        keywords.add(tag)
        for part in tag.split('_'):
            if len(part) >= 3:
                keywords.add(part)
    for m in re.finditer(r'[a-z][a-z0-9]*(?:_[a-z0-9]+)+', task_text):
        ident = m.group(0)
        keywords.add(ident)
        for part in ident.split('_'):
            if len(part) >= 3:
                keywords.add(part)
    for m in re.finditer(r'(\w+\.(?:py|sh|js|ts|json|md))', task_text):
        fname = m.group(1).replace('.py', '').replace('.sh', '').replace('.md', '')
        keywords.add(fname.lower())
        for part in fname.split('_'):
            if len(part) >= 3:
                keywords.add(part.lower())
    for m in re.finditer(r'[A-Z][a-z]+(?:[A-Z][a-z]+)+', task_text):
        keywords.add(m.group(0).lower())
    for w in re.findall(r'[a-z][a-z0-9_]+', task_text.lower()):
        if w not in _STOPWORDS and len(w) >= 4:
            keywords.add(w)
    return keywords


def _tokenize(text):
    """Split text into lowercase word tokens, filtering stopwords."""
    return [w for w in re.findall(r'[a-z][a-z0-9_]+', text.lower()) if w not in _STOPWORDS]


def _jaccard_similarity(tokens_a, tokens_b):
    """Jaccard similarity between two token sets."""
    if not tokens_a or not tokens_b:
        return 0.0
    sa, sb = set(tokens_a), set(tokens_b)
    intersection = len(sa & sb)
    union = len(sa | sb)
    return intersection / max(union, 1)


def _split_sentences(text):
    """Split text into sentence-like segments."""
    segments = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        if len(line) > 120:
            parts = re.split(r'(?<=[.!?])\s+', line)
            segments.extend(p.strip() for p in parts if p.strip())
        else:
            segments.append(line)
    return segments


def mmr_rerank(results, query_text, lambda_param=0.5, n=None):
    """Maximal Marginal Relevance reranking for brain recall results.

    Balances relevance to query with diversity among selected results.
    """
    if not results or len(results) <= 1:
        return list(results) if results else []

    n = n or len(results)

    relevances = []
    for r in results:
        dist = r.get("distance")
        if dist is not None:
            relevances.append(max(0.0, 1.0 / (1.0 + dist)))
        else:
            relevances.append(r.get("_actr_score", 0.5))

    max_rel = max(relevances) if relevances else 1.0
    if max_rel > 0:
        relevances = [r / max_rel for r in relevances]

    query_tokens = _tokenize(query_text)
    doc_token_sets = [set(_tokenize(r.get("document", ""))) for r in results]

    selected_indices = []
    remaining = set(range(len(results)))

    while remaining and len(selected_indices) < n:
        best_score = -float('inf')
        best_idx = None

        for idx in remaining:
            rel = relevances[idx]
            if query_tokens and doc_token_sets[idx]:
                query_overlap = len(set(query_tokens) & doc_token_sets[idx]) / max(len(set(query_tokens)), 1)
                rel = 0.7 * rel + 0.3 * query_overlap

            max_sim = 0.0
            for sel_idx in selected_indices:
                sim = _jaccard_similarity(doc_token_sets[idx], doc_token_sets[sel_idx])
                if sim > max_sim:
                    max_sim = sim

            mmr = lambda_param * rel - (1.0 - lambda_param) * max_sim
            if mmr > best_score:
                best_score = mmr
                best_idx = idx

        if best_idx is not None:
            selected_indices.append(best_idx)
            remaining.discard(best_idx)
        else:
            break

    return [results[i] for i in selected_indices]


def tfidf_extract(text, ratio=0.3, min_sentences=2, max_sentences=20, pinned_keywords=None):
    """Extractive compression via TF-IDF sentence scoring."""
    if not text or len(text) < 100:
        return text

    sentences = _split_sentences(text)
    if len(sentences) <= min_sentences:
        return text

    pinned = pinned_keywords or set()

    doc_freq = Counter()
    sentence_tokens = []
    for sent in sentences:
        tokens = _tokenize(sent)
        sentence_tokens.append(tokens)
        doc_freq.update(set(tokens))

    n_docs = len(sentences)

    scores = []
    for i, tokens in enumerate(sentence_tokens):
        if not tokens:
            scores.append(0.0)
            continue
        tf = Counter(tokens)
        score = 0.0
        for word, count in tf.items():
            tf_val = count / len(tokens)
            idf_val = math.log((n_docs + 1) / (doc_freq[word] + 1)) + 1
            score += tf_val * idf_val
        if re.search(r'\d+\.?\d*', sentences[i]):
            score *= 1.2
        if re.search(r'(?:error|fail|fix|target|metric|score|result|bug|critical)', sentences[i], re.I):
            score *= 1.15
        if pinned:
            token_set = set(tokens)
            pin_hits = len(pinned & token_set)
            if pin_hits:
                score *= 1.0 + 0.25 * pin_hits
        scores.append(score)

    target_chars = int(len(text) * ratio)
    n_keep = max(min_sentences, min(max_sentences, int(len(sentences) * ratio) + 1))

    ranked = sorted(range(len(sentences)), key=lambda i: scores[i], reverse=True)
    selected_indices = set()
    total_chars = 0
    for idx in ranked:
        if len(selected_indices) >= n_keep and total_chars >= target_chars:
            break
        selected_indices.add(idx)
        total_chars += len(sentences[idx])
        if len(selected_indices) >= max_sentences:
            break

    result = [sentences[i] for i in sorted(selected_indices)]
    return '\n'.join(result)


def compress_text(text, ratio=0.3, task_context=None):
    """Compress arbitrary text via extractive TF-IDF + MMR + deduplication.

    Args:
        text: Input text to compress.
        ratio: Base extraction ratio (overridden by category ratio if task_context given).
        task_context: Optional task description for category-specific ratio and keyword pinning.

    Returns (compressed_text, stats_dict).
    """
    if not text or len(text) < 150:
        return text, {"input_chars": len(text or ""), "output_chars": len(text or ""), "ratio": 1.0}

    input_chars = len(text)

    pinned_keywords = set()
    effective_ratio = ratio
    category = "default"
    if task_context:
        category = _classify_task_category(task_context)
        effective_ratio = _CATEGORY_RATIOS.get(category, ratio)
        pinned_keywords = _extract_task_keywords(task_context)

    extracted = tfidf_extract(text, ratio=effective_ratio, pinned_keywords=pinned_keywords or None)

    # Stage 2: MMR post-pass over extracted sentences to reduce redundancy
    lines = [line.strip() for line in extracted.split('\n') if line.strip()]
    if len(lines) > 1:
        mmr_items = [{"document": line, "distance": 0.0} for line in lines]
        lines = [item["document"] for item in mmr_rerank(mmr_items, text, lambda_param=0.35, n=len(lines))]

    # Stage 3: Exact-ish core dedup to catch residual near-duplicates
    seen_cores = set()
    deduped = []
    for line in lines:
        core = re.sub(r'[^a-z0-9 ]', '', line.lower().strip())[:50]
        if core in seen_cores:
            continue
        seen_cores.add(core)
        deduped.append(line)

    compressed = '\n'.join(deduped)
    output_chars = len(compressed)
    actual_ratio = output_chars / max(1, input_chars)

    return compressed, {
        "input_chars": input_chars,
        "output_chars": output_chars,
        "ratio": round(actual_ratio, 3),
        "sentences_in": len(_split_sentences(text)),
        "sentences_out": len(deduped),
        "mmr_applied": len(lines) > 1,
        "task_category": category,
        "pinned_keywords_count": len(pinned_keywords),
    }


def compress_queue(queue_file=None, max_recent_completed=5):
    """Compress QUEUE.md: pending tasks in full, last N completed as 1-liners."""
    queue_file = queue_file or QUEUE_FILE
    if not os.path.exists(queue_file):
        return "No evolution queue found."

    with open(queue_file, 'r') as f:
        lines = f.readlines()

    pending_tasks = []
    recent_completed = []
    current_section = ""

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('## '):
            current_section = stripped
            continue
        if '## Completed' in current_section:
            continue

        match_pending = re.match(r'^- \[ \] (.+)$', stripped)
        if match_pending:
            task_text = match_pending.group(1)
            core = re.split(r'\s*[\(—]', task_text, 1)[0].strip()
            if len(core) < 20:
                core = task_text[:150]
            pending_tasks.append({"section": current_section, "task": core})
            continue

        match_done = re.match(r'^- \[x\] (.+)$', stripped)
        if match_done:
            task_text = match_done.group(1)
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', task_text)
            date_str = date_match.group(1) if date_match else "unknown"
            core = re.split(r'\s*[\(—]', task_text, 1)[0].strip()
            if len(core) < 15:
                core = task_text[:100]
            recent_completed.append({"section": current_section, "task": core, "date": date_str})

    recent_completed.sort(key=lambda x: x["date"] if x["date"] != "unknown" else "0000", reverse=True)
    recent_completed = recent_completed[:max_recent_completed]

    output = ["=== EVOLUTION QUEUE (compressed) ===\n"]
    pending_by_section = {}
    for t in pending_tasks:
        sec = t["section"]
        if sec not in pending_by_section:
            pending_by_section[sec] = []
        pending_by_section[sec].append(t["task"])

    if pending_by_section:
        output.append(f"PENDING ({len(pending_tasks)} tasks):")
        for section, tasks in pending_by_section.items():
            output.append(f"\n{section}")
            for task in tasks:
                output.append(f"  - [ ] {task}")
    else:
        output.append("PENDING: 0 tasks (queue empty)")

    if recent_completed:
        output.append(f"\nRECENT COMPLETIONS (last {len(recent_completed)}):")
        for t in recent_completed:
            output.append(f"  [x] ({t['date']}) {t['task'][:80]}")

    output.append(f"\nTOTAL: {len(pending_tasks)} pending, {len(recent_completed)} recently completed")
    return "\n".join(output)


def compress_episodes(episodes, max_items=10):
    """Compress episodic recall to essentials (outcome, lesson, timestamp)."""
    if not episodes:
        return ""

    items = episodes[:max_items]
    lines = []
    for ep in items:
        if isinstance(ep, dict):
            outcome = ep.get("outcome", ep.get("metadata", {}).get("outcome", "?"))
            task = ep.get("task", ep.get("document", ""))[:80]
            lesson = ep.get("lesson", ep.get("metadata", {}).get("lesson", ""))[:60]
            valence = ep.get("valence", ep.get("metadata", {}).get("valence", ""))
            line = f"  [{outcome}] {task}"
            if lesson:
                line += f" → {lesson}"
            if valence:
                line += f" (v={valence})"
            lines.append(line)
        else:
            lines.append(f"  {str(ep)[:120]}")

    return "EPISODIC RECALL:\n" + "\n".join(lines)


def get_latest_scores():
    """Read latest capability scores and Phi from history files.

    Returns compact dict for embedding in prompts.
    """
    scores = {}
    if os.path.exists(CAPABILITY_HISTORY):
        try:
            with open(CAPABILITY_HISTORY, 'r') as f:
                history = json.load(f)
            if history:
                latest = history[-1]
                scores["capabilities"] = {
                    k: round(v, 2) for k, v in latest.get("scores", {}).items()
                    if isinstance(v, (int, float))
                }
                scores["capability_avg"] = round(
                    sum(scores["capabilities"].values()) / max(1, len(scores["capabilities"])), 2
                )
        except Exception:
            pass
    if os.path.exists(PHI_HISTORY):
        try:
            with open(PHI_HISTORY, 'r') as f:
                phi_hist = json.load(f)
            if phi_hist:
                scores["phi"] = round(phi_hist[-1].get("phi", 0), 3)
        except Exception:
            pass
    return scores


# ============================================================================
# Graduated Compaction — PRUNE → SNIP → COMPRESS
#
# Three tiers applied in order, cheapest first:
#   Tier 0 PRUNE:  Drop stale/irrelevant items from sections (zero-cost)
#   Tier 1 SNIP:   Middle-truncate sections that exceed budget (zero-cost)
#   Tier 2 COMPRESS: TF-IDF extractive compression (existing, light CPU)
# ============================================================================

# Staleness thresholds per section type
_PRUNE_STALE_DAYS = {
    "episodes": 14,
    "knowledge": 30,
    "procedures": 60,
    "default": 21,
}


def _parse_age_days(item):
    """Extract age in days from a context item dict or string.

    Looks for ISO dates, 'YYYY-MM-DD' patterns, or 'last_seen: ...' fields.
    Returns None if no date found.
    """
    text = ""
    if isinstance(item, dict):
        for key in ("ts", "timestamp", "last_seen", "date", "last_used"):
            if key in item:
                text = str(item[key])
                break
        if not text:
            text = str(item.get("document", item.get("text", "")))
    else:
        text = str(item)

    # Try ISO date
    m = re.search(r'(\d{4}-\d{2}-\d{2})', text)
    if m:
        try:
            dt = datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - dt).days
        except ValueError:
            pass
    return None


def prune_stale(items, section_type="default", max_age_days=None):
    """Tier 0 PRUNE — remove items older than staleness threshold.

    Args:
        items: List of context items (dicts or strings).
        section_type: Category key for staleness threshold lookup.
        max_age_days: Override staleness threshold (days).

    Returns:
        (kept_items, pruned_count)
    """
    threshold = max_age_days or _PRUNE_STALE_DAYS.get(section_type, _PRUNE_STALE_DAYS["default"])
    kept = []
    pruned = 0
    for item in items:
        age = _parse_age_days(item)
        if age is not None and age > threshold:
            pruned += 1
        else:
            kept.append(item)
    return kept, pruned


def snip_middle(text, budget_chars, ellipsis="\n[...snipped...]\n"):
    """Tier 1 SNIP — keep head + tail, truncate middle.

    Preserves the first ~40% and last ~40% of text, replacing the
    middle with an ellipsis marker. Useful for sections where both
    the beginning (headers, context) and end (latest items) matter.

    Args:
        text: Input text.
        budget_chars: Maximum character budget.
        ellipsis: Marker for snipped region.

    Returns:
        Snipped text (or original if already within budget).
    """
    if len(text) <= budget_chars:
        return text
    usable = budget_chars - len(ellipsis)
    if usable <= 0:
        return text[:budget_chars]
    head_len = int(usable * 0.4)
    tail_len = usable - head_len
    return text[:head_len] + ellipsis + text[-tail_len:]


def graduated_compact(text, budget_chars, section_type="default", items=None):
    """Apply graduated compaction: PRUNE → SNIP → COMPRESS.

    Args:
        text: The section text to compact.
        budget_chars: Target character budget.
        section_type: Category for staleness thresholds.
        items: Optional list of structured items (for Tier 0 pruning).
               If provided, items are pruned first, then rejoined as text.

    Returns:
        (compacted_text, stats_dict)
    """
    stats = {"tier_used": "none", "original_len": len(text), "pruned": 0, "snipped": False}

    working_text = text

    # Tier 0: PRUNE stale items if structured items provided
    if items is not None:
        kept, pruned = prune_stale(items, section_type)
        stats["pruned"] = pruned
        if pruned > 0:
            # Rejoin kept items
            parts = []
            for item in kept:
                if isinstance(item, dict):
                    parts.append(item.get("document", item.get("text", str(item))))
                else:
                    parts.append(str(item))
            working_text = "\n".join(parts)
            stats["tier_used"] = "prune"

    # Check if within budget after pruning
    if len(working_text) <= budget_chars:
        stats["final_len"] = len(working_text)
        return working_text, stats

    # Tier 1: SNIP middle
    snipped = snip_middle(working_text, budget_chars)
    if len(snipped) < len(working_text):
        stats["snipped"] = True
        stats["tier_used"] = "snip"
        working_text = snipped

    # Check if within budget after snipping
    if len(working_text) <= budget_chars:
        stats["final_len"] = len(working_text)
        return working_text, stats

    # Tier 2: COMPRESS via TF-IDF extraction
    ratio = budget_chars / max(len(working_text), 1)
    compressed = tfidf_extract(working_text, ratio=min(ratio, 0.5))
    stats["tier_used"] = "compress"
    stats["final_len"] = len(compressed)
    return compressed, stats


def generate_tiered_brief(current_task="", tier="standard", episodic_hints=None, knowledge_hints=None):
    """Generate context brief at the specified tier.

    Tiers:
        minimal: Goals + working context (~200 tokens)
        standard: + introspection, episodes, failures, queue (~1K tokens)
        full: + everything (~2K tokens)
    """
    sections = []

    # Working context (all tiers)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    sections.append(f"[{now_str}] Task: {current_task[:200]}" if current_task else f"[{now_str}]")

    # Queue summary (standard+)
    if tier in ("standard", "full"):
        try:
            queue_summary = compress_queue()
            # Keep only first 500 chars for brief
            if len(queue_summary) > 500:
                queue_summary = queue_summary[:500] + "\n  ..."
            sections.append(queue_summary)
        except Exception:
            pass

    # Episodic hints (standard+)
    if tier in ("standard", "full") and episodic_hints:
        ep_text = compress_episodes(episodic_hints)
        if ep_text:
            sections.append(ep_text)

    # Knowledge hints (full only)
    if tier == "full" and knowledge_hints:
        if isinstance(knowledge_hints, list):
            kh_lines = []
            for kh in knowledge_hints[:5]:
                if isinstance(kh, dict):
                    doc = kh.get("document", "")[:100]
                    col = kh.get("collection", "")
                    kh_lines.append(f"  [{col}] {doc}")
                else:
                    kh_lines.append(f"  {str(kh)[:100]}")
            if kh_lines:
                sections.append("KNOWLEDGE:\n" + "\n".join(kh_lines))

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Health compression (migrated from scripts/tools/context_compressor.py)
# ---------------------------------------------------------------------------

def _extract_calibration(calibration_output):
    """Extract Brier score and accuracy from calibration output."""
    brier_match = re.search(r'[Bb]rier[:\s=]*([0-9.]+)', calibration_output)
    accuracy_match = re.search(r'(\d+)/(\d+)\s*correct|accuracy[:\s=]*([0-9.]+)', calibration_output)
    brier = brier_match.group(1) if brier_match else "?"
    if accuracy_match:
        accuracy = f"{accuracy_match.group(1)}/{accuracy_match.group(2)}" if accuracy_match.group(1) else accuracy_match.group(3)
    else:
        accuracy = "?"
    return f"Calibration: Brier={brier}, accuracy={accuracy}"


def _extract_capabilities(capability_output):
    """Extract capability scores into summary lines."""
    scores = re.findall(r'(\w[\w_]+)[:=]\s*([0-9.]+)', capability_output)
    if not scores:
        return []
    score_pairs = [(name, float(val)) for name, val in scores if 0 <= float(val) <= 1.0]
    if not score_pairs:
        return []
    score_pairs.sort(key=lambda x: x[1])
    worst = score_pairs[0]
    avg = sum(v for _, v in score_pairs) / len(score_pairs)
    scores_str = ", ".join(f"{n}={v:.2f}" for n, v in score_pairs)
    return [
        f"Capabilities: avg={avg:.2f}, worst={worst[0]}={worst[1]:.2f}, n={len(score_pairs)}",
        f"  Scores: {scores_str}",
    ]


def compress_health(
    calibration_output="",
    phi_output="",
    capability_output="",
    retrieval_output="",
    episode_output="",
    goal_output="",
    param_output="",
    domain_output="",
):
    """Compress multi-line health data into compact key=value summary.

    Typical reduction: 8KB -> 1KB (87% token savings).
    """
    summary = ["=== SYSTEM HEALTH (compressed) ==="]

    if calibration_output:
        summary.append(_extract_calibration(calibration_output))

    if phi_output:
        phi_match = re.search(r'[Pp]hi[:\s=]*([0-9.]+)', phi_output)
        trend_match = re.search(r'trend[:\s=]*([a-z_]+|[↑↓→]+)', phi_output, re.IGNORECASE)
        summary.append(f"Phi={phi_match.group(1) if phi_match else '?'} (trend: {trend_match.group(1) if trend_match else 'stable'})")

    if capability_output:
        summary.extend(_extract_capabilities(capability_output))

    if retrieval_output:
        hit_match = re.search(r'hit[_ ]rate[:\s=]*([0-9.]+)%?', retrieval_output, re.IGNORECASE)
        health_match = re.search(r'(HEALTHY|DEGRADED|CRITICAL)', retrieval_output)
        summary.append(f"Retrieval: hit_rate={hit_match.group(1) if hit_match else '?'}%, status={health_match.group(1) if health_match else '?'}")

    if episode_output:
        count_match = re.search(r'(\d+)\s*episodes?', episode_output)
        success_match = re.search(r'success[:\s=]*([0-9.]+)%?', episode_output, re.IGNORECASE)
        summary.append(f"Episodes: n={count_match.group(1) if count_match else '?'}, success_rate={success_match.group(1) if success_match else '?'}%")

    if goal_output:
        stalled_match = re.search(r'(\d+)\s*stalled', goal_output, re.IGNORECASE)
        tasks_match = re.search(r'(\d+)\s*tasks?\s*(generated|added)', goal_output, re.IGNORECASE)
        summary.append(f"Goals: {stalled_match.group(1) if stalled_match else '0'} stalled, {tasks_match.group(1) if tasks_match else '0'} remediation tasks generated")

    if not any(line for line in summary if not line.startswith("===")):
        summary.append("No health data available this cycle.")

    return "\n".join(summary)


def generate_context_brief(queue_file=None):
    """Generate a full compressed context brief for Claude Code prompts.

    Combines compressed queue + latest scores into a single compact payload.
    This is the legacy brief generator; prefer generate_tiered_brief() from
    clarvis.context.assembly for new code.

    Returns string (~1-3KB instead of ~50KB).
    """
    queue_file = queue_file or QUEUE_FILE
    brief_parts = []

    brief_parts.append(compress_queue(queue_file))

    scores = get_latest_scores()
    if scores:
        brief_parts.append("\n=== LATEST METRICS ===")
        if "capabilities" in scores:
            caps = scores["capabilities"]
            worst_k = min(caps, key=caps.get) if caps else "?"
            worst_v = caps.get(worst_k, "?") if caps else "?"
            brief_parts.append(f"Capability avg={scores.get('capability_avg', '?')}, worst={worst_k}={worst_v}")
            brief_parts.append(f"  All: {', '.join(f'{k}={v}' for k, v in sorted(caps.items(), key=lambda x: x[1]))}")
        if "phi" in scores:
            brief_parts.append(f"Phi={scores['phi']}")

    try:
        from clarvis.brain import brain
        stats = brain.stats()
        brief_parts.append(f"Brain: {stats['total_memories']} memories, {stats['graph_edges']} edges")
    except Exception:
        pass

    return "\n".join(brief_parts)
