"""
SessionManager — Manage session lifecycle and state persistence.

Handles:
- Session open: restore state, set context, record session start
- Session close: save state, store learnings, record session end
- State persistence: JSON-backed session state file
- Learnings extraction: capture decisions and insights from session messages
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class SessionManager:
    """Manage session lifecycle for autonomous agent loops.

    Sessions represent a bounded period of agent activity (e.g., a daily cycle,
    a cron run, or a user interaction). The manager tracks session state,
    persists it across restarts, and extracts learnings for long-term memory.

    Args:
        data_dir: Directory for session state files (created if missing).
        on_open: Optional callback(session_state) fired on session open.
        on_close: Optional callback(session_state) fired on session close.
        on_learning: Optional callback(learning_type, items) for extracted learnings.

    Example:
        session = SessionManager("/path/to/data")
        state = session.open("day-2026-02-23")

        # ... agent does work ...

        session.close(learnings=["Learned that JWT refresh needs 5min buffer"])
    """

    def __init__(
        self,
        data_dir: str = "./data",
        on_open: Optional[Callable] = None,
        on_close: Optional[Callable] = None,
        on_learning: Optional[Callable] = None,
    ):
        self.data_dir = Path(data_dir)
        self.state_file = self.data_dir / "session_state.json"
        self.on_open = on_open
        self.on_close = on_close
        self.on_learning = on_learning
        self._state: Dict[str, Any] = {}

    def open(self, session_key: Optional[str] = None) -> Dict[str, Any]:
        """Open a new session.

        Loads prior state if it exists, records session start time,
        and fires the on_open callback.

        Args:
            session_key: Session identifier (default: day-YYYY-MM-DD).

        Returns:
            Session state dict.
        """
        now = datetime.now(timezone.utc)
        session_key = session_key or now.strftime("session-%Y-%m-%d-%H%M")

        # Load prior state if exists
        prior = self._load_state()

        self._state = {
            "session_key": session_key,
            "opened_at": now.isoformat(),
            "prior_session": prior.get("session_key"),
            "prior_closed_at": prior.get("closed_at"),
            "learnings_count": 0,
        }

        self._save_state()

        if self.on_open:
            try:
                self.on_open(self._state)
            except Exception:
                pass

        return self._state

    def close(
        self,
        learnings: Optional[List[str]] = None,
        messages: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Close the current session.

        Saves final state, extracts learnings from messages if provided,
        and fires on_close and on_learning callbacks.

        Args:
            learnings: Explicit list of learning strings to store.
            messages: Optional conversation messages to extract learnings from.
                Each message should have a 'content' key.

        Returns:
            Final session state dict.
        """
        now = datetime.now(timezone.utc)

        # Ensure we have a state (may have been loaded from disk)
        if not self._state:
            self._state = self._load_state()
        if not self._state.get("session_key"):
            self._state["session_key"] = now.strftime("session-%Y-%m-%d-%H%M")
            self._state["opened_at"] = now.isoformat()

        self._state["closed_at"] = now.isoformat()

        # Calculate duration
        opened = self._state.get("opened_at", "")
        if opened:
            try:
                open_dt = datetime.fromisoformat(opened)
                duration_s = (now - open_dt).total_seconds()
                self._state["duration_s"] = round(duration_s)
            except ValueError:
                pass

        # Extract learnings from messages
        all_learnings = list(learnings or [])
        if messages:
            extracted = self._extract_learnings(messages)
            all_learnings.extend(extracted.get("decisions", []))
            all_learnings.extend(extracted.get("insights", []))

        self._state["learnings_count"] = len(all_learnings)
        self._state["learnings"] = all_learnings[:20]  # Cap at 20

        self._save_state()

        # Fire callbacks
        if all_learnings and self.on_learning:
            try:
                self.on_learning("session_close", all_learnings)
            except Exception:
                pass

        if self.on_close:
            try:
                self.on_close(self._state)
            except Exception:
                pass

        return self._state

    @property
    def state(self) -> Dict[str, Any]:
        """Current session state."""
        if not self._state:
            self._state = self._load_state()
        return self._state

    @property
    def is_open(self) -> bool:
        """Whether a session is currently open (opened but not closed)."""
        s = self.state
        return bool(s.get("opened_at")) and not s.get("closed_at")

    def _load_state(self) -> Dict[str, Any]:
        """Load session state from disk."""
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_state(self):
        """Save session state to disk."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self._state, indent=2))

    @staticmethod
    def _extract_learnings(messages: List[Dict[str, str]]) -> Dict[str, List[str]]:
        """Extract decisions and insights from conversation messages.

        Scans message content for decision and insight markers.

        Args:
            messages: List of dicts with 'content' key.

        Returns:
            Dict with 'decisions' and 'insights' lists.
        """
        decisions = []
        insights = []

        decision_markers = ["decided", "agreed", "will do", "priority", "chose", "selected"]
        insight_markers = ["insight", "realized", "learned", "found", "discovered", "understood"]

        for msg in messages:
            content = msg.get("content", "")
            content_lower = content.lower()

            if any(m in content_lower for m in decision_markers):
                decisions.append(content[:150])
            if any(m in content_lower for m in insight_markers):
                insights.append(content[:150])

        return {"decisions": decisions[:5], "insights": insights[:5]}
