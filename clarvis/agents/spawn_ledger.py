"""Deferred-spawn ledger.

When `spawn_claude.sh` cannot start Claude immediately (global lock held),
it persists the full task + flags to a JSON ledger entry under
`data/deferred_spawns/`. A respawn script (`respawn_deferred.sh`) and the
post-run worker EXIT trap drain this directory, re-invoking spawn_claude.sh
once the lock is free.

Why a ledger rather than just a queue task?

- The QUEUE.md "Deferred spawn_claude:" entries truncated the task text to
  120 chars, so the full operator instruction was lost.
- They also lacked a `[TAG]` so the queue engine couldn't track them.
- No scheduler ever picked them up — they were inert breadcrumbs.

The ledger gives us:
- Full preservation of the task text + every flag the operator passed.
- Atomic claim via filesystem rename (no DB, no daemon).
- A predictable retry budget per ledger entry.
- An age-based expiration so entries don't pile up forever.

All paths are best-effort: failures here must not break the spawn pipeline.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
LEDGER_DIR = WORKSPACE / "data" / "deferred_spawns"
LEDGER_LOG = WORKSPACE / "memory" / "cron" / "respawn_deferred.log"

# Cap retries to bound work — escalation happens via Telegram alert past this.
MAX_ATTEMPTS = 5
# Drop ledger entries older than this even if attempts < MAX_ATTEMPTS.
# Most legit spawns finish under 30 minutes, so 24h is generous.
EXPIRY_SECONDS = 24 * 3600


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_epoch() -> float:
    return time.time()


def _ensure_ledger_dir() -> None:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class DeferredSpawn:
    """One pending spawn that couldn't run when first requested."""

    id: str
    deferred_at: str
    task: str
    timeout: int = 1200
    category: str = ""
    send_tg: bool = True
    isolated: bool = False
    tg_topic: str = ""
    tg_chat_id: str = ""
    retry_max: int = 0
    deferred_reason: str = ""
    attempts: int = 0
    last_attempt_at: Optional[str] = None
    source: str = "spawn_claude_overlap_guard"
    extra_flags: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "DeferredSpawn":
        data = json.loads(raw)
        return cls(**data)

    def path(self) -> Path:
        return LEDGER_DIR / f"{self.id}.json"

    def write(self) -> Path:
        _ensure_ledger_dir()
        target = self.path()
        tmp = target.with_suffix(".tmp")
        tmp.write_text(self.to_json(), encoding="utf-8")
        os.replace(tmp, target)
        return target


_ID_RE = re.compile(r"^[0-9TZ\-]+-[a-f0-9]{6}\.json$")


def new_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{ts}-{secrets.token_hex(3)}"


def record_deferred(
    task: str,
    *,
    timeout: int = 1200,
    category: str = "",
    send_tg: bool = True,
    isolated: bool = False,
    tg_topic: str = "",
    tg_chat_id: str = "",
    retry_max: int = 0,
    reason: str = "",
    source: str = "spawn_claude_overlap_guard",
    extra_flags: Optional[list[str]] = None,
) -> Optional[Path]:
    """Persist a deferred spawn for later auto-respawn.

    Returns the path to the new ledger file, or None if persistence failed.
    Never raises — caller treats failure as a soft signal.
    """
    if not task or not task.strip():
        return None
    try:
        entry = DeferredSpawn(
            id=new_id(),
            deferred_at=_now_iso(),
            task=task,
            timeout=int(timeout),
            category=category or "",
            send_tg=bool(send_tg),
            isolated=bool(isolated),
            tg_topic=tg_topic or "",
            tg_chat_id=tg_chat_id or "",
            retry_max=int(retry_max or 0),
            deferred_reason=reason or "",
            source=source or "spawn_claude_overlap_guard",
            extra_flags=list(extra_flags or []),
        )
        return entry.write()
    except (OSError, ValueError):
        return None


def list_pending() -> list[DeferredSpawn]:
    """Return all unclaimed ledger entries (excluding `.processing-*` files)."""
    if not LEDGER_DIR.exists():
        return []
    entries: list[DeferredSpawn] = []
    for f in sorted(LEDGER_DIR.iterdir()):
        if f.suffix != ".json" or not _ID_RE.match(f.name):
            continue
        try:
            entry = DeferredSpawn.from_json(f.read_text(encoding="utf-8"))
            entries.append(entry)
        except (OSError, ValueError, json.JSONDecodeError):
            # Corrupt entry — skip but leave file for inspection.
            continue
    return entries


def claim(entry: DeferredSpawn, claimer_pid: int) -> Optional[Path]:
    """Atomically claim a ledger entry by renaming to `.processing-<pid>`.

    Returns the new path on success, or None if another claimer beat us
    (file disappeared) or the entry has already been claimed.
    """
    src = entry.path()
    dst = LEDGER_DIR / f"{entry.id}.processing-{claimer_pid}"
    try:
        os.rename(src, dst)
        return dst
    except OSError:
        return None


def release(claimed_path: Path, entry: DeferredSpawn, success: bool) -> None:
    """Release a claimed entry.

    On success, the entry is consumed and removed.
    On failure (couldn't even invoke spawn_claude), restore the entry so a
    later respawn pass can retry it. The retry counter is bumped.
    """
    try:
        if success:
            claimed_path.unlink(missing_ok=True)
            return
        # Restore — bump attempts and last_attempt_at so cap is enforced.
        entry.attempts += 1
        entry.last_attempt_at = _now_iso()
        if entry.attempts >= MAX_ATTEMPTS:
            # Too many failures — move to a `.dead` file for operator review.
            dead = LEDGER_DIR / f"{entry.id}.dead"
            dead.write_text(entry.to_json(), encoding="utf-8")
            claimed_path.unlink(missing_ok=True)
            return
        # Atomically rewrite the original ledger path with bumped state.
        target = entry.path()
        tmp = target.with_suffix(".tmp")
        tmp.write_text(entry.to_json(), encoding="utf-8")
        os.replace(tmp, target)
        claimed_path.unlink(missing_ok=True)
    except OSError:
        pass  # Best-effort.


def reap_expired() -> list[DeferredSpawn]:
    """Delete ledger entries older than EXPIRY_SECONDS. Returns the dropped list."""
    dropped: list[DeferredSpawn] = []
    now = _now_epoch()
    for entry in list_pending():
        try:
            deferred_dt = datetime.fromisoformat(entry.deferred_at.replace("Z", "+00:00"))
            age = now - deferred_dt.timestamp()
            if age > EXPIRY_SECONDS:
                p = entry.path()
                expired_target = LEDGER_DIR / f"{entry.id}.expired"
                try:
                    os.rename(p, expired_target)
                except OSError:
                    p.unlink(missing_ok=True)
                dropped.append(entry)
        except (ValueError, OSError):
            continue
    return dropped


def log(msg: str) -> None:
    """Append a one-line message to the respawn log. Best-effort."""
    try:
        LEDGER_LOG.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER_LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"[{_now_iso()}] {msg}\n")
    except OSError:
        pass


def iter_to_respawn() -> Iterator[DeferredSpawn]:
    """Yield ledger entries that are eligible to respawn right now.

    Skips entries that are already at their attempt cap (those become `.dead`
    on the next failed claim; `reap_expired()` is called separately).
    """
    for entry in list_pending():
        if entry.attempts >= MAX_ATTEMPTS:
            continue
        yield entry
