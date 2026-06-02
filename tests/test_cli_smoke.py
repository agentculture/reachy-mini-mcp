"""The manager CLI runs end-to-end without the robot stack installed."""

from __future__ import annotations

import sys

import pytest

from reachy_mini_mcp.cli import main


def _no_daemon(monkeypatch):
    """Make the daemon probe deterministic and offline for overview/doctor."""
    monkeypatch.setattr(
        "reachy_mini_mcp.cli._meta.daemon_status",
        lambda *a, **k: (False, "stubbed offline"),
    )


def test_version_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "reachy-mini-mcp" in capsys.readouterr().out


def test_show_returns_zero(capsys):
    assert main(["show"]) == 0
    assert '"mcpServers"' in capsys.readouterr().out


def test_explain_returns_zero(capsys):
    assert main(["explain"]) == 0
    assert "mcp.json" in capsys.readouterr().out.lower()


def test_overview_returns_zero(monkeypatch, capsys):
    _no_daemon(monkeypatch)
    assert main(["overview"]) == 0
    assert "reachy-mini-mcp" in capsys.readouterr().out


def test_no_args_runs_overview(monkeypatch, capsys):
    _no_daemon(monkeypatch)
    assert main([]) == 0
    assert "reachy-mini-mcp" in capsys.readouterr().out


def test_doctor_passes_hard_checks(monkeypatch):
    _no_daemon(monkeypatch)
    # server/tts extras may be absent in CI — that is a warning, not a failure.
    assert main(["doctor"]) == 0


def test_install_uninstall_roundtrip(tmp_path, capsys):
    cfg = tmp_path / "mcp.json"
    assert main(["install", "--path", str(cfg)]) == 0
    assert cfg.exists()
    assert "reachy-mini" in cfg.read_text()
    assert main(["uninstall", "--path", str(cfg)]) == 0
    assert "reachy-mini" not in cfg.read_text()


def test_manager_does_not_import_robot_stack():
    # The dep-free guarantee: running a manager command must not pull in the
    # robot stack. Checked in a fresh subprocess — `doctor` (run by other tests
    # in this process) deliberately probes `import fastmcp`, which would pollute
    # this process's sys.modules.
    import subprocess

    code = (
        "import sys\n"
        "from reachy_mini_mcp.cli import main\n"
        "main(['show'])\n"
        "sys.exit(1 if 'fastmcp' in sys.modules else 0)\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, f"robot stack imported by `show`:\n{result.stderr}"
