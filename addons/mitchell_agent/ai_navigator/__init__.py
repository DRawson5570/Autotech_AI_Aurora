"""
AI-Driven Navigation for Mitchell OnDemand
==========================================

This module provides intelligent, dynamic navigation using LLM reasoning
instead of hard-coded paths. The AI explores the UI like a human would,
making decisions based on what it sees and backtracking when needed.

Key Components:
- element_extractor: Extracts all interactive elements from the page
- ai_navigator: LLM-based decision making and action selection  
- action_executor: Executes actions (click, type, select, etc.)
- navigation_loop: Main orchestration with systematic exploration
- navigation_memory: Learning from experience
- common_sense: Heuristic ranking of candidate paths

Usage:
    from addons.mitchell_agent.ai_navigator import NavigationLoop, ai_navigate
    
    # Quick usage
    result = await ai_navigate(page, "Find fluid capacities", vehicle_dict)
    
    # Full control with learning
    loop = NavigationLoop(page, api_key="...", max_steps_per_path=8)
    result = await loop.navigate("Find fluid capacities", vehicle_dict)
"""

from .element_extractor import (
    extract_interactive_elements,
    get_page_state,
    get_visible_text,
    ElementInfo,
    PageState,
)
from .ai_navigator import (
    AINavigator,
    NavigationAction,
    NavigationResult,
    ActionType,
)
from .action_executor import ActionExecutor
from .navigation_loop import NavigationLoop, ai_navigate, ai_navigate_with_vehicle
from .navigation_memory import (
    NavigationMemory,
    NavigationStep,
    LearnedPath,
    get_memory,
    record_success,
    record_failure,
    get_known_path,
    get_selectors,
)
from .common_sense import (
    rank_candidates,
    get_top_candidates,
    QUICK_ACCESS_BUTTONS,
)

# Import from refactored modules (an_*.py)
from .an_navigator import (
    AutonomousNavigator,
    query_mitchell_autonomous,
)

# Backwards compatibility - also export from old location name
# (autonomous_navigator.py is now just a re-export wrapper)


__all__ = [
    # Element extraction
    "extract_interactive_elements",
    "get_page_state",
    "get_visible_text",
    "ElementInfo",
    "PageState",
    # AI navigation
    "AINavigator",
    "NavigationAction",
    "NavigationResult",
    "ActionType",
    # Execution
    "ActionExecutor",
    # Main loop
    "NavigationLoop",
    "ai_navigate",
    "ai_navigate_with_vehicle",
    # Autonomous navigator (new unified approach)
    "AutonomousNavigator",
    "query_mitchell_autonomous",
    # Memory/learning
    "NavigationMemory",
    "get_memory",
    "record_success",
    "record_failure",
    "get_known_path",
    # Common sense
    "rank_candidates",
    "get_top_candidates",
    "QUICK_ACCESS_BUTTONS",
]
