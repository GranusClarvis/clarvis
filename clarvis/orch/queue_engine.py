"""Backward-compatibility shim — queue_engine moved to clarvis.queue.engine (2026-04-04).

All public API is re-exported from the canonical location.
New code should use: from clarvis.queue.engine import QueueEngine, engine, parse_queue
"""

from clarvis.queue.engine import (  # noqa: F401
    QueueEngine,
    engine,
    parse_queue,
    _extract_tag,
    _now_iso,
    _default_entry,
    _load_sidecar,
    _save_sidecar,
    _append_run,
    _load_runs,
    _update_run,
    _parse_ts,
    _lookup_run_tag,
    QUEUE_FILE,
    SIDECAR_FILE,
    RUNS_FILE,
    MAX_RETRIES,
    DEFAULT_MAX_RETRIES,
    BACKOFF_CAP,
    STUCK_RUNNING_HOURS,
)
