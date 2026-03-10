# Research Note — Free Energy Principle and World Models

Date: 2026-03-09

Topic: Free Energy Principle (FEP) as a framework for world models / active inference

Sources reviewed:
- Friston, "The free-energy principle: a unified brain theory?" (Nature Reviews Neuroscience, 2010)
- Mazzaglia et al., "The Free Energy Principle for Perception and Action: A Deep Learning Perspective" (Entropy/arXiv:2207.06415, 2022)
- Villalobos et al., "The Free Energy Principle: Good Science and Questionable Philosophy in a Grand Unifying Theory" (Entropy, 2021)

Key points:
- FEP describes adaptive systems as maintaining themselves in a restricted set of viable states by minimizing variational free energy.
- In practice, this means an agent carries a generative model of hidden causes in the world and continuously updates beliefs from sensory input.
- Action is not separate from inference: active inference treats behavior as sampling the world in ways that reduce expected surprise and fulfill prior preferences.
- This makes FEP closely related to modern world-model ideas in AI: latent-state modeling, prediction, planning, uncertainty handling, and preference-conditioned behavior.
- The ML/deep-learning interpretation is the most useful for engineering: amortized inference, learned latent dynamics, and planning in imagination make FEP operational rather than purely philosophical.
- The strongest caution from the critique literature is that FEP may be scientifically useful without justifying sweeping metaphysical claims. Treating it as an engineering and explanatory framework is safer than treating it as a final theory of mind.

Practical Clarvis takeaway:
- Use FEP as a design lens for agent architecture: maintain explicit latent beliefs, separate sensory evidence from hidden-state inference, plan by expected information gain + preference satisfaction, and update memory/models after action outcomes.
- Do not overclaim consciousness from this alone. It is stronger as a theory of adaptive world-modeling than as proof of subjective experience.
