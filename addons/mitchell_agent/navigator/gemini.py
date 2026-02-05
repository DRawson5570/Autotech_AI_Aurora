"""
Gemini Integration
==================
Google Gemini API for data extraction and parsing.
"""

import asyncio
import logging
from typing import Dict, Any, Optional

import httpx

log = logging.getLogger(__name__)


# Gemini tools for function calling
GEMINI_TOOLS = [{
    "function_declarations": [
        {
            "name": "extract_data",
            "description": "Extract structured data from the page text",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "string",
                        "description": "The extracted data in a readable format"
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
            "name": "click",
            "description": "Click on an element if more navigation is needed",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector or text= selector"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why clicking this"
                    }
                },
                "required": ["selector", "reason"]
            }
        },
        {
            "name": "done",
            "description": "Task complete or cannot continue",
            "parameters": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "message": {"type": "string"},
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


async def call_gemini(
    api_key: str,
    model: str,
    system_prompt: str,
    user_content: str,
    timeout: float = 60.0,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Call Gemini API for text analysis with rate limit retry.
    
    Args:
        api_key: Gemini API key
        model: Model name (e.g., "gemini-2.0-flash")
        system_prompt: System instruction
        user_content: User message content
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts on rate limit
        
    Returns:
        API response as dict
    """
    contents = [{"role": "user", "parts": [{"text": user_content}]}]
    
    payload = {
        "contents": contents,
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "tools": GEMINI_TOOLS,
        "tool_config": {"function_calling_config": {"mode": "ANY"}},
        "generation_config": {"temperature": 0.0}
    }
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    base_delay = 2.0
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(max_retries):
            try:
                resp = await client.post(url, json=payload)
                
                if resp.status_code == 429:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # 2, 4, 8 seconds
                        log.warning(f"Gemini rate limited (429), retrying in {delay}s...")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        log.error("Gemini rate limit exceeded after retries")
                
                return resp.json()
                
            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    log.warning(f"Gemini timeout, retry {attempt + 1}/{max_retries}")
                    await asyncio.sleep(1)
                    continue
                raise
            except Exception as e:
                log.error(f"Gemini API error: {e}")
                raise
    
    return {}


def parse_gemini_response(response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parse Gemini response to extract function call.
    
    Args:
        response: Raw API response
        
    Returns:
        Dict with 'name' and 'args' for function call, or None
    """
    candidates = response.get("candidates", [])
    if not candidates:
        return None
    
    parts = candidates[0].get("content", {}).get("parts", [])
    
    for part in parts:
        if "functionCall" in part:
            func = part["functionCall"]
            return {
                "name": func["name"],
                "args": func.get("args", {})
            }
    
    return None


def build_extraction_prompt(
    data_type: str,
    vehicle: Dict[str, Any],
) -> str:
    """
    Build system prompt for data extraction.
    
    Args:
        data_type: Type of data to extract
        vehicle: Vehicle info dict
        
    Returns:
        System prompt string
    """
    year = vehicle.get("year", "")
    make = vehicle.get("make", "")
    model = vehicle.get("model", "")
    engine = vehicle.get("engine", "")
    
    return f"""You are extracting {data_type} from an automotive repair database.
Vehicle: {year} {make} {model} {engine}

TASK: Extract the requested data from the page text provided.

RULES:
1. If the data is visible in the page text, use extract_data to return it
2. Format data as a readable list with all values
3. Include units (quarts, psi, ft-lbs, etc.)
4. If data is not found, use done with success=False

QUICK ACCESS BUTTONS (use # selector if needed):
- #fluidsQuickAccess - Fluid Capacities
- #commonSpecsAccess - Common Specs
- #resetProceduresAccess - Reset Procedures
- #technicalBulletinAccess - Technical Bulletins
- #dtcIndexAccess - DTC Index
- #tireInfoAccess - Tire Information
- #adasAccess - ADAS"""


class GeminiExtractor:
    """
    Gemini-based data extractor.
    
    Wraps Gemini API calls for automotive data extraction.
    
    Usage:
        extractor = GeminiExtractor(api_key, model)
        result = await extractor.extract(data_type, vehicle, page_text)
    """
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        """
        Initialize extractor.
        
        Args:
            api_key: Gemini API key
            model: Model name
        """
        self.api_key = api_key
        self.model = model
    
    async def extract(
        self,
        data_type: str,
        vehicle: Dict[str, Any],
        page_text: str,
        clickables: list = None,
    ) -> Dict[str, Any]:
        """
        Extract data using Gemini.
        
        Args:
            data_type: Type of data to extract
            vehicle: Vehicle info dict
            page_text: Page text content
            clickables: Optional list of clickable elements
            
        Returns:
            Extraction result dict
        """
        system_prompt = build_extraction_prompt(data_type, vehicle)
        
        user_content = f"""Extract {data_type} for this vehicle.

PAGE CONTENT:
{page_text[:15000]}"""
        
        if clickables:
            user_content += f"""

CLICKABLE ELEMENTS:
{clickables[:50]}"""
        
        try:
            response = await call_gemini(
                self.api_key,
                self.model,
                system_prompt,
                user_content
            )
            
            action = parse_gemini_response(response)
            
            if not action:
                return {"success": False, "error": "No response from Gemini"}
            
            if action["name"] == "extract_data":
                return {
                    "success": True,
                    "data": action["args"].get("data", ""),
                    "complete": action["args"].get("complete", False),
                }
            
            elif action["name"] == "done":
                return {
                    "success": action["args"].get("success", False),
                    "data": action["args"].get("data", ""),
                    "message": action["args"].get("message", ""),
                }
            
            elif action["name"] == "click":
                return {
                    "success": False,
                    "action": "click",
                    "selector": action["args"].get("selector", ""),
                    "reason": action["args"].get("reason", ""),
                }
            
            return {"success": False, "error": "Unexpected action"}
            
        except Exception as e:
            log.error(f"Extraction error: {e}")
            return {"success": False, "error": str(e)}
