#!/usr/bin/env python3
"""Inspect the current page elements via CDP."""
import asyncio
import sys
from playwright.async_api import async_playwright

async def inspect():
    port = sys.argv[1] if len(sys.argv) > 1 else "9223"
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(f'http://localhost:{port}')
        context = browser.contexts[0]
        page = context.pages[0]
        
        print('Current URL:', page.url)
        print()
        
        # Look for Cancel buttons
        print('=== CANCEL BUTTONS ===')
        cancel_elements = await page.query_selector_all('input[value*="Cancel"], button:has-text("Cancel"), [data-action="Cancel"]')
        for i, el in enumerate(cancel_elements):
            tag = await el.evaluate('e => e.tagName')
            cls = await el.evaluate('e => e.className')
            val = await el.evaluate('e => e.value || e.textContent')
            data_action = await el.evaluate('e => e.getAttribute("data-action")')
            visible = await el.is_visible()
            print(f'{i}: <{tag}> class="{cls}" value="{val}" data-action="{data_action}" visible={visible}')
        
        print()
        print('=== LOGOUT ELEMENTS ===')
        logout_elements = await page.query_selector_all('a:has-text("Logout"), a:has-text("Log Out"), #logout, [href*="logout"]')
        for i, el in enumerate(logout_elements):
            tag = await el.evaluate('e => e.tagName')
            href = await el.evaluate('e => e.href || ""')
            text = await el.evaluate('e => e.textContent.trim()')
            el_id = await el.evaluate('e => e.id')
            visible = await el.is_visible()
            print(f'{i}: <{tag}> id="{el_id}" href="{href}" text="{text}" visible={visible}')
        
        print()
        print('=== USE THIS VEHICLE BUTTON ===')
        utv_elements = await page.query_selector_all('input[value*="Use This Vehicle"], button:has-text("Use This Vehicle")')
        for i, el in enumerate(utv_elements):
            tag = await el.evaluate('e => e.tagName')
            cls = await el.evaluate('e => e.className')
            val = await el.evaluate('e => e.value || e.textContent')
            visible = await el.is_visible()
            print(f'{i}: <{tag}> class="{cls}" value="{val}" visible={visible}')

asyncio.run(inspect())
