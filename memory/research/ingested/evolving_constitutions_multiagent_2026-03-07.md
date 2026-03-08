# Evolving Interpretable Constitutions for Multi-Agent Coordination

**Date:** 2026-03-07
**Source:** Kumar, Saito, Niranjani, Yessou, Tan — arXiv:2602.00755 (Jan 2026)
**Related:** Gao et al., "Self-Evolving Agents Survey" (arXiv:2507.21046, Jan 2026, TMLR)

## Core Insight

Hand-crafted constitutions fail in multi-agent settings. Generic prosocial principles ("be helpful, harmless, honest") yield Societal Stability Score S=0.249. Expert-designed constitutions only reach S=0.332. **LLM-driven genetic programming auto-discovers constitutions reaching S=0.556 (123% improvement)** — cooperative norms emerge through agent interactions rather than prescription.

## Methodology: LLM-Driven Genetic Programming

1. **Multi-island evolution**: Multiple populations of candidate constitutions evolve independently, with periodic migration of top performers between islands (prevents premature convergence)
2. **Fitness = Societal Stability Score (S)**: Composite of productivity, survival, conflict metrics in grid-world simulation (0-1 range)
3. **LLM as mutation operator**: An LLM generates constitution variants (crossover, mutation) — constitutions are natural-language behavioral norms
4. **Selection**: Tournament selection retains highest-S constitutions per generation
5. **N=10 trials** per constitution for robust evaluation

## Key Findings

1. **Minimal communication wins**: Evolved constitution C* uses only 0.9% social actions vs 62.2% for hand-designed constitutions. Counter-intuitive: less talk = more coordination.
2. **Conflict elimination**: Evolved norms completely eliminated inter-agent conflict (0% conflict rate)
3. **Emergent cooperation**: Cooperative behaviors arise without explicit cooperation rules — the evolutionary pressure naturally selects for coordination
4. **Interpretability preserved**: Despite evolutionary optimization, resulting constitutions remain human-readable natural language norms

## 3 Adoptable Patterns for Clarvis

### Pattern 1: Evolutionary Agent Policy Discovery
Instead of hand-writing agent behavioral policies in `project_agent.py`, evolve them:
- Define fitness metric per project (PR merge rate, test pass rate, code quality)
- Start with current protocol (task brief → execute → return JSON)
- Use LLM mutations to generate protocol variants (different constraint sets, communication patterns)
- Track performance per variant, promote winners
- **Implementation**: Add `evolve_protocol()` to `project_agent.py` — maintains a population of protocol variants in `configs/protocol_variants.json`, A/B tests over spawn cycles

### Pattern 2: Minimal Communication Principle
The paper's strongest finding: over-communication hurts coordination. Apply to:
- **Digest protocol**: Current `promote()` sends full summaries. Evolved approach: only promote procedures + PR links, strip verbose context
- **Cron orchestrator**: Reduce inter-script communication overhead (e.g., QUEUE.md updates are verbose — switch to structured tags only)
- **Agent↔Clarvis protocol**: Current JSON response has 6 fields. Evolved minimum might be: `{status, pr_url, procedures}` — drop `summary` and `follow_ups` unless explicitly requested

### Pattern 3: Multi-Island Evolution for Cron Self-Alignment
Apply multi-island evolution to cron schedule optimization:
- Each "island" = a different cron configuration variant (timing, frequency, task allocation)
- Fitness = task success rate + cost efficiency + queue throughput
- Periodic migration: merge winning scheduling patterns between variants
- **Low-cost implementation**: Track cron outcomes in `data/cron_evolution.jsonl`, weekly analysis selects schedule mutations

## Connection to Self-Evolving Agents Survey (2507.21046)

The survey (Gao et al., 26 authors, TMLR) provides the taxonomy that frames this work:
- **What evolves**: Here, constitutions (behavioral norms) — in the survey's framework, this is "policy-level" evolution
- **When**: Inter-test-time (between episodes, not during) — same as Clarvis's reflection/evolution cycle
- **How**: Textual feedback (LLM mutations) rather than scalar rewards — aligns with Clarvis's reasoning-chain-based learning
- **Multi-agent**: Survey identifies multi-agent evolution as under-explored frontier; this paper is one of the first concrete implementations

## Relevance to Clarvis Architecture

| Clarvis Component | Connection |
|---|---|
| `project_agent.py` | Agent behavioral policies could be evolved, not hand-crafted |
| `cron_autonomous.sh` | Cron self-alignment via evolutionary schedule tuning |
| Orchestrator (Pillar 2) | Multi-agent coordination norms for project agents |
| `SOUL.md` | Constitutional norms are effectively Clarvis's "soul" — could be self-evolved |
| `clarvis_reflection.py` | Reflection = evaluation step in evolutionary loop |
| `scripts/cron_evolution.sh` | Already does evolution analysis — could incorporate fitness-based norm selection |

## Limitations & Caveats

- Grid-world simulation is far simpler than real agent coordination (no code, no PRs, no external tools)
- N=10 trials — small sample; results may not generalize to all agent architectures
- "Minimal communication" finding may not transfer to complex software engineering tasks where context sharing is essential
- Evolutionary overhead: running many constitution variants is expensive in LLM API calls
- No adversarial robustness analysis — evolved norms could be gamed

## Bottom Line

**For Clarvis**: The strongest actionable insight is the minimal communication principle — current inter-agent protocols likely over-communicate. The evolutionary discovery approach is fascinating but expensive for immediate adoption. Short-term: trim digest/promotion verbosity. Medium-term: A/B test protocol variants in `project_agent.py spawn` cycles. Long-term: full evolutionary constitution discovery for the multi-agent orchestrator.
