"""``serve`` lazily imports the robot stack — cover both the missing-stack
error path and the success path without needing the real server installed."""

from __future__ import annotations

import argparse
import sys
import types
from unittest import mock

from reachy_mini_mcp.cli import main
from reachy_mini_mcp.cli._commands import serve
from reachy_mini_mcp.cli._errors import EXIT_ENV_ERROR


def _fake_server_module(name: str) -> types.ModuleType:
    mod = types.ModuleType(name)
    mod.main = mock.Mock(name=f"{name}.main")
    return mod


def test_serve_import_error_raises_env_error(monkeypatch, capsys):
    # A None entry in sys.modules makes `from reachy_mini_mcp.server import main`
    # raise ImportError — the same outcome as the [server] extra being absent.
    monkeypatch.setitem(sys.modules, "reachy_mini_mcp.server", None)
    assert main(["serve"]) == EXIT_ENV_ERROR
    err = capsys.readouterr().err
    assert "the server stack is not installed" in err
    assert "reachy-mini-mcp[server]" in err


def test_serve_openai_import_error_raises_env_error(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "reachy_mini_mcp.server_openai", None)
    assert main(["serve", "--openai"]) == EXIT_ENV_ERROR
    assert "the server stack is not installed" in capsys.readouterr().err


def test_serve_success_path_invokes_server_main(monkeypatch):
    fake = _fake_server_module("reachy_mini_mcp.server")
    monkeypatch.setitem(sys.modules, "reachy_mini_mcp.server", fake)
    assert serve._handle(argparse.Namespace(openai=False)) == 0
    fake.main.assert_called_once_with()


def test_serve_openai_success_path_invokes_server_main(monkeypatch):
    fake = _fake_server_module("reachy_mini_mcp.server_openai")
    monkeypatch.setitem(sys.modules, "reachy_mini_mcp.server_openai", fake)
    assert serve._handle(argparse.Namespace(openai=True)) == 0
    fake.main.assert_called_once_with()
