# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A control layer for the [Reachy Mini](https://github.com/pollen-robotics/reachy_mini) robot. Nothing here drives motors directly — every action is an HTTP call to the **Reachy Mini daemon** (default `http://localhost:8000`), which must be running separately. The code lives in the **`reachy_mini_mcp/`** package (a pip-installable distribution, `reachy-mini-mcp`, built with hatchling). It exposes the daemon's capabilities to LLMs two ways, both backed by one shared tool repository:

- **`reachy_mini_mcp/server.py`** — a FastMCP (stdio) MCP server. Exposes exactly **one** MCP tool, `operate_robot`, a meta-tool that dispatches to every robot operation by name. Individual tools are loaded into an in-process registry but deliberately *not* surfaced as separate MCP tools.
- **`reachy_mini_mcp/server_openai.py`** — a FastAPI HTTP server (port **8100**) that speaks an OpenAI-ish dialect: `GET /tools`, `POST /execute_tool`, `POST /v1/chat/completions`. Here each tool *is* exposed individually in OpenAI function-calling format.

In front of both sits **`reachy_mini_mcp/cli/`** — the `reachy-mini-mcp` console
script, an MCP-server **manager**: `overview`, `show` (print the mcp.json
snippet), `explain`, `install`/`uninstall` (merge/remove the entry in a client
config), `doctor`, and `serve` (run the server — what mcp.json launches). The
manager imports **no** robot dependencies; only `serve` pulls in the FastMCP
stack (lazily), so a bare `pip install reachy-mini-mcp` is a working manager and
the robot runtime lives behind the `[server]` / `[tts]` / `[openai]` extras.

```text
MCP client / HTTP client  →  reachy_mini_mcp.server | .server_openai  →  Reachy daemon (:8000)  →  robot/sim
                  manager:  reachy-mini-mcp {show,install,doctor,serve,...}
```

Beyond the robot-control layer, this repo is also an **AgentCulture mesh agent** —
its mesh identity and vendored skill kit are described under [Mesh identity](#mesh-identity-agentculture)
and [Skills](#skills) below.

## Commands

```bash
# First-time setup (creates .venv, installs the package editable with [server,tts])
./setup.sh

# Manager CLI (no robot deps needed)
reachy-mini-mcp overview          # status; also the no-arg default
reachy-mini-mcp show              # print the mcp.json snippet
reachy-mini-mcp install --client claude-code --scope project   # / uninstall
reachy-mini-mcp doctor            # diagnose deps, daemon, registration

# MCP server (stdio) — requires the daemon running first
./start.sh                        # wraps: source .venv/bin/activate && python -m reachy_mini_mcp serve
reachy-mini-mcp serve             # or: python -m reachy_mini_mcp serve
fastmcp run reachy_mini_mcp/server.py

# OpenAI-compatible HTTP server on :8100
./start_openai_server.sh
reachy-mini-mcp serve --openai    # or: python -m reachy_mini_mcp.server_openai

# Tests (manager CLI only — no robot stack/daemon needed). Avoid `uv sync`/`uv run
# pytest`: the universal resolve pulls the [server] extra → reachy-mini → pycairo,
# which needs system cairo to build. Install just the manager + pytest instead:
uv pip install -e . pytest pytest-xdist pytest-cov   # `uv venv` first if you have no venv
# Plain run, or with coverage (CI uses the --cov form; fail_under=95 gate applies):
uv run --no-project pytest -n auto -v
uv run --no-project pytest -n auto --cov=reachy_mini_mcp --cov-report=xml:coverage.xml --cov-report=term -v

# Piper TTS voice model download helper
./setup_piper_model.sh
```

Tests live in `tests/` and cover the manager CLI (mcp.json builder, client-config
merge/remove, command smoke tests) — they need no robot stack or daemon. The
robot runtime (`server.py`, `server_openai.py`, `tts_queue.py`, tool scripts) is
not unit-tested; verify it by running `serve` against a live daemon. The README
links `docs/conversation_stack.md`, `DOCKER_SETUP.md`, and `SEQUENCE_COMMANDS.md`,
which are not present in the repo.

## The tool repository (the core abstraction)

Tools are data + a script, not hardcoded Python. To add or change a robot operation you edit `reachy_mini_mcp/tools_repository/`, never the server files (it ships as package data in the wheel):

```text
reachy_mini_mcp/tools_repository/
├── tools_index.json     # registry: name → definition_file, with enabled flag
├── <tool>.json          # parameter schema + which script runs it
└── scripts/<tool>.py    # the actual logic
```

Loading flow (duplicated in both servers): `tools_index.json` → each `<tool>.json` → dynamically import `scripts/<tool>.py` via `importlib`. Every script must define:

```python
async def execute(make_request, create_head_pose, tts_queue, params):
    ...
    return {...}   # Dict[str, Any]
```

- `make_request(method, endpoint, json_data=, params=)` — the daemon HTTP helper. Movement goes through `POST /api/move/goto` with `{"head_pose": ..., "antennas": [...], "duration": ...}`; state via `GET /api/state/full`.
- `create_head_pose(x, y, z, roll, pitch, yaw, degrees=False, mm=False)` — builds a pose dict. When `mm=True` it converts mm→meters; when `degrees=True` it converts degrees→radians. The daemon wants **meters and radians**; antennas are passed directly in radians (e.g. `math.radians(30)`).
- `tts_queue` — may be `None` if Piper isn't configured. Always guard: `if speech and tts_queue:`.

The `execute()` signature takes **four** args — `tts_queue` is the third (it may be `None` if Piper isn't configured, so guard with `if speech and tts_queue:`). Inline-code execution was removed entirely for security (see `INLINE_REMOVAL_SUMMARY.md`); only `"type": "script"` is supported.

To register a new tool: add the script + JSON, then add an entry to `tools_index.json` and restart the server.

## `operate_robot` semantics

This meta-tool has two modes and some implicit behavior worth knowing:

- **Single:** `operate_robot(tool_name="...", parameters={...})`. After the call it automatically appends a `get_robot_state` and returns it under `robot_state`.
- **Sequence:** `operate_robot(commands=[{tool_name, parameters}, ...])`. Runs sequentially; a failing command does **not** abort the rest; a `get_robot_state` is auto-appended as a final result.
- Tool names must match exactly (`get_robot_state`, not `get_robot_status`). Most action tools accept an optional `speech` string that is spoken via TTS while the action runs.

## Two servers, one set of machinery — keep them in sync

`reachy_mini_mcp/server.py` and `reachy_mini_mcp/server_openai.py` each contain their own copy of `create_head_pose`, `make_request`, and the tool-loading functions. A fix to loading/dispatch logic generally needs to be applied to **both**. Both now also expose a `main()` entry point (called by `reachy-mini-mcp serve` / `serve --openai`). Known divergences to be aware of:

- Both read `REACHY_BASE_URL` from the environment (defaulting to `http://localhost:8000`). (Historically `server_openai.py` hardcoded it; fixed in 0.1.0.)
- `server.py` builds an `inspect.Signature` with type annotations for each tool (FastMCP introspects it); `server_openai.py` doesn't need that and builds an OpenAI JSON schema instead.
- `server.py` is a **stdio** server, so its startup banner / tool-loading prints are routed to **stderr** (stdout is the JSON-RPC channel); `server_openai.py` is HTTP, so it prints freely.
- `server_openai.py`'s `/v1/chat/completions` is a **stub** — naive keyword matching ("turn on" → `turn_on_robot`), not a real LLM. Real LLM reasoning is expected to come from an upstream model (e.g. the vLLM containers) that then calls `/execute_tool`.

## Configuration

Copy `.env.example` (MCP/TTS) or `.env.openai.example` (HTTP/LLM) to `.env`. `.env` is gitignored. Key vars: `REACHY_BASE_URL`, `PIPER_MODEL` (path **without** `.onnx`), `AUDIO_DEVICE` (ALSA device, find via `aplay -L`), and `HF_TOKEN` for the Docker stack.

TTS (`reachy_mini_mcp/tts_queue.py`) shells out to the `piper` executable and plays WAVs with `aplay` on a background thread. If `piper`/`aplay` or a model is missing, TTS init fails gracefully and `speech` params are silently ignored.

Packaging lives in `pyproject.toml` (hatchling). Runtime deps are **extras**, not
base deps: the manager CLI has zero runtime deps; `[server]` (fastmcp/httpx/mcp/
reachy-mini/python-dotenv) is needed for `serve`, `[tts]` (piper-tts/pyaudio) for
speech, `[openai]` for the FastAPI server. `requirements*.txt` are thin shims onto
those extras. Version is single-sourced in `pyproject.toml` (read at runtime via
`importlib.metadata` in `reachy_mini_mcp/__init__.py`); bump it with the
`version-bump` skill and keep `CHANGELOG.md` in step.

## The conversation stack (Docker) — partially present

`docker-compose-vllm.yml` describes the full autonomous-robot deployment: two vLLM servers (front `:8100`, action `:8200`, both Llama-3.2-3B-Instruct-FP8), the reachy daemon, a hearing service, and a conversation app. **Be aware:** the application source it mounts (`conversation_app/`, `hearing_app/`) was removed from the repo (commit "remove app files (#8)") and lives elsewhere now — the compose file references directories that no longer exist here. Treat this file as a deployment reference, not something runnable as-is from this repo.

## Other directories

- `agents/reachy/reachy.system.md` — the robot's persona / system prompt for the LLM driving `operate_robot`.
- `dance_moves/*.json` — despite the `.json` extension these are **captured LLM debug transcripts** (example `operate_robot` command sequences with parse logs), not structured config. Useful as examples of expected tool-call output, not as data to load.
- `_config.yml` — Jekyll config for the GitHub Pages project site; unrelated to the Python servers.

## Mesh identity (AgentCulture)

This repo is also an **AgentCulture mesh agent**, declared in `culture.yaml`:

```yaml
agents:
- suffix: reachy-mini-mcp
  backend: claude
```

`backend: claude` fixes the runtime prompt file to **`CLAUDE.md`** (this file).
Together they satisfy the two invariants `steward doctor` verifies:
**prompt-file-present** (an agent is declared and the matching prompt file is on
disk) and **backend-consistency** (`claude` ↔ `CLAUDE.md`).

Note the two distinct prompts: **this file** is the *dev / mesh* prompt (guidance for
Claude Code working **on** the repo), while **`agents/reachy/reachy.system.md`** is the
robot's *runtime* persona that drives `operate_robot`. Different files, different
audiences — editing one is not editing the other.

Sign mesh / issue posts as `- reachy-mini-mcp (Claude)` — the `cicd` / `communicate`
scripts resolve the nick from `culture.yaml` automatically (via `_resolve-nick.sh` /
`agtag`), so don't hand-author the trailing signature.

## Skills

`.claude/skills/` vendors the **canonical guildmaster skill kit** (12 skills,
cite-don't-import). Provenance and the re-sync procedure live in
`docs/skill-sources.md`. Three skills (`think`, `spec-to-plan`,
`assign-to-workforce`) originate in `devague`, and `outsource` originates in
`convertible` — all re-broadcast via guildmaster.

Tooling prerequisites: **`devex`** (>=0.21) on PATH (the `cicd` skill delegates the PR
lifecycle to `devex pr`) and **`agtag`** (>=0.1) on PATH (the `communicate` skill wraps
`agtag issue`); **`convertible`** on PATH is *optional* — only the `outsource` skill
needs it, and only when invoked.

As of the `0.1.0` packaging work the repo now has a `pyproject.toml`, a `tests/`
suite, and a PyPI/TestPyPI publish workflow, so **`version-bump`, `run-tests`, and
`pypi-maintainer` are now live** (the dist name is `reachy-mini-mcp`; CI publishes
via OIDC Trusted Publishing in `.github/workflows/publish.yml`). As of `0.2.0`, the
`publish.yml` `test` job also generates `coverage.xml` and runs a **SonarCloud**
scan (`sonar-project.properties`, projectKey `agentculture_reachy-mini-mcp`; CLI
coverage is gated at `fail_under = 95`). The scan step is guarded by
`if: env.SONAR_TOKEN != ''`, so it stays inert — and `sonarclaude` / the SonarCloud
parts of `cicd` return no data — until the external SonarCloud project and the
`SONAR_TOKEN` repo secret are provisioned; once they are, both go live with no code
change. The robot runtime is coverage-excluded (it needs a live daemon/hardware)
but kept indexed for static analysis. The `cicd` PR lifecycle (`devex pr`
open/read/reply/delta), `communicate`, `outsource`, and the devague workflow trio
work today.

The vendored `.claude/skills/` are cited **verbatim** — do not reformat or edit their
scripts; re-sync from guildmaster instead (see `docs/skill-sources.md`). The
markdownlint config ignores `.claude/skills/**` for this reason.
