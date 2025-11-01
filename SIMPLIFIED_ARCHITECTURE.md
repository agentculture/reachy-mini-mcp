# Simplified Architecture: Single MCP Tool

## Summary

The Reachy Mini MCP Server has been simplified to expose **only one MCP tool** called `operate_robot` that provides access to all 18 robot control operations.

## What Changed

### Before
- 18 individual MCP tools (get_robot_state, move_head, express_emotion, etc.)
- 1 meta-tool (operate_robot) that could call any of the 18 tools
- Total: 19 MCP tools exposed to clients

### After
- **1 MCP tool only**: `operate_robot`
- All 18 operations accessible through this single tool
- Simpler, more unified interface

## Technical Details

### What Was Modified

1. **server.py**:
   - Individual tools are NO LONGER registered as MCP tools
   - Tools are still loaded into `TOOL_REGISTRY` for `operate_robot` to use
   - Only `operate_robot` is registered with FastMCP's `@mcp.tool()` decorator
   - Updated print messages to clarify the new architecture

2. **README.md**:
   - Updated to emphasize single tool approach
   - Changed all examples to use `operate_robot("tool_name", {params})`
   - Reorganized documentation to make the unified interface clear

3. **Prompts**:
   - Updated control_prompt to show operate_robot usage
   - Updated safety_prompt to use operate_robot syntax

### What Stayed the Same

1. **All JSON definition files**: Unchanged - still needed by operate_robot
2. **tools_index.json**: Unchanged - all 18 tools still enabled
3. **Scripts in tools_repository/scripts/**: Unchanged
4. **Core functionality**: All operations work exactly the same

## Benefits

1. **Simpler Interface**: One tool to learn instead of 19
2. **Cleaner MCP Tool List**: Less clutter in MCP clients
3. **Easier to Document**: Single entry point for all operations
4. **Flexible**: Easy to add new operations without adding new MCP tools
5. **Unified Error Handling**: All operations go through one pathway

## Usage

All robot operations now use the same pattern:

```python
# Pattern: operate_robot("operation_name", {parameters})

# No parameters
operate_robot("get_robot_state")
operate_robot("turn_on_robot")

# With parameters
operate_robot("express_emotion", {"emotion": "happy"})
operate_robot("move_head", {"z": 10, "duration": 2.0})
operate_robot("look_at_direction", {"direction": "left", "duration": 1.5})
```

## Available Operations

All 18 operations from the original implementation:

### State & Control
- get_robot_state
- get_head_state
- get_antennas_state
- get_power_state
- get_health_status
- turn_on_robot
- turn_off_robot
- stop_all_movements

### Head Movement
- move_head
- reset_head
- nod_head
- shake_head
- tilt_head
- look_at_direction

### Antennas
- move_antennas
- reset_antennas

### Expressions
- express_emotion
- perform_gesture

## Verification

The server initialization shows:
```
✓ Loaded tool to registry: [18 tools listed]
✓ Successfully loaded 18 tools to registry
✓ Tool registry contains 18 tools available for operate_robot
✓ Registered MCP tool: operate_robot (meta-tool for all robot operations)
✓ Individual tools are available via operate_robot but not as separate MCP tools
```

## Migration Guide

If you were using the old direct tool calls, simply wrap them in `operate_robot`:

### Before
```python
get_robot_state()
move_head(z=10, duration=2.0)
express_emotion(emotion="happy")
```

### After
```python
operate_robot("get_robot_state")
operate_robot("move_head", {"z": 10, "duration": 2.0})
operate_robot("express_emotion", {"emotion": "happy"})
```

## Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│  MCP Client     │◄───────►│  FastMCP Server  │◄───────►│ Reachy Daemon   │
│  (Claude, etc)  │  stdio  │  (server.py)     │  HTTP   │  (localhost:8000)│
└─────────────────┘         └──────────────────┘         └─────────────────┘
                                      │                             │
                                      │                             ▼
                              ┌───────▼────────┐          ┌─────────────────┐
                              │ operate_robot  │          │  Reachy Mini    │
                              │   (1 MCP Tool) │          │  Robot/Sim      │
                              └───────┬────────┘          └─────────────────┘
                                      │
                              ┌───────▼────────┐
                              │ TOOL_REGISTRY  │
                              │  (18 tools)    │
                              └────────────────┘
                              │ get_robot_state│
                              │ move_head      │
                              │ express_emotion│
                              │ ...etc         │
                              └────────────────┘
```

## Files Modified

1. `/Users/ori.nachum/Git/reachy-mini-mcp/server.py`
   - Lines 252-256: Removed MCP tool registration for individual tools
   - Lines 263-264: Updated print messages
   - Lines 467-471: Updated meta-tool registration messaging
   - Lines 308-327: Updated control_prompt
   - Lines 330-349: Updated safety_prompt

2. `/Users/ori.nachum/Git/reachy-mini-mcp/README.md`
   - Lines 96-170: Restructured "Available MCP Tools" section
   - Lines 171-244: Updated all usage examples

## Testing

Run the server to verify:
```bash
cd /Users/ori.nachum/Git/reachy-mini-mcp
source .venv/bin/activate
python server.py
```

Expected output shows:
- 18 tools loaded to registry
- Only operate_robot registered as MCP tool
- Server ready to accept connections

## Rollback (if needed)

To restore individual MCP tools, modify `server.py` line 252:
```python
# Add back:
mcp.tool()(tool_func)
```

## Date

November 1, 2025

