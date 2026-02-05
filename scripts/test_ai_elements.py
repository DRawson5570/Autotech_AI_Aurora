#!/usr/bin/env python3
"""Test what elements the AI sees on the Charging System page."""

import asyncio
import sys
sys.path.insert(0, '/home/drawson/autotech_ai/addons/mitchell_agent')

from playwright.async_api import async_playwright
from ai_navigator.element_extractor import get_page_state


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = browser.contexts[0].pages[0]
        await page.wait_for_load_state('networkidle')
        
        print(f"Current URL: {page.url[:80]}")
        
        # Navigate to operations list - try multiple approaches
        print("\n--- Clicking Estimate Guide ---")
        eg = page.locator('text="Estimate Guide"')
        if await eg.count() > 0:
            await eg.first.click(timeout=5000)
            await page.wait_for_timeout(2000)
            print("Clicked Estimate Guide")
        else:
            print("ERROR: Could not find Estimate Guide")
            return
        
        print("\n--- Clicking Electrical ---")
        await page.wait_for_load_state('networkidle')
        elec = page.locator('text="Electrical"')
        if await elec.count() > 0:
            # Use force=True to bypass potential overlays
            await elec.first.click(timeout=5000, force=True)
            await page.wait_for_timeout(1500)
            print("Clicked Electrical")
        else:
            print("ERROR: Could not find Electrical")
            return
        
        print("\n--- Clicking Charging System ---")
        cs = page.locator('text="Charging System"')
        if await cs.count() > 0:
            await cs.first.click(timeout=5000, force=True)
            await page.wait_for_timeout(1500)
            print("Clicked Charging System")
        else:
            print("ERROR: Could not find Charging System")
            return
        
        print('=== Extracting page state (what AI sees) ===')
        state = await get_page_state(page)
        
        print(f'Elements count: {len(state.elements)}')
        print()
        print('All Elements:')
        for el in state.elements:
            text = el.text[:60] if el.text else "(no text)"
            print(f'  [{el.id}] <{el.tag}> {text}')
        
        print()
        print('=== Does AI see ALTERNATOR in elements? ===')
        alt_els = [e for e in state.elements if e.text and 'ALTERNATOR' in e.text.upper()]
        if alt_els:
            for el in alt_els:
                print(f'  YES: [{el.id}] <{el.tag}> {el.text}')
        else:
            print('  NO - ALTERNATOR not in clickable elements')
            print()
            print('=== Headings (from page state) ===')
            print(state.headings[:10] if state.headings else 'No headings')
        
        # Return to landing
        print("\n--- Returning to landing ---")
        onesearch = page.locator('text="1SEARCH"')
        if await onesearch.count() > 0:
            await onesearch.first.click()
            await page.wait_for_timeout(1000)
            print('Returned to landing')
        else:
            print("Could not find 1SEARCH, trying Home")
            home = page.locator('text="HOME"')
            if await home.count() > 0:
                await home.first.click()


if __name__ == "__main__":
    asyncio.run(main())
