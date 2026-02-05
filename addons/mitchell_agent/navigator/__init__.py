"""
Navigator Module
================
Unified browser automation for ShopKeyPro.
"""

from .core import MitchellNavigator
from .config import NavigatorConfig
from .quick_access import get_quick_access_selector, QUICK_ACCESS_BUTTONS
from .gemini import call_gemini, GEMINI_TOOLS

__all__ = [
    "MitchellNavigator",
    "NavigatorConfig",
    "get_quick_access_selector",
    "QUICK_ACCESS_BUTTONS",
    "call_gemini",
    "GEMINI_TOOLS",
]
