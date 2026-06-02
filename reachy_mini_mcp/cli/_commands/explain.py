"""``reachy-mini-mcp explain`` — how to register and run this MCP server.

A self-contained, copy-pasteable briefing aimed at an agent or operator setting
the server up for the first time. Read-only.
"""

from __future__ import annotations

import argparse
import json

from reachy_mini_mcp.cli import _mcp
from reachy_mini_mcp.cli._output import emit_result

_TEMPLATE = """\
# Setting up the Reachy Mini MCP server

This server speaks MCP over **stdio**: the client launches it as a subprocess and
talks JSON-RPC over stdin/stdout. It exposes one meta-tool, `operate_robot`, that
dispatches to every robot operation by name. Under the hood it forwards to the
**Reachy Mini daemon** (default {base_url}), which must be running separately.

## 1. The mcp.json entry

Add this to your client's MCP config (see locations below):

{snippet}

`reachy-mini-mcp show` prints exactly this for your machine; add `--dev` if you
run from a source checkout that was never installed.

## 2. Where that config lives

- Claude Code  — project: ./.mcp.json    user: ~/.claude.json
- Claude Desktop — ~/.config/Claude/claude_desktop_config.json  (macOS:
  ~/Library/Application Support/Claude/...; Windows: %APPDATA%/Claude/...)
- Cursor       — project: ./.cursor/mcp.json   user: ~/.cursor/mcp.json

## 3. Let the CLI do it

Instead of hand-editing, install (merge) or uninstall (remove) the entry:

    reachy-mini-mcp install --client claude-code --scope project   # set it up
    reachy-mini-mcp install --client claude-desktop                # set it up
    reachy-mini-mcp uninstall --client claude-code --scope project # put it down

Add `--dry-run` to print the resulting file without writing it. Existing servers
in the config are preserved; install is idempotent.

## 4. Environment

- REACHY_BASE_URL  — daemon URL (default {base_url})
- PIPER_MODEL      — optional Piper TTS model path (no .onnx suffix) for speech
- AUDIO_DEVICE     — optional ALSA device for audio playback (find via `aplay -L`)

Running `serve` needs the robot stack: install it with the extra —
`pip install "reachy-mini-mcp[server]"` (add `[tts]` for speech).

## 5. Verify

    reachy-mini-mcp doctor     # checks deps, tools, daemon, and install state
    reachy-mini-mcp overview   # one-screen status summary
"""


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser(
        "explain",
        help="Explain how to register and run this MCP server.",
        description="Print a copy-pasteable briefing on setting the server up.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Daemon URL shown in the briefing "
        f"(default: $REACHY_BASE_URL or {_mcp.DEFAULT_BASE_URL}).",
    )
    parser.set_defaults(func=_handle)


def _handle(args: argparse.Namespace) -> int:
    snippet = json.dumps(_mcp.build_config(base_url=args.base_url), indent=2)
    base_url = args.base_url or _mcp.build_env(base_url=args.base_url)["REACHY_BASE_URL"]
    emit_result(_TEMPLATE.format(base_url=base_url, snippet=snippet))
    return 0
