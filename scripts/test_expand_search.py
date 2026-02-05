#!/usr/bin/env python3
"""
Test: Can Gemini find the golden key with minimal instructions?

Simulates nested expandable content like DTC Index.
AI must systematically search through categories to find the hidden key.
"""

import os
import json
import time
import requests

# Load API key
API_KEY_FILE = os.path.expanduser("~/gary_gemini_api_key")
with open(API_KEY_FILE) as f:
    API_KEY = f.read().strip()

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"

# Simulated page state - nested expandable structure
PAGE_STATE = {
    "categories": [
        {
            "name": "CATEGORY A - FRUITS",
            "expanded": False,
            "items": [
                {"name": "Apple", "has_children": False},
                {"name": "Banana", "has_children": False},
                {"name": "Cherry", "has_children": False},
            ]
        },
        {
            "name": "CATEGORY B - ANIMALS",
            "expanded": False,
            "items": [
                {
                    "name": "Dogs",
                    "has_children": True,
                    "expanded": False,
                    "children": [
                        {"name": "Labrador"},
                        {"name": "Poodle"},
                        {"name": "Golden Retriever"},
                    ]
                },
                {
                    "name": "Cats",
                    "has_children": True,
                    "expanded": False,
                    "children": [
                        {"name": "Siamese"},
                        {"name": "Persian"},
                        {"name": "*** THE GOLDEN KEY IS HERE! ***"},  # Hidden in nested!
                    ]
                },
                {"name": "Birds", "has_children": False},
            ]
        },
        {
            "name": "CATEGORY C - COLORS",
            "expanded": False,
            "items": [
                {"name": "Red", "has_children": False},
                {"name": "Blue", "has_children": False},
                {"name": "Green", "has_children": False},
            ]
        },
    ],
    "current_category": None,
    "current_subcategory": None,
}


def render_page():
    """Render current page state as text for AI to see."""
    lines = ["=" * 50, "CURRENT PAGE VIEW", "=" * 50, ""]
    
    if PAGE_STATE["current_subcategory"]:
        # Viewing a subcategory's children
        cat = PAGE_STATE["current_category"]
        subcat = PAGE_STATE["current_subcategory"]
        lines.append(f"VIEWING: {cat['name']} > {subcat['name']}")
        lines.append("")
        if subcat.get("expanded") and subcat.get("children"):
            for child in subcat["children"]:
                lines.append(f"  - {child['name']}")
        else:
            lines.append("  [Content not expanded - use expand_all()]")
        lines.append("")
        lines.append("Navigation: Use go_back() to return to category list")
        
    elif PAGE_STATE["current_category"]:
        # Viewing a category's items
        cat = PAGE_STATE["current_category"]
        lines.append(f"VIEWING: {cat['name']}")
        lines.append("")
        if cat["expanded"]:
            for item in cat["items"]:
                suffix = " [+]" if item.get("has_children") else ""
                lines.append(f"  - {item['name']}{suffix}")
            lines.append("")
            lines.append("Items marked [+] have more content - click them to drill down")
        else:
            lines.append("  [Content not expanded - use expand_all()]")
        lines.append("")
        lines.append("Navigation: Use go_back() to return to main list")
        
    else:
        # Main category list
        lines.append("MAIN MENU - Select a category:")
        lines.append("")
        for i, cat in enumerate(PAGE_STATE["categories"]):
            lines.append(f"  [{i}] {cat['name']}")
        lines.append("")
        lines.append("Use click(number) to select a category")
    
    return "\n".join(lines)


def execute_tool(tool_name: str, args: dict) -> str:
    """Execute a tool and return result."""
    
    if tool_name == "click":
        idx = args.get("index")
        
        if PAGE_STATE["current_category"] and not PAGE_STATE["current_subcategory"]:
            # Click on an item within a category
            cat = PAGE_STATE["current_category"]
            if cat["expanded"] and 0 <= idx < len(cat["items"]):
                item = cat["items"][idx]
                if item.get("has_children"):
                    PAGE_STATE["current_subcategory"] = item
                    return f"Clicked '{item['name']}'. Now viewing its contents."
                else:
                    return f"'{item['name']}' has no children to expand."
            return "Invalid index or category not expanded"
            
        elif PAGE_STATE["current_category"] is None:
            # Click on a category from main menu
            if 0 <= idx < len(PAGE_STATE["categories"]):
                PAGE_STATE["current_category"] = PAGE_STATE["categories"][idx]
                return f"Selected '{PAGE_STATE['categories'][idx]['name']}'"
            return "Invalid category index"
        
        return "Cannot click here"
    
    elif tool_name == "expand_all":
        if PAGE_STATE["current_subcategory"]:
            PAGE_STATE["current_subcategory"]["expanded"] = True
            return "Expanded subcategory content."
        elif PAGE_STATE["current_category"]:
            PAGE_STATE["current_category"]["expanded"] = True
            return "Expanded category content."
        return "Nothing to expand at main menu."
    
    elif tool_name == "go_back":
        if PAGE_STATE["current_subcategory"]:
            PAGE_STATE["current_subcategory"] = None
            return "Returned to category view."
        elif PAGE_STATE["current_category"]:
            PAGE_STATE["current_category"] = None
            return "Returned to main menu."
        return "Already at main menu."
    
    elif tool_name == "found_it":
        location = args.get("location", "")
        if "GOLDEN KEY" in location.upper():
            return "SUCCESS! You found the golden key!"
        return "That's not the golden key. Keep searching."
    
    return f"Unknown tool: {tool_name}"


def call_gemini(system_prompt: str, user_message: str) -> dict:
    """Call Gemini API."""
    
    tools = [
        {
            "function_declarations": [
                {
                    "name": "click",
                    "description": "Click on an item by its index number",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer", "description": "Index of item to click"}
                        },
                        "required": ["index"]
                    }
                },
                {
                    "name": "expand_all",
                    "description": "Expand all collapsed content on current page"
                },
                {
                    "name": "go_back",
                    "description": "Go back to previous page/level"
                },
                {
                    "name": "found_it",
                    "description": "Call this when you find the golden key",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string", "description": "The text where you found it"}
                        },
                        "required": ["location"]
                    }
                }
            ]
        }
    ]
    
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
        "tools": tools,
        "tool_config": {"function_calling_config": {"mode": "AUTO"}}
    }
    
    response = requests.post(GEMINI_URL, json=payload)
    return response.json()


def main():
    print("\n" + "=" * 60)
    print("TEST: Can Gemini find the golden key?")
    print("=" * 60)
    
    # MINIMAL instructions - let's see if it figures it out!
    system_prompt = """You are searching for a hidden item called "THE GOLDEN KEY".
It is buried somewhere in the nested content structure.
Use the tools to navigate and search.
When you find it, call found_it() with the location."""
    
    max_steps = 20
    path_taken = []  # Track what AI has done
    
    for step in range(max_steps):
        page_view = render_page()
        
        # Build full prompt with path history
        full_prompt = page_view
        if path_taken:
            full_prompt += "\n\n" + "=" * 50
            full_prompt += "\nYOUR PATH SO FAR:"
            for i, action in enumerate(path_taken, 1):
                full_prompt += f"\n  {i}. {action}"
            full_prompt += "\n" + "=" * 50
        
        print(f"\n--- STEP {step + 1} ---")
        print("FULL PROMPT TO AI:")
        print("-" * 40)
        print(full_prompt)
        print("-" * 40)
        
        # Rate limit protection
        time.sleep(3)
        
        result = call_gemini(system_prompt, full_prompt)
        
        # Parse response
        candidates = result.get("candidates", [])
        if not candidates:
            print("No response from Gemini")
            print(json.dumps(result, indent=2))
            break
        
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        
        tool_called = False
        for part in parts:
            if "functionCall" in part:
                tool_called = True
                func = part["functionCall"]
                tool_name = func["name"]
                tool_args = func.get("args", {})
                
                print(f"\n>>> AI CALLS: {tool_name}({tool_args})")
                
                tool_result = execute_tool(tool_name, tool_args)
                print(f"    Result: {tool_result}")
                
                # Record in path
                path_taken.append(f"{tool_name}({tool_args}) → {tool_result}")
                
                if "SUCCESS" in tool_result:
                    print("\n" + "=" * 60)
                    print(f"🎉 FOUND IN {step + 1} STEPS!")
                    print("=" * 60)
                    return
                    
            elif "text" in part:
                print(f"\n>>> AI SAYS: {part['text'][:200]}")
        
        if not tool_called:
            print("AI didn't call a tool - might be stuck")
    
    print("\n" + "=" * 60)
    print(f"❌ FAILED - Did not find the golden key in {max_steps} steps")
    print("=" * 60)


if __name__ == "__main__":
    main()
