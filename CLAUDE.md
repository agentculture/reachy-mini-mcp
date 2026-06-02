# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A control layer for the [Reachy Mini](https://github.com/pollen-robotics/reachy_mini) robot. Nothing here drives motors directly — every action is an HTTP call to the **Reachy Mini daemon** (default `http://localhost:8000`), which must be running separately. This repo exposes the daemon's capabilities to LLMs two ways, both backed by one shared tool repository:

- **`server.py`** — a FastMCP (stdio) MCP server. Exposes exactly **one** MCP tool, `operate_robot`, a meta-tool that dispatches to every robot operation by name. Individual tools are loaded into an in-process registry but deliberately *not* surfaced as separate MCP tools.
- **`server_openai.py`** — a FastAPI HTTP server (port **8100**) that speaks an OpenAI-ish dialect: `GET /tools`, `POST /execute_tool`, `POST /v1/chat/completions`. Here each tool *is* exposed individually in OpenAI function-calling format.

```text
MCP client / HTTP client  →  server.py | server_openai.py  →  Reachy daemon (:8000)  →  robot/sim
```

## Commands

```bash
# First-time setup (creates .venv, installs requirements.txt, offers MuJoCo sim deps)
./setup.sh

# MCP server (stdio) — requires the daemon running first
./start.sh                 # wraps: source .venv/bin/activate && python server.py
python server.py
fastmcp run server.py

# OpenAI-compatible HTTP server on :8100 (uses requirements-openai.txt)
./start_openai_server.sh
python server_openai.py

# Piper TTS voice model download helper
./setup_piper_model.sh
```

There is **no test suite**. The README references `python test_repository.py`, but that file does not exist in the repo — don't try to run it. Likewise `docs/conversation_stack.md`, `DOCKER_SETUP.md`, and `SEQUENCE_COMMANDS.md` are linked from the README but are not present.

## The tool repository (the core abstraction)

Tools are data + a script, not hardcoded Python. To add or change a robot operation you edit `tools_repository/`, never the server files:

```text
tools_repository/
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

**Gotcha:** `tools_repository/SCHEMA.md` and the README still document the old 3-argument signature `execute(make_request, create_head_pose, params)`. The real signature has **four** args (`tts_queue` was inserted third). Follow the existing scripts, not those docs. Inline-code execution was removed entirely for security (see `INLINE_REMOVAL_SUMMARY.md`); only `"type": "script"` is supported.

To register a new tool: add the script + JSON, then add an entry to `tools_index.json` and restart the server.

## `operate_robot` semantics

This meta-tool has two modes and some implicit behavior worth knowing:

- **Single:** `operate_robot(tool_name="...", parameters={...})`. After the call it automatically appends a `get_robot_state` and returns it under `robot_state`.
- **Sequence:** `operate_robot(commands=[{tool_name, parameters}, ...])`. Runs sequentially; a failing command does **not** abort the rest; a `get_robot_state` is auto-appended as a final result.
- Tool names must match exactly (`get_robot_state`, not `get_robot_status`). Most action tools accept an optional `speech` string that is spoken via TTS while the action runs.

## Two servers, one set of machinery — keep them in sync

`server.py` and `server_openai.py` each contain their own copy of `create_head_pose`, `make_request`, and the tool-loading functions. A fix to loading/dispatch logic generally needs to be applied to **both**. Known divergences to be aware of:

- `server.py` reads `REACHY_BASE_URL` from the environment; `server_openai.py` **hardcodes** `http://localhost:8000`.
- `server.py` builds an `inspect.Signature` with type annotations for each tool (FastMCP introspects it); `server_openai.py` doesn't need that and builds an OpenAI JSON schema instead.
- `server_openai.py`'s `/v1/chat/completions` is a **stub** — naive keyword matching ("turn on" → `turn_on_robot`), not a real LLM. Real LLM reasoning is expected to come from an upstream model (e.g. the vLLM containers) that then calls `/execute_tool`.

## Configuration

Copy `.env.example` (MCP/TTS) or `.env.openai.example` (HTTP/LLM) to `.env`. `.env` is gitignored. Key vars: `REACHY_BASE_URL`, `PIPER_MODEL` (path **without** `.onnx`), `AUDIO_DEVICE` (ALSA device, find via `aplay -L`), and `HF_TOKEN` for the Docker stack.

TTS (`tts_queue.py`) shells out to the `piper` executable and plays WAVs with `aplay` on a background thread. If `piper`/`aplay` or a model is missing, TTS init fails gracefully and `speech` params are silently ignored.

## The conversation stack (Docker) — partially present

`docker-compose-vllm.yml` describes the full autonomous-robot deployment: two vLLM servers (front `:8100`, action `:8200`, both Llama-3.2-3B-Instruct-FP8), the reachy daemon, a hearing service, and a conversation app. **Be aware:** the application source it mounts (`conversation_app/`, `hearing_app/`) was removed from the repo (commit "remove app files (#8)") and lives elsewhere now — the compose file references directories that no longer exist here. Treat this file as a deployment reference, not something runnable as-is from this repo.

## Other directories

- `agents/reachy/reachy.system.md` — the robot's persona / system prompt for the LLM driving `operate_robot`.
- `dance_moves/*.json` — despite the `.json` extension these are **captured LLM debug transcripts** (example `operate_robot` command sequences with parse logs), not structured config. Useful as examples of expected tool-call output, not as data to load.
- `_config.yml` — Jekyll config for the GitHub Pages project site; unrelated to the Python servers.
