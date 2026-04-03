# Clarvis MCP Server — Design Document

_Created: 2026-04-03. Status: Design (not yet implemented)._

## Goal

Expose Clarvis's core capabilities as an [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server so external tools, agents, and IDE extensions can query the brain, store memories, trigger tasks, and check system health — without knowing Clarvis internals.

## Scope

**In scope (v0):**
- `brain.search` — semantic search across brain collections
- `brain.remember` — store a memory with importance/tags
- `brain.stats` — collection counts, graph size, last-decay timestamp
- `heartbeat.status` — last heartbeat result, queue depth, active goals
- `task.spawn` — enqueue a task for Claude Code execution (async)

**Out of scope (v0):**
- Browser automation, project agent orchestration, cost tracking
- Streaming/SSE (use polling for task status)
- Multi-tenant auth (single-user system)

## Architecture

```
External client (Claude Desktop, VS Code, other MCP client)
       │
       ▼  JSON-RPC over stdio  (or HTTP/SSE, see Transport below)
┌──────────────────────────────┐
│   clarvis-mcp-server         │  ~200 LOC Python
│   (clarvis/mcp/server.py)    │
│                              │
│   Tool handlers:             │
│     brain_search()           │
│     brain_remember()         │
│     brain_stats()            │
│     heartbeat_status()       │
│     task_spawn()             │
│                              │
│   Uses: clarvis.brain,       │
│     clarvis.heartbeat,       │
│     scripts/spawn_claude.sh  │
└──────────────────────────────┘
       │
       ▼
   ClarvisDB (ChromaDB + SQLite graph)
   Heartbeat pipeline (filesystem state)
   spawn_claude.sh (subprocess)
```

## Transport

**Primary: stdio** (simplest, works with Claude Desktop / VS Code MCP clients).
The server reads JSON-RPC from stdin, writes to stdout. No network port needed.

**Optional: HTTP+SSE** (for remote access). Bind `127.0.0.1:18790` (next to gateway on 18789). Require `Authorization: Bearer <token>` header. Token read from `$CLARVIS_MCP_TOKEN` or `data/mcp_token.txt`.

## Tool Definitions

### `brain_search`

```json
{
  "name": "brain_search",
  "description": "Semantic search across Clarvis brain memories",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": { "type": "string", "description": "Natural language search query" },
      "n": { "type": "integer", "default": 5, "description": "Max results (1-20)" },
      "collection": { "type": "string", "description": "Optional: restrict to one collection" }
    },
    "required": ["query"]
  }
}
```

**Returns:** Array of `{id, text, distance, collection, importance, tags}`.

### `brain_remember`

```json
{
  "name": "brain_remember",
  "description": "Store a memory in Clarvis brain",
  "inputSchema": {
    "type": "object",
    "properties": {
      "text": { "type": "string", "description": "Memory content" },
      "importance": { "type": "number", "default": 0.5, "minimum": 0.0, "maximum": 1.0 },
      "collection": { "type": "string", "default": "clarvis-memories" },
      "tags": { "type": "array", "items": { "type": "string" }, "default": [] },
      "source": { "type": "string", "default": "mcp-client" }
    },
    "required": ["text"]
  }
}
```

**Returns:** `{id, collection, stored: true}`.

**Safety:** Importance capped at 0.9 for MCP clients (prevent external overwrite of critical memories). Source always tagged `mcp-<client_name>`.

### `brain_stats`

```json
{
  "name": "brain_stats",
  "description": "Get brain health stats: collection sizes, graph edges, last decay",
  "inputSchema": { "type": "object", "properties": {} }
}
```

**Returns:** `{collections: {name: count, ...}, graph_edges: int, last_decay: iso_date, total_memories: int}`.

### `heartbeat_status`

```json
{
  "name": "heartbeat_status",
  "description": "Get latest heartbeat status and queue depth",
  "inputSchema": { "type": "object", "properties": {} }
}
```

**Returns:** `{last_run: iso_date, last_task: str, last_status: str, queue_depth: int, active_goals: [{name, progress}]}`.

**Implementation:** Reads `data/heartbeat_state.json` and `memory/evolution/QUEUE.md` (count pending `- [ ]` lines).

### `task_spawn`

```json
{
  "name": "task_spawn",
  "description": "Spawn a Claude Code task (async). Returns immediately with task ID.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "prompt": { "type": "string", "description": "Task description for Claude Code" },
      "timeout": { "type": "integer", "default": 1200, "minimum": 600, "maximum": 1800 }
    },
    "required": ["prompt"]
  }
}
```

**Returns:** `{task_id, status: "spawned", output_file: "/tmp/claude_output_<id>.txt"}`.

**Safety:**
- Rate limit: max 1 concurrent spawn, max 3 per hour
- Prompt length cap: 4000 chars
- Uses `spawn_claude.sh` subprocess (inherits lock, env, timeout)
- Caller can poll `task_spawn_status` (follow-up tool, not in v0 — check output file existence)

## Auth & Safety

| Concern | Mitigation |
|---------|-----------|
| Unauthorized brain writes | Importance capped at 0.9; source always prefixed `mcp-` |
| Prompt injection via task_spawn | Prompt written to temp file (no shell interpolation); `spawn_claude.sh` handles escaping |
| DoS via rapid spawns | Rate limit: 1 concurrent, 3/hour, global lock via `/tmp/clarvis_claude_global.lock` |
| Data exfiltration | stdio transport has no network surface; HTTP requires bearer token |
| Collection corruption | brain_remember only writes to `clarvis-memories` by default; other collections require explicit opt-in |

## Implementation Sketch

```python
# clarvis/mcp/server.py  (~200 LOC)

import json
import sys
from clarvis.brain import brain, search, remember

def handle_tool_call(name: str, args: dict) -> dict:
    if name == "brain_search":
        results = search(args["query"], n=args.get("n", 5),
                         collection=args.get("collection"))
        return [{"id": r["id"], "text": r["document"][:500],
                 "distance": r.get("distance"), "collection": r.get("collection")}
                for r in results]

    elif name == "brain_remember":
        importance = min(args.get("importance", 0.5), 0.9)  # cap
        mem_id = brain.store(args["text"], importance=importance,
                             collection=args.get("collection", "clarvis-memories"),
                             tags=args.get("tags", []),
                             source=f"mcp-{args.get('source', 'client')}")
        return {"id": mem_id, "stored": True}

    elif name == "brain_stats":
        return brain.stats()

    elif name == "heartbeat_status":
        return _read_heartbeat_status()

    elif name == "task_spawn":
        return _spawn_task(args["prompt"], args.get("timeout", 1200))

    else:
        raise ValueError(f"Unknown tool: {name}")


def main():
    """stdio JSON-RPC loop."""
    for line in sys.stdin:
        request = json.loads(line)
        method = request.get("method")
        if method == "tools/list":
            result = TOOL_DEFINITIONS  # list of tool schemas above
        elif method == "tools/call":
            params = request.get("params", {})
            result = handle_tool_call(params["name"], params.get("arguments", {}))
        else:
            result = {"error": f"Unsupported method: {method}"}
        response = {"jsonrpc": "2.0", "id": request.get("id"), "result": result}
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()
```

## File Layout

```
clarvis/mcp/
  __init__.py          # empty
  server.py            # ~200 LOC: tool handlers + stdio loop
  tools.py             # tool schema definitions (JSON dicts)
```

## Dependencies

- No new dependencies. Uses `clarvis.brain` (already installed), `subprocess` for spawn, `json`/`sys` stdlib.
- Optional HTTP mode would add `uvicorn` + `starlette` (~2 deps), but stdio-first means zero new deps for v0.

## Configuration

Add to `claude_desktop_config.json` (or equivalent MCP client config):

```json
{
  "mcpServers": {
    "clarvis": {
      "command": "python3",
      "args": ["-m", "clarvis.mcp.server"],
      "env": {
        "CLARVIS_WORKSPACE": "/home/agent/.openclaw/workspace"
      }
    }
  }
}
```

## Implementation Plan

1. **Phase 1** (~2h): `brain_search`, `brain_remember`, `brain_stats` over stdio. Test with `echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"brain_search","arguments":{"query":"test"}}}' | python3 -m clarvis.mcp.server`.
2. **Phase 2** (~1h): `heartbeat_status`, `task_spawn` with rate limiting.
3. **Phase 3** (optional): HTTP+SSE transport, bearer token auth, `task_spawn_status` polling tool.

## Open Questions

- Should `brain_remember` support writing to `autonomous-learning` or only `clarvis-memories`? (Leaning: whitelist of safe collections.)
- Should we expose `brain.recall` (with graph traversal) as a separate tool or fold it into `brain_search`?
- Is there demand for a `queue.list` tool that returns pending QUEUE.md items?
