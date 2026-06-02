"""reachy-mini-mcp — MCP server + manager CLI for the Reachy Mini robot.

The package ships two things behind one distribution:

* the **MCP server** (:mod:`reachy_mini_mcp.server`, a FastMCP stdio server) and
  its OpenAI-compatible sibling (:mod:`reachy_mini_mcp.server_openai`), driven by
  the dynamic tool repository under ``reachy_mini_mcp/tools_repository``; and
* the **manager CLI** (:mod:`reachy_mini_mcp.cli`) — ``reachy-mini-mcp`` — which
  shows/installs/uninstalls the ``mcp.json`` entry, diagnoses the setup
  (``doctor``), and launches the server (``serve``).
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("reachy-mini-mcp")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0+dev"

__all__ = ["__version__"]
