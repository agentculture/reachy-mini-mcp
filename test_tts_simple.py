#!/usr/bin/env python3
"""
Simple TTS test - speak a sentence immediately
"""

import asyncio
import time
from tts_queue import AsyncTTSQueue

async def main():
    print("=" * 70)
    print("Simple TTS Test")
    print("=" * 70)
    
    # Initialize TTS with auto-detected model and sysdefault device
    tts = AsyncTTSQueue(audio_device="sysdefault")
    
    # Test 1: Single quoted text
    print("\nTest 1: Single quoted text")
    await tts.enqueue_text('The robot says "Hello world"')
    await asyncio.sleep(5)
    
    # Test 2: Multiple quoted texts
    print("\nTest 2: Multiple quoted texts")
    await tts.enqueue_text('First I say "Hello" then I say "How are you today?"')
    await asyncio.sleep(10)
    
    # Test 3: Clear queue mid-playback
    print("\nTest 3: Queue clearing")
    await tts.enqueue_text('I will say "This is a long sentence that will be interrupted" but it will be cut off')
    await asyncio.sleep(1)
    print("Clearing queue now!")
    await tts.clear_queue()
    await asyncio.sleep(1)
    
    # Cleanup
    tts.cleanup()
    print("\n✓ All tests complete")

if __name__ == "__main__":
    asyncio.run(main())
