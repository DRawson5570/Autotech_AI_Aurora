"""
Configuration for Autonomous Navigator.

Handles API keys, model settings, and debug flags.
"""

import logging
import os
from typing import Optional

# =============================================================================
# MODEL CONFIGURATION
# =============================================================================
# Default to Gemini for better reliability. Ollama available as fallback.
# Override with: export AN_MODEL=llama3.1:8b
#
# Gemini models: gemini-2.5-flash, gemini-2.5-pro, gemini-2.0-flash
# Ollama models: llama3.1:8b, llama3.1:70b, etc.
# =============================================================================

DEFAULT_MODEL = os.environ.get("AN_MODEL", "gemini-2.5-flash")

# Gemini API configuration
# v1beta is required for function calling support
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_API_KEY_FILE = os.path.expanduser("~/gary_gemini_api_key")


def get_gemini_api_key() -> Optional[str]:
    """Load Gemini API key from file or environment."""
    # Try environment first
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    
    # Try the key file
    if os.path.exists(GEMINI_API_KEY_FILE):
        try:
            with open(GEMINI_API_KEY_FILE, 'r') as f:
                return f.read().strip()
        except Exception as e:
            logging.warning(f"Failed to read Gemini API key: {e}")
    return None


def is_gemini_model(model_name: str) -> bool:
    """Check if model name is a Gemini model."""
    return model_name.startswith("gemini-")


# =============================================================================
# DEBUG CONFIGURATION
# =============================================================================
# Enable with: export AN_DEBUG=1  (or AN_DEBUG=true, AN_DEBUG=verbose)
# Disable with: unset AN_DEBUG (or AN_DEBUG=0, AN_DEBUG=false)
#
# Log files:
#   /tmp/autonomous_navigator.log - Summary log (always on)
#   /tmp/an_debug.log - Verbose debug log (when enabled)
# =============================================================================

def is_debug_enabled() -> bool:
    """Check if debug logging is enabled via environment variable."""
    # Default to ON for troubleshooting
    val = os.environ.get("AN_DEBUG", "1").lower()
    return val in ("1", "true", "yes", "verbose", "on")


def is_verbose() -> bool:
    """Check if EXTRA verbose (full prompts/responses) is enabled."""
    # Default to VERBOSE for troubleshooting
    return os.environ.get("AN_DEBUG", "verbose").lower() in ("verbose", "1", "true", "yes", "on")


# =============================================================================
# =============================================================================
# LOGGING SETUP (DEPRECATED - use logging_config.py instead)
# =============================================================================
# This function is kept for backward compatibility but should not be used.
# Import from logging_config instead: from .logging_config import get_logger

def get_logger():
    """DEPRECATED: Use logging_config.get_logger() instead."""
    from .logging_config import get_logger as new_get_logger
    return new_get_logger()
