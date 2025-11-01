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
from fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("Reachy Mini Controller")

# Configuration
REACHY_BASE_URL = "http://localhost:8000"
TOOLS_REPOSITORY_PATH = Path(__file__).parent / "tools_repository"


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
            return await module.execute(make_request, create_head_pose, kwargs)
        
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

All robot operations are accessed through the operate_robot() tool:
1. Express emotions: operate_robot("express_emotion", {"emotion": "happy"})
2. Perform gestures: operate_robot("perform_gesture", {"gesture": "greeting"})
3. Move head: operate_robot("move_head", {"z": 10, "duration": 2.0})
4. Control antennas: operate_robot("move_antennas", {"left": 30, "right": -30})
5. Look in directions: operate_robot("look_at_direction", {"direction": "left"})

Always check the robot state first with operate_robot("get_robot_state") before issuing commands.
Remember to turn on the robot with operate_robot("turn_on_robot") before movement commands.
"""


@mcp.prompt()
def safety_prompt() -> str:
    """Safety guidelines for robot control."""
    return """
Reachy Mini Safety Guidelines:

1. Always check robot state before issuing movement commands using operate_robot("get_robot_state")
2. Use appropriate durations (typically 1-3 seconds) for smooth movements
3. Avoid extreme angles that might stress the motors
4. Use operate_robot("stop_all_movements") in case of unexpected behavior
5. Turn off the robot with operate_robot("turn_off_robot") when done
6. Monitor health_status periodically during extended use

Head Position Limits:
- Position offsets: typically ±20mm on x/y/z
- Rotation angles: ±45 degrees for safe operation

Antenna Limits:
- Typical range: -45 to 45 degrees
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
async def operate_robot(tool_name: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute any robot control tool dynamically based on tools_index.json.
    
    This is a meta-tool that allows you to call any of the available robot control tools
    by specifying the tool name and parameters.
    
    Available tools (from tools_index.json):
    - get_robot_state: Get full robot state including all components
    - get_head_state: Get current head position and orientation
    - move_head: Move head to specific pose (params: x, y, z, roll, pitch, yaw, duration)
    - reset_head: Return head to neutral position
    - nod_head: Make robot nod (params: duration, angle)
    - shake_head: Make robot shake head (params: duration, angle)
    - tilt_head: Tilt head left or right (params: direction, angle, duration)
    - get_antennas_state: Get current antenna positions
    - move_antennas: Move antennas to specific positions (params: left, right, duration)
    - reset_antennas: Return antennas to neutral position
    - turn_on_robot: Power on the robot
    - turn_off_robot: Power off the robot
    - get_power_state: Check if robot is powered on/off
    - stop_all_movements: Emergency stop all movements
    - express_emotion: Express emotion (params: emotion - happy/sad/curious/surprised/confused)
    - look_at_direction: Look in a direction (params: direction - up/down/left/right/forward, duration)
    - perform_gesture: Perform gesture (params: gesture - greeting/yes/no/thinking/celebration)
    - get_health_status: Get overall health status
    
    Args:
        tool_name: Name of the tool to execute (from the list above)
        parameters: Dictionary of parameters to pass to the tool (optional)
    
    Returns:
        Result from the executed tool
        
    Examples:
        # Express happiness
        operate_robot("express_emotion", {"emotion": "happy"})
        
        # Move head up
        operate_robot("move_head", {"z": 10, "duration": 2.0})
        
        # Get robot state
        operate_robot("get_robot_state")
        
        # Perform greeting gesture
        operate_robot("perform_gesture", {"gesture": "greeting"})
    """
    if parameters is None:
        parameters = {}
    
    # Get the current tool registry
    registry = get_tool_registry()
    
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
        return {
            "tool": tool_name,
            "parameters": parameters,
            "result": result,
            "status": "success"
        }
    except Exception as e:
        return {
            "tool": tool_name,
            "parameters": parameters,
            "error": str(e),
            "status": "failed"
        }


# Initialize and run

def initialize_server():
    """Initialize the server by loading all tools from the repository."""
    print("=" * 60)
    print("Reachy Mini MCP Server - Repository-Based Tool Loading")
    print("=" * 60)
    print(f"Tools repository path: {TOOLS_REPOSITORY_PATH}")
    print(f"Reachy daemon URL: {REACHY_BASE_URL}")
    print("-" * 60)
    
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
