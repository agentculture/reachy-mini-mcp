#!/usr/bin/env python3
"""
Conversation Application with Speech Event Integration

This application listens to speech events from the hearing_event_emitter service
and processes them through the vLLM streaming chat system.

Instead of accepting text input from the user, this app responds to speech
detection events emitted via Unix Domain Socket.

Key features:
1. Listens to speech_started/speech_stopped events
2. Processes speech events through vLLM streaming chat completion
3. Parses responses for quotes "..." (speech) and **...** (actions)
4. Queues speech and actions for separate processing
5. Automatic conversation flow based on speech detection

Output format:
- Text in quotes "..." -> Speech queue (for TTS)
- Text in **...** -> Action queue (for movement)

Usage:
    python -m conversation_app.app
    # or from root
    python conversation_app.py
    
Requirements:
    - Hearing event emitter running (hearing_event_emitter.py)
    - vLLM server running on http://localhost:8100 with streaming support
"""

import asyncio
import json
import httpx
import traceback
import os
from pathlib import Path
from typing import List, Dict, Any
import logging

from .event_handler import EventHandler
from .conversation_parser import ConversationParser

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for detailed logging
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
CHAT_COMPLETIONS_URL = "http://localhost:8100/v1/chat/completions"
MODEL_NAME = "RedHatAI/Llama-3.2-3B-Instruct-FP8"


class ConversationApp:
    """Conversation application with speech event integration."""
    
    def __init__(self, socket_path: str = None):
        """
        Initialize the conversation application.
        
        Args:
            socket_path: Path to the Unix Domain Socket for hearing events
        """
        self.messages = []
        
        # Load the system prompt
        self.system_prompt = Path("agents/reachy/reachy.system.md").read_text()
        
        # Initialize components
        self.event_handler = EventHandler(socket_path)
        self.parser = ConversationParser()
        
        # Set up event callbacks
        self.event_handler.set_speech_started_callback(self.on_speech_started)
        self.event_handler.set_speech_stopped_callback(self.on_speech_stopped)

    async def initialize(self):
        """Initialize the application."""
        logger.info("=" * 70)
        logger.info("Initializing Conversation App")
        logger.info("=" * 70)
        
        # Initialize conversation with system prompt
        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        
        logger.info("✓ App initialized")
        logger.info("=" * 70)
    
    async def on_speech_started(self, data: Dict[str, Any]):
        """
        Callback for speech started events.
        
        Args:
            data: Event data containing event_number, timestamp, etc.
        """
        # Additional processing can be added here
        # The EventHandler already logs the event
        pass
    
    async def on_speech_stopped(self, data: Dict[str, Any]):
        """
        Callback for speech stopped events - trigger conversation processing.
        
        Args:
            data: Event data containing event_number, duration, timestamp, etc.
        """
        event_number = data.get("event_number")
        duration = data.get("duration")
        
        logger.info(f"💭 Processing speech event #{event_number}")
        
        # Create a user message representing the speech event
        # In a real system, this would be transcribed speech
        # For now, we'll create a generic message indicating user spoke
        user_message = f"[User spoke for {duration:.1f} seconds in speech event #{event_number}]"
        
        # For a real implementation, you would:
        # 1. Get the audio file saved by hearing_event_emitter
        # 2. Transcribe it using Whisper or similar
        # 3. Use the transcribed text as user_message
        
        # Since we don't have transcription yet, we'll use a placeholder approach:
        # Acknowledge the user spoke and ask Reachy to respond
        user_message = "Hello, I just said something to you."
        
        logger.info(f"👤 User (simulated): {user_message}")
        
        # Process through conversation system
        response = await self.process_message(user_message)
        
        logger.info(f"🤖 Reachy: {response}")
        logger.info(f"✓ Response complete ({self.parser.speech_count()} speech items, {self.parser.action_count()} action items)")
    
    async def chat_completion_stream(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int = 3000
    ):
        """
        Make a streaming chat completion request.
        
        Args:
            messages: Conversation history
            max_tokens: Maximum tokens to generate
            
        Yields:
            Content tokens from the streaming response
        """
        payload = {
            "model": MODEL_NAME,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.3,
            "stream": True
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                async with client.stream("POST", CHAT_COMPLETIONS_URL, json=payload) as response:
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]  # Remove "data: " prefix
                            
                            if data_str == "[DONE]":
                                break
                            
                            try:
                                data = json.loads(data_str)
                                choices = data.get("choices", [])
                                
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    
                                    if content:
                                        yield content
                                        
                            except json.JSONDecodeError:
                                continue
                                
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error: {e}")
                logger.error(f"Response: {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Error during streaming chat completion: {e}")
                raise
    
    async def process_message(self, user_message: str) -> str:
        """
        Process a user message and return the assistant's response.
        
        Args:
            user_message: The user's message text
            
        Returns:
            The assistant's complete response
        """
        # Add user message to conversation
        self.messages.append({"role": "user", "content": user_message})
       
        logger.debug(f"Current history: {len(self.messages)} messages")

        # Reset parser state
        self.parser.reset()
        
        # Collect full response
        full_response = ""
        
        logger.info("🤖 Processing response...")
        
        # Stream the response
        async for token in self.chat_completion_stream(messages=self.messages):
            full_response += token
            # Parse the token for quotes and actions
            self.parser.parse_token(token)
        
        # Add assistant response to conversation history
        self.messages.append({"role": "assistant", "content": full_response})
        
        return full_response
    
    async def run(self):
        """Run the conversation application."""
        logger.info("=" * 70)
        logger.info("Conversation Application with Speech Events")
        logger.info("=" * 70)
        logger.info("")
        logger.info("This app will:")
        logger.info("  1. Connect to hearing event emitter")
        logger.info("  2. Listen for speech events")
        logger.info("  3. Process speech through vLLM streaming chat")
        logger.info("  4. Parse responses into quotes and actions")
        logger.info("=" * 70)
        logger.info("")
        
        # Connect to hearing service
        logger.info("Step 1: Connecting to hearing service...")
        await self.event_handler.connect()
        logger.info("   ✓ Connection established")
        
        # Start event listener
        logger.info("Step 2: Starting event listener loop...")
        logger.info("👂 Listening for speech events...")
        logger.info("   (Waiting for events from hearing_event_emitter.py)")
        logger.info("")
        
        await self.event_handler.listen()
        
        logger.warning("Event listener has stopped")
    
    async def cleanup(self):
        """Cleanup resources."""
        logger.info("🧹 Cleaning up...")
        
        self.event_handler.close()
        
        logger.info("   ✓ Cleanup complete")


async def main():
    """Main function."""
    logger.info("=" * 70)
    logger.info("Starting Conversation Application")
    logger.info("=" * 70)
    logger.info("")
    logger.info("Make sure:")
    logger.info("  - Hearing event emitter is running")
    logger.info("  - vLLM server is running on http://localhost:8100")
    logger.info("=" * 70)
    logger.info("")
    
    app = ConversationApp()
    
    try:
        # Initialize app
        await app.initialize()
        
        # Run conversation app
        await app.run()
        
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
        traceback.print_exc()
    finally:
        await app.cleanup()
    
    logger.info("\n✅ Done!\n")


if __name__ == "__main__":
    asyncio.run(main())
