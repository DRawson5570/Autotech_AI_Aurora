"""
LLM model interaction for Autonomous Navigator.

Handles calls to Gemini and Ollama APIs, including response parsing.
"""

import asyncio
import json
import re
from dataclasses import dataclass
from typing import List, Optional

import aiohttp

from .logging_config import get_logger, log_trace
from .an_config import (
    DEFAULT_MODEL,
    GEMINI_API_BASE_URL,
    get_gemini_api_key,
    is_gemini_model,
)
from .timing import TIMEOUT_HTTP

logger = get_logger(__name__)


@dataclass
class TokenUsage:
    """Track token usage for billing."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    def add(self, other: 'TokenUsage') -> 'TokenUsage':
        """Add another TokenUsage to this one (cumulative)."""
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens
        )
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens
        }


# Tools the AI can call (JSON schema for Ollama)
AUTONOMOUS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "Click on an element to navigate deeper into that section",
            "parameters": {
                "type": "object",
                "properties": {
                    "element_id": {
                        "type": "integer",
                        "description": "The ID of the element to click"
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
            "name": "collect",
            "description": "Collect data from the current page and CONTINUE navigating. Use this when you need to gather data from multiple sections/dropdowns before finishing. Data is stored and accumulated.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "string",
                        "description": "The data you found on this page"
                    },
                    "label": {
                        "type": "string",
                        "description": "A label for this data, e.g. 'Connector X1' or 'Power Distribution diagrams'"
                    }
                },
                "required": ["data"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": "Signal that you have finished collecting all data and are ready to return results. Call this when you have gathered everything the user asked for.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Brief summary of what you found"
                    }
                },
                "required": ["summary"]
            }
        }
    },
    # DISABLED: extract tool - use collect() + done() instead
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "extract",
    #         "description": "Extract data and finish immediately. Use for simple single-item queries. For multi-part queries, use collect() multiple times then done().",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {
    #                 "data": {
    #                     "type": "string",
    #                     "description": "The data you found that answers the query"
    #                 }
    #             },
    #             "required": ["data"]
    #         }
    #     }
    # },
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Use the 1Search feature to search for content directly",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The search query"
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "go_back",
            "description": "Close the modal entirely and return to main page. Use this when DONE with a modal.",
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
    {
        "type": "function",
        "function": {
            "name": "prior_page",
            "description": "Go back to prior page (browser back). Use this to return to a list after viewing a detail page, especially when searching through multiple sections.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why you're going back to prior page"
                    }
                },
                "required": ["reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "where_am_i",
            "description": "Ask where you currently are in the navigation. Returns your depth and whether you're in a modal.",
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
            "name": "how_did_i_get_here",
            "description": "Ask for the path you took to get to this point. Shows your click history.",
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
            "name": "find_in_page",
            "description": "Search for specific text in the current page/modal. Returns the text with context if found.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to search for (case-insensitive)"
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "click_text",
            "description": "Click on an element by its text content. Use when you see text in PAGE TEXT that you want to click. Pass just the TEXT, not the [id] prefix - for example if you see '[22] Wiring Diagrams', pass text='Wiring Diagrams'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to click (without the [id] prefix)"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why you're clicking this"
                    }
                },
                "required": ["text", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "capture_diagram",
            "description": "Capture a diagram/image from the current page. Use when you see a wiring diagram, schematic, or image that answers the query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "What the diagram shows"
                    }
                },
                "required": ["description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "expand_all",
            "description": "Expand all collapsed/hidden content on the current page. Use when you see a list of categories that need to be expanded to reveal their contents (like DTC Index, TSBs, etc).",
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
            "name": "ask_user",
            "description": "Ask the user a question when you need clarification or there are multiple options to choose from. Use this when there are multiple cards/results and you need the user to pick one.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to ask the user"
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of choices for the user"
                    }
                },
                "required": ["question"]
            }
        }
    }
]


def _convert_to_gemini_tools(tools: list) -> list:
    """
    Convert AUTONOMOUS_TOOLS (Ollama format) to Gemini function_declarations format.
    
    Ollama format:
        {"type": "function", "function": {"name": "...", "parameters": {...}}}
    
    Gemini format:
        [{"function_declarations": [{"name": "...", "parameters": {...}}]}]
    """
    declarations = []
    for tool in tools:
        func = tool.get("function", {})
        declarations.append({
            "name": func.get("name", ""),
            "description": func.get("description", ""),
            "parameters": func.get("parameters", {})
        })
    return [{"function_declarations": declarations}]


# Gemini function calling tools (converted from AUTONOMOUS_TOOLS)
GEMINI_FUNCTION_TOOLS = _convert_to_gemini_tools(AUTONOMOUS_TOOLS)


@dataclass
class ToolResult:
    """Result of executing a tool"""
    tool_name: str
    success: bool
    result: str
    # For ask_user tool - signals navigator to pause and return question
    needs_user_input: bool = False
    question: str = ""
    options: list = None
    
    def __post_init__(self):
        if self.options is None:
            self.options = []


class ModelClient:
    """
    Client for calling LLM models (Gemini or Ollama).
    """
    
    def __init__(self, model: str = None):
        """
        Initialize model client.
        
        Args:
            model: Model name. If None, uses DEFAULT_MODEL.
        """
        self.model = model or DEFAULT_MODEL
        self.use_gemini = is_gemini_model(self.model)
        
        # Validate Gemini API key if using Gemini
        if self.use_gemini:
            key = get_gemini_api_key()
            if not key:
                raise ValueError(
                    f"Gemini model {self.model} requires API key. "
                    f"Set GEMINI_API_KEY env var or create ~/gary_gemini_api_key"
                )
            self.gemini_api_key = key
        else:
            self.gemini_api_key = None
        
        logger.info(f"ModelClient initialized with model: {self.model} (gemini={self.use_gemini})")
    
    async def call(self, system_prompt: str, messages: list) -> dict:
        """Call the configured model (Gemini or Ollama)."""
        if self.use_gemini:
            return await self._call_gemini(system_prompt, messages)
        else:
            return await self._call_ollama(system_prompt, messages)
    
    async def _call_gemini(self, system_prompt: str, messages: list) -> dict:
        """
        Call Gemini API with native function calling.
        
        Uses Gemini's function_declarations for reliable tool calling.
        Falls back to text parsing if function call not returned.
        """
        # Build user message from conversation
        user_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                user_parts.append(content)
            else:
                user_parts.append(f"[{role.upper()}]: {content}")
        
        user_message = "\n\n".join(user_parts)
        
        # Gemini API payload with native function calling
        payload = {
            "contents": [{"role": "user", "parts": [{"text": user_message}]}],
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "tools": GEMINI_FUNCTION_TOOLS,
            "tool_config": {"function_calling_config": {"mode": "ANY"}},  # Force function call
            "generationConfig": {
                "temperature": 0.1,  # Low temp for consistent tool calls
                "maxOutputTokens": 1024,
            }
        }
        
        url = f"{GEMINI_API_BASE_URL}/models/{self.model}:generateContent?key={self.gemini_api_key}"
        
        # Retry logic for rate limiting (503 errors)
        max_retries = 3
        base_delay = 2.0  # seconds
        
        for attempt in range(max_retries + 1):
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=TIMEOUT_HTTP)) as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 503:
                        # Rate limited / overloaded - retry with exponential backoff
                        if attempt < max_retries:
                            delay = base_delay * (2 ** attempt)  # 2s, 4s, 8s
                            logger.warning(f"[GEMINI] 503 overloaded, retry {attempt + 1}/{max_retries} in {delay}s...")
                            await asyncio.sleep(delay)
                            continue
                        else:
                            error_text = await response.text()
                            logger.error(f"[GEMINI] 503 after {max_retries} retries: {error_text[:200]}")
                            return {"message": {"content": "API overloaded after retries", "tool_calls": []}}
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Gemini API error {response.status}: {error_text[:500]}")
                        return {"message": {"content": f"API Error: {response.status}", "tool_calls": []}}
                    
                    result = await response.json()
                    break  # Success, exit retry loop
        
        # Extract token usage from Gemini response
        usage = None
        try:
            usage_meta = result.get("usageMetadata", {})
            if usage_meta:
                usage = TokenUsage(
                    prompt_tokens=usage_meta.get("promptTokenCount", 0),
                    completion_tokens=usage_meta.get("candidatesTokenCount", 0),
                    total_tokens=usage_meta.get("totalTokenCount", 0)
                )
                logger.info(f"[GEMINI TOKENS] prompt={usage.prompt_tokens}, completion={usage.completion_tokens}, total={usage.total_tokens}")
            else:
                logger.warning(f"[GEMINI] No usageMetadata in response")
        except Exception as e:
            logger.warning(f"[GEMINI] Failed to parse token usage: {e}")
        
        # Parse response - check for native function calls first
        tool_calls = []
        text_content = ""
        
        try:
            parts = result["candidates"][0]["content"]["parts"]
            for part in parts:
                # Check for native function call
                if "functionCall" in part:
                    fc = part["functionCall"]
                    tool_name = fc.get("name", "")
                    args = fc.get("args", {})
                    logger.info(f"[GEMINI NATIVE] Function call: {tool_name} args={args}")
                    tool_calls.append({
                        "function": {
                            "name": tool_name,
                            "arguments": args
                        }
                    })
                # Also capture any text
                if "text" in part:
                    text_content = part["text"]
        except (KeyError, IndexError) as e:
            logger.error(f"Unexpected Gemini response structure: {e}")
            logger.error(f"Response: {result}")
            return {"message": {"content": "Failed to parse response", "tool_calls": []}, "usage": usage}
        
        # Log what we got
        if tool_calls:
            logger.info(f"[GEMINI RAW] {tool_calls[0]['function']['name']}({tool_calls[0]['function']['arguments']})")
        elif text_content:
            logger.info(f"[GEMINI RAW] {text_content[:200]}")
            # Fallback: try to parse tool calls from text (for older models)
            tool_calls = self._parse_tool_calls_from_text(text_content)
            if tool_calls:
                logger.info(f"[GEMINI] Parsed from text: {tool_calls[0]['function']['name']} args={tool_calls[0]['function']['arguments']}")
            else:
                logger.warning(f"[GEMINI] No tool calls in response")
        
        return {
            "message": {
                "content": text_content,
                "tool_calls": tool_calls
            },
            "usage": usage
        }
    
    def _parse_tool_calls_from_text(self, text: str) -> list:
        """
        Parse tool calls from Gemini's text response.
        
        Gemini tends to respond with natural language followed by a tool call.
        Common formats:
        - click(element_id=22, reason="Navigate to Wiring Diagrams")
        - click(22, "Navigate to Wiring Diagrams")
        - I'll click element [22] for Wiring Diagrams
        - Action: click(22)
        
        IMPORTANT: Gemini may return MULTIPLE tool calls. We parse ALL of them
        and return them all. The caller should execute them in order.
        """
        tool_calls = []
        tool_names = ['click', 'click_text', 'extract', 'collect', 'done', 'capture_diagram', 'go_back', 'prior_page', 'search', 'expand_all', 'ask_user', 'where_am_i', 'how_did_i_get_here', 'end_session']
        
        # Pattern 0: Handle MULTI-LINE extract() calls FIRST
        # Gemini outputs extract("...content...") which may:
        # - Span multiple real lines (newlines in content)
        # - Use literal \n escape sequences instead of real newlines
        # - Be truncated with "..." at the end (no closing paren)
        for tool_name in ['extract']:
            # Case A: Properly closed extract("...")
            multiline_pattern = rf'\b{tool_name}\s*\("(.*?)"\)'
            matches = re.findall(multiline_pattern, text, re.DOTALL | re.IGNORECASE)
            if matches:
                data = matches[0].strip()
                # Convert literal \n to actual newlines
                data = data.replace('\\n', '\n').replace('\\t', '\t')
                if data:
                    tool_calls.append({
                        "function": {
                            "name": tool_name,
                            "arguments": {"data": data}
                        }
                    })
                    return tool_calls
            
            # Case B: Truncated extract("... (no closing quote/paren)
            # Match extract(" followed by content, even if truncated
            truncated_pattern = rf'\b{tool_name}\s*\("([^"]+?)(?:\.\.\.|$)'
            matches = re.findall(truncated_pattern, text, re.DOTALL | re.IGNORECASE)
            if matches:
                data = matches[0].strip()
                # Convert literal \n to actual newlines
                data = data.replace('\\n', '\n').replace('\\t', '\t')
                if data and len(data) > 20:  # Must have meaningful content
                    tool_calls.append({
                        "function": {
                            "name": tool_name,
                            "arguments": {"data": data}
                        }
                    })
                    return tool_calls
        
        # Pattern 0.5: Handle collect() with triple-quotes BEFORE paren-matching
        # Gemini likes to use: collect("label", """multi-line data""")
        # The triple-quote confuses the paren-matching string tracker
        # Case A: Properly closed triple-quote: collect("label", """data""")
        collect_triple_match = re.search(
            r'\bcollect\s*\(\s*["\']([^"\']+)["\']\s*,\s*"""(.*?)"""\s*\)',
            text, re.DOTALL | re.IGNORECASE
        )
        remaining_text = text  # Text to continue parsing after triple-quote collect
        if collect_triple_match:
            label = collect_triple_match.group(1).strip()
            data = collect_triple_match.group(2).strip()
            data = data.replace('\\n', '\n').replace('\\t', '\t')
            tool_calls.append({
                "function": {
                    "name": "collect",
                    "arguments": {"label": label, "data": data}
                }
            })
            # Don't return - continue parsing remaining text for other tools
            remaining_text = text[collect_triple_match.end():]
        
        # Case B: Truncated triple-quote: collect("label", """data... (no closing)
        elif not tool_calls:  # Only try truncated if we didn't find closed version
            collect_truncated_match = re.search(
                r'\bcollect\s*\(\s*["\']([^"\']+)["\']\s*,\s*"""(.+)',
                text, re.DOTALL | re.IGNORECASE
            )
            if collect_truncated_match:
                label = collect_truncated_match.group(1).strip()
                data = collect_truncated_match.group(2).strip()
                # Remove trailing incomplete markers
                data = re.sub(r'\.{2,}$', '', data).strip()
                data = data.replace('\\n', '\n').replace('\\t', '\t')
                if len(data) > 20:  # Must have meaningful content
                    tool_calls.append({
                        "function": {
                            "name": "collect",
                            "arguments": {"label": label, "data": data}
                        }
                    })
                    # For truncated, we can't reliably parse remaining text
                    return tool_calls
        
        # Pattern 1: Find ALL tool calls in the text using paren-matching
        # This handles multiple tools on same line like:
        #   collect("data", "value") done("summary") end_session("reason")
        # And tools with nested parens like:
        #   capture_diagram("Fig 1 (1 of 3)")
        # 
        # Use remaining_text if we already parsed a triple-quote collect
        parse_text = remaining_text
        
        for tool_name in tool_names:
            # Skip 'collect' if we already parsed it from triple-quotes
            if tool_name == 'collect' and tool_calls:
                continue
            # Find all occurrences of this tool name
            pattern = rf'\b{re.escape(tool_name)}\s*\('
            for match in re.finditer(pattern, parse_text, re.IGNORECASE):
                start = match.start()
                paren_start = match.end() - 1  # Position of opening paren
                
                # Find matching closing paren using depth counting
                depth = 1
                i = paren_start + 1
                in_string = False
                string_char = None
                
                while i < len(parse_text) and depth > 0:
                    char = parse_text[i]
                    
                    # Track string state (skip parens inside strings)
                    if char in ('"', "'") and (i == 0 or parse_text[i-1] != '\\'):
                        if not in_string:
                            in_string = True
                            string_char = char
                        elif char == string_char:
                            in_string = False
                            string_char = None
                    elif not in_string:
                        if char == '(':
                            depth += 1
                        elif char == ')':
                            depth -= 1
                    i += 1
                
                if depth == 0:
                    # Found matching paren at i-1
                    args_str = parse_text[paren_start + 1:i - 1]
                    args = self._parse_function_args(args_str, tool_name)
                    if args is not None:
                        tool_calls.append({
                            "function": {
                                "name": tool_name,
                                "arguments": args
                            }
                        })
        
        # If we found tool calls, return them (ALL of them)
        if tool_calls:
            return tool_calls
        
        # Pattern 2: JSON object with tool/function name
        json_pattern = r'\{[^{}]*"(?:tool|name|function|action)"[^{}]*\}'
        json_matches = re.findall(json_pattern, text, re.IGNORECASE)
        for match in json_matches:
            try:
                obj = json.loads(match)
                tool_name = obj.get("tool") or obj.get("name") or obj.get("function") or obj.get("action")
                if tool_name and tool_name.lower() in tool_names:
                    args = {k: v for k, v in obj.items() if k not in ("tool", "name", "function", "action")}
                    tool_calls.append({
                        "function": {
                            "name": tool_name.lower(),
                            "arguments": args
                        }
                    })
                    return tool_calls
            except json.JSONDecodeError:
                continue
        
        # Pattern 3: "click element [22]" or "click on [22]" or "click [22]"
        click_bracket_pattern = r'\bclick(?:ing|ed)?\s+(?:on\s+)?(?:element\s+)?\[(\d+)\]'
        click_matches = re.findall(click_bracket_pattern, text, re.IGNORECASE)
        if click_matches:
            element_id = int(click_matches[0])
            tool_calls.append({
                "function": {
                    "name": "click",
                    "arguments": {"element_id": element_id, "reason": "parsed from natural language"}
                }
            })
            return tool_calls
        
        # Pattern 4: "element 22" or "element_id 22" mentioned with a tool name context
        if re.search(r'\bclick', text, re.IGNORECASE):
            elem_pattern = r'element(?:_id)?[:\s]+(\d+)'
            elem_matches = re.findall(elem_pattern, text, re.IGNORECASE)
            if elem_matches:
                element_id = int(elem_matches[0])
                tool_calls.append({
                    "function": {
                        "name": "click",
                        "arguments": {"element_id": element_id, "reason": "parsed from element mention"}
                    }
                })
                return tool_calls
        
        return tool_calls
    
    def _parse_function_args(self, args_str: str, tool_name: str = None) -> dict:
        """Parse function arguments from string like 'element_id=5, reason="..."'"""
        args = {}
        
        if not args_str.strip():
            return args
        
        # Handle single number (common for click)
        if re.match(r'^\s*\d+\s*$', args_str):
            if tool_name == 'click':
                return {"element_id": int(args_str.strip()), "reason": ""}
            return {"value": int(args_str.strip())}
        
        # Handle number followed by comma and string: click(22, "reason")
        positional_match = re.match(r'^\s*(\d+)\s*,\s*["\']([^"\']*)["\']', args_str)
        if positional_match and tool_name == 'click':
            return {"element_id": int(positional_match.group(1)), "reason": positional_match.group(2)}
        
        # Handle two quoted strings: click_text("text", "reason")
        two_string_match = re.match(r'^\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']*)["\']', args_str)
        if two_string_match and tool_name == 'click_text':
            return {"text": two_string_match.group(1), "reason": two_string_match.group(2)}
        
        # Handle collect("label", "data") - two quoted strings, data may contain newlines
        # Also handle triple-quotes: collect("label", """data""")
        if tool_name == 'collect':
            # Try triple-quote format first: collect("label", """data""")
            triple_match = re.match(r'^\s*["\'](.+?)["\']\s*,\s*"""(.*?)"""', args_str, re.DOTALL)
            if triple_match:
                label = triple_match.group(1).strip()
                data = triple_match.group(2).strip()
                data = data.replace('\\n', '\n').replace('\\t', '\t')
                return {"label": label, "data": data}
            
            # Regular quotes: collect("label", "data")
            collect_match = re.match(r'^\s*["\'](.+?)["\']\s*,\s*["\'](.*)["\']', args_str, re.DOTALL)
            if collect_match:
                label = collect_match.group(1).strip()
                data = collect_match.group(2).strip()
                data = data.replace('\\n', '\n').replace('\\t', '\t')
                return {"label": label, "data": data}
        
        # Handle ask_user("question", options=["a", "b"]) or ask_user("question", ["a", "b"])
        if tool_name == 'ask_user':
            # Extract question (first quoted string)
            question_match = re.match(r'^\s*["\']([^"\']+)["\']', args_str)
            if question_match:
                question = question_match.group(1)
                # Look for options array - either as options=[] or just []
                options_match = re.search(r'options\s*=\s*\[(.*?)\]', args_str)
                if not options_match:
                    # Try bare array as second argument: ask_user("q", ["a", "b"])
                    options_match = re.search(r'["\'][^"\']+["\']\s*,\s*\[(.*?)\]', args_str)
                if options_match:
                    options_str = options_match.group(1)
                    # Parse array items
                    options = re.findall(r'["\']([^"\']+)["\']', options_str)
                    return {"question": question, "options": options}
                return {"question": question, "options": []}
        
        # Handle done("summary") - single quoted string
        if tool_name == 'done':
            text_val = args_str.strip().strip('"\'')
            return {"summary": text_val}
            return {"summary": text_val}
        
        # Handle quoted string alone (for extract, click_text, search)
        if re.match(r'^\s*["\'].*["\']\s*$', args_str):
            text_val = args_str.strip().strip('"\'')
            if tool_name == 'click_text':
                return {"text": text_val, "reason": ""}
            elif tool_name == 'extract':
                return {"data": text_val}
            elif tool_name == 'collect':
                return {"data": text_val}  # collect with just data, no label
            elif tool_name == 'search':
                return {"text": text_val}
            elif tool_name == 'capture_diagram':
                return {"description": text_val}
            return {"value": text_val}
        
        # Try parsing as JSON
        try:
            if not args_str.strip().startswith("{"):
                # Try wrapping with proper quoting
                json_str = "{" + args_str + "}"
            else:
                json_str = args_str
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        # Parse key=value pairs
        
        # Pattern for key=value (value can be string, number, or quoted)
        kv_pattern = r'(\w+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|(\d+)|(\w+))'
        for match in re.finditer(kv_pattern, args_str):
            key = match.group(1)
            # Get first non-None value group
            value = match.group(2) or match.group(3) or match.group(4) or match.group(5)
            if value and value.isdigit():
                value = int(value)
            args[key] = value
        
        return args
    
    async def _call_ollama(self, system_prompt: str, messages: list) -> dict:
        """Call Ollama API with messages and tool support."""
        import httpx
        
        async with httpx.AsyncClient(timeout=TIMEOUT_HTTP) as client:
            response = await client.post(
                'http://localhost:11434/api/chat',
                json={
                    'model': self.model,
                    'messages': [{"role": "system", "content": system_prompt}] + messages,
                    'tools': AUTONOMOUS_TOOLS,
                    'stream': False,
                }
            )
            data = response.json()
            
            # Extract token usage for billing (Ollama format)
            usage = None
            prompt_tokens = data.get("prompt_eval_count", 0)
            completion_tokens = data.get("eval_count", 0)
            if prompt_tokens or completion_tokens:
                usage = TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens
                )
                logger.debug(f"[OLLAMA] Tokens: prompt={prompt_tokens}, completion={completion_tokens}, total={prompt_tokens + completion_tokens}")
            
            # Add usage to response dict for navigator to accumulate
            data["usage"] = usage
            return data
