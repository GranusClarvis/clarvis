#!/usr/bin/env python3
"""Smoke tests for universal_web_agent.py — no browser required."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from universal_web_agent import (
    CredentialStore, TaskResult, WebAgentRunner,
    _obfuscate, _deobfuscate, VERIFICATION_PATTERNS,
)


def test_obfuscation_roundtrip():
    """Obfuscation should be reversible."""
    for plaintext in ["password123", "p@ss w0rd!", "", "ü†f-8"]:
        encoded = _obfuscate(plaintext)
        assert encoded != plaintext or plaintext == "", f"Should be obfuscated: {plaintext}"
        decoded = _deobfuscate(encoded)
        assert decoded == plaintext, f"Roundtrip failed: {plaintext} -> {encoded} -> {decoded}"
    print("  PASS: obfuscation roundtrip")


def test_credential_store():
    """CredentialStore should set/get/list/remove credentials."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = f.name

    try:
        from pathlib import Path
        store = CredentialStore(path=Path(tmp_path))

        # Empty store
        assert store.list_services() == []
        assert store.get("gmail") is None

        # Set credentials
        store.set("gmail", "test@gmail.com", "secret123",
                  login_url="https://accounts.google.com", notes="test account")

        # Get credentials — password should be decrypted
        creds = store.get("gmail")
        assert creds is not None
        assert creds["username"] == "test@gmail.com"
        assert creds["password"] == "secret123"
        assert creds["login_url"] == "https://accounts.google.com"

        # File should have obfuscated password, not plaintext
        with open(tmp_path) as fp:
            raw = json.load(fp)
        raw_pw = raw["services"]["gmail"]["password"]
        assert raw_pw != "secret123", "Password stored in plaintext!"

        # List services
        services = store.list_services()
        assert len(services) == 1
        assert services[0]["service"] == "gmail"

        # Set another
        store.set("twitter", "clarvis", "tw_pass")
        assert len(store.list_services()) == 2

        # Remove
        assert store.remove("twitter") is True
        assert store.remove("nonexistent") is False
        assert len(store.list_services()) == 1

        # File permissions should be 0600
        mode = os.stat(tmp_path).st_mode & 0o777
        assert mode == 0o600, f"Expected 0600 permissions, got {oct(mode)}"

        print("  PASS: credential store")
    finally:
        os.unlink(tmp_path)


def test_task_result():
    """TaskResult should serialize and log correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import universal_web_agent as uwa
        orig_dir = uwa.RESULTS_DIR
        orig_log = uwa.TASK_LOG
        uwa.RESULTS_DIR = Path(tmpdir)
        uwa.TASK_LOG = Path(tmpdir) / "test_log.jsonl"

        try:
            result = TaskResult(
                task="Send email", service="gmail", status="success",
                result_text="Email sent", attempts=1, total_time_s=12.5,
                verification={"verified": True, "confidence": 0.8},
            )
            result.log()

            assert uwa.TASK_LOG.exists()
            line = uwa.TASK_LOG.read_text().strip()
            entry = json.loads(line)
            assert entry["task"] == "Send email"
            assert entry["status"] == "success"
            assert entry["service"] == "gmail"
            print("  PASS: task result logging")
        finally:
            uwa.RESULTS_DIR = orig_dir
            uwa.TASK_LOG = orig_log


def test_prompt_building():
    """WebAgentRunner should build prompts with credentials and retry context."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = f.name

    try:
        from pathlib import Path
        store = CredentialStore(path=Path(tmp_path))
        store.set("gmail", "test@gmail.com", "secret123",
                  login_url="https://accounts.google.com")
        runner = WebAgentRunner(cred_store=store)

        creds = store.get("gmail")
        prompt = runner._build_prompt("Send an email", "gmail", creds, attempt=0)
        assert "test@gmail.com" in prompt
        assert "secret123" in prompt
        assert "accounts.google.com" in prompt
        assert "Send an email" in prompt
        assert "retry" not in prompt.lower()

        # Retry prompt should mention retry
        retry_prompt = runner._build_prompt("Send an email", "gmail", creds, attempt=1)
        assert "retry" in retry_prompt.lower()
        assert "attempt 2" in retry_prompt.lower()

        # No creds prompt
        generic_prompt = runner._build_prompt("Search for python", "generic", None)
        assert "Username" not in generic_prompt
        assert "Search for python" in generic_prompt

        print("  PASS: prompt building")
    finally:
        os.unlink(tmp_path)


def test_verification_patterns():
    """Verification patterns should exist for known services."""
    assert "gmail" in VERIFICATION_PATTERNS
    assert "twitter" in VERIFICATION_PATTERNS
    assert "generic" in VERIFICATION_PATTERNS
    for service, patterns in VERIFICATION_PATTERNS.items():
        assert "success_indicators" in patterns
        assert "failure_indicators" in patterns
        assert isinstance(patterns["success_indicators"], list)
    print("  PASS: verification patterns")


from pathlib import Path

if __name__ == "__main__":
    print("Running universal_web_agent smoke tests...")
    test_obfuscation_roundtrip()
    test_credential_store()
    test_task_result()
    test_prompt_building()
    test_verification_patterns()
    print("\nAll tests passed!")
