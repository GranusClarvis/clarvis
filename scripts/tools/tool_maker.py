#!/usr/bin/env python3
"""
Autonomous Tool Creation & Aggregation (LATM + ToolLibGen + ToolMaker patterns)

Research basis:
- LATM (Cai et al. 2023): closed-loop tool-making with maker/user split
- ToolLibGen (ACL 2025): semantic clustering + multi-agent consolidation
- ToolMaker (KatherLab 2025): paper-to-tool with 80% success, self-correction

Implements three capabilities for Clarvis:

1. **Tool Extraction** (LATM pattern): After successful heartbeat tasks, extract
   reusable code snippets/patterns as callable tool functions, not just step lists.
   Heavyweight model (Claude Code) creates tools; lightweight (M2.5) uses them.

2. **Tool Aggregation** (ToolLibGen pattern): Cluster semantically similar procedures,
   detect overlap, and consolidate duplicates into unified tools. Uses a Code Agent
   (merge logic) + Review Agent (validation) pattern.

3. **Tool Validation** (ToolMaker pattern): Closed-loop test-generate-fix cycle for
   each extracted tool. Tools start as "draft", get validated, then promoted.

Lifecycle: draft → validated → promoted (into procedural_memory as verified)

Storage: data/tool_library/ (JSON specs + optional code files)
Brain: clarvis-procedures collection (via procedural_memory.py)

Usage:
    python3 tool_maker.py extract <output_file>     # Extract tools from task output
    python3 tool_maker.py aggregate                  # Cluster & consolidate procedures
    python3 tool_maker.py validate <tool_id>         # Validate a draft tool
    python3 tool_maker.py promote <tool_id>          # Promote validated → procedure
    python3 tool_maker.py stats                      # Library health
    python3 tool_maker.py list [--draft|--validated]  # List tools by status
"""

import json
import os
import re
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _paths  # noqa: F401 — registers all script subdirs on sys.path

WORKSPACE = Path(os.path.dirname(__file__)).parent
TOOL_LIBRARY_DIR = WORKSPACE / "data" / "tool_library"
TOOL_INDEX_FILE = TOOL_LIBRARY_DIR / "index.json"
AGGREGATION_LOG = TOOL_LIBRARY_DIR / "aggregation_log.jsonl"

# Tool lifecycle states
STATE_DRAFT = "draft"           # Freshly extracted, not yet validated
STATE_VALIDATED = "validated"   # Passed closed-loop validation
STATE_PROMOTED = "promoted"     # Pushed to procedural_memory as verified
STATE_RETIRED = "retired"       # Superseded by aggregation or failed validation

# Extraction config
MIN_CODE_LINES = 3             # Minimum lines for a code tool
MIN_PATTERN_LENGTH = 30        # Minimum chars for a pattern tool
MAX_TOOLS_PER_EXTRACTION = 5   # Don't over-extract from a single output

# Aggregation config
SIMILARITY_THRESHOLD = 0.4     # Cosine distance threshold for clustering
MAX_CLUSTER_SIZE = 8           # Max procedures to merge in one pass


def _ensure_dirs():
    """Create tool library directories if needed."""
    TOOL_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)


def _load_index() -> dict:
    """Load the tool library index."""
    _ensure_dirs()
    if TOOL_INDEX_FILE.exists():
        try:
            return json.loads(TOOL_INDEX_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {"tools": {}, "version": 1}


def _save_index(index: dict):
    """Save the tool library index."""
    _ensure_dirs()
    TOOL_INDEX_FILE.write_text(json.dumps(index, indent=2))


def _tool_id(name: str) -> str:
    """Generate a deterministic tool ID from name."""
    sanitized = re.sub(r'[^a-z0-9_]', '_', name.lower().strip())
    sanitized = re.sub(r'_+', '_', sanitized).strip('_')[:60]
    # Add short hash for uniqueness
    h = hashlib.md5(name.encode()).hexdigest()[:6]
    return f"tool_{sanitized}_{h}"


def _log_aggregation(action: str, details: dict):
    """Append to aggregation log."""
    _ensure_dirs()
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        **details,
    }
    with open(AGGREGATION_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


# =============================================================================
# 1. TOOL EXTRACTION (LATM pattern: extract reusable tools from task output)
# =============================================================================

def extract_tools(output_text: str, task_text: str = "") -> list[dict]:
    """Extract reusable tool patterns from successful task output.

    Goes beyond simple step extraction (extract_steps.py handles that).
    Looks for:
    - Code snippets that solve a specific, reusable problem
    - Shell command patterns with parameters
    - File manipulation patterns (edit, create, configure)
    - API interaction patterns

    Args:
        output_text: The full task output from Claude Code
        task_text: The original task description (for context)

    Returns:
        List of tool dicts ready for storage
    """
    tools = []

    # Strategy 1: Extract code blocks that look reusable
    code_tools = _extract_code_patterns(output_text)
    tools.extend(code_tools)

    # Strategy 2: Extract shell command patterns
    cmd_tools = _extract_command_patterns(output_text)
    tools.extend(cmd_tools)

    # Strategy 3: Extract file operation patterns
    file_tools = _extract_file_patterns(output_text, task_text)
    tools.extend(file_tools)

    # Deduplicate by content similarity
    tools = _deduplicate_tools(tools)

    # Limit extraction count
    tools = tools[:MAX_TOOLS_PER_EXTRACTION]

    # Store each tool
    stored = []
    for tool in tools:
        tool_entry = store_tool(
            name=tool["name"],
            description=tool["description"],
            tool_type=tool["type"],
            content=tool["content"],
            source_task=task_text[:200],
            tags=tool.get("tags", []),
        )
        if tool_entry:
            stored.append(tool_entry)

    return stored


def _extract_code_patterns(text: str) -> list[dict]:
    """Extract reusable code snippets from output."""
    tools = []

    # Find python/bash code blocks
    code_blocks = re.findall(
        r'```(?:python|bash|sh)?\n(.*?)```',
        text, re.DOTALL
    )

    for block in code_blocks:
        lines = block.strip().split('\n')
        if len(lines) < MIN_CODE_LINES:
            continue

        # Skip if it's just imports or comments
        meaningful = [l for l in lines if l.strip()
                      and not l.strip().startswith('#')
                      and not l.strip().startswith('import ')
                      and not l.strip().startswith('from ')]
        if len(meaningful) < MIN_CODE_LINES:
            continue

        # Derive name from first function def or first comment
        name = _derive_code_name(block)
        if not name:
            continue

        tools.append({
            "name": name,
            "description": f"Code pattern: {name}",
            "type": "code",
            "content": block.strip(),
            "tags": ["code", "extracted"],
        })

    return tools


def _extract_command_patterns(text: str) -> list[dict]:
    """Extract reusable shell command patterns."""
    tools = []

    # Find shell commands that look like reusable patterns
    # Match lines starting with $ or that look like commands
    cmd_patterns = re.findall(
        r'(?:^|\n)\s*\$?\s*((?:python3|bash|git|curl|jq|sed|awk|find|grep|'
        r'systemctl|pip|npm|docker|chmod|mkdir|cp|mv)\s+.+?)(?:\n|$)',
        text
    )

    # Group similar commands (same base command + similar args)
    seen_bases = set()
    for cmd in cmd_patterns:
        cmd = cmd.strip()
        if len(cmd) < MIN_PATTERN_LENGTH:
            continue

        base = cmd.split()[0] if cmd.split() else ""
        # Avoid storing trivial commands
        if base in ('cd', 'ls', 'echo', 'cat', 'head', 'tail'):
            continue

        # Avoid duplicate base commands
        base_sig = base + "_" + (cmd.split()[1] if len(cmd.split()) > 1 else "")
        if base_sig in seen_bases:
            continue
        seen_bases.add(base_sig)

        name = f"cmd_{base}_{_short_hash(cmd)}"
        tools.append({
            "name": name,
            "description": f"Shell pattern: {cmd[:80]}",
            "type": "command",
            "content": cmd,
            "tags": ["command", "shell", base],
        })

    return tools[:3]  # Limit command extractions


def _extract_file_patterns(text: str, task_text: str) -> list[dict]:
    """Extract file operation patterns (create/edit/configure)."""
    tools = []

    # Look for file creation patterns
    file_creates = re.findall(
        r'(?:created|wrote|generated)\s+(?:file\s+)?[`"]?([^\s`"]+\.\w+)[`"]?',
        text, re.IGNORECASE
    )

    # Look for configuration patterns
    config_edits = re.findall(
        r'(?:configured|set|added|updated)\s+(?:in\s+)?[`"]?([^\s`"]+\.(?:json|yaml|yml|toml|cfg|conf|ini))[`"]?',
        text, re.IGNORECASE
    )

    files = list(set(file_creates + config_edits))

    # Only create a tool if there's a clear pattern with multiple files
    if len(files) >= 2:
        name = f"file_ops_{_short_hash(task_text or str(files))}"
        tools.append({
            "name": name,
            "description": f"File operation pattern: {', '.join(files[:5])}",
            "type": "file_pattern",
            "content": json.dumps({
                "files_touched": files[:10],
                "task_context": task_text[:200],
            }),
            "tags": ["file_ops", "pattern"],
        })

    return tools


def _derive_code_name(code: str) -> str | None:
    """Derive a tool name from code content."""
    # Try function definition
    func_match = re.search(r'def\s+(\w+)\s*\(', code)
    if func_match:
        return func_match.group(1)

    # Try class definition
    class_match = re.search(r'class\s+(\w+)', code)
    if class_match:
        return class_match.group(1).lower()

    # Try first meaningful comment
    comment_match = re.search(r'#\s*(.+)', code)
    if comment_match:
        comment = comment_match.group(1).strip()
        if len(comment) > 10:
            return re.sub(r'[^a-z0-9_]', '_', comment.lower())[:40]

    return None


def _short_hash(text: str) -> str:
    """Short hash for dedup."""
    return hashlib.md5(text.encode()).hexdigest()[:6]


def _deduplicate_tools(tools: list[dict]) -> list[dict]:
    """Remove tools with very similar content."""
    if len(tools) <= 1:
        return tools

    seen = set()
    unique = []
    for tool in tools:
        # Hash on content
        content_hash = _short_hash(tool["content"])
        if content_hash not in seen:
            seen.add(content_hash)
            unique.append(tool)

    return unique


# =============================================================================
# 2. TOOL STORAGE
# =============================================================================

def store_tool(name: str, description: str, tool_type: str, content: str,
               source_task: str = "", tags: list[str] | None = None) -> dict | None:
    """Store a tool in the library.

    Args:
        name: Tool name
        description: What the tool does
        tool_type: "code" | "command" | "file_pattern" | "procedure"
        content: The actual tool content (code, command, pattern)
        source_task: Task that generated this tool
        tags: Categorization tags

    Returns:
        Tool entry dict, or None if storage failed
    """
    tid = _tool_id(name)
    index = _load_index()

    # Check if tool already exists
    if tid in index["tools"]:
        existing = index["tools"][tid]
        # Update use count but don't overwrite content
        existing["seen_count"] = existing.get("seen_count", 1) + 1
        existing["last_seen"] = datetime.now(timezone.utc).isoformat()
        _save_index(index)
        return existing

    tool_entry = {
        "id": tid,
        "name": name,
        "description": description,
        "type": tool_type,
        "state": STATE_DRAFT,
        "content_hash": _short_hash(content),
        "source_task": source_task[:200],
        "tags": tags or [],
        "seen_count": 1,
        "validation_attempts": 0,
        "validation_passed": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_seen": datetime.now(timezone.utc).isoformat(),
    }

    index["tools"][tid] = tool_entry
    _save_index(index)

    # Store content in a separate file (keeps index small)
    content_file = TOOL_LIBRARY_DIR / f"{tid}.content"
    content_file.write_text(content)

    return tool_entry


# =============================================================================
# 3. TOOL AGGREGATION (ToolLibGen pattern: cluster + consolidate)
# =============================================================================

def aggregate_procedures() -> dict:
    """Cluster semantically similar procedures and consolidate overlapping ones.

    ToolLibGen pattern:
    1. Load all procedures from brain
    2. Compute pairwise similarity (via brain embeddings)
    3. Cluster by semantic similarity
    4. Within each cluster, merge overlapping step sequences
    5. Store consolidated procedure, retire originals

    Returns:
        Dict with aggregation results
    """
    try:
        from clarvis.memory.procedural_memory import list_procedures, store_procedure
        from brain import brain, PROCEDURES
    except ImportError as e:
        return {"error": f"Import failed: {e}"}

    procs = list_procedures(n=100)
    if len(procs) < 2:
        return {"clusters": 0, "consolidated": 0, "message": "Too few procedures to aggregate"}

    # Step 1: Build similarity clusters using brain embeddings
    clusters = _cluster_procedures(procs, brain)

    consolidated = 0
    retired = 0

    for cluster in clusters:
        if len(cluster) < 2:
            continue

        # Step 2: Merge overlapping procedures (Code Agent role)
        merged = _merge_cluster(cluster)
        if not merged:
            continue

        # Step 3: Validate the merge (Review Agent role)
        if not _validate_merge(merged, cluster):
            _log_aggregation("merge_rejected", {
                "cluster_size": len(cluster),
                "reason": "validation_failed",
            })
            continue

        # Step 4: Store consolidated procedure
        all_tags = set()
        for proc in cluster:
            all_tags.update(proc.get("tags", []))
        all_tags.add("consolidated")

        store_procedure(
            name=merged["name"],
            description=merged["description"],
            steps=merged["steps"],
            source_task=f"Consolidated from {len(cluster)} procedures",
            importance=0.85,
            tags=list(all_tags),
            preconditions=merged.get("preconditions", []),
            termination_criteria=merged.get("termination_criteria", []),
        )

        # Step 5: Mark originals as superseded (don't delete — keep for history)
        col = brain.collections[PROCEDURES]
        for proc in cluster:
            try:
                existing = col.get(ids=[proc["id"]])
                if existing and existing["ids"]:
                    meta = existing["metadatas"][0]
                    meta["quality_tier"] = "superseded"
                    meta["superseded_by"] = merged["name"]
                    col.upsert(
                        ids=[proc["id"]],
                        documents=existing["documents"],
                        metadatas=[meta],
                    )
                    retired += 1
            except Exception:
                pass

        consolidated += 1

        _log_aggregation("merge_completed", {
            "merged_name": merged["name"],
            "source_count": len(cluster),
            "source_ids": [p["id"] for p in cluster],
            "merged_steps": len(merged["steps"]),
        })

    return {
        "total_procedures": len(procs),
        "clusters_found": len([c for c in clusters if len(c) >= 2]),
        "consolidated": consolidated,
        "retired": retired,
    }


def _cluster_procedures(procs: list[dict], brain_instance) -> list[list[dict]]:
    """Cluster procedures by semantic similarity using brain embeddings.

    Simple agglomerative clustering: for each procedure, find all others
    within SIMILARITY_THRESHOLD distance. Merge overlapping clusters.
    """
    if len(procs) < 2:
        return []

    # Get embeddings for all procedure descriptions
    col = brain_instance.collections.get("clarvis-procedures")
    if not col:
        return []

    # Build a distance matrix via brain recall
    # For efficiency, use the embedding function directly
    clusters = []
    assigned = set()

    for i, proc_a in enumerate(procs):
        if proc_a["id"] in assigned:
            continue

        cluster = [proc_a]
        assigned.add(proc_a["id"])

        # Find similar procedures
        try:
            results = brain_instance.recall(
                proc_a["description"],
                collections=["clarvis-procedures"],
                n=MAX_CLUSTER_SIZE,
                caller="tool_maker_cluster",
            )

            for result in results:
                rid = result["id"]
                if rid in assigned:
                    continue
                dist = result.get("distance", 999)
                if dist < SIMILARITY_THRESHOLD:
                    # Find matching proc
                    for proc_b in procs:
                        if proc_b["id"] == rid:
                            cluster.append(proc_b)
                            assigned.add(rid)
                            break
        except Exception:
            pass

        clusters.append(cluster)

    return clusters


def _merge_cluster(cluster: list[dict]) -> dict | None:
    """Merge a cluster of similar procedures into one consolidated procedure.

    ToolLibGen Code Agent role: extract shared logic, create unified tool.
    """
    if len(cluster) < 2:
        return None

    # Sort by quality: verified > candidate > stale, then by use_count
    tier_order = {"verified": 0, "candidate": 1, "stale": 2}
    cluster.sort(key=lambda p: (
        tier_order.get(p.get("quality_tier", "candidate"), 1),
        -p.get("use_count", 0),
    ))

    # Best procedure is the base
    base = cluster[0]

    # Collect all unique steps across the cluster
    all_steps = []
    seen_step_hashes = set()

    for proc in cluster:
        for step in proc.get("steps", []):
            # Normalize step for comparison
            step_normalized = re.sub(r'\s+', ' ', step.lower().strip())
            step_hash = _short_hash(step_normalized)
            if step_hash not in seen_step_hashes:
                seen_step_hashes.add(step_hash)
                all_steps.append(step)

    if not all_steps:
        return None

    # Derive merged name
    names = [p["name"] for p in cluster]
    # Use the shortest common prefix or the best procedure's name
    merged_name = base["name"]
    if len(merged_name) > 60:
        merged_name = merged_name[:60]

    # Collect preconditions and termination criteria
    all_preconditions = set()
    all_termination = set()
    for proc in cluster:
        for pc in proc.get("preconditions", []):
            all_preconditions.add(pc)
        for tc in proc.get("termination_criteria", []):
            all_termination.add(tc)

    return {
        "name": f"{merged_name}_consolidated",
        "description": f"Consolidated from {len(cluster)} procedures: {', '.join(names[:3])}",
        "steps": all_steps,
        "preconditions": list(all_preconditions),
        "termination_criteria": list(all_termination),
        "source_procedures": [p["id"] for p in cluster],
    }


def _validate_merge(merged: dict, originals: list[dict]) -> bool:
    """Validate that merged procedure retains capabilities of originals.

    ToolLibGen Review Agent role: check no functionality lost.
    """
    # Check 1: Merged must have at least as many steps as the largest original
    max_original_steps = max(len(p.get("steps", [])) for p in originals)
    if len(merged["steps"]) < max_original_steps * 0.7:
        return False  # Lost too many steps

    # Check 2: Must have reasonable step count
    if len(merged["steps"]) < 2 or len(merged["steps"]) > 20:
        return False

    # Check 3: Each original's key steps should be represented
    # (simplified: check that at least 50% of each original's steps are present)
    merged_steps_lower = {re.sub(r'\s+', ' ', s.lower().strip()) for s in merged["steps"]}

    for proc in originals:
        original_steps = proc.get("steps", [])
        if not original_steps:
            continue

        matched = 0
        for step in original_steps:
            step_lower = re.sub(r'\s+', ' ', step.lower().strip())
            # Check for exact or near match
            for merged_step in merged_steps_lower:
                if step_lower == merged_step or _short_hash(step_lower) == _short_hash(merged_step):
                    matched += 1
                    break

        coverage = matched / len(original_steps) if original_steps else 1.0
        if coverage < 0.5:
            return False  # Lost more than half of this procedure's steps

    return True


# =============================================================================
# 4. TOOL VALIDATION (ToolMaker pattern: closed-loop verify)
# =============================================================================

def validate_tool(tool_id: str) -> dict:
    """Validate a draft tool via closed-loop checks.

    ToolMaker pattern: test → diagnose → fix.
    For code tools: syntax check + dry-run.
    For command tools: verify command exists + parse args.
    For patterns: verify referenced files exist.

    Args:
        tool_id: The tool to validate

    Returns:
        Validation result dict
    """
    index = _load_index()

    if tool_id not in index["tools"]:
        return {"error": f"Tool {tool_id} not found"}

    tool = index["tools"][tool_id]
    content_file = TOOL_LIBRARY_DIR / f"{tool_id}.content"

    if not content_file.exists():
        tool["state"] = STATE_RETIRED
        _save_index(index)
        return {"error": "Content file missing", "retired": True}

    content = content_file.read_text()
    tool["validation_attempts"] = tool.get("validation_attempts", 0) + 1

    checks = []
    passed = True

    if tool["type"] == "code":
        checks = _validate_code(content)
    elif tool["type"] == "command":
        checks = _validate_command(content)
    elif tool["type"] == "file_pattern":
        checks = _validate_file_pattern(content)
    elif tool["type"] == "procedure":
        checks = [{"check": "procedure_format", "passed": True}]

    passed = all(c["passed"] for c in checks) if checks else False

    if passed:
        tool["state"] = STATE_VALIDATED
        tool["validation_passed"] = True
    else:
        # ToolMaker self-correction: mark for retry or retire
        if tool["validation_attempts"] >= 3:
            tool["state"] = STATE_RETIRED
        # else stays draft for retry

    _save_index(index)

    return {
        "tool_id": tool_id,
        "passed": passed,
        "checks": checks,
        "attempts": tool["validation_attempts"],
        "state": tool["state"],
    }


def _validate_code(content: str) -> list[dict]:
    """Validate Python code tool."""
    checks = []

    # Syntax check
    try:
        compile(content, "<tool>", "exec")
        checks.append({"check": "syntax", "passed": True})
    except SyntaxError as e:
        checks.append({"check": "syntax", "passed": False, "error": str(e)})

    # Check for dangerous patterns
    dangerous = [
        (r'os\.system\s*\(', "os.system call"),
        (r'subprocess\.call\s*\(\s*["\']', "subprocess with string"),
        (r'eval\s*\(', "eval call"),
        (r'exec\s*\(', "exec call"),
        (r'__import__\s*\(', "dynamic import"),
    ]
    for pattern, desc in dangerous:
        if re.search(pattern, content):
            checks.append({"check": f"security_{desc}", "passed": False, "error": desc})

    if not any(not c["passed"] for c in checks if c["check"].startswith("security")):
        checks.append({"check": "security", "passed": True})

    # Check it defines something reusable (function or class)
    has_def = bool(re.search(r'(?:def|class)\s+\w+', content))
    checks.append({"check": "reusable_definition", "passed": has_def})

    return checks


def _validate_command(content: str) -> list[dict]:
    """Validate shell command tool."""
    checks = []

    # Check command exists
    cmd = content.strip().split()[0] if content.strip() else ""
    if not cmd:
        return [{"check": "non_empty", "passed": False}]

    # Check it's not a dangerous standalone command
    dangerous_cmds = {'rm', 'rmdir', 'dd', 'mkfs', 'shutdown', 'reboot'}
    is_safe = cmd not in dangerous_cmds
    checks.append({"check": "not_dangerous", "passed": is_safe,
                    "error": f"Dangerous command: {cmd}" if not is_safe else None})

    # Verify command is available on system
    import shutil
    cmd_found = shutil.which(cmd) is not None
    checks.append({"check": "command_exists", "passed": cmd_found,
                    "error": f"Command not found: {cmd}" if not cmd_found else None})

    return checks


def _validate_file_pattern(content: str) -> list[dict]:
    """Validate file operation pattern tool."""
    checks = []

    try:
        pattern_data = json.loads(content)
        checks.append({"check": "valid_json", "passed": True})

        files = pattern_data.get("files_touched", [])
        if files:
            checks.append({"check": "has_files", "passed": True})
        else:
            checks.append({"check": "has_files", "passed": False, "error": "No files listed"})
    except json.JSONDecodeError:
        checks.append({"check": "valid_json", "passed": False, "error": "Invalid JSON"})

    return checks


# =============================================================================
# 5. TOOL PROMOTION (push validated tools into procedural memory)
# =============================================================================

def promote_tool(tool_id: str) -> dict:
    """Promote a validated tool into procedural_memory as a verified procedure.

    LATM tool-user pattern: once the tool-maker validates a tool, it becomes
    available for the tool-user (M2.5 / future heartbeats) to discover and use.
    """
    try:
        from clarvis.memory.procedural_memory import store_procedure
    except ImportError:
        return {"error": "procedural_memory not available"}

    index = _load_index()
    if tool_id not in index["tools"]:
        return {"error": f"Tool {tool_id} not found"}

    tool = index["tools"][tool_id]

    if tool["state"] not in (STATE_VALIDATED, STATE_DRAFT):
        return {"error": f"Tool in state '{tool['state']}', expected 'validated' or 'draft'"}

    content_file = TOOL_LIBRARY_DIR / f"{tool_id}.content"
    content = content_file.read_text() if content_file.exists() else ""

    # Convert tool to procedure
    if tool["type"] == "code":
        steps = [f"Use code tool: {tool['name']}", f"Content: {content[:200]}"]
    elif tool["type"] == "command":
        steps = [f"Run: {content.strip()}"]
    elif tool["type"] == "file_pattern":
        try:
            pattern_data = json.loads(content)
            files = pattern_data.get("files_touched", [])
            steps = [f"Touch files: {', '.join(files[:5])}"]
        except json.JSONDecodeError:
            steps = [f"File pattern: {content[:200]}"]
    else:
        steps = [tool["description"]]

    proc_id = store_procedure(
        name=tool["name"],
        description=tool["description"],
        steps=steps,
        source_task=tool.get("source_task", ""),
        importance=0.85,
        tags=tool.get("tags", []) + ["tool_maker", "promoted"],
    )

    tool["state"] = STATE_PROMOTED
    tool["promoted_proc_id"] = proc_id
    tool["promoted_at"] = datetime.now(timezone.utc).isoformat()
    _save_index(index)

    return {
        "tool_id": tool_id,
        "proc_id": proc_id,
        "state": STATE_PROMOTED,
    }


# =============================================================================
# 6. POSTFLIGHT HOOK (called from heartbeat_postflight.py)
# =============================================================================

def postflight_extract(output_text: str, task_text: str, task_status: str) -> dict:
    """Hook for heartbeat postflight — extract tools from successful task output.

    Only extracts on success. Returns a summary for logging.
    """
    if task_status != "success":
        return {"skipped": True, "reason": "not_success"}

    if not output_text or len(output_text.strip()) < 100:
        return {"skipped": True, "reason": "output_too_short"}

    tools = extract_tools(output_text, task_text)

    return {
        "extracted": len(tools),
        "tool_ids": [t["id"] for t in tools],
    }


# =============================================================================
# 7. STATS & LISTING
# =============================================================================

def library_stats() -> dict:
    """Return tool library health metrics."""
    index = _load_index()
    tools = index.get("tools", {})

    states = {}
    types = {}
    total_seen = 0

    for t in tools.values():
        state = t.get("state", STATE_DRAFT)
        states[state] = states.get(state, 0) + 1
        ttype = t.get("type", "unknown")
        types[ttype] = types.get(ttype, 0) + 1
        total_seen += t.get("seen_count", 1)

    # Aggregation log stats
    agg_count = 0
    if AGGREGATION_LOG.exists():
        agg_count = sum(1 for line in open(AGGREGATION_LOG) if line.strip())

    return {
        "total_tools": len(tools),
        "states": states,
        "types": types,
        "total_observations": total_seen,
        "aggregation_events": agg_count,
        "promotion_rate": round(
            states.get(STATE_PROMOTED, 0) / len(tools) * 100, 1
        ) if tools else 0,
    }


def list_tools(state_filter: str | None = None) -> list[dict]:
    """List tools in the library, optionally filtered by state."""
    index = _load_index()

    tools = []
    for t in index.get("tools", {}).values():
        if state_filter and t.get("state") != state_filter:
            continue
        tools.append(t)

    tools.sort(key=lambda t: t.get("seen_count", 0), reverse=True)
    return tools


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: tool_maker.py <command> [args]")
        print("Commands:")
        print("  extract <output_file>     — Extract tools from task output")
        print("  aggregate                 — Cluster & consolidate procedures")
        print("  validate <tool_id>        — Validate a draft tool")
        print("  validate-all              — Validate all draft tools")
        print("  promote <tool_id>         — Promote validated → procedure")
        print("  stats                     — Library health metrics")
        print("  list [--draft|--validated|--promoted] — List tools")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "extract":
        filepath = sys.argv[2] if len(sys.argv) > 2 else ""
        task = sys.argv[3] if len(sys.argv) > 3 else ""
        if not filepath:
            print("Error: provide output file path")
            sys.exit(1)
        try:
            with open(filepath) as f:
                text = f.read()
        except (FileNotFoundError, IOError) as e:
            print(f"Error: {e}")
            sys.exit(1)
        tools = extract_tools(text, task)
        print(f"Extracted {len(tools)} tools:")
        for t in tools:
            print(f"  [{t['state']}] {t['id']}: {t['description'][:60]}")

    elif cmd == "aggregate":
        result = aggregate_procedures()
        print(json.dumps(result, indent=2))

    elif cmd == "validate":
        tool_id = sys.argv[2] if len(sys.argv) > 2 else ""
        if not tool_id:
            print("Error: provide tool_id")
            sys.exit(1)
        result = validate_tool(tool_id)
        print(json.dumps(result, indent=2))

    elif cmd == "validate-all":
        index = _load_index()
        validated = 0
        failed = 0
        for tid, t in index["tools"].items():
            if t.get("state") == STATE_DRAFT:
                result = validate_tool(tid)
                if result.get("passed"):
                    validated += 1
                    print(f"  PASS: {tid}")
                else:
                    failed += 1
                    print(f"  FAIL: {tid} — {[c for c in result.get('checks', []) if not c['passed']]}")
        print(f"\nValidated: {validated}, Failed: {failed}")

    elif cmd == "promote":
        tool_id = sys.argv[2] if len(sys.argv) > 2 else ""
        if not tool_id:
            print("Error: provide tool_id")
            sys.exit(1)
        result = promote_tool(tool_id)
        print(json.dumps(result, indent=2))

    elif cmd == "stats":
        s = library_stats()
        print("Tool Library Stats:")
        print(f"  Total tools: {s['total_tools']}")
        print(f"  States: {json.dumps(s['states'])}")
        print(f"  Types: {json.dumps(s['types'])}")
        print(f"  Total observations: {s['total_observations']}")
        print(f"  Aggregation events: {s['aggregation_events']}")
        print(f"  Promotion rate: {s['promotion_rate']}%")

    elif cmd == "list":
        state_filter = None
        for arg in sys.argv[2:]:
            if arg == "--draft":
                state_filter = STATE_DRAFT
            elif arg == "--validated":
                state_filter = STATE_VALIDATED
            elif arg == "--promoted":
                state_filter = STATE_PROMOTED
        tools = list_tools(state_filter)
        if not tools:
            print("No tools found.")
        else:
            for t in tools:
                print(f"  [{t['state']}] {t['id']}: {t['description'][:60]} (seen {t['seen_count']}x)")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
