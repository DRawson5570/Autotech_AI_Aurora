#!/usr/bin/env python3
"""
Test script for unified navigator.

Usage:
    # Start Chrome first:
    google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-test
    
    # Then run:
    python -m scripts.test_unified_navigator "oil capacity for 2018 Ford F-150 5.0L"
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright


async def test_unified(goal: str):
    """Test the unified navigator with a goal."""
    
    print(f"Goal: {goal}")
    print("=" * 60)
    
    # Import here to avoid circular imports
    from addons.mitchell_agent.ai_navigator.unified_navigator import (
        UnifiedNavigator,
        query_unified,
    )
    from addons.mitchell_agent.agent.config import load_config
    
    # Load config for credentials
    config = load_config()
    
    # Connect to Chrome
    print("Connecting to Chrome on port 9222...")
    playwright = await async_playwright().start()
    
    try:
        browser = await playwright.chromium.connect_over_cdp("http://localhost:9222")
    except Exception as e:
        print(f"ERROR: Could not connect to Chrome. Make sure it's running with:")
        print(f"  google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-test")
        print(f"\nError: {e}")
        await playwright.stop()
        return
    
    # Get or create page
    contexts = browser.contexts
    if contexts:
        context = contexts[0]
    else:
        context = await browser.new_context()
    
    pages = context.pages
    if pages:
        page = pages[0]
    else:
        page = await context.new_page()
    
    # Navigate to ShopKeyPro
    print("Navigating to ShopKeyPro...")
    await page.goto("https://www1.shopkeypro.com/Main/Index", wait_until="domcontentloaded")
    await asyncio.sleep(2)
    
    print(f"Current URL: {page.url}")
    print("=" * 60)
    
    # Try to parse vehicle from goal
    # Simple pattern: "... for YEAR MAKE MODEL ENGINE"
    import re
    vehicle = {}
    year_match = re.search(r'\b(19|20)\d{2}\b', goal)
    if year_match:
        vehicle['year'] = year_match.group()
    
    # Common makes
    makes = ['Ford', 'Chevy', 'Chevrolet', 'Toyota', 'Honda', 'Nissan', 'Dodge', 'Ram', 'GMC', 'BMW', 'Mercedes', 'Audi']
    for make in makes:
        if make.lower() in goal.lower():
            vehicle['make'] = make
            break
    
    print(f"Parsed vehicle: {vehicle}")
    print("=" * 60)
    
    # Run unified navigator
    print("Starting unified navigation...")
    
    result = await query_unified(
        page=page,
        goal=goal,
        vehicle=vehicle if vehicle else None,
        credentials={
            "username": config.mitchell_username,
            "password": config.mitchell_password,
        },
    )
    
    print("=" * 60)
    print("RESULT:")
    print(f"  Success: {result['success']}")
    print(f"  Steps: {result['steps_taken']}")
    print(f"  Tokens: {result['tokens_used']}")
    
    if result['success']:
        print(f"\nDATA:\n{result['data']}")
        if result['images']:
            print(f"\nIMAGES: {len(result['images'])} captured")
        if result['auto_selected']:
            print(f"\nAuto-selected: {result['auto_selected']}")
    else:
        print(f"\nERROR: {result['error']}")
    
    # Cleanup
    print("\n" + "=" * 60)
    print("Test complete. Browser left open for inspection.")
    await playwright.stop()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.test_unified_navigator 'your goal here'")
        print("Example: python -m scripts.test_unified_navigator 'oil capacity for 2018 Ford F-150 5.0L'")
        sys.exit(1)
    
    goal = " ".join(sys.argv[1:])
    asyncio.run(test_unified(goal))
