#!/usr/bin/env python3
"""Attention visualizer for brain search.

Shows which query tokens most influence retrieval results by computing
per-token embedding contributions against result embeddings.

Uses the same ONNX MiniLM-L6-v2 model as ClarvisDB for consistency.

Usage:
    python3 scripts/attention_visualizer.py "what are my goals?"
    python3 scripts/attention_visualizer.py "how to spawn claude code" --n 5
    python3 scripts/attention_visualizer.py "recent episodes" --output /tmp/attn.html
"""

import argparse
import html
import json
import os
import sys
import numpy as np

# Paths
MODEL_DIR = os.path.expanduser("~/.cache/chroma/onnx_models/all-MiniLM-L6-v2/onnx")
MODEL_PATH = os.path.join(MODEL_DIR, "model.onnx")
TOKENIZER_PATH = os.path.join(MODEL_DIR, "tokenizer.json")
VOCAB_PATH = os.path.join(MODEL_DIR, "vocab.txt")

DEFAULT_OUTPUT = "/tmp/clarvis_attention.html"


def load_tokenizer():
    """Load the HuggingFace tokenizer from JSON."""
    with open(TOKENIZER_PATH) as f:
        tok_data = json.load(f)
    # Build vocab from vocab.txt (id -> token)
    vocab = {}
    with open(VOCAB_PATH) as f:
        for idx, line in enumerate(f):
            vocab[idx] = line.strip()
    return tok_data, vocab


def tokenize(text, tok_data, vocab):
    """Simple WordPiece tokenization matching the ONNX model's expectations."""
    # Use the tokenizer's pre-tokenization (split on whitespace + punctuation)
    tokens = []
    token_ids = []

    # Build reverse vocab (token -> id)
    rev_vocab = {v: k for k, v in vocab.items()}

    # Add [CLS]
    cls_id = rev_vocab.get("[CLS]", 101)
    tokens.append("[CLS]")
    token_ids.append(cls_id)

    # Simple whitespace split + WordPiece
    words = text.lower().split()
    for word in words:
        # Try full word first
        if word in rev_vocab:
            tokens.append(word)
            token_ids.append(rev_vocab[word])
        else:
            # WordPiece: greedily match longest prefix, then ##suffixes
            remaining = word
            is_first = True
            while remaining:
                matched = False
                for end in range(len(remaining), 0, -1):
                    subword = remaining[:end] if is_first else f"##{remaining[:end]}"
                    if subword in rev_vocab:
                        tokens.append(subword)
                        token_ids.append(rev_vocab[subword])
                        remaining = remaining[end:]
                        is_first = False
                        matched = True
                        break
                if not matched:
                    # Unknown token
                    unk_id = rev_vocab.get("[UNK]", 100)
                    tokens.append("[UNK]")
                    token_ids.append(unk_id)
                    remaining = remaining[1:]
                    is_first = False

    # Add [SEP]
    sep_id = rev_vocab.get("[SEP]", 102)
    tokens.append("[SEP]")
    token_ids.append(sep_id)

    return tokens, token_ids


def get_hidden_states(token_ids):
    """Run ONNX model and get per-token hidden states."""
    import onnxruntime as ort

    session = ort.InferenceSession(MODEL_PATH)
    input_ids = np.array([token_ids], dtype=np.int64)
    attention_mask = np.ones_like(input_ids, dtype=np.int64)
    token_type_ids = np.zeros_like(input_ids, dtype=np.int64)

    outputs = session.run(
        None,
        {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "token_type_ids": token_type_ids,
        },
    )
    # last_hidden_state: (1, seq_len, 384)
    return outputs[0][0]  # (seq_len, 384)


def mean_pool(hidden_states):
    """Mean pooling over token dimension (excluding [CLS] and [SEP])."""
    # Exclude first ([CLS]) and last ([SEP])
    content = hidden_states[1:-1]
    if len(content) == 0:
        return hidden_states.mean(axis=0)
    return content.mean(axis=0)


def cosine_sim(a, b):
    """Cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def compute_token_contributions(hidden_states, tokens, result_embedding):
    """Compute per-token contribution to matching a result.

    For each content token, measures how much that token's hidden state
    aligns with the result embedding (cosine similarity).
    Returns list of (token, score) pairs.
    """
    contributions = []
    for i, token in enumerate(tokens):
        if token in ("[CLS]", "[SEP]"):
            contributions.append((token, 0.0))
            continue
        sim = cosine_sim(hidden_states[i], result_embedding)
        contributions.append((token, sim))

    # Normalize scores to [0, 1] range for visualization
    scores = [s for _, s in contributions if s > 0]
    if scores:
        min_s, max_s = min(scores), max(scores)
        rng = max_s - min_s if max_s > min_s else 1.0
        contributions = [
            (t, (s - min_s) / rng if s > 0 else 0.0)
            for t, s in contributions
        ]
    return contributions


def score_to_color(score):
    """Map score [0,1] to a blue→red color gradient."""
    # 0.0 = light blue, 1.0 = deep red
    if score <= 0:
        return "rgba(200, 220, 240, 0.3)"
    r = int(60 + 195 * score)
    g = int(120 * (1 - score))
    b = int(200 * (1 - score))
    alpha = 0.3 + 0.7 * score
    return f"rgba({r}, {g}, {b}, {alpha:.2f})"


def generate_html(query, results_with_contributions, output_path):
    """Generate an HTML visualization."""
    parts = []
    parts.append("""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Clarvis Brain — Attention Visualization</title>
<style>
body { font-family: 'SF Mono', 'Fira Code', monospace; background: #0d1117; color: #c9d1d9; margin: 2em; }
h1 { color: #58a6ff; font-size: 1.4em; }
h2 { color: #8b949e; font-size: 1.1em; margin-top: 2em; }
.query-box { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 1em; margin: 1em 0; }
.token { display: inline-block; padding: 2px 4px; margin: 1px; border-radius: 3px; font-size: 0.95em; }
.result { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 1em; margin: 0.8em 0; }
.result-meta { color: #8b949e; font-size: 0.85em; margin-bottom: 0.5em; }
.result-text { color: #c9d1d9; font-size: 0.9em; white-space: pre-wrap; max-height: 6em; overflow: hidden; }
.score-bar { display: inline-block; height: 8px; border-radius: 4px; margin-left: 0.5em; vertical-align: middle; }
.legend { display: flex; gap: 1em; margin: 1em 0; font-size: 0.85em; color: #8b949e; }
.legend-item { display: flex; align-items: center; gap: 0.3em; }
.legend-swatch { width: 20px; height: 12px; border-radius: 3px; }
.agg-section { margin-top: 2em; }
.agg-bar { display: flex; align-items: center; margin: 0.3em 0; }
.agg-token { width: 120px; text-align: right; padding-right: 0.8em; font-size: 0.9em; }
.agg-fill { height: 16px; border-radius: 3px; min-width: 2px; }
.agg-val { padding-left: 0.5em; font-size: 0.85em; color: #8b949e; }
footer { margin-top: 3em; color: #484f58; font-size: 0.8em; border-top: 1px solid #21262d; padding-top: 1em; }
</style></head><body>
""")

    parts.append(f'<h1>🧠 Clarvis Brain — Attention Visualization</h1>')
    parts.append(f'<div class="query-box"><strong>Query:</strong> {html.escape(query)}</div>')

    # Legend
    parts.append("""<div class="legend">
<div class="legend-item"><div class="legend-swatch" style="background: rgba(200, 220, 240, 0.3)"></div> Low influence</div>
<div class="legend-item"><div class="legend-swatch" style="background: rgba(158, 60, 40, 0.65)"></div> Medium</div>
<div class="legend-item"><div class="legend-swatch" style="background: rgba(255, 0, 0, 1.0)"></div> High influence</div>
</div>""")

    # Aggregate scores across all results
    aggregate = {}
    count = {}

    for idx, (result, contributions) in enumerate(results_with_contributions):
        dist = result.get("distance", 0)
        sim = 1 - dist if dist < 1 else 0
        collection = result.get("collection", "?")
        text_preview = (result.get("document") or result.get("text", ""))[:200]

        parts.append(f'<h2>Result #{idx + 1} — {html.escape(collection)} (sim={sim:.3f})</h2>')
        parts.append('<div class="result">')

        # Token heatmap
        parts.append('<div style="margin-bottom: 0.8em;">')
        for token, score in contributions:
            if token in ("[CLS]", "[SEP]"):
                continue
            color = score_to_color(score)
            display = html.escape(token.replace("##", "·"))
            parts.append(f'<span class="token" style="background: {color}" title="score: {score:.3f}">{display}</span>')

            # Accumulate for aggregate
            clean = token.replace("##", "")
            if clean and token not in ("[CLS]", "[SEP]"):
                aggregate[clean] = aggregate.get(clean, 0) + score
                count[clean] = count.get(clean, 0) + 1
        parts.append('</div>')

        # Result text
        parts.append(f'<div class="result-meta">Collection: {html.escape(collection)} | Distance: {dist:.4f}</div>')
        parts.append(f'<div class="result-text">{html.escape(text_preview)}</div>')
        parts.append('</div>')

    # Aggregate token importance
    if aggregate:
        avg_scores = {t: aggregate[t] / count[t] for t in aggregate}
        sorted_tokens = sorted(avg_scores.items(), key=lambda x: -x[1])
        max_score = max(s for _, s in sorted_tokens) if sorted_tokens else 1

        parts.append('<div class="agg-section">')
        parts.append('<h2>Aggregate Token Importance (averaged across results)</h2>')
        for token, score in sorted_tokens[:15]:
            width = int(300 * score / max_score) if max_score > 0 else 0
            color = score_to_color(score / max_score if max_score > 0 else 0)
            parts.append(f'<div class="agg-bar">')
            parts.append(f'<div class="agg-token">{html.escape(token)}</div>')
            parts.append(f'<div class="agg-fill" style="width: {width}px; background: {color}"></div>')
            parts.append(f'<div class="agg-val">{score:.3f}</div>')
            parts.append('</div>')
        parts.append('</div>')

    parts.append(f'<footer>Generated by Clarvis attention_visualizer.py | {len(results_with_contributions)} results visualized</footer>')
    parts.append('</body></html>')

    with open(output_path, "w") as f:
        f.write("\n".join(parts))
    return output_path


def visualize(query, n=5, output=None, collections=None):
    """Main visualization pipeline."""
    sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
    from clarvis.brain import brain

    output = output or DEFAULT_OUTPUT

    print(f"Query: {query}")
    print(f"Tokenizing...")

    tok_data, vocab = load_tokenizer()
    tokens, token_ids = tokenize(query, tok_data, vocab)
    print(f"Tokens ({len(tokens)}): {' '.join(tokens)}")

    print(f"Computing hidden states...")
    hidden_states = get_hidden_states(token_ids)
    query_embedding = mean_pool(hidden_states)

    print(f"Searching brain (n={n})...")
    kwargs = {"n": n}
    if collections:
        kwargs["collections"] = collections
    results = brain.recall(query, **kwargs)
    print(f"Got {len(results)} results")

    if not results:
        print("No results found.")
        return None

    # Get embeddings for results using the same model
    from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
    ef = ONNXMiniLM_L6_V2()
    result_texts = [r.get("document") or r.get("text", "") for r in results]
    result_embeddings = ef(result_texts)

    # Compute per-token contributions for each result
    results_with_contributions = []
    for result, result_emb in zip(results, result_embeddings):
        result_emb = np.array(result_emb)
        contributions = compute_token_contributions(hidden_states, tokens, result_emb)
        results_with_contributions.append((result, contributions))

    # Also print terminal summary
    print("\n--- Token Importance (aggregate) ---")
    agg = {}
    cnt = {}
    for _, contributions in results_with_contributions:
        for token, score in contributions:
            if token in ("[CLS]", "[SEP]"):
                continue
            clean = token.replace("##", "")
            agg[clean] = agg.get(clean, 0) + score
            cnt[clean] = cnt.get(clean, 0) + 1
    avg = {t: agg[t] / cnt[t] for t in agg}
    for token, score in sorted(avg.items(), key=lambda x: -x[1])[:10]:
        bar = "█" * int(score * 20)
        print(f"  {token:>15s}  {bar} {score:.3f}")

    # Generate HTML
    path = generate_html(query, results_with_contributions, output)
    print(f"\nHTML visualization: {path}")
    return path


def main():
    parser = argparse.ArgumentParser(description="Attention visualizer for brain search")
    parser.add_argument("query", help="Search query to visualize")
    parser.add_argument("--n", type=int, default=5, help="Number of results (default: 5)")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output HTML path")
    parser.add_argument("--collections", nargs="*", help="Specific collections to search")
    args = parser.parse_args()
    visualize(args.query, n=args.n, output=args.output, collections=args.collections)


if __name__ == "__main__":
    main()
