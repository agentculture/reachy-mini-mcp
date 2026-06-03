"""``reachy-mini-mcp serve`` — run the MCP server (what mcp.json launches).

The robot stack (FastMCP/httpx/reachy-mini) is an optional extra, imported lazily
here so the rest of the CLI works without it. ``--openai`` runs the
OpenAI-compatible FastAPI server instead of the FastMCP stdio server.
"""

from __future__ import annotations

import argparse

from reachy_mini_mcp.cli._errors import EXIT_ENV_ERROR, ReachyError


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser(
        "serve",
        help="Run the Reachy Mini MCP server (stdio).",
        description=(
            "Launch the FastMCP stdio server (default) or the OpenAI-compatible "
            "FastAPI server (--openai). Requires the [server] extra."
        ),
    )
    parser.add_argument(
        "--openai",
        action="store_true",
        help="Run the OpenAI-compatible FastAPI server on :8100 instead of stdio.",
    )
    parser.set_defaults(func=_handle)


def _handle(args: argparse.Namespace) -> int:
    try:
        if args.openai:
            from reachy_mini_mcp.server_openai import main as serve_main
        else:
            from reachy_mini_mcp.server import main as serve_main
    except ImportError as exc:
        raise ReachyError(
            code=EXIT_ENV_ERROR,
            message=f"the server stack is not installed ({exc})",
            remediation='install it with: pip install "reachy-mini-mcp[server]" '
            "(add [tts] for speech, [openai] for --openai)",
        )
    serve_main()  # blocks until the server exits
    return 0
