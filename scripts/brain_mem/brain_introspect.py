#!/usr/bin/env python3
"""
Brain Introspection — Self-awareness layer for the subconscious.

This module gives the subconscious (heartbeat cron) the ability to introspect
its own knowledge state at decision time. Instead of a blind semantic search,
the subconscious can now ask:

  "What do I know about this task's domain?"
  "Does this align with my goals?"
  "What procedures have I used for similar work?"
  "What infrastructure is relevant?"
  "What have I learned from similar failures?"
  "Who am I and what do I prefer?"

Architecture:
  brain_bridge.py  = Basic recall (learnings/memories/episodes)
  brain_introspect.py = Deep self-awareness (THIS MODULE):
    1. Knowledge map — what domains am I strong/weak in?
    2. Goal alignment — how does this task relate to active goals?
    3. Identity-informed reasoning — preferences, personality, constraints
    4. Associative recall via graph — follow relationship edges
    5. Infrastructure awareness — what systems/tools are relevant?
    6. Capability manifest — what can the brain do?

Usage:
    from brain_introspect import introspect_for_task, get_capability_manifest

    # Full introspection for a task (called in preflight)
    ctx = introspect_for_task("Build a self-awareness module")

    # Static capability manifest (for documentation/prompts)
    manifest = get_capability_manifest()

    # CLI
    python3 brain_introspect.py task "Build a self-awareness module"
    python3 brain_introspect.py manifest
    python3 brain_introspect.py knowledge-map
"""

import json
import os
import re
import sys
import time

# Spine imports used inside functions (lazy) to avoid import-time ChromaDB init

# === CAPABILITY MANIFEST ===
# Static description of what the brain can do, for injection into prompts.
# This is the "self-awareness of capabilities" — the subconscious knowing
# what tools it has available.

CAPABILITY_MANIFEST = {
    "brain_version": "ClarvisDB v2",
    "embedding_model": "ONNX MiniLM-L6-v2 (384-dim, local)",
    "collections": {
        "clarvis-identity": {
            "purpose": "Who I am — personality, constraints, core values",
            "query_when": "identity questions, ethical decisions, personality-sensitive tasks",
        },
        "clarvis-preferences": {
            "purpose": "How I prefer to work — code style, tool preferences, communication style",
            "query_when": "implementation choices, style decisions, tool selection",
        },
        "clarvis-learnings": {
            "purpose": "What I've learned — research, experiments, failures, insights",
            "query_when": "any task (primary knowledge source)",
        },
        "clarvis-infrastructure": {
            "purpose": "What systems exist — servers, APIs, configs, deployments",
            "query_when": "infrastructure tasks, deployment, system integration",
        },
        "clarvis-goals": {
            "purpose": "Where I'm going — active objectives with progress",
            "query_when": "task prioritization, alignment checks",
        },
        "clarvis-context": {
            "purpose": "What I'm currently doing — working memory",
            "query_when": "continuity between heartbeats",
        },
        "clarvis-memories": {
            "purpose": "General memories — conversations, events, decisions",
            "query_when": "broad context, relationship with human",
        },
        "clarvis-procedures": {
            "purpose": "How to do things — step-by-step procedures with success rates",
            "query_when": "execution planning, known-task optimization",
        },
        "autonomous-learning": {
            "purpose": "Self-discovered knowledge — patterns from autonomous operation",
            "query_when": "self-improvement tasks, meta-cognition",
        },
        "clarvis-episodes": {
            "purpose": "What happened — task outcomes with context",
            "query_when": "learning from experience, avoiding repeated failures",
        },
    },
    "capabilities": {
        "semantic_search": "Search any collection by meaning (embedding similarity)",
        "importance_filter": "Filter results by importance score (0-1)",
        "temporal_filter": "Filter by recency (since_days=N)",
        "graph_traversal": "Follow relationship edges between memories (48k+ edges)",
        "spreading_activation": "Synaptic memory finds connected memories via STDP weights",
        "attention_boost": "Boost results matching current spotlight focus",
        "cross_collection_links": "Memories linked across collections via auto-linking",
        "hebbian_strengthening": "Retrieved memories get stronger (use-dependent plasticity)",
        "decay_pruning": "Unused memories decay over time (importance decreases)",
        "goal_tracking": "Set/get goals with progress percentages",
        "context_management": "Working memory via set_context/get_context",
    },
    "methods": {
        "recall": "brain.recall(query, collections=[...], n=5, min_importance=0.3, include_related=True)",
        "store": "brain.store(text, collection=COL, importance=0.7, tags=[...], source='...')",
        "get_goals": "brain.get_goals() → [{goal, progress, ...}]",
        "set_goal": "brain.set_goal(name, progress, subtasks={...})",
        "get_context": "brain.get_context() → current working state",
        "set_context": "brain.set_context('what I am doing now')",
        "stats": "brain.stats() → {total_memories, graph_edges, collections: {...}}",
        "optimize": "brain.optimize(full=False) → decay + prune (full=True adds dedup)",
        "get_related": "brain.get_related(memory_id, depth=1) → graph neighbors",
        "recall_recent": "brain.recall_recent(days=7) → last N days",
    },
}


def get_capability_manifest():
    """Return the brain capability manifest for prompt injection.

    This tells the conscious mind (or any LLM executor) exactly what the
    brain can do, so it can make informed decisions about querying it.
    """
    return CAPABILITY_MANIFEST


def format_manifest_for_prompt(compact=True):
    """Format the capability manifest as a string for LLM prompts.

    Args:
        compact: If True, produce a ~300 token summary. If False, full detail.
    """
    m = CAPABILITY_MANIFEST
    if compact:
        lines = [
            "BRAIN CAPABILITIES (ClarvisDB v2, 384-dim ONNX embeddings):",
            f"  Collections: {', '.join(m['collections'].keys())}",
            "  Key methods: recall(query), store(text), get_goals(), get_context(), get_related(id), stats()",
            "  Features: semantic search, graph traversal (48k edges), spreading activation, attention boost, temporal filtering",
            "  Query collections selectively — identity for 'who am I', preferences for 'how to do it',",
            "  learnings for 'what I know', infrastructure for 'what systems exist', procedures for 'how I've done this before'",
        ]
        return "\n".join(lines)
    else:
        return json.dumps(m, indent=2)


def _filter_bridge_noise(memories):
    """Filter out graph-bridge documents that are just relationship metadata.

    ClarvisDB stores "Connection between X and Y: ..." bridge entries that
    pollute recall results. These are graph metadata, not actual knowledge.
    """
    for mem in memories:
        doc = mem.get("document", "")
        # Skip bridge/connection metadata documents
        if doc.startswith("Connection between "):
            continue
        yield mem


# === TASK INTROSPECTION ===

def introspect_for_task(task_text, budget="standard"):
    """Deep introspection for a task — the subconscious thinking about what it knows.

    Goes beyond brain_bridge's single recall() by:
    1. Extracting task domains to select relevant collections
    2. Checking goal alignment
    3. Surfacing identity/preference constraints
    4. Following graph relationships for associative recall
    5. Checking infrastructure relevance

    Args:
        task_text: The task about to be executed
        budget: "minimal" (fast, ~50ms), "standard" (~150ms), "full" (~300ms)

    Returns dict with:
        - domain_knowledge: what I know about this task's domain
        - goal_alignment: how this relates to my goals
        - identity_context: relevant identity/preference items
        - infrastructure: relevant systems/tools
        - associative_memories: graph-connected memories
        - meta_awareness: self-assessment of knowledge state for this task
    """
    from clarvis.brain import get_brain, IDENTITY, PREFERENCES, INFRASTRUCTURE, LEARNINGS
    from clarvis.brain import EPISODES, AUTONOMOUS_LEARNING, MEMORIES

    result = {
        "domain_knowledge": "",
        "goal_alignment": "",
        "identity_context": "",
        "infrastructure": "",
        "associative_memories": "",
        "meta_awareness": "",
        "timings": {},
    }

    try:
        b = get_brain()
    except Exception:
        return result

    t0 = time.monotonic()

    # --- 1. Domain detection: what is this task about? ---
    task_domains = _detect_task_domains(task_text)
    result["timings"]["domain_detect"] = round(time.monotonic() - t0, 4)

    # --- 2. Targeted knowledge recall (domain-specific collections) ---
    t1 = time.monotonic()
    collections_to_search = _select_collections(task_domains, budget)
    knowledge = b.recall(
        task_text,
        collections=collections_to_search,
        n=5 if budget == "full" else 3,
        min_importance=0.2 if budget == "full" else 0.3,
        attention_boost=True,
        caller="brain_introspect",
    )
    if knowledge:
        lines = []
        for mem in _filter_bridge_noise(knowledge):
            doc = mem.get("document", "")[:120]
            col = mem.get("collection", "")
            dist = mem.get("distance")
            dist_str = f" d={dist:.2f}" if dist is not None else ""
            # Short collection label
            col_label = col.replace("clarvis-", "").upper()[:8]
            lines.append(f"  [{col_label}{dist_str}] {doc}")
        result["domain_knowledge"] = "\n".join(lines)
    result["timings"]["domain_knowledge"] = round(time.monotonic() - t1, 4)

    # --- 3. Goal alignment: does this task serve my goals? ---
    t2 = time.monotonic()
    if budget != "minimal":
        try:
            goals = b.get_goals()
            if goals:
                alignments = []
                task_words = set(re.findall(r'[a-z]{3,}', task_text.lower()))
                for g in goals:
                    goal_name = g.get("metadata", {}).get("goal", g.get("document", ""))
                    progress = g.get("metadata", {}).get("progress", 0)
                    goal_words = set(re.findall(r'[a-z]{3,}', goal_name.lower()))
                    overlap = len(task_words & goal_words)
                    if overlap >= 2:
                        alignments.append(f"  ALIGNS ({progress}%): {goal_name[:80]}")
                    elif overlap == 1:
                        alignments.append(f"  RELATED ({progress}%): {goal_name[:80]}")
                if alignments:
                    result["goal_alignment"] = "\n".join(alignments[:3])
        except Exception:
            pass
    result["timings"]["goal_alignment"] = round(time.monotonic() - t2, 4)

    # --- 4. Identity & preferences (who am I when doing this?) ---
    t3 = time.monotonic()
    if budget == "full" or "identity" in task_domains or "preference" in task_domains:
        try:
            # Only search identity/preferences when relevant
            id_results = b.recall(
                task_text,
                collections=[IDENTITY, PREFERENCES],
                n=2,
                caller="brain_introspect_identity",
            )
            if id_results:
                id_lines = []
                for mem in _filter_bridge_noise(id_results):
                    doc = mem.get("document", "")[:100]
                    dist = mem.get("distance")
                    # Only include if reasonably relevant (distance < 1.5)
                    if dist is not None and dist < 1.5:
                        col_label = "ID" if "identity" in mem.get("collection", "") else "PREF"
                        id_lines.append(f"  [{col_label}] {doc}")
                if id_lines:
                    result["identity_context"] = "\n".join(id_lines)
        except Exception:
            pass
    result["timings"]["identity"] = round(time.monotonic() - t3, 4)

    # --- 5. Infrastructure awareness ---
    t4 = time.monotonic()
    if "infrastructure" in task_domains or "deploy" in task_domains or budget == "full":
        try:
            infra = b.recall(
                task_text,
                collections=[INFRASTRUCTURE],
                n=3,
                caller="brain_introspect_infra",
            )
            if infra:
                infra_lines = []
                for mem in _filter_bridge_noise(infra):
                    doc = mem.get("document", "")[:100]
                    dist = mem.get("distance")
                    if dist is not None and dist < 1.5:
                        infra_lines.append(f"  [INFRA] {doc}")
                if infra_lines:
                    result["infrastructure"] = "\n".join(infra_lines)
        except Exception:
            pass
    result["timings"]["infrastructure"] = round(time.monotonic() - t4, 4)

    # --- 6. Associative recall via graph ---
    t5 = time.monotonic()
    if budget in ("standard", "full") and knowledge:
        try:
            # Take top 2 results and follow their graph connections
            assoc_memories = set()
            for mem in knowledge[:2]:
                mem_id = mem.get("id", "")
                if not mem_id:
                    continue
                related = b.get_related(mem_id, depth=1)
                for rel in related[:3]:
                    rel_id = rel.get("id", "")
                    if rel_id and rel_id not in assoc_memories:
                        assoc_memories.add(rel_id)

            # Resolve the associated memory IDs to documents
            if assoc_memories:
                assoc_lines = []
                for assoc_id in list(assoc_memories)[:4]:
                    # Try each collection to find this ID
                    for col_name in [LEARNINGS, MEMORIES, EPISODES, AUTONOMOUS_LEARNING]:
                        try:
                            col = b.collections.get(col_name)
                            if not col:
                                continue
                            got = col.get(ids=[assoc_id])
                            if got["ids"] and got["documents"] and got["documents"][0]:
                                doc = got["documents"][0][:100]
                                assoc_lines.append(f"  [ASSOC] {doc}")
                                break
                        except Exception:
                            continue
                if assoc_lines:
                    result["associative_memories"] = "\n".join(assoc_lines)
        except Exception:
            pass
    result["timings"]["associative"] = round(time.monotonic() - t5, 4)

    # --- 7. Meta-awareness: self-assessment of knowledge state ---
    t6 = time.monotonic()
    if budget != "minimal":
        meta_parts = []
        # How much do I know about this domain?
        knowledge_count = len(knowledge) if knowledge else 0
        if knowledge_count == 0:
            meta_parts.append("KNOWLEDGE GAP: No relevant knowledge found — this is novel territory. Proceed with caution.")
        elif knowledge_count <= 2:
            meta_parts.append(f"LOW KNOWLEDGE: Only {knowledge_count} relevant memories. Consider researching before acting.")
        else:
            meta_parts.append(f"KNOWLEDGE AVAILABLE: {knowledge_count} relevant memories surfaced.")

        # Goal alignment assessment
        if result["goal_alignment"]:
            meta_parts.append("GOAL-ALIGNED: This task serves active objectives.")
        else:
            meta_parts.append("GOAL-NEUTRAL: No direct alignment with active goals detected.")

        # Infrastructure awareness
        if result["infrastructure"]:
            meta_parts.append("INFRA-AWARE: Relevant system knowledge available.")

        result["meta_awareness"] = " | ".join(meta_parts)
    result["timings"]["meta"] = round(time.monotonic() - t6, 4)

    result["timings"]["total"] = round(time.monotonic() - t0, 4)
    return result


def format_introspection_for_prompt(introspection, budget="standard"):
    """Format introspection results into a compact prompt section.

    Follows the primacy/recency principle from context_compressor.py:
    BEGINNING: Meta-awareness + goal alignment (decision-shaping)
    MIDDLE: Domain knowledge + infrastructure
    END: Associative memories + identity (context enrichment)
    """
    parts = []

    # HIGH ATTENTION (beginning): meta-awareness and goal alignment
    meta = introspection.get("meta_awareness", "")
    if meta:
        parts.append(f"SELF-AWARENESS: {meta}")

    goal = introspection.get("goal_alignment", "")
    if goal:
        parts.append(f"GOAL ALIGNMENT:\n{goal}")

    # MEDIUM ATTENTION (middle): domain knowledge
    domain = introspection.get("domain_knowledge", "")
    if domain:
        parts.append(f"RELEVANT KNOWLEDGE:\n{domain}")

    infra = introspection.get("infrastructure", "")
    if infra:
        parts.append(f"RELEVANT INFRASTRUCTURE:\n{infra}")

    # HIGH ATTENTION (end): associative and identity
    assoc = introspection.get("associative_memories", "")
    if assoc:
        parts.append(f"ASSOCIATED MEMORIES (graph-connected):\n{assoc}")

    identity = introspection.get("identity_context", "")
    if identity:
        parts.append(f"IDENTITY/PREFERENCES:\n{identity}")

    if not parts:
        return ""

    timings = introspection.get("timings", {})
    total_ms = int(timings.get("total", 0) * 1000)

    header = f"=== BRAIN INTROSPECTION ({total_ms}ms) ==="
    return header + "\n" + "\n\n".join(parts)


# === DOMAIN DETECTION ===

# Domain keywords — map task text patterns to relevant brain collections
DOMAIN_KEYWORDS = {
    "infrastructure": [
        "server", "deploy", "docker", "nuc", "vps", "port", "ssh", "api",
        "config", "cron", "systemd", "database", "redis", "nginx",
    ],
    "research": [
        "research", "paper", "study", "theory", "explore", "investigate",
        "analyze", "survey", "literature", "framework",
    ],
    "code": [
        "code", "script", "function", "class", "module", "import", "test",
        "refactor", "debug", "fix", "build", "implement", "wire",
    ],
    "identity": [
        "who am i", "identity", "personality", "soul", "self", "purpose",
        "values", "ethics", "consciousness",
    ],
    "preference": [
        "prefer", "style", "convention", "standard", "how to", "best practice",
    ],
    "goal": [
        "goal", "objective", "roadmap", "milestone", "progress", "priority",
        "evolution", "agi", "consciousness",
    ],
    "memory": [
        "memory", "brain", "knowledge", "remember", "recall", "learn",
        "forget", "consolidate", "optimize",
    ],
    "business": [
        "revenue", "product", "saas", "customer", "market", "launch",
        "deploy", "sell", "pricing",
    ],
    "deploy": [
        "deploy", "ship", "release", "production", "staging", "ci", "cd",
    ],
}


def _detect_task_domains(task_text):
    """Detect which knowledge domains a task touches.

    Returns a set of domain strings like {"code", "infrastructure", "goal"}.
    """
    task_lower = task_text.lower()
    domains = set()

    for domain, keywords in DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw in task_lower:
                domains.add(domain)
                break  # One keyword per domain is enough

    if not domains:
        domains.add("general")

    return domains


def _select_collections(task_domains, budget="standard"):
    """Select brain collections to search based on detected task domains.

    This is the key intelligence: instead of searching everything, we
    search the RIGHT collections based on what the task is about.
    """
    from clarvis.brain import (LEARNINGS, MEMORIES, EPISODES, AUTONOMOUS_LEARNING,
                       IDENTITY, PREFERENCES, INFRASTRUCTURE, PROCEDURES, GOALS)

    # Always search these (core knowledge)
    collections = [LEARNINGS]

    if budget == "minimal":
        return collections

    # Add domain-specific collections
    domain_to_collections = {
        "infrastructure": [INFRASTRUCTURE],
        "research": [AUTONOMOUS_LEARNING, MEMORIES],
        "code": [PROCEDURES, LEARNINGS],
        "identity": [IDENTITY],
        "preference": [PREFERENCES],
        "goal": [GOALS],
        "memory": [LEARNINGS, EPISODES],
        "business": [LEARNINGS, MEMORIES],
        "deploy": [INFRASTRUCTURE, PROCEDURES],
        "general": [MEMORIES, EPISODES],
    }

    for domain in task_domains:
        extra = domain_to_collections.get(domain, [])
        collections.extend(extra)

    # Standard always includes episodes + memories (experience-based reasoning)
    if budget in ("standard", "full"):
        collections.extend([EPISODES, MEMORIES])

    # Full adds everything
    if budget == "full":
        collections.extend([AUTONOMOUS_LEARNING, PROCEDURES])

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for c in collections:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    return unique


# === KNOWLEDGE MAP ===

def build_knowledge_map():
    """Build a map of what the brain knows, organized by domain.

    This is a higher-order introspection: not "what do I know about X?"
    but "what DOMAINS do I have knowledge in, and how deep?"

    Returns dict: {domain: {count, top_topics, strength}}
    """
    from clarvis.brain import get_brain, ALL_COLLECTIONS

    b = get_brain()
    knowledge_map = {}

    for col_name in ALL_COLLECTIONS:
        col = b.collections.get(col_name)
        if not col:
            continue
        count = col.count()
        if count == 0:
            continue

        # Sample top entries to get a sense of content
        sample = col.get(limit=min(20, count))
        topics = set()
        for doc in sample.get("documents", []):
            if doc:
                # Extract key noun phrases (simple: capitalized words, technical terms)
                words = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*|[a-z]+_[a-z]+|[A-Z]{2,}', doc)
                topics.update(w for w in words if len(w) > 3)

        # Compute average importance
        importances = []
        for meta in sample.get("metadatas", []):
            if meta and "importance" in meta:
                try:
                    importances.append(float(meta["importance"]))
                except (ValueError, TypeError):
                    pass

        avg_importance = sum(importances) / len(importances) if importances else 0.5

        col_label = col_name.replace("clarvis-", "")
        knowledge_map[col_label] = {
            "count": count,
            "avg_importance": round(avg_importance, 2),
            "sample_topics": sorted(list(topics))[:10],
        }

    return knowledge_map


def format_knowledge_map(kmap):
    """Format knowledge map as a compact string."""
    lines = ["KNOWLEDGE MAP:"]
    for domain, info in sorted(kmap.items(), key=lambda x: -x[1]["count"]):
        topics = ", ".join(info["sample_topics"][:5]) if info["sample_topics"] else "mixed"
        lines.append(f"  {domain}: {info['count']} memories (avg imp={info['avg_importance']}) — {topics}")
    return "\n".join(lines)


# === CLI ===

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: brain_introspect.py <command> [args]")
        print("Commands:")
        print("  task <task_text>    - Full introspection for a task")
        print("  manifest            - Show brain capability manifest")
        print("  knowledge-map       - Show what the brain knows by domain")
        print("  domains <text>      - Detect domains in task text")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "task" and len(sys.argv) > 2:
        task_text = " ".join(sys.argv[2:])
        budget = "full"
        if "--budget" in sys.argv:
            idx = sys.argv.index("--budget")
            if idx + 1 < len(sys.argv):
                budget = sys.argv[idx + 1]
                task_text = " ".join(a for a in sys.argv[2:] if a not in ("--budget", budget))

        print(f"Introspecting for: {task_text[:80]}...")
        print(f"Budget: {budget}\n")

        result = introspect_for_task(task_text, budget=budget)
        formatted = format_introspection_for_prompt(result, budget)
        print(formatted)

        print("\n--- Timings ---")
        for k, v in result["timings"].items():
            print(f"  {k}: {v*1000:.1f}ms")

    elif cmd == "manifest":
        print(format_manifest_for_prompt(compact="--full" not in sys.argv))

    elif cmd == "knowledge-map":
        kmap = build_knowledge_map()
        print(format_knowledge_map(kmap))

    elif cmd == "domains" and len(sys.argv) > 2:
        text = " ".join(sys.argv[2:])
        domains = _detect_task_domains(text)
        print(f"Detected domains: {domains}")

        collections = _select_collections(domains, budget="full")
        print(f"Collections to search: {[c.replace('clarvis-', '') for c in collections]}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
