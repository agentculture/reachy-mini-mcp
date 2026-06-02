"""Shared helpers: ``_output.emit_error`` formatting and ``_meta`` probes
(``count_tools`` edge cases and ``daemon_status`` for each urllib outcome)."""

from __future__ import annotations

import io
import urllib.error

from reachy_mini_mcp.cli import _meta
from reachy_mini_mcp.cli._errors import ReachyError
from reachy_mini_mcp.cli._output import emit_error


def test_emit_error_writes_message_and_hint():
    buf = io.StringIO()
    emit_error(ReachyError(code=1, message="boom", remediation="do x"), stream=buf)
    assert buf.getvalue() == "error: boom\nhint: do x\n"


def test_emit_error_omits_empty_hint():
    buf = io.StringIO()
    emit_error(ReachyError(code=1, message="boom"), stream=buf)
    assert buf.getvalue() == "error: boom\n"


def test_reachy_error_to_dict_round_trips_fields():
    err = ReachyError(code=2, message="oops", remediation="retry")
    assert err.to_dict() == {"code": 2, "message": "oops", "remediation": "retry"}


def test_count_tools_missing_index(tmp_path, monkeypatch):
    monkeypatch.setattr(_meta, "tools_dir", lambda: tmp_path)
    assert _meta.count_tools() == (0, 0)


def test_count_tools_bad_shape(tmp_path, monkeypatch):
    (tmp_path / "tools_index.json").write_text('{"tools": "not-a-list"}', encoding="utf-8")
    monkeypatch.setattr(_meta, "tools_dir", lambda: tmp_path)
    assert _meta.count_tools() == (0, 0)


def test_count_tools_counts_enabled(tmp_path, monkeypatch):
    (tmp_path / "tools_index.json").write_text(
        '{"tools": [{"enabled": true}, {"enabled": false}, {}]}', encoding="utf-8"
    )
    monkeypatch.setattr(_meta, "tools_dir", lambda: tmp_path)
    assert _meta.count_tools() == (2, 3)  # {} defaults to enabled=True


class _FakeResp:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_daemon_status_reachable(monkeypatch):
    monkeypatch.setattr(_meta.urllib.request, "urlopen", lambda *a, **k: _FakeResp())
    reachable, detail = _meta.daemon_status("http://localhost:8000")
    assert reachable is True
    assert detail == "HTTP 200"


def test_daemon_status_http_error_is_still_reachable(monkeypatch):
    def boom(*a, **k):
        raise urllib.error.HTTPError("http://x", 503, "unavailable", {}, None)

    monkeypatch.setattr(_meta.urllib.request, "urlopen", boom)
    reachable, detail = _meta.daemon_status("http://localhost:8000")
    assert reachable is True
    assert detail == "HTTP 503"


def test_daemon_status_connection_failure_is_unreachable(monkeypatch):
    def boom(*a, **k):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(_meta.urllib.request, "urlopen", boom)
    reachable, detail = _meta.daemon_status("http://localhost:8000")
    assert reachable is False
    assert "connection refused" in detail
