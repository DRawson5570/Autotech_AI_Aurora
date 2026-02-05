"""
Ollama Navigator - Local LLM Decision Making
=============================================

Uses local Ollama models for navigation decisions.
Drop-in replacement for Gemini-based AINavigator.
"""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from .element_extractor import PageState, ElementInfo
from .ai_navigator import (
    ActionType, NavigationAction, 
    build_navigation_prompt
)
from .timing import TIMEOUT_OLLAMA, MAX_PAGE_TEXT, MAX_HISTORY_OLLAMA, MAX_ELEMENTS_OLLAMA

log = logging.getLogger(__name__)


def build_user_message_compact(
    page_state: PageState,
    page_text: str,
    history: List[str],
    goal: str = "",
) -> str:
    """
    Build a compact user message for Ollama (smaller context).
    Clear table format so AI knows exactly what it can do.
    """
    parts = []
    
    # Brief history
    if history:
        parts.append("RECENT ACTIONS:")
        for h in history[-MAX_HISTORY_OLLAMA:]:
            parts.append(f"  • {h[:60]}")
        parts.append("")
    
    # State
    parts.append(f"STATE: {'Inside a modal/popup' if page_state.has_modal else 'On main page'}")
    parts.append("")
    
    # Check for images/diagrams in elements
    image_elements = [e for e in page_state.elements 
                      if e.tag in ('svg', 'img', 'object', 'canvas') or 
                      'svg' in (e.element_class or '').lower()]
    if image_elements:
        parts.append("📊 IMAGE/DIAGRAM DETECTED - may contain wiring diagram or visual")
        parts.append("")
    
    # Clear table of clickable elements
    parts.append("CLICKABLE ELEMENTS (use ID number to click):")
    parts.append("-" * 50)
    parts.append(f"{'ID':<4} {'Type':<8} {'Text':<35}")
    parts.append("-" * 50)
    
    for elem in page_state.elements[:MAX_ELEMENTS_OLLAMA]:
        text = (elem.text[:32] + "...") if elem.text and len(elem.text) > 35 else (elem.text or "")
        text = text.replace("\n", " ").strip()
        tag = elem.tag[:6]
        # Highlight image types
        if elem.tag in ('svg', 'img', 'object'):
            tag = f"📊{elem.tag}"
        parts.append(f"[{elem.id:<2}] {tag:<8} {text}")
    
    if len(page_state.elements) > MAX_ELEMENTS_OLLAMA:
        parts.append(f"... +{len(page_state.elements) - MAX_ELEMENTS_OLLAMA} more elements")
    parts.append("-" * 50)
    parts.append("")
    
    # Page content
    parts.append("PAGE CONTENT:")
    parts.append("=" * 50)
    if page_text:
        # Truncate but try to keep it readable
        content = page_text[:MAX_PAGE_TEXT].replace("\n\n\n", "\n\n")
        parts.append(content)
    else:
        parts.append("(No text content visible)")
    parts.append("=" * 50)
    parts.append("")
    
    # Decision guide
    parts.append("YOUR DECISION:")
    parts.append("• If PAGE CONTENT has actual data (values, specs, procedures) → extract_data")
    parts.append("• If PAGE CONTENT only shows menus/categories → click the relevant one")
    parts.append("• For diagrams: navigate until you see SVG/image content, not just titles")
    
    return "\n".join(parts)
    
    return "\n".join(parts)


# Ollama tool definitions (OpenAI-compatible format)
OLLAMA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "Click on an interactive element to navigate or expand content",
            "parameters": {
                "type": "object",
                "properties": {
                    "element_id": {
                        "type": "integer",
                        "description": "The ID number of the element from the elements list"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why you're clicking this element"
                    }
                },
                "required": ["element_id", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extract_data",
            "description": "Extract the requested data when you've found it on the page",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "string",
                        "description": "The extracted data matching the goal"
                    },
                    "complete": {
                        "type": "boolean",
                        "description": "True if this is all the requested data"
                    }
                },
                "required": ["data", "complete"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "close_modal",
            "description": "Close the currently open modal/popup",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why you're closing the modal"
                    }
                },
                "required": ["reason"]
            }
        }
    },
    # NOTE: go_back removed - browser back is too dangerous, can navigate away from ShopKeyPro
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": "Navigation complete - either succeeded or giving up",
            "parameters": {
                "type": "object",
                "properties": {
                    "success": {
                        "type": "boolean",
                        "description": "True if goal was achieved"
                    },
                    "message": {
                        "type": "string",
                        "description": "Summary of outcome"
                    },
                    "data": {
                        "type": "string",
                        "description": "Any data found (if successful)"
                    }
                },
                "required": ["success", "message"]
            }
        }
    }
]


class OllamaNavigator:
    """
    Local LLM navigator using Ollama.
    
    Usage:
        nav = OllamaNavigator(model="llama3.1:8b")
        action = await nav.decide_action(page_state, page_text, goal, vehicle, history)
    """
    
    def __init__(
        self,
        model: str = "llama3.1:8b",
        host: str = "http://localhost:11434",
        timeout: float = None,  # Default from config
        max_retries: int = 2
    ):
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout if timeout is not None else TIMEOUT_OLLAMA
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
        Decide the next navigation action using local Ollama model.
        """
        system_prompt = build_navigation_prompt(goal, vehicle)
        user_message = build_user_message_compact(page_state, page_text, history)
        
        log.debug(f"Asking Ollama ({self.model}) for next action. Goal: {goal}")
        log.debug(f"Page has {len(page_state.elements)} elements, modal={page_state.has_modal}")
        
        try:
            response = await self._call_ollama(system_prompt, user_message)
            action = self._parse_response(response, page_state.elements)
            
            if action:
                log.info(f"Ollama decided: {action.action_type.value} - {action.reason}")
                return action
            else:
                log.warning("Ollama returned no valid action")
                return NavigationAction(
                    action_type=ActionType.FAIL,
                    reason="Ollama returned no valid action"
                )
                
        except Exception as e:
            log.error(f"Ollama decision failed: {e}")
            return NavigationAction(
                action_type=ActionType.FAIL,
                reason=f"Ollama error: {str(e)}"
            )
    
    async def _call_ollama(self, system_prompt: str, user_message: str) -> Dict[str, Any]:
        """Call Ollama API with tool support."""
        
        # Use chat endpoint with tools
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "tools": OLLAMA_TOOLS,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temp for deterministic decisions
                "num_predict": 512   # Limit response length
            }
        }
        
        url = f"{self.host}/api/chat"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    log.debug(f"Calling Ollama (attempt {attempt + 1})...")
                    resp = await client.post(url, json=payload)
                    resp.raise_for_status()
                    result = resp.json()
                    log.debug(f"Ollama response keys: {result.keys()}")
                    return result
                    
                except httpx.TimeoutException:
                    if attempt < self.max_retries - 1:
                        log.warning(f"Ollama timeout, retry {attempt + 1}")
                        await asyncio.sleep(1)
                        continue
                    raise
                except Exception as e:
                    log.error(f"Ollama call failed: {e}")
                    raise
        
        return {}
    
    def _parse_response(
        self,
        response: Dict[str, Any],
        elements: List[ElementInfo]
    ) -> Optional[NavigationAction]:
        """Parse Ollama response into NavigationAction."""
        
        message = response.get("message", {})
        
        # Check for tool calls
        tool_calls = message.get("tool_calls", [])
        
        if tool_calls:
            return self._parse_tool_call(tool_calls[0], elements)
        
        # Fallback: try to parse from content (some models output JSON directly)
        content = message.get("content", "")
        if content:
            return self._parse_content_fallback(content, elements)
        
        return None
    
    def _parse_tool_call(
        self, 
        tool_call: Dict[str, Any], 
        elements: List[ElementInfo]
    ) -> Optional[NavigationAction]:
        """Parse a tool call into NavigationAction."""
        
        func = tool_call.get("function", {})
        name = func.get("name", "")
        args = func.get("arguments", {})
        
        # Args might be string JSON
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except:
                args = {}
        
        log.debug(f"Tool call: {name}({args})")
        
        if name == "click":
            elem_id = args.get("element_id")
            selector = None
            for elem in elements:
                if elem.id == elem_id:
                    selector = elem.selector
                    break
            
            if not selector:
                log.warning(f"Element ID {elem_id} not found")
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
        
        elif name == "extract_data":
            return NavigationAction(
                action_type=ActionType.EXTRACT_DATA,
                text=args.get("data", ""),
                reason=f"complete={args.get('complete', False)}"
            )
        
        elif name == "close_modal":
            return NavigationAction(
                action_type=ActionType.CLOSE_MODAL,
                reason=args.get("reason", "")
            )
        
        elif name == "go_back":
            # go_back is disabled - too dangerous, treat as close_modal
            return NavigationAction(
                action_type=ActionType.CLOSE_MODAL,
                reason=args.get("reason", "") + " (go_back converted to close_modal)",
            )
        
        elif name == "done":
            success = args.get("success", False)
            return NavigationAction(
                action_type=ActionType.DONE if success else ActionType.FAIL,
                text=args.get("data", ""),
                reason=args.get("message", "")
            )
        
        return None
    
    def _parse_content_fallback(
        self, 
        content: str, 
        elements: List[ElementInfo]
    ) -> Optional[NavigationAction]:
        """
        Fallback parser for models that output text instead of tool calls.
        Looks for JSON or structured patterns in the response.
        """
        log.debug(f"Trying content fallback parse: {content[:200]}...")
        
        # Try to find JSON in the response
        json_match = re.search(r'\{[^{}]*"(click|extract_data|done|go_back|close_modal)"[^{}]*\}', content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                # Convert to tool call format
                for key in ["click", "extract_data", "done", "go_back", "close_modal"]:
                    if key in data or data.get("action") == key:
                        return self._parse_tool_call(
                            {"function": {"name": key, "arguments": data}},
                            elements
                        )
            except:
                pass
        
        # Look for "click element X" pattern
        click_match = re.search(r'click.*?(?:element|id).*?(\d+)', content, re.IGNORECASE)
        if click_match:
            elem_id = int(click_match.group(1))
            selector = None
            for elem in elements:
                if elem.id == elem_id:
                    selector = elem.selector
                    break
            
            if selector:
                return NavigationAction(
                    action_type=ActionType.CLICK,
                    selector=selector,
                    element_id=elem_id,
                    reason="Parsed from text response"
                )
        
        # Look for extract_data indicators
        if any(x in content.lower() for x in ["found the data", "extract", "here is the"]):
            # Try to extract the data portion
            data_match = re.search(r'data["\s:]+(.+?)(?:\n|$)', content, re.IGNORECASE)
            if data_match:
                return NavigationAction(
                    action_type=ActionType.EXTRACT_DATA,
                    text=data_match.group(1).strip(),
                    reason="Parsed from text response"
                )
        
        return None
