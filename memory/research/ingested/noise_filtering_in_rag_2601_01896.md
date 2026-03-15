# Noise Filtering in RAG — arXiv:2601.01896

Paper: *Tackling the Inherent Difficulty of Noise Filtering in RAG* (Jingyu Liu, Jiaen Lin, Yong Liu)
Source: https://arxiv.org/abs/2601.01896
Date researched: 2026-03-14

This paper argues that noise filtering in retrieval-augmented generation is not merely an engineering nuisance; it is structurally hard. The core claim is that deciding whether a retrieved token or document is relevant often requires reasoning over relationships among multiple tokens at once, while standard transformer attention only computes pairwise interactions per layer. That mismatch makes perfect filtering difficult for small retrievers and rerankers, so some irrelevant context is likely to survive retrieval.

The authors then argue that standard fine-tuning does not cleanly solve the problem inside the LLM either. A linear attention update can suppress irrelevant tokens, but the same update also perturbs the relative attention pattern among relevant tokens. In other words, the model is pushed into a trade-off: filter aggressively and damage reasoning, or preserve reasoning and tolerate noise.

Their proposed fix is an attention-rectification fine-tuning method that decouples these objectives. Irrelevant tokens receive a strong saturating penalty, while relevant tokens are adjusted more gently so their useful internal structure is preserved. For Clarvis, the practical lesson is clear: do not assume retrieval quality alone will eliminate noise, and do not rely on generic robustness fine-tuning as a cure-all. Build retrieval gates, calibrated context selection, and explicit noise-aware context assembly because some contamination is structurally inevitable.