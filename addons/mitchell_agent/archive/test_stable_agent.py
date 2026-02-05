#!/usr/bin/env python3
"""
Stable Agent Test - Deterministic vehicle selection + Gemini for data extraction

This test uses:
1. DETERMINISTIC selectors for vehicle selection (Year->Make->Model->Engine->Submodel)
2. Gemini vision only for finding and extracting the fluid capacities data

This is more stable than pure Gemini-driven navigation because:
- Vehicle selection requires scrolling and the Gemini vision can miss options
- Vehicle selection follows a known pattern that we can script reliably
"""
import asyncio
import base64
import httpx
import os
import re
import sys
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.0-flash"

# All the actions Gemini can take for data extraction
TOOLS = [{
    "function_declarations": [
        {
            "name": "click",
            "description": "Click on an element",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector or text to click, e.g. '#loginButton' or 'text=Maintenance'"},
                    "reason": {"type": "string", "description": "Why you're clicking this"}
                },
                "required": ["selector", "reason"]
            }
        },
        {
            "name": "wait",
            "description": "Wait for page to load",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {"type": "number", "description": "How long to wait"}
                },
                "required": ["seconds"]
            }
        },
        {
            "name": "extract_data",
            "description": "Extract structured data from what's visible on the page",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {"type": "string", "description": "The extracted data in a readable format"},
                    "complete": {"type": "boolean", "description": "True if all requested data was found"}
                },
                "required": ["data", "complete"]
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
                    "data": {"type": "string", "description": "Any extracted data"}
                },
                "required": ["success", "message"]
            }
        }
    ]
}]


async def select_vehicle(page, year: str, make: str, model: str, engine: str = None, submodel: str = None):
    """
    Deterministic vehicle selection using known ShopKeyPro selectors.
    This is much more reliable than letting Gemini navigate.
    """
    print(f"\n🚗 Selecting vehicle: {year} {make} {model}")
    
    # First, close any open modals that might be blocking
    for sel in ["input[data-action='Cancel']", "span.close"]:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible(timeout=500):
                await loc.click()
                await asyncio.sleep(0.3)
        except:
            pass
    
    # Click on vehicle selector to open it
    print("  Opening vehicle selector...")
    try:
        vs = page.locator("#vehicleSelectorButton")
        if await vs.is_visible(timeout=3000):
            await vs.click()
            await asyncio.sleep(1)
            print("  ✅ Vehicle selector opened")
        else:
            print("  ⚠️ Vehicle selector button not visible")
            return False
    except Exception as e:
        print(f"  ⚠️ Could not open vehicle selector: {e}")
        return False
    
    # IMPORTANT: Click "Vehicle Selection" accordion to show Year/Make/Model view
    # The modal has accordion sections: Vehicle History, VIN or Plate, Vehicle Selection
    print("  Clicking 'Vehicle Selection' accordion...")
    result = await page.evaluate('''() => {
        const headers = document.querySelectorAll('.accordion .header');
        for (const h of headers) {
            if (h.textContent.includes('Vehicle Selection')) {
                h.click();
                return 'clicked';
            }
        }
        return 'not found';
    }''')
    if result != 'clicked':
        print("  ⚠️ Could not find Vehicle Selection accordion")
        return False
    print("  ✅ Expanded Vehicle Selection view")
    await asyncio.sleep(1)
    
    # Now verify Year tab/values are visible
    year_tab = await page.query_selector("#qualifierTypeSelector li.selected:has-text('Year')")
    if not year_tab:
        # Try clicking Year tab explicitly
        try:
            await page.click("li:has-text('Year')", timeout=2000)
            await asyncio.sleep(0.5)
        except:
            pass
    
    # Helper to click an option and wait
    async def select_option(value: str, tab_name: str):
        print(f"  Selecting {tab_name}: {value}")
        
        # Wait for the value selector to have options
        await asyncio.sleep(0.5)
        
        # Try clicking the value - it should be in the qualifier list
        selectors = [
            f"#qualifierValueSelector li.qualifier:has-text('{value}')",
            f"li.qualifier:has-text('{value}')",
            f"text={value}",
        ]
        
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if await loc.is_visible(timeout=2000):
                    await loc.click()
                    await asyncio.sleep(0.5)
                    return True
            except:
                continue
        
        print(f"  ⚠️ Could not find {value} in {tab_name}")
        return False
    
    # Select Year
    if not await select_option(year, "Year"):
        return False
    await asyncio.sleep(0.5)
    
    # Select Make
    if not await select_option(make, "Make"):
        return False
    await asyncio.sleep(0.5)
    
    # Select Model  
    if not await select_option(model, "Model"):
        return False
    await asyncio.sleep(0.5)
    
    # Select Engine if specified
    if engine:
        if not await select_option(engine, "Engine"):
            # Try to find any engine with that prefix
            engines = await page.locator("#qualifierValueSelector li.qualifier").all()
            for eng in engines:
                text = await eng.inner_text()
                if engine.lower() in text.lower():
                    await eng.click()
                    await asyncio.sleep(0.5)
                    break
    else:
        # Just pick the first engine
        first_engine = page.locator("#qualifierValueSelector li.qualifier").first
        if await first_engine.is_visible(timeout=2000):
            await first_engine.click()
            await asyncio.sleep(0.5)
    
    # Select Submodel if specified, otherwise pick first
    await asyncio.sleep(0.5)
    if submodel:
        await select_option(submodel, "Submodel")
    else:
        first_sub = page.locator("#qualifierValueSelector li.qualifier").first
        if await first_sub.is_visible(timeout=2000):
            await first_sub.click()
            await asyncio.sleep(0.5)
    
    # Click "Use This Vehicle" to confirm
    await asyncio.sleep(0.5)
    try:
        utv = page.locator('input[value="Use This Vehicle"]')
        if await utv.is_visible(timeout=2000):
            await utv.click()
            print("  ✅ Clicked 'Use This Vehicle'")
            await asyncio.sleep(1)
        else:
            # Vehicle selector may have auto-closed
            print("  ℹ️ Vehicle selector closed automatically")
    except Exception as e:
        print(f"  ℹ️ Note: {e}")
    
    return True


async def call_gemini(messages: list, screenshot_b64: str = None) -> dict:
    """Call Gemini and return the response with screenshot."""
    contents = []
    system_instruction = None
    
    for msg in messages:
        if msg["role"] == "system":
            system_instruction = {"parts": [{"text": msg["content"]}]}
        elif msg["role"] == "user":
            parts = [{"text": msg["content"]}]
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


async def call_gemini_text(messages: list) -> dict:
    """Call Gemini with text only (no vision)."""
    contents = []
    system_instruction = None
    
    for msg in messages:
        if msg["role"] == "system":
            system_instruction = {"parts": [{"text": msg["content"]}]}
        elif msg["role"] == "user":
            contents.append({"role": "user", "parts": [{"text": msg["content"]}]})
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


async def get_page_text(page) -> str:
    """Extract all text content from the page, including scrollable areas."""
    # Get main content text
    text = await page.evaluate('''() => {
        // Get all text from the page
        const getText = (el) => {
            if (!el) return '';
            
            // Skip hidden elements
            const style = window.getComputedStyle(el);
            if (style.display === 'none' || style.visibility === 'hidden') return '';
            
            // Get text content
            let text = '';
            for (const child of el.childNodes) {
                if (child.nodeType === Node.TEXT_NODE) {
                    const t = child.textContent.trim();
                    if (t) text += t + ' ';
                } else if (child.nodeType === Node.ELEMENT_NODE) {
                    text += getText(child);
                }
            }
            return text;
        };
        
        // Get sidebar menu items
        const menuItems = [];
        document.querySelectorAll('.menuItem, .category, [data-category]').forEach(el => {
            const t = el.textContent.trim();
            if (t && t.length < 100) menuItems.push(t);
        });
        
        // Get modal content if present
        const modals = [];
        document.querySelectorAll('.modal, .modalDialogView, [role="dialog"], .popup').forEach(el => {
            modals.push(el.innerText || el.textContent);
        });
        
        // Get main content
        const mainContent = document.querySelector('#contentPanel, .content, main, #main')?.innerText || '';
        
        // Get any tables
        const tables = [];
        document.querySelectorAll('table').forEach(table => {
            const rows = [];
            table.querySelectorAll('tr').forEach(tr => {
                const cells = [];
                tr.querySelectorAll('td, th').forEach(cell => {
                    cells.push(cell.textContent.trim());
                });
                if (cells.length) rows.push(cells.join(' | '));
            });
            if (rows.length) tables.push(rows.join('\\n'));
        });
        
        // Get any specification data
        const specs = [];
        document.querySelectorAll('.spec, .specification, .data-row, .row').forEach(el => {
            const t = el.textContent.trim();
            if (t && t.length < 500) specs.push(t);
        });
        
        return JSON.stringify({
            url: window.location.href,
            title: document.title,
            menuItems: menuItems.slice(0, 50),
            modals: modals.slice(0, 5),
            mainContent: mainContent.substring(0, 10000),
            tables: tables.slice(0, 10),
            specs: specs.slice(0, 100)
        });
    }''')
    return text


async def get_clickable_elements(page) -> str:
    """Get list of clickable elements on the page, including Quick Access buttons."""
    elements = await page.evaluate('''() => {
        const items = [];
        
        // Quick Access buttons (important!)
        document.querySelectorAll('.accessItem, [id*="Access"]').forEach(el => {
            const text = el.textContent.trim();
            const id = el.id;
            if (text && id) {
                items.push({
                    text: text.substring(0, 80),
                    id: id,
                    tag: 'quickAccess'
                });
            }
        });
        
        // Menu items in sidebar
        document.querySelectorAll('.menuItem, .category, [data-action], a, button').forEach(el => {
            const text = el.textContent.trim();
            const id = el.id;
            if (text && text.length < 100 && text.length > 2) {
                items.push({
                    text: text.substring(0, 80),
                    id: id || null,
                    tag: el.tagName.toLowerCase()
                });
            }
        });
        
        return items.slice(0, 100);
    }''')
    return elements


async def do_logout(page):
    """Logout from ShopKeyPro."""
    print("\n🚪 Logging out...")
    try:
        # Close any modals first
        for sel in ["input[data-action='Cancel']", "span.close", ".close"]:
            try:
                loc = page.locator(sel).first
                if await loc.is_visible(timeout=500):
                    await loc.click()
                    await asyncio.sleep(0.3)
            except:
                pass
        
        # Click logout
        logout = page.locator("#logout")
        if await logout.is_visible(timeout=2000):
            await logout.click()
            print("  ✅ Logged out")
            await asyncio.sleep(1)
    except Exception as e:
        print(f"  ⚠️ Logout: {e}")


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Stable agent test")
    parser.add_argument("--cdp-port", type=int, default=9222, help="CDP port")
    parser.add_argument("--year", type=str, default="2020", help="Vehicle year")
    parser.add_argument("--make", type=str, default="Toyota", help="Vehicle make")
    parser.add_argument("--model", type=str, default="Camry", help="Vehicle model")
    parser.add_argument("--engine", type=str, default="2.5L", help="Engine (partial match OK)")
    parser.add_argument("--submodel", type=str, default=None, help="Submodel")
    parser.add_argument("--data", type=str, default="fluid capacities", help="What data to find")
    args = parser.parse_args()
    
    print("=" * 60)
    print("STABLE AGENT TEST")
    print("=" * 60)
    print(f"Vehicle: {args.year} {args.make} {args.model} {args.engine or ''}")
    print(f"Looking for: {args.data}")
    print(f"CDP Port: {args.cdp_port}")
    
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(f"http://localhost:{args.cdp_port}")
        context = browser.contexts[0]
        page = context.pages[0]
        
        try:
            # Make sure we're on ShopKeyPro
            if "shopkeypro" not in page.url.lower():
                print("\nNavigating to ShopKeyPro...")
                await page.goto("https://www1.shopkeypro.com/Main/Index", timeout=30000)
                await asyncio.sleep(2)
            
            print(f"\nCurrent URL: {page.url}")
            
            # Check if logged in
            logout = await page.query_selector("#logout")
            if not logout or not await logout.is_visible():
                print("❌ Not logged in - please restart CDP server")
                return
            print("✅ Logged in")
            
            # PHASE 1: Deterministic vehicle selection
            print("\n" + "=" * 60)
            print("PHASE 1: Vehicle Selection (Deterministic)")
            print("=" * 60)
            
            success = await select_vehicle(page, args.year, args.make, args.model, args.engine, args.submodel)
            if not success:
                print("❌ Vehicle selection failed")
                return
            
            await asyncio.sleep(1)
            
            # Verify vehicle is selected
            vs = await page.query_selector("#vehicleSelectorButton")
            if vs:
                text = await vs.inner_text()
                print(f"\n✅ Vehicle selected: {text.strip()[:60]}")
            
            # PHASE 2: Use Gemini to find and extract the data (TEXT-BASED)
            print("\n" + "=" * 60)
            print("PHASE 2: Data Extraction (Gemini Text)")
            print("=" * 60)
            
            system_prompt = f"""You are helping extract {args.data} from the ShopKeyPro website.
The vehicle has been selected: {args.year} {args.make} {args.model}

Your task:
1. Look at the PAGE TEXT to see the current page content
2. Navigate to find "{args.data}" - use Quick Access buttons or menu items
3. Once you see the actual data (tables with values), use extract_data to capture ALL the values
4. If you need to navigate, click on menu items

QUICK ACCESS BUTTONS (use these with # selector):
- #fluidsQuickAccess - Fluid Capacities
- #commonSpecsAccess - Common Specs (torque specs, general specs)
- #resetProceduresAccess - Reset Procedures (oil life reset, TPMS reset)
- #technicalBulletinAccess - Technical Bulletins / TSBs
- #dtcIndexAccess - DTC Index (trouble codes)
- #tireInfoAccess - Tire Information
- #adasAccess - Driver Assist / ADAS

HOW TO CLICK: Use the ID directly, e.g. selector="#commonSpecsAccess"

DATA EXTRACTION RULES:
- When you see the data in the page text, READ ALL THE VALUES
- Include ALL items with their values
- Format as a readable list or comma-separated values
- The data should be the ACTUAL VALUES, not just titles

IMPORTANT:
- The vehicle is already selected - don't re-select it
- PREFER Quick Access buttons over menu navigation - they're faster
- When you see tables in the page text, extract ALL rows"""
            
            # Get initial page text
            page_text = await get_page_text(page)
            clickables = await get_clickable_elements(page)
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"""Find {args.data} for this vehicle.

PAGE CONTENT:
{page_text}

CLICKABLE ELEMENTS (can use text= selector):
{clickables[:2000] if isinstance(clickables, str) else str(clickables)[:2000]}"""}
            ]
            
            extracted_data = None
            
            for step in range(1, 16):  # Max 15 steps
                print(f"\n--- Step {step} ---")
                
                response = await call_gemini_text(messages)
                
                candidates = response.get("candidates", [])
                if not candidates:
                    print(f"No response: {response}")
                    break
                
                parts = candidates[0].get("content", {}).get("parts", [])
                
                action = None
                for part in parts:
                    if "functionCall" in part:
                        func = part["functionCall"]
                        action = {"name": func["name"], "args": func.get("args", {})}
                        break
                
                if not action:
                    print("No action returned")
                    break
                
                print(f"Action: {action['name']}({action['args']})")
                
                # Execute action
                if action["name"] == "click":
                    selector = action["args"]["selector"]
                    try:
                        # Handle text= prefix
                        if selector.startswith("text="):
                            await page.click(selector, timeout=5000)
                        else:
                            # Try as selector first, then as text
                            try:
                                await page.click(selector, timeout=3000)
                            except:
                                await page.click(f"text={selector}", timeout=5000)
                        print(f"  Clicked: {selector}")
                        await asyncio.sleep(1.5)
                    except Exception as e:
                        print(f"  Error clicking: {e}")
                
                elif action["name"] == "wait":
                    secs = action["args"].get("seconds", 2)
                    await asyncio.sleep(secs)
                    print(f"  Waited {secs}s")
                
                elif action["name"] == "extract_data":
                    extracted_data = action["args"].get("data", "")
                    complete = action["args"].get("complete", False)
                    print(f"  Extracted data (complete={complete}):")
                    print(f"  {extracted_data[:800]}...")
                    if complete:
                        break
                
                elif action["name"] == "done":
                    success = action["args"].get("success", False)
                    msg = action["args"].get("message", "")
                    extracted_data = action["args"].get("data", extracted_data)
                    print(f"  Done: success={success}, {msg}")
                    break
                
                # Get new page text
                page_text = await get_page_text(page)
                clickables = await get_clickable_elements(page)
                
                # Update messages with result
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"""Continue finding {args.data}. Last action: {action['name']}.

PAGE CONTENT:
{page_text}

CLICKABLE ELEMENTS:
{clickables[:2000] if isinstance(clickables, str) else str(clickables)[:2000]}"""}
                ]
            
            # Final result
            print("\n" + "=" * 60)
            print("RESULT")
            print("=" * 60)
            if extracted_data:
                print(extracted_data)
            else:
                print("No data extracted")
                
        finally:
            await do_logout(page)
            print("\nDone.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(130)
