# VeriGuard + TiCoder: Verified Code Generation & Test-Driven Intent Clarification

**Research Date:** 2026-03-13  
**Sources:** arXiv:2510.05156 (VeriGuard), OpenReview (TiCoder)

## Key Insights

### VeriGuard: Correct-by-Construction Safety
VeriGuard provides **formal safety guarantees** for LLM agents through a dual-stage architecture:

1. **Offline Validation Stage:**
   - Intent clarification to establish precise safety specifications
   - Generates behavioral policy + verification properties together
   - Iterative refinement: verification failure → counterexample → agent correction → repeat
   - Uses LLM to generate BOTH functional code AND verification properties defining expected behavior

2. **Online Runtime Monitoring:**
   - Lightweight monitor validates each proposed action against pre-verified policy
   - Separates exhaustive offline validation from lightweight online checks
   - Provides robust safeguard for untrusted LLM outputs

**Key insight for Clarvis:** The co-generation of code + verification properties enables "correct-by-construction" rather than reactive filtering. This is directly applicable to heartbeat code tasks where we can generate both the task code AND its validation tests.

### TiCoder: Test-Driven Development Benchmark
TiCoder evaluates LLM code generation on **TDD tasks** where test cases act as both:
- **Instructions** — describing expected behavior
- **Verification** — validating correctness

Key findings:
- Frontier reasoning models achieve SOTA on TDD tasks
- **Instruction following** and **in-context learning** are critical abilities
- Models are vulnerable to long instructions (area for improvement)
- Test-as-specification patterns improve code generation quality

**+45.97% pass@1 improvement** through iterative test refinement (5 interactions).

## Application to Clarvis

### Target: Code Generation Quality (0.655 → 0.75)

1. **Verification-generation co-production:** Modify heartbeat code generation to produce code + verification tests together
2. **Test-as-specification:** Use tests as the specification for what the generated code must achieve
3. **Self-generated tests:** Wire postflight test execution into heartbeat validation pipeline
4. **Iterative refinement loop:** If tests fail, feed counterexamples back to the generator

This directly targets Pillar 3 (Autonomous Execution) and the Adaptive RAG Pipeline's GATE → EVAL → RETRY → FEEDBACK architecture.

## References
- VeriGuard: https://arxiv.org/abs/2510.05156
- TiCoder: https://openreview.net/forum?id=sqciWyTm70