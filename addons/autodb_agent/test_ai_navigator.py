#!/usr/bin/env python3
"""
Test AI navigator on Operation CHARM site.

Tests the AI's ability to navigate, backtrack when wrong, and find info.
Uses the same patterns as Mitchell AI navigator.
"""

import asyncio
import json
import os
import time
import httpx
from playwright.async_api import async_playwright, Page
from urllib.parse import quote, unquote

# Gemini settings
GEMINI_API_KEY = open(os.path.expanduser("~/gary_gemini_api_key")).read().strip()
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# Rate limiting - be slow to avoid limits
DELAY_BETWEEN_CALLS = 5.0  # seconds - Gemini free tier is strict

BASE_URL = "http://automotive.aurora-sentient.net/autodb"

# Test cases - queries that ARE answerable from Operation CHARM structure
TEST_CASES = [
    {
        "vehicle": "Chevrolet/2010/Impala V6-3.5L",
        "query": "what is the engine oil pressure specification",
        "hint": "Look in Specifications > Pressure, Vacuum and Temperature"
    },
    {
        "vehicle": "Jeep Truck/1985/CJ-7 L4-150 2.5L VIN U 1-bbl",
        "query": "choke relay location",
        "hint": "Could be under Relays, Fuel System, or Carburetor"
    },
    {
        "vehicle": "Ford Truck/2005/F 150 2WD Pickup V8-5.4L SOHC VIN 5",
        "query": "spark plug torque specification",
        "hint": "Under Engine > Ignition System or Specifications"
    },
    {
        "vehicle": "Toyota/2008/Camry L4-2.4L (2AZ-FE)",
        "query": "coolant capacity",
        "hint": "Under Specifications > Capacity Specifications"
    },
    {
        "vehicle": "Honda/2012/Civic L4-1.8L",
        "query": "timing chain tensioner procedure",
        "hint": "Under Engine > Timing"
    },
    {
        "vehicle": "Ford/2008/Focus L4-2.0L",
        "query": "wheel lug nut torque",
        "hint": "Under Specifications or Wheels"
    },
    {
        "vehicle": "Nissan-Datsun/2005/Altima L4-2.5L (QR25DE)",
        "query": "spark plug torque specification",
        "hint": "Under Specifications > Mechanical"
    },
    {
        "vehicle": "BMW/2006/325i Sedan (E90) L6-3.0L (N52)",
        "query": "engine oil capacity",
        "hint": "Under Specifications > Capacity"
    },
    {
        "vehicle": "Dodge/2010/Charger V6-3.5L",
        "query": "transmission fluid capacity",
        "hint": "Under Specifications > Capacity"
    },
    {
        "vehicle": "Subaru/2009/Impreza F4-2.5L SOHC",
        "query": "brake rotor minimum thickness",
        "hint": "Under Brakes > Specifications"
    },
]


async def extract_page_state(page: Page, tree_path: list = None) -> dict:
    """Extract current page state for AI.
    
    tree_path: List of folder names to drill into on the current page.
               e.g., ["Specifications", "Pressure, Vacuum and Temperature Specifications"]
               This lets us navigate INTO the tree without changing pages.
    """
    if tree_path is None:
        tree_path = []
    
    # Get current URL path
    url = page.url
    path = unquote(url.replace(BASE_URL, "").strip("/"))
    
    # Add tree path to display path
    display_path = path
    if tree_path:
        display_path = path + " > " + " > ".join(tree_path)
    
    # Get page title
    title = await page.title()
    
    # Get items at the specified tree depth
    # Pass tree_path to JavaScript to drill into the correct folder
    tree_path_json = json.dumps(tree_path)
    links = await page.evaluate(f"""
        () => {{
            const treePath = {tree_path_json};
            const links = [];
            let id = 1;
            
            // Find the main content area
            const main = document.querySelector('.main');
            if (!main) return links;
            
            // Start at the first <ul>
            let currentUl = main.querySelector('ul');
            if (!currentUl) return links;
            
            // Navigate down the tree path to find the right folder
            for (const folderName of treePath) {{
                // Find the <li> that contains this folder name
                let found = false;
                const items = currentUl.querySelectorAll(':scope > li');
                for (const li of items) {{
                    const anchor = li.querySelector(':scope > a, :scope > img + a');
                    if (anchor && anchor.textContent.trim() === folderName) {{
                        // Found it! Drill into its <ul>
                        const subUl = li.querySelector(':scope > ul');
                        if (subUl) {{
                            currentUl = subUl;
                            found = true;
                            break;
                        }}
                    }}
                }}
                if (!found) {{
                    // Folder not found, return empty
                    return links;
                }}
            }}
            
            // Now get the immediate children of currentUl
            const topItems = currentUl.querySelectorAll(':scope > li');
            
            topItems.forEach(li => {{
                // Get the direct <a> child (could be folder label or actual link)
                const anchor = li.querySelector(':scope > a, :scope > img + a');
                if (!anchor) return;
                
                const text = anchor.textContent.trim();
                const href = anchor.getAttribute('href') || '';
                const name = anchor.getAttribute('name') || '';
                
                // Skip empty text
                if (!text || text.length < 2) return;
                
                // Check if this item has children (is a folder)
                const hasChildren = li.querySelector(':scope > ul') !== null;
                
                // Determine if this is a navigable link or just a folder label
                if (href && !href.startsWith('javascript:')) {{
                    // It's an actual link (may also have children)
                    links.push({{ id: id++, text, href, isFolder: hasChildren }});
                }} else if (name || hasChildren) {{
                    // It's a folder (has name attribute or children)
                    links.push({{ id: id++, text, href: name || '', isFolder: true }});
                }}
            }});
            
            return links;
        }}
    """)
    
    # Get page text content
    text_content = await page.evaluate("""
        () => {
            const main = document.querySelector('.main') || document.body;
            return main.innerText;
        }
    """)
    
    # Detect if this is a content page (actual data) vs index page (just navigation links)
    # Content pages have real info, not just lists of links
    is_content_page = False
    
    # Check if page has minimal links (1 or 0) and actual text content
    if len(links) <= 2:
        # Few links = likely a content page
        # But check if the text has actual info beyond just a title
        text_lines = text_content.strip().split('\n')
        # Filter out empty lines and lines that are just headers
        content_lines = [l for l in text_lines if l.strip() and 'Expand All' not in l and 'Collapse All' not in l]
        if len(content_lines) > 2:  # More than just title + header
            is_content_page = True
    
    # Also check for specific content markers
    content_markers = ['located', 'install', 'remove', 'procedure', 'torque:', 'capacity:', 'ft-lb', 'n.m', 'quarts', 'liters', 'psi', 'kpa']
    text_lower = text_content.lower()
    for marker in content_markers:
        if marker in text_lower:
            is_content_page = True
            break
    
    return {
        "path": display_path,  # Show the full navigation path including tree drill-down
        "title": title,
        "links": links,
        "text": text_content[:3000],
        "tree_path": tree_path,  # Track current tree position
        "is_content_page": is_content_page,
    }


async def call_gemini(messages: list) -> str:
    """Call Gemini API with rate limiting and retry."""
    max_retries = 3
    
    for attempt in range(max_retries):
        # Rate limit - wait before each call
        await asyncio.sleep(DELAY_BETWEEN_CALLS)
        
        # Convert messages to Gemini format
        # Gemini uses "contents" with "parts" instead of "messages"
        contents = []
        system_instruction = None
        
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            elif msg["role"] == "user":
                contents.append({"role": "user", "parts": [{"text": msg["content"]}]})
            elif msg["role"] == "assistant":
                contents.append({"role": "model", "parts": [{"text": msg["content"]}]})
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 100,  # Keep responses short
            }
        }
        
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{GEMINI_URL}?key={GEMINI_API_KEY}",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 429:
                    wait_time = 30 * (attempt + 1)  # 30s, 60s, 90s
                    print(f"  ⏳ Rate limited, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                    
                response.raise_for_status()
                result = response.json()
                
                # Extract text from Gemini response
                if "candidates" in result and result["candidates"]:
                    parts = result["candidates"][0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
                return ""
                
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"  ⚠️ Error: {e}, retrying...")
                await asyncio.sleep(10)
            else:
                raise
    
    return ""


def build_system_prompt(query: str, vehicle: str) -> str:
    """Build the system prompt."""
    return f"""You are navigating Operation CHARM, a car repair manual website.

VEHICLE: {vehicle}
GOAL: Find "{query}"

TOOLS:
- click(id) - Click a link by its ID number
- back() - Go back to previous page/folder to try a different path
- extract() - Extract the answer from current page (ONLY when you found the right info)

CRITICAL RULES:
1. BEFORE using extract(), READ THE PAGE TEXT carefully - does it actually contain "{query}"?
2. If the page has 0 links but DOES NOT contain your answer, use back() to try another path!
3. Example: Looking for "coolant capacity" but page shows "torque specifications" → use back()
4. There are often MULTIPLE paths to find something - if one path fails, backtrack and try another
5. Top-level "Specifications" folder often has organized categories like "Capacity Specifications"
6. Don't give up after one dead end - explore different branches

NAVIGATION TIPS:
- "capacity" info → look for "Capacity Specifications" 
- "torque" info → look for component-specific specs (e.g., "Spark Plug" has its own torque)
- "location" info → look for "Locations" under the component
- If you went into "Cooling System" but didn't find capacity, try top-level "Specifications" instead

Respond with ONLY ONE of these (nothing else):
click(5)
back()
extract()"""


def build_user_message(state: dict, path_taken: list, query: str) -> str:
    """Build the user message showing current page state and path taken."""
    lines = []
    
    # Show path taken with results
    if path_taken:
        lines.append("YOUR PATH SO FAR:")
        for i, step in enumerate(path_taken, 1):
            action = step["action"]
            result = step.get("result", "")
            if action.startswith("CLICK"):
                lines.append(f"  {i}. {action} → {result}")
            elif action == "BACK":
                lines.append(f"  {i}. BACK → returned to previous page")
            elif action == "EXTRACT":
                lines.append(f"  {i}. EXTRACT")
        lines.append("")
    
    # Current location
    lines.append("CURRENT PAGE:")
    lines.append(f"  Path: {state['path']}")
    lines.append(f"  Title: {state['title']}")
    lines.append("")
    
    # Page type indicator - make it VERY clear when to click vs extract
    num_links = len(state['links'])
    page_text = state['text'].strip()
    
    # Detect dead ends (404 pages or empty content)
    is_dead_end = num_links == 0 and (
        "Page Not Found" in state['title'] or
        "Error 404" in page_text or
        len(page_text) < 50
    )
    
    # Check if page content seems relevant to the query
    query_words = query.lower().split()
    page_text_lower = page_text.lower()
    query_match = any(word in page_text_lower for word in query_words if len(word) > 3)
    
    if is_dead_end:
        lines.append("⛔ DEAD END - This page doesn't exist or is empty. Use back() to try a different path!")
    elif num_links == 0 and not query_match:
        lines.append(f"⚠️ NO LINKS and page doesn't seem to contain '{query}' - consider using back() to try another path!")
    elif num_links == 0:
        lines.append("📄 NO MORE LINKS - check PAGE TEXT below, use extract() if it has your answer, or back() if not")
    elif num_links <= 5:
        lines.append(f"⚠️ {num_links} LINK(S) AVAILABLE - click the right one, or extract() if answer is in PAGE TEXT")
    else:
        lines.append(f"📁 {num_links} LINKS AVAILABLE - click one to navigate deeper")
    lines.append("")
    
    # Clickable options - show ALL links, no filtering
    lines.append(f"CLICKABLE OPTIONS ({len(state['links'])} links):")
    for link in state['links']:
        lines.append(f"  [{link['id']}] {link['text']}")
    lines.append("")
    
    # Page text
    lines.append("PAGE TEXT:")
    lines.append(state['text'][:2000])
    if len(state['text']) > 2000:
        lines.append("... (truncated)")
    
    return "\n".join(lines)


async def ai_navigate(page: Page, query: str, vehicle: str, start_url: str, max_steps: int = 15) -> dict:
    """
    Use AI to navigate the site and find information.
    
    Navigation model:
    - tree_path: Current position in the tree on this page (list of folder names)
    - When clicking a folder: Add to tree_path (stay on same page, drill down)
    - When clicking a link (actual href): Navigate to new page, reset tree_path
    - When going back: Either pop from tree_path, or go to previous page
    """
    
    path_taken = []
    # Stack of (url, tree_path) tuples for back()
    nav_stack = [(start_url, [])]
    current_tree_path = []
    
    system_prompt = build_system_prompt(query, vehicle)
    messages = [{"role": "system", "content": system_prompt}]
    
    for step in range(max_steps):
        # Get current page state at current tree depth
        state = await extract_page_state(page, current_tree_path)
        
        # Build user message
        user_msg = build_user_message(state, path_taken, query)
        messages.append({"role": "user", "content": user_msg})
        
        # Get AI response
        print(f"\n--- Step {step + 1} ---")
        print(f"Path: {state['path']}")
        print(f"Links: {len(state['links'])} | Content page: {state.get('is_content_page')}")
        
        response = await call_gemini(messages)
        response = response.strip().split('\n')[0]  # Take first line only
        print(f"AI: {response}")
        
        # Debug: show what AI sees for dead-end detection
        if len(state['links']) == 0:
            print(f"  DEBUG: Title='{state['title']}', Text length={len(state['text'])}, Text preview='{state['text'][:100]}...'")
        
        messages.append({"role": "assistant", "content": response})
        
        # Parse response
        if response.startswith("click("):
            # Extract ID
            try:
                id_str = response.split("(")[1].split(")")[0]
                link_id = int(id_str)
                
                # Find link with this ID
                link = next((l for l in state['links'] if l['id'] == link_id), None)
                if link:
                    link_text = link['text']
                    link_href = link['href']
                    is_folder = link.get('isFolder', False)
                    
                    path_taken.append({
                        "action": f"CLICK [{link_id}] '{link_text}'",
                        "result": "navigating..."
                    })
                    
                    if is_folder and (not link_href or not link_href.startswith('http')):
                        # It's a folder - drill into the tree on the same page
                        nav_stack.append((page.url, current_tree_path.copy()))
                        current_tree_path.append(link_text)
                        path_taken[-1]["result"] = f"entered folder: {link_text}"
                        print(f"  → Entered folder: {link_text}")
                    else:
                        # It's an actual link - navigate to new page
                        nav_stack.append((page.url, current_tree_path.copy()))
                        
                        if link_href.startswith('http'):
                            new_url = link_href
                        elif link_href.startswith('/'):
                            new_url = f"http://automotive.aurora-sentient.net{link_href}"
                        else:
                            # Relative URL - build from current page
                            base_url = page.url.rstrip('/')
                            new_url = f"{base_url}/{link_href}"
                        
                        await page.goto(new_url)
                        await page.wait_for_load_state("networkidle")
                        current_tree_path = []  # Reset tree path on new page
                        
                        # Update result
                        new_state = await extract_page_state(page, [])
                        path_taken[-1]["result"] = f"now at: {new_state['path'].split('/')[-1] or 'page'}"
                        print(f"  → Navigated to: {link_text}")
                else:
                    path_taken.append({"action": f"CLICK [{link_id}]", "result": "FAILED - ID not found"})
                    print(f"  → Error: Link ID {link_id} not found")
            except Exception as e:
                path_taken.append({"action": response, "result": f"FAILED - {e}"})
                print(f"  → Error: {e}")
                
        elif response.startswith("back()"):
            path_taken.append({"action": "BACK", "result": ""})
            
            if len(nav_stack) > 1:
                nav_stack.pop()  # Remove current
                prev_url, prev_tree_path = nav_stack[-1]
                
                if prev_url != page.url:
                    # Need to navigate to previous page
                    await page.goto(prev_url)
                    await page.wait_for_load_state("networkidle")
                
                current_tree_path = prev_tree_path
                print(f"  → Went back (tree: {' > '.join(current_tree_path) or 'root'})")
            else:
                print(f"  → Can't go back, at start")
                
        elif response.startswith("extract()"):
            # Guard: If there are still links, don't extract - click first!
            if len(state['links']) > 0:
                print(f"  → Can't extract yet - there are {len(state['links'])} link(s) to explore!")
                # Add a hint to the conversation
                messages.append({
                    "role": "user", 
                    "content": f"You cannot extract yet! There are {len(state['links'])} clickable links. Click one of them first: " + 
                              ", ".join([f"[{l['id']}] {l['text']}" for l in state['links'][:5]])
                })
                continue
                
            path_taken.append({"action": "EXTRACT", "result": ""})
            
            # Get the full page content for extraction
            state = await extract_page_state(page)
            
            # Ask AI to extract the answer
            extract_msg = f"""You found the page! Extract the answer to: {query}

Page content:
{state['text']}

Give a concise, specific answer based on what you see. If the answer isn't here, say "NOT FOUND"."""
            
            answer = await call_gemini([
                {"role": "system", "content": "Extract the specific answer from the page content. Be concise."},
                {"role": "user", "content": extract_msg}
            ])
            
            return {
                "success": "NOT FOUND" not in answer.upper(),
                "answer": answer,
                "path_taken": path_taken,
                "steps": step + 1,
                "final_path": state['path'],
            }
        else:
            print(f"  → Unknown response: {response}")
            path_taken.append({"action": f"UNKNOWN: {response}", "result": ""})
    
    return {
        "success": False,
        "answer": "Max steps reached",
        "path_taken": path_taken,
        "steps": max_steps,
        "final_path": state['path'],
    }


async def run_test(test_case: dict):
    """Run a single test case."""
    print("\n" + "="*70)
    print(f"TEST: {test_case['query']}")
    print(f"Vehicle: {test_case['vehicle']}")
    print(f"Hint: {test_case['hint']}")
    print("="*70)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Navigate to vehicle's Repair and Diagnosis page
        vehicle_encoded = quote(test_case['vehicle'], safe='/')
        start_url = f"{BASE_URL}/{vehicle_encoded}/Repair%20and%20Diagnosis/"
        print(f"\nStarting at: {start_url}")
        
        await page.goto(start_url)
        await page.wait_for_load_state("networkidle")
        
        # Run AI navigation
        result = await ai_navigate(page, test_case['query'], test_case['vehicle'], start_url)
        
        await browser.close()
    
    # Print results
    print("\n" + "-"*50)
    print("RESULTS:")
    print(f"  Success: {result['success']}")
    print(f"  Steps: {result['steps']}")
    print(f"  Final path: {result.get('final_path', 'N/A')}")
    print(f"  Path taken:")
    for i, step in enumerate(result['path_taken'], 1):
        print(f"    {i}. {step['action']} → {step.get('result', '')}")
    if result['answer']:
        print(f"\n  ANSWER:\n{result['answer'][:800]}")
    
    return result


async def main():
    """Run all test cases."""
    print("AutoDB AI Navigator Test")
    print(f"Using model: {GEMINI_MODEL}")
    print(f"Rate limit delay: {DELAY_BETWEEN_CALLS}s between calls")
    
    results = []
    for test_case in TEST_CASES:
        result = await run_test(test_case)
        results.append({
            "query": test_case['query'],
            "vehicle": test_case['vehicle'],
            **result
        })
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    successes = sum(1 for r in results if r['success'])
    print(f"Passed: {successes}/{len(results)}")
    for r in results:
        status = "✓" if r['success'] else "✗"
        print(f"  {status} {r['query']} ({r['steps']} steps)")


if __name__ == "__main__":
    asyncio.run(main())
