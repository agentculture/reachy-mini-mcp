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
    python conversation_app.py
    
Requirements:
    - Hearing event emitter running (hearing_event_emitter.py)
    - vLLM server running on http://localhost:8100 with streaming support
"""

import asyncio
import json
import httpx
import traceback
import socket
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import deque
import logging

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for detailed logging
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
CHAT_COMPLETIONS_URL = "http://localhost:8100/v1/chat/completions"
MODEL_NAME = "RedHatAI/Llama-3.2-3B-Instruct-FP8"
SOCKET_PATH = os.getenv('SOCKET_PATH', '/tmp/reachy_sockets/hearing.sock')


class ConversationApp:
    """Conversation application with speech event integration."""
    
    def __init__(self):
        self.messages = []
        
        # Load the system prompt
        self.system_prompt = Path("agents/reachy/reachy.system.md").read_text()
        
        # Socket connection
        self.socket = None
        self.socket_buffer = ""
        
        # State tracking
        self.is_speaking = False
        self.current_speech_event = None
        self.processing_speech = False
        
        # Queues for parsed content
        self.speech_queue = deque()  # Queue of speech items (text in quotes)
        self.action_queue = deque()  # Queue of action items (text in **)
        
        # Parser state for streaming
        self.current_quote = ""
        self.current_action = ""
        self.in_quote = False
        self.in_action = False
        self._star_count = 0

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
    
    async def connect_to_hearing_service(self):
        """Connect to the hearing event emitter via Unix Domain Socket."""
        max_retries = 10
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Connecting to hearing service at {SOCKET_PATH} (attempt {attempt + 1}/{max_retries})")
                
                # Check if socket file exists
                if not os.path.exists(SOCKET_PATH):
                    logger.warning(f"Socket file does not exist: {SOCKET_PATH}")
                else:
                    logger.info(f"Socket file exists: {SOCKET_PATH}")
                    # Check file permissions
                    import stat
                    st = os.stat(SOCKET_PATH)
                    logger.info(f"Socket permissions: {oct(st.st_mode)}")
                
                self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.socket.connect(SOCKET_PATH)
                self.socket.setblocking(False)
                
                logger.info("✓ Connected to hearing service")
                logger.info(f"   Socket FD: {self.socket.fileno()}")
                
                # Try to get peer name (Unix sockets don't really have this, but try anyway)
                try:
                    peer = self.socket.getpeername()
                    logger.info(f"   Peer: {peer}")
                except:
                    logger.info(f"   (Unix socket, no peer name)")
                
                return
                
            except (FileNotFoundError, ConnectionRefusedError) as e:
                logger.warning(f"Connection failed: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                else:
                    raise RuntimeError(f"Failed to connect to hearing service after {max_retries} attempts")
            except Exception as e:
                logger.error(f"Unexpected error connecting to socket: {e}", exc_info=True)
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    raise
    
    async def listen_to_events(self):
        """Listen to events from the hearing service."""
        logger.info("Starting event listener...")
        logger.info(f"Socket file descriptor: {self.socket.fileno()}")
        logger.info(f"Socket is connected: {self.socket.getpeername() if hasattr(self.socket, 'getpeername') else 'unknown'}")
        
        event_count = 0
        last_data_time = asyncio.get_event_loop().time()
        
        while True:
            try:
                # Try to receive data (non-blocking)
                try:
                    #logger.debug("Attempting to receive data from socket...")
                    data = await asyncio.to_thread(self.socket.recv, 4096)
                    
                    if not data:
                        logger.warning("Socket closed by server (received empty data)")
                        break
                    
                    current_time = asyncio.get_event_loop().time()
                    time_since_last = current_time - last_data_time
                    last_data_time = current_time
                    
                    logger.debug(f"Received {len(data)} bytes from socket (time since last: {time_since_last:.2f}s)")
                    
                    # Add to buffer
                    self.socket_buffer += data.decode('utf-8')
                    logger.debug(f"Buffer size: {len(self.socket_buffer)} chars")
                    
                    # Process complete lines (events)
                    lines_processed = 0
                    while '\n' in self.socket_buffer:
                        line, self.socket_buffer = self.socket_buffer.split('\n', 1)
                        if line.strip():
                            lines_processed += 1
                            event_count += 1
                            logger.info(f"Processing event #{event_count} from buffer")
                            await self.handle_event(line)
                    
                    if lines_processed > 0:
                        logger.debug(f"Processed {lines_processed} line(s), remaining buffer: {len(self.socket_buffer)} chars")
                            
                except BlockingIOError:
                    # No data available, sleep briefly
                    #logger.debug("No data available (BlockingIOError), sleeping...")
                    await asyncio.sleep(0.1)
                except Exception as recv_error:
                    logger.error(f"Error receiving data: {recv_error}", exc_info=True)
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Error in event listener main loop: {e}", exc_info=True)
                await asyncio.sleep(1)
        logger.warning(f"Event listener stopped after processing {event_count} events")
        await asyncio.sleep(0.1)        
    
    async def handle_event(self, event_line: str):
        """Handle a received event."""
        try:
            logger.debug(f"Parsing event line: {event_line[:100]}...")
            event = json.loads(event_line)
            event_type = event.get("type")
            event_data = event.get("data", {})
            
            logger.info(f"📡 Received event: {event_type}")
            logger.debug(f"   Full event: {event}")
            logger.debug(f"   Data: {event_data}")
            
            if event_type == "speech_started":
                await self.on_speech_started(event_data)
            elif event_type == "speech_stopped":
                await self.on_speech_stopped(event_data)
            else:
                logger.warning(f"Unknown event type: {event_type}")
                logger.debug(f"   Full unknown event: {event}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse event JSON: {e}")
            logger.error(f"   Raw data: {event_line}")
        except Exception as e:
            logger.error(f"Error handling event: {e}", exc_info=True)
            logger.error(f"   Event line was: {event_line}")
    
    async def on_speech_started(self, data: Dict[str, Any]):
        """Handle speech started event."""
        event_number = data.get("event_number")
        timestamp = data.get("timestamp")
        
        logger.info(f"🎤 Speech started (Event #{event_number}) at {timestamp}")
        logger.debug(f"   Full data: {data}")
        
        # Store current speech event
        self.current_speech_event = {
            "event_number": event_number,
            "timestamp": timestamp,
            "start_time": timestamp
        }
        
        # User is speaking, Reachy should listen
        self.is_speaking = True
        logger.debug(f"   State updated: is_speaking={self.is_speaking}")
    
    async def on_speech_stopped(self, data: Dict[str, Any]):
        """Handle speech stopped event - trigger conversation processing."""
        event_number = data.get("event_number")
        duration = data.get("duration")
        timestamp = data.get("timestamp")
        
        logger.info(f"🔇 Speech stopped (Event #{event_number}) - Duration: {duration:.2f}s")
        logger.debug(f"   Full data: {data}")
        logger.debug(f"   Current state: is_speaking={self.is_speaking}, processing_speech={self.processing_speech}")
        
        # User finished speaking
        self.is_speaking = False
        
        # Prevent concurrent processing
        if self.processing_speech:
            logger.warning("Already processing speech, skipping this event")
            return
        
        # Process the speech event
        try:
            self.processing_speech = True
            logger.info(f"Starting speech processing for event #{event_number}")
            await self.process_speech_event(event_number, duration)
            logger.info(f"Completed speech processing for event #{event_number}")
        except Exception as e:
            logger.error(f"Error processing speech event: {e}", exc_info=True)
        finally:
            self.processing_speech = False
            logger.debug(f"   State reset: processing_speech={self.processing_speech}")
    
    async def process_speech_event(self, event_number: int, duration: float):
        """Process a complete speech event through the conversation system."""
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
    
    def parse_token(self, token: str):
        """
        Parse a token from the streaming response.
        Extracts quotes "..." as speech and **...** as actions.
        """
        for char in token:
            # Handle quote parsing
            if char == '"':
                if self.in_quote:
                    # End of quote - add to speech queue
                    if self.current_quote:
                        self.speech_queue.append(self.current_quote)
                        logger.info(f'� Speech: "{self.current_quote}"')
                    self.current_quote = ""
                    self.in_quote = False
                else:
                    # Start of quote
                    self.in_quote = True
            elif self.in_quote:
                self.current_quote += char
            
            # Handle action parsing (skip if inside quote)
            elif char == '*':
                if not hasattr(self, '_star_count'):
                    self._star_count = 0
                    
                self._star_count += 1
                
                if self.in_action:
                    # We're inside an action
                    if self._star_count == 2:
                        # Found closing **, end the action
                        if self.current_action:
                            self.action_queue.append(self.current_action)
                            logger.info(f'⚡ Action: **{self.current_action}**')
                        self.current_action = ""
                        self.in_action = False
                        self._star_count = 0
                else:
                    # Not in action yet
                    if self._star_count == 2:
                        # Found opening **, start action
                        self.in_action = True
                        self._star_count = 0
            else:
                # Reset star count if we see a non-star character
                if hasattr(self, '_star_count'):
                    self._star_count = 0
                    
                if self.in_action:
                    self.current_action += char
    
    async def chat_completion_stream(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int = 3000
    ):
        """Make a streaming chat completion request."""
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
                                        # Parse the token for quotes and actions
                                        self.parse_token(content)
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
        """Process a user message and return the assistant's response."""
        # Add user message to conversation
        self.messages.append({"role": "user", "content": user_message})
       
        logger.debug(f"Current history: {len(self.messages)} messages")

        # Reset parser state
        self.current_quote = ""
        self.current_action = ""
        self.in_quote = False
        self.in_action = False
        self._star_count = 0
        
        # Collect full response
        full_response = ""
        
        logger.info("🤖 Processing response...")
        
        # Stream the response
        async for token in self.chat_completion_stream(messages=self.messages):
            full_response += token
        
        # Add assistant response to conversation history
        self.messages.append({"role": "assistant", "content": full_response})
        
        logger.info(f"✓ Response complete ({len(self.speech_queue)} speech items, {len(self.action_queue)} action items)")
        
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
        await self.connect_to_hearing_service()
        logger.info("   ✓ Connection established")
        
        # Start event listener
        logger.info("Step 2: Starting event listener loop...")
        logger.info("👂 Listening for speech events...")
        logger.info("   (Waiting for events from hearing_event_emitter.py)")
        logger.info("")
        
        await self.listen_to_events()
        
        logger.warning("Event listener has stopped")
    
    async def cleanup(self):
        """Cleanup resources."""
        logger.info("🧹 Cleaning up...")
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        
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
