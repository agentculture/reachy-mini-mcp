# API Endpoint Fixes

## Problem
The MCP server was calling API endpoints that don't exist in the actual Reachy Mini daemon, resulting in 404 errors.

## Root Cause
The MCP server code was written for an older or different version of the Reachy Mini daemon API. The actual daemon uses different endpoint paths and request/response formats.

## Changes Made

### 1. Movement Endpoints
**Before:**
- `POST /api/goto` ❌

**After:**
- `POST /api/move/goto` ✅

**Affected Functions:**
- `move_head()`
- `reset_head()`
- `nod_head()`
- `shake_head()`
- `tilt_head()`
- `move_antennas()`
- `reset_antennas()`
- `express_emotion()`
- `look_at_direction()`
- `perform_gesture()`

**Changes:**
- Changed endpoint from `/api/goto` to `/api/move/goto`
- Changed payload field from `"head"` to `"head_pose"`
- Changed antenna format from `{"left": deg, "right": deg}` to `[rad_left, rad_right]` array with radians

### 2. Power Management Endpoints
**Before:**
- `POST /api/power/on` ❌
- `POST /api/power/off` ❌
- `GET /api/state/power` ❌

**After:**
- `POST /api/motors/set_mode/enabled` ✅
- `POST /api/motors/set_mode/disabled` ✅
- `GET /api/motors/status` ✅

**Affected Functions:**
- `turn_on_robot()` - now calls `/api/motors/set_mode/enabled`
- `turn_off_robot()` - now calls `/api/motors/set_mode/disabled`
- `get_power_state()` - now calls `/api/motors/status`

### 3. State Query Endpoints
**Before:**
- `GET /api/state/head` ❌
- `GET /api/state/antennas` ❌
- `GET /api/state/camera` ❌
- `GET /api/state/power` ❌

**After:**
- All use `GET /api/state/full` ✅ and extract relevant fields

**Affected Functions:**
- `get_head_state()` - extracts `head_pose` from full state
- `get_antennas_state()` - extracts `antennas_position` from full state
- `get_camera_state()` - returns placeholder (not available)
- `get_power_state()` - uses `/api/motors/status`

### 4. Safety & Health Endpoints
**Before:**
- `POST /api/stop` ❌
- `GET /api/health` ❌

**After:**
- `POST /api/motors/set_mode/disabled` ✅ (for emergency stop)
- `GET /api/daemon/status` ✅

**Affected Functions:**
- `stop_all_movements()` - now disables motors
- `get_health_status()` - now calls `/api/daemon/status`

### 5. Camera Endpoints
**Status:** Camera endpoints are not available in the current daemon API

**Affected Functions:**
- `get_camera_image()` - returns error message
- `get_camera_state()` - returns placeholder message

## Key Format Changes

### Antenna Positions
**Before:**
```json
{
  "antennas": {
    "left": 30,
    "right": -30
  }
}
```

**After:**
```json
{
  "antennas": [0.5236, -0.5236]
}
```
*(degrees converted to radians, object → array)*

### Head Pose Field
**Before:**
```json
{
  "head": {
    "x": 0, "y": 0, "z": 0,
    "roll": 0, "pitch": 0, "yaw": 0
  }
}
```

**After:**
```json
{
  "head_pose": {
    "x": 0, "y": 0, "z": 0,
    "roll": 0, "pitch": 0, "yaw": 0
  }
}
```

## Testing

Run the connection test to verify:
```bash
source .venv/bin/activate
python test_connection.py
```

Expected output:
```
✅ All tests passed! Daemon is running correctly.
```

## Breaking Changes for Users

### Antenna Control
The `move_antennas()` function now **requires both left and right values**. You can no longer specify just one antenna position. This is because the API requires an array of both values.

**Before (worked):**
```python
move_antennas(left=30)  # Worked - only moved left antenna
```

**After (required):**
```python
move_antennas(left=30, right=0)  # Both values required
```

### Camera Functions
Camera functions now return error messages instead of actual data, as the daemon API doesn't expose camera endpoints.

## Compatibility

✅ **Working:** Movement, power management, state queries, health status  
⚠️ **Limited:** Antenna control (requires both values)  
❌ **Not Available:** Camera image capture, camera state

## Next Steps

If you need camera functionality, you may need to:
1. Access the camera directly in Python using the Reachy SDK
2. Request camera endpoints be added to the daemon API
3. Implement a custom camera service

## Files Modified

1. `server.py` - All endpoint paths and payload formats updated
2. `test_connection.py` - Updated to test correct endpoints
3. `API_FIXES.md` - This documentation file (new)


