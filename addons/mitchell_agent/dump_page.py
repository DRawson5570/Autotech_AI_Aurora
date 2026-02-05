#!/usr/bin/env python3
import asyncio
from playwright.async_api import async_playwright

async def dump_html():
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp("http://localhost:9223")
    ctx = browser.contexts[0]
    page = ctx.pages[0]
    
    links = await page.evaluate("""
        () => {
            const links = document.querySelectorAll("a");
            return Array.from(links).map(a => ({
                text: a.textContent?.trim().substring(0, 80),
                className: a.className
            })).filter(l => l.text);
        }
    """)
    
    print("=== ALL LINKS ===")
    for i, link in enumerate(links[:40]):
        t = link["text"]
        c = link["className"]
        print(f'{i}: "{t}" class="{c}"')
    
    # Click SYSTEM WIRING DIAGRAMS
    print("\n=== CLICKING SYSTEM WIRING DIAGRAMS ===")
    try:
        await page.click('a:has-text("SYSTEM WIRING DIAGRAMS")', timeout=5000)
        print("Clicked!")
        await asyncio.sleep(2)
        
        # Now get new links
        links2 = await page.evaluate("""
            () => {
                const links = document.querySelectorAll("a");
                return Array.from(links).map(a => ({
                    text: a.textContent?.trim().substring(0, 80),
                    className: a.className
                })).filter(l => l.text);
            }
        """)
        print("\n=== LINKS AFTER CLICK ===")
        for i, link in enumerate(links2[:40]):
            t = link["text"]
            c = link["className"]
            print(f'{i}: "{t}" class="{c}"')
    except Exception as e:
        print(f"Error: {e}")
    
    await pw.stop()

asyncio.run(dump_html())
