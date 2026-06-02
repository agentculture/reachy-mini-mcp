"""Build the ``mcp.json`` entry for this server and resolve how to launch it.

The headline artifact the manager produces is the ``mcpServers`` snippet an MCP
client needs::

    {
      "mcpServers": {
        "reachy-mini": {
          "command": "reachy-mini-mcp",
          "args": ["serve"],
          "env": {"REACHY_BASE_URL": "http://localhost:8000"}
        }
      }
    }

When the console script is on ``PATH`` (the installed case) we emit it directly.
Otherwise — a source checkout that was never installed — we fall back to
``<python> -m reachy_mini_mcp serve`` so the snippet still works.
"""

from __future__ import annotations

import os
import shutil
import sys
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_NAME = "reachy-mini"
CONSOLE_SCRIPT = "reachy-mini-mcp"
DEFAULT_BASE_URL = "http://localhost:8000"


def resolve_command(*, dev: bool = False) -> Tuple[str, List[str]]:
    """Return the ``(command, args)`` an MCP client should use to launch serve.

    ``dev=True`` (or no console script on PATH) yields the in-tree form
    ``<python> -m reachy_mini_mcp serve``; otherwise the installed console
    script ``reachy-mini-mcp serve``.
    """
    if not dev:
        found = shutil.which(CONSOLE_SCRIPT)
        if found:
            return found, ["serve"]
    return sys.executable, ["-m", "reachy_mini_mcp", "serve"]


def build_env(
    *,
    base_url: Optional[str] = None,
    include_optional: bool = True,
) -> Dict[str, str]:
    """Build the ``env`` block. Always carries ``REACHY_BASE_URL``; folds in the
    optional TTS vars when they are set in the current environment."""
    env: Dict[str, str] = {
        "REACHY_BASE_URL": base_url or os.environ.get("REACHY_BASE_URL", DEFAULT_BASE_URL),
    }
    if include_optional:
        for key in ("PIPER_MODEL", "AUDIO_DEVICE"):
            value = os.environ.get(key)
            if value:
                env[key] = value
    return env


def build_entry(
    *,
    base_url: Optional[str] = None,
    dev: bool = False,
    include_optional_env: bool = True,
) -> Dict[str, Any]:
    """Build a single ``mcpServers`` value: ``{command, args, env}``."""
    command, args = resolve_command(dev=dev)
    return {
        "command": command,
        "args": args,
        "env": build_env(base_url=base_url, include_optional=include_optional_env),
    }


def build_config(
    *,
    name: str = DEFAULT_NAME,
    base_url: Optional[str] = None,
    dev: bool = False,
    include_optional_env: bool = True,
) -> Dict[str, Any]:
    """Build the full ``{"mcpServers": {name: entry}}`` document."""
    return {
        "mcpServers": {
            name: build_entry(
                base_url=base_url,
                dev=dev,
                include_optional_env=include_optional_env,
            )
        }
    }
