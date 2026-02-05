"""
Autonomous Navigator - Backwards compatibility wrapper.

This module re-exports from the refactored an_*.py modules.
For new code, import directly from those modules.

Refactored structure:
- logging_config.py - Centralized logging configuration
- an_config.py - Configuration, API keys
- an_prompts.py - System prompt and user message builders
- an_models.py - LLM model interaction (Gemini, Ollama)
- an_tools.py - Tool implementations (click, extract, capture_diagram, etc.)
- an_navigator.py - Main navigator class
"""

# Re-export everything for backwards compatibility
from .logging_config import get_logger, log_trace

from .an_config import (
    DEFAULT_MODEL,
    GEMINI_API_BASE_URL,
    GEMINI_API_KEY_FILE,
    get_gemini_api_key,
    is_gemini_model,
    is_debug_enabled as _is_debug_enabled,
    is_verbose as _is_verbose,
)

# Keep old debug exports for backward compatibility but they delegate to new system
from .an_debug import (
    ANDebugLogger,
    get_debug_logger,
)

from .an_prompts import (
    build_system_prompt as build_autonomous_system_prompt,
    build_user_message as build_autonomous_user_message,
)

from .an_models import (
    AUTONOMOUS_TOOLS,
    ToolResult,
    ModelClient,
)

from .an_tools import execute_tool

from .an_navigator import (
    AutonomousNavigator,
    query_mitchell_autonomous,
    test_autonomous_navigation,
)

# Also set up the logger for backwards compatibility
logger = get_logger()

__all__ = [
    # Config
    'DEFAULT_MODEL',
    'GEMINI_API_BASE_URL',
    'GEMINI_API_KEY_FILE',
    'get_gemini_api_key',
    'is_gemini_model',
    # Debug
    'ANDebugLogger',
    'get_debug_logger',
    # Prompts
    'build_autonomous_system_prompt',
    'build_autonomous_user_message',
    # Models
    'AUTONOMOUS_TOOLS',
    'ToolResult',
    'ModelClient',
    # Tools
    'execute_tool',
    # Navigator
    'AutonomousNavigator',
    'query_mitchell_autonomous',
    'test_autonomous_navigation',
    # Logger
    'logger',
]


# Allow running as script for testing
if __name__ == "__main__":
    import asyncio
    import sys
    import argparse
    import logging
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    
    parser = argparse.ArgumentParser(description='Autonomous Navigator Test')
    parser.add_argument('goal', nargs='*', help='Navigation goal')
    parser.add_argument('--model', '-m', default=None, help=f'Model to use (default: {DEFAULT_MODEL})')
    args = parser.parse_args()
    
    goal_text = " ".join(args.goal) if args.goal else None
    asyncio.run(test_autonomous_navigation(goal=goal_text, model=args.model))
