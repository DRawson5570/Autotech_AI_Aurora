#!/usr/bin/env python3
"""
Test what elements the AI sees on the Charging System operations page.
Uses JavaScript clicks to bypass overlay issues.
"""

import asyncio
import sys
sys.path.insert(0, '/home/drawson/autotech_ai/addons/mitchell_agent')

from playwright.async_api import async_playwright
from ai_navigator.element_extractor import get_page_state


async def js_click(page, selector_or_text, timeout=5000):
    """Click element using JavaScript evaluation to bypass overlay issues."""
    # Try by text first
    result = await page.evaluate(f'''(text) => {{
        // Find by exact text
        const els = [...document.querySelectorAll('a, button, li, div, h2, span')];
        for (const el of els) {{
            if (el.textContent?.trim() === text) {{
                el.click();
                return 'clicked';
            }}
        }}
        // Try partial match
        for (const el of els) {{
            if (el.textContent?.includes(text)) {{
                el.click();
                return 'clicked partial';
            }}
        }}
        return 'not found';
    }}''', selector_or_text)
    return result


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = browser.contexts[0].pages[0]
        await page.wait_for_load_state('networkidle')
        
        print(f"Current URL: {page.url[:60]}")
        
        # Navigate using JS clicks
        print("\n--- Clicking Estimate Guide ---")
        result = await js_click(page, "Estimate Guide")
        print(f"Result: {result}")
        await page.wait_for_timeout(2000)
        
        print("\n--- Clicking Electrical ---")
        result = await js_click(page, "Electrical")
        print(f"Result: {result}")
        await page.wait_for_timeout(1500)
        
        print("\n--- Clicking Charging System ---")
        result = await js_click(page, "Charging System")
        print(f"Result: {result}")
        await page.wait_for_timeout(1500)
        
        # Now extract page state
        print('\n=== Extracting page state (what AI sees) ===')
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
        
        # Check what H2s are on the page
        print()
        print('=== All H2 elements on page ===')
        h2s = await page.query_selector_all('h2')
        for h2 in h2s[:15]:
            text = await h2.inner_text()
            print(f'  <h2> {text[:60]}')
        
        # Return to landing
        print("\n--- Returning to landing ---")
        await page.evaluate('() => { document.querySelector("a[href*=OneView]")?.click(); }')
        await page.wait_for_timeout(1000)
        print('Done')


if __name__ == "__main__":
    asyncio.run(main())
