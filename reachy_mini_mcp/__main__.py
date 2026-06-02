"""``python -m reachy_mini_mcp`` → the manager CLI.

This is the dev/source equivalent of the ``reachy-mini-mcp`` console script, and
the command an un-installed checkout's ``mcp.json`` points at
(``python -m reachy_mini_mcp serve``).
"""

from __future__ import annotations

import sys

from reachy_mini_mcp.cli import main

if __name__ == "__main__":
    sys.exit(main())
