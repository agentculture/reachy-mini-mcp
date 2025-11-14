"""
Reachy Mini MCP Server

A Model Context Protocol (MCP) server for controlling the Reachy Mini robot.
This server provides tools to control the robot's head, antennas, camera, and more.

The server communicates with the Reachy Mini daemon running on localhost:8000.

This version uses a repository-based approach for defining tools dynamically.
"""

import httpx
import json
import os
import math
import asyncio
import importlib.util
from pathlib import Path
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from fastmcp import FastMCP
from tts_queue import AsyncTTSQueue

# Load environment variables from .env file
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("Reachy Mini Controller")

# Configuration
REACHY_BASE_URL = os.getenv("REACHY_BASE_URL", "http://localhost:8000")
TOOLS_REPOSITORY_PATH = Path(__file__).parent / "tools_repository"

# TTS Queue (initialized in initialize_server)
tts_queue = None


# Helper functions
def create_head_pose(
    x: float = 0.0,
    y: float = 0.0, 
    z: float = 0.0,
    roll: float = 0.0,
    pitch: float = 0.0,
    yaw: float = 0.0,
    degrees: bool = False,
    mm: bool = False
) -> Dict[str, Any]:
    """
    Create a head pose configuration for Reachy Mini.
    
    Args:
        x, y, z: Position offsets (meters by default, mm if mm=True)
        roll, pitch, yaw: Rotation angles (radians by default, degrees if degrees=True)
        degrees: If True, angles are in degrees
        mm: If True, positions are in millimeters
    
    Returns:
        Dictionary with head pose configuration
    """
    if mm:
        x, y, z = x / 1000, y / 1000, z / 1000
    
    if degrees:
        roll = math.radians(roll)
        pitch = math.radians(pitch)
        yaw = math.radians(yaw)
    
    return {
        "x": x,
        "y": y,
        "z": z,
        "roll": roll,
        "pitch": pitch,
        "yaw": yaw
    }


async def make_request(
    method: str,
    endpoint: str,
    json_data: Optional[Dict] = None,
    params: Optional[Dict] = None
) -> Dict[str, Any]:
    """Make an HTTP request to the Reachy Mini daemon."""
    url = f"{REACHY_BASE_URL}{endpoint}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if method.upper() == "GET":
                response = await client.get(url, params=params)
            elif method.upper() == "POST":
                response = await client.post(url, json=json_data)
            elif method.upper() == "PUT":
                response = await client.put(url, json=json_data)
            elif method.upper() == "DELETE":
                response = await client.delete(url)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json() if response.content else {"status": "success"}
            
        except httpx.HTTPError as e:
            return {"error": str(e), "status": "failed"}


# Dynamic tool loading functions

def load_tool_index() -> Dict[str, Any]:
    """Load the tool index from tools_index.json."""
    index_path = TOOLS_REPOSITORY_PATH / "tools_index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"Tool index not found at {index_path}")
    
    with open(index_path, 'r') as f:
        return json.load(f)


def load_tool_definition(definition_file: str) -> Dict[str, Any]:
    """Load a tool definition from a JSON file."""
    def_path = TOOLS_REPOSITORY_PATH / definition_file
    if not def_path.exists():
        raise FileNotFoundError(f"Tool definition not found at {def_path}")
    
    with open(def_path, 'r') as f:
        return json.load(f)


def load_script_module(script_file: str):
    """Dynamically load a Python script as a module."""
    script_path = TOOLS_REPOSITORY_PATH / "scripts" / script_file
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found at {script_path}")
    
    spec = importlib.util.spec_from_file_location("tool_script", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_tool_function(tool_def: Dict[str, Any]):
    """Create a tool function from a tool definition."""
    import inspect
    
    # Map JSON types to Python types
    type_mapping = {
        "string": str,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict
    }
    
    # Build parameter list for function signature
    params = []
    annotations = {}
    required_params = tool_def.get("parameters", {}).get("required", [])
    optional_params = tool_def.get("parameters", {}).get("optional", [])
    
    # Add required parameters
    for param in required_params:
        param_name = param["name"]
        param_type = type_mapping.get(param["type"], Any)
        params.append(inspect.Parameter(
            param_name,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=param_type
        ))
        annotations[param_name] = param_type
    
    # Add optional parameters with defaults
    for param in optional_params:
        param_name = param["name"]
        default_value = param.get("default", None)
        param_type = Optional[type_mapping.get(param["type"], Any)]
        params.append(inspect.Parameter(
            param_name,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=default_value,
            annotation=param_type
        ))
        annotations[param_name] = param_type
    
    execution = tool_def.get("execution", {})
    exec_type = execution.get("type")
    
    if exec_type == "script":
        # Load the script module
        script_file = execution.get("script_file")
        module = load_script_module(script_file)
        
        async def tool_func_impl(*args, **kwargs):
            # Call the execute function from the script
            return await module.execute(make_request, create_head_pose, tts_queue, kwargs)
        
        # Create a new function with the proper signature and annotations
        tool_func_impl.__signature__ = inspect.Signature(params)
        tool_func_impl.__annotations__ = annotations
        return tool_func_impl
    
    else:
        raise ValueError(f"Unknown execution type: {exec_type}. Only 'script' type is supported.")


def register_tools_from_repository():
    """Load and register all tools from the repository."""
    try:
        index = load_tool_index()
        
        for tool_entry in index.get("tools", []):
            # Skip disabled tools
            if not tool_entry.get("enabled", True):
                continue
            
            tool_name = tool_entry.get("name")
            definition_file = tool_entry.get("definition_file")
            
            try:
                # Load tool definition
                tool_def = load_tool_definition(definition_file)
                
                # Create the tool function
                tool_func = create_tool_function(tool_def)
                
                # Set the function name and docstring
                tool_func.__name__ = tool_name
                tool_func.__doc__ = tool_def.get("description", "")
                
                # Only register in the global registry for operate_robot tool
                # Individual tools are NOT registered as MCP tools - only operate_robot is exposed
                register_tool_to_registry(tool_name, tool_func)
                
                print(f"✓ Loaded tool to registry: {tool_name}")
                
            except Exception as e:
                import traceback
                print(f"✗ Failed to register tool {tool_name}: {e}")
                print(f"  Traceback: {traceback.format_exc()}")
        
        print(f"\n✓ Successfully loaded {len([t for t in index.get('tools', []) if t.get('enabled', True)])} tools to registry")
        print(f"✓ Tool registry contains {len(TOOL_REGISTRY)} tools available for operate_robot")
        
    except Exception as e:
        print(f"✗ Failed to load tools from repository: {e}")
        raise


# Resources

@mcp.resource("reachy://status")
async def get_status_resource() -> str:
    """Get robot status as a formatted resource."""
    state = await make_request("GET", "/api/state/full")
    return f"Reachy Mini Status:\n{json.dumps(state, indent=2)}"


@mcp.resource("reachy://capabilities")
async def get_capabilities_resource() -> str:
    """Get a description of robot capabilities."""
    return """
Reachy Mini Capabilities:

MOVEMENT:
- 3-DOF head movement (x, y, z position + roll, pitch, yaw orientation)
- 2 expressive antennas (independent control)

SENSORS:
- Camera for vision tasks
- Motor position feedback

EMOTIONS & GESTURES:
- Express emotions: happy, sad, curious, surprised, confused
- Perform gestures: greeting, yes, no, thinking, celebration
- Look in directions: up, down, left, right, forward

CONTROL:
- Power management (on/off)
- Emergency stop
- Real-time state monitoring
"""


# Prompts

@mcp.prompt()
def control_prompt() -> str:
    """Prompt for controlling Reachy Mini."""
    return """
You are controlling a Reachy Mini robot. The robot has:
- A movable head with 3D position and orientation control
- Two expressive antennas
- A camera for vision
- Various gestures and emotion expressions

All robot operations are accessed through the operate_robot() tool, which supports both single commands and sequences:

Single Commands:
1. Express emotions: operate_robot(tool_name="express_emotion", parameters={"emotion": "happy"})
2. Perform gestures: operate_robot(tool_name="perform_gesture", parameters={"gesture": "greeting"})
3. Move head: operate_robot(tool_name="move_head", parameters={"z": 10, "duration": 2.0})
4. Control antennas: operate_robot(tool_name="move_antennas", parameters={"left": 30, "right": -30})
5. Look in directions: operate_robot(tool_name="look_at_direction", parameters={"direction": "left"})

Command Sequences (execute multiple actions):
operate_robot(commands=[
    {"tool_name": "perform_gesture", "parameters": {"gesture": "greeting"}},
    {"tool_name": "nod_head", "parameters": {"duration": 2.0, "angle": 15}},
    {"tool_name": "move_antennas", "parameters": {"left": 30, "right": -30, "duration": 1.5}}
])

Always check the robot state first with operate_robot(tool_name="get_robot_state") before issuing commands.
Remember to turn on the robot with operate_robot(tool_name="turn_on_robot") before movement commands.
"""


@mcp.prompt()
def safety_prompt() -> str:
    """Safety guidelines for robot control."""
    return """
Reachy Mini Safety Guidelines:

1. Always check robot state before issuing movement commands using operate_robot(tool_name="get_robot_state")
2. Use appropriate durations (typically 1-3 seconds) for smooth movements
3. Avoid extreme angles that might stress the motors
4. Use operate_robot(tool_name="stop_all_movements") in case of unexpected behavior
5. Turn off the robot with operate_robot(tool_name="turn_off_robot") when done
6. Monitor health_status periodically during extended use
7. When using command sequences, ensure movements have appropriate durations to complete before the next command

Head Position Limits:
- Position offsets: typically ±20mm on x/y/z
- Rotation angles: ±45 degrees for safe operation

Antenna Limits:
- Typical range: -45 to 45 degrees

Command Sequences:
- Commands in a sequence are executed sequentially
- Each command waits for the previous one to complete
- If a command fails, subsequent commands will still be attempted
- Check the results array to see which commands succeeded or failed
"""


# Tool registry for dynamic tool execution
TOOL_REGISTRY = {}

def register_tool_to_registry(tool_name: str, tool_func):
    """Register a tool in the global registry for dynamic execution."""
    TOOL_REGISTRY[tool_name] = tool_func


def get_tool_registry() -> Dict[str, Any]:
    """Get the current tool registry. Ensures it's loaded."""
    if not TOOL_REGISTRY:
        # This shouldn't happen if initialize_server was called
        # but provides a safety net
        print("WARNING: Tool registry is empty. This should not happen in normal operation.")
    return TOOL_REGISTRY


# Meta-tool for operating the robot dynamically
# Note: This is registered manually in initialize_server() after all tools are loaded
async def operate_robot(
    tool_name: Optional[str] = None, 
    parameters: Optional[Dict[str, Any]] = None,
    commands: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Execute robot control tool(s) dynamically based on tools_index.json.
    
    This is a meta-tool that allows you to call any of the available robot control tools
    either as a single command or as a sequence of commands.
    
    Available tools (from tools_index.json):
    - get_robot_state: Get full robot state including all components
    - get_head_state: Get current head position and orientation
    - move_head: Move head to specific pose (params: x, y, z, roll, pitch, yaw, duration, speech)
    - reset_head: Return head to neutral position (params: speech)
    - nod_head: Make robot nod (params: duration, angle, speech)
    - shake_head: Make robot shake head (params: duration, angle, speech)
    - tilt_head: Tilt head left or right (params: direction, angle, duration, speech)
    - get_antennas_state: Get current antenna positions
    - move_antennas: Move antennas to specific positions (params: left, right, duration, speech)
    - reset_antennas: Return antennas to neutral position (params: speech)
    - turn_on_robot: Power on the robot (params: speech)
    - turn_off_robot: Power off the robot (params: speech)
    - get_power_state: Check if robot is powered on/off
    - stop_all_movements: Emergency stop all movements (params: speech)
    - express_emotion: Express emotion (params: emotion - happy/sad/curious/surprised/confused, speech)
    - look_at_direction: Look in a direction (params: direction - up/down/left/right/forward, duration, speech)
    - perform_gesture: Perform gesture (params: gesture - greeting/yes/no/thinking/celebration, speech)
    - get_health_status: Get overall health status
    
    Speech Parameter:
    Most action commands support an optional 'speech' parameter. When provided, the robot will
    speak the text using text-to-speech (TTS) while performing the action.
    
    Args:
        tool_name: Name of the tool to execute (for single command mode)
        parameters: Dictionary of parameters to pass to the tool (for single command mode)
        commands: List of command dictionaries for sequence mode. Each dict should have:
                  - "tool_name": Name of the tool to execute
                  - "parameters": Dictionary of parameters (optional)
    
    Returns:
        For single command: Result from the executed tool
        For sequence: Dictionary with results from all commands
        
    Examples:
        # Single command - Express happiness with speech
        operate_robot(tool_name="express_emotion", parameters={"emotion": "happy", "speech": "Hello! I'm so happy to see you!"})
        
        # Single command - Move head up with speech
        operate_robot(tool_name="move_head", parameters={"z": 10, "duration": 2.0, "speech": "Looking up!"})
        
        # Single command - Get robot state
        operate_robot(tool_name="get_robot_state")
        
        # Sequence of commands with speech
        operate_robot(commands=[
            {"tool_name": "perform_gesture", "parameters": {"gesture": "greeting", "speech": "Hello there!"}},
            {"tool_name": "nod_head", "parameters": {"duration": 2.0, "angle": 15, "speech": "Yes, I understand"}},
            {"tool_name": "move_antennas", "parameters": {"left": 30, "right": -30, "duration": 1.5}},
            {"tool_name": "look_at_direction", "parameters": {"direction": "left", "duration": 1.0}}
        ])
    """
    # Get the current tool registry
    registry = get_tool_registry()
    
    # Determine mode: sequence or single command
    if commands is not None:
        # Sequence mode
        if not isinstance(commands, list):
            return {
                "error": "commands parameter must be a list of command dictionaries",
                "status": "failed"
            }
        
        results = []
        failed_count = 0
        
        for idx, command in enumerate(commands):
            if not isinstance(command, dict):
                results.append({
                    "command_index": idx,
                    "error": "Each command must be a dictionary",
                    "status": "failed"
                })
                failed_count += 1
                continue
            
            cmd_tool_name = command.get("tool_name")
            cmd_parameters = command.get("parameters", {})
            
            if not cmd_tool_name:
                results.append({
                    "command_index": idx,
                    "error": "Missing 'tool_name' in command",
                    "status": "failed"
                })
                failed_count += 1
                continue
            
            # Check if tool exists
            if cmd_tool_name not in registry:
                available_tools = ", ".join(sorted(registry.keys()))
                results.append({
                    "command_index": idx,
                    "tool_name": cmd_tool_name,
                    "error": f"Tool '{cmd_tool_name}' not found",
                    "available_tools": available_tools,
                    "status": "failed"
                })
                failed_count += 1
                continue
            
            # Execute the command
            try:
                tool_func = registry[cmd_tool_name]
                result = await tool_func(**cmd_parameters)
                results.append({
                    "command_index": idx,
                    "tool": cmd_tool_name,
                    "parameters": cmd_parameters,
                    "result": result,
                    "status": "success"
                })
            except Exception as e:
                results.append({
                    "command_index": idx,
                    "tool": cmd_tool_name,
                    "parameters": cmd_parameters,
                    "error": str(e),
                    "status": "failed"
                })
                failed_count += 1
        
        # Automatically append get_robot_state at the end
        try:
            if "get_robot_state" in registry:
                tool_func = registry["get_robot_state"]
                state_result = await tool_func()
                results.append({
                    "command_index": len(commands),
                    "tool": "get_robot_state",
                    "parameters": {},
                    "result": state_result,
                    "status": "success",
                    "auto_appended": True
                })
        except Exception as e:
            results.append({
                "command_index": len(commands),
                "tool": "get_robot_state",
                "parameters": {},
                "error": str(e),
                "status": "failed",
                "auto_appended": True
            })
        
        return {
            "mode": "sequence",
            "total_commands": len(commands),
            "successful": len(commands) - failed_count,
            "failed": failed_count,
            "results": results,
            "status": "success" if failed_count == 0 else "partial" if failed_count < len(commands) else "failed"
        }
    
    elif tool_name is not None:
        # Single command mode (backward compatible)
        if parameters is None:
            parameters = {}
        
        # Check if tool exists in registry
        if tool_name not in registry:
            available_tools = ", ".join(sorted(registry.keys()))
            return {
                "error": f"Tool '{tool_name}' not found",
                "available_tools": available_tools,
                "registry_size": len(registry),
                "status": "failed"
            }
        
        try:
            # Execute the tool
            tool_func = registry[tool_name]
            result = await tool_func(**parameters)
            
            # Automatically get robot state after execution (unless already getting state)
            robot_state = None
            if tool_name != "get_robot_state" and "get_robot_state" in registry:
                try:
                    state_func = registry["get_robot_state"]
                    robot_state = await state_func()
                except Exception as state_error:
                    robot_state = {"error": str(state_error)}
            
            return {
                "tool": tool_name,
                "parameters": parameters,
                "result": result,
                "robot_state": robot_state,
                "status": "success"
            }
        except Exception as e:
            return {
                "tool": tool_name,
                "parameters": parameters,
                "error": str(e),
                "status": "failed"
            }
    
    else:
        return {
            "error": "Must provide either 'tool_name' for single command or 'commands' for sequence",
            "status": "failed"
        }


# Initialize and run

def initialize_server():
    """Initialize the server by loading all tools from the repository."""
    global tts_queue
    
    print("=" * 60)
    print("Reachy Mini MCP Server - Repository-Based Tool Loading")
    print("=" * 60)
    print(f"Tools repository path: {TOOLS_REPOSITORY_PATH}")
    print(f"Reachy daemon URL: {REACHY_BASE_URL}")
    print("-" * 60)
    
    # Initialize TTS queue
    try:
        model_path = os.environ.get("PIPER_MODEL")
        audio_device = os.environ.get("AUDIO_DEVICE", "sysdefault")
        tts_queue = AsyncTTSQueue(voice_model=model_path, audio_device=audio_device)
        print("✓ TTS queue initialized")
    except Exception as e:
        print(f"⚠️  TTS queue initialization failed: {e}")
        print("   Speech parameter will be ignored in commands")
        tts_queue = None
    
    # Register all tools from repository
    register_tools_from_repository()
    
    # Register ONLY the operate_robot meta-tool as an MCP tool
    # All other tools are loaded into the registry but not exposed as individual MCP tools
    mcp.tool()(operate_robot)
    print("✓ Registered MCP tool: operate_robot (meta-tool for all robot operations)")
    print(f"✓ Individual tools are available via operate_robot but not as separate MCP tools")
    
    print("=" * 60)
    print("Server initialized and ready!")
    print("=" * 60)


if __name__ == "__main__":
    # Initialize the server and load all tools BEFORE FastMCP starts
    initialize_server()
    
    # Run the MCP server
    mcp.run()
else:
    # If imported as a module, initialize immediately
    initialize_server()