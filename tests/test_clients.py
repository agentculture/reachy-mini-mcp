"""Client-config merge/remove helpers: preserve siblings, stay idempotent."""

from __future__ import annotations

import sys

import pytest

from reachy_mini_mcp.cli import _clients
from reachy_mini_mcp.cli._errors import ReachyError

ENTRY = {"command": "reachy-mini-mcp", "args": ["serve"], "env": {"REACHY_BASE_URL": "x"}}
OTHER = {"command": "foo", "args": ["bar"]}


def test_merge_preserves_other_servers_and_keys():
    config = {"mcpServers": {"other": dict(OTHER)}, "topLevel": 1}
    changed = _clients.merge_entry(config, name="reachy-mini", entry=ENTRY)
    assert changed is True
    assert config["mcpServers"]["other"] == OTHER
    assert config["mcpServers"]["reachy-mini"] == ENTRY
    assert config["topLevel"] == 1


def test_merge_is_idempotent():
    config = {}
    assert _clients.merge_entry(config, name="reachy-mini", entry=ENTRY) is True
    assert _clients.merge_entry(config, name="reachy-mini", entry=ENTRY) is False


def test_merge_refuses_clobber_without_force():
    config = {"mcpServers": {"reachy-mini": dict(OTHER)}}
    with pytest.raises(ReachyError):
        _clients.merge_entry(config, name="reachy-mini", entry=ENTRY)
    # force overwrites
    assert _clients.merge_entry(config, name="reachy-mini", entry=ENTRY, force=True) is True


def test_remove_only_targets_named_entry():
    config = {"mcpServers": {"other": dict(OTHER), "reachy-mini": dict(ENTRY)}}
    assert _clients.remove_entry(config, name="reachy-mini") is True
    assert "other" in config["mcpServers"]
    assert "reachy-mini" not in config["mcpServers"]
    assert _clients.remove_entry(config, name="reachy-mini") is False


def test_round_trip_on_disk(tmp_path):
    path = tmp_path / "nested" / "mcp.json"
    config = {"mcpServers": {}}
    _clients.merge_entry(config, name="reachy-mini", entry=ENTRY)
    _clients.write_config(path, config)
    assert _clients.is_installed(path, name="reachy-mini")
    reloaded = _clients.load_config(path)
    assert reloaded == config


def test_load_missing_returns_empty(tmp_path):
    assert _clients.load_config(tmp_path / "nope.json") == {}


def test_load_rejects_bad_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ReachyError):
        _clients.load_config(bad)


def test_resolve_target_explicit_path(tmp_path):
    target = _clients.resolve_target(client="claude-code", path=str(tmp_path / "x.json"))
    assert target.client == "path"
    assert target.path == tmp_path / "x.json"


def test_resolve_target_unknown_client():
    with pytest.raises(ReachyError):
        _clients.resolve_target(client="nope")


def test_resolve_claude_code_scopes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _clients.resolve_target(client="claude-code", scope="project")
    assert project.path == tmp_path / ".mcp.json"
    user = _clients.resolve_target(client="claude-code", scope="user")
    assert user.path.name == ".claude.json"


def test_claude_desktop_path_darwin(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    target = _clients.resolve_target(client="claude-desktop")
    assert target.path.as_posix().endswith(
        "Library/Application Support/Claude/claude_desktop_config.json"
    )


def test_claude_desktop_path_windows_with_appdata(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    target = _clients.resolve_target(client="claude-desktop")
    assert target.path == tmp_path / "Claude" / "claude_desktop_config.json"


def test_claude_desktop_path_windows_without_appdata(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("APPDATA", raising=False)
    target = _clients.resolve_target(client="claude-desktop")
    assert "AppData" in target.path.parts
    assert "Roaming" in target.path.parts


def test_resolve_target_unknown_scope():
    with pytest.raises(ReachyError):
        _clients.resolve_target(client="claude-code", scope="bogus")


def test_load_config_oserror_on_directory(tmp_path):
    # Reading a directory as text raises OSError → ReachyError, not a traceback.
    d = tmp_path / "is_a_dir"
    d.mkdir()
    with pytest.raises(ReachyError):
        _clients.load_config(d)


def test_load_config_empty_file_returns_empty(tmp_path):
    p = tmp_path / "empty.json"
    p.write_text("   \n", encoding="utf-8")
    assert _clients.load_config(p) == {}


def test_load_config_rejects_non_object(tmp_path):
    p = tmp_path / "array.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ReachyError):
        _clients.load_config(p)


def test_merge_entry_rejects_non_object_servers():
    with pytest.raises(ReachyError):
        _clients.merge_entry({"mcpServers": "not-an-object"}, name="reachy-mini", entry=ENTRY)


def test_is_installed_swallows_bad_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert _clients.is_installed(bad, name="reachy-mini") is False


def test_write_config_oserror_becomes_reachy_error(tmp_path, monkeypatch):
    # Force the atomic replace to fail; write_config must surface a ReachyError
    # (and clean up the temp file) rather than leak the OSError.
    def boom(*a, **k):
        raise OSError("replace failed")

    monkeypatch.setattr(_clients.os, "replace", boom)
    with pytest.raises(ReachyError):
        _clients.write_config(tmp_path / "cfg.json", {"mcpServers": {}})
