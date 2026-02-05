"""
Navigation Timing Configuration
===============================

Centralized timing settings loaded from environment variables.
All delays configurable via .env file.
"""

import os


def _get_int(key: str, default: int) -> int:
    """Get int from env with default."""
    return int(os.environ.get(key, default))


def _get_float(key: str, default: float) -> float:
    """Get float from env with default."""
    return float(os.environ.get(key, default))


# Millisecond delays (for page.wait_for_timeout)
DELAY_SHORT = _get_int("MITCHELL_NAV_DELAY_SHORT", 300)      # Quick UI updates
DELAY_MEDIUM = _get_int("MITCHELL_NAV_DELAY_MEDIUM", 1000)   # Page transitions
DELAY_LONG = _get_int("MITCHELL_NAV_DELAY_LONG", 3000)       # Heavy content loads
DELAY_AJAX = _get_int("MITCHELL_NAV_DELAY_AJAX", 600)        # After AJAX requests

# Second delays (for asyncio.sleep)
DELAY_STEP = _get_float("MITCHELL_NAV_DELAY_STEP", 0.6)      # Between nav steps
DELAY_MODAL = _get_float("MITCHELL_NAV_DELAY_MODAL", 1.0)    # After modal close

# Click/action timeouts (milliseconds)
TIMEOUT_CLICK_SHORT = _get_int("MITCHELL_TIMEOUT_CLICK_SHORT", 3000)   # Quick button clicks
TIMEOUT_CLICK_LONG = _get_int("MITCHELL_TIMEOUT_CLICK_LONG", 5000)     # Slower element clicks
TIMEOUT_MODAL_CLOSE = _get_int("MITCHELL_TIMEOUT_MODAL_CLOSE", 2000)   # Modal close button

# Action/operation timeouts (seconds)
TIMEOUT_ACTION = _get_float("MITCHELL_TIMEOUT_ACTION", 10.0)           # General action timeout
TIMEOUT_HTTP = _get_float("MITCHELL_TIMEOUT_HTTP", 60.0)               # HTTP client timeout
TIMEOUT_OLLAMA = _get_float("MITCHELL_TIMEOUT_OLLAMA", 120.0)          # Ollama (local model) timeout

# Truncation limits
MAX_PAGE_TEXT = _get_int("MITCHELL_MAX_PAGE_TEXT", 2500)               # Max page text chars (Ollama)
MAX_HISTORY_GEMINI = _get_int("MITCHELL_MAX_HISTORY_GEMINI", 5)        # Max history items for Gemini
MAX_HISTORY_LOOP = _get_int("MITCHELL_MAX_HISTORY_LOOP", 8)            # Max history items for nav loop
MAX_HISTORY_OLLAMA = _get_int("MITCHELL_MAX_HISTORY_OLLAMA", 3)        # Max history items for Ollama
MAX_ELEMENTS_OLLAMA = _get_int("MITCHELL_MAX_ELEMENTS_OLLAMA", 35)     # Max elements for Ollama
