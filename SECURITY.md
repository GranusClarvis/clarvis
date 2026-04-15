# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, please email **security@granuslabs.com** with:

- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will acknowledge your report within 48 hours and aim to provide a fix timeline within 5 business days.

## Scope

The following are in scope:

- Secret leakage in tracked files or git history
- Code injection via brain queries, CLI inputs, or hook scripts
- Privilege escalation in the cron/heartbeat pipeline
- Unsafe deserialization of stored data (ChromaDB, JSONL, JSON)

The following are out of scope:

- Vulnerabilities in upstream dependencies (report to their maintainers)
- Issues requiring physical access to the host machine
- Social engineering attacks

## Security Measures

Clarvis includes several built-in security features:

- **Secret redaction** (`clarvis/brain/secret_redaction.py`) — hooks into brain storage to detect and redact API keys, tokens, and credentials before they reach the vector store
- **Gitleaks CI** — automated secret scanning on every push and pull request
- **Environment-only credentials** — all API keys and tokens are loaded from environment variables or external config files excluded from version control
- **Mutual-exclusion locking** — cron jobs and Claude Code spawners acquire locks to prevent race conditions
