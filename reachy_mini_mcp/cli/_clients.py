"""Where each MCP client keeps its config, and how to edit it safely.

Every supported client uses the same ``{"mcpServers": {...}}`` schema, so this
module is one path-resolver plus a small set of pure JSON merge/remove helpers
(easy to unit-test without touching a real client).

Supported ``--client`` values:

* ``claude-code``    — project: ``<cwd>/.mcp.json``; user: ``~/.claude.json``
* ``claude-desktop`` — the platform ``claude_desktop_config.json`` (scope ignored)
* ``cursor``         — project: ``<cwd>/.cursor/mcp.json``; user: ``~/.cursor/mcp.json``

``--path FILE`` overrides everything for any other client that speaks the schema.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from reachy_mini_mcp.cli._errors import EXIT_USER_ERROR, ReachyError

CLIENTS = ("claude-code", "claude-desktop", "cursor")
SCOPES = ("user", "project")

_DESKTOP_CONFIG_FILENAME = "claude_desktop_config.json"


@dataclass
class ClientTarget:
    """A resolved config file plus a human label for messages."""

    client: str
    scope: str
    path: Path
    label: str


def _claude_desktop_path() -> Path:
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Claude" / _DESKTOP_CONFIG_FILENAME
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA")
        root = Path(base) if base else home / "AppData" / "Roaming"
        return root / "Claude" / _DESKTOP_CONFIG_FILENAME
    return home / ".config" / "Claude" / _DESKTOP_CONFIG_FILENAME


def resolve_target(
    *,
    client: str,
    scope: str = "project",
    path: Optional[str] = None,
    cwd: Optional[Path] = None,
) -> ClientTarget:
    """Resolve the config file for ``client``/``scope`` (or an explicit ``path``)."""
    here = (cwd or Path.cwd()).resolve()

    if path:
        p = Path(path).expanduser().resolve()
        return ClientTarget(client="path", scope=scope, path=p, label=str(p))

    if client not in CLIENTS:
        raise ReachyError(
            code=EXIT_USER_ERROR,
            message=f"unknown client {client!r}",
            remediation=f"choose one of: {', '.join(CLIENTS)} (or use --path FILE)",
        )
    if scope not in SCOPES:
        raise ReachyError(
            code=EXIT_USER_ERROR,
            message=f"unknown scope {scope!r}",
            remediation=f"choose one of: {', '.join(SCOPES)}",
        )

    if client == "claude-code":
        if scope == "user":
            p = Path.home() / ".claude.json"
            return ClientTarget(client, scope, p, f"Claude Code (user, {p})")
        p = here / ".mcp.json"
        return ClientTarget(client, scope, p, f"Claude Code (project, {p})")

    if client == "claude-desktop":
        p = _claude_desktop_path()
        return ClientTarget(client, "user", p, f"Claude Desktop ({p})")

    # cursor
    if scope == "user":
        p = Path.home() / ".cursor" / "mcp.json"
        return ClientTarget(client, scope, p, f"Cursor (user, {p})")
    p = here / ".cursor" / "mcp.json"
    return ClientTarget(client, scope, p, f"Cursor (project, {p})")


def load_config(path: Path) -> Dict[str, Any]:
    """Read a client config, or return ``{}`` when it does not exist yet."""
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReachyError(
            code=EXIT_USER_ERROR,
            message=f"could not read {path}: {exc}",
            remediation="check the path and permissions",
        )
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ReachyError(
            code=EXIT_USER_ERROR,
            message=f"{path} is not valid JSON: {exc}",
            remediation="fix or remove the file, then retry",
        )
    if not isinstance(data, dict):
        raise ReachyError(
            code=EXIT_USER_ERROR,
            message=f"{path} does not contain a JSON object",
            remediation="expected an object with an 'mcpServers' key",
        )
    return data


def merge_entry(
    config: Dict[str, Any],
    *,
    name: str,
    entry: Dict[str, Any],
    force: bool = False,
) -> bool:
    """Set ``mcpServers[name] = entry`` in ``config`` (mutated in place).

    Returns ``True`` if the config changed. Raises if a *different* entry of the
    same name already exists and ``force`` is not set. Other servers are
    preserved.
    """
    servers = config.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise ReachyError(
            code=EXIT_USER_ERROR,
            message="existing 'mcpServers' is not a JSON object",
            remediation="fix the config file, then retry",
        )
    existing = servers.get(name)
    if existing == entry:
        return False
    if existing is not None and not force:
        raise ReachyError(
            code=EXIT_USER_ERROR,
            message=f"server {name!r} already exists with different settings",
            remediation="pass --force to overwrite, or choose another --name",
        )
    servers[name] = entry
    return True


def remove_entry(config: Dict[str, Any], *, name: str) -> bool:
    """Delete ``mcpServers[name]`` if present. Returns ``True`` if removed."""
    servers = config.get("mcpServers")
    if isinstance(servers, dict) and name in servers:
        del servers[name]
        return True
    return False


def is_installed(path: Path, *, name: str) -> bool:
    """True if ``path`` exists and already registers a server called ``name``."""
    if not path.exists():
        return False
    try:
        config = load_config(path)
    except ReachyError:
        return False
    servers = config.get("mcpServers")
    return isinstance(servers, dict) and name in servers


def write_config(path: Path, config: Dict[str, Any]) -> None:
    """Write ``config`` to ``path`` atomically (creating parent dirs)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(config, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".mcp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise ReachyError(
            code=EXIT_USER_ERROR,
            message=f"could not write {path}: {exc}",
            remediation="check the path and permissions",
        )
