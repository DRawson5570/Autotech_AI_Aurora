"""
Server-Side Navigation Brain
=============================
Uses the server's Ollama model to decide navigation actions.

This allows clients without GPUs to use the AI Employee - they just send
page state and execute the returned actions.

Token Usage Tracking:
- Ollama returns prompt_eval_count and eval_count in response
- We track these and return them so the caller can bill the user
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("mitchell-navigation")


@dataclass
class NavigationDecision:
    """Result from navigation decision with token tracking."""
    tool: str
    args: Dict[str, Any]
    done: bool = False
    needs_clarification: bool = False
    error: Optional[str] = None
    # Token usage from Ollama
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


# Server's Ollama configuration
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen3:8b"

# Tool definitions (same as client-side navigator)
NAVIGATION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "select_year",
            "description": "Select a year from the vehicle selector",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "string", "description": "The year to select, e.g. '2018'"}
                },
                "required": ["year"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "select_make",
            "description": "Select a make/manufacturer from the vehicle selector",
            "parameters": {
                "type": "object",
                "properties": {
                    "make": {"type": "string", "description": "The make to select, e.g. 'Ford'"}
                },
                "required": ["make"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "select_model",
            "description": "Select a vehicle model from the selector",
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "The model to select, e.g. 'F-150'"}
                },
                "required": ["model"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "select_engine",
            "description": "Select an engine from the vehicle selector",
            "parameters": {
                "type": "object",
                "properties": {
                    "engine": {"type": "string", "description": "The engine to select, e.g. '5.0L VIN 5'"}
                },
                "required": ["engine"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "select_submodel",
            "description": "Select a submodel/trim from the vehicle selector",
            "parameters": {
                "type": "object",
                "properties": {
                    "submodel": {"type": "string", "description": "The submodel to select, e.g. 'XLT'"}
                },
                "required": ["submodel"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "select_body_style",
            "description": "Select a body style option",
            "parameters": {
                "type": "object",
                "properties": {
                    "body_style": {"type": "string", "description": "The body style, e.g. '4D Pickup Crew Cab'"}
                },
                "required": ["body_style"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "select_drive_type",
            "description": "Select a drive type option (4WD, RWD, AWD, FWD)",
            "parameters": {
                "type": "object",
                "properties": {
                    "drive_type": {"type": "string", "description": "The drive type, e.g. '4WD' or 'RWD'"}
                },
                "required": ["drive_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "request_info",
            "description": "Request missing information from the user when the goal doesn't specify a required option.",
            "parameters": {
                "type": "object",
                "properties": {
                    "option_name": {"type": "string", "description": "What option is needed, e.g. 'Drive Type'"},
                    "available_values": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of available options to choose from"
                    },
                    "message": {"type": "string", "description": "A helpful message explaining what's needed"}
                },
                "required": ["option_name", "available_values", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_vehicle",
            "description": "Confirm the vehicle selection after all options are selected",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": "Navigation is complete - vehicle selector is closed",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    }
]

SYSTEM_MESSAGE = """You are navigating a vehicle selection interface. Your goal is to select the vehicle specified by the user.

IMPORTANT RULES:
1. Look at the current state - what tab is active and what values are available
2. Choose ONE action to take based on the goal and current state
3. Options with values need to be selected - options with empty [] will appear after you select earlier options
4. Select options that ARE specified in the goal first (e.g., body style "4D Pickup Crew Cab")
5. Only use request_info when you need to select an option that is NOT in the goal AND has available values
6. Items marked with * are already selected - don't re-select them
7. When Tab is None, the selector is closed - use done

ORDER OF OPERATIONS on Options tab:
- First, select any options that ARE mentioned in the goal (like body style)
- Then, if new options appear (like Drive Type with actual values), check if they're in the goal
- Only request_info for options with values that aren't specified in the goal"""


def format_state_message(state: Dict[str, Any], goal: str) -> str:
    """Format page state as a user message for the model."""
    tab = state.get("current_tab") or "None"
    values = state.get("values", [])[:15]
    
    msg = f"""GOAL: {goal}

CURRENT STATE:
- Tab: {tab}
- Available values: {values}"""
    
    if state.get("options"):
        completed = []
        pending = []
        for opt in state["options"]:
            vals = opt.get("values", [])
            if not vals:
                continue
            has_selection = any(v.get("selected") for v in vals)
            if has_selection:
                selected_val = next((v["text"] for v in vals if v.get("selected")), "?")
                completed.append(f"{opt['name']}: {selected_val}")
            else:
                pending.append(f"{opt['name']}: {[v['text'] for v in vals]}")
        
        if completed:
            msg += f"\n\n✅ ALREADY SELECTED (do not re-select):\n  " + "\n  ".join(completed)
        if pending:
            msg += f"\n\n⚠️ NEEDS SELECTION (pick one OR request_info if not in goal):\n  " + "\n  ".join(pending)
    
    msg += "\n\nWhat action should I take next?"
    return msg


async def get_navigation_decision(goal: str, state: Dict[str, Any], step: int = 1) -> NavigationDecision:
    """
    Use the server's Ollama model to decide the next navigation action.
    
    Args:
        goal: Vehicle selection goal (e.g., "2018 Ford F-150 5.0L XLT")
        state: Current page state (tab, values, options)
        step: Current step number (for logging)
    
    Returns:
        NavigationDecision with tool, args, and token usage for billing
    """
    tab = state.get("current_tab")
    
    # If selector is closed, we're done (no tokens used)
    if tab is None:
        return NavigationDecision(tool="done", args={}, done=True)
    
    # Build message for model
    user_msg = format_state_message(state, goal)
    
    messages = [
        {"role": "system", "content": SYSTEM_MESSAGE},
        {"role": "user", "content": user_msg}
    ]
    
    # Call Ollama
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "tools": NAVIGATION_TOOLS,
                "stream": False,
                "options": {"temperature": 0.1}
            }
        )
        response.raise_for_status()
        result = response.json()
    
    # Extract token usage from Ollama response
    # Ollama returns: prompt_eval_count (input), eval_count (output)
    prompt_tokens = result.get("prompt_eval_count", 0)
    completion_tokens = result.get("eval_count", 0)
    total_tokens = prompt_tokens + completion_tokens
    
    logger.debug(f"Step {step}: tokens used - prompt={prompt_tokens}, completion={completion_tokens}")
    
    # Extract tool call
    message = result.get("message", {})
    tool_calls = message.get("tool_calls", [])
    
    if not tool_calls:
        # No tool call - model might have just responded with text
        logger.warning(f"Step {step}: No tool call from model")
        return NavigationDecision(
            tool="done", args={}, done=False, error="No tool call",
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens
        )
    
    tool_call = tool_calls[0]
    func = tool_call.get("function", {})
    tool_name = func.get("name")
    args = func.get("arguments", {})
    
    logger.info(f"Step {step}: {tool_name}({args})")
    
    # Handle special cases
    if tool_name == "done":
        return NavigationDecision(
            tool="done", args={}, done=True,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens
        )
    
    if tool_name == "request_info":
        return NavigationDecision(
            tool="request_info", args=args, done=False, needs_clarification=True,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens
        )
    
    return NavigationDecision(
        tool=tool_name, args=args, done=False, needs_clarification=False,
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens
    )
