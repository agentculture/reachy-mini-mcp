"""``doctor`` health-check branches: each Check helper and the text/JSON output.

Daemon probing is patched at the command module's binding (``doctor`` imports
``daemon_status`` by name, so the effective target is
``reachy_mini_mcp.cli._commands.doctor.daemon_status``) — never the network.
"""

from __future__ import annotations

import json

from reachy_mini_mcp.cli import main
from reachy_mini_mcp.cli._commands import doctor


def _offline(monkeypatch):
    monkeypatch.setattr(doctor, "daemon_status", lambda *a, **k: (False, "stubbed offline"))


def test_tools_check_missing_index_is_hard_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(doctor, "tools_dir", lambda: tmp_path)
    check = doctor._tools_check()
    assert check.status == doctor._FAIL
    assert check.hard is True
    assert "tools_index.json missing" in check.detail


def test_doctor_hard_fail_returns_env_error(tmp_path, monkeypatch, capsys):
    _offline(monkeypatch)
    monkeypatch.setattr(doctor, "tools_dir", lambda: tmp_path)
    assert main(["doctor"]) == 2  # EXIT_ENV_ERROR
    assert "FAILED" in capsys.readouterr().out


def test_available_swallows_value_error(monkeypatch):
    def boom(_name):
        raise ValueError("dotted name with leading dot")

    monkeypatch.setattr(doctor.importlib.util, "find_spec", boom)
    assert doctor._available("..bad") is False


def test_import_check_all_present(monkeypatch):
    monkeypatch.setattr(doctor, "_available", lambda _m: True)
    check = doctor._import_check("server-extra", ["fastmcp", "httpx"], "server")
    assert check.status == doctor._OK
    assert check.detail == "installed"


def test_import_check_reports_missing(monkeypatch):
    monkeypatch.setattr(doctor, "_available", lambda _m: False)
    check = doctor._import_check("server-extra", ["fastmcp"], "server")
    assert check.status == doctor._WARN
    assert "fastmcp" in check.detail


def test_binaries_check_all_present(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda b: f"/usr/bin/{b}")
    check = doctor._binaries_check()
    assert check.status == doctor._OK
    assert "piper and aplay" in check.detail


def test_env_check_reports_set_vars(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no .env here, so only env vars contribute
    monkeypatch.setenv("REACHY_BASE_URL", "http://x:1")
    detail = doctor._env_check().detail
    assert detail.startswith("set: ")
    assert "REACHY_BASE_URL" in detail


def test_env_check_reports_dotenv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("X=1\n", encoding="utf-8")
    for k in ("REACHY_BASE_URL", "PIPER_MODEL", "AUDIO_DEVICE"):
        monkeypatch.delenv(k, raising=False)
    assert ".env present" in doctor._env_check().detail


def test_env_check_defaults_when_nothing_set(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for k in ("REACHY_BASE_URL", "PIPER_MODEL", "AUDIO_DEVICE"):
        monkeypatch.delenv(k, raising=False)
    assert "no robot env vars set" in doctor._env_check().detail


def test_install_check_reports_installed(monkeypatch):
    monkeypatch.setattr(doctor._clients, "is_installed", lambda path, *, name: True)
    assert doctor._install_check().status == doctor._OK


def test_install_check_reports_none(monkeypatch):
    monkeypatch.setattr(doctor._clients, "is_installed", lambda path, *, name: False)
    check = doctor._install_check()
    assert check.status == doctor._WARN
    assert "not registered" in check.detail


def test_doctor_json_output(monkeypatch, capsys):
    _offline(monkeypatch)
    assert main(["doctor", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload) == {"ok", "checks"}
    assert payload["ok"] is True
    assert isinstance(payload["checks"], list)
    assert {"name", "status", "detail", "hard"} <= set(payload["checks"][0])
