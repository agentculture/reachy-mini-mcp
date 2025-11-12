#!/usr/bin/env python3
"""
Interactive Chat Application with OpenAI API Tool Integration for Reachy Robot

This is an interactive chat application that allows you to have continuous
conversations with OpenAI models (or compatible APIs) while leveraging tools for
robot control.

Key features:
1. Interactive command-line chat interface
2. Full OpenAI tool integration (robot control)
3. Multi-turn conversations with context
4. Standard OpenAI API tool calling format
5. Commands: /help, /clear, /history, /quit

Usage:
    python chat_app_openai.py
    
Requirements:
    - Reachy Mini daemon running (reachy-mini-daemon)
    - OpenAI API key set in environment (OPENAI_API_KEY)
      OR compatible API endpoint (e.g., local LLM with OpenAI-compatible API)
    - Robot control server running (server_openai.py)
"""

import asyncio
import httpx
import json
import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Optional


# Configuration
# For OpenAI API
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.environ.get("OPENAI_MODEL", "gpt-4-turbo-preview")

# For robot control server
ROBOT_SERVER_URL = os.environ.get("ROBOT_SERVER_URL", "http://localhost:8100")


class InteractiveChatApp:
    """Interactive chat application with OpenAI API tool integration."""
    
    def __init__(self):
        self.tools = []
        self.messages = []
        # Load the prompt from agents/reachy/reachy.system.md
        system_prompt_path = Path("agents/reachy/reachy.system.md")
        if system_prompt_path.exists():
            self.system_prompt = system_prompt_path.read_text()
        else:
            self.system_prompt = "You are a helpful assistant controlling a Reachy Mini robot."
        
        # Keep track of conversation summary for context
        self.conversation_summary = []

    async def initialize_tools(self):
        """Load available tools from the robot control server."""
        print("=" * 70)
        print("Initializing Robot Control Tools")
        print("=" * 70)
        
        print(f"\n📋 Robot server URL: {ROBOT_SERVER_URL}")
        print(f"📋 OpenAI API URL: {OPENAI_BASE_URL}")
        print(f"📋 Model: {MODEL_NAME}")
        
        # Fetch available tools from robot server
        print("\n🔧 Loading available tools...")
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{ROBOT_SERVER_URL}/tools")
                response.raise_for_status()
                tools_data = response.json()
                self.tools = tools_data.get("tools", [])
                
                print(f"\n   Found {len(self.tools)} tool(s):")
                for tool in self.tools:
                    func_name = tool.get("function", {}).get("name", "unknown")
                    print(f"   - {func_name}")
                
            except Exception as e:
                print(f"\n❌ Error loading tools: {e}")
                print("   Make sure the robot control server is running")
                raise
        
        print("\n" + "=" * 70)
        print(f"✓ Tools loaded successfully")
        print("=" * 70 + "\n")
        
        # Initialize conversation with system prompt
        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]
    
    def _generate_conversation_summary(self) -> str:
        """
        Generate a summary of User-Robot exchanges for context continuity.
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
                    summary_lines.append(f"Robot: {current_assistant_response}")
                    summary_lines.append("")
                
                # Start new exchange
                current_user_msg = content
                current_assistant_response = None
                
            elif role == "assistant":
                # Accumulate assistant responses
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
            summary_lines.append(f"Robot: {current_assistant_response}")
        
        # Join all summary lines
        if summary_lines:
            summary = "\n".join(summary_lines)
            return f"\n=== Conversation Summary ===\n{summary}\n=== End Summary ===\n"
        else:
            return ""
    
    def _get_enhanced_system_prompt(self) -> str:
        """Get system prompt enhanced with conversation summary."""
        base_prompt = self.system_prompt
        summary = self._generate_conversation_summary()
        
        if summary:
            return f"{base_prompt}\n\n{summary}\n\nPlease continue the conversation naturally from where you left off."
        else:
            return base_prompt
    
    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 3000
    ) -> Dict[str, Any]:
        """Make a chat completion request using OpenAI API."""
        headers = {
            "Content-Type": "application/json"
        }
        
        if OPENAI_API_KEY:
            headers["Authorization"] = f"Bearer {OPENAI_API_KEY}"
        
        payload = {
            "model": MODEL_NAME,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{OPENAI_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                return result
            except httpx.HTTPStatusError as e:
                print(f"\n❌ Error calling model: {e}")
                print(f"\n📋 Response: {e.response.text[:500]}")
                raise
            except Exception as e:
                print(f"\n❌ Error calling model: {e}")
                raise
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool via the robot control server."""
        print(f"\n🔧 Executing tool: {tool_name}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{ROBOT_SERVER_URL}/execute_tool",
                    json={
                        "tool_name": tool_name,
                        "arguments": arguments
                    }
                )
                response.raise_for_status()
                result = response.json()
                print(f"   ✓ Tool executed successfully")
                return result
        except Exception as e:
            error_msg = f"Error executing tool {tool_name}: {str(e)}"
            print(f"   ✗ {error_msg}")
            return {"error": error_msg}
    
    async def process_message(self, user_message: str) -> str:
        """Process a user message and return the assistant's response."""
        # Add user message to conversation
        self.messages.append({"role": "user", "content": user_message})
       
        print(f"\n[DEBUG] Current history: {len(self.messages)} messages")

        # Update system prompt with conversation summary
        enhanced_system_prompt = self._get_enhanced_system_prompt()
        
        # Create messages list with enhanced system prompt
        messages_with_summary = [
            {"role": "system", "content": enhanced_system_prompt}
        ] + self.messages[1:]  # Skip original system message

        max_iterations = 10  # Prevent infinite loops
        iteration = 0
        final_response = None
        
        while iteration < max_iterations:
            iteration += 1
            
            # Make chat completion request
            response = await self.chat_completion(
                messages=messages_with_summary,
                tools=self.tools if self.tools else None
            )
            
            # Get the assistant's message
            choice = response["choices"][0]
            assistant_message = choice["message"]
            finish_reason = choice["finish_reason"]
            
            # Debug output
            print(f"\n[DEBUG] Iteration {iteration}:")
            print(f"  finish_reason: {finish_reason}")
            print(f"  has content: {assistant_message.get('content') is not None}")
            print(f"  has tool_calls: {bool(assistant_message.get('tool_calls'))}")
            
            # Add assistant message to conversation
            self.messages.append(assistant_message)
            messages_with_summary.append(assistant_message)
            
            # Check if we have a text response
            content_str = assistant_message.get("content", "")
            if content_str:
                final_response = content_str
            
            # Handle tool calls
            if assistant_message.get("tool_calls"):
                tool_calls = assistant_message["tool_calls"]
                
                print(f"\n🔧 Processing {len(tool_calls)} tool call(s)...")
                
                # Execute each tool call
                for tool_call in tool_calls:
                    tool_call_id = tool_call.get("id")
                    function = tool_call.get("function", {})
                    tool_name = function.get("name")
                    arguments_str = function.get("arguments", "{}")
                    
                    # Parse arguments
                    try:
                        if isinstance(arguments_str, str):
                            arguments = json.loads(arguments_str)
                        elif isinstance(arguments_str, dict):
                            arguments = arguments_str
                        else:
                            arguments = {}
                    except json.JSONDecodeError as e:
                        print(f"   ⚠️  Failed to parse arguments: {e}")
                        arguments = {}
                    
                    # Execute tool
                    tool_result = await self.execute_tool(tool_name, arguments)
                    
                    # Format tool result
                    tool_result_content = json.dumps(tool_result)
                    
                    # Create tool result message
                    tool_result_msg = {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "content": tool_result_content
                    }
                    
                    # Add tool result to conversation
                    self.messages.append(tool_result_msg)
                    messages_with_summary.append(tool_result_msg)
                
                # Continue conversation with tool results
                continue  
            
            # If we have a response and finish_reason is stop, we're done
            if finish_reason == "stop":
                break
            
            # Check if response was truncated
            if finish_reason == "length":
                if not final_response:
                    final_response = "(Response truncated due to length limit)"
                break
            
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
        print("  /summary  - Show conversation summary")
        print("  /quit     - Exit the chat application")
        print("  /exit     - Exit the chat application")
        print("\nAvailable robot tools:")
        for tool in self.tools:
            func = tool.get("function", {})
            print(f"  - {func.get('name', 'unknown')}")
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
        """Print conversation summary."""
        summary = self._generate_conversation_summary()
        
        if summary:
            print("\n" + "=" * 70)
            print("Conversation Summary")
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
        print("Interactive Chat with Reachy Mini Robot (OpenAI API)")
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


async def main():
    """Main function."""
    print("\n" + "=" * 70)
    print("Starting Interactive Chat Application (OpenAI API)")
    print("=" * 70)
    print("\nMake sure:")
    print("  - Reachy Mini daemon is running (reachy-mini-daemon)")
    print("  - Robot control server is running (server_openai.py)")
    print("  - OPENAI_API_KEY is set (or using compatible API)")
    print("=" * 70 + "\n")
    
    app = InteractiveChatApp()
    
    try:
        # Initialize tools
        await app.initialize_tools()
        
        # Run interactive chat
        await app.run()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n✅ Done!\n")


if __name__ == "__main__":
    asyncio.run(main())
