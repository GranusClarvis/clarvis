"""Brain constants — collection names, paths, query routing."""

import os
import re

# Single database location
DATA_DIR = "/home/agent/.openclaw/workspace/data/clarvisdb"
LOCAL_DATA_DIR = "/home/agent/.openclaw/workspace/data/clarvisdb-local"
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

# Collection names
IDENTITY = "clarvis-identity"
PREFERENCES = "clarvis-preferences"
LEARNINGS = "clarvis-learnings"
INFRASTRUCTURE = "clarvis-infrastructure"
GOALS = "clarvis-goals"
CONTEXT = "clarvis-context"
MEMORIES = "clarvis-memories"
PROCEDURES = "clarvis-procedures"
AUTONOMOUS_LEARNING = "autonomous-learning"
EPISODES = "clarvis-episodes"

ALL_COLLECTIONS = [IDENTITY, PREFERENCES, LEARNINGS, INFRASTRUCTURE, GOALS, CONTEXT, MEMORIES, PROCEDURES, AUTONOMOUS_LEARNING, EPISODES]
# Fast defaults - includes identity/procedures (needed for accurate recall)
DEFAULT_COLLECTIONS = [IDENTITY, LEARNINGS, MEMORIES, GOALS, CONTEXT, PREFERENCES, PROCEDURES, AUTONOMOUS_LEARNING, EPISODES]

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
