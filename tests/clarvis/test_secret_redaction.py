"""Tests for brain secret redaction hook."""

import pytest
from clarvis.brain.secret_redaction import redact_secrets, brain_pre_store_hook


class TestRedactSecrets:
    """Test the core redaction function."""

    def test_clean_text_passes_through(self):
        text = "This is a normal memory about code architecture."
        cleaned, matched = redact_secrets(text)
        assert cleaned == text
        assert matched == []

    def test_aws_access_key(self):
        text = "Found key AKIAIOSFODNN7EXAMPLE in config"
        cleaned, matched = redact_secrets(text)
        assert "AKIA" not in cleaned
        assert "[REDACTED:AWS_KEY]" in cleaned
        assert "aws_access_key" in matched

    def test_openai_key(self):
        text = "Using sk-abc123def456ghi789jkl012mno345 for API"
        cleaned, matched = redact_secrets(text)
        assert "sk-abc" not in cleaned
        assert "[REDACTED:API_KEY]" in cleaned
        assert "openai_key" in matched

    def test_openrouter_key(self):
        text = "Key is sk-or-v1-" + "a" * 64 + " in env"
        cleaned, matched = redact_secrets(text)
        assert "sk-or-v1" not in cleaned
        assert "openrouter_key" in matched

    def test_bearer_token(self):
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature"
        cleaned, matched = redact_secrets(text)
        assert "Bearer eyJ" not in cleaned
        assert "bearer_token" in matched

    def test_generic_api_key(self):
        text = "api_key = 'abcdefghijklmnopqrstuvwxyz123456'"
        cleaned, matched = redact_secrets(text)
        assert "abcdefg" not in cleaned
        assert "generic_api_key" in matched

    def test_private_key_block(self):
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA\n-----END RSA PRIVATE KEY-----"
        cleaned, matched = redact_secrets(text)
        assert "MIIEp" not in cleaned
        assert "private_key_block" in matched

    def test_github_token(self):
        text = "Using ghp_" + "A" * 36 + " for auth"
        cleaned, matched = redact_secrets(text)
        assert "ghp_" not in cleaned
        assert "github_token" in matched

    def test_telegram_bot_token(self):
        text = "Bot token: 123456789:ABCdefGhi-JKLmnoPQR_stuvwxyz1234567"
        cleaned, matched = redact_secrets(text)
        assert "123456789:ABC" not in cleaned
        assert "telegram_bot_token" in matched

    def test_multiple_secrets(self):
        text = "Key AKIAIOSFODNN7EXAMPLE and token Bearer eyJhbGciOiJIUzI1NiJ9.x.y"
        cleaned, matched = redact_secrets(text)
        assert len(matched) >= 2
        assert "AKIA" not in cleaned
        assert "Bearer eyJ" not in cleaned


class TestBrainPreStoreHook:
    """Test the hook interface."""

    def test_clean_text_no_mutation(self):
        ctx = {"text": "Normal memory about architecture", "importance": 0.8}
        result = brain_pre_store_hook(ctx)
        assert result["redacted"] is False
        assert ctx["text"] == "Normal memory about architecture"

    def test_secret_text_mutated(self):
        original = "Stored AKIAIOSFODNN7EXAMPLE in brain"
        ctx = {"text": original, "importance": 0.9}
        result = brain_pre_store_hook(ctx)
        assert result["redacted"] is True
        assert "AKIA" not in ctx["text"]
        assert "[REDACTED:AWS_KEY]" in ctx["text"]
        assert result["count"] >= 1

    def test_empty_text(self):
        ctx = {"text": "", "importance": 0.5}
        result = brain_pre_store_hook(ctx)
        assert result["redacted"] is False

    def test_missing_text(self):
        ctx = {"importance": 0.5}
        result = brain_pre_store_hook(ctx)
        assert result["redacted"] is False


class TestHookRegistration:
    """Test that the hook registers correctly."""

    def test_register_adds_to_registry(self):
        from clarvis.heartbeat.hooks import HookRegistry, HookPhase
        from clarvis.brain.secret_redaction import register

        reg = HookRegistry()
        register(reg)
        names = reg.hook_names(HookPhase.BRAIN_PRE_STORE)
        assert "secret_redaction" in names
        # Priority 5 means it should be first
        hooks = reg.hooks_for(HookPhase.BRAIN_PRE_STORE)
        assert hooks[0] == ("secret_redaction", 5)
