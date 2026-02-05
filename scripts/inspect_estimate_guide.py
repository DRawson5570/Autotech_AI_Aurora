#!/usr/bin/env python3
"""Inspect the Estimate Guide page structure."""
import asyncio
from playwright.async_api import async_playwright

async def inspect_structure():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://localhost:9222')
        contexts = browser.contexts
        page = contexts[0].pages[0]
        
        # Get detailed structure of the partsAndLaborNavigatorContainer
        result = await page.evaluate('''() => {
            const container = document.querySelector(".partsAndLaborNavigatorContainer");
            if (!container) return {found: false};
            
            // Get all interactive elements
            const interactive = container.querySelectorAll("a, button, input, [onclick], .clickable, li.item, .row");
            const elements = [];
            
            interactive.forEach((el, i) => {
                if (i > 40) return;  // Limit
                const text = el.textContent?.trim().slice(0, 80) || '';
                const cls = el.className?.toString() || '';
                const tag = el.tagName;
                const href = el.href || '';
                
                elements.push({
                    tag,
                    cls: cls.slice(0, 60),
                    text: text.slice(0, 60),
                    href: href ? 'has href' : ''
                });
            });
            
            // Also get the page text from this container
            const pageText = container.innerText?.slice(0, 2000) || '';
            
            return {
                found: true,
                elementCount: interactive.length,
                elements,
                pageText
            };
        }''')
        
        print(f'Found partsAndLaborNavigatorContainer: {result.get("found")}')
        print(f'Interactive elements: {result.get("elementCount")}')
        
        print('\n=== INTERACTIVE ELEMENTS ===')
        for el in result.get('elements', []):
            print(f'{el["tag"]} class="{el["cls"][:40]}" text="{el["text"]}" {el["href"]}')
        
        print('\n=== PAGE TEXT FROM CONTAINER ===')
        print(result.get('pageText', '')[:1500])

asyncio.run(inspect_structure())
