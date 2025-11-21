@# Reachy Mini MCP Server

A Model Context Protocol (MCP) server for controlling the [Reachy Mini](https://github.com/pollen-robotics/reachy_mini) robot using [FastMCP](https://github.com/jlowin/fastmcp).

> [!NOTE]
> **Looking for the full Conversation App?**
> This repository also contains the full "Conversation Stack" (Hearing + LLM + Conversation Logic) which turns Reachy Mini into an autonomous conversational robot.
>
> The **Docker setup** is specifically for running this full conversation application.
>
> 👉 **[Read the Conversation Stack Overview](docs/conversation_stack.md)**
>
> 👉 **[Full Docker Setup Guide](DOCKER_SETUP.md)**

This MCP server provides a comprehensive set of tools to control Reachy Mini's head movements, antennas, camera, and perform various gestures and emotional expressions.

## Roadmap

### MCP
- [ ] Speech: TTS, piper
- [ ] Agentic layer
- [ ] Queue actions support
- [ ] Interruption support
- [ ] Move body support, reachy-mini python SDK

### Conversation app 
- [ ] Hearing: 
  - [ ] VAD, WebRTCVAD / SileroVAD
  - [ ] STT, faster-whisper
- [ ] Vision
- [ ] Memory:
  - [ ] File
  - [ ] Vector DB
  - [ ] Vector Graph DB
- [ ] Growth, nightly fine tunes support
- [ ] MQTT support 
- [ ] Move to [autonomous-intelligence](https://github.com/OriNachum/autonomous-intelligence) repo




## Features

### Movement & Speech Control
- **Head Control**: Move the head in 3D space (x, y, z) with orientation (roll, pitch, yaw)
- **Antenna Control**: Control left and right antennas independently
- **Speech (TTS)**: Make the robot speak while performing actions (via `speech` parameter)
- **Gestures**: Perform predefined gestures (greeting, yes, no, thinking, celebration)
- **Emotions**: Express emotions (happy, sad, curious, surprised, confused)
- **Direction Looking**: Make the robot look in specific directions (up, down, left, right)

### Monitoring & Control
- **State Monitoring**: Get full robot state, head state, antenna state, camera state
- **Power Management**: Turn robot on/off
- **Emergency Stop**: Immediately halt all movements
- **Health Status**: Monitor robot health and system status

### Advanced Features
- **Command Sequences**: Execute multiple robot operations in a single call (NEW!)
- **Single Unified Interface**: Access all functionality through one `operate_robot` tool
- **Repository-Based Tools**: Easily extensible tool system with JSON definitions

## Prerequisites

1. **Python 3.10+** (tested with Python 3.10-3.13)
2. **Reachy Mini Robot**: Either physical robot connected via USB or wireless, or simulation running in MuJoCo
3. **Reachy Mini Daemon**: Must be running on `localhost:8000` (default)

## Installation

### 1. Set up Python Environment

```bash
# Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- `fastmcp`: MCP server framework
- `httpx`: HTTP client for API communication
- `reachy-mini`: Reachy Mini SDK (optional, for direct Python control)

## Running the MCP Server

### Step 1: Start the Reachy Mini Daemon

Before starting the MCP server, you need to have the Reachy Mini daemon running.

👉 **[Follow the official Reachy Mini Daemon Setup Guide](https://github.com/pollen-robotics/reachy_mini)**

Ensure the daemon is running and accessible (default: `http://localhost:8000`).

### Step 2: Start the MCP Server

In a new terminal (with the same virtual environment activated):

```bash
python server.py
```

Or use FastMCP directly:
```bash
fastmcp run server.py
```

The MCP server will now be running and ready to accept connections from MCP clients.

## Available MCP Tools

### Single Unified Tool: `operate_robot`

This MCP server exposes **one MCP tool** that provides access to all robot control functionality:

| Tool | Description |
|------|-------------|
| `operate_robot(tool_name, parameters)` | **Meta-tool** to dynamically execute any robot control operation by name. |
| `operate_robot(commands)` | **Sequence mode** to execute multiple operations in sequence. |

This unified interface allows you to call any of the robot control operations either individually or as a sequence:

**Single Command Mode:**
```python
# Example: Get robot state
operate_robot("get_robot_state")

# Example: Express emotion with parameters
operate_robot("express_emotion", {"emotion": "happy"})

# Example: Move head with multiple parameters
operate_robot("move_head", {"z": 10, "duration": 2.0, "mm": True})
```

**Sequence Mode (NEW!):**
```python
# Example: Execute multiple commands in sequence
operate_robot(commands=[
    {"tool_name": "perform_gesture", "parameters": {"gesture": "greeting"}},
    {"tool_name": "nod_head", "parameters": {"duration": 2.0, "angle": 15}},
    {"tool_name": "move_antennas", "parameters": {"left": 30, "right": -30, "duration": 1.5}},
    {"tool_name": "look_at_direction", "parameters": {"direction": "left", "duration": 1.0}}
])
```

**Note:** The tool name must match exactly. The correct tool is `get_robot_state`, not `get_robot_status`.

### Available Robot Operations

All operations are accessible through the `operate_robot` tool. Here are all available operations:

#### Basic State & Control

| Operation | Description |
|-----------|-------------|
| `get_robot_state` | Get full robot state including all components |
| `get_head_state` | Get current head position and orientation |
| `get_antennas_state` | Get current antenna positions |
| `get_camera_state` | Get camera status |
| `get_power_state` | Check if robot is powered on/off |
| `get_health_status` | Get overall health status |
| `turn_on_robot` | Power on the robot |
| `turn_off_robot` | Power off the robot |
| `stop_all_movements` | Emergency stop all movements |

#### Head Movement

| Operation | Description |
|-----------|-------------|
| `move_head` | Move head to specific pose (params: x, y, z, roll, pitch, yaw, duration) |
| `reset_head` | Return head to neutral position |
| `nod_head` | Make robot nod (params: duration, angle) |
| `shake_head` | Make robot shake head (params: duration, angle) |
| `tilt_head` | Tilt head left or right (params: direction, angle, duration) |
| `look_at_direction` | Look in a direction (params: direction - up/down/left/right, duration) |

#### Antenna Movement

| Operation | Description |
|-----------|-------------|
| `move_antennas` | Move antennas to specific positions (params: left, right, duration) |
| `reset_antennas` | Return antennas to neutral position |

#### Emotions & Gestures

| Operation | Description |
|-----------|-------------|
| `express_emotion` | Express emotion (params: emotion - happy/sad/curious/surprised/confused) |
| `perform_gesture` | Perform gesture (params: gesture - greeting/yes/no/thinking/celebration) |

#### Camera

| Operation | Description |
|-----------|-------------|
| `get_camera_image` | Capture image from camera |
| `get_camera_state` | Get camera status |

## Usage Examples

All operations are called through the `operate_robot` tool. Here are some examples:

### Example 1: Basic Head Movement

```python
# In your MCP client (e.g., Claude Desktop)
# Move head up 10mm and tilt 15 degrees
operate_robot("move_head", {"z": 10, "roll": 15, "duration": 2.0})

# Return to neutral
operate_robot("reset_head")
```

### Example 2: Express Emotions

```python
# Make the robot look happy
operate_robot("express_emotion", {"emotion": "happy"})

# Make the robot look curious
operate_robot("express_emotion", {"emotion": "curious"})

# Return to neutral
operate_robot("express_emotion", {"emotion": "neutral"})
```

### Example 3: Perform Gestures

```python
# Wave hello
operate_robot("perform_gesture", {"gesture": "greeting"})

# Nod yes
operate_robot("perform_gesture", {"gesture": "yes"})

# Shake no
operate_robot("perform_gesture", {"gesture": "no"})
```

### Example 4: Complex Interaction

```python
# Turn on the robot
operate_robot("turn_on_robot")

# Check state
state = operate_robot("get_robot_state")

# Make robot look around
operate_robot("look_at_direction", {"direction": "left", "duration": 1.5})
operate_robot("look_at_direction", {"direction": "right", "duration": 1.5})
operate_robot("look_at_direction", {"direction": "forward"})

# Express surprise
operate_robot("express_emotion", {"emotion": "surprised"})

# Perform celebration
operate_robot("perform_gesture", {"gesture": "celebration"})

# Turn off when done
operate_robot("turn_off_robot")
```

### Example 5: Control Antennas

```python
# Move antennas independently
operate_robot("move_antennas", {"left": 30, "right": -30, "duration": 1.0})

# Reset to neutral
operate_robot("reset_antennas")
```

### Example 6: Command Sequences (NEW!)

Execute complex robot behaviors with command sequences:

```python
# Greeting sequence
operate_robot(commands=[
    {"tool_name": "express_emotion", "parameters": {"emotion": "happy"}},
    {"tool_name": "perform_gesture", "parameters": {"gesture": "greeting"}},
    {"tool_name": "nod_head", "parameters": {"duration": 1.5, "angle": 10}},
    {"tool_name": "reset_head", "parameters": {}}
])

# Curious behavior - look around
operate_robot(commands=[
    {"tool_name": "express_emotion", "parameters": {"emotion": "curious"}},
    {"tool_name": "move_antennas", "parameters": {"left": 30, "right": 30, "duration": 1.0}},
    {"tool_name": "look_at_direction", "parameters": {"direction": "left", "duration": 1.0}},
    {"tool_name": "look_at_direction", "parameters": {"direction": "right", "duration": 1.0}},
    {"tool_name": "look_at_direction", "parameters": {"direction": "forward", "duration": 0.5}}
])

# Initialization routine
operate_robot(commands=[
    {"tool_name": "turn_on_robot", "parameters": {}},
    {"tool_name": "reset_head", "parameters": {}},
    {"tool_name": "reset_antennas", "parameters": {}},
    {"tool_name": "get_robot_state", "parameters": {}}
])
```

For more details on command sequences, see [SEQUENCE_COMMANDS.md](SEQUENCE_COMMANDS.md).

## Using with MCP Supported client

To use this MCP server, add the following to your MCP configuration file:

### macOS/Linux
Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "reachy-mini": {
      "command": "python",
      "args": ["/Users/ori.nachum/Git/InnovationLabs/mcps/reachy-mini-mcp/server.py"],
      "env": {
        "PYTHONPATH": "/Users/ori.nachum/Git/InnovationLabs/mcps/reachy-mini-mcp/.venv/lib/python3.12/site-packages"
      }
    }
  }
}
```

### Windows
Edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "reachy-mini": {
      "command": "python",
      "args": ["C:\\path\\to\\InnovationLabs\\mcps\\reachy-mini-mcp\\server.py"]
    }
  }
}
```

After editing the config, restart Claude Desktop. The Reachy Mini tools will be available in your conversations.

## MCP Prompts

The server includes helpful prompts:

- `control_prompt` - Guidelines for controlling Reachy Mini
- `safety_prompt` - Safety guidelines and limits

## Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│  MCP Client     │◄───────►│  FastMCP Server  │◄───────►│ Reachy Daemon   │
│  (Claude, etc)  │  stdio  │  (server.py)     │  HTTP   │  (localhost:8000)│
└─────────────────┘         └──────────────────┘         └─────────────────┘
                                                                    │
                                                                    ▼
                                                          ┌─────────────────┐
                                                          │  Reachy Mini    │
                                                          │  Robot/Sim      │
                                                          └─────────────────┘
```
## Development

### Repository-Based Tool System

This MCP server uses a **repository-based approach** for defining tools, making it highly extensible and customizable. Tools are defined in JSON files rather than hardcoded in Python.

**Key Benefits:**
- ✅ Add new tools without modifying server code
- ✅ Customize tool behavior by editing JSON files
- ✅ Easy to version control and share tool definitions
- ✅ Script-based execution for complex operations

**Repository Structure:**
```
tools_repository/
├── tools_index.json          # Root file listing all tools
├── *.json                    # Individual tool definitions
└── scripts/                  # Python scripts for complex tools
    ├── nod_head.py
    ├── shake_head.py
    ├── express_emotion.py
    └── perform_gesture.py
```

### Adding New Tools

Create a Python script in `tools_repository/scripts/my_tool.py`:

```python
async def execute(make_request, create_head_pose, params):
    """Execute the tool."""
    # Your logic here
    await make_request("POST", "/api/endpoint1", json_data={...})
    await asyncio.sleep(1.0)
    await make_request("POST", "/api/endpoint2", json_data={...})
    return {"status": "success"}
```

Then create a JSON file (e.g., `tools_repository/my_tool.json`):

```json
{
  "name": "my_tool",
  "description": "Description of what my tool does",
  "parameters": {
    "required": [
      {"name": "param1", "type": "string", "description": "First parameter"}
    ],
    "optional": [
      {"name": "param2", "type": "number", "default": 1.0, "description": "Second parameter"}
    ]
  },
  "execution": {
    "type": "script",
    "script_file": "my_tool.py"
  }
}
```

Add to `tools_repository/tools_index.json`:
```json
{
  "name": "my_tool",
  "enabled": true,
  "definition_file": "my_tool.json"
}
```

Restart the server - your tool is now available!

### Testing Tools

Validate your tool definitions:

```bash
python test_repository.py
```

This verifies all JSON files are valid and script files exist.

## Resources

- [Reachy Mini GitHub](https://github.com/pollen-robotics/reachy_mini)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)

## License

This project is licensed under the MIT License, including the conversation and hearing app within this repository, and does not extend to the Reachy Mini Daemon.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Support

For issues related to:
- **This MCP server**: Open an issue in this repository
- **Reachy Mini robot**: Visit [Reachy Mini GitHub Issues](https://github.com/pollen-robotics/reachy_mini/issues)

## Credits

- Built with [FastMCP](https://github.com/jlowin/fastmcp) by Marvin
- For [Reachy Mini](https://github.com/pollen-robotics/reachy_mini) by Pollen Robotics & Hugging Face
- Follows the [Model Context Protocol](https://modelcontextprotocol.io/) specification


