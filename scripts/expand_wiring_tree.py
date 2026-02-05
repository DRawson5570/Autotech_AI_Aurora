#!/usr/bin/env python3
"""
CDP inspector - expand each category and capture diagram names.
Run this while you have the SYSTEM WIRING DIAGRAMS view open.
"""

import asyncio
import json
from playwright.async_api import async_playwright


async def expand_and_capture():
    """Connect to Chrome via CDP and expand each category to capture diagrams."""
    
    print("Connecting to Chrome on port 9222...")
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        
        contexts = browser.contexts
        if not contexts:
            print("ERROR: No browser contexts found")
            return
        
        page = contexts[0].pages[0]
        print(f"Connected to page: {page.url[:60]}...")
        
        full_tree = {}
        
        # Get all top-level categories
        categories = await page.query_selector_all(".modalDialogView ul.tree > li.node")
        print(f"\nFound {len(categories)} categories to process\n")
        
        for i, cat in enumerate(categories):
            # Get category name
            label = await cat.query_selector("span.label")
            if label:
                cat_name = (await label.inner_text()).strip()
            else:
                continue
            
            # Skip the "USING MITCHELL1'S..." intro item
            if "USING MITCHELL" in cat_name:
                print(f"[{i+1}] {cat_name} (skipping)")
                continue
            
            print(f"[{i+1}] {cat_name}")
            
            # Check if already expanded (has visible children)
            children = await cat.query_selector_all(":scope > ul > li.node")
            
            if not children:
                # Try to expand by clicking the expand icon
                expand_icon = await cat.query_selector(".treeExpandCollapseIcon")
                if expand_icon:
                    try:
                        await expand_icon.click()
                        await page.wait_for_timeout(300)
                        children = await cat.query_selector_all(":scope > ul > li.node")
                    except Exception as e:
                        print(f"    Could not expand: {e}")
            
            # Capture children (diagram names)
            diagrams = []
            if children:
                for child in children:
                    child_label = await child.query_selector("span.label")
                    if child_label:
                        diag_name = (await child_label.inner_text()).strip()
                        diagrams.append(diag_name)
                        print(f"    - {diag_name}")
            else:
                print(f"    (no sub-items or leaf node)")
            
            full_tree[cat_name] = diagrams
        
        # Output
        print("\n" + "="*60)
        print("COMPLETE WIRING DIAGRAM TREE")
        print("="*60 + "\n")
        print(json.dumps(full_tree, indent=2))
        
        # Save
        with open("/tmp/wiring_full_tree.json", "w") as f:
            json.dump(full_tree, f, indent=2)
        print("\nSaved to: /tmp/wiring_full_tree.json")
        
        # Take final screenshot
        await page.screenshot(path="/tmp/wiring_expanded.png")
        print("Screenshot: /tmp/wiring_expanded.png")


if __name__ == "__main__":
    asyncio.run(expand_and_capture())
