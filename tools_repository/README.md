# Reachy Mini Tools Repository

This directory contains the repository-based tool definitions for the Reachy Mini MCP Server. All tools are defined in JSON files and loaded dynamically, making the system extensible and customizable.

## Repository Structure

```
tools_repository/
├── tools_index.json          # Root file listing all available tools
├── SCHEMA.md                 # Documentation of the JSON schema
├── README.md                 # This file
├── *.json                    # Individual tool definition files
└── scripts/                  # Python scripts for complex tools
    ├── nod_head.py
    ├── shake_head.py
    ├── express_emotion.py
    └── perform_gesture.py
```

## How It Works

### 1. Tool Index (`tools_index.json`)

The root file that lists all available tools:

```json
{
  "schema_version": "1.0",
  "description": "Repository of dynamically loaded tools",
  "tools": [
    {
      "name": "tool_name",
      "enabled": true,
      "definition_file": "tool_name.json"
    }
  ]
}
```

### 2. Tool Definition Files

Each tool has its own JSON file defining:
- **Name**: Tool identifier
- **Description**: What the tool does
- **Parameters**: Required and optional parameters
- **Execution**: Inline code or script file

Example (`get_robot_state.json`):

```json
{
  "name": "get_robot_state",
  "description": "Get the current full state of the Reachy Mini robot",
  "parameters": {
    "required": [],
    "optional": []
  },
  "execution": {
    "type": "inline",
    "code": "return await make_request('GET', '/api/state/full')"
  }
}
```

### 3. Execution Types

#### Inline Code
Simple operations defined directly in JSON:
- Best for single API calls
- Can use helper functions: `make_request()`, `create_head_pose()`
- Access parameters via `params` dict

#### Script Files
Complex operations in separate Python files:
- Best for multi-step operations
- Define an `async def execute(make_request, create_head_pose, params)` function
- Located in `scripts/` directory

## Adding a New Tool

### Method 1: Simple Inline Tool

1. Create a new JSON file (e.g., `my_tool.json`):

```json
{
  "name": "my_tool",
  "description": "Description of what my tool does",
  "parameters": {
    "required": [
      {
        "name": "param1",
        "type": "string",
        "description": "First parameter"
      }
    ],
    "optional": [
      {
        "name": "param2",
        "type": "number",
        "default": 1.0,
        "description": "Second parameter"
      }
    ]
  },
  "execution": {
    "type": "inline",
    "code": "return await make_request('POST', '/api/endpoint', json_data={'key': params.get('param1')})"
  }
}
```

2. Add to `tools_index.json`:

```json
{
  "name": "my_tool",
  "enabled": true,
  "definition_file": "my_tool.json"
}
```

3. Restart the server - your tool is now available!

### Method 2: Complex Script-Based Tool

1. Create a script file in `scripts/` (e.g., `scripts/my_complex_tool.py`):

```python
"""Script for my complex tool."""
import asyncio

async def execute(make_request, create_head_pose, params):
    """
    Perform a complex operation.
    
    Args:
        make_request: Function to make HTTP requests
        create_head_pose: Function to create head pose
        params: Dictionary with all parameters
    """
    # Step 1
    await make_request("POST", "/api/endpoint1", json_data={...})
    await asyncio.sleep(1.0)
    
    # Step 2
    await make_request("POST", "/api/endpoint2", json_data={...})
    
    return {"status": "success"}
```

2. Create the JSON definition (`my_complex_tool.json`):

```json
{
  "name": "my_complex_tool",
  "description": "Perform a complex sequence of operations",
  "parameters": {
    "required": [
      {
        "name": "mode",
        "type": "string",
        "description": "Operation mode"
      }
    ],
    "optional": []
  },
  "execution": {
    "type": "script",
    "script_file": "my_complex_tool.py"
  }
}
```

3. Add to `tools_index.json` and restart the server.

## Modifying Existing Tools

To modify a tool's behavior:

1. Find its definition file in the repository
2. Edit the JSON file:
   - Update description
   - Add/remove/modify parameters
   - Change inline code or script reference
3. If using a script, edit the Python file in `scripts/`
4. Restart the server

## Disabling Tools

To temporarily disable a tool without deleting it:

1. Open `tools_index.json`
2. Set `"enabled": false` for the tool
3. Restart the server

The tool will not be loaded or available to clients.

## Testing Tools

Use the test script to validate your changes:

```bash
python test_repository.py
```

This verifies:
- Tool index is valid JSON
- All definition files exist and are valid
- Script files exist for script-based tools
- Required fields are present

## Available Helper Functions

When writing inline code or scripts, you have access to:

### `make_request(method, endpoint, json_data=None, params=None)`
Make HTTP requests to the Reachy daemon:
```python
await make_request("GET", "/api/state/full")
await make_request("POST", "/api/move/goto", json_data={"head_pose": pose, "duration": 2.0})
```

### `create_head_pose(x, y, z, roll, pitch, yaw, degrees=False, mm=False)`
Create head pose configurations:
```python
pose = create_head_pose(z=10, pitch=-15, degrees=True, mm=True)
```

### Standard Libraries
- `math`: Mathematical functions
- `asyncio`: Async operations (sleep, etc.)
- `httpx`: HTTP client (imported but `make_request` preferred)

## Benefits of Repository-Based Approach

✅ **Extensible**: Add new tools without modifying server code  
✅ **Customizable**: Easily adjust tool behavior by editing JSON  
✅ **Maintainable**: Each tool is isolated in its own file  
✅ **Versionable**: JSON files are easy to track in git  
✅ **Testable**: Validate structure with `test_repository.py`  
✅ **Shareable**: Export/import tool definitions easily  

## Migration from Hardcoded Tools

The original `server.py` had 18 hardcoded tools with `@mcp.tool()` decorators. These have all been migrated to the repository:

- ✅ 14 simple tools → inline code
- ✅ 4 complex tools → script files
- ✅ All functionality preserved
- ✅ Easier to extend and customize

## Troubleshooting

**Tool not loading?**
- Check `tools_index.json` has the tool listed with `"enabled": true`
- Verify the definition file exists and has valid JSON
- Run `python test_repository.py` to validate

**Script file errors?**
- Ensure script file exists in `scripts/` directory
- Check the `execute()` function signature is correct
- Verify async/await is used properly

**Parameters not working?**
- Check parameter names match between JSON and code
- Use `params.get('param_name')` to access parameters
- Remember to provide defaults for optional parameters

