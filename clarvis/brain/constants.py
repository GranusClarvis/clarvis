"""Brain constants — collection names, paths, query routing."""

import os
import re

# Single database location
_WS = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
DATA_DIR = os.path.join(_WS, "data", "clarvisdb")
LOCAL_DATA_DIR = os.path.join(_WS, "data", "clarvisdb-local")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOCAL_DATA_DIR, exist_ok=True)

# Graph file (JSON — legacy default)
GRAPH_FILE = os.path.join(DATA_DIR, "relationships.json")
LOCAL_GRAPH_FILE = os.path.join(LOCAL_DATA_DIR, "relationships.json")

# Graph SQLite database
GRAPH_SQLITE_FILE = os.path.join(DATA_DIR, "graph.db")
LOCAL_GRAPH_SQLITE_FILE = os.path.join(LOCAL_DATA_DIR, "graph.db")

# Graph backend: sqlite (default since 2026-03-29 cutover).
# JSON backend retained only for export/archive tooling.
GRAPH_BACKEND = os.environ.get("CLARVIS_GRAPH_BACKEND", "sqlite")

# Collection names and boundaries.
# Each collection has a defined purpose. Store items in the right collection
# to keep retrieval clean and routing effective.

IDENTITY = "clarvis-identity"
# Purpose: Core self-knowledge — who Clarvis is, capabilities, creator, origin.
# Store: identity statements, capability assessments, self-model snapshots.
# Do NOT store: task completion records, meta-cognition logs (→ EPISODES),
#   bridge/relationship metadata (→ graph), progress snapshots (→ CONTEXT).

PREFERENCES = "clarvis-preferences"
# Purpose: User and agent preferences — style, format, conventions, defaults.
# Store: operator preferences, output format rules, communication style.
# Do NOT store: infrastructure config (→ INFRASTRUCTURE), goals (→ GOALS).

LEARNINGS = "clarvis-learnings"
# Purpose: Insights, lessons learned, discoveries, patterns.
# Store: "I learned that...", research findings, post-incident insights.
# Do NOT store: how-to procedures (→ PROCEDURES), raw episode logs (→ EPISODES).

INFRASTRUCTURE = "clarvis-infrastructure"
# Purpose: System config, cron setup, server state, script inventory.
# Store: infra facts, config changes, service endpoints, cron schedule notes.
# Do NOT store: learnings about infra (→ LEARNINGS), infra procedures (→ PROCEDURES).

GOALS = "clarvis-goals"
# Purpose: Goal definitions — what Clarvis is working toward.
# Store: goal statements, objectives, milestones, target metrics.
# Do NOT store: progress percentages or priority snapshots (→ CONTEXT),
#   completed goal records (→ EPISODES).

CONTEXT = "clarvis-context"
# Purpose: Current/recent state — what's happening now, active work.
# Store: current priorities, working-on notes, recent state snapshots.
# Do NOT store: permanent learnings (→ LEARNINGS), identity facts (→ IDENTITY).

MEMORIES = "clarvis-memories"
# Purpose: General-purpose long-term memories that don't fit other collections.
# Store: facts, observations, broad knowledge, catch-all for uncategorized items.
# Do NOT store: items that clearly belong in a specific collection above.

PROCEDURES = "clarvis-procedures"
# Purpose: How-to knowledge — step-by-step recipes, workflows, runbooks.
# Store: "To do X, first Y then Z", operational procedures, fix recipes.
# Do NOT store: one-time learnings (→ LEARNINGS), episode logs (→ EPISODES).

AUTONOMOUS_LEARNING = "autonomous-learning"
# Purpose: Discoveries made during autonomous (cron) execution cycles.
# Store: autonomous session findings, self-discovered patterns, cron insights.
# Do NOT store: operator-provided learnings (→ LEARNINGS), episode metadata (→ EPISODES).

EPISODES = "clarvis-episodes"
# Purpose: Session records — what happened, outcomes, task completions.
# Store: episode logs, task outcomes, meta-cognition completion records,
#   session summaries, failure/success records with lessons.
# Do NOT store: permanent procedures (→ PROCEDURES), identity facts (→ IDENTITY).

ALL_COLLECTIONS = [IDENTITY, PREFERENCES, LEARNINGS, INFRASTRUCTURE, GOALS, CONTEXT, MEMORIES, PROCEDURES, AUTONOMOUS_LEARNING, EPISODES]
# Fast defaults — all 10 collections. INFRASTRUCTURE was previously excluded
# ("fast defaults") but its ~46 entries add negligible latency and it has the
# best avg_distance (1.07) of any collection — excluding it caused a 10×
# under-hit in retrieval_quality traces (AUDIT_PHASE_4, 2026-04-17).
DEFAULT_COLLECTIONS = ALL_COLLECTIONS

# === QUERY ROUTING ===
# Route queries to the most relevant collections for better hit rates.
_ROUTE_PATTERNS = [
    (re.compile(r'\b(goals?|objectives?|targets?|milestones?|progress)\b', re.I), [GOALS]),
    (re.compile(r'\b(procedur\w*|how to|steps? for|recipe|workflow)\b', re.I), [PROCEDURES, LEARNINGS]),
    (re.compile(r'\b(who am i|my identity|my name|about me|self model|who created|creator|capabilit\w+|what am i)\b', re.I), [IDENTITY, MEMORIES]),
    (re.compile(r'\b(cron|script|server|system|infra|config)\b', re.I), [INFRASTRUCTURE, LEARNINGS]),
    (re.compile(r'\b(graph|sqlite|backend|database|chromadb|checkpoint|compaction|maintenance|collections?)\b', re.I), [INFRASTRUCTURE, PROCEDURES]),
    (re.compile(r'\b(current|right now|working on|context|today|last|recent|previous|heartbeat)\b', re.I), [CONTEXT, MEMORIES]),
    (re.compile(r'\b(learned|lesson|insight|pattern|discovery|found that)\b', re.I), [LEARNINGS]),
    (re.compile(r'\b(prefer|like|style|format|convention)\b', re.I), [PREFERENCES]),
    (re.compile(r'\b(episode|session|conversation|happened|did|bug|fixed|error)\b', re.I), [EPISODES, MEMORIES]),
]


def route_query(query: str) -> list:
    """Route query to relevant collections. Returns None if no specific route matches."""
    matched = set()
    for pattern, collections in _ROUTE_PATTERNS:
        if pattern.search(query):
            matched.update(collections)
    if matched:
        # Always include LEARNINGS and MEMORIES as broad fallback
        matched.add(LEARNINGS)
        matched.add(MEMORIES)
        return list(matched)
    return None  # No routing — use default


def get_local_embedding_function():
    """Get ONNX MiniLM embedding function (fully local, no cloud)"""
    from chromadb.utils import embedding_functions
    return embedding_functions.ONNXMiniLM_L6_V2()
