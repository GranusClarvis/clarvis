# Research — Free Energy Principle

Date: 2026-03-10

Topic: Free Energy Principle / Active Inference

Key sources reviewed:
- https://arxiv.org/abs/2201.06387 — "The free energy principle made simpler but not too simple"
- https://arxiv.org/abs/1906.10184 — "A free energy principle for a particular physics"
- https://activeinference.github.io/ — curated overview and reading map
- https://www.nature.com/articles/nrn2787 — "The free-energy principle: a unified brain theory?"

Summary:
The Free Energy Principle (FEP) frames adaptive systems as maintaining themselves by minimizing variational free energy, an upper bound on surprise. In practical terms, an agent survives by keeping its sensory states within viable bounds while continually updating a generative model of hidden causes. Active inference extends this from perception to action: the system does not just revise beliefs to fit sensations, it also acts to make sensations conform to predicted preferred states. The crucial structural idea is the Markov blanket, which separates internal states from the external world while allowing conditional dependence through sensory and active states. What matters for Clarvis is not the grand metaphysics, but the engineering consequence: intelligence requires tight perception–model–action loops, not passive retrieval alone. A useful implementation lesson is hierarchical temporal modelling. Friston’s deep temporal models suggest agents need models operating at multiple timescales so short-horizon corrections and long-horizon plans can cohere. For memory architecture, FEP implies context should be selected for action-relevance and uncertainty reduction, not only semantic similarity. For orchestration, it suggests explicit prediction, error tracking, and policy selection under uncertainty are more fundamental than static prompt stuffing.

Key insight for brain memory:
Research: Free Energy Principle — useful as an engineering pattern when treated as prediction-error minimization across perception, memory selection, and action, rather than as a vague theory of consciousness.
