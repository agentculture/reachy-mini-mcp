#!/usr/bin/env python3
"""
Conversation Application Package

This package provides a conversation system with speech event integration.

Main components:
- EventHandler: Manages speech events from hearing service
- ConversationParser: Parses LLM responses for speech and actions
- ConversationApp: Main application orchestrating the conversation flow
"""

from .event_handler import EventHandler
from .conversation_parser import ConversationParser
from .app import ConversationApp

__all__ = [
    'EventHandler',
    'ConversationParser',
    'ConversationApp',
]

__version__ = '1.0.0'
