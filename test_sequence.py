"""
Test script for the command sequence functionality.

This script tests both single command and sequence mode of the operate_robot function.
"""

import asyncio
import sys
from pathlib import Path

# Add the server to the path
sys.path.insert(0, str(Path(__file__).parent))

# Import after path is set
from server import operate_robot, initialize_server, TOOL_REGISTRY


async def test_single_command():
    """Test single command mode (backward compatible)."""
    print("\n" + "="*60)
    print("Test 1: Single Command Mode")
    print("="*60)
    
    # Test with a simple tool that should be in the registry
    result = await operate_robot(
        tool_name="get_robot_state",
        parameters={}
    )
    
    print(f"Result: {result}")
    assert result.get("status") in ["success", "failed"], "Should return a status"
    assert "tool" in result, "Should contain tool name"
    print("✓ Single command mode test passed")


async def test_sequence_empty():
    """Test sequence mode with empty list."""
    print("\n" + "="*60)
    print("Test 2: Empty Sequence")
    print("="*60)
    
    result = await operate_robot(commands=[])
    
    print(f"Result: {result}")
    assert result.get("mode") == "sequence", "Should be in sequence mode"
    assert result.get("total_commands") == 0, "Should have 0 commands"
    assert result.get("successful") == 0, "Should have 0 successful"
    assert result.get("status") == "success", "Empty sequence should succeed"
    print("✓ Empty sequence test passed")


async def test_sequence_single():
    """Test sequence mode with a single command."""
    print("\n" + "="*60)
    print("Test 3: Sequence with Single Command")
    print("="*60)
    
    result = await operate_robot(commands=[
        {"tool_name": "get_robot_state", "parameters": {}}
    ])
    
    print(f"Result: {result}")
    assert result.get("mode") == "sequence", "Should be in sequence mode"
    assert result.get("total_commands") == 1, "Should have 1 command"
    assert len(result.get("results", [])) == 1, "Should have 1 result"
    print("✓ Single command sequence test passed")


async def test_sequence_multiple():
    """Test sequence mode with multiple commands."""
    print("\n" + "="*60)
    print("Test 4: Sequence with Multiple Commands")
    print("="*60)
    
    result = await operate_robot(commands=[
        {"tool_name": "get_robot_state", "parameters": {}},
        {"tool_name": "get_power_state", "parameters": {}},
        {"tool_name": "get_head_state", "parameters": {}}
    ])
    
    print(f"Result: {result}")
    assert result.get("mode") == "sequence", "Should be in sequence mode"
    assert result.get("total_commands") == 3, "Should have 3 commands"
    assert len(result.get("results", [])) == 3, "Should have 3 results"
    
    # Check that all results have command_index
    for idx, cmd_result in enumerate(result.get("results", [])):
        assert cmd_result.get("command_index") == idx, f"Command {idx} should have correct index"
        assert "status" in cmd_result, f"Command {idx} should have status"
    
    print("✓ Multiple command sequence test passed")


async def test_sequence_with_invalid_tool():
    """Test sequence mode with an invalid tool name."""
    print("\n" + "="*60)
    print("Test 5: Sequence with Invalid Tool")
    print("="*60)
    
    result = await operate_robot(commands=[
        {"tool_name": "get_robot_state", "parameters": {}},
        {"tool_name": "invalid_tool_name", "parameters": {}},
        {"tool_name": "get_power_state", "parameters": {}}
    ])
    
    print(f"Result: {result}")
    assert result.get("mode") == "sequence", "Should be in sequence mode"
    assert result.get("total_commands") == 3, "Should have 3 commands"
    assert result.get("failed") >= 1, "Should have at least 1 failure"
    assert result.get("status") == "partial", "Should have partial status"
    
    # Check that the invalid command has error
    results = result.get("results", [])
    invalid_result = results[1]  # Second command (index 1)
    assert invalid_result.get("status") == "failed", "Invalid tool should fail"
    assert "error" in invalid_result, "Should have error message"
    
    print("✓ Invalid tool sequence test passed")


async def test_sequence_missing_tool_name():
    """Test sequence with missing tool_name."""
    print("\n" + "="*60)
    print("Test 6: Sequence with Missing tool_name")
    print("="*60)
    
    result = await operate_robot(commands=[
        {"parameters": {}}  # Missing tool_name
    ])
    
    print(f"Result: {result}")
    assert result.get("mode") == "sequence", "Should be in sequence mode"
    assert result.get("failed") == 1, "Should have 1 failure"
    
    cmd_result = result.get("results", [])[0]
    assert cmd_result.get("status") == "failed", "Should fail"
    assert "error" in cmd_result, "Should have error message"
    print("✓ Missing tool_name test passed")


async def test_no_parameters():
    """Test that providing neither tool_name nor commands fails."""
    print("\n" + "="*60)
    print("Test 7: No Parameters Provided")
    print("="*60)
    
    result = await operate_robot()
    
    print(f"Result: {result}")
    assert result.get("status") == "failed", "Should fail"
    assert "error" in result, "Should have error message"
    print("✓ No parameters test passed")


async def test_invalid_commands_type():
    """Test that commands must be a list."""
    print("\n" + "="*60)
    print("Test 8: Invalid Commands Type")
    print("="*60)
    
    result = await operate_robot(commands="not a list")
    
    print(f"Result: {result}")
    assert result.get("status") == "failed", "Should fail"
    assert "error" in result, "Should have error message"
    assert "list" in result.get("error", "").lower(), "Error should mention list"
    print("✓ Invalid commands type test passed")


async def test_sequence_example_from_user():
    """Test the exact example from the user's request."""
    print("\n" + "="*60)
    print("Test 9: User's Example Sequence")
    print("="*60)
    
    result = await operate_robot(commands=[
        {"tool_name": "perform_gesture", "parameters": {"gesture": "greeting"}},
        {"tool_name": "nod_head", "parameters": {"duration": 2.0, "angle": 15}},
        {"tool_name": "move_antennas", "parameters": {"left": 30, "right": -30, "duration": 1.5}},
        {"tool_name": "look_at_direction", "parameters": {"direction": "left", "duration": 1.0}}
    ])
    
    print(f"Result: {result}")
    assert result.get("mode") == "sequence", "Should be in sequence mode"
    assert result.get("total_commands") == 4, "Should have 4 commands"
    assert len(result.get("results", [])) == 4, "Should have 4 results"
    print("✓ User's example sequence test passed")


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("Command Sequence Functionality Tests")
    print("="*60)
    print(f"Tool registry size: {len(TOOL_REGISTRY)} tools")
    print("="*60)
    
    tests = [
        test_single_command,
        test_sequence_empty,
        test_sequence_single,
        test_sequence_multiple,
        test_sequence_with_invalid_tool,
        test_sequence_missing_tool_name,
        test_no_parameters,
        test_invalid_commands_type,
        test_sequence_example_from_user
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            await test()
            passed += 1
        except AssertionError as e:
            print(f"✗ Test failed: {test.__name__}")
            print(f"  Error: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ Test error: {test.__name__}")
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed == 0:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

