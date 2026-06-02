"""Top-level dispatch: argparse errors, ReachyError, and last-resort wrapping
all route through the structured ``emit_error`` path with the right exit codes."""

from __future__ import annotations

import importlib
import subprocess
import sys

import pytest

from reachy_mini_mcp.cli import main
from reachy_mini_mcp.cli._commands import show
from reachy_mini_mcp.cli._errors import EXIT_USER_ERROR


def test_unknown_subcommand_routes_through_emit_error(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["bogus-subcommand"])
    assert exc.value.code == EXIT_USER_ERROR
    err = capsys.readouterr().err
    assert "error:" in err
    assert "hint:" in err


def test_unknown_flag_routes_through_emit_error(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["show", "--no-such-flag"])
    assert exc.value.code == EXIT_USER_ERROR
    assert "error:" in capsys.readouterr().err


def test_dispatch_catches_reachy_error(tmp_path, capsys):
    cfg = tmp_path / "mcp.json"
    cfg.write_text('{"mcpServers": {"reachy-mini": {"command": "old"}}}', encoding="utf-8")
    # A conflicting entry without --force makes merge_entry raise ReachyError,
    # which _dispatch must turn into exit code 1 (not a traceback).
    assert main(["install", "--path", str(cfg)]) == EXIT_USER_ERROR
    assert "already exists with different settings" in capsys.readouterr().err


def test_dispatch_wraps_unexpected_exception(monkeypatch, capsys):
    def boom(_args):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(show, "_handle", boom)
    assert main(["show"]) == EXIT_USER_ERROR
    err = capsys.readouterr().err
    assert "unexpected: RuntimeError" in err
    assert "file a bug" in err


def test_dispatch_keyboard_interrupt_returns_130(monkeypatch):
    def boom(_args):
        raise KeyboardInterrupt

    monkeypatch.setattr(show, "_handle", boom)
    assert main(["show"]) == 130


def test_main_module_imports_cleanly():
    # Importing the module (name != "__main__") runs its top-level imports under
    # coverage; the `sys.exit(main())` guard is excluded by coverage config.
    mod = importlib.import_module("reachy_mini_mcp.__main__")
    assert hasattr(mod, "main")


def test_python_m_entrypoint_runs():
    result = subprocess.run(
        [sys.executable, "-m", "reachy_mini_mcp", "show"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "mcpServers" in result.stdout
