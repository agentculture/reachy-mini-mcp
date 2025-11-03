"""
Script for stop_all_movements tool.
Emergency stop - immediately halts all robot movements.
"""


async def execute(make_request, create_head_pose, params):
    """Execute the stop_all_movements tool."""
    return await make_request('POST', '/api/motors/set_mode/disabled')


