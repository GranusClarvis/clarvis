"""Regression test: brain-attribution trace lookup must use trace_path_for(),
not datetime.now(UTC), so day-rollover between preflight and postflight
doesn't silently drop attribution rows."""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestTraceDayRollover:
    """Simulate a trace created at 23:59 UTC, with postflight running at 00:01 the next day."""

    def test_trace_path_for_extracts_date_from_id(self):
        from clarvis.audit.trace import trace_path_for

        tid = "20260419T235900Z-abc123"
        path = trace_path_for(tid, root=Path("/fake/traces"))
        assert path == Path("/fake/traces/2026-04-19") / f"{tid}.json"

    def test_trace_path_for_ignores_wall_clock(self):
        """Even when wall clock is April 20, a trace id from April 19 resolves to 2026-04-19."""
        from clarvis.audit.trace import trace_path_for

        tid = "20260419T235900Z-abc123"
        fake_now = datetime(2026, 4, 20, 0, 5, 0, tzinfo=timezone.utc)
        with mock.patch("clarvis.audit.trace.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            path = trace_path_for(tid, root=Path("/fake/traces"))
        assert "2026-04-19" in str(path), f"Expected 2026-04-19 in path, got {path}"

    def test_postflight_attribution_finds_trace_across_day_boundary(self):
        """End-to-end: trace created pre-midnight, attribution runs post-midnight."""
        from clarvis.audit.trace import trace_path_for

        pre_midnight_tid = "20260419T235500Z-f1a2b3"
        with tempfile.TemporaryDirectory() as tmpdir:
            traces_root = Path(tmpdir) / "data" / "audit" / "traces"

            trace_file = trace_path_for(pre_midnight_tid, root=traces_root)
            trace_file.parent.mkdir(parents=True, exist_ok=True)
            trace_data = {
                "audit_trace_id": pre_midnight_tid,
                "created_at": "2026-04-19T23:55:00Z",
                "source": "heartbeat",
                "preflight": {"brain_context": {"blocks": [{"text": "test", "collection": "clarvis-memories"}]}},
                "outcome": {"status": "success"},
            }
            trace_file.write_text(json.dumps(trace_data))

            resolved = str(trace_path_for(pre_midnight_tid, root=traces_root))
            assert os.path.isfile(resolved), (
                f"trace_path_for should resolve to the file at {resolved}"
            )

            wrong_path = traces_root / "2026-04-20" / f"{pre_midnight_tid}.json"
            assert not wrong_path.exists(), (
                "A next-day path must NOT exist — the old datetime.now bug would look here"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
