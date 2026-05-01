"""Tests for `scripts/cron/cron_schedule_audit.sh` permission/read-failure handling.

Regression guard for `[CRON_AUDIT_CRONTAB_PERMISSION_ERROR]`: an unreadable live
`crontab -l` (e.g. permission denied) must be an explicit audit failure (exit 2)
that logs the cause, not silently swallowed into a "clean / zero-drift" report.

Tests inject a fake `crontab` binary via the `CLARVIS_CRONTAB_CMD` env hook —
no system crontab is touched.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

import pytest

WORKSPACE = os.environ.get(
    "CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")
)
AUDIT_SCRIPT = Path(WORKSPACE) / "scripts" / "cron" / "cron_schedule_audit.sh"


def _make_fake_crontab(bindir: Path, *, stderr: str, exit_code: int) -> Path:
    bindir.mkdir(parents=True, exist_ok=True)
    fake = bindir / "crontab"
    quoted_stderr = shlex.quote(stderr)
    fake.write_text(
        "#!/bin/bash\n"
        f"printf '%s\\n' {quoted_stderr} >&2\n"
        f"exit {exit_code}\n"
    )
    fake.chmod(0o755)
    return fake


@pytest.fixture
def isolated_ws(tmp_path: Path) -> Path:
    """Minimal isolated workspace mirroring `scripts/cron/` so the audit script
    can source `cron_env.sh` and write to `monitoring/cron_drift.log` without
    touching the real workspace."""
    ws = tmp_path / "workspace"
    (ws / "monitoring").mkdir(parents=True)
    (ws / "scripts" / "cron").mkdir(parents=True)
    real_cron = Path(WORKSPACE) / "scripts" / "cron"
    for f in real_cron.iterdir():
        if f.is_file():
            dest = ws / "scripts" / "cron" / f.name
            dest.write_bytes(f.read_bytes())
            dest.chmod(f.stat().st_mode)
    return ws


def _run_audit(
    ws: Path, env_overrides: dict, timeout: int = 30
) -> subprocess.CompletedProcess:
    env = {**os.environ, **env_overrides}
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)
    env["CLARVIS_WORKSPACE"] = str(ws)
    return subprocess.run(
        ["bash", str(ws / "scripts" / "cron" / "cron_schedule_audit.sh")],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


class TestCrontabPermissionDenied:
    def test_permission_denied_exits_two(self, tmp_path, isolated_ws):
        """A `crontab -l` permission-denied failure exits 2 (audit error), not 0."""
        fake = _make_fake_crontab(
            tmp_path / "fakebin",
            stderr="crontab: cannot read /var/spool/cron/crontabs: Permission denied",
            exit_code=1,
        )
        rc = _run_audit(isolated_ws, {"CLARVIS_CRONTAB_CMD": str(fake)})
        assert rc.returncode == 2, (
            f"Expected exit 2 (audit error), got {rc.returncode}.\n"
            f"stdout:\n{rc.stdout}\nstderr:\n{rc.stderr}"
        )

    def test_permission_denied_logs_reason(self, tmp_path, isolated_ws):
        """The drift log records WHY the audit was aborted (no silent failure)."""
        fake = _make_fake_crontab(
            tmp_path / "fakebin",
            stderr="crontab: cannot read /var/spool/cron/crontabs: Permission denied",
            exit_code=1,
        )
        _run_audit(isolated_ws, {"CLARVIS_CRONTAB_CMD": str(fake)})
        log_path = isolated_ws / "monitoring" / "cron_drift.log"
        assert log_path.exists(), "drift log must be written even on audit error"
        content = log_path.read_text()
        assert "ERROR" in content, f"Expected ERROR line in log:\n{content}"
        assert "Permission denied" in content, (
            f"Expected stderr cause in log:\n{content}"
        )
        assert "ABORTED" in content, f"Expected explicit abort marker:\n{content}"
        # Critical: an unreadable crontab must NEVER yield a zero-drift report.
        assert "Audit clean" not in content
        assert "zero drift" not in content

    def test_no_crontab_for_user_is_benign(self, tmp_path, isolated_ws):
        """`no crontab for <user>` is a valid empty schedule, not a permission error."""
        fake = _make_fake_crontab(
            tmp_path / "fakebin",
            stderr="no crontab for agent",
            exit_code=1,
        )
        rc = _run_audit(isolated_ws, {"CLARVIS_CRONTAB_CMD": str(fake)})
        assert rc.returncode != 2, (
            f"'no crontab for user' should be benign, got exit 2 (audit error).\n"
            f"stdout:\n{rc.stdout}\nstderr:\n{rc.stderr}"
        )

    def test_override_file_bypasses_live_failure(self, tmp_path, isolated_ws):
        """`CRON_AUDIT_CRONTAB_FILE` short-circuits before `crontab` is invoked."""
        fixture = tmp_path / "fixture.crontab"
        fixture.write_text("*/15 * * * * /bin/health_monitor.sh\n")
        fake = _make_fake_crontab(
            tmp_path / "fakebin",
            stderr="crontab: cannot read /var/spool/cron/crontabs: Permission denied",
            exit_code=1,
        )
        rc = _run_audit(
            isolated_ws,
            {
                "CRON_AUDIT_CRONTAB_FILE": str(fixture),
                "CLARVIS_CRONTAB_CMD": str(fake),
            },
        )
        assert rc.returncode != 2, (
            f"Override should bypass live crontab failure, got exit 2.\n"
            f"stdout:\n{rc.stdout}\nstderr:\n{rc.stderr}"
        )
