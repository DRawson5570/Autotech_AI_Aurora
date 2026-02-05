#!/usr/bin/env python3
"""
Test AI-Driven Navigation
===========================

Interactive test script for the AI navigation system.
Tests element extraction, AI decision making, and navigation.

Usage:
    # Activate conda env first
    conda activate open-webui
    
    # Run test
    cd /home/drawson/autotech_ai
    python -m addons.mitchell_agent.test_ai_navigator

Requirements:
    - GEMINI_API_KEY set in environment or .env
    - Chrome running with CDP on port 9222, logged into ShopKeyPro
    - Or: MITCHELL_USERNAME/PASSWORD to auto-login
"""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("test_ai_nav")

# Reduce noise from httpx
logging.getLogger("httpx").setLevel(logging.WARNING)


async def test_element_extraction(page):
    """Test element extraction from current page."""
    from addons.mitchell_agent.ai_navigator import get_page_state, get_visible_text
    
    log.info("=" * 60)
    log.info("TEST: Element Extraction")
    log.info("=" * 60)
    
    # Get page state
    state = await get_page_state(page)
    
    log.info(f"URL: {state.url}")
    log.info(f"Title: {state.title}")
    log.info(f"Has Modal: {state.has_modal}")
    log.info(f"Total Elements: {len(state.elements)}")
    
    # Show element summary
    visible = [e for e in state.elements if e.visible]
    disabled = [e for e in state.elements if e.disabled]
    in_modal = [e for e in state.elements if e.in_modal]
    
    log.info(f"Visible: {len(visible)}, Disabled: {len(disabled)}, In Modal: {len(in_modal)}")
    
    # Show first 20 elements
    log.info("\nFirst 20 interactive elements:")
    for elem in state.elements[:20]:
        text = elem.text[:40] if elem.text else elem.aria_label or elem.element_id or "no-text"
        log.info(f"  [{elem.id}] {elem.tag.upper():8} {text}")
    
    # Get visible text
    text = await get_visible_text(page)
    log.info(f"\nPage text length: {len(text)} chars")
    log.info(f"Preview: {text[:200]}...")
    
    # Show LLM context format
    log.info("\n--- LLM Context Preview ---")
    llm_context = state.to_llm_context(max_elements=30)
    log.info(llm_context[:2000])
    
    return state


async def test_ai_decision(page, goal: str, vehicle: dict):
    """Test AI decision making for a single step."""
    from addons.mitchell_agent.ai_navigator import (
        get_page_state, get_visible_text, AINavigator
    )
    
    log.info("=" * 60)
    log.info("TEST: AI Decision Making")
    log.info("=" * 60)
    log.info(f"Goal: {goal}")
    log.info(f"Vehicle: {vehicle}")
    
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        log.error("GEMINI_API_KEY not set!")
        return None
    
    # Get page state
    state = await get_page_state(page)
    text = await get_visible_text(page)
    
    # Create AI navigator
    ai = AINavigator(api_key=api_key)
    
    # Get decision
    log.info("Asking Gemini for next action...")
    action = await ai.decide_action(
        page_state=state,
        page_text=text,
        goal=goal,
        vehicle=vehicle,
        history=[],
    )
    
    log.info(f"AI Decision: {action.action_type.value}")
    log.info(f"Selector: {action.selector}")
    log.info(f"Element ID: {action.element_id}")
    log.info(f"Reason: {action.reason}")
    
    if action.text:
        log.info(f"Data/Text: {action.text[:200]}...")
    
    return action


async def test_full_navigation(page, goal: str, vehicle: dict, max_steps: int = 10):
    """Test full AI navigation loop."""
    from addons.mitchell_agent.ai_navigator import NavigationLoop
    
    log.info("=" * 60)
    log.info("TEST: Full Navigation Loop")
    log.info("=" * 60)
    log.info(f"Goal: {goal}")
    log.info(f"Vehicle: {vehicle}")
    log.info(f"Max Steps: {max_steps}")
    
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        log.error("GEMINI_API_KEY not set!")
        return None
    
    # Create navigation loop
    loop = NavigationLoop(
        page=page,
        api_key=api_key,
        max_steps=max_steps,
        save_screenshots=True,
    )
    
    # Run navigation
    log.info("Starting navigation...")
    result = await loop.navigate(goal=goal, vehicle=vehicle)
    
    log.info("=" * 60)
    log.info("RESULT")
    log.info("=" * 60)
    log.info(f"Success: {result.success}")
    log.info(f"Steps Taken: {result.steps_taken}")
    log.info(f"Message: {result.message}")
    
    if result.data:
        log.info(f"Data:\n{result.data[:1000]}...")
    
    log.info("\nHistory:")
    for h in result.history:
        log.info(f"  {h}")
    
    log.info(f"\nScreenshots saved to: /tmp/ai_navigator_screenshots/")
    
    return result


async def connect_to_chrome(cdp_port: int = 9222):
    """Connect to existing Chrome instance via CDP."""
    pw = await async_playwright().start()
    
    try:
        browser = await pw.chromium.connect_over_cdp(f"http://localhost:{cdp_port}")
        log.info(f"Connected to Chrome on port {cdp_port}")
        
        contexts = browser.contexts
        if not contexts:
            log.error("No browser contexts found")
            return None, None, pw
        
        context = contexts[0]
        pages = context.pages
        if not pages:
            log.error("No pages found")
            return None, None, pw
        
        page = pages[0]
        log.info(f"Using page: {await page.title()}")
        
        return browser, page, pw
        
    except Exception as e:
        log.error(f"Could not connect to Chrome: {e}")
        log.error("Make sure Chrome is running with: google-chrome --remote-debugging-port=9222")
        return None, None, pw


async def main():
    """Main test runner."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║         AI-Driven Navigation Test Suite                       ║
║                                                              ║
║  This tests the AI navigation system that replaces          ║
║  hardcoded navigation paths with LLM reasoning.             ║
║                                                              ║
║  Requirements:                                               ║
║  - Chrome running with --remote-debugging-port=9222         ║
║  - Logged into ShopKeyPro with a vehicle selected           ║
║  - GEMINI_API_KEY set                                        ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # Check API key
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set!")
        print("Set it in your .env file or environment")
        sys.exit(1)
    
    print(f"API Key: {api_key[:10]}...{api_key[-4:]}")
    
    # Connect to Chrome
    browser, page, pw = await connect_to_chrome()
    if not page:
        print("\nTo start Chrome with CDP:")
        print("  google-chrome --remote-debugging-port=9222")
        await pw.stop()
        sys.exit(1)
    
    try:
        # Menu
        while True:
            print("\n" + "=" * 50)
            print("Test Menu:")
            print("  1. Test Element Extraction")
            print("  2. Test Single AI Decision")
            print("  3. Test Full Navigation (Fluid Capacities)")
            print("  4. Test Full Navigation (Custom Goal)")
            print("  5. Show Current Page State")
            print("  q. Quit")
            print("=" * 50)
            
            choice = input("Choice: ").strip().lower()
            
            if choice == 'q':
                break
            
            elif choice == '1':
                await test_element_extraction(page)
            
            elif choice == '2':
                goal = input("Goal (e.g., 'Find fluid capacities'): ").strip()
                goal = goal or "Find fluid capacities"
                
                vehicle = {
                    "year": input("Year (2020): ").strip() or "2020",
                    "make": input("Make (Toyota): ").strip() or "Toyota",
                    "model": input("Model (Camry): ").strip() or "Camry",
                    "engine": input("Engine (2.5L): ").strip() or "2.5L",
                }
                
                await test_ai_decision(page, goal, vehicle)
            
            elif choice == '3':
                vehicle = {
                    "year": input("Year (2020): ").strip() or "2020",
                    "make": input("Make (Toyota): ").strip() or "Toyota",
                    "model": input("Model (Camry): ").strip() or "Camry",
                    "engine": input("Engine (2.5L): ").strip() or "2.5L",
                }
                
                await test_full_navigation(
                    page,
                    goal="Find fluid capacities and specifications (oil, coolant, transmission)",
                    vehicle=vehicle,
                    max_steps=15,
                )
            
            elif choice == '4':
                goal = input("Goal: ").strip()
                if not goal:
                    print("Goal required!")
                    continue
                
                vehicle = {
                    "year": input("Year (2020): ").strip() or "2020",
                    "make": input("Make (Toyota): ").strip() or "Toyota",
                    "model": input("Model (Camry): ").strip() or "Camry",
                    "engine": input("Engine (2.5L): ").strip() or "2.5L",
                }
                
                max_steps = int(input("Max steps (15): ").strip() or "15")
                
                await test_full_navigation(page, goal, vehicle, max_steps)
            
            elif choice == '5':
                state = await test_element_extraction(page)
                
                # Save full state to file
                state_file = Path("/tmp/page_state.json")
                with open(state_file, "w") as f:
                    json.dump(state.to_dict(), f, indent=2)
                print(f"\nFull state saved to: {state_file}")
            
            else:
                print("Invalid choice")
    
    finally:
        await pw.stop()
        print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
