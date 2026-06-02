"""Unified CLI entry point for ``reachy-mini-mcp`` — the MCP server manager.

Every handler raises :class:`reachy_mini_mcp.cli._errors.ReachyError` on failure;
``main()`` catches it via :func:`_dispatch` and routes through
:mod:`reachy_mini_mcp.cli._output`. Argparse errors route through
``_ReachyArgumentParser`` so they share the same structured output.

Modelled on guildmaster's ``guild.cli`` (cite-don't-import). Note: the manager
commands import **no** robot dependencies at module load — only ``serve`` pulls
in the FastMCP/httpx stack, lazily, so ``pip install reachy-mini-mcp`` (without
the ``[server]`` extra) still gives a fully working manager.
"""

from __future__ import annotations

import argparse
import sys

from reachy_mini_mcp import __version__
from reachy_mini_mcp.cli._errors import EXIT_USER_ERROR, ReachyError
from reachy_mini_mcp.cli._output import emit_error

ISSUES_URL = "https://github.com/agentculture/reachy-mini-mcp/issues"


class _ReachyArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that routes errors through :func:`emit_error`."""

    def error(self, message: str) -> None:  # type: ignore[override]
        err = ReachyError(
            code=EXIT_USER_ERROR,
            message=message,
            remediation=f"run '{self.prog} --help' to see valid arguments",
        )
        emit_error(err)
        raise SystemExit(err.code)


def _build_parser() -> argparse.ArgumentParser:
    # Deferred imports keep the parser module decoupled from the command modules
    # at import time (matches the guild pattern).
    from reachy_mini_mcp.cli._commands import doctor as _doctor_cmd
    from reachy_mini_mcp.cli._commands import explain as _explain_cmd
    from reachy_mini_mcp.cli._commands import install as _install_cmd
    from reachy_mini_mcp.cli._commands import overview as _overview_cmd
    from reachy_mini_mcp.cli._commands import serve as _serve_cmd
    from reachy_mini_mcp.cli._commands import show as _show_cmd
    from reachy_mini_mcp.cli._commands import uninstall as _uninstall_cmd

    parser = _ReachyArgumentParser(
        prog="reachy-mini-mcp",
        description=(
            "Manage the Reachy Mini MCP server: show/install/uninstall its "
            "mcp.json entry, diagnose the setup, and run the server."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    sub = parser.add_subparsers(dest="command", parser_class=_ReachyArgumentParser)

    _overview_cmd.register(sub)
    _show_cmd.register(sub)
    _explain_cmd.register(sub)
    _install_cmd.register(sub)
    _uninstall_cmd.register(sub)
    _doctor_cmd.register(sub)
    _serve_cmd.register(sub)

    return parser


def _dispatch(args: argparse.Namespace) -> int:
    try:
        rc = args.func(args)
    except ReachyError as err:
        emit_error(err)
        return err.code
    except KeyboardInterrupt:  # serve / network waits — exit quietly
        return 130
    except Exception as err:  # noqa: BLE001 - last resort: wrap so no traceback leaks
        wrapped = ReachyError(
            code=EXIT_USER_ERROR,
            message=f"unexpected: {err.__class__.__name__}: {err}",
            remediation=f"file a bug at {ISSUES_URL}",
        )
        emit_error(wrapped)
        return wrapped.code
    return rc if rc is not None else 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        # No subcommand → show the read-only overview, the natural landing page.
        from reachy_mini_mcp.cli._commands import overview as _overview_cmd

        return _overview_cmd.run_default()

    return _dispatch(args)


if __name__ == "__main__":
    sys.exit(main())
