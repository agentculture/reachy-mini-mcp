#!/usr/bin/env python3
"""
Conversation Application with Speech Event Integration

This application listens to speech events from the hearing_event_emitter service
and processes them through the vLLM chat system with MCP tool integration.

Instead of accepting text input from the user, this app responds to speech
detection events emitted via Unix Domain Socket.

Key features:
1. Listens to speech_started/speech_stopped events
2. Processes speech events through vLLM chat completion
3. Full MCP tool integration (robot control)
4. Automatic conversation flow based on speech detection
5. Text-to-speech responses via robot

Usage:
    python conversation_app.py
    
Requirements:
    - Hearing event emitter running (hearing_event_emitter.py)
    - Reachy Mini daemon running (reachy-mini-daemon)
    - vLLM server running on http://localhost:8100 with:
      --enable-auto-tool-choice
      --tool-call-parser llama3_json
    - MCP server configured in mcp.json
"""

import asyncio
import json
import httpx
import traceback
import socket
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
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
        self.mcp_session = None
        self.read_stream = None
        self.write_stream = None
        self.client_context = None
        self.stdio_context = None
        self.mcp_tools = []
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

    async def initialize_mcp(self):
        """Initialize MCP client and load tools from mcp.json."""
        logger.info("=" * 70)
        logger.info("Initializing MCP Client")
        logger.info("=" * 70)
        
        # Load mcp.json configuration
        mcp_config_path = Path(__file__).parent / "mcp.json"
        with open(mcp_config_path, 'r') as f:
            mcp_config = json.load(f)
        
        server_config = mcp_config["mcpServers"]["reachy-mini"]
        
        logger.info(f"Server configuration:")
        logger.info(f"   Command: {server_config['command']}")
        logger.info(f"   Args: {server_config['args']}")
        
        # Merge environment variables: mcp.json config + current environment
        env_vars = server_config.get('env', {}).copy()
        
        # Pass through important environment variables from current process
        if 'REACHY_BASE_URL' in os.environ:
            env_vars['REACHY_BASE_URL'] = os.environ['REACHY_BASE_URL']
            logger.info(f"   Passing REACHY_BASE_URL: {env_vars['REACHY_BASE_URL']}")
        
        if 'PIPER_MODEL' in os.environ:
            env_vars['PIPER_MODEL'] = os.environ['PIPER_MODEL']
        
        if 'AUDIO_DEVICE' in os.environ:
            env_vars['AUDIO_DEVICE'] = os.environ['AUDIO_DEVICE']
        
        for key, value in env_vars.items():
            logger.info(f"      {key}: {value}")
        
        # Initialize MCP client
        logger.info("Starting MCP server...")
        server_params = StdioServerParameters(
            command=server_config["command"],
            args=server_config["args"],
            env=env_vars
        )
        
        # Store contexts for later cleanup
        self.stdio_context = stdio_client(server_params)
        self.read_stream, self.write_stream = await self.stdio_context.__aenter__()
        
        self.client_context = ClientSession(self.read_stream, self.write_stream)
        self.mcp_session = await self.client_context.__aenter__()
        
        # Initialize the session
        await self.mcp_session.initialize()
        logger.info("   ✓ MCP session initialized")
        
        # List available tools
        logger.info("Loading available tools...")
        tools_result = await self.mcp_session.list_tools()
        
        logger.info(f"   Found {len(tools_result.tools)} tool(s):")
        for tool in tools_result.tools:
            logger.info(f"   - {tool.name}")
            
            # Convert MCP tool to OpenAI tool format
            openai_tool = self._convert_mcp_tool_to_openai(tool)
            self.mcp_tools.append({
                "mcp_tool": tool,
                "openai_tool": openai_tool
            })
        
        logger.info("=" * 70)
        logger.info(f"✓ MCP Client ready with {len(self.mcp_tools)} tools")
        logger.info("=" * 70)
        
        # Initialize conversation with system prompt
        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        
    def _convert_mcp_tool_to_openai(self, mcp_tool) -> Dict[str, Any]:
        """Convert MCP tool definition to OpenAI tool format."""
        return {
            "type": "function",
            "function": {
                "name": mcp_tool.name,
                "description": mcp_tool.description,
                "parameters": mcp_tool.inputSchema if mcp_tool.inputSchema else {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False
                }
            }
        }
    
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
    
    def _clean_tool_arguments(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Clean tool arguments to handle LLM output quirks."""
        cleaned = {}
        for key, value in arguments.items():
            # Handle string "null" - omit entirely for optional parameters
            if value == "null" or value == "None":
                continue
            elif value == "true":
                cleaned[key] = True
            elif value == "false":
                cleaned[key] = False
            else:
                cleaned[key] = value
        
        return cleaned
    
    async def execute_tool_via_mcp(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool via MCP server with argument cleaning."""
        logger.info(f"🔧 Executing tool: {tool_name}")
        
        # Clean arguments to handle LLM pythonic tool calling quirks
        cleaned_arguments = self._clean_tool_arguments(arguments)
        
        # Show cleaning if arguments were modified
        if cleaned_arguments != arguments:
            logger.debug(f"   Original args: {arguments}")
            logger.debug(f"   Cleaned args: {cleaned_arguments}")
        
        try:
            result = await self.mcp_session.call_tool(tool_name, cleaned_arguments)
            logger.info(f"   ✓ Tool executed successfully")
            return result
        except Exception as e:
            error_msg = f"Error executing tool {tool_name}: {str(e)}"
            logger.error(f"   ✗ {error_msg}")
            return {"error": error_msg}
    
    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] = None,
        max_tokens: int = 3000
    ) -> Dict[str, Any]:
        """Make a chat completion request with tool calling support."""
        payload = {
            "model": MODEL_NAME,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.3
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
            payload["parallel_tool_calls"] = False
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(CHAT_COMPLETIONS_URL, json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error: {e}")
                logger.error(f"Response: {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Error during chat completion: {e}")
                raise
    
    async def process_message(self, user_message: str) -> str:
        """Process a user message and return the assistant's response."""
        # Add user message to conversation
        self.messages.append({"role": "user", "content": user_message})
       
        logger.debug(f"Current history: {len(self.messages)} messages")

        # Get OpenAI-formatted tools
        openai_tools = [tool_dict["openai_tool"] for tool_dict in self.mcp_tools]
        
        max_iterations = 10
        iteration = 0
        final_response = None
        
        while iteration < max_iterations:
            iteration += 1
            
            # Make chat completion request
            response = await self.chat_completion(
                messages=self.messages,
                tools=openai_tools
            )
            
            # Get the assistant's message
            choice = response["choices"][0]
            assistant_message = choice["message"]
            finish_reason = choice["finish_reason"]
            
            logger.debug(f"Iteration {iteration}: finish_reason={finish_reason}")
            
            # Clean up empty tool_calls array
            if "tool_calls" in assistant_message and not assistant_message["tool_calls"]:
                del assistant_message["tool_calls"]
            
            # Add assistant message to conversation
            self.messages.append(assistant_message)
            
            # Check if we have a text response
            content_str = assistant_message.get("content", "")
            if content_str:
                final_response = content_str
            
            # Handle tool calls
            if "tool_calls" in assistant_message and assistant_message["tool_calls"]:
                logger.info(f"🛠️  Processing {len(assistant_message['tool_calls'])} tool call(s)")
                
                # Execute each tool call
                for tool_call in assistant_message["tool_calls"]:
                    tool_name = tool_call["function"]["name"]
                    tool_args_str = tool_call["function"]["arguments"]
                    
                    # Parse arguments
                    try:
                        tool_args = json.loads(tool_args_str) if isinstance(tool_args_str, str) else tool_args_str
                    except json.JSONDecodeError:
                        tool_args = {}
                    
                    # Execute tool
                    result = await self.execute_tool_via_mcp(tool_name, tool_args)
                    
                    # Add tool result to conversation
                    tool_result_message = {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(result.content[0].text if hasattr(result, 'content') else str(result))
                    }
                    self.messages.append(tool_result_message)
                
                # Continue loop to get next response
                continue
                
            elif final_response:
                # We have a text response and no tool calls, we're done
                logger.info("✓ Conversation turn complete")
                return final_response
                
            elif finish_reason == "stop":
                # No content and stop reason - return empty or final
                return final_response or "(No response)"
            
            # Continue to next iteration
            
        return final_response or "(No response generated)"
    
    async def run(self):
        """Run the conversation application."""
        logger.info("=" * 70)
        logger.info("Conversation Application with Speech Events")
        logger.info("=" * 70)
        logger.info("")
        logger.info("This app will:")
        logger.info("  1. Connect to hearing event emitter")
        logger.info("  2. Listen for speech events")
        logger.info("  3. Process speech through vLLM chat")
        logger.info("  4. Control robot via MCP tools")
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
        
        if self.client_context:
            await self.client_context.__aexit__(None, None, None)
        if self.stdio_context:
            await self.stdio_context.__aexit__(None, None, None)
        
        logger.info("   ✓ Cleanup complete")


async def main():
    """Main function."""
    logger.info("=" * 70)
    logger.info("Starting Conversation Application")
    logger.info("=" * 70)
    logger.info("")
    logger.info("Make sure:")
    logger.info("  - Hearing event emitter is running")
    logger.info("  - Reachy Mini daemon is running")
    logger.info("  - vLLM server is running on http://localhost:8100")
    logger.info("=" * 70)
    logger.info("")
    
    app = ConversationApp()
    
    try:
        # Initialize MCP
        await app.initialize_mcp()
        
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
