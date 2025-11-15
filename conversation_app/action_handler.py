#!/usr/bin/env python3
"""
Action Handler Module

This module handles robot action execution, managing:
- Actions queue initialization with reachy-daemon connection
- Action item processing from conversation parser
- Execution queue management

Integrates with AsyncActionsQueue to execute robot actions through reachy-daemon.
"""

import logging
import os
from typing import Optional
from pathlib import Path
from .actions_queue import AsyncActionsQueue

logger = logging.getLogger(__name__)


class ActionHandler:
    """Handles robot action execution."""
    
    def __init__(self, 
                 reachy_base_url: Optional[str] = None,
                 tools_repository_path: Optional[Path] = None):
        """
        Initialize the action handler.
        
        Args:
            reachy_base_url: URL for reachy-daemon (if None, uses REACHY_BASE_URL env var)
            tools_repository_path: Path to tools_repository directory
        """
        # Get configuration from environment if not provided
        if reachy_base_url is None:
            reachy_base_url = os.environ.get("REACHY_BASE_URL", "http://localhost:8000")
        
        if tools_repository_path is None:
            # Default to tools_repository in parent directory
            tools_repository_path = Path(__file__).parent.parent / "tools_repository"
        
        logger.info(f"Initializing action handler...")
        logger.info(f"  Reachy daemon: {reachy_base_url}")
        logger.info(f"  Tools repository: {tools_repository_path}")
        
        try:
            self.actions_queue = AsyncActionsQueue(
                reachy_base_url=reachy_base_url,
                tools_repository_path=tools_repository_path
            )
            logger.info("✓ Action handler initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize actions queue: {e}")
            raise
    
    async def execute(self, action_string: str):
        """
        Queue an action for execution.
        
        Args:
            action_string: Action to execute (e.g., "nod_head" or "look_at_direction(direction=left)")
        """
        if not action_string or not action_string.strip():
            return
        
        logger.debug(f"Queueing action: {action_string}")
        
        try:
            await self.actions_queue.enqueue_action(action_string)
        except Exception as e:
            logger.error(f"❌ Error queueing action: {e}")
    
    async def clear(self):
        """Clear all pending actions from the queue."""
        logger.debug("Clearing actions queue")
        try:
            await self.actions_queue.clear_queue()
        except Exception as e:
            logger.error(f"❌ Error clearing actions queue: {e}")
    
    def cleanup(self):
        """Clean up resources."""
        logger.debug("Cleaning up action handler")
        try:
            self.actions_queue.cleanup()
        except Exception as e:
            logger.error(f"❌ Error during action handler cleanup: {e}")
