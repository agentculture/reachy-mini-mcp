"""
Script for turn_on_robot tool.
Turns on the robot's motors and activates all systems.
"""


async def execute(make_request, create_head_pose, params):
    """Execute the turn_on_robot tool."""
    return await make_request('POST', '/api/motors/set_mode/enabled')


