"""``reachy-mini-mcp install`` (alias ``up``) — set the server up in a client.

Merges the ``mcpServers`` entry into a target client config, preserving any other
servers. Idempotent; refuses to clobber a different entry of the same name unless
``--force``; ``--dry-run`` prints the resulting file instead of writing it.
"""

from __future__ import annotations

import argparse
import json

from reachy_mini_mcp.cli import _clients, _mcp
from reachy_mini_mcp.cli._output import emit_diagnostic, emit_result


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser(
        "install",
        aliases=["up"],
        help="Set this server up in an MCP client config.",
        description=(
            "Merge the Reachy Mini MCP server entry into a client's config, "
            "leaving any other servers intact."
        ),
    )
    _add_target_args(parser)
    parser.add_argument(
        "--base-url",
        default=None,
        help="Reachy daemon URL for the REACHY_BASE_URL env "
        f"(default: $REACHY_BASE_URL or {_mcp.DEFAULT_BASE_URL}).",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Register the in-tree form (python -m reachy_mini_mcp serve).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing server of the same name.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resulting config instead of writing it.",
    )
    parser.set_defaults(func=_handle)


def _add_target_args(parser: argparse.ArgumentParser) -> None:
    """Shared --client/--scope/--path/--name args (also used by uninstall)."""
    parser.add_argument(
        "--client",
        choices=_clients.CLIENTS,
        default="claude-code",
        help="Target MCP client (default: claude-code). Ignored if --path is set.",
    )
    parser.add_argument(
        "--scope",
        choices=_clients.SCOPES,
        default="project",
        help="user or project config (default: project; ignored for claude-desktop).",
    )
    parser.add_argument(
        "--path",
        default=None,
        help="Write to an explicit config file instead of a known client location.",
    )
    parser.add_argument(
        "--name",
        default=_mcp.DEFAULT_NAME,
        help=f"Server key in the config (default: {_mcp.DEFAULT_NAME}).",
    )


def _handle(args: argparse.Namespace) -> None:
    target = _clients.resolve_target(client=args.client, scope=args.scope, path=args.path)
    entry = _mcp.build_entry(base_url=args.base_url, dev=args.dev)
    config = _clients.load_config(target.path)
    changed = _clients.merge_entry(config, name=args.name, entry=entry, force=args.force)

    if args.dry_run:
        emit_diagnostic(f"# would write {target.label}")
        emit_result(json.dumps(config, indent=2))
        return

    if not changed:
        emit_diagnostic(f"{args.name!r} already registered in {target.label} — no change.")
        return

    _clients.write_config(target.path, config)
    emit_diagnostic(f"Installed {args.name!r} → {target.label}")
