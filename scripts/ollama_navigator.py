#!/usr/bin/env python3
"""
Ollama Navigator v2
===================
The LLM decides WHAT to do, Python handles HOW.

The model outputs simple decisions like:
  {"action": "select_year", "value": "2018"}
  {"action": "select_make", "value": "Ford"}
  {"action": "done"}

Python translates these into actual Playwright clicks.
"""

import asyncio
import json
import sys
from pathlib import Path
import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.1:8b"  # Good reasoning, should parse goal properly

SYSTEM_PROMPT = """You are navigating ShopKeyPro to select a vehicle.

RESPOND WITH ONLY JSON - NO OTHER TEXT:
{"action": "ACTION_NAME", "value": "VALUE"}

VALID ACTIONS:
- select_year, select_make, select_model, select_engine, select_submodel
- select_body_style, select_drive_type
- request_info - ONLY when the GOAL doesn't specify a required option
- confirm_vehicle (when all required options are selected)
- done (after confirm_vehicle, or if Tab is None)

DECISION LOGIC:
1. Read the GOAL carefully - extract year, make, model, engine, submodel, body style, drive type
2. If the GOAL specifies a value, USE IT (e.g., "XLT submodel" means select XLT)
3. If the GOAL does NOT specify a required option, use request_info
4. Items marked with * are already selected - skip them

EXAMPLES:
- Goal says "2018 Ford F-150 5.0L XLT" → select_submodel with value "XLT"
- Goal says "2018 Ford F-150 5.0L" (no submodel) → request_info for Submodel
- Goal says "4D Pickup Crew Cab" but no drive type → request_info for Drive Type

DO NOT request_info if the value is in the GOAL.
"""


async def call_ollama(prompt: str) -> dict:
    """Call Ollama and parse JSON response."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 150}
            }
        )
        response.raise_for_status()
        text = response.json()["response"].strip()
        
        # Extract JSON
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        return {"action": "wait"}


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


async def execute_action(page, action: dict, state: dict) -> tuple[bool, dict | None]:
    """Execute the model's decision. Returns (success, info_request or None)."""
    act = action.get("action", "")
    value = action.get("value", "")
    
    print(f"  Executing: {act} {value}")
    
    try:
        if act == "done":
            return True, None
            
        elif act == "wait":
            await asyncio.sleep(1)
            return True, None
            
        elif act == "request_info":
            # Navigator needs info from Autotech AI
            info_request = {
                "type": "info_needed",
                "option": action.get("option", "unknown"),
                "available_values": action.get("available", []),
                "message": action.get("message", "Please provide missing information")
            }
            print(f"  📋 Requesting info: {info_request}")
            return False, info_request
            
        elif act == "confirm_vehicle":
            await page.click("input[data-action='SelectComplete']", timeout=5000)
            await asyncio.sleep(1)
            return True, None
            
        elif act in ["select_year", "select_make", "select_model", "select_engine", "select_submodel"]:
            # Find matching value in list
            for v in state.get("values", []):
                if value.lower() in v.lower() or v.lower() in value.lower():
                    selector = f"#qualifierValueSelector li.qualifier:has-text('{v}')"
                    await page.click(selector, timeout=5000)
                    # Wait for next tab to load values
                    await asyncio.sleep(0.5)
                    try:
                        await page.wait_for_selector("#qualifierValueSelector li.qualifier", timeout=5000)
                    except:
                        pass  # May not have more values (e.g., after submodel)
                    await asyncio.sleep(0.5)
                    return True, None
            # Wait a moment - values might still be loading
            if len(state.get("values", [])) == 0:
                await asyncio.sleep(1)
                return False, None  # Retry will get fresh state
            print(f"  ⚠️ Value '{value}' not found in {state.get('values', [])[:10]}")
            return False, None
            
        elif act in ["select_body_style", "select_drive_type", "select_fuel_type"]:
            # Map action to option name
            option_map = {
                "select_body_style": "Body Style",
                "select_drive_type": "Drive Type",
                "select_fuel_type": "Fuel Type",
            }
            option_name = option_map.get(act, "")
            selector = f"div.optionGroup:has(h1:has-text('{option_name}')) li.qualifier:has-text('{value}')"
            await page.click(selector, timeout=5000)
            await asyncio.sleep(1)
            return True, None
            
        elif act == "select_option":
            option_name = action.get("option_name", "")
            selector = f"div.optionGroup:has(h1:has-text('{option_name}')) li.qualifier:has-text('{value}')"
            await page.click(selector, timeout=5000)
            await asyncio.sleep(1)
            return True, None
            
        else:
            print(f"  ⚠️ Unknown action: {act}")
            return False, None
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False, None


async def navigate(page, goal: str, max_steps: int = 25, on_info_needed=None):
    """Navigate toward goal using Ollama.
    
    Args:
        page: Playwright page
        goal: Natural language goal (e.g., "Select 2018 Ford F-150 5.0L XLT 4WD")
        max_steps: Max navigation steps
        on_info_needed: Callback when navigator needs info. 
                       Called with (option, available_values, message).
                       Should return the selected value or None to abort.
    
    Returns:
        dict with 'success', 'info_requests' (list of any info that was needed)
    """
    print(f"\n{'='*60}")
    print(f"GOAL: {goal}")
    print(f"{'='*60}")
    
    info_requests = []
    
    for step in range(max_steps):
        print(f"\n--- Step {step + 1} ---")
        
        state = await get_state(page)
        print(f"Tab: {state.get('current_tab')} | Values: {len(state.get('values', []))}")
        
        if state.get("values"):
            print(f"  Available: {state['values'][:8]}{'...' if len(state['values']) > 8 else ''}")
        
        if state.get("options"):
            for opt in state["options"]:
                vals = [v["text"] + ("*" if v["selected"] else "") for v in opt["values"][:5]]
                print(f"  {opt['name']}: {vals}")
        
        # Build prompt with clearer context about what's done vs remaining
        completed = []
        remaining = []
        
        # Figure out progress based on current tab
        tab = state.get('current_tab', '')
        
        # If tab is None/empty, vehicle selection is complete
        if not tab:
            print("  Vehicle selector closed - selection complete!")
            return {"success": True, "info_requests": info_requests}
        
        if tab == 'Year':
            remaining = ['year', 'make', 'model', 'engine', 'submodel', 'options']
        elif tab == 'Make':
            completed = ['year']
            remaining = ['make', 'model', 'engine', 'submodel', 'options']
        elif tab == 'Model':
            completed = ['year', 'make']
            remaining = ['model', 'engine', 'submodel', 'options']
        elif tab == 'Engine':
            completed = ['year', 'make', 'model']
            remaining = ['engine', 'submodel', 'options']
        elif tab == 'Submodel':
            completed = ['year', 'make', 'model', 'engine']
            remaining = ['submodel', 'options']
        elif tab == 'Options':
            completed = ['year', 'make', 'model', 'engine', 'submodel']
            # Check which options still need selection
            for opt in state.get('options', []):
                if opt.get('values') and not opt.get('selected'):
                    # Has values but none selected
                    has_selected = any(v.get('selected') for v in opt['values'])
                    if not has_selected:
                        remaining.append(opt['name'])
        
        # Check if goal mentions drive type (for request_info logic)
        goal_lower = goal.lower()
        has_drive_type = any(dt in goal_lower for dt in ['4wd', 'rwd', 'awd', 'fwd', '2wd', 'drive type'])
        has_body_style = any(bs in goal_lower for bs in ['pickup', 'cab', 'sedan', 'coupe', 'suv', 'body style'])
        
        prompt = f"""{SYSTEM_PROMPT}

GOAL: {goal}
GOAL ANALYSIS:
- Mentions drive type: {has_drive_type}
- Mentions body style: {has_body_style}
(If an option is needed but NOT mentioned in goal, you MUST use request_info)

PROGRESS:
- Completed: {completed if completed else 'nothing yet'}
- Still need: {remaining if remaining else 'all done - use confirm_vehicle or done'}

CURRENT STATE:
- Tab: {state.get('current_tab')}
- Available values: {state.get('values', [])}
- Options: {json.dumps(state.get('options'), indent=2) if state.get('options') else 'N/A'}

Next action (JSON only):"""

        print("  Thinking...")
        decision = await call_ollama(prompt)
        print(f"  Decision: {decision}")
        
        if decision.get("action") == "done":
            print("\n✅ Goal achieved!")
            return {"success": True, "info_requests": info_requests}
        
        success, info_request = await execute_action(page, decision, state)
        
        if info_request:
            # Navigator needs info
            info_requests.append(info_request)
            
            if on_info_needed:
                # Ask the callback for the value
                value = on_info_needed(
                    info_request["option"],
                    info_request["available_values"],
                    info_request["message"]
                )
                if value:
                    # Update goal with the new info and continue
                    goal = f"{goal}, {info_request['option']}: {value}"
                    print(f"  Got info: {info_request['option']} = {value}")
                else:
                    print("\n⚠️ Info not provided, stopping")
                    return {"success": False, "info_requests": info_requests}
            else:
                # No callback, just report the need
                print(f"\n📋 Need info: {info_request['message']}")
                print(f"   Options: {info_request['available_values']}")
                return {"success": False, "info_requests": info_requests}
        
        if not success and not info_request:
            print("  Retrying...")
    
    print("\n⚠️ Max steps reached")
    return {"success": False, "info_requests": info_requests}


async def main():
    print("=" * 60)
    print("  Ollama Navigator v2 (gemma3:4b)")
    print("  LLM decides, Python executes")
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
    print(f"  ✅ Logged in (vehicle selector should be open)")
    
    # Demo callback for handling info requests
    def handle_info_request(option: str, available: list, message: str) -> str | None:
        """Simulates Autotech AI responding to info requests.
        
        In production, this would:
        1. Send the request back to the Autotech AI server
        2. Autotech AI might ask the user or make a default choice
        3. Return the selected value
        """
        print(f"\n📋 AUTOTECH AI RECEIVED INFO REQUEST:")
        print(f"   Option: {option}")
        print(f"   Available: {available}")
        print(f"   Message: {message}")
        
        # For demo, ask user directly
        print(f"\n   (Demo: Enter your choice or press Enter to abort)")
        try:
            choice = input(f"   Select {option} [{'/'.join(available)}]: ").strip()
            if choice:
                return choice
        except EOFError:
            pass
        return None
    
    # Navigate - NOTE: Goal intentionally missing drive type to test request_info!
    print("\n[3/3] Starting navigation...")
    goal = "Select 2018 Ford F-150 with 5.0L engine, XLT submodel, 4D Pickup Crew Cab"
    # ^ Missing drive type - navigator should request it!
    
    try:
        result = await navigate(page, goal, on_info_needed=handle_info_request)
        
        await page.screenshot(path="/tmp/ollama_nav_result.png")
        print(f"\nScreenshot: /tmp/ollama_nav_result.png")
        
        if result["success"]:
            print("\n🎉 Success!")
        else:
            print("\n⚠️ Navigation incomplete")
            if result["info_requests"]:
                print("Info requests made:")
                for req in result["info_requests"]:
                    print(f"  - {req['option']}: {req['available_values']}")
        
        input("\nPress Enter to close...")
        
    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        await api.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
