"""
Script for turn_off_robot tool.
Turns off the robot's motors and deactivates systems.
"""


async def execute(make_request, create_head_pose, params):
    """Execute the turn_off_robot tool."""
    return await make_request('POST', '/api/motors/set_mode/disabled')


