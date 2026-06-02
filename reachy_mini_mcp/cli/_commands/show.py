"""``reachy-mini-mcp show`` — print the mcp.json snippet for this machine.

This is the artifact an agent copies into a client config. By default it prints a
pretty JSON ``mcpServers`` block resolved for the current install (console script
vs ``python -m`` fallback); ``--dev`` forces the in-tree form.
"""

from __future__ import annotations

import argparse
import json

from reachy_mini_mcp.cli import _mcp
from reachy_mini_mcp.cli._output import emit_result


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser(
        "show",
        help="Print the mcp.json snippet to register this server.",
        description=(
            "Print the JSON 'mcpServers' block an MCP client needs to launch the "
            "Reachy Mini MCP server, resolved for how this machine runs it."
        ),
    )
    parser.add_argument(
        "--name",
        default=_mcp.DEFAULT_NAME,
        help=f"Server key in the config (default: {_mcp.DEFAULT_NAME}).",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Reachy daemon URL for the REACHY_BASE_URL env "
        f"(default: $REACHY_BASE_URL or {_mcp.DEFAULT_BASE_URL}).",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Emit the in-tree form (python -m reachy_mini_mcp serve) "
        "instead of the installed console script.",
    )
    parser.add_argument(
        "--entry-only",
        action="store_true",
        help="Print just the server entry, not the wrapping {'mcpServers': {...}}.",
    )
    parser.set_defaults(func=_handle)


def _handle(args: argparse.Namespace) -> int:
    if args.entry_only:
        payload = _mcp.build_entry(base_url=args.base_url, dev=args.dev)
    else:
        payload = _mcp.build_config(name=args.name, base_url=args.base_url, dev=args.dev)
    emit_result(json.dumps(payload, indent=2))
    return 0
