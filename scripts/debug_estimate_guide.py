#!/usr/bin/env python3
"""
Debug script to thoroughly inspect the Estimate Guide page structure.
Run with Chrome already open at landing page.
"""

import asyncio
import sys
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        except Exception as e:
            print(f"ERROR: Cannot connect to Chrome at 127.0.0.1:9222")
            print(f"Make sure Chrome is running with: google-chrome --remote-debugging-port=9222")
            return
        
        page = browser.contexts[0].pages[0]
        print(f"Current URL: {page.url}")
        
        # Step 1: Click Estimate Guide
        print("\n=== STEP 1: Click Estimate Guide ===")
        await page.wait_for_load_state('networkidle')
        eg = page.locator('#estimateGuideAccess, a:has-text("Estimate Guide")')
        if await eg.count() > 0:
            await eg.first.click()
            await page.wait_for_timeout(2000)
            await page.wait_for_load_state('networkidle')
            print("Clicked Estimate Guide")
        else:
            print("ERROR: Could not find Estimate Guide")
            return
        
        # Step 2: Click Electrical
        print("\n=== STEP 2: Click Electrical ===")
        await page.wait_for_load_state('networkidle')
        elec = page.locator('a:text-is("Electrical"), div:text-is("Electrical")')
        if await elec.count() > 0:
            await elec.first.click()
            await page.wait_for_timeout(1500)
            await page.wait_for_load_state('networkidle')
            print("Clicked Electrical")
        else:
            print("ERROR: Could not find Electrical")
            return
        
        # Step 3: Click Charging System
        print("\n=== STEP 3: Click Charging System ===")
        await page.wait_for_load_state('networkidle')
        cs = page.locator('a:text-is("Charging System"), div:text-is("Charging System")')
        if await cs.count() > 0:
            await cs.first.click()
            await page.wait_for_timeout(1500)
            await page.wait_for_load_state('networkidle')
            print("Clicked Charging System")
        else:
            print("ERROR: Could not find Charging System")
            return
        
        # Now inspect the page structure
        print("\n" + "="*60)
        print("INSPECTING PAGE AFTER CHARGING SYSTEM CLICK")
        print("="*60)
        
        # Check rightPane
        print("\n--- .rightPane contents ---")
        right_pane = await page.query_selector('.rightPane')
        if right_pane:
            rp_html = await right_pane.inner_html()
            print(f"rightPane HTML length: {len(rp_html)} chars")
            rp_text = await right_pane.inner_text()
            print(f"rightPane text:\n{rp_text[:2000]}")
        else:
            print("NO .rightPane found!")
        
        # Check for div.view elements
        print("\n--- All div.view elements ---")
        views = await page.query_selector_all('div.view')
        print(f"Found {len(views)} div.view elements")
        for i, v in enumerate(views[:20]):
            text = await v.inner_text()
            text_clean = ' '.join(text.split())[:80]
            classes = await v.get_attribute('class')
            print(f"  [{i}] class='{classes}' text='{text_clean}'")
        
        # Check for .rightPane div.view elements specifically
        print("\n--- .rightPane div.view elements ---")
        rp_views = await page.query_selector_all('.rightPane div.view')
        print(f"Found {len(rp_views)} .rightPane div.view elements")
        for i, v in enumerate(rp_views[:20]):
            text = await v.inner_text()
            text_clean = ' '.join(text.split())[:80]
            print(f"  [{i}] '{text_clean}'")
        
        # Check for items with ALTERNATOR in text
        print("\n--- Elements containing 'ALTERNATOR' ---")
        alt_els = await page.query_selector_all('*:has-text("ALTERNATOR")')
        print(f"Found {len(alt_els)} elements with ALTERNATOR")
        for i, el in enumerate(alt_els[:15]):
            tag = await el.evaluate('el => el.tagName')
            classes = await el.get_attribute('class') or ''
            text = await el.inner_text()
            text_clean = ' '.join(text.split())[:60]
            print(f"  [{i}] <{tag}> class='{classes[:40]}' text='{text_clean}'")
        
        # Try exact text match for ALTERNATOR ASSEMBLY - Remove & Replace
        print("\n--- Testing locators for 'ALTERNATOR ASSEMBLY - Remove & Replace' ---")
        test_text = "ALTERNATOR ASSEMBLY - Remove & Replace"
        
        locators_to_test = [
            (f'div:text-is("{test_text}")', 'div:text-is'),
            (f'.rightPane div.view:text-is("{test_text}")', '.rightPane div.view:text-is'),
            (f'*:text-is("{test_text}")', '*:text-is'),
            (f'text="{test_text}"', 'text='),
            (f':has-text("{test_text}")', ':has-text'),
            (f'.rightPane :has-text("{test_text}")', '.rightPane :has-text'),
        ]
        
        for selector, name in locators_to_test:
            try:
                loc = page.locator(selector)
                count = await loc.count()
                if count > 0:
                    first_text = await loc.first.inner_text()
                    first_text_clean = ' '.join(first_text.split())[:60]
                    print(f"  {name}: {count} matches, first='{first_text_clean}'")
                else:
                    print(f"  {name}: 0 matches")
            except Exception as e:
                print(f"  {name}: ERROR - {e}")
        
        # Check what the itemsContainer looks like
        print("\n--- .itemsContainer structure ---")
        items_container = await page.query_selector('.itemsContainer')
        if items_container:
            ic_html = await items_container.inner_html()
            print(f"itemsContainer HTML (first 3000 chars):\n{ic_html[:3000]}")
        else:
            print("NO .itemsContainer found")
        
        # Check for specific operation text patterns
        print("\n--- Looking for operation patterns ---")
        ops = ['ALTERNATOR', 'BATTERY', 'GENERATOR', 'Remove & Replace']
        for op in ops:
            els = await page.query_selector_all(f'*:text("{op}")')
            print(f"  '{op}': {len(els)} matches")
        
        # Screenshot
        print("\n--- Taking screenshot ---")
        await page.screenshot(path='/tmp/estimate_guide_debug.png')
        print("Screenshot saved to /tmp/estimate_guide_debug.png")
        
        # Go back to landing
        print("\n=== Returning to landing page ===")
        onesearch = page.locator('#oneSearchPlusAccess, a:has-text("1SEARCH")')
        if await onesearch.count() > 0:
            await onesearch.first.click()
            await page.wait_for_timeout(1000)
            print("Clicked 1SEARCH to return")


if __name__ == "__main__":
    asyncio.run(main())
