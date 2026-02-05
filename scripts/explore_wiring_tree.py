#!/usr/bin/env python3
"""
Explore wiring diagram tree structure in ShopKeyPro.
Captures all branches for documentation in navigation_config.json.
"""

import asyncio
import json
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addons.mitchell_agent.api import MitchellAPI
from addons.mitchell_agent.tools.base import Vehicle


async def explore_wiring_tree():
    """Navigate to wiring diagrams and capture tree structure."""
    
    api = MitchellAPI(headless=False)
    
    try:
        print("Connecting to browser...")
        connected = await api.connect()
        if not connected:
            print("ERROR: Failed to connect")
            return
        
        print("Connected! Getting page...")
        
        # Get the page from the internal context
        page = api._page
        if not page:
            print("ERROR: No page available")
            return
        
        # First select a vehicle (required to access wiring diagrams)
        print("\nSelecting vehicle: 2014 Chevrolet Cruze 1.4L...")
        vehicle = Vehicle(year=2014, make="Chevrolet", model="Cruze", engine="1.4L")
        result = await api.get_fluid_capacities(2014, "Chevrolet", "Cruze", "1.4L")
        print(f"Vehicle selection result: success={result.get('success', False)}")
        
        # Wait for page to settle
        await page.wait_for_timeout(1000)
        
        print("\nClicking Wiring Diagrams quick access...")
        await page.click("#wiringDiagramsAccess")
        await page.wait_for_timeout(2000)
        
        # Take screenshot
        await page.screenshot(path="/tmp/wiring_tree_01_initial.png")
        print("Screenshot: /tmp/wiring_tree_01_initial.png")
        
        # Look for the modal dialog
        modal = await page.query_selector(".modalDialogView")
        if not modal:
            print("ERROR: No modal found")
            return
        
        print("\n=== WIRING DIAGRAM TREE STRUCTURE ===\n")
        
        # Get all top-level items in the tree
        tree_structure = {}
        
        # First, let's see what's at the top level
        top_level_items = await page.query_selector_all(".modalDialogView ul.tree > li.node")
        print(f"Found {len(top_level_items)} top-level items")
        
        for i, item in enumerate(top_level_items):
            label = await item.query_selector("span.label")
            if label:
                text = await label.inner_text()
                text = text.strip()
                print(f"\n[{i+1}] TOP LEVEL: {text}")
                tree_structure[text] = {"subcategories": []}
                
                # Check if it has an expand icon
                expand_icon = await item.query_selector(".treeExpandCollapseIcon")
                if expand_icon:
                    # Click to expand
                    await expand_icon.click()
                    await page.wait_for_timeout(500)
                    
                    # Get children
                    children = await item.query_selector_all(":scope > ul > li.node")
                    print(f"    Found {len(children)} children")
                    
                    for child in children:
                        child_label = await child.query_selector("span.label")
                        if child_label:
                            child_text = await child_label.inner_text()
                            child_text = child_text.strip()
                            print(f"    - {child_text}")
                            tree_structure[text]["subcategories"].append(child_text)
        
        # Take screenshot after expansion
        await page.screenshot(path="/tmp/wiring_tree_02_expanded.png")
        print("\nScreenshot: /tmp/wiring_tree_02_expanded.png")
        
        # Now let's explore SYSTEM WIRING DIAGRAMS specifically
        print("\n\n=== EXPLORING SYSTEM WIRING DIAGRAMS ===\n")
        
        # Find and click "SYSTEM WIRING DIAGRAMS"
        system_wiring = await page.query_selector(".modalDialogView li.node:has(span.label:has-text('SYSTEM WIRING DIAGRAMS'))")
        if system_wiring:
            expand_icon = await system_wiring.query_selector(".treeExpandCollapseIcon")
            if expand_icon:
                # Make sure it's expanded
                is_expanded = await system_wiring.query_selector(":scope > ul")
                if not is_expanded:
                    await expand_icon.click()
                    await page.wait_for_timeout(500)
                
                # Get all system categories
                system_categories = await system_wiring.query_selector_all(":scope > ul > li.node")
                print(f"Found {len(system_categories)} system categories:\n")
                
                system_wiring_tree = {}
                
                for cat in system_categories:
                    cat_label = await cat.query_selector("span.label")
                    if cat_label:
                        cat_text = await cat_label.inner_text()
                        cat_text = cat_text.strip()
                        print(f"  CATEGORY: {cat_text}")
                        system_wiring_tree[cat_text] = []
                        
                        # Try to expand this category to see diagrams
                        cat_expand = await cat.query_selector(".treeExpandCollapseIcon")
                        if cat_expand:
                            await cat_expand.click()
                            await page.wait_for_timeout(300)
                            
                            # Get diagram names
                            diagrams = await cat.query_selector_all(":scope > ul > li.node span.label")
                            for diag in diagrams[:5]:  # Limit to first 5
                                diag_text = await diag.inner_text()
                                diag_text = diag_text.strip()
                                print(f"      - {diag_text}")
                                system_wiring_tree[cat_text].append(diag_text)
                            
                            if len(diagrams) > 5:
                                print(f"      ... and {len(diagrams) - 5} more")
                                system_wiring_tree[cat_text].append(f"... ({len(diagrams)} total)")
                        
                        print()
                
                tree_structure["SYSTEM WIRING DIAGRAMS"]["detail"] = system_wiring_tree
        
        # Take final screenshot
        await page.screenshot(path="/tmp/wiring_tree_03_full.png")
        print("\nScreenshot: /tmp/wiring_tree_03_full.png")
        
        # Output JSON for navigation_config.json
        print("\n\n=== JSON FOR navigation_config.json ===\n")
        print(json.dumps(tree_structure, indent=2))
        
        # Save to file
        with open("/tmp/wiring_tree_structure.json", "w") as f:
            json.dump(tree_structure, f, indent=2)
        print("\nSaved to: /tmp/wiring_tree_structure.json")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\nLogging out...")
        await api.logout()
        await api.disconnect()


if __name__ == "__main__":
    asyncio.run(explore_wiring_tree())
