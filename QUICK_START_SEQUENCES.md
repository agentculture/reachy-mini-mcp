# Quick Start: Command Sequences

This guide will get you started with the new command sequence feature in under 5 minutes.

## What is Command Sequence?

Instead of calling `operate_robot` multiple times for complex behaviors, you can now execute multiple commands in a single call.

## Basic Usage

### Before (Multiple Calls)
```python
operate_robot("perform_gesture", {"gesture": "greeting"})
operate_robot("nod_head", {"duration": 2.0, "angle": 15})
operate_robot("reset_head", {})
```

### After (Single Sequence Call)
```python
operate_robot(commands=[
    {"tool_name": "perform_gesture", "parameters": {"gesture": "greeting"}},
    {"tool_name": "nod_head", "parameters": {"duration": 2.0, "angle": 15}},
    {"tool_name": "reset_head", "parameters": {}}
])
```

## Copy-Paste Examples

### 1. Greeting Sequence
```python
operate_robot(commands=[
    {"tool_name": "express_emotion", "parameters": {"emotion": "happy"}},
    {"tool_name": "perform_gesture", "parameters": {"gesture": "greeting"}},
    {"tool_name": "nod_head", "parameters": {"duration": 1.5, "angle": 10}},
    {"tool_name": "reset_head", "parameters": {}}
])
```

### 2. Look Around (Curious Behavior)
```python
operate_robot(commands=[
    {"tool_name": "express_emotion", "parameters": {"emotion": "curious"}},
    {"tool_name": "move_antennas", "parameters": {"left": 30, "right": 30, "duration": 1.0}},
    {"tool_name": "look_at_direction", "parameters": {"direction": "left", "duration": 1.0}},
    {"tool_name": "look_at_direction", "parameters": {"direction": "right", "duration": 1.0}},
    {"tool_name": "look_at_direction", "parameters": {"direction": "forward", "duration": 0.5}}
])
```

### 3. Robot Startup
```python
operate_robot(commands=[
    {"tool_name": "turn_on_robot", "parameters": {}},
    {"tool_name": "reset_head", "parameters": {}},
    {"tool_name": "reset_antennas", "parameters": {}},
    {"tool_name": "express_emotion", "parameters": {"emotion": "happy"}},
    {"tool_name": "get_robot_state", "parameters": {}}
])
```

### 4. Robot Shutdown
```python
operate_robot(commands=[
    {"tool_name": "express_emotion", "parameters": {"emotion": "sad"}},
    {"tool_name": "reset_head", "parameters": {}},
    {"tool_name": "reset_antennas", "parameters": {}},
    {"tool_name": "turn_off_robot", "parameters": {}}
])
```

### 5. Yes Response with Enthusiasm
```python
operate_robot(commands=[
    {"tool_name": "perform_gesture", "parameters": {"gesture": "yes"}},
    {"tool_name": "nod_head", "parameters": {"duration": 1.0, "angle": 15}},
    {"tool_name": "express_emotion", "parameters": {"emotion": "happy"}},
    {"tool_name": "move_antennas", "parameters": {"left": 45, "right": 45, "duration": 1.0}}
])
```

### 6. No Response with Head Shake
```python
operate_robot(commands=[
    {"tool_name": "perform_gesture", "parameters": {"gesture": "no"}},
    {"tool_name": "shake_head", "parameters": {"duration": 1.5, "angle": 20}},
    {"tool_name": "express_emotion", "parameters": {"emotion": "sad"}}
])
```

### 7. Thinking Gesture
```python
operate_robot(commands=[
    {"tool_name": "express_emotion", "parameters": {"emotion": "curious"}},
    {"tool_name": "perform_gesture", "parameters": {"gesture": "thinking"}},
    {"tool_name": "look_at_direction", "parameters": {"direction": "up", "duration": 1.5}},
    {"tool_name": "tilt_head", "parameters": {"direction": "left", "angle": 15, "duration": 1.0}}
])
```

### 8. Celebration
```python
operate_robot(commands=[
    {"tool_name": "express_emotion", "parameters": {"emotion": "happy"}},
    {"tool_name": "perform_gesture", "parameters": {"gesture": "celebration"}},
    {"tool_name": "move_antennas", "parameters": {"left": 45, "right": -45, "duration": 0.5}},
    {"tool_name": "move_antennas", "parameters": {"left": -45, "right": 45, "duration": 0.5}},
    {"tool_name": "reset_antennas", "parameters": {}}
])
```

## Understanding the Response

### Successful Sequence
```json
{
    "mode": "sequence",
    "total_commands": 3,
    "successful": 3,
    "failed": 0,
    "status": "success",
    "results": [...]
}
```

### Partial Success (Some Failed)
```json
{
    "mode": "sequence",
    "total_commands": 3,
    "successful": 2,
    "failed": 1,
    "status": "partial",
    "results": [...]
}
```

### Checking Individual Results
```python
result = operate_robot(commands=[...])

# Check overall status
if result["status"] == "success":
    print("All commands succeeded!")
elif result["status"] == "partial":
    print(f"{result['failed']} commands failed")
    
# Check individual commands
for cmd in result["results"]:
    if cmd["status"] == "failed":
        print(f"Failed: {cmd['tool']} - {cmd.get('error')}")
```

## Available Tools

All these tools can be used in sequences:

**Movement:**
- `move_head` - Move head to specific pose
- `reset_head` - Return head to neutral
- `nod_head` - Nod head
- `shake_head` - Shake head
- `tilt_head` - Tilt head
- `move_antennas` - Move antennas
- `reset_antennas` - Reset antennas
- `look_at_direction` - Look in direction

**Emotions & Gestures:**
- `express_emotion` - Express emotion (happy/sad/curious/surprised/confused)
- `perform_gesture` - Perform gesture (greeting/yes/no/thinking/celebration)

**State & Control:**
- `get_robot_state` - Get full state
- `get_head_state` - Get head state
- `get_antennas_state` - Get antenna state
- `get_power_state` - Get power state
- `get_health_status` - Get health status
- `turn_on_robot` - Power on
- `turn_off_robot` - Power off
- `stop_all_movements` - Emergency stop

## Tips & Best Practices

### 1. Add Appropriate Durations
```python
# Good - movements have time to complete
{"tool_name": "move_head", "parameters": {"z": 10, "duration": 2.0}}

# Not ideal - may be too fast
{"tool_name": "move_head", "parameters": {"z": 10, "duration": 0.1}}
```

### 2. Reset Between Major Actions
```python
operate_robot(commands=[
    {"tool_name": "perform_gesture", "parameters": {"gesture": "greeting"}},
    {"tool_name": "reset_head", "parameters": {}},      # Reset before next action
    {"tool_name": "perform_gesture", "parameters": {"gesture": "celebration"}}
])
```

### 3. Check State at Start
```python
operate_robot(commands=[
    {"tool_name": "get_power_state", "parameters": {}},  # Check if on
    {"tool_name": "get_robot_state", "parameters": {}},  # Get current state
    # ... rest of commands
])
```

### 4. End with Neutral Position
```python
operate_robot(commands=[
    # ... your commands
    {"tool_name": "reset_head", "parameters": {}},
    {"tool_name": "reset_antennas", "parameters": {}}
])
```

## Testing Your Sequence

Run the example script to see sequences in action:

```bash
python example_sequence_commands.py
```

Run the test suite to verify everything works:

```bash
python test_sequence.py
```

## Need More Help?

- **Full Documentation**: See [SEQUENCE_COMMANDS.md](SEQUENCE_COMMANDS.md)
- **Implementation Details**: See [SEQUENCE_FEATURE_SUMMARY.md](SEQUENCE_FEATURE_SUMMARY.md)
- **General Usage**: See [README.md](README.md)

## Command Template

Copy this template to create your own sequences:

```python
operate_robot(commands=[
    {"tool_name": "TOOL_NAME", "parameters": {"param1": "value1"}},
    {"tool_name": "TOOL_NAME", "parameters": {"param1": "value1", "param2": 2.0}},
    {"tool_name": "TOOL_NAME", "parameters": {}},
])
```

Replace `TOOL_NAME` with any available tool and fill in the appropriate parameters!

## That's It!

You're now ready to create complex robot behaviors with command sequences. Start with the copy-paste examples above and customize them for your needs!

Happy robot controlling! 🤖

