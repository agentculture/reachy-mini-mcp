# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/), and this
project adheres to [Semantic Versioning](https://semver.org/).

## [0.2.1] - 2026-06-03

### Fixed

- Corrected the SonarCloud projectKey to the hyphenated agentculture_reachy-mini-mcp (matching the GitHub-integration project). The underscored key auto-provisioned a separate project whose main branch defaulted to master, so push-to-main analysis failed with Project not found and blocked the publish job. Updated sonar-project.properties, the README badges, and CLAUDE.md.

## [0.2.0] - 2026-06-03

### Added

- Test pipeline now generates coverage.xml and runs a SonarCloud scan in CI (publish.yml test job), guarded by SONAR_TOKEN so token-less and fork PRs stay green.
- sonar-project.properties (projectKey agentculture_reachy-mini-mcp) wiring SonarCloud coverage decoration; robot runtime is coverage-excluded but kept indexed for static analysis.
- Manager-CLI unit tests for serve lazy-import, doctor checks, overview render, dispatch/error routing, _meta/_output helpers, client-config edge cases, and the __main__ entrypoint.

### Changed

- Coverage gate: pyproject.toml [tool.coverage.report] now sets fail_under = 95; CLI-manager coverage raised from 84% to ~99%.

### Fixed

- publish.yml `paths:` filter now also triggers on `sonar-project.properties` and the workflow file itself, so Sonar/coverage-config changes can't silently skip CI (Qodo review, PR #13).

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
  stdio protocol channel. This also covers TTS diagnostics (`tts_queue.py` prints,
  including the background playback thread) and tool-script output (tool
  `execute()` runs under `redirect_stdout(stderr)`), so enabling `speech` can't
  break the channel.
- `mcp.stdio.example.json`, `start.sh`, `start_openai_server.sh`, and `setup.sh`
  updated for the package layout and the console script.

### Fixed

- `server_openai.py` now honors `REACHY_BASE_URL` from the environment instead of
  hardcoding `http://localhost:8000`, so `serve --openai` reaches non-local
  daemons (matches `server.py`).
- `doctor`'s optional-dependency probe uses `importlib.util.find_spec` instead of
  `__import__`, so it reports availability without importing heavy modules or
  polluting `sys.modules`.

### Removed

- The bogus `asyncio>=4.0.0` requirement (asyncio is part of the standard
  library); dependencies now live in `pyproject.toml`.
