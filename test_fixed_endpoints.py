"""
Test script to verify the fixed API endpoints work correctly.
"""

import asyncio
import httpx

REACHY_BASE_URL = "http://localhost:8000"

async def test_endpoints():
    """Test the corrected API endpoints."""
    print("=" * 60)
    print("Testing Fixed API Endpoints")
    print("=" * 60)
    print()
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Test 1: Get full state
        print("1️⃣  Testing GET /api/state/full...")
        try:
            response = await client.get(f"{REACHY_BASE_URL}/api/state/full")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ SUCCESS - Got state with keys: {list(data.keys())}")
            else:
                print(f"   ❌ FAILED - Status: {response.status_code}")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
        print()
        
        # Test 2: Get motor status
        print("2️⃣  Testing GET /api/motors/status...")
        try:
            response = await client.get(f"{REACHY_BASE_URL}/api/motors/status")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ SUCCESS - Motor mode: {data.get('mode')}")
            else:
                print(f"   ❌ FAILED - Status: {response.status_code}")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
        print()
        
        # Test 3: Get daemon status
        print("3️⃣  Testing GET /api/daemon/status...")
        try:
            response = await client.get(f"{REACHY_BASE_URL}/api/daemon/status")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ SUCCESS - Daemon state: {data.get('state')}")
            else:
                print(f"   ❌ FAILED - Status: {response.status_code}")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
        print()
        
        # Test 4: Test movement endpoint (goto)
        print("4️⃣  Testing POST /api/move/goto (head movement)...")
        try:
            payload = {
                "head_pose": {
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0,
                    "roll": 0.0,
                    "pitch": 0.0,
                    "yaw": 0.0
                },
                "duration": 1.0
            }
            response = await client.post(
                f"{REACHY_BASE_URL}/api/move/goto",
                json=payload
            )
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ SUCCESS - Movement UUID: {data.get('uuid', 'N/A')}")
            else:
                print(f"   ❌ FAILED - Status: {response.status_code}")
                print(f"      Response: {response.text}")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
        print()
        
        # Test 5: Test antenna movement
        print("5️⃣  Testing POST /api/move/goto (antenna movement)...")
        try:
            import math
            payload = {
                "antennas": [math.radians(0), math.radians(0)],
                "duration": 1.0
            }
            response = await client.post(
                f"{REACHY_BASE_URL}/api/move/goto",
                json=payload
            )
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ SUCCESS - Movement UUID: {data.get('uuid', 'N/A')}")
            else:
                print(f"   ❌ FAILED - Status: {response.status_code}")
                print(f"      Response: {response.text}")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
        print()
        
        # Test 6: Test motor control
        print("6️⃣  Testing POST /api/motors/set_mode/enabled...")
        try:
            response = await client.post(f"{REACHY_BASE_URL}/api/motors/set_mode/enabled")
            if response.status_code == 200:
                print(f"   ✅ SUCCESS - Motors enabled")
            else:
                print(f"   ❌ FAILED - Status: {response.status_code}")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
        print()
    
    print("=" * 60)
    print("✅ All endpoint tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_endpoints())


