"""Secret redaction hook for brain storage.

Scans text for common secret patterns (API keys, tokens, private keys)
before brain.remember() persists it. Redacts matches in-place by mutating
the hook context dict, so the stored text never contains raw secrets.

Wired as a BRAIN_PRE_STORE hook with priority 5 (runs before everything).
"""

import logging
import re

log = logging.getLogger(__name__)

# --- Secret patterns ---
# Each tuple: (name, compiled regex, replacement)
_PATTERNS = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED:AWS_KEY]"),
    ("aws_secret_key", re.compile(r"(?:aws_secret_access_key|secret_key)\s*[=:]\s*[A-Za-z0-9/+=]{40}"), "[REDACTED:AWS_SECRET]"),
    ("openai_key", re.compile(r"sk-[A-Za-z0-9]{20,}"), "[REDACTED:API_KEY]"),
    ("openrouter_key", re.compile(r"sk-or-v1-[A-Za-z0-9]{64,}"), "[REDACTED:OPENROUTER_KEY]"),
    ("bearer_token", re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}"), "[REDACTED:BEARER]"),
    ("generic_api_key", re.compile(r"(?:api[_-]?key|apikey|token|secret)\s*[=:]\s*['\"]?[A-Za-z0-9._~+/=-]{20,}['\"]?", re.IGNORECASE), "[REDACTED:CREDENTIAL]"),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"), "[REDACTED:PRIVATE_KEY]"),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}"), "[REDACTED:GITHUB_TOKEN]"),
    ("telegram_bot_token", re.compile(r"\d{8,10}:[A-Za-z0-9_-]{35}"), "[REDACTED:TELEGRAM_TOKEN]"),
]


def redact_secrets(text: str) -> tuple[str, list[str]]:
    """Scan text and replace secret patterns.

    Returns:
        (redacted_text, list_of_matched_pattern_names)
    """
    matched = []
    for name, pattern, replacement in _PATTERNS:
        if pattern.search(text):
            text = pattern.sub(replacement, text)
            matched.append(name)
    return text, matched


def brain_pre_store_hook(context: dict) -> dict:
    """BRAIN_PRE_STORE hook — redact secrets from text before storage.

    Mutates context["text"] in-place so downstream storage sees clean text.
    Returns dict with redaction info for audit logging.
    """
    text = context.get("text", "")
    if not text:
        return {"redacted": False}

    cleaned, matched = redact_secrets(text)
    if matched:
        context["text"] = cleaned
        log.warning("Secret redaction: removed %d pattern(s) from brain store: %s",
                     len(matched), ", ".join(matched))
        return {"redacted": True, "patterns": matched, "count": len(matched)}

    return {"redacted": False}


def register(hook_registry):
    """Register the secret redaction hook with priority 5 (earliest possible)."""
    from clarvis.heartbeat.hooks import HookPhase
    hook_registry.register(
        HookPhase.BRAIN_PRE_STORE,
        "secret_redaction",
        brain_pre_store_hook,
        priority=5,
    )
