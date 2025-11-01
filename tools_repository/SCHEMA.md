# Tool Definition Schema

This document describes the schema for defining tools in the repository.

## Tool Definition JSON Structure

```json
{
  "name": "tool_name",
  "description": "Brief description of what the tool does",
  "parameters": {
    "required": [
      {
        "name": "param_name",
        "type": "string|number|boolean|array|object",
        "description": "Parameter description"
      }
    ],
    "optional": [
      {
        "name": "param_name",
        "type": "string|number|boolean|array|object",
        "default": "default_value",
        "description": "Parameter description"
      }
    ]
  },
  "execution": {
    "type": "inline|script",
    "code": "inline Python code (if type=inline)",
    "script_file": "path/to/script.py (if type=script)"
  }
}
```

## Execution Types

### Inline Code
For simple operations, you can define the code directly in the JSON:
- `type`: "inline"
- `code`: Python code that uses available variables and helper functions
- Available context:
  - `params`: Dict of all parameters
  - `make_request()`: Helper function for HTTP requests
  - `create_head_pose()`: Helper function for creating head poses
  - `asyncio`, `math`, `httpx` modules

### Script File
For complex operations, reference a separate Python file:
- `type`: "script"
- `script_file`: Relative path to script file from tools_repository/scripts/
- The script should define an async `execute(**params)` function
- Returns Dict[str, Any]

## Examples

### Simple GET Request (Inline)
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

### Complex Operation (Script)
```json
{
  "name": "express_emotion",
  "description": "Make the robot express an emotion using head and antenna movements",
  "parameters": {
    "required": [
      {
        "name": "emotion",
        "type": "string",
        "description": "One of: happy, sad, curious, surprised, confused, neutral"
      }
    ],
    "optional": []
  },
  "execution": {
    "type": "script",
    "script_file": "express_emotion.py"
  }
}
```

