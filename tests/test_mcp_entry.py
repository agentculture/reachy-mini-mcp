"""The mcp.json builder produces a valid mcpServers document."""

from __future__ import annotations

from reachy_mini_mcp.cli import _mcp


def test_build_config_shape():
    cfg = _mcp.build_config()
    assert set(cfg) == {"mcpServers"}
    assert _mcp.DEFAULT_NAME in cfg["mcpServers"]
    entry = cfg["mcpServers"][_mcp.DEFAULT_NAME]
    assert set(entry) == {"command", "args", "env"}
    assert isinstance(entry["command"], str) and entry["command"]
    assert isinstance(entry["args"], list)
    assert entry["env"]["REACHY_BASE_URL"]


def test_custom_name_and_base_url():
    cfg = _mcp.build_config(name="robot", base_url="http://example:9000")
    assert "robot" in cfg["mcpServers"]
    assert cfg["mcpServers"]["robot"]["env"]["REACHY_BASE_URL"] == "http://example:9000"


def test_dev_form_uses_python_module():
    command, args = _mcp.resolve_command(dev=True)
    assert args == ["-m", "reachy_mini_mcp", "serve"]
    assert command  # the interpreter path


def test_entry_only_helper():
    entry = _mcp.build_entry()
    assert "command" in entry and "args" in entry and "env" in entry


def test_base_url_from_env(monkeypatch):
    monkeypatch.setenv("REACHY_BASE_URL", "http://daemon:1234")
    assert _mcp.build_env()["REACHY_BASE_URL"] == "http://daemon:1234"


def test_build_env_folds_in_optional_tts_vars(monkeypatch):
    monkeypatch.setenv("PIPER_MODEL", "/models/voice")
    monkeypatch.setenv("AUDIO_DEVICE", "hw:1,0")
    env = _mcp.build_env()
    assert env["PIPER_MODEL"] == "/models/voice"
    assert env["AUDIO_DEVICE"] == "hw:1,0"


def test_resolve_command_installed_uses_console_script(monkeypatch):
    monkeypatch.setattr(_mcp.shutil, "which", lambda _name: "/usr/local/bin/reachy-mini-mcp")
    command, args = _mcp.resolve_command()
    assert command == "/usr/local/bin/reachy-mini-mcp"
    assert args == ["serve"]
