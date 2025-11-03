"""
Example demonstrating sequence mode in operate_robot.

This script shows how to use the new command sequence functionality
to execute multiple robot operations in a single call.
"""

import asyncio
import httpx
import json

MCP_SERVER_URL = "http://localhost:8000"  # Adjust if your server is on a different port


async def execute_single_command():
    """Example of executing a single command (backward compatible)."""
    print("\n" + "="*60)
    print("Example 1: Single Command (Backward Compatible)")
    print("="*60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Single command: Get robot state
        response = await client.post(
            f"{MCP_SERVER_URL}/operate_robot",
            json={
                "tool_name": "get_robot_state",
                "parameters": {}
            }
        )
        result = response.json()
        print(f"Single command result:\n{json.dumps(result, indent=2)}")


async def execute_command_sequence():
    """Example of executing a sequence of commands."""
    print("\n" + "="*60)
    print("Example 2: Command Sequence")
    print("="*60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Define a sequence of commands
        commands = [
            {
                "tool_name": "perform_gesture",
                "parameters": {"gesture": "greeting"}
            },
            {
                "tool_name": "nod_head",
                "parameters": {"duration": 2.0, "angle": 15}
            },
            {
                "tool_name": "move_antennas",
                "parameters": {"left": 30, "right": -30, "duration": 1.5}
            },
            {
                "tool_name": "look_at_direction",
                "parameters": {"direction": "left", "duration": 1.0}
            }
        ]
        
        # Execute the sequence
        response = await client.post(
            f"{MCP_SERVER_URL}/operate_robot",
            json={"commands": commands}
        )
        result = response.json()
        
        print(f"Sequence execution result:")
        print(f"  Mode: {result.get('mode')}")
        print(f"  Total commands: {result.get('total_commands')}")
        print(f"  Successful: {result.get('successful')}")
        print(f"  Failed: {result.get('failed')}")
        print(f"  Overall status: {result.get('status')}")
        print(f"\nDetailed results:")
        for cmd_result in result.get('results', []):
            print(f"  Command {cmd_result.get('command_index')}: {cmd_result.get('tool')} - {cmd_result.get('status')}")
            if cmd_result.get('error'):
                print(f"    Error: {cmd_result.get('error')}")


async def execute_greeting_sequence():
    """Example of a complete greeting sequence."""
    print("\n" + "="*60)
    print("Example 3: Complete Greeting Routine")
    print("="*60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # A more complex sequence demonstrating a greeting routine
        commands = [
            # First check if robot is on
            {"tool_name": "get_power_state", "parameters": {}},
            
            # Express happiness
            {"tool_name": "express_emotion", "parameters": {"emotion": "happy"}},
            
            # Perform greeting gesture
            {"tool_name": "perform_gesture", "parameters": {"gesture": "greeting"}},
            
            # Nod to acknowledge
            {"tool_name": "nod_head", "parameters": {"duration": 1.5, "angle": 10}},
            
            # Move antennas in excitement
            {"tool_name": "move_antennas", "parameters": {"left": 45, "right": 45, "duration": 1.0}},
            
            # Look around
            {"tool_name": "look_at_direction", "parameters": {"direction": "left", "duration": 0.8}},
            {"tool_name": "look_at_direction", "parameters": {"direction": "right", "duration": 0.8}},
            {"tool_name": "look_at_direction", "parameters": {"direction": "forward", "duration": 0.5}},
            
            # Reset to neutral position
            {"tool_name": "reset_head", "parameters": {}},
            {"tool_name": "reset_antennas", "parameters": {}}
        ]
        
        # Execute the greeting sequence
        response = await client.post(
            f"{MCP_SERVER_URL}/operate_robot",
            json={"commands": commands}
        )
        result = response.json()
        
        print(f"Greeting sequence result:")
        print(f"  Total commands executed: {result.get('total_commands')}")
        print(f"  Successful: {result.get('successful')}")
        print(f"  Failed: {result.get('failed')}")
        print(f"  Overall status: {result.get('status')}")


async def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("Reachy Mini Command Sequence Examples")
    print("="*60)
    print("\nNote: Make sure the Reachy Mini MCP server is running")
    print("and the robot daemon is accessible.\n")
    
    try:
        # Example 1: Single command (backward compatible)
        await execute_single_command()
        
        # Wait a bit between examples
        await asyncio.sleep(1)
        
        # Example 2: Basic command sequence
        await execute_command_sequence()
        
        # Wait a bit between examples
        await asyncio.sleep(1)
        
        # Example 3: Complete greeting routine
        await execute_greeting_sequence()
        
        print("\n" + "="*60)
        print("All examples completed!")
        print("="*60)
        
    except httpx.ConnectError:
        print("\nError: Could not connect to the MCP server.")
        print("Please ensure the server is running with: python server.py")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

