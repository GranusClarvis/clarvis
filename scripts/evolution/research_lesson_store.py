#!/usr/bin/env python3
"""
research_lesson_store.py — Cross-run research lesson tracking.

Inspired by AutoResearchClaw's MetaClaw bridge pattern: captures what research
topics led to actionable outcomes vs. dead ends, and injects this history into
future research prompts so the system learns from past sessions.

Usage:
    from research_lesson_store import ResearchLessonStore
    store = ResearchLessonStore()
    store.record(topic="GWT architectures", decision="APPLY",
                 findings="...", queue_items=["Implement GWT broadcast"], outcome="pending")
    lessons = store.get_recent_lessons(n=5)

CLI:
    python3 research_lesson_store.py record --topic "..." --decision APPLY --findings "..." [--queue-items "item1;item2"]
    python3 research_lesson_store.py inject           # Print lesson context for prompt injection
    python3 research_lesson_store.py stats             # Success rates, patterns
    python3 research_lesson_store.py update-outcome --topic "..." --outcome success|failure|stale
"""

import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
STORE_PATH = os.path.join(WORKSPACE, "data", "research_lessons.jsonl")

VALID_DECISIONS = {"APPLY", "ARCHIVE", "DISCARD"}
VALID_OUTCOMES = {"pending", "success", "failure", "stale"}


@dataclass
class ResearchLesson:
    topic: str
    decision: str  # APPLY, ARCHIVE, DISCARD
    findings_summary: str
    queue_items: list[str] = field(default_factory=list)
    outcome: str = "pending"  # pending, success, failure, stale
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


class ResearchLessonStore:
    """JSONL-backed store for research session outcomes."""

    def __init__(self, path: str = STORE_PATH):
        self._path = path
        os.makedirs(os.path.dirname(self._path), exist_ok=True)

    def record(self, topic: str, decision: str, findings: str,
               queue_items: Optional[list[str]] = None, outcome: str = "pending") -> ResearchLesson:
        decision = decision.upper()
        if decision not in VALID_DECISIONS:
            raise ValueError(f"Invalid decision: {decision}. Must be one of {VALID_DECISIONS}")
        if outcome not in VALID_OUTCOMES:
            raise ValueError(f"Invalid outcome: {outcome}. Must be one of {VALID_OUTCOMES}")

        lesson = ResearchLesson(
            topic=topic,
            decision=decision,
            findings_summary=findings[:500],
            queue_items=queue_items or [],
            outcome=outcome,
        )
        with open(self._path, "a") as f:
            f.write(json.dumps(asdict(lesson), ensure_ascii=False) + "\n")
        return lesson

    def load_all(self) -> list[ResearchLesson]:
        if not os.path.exists(self._path):
            return []
        lessons = []
        for line in open(self._path):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                lessons.append(ResearchLesson(**data))
            except (json.JSONDecodeError, TypeError):
                continue
        return lessons

    def update_outcome(self, topic: str, outcome: str) -> bool:
        """Update the outcome of the most recent lesson matching topic."""
        if outcome not in VALID_OUTCOMES:
            raise ValueError(f"Invalid outcome: {outcome}")
        lessons = self.load_all()
        updated = False
        for lesson in reversed(lessons):
            if topic.lower() in lesson.topic.lower():
                lesson.outcome = outcome
                updated = True
                break
        if updated:
            self._rewrite(lessons)
        return updated

    def get_recent_lessons(self, n: int = 5) -> list[ResearchLesson]:
        lessons = self.load_all()
        return lessons[-n:]

    def inject_prompt_context(self) -> str:
        """Format recent lessons for injection into research prompts."""
        lessons = self.load_all()
        if not lessons:
            return ""

        # Group by decision and outcome for concise summary
        applied = [l for l in lessons if l.decision == "APPLY"]
        successful = [l for l in applied if l.outcome == "success"]
        failed = [l for l in applied if l.outcome == "failure"]
        discarded = [l for l in lessons if l.decision == "DISCARD"]

        lines = ["PAST RESEARCH LESSONS (learn from these):"]

        if successful:
            lines.append(f"  Successful research→action ({len(successful)}):")
            for l in successful[-3:]:
                lines.append(f"    - {l.topic}: {l.findings_summary[:80]}")

        if failed:
            lines.append(f"  Failed/unhelpful research ({len(failed)}):")
            for l in failed[-3:]:
                lines.append(f"    - {l.topic}: {l.findings_summary[:80]} → AVOID similar")

        if discarded:
            lines.append(f"  Discarded topics ({len(discarded)}): {', '.join(l.topic[:30] for l in discarded[-3:])}")

        recent = lessons[-3:]
        lines.append("  Recent sessions:")
        for l in recent:
            items_str = f", queued {len(l.queue_items)} items" if l.queue_items else ""
            lines.append(f"    - [{l.decision}] {l.topic[:50]} → {l.outcome}{items_str}")

        return "\n".join(lines)

    def stats(self) -> dict:
        lessons = self.load_all()
        if not lessons:
            return {"total": 0}

        by_decision = {}
        by_outcome = {}
        for l in lessons:
            by_decision[l.decision] = by_decision.get(l.decision, 0) + 1
            by_outcome[l.outcome] = by_outcome.get(l.outcome, 0) + 1

        applied = [l for l in lessons if l.decision == "APPLY"]
        success_rate = 0.0
        if applied:
            resolved = [l for l in applied if l.outcome in ("success", "failure")]
            if resolved:
                success_rate = sum(1 for l in resolved if l.outcome == "success") / len(resolved)

        return {
            "total": len(lessons),
            "by_decision": by_decision,
            "by_outcome": by_outcome,
            "apply_success_rate": round(success_rate, 2),
            "total_queue_items": sum(len(l.queue_items) for l in lessons),
        }

    def _rewrite(self, lessons: list[ResearchLesson]):
        tmp = self._path + ".tmp"
        with open(tmp, "w") as f:
            for l in lessons:
                f.write(json.dumps(asdict(l), ensure_ascii=False) + "\n")
        os.replace(tmp, self._path)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Research lesson store")
    sub = parser.add_subparsers(dest="command")

    rec = sub.add_parser("record")
    rec.add_argument("--topic", required=True)
    rec.add_argument("--decision", required=True, choices=["APPLY", "ARCHIVE", "DISCARD"])
    rec.add_argument("--findings", required=True)
    rec.add_argument("--queue-items", default="", help="Semicolon-separated items")
    rec.add_argument("--outcome", default="pending", choices=list(VALID_OUTCOMES))

    inj = sub.add_parser("inject")

    st = sub.add_parser("stats")

    upd = sub.add_parser("update-outcome")
    upd.add_argument("--topic", required=True)
    upd.add_argument("--outcome", required=True, choices=list(VALID_OUTCOMES))

    args = parser.parse_args()
    store = ResearchLessonStore()

    if args.command == "record":
        items = [i.strip() for i in args.queue_items.split(";") if i.strip()] if args.queue_items else []
        lesson = store.record(args.topic, args.decision, args.findings, items, args.outcome)
        print(f"Recorded: [{lesson.decision}] {lesson.topic}")

    elif args.command == "inject":
        text = store.inject_prompt_context()
        print(text if text else "(no lessons yet)")

    elif args.command == "stats":
        s = store.stats()
        print(json.dumps(s, indent=2))

    elif args.command == "update-outcome":
        ok = store.update_outcome(args.topic, args.outcome)
        print(f"Updated: {ok}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
