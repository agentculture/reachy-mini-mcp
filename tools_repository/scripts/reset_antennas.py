"""
Script for reset_antennas tool.
Resets both antennas to their neutral position (0 degrees).
"""


async def execute(make_request, create_head_pose, params):
    """Execute the reset_antennas tool."""
    payload = {'antennas': [0.0, 0.0], 'duration': 2.0}
    return await make_request('POST', '/api/move/goto', json_data=payload)


