"""
Script for get_robot_state tool.
Gets the current full state of the Reachy Mini robot.
"""


async def execute(make_request, _create_head_pose, _tts_queue, _params):
    """Execute the get_robot_state tool."""
    return await make_request('GET', '/api/state/full')


