"""
Script for get_health_status tool.
Gets the overall health status of the robot.
"""


async def execute(make_request, _create_head_pose, _tts_queue, _params):
    """Execute the get_health_status tool."""
    return await make_request('GET', '/api/daemon/status')


