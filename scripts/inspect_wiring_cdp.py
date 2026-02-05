#!/usr/bin/env python3
"""
CDP inspector for wiring diagram tree structure.
Run this while you have the wiring diagrams modal open in Chrome.
"""

import asyncio
import json
from playwright.async_api import async_playwright


async def inspect_wiring_tree():
    """Connect to Chrome via CDP and inspect the wiring diagram tree."""
    
    print("Connecting to Chrome on port 9222...")
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        
        # Get the first context and page
        contexts = browser.contexts
        if not contexts:
            print("ERROR: No browser contexts found")
            return
        
        pages = contexts[0].pages
        if not pages:
            print("ERROR: No pages found")
            return
        
        page = pages[0]
        print(f"Connected to page: {page.url[:60]}...")
        
        # Take screenshot first
        await page.screenshot(path="/tmp/wiring_cdp_inspect.png")
        print("Screenshot: /tmp/wiring_cdp_inspect.png")
        
        tree_structure = {}
        
        # Check for modal dialog
        modal = await page.query_selector(".modalDialogView")
        if modal:
            print("\n✓ Modal dialog found")
            modal_visible = await modal.is_visible()
            print(f"  Visible: {modal_visible}")
        else:
            print("\n✗ No modal dialog found - make sure wiring diagrams is open")
            return
        
        # Look for tree structure in modal
        print("\n=== TREE STRUCTURE ===\n")
        
        # Try different tree selectors
        selectors_to_try = [
            ".modalDialogView ul.tree > li.node",
            ".modalDialogView ul.usercontrol.tree > li",
            ".modalDialogView li.node",
            ".modalDialogView li.usercontrol.node",
            ".modalDialogView .treeview li",
            ".modalDialogView ul > li",
        ]
        
        for selector in selectors_to_try:
            items = await page.query_selector_all(selector)
            if items:
                print(f"Selector '{selector}' found {len(items)} items")
                break
        else:
            print("No tree items found with standard selectors")
            # Let's dump the modal HTML structure
            print("\n=== MODAL HTML STRUCTURE ===\n")
            modal_html = await modal.inner_html()
            # Just show first 3000 chars
            print(modal_html[:3000])
            if len(modal_html) > 3000:
                print(f"\n... ({len(modal_html)} total chars)")
            return
        
        # Now extract the tree
        print(f"\nExtracting {len(items)} top-level items...\n")
        
        for i, item in enumerate(items):
            # Get the label
            label = await item.query_selector("span.label")
            if not label:
                label = await item.query_selector(".label")
            if not label:
                # Try getting direct text
                text = await item.inner_text()
                text = text.split('\n')[0].strip()[:50]
            else:
                text = await label.inner_text()
                text = text.strip()
            
            print(f"[{i+1}] {text}")
            tree_structure[text] = {"subcategories": []}
            
            # Check for children (already expanded or expandable)
            children = await item.query_selector_all(":scope > ul > li")
            if children:
                print(f"    └── {len(children)} children:")
                for child in children[:10]:  # Limit to first 10
                    child_label = await child.query_selector("span.label, .label")
                    if child_label:
                        child_text = await child_label.inner_text()
                    else:
                        child_text = await child.inner_text()
                        child_text = child_text.split('\n')[0]
                    child_text = child_text.strip()[:60]
                    print(f"        - {child_text}")
                    tree_structure[text]["subcategories"].append(child_text)
                if len(children) > 10:
                    print(f"        ... and {len(children) - 10} more")
        
        # Save structure
        print("\n=== JSON OUTPUT ===\n")
        print(json.dumps(tree_structure, indent=2))
        
        with open("/tmp/wiring_tree_structure.json", "w") as f:
            json.dump(tree_structure, f, indent=2)
        print("\nSaved to: /tmp/wiring_tree_structure.json")


if __name__ == "__main__":
    asyncio.run(inspect_wiring_tree())
