# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

`reachy-mini-mcp` is a **Model Context Protocol (MCP) server for controlling the
[Reachy Mini](https://github.com/pollen-robotics/reachy_mini) expressive robot**
(Pollen Robotics), built on [FastMCP](https://github.com/jlowin/fastmcp). It lets
an MCP client (Claude Desktop, an agent, etc.) drive the robot's head, antennas,
emotions, and gestures, and speak through a text-to-speech queue.

The server exposes a **single meta-tool**, `operate_robot`, rather than one MCP tool
per action (`server.py:612` registers only `operate_robot`). Call it with a single
action or a sequence:

```python
operate_robot(tool_name="express_emotion", parameters={"emotion": "happy", "speech": "Hello!"})
operate_robot(commands=[{"tool_name": "turn_on_robot"}, {"tool_name": "nod_head"}])
```

A `"speech"` parameter on any command is spoken aloud via the TTS queue. The server
also publishes MCP resources (`reachy://status`, `reachy://capabilities`) and prompts.

As of this onboarding the repo is also an **AgentCulture mesh agent** (see Identity).

## Identity

Declared in `culture.yaml`:

```yaml
agents:
- suffix: reachy-mini-mcp
  backend: claude
```

`backend: claude` fixes the runtime prompt file to **`CLAUDE.md`** (this file).
Together they satisfy the two invariants `steward doctor` verifies:
**prompt-file-present** (an agent is declared and the matching prompt file is on
disk) and **backend-consistency** (`claude` ↔ `CLAUDE.md`).

Sign mesh/issue posts as `- reachy-mini-mcp (Claude)` — the `cicd` / `communicate`
scripts resolve the nick from `culture.yaml` automatically (via
`_resolve-nick.sh` / `agtag`), so don't hand-author the trailing signature.

## Two distinct prompts (important)

- **This file (`CLAUDE.md`)** is the *dev / mesh* system prompt — guidance for Claude
  Code working **on** this repository.
- **`agents/reachy/reachy.system.md`** is the robot's *runtime* personality prompt
  ("You are a cute robot called Reachy Mini…") loaded into the conversation agent that
  drives the physical robot.

They are different files for different audiences. Editing one is not editing the other.

## Architecture / Layout

```text
server.py                 FastMCP server; the operate_robot meta-tool + TOOL_REGISTRY,
                          loads tool definitions from tools_repository/ at startup
server_openai.py          OpenAI-compatible server variant
tts_queue.py              piper-TTS background queue (speaks text passed via "speech")
tools_repository/         the extensible tool system
  tools_index.json        index of the 18 robot operations
  <tool>.json (x18)       per-tool MCP-style definitions
  scripts/<tool>.py (x18) one Python script per tool (script-based execution)
  README.md, SCHEMA.md    tool-definition format docs
dance_moves/              JSON dance sequences
agents/reachy/            reachy.system.md — the robot runtime prompt (see above)
requirements.txt          fastmcp, httpx, reachy-mini, mcp, piper-tts, pyaudio
.claude/skills/           vendored AgentCulture skill kit (cite-don't-import)
docs/skill-sources.md     skill provenance ledger
culture.yaml              mesh identity (suffix + backend)
```

The 18 operations cover state/monitoring (`get_robot_state`, `get_head_state`,
`get_antennas_state`, `get_power_state`, `get_health_status`), power
(`turn_on_robot`, `turn_off_robot`), head motion (`move_head`, `reset_head`,
`nod_head`, `shake_head`, `tilt_head`, `look_at_direction`), antennas
(`move_antennas`, `reset_antennas`), expression (`express_emotion`,
`perform_gesture`), and safety (`stop_all_movements`). All tools execute as standalone
Python scripts — inline code execution was removed (see `INLINE_REMOVAL_SUMMARY.md`).

## Skills

`.claude/skills/` vendors the **canonical guildmaster skill kit** (12 skills,
cite-don't-import). Provenance and the re-sync procedure live in
`docs/skill-sources.md`. Three skills (`think`, `spec-to-plan`,
`assign-to-workforce`) originate in `devague`, and `outsource` originates in
`convertible` — all re-broadcast via guildmaster.

Tooling prerequisites: **`devex`** (>=0.21) on PATH (the `cicd` skill delegates the
PR lifecycle to `devex pr`) and **`agtag`** (>=0.1) on PATH (the `communicate` skill
wraps `agtag issue`); **`convertible`** on PATH is *optional* — only the `outsource`
skill needs it, and only when invoked.

This repo is a FastMCP server driven by `requirements.txt`, **not** a Python
package/CLI. Several kit skills assume a `pyproject.toml` / tests / PyPI / SonarCloud
project that does not exist here yet — `version-bump`, `run-tests`, `sonarclaude`,
`pypi-maintainer`, and the SonarCloud/PyPI parts of `cicd` are therefore **dormant**
(vendored for kit completeness and mesh uniformity). The `cicd` PR lifecycle
(`devex pr` open/read/reply/delta), `communicate`, `outsource`, and the devague
workflow trio work today.

## Conventions

- The vendored `.claude/skills/` are cited **verbatim** — do not reformat or edit
  their scripts; re-sync from guildmaster instead (see `docs/skill-sources.md`).
- PRs go through the `cicd` skill (`devex pr`). Markdownlint config ignores
  `.claude/skills/**` (vendored, never reformatted).
- This repo has **no version-bump merge gate and no PyPI deploy** — do not add claims
  of either to docs until the corresponding scaffolding actually lands.

## Running

```bash
pip install -r requirements.txt        # see setup.sh / setup.ps1 for full setup
./setup_piper_model.sh                 # download the piper TTS voice model
./start.sh                             # start the MCP server (stdio)
./start_openai_server.sh               # start the OpenAI-compatible variant
```

`mcp.stdio.example.json` is a sample MCP client config. `start_daemon.sh` /
`shutdown_daemon.sh` manage the Reachy Mini daemon.

This file describes the repository **as it exists on disk today**. When you edit, keep
claims grounded in checked-in reality; mark anything aspirational `(planned)` or move
it under a `## Roadmap` heading (the README tracks the project roadmap).
