# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/), and this
project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-06-02

### Added

- **Packaging.** The project is now a pip-installable distribution
  (`reachy-mini-mcp`) built with hatchling, published to PyPI and TestPyPI via
  OIDC Trusted Publishing (`.github/workflows/publish.yml`).
- **Manager CLI** (`reachy-mini-mcp`) — an MCP-server manager:
  - `overview` — one-screen status (also the no-argument landing page);
  - `show` — print the `mcp.json` snippet for this machine;
  - `explain` — how to register and run the server;
  - `install` / `up` and `uninstall` / `down` — merge/remove the server entry in
    Claude Code (`.mcp.json` / `~/.claude.json`), Claude Desktop, Cursor, or any
    `--path`, preserving other servers; `--dry-run` for print-only;
  - `doctor` — diagnose install, deps, daemon, and client registration;
  - `serve` — run the FastMCP stdio server (or `--openai` for the FastAPI server).
- Optional-dependency extras: `[server]`, `[tts]`, `[openai]`. The manager itself
  needs no runtime dependencies; `serve` lazy-imports the robot stack.

### Changed

- Runtime code moved into a `reachy_mini_mcp/` package (`server.py`,
  `server_openai.py`, `tts_queue.py`, `tools_repository/`). Cross-module imports
  updated accordingly; both servers gained a `main()` entry point.
- The MCP server's banner output now goes to stderr so it cannot corrupt the
  stdio protocol channel.
- `mcp.stdio.example.json`, `start.sh`, `start_openai_server.sh`, and `setup.sh`
  updated for the package layout and the console script.

### Removed

- The bogus `asyncio>=4.0.0` requirement (asyncio is part of the standard
  library); dependencies now live in `pyproject.toml`.
