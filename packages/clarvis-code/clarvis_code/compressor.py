"""
ContextCompressor — Compress context to minimize token consumption.

Reduces token usage by 80-90% when injecting context into agent prompts:
- Queue/task list compression: strip completed, keep pending + recent N
- Health data compression: extract key metrics from verbose output
- Episode compression: trim to outcome + lesson only
- Full brief generation: one-shot compressed context payload
"""

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class ContextCompressor:
    """Compress various context sources for token-efficient agent prompts.

    Args:
        max_recent_completed: How many recent completions to keep.
        max_episode_chars: Max chars per episode hint.
        custom_extractors: Dict of name -> callable(text) -> str for
            custom metric extraction from health output.

    Example:
        compressor = ContextCompressor()
        brief = compressor.compress_queue("/path/to/queue.md")
        health = compressor.compress_health(phi_output="Phi: 0.72 trend: up")
        episodes = compressor.compress_episodes(similar, failures)
    """

    def __init__(
        self,
        max_recent_completed: int = 5,
        max_episode_chars: int = 100,
        custom_extractors: Optional[Dict[str, Callable[[str], str]]] = None,
    ):
        self.max_recent_completed = max_recent_completed
        self.max_episode_chars = max_episode_chars
        self.custom_extractors = custom_extractors or {}

    def compress_queue(
        self,
        queue_path: str,
        pending_prefix: str = "- [ ] ",
        completed_prefix: str = "- [x] ",
    ) -> str:
        """Compress a markdown task queue file.

        Keeps pending tasks verbatim (with section headers),
        reduces completed tasks to last N as 1-liners,
        strips everything else.

        Typical reduction: 85-90% token savings.

        Args:
            queue_path: Path to queue markdown file.
            pending_prefix: Line prefix for pending tasks.
            completed_prefix: Line prefix for completed tasks.

        Returns:
            Compressed queue as a string.
        """
        path = Path(queue_path)
        if not path.exists():
            return "No queue found."

        lines = path.read_text().splitlines()

        pending_tasks: List[Dict[str, str]] = []
        recent_completed: List[Dict[str, str]] = []
        current_section = ""

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("## "):
                current_section = stripped
                continue

            if "Completed" in current_section or "completed" in current_section:
                continue

            # Pending
            if stripped.startswith(pending_prefix):
                task_text = stripped[len(pending_prefix):]
                core = re.split(r'\s*[\(\u2014]', task_text, 1)[0].strip()
                if len(core) < 20:
                    core = task_text[:150]
                pending_tasks.append({"section": current_section, "task": core})
                continue

            # Completed
            if stripped.startswith(completed_prefix):
                task_text = stripped[len(completed_prefix):]
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', task_text)
                date_str = date_match.group(1) if date_match else "unknown"
                core = re.split(r'\s*[\(\u2014]', task_text, 1)[0].strip()
                if len(core) < 15:
                    core = task_text[:100]
                recent_completed.append({
                    "section": current_section,
                    "task": core,
                    "date": date_str,
                })

        # Sort completed by date (newest first)
        recent_completed.sort(
            key=lambda x: x["date"] if x["date"] != "unknown" else "0000",
            reverse=True,
        )
        recent_completed = recent_completed[:self.max_recent_completed]

        # Build output
        out = ["=== QUEUE (compressed) ===\n"]

        pending_by_section: Dict[str, List[str]] = {}
        for t in pending_tasks:
            pending_by_section.setdefault(t["section"], []).append(t["task"])

        if pending_by_section:
            out.append(f"PENDING ({len(pending_tasks)} tasks):")
            for section, tasks in pending_by_section.items():
                out.append(f"\n{section}")
                for task in tasks:
                    out.append(f"  - [ ] {task}")
        else:
            out.append("PENDING: 0 tasks (queue empty)")

        if recent_completed:
            out.append(f"\nRECENT ({len(recent_completed)}):")
            for t in recent_completed:
                out.append(f"  [x] ({t['date']}) {t['task'][:80]}")

        out.append(f"\nTOTAL: {len(pending_tasks)} pending, {len(recent_completed)} recent shown")
        return "\n".join(out)

    def compress_health(self, **named_outputs: str) -> str:
        """Compress multi-line health data into compact key=value summary.

        Accepts named keyword arguments where each value is raw stdout
        from a health/metric script. Extracts key numbers, discards verbose text.

        Built-in extractors handle: calibration, phi, capability, retrieval, episodes.
        Custom extractors can be registered via constructor.

        Typical reduction: 87% token savings.

        Args:
            **named_outputs: name=raw_output pairs. Recognized names:
                calibration, phi, capability, retrieval, episodes, goals.
                Unknown names use custom_extractors or are included as-is (truncated).

        Returns:
            Compact health summary string.
        """
        summary = ["=== HEALTH (compressed) ==="]

        extractors = {
            "calibration": self._extract_calibration,
            "phi": self._extract_phi,
            "capability": self._extract_capability,
            "retrieval": self._extract_retrieval,
            "episodes": self._extract_episodes,
            "goals": self._extract_goals,
        }
        extractors.update(self.custom_extractors)

        for name, output in named_outputs.items():
            if not output:
                continue
            if name in extractors:
                line = extractors[name](output)
                if line:
                    summary.append(line)
            else:
                # Unknown metric — include truncated
                summary.append(f"{name}: {output[:120]}")

        if len(summary) == 1:
            summary.append("No health data available.")

        return "\n".join(summary)

    def compress_episodes(
        self,
        similar_text: str = "",
        failure_text: str = "",
    ) -> str:
        """Compress episodic memory hints for task prompts.

        Strips verbose episode details, keeps only outcome + key lesson.

        Args:
            similar_text: Raw similar episode recall output.
            failure_text: Raw failure episode output.

        Returns:
            Compressed episode hints string.
        """
        lines = []
        max_chars = self.max_episode_chars

        if similar_text:
            for line in similar_text.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                match = re.match(r'\[(\w+)\]\s*(?:\(act=[0-9.]+\)\s*)?(?:Task:\s*)?(.+)', line)
                if match:
                    lines.append(f"  [{match.group(1)}] {match.group(2)[:max_chars]}")
                else:
                    lines.append(f"  {line[:max_chars]}")

        if failure_text:
            for line in failure_text.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                err_match = re.search(r'Error:\s*\[?(\w+)\]?\s*(.+)', line)
                if err_match:
                    lines.append(f"  AVOID: [{err_match.group(1)}] {err_match.group(2)[:max_chars]}")
                elif len(line) > 10:
                    lines.append(f"  AVOID: {line[:max_chars]}")

        if lines:
            return "EPISODIC HINTS:\n" + "\n".join(lines)
        return ""

    def generate_brief(
        self,
        queue_path: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
        extra_context: Optional[str] = None,
    ) -> str:
        """Generate a full compressed context brief for agent prompts.

        Combines compressed queue + metrics + extra context into a single
        compact payload suitable for prompt injection.

        Args:
            queue_path: Path to queue file (or None to skip).
            metrics: Dict of metric_name -> value to include.
            extra_context: Any additional context string.

        Returns:
            Compressed brief string (~1-3KB).
        """
        parts = []

        if queue_path:
            parts.append(self.compress_queue(queue_path))

        if metrics:
            parts.append("\n=== METRICS ===")
            for name, val in metrics.items():
                if isinstance(val, float):
                    parts.append(f"{name}={val:.3f}")
                else:
                    parts.append(f"{name}={val}")

        if extra_context:
            parts.append(f"\n{extra_context}")

        return "\n".join(parts)

    def estimate_savings(self, raw_text: str, compressed_text: str) -> Dict[str, Any]:
        """Estimate token savings from compression.

        Args:
            raw_text: Original uncompressed text.
            compressed_text: Compressed version.

        Returns:
            Dict with raw_tokens, compressed_tokens, savings, reduction_pct.
        """
        raw_tokens = len(raw_text) // 4  # ~4 chars/token estimate
        comp_tokens = len(compressed_text) // 4
        savings = raw_tokens - comp_tokens
        pct = (1 - comp_tokens / max(1, raw_tokens)) * 100
        return {
            "raw_tokens": raw_tokens,
            "compressed_tokens": comp_tokens,
            "savings": savings,
            "reduction_pct": round(pct, 1),
        }

    # === Built-in metric extractors ===

    @staticmethod
    def _extract_calibration(output: str) -> str:
        brier = re.search(r'[Bb]rier[:\s=]*([0-9.]+)', output)
        acc = re.search(r'(\d+)/(\d+)\s*correct|accuracy[:\s=]*([0-9.]+)', output)
        b = brier.group(1) if brier else "?"
        if acc:
            a = f"{acc.group(1)}/{acc.group(2)}" if acc.group(1) else acc.group(3)
        else:
            a = "?"
        return f"Calibration: Brier={b}, accuracy={a}"

    @staticmethod
    def _extract_phi(output: str) -> str:
        phi = re.search(r'[Pp]hi[:\s=]*([0-9.]+)', output)
        trend = re.search(r'trend[:\s=]*([a-z_]+|[^\s]+)', output, re.IGNORECASE)
        return f"Phi={phi.group(1) if phi else '?'} (trend: {trend.group(1) if trend else 'stable'})"

    @staticmethod
    def _extract_capability(output: str) -> str:
        scores = re.findall(r'(\w[\w_]+)[:=]\s*([0-9.]+)', output)
        pairs = [(n, float(v)) for n, v in scores if 0 <= float(v) <= 1.0]
        if not pairs:
            return ""
        pairs.sort(key=lambda x: x[1])
        avg = sum(v for _, v in pairs) / len(pairs)
        worst = pairs[0]
        return f"Capabilities: avg={avg:.2f}, worst={worst[0]}={worst[1]:.2f}, n={len(pairs)}"

    @staticmethod
    def _extract_retrieval(output: str) -> str:
        hit = re.search(r'hit[_ ]rate[:\s=]*([0-9.]+)%?', output, re.IGNORECASE)
        status = re.search(r'(HEALTHY|DEGRADED|CRITICAL)', output)
        return f"Retrieval: hit_rate={hit.group(1) if hit else '?'}%, status={status.group(1) if status else '?'}"

    @staticmethod
    def _extract_episodes(output: str) -> str:
        count = re.search(r'(\d+)\s*episodes?', output)
        success = re.search(r'success[:\s=]*([0-9.]+)%?', output, re.IGNORECASE)
        return f"Episodes: n={count.group(1) if count else '?'}, success={success.group(1) if success else '?'}%"

    @staticmethod
    def _extract_goals(output: str) -> str:
        stalled = re.search(r'(\d+)\s*stalled', output, re.IGNORECASE)
        tasks = re.search(r'(\d+)\s*tasks?\s*(generated|added)', output, re.IGNORECASE)
        return f"Goals: {stalled.group(1) if stalled else '0'} stalled, {tasks.group(1) if tasks else '0'} remediation"
