# Command Sequence Feature

The `operate_robot` tool now supports executing multiple commands in a single call, enabling complex robot behaviors through command sequences.

## Overview

The enhanced `operate_robot` function can operate in two modes:
1. **Single Command Mode** - Execute one command at a time (backward compatible)
2. **Sequence Mode** - Execute multiple commands sequentially

## Usage

### Single Command Mode (Backward Compatible)

Execute a single robot command:

```python
operate_robot(
    tool_name="perform_gesture",
    parameters={"gesture": "greeting"}
)
```

### Sequence Mode

Execute multiple commands in sequence:

```python
operate_robot(commands=[
    {"tool_name": "perform_gesture", "parameters": {"gesture": "greeting"}},
    {"tool_name": "nod_head", "parameters": {"duration": 2.0, "angle": 15}},
    {"tool_name": "move_antennas", "parameters": {"left": 30, "right": -30, "duration": 1.5}},
    {"tool_name": "look_at_direction", "parameters": {"direction": "left", "duration": 1.0}}
])
```

## Parameters

### Single Command Mode
- `tool_name` (str): Name of the tool to execute
- `parameters` (dict, optional): Dictionary of parameters for the tool

### Sequence Mode
- `commands` (list): List of command dictionaries, where each dictionary contains:
  - `tool_name` (str): Name of the tool to execute
  - `parameters` (dict, optional): Dictionary of parameters for the tool

## Return Values

### Single Command Mode Response
```json
{
    "tool": "perform_gesture",
    "parameters": {"gesture": "greeting"},
    "result": { ... },
    "status": "success"
}
```

### Sequence Mode Response
```json
{
    "mode": "sequence",
    "total_commands": 4,
    "successful": 4,
    "failed": 0,
    "status": "success",
    "results": [
        {
            "command_index": 0,
            "tool": "perform_gesture",
            "parameters": {"gesture": "greeting"},
            "result": { ... },
            "status": "success"
        },
        {
            "command_index": 1,
            "tool": "nod_head",
            "parameters": {"duration": 2.0, "angle": 15},
            "result": { ... },
            "status": "success"
        },
        ...
    ]
}
```

### Status Values
- `"success"` - All commands executed successfully
- `"partial"` - Some commands succeeded, some failed
- `"failed"` - All commands failed or invalid input

## Example Use Cases

### 1. Greeting Routine

Perform a complete greeting sequence:

```python
operate_robot(commands=[
    {"tool_name": "express_emotion", "parameters": {"emotion": "happy"}},
    {"tool_name": "perform_gesture", "parameters": {"gesture": "greeting"}},
    {"tool_name": "nod_head", "parameters": {"duration": 1.5, "angle": 10}},
    {"tool_name": "reset_head", "parameters": {}}
])
```

### 2. Expressive Behavior

Show curiosity and look around:

```python
operate_robot(commands=[
    {"tool_name": "express_emotion", "parameters": {"emotion": "curious"}},
    {"tool_name": "move_antennas", "parameters": {"left": 30, "right": 30, "duration": 1.0}},
    {"tool_name": "look_at_direction", "parameters": {"direction": "left", "duration": 1.0}},
    {"tool_name": "look_at_direction", "parameters": {"direction": "right", "duration": 1.0}},
    {"tool_name": "look_at_direction", "parameters": {"direction": "forward", "duration": 0.5}}
])
```

### 3. Yes/No Response

Perform a "yes" gesture with confirmation:

```python
operate_robot(commands=[
    {"tool_name": "perform_gesture", "parameters": {"gesture": "yes"}},
    {"tool_name": "nod_head", "parameters": {"duration": 1.0, "angle": 15}},
    {"tool_name": "express_emotion", "parameters": {"emotion": "happy"}}
])
```

### 4. Initialization Sequence

Turn on the robot and prepare for operation:

```python
operate_robot(commands=[
    {"tool_name": "turn_on_robot", "parameters": {}},
    {"tool_name": "reset_head", "parameters": {}},
    {"tool_name": "reset_antennas", "parameters": {}},
    {"tool_name": "get_robot_state", "parameters": {}}
])
```

### 5. Shutdown Sequence

Safely shutdown the robot:

```python
operate_robot(commands=[
    {"tool_name": "reset_head", "parameters": {}},
    {"tool_name": "reset_antennas", "parameters": {}},
    {"tool_name": "express_emotion", "parameters": {"emotion": "sad"}},
    {"tool_name": "turn_off_robot", "parameters": {}}
])
```

## Error Handling

### Partial Failures

If some commands in a sequence fail, the function will:
1. Continue executing remaining commands
2. Return a `"partial"` status
3. Include error details for each failed command

Example response with partial failure:

```json
{
    "mode": "sequence",
    "total_commands": 3,
    "successful": 2,
    "failed": 1,
    "status": "partial",
    "results": [
        {
            "command_index": 0,
            "tool": "perform_gesture",
            "parameters": {"gesture": "greeting"},
            "result": { ... },
            "status": "success"
        },
        {
            "command_index": 1,
            "tool": "invalid_tool",
            "error": "Tool 'invalid_tool' not found",
            "status": "failed"
        },
        {
            "command_index": 2,
            "tool": "nod_head",
            "parameters": {"duration": 2.0},
            "result": { ... },
            "status": "success"
        }
    ]
}
```

### Invalid Input

If the input is invalid (e.g., `commands` is not a list), the function returns an error:

```json
{
    "error": "commands parameter must be a list of command dictionaries",
    "status": "failed"
}
```

## Best Practices

### 1. Timing and Duration

Ensure commands have appropriate durations to complete before the next command starts:

```python
# Good: Adequate durations for smooth transitions
operate_robot(commands=[
    {"tool_name": "move_head", "parameters": {"z": 10, "duration": 2.0}},
    {"tool_name": "nod_head", "parameters": {"duration": 1.5, "angle": 10}}
])

# Avoid: Very short durations may cause jerky movements
operate_robot(commands=[
    {"tool_name": "move_head", "parameters": {"z": 10, "duration": 0.1}},
    {"tool_name": "nod_head", "parameters": {"duration": 0.1, "angle": 10}}
])
```

### 2. State Checking

Include state checks in your sequences when needed:

```python
operate_robot(commands=[
    {"tool_name": "get_power_state", "parameters": {}},
    {"tool_name": "get_robot_state", "parameters": {}},
    # ... rest of commands
])
```

### 3. Reset Positions

Reset to neutral positions between major movements:

```python
operate_robot(commands=[
    {"tool_name": "perform_gesture", "parameters": {"gesture": "greeting"}},
    {"tool_name": "reset_head", "parameters": {}},
    {"tool_name": "reset_antennas", "parameters": {}},
    {"tool_name": "perform_gesture", "parameters": {"gesture": "celebration"}}
])
```

### 4. Emergency Stop

In case of unexpected behavior, you can still call:

```python
operate_robot(tool_name="stop_all_movements")
```

### 5. Monitoring Results

Always check the results array to verify command execution:

```python
result = operate_robot(commands=[...])

if result["status"] == "success":
    print("All commands executed successfully")
elif result["status"] == "partial":
    print(f"Some commands failed: {result['failed']} out of {result['total_commands']}")
    # Check individual results for details
    for cmd_result in result["results"]:
        if cmd_result["status"] == "failed":
            print(f"Failed: {cmd_result['tool']} - {cmd_result.get('error')}")
```

## Limitations

1. **Sequential Execution**: Commands are executed sequentially, not in parallel
2. **No Rollback**: If a command fails, previous commands are not rolled back
3. **Continuation**: Failed commands don't stop the sequence; remaining commands still execute
4. **Timeout**: Very long sequences may timeout; consider breaking into smaller sequences

## Available Tools

All tools available in single command mode are available in sequence mode:

- `get_robot_state` - Get full robot state
- `get_head_state` - Get head position and orientation
- `move_head` - Move head to specific pose
- `reset_head` - Return head to neutral position
- `nod_head` - Make robot nod
- `shake_head` - Make robot shake head
- `tilt_head` - Tilt head left or right
- `get_antennas_state` - Get antenna positions
- `move_antennas` - Move antennas to positions
- `reset_antennas` - Return antennas to neutral
- `turn_on_robot` - Power on the robot
- `turn_off_robot` - Power off the robot
- `get_power_state` - Check power state
- `stop_all_movements` - Emergency stop
- `express_emotion` - Express emotion (happy/sad/curious/surprised/confused)
- `look_at_direction` - Look in direction (up/down/left/right/forward)
- `perform_gesture` - Perform gesture (greeting/yes/no/thinking/celebration)
- `get_health_status` - Get health status

## Examples

See `example_sequence_commands.py` for complete working examples demonstrating:
- Single command execution
- Basic command sequences
- Complex greeting routines
- Error handling

## Migration Guide

### From Single Commands

If you're currently using multiple individual calls:

**Before:**
```python
await operate_robot("perform_gesture", {"gesture": "greeting"})
await operate_robot("nod_head", {"duration": 2.0, "angle": 15})
await operate_robot("reset_head", {})
```

**After:**
```python
await operate_robot(commands=[
    {"tool_name": "perform_gesture", "parameters": {"gesture": "greeting"}},
    {"tool_name": "nod_head", "parameters": {"duration": 2.0, "angle": 15}},
    {"tool_name": "reset_head", "parameters": {}}
])
```

### Backward Compatibility

All existing single command calls remain fully functional:

```python
# This still works exactly as before
operate_robot(tool_name="express_emotion", parameters={"emotion": "happy"})
```

## Technical Details

- Commands are executed sequentially in the order provided
- Each command is awaited before the next one starts
- The function returns after all commands complete or fail
- Individual command errors don't stop the sequence execution
- Results include detailed status for each command

