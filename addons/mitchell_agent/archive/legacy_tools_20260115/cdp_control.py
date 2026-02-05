#!/usr/bin/env python3
"""
CDP Control - Interactive browser control via Chrome DevTools Protocol.

Usage:
    python -m addons.mitchell_agent.tools.cdp_control save          # Save page HTML
    python -m addons.mitchell_agent.tools.cdp_control click "selector"
    python -m addons.mitchell_agent.tools.cdp_control click_text "selector" "text"  # Click element with text
    python -m addons.mitchell_agent.tools.cdp_control type "selector" "text"
    python -m addons.mitchell_agent.tools.cdp_control goto "url"
    python -m addons.mitchell_agent.tools.cdp_control eval "js_expression"
    python -m addons.mitchell_agent.tools.cdp_control wait 2000     # Wait ms
    python -m addons.mitchell_agent.tools.cdp_control screenshot    # Save screenshot
"""

import asyncio
import sys
import json
from pathlib import Path
from playwright.async_api import async_playwright

CDP_URL = "http://localhost:9222"
OUTPUT_DIR = Path(__file__).parent.parent / "mappings" / "live"


async def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    cmd = sys.argv[1]
    args = sys.argv[2:]
    
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(CDP_URL)
        except Exception as e:
            print(f"Failed to connect to CDP at {CDP_URL}: {e}")
            print("Make sure Chrome is running with --remote-debugging-port=9222")
            sys.exit(1)
        
        # Get the first page
        contexts = browser.contexts
        if not contexts:
            print("No browser contexts found")
            sys.exit(1)
        
        pages = contexts[0].pages
        if not pages:
            print("No pages found")
            sys.exit(1)
        
        page = pages[0]
        print(f"Connected to: {page.url}")
        print(f"Title: {await page.title()}")
        
        if cmd == "save":
            # Save HTML and basic info
            html = await page.content()
            html_file = OUTPUT_DIR / "current_page.html"
            html_file.write_text(html)
            print(f"Saved HTML to {html_file} ({len(html)} bytes)")
            
            # Also save page info
            info = {
                "url": page.url,
                "title": await page.title(),
                "timestamp": str(asyncio.get_event_loop().time()),
            }
            info_file = OUTPUT_DIR / "page_info.json"
            info_file.write_text(json.dumps(info, indent=2))
            print(f"Saved info to {info_file}")
            
        elif cmd == "screenshot":
            screenshot_file = OUTPUT_DIR / "screenshot.png"
            await page.screenshot(path=str(screenshot_file), full_page=True)
            print(f"Saved screenshot to {screenshot_file}")
            
        elif cmd == "click":
            if not args:
                print("Usage: click 'selector'")
                sys.exit(1)
            selector = args[0]
            print(f"Clicking: {selector}")
            await page.click(selector, timeout=10000)
            print("Click successful")
            await asyncio.sleep(0.5)  # Let page settle
            
        elif cmd == "click_text":
            if len(args) < 2:
                print("Usage: click_text 'selector' 'text'")
                sys.exit(1)
            selector, text = args[0], args[1]
            print(f"Clicking: {selector} containing '{text}'")
            # Find element with matching text
            locator = page.locator(selector).filter(has_text=text).first
            await locator.click(timeout=10000)
            print("Click successful")
            await asyncio.sleep(0.5)
            
        elif cmd == "type":
            if len(args) < 2:
                print("Usage: type 'selector' 'text'")
                sys.exit(1)
            selector, text = args[0], args[1]
            print(f"Typing into: {selector}")
            await page.fill(selector, text, timeout=10000)
            print("Type successful")
            
        elif cmd == "goto":
            if not args:
                print("Usage: goto 'url'")
                sys.exit(1)
            url = args[0]
            print(f"Navigating to: {url}")
            await page.goto(url, timeout=30000)
            print(f"Now at: {page.url}")
            
        elif cmd == "eval":
            if not args:
                print("Usage: eval 'js_expression'")
                sys.exit(1)
            expr = args[0]
            result = await page.evaluate(expr)
            print(f"Result: {json.dumps(result, indent=2, default=str)}")
            
        elif cmd == "wait":
            ms = int(args[0]) if args else 1000
            print(f"Waiting {ms}ms...")
            await asyncio.sleep(ms / 1000)
            print("Done")
            
        elif cmd == "info":
            # Print current page state
            print(f"URL: {page.url}")
            print(f"Title: {await page.title()}")
            
        elif cmd == "find":
            # Find elements matching selector and print their text
            if not args:
                print("Usage: find 'selector'")
                sys.exit(1)
            selector = args[0]
            elements = await page.locator(selector).all()
            print(f"Found {len(elements)} elements matching '{selector}':")
            for i, el in enumerate(elements[:20]):  # Limit to 20
                try:
                    text = await el.inner_text()
                    text = text.strip()[:80]  # Truncate
                    tag = await el.evaluate("el => el.tagName")
                    classes = await el.evaluate("el => el.className")
                    print(f"  [{i}] <{tag.lower()} class='{classes}'> {text}")
                except:
                    print(f"  [{i}] (could not get text)")
                    
        else:
            print(f"Unknown command: {cmd}")
            print(__doc__)
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
