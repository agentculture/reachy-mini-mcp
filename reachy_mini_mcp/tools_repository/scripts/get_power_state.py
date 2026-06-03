"""
Script for get_power_state tool.
Gets the current power state of the robot.
"""


async def execute(make_request, _create_head_pose, _tts_queue, _params):
    """Execute the get_power_state tool."""
    return await make_request('GET', '/api/motors/status')


