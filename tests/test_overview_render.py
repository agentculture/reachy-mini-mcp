"""``overview`` render branches: the "Installed" list and the JSON shape."""

from __future__ import annotations

import json

from reachy_mini_mcp.cli import main
from reachy_mini_mcp.cli._commands import overview


def _offline(monkeypatch):
    monkeypatch.setattr(overview, "daemon_status", lambda *a, **k: (False, "stubbed offline"))


def test_overview_lists_installed_clients(monkeypatch, capsys):
    _offline(monkeypatch)
    monkeypatch.setattr(overview._clients, "is_installed", lambda path, *, name: True)
    assert main(["overview"]) == 0
    out = capsys.readouterr().out
    assert "Installed   :" in out
    assert "- claude-code (project):" in out


def test_overview_json_output(monkeypatch, capsys):
    _offline(monkeypatch)
    assert main(["overview", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert set(data) == {
        "version",
        "server_name",
        "launch",
        "tools",
        "daemon",
        "installed_in",
    }
    assert data["daemon"]["reachable"] is False
