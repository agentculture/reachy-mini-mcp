"""
Example usage of the operate_robot meta-tool

This demonstrates how to use the operate_robot tool to dynamically
execute any of the available robot control tools.
"""

import asyncio
from server import operate_robot

async def main():
    """Run examples of using operate_robot."""
    
    print("=" * 60)
    print("Example: Using operate_robot meta-tool")
    print("=" * 60)
    
    # Example 1: Get robot state
    print("\n1. Getting robot state...")
    result = await operate_robot("get_robot_state")
    print(f"   Status: {result['status']}")
    
    # Example 2: Express emotion
    print("\n2. Expressing happiness...")
    result = await operate_robot("express_emotion", {"emotion": "happy"})
    print(f"   Status: {result['status']}")
    
    # Example 3: Move head with parameters
    print("\n3. Moving head up 10mm...")
    result = await operate_robot("move_head", {
        "z": 10,
        "duration": 2.0,
        "mm": True
    })
    print(f"   Status: {result['status']}")
    
    # Example 4: Perform gesture
    print("\n4. Performing greeting gesture...")
    result = await operate_robot("perform_gesture", {"gesture": "greeting"})
    print(f"   Status: {result['status']}")
    
    # Example 5: Error handling - invalid tool name
    print("\n5. Testing error handling (invalid tool)...")
    result = await operate_robot("invalid_tool_name")
    print(f"   Status: {result['status']}")
    print(f"   Error: {result.get('error')}")
    print(f"   Available tools count: {result.get('registry_size', 'N/A')}")
    
    print("\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())


