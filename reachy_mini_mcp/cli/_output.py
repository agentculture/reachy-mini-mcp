"""stdout / stderr helpers with a strict split.

Rule: results go to stdout, diagnostics and errors go to stderr. Agents parsing
CLI output can rely on this invariant. Modelled on guildmaster's
``guild.cli._output`` (cite-don't-import).
"""

from __future__ import annotations

import sys
from typing import Any, TextIO

from reachy_mini_mcp.cli._errors import ReachyError


def emit_result(data: Any, *, stream: TextIO | None = None) -> None:
    """Write a command result to stdout (default)."""
    s = stream if stream is not None else sys.stdout
    text = data if isinstance(data, str) else str(data)
    s.write(text)
    if not text.endswith("\n"):
        s.write("\n")


def emit_error(err: ReachyError, *, stream: TextIO | None = None) -> None:
    """Write a :class:`ReachyError` to stderr as one or two lines::

    error: <message>
    hint: <remediation>
    """
    s = stream if stream is not None else sys.stderr
    s.write(f"error: {err.message}\n")
    if err.remediation:
        s.write(f"hint: {err.remediation}\n")


def emit_diagnostic(message: str, *, stream: TextIO | None = None) -> None:
    """Write a human diagnostic to stderr."""
    s = stream if stream is not None else sys.stderr
    s.write(message if message.endswith("\n") else message + "\n")
