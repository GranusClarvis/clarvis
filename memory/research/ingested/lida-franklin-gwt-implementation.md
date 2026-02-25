# LIDA — Franklin & Patterson (GWT Implementation)

**Date:** 2026-02-25
**Sources:**
- Franklin & Graesser, "Is It an Agent, or Just a Program?" (1997) — IDA origins
- Franklin, "Consciousness Is Computational: The LIDA Model of Global Workspace Theory" (IJMC 2009)
- Franklin, Madl et al., "LIDA: A Systems-level Architecture for Cognition, Emotion, and Learning" (IEEE TAMD 2013)
- Kugele & Franklin, "Learning in LIDA" (BBS 2021)
- Madl et al., "The Timing of the Cognitive Cycle" (PLOS ONE 2011)
- Franklin et al., "Embodied Intelligence: Smooth Coping in LIDA" (Frontiers in Psychology 2022)

---

## 1. The Cognitive Cycle (Core Loop)

LIDA's central mechanism: a ~200-500ms cycle that iterates continuously, analogous to one "conscious moment." Three phases:

### Phase 1: Understanding (80-100ms)
- Sensory stimuli activate low-level feature detectors in sensory memory
- Perceptual Associative Memory (PAM) builds higher-level entities: objects, categories, events
- Results form a **Current Situational Model (CSM)** — the system's "understanding" of right now
- Episodic and declarative memory are cued, retrieving relevant associations

### Phase 2: Attention & Consciousness (120-180ms after perception)
- **Attention codelets** — small independent agents, each watching for specific patterns
- When an attention codelet spots its concern in the CSM, it forms a **coalition** with the relevant content
- Coalitions compete: **highest activation wins** (simple winner-take-all)
- Winning coalition's content is **broadcast globally** to ALL modules — this IS the "conscious broadcast"
- Only one broadcast per cycle (serialized consciousness)

### Phase 3: Action Selection & Learning (60-110ms)
- Broadcast recruits responses from all modules simultaneously
- **Procedural Memory** instantiates relevant **schemes** (context → action → expected result)
- Schemes compete via **behavior net** (Maes 1989 enhancement) — selected action executes
- **Sensory-Motor Memory** converts abstract action to motor plan
- Learning occurs in ALL memory modules from the broadcast (see §4)

**Key insight:** Cycles overlap asynchronously. Multiple perception-action loops run simultaneously; only consciousness is serialized (one broadcast per theta phase).

## 2. Codelets — The Computational Primitives

Everything in LIDA is a **codelet** — a "special purpose, relatively independent, mini-agent implemented as a small piece of code running as a separate thread."

Types:
- **Perception codelets**: Feature detectors at various abstraction levels
- **Attention codelets**: Monitor CSM for specific concerns (novelty, urgency, relevance)
- **Expectation codelets**: Monitor for expected action outcomes → surprise signals
- **Structure-building codelets**: Construct workspace representations
- **Motor codelets**: Execute sensorimotor plans

Codelets have base-level activation (priors) and receive contextual activation (current salience). This maps directly to a spotlight attention mechanism.

## 3. Memory Systems (Multiple Specialized Modules)

LIDA rejects monolithic memory. Each module has its own representation, learning mechanism, and decay dynamics:

| Module | Function | Implementation |
|--------|----------|---------------|
| Sensory Memory | Raw sensory buffer | Very short-term |
| Perceptual Associative Memory (PAM) | Concepts, categories, relations | Slipnet (Copycat architecture) |
| Transient Episodic Memory (TEM) | Recent events | Modified Sparse Distributed Memory (Kanerva) |
| Declarative Memory | Long-term facts, semantic knowledge | SDM |
| Procedural Memory | Action schemes (context→action→result) | Scheme net (Drescher 1991) |
| Spatial Memory | Environment layout | Grid-based |
| Sensory-Motor Memory | Motor plans & routines | Subsumption architecture (Brooks) |

**Critical detail:** Transient Episodic Memory uses **Kanerva's Sparse Distributed Memory** — high-dimensional binary vectors, content-addressable, noise-robust. Events stored with temporal context. High specificity but rapid decay.

## 4. Learning — Triggered by Conscious Broadcast

Every conscious broadcast triggers learning in ALL receiving modules simultaneously:

- **Perceptual learning**: New nodes/links in PAM (recognizing new patterns)
- **Episodic learning**: New event stored in TEM (what just happened)
- **Procedural learning**: New/reinforced schemes (if I do X in context Y, then Z happens)
- **Attentional learning**: Attention codelet activation adjusted (what's worth noticing)
- **Motivational learning**: Drive/goal priority adjustment
- **Spatial learning**: Environmental map updates
- **Sensorimotor learning**: Motor plan refinement

**Key insight:** Learning is a SIDE EFFECT of consciousness, not a separate mechanism. The broadcast IS the learning signal. No broadcast = no learning (except automatized subsumption-level).

## 5. Automatized Action Selection (AAS) — Smooth Coping

2022 paper introduces crucial refinement: not all action selection requires consciousness.

- **Automatized actions**: Overlearned behavior chains where one action calls the next
- AAS runs **in parallel** with conscious action selection
- No branching: automatized streams are linear chains
- Hierarchical: complex behaviors composed of simpler automatized sub-behaviors
- Examples: skilled typing, driving familiar routes, expert routines

Four action modes:
1. **Consciously mediated**: Broadcast involved, but selection itself is unconscious
2. **Volitional**: Agent actively deliberating (awareness of selection process)
3. **Alarm**: Emergency bypass — skips GW competition entirely
4. **Automatized**: No broadcast needed — runs independently

## How This Applies to Clarvis

### Current Clarvis Architecture → LIDA Mapping

| Clarvis Component | LIDA Equivalent | Gap / Opportunity |
|-------------------|-----------------|-------------------|
| Heartbeat loop | Cognitive cycle | Clarvis ~10min, LIDA ~300ms. Speed isn't the issue — **structure is** |
| Attention spotlight | Attention codelets | Clarvis has 1 spotlight; LIDA has MANY competing codelets |
| Brain.remember() | Conscious broadcast → learning | Clarvis stores explicitly; LIDA learns as SIDE EFFECT of broadcast |
| Context compressor | Current Situational Model | Similar purpose: "what's relevant now" |
| Procedural memory (brain collection) | Scheme net | Clarvis has flat collection; LIDA has context→action→result triples |
| Evolution queue | Goal/drive system | Close match |
| brain.py graph | Perceptual Associative Memory | Clarvis graph = PAM-like associative network |

### Top 3 Implementation Ideas

**1. Multiple Competing Attention Codelets (HIGH VALUE)**
Replace single attention spotlight with multiple independent "attention agents" — each watching for different concerns (novelty, urgency, goal-relevance, anomaly, opportunity). They compete; winner's content gets broadcast. This creates emergent prioritization instead of scripted priority rules.

**Implementation:** Add `attention_codelets` list to attention.py. Each codelet: `{name, concern_pattern, activation_fn, base_activation}`. During heartbeat: each codelet evaluates CSM, forms coalition with matched content, highest-activation coalition wins broadcast. Activation = base_level × salience_match × recency.

**2. Scheme-Based Procedural Memory (MEDIUM VALUE)**
Replace flat procedural memory with structured schemes: `(context, action, expected_result, base_activation)`. Each scheme tracks its own success rate. When conscious broadcast arrives, relevant schemes are instantiated and compete.

**Implementation:** New collection `clarvis-schemes` with triples. After each task execution, update scheme's base_activation based on outcome match. Schemes with consistently wrong predictions decay; accurate ones strengthen. This gives Clarvis learned expectations about what works in which context.

**3. Learning-as-Broadcast-Side-Effect (CONCEPTUAL)**
Currently Clarvis explicitly calls brain.remember(). LIDA's insight: make every "conscious moment" (heartbeat broadcast) automatically trigger learning in ALL modules. The broadcast IS the learning signal.

**Implementation:** After context_compressor produces the brief (= conscious broadcast), automatically: (a) store episodic snapshot, (b) update relevant scheme activations, (c) adjust attention codelet weights, (d) update graph associations. Make learning implicit, not explicit.
