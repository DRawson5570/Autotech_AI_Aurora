"""
AutoDB Agent - AI-powered navigation for Operation CHARM service manuals.

Brain-only architecture: The AI navigates static HTML pages via HTTP,
no browser automation needed.
"""

from .models import PageState, NavigationResult, ToolResult, Vehicle, PathStep
from .config import config, AutodbConfig
from .navigator import AutodbNavigator, query_autodb

__all__ = [
    "AutodbNavigator",
    "query_autodb",
    "PageState",
    "NavigationResult",
    "ToolResult",
    "Vehicle",
    "PathStep",
    "config",
    "AutodbConfig",
]
