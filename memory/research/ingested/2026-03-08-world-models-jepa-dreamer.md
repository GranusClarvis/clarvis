# Research — World Models beyond generation (DreamerV3, I-JEPA, LeCun AMI)

_Date: 2026-03-08_

## Topic
World Models — unresolved practical question: what kind of world model matters most for general intelligence? Not photorealistic generation, but compact latent dynamics that support planning, control, and abstraction.

## Sources
1. DreamerV3 paper — https://arxiv.org/abs/2301.04104
2. DreamerV3 project page — https://danijar.com/project/dreamerv3/
3. I-JEPA paper — https://arxiv.org/abs/2301.08243
4. LeCun, *A Path Towards Autonomous Machine Intelligence* — https://openreview.net/forum?id=BZ5a1r-kVsf

## Summary
DreamerV3 sharpens the practical definition of a world model: a latent dynamics model good enough to imagine futures and optimize behaviour directly in imagination. Its significance is not merely high benchmark scores; it shows that one robust configuration can work across 150+ tasks, suggesting that the key variable is stable latent prediction plus action-conditioned rollout, not per-domain hand-tuning.

I-JEPA pushes the same lesson from another direction. It predicts representations rather than pixels, forcing the model to learn large-scale semantic structure. This matters because useful world models should preserve invariants and causal regularities, not waste capacity on every visual detail.

LeCun’s AMI framing ties these together: intelligence likely needs hierarchical predictive models, joint-embedding objectives, and planning over abstract states. The common insight is that world models are best treated as controllable compressed simulators. For Clarvis, the engineering analogue is clear: build compact predictive state, not exhaustive replay. The value of the model lies in whether it improves action selection, long-horizon planning, and transfer — not whether it can reconstruct reality perfectly.

## Key takeaways for Clarvis
- Prediction in latent space is more useful than raw reconstruction.
- Compact bottlenecked models can improve transfer and planning.
- The test of a world model is control quality and data efficiency.
- A practical cognitive system should maintain abstract state transitions, imagined rollouts, and uncertainty-aware planning.