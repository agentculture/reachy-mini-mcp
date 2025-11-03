"""
Script for reset_head tool.
Resets the robot's head to the default neutral position.
"""


async def execute(make_request, create_head_pose, params):
    """Execute the reset_head tool."""
    pose = create_head_pose()
    payload = {'head_pose': pose, 'duration': 2.0}
    return await make_request('POST', '/api/move/goto', json_data=payload)


