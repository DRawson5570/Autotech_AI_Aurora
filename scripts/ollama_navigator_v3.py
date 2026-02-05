#!/usr/bin/env python3
"""
Ollama Navigator v3 - Native Tool Calling

Uses Ollama's native tool calling API instead of prompting for JSON.
The model is trained to output structured tool_calls - much more reliable!
"""

import asyncio
import httpx
import json
import sys
sys.path.insert(0, '/home/drawson/autotech_ai')

# Force unbuffered output
import functools
print = functools.partial(print, flush=True)

# Log to file as well
LOG_FILE = "/tmp/ollama_nav_v3.log"
_log_file = open(LOG_FILE, "w")
def log(msg):
    print(msg)
    _log_file.write(msg + "\n")
    _log_file.flush()

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:8b"  # Try qwen3 - better at tool calling

# Define tools that the model can call
TOOLS = [
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
- Only request_info for options with values that aren't specified in the goal

Example: Goal "2018 Ford F-150 5.0L XLT 4D Pickup Crew Cab" (no drive type mentioned)
- Body Style has ['2D Pickup', '4D Pickup Crew Cab'] → select '4D Pickup Crew Cab' (it's in the goal!)
- Drive Type appears with ['4WD', 'RWD'] → use request_info (not in goal)"""


async def call_ollama_tools(messages: list) -> dict:
    """Call Ollama with tool definitions and get tool_calls back."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "messages": messages,
                "tools": TOOLS,
                "stream": False,
                "options": {"temperature": 0.1}
            }
        )
        response.raise_for_status()
        return response.json()


async def get_state(page) -> dict:
    """Get current page state."""
    return await page.evaluate("""
        () => {
            const result = {current_tab: null, values: [], options: []};
            
            // Current tab
            const selected = document.querySelector('#qualifierTypeSelector li.selected');
            if (selected) result.current_tab = selected.textContent.trim();
            
            // Value list (year/make/model/engine/submodel)
            const items = document.querySelectorAll('#qualifierValueSelector li.qualifier');
            result.values = Array.from(items).map(li => li.textContent.trim());
            
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


async def execute_tool_call(page, tool_name: str, args: dict, state: dict):
    """Execute a tool call on the page."""
    try:
        if tool_name == "done":
            return {"success": True, "done": True}
            
        if tool_name == "request_info":
            return {
                "success": False,
                "info_request": {
                    "option": args.get("option_name"),
                    "available": args.get("available_values", []),
                    "message": args.get("message", "Please provide info")
                }
            }
            
        if tool_name == "confirm_vehicle":
            await page.click("input[data-action='SelectComplete']", timeout=5000)
            await asyncio.sleep(1)
            return {"success": True}
        
        # Map tool names to their parameter keys and selector logic
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
                    await page.click(selector, timeout=5000)
                    await asyncio.sleep(0.5)
                    try:
                        await page.wait_for_selector("#qualifierValueSelector li.qualifier", timeout=5000)
                    except:
                        pass
                    await asyncio.sleep(0.5)
                    return {"success": True}
            
            return {"success": False, "error": f"Value '{value}' not found"}
            
        elif tool_name in option_selectors:
            param_key, option_name = option_selectors[tool_name]
            value = args.get(param_key, "")
            
            # The DOM has uppercase headers like "BODY STYLE:" so match case-insensitively
            # Try to find the option group by checking state
            for opt in state.get("options", []):
                opt_name_lower = opt.get("name", "").lower().replace(":", "").strip()
                if option_name.lower() in opt_name_lower:
                    # Check if already selected
                    for v in opt.get("values", []):
                        if value.lower() in v["text"].lower():
                            if v.get("selected"):
                                log(f"  ⏭️ '{v['text']}' already selected, skipping")
                                return {"success": True, "already_selected": True}
                            # Use the exact text from the DOM
                            selector = f"li.qualifier:has-text('{v['text']}')"
                            log(f"  → Clicking: {selector}")
                            await page.click(selector, timeout=5000, force=True)
                            await asyncio.sleep(1)
                            return {"success": True}
                    return {"success": False, "error": f"Value '{value}' not in {[v['text'] for v in opt['values']]}"}
            
            return {"success": False, "error": f"Option group '{option_name}' not found"}
            
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def format_state_message(state: dict, goal: str) -> str:
    """Format current state as a user message for the model."""
    tab = state.get("current_tab") or "None"
    values = state.get("values", [])[:15]  # Limit for context
    
    msg = f"""GOAL: {goal}

CURRENT STATE:
- Tab: {tab}
- Available values: {values}"""
    
    if state.get("options"):
        # Separate completed vs pending options
        completed = []
        pending = []
        for opt in state["options"]:
            vals = opt.get("values", [])
            if not vals:
                continue  # Skip empty option groups
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


async def navigate(page, goal: str, max_steps: int = 25, on_info_needed=None):
    """Navigate using Ollama's native tool calling."""
    log(f"\n{'='*60}")
    log(f"GOAL: {goal}")
    log("="*60)
    
    messages = [{"role": "system", "content": SYSTEM_MESSAGE}]
    info_requests = []
    
    for step in range(1, max_steps + 1):
        state = await get_state(page)
        tab = state.get("current_tab")
        
        log(f"\n--- Step {step} ---")
        log(f"Tab: {tab or 'None'} | Values: {len(state.get('values', []))}")
        
        if tab is None:
            log("  Vehicle selector closed - done!")
            return {"success": True, "info_requests": info_requests}
        
        # Show options if on Options tab (for our debug)
        if tab == "Options" and state.get("options"):
            for opt in state["options"]:
                opt_vals = [f"{v['text']}{'*' if v['selected'] else ''}" for v in opt.get("values", [])]
                log(f"  {opt['name']}: {opt_vals}")
        
        # Build message for this step
        user_msg = format_state_message(state, goal)
        step_messages = messages + [{"role": "user", "content": user_msg}]
        
        # Debug: show what the model sees (first time on Options)
        if tab == "Options" and step == 6:
            log(f"\n  === MESSAGE TO MODEL ===\n{user_msg}\n  =========================")
        
        log("  Thinking...")
        response = await call_ollama_tools(step_messages)
        
        message = response.get("message", {})
        tool_calls = message.get("tool_calls", [])
        
        if not tool_calls:
            # Model didn't call a tool - might have responded with text
            content = message.get("content", "")
            log(f"  No tool call. Response: {content[:200]}")
            continue
        
        # Execute the first tool call
        tool_call = tool_calls[0]
        func = tool_call.get("function", {})
        tool_name = func.get("name")
        args = func.get("arguments", {})
        
        log(f"  Tool: {tool_name}({args})")
        
        result = await execute_tool_call(page, tool_name, args, state)
        
        if result.get("done"):
            log("  ✅ Navigation complete!")
            return {"success": True, "info_requests": info_requests}
        
        if result.get("info_request"):
            info = result["info_request"]
            info_requests.append(info)
            log(f"  📋 Requesting: {info['option']} from {info['available']}")
            
            if on_info_needed:
                answer = on_info_needed(info["option"], info["available"], info["message"])
                if answer:
                    # Update goal with the answer and continue
                    goal = f"{goal}, {info['option']}: {answer}"
                    log(f"  → Got answer: {answer}")
                else:
                    log("  ⚠️ No answer provided - aborting")
                    return {"success": False, "info_requests": info_requests}
            else:
                log("  ⚠️ No callback to handle info request")
                return {"success": False, "info_requests": info_requests}
                
        elif result.get("success"):
            log(f"  ✅ Success")
        else:
            log(f"  ⚠️ Failed: {result.get('error', 'unknown')}")
    
    log("\n⚠️ Max steps reached")
    return {"success": False, "info_requests": info_requests}


async def main():
    print("=" * 60)
    print("  Ollama Navigator v3 - Native Tool Calling")
    print("  Using Ollama's built-in tool support")
    print("=" * 60)
    
    # Check Ollama
    print("\n[1/3] Checking Ollama...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            if not any(MODEL in m for m in models):
                print(f"  ❌ {MODEL} not found. Available: {models}")
                return
            print(f"  ✅ {MODEL} ready")
    except Exception as e:
        print(f"  ❌ Ollama not running: {e}")
        return
    
    # Launch Chrome and login
    print("\n[2/3] Launching Chrome...")
    from addons.mitchell_agent.api import MitchellAPI
    
    api = MitchellAPI(headless=False)
    if not await api.connect():
        print("  ❌ Failed to connect")
        return
    
    page = api._page
    print(f"  ✅ Logged in")
    
    # Reset vehicle selector - click to ensure it's open and on Year tab
    print("  Resetting vehicle selector...")
    try:
        # Click the Year tab to reset selection
        await page.click("#qualifierTypeSelector li:has-text('Year')", timeout=3000)
        await asyncio.sleep(0.5)
    except:
        # Maybe selector isn't open, try clicking the button
        try:
            await page.click("#vehicleSelectorButton", timeout=3000)
            await page.wait_for_selector("#qualifierTypeSelector", timeout=3000)
        except:
            pass
    print("  ✅ Ready")
    
    # Demo callback for handling info requests
    def handle_info_request(option: str, available: list, message: str) -> str | None:
        """Simulates Autotech AI responding to info requests."""
        print(f"\n📋 AUTOTECH AI RECEIVED INFO REQUEST:")
        print(f"   Option: {option}")
        print(f"   Available: {available}")
        print(f"   Message: {message}")
        
        # For demo, ask user directly
        print(f"\n   (Demo: Enter your choice or press Enter to abort)")
        try:
            choice = input(f"   Select {option} [{'/'.join(available[:5])}]: ").strip()
            if choice:
                return choice
        except EOFError:
            pass
        return None
    
    # Navigate - Goal intentionally missing drive type to test request_info!
    print("\n[3/3] Starting navigation...")
    goal = "Select 2018 Ford F-150 with 5.0L engine, XLT submodel, 4D Pickup Crew Cab"
    # ^ Missing drive type - navigator should request it via tool call!
    
    try:
        result = await navigate(page, goal, on_info_needed=handle_info_request)
        
        await page.screenshot(path="/tmp/ollama_nav_v3_result.png")
        print(f"\nScreenshot: /tmp/ollama_nav_v3_result.png")
        
        if result["success"]:
            print("\n🎉 Success!")
        else:
            print("\n⚠️ Navigation incomplete")
            if result["info_requests"]:
                print("Info requests made:")
                for req in result["info_requests"]:
                    print(f"  - {req['option']}: {req['available']}")
        
        input("\nPress Enter to close...")
        
    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        await api.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
