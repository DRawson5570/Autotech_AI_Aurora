"""
Navigator Module
================
Autonomous vehicle selection using LLM with native tool calling.

Supported backends:
- Gemini (default): Google's Gemini Flash - fast and cheap
- Ollama: Local Ollama instance with qwen3:8b
- Server: Autotech AI server's /navigate endpoint

Usage:
    from addons.mitchell_agent.agent.navigator import Navigator
    
    navigator = Navigator(page, on_clarification_needed=callback, backend="gemini")
    result = await navigator.navigate(goal="2018 Ford F-150 5.0L XLT")
"""

import asyncio
import json
import logging
import os
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass

import httpx


logger = logging.getLogger("mitchell-navigator")


class NavigatorBackend(str, Enum):
    """Which LLM backend to use for navigation."""
    GEMINI = "gemini"     # Google Gemini API (default)
    OLLAMA = "ollama"     # Local Ollama instance
    SERVER = "server"     # Autotech AI server endpoint


# Keep old enum for backward compatibility
class NavigationMode(str, Enum):
    """Deprecated: Use NavigatorBackend instead."""
    AUTO = "auto"
    LOCAL = "local"
    SERVER = "server"


@dataclass
class ClarificationRequest:
    """Request for clarification from Autotech AI."""
    option_name: str
    available_values: List[str]
    message: str


@dataclass
class NavigationResult:
    """Result of vehicle navigation."""
    success: bool
    clarifications: List[ClarificationRequest]
    error: Optional[str] = None
    auto_selected: Optional[Dict[str, str]] = None  # Track auto-selected options, e.g. {"submodel": "XL", "drive_type": "4WD"}


# Tool definitions for Ollama native tool calling
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
            "description": "Request missing information from the user when the goal doesn't specify a required option. Use this when you need to select an option but the goal doesn't tell you which one.",
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
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": "Navigation is complete - vehicle selector is closed or task is finished",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

SYSTEM_MESSAGE = """You are navigating a vehicle selector UI. Trust the SCREENSHOT to see the current state.

Use the appropriate select_* function based on what tab is currently active:
- Year tab → select_year
- Make tab → select_make  
- Model tab → select_model
- Engine tab → select_engine
- Submodel tab → select_submodel
- Options tab → select_body_style or select_drive_type

IMPORTANT: If an option (like body style, drive type, etc.) is NOT specified in the goal, you MUST use request_info to ask the user. Never guess.
Don't repeat actions that already succeeded."""


# Gemini function declarations (different format from Ollama)
GEMINI_TOOLS = [
    {
        "function_declarations": [
            {
                "name": "select_year",
                "description": "Select a year from the vehicle selector",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "year": {"type": "string", "description": "The year to select, e.g. '2018'"}
                    },
                    "required": ["year"]
                }
            },
            {
                "name": "select_make",
                "description": "Select a make/manufacturer from the vehicle selector",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "make": {"type": "string", "description": "The make to select, e.g. 'Ford'"}
                    },
                    "required": ["make"]
                }
            },
            {
                "name": "select_model",
                "description": "Select a vehicle model from the selector",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string", "description": "The model to select, e.g. 'F-150'"}
                    },
                    "required": ["model"]
                }
            },
            {
                "name": "select_engine",
                "description": "Select an engine from the vehicle selector",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "engine": {"type": "string", "description": "The engine to select, e.g. '5.0L VIN 5'"}
                    },
                    "required": ["engine"]
                }
            },
            {
                "name": "select_submodel",
                "description": "Select a submodel/trim from the vehicle selector. IMPORTANT: Match EXACTLY what's in the goal.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "submodel": {"type": "string", "description": "The submodel to select EXACTLY as specified in goal, e.g. 'XL' not 'XLT'"}
                    },
                    "required": ["submodel"]
                }
            },
            {
                "name": "select_body_style",
                "description": "Select a body style option",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "body_style": {"type": "string", "description": "The body style, e.g. '4D Pickup Crew Cab'"}
                    },
                    "required": ["body_style"]
                }
            },
            {
                "name": "select_drive_type",
                "description": "Select a drive type option (4WD, RWD, AWD, FWD)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "drive_type": {"type": "string", "description": "The drive type, e.g. '4WD' or 'RWD'"}
                    },
                    "required": ["drive_type"]
                }
            },
            {
                "name": "request_info",
                "description": "Request missing information from the user when the goal doesn't specify a required option",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "option_name": {"type": "string", "description": "What option is needed, e.g. 'Drive Type'"},
                        "available_values": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of available options"
                        },
                        "message": {"type": "string", "description": "A helpful message explaining what's needed"}
                    },
                    "required": ["option_name", "available_values", "message"]
                }
            },
            {
                "name": "confirm_vehicle",
                "description": "Confirm the vehicle selection after all options are selected",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "done",
                "description": "Navigation is complete - vehicle selector is closed or task is finished",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]
    }
]


class Navigator:
    """
    Autonomous vehicle selector using LLM for navigation decisions.
    
    Supports multiple backends:
    - GEMINI (default): Google Gemini Flash - fast and cheap
    - OLLAMA: Local Ollama instance with qwen3:8b
    - SERVER: Autotech AI server's /navigate endpoint
    
    Args:
        page: Playwright Page connected to ShopKeyPro
        on_clarification_needed: Async callback for handling info requests.
            Called with (option_name, available_values, message).
            Should return the user's selection or None to abort.
        backend: Which LLM to use (gemini, ollama, server)
        gemini_api_key: Google API key for Gemini (or set GEMINI_API_KEY env var)
        gemini_model: Gemini model to use (default: gemini-2.0-flash)
        ollama_url: Local Ollama API URL (default: localhost:11434)
        ollama_model: Ollama model to use (default: qwen3:8b)
        server_url: Autotech AI server URL for server-side navigation
        shop_id: Shop identifier
        request_id: Mitchell request ID (server uses this to lookup user for billing)
        max_steps: Maximum navigation steps before giving up
    """
    
    def __init__(
        self,
        page,
        on_clarification_needed: Optional[Callable[[str, List[str], str], Optional[str]]] = None,
        backend: NavigatorBackend = NavigatorBackend.GEMINI,
        gemini_api_key: Optional[str] = None,
        gemini_model: str = "gemini-2.0-flash",
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen3:8b",
        server_url: str = "https://automotive.aurora-sentient.net",
        shop_id: str = "",
        request_id: Optional[str] = None,
        max_steps: int = 25
    ):
        self.page = page
        self.on_clarification_needed = on_clarification_needed
        self.backend = backend
        
        # Gemini settings
        self.gemini_api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
        self.gemini_model = gemini_model
        self.gemini_url = "https://generativelanguage.googleapis.com/v1beta/models"
        
        # Ollama settings
        self.ollama_url = f"{ollama_url}/api/chat"
        self.ollama_model = ollama_model
        
        # Server settings
        self.server_url = f"{server_url}/api/mitchell/navigate"
        
        self.shop_id = shop_id
        self.request_id = request_id
        self.max_steps = max_steps
        
        # Parsed vehicle info (populated by _parse_goal)
        self._parsed_goal = {}
        
        # Debug settings
        self._screenshot_dir = "/tmp/navigator_screenshots"
        self._step_counter = 0
        
        logger.info(f"Navigator initialized with backend={backend.value}")
    
    async def _debug_screenshot(self, step_name: str, extra_info: str = "") -> str:
        """Take a screenshot and log the current state for debugging.
        
        Args:
            step_name: Short name for this step (e.g., "after_year_select")
            extra_info: Additional context to log
            
        Returns:
            Path to saved screenshot
        """
        import os
        from datetime import datetime
        
        self._step_counter += 1
        timestamp = datetime.now().strftime("%H%M%S")
        
        # Ensure screenshot directory exists
        os.makedirs(self._screenshot_dir, exist_ok=True)
        
        # Take screenshot
        filename = f"{self._step_counter:02d}_{step_name}_{timestamp}.png"
        filepath = os.path.join(self._screenshot_dir, filename)
        
        try:
            await self.page.screenshot(path=filepath)
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            filepath = "FAILED"
        
        # Get current state
        try:
            state = await self.page.evaluate("""
                () => {
                    const result = {};
                    
                    // Current tab
                    const tabs = document.querySelectorAll('#qualifierTypeSelector li');
                    result.all_tabs = Array.from(tabs).map(li => ({
                        text: li.textContent.trim(),
                        classes: li.className,
                        disabled: li.classList.contains('disabled')
                    }));
                    
                    // Find selected/active tab
                    for (const tab of tabs) {
                        if (tab.classList.contains('selected') || 
                            tab.classList.contains('active') ||
                            tab.classList.contains('current')) {
                            result.current_tab = tab.textContent.trim();
                            result.current_tab_class = tab.className;
                            break;
                        }
                    }
                    
                    // Values in right panel
                    const items = document.querySelectorAll('#qualifierValueSelector li.qualifier');
                    result.values = Array.from(items).slice(0, 10).map(li => li.textContent.trim());
                    result.value_count = items.length;
                    
                    // Also get selected state for each value
                    result.values_detail = Array.from(items).slice(0, 10).map(li => ({
                        text: li.textContent.trim(),
                        selected: li.classList.contains('selected')
                    }));
                    
                    // Check if Use This Vehicle button is enabled
                    const useBtn = document.querySelector('input[data-action="SelectComplete"]');
                    result.use_button_disabled = useBtn ? useBtn.disabled : null;
                    
                    // Check for vehicle display (selector might be closed)
                    const vehicleDisplay = document.querySelector('#vehicleSelectorButton');
                    result.vehicle_button_text = vehicleDisplay ? vehicleDisplay.textContent.trim() : null;
                    
                    // Check if selector is visible
                    const container = document.querySelector('#VehicleSelectorContainer');
                    result.selector_visible = container ? container.offsetParent !== null : false;
                    
                    return result;
                }
            """)
        except Exception as e:
            state = {"error": str(e)}
        
        # Log everything
        log_msg = (
            f"\n{'='*60}\n"
            f"STEP {self._step_counter}: {step_name}\n"
            f"{'='*60}\n"
            f"Screenshot: {filepath}\n"
            f"Current tab: {state.get('current_tab', 'NOT FOUND')}\n"
            f"Tab class: {state.get('current_tab_class', 'N/A')}\n"
            f"Values ({state.get('value_count', 0)}): {state.get('values', [])}\n"
            f"Use button disabled: {state.get('use_button_disabled')}\n"
            f"Selector visible: {state.get('selector_visible')}\n"
            f"Vehicle button: {state.get('vehicle_button_text', 'N/A')}\n"
        )
        
        # Log values with selected state
        if state.get('values_detail'):
            selected_vals = [v['text'] for v in state['values_detail'] if v.get('selected')]
            unselected_vals = [v['text'] for v in state['values_detail'] if not v.get('selected')]
            log_msg += f"Selected values: {selected_vals}\n"
            log_msg += f"Unselected values: {unselected_vals[:5]}\n"
        
        if state.get('all_tabs'):
            log_msg += f"All tabs:\n"
            for tab in state['all_tabs']:
                log_msg += f"  - {tab['text']}: classes='{tab['classes']}' disabled={tab['disabled']}\n"
        
        if extra_info:
            log_msg += f"Extra: {extra_info}\n"
        
        log_msg += f"{'='*60}\n"
        
        logger.info(log_msg)
        
        # Also write to debug file
        with open("/tmp/navigator_debug.log", "a") as f:
            f.write(log_msg)
        
        return filepath

    def _parse_goal(self, goal: str) -> Dict[str, Optional[str]]:
        """
        Parse a goal string to extract vehicle components.
        
        Returns dict with: year, make, model, engine, submodel, body_style, drive_type
        Example goal: "2018 Ford F-150 5.0L XLT 2D Pickup 4WD"
        """
        import re
        
        result = {
            "year": None,
            "make": None, 
            "model": None,
            "engine": None,
            "submodel": None,
            "body_style": None,
            "drive_type": None
        }
        
        # Extract year (4 digits at start)
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', goal)
        if year_match:
            result["year"] = year_match.group(1)
        
        # Common makes
        makes = ["Ford", "Chevrolet", "Chevy", "Toyota", "Honda", "Nissan", "Dodge", "Ram", 
                 "Jeep", "GMC", "BMW", "Mercedes", "Audi", "Volkswagen", "VW", "Hyundai", 
                 "Kia", "Mazda", "Subaru", "Lexus", "Acura", "Infiniti", "Cadillac", "Buick",
                 "Lincoln", "Chrysler", "Porsche", "Volvo", "Tesla", "Mitsubishi"]
        for make in makes:
            if re.search(rf'\b{make}\b', goal, re.IGNORECASE):
                result["make"] = make
                break
        
        # Drive types
        drive_match = re.search(r'\b(4WD|AWD|RWD|FWD|4x4|4X4)\b', goal, re.IGNORECASE)
        if drive_match:
            result["drive_type"] = drive_match.group(1).upper()
        
        # Body styles
        body_patterns = [
            r'(\d+D\s+(?:Pickup|Sedan|Hatchback|Coupe|SUV|Wagon|Van|Cab)(?:\s+(?:Crew|Extended|Double|Regular|Extra)\s+Cab)?)',
            r'((?:Crew|Extended|Double|Regular|Extra)\s+Cab)',
            r'(\d+\s*[Dd]oor)',
        ]
        for pattern in body_patterns:
            body_match = re.search(pattern, goal, re.IGNORECASE)
            if body_match:
                result["body_style"] = body_match.group(1)
                break
        
        # Engine (look for L followed by optional V designation or just displacement)
        engine_match = re.search(r'\b(\d+\.\d+L?)\s*(V\d+)?', goal)
        if engine_match:
            engine = engine_match.group(1)
            if not engine.endswith('L'):
                engine += 'L'
            result["engine"] = engine
        
        # Model - extract word(s) after make, before engine/body/drive
        if result["make"]:
            # Get text after make
            make_pattern = rf'\b{result["make"]}\s+(.+)'
            model_match = re.search(make_pattern, goal, re.IGNORECASE)
            if model_match:
                rest = model_match.group(1)
                # Remove known suffixes (just the suffix, not everything after)
                for suffix in [result.get("engine", ""), result.get("body_style", ""), 
                              result.get("drive_type", "")]:
                    if suffix:
                        # Only remove the suffix word itself, keep what comes after
                        rest = re.sub(rf'\s*\b{re.escape(suffix)}\b\s*', ' ', rest, flags=re.IGNORECASE)
                
                # Split into tokens and identify model vs submodel
                model_tokens = rest.strip().split()
                if model_tokens:
                    # Take first token as model
                    result["model"] = model_tokens[0]
                    
                    # Store remaining tokens as potential submodel candidates
                    # These will be matched against available options from Mitchell
                    if len(model_tokens) > 1:
                        # Join remaining tokens - might be multi-word like "King Ranch"
                        result["submodel"] = " ".join(model_tokens[1:])
        
        logger.debug(f"Parsed goal '{goal}' -> {result}")
        return result

    # Common make aliases (user input -> ShopKeyPro name)
    MAKE_ALIASES = {
        "chevy": "Chevrolet",
        "vw": "Volkswagen",
        "mercedes": "Mercedes-Benz",
        "merc": "Mercedes-Benz",
    }

    async def _select_value_deterministic(self, value: str, tab_name: str) -> bool:
        """
        Deterministically select a value from the qualifier list.
        Much more reliable than AI-driven selection.
        """
        import asyncio
        
        # Apply make aliases if selecting Make
        if tab_name == "Make":
            value = self.MAKE_ALIASES.get(value.lower(), value)
        
        # Wait for values to load (especially important for Year on first load)
        await asyncio.sleep(0.5)
        
        # Get all options - wait up to 5 seconds for them to appear
        options = self.page.locator("#qualifierValueSelector li.qualifier")
        count = await options.count()
        
        if count == 0:
            logger.info(f"No {tab_name} options found yet, waiting...")
            for wait_attempt in range(10):  # Up to 5 seconds
                await asyncio.sleep(0.5)
                count = await options.count()
                if count > 0:
                    logger.info(f"{tab_name} options loaded: {count} items")
                    break
        
        logger.debug(f"Looking for '{value}' in {tab_name} ({count} options)")
        
        for i in range(count):
            opt = options.nth(i)
            text = (await opt.inner_text()).strip()
            
            # Exact match first
            if text.lower() == value.lower():
                await opt.click()
                logger.info(f"Selected {tab_name}: {text} (exact match)")
                await asyncio.sleep(0.5)
                return True
            
            # Partial match (value contained in option)
            if value.lower() in text.lower():
                await opt.click()
                logger.info(f"Selected {tab_name}: {text} (partial match for '{value}')")
                await asyncio.sleep(0.5)
                return True
        
        logger.warning(f"Could not find '{value}' in {tab_name} options")
        return False

    async def call_gemini(self, messages: List[Dict], screenshot_b64: str = None) -> Dict:
        """Call Gemini API with function calling and optional vision."""
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not set")
        
        # Convert messages to Gemini format
        contents = []
        system_instruction = None
        
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            
            if role == "system":
                system_instruction = {"parts": [{"text": content}]}
            elif role == "user":
                parts = [{"text": content}]
                # Add screenshot to the last user message
                if screenshot_b64 and msg == messages[-1]:
                    parts.append({
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": screenshot_b64
                        }
                    })
                contents.append({"role": "user", "parts": parts})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})
        
        payload = {
            "contents": contents,
            "tools": GEMINI_TOOLS,
            "tool_config": {"function_calling_config": {"mode": "ANY"}},  # Force function calling
            "generation_config": {"temperature": 0.0}  # More deterministic
        }
        
        if system_instruction:
            payload["system_instruction"] = system_instruction
        
        url = f"{self.gemini_url}/{self.gemini_model}:generateContent?key={self.gemini_api_key}"
        
        # Retry logic for rate limits (429)
        max_retries = 3
        base_delay = 2.0
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(max_retries):
                response = await client.post(url, json=payload)
                
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # Exponential backoff: 2, 4, 8 seconds
                        logger.warning(f"Gemini rate limited (429), retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        response.raise_for_status()  # Raise on final attempt
                
                response.raise_for_status()
                result = response.json()
                break
        
        # Extract function call from Gemini response
        candidates = result.get("candidates", [])
        if not candidates:
            return {"message": {"content": "No response from Gemini"}}
        
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        
        for part in parts:
            if "functionCall" in part:
                func_call = part["functionCall"]
                # Convert to Ollama-like format for compatibility
                return {
                    "message": {
                        "tool_calls": [{
                            "function": {
                                "name": func_call["name"],
                                "arguments": func_call.get("args", {})
                            }
                        }]
                    }
                }
            elif "text" in part:
                return {"message": {"content": part["text"]}}
        
        return {"message": {"content": "No function call or text in response"}}
    
    async def call_ollama(self, messages: List[Dict]) -> Dict:
        """Call local Ollama with native tool calling."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self.ollama_url,
                json={
                    "model": self.ollama_model,
                    "messages": messages,
                    "tools": NAVIGATION_TOOLS,
                    "stream": False,
                    "options": {"temperature": 0.1}
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def call_server(self, goal: str, state: Dict, step: int) -> Dict:
        """Call server's /navigate endpoint for navigation decision.
        
        Sends request_id so server can lookup the original user for secure billing.
        
        Returns dict with same structure as local Ollama response:
        {"message": {"tool_calls": [{"function": {"name": ..., "arguments": ...}}]}}
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self.server_url,
                json={
                    "request_id": self.request_id,
                    "shop_id": self.shop_id,
                    "goal": goal,
                    "state": state,
                    "step": step
                }
            )
            response.raise_for_status()
            result = response.json()
            
            # Log token usage if returned
            if result.get("tokens_used"):
                tokens = result["tokens_used"]
                logger.info(f"Server navigation step {step}: {tokens.get('total_tokens', 0)} tokens billed")
            
            # Convert server response to Ollama-like format
            if result.get("action"):
                return {
                    "message": {
                        "tool_calls": [{
                            "function": {
                                "name": result["action"]["tool"],
                                "arguments": result["action"]["args"]
                            }
                        }]
                    }
                }
            else:
                # No action (error or done)
                return {"message": {"content": result.get("error", "No action returned")}}
    
    async def get_state(self) -> Dict[str, Any]:
        """Get current page state from vehicle selector."""
        state = await self.page.evaluate("""
            () => {
                const result = {current_tab: null, values: [], options: [], debug: {}};
                
                // Debug: check if selector container exists
                const container = document.querySelector('#VehicleSelectorContainer');
                result.debug.has_container = !!container;
                result.debug.container_visible = container ? container.offsetParent !== null : false;
                
                // Current tab - ShopKeyPro uses multiple ways to indicate active tab
                const tabSelector = document.querySelector('#qualifierTypeSelector');
                result.debug.has_tab_selector = !!tabSelector;
                
                // Method 1: Look for 'selected' class
                let selected = document.querySelector('#qualifierTypeSelector li.selected');
                
                // Method 2: Look for 'active' class
                if (!selected) {
                    selected = document.querySelector('#qualifierTypeSelector li.active');
                }
                
                // Method 3: Look for 'current' or 'on' class
                if (!selected) {
                    const tabs = document.querySelectorAll('#qualifierTypeSelector li');
                    for (const tab of tabs) {
                        if (tab.classList.contains('current') || 
                            tab.classList.contains('on') ||
                            tab.getAttribute('aria-selected') === 'true') {
                            selected = tab;
                            break;
                        }
                    }
                }
                
                // Method 4: Look for which tab is NOT disabled and has matching content visible
                // The active tab typically has its values showing in #qualifierValueSelector
                if (!selected) {
                    const tabs = document.querySelectorAll('#qualifierTypeSelector li');
                    const tabNames = ['year', 'make', 'model', 'engine', 'submodel', 'options', 'odometer'];
                    
                    // Find the last non-disabled tab that comes before a disabled one
                    // This is usually the active tab in the ShopKeyPro UI
                    let lastEnabled = null;
                    for (const tab of tabs) {
                        if (!tab.classList.contains('disabled')) {
                            lastEnabled = tab;
                        }
                    }
                    if (lastEnabled) {
                        selected = lastEnabled;
                        result.debug.selected_method = 'last_enabled';
                    }
                }
                
                // Method 5: Check computed styles for background color difference
                if (!selected) {
                    const tabs = document.querySelectorAll('#qualifierTypeSelector li');
                    for (const tab of tabs) {
                        const style = window.getComputedStyle(tab);
                        // Active tabs often have different background
                        if (style.backgroundColor !== 'rgba(0, 0, 0, 0)' && 
                            style.backgroundColor !== 'transparent' &&
                            !tab.classList.contains('disabled')) {
                            selected = tab;
                            result.debug.selected_method = 'computed_style';
                            break;
                        }
                    }
                }
                
                if (selected) {
                    result.current_tab = selected.textContent.trim();
                    result.debug.selected_classes = selected.className;
                } else {
                    // Fallback: report all tab info for debugging
                    const tabs = document.querySelectorAll('#qualifierTypeSelector li');
                    result.debug.tab_count = tabs.length;
                    result.debug.tab_classes = Array.from(tabs).map(li => li.className);
                    result.debug.tab_texts = Array.from(tabs).map(li => li.textContent.trim());
                }
                
                // Value list (year/make/model/engine/submodel)
                const valueSelector = document.querySelector('#qualifierValueSelector');
                result.debug.has_value_selector = !!valueSelector;
                
                const items = document.querySelectorAll('#qualifierValueSelector li.qualifier');
                result.debug.item_count = items.length;
                result.values = Array.from(items).map(li => li.textContent.trim());
                // Also track selected state for flat values (Options tab)
                result.values_with_selected = Array.from(items).map(li => ({
                    text: li.textContent.trim(),
                    selected: li.classList.contains('selected')
                }));
                
                // Options panel
                const optionsDiv = document.querySelector('#qualifierValueSelector div.options');
                if (optionsDiv) {
                    for (const g of optionsDiv.querySelectorAll('div.optionGroup')) {
                        const name = g.querySelector('h1')?.textContent?.trim() || '';
                        const vals = Array.from(g.querySelectorAll('li.qualifier')).map(li => ({
                            text: li.textContent.trim(),
                            selected: li.classList.contains('selected')
                        }));
                        const selected_val = g.querySelector('h2')?.textContent?.trim() || '';
                        result.options.push({name, values: vals, selected: selected_val});
                    }
                }
                
                return result;
            }
        """)
        
        # Log debug info
        debug = state.pop("debug", {})
        logger.info(f"State: tab={state.get('current_tab')}, values={state.get('values', [])[:5]}, debug={debug}")
        
        return state
    
    def format_state_message(self, state: Dict, goal: str) -> str:
        """Format current state as a user message for the model.
        
        Keep it minimal - Gemini is smart enough to figure out what to do.
        """
        tab = state.get("current_tab") or "None"
        values = state.get("values", [])[:15]  # Limit for context
        
        msg = f"Goal: {goal}\nCurrent tab: {tab}\nAvailable values: {values}"
        
        if state.get("options"):
            for opt in state["options"]:
                vals = opt.get("values", [])
                if not vals:
                    continue
                selected = next((v["text"] for v in vals if v.get("selected")), None)
                if selected:
                    msg += f"\n{opt['name']}: {selected} (selected)"
                else:
                    msg += f"\n{opt['name']}: {[v['text'] for v in vals]}"
        
        return msg
    
    async def execute_tool_call(self, tool_name: str, args: Dict, state: Dict) -> Dict:
        """Execute a tool call on the page."""
        try:
            if tool_name == "done":
                return {"success": True, "done": True}
                
            if tool_name == "request_info":
                return {
                    "success": False,
                    "info_request": ClarificationRequest(
                        option_name=args.get("option_name", "Unknown"),
                        available_values=args.get("available_values", []),
                        message=args.get("message", "Please provide info")
                    )
                }
                
            if tool_name == "confirm_vehicle":
                log_file = "/tmp/navigator_debug.log"
                with open(log_file, "a") as f:
                    f.write(f"\nExecuting confirm_vehicle - clicking SelectComplete button...\n")
                try:
                    await self.page.click("input[data-action='SelectComplete']", timeout=15000)
                    await asyncio.sleep(1)
                    with open(log_file, "a") as f:
                        f.write(f"confirm_vehicle SUCCESS\n")
                    return {"success": True}
                except Exception as e:
                    with open(log_file, "a") as f:
                        f.write(f"confirm_vehicle FAILED: {e}\n")
                    return {"success": False, "error": str(e)}
            
            # Map tool names to their parameter keys
            value_selectors = {
                "select_year": ("year", None),
                "select_make": ("make", None),
                "select_model": ("model", None),
                "select_engine": ("engine", None),
                "select_submodel": ("submodel", None),
            }
            
            option_selectors = {
                "select_body_style": ("body_style", "Body Style"),
                "select_drive_type": ("drive_type", "Drive Type"),
            }
            
            if tool_name in value_selectors:
                param_key, _ = value_selectors[tool_name]
                value = args.get(param_key, "")
                
                # Find matching value in list
                for v in state.get("values", []):
                    if value.lower() in v.lower() or v.lower() in value.lower():
                        selector = f"#qualifierValueSelector li.qualifier:has-text('{v}')"
                        await self.page.click(selector, timeout=15000)
                        await asyncio.sleep(0.5)
                        try:
                            await self.page.wait_for_selector("#qualifierValueSelector li.qualifier", timeout=15000)
                        except:
                            pass
                        await asyncio.sleep(0.5)
                        return {"success": True}
                
                return {"success": False, "error": f"Value '{value}' not found"}
                
            elif tool_name in option_selectors:
                param_key, option_name = option_selectors[tool_name]
                value = args.get(param_key, "")
                
                # Match case-insensitively from state
                for opt in state.get("options", []):
                    opt_name_lower = opt.get("name", "").lower().replace(":", "").strip()
                    if option_name.lower() in opt_name_lower:
                        # Check if already selected
                        for v in opt.get("values", []):
                            if value.lower() in v["text"].lower():
                                if v.get("selected"):
                                    logger.debug(f"'{v['text']}' already selected, skipping")
                                    return {"success": True, "already_selected": True}
                                # Use the exact text from the DOM
                                selector = f"li.qualifier:has-text('{v['text']}')"
                                await self.page.click(selector, timeout=15000, force=True)
                                await asyncio.sleep(1)
                                return {"success": True}
                        return {"success": False, "error": f"Value '{value}' not in options"}
                
                return {"success": False, "error": f"Option group '{option_name}' not found"}
                
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
            
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"success": False, "error": str(e)}
    
    async def ensure_selector_open(self):
        """Ensure vehicle selector is open and reset to Year tab."""
        import asyncio
        
        # First check if selector is already fully visible (Year/Make/Model tabs showing)
        try:
            selector_visible = await self.page.locator("#qualifierTypeSelector").is_visible(timeout=2000)
            if selector_visible:
                # Already open, just click Year tab to reset
                await self.page.click("#qualifierTypeSelector li:has-text('Year')", timeout=5000)
                await asyncio.sleep(0.5)
                return
        except:
            pass
        
        # Selector not visible - need to open it (3-level hierarchy)
        for attempt in range(3):
            try:
                # Step 1: Click the "Select Vehicle" button to open dropdown
                vehicle_btn = self.page.locator("#vehicleSelectorButton")
                if await vehicle_btn.count() > 0:
                    await vehicle_btn.click(timeout=5000)
                    logger.info("Clicked vehicle selector button")
                    await asyncio.sleep(0.5)
                    
                    # Step 2: Click "Vehicle Selection" to expand the Year/Make/Model panel
                    # This is inside the dropdown that just opened
                    try:
                        vehicle_selection = self.page.locator("text=Vehicle Selection").first
                        if await vehicle_selection.is_visible(timeout=3000):
                            await vehicle_selection.click(timeout=5000)
                            logger.info("Clicked 'Vehicle Selection' to expand")
                            await asyncio.sleep(0.5)
                    except Exception as e:
                        logger.debug(f"Vehicle Selection click: {e}")
                    
                    # Step 3: Wait for the Year/Make/Model tabs to appear
                    try:
                        await self.page.wait_for_selector("#qualifierTypeSelector", timeout=10000)
                        await asyncio.sleep(0.5)
                        
                        # Click Year tab to ensure we start fresh
                        await self.page.click("#qualifierTypeSelector li:has-text('Year')", timeout=5000)
                        await asyncio.sleep(0.5)
                        logger.info("Vehicle selector fully opened")
                        return
                    except Exception as e:
                        logger.warning(f"Waiting for qualifier tabs: {e}")
                        
            except Exception as e:
                logger.warning(f"Attempt {attempt+1} to open selector failed: {e}")
                await asyncio.sleep(1)
        
        logger.error("Could not open vehicle selector after 3 attempts")
    
    async def navigate(self, goal: str) -> NavigationResult:
        """
        Navigate the vehicle selector to select the specified vehicle.
        
        HYBRID APPROACH:
        1. DETERMINISTIC selection for Year→Make→Model→Engine→Submodel (known values from goal)
        2. GEMINI only for Options tab (body_style, drive_type) when not in goal
        
        This is much more reliable than letting AI make every decision.
        
        Args:
            goal: Natural language description of the vehicle to select.
                  e.g. "2018 Ford F-150 5.0L XLT 2D Pickup 4WD"
        
        Returns:
            NavigationResult with success status and any clarification requests.
        """
        import base64
        
        logger.info(f"Starting HYBRID navigation: {goal}")
        logger.info(f"Backend for Options: {self.backend.value}")
        
        # Store original goal for dynamic matching
        self._original_goal = goal
        
        # Parse goal to extract known values
        self._parsed_goal = self._parse_goal(goal)
        logger.info(f"Parsed goal: {self._parsed_goal}")
        
        # Clear debug log for fresh run
        log_file = "/tmp/navigator_debug.log"
        with open(log_file, "w") as f:
            f.write(f"=== Navigator Debug Log (HYBRID) ===\n")
            f.write(f"Goal: {goal}\n")
            f.write(f"Parsed: {self._parsed_goal}\n")
            f.write(f"Backend for Options: {self.backend.value}\n")
            f.write(f"{'=' * 60}\n\n")
        
        clarifications: List[ClarificationRequest] = []
        
        # Reset step counter for this navigation
        self._step_counter = 0
        
        # Clear screenshot directory
        import shutil
        if os.path.exists(self._screenshot_dir):
            shutil.rmtree(self._screenshot_dir)
        os.makedirs(self._screenshot_dir, exist_ok=True)
        
        # =========================================================================
        # PHASE 1: DETERMINISTIC - Year→Make→Model→Engine→Submodel
        # =========================================================================
        logger.info("PHASE 1: Deterministic vehicle selection")
        
        await self.ensure_selector_open()
        
        # Verify selector is actually open
        for verify_attempt in range(5):
            selector_visible = await self.page.locator("#qualifierTypeSelector").is_visible()
            if selector_visible:
                logger.info("Vehicle selector is open")
                break
            logger.warning(f"Selector not visible after ensure_selector_open (attempt {verify_attempt+1})")
            
            # Log current page state for debugging
            current_url = self.page.url
            logger.warning(f"Current URL: {current_url}")
            
            await asyncio.sleep(1)
            # Try the full open sequence again
            await self.ensure_selector_open()
        
        await self._debug_screenshot("selector_opened", f"Goal: {goal}")
        
        # Year (required)
        if self._parsed_goal.get("year"):
            if not await self._select_value_deterministic(self._parsed_goal["year"], "Year"):
                await self._debug_screenshot("year_failed", f"Could not find year {self._parsed_goal['year']}")
                return NavigationResult(success=False, clarifications=[], 
                                        error=f"Year '{self._parsed_goal['year']}' not found")
            await self._debug_screenshot("year_selected", f"Selected year: {self._parsed_goal['year']}")
        else:
            return NavigationResult(success=False, clarifications=[], error="Year not specified in goal")
        
        # Make (required)
        await asyncio.sleep(0.5)
        if self._parsed_goal.get("make"):
            if not await self._select_value_deterministic(self._parsed_goal["make"], "Make"):
                await self._debug_screenshot("make_failed", f"Could not find make {self._parsed_goal['make']}")
                return NavigationResult(success=False, clarifications=[], 
                                        error=f"Make '{self._parsed_goal['make']}' not found")
            await self._debug_screenshot("make_selected", f"Selected make: {self._parsed_goal['make']}")
        else:
            return NavigationResult(success=False, clarifications=[], error="Make not specified in goal")
        
        # Model (required)
        await asyncio.sleep(0.5)
        if self._parsed_goal.get("model"):
            if not await self._select_value_deterministic(self._parsed_goal["model"], "Model"):
                await self._debug_screenshot("model_failed", f"Could not find model {self._parsed_goal['model']}")
                return NavigationResult(success=False, clarifications=[], 
                                        error=f"Model '{self._parsed_goal['model']}' not found")
            await self._debug_screenshot("model_selected", f"Selected model: {self._parsed_goal['model']}")
        else:
            return NavigationResult(success=False, clarifications=[], error="Model not specified in goal")
        
        # Engine (optional but try if specified, otherwise pick first)
        await asyncio.sleep(0.5)
        await self._debug_screenshot("before_engine", "Checking for engine tab")
        state = await self.get_state()
        logger.info(f"After Model selection - current tab: {state.get('current_tab')}, values count: {len(state.get('values', []))}")
        if state.get("current_tab") == "Engine":
            if self._parsed_goal.get("engine"):
                await self._select_value_deterministic(self._parsed_goal["engine"], "Engine")
                await self._debug_screenshot("engine_selected", f"Selected engine: {self._parsed_goal['engine']}")
            else:
                # Pick first engine
                first = self.page.locator("#qualifierValueSelector li.qualifier").first
                if await first.is_visible(timeout=2000):
                    await first.click()
                    logger.info("Selected first available Engine")
                    await asyncio.sleep(0.5)
                    await self._debug_screenshot("engine_first", "Selected first engine")
        else:
            await self._debug_screenshot("engine_skipped", f"Not on Engine tab, current: {state.get('current_tab')}")
        
        # Submodel - Try to match from available options, or ASK if no match
        await asyncio.sleep(0.5)
        await self._debug_screenshot("before_submodel", "Checking for submodel tab")
        state = await self.get_state()
        current_tab = state.get("current_tab")
        logger.info(f"Checking for Submodel tab - current tab: {current_tab}, values: {state.get('values', [])[:5]}")
        if state.get("current_tab") == "Submodel":
            # Wait for submodel values to load (they may be async)
            submodel_values = state.get("values", [])
            if not submodel_values:
                logger.info("Submodel tab has no values yet, waiting...")
                for _ in range(5):  # Wait up to 2.5 seconds for values
                    await asyncio.sleep(0.5)
                    state = await self.get_state()
                    submodel_values = state.get("values", [])
                    if submodel_values:
                        logger.info(f"Submodel values loaded: {submodel_values[:5]}")
                        break
            
            await self._debug_screenshot("submodel_detected", f"On Submodel tab with values: {state.get('values', [])}")
            submodel_values = state.get("values", [])
            
            # First check if we have a parsed submodel that matches
            matched_submodel = None
            if self._parsed_goal.get("submodel"):
                # Check if it matches any available option
                for val in submodel_values:
                    if self._parsed_goal["submodel"].lower() == val.lower():
                        matched_submodel = val
                        break
                    # Partial match
                    if self._parsed_goal["submodel"].lower() in val.lower():
                        matched_submodel = val
                        break
            
            # If no parsed submodel, try to find a match from the original goal string
            if not matched_submodel and hasattr(self, '_original_goal'):
                goal_upper = self._original_goal.upper()
                for val in submodel_values:
                    # Check if this submodel appears in the goal
                    if val.upper() in goal_upper:
                        matched_submodel = val
                        logger.info(f"Found submodel '{val}' in goal string")
                        break
            
            if matched_submodel:
                await self._select_value_deterministic(matched_submodel, "Submodel")
            elif len(submodel_values) == 1:
                # Only one option, just select it
                first = self.page.locator("#qualifierValueSelector li.qualifier").first
                if await first.is_visible(timeout=2000):
                    await first.click()
                    logger.info(f"Selected only available Submodel: {submodel_values[0]}")
                    await asyncio.sleep(0.5)
            elif len(submodel_values) > 1:
                # Multiple submodels and no match - AUTO-SELECT first option
                first_submodel = submodel_values[0]
                logger.info(f"🔧 Auto-selecting first Submodel: {first_submodel} (from {len(submodel_values)} options)")
                await self._select_value_deterministic(first_submodel, "Submodel")
                if not hasattr(self, '_auto_selected'):
                    self._auto_selected = {}
                self._auto_selected["submodel"] = first_submodel
            else:
                # No submodel values available - this is unusual, log and continue
                logger.warning("No submodel values found - skipping submodel selection")
        else:
            # Tab is NOT "Submodel" - either we're on a different tab or detection failed
            # Log this for debugging and proceed to Phase 2
            await self._debug_screenshot("submodel_not_detected", 
                f"Expected Submodel tab but got: '{current_tab}'. Values visible: {state.get('values', [])[:5]}")
            logger.warning(f"Submodel tab NOT detected. Current tab: '{current_tab}'. Proceeding to Phase 2...")
        
        # =========================================================================
        # PHASE 2: OPTIONS TAB - Use known values or ask Gemini
        # =========================================================================
        await self._debug_screenshot("phase2_start", "Starting Phase 2 - Options handling")
        logger.info("PHASE 2: Options tab handling")
        
        for step in range(1, 15):  # Max 15 steps for options
            await asyncio.sleep(0.5)
            state = await self.get_state()
            tab = state.get("current_tab")
            
            # Take screenshot every 3 steps or on important events
            if step % 3 == 1:
                await self._debug_screenshot(f"phase2_step{step}", f"Tab: {tab}, Values: {state.get('values', [])[:3]}, Options: {len(state.get('options', []))} groups")
            
            # Check if done (no tab = selector closed)
            if tab is None:
                await self._debug_screenshot("selector_closed", "Vehicle selector closed - SUCCESS")
                logger.info("Vehicle selector closed - navigation complete!")
                return NavigationResult(success=True, clarifications=clarifications, 
                                       auto_selected=getattr(self, '_auto_selected', None))
            
            # If still on Submodel tab, we need to handle it
            if tab == "Submodel":
                await self._debug_screenshot(f"phase2_submodel_step{step}", f"Still on Submodel with values: {state.get('values', [])}")
                submodel_values = state.get("values", [])
                if submodel_values:
                    logger.info(f"Still on Submodel tab with {len(submodel_values)} options - requesting clarification")
                    # AUTO-SELECT first submodel instead of asking
                    first_submodel = submodel_values[0]
                    logger.info(f"🔧 Phase 2: Auto-selecting first Submodel: {first_submodel}")
                    await self._select_value_deterministic(first_submodel, "Submodel")
                    if not hasattr(self, '_auto_selected'):
                        self._auto_selected = {}
                    self._auto_selected["submodel"] = first_submodel
                    continue  # Re-check state after selection
                else:
                    logger.warning("On Submodel tab but no values found")
                    continue
            
            # If not on Options tab and not Submodel, might be Engine or other
            if tab != "Options":
                logger.debug(f"Step {step}: Still on {tab} tab")
                # If we're still on Year/Make/Model/Engine after 5 steps, something is wrong
                if step > 5 and tab in ["Year", "Make", "Model", "Engine"]:
                    logger.warning(f"Stuck on {tab} tab after {step} steps - aborting")
                    return NavigationResult(success=False, clarifications=[],
                                            error=f"Navigation stuck on {tab} selection")
                # Could be waiting for more selections, continue
                continue
            
            # On Options tab - check what we need
            options = state.get("options", [])
            values = state.get("values", [])  # Flat list of values (ShopKeyPro may show options this way)
            values_with_selected = state.get("values_with_selected", [])  # Values with selected state
            all_selected = True
            
            # Debug: log all options for visibility
            logger.info(f"Options tab step {step}: {len(options)} option groups, {len(values)} flat values")
            for opt_debug in options:
                logger.info(f"  - {opt_debug.get('name')}: values={[v['text'] for v in opt_debug.get('values', [])]}, selected={opt_debug.get('selected')}")
            if values and not options:
                selected_vals = [v['text'] for v in values_with_selected if v.get('selected')]
                unselected_vals = [v['text'] for v in values_with_selected if not v.get('selected')]
                logger.info(f"  Flat values on Options tab: {len(values)} total, {len(selected_vals)} selected, {len(unselected_vals)} unselected")
                logger.info(f"  Selected: {selected_vals[:5]}")
                logger.info(f"  Unselected: {unselected_vals[:5]}")
            
            # CASE 1: Options shown as flat values (not in optionGroup divs)
            # This happens on ShopKeyPro when Options tab shows simple selections
            if not options and values:
                # Build set of already-selected values to skip
                selected_set = {v['text'] for v in values_with_selected if v.get('selected')}
                unselected_values = [v for v in values if v not in selected_set]
                logger.info(f"Options tab shows flat values: {len(values)} total, {len(selected_set)} selected, trying to match from {len(unselected_values)} unselected")
                
                # If all values from goal are already selected, we're done with this selection
                if not unselected_values:
                    logger.info("All flat values are selected - checking if we can proceed")
                    # Try clicking Use This Vehicle
                    try:
                        use_button = self.page.locator("input[data-action='SelectComplete']")
                        if await use_button.count() > 0 and await use_button.is_enabled():
                            await use_button.click(timeout=5000)
                            logger.info("Clicked Use This Vehicle after all options selected")
                            await asyncio.sleep(1.0)
                            continue
                    except Exception as e:
                        logger.debug(f"Could not click Use This Vehicle yet: {e}")
                        continue
                
                # Try to match UNSELECTED values against goal string
                matched_value = None
                goal_str = getattr(self, '_original_goal', '').upper()
                
                for val in unselected_values:  # Only check unselected values!
                    val_upper = val.upper()
                    # Check exact match
                    if val_upper in goal_str:
                        matched_value = val
                        logger.info(f"Found flat option '{val}' in goal string")
                        break
                    # Check partial match for body styles
                    if any(x in val_upper for x in ['2D', '4D', 'PICKUP', 'SEDAN', 'COUPE', 'HATCH', 'WAGON', 'CAB']):
                        val_parts = val_upper.split()
                        for i in range(len(val_parts)):
                            partial = ' '.join(val_parts[:i+1])
                            if partial in goal_str:
                                matched_value = val
                                logger.info(f"Partial match: '{partial}' found in goal")
                                break
                        if matched_value:
                            break
                    # Check for drive type
                    for drive in ['4WD', '2WD', 'AWD', 'RWD', 'FWD']:
                        if drive in val_upper and drive in goal_str:
                            matched_value = val
                            logger.info(f"Drive type match: '{drive}' in both")
                            break
                    if matched_value:
                        break
                
                if matched_value:
                    selector = f"li.qualifier:has-text('{matched_value}')"
                    try:
                        await self.page.click(selector, timeout=15000, force=True)
                        logger.info(f"Selected flat option: {matched_value}")
                        await asyncio.sleep(0.5)
                        continue  # Re-check state after selection
                    except Exception as e:
                        logger.warning(f"Failed to click flat option '{matched_value}': {e}")
                else:
                    # No match found in unselected values
                    # Check if we've already selected something from the goal
                    # If yes, we can proceed with "Use This Vehicle"
                    goal_str = getattr(self, '_original_goal', '').upper()
                    already_selected_from_goal = any(
                        v.upper() in goal_str or 
                        any(drive in v.upper() and drive in goal_str for drive in ['4WD', '2WD', 'AWD', 'RWD', 'FWD'])
                        for v in selected_set
                    )
                    
                    if already_selected_from_goal:
                        logger.info(f"Goal-relevant options already selected ({[v for v in selected_set if v.upper() in goal_str][:3]}), attempting to proceed")
                        try:
                            use_button = self.page.locator("input[data-action='SelectComplete']")
                            if await use_button.count() > 0 and await use_button.is_enabled():
                                await use_button.click(timeout=5000)
                                logger.info("Clicked Use This Vehicle - goal options are selected")
                                await asyncio.sleep(1.0)
                                continue
                        except Exception as e:
                            logger.debug(f"Could not click Use This Vehicle: {e}")
                    
                    # Still no match and nothing relevant selected - AUTO-SELECT first option
                    first_option = values[0] if values else None
                    if first_option:
                        logger.info(f"🔧 Auto-selecting first flat option: {first_option}")
                        try:
                            selector = f"li.qualifier:has-text('{first_option}')"
                            await self.page.click(selector, timeout=15000, force=True)
                            if not hasattr(self, '_auto_selected'):
                                self._auto_selected = {}
                            self._auto_selected["options"] = first_option
                            await asyncio.sleep(0.5)
                            continue  # Re-check state
                        except Exception as e:
                            logger.warning(f"Failed to auto-select '{first_option}': {e}")
            
            # CASE 2: Options shown in structured optionGroup divs
            
            for opt in options:
                opt_name = opt.get("name", "").lower().replace(":", "").strip()
                opt_values = [v["text"] for v in opt.get("values", [])]
                selected = opt.get("selected", "")
                
                # Skip if already has a value selected
                if selected and selected not in ["", "None"]:
                    logger.debug(f"Option '{opt_name}' already selected: {selected}")
                    continue
                
                all_selected = False
                
                # Body Style - try to match from goal string first
                if "body" in opt_name or "style" in opt_name:
                    matched_body = None
                    
                    # First check parsed goal
                    if self._parsed_goal.get("body_style"):
                        for v in opt.get("values", []):
                            if self._parsed_goal["body_style"].lower() in v["text"].lower():
                                matched_body = v["text"]
                                break
                    
                    # If no match, try dynamic matching against original goal
                    if not matched_body and hasattr(self, '_original_goal'):
                        goal_upper = self._original_goal.upper()
                        for v in opt.get("values", []):
                            if v["text"].upper() in goal_upper:
                                matched_body = v["text"]
                                logger.info(f"Found body style '{v['text']}' in goal string")
                                break
                            # Also try partial match (e.g., "2D PICKUP" matches "2D Pickup Crew Cab")
                            v_parts = v["text"].upper().split()
                            if len(v_parts) >= 2 and f"{v_parts[0]} {v_parts[1]}" in goal_upper:
                                matched_body = v["text"]
                                logger.info(f"Found body style '{v['text']}' (partial) in goal string")
                                break
                    
                    if matched_body:
                        selector = f"li.qualifier:has-text('{matched_body}')"
                        await self.page.click(selector, timeout=15000, force=True)
                        logger.info(f"Selected Body Style: {matched_body}")
                        await asyncio.sleep(0.5)
                        break  # Break to re-read state on next iteration
                    else:
                        # Auto-select first option instead of asking for clarification
                        first_option = opt.get("values", [{}])[0].get("text") if opt.get("values") else None
                        if first_option:
                            selector = f"li.qualifier:has-text('{first_option}')"
                            await self.page.click(selector, timeout=15000, force=True)
                            logger.info(f"Auto-selected Body Style (first option): {first_option}")
                            if not hasattr(self, '_auto_selected'):
                                self._auto_selected = {}
                            self._auto_selected["body_style"] = first_option
                            await asyncio.sleep(0.5)
                            break  # Break to re-read state on next iteration
                        else:
                            logger.warning("No body style options available")
                            return NavigationResult(success=False, clarifications=clarifications,
                                                    error="No body style options available")
                
                # Drive Type - try to match from goal string first
                elif "drive" in opt_name:
                    matched_drive = None
                    
                    # First check parsed goal
                    if self._parsed_goal.get("drive_type"):
                        for v in opt.get("values", []):
                            if self._parsed_goal["drive_type"].lower() in v["text"].lower():
                                matched_drive = v["text"]
                                break
                    
                    # If no match, try dynamic matching against original goal
                    if not matched_drive and hasattr(self, '_original_goal'):
                        goal_upper = self._original_goal.upper()
                        for v in opt.get("values", []):
                            v_text = v["text"].upper()
                            # Match "4WD", "2WD", "AWD", etc.
                            if v_text in goal_upper:
                                matched_drive = v["text"]
                                logger.info(f"Found drive type '{v['text']}' in goal string")
                                break
                            # Also try matching just the abbreviation part
                            if "4WD" in v_text and "4WD" in goal_upper:
                                matched_drive = v["text"]
                                break
                            if "2WD" in v_text and "2WD" in goal_upper:
                                matched_drive = v["text"]
                                break
                            if "AWD" in v_text and "AWD" in goal_upper:
                                matched_drive = v["text"]
                                break
                            if "RWD" in v_text and "RWD" in goal_upper:
                                matched_drive = v["text"]
                                break
                            if "FWD" in v_text and "FWD" in goal_upper:
                                matched_drive = v["text"]
                                break
                    
                    if matched_drive:
                        selector = f"li.qualifier:has-text('{matched_drive}')"
                        await self.page.click(selector, timeout=15000, force=True)
                        logger.info(f"Selected Drive Type: {matched_drive}")
                        await asyncio.sleep(0.5)
                        break  # Break to re-read state on next iteration
                    else:
                        # Auto-select first option instead of asking for clarification
                        first_option = opt.get("values", [{}])[0].get("text") if opt.get("values") else None
                        if first_option:
                            selector = f"li.qualifier:has-text('{first_option}')"
                            await self.page.click(selector, timeout=15000, force=True)
                            logger.info(f"Auto-selected Drive Type (first option): {first_option}")
                            if not hasattr(self, '_auto_selected'):
                                self._auto_selected = {}
                            self._auto_selected["drive_type"] = first_option
                            await asyncio.sleep(0.5)
                            break  # Break to re-read state on next iteration
                        else:
                            logger.warning("No drive type options available")
                            return NavigationResult(success=False, clarifications=clarifications,
                                                    error="No drive type options available")
                
                # Other option types (Transmission, etc.) - auto-select first option
                else:
                    all_selected = False
                    first_option = opt.get("values", [{}])[0].get("text") if opt.get("values") else None
                    if first_option:
                        selector = f"li.qualifier:has-text('{first_option}')"
                        await self.page.click(selector, timeout=15000, force=True)
                        logger.info(f"Auto-selected {opt.get('name', 'option')} (first option): {first_option}")
                        if not hasattr(self, '_auto_selected'):
                            self._auto_selected = {}
                        # Store with cleaned key name
                        key = opt.get('name', 'option').lower().replace(':', '').replace(' ', '_').strip()
                        self._auto_selected[key] = first_option
                        await asyncio.sleep(0.5)
                        break  # Break to re-read state on next iteration
                    else:
                        logger.warning(f"No options available for {opt.get('name', 'unknown')}")
            
            # After processing all options, check if we can proceed
            # all_selected is True if no option group needed action (all had selections)
            # Also try clicking Use This Vehicle if button is enabled
            if all_selected:
                try:
                    # Click "Use This Vehicle" button
                    utv = self.page.locator('input[value="Use This Vehicle"]')
                    if await utv.count() > 0:
                        is_enabled = await utv.is_enabled()
                        logger.info(f"Use This Vehicle button found, enabled: {is_enabled}")
                        if is_enabled:
                            await utv.click()
                            logger.info("Clicked 'Use This Vehicle' - all options selected")
                            await asyncio.sleep(1)
                            # Check if selector closed
                            state = await self.get_state()
                            if not state.get("selector_visible", True):
                                return NavigationResult(success=True, clarifications=clarifications,
                                                       auto_selected=getattr(self, '_auto_selected', None))
                            # Still open, continue loop
                except Exception as e:
                    logger.debug(f"Could not click Use This Vehicle: {e}")
        
        logger.warning("Max options steps reached")
        return NavigationResult(success=False, clarifications=clarifications,
                                error="Could not complete Options selection")


async def check_ollama_model(model: str = "qwen3:8b", url: str = "http://localhost:11434") -> bool:
    """Check if the required Ollama model is available."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{url}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            return any(model in m for m in models)
    except Exception as e:
        logger.error(f"Failed to check Ollama: {e}")
        return False


# Backward compatibility alias
OllamaNavigator = Navigator
