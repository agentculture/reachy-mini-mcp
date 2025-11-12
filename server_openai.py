"""
Reachy Mini OpenAI-Compatible API Server

A standard OpenAI-compatible API server for controlling the Reachy Mini robot.
This server provides:
1. GET /tools - List available tools in OpenAI format
2. POST /execute_tool - Execute a tool with given arguments
3. POST /v1/chat/completions - Full OpenAI-compatible chat completions endpoint

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
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from tts_queue import AsyncTTSQueue
import uvicorn

# Load environment variables from .env file
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Reachy Mini OpenAI-Compatible API",
    description="OpenAI-compatible API for controlling Reachy Mini robot",
    version="1.0.0"
)

# Configuration
REACHY_BASE_URL = "http://localhost:8000"
TOOLS_REPOSITORY_PATH = Path(__file__).parent / "tools_repository"

# TTS Queue (initialized in startup)
tts_queue = None

# Tool registry
TOOL_REGISTRY = {}


# Pydantic models for API

class ToolExecutionRequest(BaseModel):
    """Request model for tool execution."""
    tool_name: str = Field(..., description="Name of the tool to execute")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool")


class Message(BaseModel):
    """Chat message model."""
    role: str = Field(..., description="Role: system, user, assistant, or tool")
    content: Optional[str] = Field(None, description="Message content")
    name: Optional[str] = Field(None, description="Name of the function (for tool role)")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="Tool calls made by assistant")
    tool_call_id: Optional[str] = Field(None, description="ID of the tool call (for tool role)")


class ChatCompletionRequest(BaseModel):
    """Chat completion request model."""
    model: str = Field(..., description="Model to use")
    messages: List[Message] = Field(..., description="List of messages")
    tools: Optional[List[Dict[str, Any]]] = Field(None, description="Available tools")
    tool_choice: Optional[str] = Field("auto", description="Tool choice strategy")
    temperature: Optional[float] = Field(0.7, description="Sampling temperature")
    max_tokens: Optional[int] = Field(3000, description="Maximum tokens to generate")


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
    """Create a head pose configuration for Reachy Mini."""
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


def convert_tool_to_openai_format(tool_def: Dict[str, Any]) -> Dict[str, Any]:
    """Convert tool definition to OpenAI function calling format."""
    # Build parameters schema
    properties = {}
    required = []
    
    for param in tool_def.get("parameters", {}).get("required", []):
        param_name = param["name"]
        properties[param_name] = {
            "type": param["type"],
            "description": param.get("description", "")
        }
        if param.get("enum"):
            properties[param_name]["enum"] = param["enum"]
        required.append(param_name)
    
    for param in tool_def.get("parameters", {}).get("optional", []):
        param_name = param["name"]
        properties[param_name] = {
            "type": param["type"],
            "description": param.get("description", "")
        }
        if param.get("enum"):
            properties[param_name]["enum"] = param["enum"]
    
    return {
        "type": "function",
        "function": {
            "name": tool_def["name"],
            "description": tool_def["description"],
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    }


def create_tool_function(tool_def: Dict[str, Any]):
    """Create a tool function from a tool definition."""
    execution = tool_def.get("execution", {})
    exec_type = execution.get("type")
    
    if exec_type == "script":
        # Load the script module
        script_file = execution.get("script_file")
        module = load_script_module(script_file)
        
        async def tool_func_impl(**kwargs):
            # Call the execute function from the script
            return await module.execute(make_request, create_head_pose, tts_queue, kwargs)
        
        return tool_func_impl
    
    else:
        raise ValueError(f"Unknown execution type: {exec_type}")


def register_tools_from_repository():
    """Load and register all tools from the repository."""
    try:
        index = load_tool_index()
        openai_tools = []
        
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
                
                # Register in tool registry
                TOOL_REGISTRY[tool_name] = {
                    "function": tool_func,
                    "definition": tool_def
                }
                
                # Convert to OpenAI format
                openai_tool = convert_tool_to_openai_format(tool_def)
                openai_tools.append(openai_tool)
                
                print(f"✓ Loaded tool: {tool_name}")
                
            except Exception as e:
                import traceback
                print(f"✗ Failed to register tool {tool_name}: {e}")
                print(f"  Traceback: {traceback.format_exc()}")
        
        print(f"\n✓ Successfully loaded {len(openai_tools)} tools")
        return openai_tools
        
    except Exception as e:
        print(f"✗ Failed to load tools from repository: {e}")
        raise


# API Endpoints

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Reachy Mini OpenAI-Compatible API",
        "version": "1.0.0",
        "endpoints": {
            "tools": "/tools",
            "execute_tool": "/execute_tool",
            "chat_completions": "/v1/chat/completions"
        }
    }


@app.get("/tools")
async def get_tools():
    """Get all available tools in OpenAI format."""
    tools = []
    for tool_name, tool_data in TOOL_REGISTRY.items():
        tool_def = tool_data["definition"]
        openai_tool = convert_tool_to_openai_format(tool_def)
        tools.append(openai_tool)
    
    return {"tools": tools}


@app.post("/execute_tool")
async def execute_tool(request: ToolExecutionRequest):
    """Execute a tool with given arguments."""
    tool_name = request.tool_name
    arguments = request.arguments
    
    if tool_name not in TOOL_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{tool_name}' not found. Available tools: {list(TOOL_REGISTRY.keys())}"
        )
    
    try:
        tool_func = TOOL_REGISTRY[tool_name]["function"]
        result = await tool_func(**arguments)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error executing tool: {str(e)}"
        )


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """
    OpenAI-compatible chat completions endpoint.
    
    This endpoint processes chat messages and can execute tools when requested.
    It mimics OpenAI's API behavior for tool calling.
    """
    messages = [msg.dict(exclude_none=True) for msg in request.messages]
    
    # Get the last user message
    last_user_message = None
    for msg in reversed(messages):
        if msg["role"] == "user":
            last_user_message = msg["content"]
            break
    
    if not last_user_message:
        raise HTTPException(status_code=400, detail="No user message found")
    
    # Simple response generation (you can integrate with an actual LLM here)
    # For now, we'll check if the message requests a tool and execute it
    
    # Check if tools are available and if the message seems to request an action
    if request.tools:
        # Simple keyword-based tool selection (in production, use an LLM)
        selected_tool = None
        tool_args = {}
        
        # Example: detect "turn on" -> turn_on_robot
        if "turn on" in last_user_message.lower():
            selected_tool = "turn_on_robot"
        elif "turn off" in last_user_message.lower():
            selected_tool = "turn_off_robot"
        elif "nod" in last_user_message.lower():
            selected_tool = "nod_head"
        elif "shake" in last_user_message.lower():
            selected_tool = "shake_head"
        elif "state" in last_user_message.lower() or "status" in last_user_message.lower():
            selected_tool = "get_robot_state"
        
        if selected_tool and selected_tool in TOOL_REGISTRY:
            # Create tool call response
            tool_call_id = f"call_{asyncio.get_event_loop().time()}"
            
            response = {
                "id": f"chatcmpl-{asyncio.get_event_loop().time()}",
                "object": "chat.completion",
                "created": int(asyncio.get_event_loop().time()),
                "model": request.model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": tool_call_id,
                            "type": "function",
                            "function": {
                                "name": selected_tool,
                                "arguments": json.dumps(tool_args)
                            }
                        }]
                    },
                    "finish_reason": "tool_calls"
                }],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0
                }
            }
            
            return response
    
    # Default text response
    response_text = "I'm a robot control assistant. I can help you control the Reachy Mini robot. What would you like me to do?"
    
    response = {
        "id": f"chatcmpl-{asyncio.get_event_loop().time()}",
        "object": "chat.completion",
        "created": int(asyncio.get_event_loop().time()),
        "model": request.model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": response_text
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
    }
    
    return response


# Startup and shutdown events

@app.on_event("startup")
async def startup_event():
    """Initialize server on startup."""
    global tts_queue
    
    print("=" * 60)
    print("Reachy Mini OpenAI-Compatible API Server")
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
    
    print("=" * 60)
    print("Server initialized and ready!")
    print("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    if tts_queue:
        tts_queue.cleanup()
    print("Server shutdown complete")


if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8100,
        log_level="info"
    )
