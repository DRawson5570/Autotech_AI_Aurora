"""
AI Navigator - Gemini-based Decision Making
============================================

Uses Gemini to reason about page state and decide next actions.
The AI explores the UI like a human mechanic would.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx

from .element_extractor import PageState, ElementInfo
from .timing import TIMEOUT_HTTP, MAX_HISTORY_GEMINI

log = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of actions the AI can take."""
    CLICK = "click"
    TYPE = "type"
    SELECT = "select"
    SCROLL = "scroll"
    BACK = "back"
    CLOSE_MODAL = "close_modal"
    WAIT = "wait"
    EXTRACT_DATA = "extract_data"
    DONE = "done"
    FAIL = "fail"


@dataclass
class NavigationAction:
    """An action decided by the AI."""
    action_type: ActionType
    selector: Optional[str] = None
    text: Optional[str] = None  # For TYPE action
    element_id: Optional[int] = None  # Reference to extracted element
    reason: str = ""
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action_type.value,
            "selector": self.selector,
            "text": self.text,
            "element_id": self.element_id,
            "reason": self.reason,
            "confidence": self.confidence
        }


@dataclass 
class NavigationResult:
    """Result of a navigation session."""
    success: bool
    data: Optional[str] = None
    message: str = ""
    steps_taken: int = 0
    history: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.history is None:
            self.history = []


# Gemini function declarations for navigation
NAVIGATION_TOOLS = [{
    "function_declarations": [
        {
            "name": "click",
            "description": "Click on an interactive element to navigate or expand content",
            "parameters": {
                "type": "object",
                "properties": {
                    "element_id": {
                        "type": "integer",
                        "description": "The ID number of the element from the elements list (e.g., 5)"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why you're clicking this element"
                    }
                },
                "required": ["element_id", "reason"]
            }
        },
        {
            "name": "type_text",
            "description": "Type text into an input field",
            "parameters": {
                "type": "object", 
                "properties": {
                    "element_id": {
                        "type": "integer",
                        "description": "The ID of the input element"
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to type"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why typing this"
                    }
                },
                "required": ["element_id", "text", "reason"]
            }
        },
        {
            "name": "close_modal",
            "description": "Close the currently open modal/dialog to go back",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why closing the modal"
                    }
                },
                "required": ["reason"]
            }
        },
        # NOTE: go_back removed - browser back is too dangerous
        {
            "name": "scroll",
            "description": "Scroll the page to see more content",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "description": "up or down"
                    }
                },
                "required": ["direction"]
            }
        },
        {
            "name": "scroll",
            "description": "Scroll the page to see more content",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["down", "up"],
                        "description": "Scroll direction"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why scrolling"
                    }
                },
                "required": ["direction", "reason"]
            }
        },
        {
            "name": "extract_data",
            "description": "The requested data is visible on the current page. Extract and return it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "string",
                        "description": "The extracted data in a clear, formatted way"
                    },
                    "complete": {
                        "type": "boolean",
                        "description": "True if all requested data was found"
                    }
                },
                "required": ["data", "complete"]
            }
        },
        {
            "name": "done",
            "description": "Navigation complete - either succeeded or cannot continue",
            "parameters": {
                "type": "object",
                "properties": {
                    "success": {
                        "type": "boolean",
                        "description": "Whether the goal was achieved"
                    },
                    "message": {
                        "type": "string",
                        "description": "Summary of what happened"
                    },
                    "data": {
                        "type": "string",
                        "description": "Any extracted data"
                    }
                },
                "required": ["success", "message"]
            }
        }
    ]
}]


def build_navigation_prompt(goal: str, vehicle: Dict[str, str]) -> str:
    """
    Build the system prompt for navigation.
    
    Args:
        goal: What data/page we're trying to reach
        vehicle: Vehicle info dict
    """
    year = vehicle.get("year", "")
    make = vehicle.get("make", "")
    model = vehicle.get("model", "")
    engine = vehicle.get("engine", "")
    
    return f"""You are a navigation agent for ShopKeyPro, an automotive repair database.

VEHICLE: {year} {make} {model} {engine}
GOAL: {goal}

ACTIONS:
• click(element_id, reason) - Click an element from the table
• extract_data(data, complete=true) - Extract data visible on page  
• close_modal(reason) - Close current modal
• scroll(direction, reason) - Scroll page
• done(success, message) - Navigation complete

HOW TO DECIDE:

1. READ the PAGE CONTENT section
2. ASK: Does it contain ACTUAL DATA (numbers, specs, steps)?
   - YES → extract_data with the values
   - NO (just menu items/categories) → click the relevant item

DATA vs NAVIGATION:
• Menu/Navigation: "Fluid Capacities", "Wiring Diagrams", "STARTING/CHARGING" → CLICK
• Actual Data: "5.7 QTS", "118 Ft. Lbs.", step-by-step procedure → EXTRACT

TREE STRUCTURES:
Many pages have expandable trees. Keep clicking until you reach:
• For specs: Actual values with units (QTS, L, Ft. Lbs.)
• For procedures: Step-by-step instructions
• For diagrams: SVG/image content (look for svg, img, object tags)

IMPORTANT:
• Only use element IDs from the CLICKABLE ELEMENTS table
• Section headers are NOT data - keep navigating
• For diagrams: Navigate until you see actual image elements, not just titles"""


def build_user_message(page_state: PageState, page_text: str, history: List[str]) -> str:
    """
    Build the user message with current page state.
    
    Args:
        page_state: Current page state
        page_text: Visible text content for data extraction
        history: List of previous actions taken
    """
    parts = []
    
    # Add history of recent actions
    if history:
        parts.append("=== RECENT ACTIONS ===")
        for h in history[-MAX_HISTORY_GEMINI:]:  # Configurable limit
            parts.append(h)
        parts.append("")
    
    # Add page state (no truncation)
    parts.append(page_state.to_llm_context(max_elements=None))
    
    # Add page text for data extraction (no truncation)
    if page_text:
        parts.append("")
        parts.append("=== PAGE TEXT (for data extraction) ===")
        parts.append(page_text)
    
    parts.append("")
    parts.append("What is your next action? Use one of the available functions.")
    
    return "\n".join(parts)


class AINavigator:
    """
    AI-driven navigator using Gemini for decision making.
    
    Usage:
        nav = AINavigator(api_key="...", model="gemini-2.0-flash")
        action = await nav.decide_action(page_state, page_text, goal, vehicle, history)
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        timeout: float = None,
        max_retries: int = 3
    ):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout if timeout is not None else TIMEOUT_HTTP
        self.max_retries = max_retries
    
    async def decide_action(
        self,
        page_state: PageState,
        page_text: str,
        goal: str,
        vehicle: Dict[str, str],
        history: List[str],
    ) -> NavigationAction:
        """
        Decide the next navigation action based on page state.
        
        Args:
            page_state: Current page state with elements
            page_text: Visible text content
            goal: What we're trying to find
            vehicle: Vehicle info
            history: Previous actions taken
            
        Returns:
            NavigationAction to execute
        """
        system_prompt = build_navigation_prompt(goal, vehicle)
        user_message = build_user_message(page_state, page_text, history)
        
        # Log what we're sending
        log.debug(f"Asking Gemini for next action. Goal: {goal}")
        log.debug(f"Page has {len(page_state.elements)} elements, modal={page_state.has_modal}")
        
        try:
            response = await self._call_gemini(system_prompt, user_message)
            action = self._parse_response(response, page_state.elements)
            
            if action:
                log.info(f"AI decided: {action.action_type.value} - {action.reason}")
                return action
            else:
                log.warning("AI returned no valid action")
                return NavigationAction(
                    action_type=ActionType.FAIL,
                    reason="AI returned no valid action"
                )
                
        except Exception as e:
            log.error(f"AI decision failed: {e}")
            return NavigationAction(
                action_type=ActionType.FAIL,
                reason=f"AI error: {str(e)}"
            )
    
    async def _call_gemini(self, system_prompt: str, user_message: str) -> Dict[str, Any]:
        """Call Gemini API with retry logic."""
        payload = {
            "contents": [{"role": "user", "parts": [{"text": user_message}]}],
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "tools": NAVIGATION_TOOLS,
            "tool_config": {"function_calling_config": {"mode": "ANY"}},
            "generation_config": {"temperature": 0.1}  # Low temp for deterministic decisions
        }
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    resp = await client.post(url, json=payload)
                    
                    if resp.status_code == 429:
                        if attempt < self.max_retries - 1:
                            delay = 2 ** (attempt + 1)
                            log.warning(f"Rate limited, waiting {delay}s...")
                            await asyncio.sleep(delay)
                            continue
                        raise Exception("Rate limit exceeded")
                    
                    resp.raise_for_status()
                    return resp.json()
                    
                except httpx.TimeoutException:
                    if attempt < self.max_retries - 1:
                        log.warning(f"Timeout, retry {attempt + 1}")
                        await asyncio.sleep(1)
                        continue
                    raise
        
        return {}
    
    def _parse_response(
        self,
        response: Dict[str, Any],
        elements: List[ElementInfo]
    ) -> Optional[NavigationAction]:
        """Parse Gemini response into NavigationAction."""
        candidates = response.get("candidates", [])
        if not candidates:
            return None
        
        parts = candidates[0].get("content", {}).get("parts", [])
        
        for part in parts:
            if "functionCall" not in part:
                continue
            
            func = part["functionCall"]
            name = func["name"]
            args = func.get("args", {})
            
            # Map function calls to actions
            if name == "click":
                elem_id = args.get("element_id")
                # Find the element's selector
                selector = None
                for elem in elements:
                    if elem.id == elem_id:
                        selector = elem.selector
                        break
                
                if not selector:
                    log.warning(f"Element ID {elem_id} not found in elements list")
                    return NavigationAction(
                        action_type=ActionType.FAIL,
                        reason=f"Invalid element ID: {elem_id}"
                    )
                
                return NavigationAction(
                    action_type=ActionType.CLICK,
                    selector=selector,
                    element_id=elem_id,
                    reason=args.get("reason", "")
                )
            
            elif name == "type_text":
                elem_id = args.get("element_id")
                selector = None
                for elem in elements:
                    if elem.id == elem_id:
                        selector = elem.selector
                        break
                
                return NavigationAction(
                    action_type=ActionType.TYPE,
                    selector=selector,
                    element_id=elem_id,
                    text=args.get("text", ""),
                    reason=args.get("reason", "")
                )
            
            elif name == "close_modal":
                return NavigationAction(
                    action_type=ActionType.CLOSE_MODAL,
                    reason=args.get("reason", "")
                )
            
            elif name == "go_back":
                return NavigationAction(
                    action_type=ActionType.BACK,
                    reason=args.get("reason", "")
                )
            
            elif name == "scroll":
                direction = args.get("direction", "down")
                return NavigationAction(
                    action_type=ActionType.SCROLL,
                    text=direction,
                    reason=args.get("reason", "")
                )
            
            elif name == "extract_data":
                return NavigationAction(
                    action_type=ActionType.EXTRACT_DATA,
                    text=args.get("data", ""),
                    reason=f"complete={args.get('complete', False)}"
                )
            
            elif name == "done":
                success = args.get("success", False)
                return NavigationAction(
                    action_type=ActionType.DONE if success else ActionType.FAIL,
                    text=args.get("data", ""),
                    reason=args.get("message", "")
                )
        
        return None
