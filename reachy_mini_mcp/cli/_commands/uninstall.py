"""``reachy-mini-mcp uninstall`` (alias ``down``) — put the server down.

Removes our ``mcpServers`` entry from a target client config, leaving every other
server untouched. ``--dry-run`` prints the resulting file instead of writing it.
"""

from __future__ import annotations

import argparse
import json

from reachy_mini_mcp.cli import _clients
from reachy_mini_mcp.cli._commands.install import _add_target_args
from reachy_mini_mcp.cli._output import emit_diagnostic, emit_result


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser(
        "uninstall",
        aliases=["down"],
        help="Remove this server from an MCP client config.",
        description=(
            "Remove the Reachy Mini MCP server entry from a client's config, "
            "leaving any other servers intact."
        ),
    )
    _add_target_args(parser)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resulting config instead of writing it.",
    )
    parser.set_defaults(func=_handle)


def _handle(args: argparse.Namespace) -> None:
    target = _clients.resolve_target(client=args.client, scope=args.scope, path=args.path)
    config = _clients.load_config(target.path)
    removed = _clients.remove_entry(config, name=args.name)

    if args.dry_run:
        emit_diagnostic(f"# would write {target.label}")
        emit_result(json.dumps(config, indent=2))
        return

    if not removed:
        emit_diagnostic(f"{args.name!r} not found in {target.label} — nothing to do.")
        return

    _clients.write_config(target.path, config)
    emit_diagnostic(f"Removed {args.name!r} from {target.label}")
