"""The package version falls back to a dev marker when the distribution
metadata is absent (a source tree that was never installed)."""

from __future__ import annotations

import importlib
import importlib.metadata as md

import reachy_mini_mcp


def test_version_falls_back_when_not_installed(monkeypatch):
    def not_found(name):
        raise md.PackageNotFoundError(name)

    monkeypatch.setattr(md, "version", not_found)
    try:
        reloaded = importlib.reload(reachy_mini_mcp)
        assert reloaded.__version__ == "0.0.0+dev"
    finally:
        # Restore the real, installed version for any later tests.
        monkeypatch.undo()
        importlib.reload(reachy_mini_mcp)
