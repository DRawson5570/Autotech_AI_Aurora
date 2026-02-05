#!/usr/bin/env python3
"""
Test if Gemini can figure out navigation state on its own.
Simulates the state after round 2 where it got confused.
"""

import asyncio
import os
import httpx

# Load API key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    # Try loading from .env
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            if line.startswith("GEMINI_API_KEY="):
                GEMINI_API_KEY = line.split("=", 1)[1].strip()

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

# The tools we provide
TOOLS = [
    {
        "function_declarations": [
            {"name": "select_year", "description": "Select a year", "parameters": {"type": "object", "properties": {"year": {"type": "string"}}, "required": ["year"]}},
            {"name": "select_make", "description": "Select a make", "parameters": {"type": "object", "properties": {"make": {"type": "string"}}, "required": ["make"]}},
            {"name": "select_model", "description": "Select a model", "parameters": {"type": "object", "properties": {"model": {"type": "string"}}, "required": ["model"]}},
            {"name": "select_engine", "description": "Select an engine", "parameters": {"type": "object", "properties": {"engine": {"type": "string"}}, "required": ["engine"]}},
            {"name": "select_submodel", "description": "Select a submodel/trim", "parameters": {"type": "object", "properties": {"submodel": {"type": "string"}}, "required": ["submodel"]}},
            {"name": "select_body_style", "description": "Select body style", "parameters": {"type": "object", "properties": {"body_style": {"type": "string"}}, "required": ["body_style"]}},
            {"name": "request_info", "description": "Ask user for missing info", "parameters": {"type": "object", "properties": {"option_name": {"type": "string"}, "available_values": {"type": "array", "items": {"type": "string"}}, "message": {"type": "string"}}, "required": ["option_name", "available_values", "message"]}},
            {"name": "done", "description": "Navigation complete", "parameters": {"type": "object", "properties": {}, "required": []}}
        ]
    }
]

async def test_gemini(system_prompt: str, user_prompt: str, test_name: str):
    """Send a prompt to Gemini and see what it returns."""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")
    print(f"\nSystem prompt:\n{system_prompt[:200]}...")
    print(f"\nUser prompt:\n{user_prompt}")
    
    payload = {
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "tools": TOOLS,
        "tool_config": {"function_calling_config": {"mode": "ANY"}},
        "generation_config": {"temperature": 0.0}
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(GEMINI_URL, json=payload)
        result = resp.json()
    
    # Extract the response
    candidates = result.get("candidates", [])
    if not candidates:
        print(f"\n❌ No response from Gemini")
        return
    
    parts = candidates[0].get("content", {}).get("parts", [])
    for part in parts:
        if "functionCall" in part:
            func = part["functionCall"]
            print(f"\n✅ Gemini called: {func['name']}({func.get('args', {})})")
            return func
        elif "text" in part:
            print(f"\n⚠️ Gemini returned text: {part['text'][:200]}")
            return None
    
    print(f"\n❌ No function call in response")
    return None


async def main():
    # Minimal system prompt - let's see how smart it really is
    minimal_system = "You are navigating a vehicle selector UI. Use the appropriate select_* function based on the current tab. If a required value isn't in the goal, use request_info."
    
    # Test 1: The exact scenario that failed - on Submodel tab, should select XL
    test1_prompt = """Goal: 2018 Ford F-150 XL 2D Pickup 5.0L

Current state:
- Tab: Submodel
- Available values: ['King Ranch', 'Lariat', 'Platinum', 'SSV', 'XL', 'XLT']

What's your next action?"""

    result1 = await test_gemini(minimal_system, test1_prompt, "Submodel tab with XL in goal")
    
    # Test 2: On Submodel tab but NO submodel in goal - should request_info
    test2_prompt = """Goal: 2018 Ford F-150 5.0L

Current state:
- Tab: Submodel  
- Available values: ['King Ranch', 'Lariat', 'Platinum', 'SSV', 'XL', 'XLT']

What's your next action?"""

    result2 = await test_gemini(minimal_system, test2_prompt, "Submodel tab with NO submodel in goal")
    
    # Test 3: On Options tab with body style in goal
    test3_prompt = """Goal: 2018 Ford F-150 XL 2D Pickup 5.0L

Current state:
- Tab: Options
- Available values: ['2D Pickup', '4D Pickup Crew Cab', '4D Pickup Extra Cab']
- Option group: Body Style

What's your next action?"""

    result3 = await test_gemini(minimal_system, test3_prompt, "Options tab with 2D Pickup in goal")
    
    # Test 4: Year tab - basic sanity check
    test4_prompt = """Goal: 2018 Ford F-150 5.0L

Current state:
- Tab: Year
- Available values: ['2025', '2024', '2023', '2022', '2021', '2020', '2019', '2018', '2017']

What's your next action?"""

    result4 = await test_gemini(minimal_system, test4_prompt, "Year tab - basic")
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Test 1 (Submodel with XL): {'PASS' if result1 and result1['name'] == 'select_submodel' else 'FAIL'}")
    print(f"Test 2 (Submodel no goal): {'PASS' if result2 and result2['name'] == 'request_info' else 'FAIL'}")
    print(f"Test 3 (Options 2D Pickup): {'PASS' if result3 and result3['name'] == 'select_body_style' else 'FAIL'}")
    print(f"Test 4 (Year basic): {'PASS' if result4 and result4['name'] == 'select_year' else 'FAIL'}")


if __name__ == "__main__":
    asyncio.run(main())
