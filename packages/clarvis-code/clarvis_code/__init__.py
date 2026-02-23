"""
ClarvisCode — Smart task routing and context compression for Claude Code / OpenCode.

A standalone package for autonomous AI agent orchestration:
- TaskRouter: Classify task complexity and route to cheapest capable executor
- ContextCompressor: Compress context to minimize token consumption
- PromptBuilder: Build structured prompts with episodic/procedural hints
- SessionManager: Manage session lifecycle and state persistence

Usage:
    from clarvis_code import TaskRouter, ContextCompressor, PromptBuilder, SessionManager

    router = TaskRouter()
    result = router.classify("Build a new REST API endpoint")
    # -> {"tier": "complex", "executor": "claude", "score": 0.72, ...}

    compressor = ContextCompressor()
    brief = compressor.compress_queue("path/to/queue.md")

    builder = PromptBuilder()
    prompt = builder.build("Fix the auth bug", context=brief, episodes=[...])

    session = SessionManager("/path/to/data")
    session.open()
    # ... do work ...
    session.close(learnings=["Fixed auth bug via token refresh"])
"""

from clarvis_code.router import TaskRouter
from clarvis_code.compressor import ContextCompressor
from clarvis_code.prompt_builder import PromptBuilder
from clarvis_code.session import SessionManager

__version__ = "1.0.0"
__all__ = ["TaskRouter", "ContextCompressor", "PromptBuilder", "SessionManager"]
