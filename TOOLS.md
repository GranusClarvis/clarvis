# Clarvis — Available Tools

## Conway Terminal (via mcporter MCP — 48 tools)
Connected as a native MCP server via mcporter. All tools called directly.

### Sandboxes (Cloud VMs)
- sandbox_create, sandbox_list, sandbox_get, sandbox_delete
- sandbox_exec — Run shell commands
- sandbox_write_file, sandbox_read_file
- sandbox_expose_port, sandbox_list_ports, sandbox_remove_port
- sandbox_add_domain, sandbox_list_domains, sandbox_remove_domain
- sandbox_terminal_session, sandbox_metrics, sandbox_activity, sandbox_commands, sandbox_get_url

### PTY (Interactive Terminals)
- sandbox_pty_create, sandbox_pty_write, sandbox_pty_read
- sandbox_pty_close, sandbox_pty_resize, sandbox_pty_list

### Wallet & x402 Payments
- wallet_info — Address + USDC balance on Base
- wallet_networks — Supported networks
- x402_discover, x402_check, x402_fetch — Automatic USDC payments

### Credits
- credits_balance, credits_history, credits_pricing
- credits_topup / credits_purchase — Buy credits with USDC

### Inference
- chat_completions — LLM inference via Conway credits

### Domains
- domain_search, domain_check, domain_list, domain_info
- domain_register, domain_renew
- domain_dns_list, domain_dns_add, domain_dns_update, domain_dns_delete
- domain_pricing, domain_privacy, domain_nameservers

### Network
- Base Mainnet (USDC)
- Protocol: x402 (HTTP 402 auto-payment)
