"""
PromptBuilder — Build structured prompts for Claude Code / OpenCode execution.

Constructs token-efficient prompts with:
- Task description
- Procedural memory hints (prior steps that worked)
- Episodic hints (similar past outcomes)
- Compressed context
- Configurable system preamble and suffix
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PromptConfig:
    """Configuration for prompt generation."""
    preamble: str = "You are an autonomous executive function. Execute this task:"
    suffix: str = "Do the work. Be concrete. Write code if needed. Test it.\nWhen done, output a 1-line summary of what you accomplished."
    max_context_chars: int = 4000
    max_episode_chars: int = 1000
    max_procedure_chars: int = 800
    include_escalation_instruction: bool = False
    escalation_marker: str = "NEEDS_AGENT: true"


class PromptBuilder:
    """Build structured prompts for agent execution.

    Assembles task prompts with optional procedural memory,
    episodic hints, and compressed context. Designed for
    both lightweight (Gemini, local) and full (Claude Code) executors.

    Args:
        config: PromptConfig with preamble, suffix, and limits.

    Example:
        builder = PromptBuilder()

        # Full prompt for Claude Code
        prompt = builder.build(
            task="Fix the authentication timeout bug",
            context="Current auth module uses JWT with 1h expiry...",
            episodes=[{"outcome": "success", "task": "Fixed token refresh"}],
            procedure={"steps": ["Check token expiry", "Add refresh logic"]},
        )

        # Lightweight prompt with escalation instruction
        config = PromptConfig(include_escalation_instruction=True)
        builder = PromptBuilder(config)
        prompt = builder.build_lightweight("Check queue status")
    """

    def __init__(self, config: Optional[PromptConfig] = None):
        self.config = config or PromptConfig()

    def build(
        self,
        task: str,
        context: str = "",
        episodes: Optional[List[Dict[str, Any]]] = None,
        procedure: Optional[Dict[str, Any]] = None,
        extra_instructions: str = "",
    ) -> str:
        """Build a full prompt for agent execution.

        Args:
            task: The task description.
            context: Compressed context (from ContextCompressor).
            episodes: List of episode dicts with at minimum 'outcome' and 'task' keys.
            procedure: Procedure dict with 'steps' list and optional 'success_rate'.
            extra_instructions: Any additional instructions to append.

        Returns:
            Formatted prompt string.
        """
        parts = [self.config.preamble, "", f"TASK: {task}"]

        # Procedural memory
        if procedure and procedure.get("steps"):
            steps = procedure["steps"]
            rate = procedure.get("success_rate", "unknown")
            proc_text = f"\nPROCEDURAL MEMORY (success rate: {rate}). Suggested steps:"
            for i, step in enumerate(steps, 1):
                proc_text += f"\n  {i}. {step}"
            proc_text += "\nUse these as a starting guide, adapt as needed."
            parts.append(proc_text[:self.config.max_procedure_chars])

        # Episodic hints
        if episodes:
            ep_lines = ["\nEPISODIC HINTS:"]
            for ep in episodes[:5]:
                outcome = ep.get("outcome", "?")
                ep_task = ep.get("task", "")[:80]
                ep_lines.append(f"  [{outcome}] {ep_task}")
            ep_text = "\n".join(ep_lines)
            parts.append(ep_text[:self.config.max_episode_chars])

        # Context
        if context:
            parts.append(f"\nCONTEXT: {context[:self.config.max_context_chars]}")

        # Extra instructions
        if extra_instructions:
            parts.append(f"\n{extra_instructions}")

        # Suffix
        parts.append(f"\n{self.config.suffix}")

        return "\n".join(parts)

    def build_lightweight(self, task: str, context: str = "") -> str:
        """Build a lightweight prompt with optional escalation instruction.

        For use with cheap models (Gemini Flash, local LLMs) that should
        escalate to a full agent when the task requires file editing.

        Args:
            task: The task description.
            context: Optional compressed context.

        Returns:
            Formatted prompt string.
        """
        parts = [self.config.preamble, "", f"TASK: {task}"]

        if context:
            parts.append(f"\nCONTEXT: {context[:self.config.max_context_chars]}")

        if self.config.include_escalation_instruction:
            parts.append(
                f"\nIMPORTANT: You are running in lightweight mode (no file editing tools).\n"
                f"If this task requires writing or modifying code files, output exactly:\n"
                f"{self.config.escalation_marker}\n"
                f"and explain what needs to be done."
            )

        parts.append(f"\n{self.config.suffix}")

        return "\n".join(parts)

    def estimate_tokens(self, prompt: str) -> int:
        """Rough token estimate (~4 chars per token)."""
        return len(prompt) // 4
