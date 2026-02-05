#!/usr/bin/env python3
"""
Ollama Navigator Test
=====================
Uses gemma3:4b via Ollama to navigate ShopKeyPro autonomously.

This is a proof-of-concept for AI-driven browser navigation.
The model receives:
  - Current page state (visible elements, selections)
  - Navigation config (available selectors)
  - Goal description

And returns the next action to take.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional
import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

# Ollama settings
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma3:4b"

# System prompt for the navigator
SYSTEM_PROMPT = """You are a browser navigation agent. Your job is to navigate a web application to achieve a goal.

You will receive:
1. GOAL: What we're trying to accomplish
2. STATE: Current page state (URL, visible elements, current selections)
3. AVAILABLE_ACTIONS: Valid selectors you can click

Respond with ONLY a JSON object (no markdown, no explanation):
{
  "thought": "Brief reasoning about what to do next",
  "action": "click" | "wait" | "done" | "extract",
  "selector": "the selector to click (if action=click)",
  "reason": "Why this action moves us toward the goal"
}

Rules:
- Only use selectors from AVAILABLE_ACTIONS
- If the goal is achieved, use action="done"
- If you need to wait for page load, use action="wait"
- If you see the target data, use action="extract"
- Be efficient - take the most direct path to the goal
"""


async def call_ollama(prompt: str) -> str:
    """Call Ollama API and return the response."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Low temp for consistent actions
                    "num_predict": 200,  # Short responses
                }
            }
        )
        response.raise_for_status()
        return response.json()["response"]


async def get_page_state(page) -> dict:
    """Extract current page state for the model."""
    state = await page.evaluate("""
        () => {
            const result = {
                url: window.location.href,
                title: document.title,
                visible_elements: [],
                current_selection: {},
                options_panel: null
            };
            
            // Check vehicle selector state
            const leftPane = document.querySelector('#qualifierTypeSelector');
            if (leftPane) {
                const items = leftPane.querySelectorAll('li');
                for (const li of items) {
                    const text = li.textContent.trim();
                    const isSelected = li.classList.contains('selected');
                    const isDisabled = li.classList.contains('disabled');
                    if (isSelected) result.current_selection.active_tab = text;
                    result.visible_elements.push({
                        type: 'tab',
                        text: text,
                        selected: isSelected,
                        disabled: isDisabled
                    });
                }
            }
            
            // Check qualifier values (year/make/model/engine list)
            const rightPane = document.querySelector('#qualifierValueSelector');
            if (rightPane) {
                // Check if it's the options panel
                const optionsDiv = rightPane.querySelector('div.options');
                if (optionsDiv) {
                    result.options_panel = {visible: true, groups: []};
                    const groups = optionsDiv.querySelectorAll('div.optionGroup');
                    for (const g of groups) {
                        const h1 = g.querySelector('h1');
                        const h2 = g.querySelector('h2');
                        const items = g.querySelectorAll('li.qualifier');
                        result.options_panel.groups.push({
                            name: h1?.textContent?.trim() || '',
                            selected_value: h2?.textContent?.trim() || '',
                            is_selected: g.classList.contains('selected'),
                            values: Array.from(items).map(li => ({
                                text: li.textContent.trim(),
                                selected: li.classList.contains('selected')
                            }))
                        });
                    }
                } else {
                    // Regular qualifier list
                    const items = rightPane.querySelectorAll('li.qualifier');
                    result.visible_elements.push({
                        type: 'value_list',
                        count: items.length,
                        values: Array.from(items).slice(0, 10).map(li => li.textContent.trim())
                    });
                }
            }
            
            // Check for quick access panel
            const quickAccess = document.querySelector('#quickAccessPanel');
            if (quickAccess) {
                result.visible_elements.push({type: 'quick_access_panel', visible: true});
            }
            
            // Check for fluid capacities content
            const fluidContent = document.querySelector('[class*="fluid"], [id*="fluid"]');
            if (fluidContent) {
                result.visible_elements.push({
                    type: 'fluid_content',
                    text: fluidContent.textContent?.substring(0, 200)
                });
            }
            
            // Check for modal
            const modal = document.querySelector('.modalDialogView, [class*="modal"]');
            if (modal && modal.offsetParent !== null) {
                result.visible_elements.push({type: 'modal', visible: true});
            }
            
            return result;
        }
    """)
    return state


def build_available_actions(state: dict) -> list:
    """Build list of available actions based on current state."""
    actions = []
    
    # Always available
    actions.append({"name": "wait", "selector": None, "desc": "Wait for page to load"})
    
    # Vehicle selector tabs
    for elem in state.get("visible_elements", []):
        if elem.get("type") == "tab" and not elem.get("disabled"):
            tab_name = elem["text"].lower()
            actions.append({
                "name": f"click_{tab_name}_tab",
                "selector": f"#qualifierTypeSelector li.{tab_name}",
                "desc": f"Click the {elem['text']} tab"
            })
        
        if elem.get("type") == "value_list":
            for val in elem.get("values", []):
                actions.append({
                    "name": f"select_{val}",
                    "selector": f"#qualifierValueSelector li.qualifier:has-text('{val}')",
                    "desc": f"Select {val}"
                })
    
    # Options panel actions
    if state.get("options_panel"):
        for group in state["options_panel"].get("groups", []):
            for val in group.get("values", []):
                actions.append({
                    "name": f"select_{group['name']}_{val['text']}",
                    "selector": f"div.optionGroup:has(h1:has-text('{group['name']}')) li.qualifier:has-text('{val['text']}')",
                    "desc": f"Select {val['text']} for {group['name']}"
                })
    
    # Quick access
    actions.append({
        "name": "click_fluid_capacities",
        "selector": "#fluidsQuickAccess",
        "desc": "Open Fluid Capacities quick access"
    })
    
    # Use vehicle button
    actions.append({
        "name": "use_this_vehicle",
        "selector": "input[data-action='SelectComplete']",
        "desc": "Confirm vehicle selection"
    })
    
    return actions


async def navigate_with_ollama(page, goal: str, max_steps: int = 15):
    """Use Ollama to navigate the page toward a goal."""
    print(f"\n{'='*60}")
    print(f"GOAL: {goal}")
    print(f"{'='*60}\n")
    
    for step in range(max_steps):
        print(f"\n--- Step {step + 1}/{max_steps} ---")
        
        # Get current state
        state = await get_page_state(page)
        print(f"URL: {state['url']}")
        print(f"Active tab: {state.get('current_selection', {}).get('active_tab', 'N/A')}")
        
        if state.get("options_panel"):
            print("Options panel visible with groups:", 
                  [g["name"] for g in state["options_panel"]["groups"]])
        
        # Build available actions
        actions = build_available_actions(state)
        
        # Build prompt
        prompt = f"""{SYSTEM_PROMPT}

GOAL: {goal}

CURRENT STATE:
{json.dumps(state, indent=2)}

AVAILABLE ACTIONS:
{json.dumps([{"name": a["name"], "selector": a["selector"], "desc": a["desc"]} for a in actions[:20]], indent=2)}

What is your next action? Respond with ONLY a JSON object."""

        # Call Ollama
        print("Thinking...")
        try:
            response = await call_ollama(prompt)
            print(f"Model response: {response[:300]}")
            
            # Parse response - try to find JSON
            response = response.strip()
            if response.startswith("```"):
                # Remove markdown code blocks
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            
            # Find JSON object
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                decision = json.loads(json_str)
            else:
                print(f"Could not find JSON in response")
                continue
                
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON: {e}")
            continue
        except Exception as e:
            print(f"Error calling Ollama: {e}")
            continue
        
        print(f"Thought: {decision.get('thought', 'N/A')}")
        print(f"Action: {decision.get('action')} -> {decision.get('selector', 'N/A')}")
        
        # Execute action
        action = decision.get("action", "").lower()
        
        if action == "done":
            print("\n✅ Goal achieved!")
            return True
            
        elif action == "extract":
            print("\n📊 Extracting data...")
            # Could extract and return data here
            return True
            
        elif action == "wait":
            print("Waiting...")
            await asyncio.sleep(1)
            
        elif action == "click":
            selector = decision.get("selector")
            if selector:
                try:
                    print(f"Clicking: {selector}")
                    await page.click(selector, timeout=5000)
                    await asyncio.sleep(1)  # Wait for page update
                except Exception as e:
                    print(f"Click failed: {e}")
        else:
            print(f"Unknown action: {action}")
    
    print("\n⚠️ Max steps reached without completing goal")
    return False


async def main():
    print("=" * 60)
    print("  Ollama Navigator Test (gemma3:4b)")
    print("=" * 60)
    
    # First, check if Ollama is running
    print("\nChecking Ollama...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            print(f"Available models: {models}")
            if not any(MODEL in m for m in models):
                print(f"⚠️ Model {MODEL} not found. Available: {models}")
    except Exception as e:
        print(f"❌ Ollama not running: {e}")
        print("Start Ollama with: ollama serve")
        return
    
    # Connect to CDP
    print("\nConnecting to Chrome CDP on port 9222...")
    from playwright.async_api import async_playwright
    
    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.connect_over_cdp("http://localhost:9222")
    except Exception as e:
        print(f"❌ Could not connect to CDP: {e}")
        print("Start the CDP server first: python scripts/mitchell_cdp_server.py")
        return
    
    ctx = browser.contexts[0]
    page = ctx.pages[0]
    print(f"Connected! Current URL: {page.url}")
    
    # Run navigation
    goal = "Select a 2018 Ford F-150 with 5.0L engine, XLT submodel, and 4WD drive type"
    
    try:
        success = await navigate_with_ollama(page, goal)
        if success:
            print("\n🎉 Navigation successful!")
            await page.screenshot(path="/tmp/ollama_nav_result.png")
            print("Screenshot saved: /tmp/ollama_nav_result.png")
    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
