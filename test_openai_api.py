#!/usr/bin/env python3
"""
Test script for OpenAI-compatible API server

This script tests the basic functionality of the OpenAI-compatible
robot control server.
"""

import asyncio
import httpx
import json
from typing import Dict, Any


ROBOT_SERVER_URL = "http://localhost:8100"


async def test_root_endpoint():
    """Test the root endpoint."""
    print("\n" + "=" * 60)
    print("Testing Root Endpoint")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{ROBOT_SERVER_URL}/")
            response.raise_for_status()
            data = response.json()
            print("✓ Root endpoint working")
            print(f"  API: {data.get('name')}")
            print(f"  Version: {data.get('version')}")
            print(f"  Endpoints: {list(data.get('endpoints', {}).keys())}")
            return True
        except Exception as e:
            print(f"✗ Root endpoint failed: {e}")
            return False


async def test_tools_endpoint():
    """Test the /tools endpoint."""
    print("\n" + "=" * 60)
    print("Testing /tools Endpoint")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{ROBOT_SERVER_URL}/tools")
            response.raise_for_status()
            data = response.json()
            tools = data.get("tools", [])
            
            print(f"✓ Found {len(tools)} tools")
            for tool in tools[:5]:  # Show first 5
                func = tool.get("function", {})
                print(f"  - {func.get('name')}: {func.get('description', '')[:50]}...")
            
            if len(tools) > 5:
                print(f"  ... and {len(tools) - 5} more")
            
            return True
        except Exception as e:
            print(f"✗ /tools endpoint failed: {e}")
            return False


async def test_execute_tool():
    """Test the /execute_tool endpoint."""
    print("\n" + "=" * 60)
    print("Testing /execute_tool Endpoint")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Test get_robot_state (safe, read-only operation)
            print("\nExecuting: get_robot_state")
            response = await client.post(
                f"{ROBOT_SERVER_URL}/execute_tool",
                json={
                    "tool_name": "get_robot_state",
                    "arguments": {}
                }
            )
            response.raise_for_status()
            result = response.json()
            
            print("✓ Tool executed successfully")
            print(f"  Status: {result.get('status', 'unknown')}")
            
            # Show some state info if available
            if "state" in result:
                state = result["state"]
                print(f"  Robot state keys: {list(state.keys())[:5]}")
            
            return True
        except Exception as e:
            print(f"✗ /execute_tool failed: {e}")
            return False


async def test_chat_completions():
    """Test the /v1/chat/completions endpoint."""
    print("\n" + "=" * 60)
    print("Testing /v1/chat/completions Endpoint")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Test simple chat
            print("\nSending: 'What is the robot status?'")
            response = await client.post(
                f"{ROBOT_SERVER_URL}/v1/chat/completions",
                json={
                    "model": "test-model",
                    "messages": [
                        {"role": "system", "content": "You are a robot control assistant."},
                        {"role": "user", "content": "What is the robot status?"}
                    ]
                }
            )
            response.raise_for_status()
            result = response.json()
            
            print("✓ Chat completion successful")
            choice = result.get("choices", [{}])[0]
            message = choice.get("message", {})
            print(f"  Role: {message.get('role')}")
            print(f"  Content: {message.get('content', '')[:100]}")
            print(f"  Finish reason: {choice.get('finish_reason')}")
            
            # Test with tool calling
            print("\nSending: 'Turn on the robot' (should trigger tool call)")
            response = await client.post(
                f"{ROBOT_SERVER_URL}/v1/chat/completions",
                json={
                    "model": "test-model",
                    "messages": [
                        {"role": "system", "content": "You are a robot control assistant."},
                        {"role": "user", "content": "Turn on the robot"}
                    ],
                    "tools": [
                        {
                            "type": "function",
                            "function": {
                                "name": "turn_on_robot",
                                "description": "Turn on the robot",
                                "parameters": {"type": "object", "properties": {}}
                            }
                        }
                    ]
                }
            )
            response.raise_for_status()
            result = response.json()
            
            choice = result.get("choices", [{}])[0]
            message = choice.get("message", {})
            
            if message.get("tool_calls"):
                print("✓ Tool call detected")
                tool_call = message["tool_calls"][0]
                func = tool_call.get("function", {})
                print(f"  Tool: {func.get('name')}")
                print(f"  Arguments: {func.get('arguments')}")
            else:
                print("⚠️  No tool call detected (expected for simple keyword matching)")
            
            return True
        except Exception as e:
            print(f"✗ /v1/chat/completions failed: {e}")
            import traceback
            traceback.print_exc()
            return False


async def test_invalid_tool():
    """Test error handling with invalid tool."""
    print("\n" + "=" * 60)
    print("Testing Error Handling")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        try:
            print("\nTrying to execute non-existent tool")
            response = await client.post(
                f"{ROBOT_SERVER_URL}/execute_tool",
                json={
                    "tool_name": "non_existent_tool",
                    "arguments": {}
                }
            )
            
            if response.status_code == 404:
                print("✓ Correctly returned 404 for invalid tool")
                error_detail = response.json().get("detail", "")
                print(f"  Error: {error_detail[:100]}")
                return True
            else:
                print(f"✗ Unexpected status code: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"✗ Error handling test failed: {e}")
            return False


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("OpenAI-Compatible API Server Test Suite")
    print("=" * 60)
    print("\nMake sure:")
    print("  1. Reachy Mini daemon is running (reachy-mini-daemon)")
    print("  2. Robot control server is running (python server_openai.py)")
    print("=" * 60)
    
    # Wait a moment for user to read
    await asyncio.sleep(2)
    
    results = []
    
    # Run tests
    results.append(("Root Endpoint", await test_root_endpoint()))
    results.append(("Tools Endpoint", await test_tools_endpoint()))
    results.append(("Execute Tool", await test_execute_tool()))
    results.append(("Chat Completions", await test_chat_completions()))
    results.append(("Error Handling", await test_invalid_tool()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    print("\n" + "=" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60 + "\n")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
