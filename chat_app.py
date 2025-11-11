#!/usr/bin/env python3
"""
Interactive Chat Application with MCP Tool Integration for Llama Models

This is an interactive chat application that allows you to have continuous
conversations with vLLM-served Llama models while leveraging MCP tools for
robot control.

Key features:
1. Interactive command-line chat interface
2. Full MCP tool integration (robot control)
3. Multi-turn conversations with context
4. Pythonic tool calling support for Llama models
5. Commands: /help, /clear, /history, /quit

Pythonic Tool Calling:
- Uses vLLM's --enable-auto-tool-choice flag
- Uses --tool-call-parser llama3_json for native Llama format
- Handles Llama-specific output quirks (string "null", etc.)
- Automatic argument cleaning before MCP execution

Usage:
    python chat_app.py
    
Requirements:
    - Reachy Mini daemon running (reachy-mini-daemon)
    - vLLM server running on http://localhost:8100 with:
      --enable-auto-tool-choice
      --tool-call-parser llama3_json
    - MCP server configured in mcp.json
"""

import asyncio
import httpx
import json
import sys
import os
from pathlib import Path
from typing import List, Dict, Any
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# Configuration
CHAT_COMPLETIONS_URL = "http://localhost:8100/v1/chat/completions"
# The model name can be anything when using vLLM - it just needs to be non-empty
# vLLM will use whatever model it's serving
#MODEL_NAME = "meta-llama/Llama-3.2-3B-Instruct"  # Adjust based on your vLLM setup
#MODEL_NAME = "meta-llama/Llama-3.1-8B-Instruct"
#MODEL_NAME = "meta-llama/Llama-3.2-11B-Vision-Instruct"  # Adjust based on your vLLM setup
MODEL_NAME = "RedHatAI/Llama-3.2-3B-Instruct-FP8"

class InteractiveChatApp:
    """Interactive chat application with MCP tool integration."""
    
    def __init__(self):
        self.mcp_session = None
        self.read_stream = None
        self.write_stream = None
        self.client_context = None
        self.stdio_context = None
        self.mcp_tools = []
        self.messages = []
        # load the prompt from agents/reachy/reachy.system.md
        self.system_prompt = Path("agents/reachy/reachy.system.md").read_text()
        # Keep track of conversation summary for context
        self.conversation_summary = []

    async def initialize_mcp(self):
        """Initialize MCP client and load tools from mcp.json."""
        print("=" * 70)
        print("Initializing MCP Client")
        print("=" * 70)
        
        # Load mcp.json configuration
        mcp_config_path = Path(__file__).parent / "mcp.json"
        with open(mcp_config_path, 'r') as f:
            mcp_config = json.load(f)
        
        server_config = mcp_config["mcpServers"]["reachy-mini"]
        
        print(f"\n📋 Server configuration:")
        print(f"   Command: {server_config['command']}")
        print(f"   Args: {server_config['args']}")
        
        # Initialize MCP client
        print("\n🚀 Starting MCP server...")
        server_params = StdioServerParameters(
            command=server_config["command"],
            args=server_config["args"],
            env=server_config.get("env", {})
        )
        
        # Store contexts for later cleanup
        self.stdio_context = stdio_client(server_params)
        self.read_stream, self.write_stream = await self.stdio_context.__aenter__()
        
        self.client_context = ClientSession(self.read_stream, self.write_stream)
        self.mcp_session = await self.client_context.__aenter__()
        
        # Initialize the session
        await self.mcp_session.initialize()
        print("   ✓ MCP session initialized")
        
        # List available tools
        print("\n🔧 Loading available tools...")
        tools_result = await self.mcp_session.list_tools()
        
        print(f"\n   Found {len(tools_result.tools)} tool(s):")
        for tool in tools_result.tools:
            print(f"   - {tool.name}")
            
            # Convert MCP tool to OpenAI tool format
            openai_tool = self._convert_mcp_tool_to_openai(tool)
            self.mcp_tools.append({
                "mcp_tool": tool,
                "openai_tool": openai_tool
            })
        
        print("\n" + "=" * 70)
        print(f"✓ MCP Client ready with {len(self.mcp_tools)} tools")
        print("=" * 70 + "\n")
        
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
    
    def _generate_conversation_summary(self) -> str:
        """
        Generate a summary of User-Reachy exchanges for context continuity.
        
        This creates a concise summary of what the user said and what Reachy responded,
        helping Reachy understand the conversation flow and continue naturally from
        its last words.
        """
        summary_lines = []
        current_user_msg = None
        current_assistant_response = None
        
        # Skip system message and process conversation pairs
        for msg in self.messages[1:]:  # Skip system prompt
            role = msg.get("role")
            content = msg.get("content", "")
            
            if role == "user":
                # Save the current exchange if we have one
                if current_user_msg and current_assistant_response:
                    summary_lines.append(f"User: {current_user_msg}")
                    summary_lines.append(f"Reachy: {current_assistant_response}")
                    summary_lines.append("")
                
                # Start new exchange
                current_user_msg = content
                current_assistant_response = None
                
            elif role == "assistant":
                # Accumulate assistant responses (might be multiple with tool calls)
                if content:
                    if current_assistant_response:
                        current_assistant_response += " " + content
                    else:
                        current_assistant_response = content
                        
                # Note tool calls if present
                if msg.get("tool_calls"):
                    tool_names = [tc.get("function", {}).get("name", "unknown") 
                                  for tc in msg["tool_calls"]]
                    tool_note = f"[Used tools: {', '.join(tool_names)}]"
                    if current_assistant_response:
                        current_assistant_response += " " + tool_note
                    else:
                        current_assistant_response = tool_note
        
        # Add the last exchange if exists
        if current_user_msg and current_assistant_response:
            summary_lines.append(f"User: {current_user_msg}")
            summary_lines.append(f"Reachy: {current_assistant_response}")
        
        # Join all summary lines
        if summary_lines:
            summary = "\n".join(summary_lines)
            return f"\n=== Conversation Summary ===\n{summary}\n=== End Summary ===\n"
        else:
            return ""
    
    def _get_enhanced_system_prompt(self) -> str:
        """
        Get system prompt enhanced with conversation summary.
        
        This helps Reachy maintain context of what has been said and done,
        enabling more natural conversation continuity.
        """
        base_prompt = self.system_prompt
        summary = self._generate_conversation_summary()
        
        if summary:
            # Add summary to the end of system prompt
            return f"{base_prompt}\n\n{summary}\n\nPlease continue the conversation naturally from where you left off."
        else:
            return base_prompt
    
    def _fix_double_encoded_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fix double-encoded JSON parameters.
        
        Some LLMs (especially Llama models) double-encode complex parameters by 
        converting arrays/objects to JSON strings. This function recursively parses
        any string values that look like JSON.
        
        Example:
        {"commands": "[{...}]"}  ->  {"commands": [{...}]}
        """
        if not isinstance(params, dict):
            return params
            
        fixed = {}
        for key, value in params.items():
            if isinstance(value, str):
                # Check if the string looks like JSON (starts with [ or {)
                stripped = value.strip()
                if (stripped.startswith('[') and stripped.endswith(']')) or \
                   (stripped.startswith('{') and stripped.endswith('}')):
                    try:
                        # Try to parse it as JSON
                        parsed = json.loads(value)
                        fixed[key] = parsed
                        print(f"  [DEBUG] Fixed double-encoded param '{key}': string -> {type(parsed).__name__}")
                    except json.JSONDecodeError:
                        # If parsing fails, keep the original string
                        fixed[key] = value
                else:
                    fixed[key] = value
            elif isinstance(value, dict):
                # Recursively fix nested dicts
                fixed[key] = self._fix_double_encoded_params(value)
            else:
                fixed[key] = value
        
        return fixed
    
    def _parse_tool_call_from_content(self, content: str) -> Dict[str, Any]:
        """
        Parse tool call from JSON content.
        
        Some Llama models output tool calls as JSON in the content field instead of
        using the tool_calls structure. This function detects and parses that format.
        
        This version robustly extracts the JSON by finding the first '{' and last '}'
        to strip away any leading/trailing text or artifacts (like '$').
        
        Expected format:
        {"name": "operate_robot", "parameters": {...}}
        
        Returns:
        Dict with 'name' and 'arguments' keys if valid tool call, None otherwise
        """
        if not content or not content.strip():
            return None
        print("trying to parse tool call from content...")
        # Find the first '{' and the last '}'
        start_index = content.find('{')
        # find very last
        end_index = content.rfind('}')
        
        if start_index == -1 or end_index == -1 or end_index < start_index:
            # No valid JSON object markers found
            print(f"  [DEBUG] No JSON object markers found in content.")
            return None
        
        # Extract the potential JSON string
        json_str = content[start_index : end_index + 1]
        print (json_str)
        # Try to parse the extracted string as JSON
        try:
            parsed = ''
            try:
                parsed = json.loads(json_str)
            except json.JSONDecodeError:
                # add } and try again.
                parsed = json.loads(json_str + '}')

            # Check if it looks like a tool call
            if isinstance(parsed, dict) and "name" in parsed:
                # Extract function name and parameters
                func_name = parsed.get("name")
                parameters = parsed.get("parameters", {})
                
                # Fix double-encoded JSON strings in parameters (common with Llama models)
                parameters = self._fix_double_encoded_params(parameters)
                
                # Validate it's a known tool
                known_tools = [tool["mcp_tool"].name for tool in self.mcp_tools]
                if func_name in known_tools:
                    print(f"  [DEBUG] Successfully parsed tool call from content: {func_name}")
                    return {
                        "name": func_name,
                        "arguments": parameters
                    }
                else:
                    print(f"  [DEBUG] Parsed JSON, but func_name '{func_name}' not in known tools.")
            else:
                print(f"  [DEBUG] Parsed JSON, but it's not a valid tool call structure.")
                
        except json.JSONDecodeError as e:
            # Parsing the extracted string failed
            print(f"  [DEBUG] Failed to parse extracted JSON string: {e}")
            print(f"      Extracted string: {json_str[:150]}...")
            pass
        
        return None
    
    def _clean_tool_arguments(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean tool arguments to handle Llama model output quirks.
        
        Llama models with pythonic tool calling sometimes output:
        - String "null" instead of None/omitting optional parameters
        - String "true"/"false" instead of boolean values
        
        This function cleans up such issues before passing to MCP.
        """
        cleaned = {}
        for key, value in arguments.items():
            # Handle string "null" - omit entirely for optional parameters
            if value == "null" or value == "None":
                continue
            # Handle string "true"/"false" - convert to boolean
            elif value == "true":
                cleaned[key] = True
            elif value == "false":
                cleaned[key] = False
            # Keep other values as-is
            else:
                cleaned[key] = value
        
        return cleaned
    
    async def execute_tool_via_mcp(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool via MCP server with argument cleaning."""
        print(f"\n🔧 Executing tool: {tool_name}")
        
        # Clean arguments to handle Llama pythonic tool calling quirks
        cleaned_arguments = self._clean_tool_arguments(arguments)
        
        # Show cleaning if arguments were modified
        if cleaned_arguments != arguments:
            print(f"   Original args: {arguments}")
            print(f"   Cleaned args: {cleaned_arguments}")
        
        try:
            result = await self.mcp_session.call_tool(tool_name, cleaned_arguments)
            print(f"   ✓ Tool executed successfully")
            return result
        except Exception as e:
            error_msg = f"Error executing tool {tool_name}: {str(e)}"
            print(f"   ✗ {error_msg}")
            return {"error": error_msg}
    
    def _prepare_messages_for_api(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Prepare messages for API call by cleaning up problematic sequences.
        
        vLLM has issues with:
        - Empty tool_calls arrays
        - Orphaned tool messages (tool messages without preceding tool_calls)
        
        This function ensures the message sequence is valid for vLLM.
        """
        cleaned_messages = []
        last_assistant_had_tool_calls = False
        
        for msg in messages:
            role = msg.get("role")
            msg_copy = msg.copy()
            
            if role == "assistant":
                # Track if this assistant message has tool calls
                has_tool_calls = bool(msg.get("tool_calls"))
                last_assistant_had_tool_calls = has_tool_calls
                
                # Remove empty tool_calls array
                if "tool_calls" in msg_copy and not msg_copy["tool_calls"]:
                    del msg_copy["tool_calls"]
                
                cleaned_messages.append(msg_copy)
                
            elif role == "tool":
                # Only include tool messages if the last assistant had tool_calls
                if last_assistant_had_tool_calls:
                    cleaned_messages.append(msg_copy)
                else:
                    # Skip orphaned tool message
                    print(f"   [DEBUG] Skipping orphaned tool message: {msg.get('name')}")
                    
            else:
                # system, user, etc - include as-is
                cleaned_messages.append(msg_copy)
                # Reset tool call tracking on new user message
                if role == "user":
                    last_assistant_had_tool_calls = False
        
        return cleaned_messages
    
    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] = None,
        max_tokens: int = 3000
    ) -> Dict[str, Any]:
        """Make a chat completion request with pythonic tool calling support."""
        # Clean up messages before sending to API
        cleaned_messages = self._prepare_messages_for_api(messages)
        
        payload = {
            "model": MODEL_NAME,
            "messages": cleaned_messages,
            "max_tokens": max_tokens,
            "temperature": 0.3  # Lower temperature for more consistent tool calling
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
            # Llama models with pythonic tool calling work better without parallel calls
            payload["parallel_tool_calls"] = False
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(CHAT_COMPLETIONS_URL, json=payload)
                response.raise_for_status()
                result = response.json()
                return result
            except httpx.HTTPStatusError as e:
                print(f"\n❌ Error calling model: {e}")
                print(f"\n📋 Request payload (last 3 messages):")
                for msg in cleaned_messages[-3:]:
                    print(f"   Role: {msg.get('role')}")
                    if msg.get('content'):
                        print(f"   Content: {msg['content'][:100]}...")
                    if msg.get('tool_calls'):
                        print(f"   Tool calls: {len(msg['tool_calls'])}")
                    if msg.get('tool_call_id'):
                        print(f"   Tool call ID: {msg['tool_call_id']}")
                print(f"\n📋 Response: {e.response.text[:500]}")
                raise
            except Exception as e:
                print(f"\n❌ Error calling model: {e}")
                raise
    
    async def process_message(self, user_message: str) -> str:
        """Process a user message and return the assistant's response."""
        # Add user message to conversation
        self.messages.append({"role": "user", "content": user_message})
       
        # Keep ALL history - no pruning
        # The conversation summary in the system prompt helps maintain context
        # while the full history ensures complete accuracy
        print(f"\n[DEBUG] Current history: {len(self.messages)} messages")

        # Update system prompt with conversation summary for better context
        enhanced_system_prompt = self._get_enhanced_system_prompt()
        
        # Create messages list with enhanced system prompt
        messages_with_summary = [
            {"role": "system", "content": enhanced_system_prompt}
        ] + self.messages[1:]  # Skip original system message, use enhanced one

        # Get OpenAI-formatted tools
        openai_tools = [tool_dict["openai_tool"] for tool_dict in self.mcp_tools]
        
        max_iterations = 10  # Prevent infinite loops
        iteration = 0
        final_response = None
        
        while iteration < max_iterations:
            iteration += 1
            
            # Make chat completion request with enhanced context
            response = await self.chat_completion(
                messages=messages_with_summary,
                tools=openai_tools
            )
            
            # Get the assistant's message
            choice = response["choices"][0]
            assistant_message = choice["message"]
            finish_reason = choice["finish_reason"]
            
            # Debug: Print what we got back
            print(f"\n[DEBUG] Iteration {iteration}:")
            print(f"  finish_reason: {finish_reason}")
            print(f"  has content: {'content' in assistant_message and assistant_message['content'] is not None}")
            print(f"  'tool_calls' key exists: {'tool_calls' in assistant_message}")
            print(f"  tool_calls is truthy: {bool(assistant_message.get('tool_calls'))}")
            print(f"  tool_calls value: {assistant_message.get('tool_calls')}")
            
            # Show content if present
            if assistant_message.get("content"):
                content_preview = assistant_message['content'][:150]
                print(f"  content preview: {content_preview}...")
            
            # Show tool calls if present
            if assistant_message.get("tool_calls"):
                print(f"  tool_calls count: {len(assistant_message['tool_calls'])}")
                for tc in assistant_message['tool_calls']:
                    func = tc.get('function', {})
                    print(f"    - Function: {func.get('name')}")
                    args_preview = str(func.get('arguments', ''))[:100]
                    print(f"      Args preview: {args_preview}")
            else:
                print(f"  tool_calls is empty or None")
            
            # Clean up empty tool_calls array before adding to conversation
            # vLLM expects clean message format - empty arrays cause issues
            if "tool_calls" in assistant_message and not assistant_message["tool_calls"]:
                del assistant_message["tool_calls"]
            
            # Add assistant message to conversation (both history and working list)
            self.messages.append(assistant_message)
            messages_with_summary.append(assistant_message)
            
            # Check if we have a text response
            content_str = assistant_message.get("content", "")
            if content_str:
                final_response = content_str
            
            # Check if content contains a JSON tool call (Llama fallback format)
            parsed_tool_call = None
            if content_str and not assistant_message.get("tool_calls"):
                parsed_tool_call = self._parse_tool_call_from_content(content_str)
                if parsed_tool_call:
                    print(f"\n✓ Detected JSON tool call in content (Llama fallback format)")
                    print(f"   Function: {parsed_tool_call['name']}")
                    print(f"   Arguments: {json.dumps(parsed_tool_call['arguments'], indent=2)}")
            
            # Handle tool calls FIRST (prioritize structured tool_calls, then JSON in content)
            if "tool_calls" in assistant_message and assistant_message["tool_calls"]:
                # Model made proper structured tool calls
                print(f"\n✓ Processing structured tool calls (pythonic format)")
                # Don't break here - continue to tool call processing below
            elif parsed_tool_call:
                # Model output tool call as JSON in content - convert to tool_call format
                print(f"\n✓ Converting JSON content to tool call format")
                
                # Create a synthetic tool_call structure
                # NOTE: arguments must be a JSON string, not a dict
                synthetic_tool_call = {
                    "id": f"call_{iteration}",  # Generate a simple ID
                    "function": {
                        "name": parsed_tool_call["name"],
                        "arguments": json.dumps(parsed_tool_call["arguments"])  # Convert dict to JSON string
                    },
                    "type": "function"
                }
                
                # Add it to the assistant message for processing
                if "tool_calls" not in assistant_message:
                    assistant_message["tool_calls"] = []
                assistant_message["tool_calls"].append(synthetic_tool_call)
                
                # Update the message in conversation history
                self.messages[-1] = assistant_message
                
                # Clear final_response so we don't treat this as a text response
                final_response = None
                # Don't break here - continue to tool call processing below
            elif final_response:
                # Only text content, no tool calls - check if this is after tool execution
                if finish_reason == "stop":
                    # Check if the previous messages contain tool results
                    # If so, this is the final response after tool chain completion
                    has_recent_tool_results = False
                    for msg in reversed(self.messages[-5:]):  # Check last 5 messages
                        if msg.get("role") == "tool":
                            has_recent_tool_results = True
                            break
                    
                    if has_recent_tool_results:
                        # This is the final response after tool execution - we're done with this chain
                        print(f"\n✓ Model provided final response after tool execution")
                        break
                    else:
                        # Just a normal text response, we're done
                        break
            elif finish_reason == "stop":
                # No content and no tool calls, we're done
                break
            
            # Check if response was truncated
            if finish_reason == "length":
                if not final_response:
                    final_response = "(Response truncated due to length limit)"
                break
            
            # Handle tool calls (both with finish_reason "tool_calls" or "stop")
            if "tool_calls" in assistant_message and assistant_message["tool_calls"]:
                tool_calls = assistant_message["tool_calls"]
                
                print(f"\n🔧 Processing {len(tool_calls)} tool call(s) (pythonic format)...")
                
                # Execute each tool call
                for tool_call in tool_calls:
                    tool_call_id = tool_call.get("id")
                    function = tool_call.get("function", {})
                    tool_name = function.get("name")
                    arguments_str = function.get("arguments", "{}")
                    
                    # Parse arguments (pythonic tool calling may return dict or string)
                    try:
                        if isinstance(arguments_str, str):
                            arguments = json.loads(arguments_str)
                        elif isinstance(arguments_str, dict):
                            arguments = arguments_str
                        else:
                            arguments = {}
                    except json.JSONDecodeError as e:
                        print(f"   ⚠️  Failed to parse arguments: {e}")
                        print(f"      Raw arguments: {arguments_str}")
                        arguments = {}
                    
                    # Execute tool via MCP with argument cleaning
                    tool_result = await self.execute_tool_via_mcp(tool_name, arguments)
                    
                    # Format tool result
                    tool_result_content = json.dumps(tool_result.model_dump() if hasattr(tool_result, 'model_dump') else tool_result)
                    
                    # Create tool result message
                    tool_result_msg = {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "content": tool_result_content
                    }
                    
                    # Add tool result to conversation (both history and working list)
                    self.messages.append(tool_result_msg)
                    messages_with_summary.append(tool_result_msg)
                
                # Continue conversation with tool results
                # Allow the model to respond to the tool results and potentially chain more commands
                continue  
            
            # If we get here with a different finish reason, something unexpected happened
            break
        
        return final_response or "(No response generated)"
    
    def print_help(self):
        """Print help message."""
        print("\n" + "=" * 70)
        print("Available Commands:")
        print("=" * 70)
        print("  /help     - Show this help message")
        print("  /clear    - Clear conversation history (keeps system prompt)")
        print("  /history  - Show conversation history")
        print("  /summary  - Show conversation summary (User-Reachy exchanges)")
        print("  /quit     - Exit the chat application")
        print("  /exit     - Exit the chat application")
        print("\nAvailable robot tools:")
        for tool_dict in self.mcp_tools:
            tool = tool_dict["mcp_tool"]
            print(f"  - {tool.name}")
        print("=" * 70 + "\n")
    
    def print_history(self):
        """Print conversation history."""
        print("\n" + "=" * 70)
        print("Conversation History")
        print("=" * 70)
        for i, msg in enumerate(self.messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            
            if role == "system":
                print(f"\n[{i}] SYSTEM:")
                print(f"    {content[:100]}..." if len(content) > 100 else f"    {content}")
            elif role == "user":
                print(f"\n[{i}] USER:")
                print(f"    {content}")
            elif role == "assistant":
                print(f"\n[{i}] ASSISTANT:")
                if content:
                    print(f"    {content}")
                if "tool_calls" in msg:
                    print(f"    (Made {len(msg['tool_calls'])} tool call(s))")
            elif role == "tool":
                print(f"\n[{i}] TOOL ({msg.get('name', 'unknown')}):")
                print(f"    Result: {content[:100]}..." if len(content) > 100 else f"    Result: {content}")
        
        print("\n" + "=" * 70)
        print(f"Total messages: {len(self.messages)}")
        print("=" * 70 + "\n")
    
    def print_summary(self):
        """Print conversation summary (User-Reachy exchanges)."""
        summary = self._generate_conversation_summary()
        
        if summary:
            print("\n" + "=" * 70)
            print("Conversation Summary (User-Reachy Exchanges)")
            print("=" * 70)
            print(summary)
            print("=" * 70 + "\n")
        else:
            print("\n✓ No conversation exchanges yet.\n")
    
    def clear_history(self):
        """Clear conversation history but keep system prompt."""
        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        self.conversation_summary = []
        print("\n✓ Conversation history and summary cleared (system prompt retained)\n")
    
    async def run(self):
        """Run the interactive chat loop."""
        print("\n" + "=" * 70)
        print("Interactive Chat with Reachy Mini Robot")
        print("=" * 70)
        print("\nType '/help' for available commands")
        print("Type '/quit' or '/exit' to exit")
        print("=" * 70 + "\n")
        
        while True:
            try:
                # Get user input
                user_input = input("You: ").strip()
                
                # Handle empty input
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.startswith("/"):
                    command = user_input.lower()
                    
                    if command in ["/quit", "/exit"]:
                        print("\n👋 Goodbye!\n")
                        break
                    elif command == "/help":
                        self.print_help()
                        continue
                    elif command == "/history":
                        self.print_history()
                        continue
                    elif command == "/summary":
                        self.print_summary()
                        continue
                    elif command == "/clear":
                        self.clear_history()
                        continue
                    else:
                        print(f"\n❌ Unknown command: {user_input}")
                        print("Type '/help' for available commands\n")
                        continue
                
                # Process the message
                response = await self.process_message(user_input)
                print(f"\n🤖 Assistant: {response}\n")
                
            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted. Type '/quit' to exit or continue chatting.\n")
                continue
            except EOFError:
                print("\n\n👋 Goodbye!\n")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")
                continue
    
    async def cleanup(self):
        """Cleanup MCP session."""
        print("\n🧹 Cleaning up...")
        
        if self.client_context:
            await self.client_context.__aexit__(None, None, None)
        if self.stdio_context:
            await self.stdio_context.__aexit__(None, None, None)
        print("   ✓ Cleanup complete")


async def main():
    """Main function."""
    print("\n" + "=" * 70)
    print("Starting Interactive Chat Application")
    print("=" * 70)
    print("\nMake sure:")
    print("  - Reachy Mini daemon is running (reachy-mini-daemon)")
    print("  - vLLM server is running on http://localhost:8100 with:")
    print("    --enable-auto-tool-choice")
    print("    --tool-call-parser llama3_json")
    print("=" * 70 + "\n")
    
    app = InteractiveChatApp()
    
    try:
        # Initialize MCP
        await app.initialize_mcp()
        
        # Run interactive chat
        await app.run()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await app.cleanup()
    
    print("\n✅ Done!\n")


if __name__ == "__main__":
    asyncio.run(main())
