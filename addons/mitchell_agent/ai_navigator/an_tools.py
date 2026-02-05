"""
Tool implementations for Autonomous Navigator.

Contains all the tool execution logic for clicking, extracting, capturing diagrams, etc.
"""

import base64
import io
import os
import re
import uuid
from typing import Optional

from playwright.async_api import Page

from .logging_config import get_logger, log_trace
from .an_models import ToolResult
from .element_extractor import PageState
from .timing import DELAY_SHORT, DELAY_MEDIUM, DELAY_LONG, DELAY_AJAX, TIMEOUT_CLICK_LONG
from . import action_log

logger = get_logger(__name__)


async def execute_tool(
    tool_name: str, 
    args: dict, 
    page: Page,
    page_state: PageState,
    goal: str,
    path_taken: list = None,
    modal_open: bool = False,
    captured_images: list = None,
    **kwargs,
) -> ToolResult:
    """
    Execute a tool call and return the result.
    
    Args:
        tool_name: Name of the tool to execute
        args: Arguments for the tool
        page: Playwright page
        page_state: Current page state from element extractor
        goal: User's goal/query
        path_taken: Navigation history
        modal_open: Whether a modal is currently open
        captured_images: List to append captured images to (mutable)
        **kwargs: Additional args like collected_data for multi-step collection
        
    Returns:
        ToolResult with success status and result message
    """
    path_taken = path_taken or []
    captured_images = captured_images if captured_images is not None else []
    
    # Get collected_data from kwargs if provided
    collected_data = kwargs.get('collected_data', [])
    
    if tool_name == "where_am_i":
        return _execute_where_am_i(path_taken, modal_open)
    
    elif tool_name == "how_did_i_get_here":
        return _execute_how_did_i_get_here(path_taken)
    
    elif tool_name == "click":
        return await _execute_click(args, page, page_state, goal)
    
    elif tool_name == "extract":
        return await _execute_extract(args, page, goal, captured_images)
    
    elif tool_name == "collect":
        return _execute_collect(args, collected_data)
    
    elif tool_name == "done":
        return _execute_done(args, collected_data, captured_images)
    
    elif tool_name == "search":
        return await _execute_search(args, page, goal)
    
    elif tool_name == "click_text":
        return await _execute_click_text(args, page, goal)
    
    elif tool_name == "go_back":
        return await _execute_go_back(page)
    
    elif tool_name == "prior_page":
        return await _execute_prior_page(page)
    
    elif tool_name == "capture_diagram":
        return await _execute_capture_diagram(args, page, captured_images)
    
    elif tool_name == "expand_all":
        return await _execute_expand_all(page, goal)
    
    elif tool_name == "ask_user":
        return _execute_ask_user(args)
    
    return ToolResult(tool_name, False, f"Unknown tool: {tool_name}")


def _execute_where_am_i(path_taken: list, modal_open: bool) -> ToolResult:
    """Tell the AI where it is - like 'look' in Zork."""
    click_count = len([p for p in path_taken if p["tool"] == "click"])
    location = "LANDING PAGE"
    if click_count > 0:
        last_click = next((p for p in reversed(path_taken) if p["tool"] == "click"), None)
        if last_click:
            location = last_click["args"].get("clicked_text", "unknown section")
    
    modal_status = "inside a MODAL DIALOG" if modal_open else "on the main page"
    return ToolResult("where_am_i", True, 
        f"You are at: {location}\n"
        f"You are {modal_status}.\n"
        f"Depth: {click_count} click(s) from landing page.\n"
        f"{'Use go_back() to close modal before navigating elsewhere.' if modal_open else ''}")


def _execute_how_did_i_get_here(path_taken: list) -> ToolResult:
    """Show the breadcrumb trail."""
    if not path_taken:
        return ToolResult("how_did_i_get_here", True, "You just started. You're at the landing page.")
    
    clicks = [p for p in path_taken if p["tool"] == "click"]
    if not clicks:
        return ToolResult("how_did_i_get_here", True, "You haven't clicked anything yet. You're at the landing page.")
    
    trail = " → ".join([c["args"].get("clicked_text", "?") for c in clicks])
    return ToolResult("how_did_i_get_here", True, f"Your path: LANDING → {trail}")


def _execute_ask_user(args: dict) -> ToolResult:
    """
    Ask the user a question and pause navigation.
    
    Returns a special result that signals the navigator to stop and 
    return the question to the caller. The caller can then pass the
    user's answer back on the next navigation call.
    """
    question = args.get("question", "")
    options = args.get("options", [])
    
    if not question:
        return ToolResult("ask_user", False, "No question provided")
    
    # Format the question with options if provided
    if options:
        options_text = "\n".join([f"  - {opt}" for opt in options])
        full_question = f"{question}\n{options_text}"
    else:
        full_question = question
    
    logger.info(f"    [ask_user] Question: {question}")
    if options:
        logger.info(f"    [ask_user] Options: {options}")
    
    # Return a special result that signals "needs user input"
    result = ToolResult("ask_user", True, full_question)
    result.needs_user_input = True
    result.question = question
    result.options = options
    return result


def _execute_collect(args: dict, collected_data: list) -> ToolResult:
    """
    Collect data and continue navigating.
    
    Stores the data in collected_data list (mutable) so it accumulates
    across multiple collect() calls. The AI can then call done() to
    combine everything.
    """
    data = args.get("data", "")
    label = args.get("label", f"Item {len(collected_data) + 1}")
    
    if not data:
        return ToolResult("collect", False, "No data provided to collect")
    
    # Normalize data
    if isinstance(data, str):
        data = data.replace('\\n', '\n').replace('\\t', '\t').strip()
    
    # Store with label
    collected_data.append({
        "label": label,
        "data": data
    })
    
    # Log the extract action
    data_preview = data[:80].replace('\n', ' ') if len(data) > 80 else data.replace('\n', ' ')
    action_log.log_extract(label, data_preview)
    
    logger.info(f"    [collect] Stored '{label}': {len(data)} chars (total items: {len(collected_data)})")
    return ToolResult("collect", True, 
        f"Collected '{label}' ({len(data)} chars). You have {len(collected_data)} item(s) stored. "
        f"Continue navigating to collect more, or call done() when finished.")


def _execute_done(args: dict, collected_data: list, captured_images: list) -> ToolResult:
    """
    Signal completion and combine all collected data.
    
    Combines all items from collected_data into a single result.
    """
    summary = args.get("summary", "Data collection complete")
    
    if not collected_data and not captured_images:
        return ToolResult("done", False, 
            "No data collected! Use collect() to store data before calling done().")
    
    # Combine all collected data
    combined_parts = []
    for item in collected_data:
        label = item.get("label", "")
        data = item.get("data", "")
        if label:
            combined_parts.append(f"=== {label} ===\n{data}")
        else:
            combined_parts.append(data)
    
    combined = "\n\n".join(combined_parts)
    
    # Include image count in result
    img_note = ""
    if captured_images:
        img_note = f" (+ {len(captured_images)} diagram(s))"
    
    logger.info(f"    [done] Combined {len(collected_data)} items{img_note}")
    return ToolResult("done", True, combined)


async def _execute_click(args: dict, page: Page, page_state: PageState, goal: str) -> ToolResult:
    """Click on an element by ID."""
    element_id = args.get("element_id")
    # Handle string IDs (LLM might return "[22]" instead of just "22")
    if isinstance(element_id, str):
        element_id = element_id.strip('[]')
        element_id = int(element_id)
    
    element = next((e for e in page_state.elements if e.id == element_id), None)
    
    if not element:
        return ToolResult("click", False, f"Element {element_id} not found. Available IDs: {[e.id for e in page_state.elements[:10]]}")
    
    # GUARD: Don't click on diagram images - use capture_diagram() instead!
    if element.text:
        text_lower = element.text.lower()
        if 'fig' in text_lower and ('diagram' in goal.lower() or 'wiring' in goal.lower()):
            return ToolResult("click", False, 
                f"STOP! Don't click on '{element.text[:40]}' - that opens a viewer. "
                f"You're already on the diagram page! Use capture_diagram() NOW to save the image.")
    
    try:
        # Use the element's actual selector
        if element.selector:
            el = page.locator(element.selector).first
        else:
            # Build selector from element info
            if element.text:
                el = page.locator(f'{element.tag}:has-text("{element.text}")').first
            else:
                return ToolResult("click", False, f"No selector for element {element_id}")
        
        await el.click(timeout=TIMEOUT_CLICK_LONG)
        await page.wait_for_timeout(DELAY_LONG)
        
        # Log the successful click action
        action_log.log_click(element_id, element.text or "", args.get("reason", ""))
        
        return ToolResult("click", True, f"Clicked '{element.text}'. Page may have updated.")
            
    except Exception as e:
        action_log.log_error(f"Click [{element_id}] failed: {e}")
        return ToolResult("click", False, f"Click failed: {e}")


async def _execute_extract(args: dict, page: Page, goal: str, captured_images: list = None) -> ToolResult:
    """Extract data from the current page."""
    data = args.get("data", "")
    
    # Normalize data - convert literal \n to newlines, strip extra whitespace
    if isinstance(data, str):
        data = data.replace('\\n', '\n').replace('\\t', '\t').strip()
    
    # Allow "DATA NOT FOUND" responses - this is valid!
    if data.upper().startswith("DATA NOT FOUND"):
        return ToolResult("extract", True, data)
    
    # Get full page text
    page_text = await page.evaluate('() => document.body.innerText')
    
    # DISABLED: extract tool is deprecated. Use collect() + done() instead.
    # The code is left here for reference but will not be called by the AI.
    return ToolResult("extract", False, "extract() is disabled. Use collect() + done() instead.")
    
    # AUTO-EXTRACT: For parts/labor queries, grab data from rightPane
    if 'parts' in goal.lower() or 'labor' in goal.lower() or 'alternator' in goal.lower() or 'starter' in goal.lower():
        # Check if we're on an Estimate Guide detail page (has rightPane with parts/labor data)
        right_pane = page.locator('.rightPane')
        if await right_pane.count() > 0:
            # EXPAND ALL parts items first to reveal part numbers and prices
            # Parts items load their details on click - check for empty details divs
            parts_items = page.locator('#partDetails li.item')
            parts_count = await parts_items.count()
            if parts_count > 0:
                logger.info(f"    [extract] Found {parts_count} parts items, expanding any with empty details...")
                for i in range(parts_count):
                    item = parts_items.nth(i)
                    details = item.locator('.details')
                    if await details.count() > 0:
                        details_html = await details.evaluate('(el) => el.innerHTML')
                        if len(details_html.strip()) < 20:  # Empty or minimal content
                            try:
                                header = item.locator('.itemCollapsableHeader')
                                await header.click()
                                await page.wait_for_timeout(DELAY_AJAX)  # Wait for AJAX load
                                logger.info(f"    [extract] Expanded parts item {i}")
                            except Exception as e:
                                logger.debug(f"    [extract] Could not expand parts item {i}: {e}")
            
            rp_text = await right_pane.evaluate('(el) => el.innerText')
            # Check if it has parts/labor data indicators
            if rp_text and ('PART' in rp_text.upper() or 'LABOR' in rp_text.upper()):
                # Clean up and format the text
                lines = [line.strip() for line in rp_text.split('\n') if line.strip()]
                # Filter out UI elements but keep all data
                data_lines = []
                skip_exact = ['add', 'close', 'print', 'back', 'home', 'search', 'menu', '-', '+']
                for line in lines:
                    line_lower = line.lower()
                    # Skip single-word UI elements and short noise
                    if len(line) > 2 and line_lower not in skip_exact and 'view quote' not in line_lower:
                        data_lines.append(line)
                
                if data_lines:
                    # No line limit - grab all parts/labor data
                    full_data = '\n'.join(data_lines)
                    
                    logger.info(f"    [extract] Auto-extracted {len(data_lines)} lines of parts/labor data")
                    return ToolResult("extract", True, full_data)
    
    # AUTO-EXTRACT: For TSB queries, grab the TSB list from modal
    tsb_keywords = ['tsb', 'technical service bulletin', 'bulletin', 'recall']
    if any(kw in goal.lower() for kw in tsb_keywords):
        modal = page.locator('.modalDialogView')
        if await modal.count() > 0:
            # Check if this is a "list all TSBs" request vs a specific category request
            goal_lower = goal.lower()
            wants_list = any(x in goal_lower for x in ['any tsb', 'are there any', 'tsbs for', 'list of tsb', 'all tsb', 'what tsb'])
            
            # IMPORTANT: Check if AI passed actual TSB DETAIL content (not just a title)
            # If data contains TSB detail markers, skip auto-extraction and return it directly
            data_lower = data.lower()
            is_tsb_detail = any(marker in data_lower for marker in [
                'technical service bulletin',
                'reference number',
                'date of issue',
                'overview',
                'discussion',
                'subject\n',
                'models\n'
            ])
            if is_tsb_detail:
                # AI has extracted TSB detail content - but it may be truncated!
                # Grab the FULL modal content to ensure we get complete TSB text
                full_modal_text = await modal.inner_text()
                if full_modal_text and len(full_modal_text) > 100:
                    # Clean up the text - remove excessive whitespace
                    lines = [line.strip() for line in full_modal_text.split('\n') if line.strip()]
                    # Filter out UI elements
                    skip_patterns = ['back', 'print', 'close', '[x]', '×']
                    clean_lines = [line for line in lines if line.lower() not in skip_patterns and len(line) > 1]
                    full_data = '\n'.join(clean_lines)
                    logger.info(f"    [extract] TSB detail - grabbed full modal content ({len(full_data)} chars)")
                    return ToolResult("extract", True, full_data)
                else:
                    # Modal text isn't long enough, use what AI passed
                    logger.info(f"    [extract] TSB detail content detected ({len(data)} chars), returning as-is")
                    return ToolResult("extract", True, data)
            
            # Always try to get categories first - they show the full TSB overview
            categories = await modal.evaluate('''(el) => {
                const cats = [];
                const nodes = el.querySelectorAll('li.usercontrol.node');
                for (const node of nodes) {
                    const link = node.querySelector('a');
                    if (link) {
                        const text = link.textContent.trim();
                        // Parse "Category Name (count)" format
                        const match = text.match(/^(.+?)\\s*\\((\\d+)\\)$/);
                        if (match) {
                            cats.push({ category: match[1].trim(), count: parseInt(match[2], 10) });
                        }
                    }
                }
                return cats;
            }''')
            
            # If we found categories and user wants a list, return categories
            if categories and len(categories) > 0 and wants_list:
                total = sum(cat['count'] for cat in categories)
                # Format as a direct answer, not reference material
                lines = [f"Yes, there are {total} Technical Service Bulletins for this vehicle:\n"]
                for cat in categories:
                    lines.append(f"- **{cat['category']}**: {cat['count']}")
                lines.append(f"\nWould you like details on any specific category?")
                full_data = '\n'.join(lines)
                
                logger.info(f"    [extract] Auto-extracted {len(categories)} TSB categories, {total} total TSBs")
                return ToolResult("extract", True, full_data)
            
            # Otherwise check for table data (user clicked into a specific category)
            table = modal.locator('table')
            if await table.count() > 0:
                # Extract TSB rows from the table
                tsb_data = await modal.evaluate('''(el) => {
                    const table = el.querySelector('table');
                    if (!table) return null;
                    
                    const tsbs = [];
                    const rows = table.querySelectorAll('tr');
                    
                    // Skip header row (index 0)
                    for (let i = 1; i < rows.length; i++) {
                        const cells = rows[i].querySelectorAll('td');
                        if (cells.length >= 2) {
                            const oem_ref = cells[0]?.innerText?.trim() || '';
                            const title = cells[1]?.innerText?.trim() || '';
                            const pub_date = cells[2]?.innerText?.trim() || '';
                            if (title) {
                                tsbs.push({ oem_ref, title, pub_date });
                            }
                        }
                    }
                    return tsbs;
                }''')
                
                if tsb_data and len(tsb_data) > 0:
                    # Format as readable list
                    lines = [f"**Technical Service Bulletins ({len(tsb_data)} found)**\n"]
                    for tsb in tsb_data:
                        oem = tsb.get('oem_ref', '')
                        title = tsb.get('title', '')
                        date = tsb.get('pub_date', '')
                        if date:
                            lines.append(f"- **{oem}**: {title} ({date})")
                        else:
                            lines.append(f"- **{oem}**: {title}")
                    
                    lines.append("\n*Ask about a specific TSB by title for more details.*")
                    full_data = '\n'.join(lines)
                    
                    logger.info(f"    [extract] Auto-extracted {len(tsb_data)} TSBs from table")
                    return ToolResult("extract", True, full_data)
            
            # Fallback: return categories if we have them
            if categories and len(categories) > 0:
                total = sum(cat['count'] for cat in categories)
                # Format as a direct answer, not reference material
                lines = [f"Yes, there are {total} Technical Service Bulletins for this vehicle:\n"]
                for cat in categories:
                    lines.append(f"- **{cat['category']}**: {cat['count']}")
                lines.append(f"\nWould you like details on any specific category?")
                full_data = '\n'.join(lines)
                
                logger.info(f"    [extract] Auto-extracted {len(categories)} TSB categories, {total} total TSBs")
                return ToolResult("extract", True, full_data)
    
    # OPTION 1: Trust the AI - it navigated to the right page and is reporting what it sees.
    # No verbatim validation - the AI may format/summarize data differently than raw page text.
    # We keep sanity checks below to catch obviously wrong data types (e.g., torque for gap).
    
    # Validate it looks like real spec data (has units or is a meaningful value)
    has_units = bool(re.search(r'\b(in|inch|mm|ft|lb|lbs|n\.?m|oz|qt|gal|psi|rpm|°|degrees?)\b', data.lower()))
    has_range = bool(re.search(r'\d+\s*[-–]\s*\d+', data))  # e.g., "0.028-0.032"
    has_decimal = bool(re.search(r'\d+\.\d+', data))  # e.g., "0.028"
    is_short_number = bool(re.match(r'^[\d,\.]+$', data.strip()))  # Just a number like "38,744"
    is_just_words = bool(re.match(r'^[a-zA-Z\s]+$', data.strip()))  # Just words like "spark Plug"
    
    # SANITY CHECK: Does this make sense for the goal?
    goal_lower = goal.lower()
    data_lower = data.lower()
    
    # DTC CODE CHECK: For DTC lookups, accept any data containing the DTC code pattern
    # or DTC descriptor text
    dtc_match = re.search(r'[pPbBcCuU]\d{4}', data)
    if dtc_match:
        # Data contains a valid DTC code (P0300, B1234, C0123, U0100, etc.)
        return ToolResult("extract", True, data)
    
    # Also accept DTC descriptor text if the goal is asking for a DTC code
    goal_dtc = re.search(r'[pPbBcCuU]\d{4}', goal)
    if goal_dtc and ('descriptor' in data_lower or 'evap' in data_lower or 'emission' in data_lower or 'misfire' in data_lower):
        return ToolResult("extract", True, data)
    
    # CONNECTOR/PINOUT CHECK: For connector requests, accept structured connector data
    if 'connector' in goal_lower or 'pinout' in goal_lower:
        # Accept connector-type data
        if any(x in data_lower for x in ['way', 'connector', 'oem', 'service', 'terminal', 'pin']):
            return ToolResult("extract", True, data)
    
    # DIAGRAM CHECK: If looking for a diagram, don't use extract - use capture_diagram!
    if 'diagram' in goal_lower or 'wiring' in goal_lower:
        if 'fig' in data_lower or 'diagram' in data_lower or 'circuit' in data_lower:
            return ToolResult("extract", False,
                f"You found a DIAGRAM ('{data}'). Don't use extract() for diagrams! "
                f"Use capture_diagram() instead to save the image.")
    
    # Gap measurements should be in inches or mm, NOT torque (ft-lb, N.m)
    if 'gap' in goal_lower:
        if 'ft' in data_lower or 'lb' in data_lower or 'n.m' in data_lower or 'n m' in data_lower:
            return ToolResult("extract", False, 
                f"SANITY CHECK FAILED: '{data}' is a TORQUE value (ft-lb/N.m), but you're looking for a GAP measurement. "
                f"Gaps are measured in INCHES or MM (like '0.028 in' or '0.70 mm'). Keep looking!")
    
    # Torque should be in ft-lb or N.m, NOT length (in, mm)
    if 'torque' in goal_lower:
        if not ('ft' in data_lower or 'lb' in data_lower or 'n.m' in data_lower or 'n m' in data_lower):
            return ToolResult("extract", False,
                f"SANITY CHECK FAILED: '{data}' doesn't look like torque. "
                f"Torque is measured in FT-LB or N.m. Keep looking!")
    
    # Capacity should be in quarts, liters, oz, etc.
    if 'capacity' in goal_lower or 'fluid' in goal_lower:
        if not any(u in data_lower for u in ['qt', 'quart', 'liter', 'l', 'oz', 'gal', 'pt', 'pint']):
            if 'ft' in data_lower or 'lb' in data_lower:
                return ToolResult("extract", False,
                    f"SANITY CHECK FAILED: '{data}' looks like torque, not fluid capacity. "
                    f"Capacity is in QUARTS, LITERS, or OZ. Keep looking!")
    
    if is_short_number and not has_units:
        return ToolResult("extract", False, f"'{data}' looks like a count, not a specification. Look for values with UNITS like '0.028 in' or '25 N.m'")
    
    if is_just_words:
        return ToolResult("extract", False, f"'{data}' is just a label/name. Look for ACTUAL VALUES with numbers and units, like 'Gap 0.028 in (0.70 mm)'")
    
    if not (has_units or has_decimal or has_range):
        return ToolResult("extract", False, f"'{data}' doesn't look like spec data. Find values with units (in, mm, N.m) or decimal numbers.")
    
    return ToolResult("extract", True, data)


async def _execute_search(args: dict, page: Page, goal: str) -> ToolResult:
    """Use the 1Search feature."""
    search_text = args.get("text", goal)
    try:
        # Look for 1Search input - ShopKeyPro uses specific placeholder
        search_input = page.locator(
            'input[placeholder*="Codes"], '
            'input[placeholder*="Components"], '
            'input[placeholder*="Symptoms"], '
            'input[placeholder*="Search"], '
            '#searchInput, '
            '.searchBox input'
        )
        if await search_input.count() > 0:
            await search_input.first.click()
            await search_input.first.fill(search_text)
            await page.wait_for_timeout(DELAY_LONG)
            await search_input.first.press("Enter")
            await page.wait_for_timeout(DELAY_LONG)
            return ToolResult("search", True, f"Searched for '{search_text}'. Check results.")
        else:
            return ToolResult("search", False, "Could not find search input on this page. Try clicking on a navigation element instead.")
    except Exception as e:
        return ToolResult("search", False, f"Search failed: {e}")


async def _execute_click_text(args: dict, page: Page, goal: str) -> ToolResult:
    """Click on an element by its text content."""
    text = args.get("text", "")
    reason = args.get("reason", "")
    
    # GUARD: Don't click on diagram images - use capture_diagram() instead!
    text_lower = text.lower()
    if 'fig' in text_lower and ('diagram' in goal.lower() or 'wiring' in goal.lower()):
        return ToolResult("click_text", False, 
            f"STOP! Don't click on '{text[:40]}' - that opens a viewer. "
            f"You're already on the diagram page! Use capture_diagram() NOW to save the image.")
    
    try:
        # Try to find and click element by text content
        # IMPORTANT: Use :text-is() for exact match, NOT :has-text() which matches descendants
        # Priority order: exact match on specific tags, then fallback to contains
        locators = [
            # Modal-specific first (exact text match)
            page.locator(f'.modalDialogView a:text-is("{text}")'),
            page.locator(f'.modalDialogView li:text-is("{text}")'),
            page.locator(f'.modalDialogView span:text-is("{text}")'),
            page.locator(f'.modalDialogView h2:text-is("{text}")'),
            # Then page-wide with exact text match on common clickable elements
            page.locator(f'a:text-is("{text}")'),
            page.locator(f'li:text-is("{text}")'),
            page.locator(f'h2:text-is("{text}")'),  # Estimate Guide operations use <h2>
            page.locator(f'span:text-is("{text}")'),
            page.locator(f'div:text-is("{text}")'),
            # Fallback to contains but ONLY for links and buttons (leaf elements)
            page.locator(f'.modalDialogView a:has-text("{text}")'),
            page.locator(f'a:has-text("{text}")'),
            page.locator(f'button:has-text("{text}")'),
        ]
        
        for i, loc in enumerate(locators):
            count = await loc.count()
            if count > 0:
                # Log which locator matched
                logger.info(f"    [click_text] Locator #{i} matched {count} element(s), clicking first")
                await loc.first.click(timeout=TIMEOUT_CLICK_LONG)
                await page.wait_for_timeout(DELAY_LONG)
                
                # Log the successful click_text action
                action_log.log_click_text(text, reason)
                
                return ToolResult("click_text", True, f"Clicked '{text}'. Page may have updated.")
        
        action_log.log_error(f"click_text '{text}' not found")
        return ToolResult("click_text", False, f"Could not find clickable element with text '{text}'. Use click(element_id) with an ID from the element list instead.")
    except Exception as e:
        action_log.log_error(f"click_text '{text}' failed: {e}")
        return ToolResult("click_text", False, f"Click failed: {e}")


async def _execute_go_back(page: Page) -> ToolResult:
    """Close the modal and return to main page."""
    try:
        # Check if we're in a modal first
        modal = page.locator('.modalDialogView')
        if await modal.count() > 0:
            close_btn = page.locator('.modalDialogView .close, .modal .close, button:has-text("Close")')
            btn_count = await close_btn.count()
            logger.info(f"    [go_back] Found {btn_count} close buttons in modal")
            if btn_count > 0:
                await close_btn.first.click(timeout=TIMEOUT_CLICK_LONG)
                await page.wait_for_timeout(DELAY_LONG)
                action_log.log_close_modal()
                return ToolResult("go_back", True, "Closed modal. Back to previous view.")
        
        page_text = await page.inner_text('body')
        
        # If on Search Results page → Home takes us back to landing
        if 'Search Results' in page_text and 'SEARCH RESULTS FOR' in page_text:
            home_link = page.locator('a:text-is("Home")')
            if await home_link.count() > 0:
                await home_link.first.click(timeout=TIMEOUT_CLICK_LONG)
                await page.wait_for_timeout(DELAY_LONG)
                return ToolResult("go_back", True, "Clicked Home. Back to landing page.")
        
        # If on MODULE page (accidentally) → click 1SEARCH PLUS to get to landing
        if 'SELECT MODULE' in page_text or 'Product Training Center' in page_text:
            onesearch = page.locator('a:has-text("1SEARCH"), #oneSearchPlusAccess')
            if await onesearch.count() > 0:
                await onesearch.first.click(timeout=TIMEOUT_CLICK_LONG)
                await page.wait_for_timeout(DELAY_LONG)
                return ToolResult("go_back", True, "Clicked 1SEARCH PLUS. Back to landing page.")
        
        # Fallback: close any modal as go_back is for exiting modals
        logger.info(f"    [go_back] No modal found, nothing to close")
        return ToolResult("go_back", True, "No modal to close. Already on main page.")
    except Exception as e:
        logger.error(f"    [go_back] Error: {e}")
        return ToolResult("go_back", False, f"Go back failed: {e}")


async def _execute_prior_page(page: Page) -> ToolResult:
    """Go back to previous page - prefer in-modal Back link over browser back."""
    try:
        # Safety check: don't go back if we're already at landing/login page
        current_url = page.url
        if "login" in current_url.lower() or "auth" in current_url.lower():
            return ToolResult("prior_page", False, "Already at login page - cannot go back further!")
        
        # Check if modal is open
        modal_open_before = await page.locator('.modalDialogView').count() > 0
        
        # STRATEGY: ShopKeyPro uses AJAX navigation inside modals, so browser back
        # often doesn't work. Instead, look for the "Back" breadcrumb link.
        back_link_clicked = False
        if modal_open_before:
            # Try to find and click the Back breadcrumb link inside the modal
            # It appears as a link with text "Back" in the breadcrumb area
            back_selectors = [
                '.modalDialogView a:has-text("Back")',
                '.modalDialogView .breadcrumb a:first-child',
                '.modalDialogView a.back',
                '.modalDialogView [class*="back"]',
            ]
            for selector in back_selectors:
                try:
                    back_link = page.locator(selector).first
                    if await back_link.count() > 0 and await back_link.is_visible():
                        logger.info(f"    [prior_page] Found Back link with selector: {selector}")
                        await back_link.click()
                        await page.wait_for_timeout(DELAY_LONG)
                        back_link_clicked = True
                        break
                except Exception as e:
                    logger.debug(f"    [prior_page] Selector {selector} failed: {e}")
                    continue
        
        # If no Back link found, fall back to browser back
        if not back_link_clicked:
            logger.info(f"    [prior_page] No Back link found, using browser back (modal_open={modal_open_before})")
            await page.go_back()
            await page.wait_for_timeout(DELAY_LONG)
        
        # Check where we landed
        new_url = page.url
        modal_open_after = await page.locator('.modalDialogView').count() > 0
        
        # Log the go_back action
        action_log.log_go_back("prior_page")
        
        # Detect if we went too far (out of ShopKeyPro main area)
        if "login" in new_url.lower() or "auth" in new_url.lower():
            # Try to go forward again
            await page.go_forward()
            await page.wait_for_timeout(DELAY_LONG)
            return ToolResult("prior_page", False, "STOP! Going back further would exit ShopKeyPro. Try a different approach.")
        
        # Provide context about where we are now
        page_text = await page.evaluate('() => document.body.innerText.substring(0, 500)')
        
        # Check if we're now at section selector (has multiple "X OF 3" as clickable items)
        # vs still inside connector list (has "X OF 3" only as breadcrumb)
        section_selector_visible = False
        if modal_open_after:
            # Look for section selector links (they have specific structure)
            section_links = await page.locator('.modalDialogView a:has-text("OF 3")').count()
            if section_links >= 2:  # Multiple section links = section selector
                section_selector_visible = True
        
        # Detect page type for helpful feedback
        if section_selector_visible:
            return ToolResult("prior_page", True, "Back to Wiring Diagrams section selector! You can now click SECTION 2 OF 3 or SECTION 3 OF 3 to search there.")
        elif "SYSTEM WIRING DIAGRAMS" in page_text and modal_open_after:
            return ToolResult("prior_page", True, "Back to Wiring Diagrams menu. Pick a category or section.")
        elif modal_open_after:
            return ToolResult("prior_page", True, "Still in modal. Check elements list for navigation options.")
        elif not modal_open_after and modal_open_before:
            return ToolResult("prior_page", True, "Modal closed - now on main page. Click Wiring Diagrams again if needed.")
        else:
            return ToolResult("prior_page", True, "Page changed. Check PAGE TEXT to see where you are.")
            
    except Exception as e:
        logger.error(f"    [prior_page] Error: {e}")
        return ToolResult("prior_page", False, f"Prior page failed: {e}")


async def _execute_capture_diagram(args: dict, page: Page, captured_images: list) -> ToolResult:
    """Capture a diagram/image from the current page."""
    description = args.get("description", "diagram")
    try:
        local_captured = []
        
        # First try: Extract SVG from object.clsArticleSvg elements
        svg_data = await page.evaluate('''() => {
            const svgObjects = document.querySelectorAll('object.clsArticleSvg');
            const results = [];
            for (const obj of svgObjects) {
                try {
                    const svgDoc = obj.contentDocument;
                    if (svgDoc && svgDoc.documentElement) {
                        results.push(svgDoc.documentElement.outerHTML);
                    }
                } catch (e) {
                    console.error('Error extracting SVG:', e);
                }
            }
            return results;
        }''')
        
        if svg_data:
            # Convert SVGs to PNGs and encode as base64
            try:
                import cairosvg
                from PIL import Image
                
                for i, svg in enumerate(svg_data):
                    # Convert SVG to PNG
                    png_data = cairosvg.svg2png(bytestring=svg.encode('utf-8'), output_width=1200)
                    
                    # Composite onto white background to remove transparency
                    img = Image.open(io.BytesIO(png_data))
                    if img.mode == 'RGBA':
                        # Create white background
                        white_bg = Image.new('RGB', img.size, (255, 255, 255))
                        # Paste image onto white background using alpha as mask
                        white_bg.paste(img, mask=img.split()[3])
                        img = white_bg
                    
                    # Convert back to bytes
                    output = io.BytesIO()
                    img.save(output, format='PNG')
                    png_with_bg = output.getvalue()
                    
                    b64_data = base64.b64encode(png_with_bg).decode('utf-8')
                    local_captured.append({
                        "name": f"{description} (Part {i+1})" if len(svg_data) > 1 else description,
                        "base64": b64_data,
                        "mime_type": "image/png"
                    })
                    logger.info(f"    [capture_diagram] Converted SVG {i+1} to PNG with white bg ({len(png_with_bg)} bytes)")
            except ImportError as e:
                logger.warning(f"    [capture_diagram] cairosvg/PIL not available: {e}, saving raw SVGs")
                for i, svg in enumerate(svg_data):
                    b64_data = base64.b64encode(svg.encode('utf-8')).decode('utf-8')
                    local_captured.append({
                        "name": f"{description} (Part {i+1})" if len(svg_data) > 1 else description,
                        "base64": b64_data,
                        "mime_type": "image/svg+xml"
                    })
        else:
            # Second try: Capture images from imageHolder containers
            # ShopKeyPro displays images as thumbnails (300x225) but the actual image
            # is loaded at full resolution (e.g., 2130x1595). We use canvas to draw
            # the image scaled to a readable size (max 1200px width).
            modal = page.locator('.modalDialogView')
            if await modal.count() > 0:
                # Use canvas to capture scaled images (works with browser auth)
                img_data = await modal.evaluate('''(modal) => {
                    const holders = modal.querySelectorAll('.imageHolder img');
                    const results = [];
                    const MAX_WIDTH = 900;  // Cap width for reasonable display size
                    
                    for (const img of holders) {
                        // Only include actual diagram images (reasonable size)
                        if (img.naturalWidth < 100 || img.naturalHeight < 100) continue;
                        
                        const caption = img.closest('.imageHolder')?.querySelector('.imageCaption')?.textContent?.trim();
                        
                        // Scale down if wider than MAX_WIDTH, maintaining aspect ratio
                        let targetWidth = img.naturalWidth;
                        let targetHeight = img.naturalHeight;
                        if (targetWidth > MAX_WIDTH) {
                            const scale = MAX_WIDTH / targetWidth;
                            targetWidth = MAX_WIDTH;
                            targetHeight = Math.round(img.naturalHeight * scale);
                        }
                        
                        // Draw to canvas at scaled size
                        const canvas = document.createElement('canvas');
                        canvas.width = targetWidth;
                        canvas.height = targetHeight;
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(img, 0, 0, targetWidth, targetHeight);
                        
                        // Export as JPEG data URL
                        const dataUrl = canvas.toDataURL('image/jpeg', 0.95);
                        
                        results.push({
                            caption: caption || '',
                            width: targetWidth,
                            height: targetHeight,
                            dataUrl: dataUrl
                        });
                    }
                    return results;
                }''')
                
                for i, info in enumerate(img_data):
                    data_url = info['dataUrl']
                    if data_url.startswith('data:image/jpeg;base64,'):
                        b64_data = data_url.split(',')[1]
                        name = info['caption'] or f"{description} (Part {i+1})"
                        local_captured.append({
                            "name": name,
                            "base64": b64_data,
                            "mime_type": "image/jpeg"
                        })
                        logger.info(f"    [capture_diagram] Captured image {i+1}: {info['width']}x{info['height']} ({len(b64_data)*3//4} bytes)")
                    else:
                        logger.warning(f"    [capture_diagram] Unexpected data URL format for image {i+1}")
        
        if not local_captured:
            return ToolResult("capture_diagram", False, "No diagrams found on this page. Navigate to a wiring diagram or connector view first.")
        
        # Append to the mutable captured_images list
        captured_images.extend(local_captured)
        
        # Log the capture action
        action_log.log_capture_diagram(description, success=True)
        
        return ToolResult("capture_diagram", True, 
            f"Captured {len(local_captured)} wiring diagram(s). The diagrams contain wire colors, pin numbers, connector IDs, and component locations. Refer to the images for specific values.")
            
    except Exception as e:
        logger.error(f"    [capture_diagram] Error: {e}")
        return ToolResult("capture_diagram", False, f"Failed to capture diagram: {e}")


async def _execute_expand_all(page: Page, goal: str) -> ToolResult:
    """Expand all collapsed content on the current page, including nested items."""
    try:
        # Try to expand all collapsed content in modal or page
        modal = page.locator('.modalDialogView')
        target = modal if await modal.count() > 0 else page
        
        # Multiple passes to handle nested collapsible items
        total_expanded = 0
        max_passes = 5  # Prevent infinite loops
        
        for pass_num in range(max_passes):
            # Use JavaScript to expand BOTH:
            # 1. showContentIcon elements (DTC Index, TSBs)
            # 2. Tree branch nodes (Component Tests, Service Manual)
            expanded = await target.evaluate('''(el) => {
                let clicked = 0;
                
                // 1. ShopKeyPro showContentIcon elements
                const icons = el.querySelectorAll('.showContentIcon');
                icons.forEach(icon => {
                    if (icon.classList.contains('showAll') || 
                        icon.classList.contains('show') ||
                        !icon.classList.contains('hideAll')) {
                        icon.click();
                        clicked++;
                    }
                });
                
                // 2. Tree branch nodes (Component Tests uses li.node.branch)
                // Only expand branches that are NOT already open
                const branches = el.querySelectorAll('li.node.branch:not(.open), li.usercontrol.node.branch:not(.open)');
                branches.forEach(branch => {
                    // Click the expander or the link inside
                    const expander = branch.querySelector('.expander, span.toggle, > a');
                    if (expander) {
                        expander.click();
                        clicked++;
                    }
                });
                
                return clicked;
            }''')
            
            if expanded == 0:
                break  # No more items to expand
                
            total_expanded += expanded
            logger.info(f"    [expand_all] Pass {pass_num + 1}: Expanded {expanded} items")
            await page.wait_for_timeout(DELAY_LONG)  # Wait for content to load
        
        expanded = total_expanded
        
        if expanded > 0:
            logger.info(f"    [expand_all] Expanded {expanded} items")
            await page.wait_for_timeout(DELAY_LONG)
            
            # Just report what was expanded - let AI click and collect
            return ToolResult("expand_all", True, 
                f"Expanded {expanded} sections. Look in PAGE TEXT for your target, then use click_text() to navigate and collect() + done() to get the data.")
        else:
            return ToolResult("expand_all", False, "No expandable content found on this page.")
            
    except Exception as e:
        logger.error(f"    [expand_all] Error: {e}")
        return ToolResult("expand_all", False, f"Failed to expand: {e}")
