#!/usr/bin/env python3
"""
Test: Let Gemini figure it out like a human would.

Give it a simple goal and let it observe the page and decide what to do.
No hand-holding - just "here's what you see, here's what you need to do".
Now with VISION - Gemini can see the actual page!

IMPORTANT: This script ALWAYS logs out before closing to avoid session limits.
"""
import asyncio
import base64
import httpx
import os
import signal
import subprocess
import sys
import time
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.0-flash"
MITCHELL_USERNAME = os.environ.get("MITCHELL_USERNAME")
MITCHELL_PASSWORD = os.environ.get("MITCHELL_PASSWORD")

# Use local Ollama with vision model
USE_OLLAMA = False  # Using Gemini for testing
OLLAMA_MODEL = "ministral-3:8b"
OLLAMA_URL = "http://localhost:11434"

# All the actions it can take
TOOLS = [{
    "function_declarations": [
        {
            "name": "click",
            "description": "Click on an element",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector or text to click, e.g. '#loginButton' or 'button:has-text(\"Login\")'"},
                    "reason": {"type": "string", "description": "Why you're clicking this"}
                },
                "required": ["selector", "reason"]
            }
        },
        {
            "name": "type_text",
            "description": "Type text into an input field",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector for the input field"},
                    "text": {"type": "string", "description": "Text to type"},
                    "reason": {"type": "string", "description": "Why you're typing this"}
                },
                "required": ["selector", "text", "reason"]
            }
        },
        {
            "name": "wait",
            "description": "Wait for page to load or element to appear",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {"type": "number", "description": "How long to wait"},
                    "reason": {"type": "string", "description": "What you're waiting for"}
                },
                "required": ["seconds", "reason"]
            }
        },
        {
            "name": "ask_user",
            "description": "Ask the user for missing information",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "What to ask the user"},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Available options if applicable"
                    }
                },
                "required": ["question"]
            }
        },
        {
            "name": "done",
            "description": "Task is complete or cannot continue",
            "parameters": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "description": "Whether the task succeeded"},
                    "message": {"type": "string", "description": "Summary of what happened"}
                },
                "required": ["success", "message"]
            }
        }
    ]
}]

SYSTEM_PROMPT = f"""You are an assistant helping navigate the ShopKeyPro automotive repair website.

Your task: Help the user get automotive repair information.

IMPORTANT: The SCREENSHOT shows the current page. Trust what you SEE in the screenshot over any text descriptions.

You'll need to:
1. FIRST: If you see any cookie consent popups, privacy notices, or "Accept Cookies" dialogs, CLOSE THEM IMMEDIATELY
2. Login if you see a login page (username: {MITCHELL_USERNAME}, password: {MITCHELL_PASSWORD})
3. Select the vehicle using the Vehicle Selector:
   - Click through Year -> Make -> Model -> Engine -> Submodel tabs
   - After selecting submodel, click "Use This Vehicle" button (it's an input button, use selector: input[value="Use This Vehicle"])
   - NOTE: Sometimes the selector AUTO-CLOSES after submodel - if you see the vehicle already displayed at top (e.g. "2020 Toyota Camry L 2.5L"), the vehicle IS selected - proceed to step 4!
4. Navigate to find the requested information:
   - Look in the left sidebar for menu items like "Maintenance", "Specifications", "Fluid Capacities"
   - Click "Maintenance" first, then look for "Fluid Capacities" or the data you need
5. Once you see the data (fluid capacities table, specifications, etc.), extract it and call "done"

CRITICAL RULES:
- If vehicle is already selected (shown at top like "2020 Toyota Camry L 2.5L"), DO NOT re-open the vehicle selector!
- DO NOT click "Vehicle Selection" if a vehicle is already displayed - go directly to the menu items
- For "Use This Vehicle" button, use selector: input[value="Use This Vehicle"] (NOT button:has-text)
- For short options like "L" or "LE", use: li:has-text("L") or li:has-text("LE")

Look at the SCREENSHOT to decide what action to take next.
If you need information that wasn't provided (like which engine or trim level), pick the most common/basic option.

Take it step by step. Don't repeat actions that already succeeded."""


async def call_ollama(messages: list, screenshot_b64: str = None) -> dict:
    """Call local Ollama with vision model."""
    # Ollama format - combine system into first user message
    ollama_messages = []
    system_content = ""
    
    for msg in messages:
        if msg["role"] == "system":
            system_content = msg["content"]
        elif msg["role"] == "user":
            content = msg["content"]
            if system_content:
                content = f"{system_content}\n\n{content}"
                system_content = ""
            
            message = {"role": "user", "content": content}
            # Add image for vision
            if screenshot_b64 and msg == messages[-1]:
                message["images"] = [screenshot_b64]
            ollama_messages.append(message)
        elif msg["role"] == "assistant":
            ollama_messages.append({"role": "assistant", "content": msg["content"]})
    
    payload = {
        "model": OLLAMA_MODEL,
        "messages": ollama_messages,
        "stream": False,
        "options": {"temperature": 0.1}
    }
    
    # Note: qwen2-vl doesn't support native tool calling well
    # So we ask it to respond with JSON format
    ollama_messages[-1]["content"] += """

Respond with ONLY a JSON object in this exact format (no other text):
{"action": "click", "selector": "...", "reason": "..."}
or {"action": "type_text", "selector": "...", "text": "...", "reason": "..."}
or {"action": "wait", "seconds": N, "reason": "..."}
or {"action": "ask_user", "question": "...", "options": [...]}
or {"action": "done", "success": true/false, "message": "..."}"""
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
        result = resp.json()
    
    # Parse the response - Ollama returns content as text
    content = result.get("message", {}).get("content", "")
    
    # Try to extract JSON from the response
    import json
    import re
    
    # Look for JSON in the response
    json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
    if json_match:
        try:
            action_data = json.loads(json_match.group())
            action_name = action_data.pop("action", "unknown")
            return {
                "action": {"name": action_name, "args": action_data},
                "raw": content
            }
        except json.JSONDecodeError:
            pass
    
    return {"action": None, "raw": content}


async def call_gemini(messages: list, screenshot_b64: str = None) -> dict:
    """Call Gemini and return the response. Can include a screenshot!"""
    # Convert to Gemini format
    contents = []
    system_instruction = None
    
    for msg in messages:
        if msg["role"] == "system":
            system_instruction = {"parts": [{"text": msg["content"]}]}
        elif msg["role"] == "user":
            parts = [{"text": msg["content"]}]
            # Add screenshot to the last user message
            if screenshot_b64 and msg == messages[-1]:
                parts.append({
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": screenshot_b64
                    }
                })
            contents.append({"role": "user", "parts": parts})
        elif msg["role"] == "assistant":
            contents.append({"role": "model", "parts": [{"text": msg["content"]}]})
    
    payload = {
        "contents": contents,
        "tools": TOOLS,
        "tool_config": {"function_calling_config": {"mode": "ANY"}},
        "generation_config": {"temperature": 0.0}
    }
    if system_instruction:
        payload["system_instruction"] = system_instruction
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json=payload)
        return resp.json()


async def get_page_state(page) -> str:
    """Get a description of what's visible on the page."""
    # Wait for page to be ready
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=10000)
    except:
        pass
    
    try:
        state = await page.evaluate("""
            () => {
                const result = {
                    url: window.location.href,
                    title: document.title,
                    visible_text: [],
                    inputs: [],
                    buttons: [],
                    links: [],
                    selected_vehicle: null
                };
                
                // Check if a vehicle is already selected (appears at top of page)
                const vehicleButton = document.querySelector('#vehicleSelectorButton');
                if (vehicleButton) {
                    const vehicleText = vehicleButton.textContent?.trim();
                    // If it has year/make/model info, a vehicle is selected
                    if (vehicleText && /\\d{4}/.test(vehicleText) && vehicleText.length > 10) {
                        result.selected_vehicle = vehicleText;
                    }
                }
                
                // Get visible text (limited) - with safety check
                if (document.body) {
                    try {
                        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                        let count = 0;
                        while (walker.nextNode() && count < 50) {
                            const text = walker.currentNode.textContent.trim();
                            if (text.length > 2 && text.length < 100) {
                                result.visible_text.push(text);
                                count++;
                            }
                        }
                    } catch (e) {
                        result.visible_text.push("[Could not read text]");
                    }
                }
                
                // Get input fields
                document.querySelectorAll('input:not([type="hidden"])').forEach(el => {
                    result.inputs.push({
                        id: el.id,
                        name: el.name,
                        type: el.type,
                        placeholder: el.placeholder,
                        value: el.value ? '[has value]' : ''
                    });
                });
                
                // Get buttons
                document.querySelectorAll('button, input[type="submit"], input[type="button"], [role="button"]').forEach(el => {
                    const text = el.textContent?.trim() || el.value || el.id;
                    if (text) result.buttons.push({text, id: el.id});
                });
                
                // Get key links
                document.querySelectorAll('a').forEach(el => {
                    const text = el.textContent?.trim();
                    if (text && text.length < 50) result.links.push(text);
                });
                
                // Check for vehicle selector
                const vehicleSelector = document.querySelector('#vehicleSelectorButton, #qualifierTypeSelector');
                if (vehicleSelector) {
                    result.vehicle_selector_visible = true;
                    
                    // Get current tab
                    const activeTab = document.querySelector('#qualifierTypeSelector li.selected');
                    if (activeTab) result.current_tab = activeTab.textContent.trim();
                    
                    // Get available values
                    const values = [];
                    document.querySelectorAll('#qualifierValueSelector li.qualifier').forEach(li => {
                        values.push(li.textContent.trim());
                    });
                    if (values.length) result.available_values = values;
                    
                    // Get option groups
                    const options = [];
                    document.querySelectorAll('#qualifierValueSelector div.optionGroup').forEach(g => {
                        const name = g.querySelector('h1')?.textContent?.trim();
                        const vals = Array.from(g.querySelectorAll('li.qualifier')).map(li => ({
                            text: li.textContent.trim(),
                            selected: li.classList.contains('selected')
                        }));
                        if (name && vals.length) options.push({name, values: vals});
                    });
                    if (options.length) result.option_groups = options;
                }
                
                return result;
            }
        """)
    except Exception as e:
        # If page evaluation fails, return basic info from URL
        try:
            current_url = page.url
        except:
            current_url = "unknown"
        return f"URL: {current_url}\n\n⚠️ Page is still loading - TRUST THE SCREENSHOT to see what's actually on screen. Ignore any old URLs."
    
    # Format as readable text
    lines = [
        f"URL: {state['url']}",
        f"Title: {state['title']}"
    ]
    
    # IMPORTANT: Show if a vehicle is already selected
    if state.get('selected_vehicle'):
        lines.append(f"\n🚗 VEHICLE ALREADY SELECTED: {state['selected_vehicle']}")
        lines.append("   (No need to open Vehicle Selector - proceed to find the data!)")
    
    if state.get('inputs'):
        lines.append("\nInput fields:")
        for inp in state['inputs']:
            desc = f"  - #{inp['id']}" if inp['id'] else f"  - name={inp['name']}"
            if inp['type']: desc += f" (type={inp['type']})"
            if inp['placeholder']: desc += f" placeholder='{inp['placeholder']}'"
            if inp['value']: desc += f" {inp['value']}"
            lines.append(desc)
    
    if state.get('buttons'):
        lines.append("\nButtons:")
        for btn in state['buttons'][:10]:
            lines.append(f"  - '{btn['text']}'" + (f" id={btn['id']}" if btn['id'] else ""))
    
    if state.get('vehicle_selector_visible'):
        lines.append("\nVehicle Selector:")
        if state.get('current_tab'):
            lines.append(f"  Current tab: {state['current_tab']}")
        if state.get('available_values'):
            # Show ALL available values - important for finding Toyota, etc.
            lines.append(f"  Available values: {state['available_values']}")
            lines.append(f"  (Look at the SCREENSHOT for the full list - you may need to scroll)")
        if state.get('option_groups'):
            for opt in state['option_groups']:
                selected = next((v['text'] for v in opt['values'] if v['selected']), None)
                if selected:
                    lines.append(f"  {opt['name']}: {selected} (selected)")
                else:
                    lines.append(f"  {opt['name']}: {[v['text'] for v in opt['values']]}")
    
    if not state.get('vehicle_selector_visible') and state.get('visible_text'):
        lines.append("\nVisible text (sample):")
        for text in state['visible_text'][:20]:
            lines.append(f"  {text}")
    
    return "\n".join(lines)


async def execute_action(page, action: dict) -> str:
    """Execute an action and return the result."""
    name = action["name"]
    args = action.get("args", {})
    
    try:
        if name == "click":
            selector = args["selector"]
            
            # Handle text= prefix (Playwright format) - use directly
            if selector.startswith("text="):
                try:
                    await page.click(selector, timeout=5000)
                    await asyncio.sleep(1)
                    return f"Clicked {selector}"
                except Exception as e:
                    # Try without the text= prefix as fallback
                    plain_text = selector[5:]
                    return await execute_action(page, {"name": "click", "args": {"selector": plain_text}})
            
            # Handle button:has-text() - try as-is first, then fallback to input[value]
            if 'button:has-text' in selector:
                try:
                    await page.click(selector, timeout=3000)
                    await asyncio.sleep(1)
                    return f"Clicked {selector}"
                except:
                    # Extract the text and try input[value] instead
                    # button:has-text("Use This Vehicle") -> Use This Vehicle
                    import re
                    match = re.search(r'has-text\(["\']([^"\']+)["\']\)', selector)
                    if match:
                        btn_text = match.group(1)
                        try:
                            await page.click(f'input[value="{btn_text}"]', timeout=3000)
                            await asyncio.sleep(1)
                            return f"Clicked input[value='{btn_text}'] (fallback from button)"
                        except:
                            pass
                    # Let it fall through to the smart handling below
            
            # Smart selector handling - if it looks like plain text, try multiple approaches
            if not selector.startswith(('#', '.', '[', '/')) and ':' not in selector:
                # It's probably just text like "Login" or "L"
                # For short text (1-2 chars), be more specific to avoid false matches
                is_short_text = len(selector) <= 2
                
                if is_short_text:
                    # For short text, prioritize elements in the vehicle selector
                    approaches = [
                        # Vehicle selector list items (most specific for Y/M/M/E/S selection)
                        f".qualifierList li:has-text('{selector}')",
                        f"li:has-text('{selector}'):not(:has-text('{selector}a')):not(:has-text('{selector}o'))",  # Exact match
                        f"a:has-text('{selector}')",
                        f"button:has-text('{selector}')",
                        f"text='{selector}'",  # Exact match with quotes
                    ]
                else:
                    approaches = [
                        f"text={selector}",
                        f"li:has-text('{selector}')",
                        f"button:has-text('{selector}')",
                        f"input[value='{selector}']",  # Important for ShopKeyPro buttons
                        f"a:has-text('{selector}')",
                        f"*:has-text('{selector}')",
                    ]
                
                for approach in approaches:
                    try:
                        loc = page.locator(approach).first
                        if await loc.is_visible(timeout=1000):
                            await loc.click()
                            await asyncio.sleep(1)
                            return f"Clicked '{selector}' (using {approach})"
                    except:
                        continue
                return f"Error: Could not find clickable element with text '{selector}'"
            else:
                # It's a proper selector
                await page.click(selector, timeout=10000)
                await asyncio.sleep(1)
                return f"Clicked {selector}"
            
        elif name == "type_text":
            selector = args["selector"]
            text = args["text"]
            await page.fill(selector, text)
            return f"Typed into {selector}"
            
        elif name == "wait":
            seconds = args.get("seconds", 2)
            await asyncio.sleep(seconds)
            return f"Waited {seconds} seconds"
            
        elif name == "ask_user":
            question = args["question"]
            options = args.get("options", [])
            print(f"\n🤖 GEMINI ASKS: {question}")
            if options:
                print(f"   Options: {options}")
            # For now, just return "I don't know, please pick the best option"
            # In real usage, this would be interactive
            return f"User says: Please pick whatever makes the most sense based on the goal"
            
        elif name == "done":
            return f"DONE: {args.get('message', 'Complete')}"
            
        else:
            return f"Unknown action: {name}"
            
    except Exception as e:
        return f"Error: {e}"


async def main():
    import sys
    import argparse
    
    print("=" * 60)
    print("SMART AGENT TEST - Let Gemini figure it out")
    print("=" * 60)
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Smart agent test")
    parser.add_argument("--cdp-port", type=int, default=None, help="CDP port to connect to existing browser")
    parser.add_argument("--goal", type=str, default=None, help="Goal to accomplish")
    parser.add_argument("goal_args", nargs="*", help="Goal (if not using --goal)")
    args = parser.parse_args()
    
    # Get goal from --goal or positional args
    if args.goal:
        goal = args.goal
    elif args.goal_args:
        goal = " ".join(args.goal_args)
    else:
        goal = "fluid capacities for 2018 Ford F-150 5.0L"
    
    # Get CDP port
    chrome_port = args.cdp_port or 9333
    use_existing_browser = args.cdp_port is not None
    
    print(f"\nGoal: {goal}")
    print(f"CDP Port: {chrome_port} ({'existing' if use_existing_browser else 'new'})")
    print("\nLaunching browser...")
    
    chrome_proc = None
    if not use_existing_browser:
        # Kill any existing Chrome on our debug port
        subprocess.run(["pkill", "-f", f"remote-debugging-port={chrome_port}"], capture_output=True)
        await asyncio.sleep(1)
        
        # Launch Chrome with proper window
        chrome_proc = subprocess.Popen([
            "/usr/bin/google-chrome",
            f"--remote-debugging-port={chrome_port}",
            "--no-first-run",
            "--no-default-browser-check",
            "--window-size=1200,900",
            f"--user-data-dir=/tmp/mitchell-smart-test",
            "https://www.shopkeypro.com/"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        await asyncio.sleep(3)
    
    # Connect Playwright
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(f"http://localhost:{chrome_port}")
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else await context.new_page()
        
        # Define logout function to be called in finally
        async def do_logout():
            """Logout from ShopKeyPro - MUST be called before closing browser."""
            print("\n🚪 Logging out to close ShopKeyPro session...")
            try:
                # First check if we're on a ShopKeyPro page
                if "shopkeypro.com" not in page.url.lower() and "mitchell" not in page.url.lower():
                    print("   ℹ️ Not on ShopKeyPro page")
                    return True
                
                # STEP 1: Smart modal discovery - find and close any blocking modals
                # Try multiple times in case there are nested modals
                print("   📋 Step 1: Checking for open modals...")
                for attempt in range(3):
                    modal_closed = False
                    
                    # SMART DISCOVERY: Find any visible close mechanism
                    # These are ordered from most specific to most generic
                    modal_close_selectors = [
                        # VERIFIED: ShopKeyPro vehicle selector Cancel button
                        "input.grey.button[value='Cancel']",
                        "input[data-action='Cancel']",
                        # VERIFIED: Data modal close (Fluid Capacities, etc.) - X button
                        "span.close",
                        # Generic close patterns
                        "button.close",
                        ".close-button",
                        "[aria-label='Close']",
                        "[aria-label='close']",
                        # Modal close icons
                        ".modal-close",
                        ".modalDialogView .close",
                        "button.close-modal",
                        # Back/close arrows
                        ".back-button",
                        "a.back",
                    ]
                    
                    for sel in modal_close_selectors:
                        try:
                            loc = page.locator(sel).first
                            if await loc.is_visible(timeout=300):
                                await loc.click()
                                print(f"   ℹ️ Closed modal with: {sel}")
                                await asyncio.sleep(0.5)
                                modal_closed = True
                                break  # One modal closed, loop to check for more
                        except:
                            continue
                    
                    # If no predefined selector worked, try dynamic discovery
                    if not modal_closed:
                        try:
                            # Look for any element with 'close' in class that's visible
                            close_els = await page.query_selector_all('[class*="close"]:visible')
                            for el in close_els[:5]:
                                try:
                                    if await el.is_visible():
                                        tag = await el.evaluate('e => e.tagName')
                                        cls = await el.evaluate('e => e.className')
                                        # Skip if it's a huge container
                                        box = await el.bounding_box()
                                        if box and box['width'] < 100 and box['height'] < 100:
                                            await el.click()
                                            print(f"   ℹ️ Closed modal with discovered: <{tag}> class={cls}")
                                            modal_closed = True
                                            await asyncio.sleep(0.5)
                                            break
                                except:
                                    continue
                        except:
                            pass
                    
                    if not modal_closed:
                        break  # No more modals to close
                
                # STEP 2: Click logout
                print("   📋 Step 2: Clicking logout...")
                logout_clicked = False
                
                # VERIFIED: ShopKeyPro logout is <LI id="logout"> with icon (no text)
                try:
                    logout = page.locator("#logout")
                    if await logout.is_visible(timeout=2000):
                        await logout.click()
                        logout_clicked = True
                        print("   ✅ Clicked logout (#logout)")
                except Exception as e:
                    print(f"   ⚠️ #logout click failed: {e}")
                
                # Fallback selectors if #logout didn't work
                if not logout_clicked:
                    fallback_selectors = [
                        "#logout a",
                        'li#logout',
                        'a:has-text("Logout")',
                        'a:has-text("Log Out")',
                    ]
                    for selector in fallback_selectors:
                        try:
                            loc = page.locator(selector).first
                            if await loc.is_visible(timeout=1000):
                                await loc.click()
                                logout_clicked = True
                                print(f"   ✅ Clicked logout via {selector}")
                                break
                        except:
                            continue
                
                if not logout_clicked:
                    print("   ⚠️ Could not find logout button")
                    return False
                
                # STEP 3: CONFIRM logout with screenshot + page state check
                print("   📋 Step 3: Confirming logout...")
                await asyncio.sleep(2)
                
                # Take confirmation screenshot
                try:
                    await page.screenshot(path='/tmp/logout_confirm.png')
                    print("   📸 Screenshot saved: /tmp/logout_confirm.png")
                except:
                    pass
                
                # Check page state to confirm logout
                current_url = page.url.lower()
                
                # Look for indicators we're logged out
                login_indicators = [
                    await page.query_selector('#loginButton'),
                    await page.query_selector('#btnLogin'),
                    await page.query_selector('#username'),
                    await page.query_selector('input[name="username"]'),
                ]
                has_login_form = any(ind is not None for ind in login_indicators)
                
                # Look for indicators we're still logged in
                logout_button = await page.query_selector('#logout')
                logout_visible = await logout_button.is_visible() if logout_button else False
                
                # Confirm status
                if has_login_form or 'login' in current_url or not logout_visible:
                    print("   ✅ LOGOUT CONFIRMED - login page detected")
                    print(f"      URL: {page.url}")
                    return True
                else:
                    print("   ⚠️ LOGOUT UNCERTAIN - may still be logged in")
                    print(f"      URL: {page.url}")
                    print(f"      Login form found: {has_login_form}")
                    print(f"      Logout button still visible: {logout_visible}")
                    return False
                    
            except Exception as e:
                print(f"   ⚠️ Logout error: {e}")
            return False
        
        try:
            # Make sure we're on ShopKeyPro
            if "shopkeypro" not in page.url.lower():
                print("Navigating to ShopKeyPro...")
                await page.goto("https://www.shopkeypro.com/", timeout=30000)
            else:
                print(f"Already at: {page.url}")
            await asyncio.sleep(2)
        
            # Take initial screenshot
            screenshot_bytes = await page.screenshot()
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            print(f"📸 Screenshot taken ({len(screenshot_bytes)} bytes)")
            
            # Conversation with Gemini
            page_state = await get_page_state(page)
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"I need to find: {goal}\n\nHere's what I see on the page (I'm also sending you a screenshot):\n{page_state}"}
            ]
            
            print("\n" + "=" * 60)
            if USE_OLLAMA:
                print(f"Starting conversation with OLLAMA ({OLLAMA_MODEL}) with VISION!")
            else:
                print("Starting conversation with Gemini (with VISION!)...")
            print("=" * 60)
            
            last_action = None
            
            for step in range(1, 31):
                print(f"\n{'='*60}")
                print(f"STEP {step}")
                print("=" * 60)
                
                # FRESH messages each step - no history accumulation
                # Just system prompt + current state
                if last_action:
                    user_content = f"I need to find: {goal}\n\nLast action: {last_action}\n\nCurrent page state (screenshot attached):\n{page_state}"
                else:
                    user_content = f"I need to find: {goal}\n\nHere's what I see on the page (screenshot attached):\n{page_state}"
                
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content}
                ]
                
                # Show the prompt
                model_name = OLLAMA_MODEL if USE_OLLAMA else "Gemini"
                print(f"\n📤 PROMPT TO {model_name} (+ screenshot):")
                print("-" * 40)
                print(messages[-1]["content"][:2000])
                if len(messages[-1]["content"]) > 2000:
                    print("... [truncated]")
                print("-" * 40)
                
                # Call the model WITH screenshot
                if USE_OLLAMA:
                    response = await call_ollama(messages, screenshot_b64)
                    action = response.get("action")
                    raw = response.get("raw", "")
                    
                    print(f"\n📥 {OLLAMA_MODEL} RESPONSE:")
                    print("-" * 40)
                    if raw:
                        print(f"Raw: {raw[:500]}")
                    if action:
                        print(f"Parsed Action: {action['name']}({action['args']})")
                    print("-" * 40)
                else:
                    response = await call_gemini(messages, screenshot_b64)
                    
                    # Parse Gemini response
                    candidates = response.get("candidates", [])
                    if not candidates:
                        print(f"❌ No response from Gemini: {response}")
                        break
                    
                    parts = candidates[0].get("content", {}).get("parts", [])
                    
                    print("\n📥 GEMINI RESPONSE:")
                    print("-" * 40)
                    
                    action = None
                    for part in parts:
                        if "functionCall" in part:
                            func = part["functionCall"]
                            action = {"name": func["name"], "args": func.get("args", {})}
                            print(f"Action: {action['name']}({action['args']})")
                        elif "text" in part:
                            print(f"Text: {part['text']}")
                    print("-" * 40)
                
                if not action:
                    print("No action returned, stopping")
                    break
                
                # Execute the action
                print(f"\n⚡ EXECUTING: {action['name']}")
                result = await execute_action(page, action)
                print(f"   Result: {result}")
                
                if action["name"] == "done":
                    print(f"\n✅ COMPLETE: {action['args'].get('message', '')}")
                    break
                
                # Remember what we just did
                last_action = f"{action['name']}({action['args']}) -> {result}"
                
                # Get new page state AND new screenshot
                # Wait longer if page might be navigating
                await asyncio.sleep(2)
                
                # Try to wait for page to be stable
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                except:
                    pass
                
                page_state = await get_page_state(page)
                screenshot_bytes = await page.screenshot()
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                print(f"📸 New screenshot taken ({len(screenshot_bytes)} bytes)")
        
        finally:
            # ALWAYS logout before closing - this is critical!
            await do_logout()
            print("\nTest complete. Browser will close in 3 seconds...")
            await asyncio.sleep(3)
        
        # Only terminate if we launched the browser
        if chrome_proc:
            chrome_proc.terminate()


if __name__ == "__main__":
    # Handle Ctrl+C gracefully - the finally block in main() will handle logout
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted! Logout should have been attempted in finally block.")
        print("If not logged out, manually visit ShopKeyPro and logout to free the session.")
        sys.exit(130)
