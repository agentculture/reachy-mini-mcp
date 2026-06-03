"""Shared read-only helpers for the manager commands (overview / doctor).

Deliberately dependency-free: the daemon ping uses :mod:`urllib` from the stdlib
rather than ``httpx`` so these commands work without the ``[server]`` extra.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Tuple

import reachy_mini_mcp


def tools_dir() -> Path:
    """Absolute path to the bundled ``tools_repository`` (package data)."""
    return Path(reachy_mini_mcp.__file__).parent / "tools_repository"


def count_tools() -> Tuple[int, int]:
    """Return ``(enabled, total)`` tool counts from ``tools_index.json``.

    Returns ``(0, 0)`` if the index is missing or unreadable.
    """
    index = tools_dir() / "tools_index.json"
    try:
        data = json.loads(index.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return (0, 0)
    tools = data.get("tools", [])
    if not isinstance(tools, list):
        return (0, 0)
    enabled = sum(1 for t in tools if isinstance(t, dict) and t.get("enabled", True))
    return (enabled, len(tools))


def daemon_status(base_url: str, *, timeout: float = 2.0) -> Tuple[bool, str]:
    """Probe the Reachy daemon's ``/api/state/full`` endpoint.

    Returns ``(reachable, detail)``. ``reachable`` is True for any HTTP response
    (even a 4xx/5xx — the daemon answered); False only when the connection
    itself fails.
    """
    url = base_url.rstrip("/") + "/api/state/full"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 - local daemon
            return True, f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        return True, f"HTTP {exc.code}"
    except (OSError, ValueError) as exc:  # urllib.error.URLError is an OSError subclass
        reason = getattr(exc, "reason", exc)
        return False, str(reason)
