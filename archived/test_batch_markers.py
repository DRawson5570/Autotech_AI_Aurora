#!/usr/bin/env python3
"""Test whether Gemini follows batch marker instructions via OpenAI-style API."""

import httpx
from pathlib import Path
import json

# Load API key
api_key = Path.home() / "gary_gemini_api_key"
API_KEY = api_key.read_text().strip()

# Tool definition in OpenAI format (how Open WebUI sends it)
MITCHELL_TOOL = {
    "type": "function",
    "function": {
        "name": "mitchell",
        "description": "Ask any automotive question. AI will intelligently find the answer.",
        "parameters": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "description": "Vehicle year (e.g., 2018)"},
                "make": {"type": "string", "description": "Vehicle make (e.g., Ford)"},
                "model": {"type": "string", "description": "Vehicle model (e.g., F-150)"},
                "question": {"type": "string", "description": "Your automotive question"},
                "engine": {"type": "string", "description": "Engine specification - optional"},
            },
            "required": ["year", "make", "model", "question"]
        }
    }
}

# System prompt with batch instructions (same as in database)
SYSTEM_PROMPT = """You are an automotive technician assistant.

## Mitchell Tool - Session Management

When using the `mitchell` tool for automotive data queries:

**Single Query:** Just call the tool normally.

**Multiple Queries (Batch Requests):**
When the user asks for multiple pieces of information in one request, include the batch position in each query:
Format: `[batch item N of M]` where N is current item and M is total
Examples:
- User: "Get oil capacity, coolant capacity, and torque specs for my 2018 F-150"
  - Query 1: "oil capacity [batch item 1 of 3]"
  - Query 2: "coolant capacity [batch item 2 of 3]"
  - Query 3: "torque specs [batch item 3 of 3]"

This keeps the browser session open between queries. The remote agent will end the session after the final item.
"""

# User request that should trigger multiple tool calls with batch markers
USER_REQUEST = "Get oil capacity, coolant capacity, and torque specs for my 2018 Ford F-150"

def test_batch_markers_openai_api():
    """Test using Gemini's OpenAI-compatible API (how Open WebUI calls it)."""
    print("=" * 60)
    print("Testing via OpenAI-compatible API (how Open WebUI does it)")
    print("=" * 60)
    print(f"\nUser request: {USER_REQUEST}\n")
    print("-" * 60)
    
    # OpenAI-compatible endpoint
    url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    
    payload = {
        "model": "gemini-2.0-flash",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_REQUEST}
        ],
        "tools": [MITCHELL_TOOL],
        "tool_choice": "auto"
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    response = httpx.post(url, json=payload, headers=headers, timeout=60)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return
    
    data = response.json()
    
    # Parse the response
    message = data.get("choices", [{}])[0].get("message", {})
    tool_calls = message.get("tool_calls", [])
    
    if tool_calls:
        for i, tc in enumerate(tool_calls):
            func = tc.get("function", {})
            name = func.get("name")
            args = json.loads(func.get("arguments", "{}"))
            question = args.get("question", "")
            
            print(f"\nTool call {i+1}: {name}")
            print(f"  year: {args.get('year')}")
            print(f"  make: {args.get('make')}")
            print(f"  model: {args.get('model')}")
            print(f"  question: '{question}'")
            
            if "[batch item" in question:
                print(f"  ✅ HAS BATCH MARKER")
            else:
                print(f"  ❌ NO BATCH MARKER")
    else:
        content = message.get("content", "")
        print(f"\nNo tool calls. Text response: {content[:300]}...")
    
    print("\n" + "=" * 60)


def test_batch_markers_native_api():
    """Test using Gemini's native API."""
    import google.generativeai as genai
    
    genai.configure(api_key=API_KEY)
    
    # Native Gemini tool format
    mitchell_tool_native = {
        "function_declarations": [{
            "name": "mitchell",
            "description": "Get automotive data from Mitchell/ShopKeyPro",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "Vehicle year"},
                    "make": {"type": "string", "description": "Vehicle make"},
                    "model": {"type": "string", "description": "Vehicle model"},
                    "question": {"type": "string", "description": "Your automotive question"},
                    "engine": {"type": "string", "description": "Engine spec (optional)"},
                },
                "required": ["year", "make", "model", "question"]
            }
        }]
    }
    
    print("=" * 60)
    print("Testing via Native Gemini API (direct SDK)")
    print("=" * 60)
    print(f"\nUser request: {USER_REQUEST}\n")
    print("-" * 60)
    
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=SYSTEM_PROMPT,
        tools=[mitchell_tool_native]
    )
    
    response = model.generate_content(USER_REQUEST)
    
    # Check for tool calls
    if response.candidates[0].content.parts:
        for i, part in enumerate(response.candidates[0].content.parts):
            if hasattr(part, 'function_call') and part.function_call:
                fc = part.function_call
                args = dict(fc.args)
                question = args.get('question', '')
                
                print(f"\nTool call {i+1}: {fc.name}")
                print(f"  year: {args.get('year')}")
                print(f"  make: {args.get('make')}")
                print(f"  model: {args.get('model')}")
                print(f"  question: '{question}'")
                
                if "[batch item" in question:
                    print(f"  ✅ HAS BATCH MARKER")
                else:
                    print(f"  ❌ NO BATCH MARKER")
            elif hasattr(part, 'text') and part.text:
                print(f"\nText response: {part.text[:200]}...")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_batch_markers_openai_api()
    print("\n\n")
    test_batch_markers_native_api()
