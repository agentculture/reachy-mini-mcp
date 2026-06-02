"""``reachy-mini-mcp overview`` — one-screen status of the server + its setup.

The natural landing page (also shown when the CLI is run with no subcommand).
Read-only: what this is, the resolved launch command, bundled tool count, daemon
reachability, and which clients already have it registered.
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, Optional

from reachy_mini_mcp import __version__
from reachy_mini_mcp.cli import _clients, _mcp
from reachy_mini_mcp.cli._meta import count_tools, daemon_status
from reachy_mini_mcp.cli._output import emit_result

_CLIENT_TARGETS = (
    ("claude-code", "project"),
    ("claude-code", "user"),
    ("claude-desktop", "user"),
    ("cursor", "project"),
    ("cursor", "user"),
)


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser(
        "overview",
        help="One-screen status: server, tools, daemon, and where it's installed.",
        description="Read-only status summary of the Reachy Mini MCP server and its setup.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help=f"Daemon URL to probe (default: $REACHY_BASE_URL or {_mcp.DEFAULT_BASE_URL}).",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    parser.set_defaults(func=_handle)


def _build(base_url: Optional[str]) -> Dict[str, Any]:
    url = base_url or os.environ.get("REACHY_BASE_URL", _mcp.DEFAULT_BASE_URL)
    command, args = _mcp.resolve_command()
    enabled, total = count_tools()
    reachable, detail = daemon_status(url)

    installs = []
    for client, scope in _CLIENT_TARGETS:
        target = _clients.resolve_target(client=client, scope=scope)
        if _clients.is_installed(target.path, name=_mcp.DEFAULT_NAME):
            installs.append({"client": client, "scope": scope, "path": str(target.path)})

    return {
        "version": __version__,
        "server_name": _mcp.DEFAULT_NAME,
        "launch": {"command": command, "args": args},
        "tools": {"enabled": enabled, "total": total},
        "daemon": {"base_url": url, "reachable": reachable, "detail": detail},
        "installed_in": installs,
    }


def _render(data: Dict[str, Any]) -> str:
    launch = f"{data['launch']['command']} {' '.join(data['launch']['args'])}".strip()
    daemon = data["daemon"]
    daemon_line = (
        f"{daemon['base_url']} — "
        f"{'reachable' if daemon['reachable'] else 'UNREACHABLE'} ({daemon['detail']})"
    )
    lines = [
        f"# reachy-mini-mcp {data['version']}",
        "",
        "MCP server + manager CLI for the Reachy Mini robot. The server exposes one",
        "meta-tool, `operate_robot`, and forwards to the Reachy daemon.",
        "",
        f"  Server name : {data['server_name']}",
        f"  Launch      : {launch}",
        f"  Tools       : {data['tools']['enabled']} enabled / {data['tools']['total']} total",
        f"  Daemon      : {daemon_line}",
    ]
    if data["installed_in"]:
        lines.append("  Installed   :")
        for i in data["installed_in"]:
            lines.append(f"    - {i['client']} ({i['scope']}): {i['path']}")
    else:
        lines.append("  Installed   : not registered in any known client")
    lines += [
        "",
        "Next: `reachy-mini-mcp show` (mcp.json) · `explain` (how-to) · "
        "`install` / `uninstall` · `doctor`.",
    ]
    return "\n".join(lines)


def _emit(data: Dict[str, Any], as_json: bool) -> int:
    emit_result(json.dumps(data, indent=2) if as_json else _render(data))
    return 0


def _handle(args: argparse.Namespace) -> int:
    return _emit(_build(args.base_url), args.json)


def run_default() -> int:
    """Entry used when the CLI is invoked with no subcommand."""
    return _emit(_build(None), as_json=False)
