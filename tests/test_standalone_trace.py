"""Tests for standalone_trace context manager — error-safe audit trace finalization."""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def isolate_traces(tmp_path, monkeypatch):
    """Redirect trace writes to a temp dir and clear ambient state."""
    monkeypatch.setattr("clarvis.audit.trace.TRACES_ROOT", tmp_path)
    monkeypatch.delenv("CLARVIS_AUDIT_TRACE_ID", raising=False)
    from clarvis.audit.trace import set_current_trace_id
    set_current_trace_id(None)
    yield tmp_path


def _read_trace(traces_root, tid):
    from clarvis.audit.trace import trace_path_for
    path = trace_path_for(tid, root=traces_root)
    with open(path) as f:
        return json.load(f)


class TestStandaloneTraceSuccess:
    def test_success_on_normal_exit(self, isolate_traces):
        from clarvis.audit.trace import standalone_trace

        with standalone_trace(source="test", task={"name": "t"}, cron_origin="test.py") as handle:
            assert handle.tid is not None
            tid = handle.tid

        data = _read_trace(isolate_traces, tid)
        assert data["outcome"]["status"] == "success"
        assert "duration_s" in data["outcome"]
        assert data["outcome"]["duration_s"] >= 0

    def test_no_trace_when_ambient_exists(self, isolate_traces):
        from clarvis.audit.trace import standalone_trace, set_current_trace_id
        set_current_trace_id("existing-trace-id")

        with standalone_trace(source="test", task={"name": "t"}) as handle:
            assert handle.tid is None


class TestStandaloneTraceError:
    def test_error_on_exception(self, isolate_traces):
        from clarvis.audit.trace import standalone_trace

        tid = None
        with pytest.raises(ValueError):
            with standalone_trace(source="test", task={"name": "t"}) as handle:
                tid = handle.tid
                raise ValueError("boom")

        assert tid is not None
        data = _read_trace(isolate_traces, tid)
        assert data["outcome"]["status"] == "error"
        assert data["outcome"]["duration_s"] >= 0

    def test_error_on_nonzero_sys_exit(self, isolate_traces):
        from clarvis.audit.trace import standalone_trace

        tid = None
        with pytest.raises(SystemExit):
            with standalone_trace(source="test", task={"name": "t"}) as handle:
                tid = handle.tid
                sys.exit(1)

        data = _read_trace(isolate_traces, tid)
        assert data["outcome"]["status"] == "error"

    def test_success_on_zero_sys_exit(self, isolate_traces):
        from clarvis.audit.trace import standalone_trace

        tid = None
        with pytest.raises(SystemExit):
            with standalone_trace(source="test", task={"name": "t"}) as handle:
                tid = handle.tid
                sys.exit(0)

        data = _read_trace(isolate_traces, tid)
        assert data["outcome"]["status"] == "success"


class TestStandaloneTraceEarlyFinalize:
    def test_early_finalize_skipped(self, isolate_traces):
        from clarvis.audit.trace import standalone_trace

        with standalone_trace(source="test", task={"name": "t"}) as handle:
            tid = handle.tid
            handle.finalize("skipped")

        data = _read_trace(isolate_traces, tid)
        assert data["outcome"]["status"] == "skipped"

    def test_early_finalize_prevents_double_write(self, isolate_traces):
        from clarvis.audit.trace import standalone_trace

        with standalone_trace(source="test", task={"name": "t"}) as handle:
            handle.finalize("skipped")
            assert handle.finalized is True
            result = handle.finalize("success")
            assert result is False


class TestTraceHandle:
    def test_handle_finalize_returns_false_when_no_tid(self):
        from clarvis.audit.trace import TraceHandle
        h = TraceHandle(None)
        assert h.finalize("success") is False
        assert h.finalized is False
