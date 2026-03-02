---
name: project-agent
description: "Manage project agents — spawn tasks, check status, promote results, list agents. Usage: /project-agent <command>"
metadata: {"clawdbot":{"emoji":"🏗️","requires":{"bins":["claude","python3"]}}}
user-invocable: true
---

# /project-agent — Manage Project Agents

When the user sends `/project-agent <command>`, manage isolated project agents that handle tasks in external repos.

## What This Skill Does

Project agents are isolated Claude Code instances that work in their own git repos with separate ChromaDB brains. Clarvis delegates specialized tasks (PRs, bug fixes, features) to project agents without polluting its own workspace. Results are promoted back to Clarvis's memory via digest files.

## Commands

### spawn — Delegate a task to an agent
```bash
python3 /home/agent/.openclaw/workspace/scripts/project_agent.py spawn <agent-name> "<task description>" --timeout 1200
# With extra context:
python3 /home/agent/.openclaw/workspace/scripts/project_agent.py spawn <agent-name> "<task>" --context "PR #42 needs hotfix for auth bug"
# With auto-retry on failure (max 2):
python3 /home/agent/.openclaw/workspace/scripts/project_agent.py spawn <agent-name> "<task>" --retries 1
```
Returns JSON: `{task_id, agent, exit_code, elapsed, result: {status, pr_url, summary, files_changed, procedures, follow_ups, tests_passed}}`

### status — Check if an agent is running or idle
```bash
python3 /home/agent/.openclaw/workspace/scripts/project_agent.py status <agent-name>
```
Returns JSON: `{name, status, last_run, last_task, tasks, successes}`

### promote — Pull results back to Clarvis
```bash
python3 /home/agent/.openclaw/workspace/scripts/project_agent.py promote <agent-name>
```
Collects unpromoted task summaries, extracts procedures and follow-ups, writes `memory/cron/agent_<name>_digest.md`, stores top procedures in Clarvis brain. Returns JSON: `{status, agent, count, procedures, brain_stored, digest}`

### list — Show all agents
```bash
python3 /home/agent/.openclaw/workspace/scripts/project_agent.py list
```
Returns JSON array: `[{name, repo, branch, status, tasks, successes, prs, last_run}]`

### info — Detailed agent state
```bash
python3 /home/agent/.openclaw/workspace/scripts/project_agent.py info <agent-name>
```
Returns JSON with full config, summaries, brain size, git status.

### create — Scaffold a new agent
```bash
python3 /home/agent/.openclaw/workspace/scripts/project_agent.py create <name> --repo <git-url> --branch dev
```
Clones repo, initializes lite brain (5 collections), writes CLAUDE.md with constraints.

### benchmark — Run agent health metrics
```bash
python3 /home/agent/.openclaw/workspace/scripts/project_agent.py benchmark <agent-name>
```
Returns isolation, retrieval quality, and task success metrics.

### destroy — Remove an agent permanently
```bash
python3 /home/agent/.openclaw/workspace/scripts/project_agent.py destroy <agent-name> --confirm
```
**Irreversible.** Requires `--confirm` flag.

## Execution Steps

1. Parse the command after `/project-agent` — extract subcommand and arguments
2. Run the corresponding `project_agent.py` command using the template above
3. Parse the JSON output and present results clearly to the user
4. For **spawn**: report task_id, elapsed time, status, PR URL (if any), and summary
5. For **promote**: report how many summaries were promoted and what procedures were learned
6. For **list/status**: present agent states in a readable table

## Rules

- **Always use full path**: `python3 /home/agent/.openclaw/workspace/scripts/project_agent.py`
- **Default timeout for spawn is 1200s** (20 min). Use 1800s for large tasks. Minimum 600s.
- **Tell the user** what agent you're spawning to and the task — spawn is async and takes minutes
- **Promote after spawn** — results stay in the agent's workspace until promoted
- **NEVER destroy without user confirmation** — always ask first, even if they said "delete"
- **Check status before spawning** — if an agent is already `running`, warn the user
- **Available agents** — run `list` first if unsure which agents exist
- **Fork workflow**: project agents push to forks and PR against upstream repos (they don't have direct push access to upstream)
- **Cost awareness**: each spawn costs ~$0.30-1.50 depending on task complexity and timeout

## Example

User: `/project-agent spawn star-world-order "Fix the failing CI tests in the auth module"`

Response: "Spawning task to **star-world-order** agent (20 min timeout) — fixing failing CI tests in auth module."

Then execute:
```bash
python3 /home/agent/.openclaw/workspace/scripts/project_agent.py spawn star-world-order "Fix the failing CI tests in the auth module" --timeout 1200
```

After completion, report the result and suggest promoting:
```bash
python3 /home/agent/.openclaw/workspace/scripts/project_agent.py promote star-world-order
```
