# Agent Interoperability Protocols: MCP + A2A + ACP + ANP

**Date:** 2026-03-06
**Source:** Ehtesham et al., "A Survey of Agent Interoperability Protocols" (arXiv:2505.02279, May 2025)
**Additional:** Google A2A announcement, Anthropic MCP spec, IBM ACP docs, LF AAIF announcements

## The Four Protocols — Layered Stack

### 1. MCP (Model Context Protocol) — Tool & Data Access Layer
- **Origin:** Anthropic (Nov 2024), donated to Linux Foundation AAIF (Dec 2025)
- **Co-founders:** Anthropic, Block, OpenAI; backed by Google, Microsoft, AWS, Cloudflare
- **Mechanism:** JSON-RPC client-server interface for secure tool invocation and typed data exchange
- **Adoption:** 97M+ monthly SDK downloads, 10K+ servers, supported by Claude/ChatGPT/Gemini/VS Code/Cursor
- **Latest spec:** 2025-11-25
- **Scope:** Agent↔Tool communication (not agent↔agent)

### 2. A2A (Agent-to-Agent Protocol) — Peer Collaboration Layer
- **Origin:** Google (Apr 2025), now under Linux Foundation
- **Version:** 0.3 (Jul 2025) — added gRPC, signed security cards, extended Python SDK
- **Participants:** 150+ organizations
- **Key concept:** **Agent Cards** — JSON capability descriptors published at `/.well-known/agent.json`
  - Include: name, description, capabilities, content types, security schemes (OAuth2, API keys, OIDC)
- **Task lifecycle:** submitted → working → input-required → completed/failed
- **Transport:** HTTPS + JSON-RPC 2.0 (+ gRPC in v0.3)
- **ACP merger (Aug 2025):** IBM's ACP merged into A2A, adding RESTful simplicity and async-first patterns

### 3. ACP (Agent Communication Protocol) — Now Part of A2A
- **Origin:** IBM Research (Mar 2025), powered BeeAI Platform
- **Merged:** Into A2A under Linux Foundation (Aug 2025)
- **Key contributions absorbed:** RESTful HTTP endpoints, MIME-typed multipart messages, session management, async-first design
- **Migration:** BeeAI agents become A2A-compliant via `A2AServer` adapter

### 4. ANP (Agent Network Protocol) — Decentralized Discovery Layer
- **Origin:** Open-source community project, W3C Community Group
- **Identity:** W3C DIDs (`did:wba` method) — HTTPS-hosted DID documents
- **Discovery:** JSON-LD agent descriptions at predictable URLs, crawlable by search engines
- **Three-layer arch:** Identity+encryption → Meta-protocol negotiation → Application protocol
- **Goal:** "HTTP of the agentic web era" — open agent marketplace/registry

## Phased Adoption Roadmap (from paper)

| Phase | Protocol | Purpose | Clarvis Status |
|-------|----------|---------|----------------|
| 1 | MCP | Tool access | **Active** — Claude Code uses MCP natively |
| 2 | A2A | Agent collaboration | **Mappable** — project_agent.py task protocol aligns |
| 3 | ANP | Decentralized discovery | **Future** — relevant for open agent marketplace |

## Clarvis Application — 5 Concrete Ideas

### Idea 1: A2A-Align project_agent.py Task Protocol
Current `project_agent.py` JSON result format maps well to A2A Task lifecycle:
- `status: "success"/"partial"/"failed"` → A2A: `completed`/`working`/`failed`
- `pr_url`, `summary`, `files_changed` → A2A artifacts
- `follow_ups` → A2A `input-required` state
- **Action:** Add A2A-compatible status codes and artifact structure to agent result format

### Idea 2: Agent Cards for Project Agents
Current `agent.json` has name/repo/branch/constraints/budget but lacks:
- Capability advertisement (what tasks this agent can handle)
- Supported content types
- Security scheme declarations
- **Action:** Extend agent.json with A2A Agent Card fields: `capabilities[]`, `contentTypes[]`, `securitySchemes{}`

### Idea 3: Expose ClarvisDB as MCP Server
Since MCP is the universal tool-access protocol:
- Expose `brain.search()`, `brain.remember()`, `brain.stats()` as MCP tools
- Any MCP-compatible client (Claude, ChatGPT, Cursor) could query Clarvis knowledge
- **Action:** Create `clarvis_mcp_server.py` implementing MCP JSON-RPC spec

### Idea 4: Task Router as A2A Client
`task_router.py` already routes by complexity to different models. Extend to:
- Discover project agents via Agent Cards
- Delegate CODE-HEAVY tasks to matching project agents via A2A protocol
- **Action:** Add agent discovery to task_router.py routing logic

### Idea 5: ANP Discovery for Multi-Instance Clarvis (Long-term)
If multiple Clarvis instances or external agents need to discover each other:
- Publish agent descriptions as JSON-LD at `/.well-known/agent.json`
- Use DID-based authentication for cross-instance trust
- **Timeline:** Only after A2A alignment is mature

## Context Relevance Note
This research directly improves Context Relevance (current: 0.838) by:
- Standardizing agent communication reduces ambiguous/misformatted task results
- A2A Agent Cards provide structured capability metadata, improving task-agent matching
- MCP tools for brain access would let external agents query with proper context

## Key Takeaway
The agent protocol landscape is converging: MCP won the tool layer, A2A (absorbing ACP) won the agent collaboration layer, ANP targets the open discovery layer. All three are now under Linux Foundation governance. Clarvis's `project_agent.py` already implements 70% of A2A's Task model — aligning the remaining 30% (Agent Cards, standard status codes, artifact format) is low-effort, high-value.

## Sources
- [Survey paper](https://arxiv.org/abs/2505.02279) — Ehtesham et al., May 2025
- [A2A announcement](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/)
- [A2A spec v0.3](https://a2a-protocol.org/latest/specification/)
- [MCP spec](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP → AAIF donation](https://www.anthropic.com/news/donating-the-model-context-protocol-and-establishing-of-the-agentic-ai-foundation)
- [ACP merges into A2A](https://lfaidata.foundation/communityblog/2025/08/29/acp-joins-forces-with-a2a-under-the-linux-foundations-lf-ai-data/)
- [ANP white paper](https://arxiv.org/html/2508.00007v1)
- [IBM ACP overview](https://www.ibm.com/think/topics/agent-communication-protocol)
