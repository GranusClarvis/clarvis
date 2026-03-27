"""Error classification for heartbeat postflight.

Classifies task failures into structured categories using keyword matching.
Extracted from heartbeat_postflight.py for testability and reuse.
"""

# Checked in order — first match wins. Priority matters.
ERROR_RULES = [
    ("import_error", [
        "importerror", "modulenotfounderror", "no module named",
        "cannot import name", "dll load failed", "shared object",
    ], 1),
    ("data_missing", [
        "filenotfounderror", "no such file", "file not found",
        "json.decoder.jsondecodeerror", "empty file", "missing config",
        "keyerror", "data not found", "not found in collection",
        "jsondecodeerror", "yaml.scanner", "config missing",
    ], 2),
    ("external_dep", [
        "connectionerror", "connectionrefusederror", "timeout error",
        "httperror", "401", "403", "429", "500", "502", "503",
        "rate limit", "authentication_error", "oauth", "api error",
        "requests.exceptions", "urllib", "ssl", "certificate",
        "unreachable", "dns", "econnrefused", "etimeout",
    ], 2),
    ("memory", [
        "chromadb", "chroma", "embedding", "brain.store", "brain.recall",
        "collection", "vector", "onnx", "recall failed", "store failed",
        "memory_consolidation", "hebbian", "graph edge", "relationships.json",
    ], 2),
    ("planning", [
        "task_selector", "queue.md", "preflight", "routing", "attention",
        "salience", "task selection", "no tasks", "queue empty",
        "codelet", "spotlight", "score_tasks",
    ], 2),
    ("logic_bug", [
        "assertionerror", "typeerror", "valueerror", "indexerror",
        "attributeerror", "nameerror", "zerodivisionerror",
        "recursionerror", "unboundlocalerror", "stopiteration",
    ], 1),
    ("system", [
        "permission denied", "oserror", "disk", "killed", "oom",
        "memory error", "segfault", "errno", "command not found",
        "systemctl", "subprocess.calledprocesserror",
    ], 1),
    # Action sub-types (was catch-all "action")
    ("action.validation", [
        "validation error", "invalid", "schema", "pydantic",
        "required field", "must be", "expected type", "malformed",
        "not a valid", "constraint", "violat", "format error",
    ], 2),
    ("action.param_missing", [
        "missing required", "missing argument", "missing parameter",
        "positional argument", "unexpected keyword", "got an unexpected",
        "takes 0 positional", "takes 1 positional", "required positional",
        "none is not", "nonetype", "missing key", "argument required",
    ], 1),
    ("action.api_error", [
        "api error", "api_error", "bad request", "response error",
        "status code", "http error", "endpoint", "api call failed",
        "openrouter", "anthropic", "response.status",
    ], 1),
    ("action.race_condition", [
        "race condition", "lock", "deadlock", "concurrent", "stale",
        "already running", "lock file", "flock", "mutex", "conflict",
        "resource busy", "locked", "try again",
    ], 2),
]


def _match_keywords(text_lower, keywords, min_hits):
    """Count keyword hits in text and check against threshold."""
    hits = sum(1 for kw in keywords if kw in text_lower)
    return hits if hits >= min_hits else 0


def classify_error(exit_code, output_text):
    """Classify error into structured failure categories using keyword matching.

    Categories (checked in priority order):
      timeout, import_error, data_missing, external_dep, memory,
      planning, logic_bug, system, action.validation, action.param_missing,
      action.api_error, action.race_condition, action (default).

    Returns: (error_type: str, evidence: str)
    """
    if exit_code == 124:
        return "timeout", "exit code 124"

    text_lower = (output_text or "")[-3000:].lower()

    for category, keywords, min_hits in ERROR_RULES:
        hits = _match_keywords(text_lower, keywords, min_hits)
        if hits:
            return category, f"{hits} {category} keywords matched"

    return "action", "default classification (no sub-type matched)"
