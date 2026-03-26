#!/usr/bin/env python3
"""Research-memory dedupe / canonicalization for Clarvis.

Goal: identify repeated research conclusions in `clarvis-learnings` and collapse
redundant variants under a canonical keeper by marking them `status=superseded`.
This is safer than hard deletion and works with recall filtering.

Usage:
  python3 scripts/brain_research_dedupe.py audit
  python3 scripts/brain_research_dedupe.py apply --topic phi
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path('/home/agent/.openclaw/workspace')
sys.path.insert(0, str(WORKSPACE / 'scripts'))

from clarvis.brain import get_brain  # noqa: E402

TOPIC_PATTERNS = {
    'phi': [
        r'\bphi\b',
        r'\biit\b',
        r'integrated information theory',
        r'phi computation',
        r'phi approximation',
        r'phi approximations',
        r'phi proxies',
        r'scalable phi',
        r'consciousness architectures',
    ],
}

STOPWORDS = {
    'research', 'the', 'and', 'for', 'with', 'that', 'this', 'from', 'into', 'under',
    'exact', 'current', 'practical', 'systems', 'their', 'than', 'does', 'remain',
    'using', 'used', 'rather', 'should', 'small', 'large', 'larger', 'only', 'after',
    'where', 'which', 'while', 'being', 'they', 'them', 'have', 'has', 'are', 'not',
    'yet', 'via', 'agent', 'agents', 'clarvis', 'style', 'task', 'summary'
}


def normalize_topic_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'^\[research[^\]]*\]\s*', '', text)
    text = re.sub(r'^research:\s*', '', text)
    text = re.sub(r'\biit 4\.0\b', 'iit', text)
    text = re.sub(r'\bintegrated information theory\b', 'iit', text)
    text = re.sub(r'\bφ\b', 'phi', text)
    text = re.sub(r'[^a-z0-9\s-]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def token_signature(text: str) -> set[str]:
    toks = []
    for tok in normalize_topic_text(text).split():
        if len(tok) < 4 or tok in STOPWORDS:
            continue
        toks.append(tok)
    return set(toks)


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def is_research_memory(mem: dict, topic: str) -> bool:
    text = mem.get('document', '')
    meta = mem.get('metadata', {}) or {}
    source = str(meta.get('source', '')).lower()
    tags_raw = meta.get('tags', '')
    tags = tags_raw if isinstance(tags_raw, list) else str(tags_raw)
    text_l = text.lower().strip()

    # Strict research-only gate: avoid catching generic metrics / failure logs /
    # reasoning traces that merely mention Phi.
    researchish = (
        text_l.startswith('research:')
        or text_l.startswith('[research')
        or text_l.startswith('[research summary]')
        or source.startswith('research')
        or 'research' in str(tags).lower()
    )
    if not researchish:
        return False

    blob = f"{text}\n{source}\n{tags}".lower()
    pats = TOPIC_PATTERNS.get(topic, [])
    return any(re.search(p, blob, re.I) for p in pats)


def keeper_score(mem: dict) -> tuple:
    """Score a memory for keeper selection.  Higher = better keeper.

    Order: (active?, importance, access_count, length, created_at).
    A memory is considered inactive if its status is superseded/deleted
    OR if it already has a ``superseded_by`` pointer (inconsistent metadata).
    """
    meta = mem.get('metadata', {}) or {}
    imp = float(meta.get('importance', 0.0) or 0.0)
    acc = int(meta.get('access_count', 0) or 0)
    created = str(meta.get('created_at', ''))
    length = len(mem.get('document', ''))
    is_inactive = (
        str(meta.get('status', '')).lower() in {'superseded', 'deleted'}
        or bool(meta.get('superseded_by'))
    )
    status = 0 if is_inactive else 1
    return (status, imp, acc, length, created)


def build_clusters(memories: list[dict]) -> list[list[dict]]:
    clusters = []
    used = set()
    sigs = {m['id']: token_signature(m['document']) for m in memories}
    for mem in memories:
        if mem['id'] in used:
            continue
        cluster = [mem]
        used.add(mem['id'])
        for other in memories:
            if other['id'] in used:
                continue
            sim = jaccard(sigs[mem['id']], sigs[other['id']])
            same_prefix = normalize_topic_text(mem['document'])[:90] == normalize_topic_text(other['document'])[:90]
            if sim >= 0.55 or same_prefix:
                cluster.append(other)
                used.add(other['id'])
        clusters.append(cluster)
    return [c for c in clusters if len(c) > 1]


def audit(topic: str):
    b = get_brain()
    rows = b.get('clarvis-learnings', n=10000)
    candidates = [r for r in rows if is_research_memory(r, topic)]
    clusters = build_clusters(candidates)
    result = []
    for cluster in clusters:
        keeper = sorted(cluster, key=keeper_score, reverse=True)[0]
        result.append({
            'topic': topic,
            'cluster_size': len(cluster),
            'keeper': {'id': keeper['id'], 'document': keeper['document'][:220]},
            'duplicates': [
                {'id': m['id'], 'document': m['document'][:220], 'status': (m.get('metadata', {}) or {}).get('status')}
                for m in cluster if m['id'] != keeper['id']
            ],
        })
    print(json.dumps({'topic': topic, 'candidate_count': len(candidates), 'clusters': result}, indent=2, ensure_ascii=False))


def apply(topic: str):
    b = get_brain()
    rows = b.get('clarvis-learnings', n=10000)
    candidates = [r for r in rows if is_research_memory(r, topic)]
    clusters = build_clusters(candidates)
    applied = []
    for cluster in clusters:
        keeper = sorted(cluster, key=keeper_score, reverse=True)[0]
        dup_ids = [m['id'] for m in cluster if m['id'] != keeper['id'] and str((m.get('metadata', {}) or {}).get('status', '')).lower() != 'superseded']
        if not dup_ids:
            continue
        res = b.supersede_duplicates(keeper['id'], dup_ids, collection='clarvis-learnings', reason=f'research_duplicate_{topic}')
        applied.append({
            'keeper': keeper['id'],
            'updated': res.get('updated', []),
            'skipped': res.get('skipped', []),
        })
    out = {
        'topic': topic,
        'applied_clusters': len(applied),
        'details': applied,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }
    audit_path = WORKSPACE / 'data' / 'brain_hygiene' / f'research_dedupe_{topic}_{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}.json'
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=2, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    valid_topics = list(TOPIC_PATTERNS.keys())
    p1 = sub.add_parser('audit')
    p1.add_argument('--topic', default='phi', choices=valid_topics,
                     help=f'Topic to audit (choices: {valid_topics})')
    p2 = sub.add_parser('apply')
    p2.add_argument('--topic', default='phi', choices=valid_topics,
                     help=f'Topic to apply (choices: {valid_topics})')
    args = ap.parse_args()
    if args.cmd == 'audit':
        audit(args.topic)
    else:
        apply(args.topic)


if __name__ == '__main__':
    main()
