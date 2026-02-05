"""
AutoDB AI Navigator - Production version using tree-based navigation.

This module provides the AI-powered navigator for Operation CHARM that
achieved 10/10 success in testing. Uses Playwright + Gemini for navigation.
"""

import asyncio
import json
import os
import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from urllib.parse import quote, unquote

import httpx
from playwright.async_api import async_playwright, Page, Browser

# Configure logging to file
log = logging.getLogger("autodb_navigator")
if not log.handlers:
    log.setLevel(logging.INFO)
    fh = logging.FileHandler("/tmp/autodb_navigator.log")
    fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    log.addHandler(fh)

# Configuration
GEMINI_API_KEY = None  # Loaded lazily
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
DELAY_BETWEEN_CALLS = 3.0  # Reduced from 5s for production
BASE_URL = os.environ.get("AUTODB_BASE_URL", "http://automotive.aurora-sentient.net/autodb")


def get_gemini_api_key() -> str:
    """Load Gemini API key from environment or file."""
    global GEMINI_API_KEY
    if GEMINI_API_KEY:
        return GEMINI_API_KEY
    
    key = os.environ.get("GOOGLE_API_KEY")
    if key:
        GEMINI_API_KEY = key
        return key
    
    for path in [
        os.path.expanduser("~/gary_gemini_api_key"),
        "/home/drawson/gary_gemini_api_key",
    ]:
        try:
            with open(path, 'r') as f:
                GEMINI_API_KEY = f.read().strip()
                return GEMINI_API_KEY
        except FileNotFoundError:
            continue
    
    raise RuntimeError("Gemini API key not found")


@dataclass
class NavigationResult:
    """Result from navigation."""
    success: bool
    content: str = ""
    url: str = ""
    breadcrumb: str = ""
    error: str = ""
    path_taken: List[str] = field(default_factory=list)
    steps: int = 0
    tokens_used: Dict[str, int] = field(default_factory=dict)
    images: List[str] = field(default_factory=list)  # URLs of images on the page


async def call_gemini(messages: list) -> str:
    """Call Gemini API with rate limiting and retry."""
    api_key = get_gemini_api_key()
    max_retries = 3
    
    for attempt in range(max_retries):
        await asyncio.sleep(DELAY_BETWEEN_CALLS)
        
        # Convert messages to Gemini format
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
                "maxOutputTokens": 100,
            }
        }
        
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{GEMINI_URL}?key={api_key}",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 429:
                    wait_time = 30 * (attempt + 1)
                    log.warning(f"Rate limited, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                result = response.json()
                
                if "candidates" in result and result["candidates"]:
                    parts = result["candidates"][0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
                return ""
                
        except Exception as e:
            if attempt < max_retries - 1:
                log.warning(f"Error: {e}, retrying...")
                await asyncio.sleep(10)
            else:
                raise
    
    return ""


async def get_links_at_tree_depth(page: Page, tree_path: list) -> list:
    """Get links at the current tree depth using Playwright locators.
    
    The HTML structure uses nested ul/li with folder markers:
    <li class='li-folder'><a name='Folder%20Name/'>Folder Name</a><ul>...</ul></li>
    <li><a href='page.html'>Content Page</a></li>
    """
    links = []
    
    try:
        if not tree_path:
            # Root level - get direct children of main ul
            items = page.locator("div.main > ul > li")
        else:
            # Navigate through tree path to find current container
            # Start from root
            container = page.locator("div.main > ul")
            
            for folder_name in tree_path:
                # Find the li.li-folder that has an <a> with EXACT text match
                # We need to iterate because filter(has_text=) does substring matching
                folder_items = container.locator("> li.li-folder")
                folder_count = await folder_items.count()
                found_folder = None
                
                for idx in range(folder_count):
                    folder_li = folder_items.nth(idx)
                    link_el = folder_li.locator("> a").first
                    if await link_el.count() > 0:
                        link_text = (await link_el.inner_text()).strip()
                        if link_text == folder_name:
                            found_folder = folder_li
                            break
                
                if found_folder is None:
                    log.warning(f"Could not find folder '{folder_name}' in tree")
                    return []
                
                # Get the ul inside this folder
                container = found_folder.locator("> ul")
                
                if await container.count() == 0:
                    log.warning(f"Folder '{folder_name}' has no ul container")
                    return []
            
            items = container.locator("> li")
        
        count = await items.count()
        log.debug(f"Found {count} items at tree depth {len(tree_path)}")
        
        for i in range(min(count, 50)):
            item = items.nth(i)
            link = item.locator("> a").first
            
            if await link.count() > 0:
                text = (await link.inner_text()).strip()
                if text:
                    has_href = await link.get_attribute("href")
                    is_folder = "li-folder" in (await item.get_attribute("class") or "")
                    links.append({
                        "id": len(links) + 1,
                        "text": text,
                        "is_folder": is_folder,
                        "has_href": bool(has_href)
                    })
    except Exception as e:
        log.error(f"Error getting links at tree depth: {e}")
    
    return links


async def extract_page_state(page: Page, tree_path: list) -> dict:
    """Extract the current page state for AI navigation."""
    
    # Get page text
    text = await page.inner_text("body")
    text_content = ' '.join(text.split())[:3000]
    
    # Get title
    title = await page.title()
    
    # Build display path
    url = page.url
    path_part = unquote(url.replace(BASE_URL, "").strip("/"))
    if tree_path:
        display_path = f"{path_part} > {' > '.join(tree_path)}"
    else:
        display_path = path_part
    
    # Get links at current tree depth using proper Playwright navigation
    links = await get_links_at_tree_depth(page, tree_path)
    
    # Detect if this is a content page
    content_markers = ["procedure", "specification", "operation", "description", "torque", "capacity"]
    text_lower = text_content.lower()
    is_content_page = any(marker in text_lower for marker in content_markers) or len(links) == 0
    
    return {
        "path": display_path,
        "title": title,
        "links": links,
        "text": text_content,
        "tree_path": tree_path,
        "is_content_page": is_content_page,
    }


def build_system_prompt(query: str, vehicle: str) -> str:
    """Build the system prompt for AI navigation."""
    return f"""You are navigating a car repair manual website.

VEHICLE: {vehicle}
GOAL: Find "{query}"

TOOLS:
- click(id) - Click a link by its ID number
- back() - Go back up one level to try a different path
- extract() - Extract the answer from current page when you've found it

Respond with ONLY the tool call like: click(5) or back() or extract()"""


def build_user_message(state: dict, path_taken: list, query: str) -> str:
    """Build the user message showing current page state."""
    
    links_text = ""
    if state["links"]:
        link_lines = []
        for link in state["links"]:
            marker = "📁" if link["is_folder"] else "📄"
            link_lines.append(f"  [{link['id']}] {marker} {link['text']}")
        links_text = "\n".join(link_lines)
    else:
        links_text = "  (no navigation links - this is a content page)"
    
    # Check if page content matches the query
    query_words = query.lower().split()
    text_lower = state["text"].lower()
    matching_words = [w for w in query_words if w in text_lower]
    mismatch_warning = ""
    if len(matching_words) < len(query_words) / 2:
        mismatch_warning = f"\n⚠️ Warning: Page doesn't seem to contain '{query}' - consider using back() if this isn't the right page."
    
    path_str = "\n".join([f"  {i+1}. {step}" for i, step in enumerate(path_taken)]) if path_taken else "  (start)"
    
    return f"""CURRENT LOCATION:
Path: {state['path']}
Links: {len(state['links'])} | Content page: {state['is_content_page']}

AVAILABLE LINKS:
{links_text}

PAGE TEXT PREVIEW:
{state['text'][:1500]}
{mismatch_warning}

YOUR PATH SO FAR:
{path_str}

What's your next action?"""


def parse_action(response: str) -> tuple:
    """Parse AI response into action and argument."""
    response = response.strip().lower()
    
    # Handle click(N)
    match = re.search(r'click\s*\(\s*(\d+)\s*\)', response)
    if match:
        return "click", int(match.group(1))
    
    # Handle back()
    if "back()" in response or response == "back":
        return "back", None
    
    # Handle extract()
    if "extract()" in response or response == "extract":
        return "extract", None
    
    return "unknown", response


async def ai_navigate(page: Page, query: str, vehicle: str, start_url: str) -> NavigationResult:
    """
    Navigate using AI to find the requested information.
    
    Uses tree-based navigation where folders expand in-place
    and content links navigate to new pages.
    """
    max_steps = 20
    tree_path = []  # Current position in folder tree
    nav_stack = [(start_url, [])]  # Stack of (url, tree_path) for backtracking
    path_taken = []
    
    messages = [
        {"role": "system", "content": build_system_prompt(query, vehicle)}
    ]
    
    for step in range(max_steps):
        # Get current page state
        state = await extract_page_state(page, tree_path)
        
        log.info(f"Step {step + 1}: path={state['path']}, links={len(state['links'])}")
        
        # Build user message
        user_msg = build_user_message(state, path_taken, query)
        messages.append({"role": "user", "content": user_msg})
        
        # Get AI decision
        response = await call_gemini(messages)
        messages.append({"role": "assistant", "content": response})
        
        action, arg = parse_action(response)
        log.info(f"  AI: {action}({arg if arg else ''})")
        
        if action == "extract":
            # Extract content from page
            text = state["text"]
            
            # Clean up the text
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            content = '\n'.join(lines)
            
            # Extract images from the page (specification diagrams)
            images = []
            try:
                img_elements = await page.query_selector_all(".oxe-image img, .big-img, img[src*='/autodb/images/']")
                for img in img_elements:
                    src = await img.get_attribute("src")
                    if src:
                        # Make absolute URL
                        if src.startswith("/"):
                            src = f"http://automotive.aurora-sentient.net{src}"
                        images.append(src)
                        log.info(f"  → Found image: {src}")
            except Exception as e:
                log.warning(f"Failed to extract images: {e}")
            
            breadcrumb = state["path"].replace(" > ", " >> ")
            
            return NavigationResult(
                success=True,
                content=content,
                url=page.url,
                breadcrumb=breadcrumb,
                path_taken=path_taken,
                steps=step + 1,
                images=images
            )
        
        elif action == "back":
            if tree_path:
                # Back out of current folder
                folder = tree_path.pop()
                path_taken.append(f"BACK from {folder}")
                log.info(f"  → Exited folder: {folder}")
            elif len(nav_stack) > 1:
                # Go back to previous page
                nav_stack.pop()
                prev_url, prev_tree = nav_stack[-1]
                await page.goto(prev_url)
                await page.wait_for_load_state("networkidle")
                tree_path = prev_tree.copy()
                path_taken.append("BACK to previous page")
                log.info(f"  → Went back to {prev_url}")
            else:
                path_taken.append("BACK (already at start)")
                log.info("  → Already at start, can't go back")
        
        elif action == "click" and arg:
            # Find the link
            link = next((l for l in state["links"] if l["id"] == arg), None)
            if not link:
                path_taken.append(f"CLICK [{arg}] (not found)")
                continue
            
            link_text = link["text"]
            
            if link["is_folder"]:
                # Folder - expand in tree, stay on same page
                tree_path.append(link_text)
                path_taken.append(f"CLICK [{arg}] '{link_text}' → entered folder")
                log.info(f"  → Entered folder: {link_text}")
            else:
                # Content link - navigate to new page via href
                try:
                    # Find the link element using tree navigation with EXACT matching
                    container = page.locator("div.main > ul")
                    
                    # Navigate down tree_path to find parent container
                    for folder_name in tree_path:
                        folder_items = container.locator("> li.li-folder")
                        folder_count = await folder_items.count()
                        found_folder = None
                        
                        for idx in range(folder_count):
                            folder_li = folder_items.nth(idx)
                            link_el = folder_li.locator("> a").first
                            if await link_el.count() > 0:
                                text = (await link_el.inner_text()).strip()
                                if text == folder_name:
                                    found_folder = folder_li
                                    break
                        
                        if found_folder is None:
                            path_taken.append(f"CLICK [{arg}] '{link_text}' (folder '{folder_name}' not found)")
                            continue
                        container = found_folder.locator("> ul")
                    
                    # Now find the actual link within this container using exact text match
                    link_items = container.locator("> li > a[href]")
                    link_count = await link_items.count()
                    link_el = None
                    
                    for idx in range(link_count):
                        el = link_items.nth(idx)
                        text = (await el.inner_text()).strip()
                        if text == link_text:
                            link_el = el
                            break
                    
                    if link_el is not None:
                        href = await link_el.get_attribute("href")
                        if href:
                            # Navigate
                            if href.startswith("/"):
                                new_url = f"{BASE_URL.rsplit('/autodb', 1)[0]}{href}"
                            elif href.startswith("http"):
                                new_url = href
                            else:
                                new_url = f"{page.url.rstrip('/')}/{href}"
                            
                            await page.goto(new_url)
                            await page.wait_for_load_state("networkidle")
                            
                            # Save to nav stack and reset tree
                            nav_stack.append((new_url, []))
                            tree_path = []
                            path_taken.append(f"CLICK [{arg}] '{link_text}' → navigated to page")
                            log.info(f"  → Navigated to: {new_url}")
                        else:
                            path_taken.append(f"CLICK [{arg}] '{link_text}' (no href)")
                    else:
                        path_taken.append(f"CLICK [{arg}] '{link_text}' (element not found)")
                except Exception as e:
                    log.error(f"Click error: {e}")
                    path_taken.append(f"CLICK [{arg}] (error: {e})")
        
        else:
            path_taken.append(f"UNKNOWN: {response[:50]}")
    
    return NavigationResult(
        success=False,
        error="Max steps reached",
        url=page.url,
        path_taken=path_taken,
        steps=max_steps
    )


async def navigate_autodb(goal: str, vehicle: dict) -> NavigationResult:
    """
    Navigate Operation CHARM to find information.
    
    Args:
        goal: What to find (e.g., "charging system operation description")
        vehicle: Dict with year, make, model
    
    Returns:
        NavigationResult with content or error
    """
    log.info(f"=== navigate_autodb START ===")
    log.info(f"Goal: {goal}")
    log.info(f"Vehicle: {vehicle}")
    
    year = vehicle.get("year", "")
    make = vehicle.get("make", "")
    model = vehicle.get("model", "")
    engine = vehicle.get("engine", "")
    
    # Build vehicle string and URL
    vehicle_str = f"{year} {make} {model}"
    
    # Build start URL - go directly to vehicle's Repair and Diagnosis page
    # Make might need "Truck" suffix for SUVs
    make_variants = [make, f"{make} Truck"]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Try different make variants and model matching strategies
        start_url = None
        final_model = model
        
        for make_var in make_variants:
            make_encoded = quote(make_var, safe='')
            
            # Strategy 1: Try exact model name
            model_encoded = quote(model, safe='')
            test_url = f"{BASE_URL}/{make_encoded}/{year}/{model_encoded}/Repair%20and%20Diagnosis/"
            
            try:
                response = await page.goto(test_url, timeout=15000)
                if response and response.status == 200:
                    title = await page.title()
                    if "Page Not Found" not in title:
                        start_url = test_url
                        log.info(f"Found vehicle at: {start_url}")
                        break
            except Exception as e:
                log.debug(f"Failed {test_url}: {e}")
            
            # Strategy 2: If model+engine were split, try combining them
            if engine and not start_url:
                combined_model = f"{model} {engine}"
                model_encoded = quote(combined_model, safe='')
                test_url = f"{BASE_URL}/{make_encoded}/{year}/{model_encoded}/Repair%20and%20Diagnosis/"
                
                try:
                    response = await page.goto(test_url, timeout=15000)
                    if response and response.status == 200:
                        title = await page.title()
                        if "Page Not Found" not in title:
                            start_url = test_url
                            final_model = combined_model
                            log.info(f"Found vehicle with combined model+engine at: {start_url}")
                            break
                except Exception as e:
                    log.debug(f"Failed combined {test_url}: {e}")
            
            # Strategy 3: Browse year page and find model that matches
            if not start_url:
                year_url = f"{BASE_URL}/{make_encoded}/{year}/"
                try:
                    response = await page.goto(year_url, timeout=15000)
                    if response and response.status == 200:
                        # Get all model links
                        model_links = await page.query_selector_all("a[href]")
                        for link in model_links:
                            href = await link.get_attribute("href")
                            if href and href.endswith("/"):
                                link_text = await link.inner_text()
                                link_text = link_text.strip()
                                # Check if model matches (starts with, or base model name matches)
                                # e.g., "Liberty Sport" matches "Liberty 2WD V6-3.7L" via base "Liberty"
                                model_base = model.split()[0].lower()  # "Liberty" from "Liberty Sport"
                                link_base = link_text.split()[0].lower()  # "Liberty" from "Liberty 2WD..."
                                if link_text.lower().startswith(model.lower()) or model_base == link_base:
                                    # Found a matching model! Try it
                                    model_encoded = quote(link_text, safe='')
                                    test_url = f"{BASE_URL}/{make_encoded}/{year}/{model_encoded}/Repair%20and%20Diagnosis/"
                                    try:
                                        response = await page.goto(test_url, timeout=15000)
                                        if response and response.status == 200:
                                            title = await page.title()
                                            if "Page Not Found" not in title:
                                                start_url = test_url
                                                final_model = link_text
                                                log.info(f"Found vehicle via partial match '{model}' → '{link_text}' at: {start_url}")
                                                break
                                    except Exception as e:
                                        log.debug(f"Failed partial match {test_url}: {e}")
                except Exception as e:
                    log.debug(f"Failed to browse year page {year_url}: {e}")
            
            if start_url:
                break
        
        if not start_url:
            await browser.close()
            return NavigationResult(
                success=False,
                error=f"Vehicle not found: {vehicle_str}. Check year/make/model spelling."
            )
        
        # Update vehicle string with resolved model
        vehicle_str = f"{year} {make} {final_model}"
        
        await page.wait_for_load_state("networkidle")
        
        # Run AI navigation
        result = await ai_navigate(page, goal, vehicle_str, start_url)
        
        await browser.close()
        
    return result


# For compatibility with existing code
async def query_autodb(goal: str, vehicle: dict, model: str = None) -> NavigationResult:
    """
    Query autodb using AI navigation.
    
    This is the main entry point for the tool.
    """
    log.info(f"=== query_autodb ENTRY POINT ===")
    log.info(f"Goal: {goal}, Vehicle: {vehicle}")
    try:
        result = await navigate_autodb(goal, vehicle)
        log.info(f"=== query_autodb COMPLETE: success={result.success} ===")
        return result
    except Exception as e:
        log.exception(f"=== query_autodb EXCEPTION: {e} ===")
        return NavigationResult(success=False, error=str(e))


if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    async def test():
        vehicle = {
            "year": "2012",
            "make": "Jeep",
            "model": "Liberty 4WD V6-3.7L"
        }
        goal = "charging system operation description"
        
        if len(sys.argv) > 1:
            goal = " ".join(sys.argv[1:])
        
        print(f"Query: {goal}")
        print(f"Vehicle: {vehicle}")
        print("="*60)
        
        result = await navigate_autodb(goal, vehicle)
        
        print(f"\nSuccess: {result.success}")
        print(f"URL: {result.url}")
        print(f"Steps: {result.steps}")
        print(f"Path: {result.path_taken}")
        print(f"\nContent:\n{result.content[:2000] if result.content else result.error}")
    
    asyncio.run(test())
