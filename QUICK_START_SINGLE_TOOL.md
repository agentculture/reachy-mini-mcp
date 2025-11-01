# Quick Start: Single Tool Interface

## Overview

The Reachy Mini MCP Server now exposes **one MCP tool** that provides access to all robot control operations.

## The One Tool: `operate_robot`

```python
operate_robot(tool_name: str, parameters: Optional[Dict] = None)
```

## Quick Examples

### Power Control
```python
# Turn robot on
operate_robot("turn_on_robot")

# Turn robot off
operate_robot("turn_off_robot")

# Check power state
operate_robot("get_power_state")
```

### Get Robot State
```python
# Get full state
operate_robot("get_robot_state")

# Get head state only
operate_robot("get_head_state")

# Get antenna state only
operate_robot("get_antennas_state")
```

### Move Head
```python
# Move head up 10mm
operate_robot("move_head", {"z": 10, "duration": 2.0})

# Tilt head with roll
operate_robot("move_head", {"roll": 15, "duration": 2.0})

# Move in 3D space
operate_robot("move_head", {
    "x": 5,
    "y": 0,
    "z": 10,
    "roll": 15,
    "pitch": 0,
    "yaw": 10,
    "duration": 2.5
})

# Reset to neutral
operate_robot("reset_head")
```

### Head Gestures
```python
# Nod (yes)
operate_robot("nod_head", {"angle": 15, "duration": 1.0})

# Shake (no)
operate_robot("shake_head", {"angle": 20, "duration": 1.0})

# Tilt
operate_robot("tilt_head", {"direction": "left", "angle": 15, "duration": 2.0})
```

### Look Around
```python
# Look up
operate_robot("look_at_direction", {"direction": "up", "duration": 1.5})

# Look left
operate_robot("look_at_direction", {"direction": "left", "duration": 1.5})

# Look forward
operate_robot("look_at_direction", {"direction": "forward", "duration": 1.5})
```

### Antennas
```python
# Move both antennas
operate_robot("move_antennas", {"left": 30, "right": -30, "duration": 1.0})

# Move left antenna only
operate_robot("move_antennas", {"left": 45, "duration": 1.0})

# Reset to neutral
operate_robot("reset_antennas")
```

### Emotions
```python
# Happy
operate_robot("express_emotion", {"emotion": "happy"})

# Sad
operate_robot("express_emotion", {"emotion": "sad"})

# Curious
operate_robot("express_emotion", {"emotion": "curious"})

# Surprised
operate_robot("express_emotion", {"emotion": "surprised"})

# Confused
operate_robot("express_emotion", {"emotion": "confused"})
```

### Gestures
```python
# Wave hello
operate_robot("perform_gesture", {"gesture": "greeting"})

# Nod yes
operate_robot("perform_gesture", {"gesture": "yes"})

# Shake no
operate_robot("perform_gesture", {"gesture": "no"})

# Thinking
operate_robot("perform_gesture", {"gesture": "thinking"})

# Celebration
operate_robot("perform_gesture", {"gesture": "celebration"})
```

### Emergency Stop
```python
# Stop all movements immediately
operate_robot("stop_all_movements")
```

### Health Check
```python
# Get health status
operate_robot("get_health_status")
```

## Complete Interaction Example

```python
# 1. Turn on robot
operate_robot("turn_on_robot")

# 2. Check it's ready
state = operate_robot("get_robot_state")

# 3. Greet the user
operate_robot("perform_gesture", {"gesture": "greeting"})

# 4. Look around
operate_robot("look_at_direction", {"direction": "left", "duration": 1.5})
operate_robot("look_at_direction", {"direction": "right", "duration": 1.5})
operate_robot("look_at_direction", {"direction": "forward", "duration": 1.0})

# 5. Express happiness
operate_robot("express_emotion", {"emotion": "happy"})

# 6. Celebrate
operate_robot("perform_gesture", {"gesture": "celebration"})

# 7. Return to neutral
operate_robot("reset_head")
operate_robot("reset_antennas")

# 8. Turn off
operate_robot("turn_off_robot")
```

## All Available Operations

### State & Control (8)
- `get_robot_state` - Full robot state
- `get_head_state` - Head position and orientation
- `get_antennas_state` - Antenna positions
- `get_power_state` - Power on/off status
- `get_health_status` - System health
- `turn_on_robot` - Power on
- `turn_off_robot` - Power off
- `stop_all_movements` - Emergency stop

### Head Movement (6)
- `move_head` - Move to specific pose
- `reset_head` - Return to neutral
- `nod_head` - Nod gesture
- `shake_head` - Shake gesture
- `tilt_head` - Tilt left/right
- `look_at_direction` - Look up/down/left/right

### Antennas (2)
- `move_antennas` - Move to positions
- `reset_antennas` - Return to neutral

### Expressions (2)
- `express_emotion` - Show emotion
- `perform_gesture` - Perform gesture

**Total: 18 operations, all via one tool!**

## Error Handling

If you specify an invalid operation name:

```python
result = operate_robot("invalid_operation")

# Returns:
{
    "error": "Tool 'invalid_operation' not found",
    "available_tools": "express_emotion, get_antennas_state, ...",
    "registry_size": 18,
    "status": "failed"
}
```

## Tips

1. **Always turn on first**: `operate_robot("turn_on_robot")`
2. **Use appropriate durations**: 1-3 seconds for smooth movements
3. **Check state first**: `operate_robot("get_robot_state")`
4. **Emergency stop available**: `operate_robot("stop_all_movements")`
5. **Turn off when done**: `operate_robot("turn_off_robot")`

## Migration from Old Interface

### Before (19 separate tools)
```python
get_robot_state()
move_head(z=10, duration=2.0)
express_emotion(emotion="happy")
```

### After (1 unified tool)
```python
operate_robot("get_robot_state")
operate_robot("move_head", {"z": 10, "duration": 2.0})
operate_robot("express_emotion", {"emotion": "happy"})
```

## More Information

- See `README.md` for full documentation
- See `SIMPLIFIED_ARCHITECTURE.md` for technical details
- All JSON definitions remain in `tools_repository/`

