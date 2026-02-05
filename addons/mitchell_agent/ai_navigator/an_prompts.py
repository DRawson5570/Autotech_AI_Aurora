"""
Prompt builders for Autonomous Navigator.

Contains system prompt and user message construction.
"""

import re
from typing import List, Optional

from .element_extractor import PageState


def build_system_prompt(goal: str, vehicle: dict, context: str = "") -> str:
    """
    Build the system prompt with navigation paths.
    
    Args:
        context: Optional conversation context from prior messages
    """
    # Detect connector type from goal to give explicit instruction
    goal_lower = goal.lower()
    connector_hint = ""
    
    # Check for C### connector pattern (C205, C102A, C1979, etc.) or "connector" in query
    c_connector_match = re.search(r'\bc(\d+[a-z]?)\b', goal_lower)
    if c_connector_match or ('connector' in goal_lower and 'end' in goal_lower):
        connector_hint = "\n*** Your search term is located in one of the links that contain connector end views. ***\n"
    elif any(x in goal_lower for x in ['body harness', 'harness to', 'x200', 'x310', 'x400']):
        connector_hint = "\n*** YOUR GOAL REQUIRES INLINE HARNESS CONNECTOR - NOT COMPONENT! ***\n"
    elif any(x in goal_lower for x in ['a11', 'k20', 'radio', 'ecm', 'module']):
        connector_hint = "\n*** YOUR GOAL REQUIRES COMPONENT CONNECTOR ***\n"
    
    # Add a hint for DTC codes - use search directly
    dtc_match = re.search(r'[PBCUpbcu]\d{4}', goal)
    dtc_hint = ""
    if dtc_match:
        dtc_code = dtc_match.group().upper()
        dtc_hint = f"\n*** DTC CODE: {dtc_code} → Use search('{dtc_code}') → click the search result → click the first VIEW CARD (e.g., 'OEM Testing') → collect() + done() ***\n"
    
    # Add hint for TSB list requests - don't drill down, just collect the list
    tsb_hint = ""
    if any(x in goal_lower for x in ['any tsb', 'are there any tsb', 'tsbs for', 'list of tsb', 'all tsb']):
        tsb_hint = "\n*** TSB LIST REQUEST - Go to Technical Bulletins, then collect() the FULL TABLE + done(). Do NOT click individual TSBs! ***\n"
    
    # Add hint for SPECIFIC TSB lookup - use context to find the category, don't expand_all
    specific_tsb_match = re.search(r'\b\d{2}-\d{3}-\d{2}\b', goal)
    if specific_tsb_match:
        tsb_number = specific_tsb_match.group()
        # Check if we know the category from context
        category_hint = ""
        if context:
            # Common TSB category names
            tsb_categories = [
                'body interior', 'engine control', 'transmission', 'electrical',
                'air bag', 'srs', 'cooling', 'fuel', 'brakes', 'suspension',
                'steering', 'hvac', 'climate', 'accessories', 'infotainment',
                'recalls', 'seats', 'exterior', 'wheels', 'tire'
            ]
            context_lower = context.lower()
            for cat in tsb_categories:
                if cat in context_lower:
                    category_hint = f" (look in '{cat.title()}' category)"
                    break
        tsb_hint = f"\n*** SPECIFIC TSB: {tsb_number}{category_hint} - Go to Technical Bulletins → click the CATEGORY containing this TSB → click the TSB number or title → collect() + done() ***\n"
    
    # Add conversation context if provided
    context_section = ""
    if context:
        context_section = f"""
{context}
NOTE: The vehicle above has already been selected. Just focus on finding the data for the current query.
"""
    
    return f"""You are a navigation AI for ShopKeyPro automotive data.

VEHICLE: {vehicle.get('year')} {vehicle.get('make')} {vehicle.get('model')} {vehicle.get('engine', '')}
GOAL: Find "{goal}"
{context_section}{connector_hint}{dtc_hint}{tsb_hint}
TOOLS:
- click(element_id, reason) - Click an element by ID
- click_text(text, reason) - Click on text visible in PAGE TEXT
- collect(label, data) - Store data and CONTINUE navigating (use when gathering multiple items)
- done(summary) - Signal you're FINISHED collecting - returns all collected data
- capture_diagram(description) - Save a wiring diagram or connector image
- search(text) - Use 1Search to find specific items (connector numbers, part numbers, DTC codes)
- prior_page(reason) - Go back to prior page (browser back). Use when searching through multiple sections/pages.
- go_back(reason) - Close modal entirely and return to main page. Use when DONE with modal.
- expand_all() - Expand all collapsed/hidden content on current page (use in DTC Index, TSBs, etc)

⚡ WHEN TO USE SEARCH: If your goal is a SPECIFIC item (connector C102A, part number, DTC code), use search() FIRST! It's faster than browsing menus.
⚡ FOR DTC CODES: Use search() directly - DTC Index has complex nested accordions.

⚡ AFTER SEARCH: When you see search results in the CLICKABLE OPTIONS list (e.g., "[28] c1979"), CLICK the first one!

⚡ SEARCH RESULT CARDS: After clicking a search result, you may see VIEW CARDS (Top Repairs, OEM Testing, Causes & Fixes, etc):
- Click the first card (prefer 'OEM Testing' for DTCs if available)
- Cards may not appear in CLICKABLE OPTIONS - use click_text() to click them
- Once on detail page, data is in PAGE TEXT - use collect() to store it!

MULTI-ITEM COLLECTION (images AND pinout, multiple specs, etc.):
- If user asks for MULTIPLE things (e.g., "get me images AND pinout"):
  1. Get to the detail page (e.g., connector pinout page)
  2. COPY the actual data from PAGE TEXT into collect(), like:
     collect("pinout", "Pin 1: CDC15 GN 20 GENERATOR LOAD INPUT\nPin 2: CDC10 BU-OG 20 GENERATOR REGULATOR...")
  3. Use capture_diagram("connector end view") to save the image
  4. Call done("Got pinout data and connector image") to finish
- CRITICAL: collect() data must be REAL DATA copied from PAGE TEXT, not empty or placeholder!
- You can call collect() + capture_diagram() + done() all in ONE response - they'll execute in order
- capture_diagram() captures ALL visible images on the page automatically

⚠️ ALWAYS CAPTURE IMAGES FOR CONNECTORS:
- When you find connector pinout data, ALWAYS call capture_diagram() even if images aren't explicitly mentioned
- Connector end view images show pin locations which are essential for technicians
- Pattern: collect("pinout", "...data...") + capture_diagram("connector end view") + done()

NAVIGATION PATHS (follow these!):
- Parts and labor / repair cost / estimate → Estimate Guide → click category (e.g., "Electrical") → click subcategory (e.g., "Charging System") → click operation name (e.g., "ALTERNATOR ASSEMBLY") → collect() part #, price, labor hours from PAGE TEXT → done()
- Spark plug gap → Common Specs → look for "Spark Plug" or "Ignition" section → collect() + done()
- Oil drain plug torque → Fluid Capacities → look for torque value with "ft-lb" or "N.m" → collect() + done()
- Oil capacity → Fluid Capacities → collect() quarts/liters value → done()
- Torque specs → Fluid Capacities OR Common Specs → look for "ft-lb" or "N.m" values → collect() + done()
- DTC code (P0171, P0300, B1000, etc) → DTC Index → navigate the hierarchy → find and click the code → collect() full procedure → done()
- Multiple DTC codes → DTC Index → find each code → collect() → prior_page() → repeat → done()
- Wiring diagram → Wiring Diagrams → SYSTEM WIRING DIAGRAMS → click category (e.g., STARTING/CHARGING) → when you see "Fig X:" in the element list, call capture_diagram() IMMEDIATELY
- Connector pinout / connector C### (e.g., C205, C102A) → Wiring Diagrams → look for "CONNECTOR END VIEWS" links → click the range containing your connector number → find connector → collect() + capture_diagram() + done()
- Harness-to-harness connector (X200, X310, "body harness", "harness to") → Wiring Diagrams → INLINE HARNESS CONNECTOR END VIEWS - INDEX → click connector → collect() + capture_diagram() + done()
- Component location (where is ECM, fuel pump relay, fuse box) → Component Locations → click section (1 OF 3, 2 OF 3, 3 OF 3) → find component → collect() location info + capture_diagram() + done()
- Component test / diagnostic test / how to test → Component Tests → click system category (ABS, Body Electrical, Charging System, Engine, HVAC, Starting, Transmission) → click specific component → collect() pinouts, operation, location → done()
- TSBs / technical service bulletins / "any TSBs" → Technical Bulletins → collect() the TSB list from the table → done()
- Specific TSB detail → Technical Bulletins → click the CATEGORY (from context) → click TSB number/title → collect() details → done()

CRITICAL - CONNECTOR END VIEWS (C### connectors like C205, C102A, C1979):
- Go to Wiring Diagrams modal - you'll see connector end views links
- LOOK FOR INDEX FIRST! If you see "INDEX" in a link, click that - it shows ALL connectors
- THREE possible structures depending on vehicle make:
  A) INDEX LINK (Chevrolet, etc): "COMPONENT CONNECTOR END VIEWS - INDEX" or "INLINE HARNESS CONNECTOR END VIEWS - INDEX"
     → Click INDEX to see all connectors, find yours in the list
  B) RANGED LINKS (Ford, etc): "OEM CONNECTOR END VIEWS - C100 THROUGH C327", "A3L TO E8S", etc.
     → Parse your connector ID and pick the range that contains it
  C) NUMBERED SECTIONS (Jeep, etc): "CONNECTOR END VIEWS (1 OF 3)", "(2 OF 3)", "(3 OF 3)"
     → Try section 1 first, search for connector, use prior_page() if not found, try next section
- After clicking INDEX/range/section → look for your connector ID in the list
- Click the connector → collect() pinout data from PAGE TEXT + capture_diagram() + done()
- If connector NOT found in that section → prior_page() → try the next range/section

CRITICAL - WIRING DIAGRAMS:
- After clicking a category (STARTING/CHARGING, HEADLIGHTS, etc.), look at the elements
- If you see "Fig 1:", "Fig 2:", etc. in the element list → the diagram is VISIBLE!
- Call capture_diagram() IMMEDIATELY when you see "Fig X:" - do NOT click it!
- Do NOT keep clicking the same category - that just toggles it open/closed

CRITICAL - DTC CODES:
- Use search(dtc_code) directly - DTC Index has nested accordions that are hard to navigate
- After search, click the result to see VIEW CARDS
- If multiple cards, ask user which one they want

CRITICAL - TSBs (Technical Service Bulletins):
- When asked "any TSBs?" or "TSBs for [vehicle]", return the category list from Technical Bulletins
- Technical Bulletins modal shows categories with counts like "Recalls (2)", "Engine Control Systems (3)"
- Use collect() to store the full category list with counts, then done()
- After showing the list, user can ask about a specific category for actual bulletin details
- Only click into a specific category if user asks for it by name

CRITICAL - SPECIFIC TSB LOOKUP (e.g., "TSB 31-002-16"):
- USE THE CONVERSATION CONTEXT! If you already discussed this TSB, you know which category it's in.
- WORKFLOW:
  1. Go to Technical Bulletins
  2. Look at CONVERSATION CONTEXT - what category was the TSB mentioned under?
  3. Click that category (e.g., "Body Interior (1)")
  4. The TSB table appears - click the TSB NUMBER (e.g., "31-002-16") or TITLE
  5. Extract the TSB content
- DO NOT use expand_all() - it's slow and the selectors break!
- The context already told you where to find it - use that knowledge!

CRITICAL - COLLECT RULES:
- collect() requires REAL data from PAGE TEXT - COPY, don't compose!
- Find your data in PAGE TEXT, then copy that into collect()
- Always call done() after collecting to return the results
- DON'T guess what the text should say - READ what it actually says
- If you can't find it after searching PAGE TEXT → extract("DATA NOT FOUND: [target]")
- It's OK to report that data doesn't exist - that's useful information!
- After trying 2-3 sections with no luck → extract("DATA NOT FOUND: searched [sections] but [target] not available for this vehicle")

CRITICAL - SEARCHING MULTIPLE SECTIONS (1 OF 3, 2 OF 3, 3 OF 3):
- Connectors are split across numbered sections. If your target isn't in section 1, try section 2 or 3!
- WORKFLOW:
  1. Click section 1 → search PAGE TEXT for your target
  2. If NOT found → call prior_page() to go back to section selector
  3. After prior_page(), you should see sections "1 OF 3", "2 OF 3", "3 OF 3" as clickable options again
  4. Click the NEXT section (2 OF 3) and search again
  5. Repeat until found or all sections exhausted
- prior_page() clicks the "Back" breadcrumb link to return to section selector
- Only use go_back() when you're DONE with the entire Wiring Diagrams modal
- If prior_page() doesn't return you to section selector, the page may have changed - check elements!

CRITICAL - CONNECTOR TYPE SELECTION:
- If goal mentions "A11", "K20", "radio", "ECM", "module" → use COMPONENT CONNECTOR
- If goal mentions "X200", "X310", "body harness", "harness to harness", "harness to driver" → use INLINE HARNESS
- Look for the INDEX option (not specific letter ranges like A-K)

CRITICAL - COMPONENT TESTS:
- Opens a modal with DRILL-DOWN navigation: Categories → Components → Details
- Top-level categories: ABS, Driver Aids/ADAS, Engine, Transfer Case, Transmission
- Clicking a CATEGORY expands it and shows its components (collapses other categories)
- Step 1: Click the category that matches your goal (e.g., "ABS" for wheel speed sensors, "Engine" for ECM)
- Step 2: Click the specific component to see its detail page
- Step 3: Extract the test procedure, pinouts, operation info
- If you picked the WRONG category: use prior_page() to go back, then try another category
- Category hints:
  - Wheel speed sensors, brake module, ABS → click "ABS"
  - ECM, engine sensors, throttle, MAF, O2 → click "Engine"  
  - Alternator, generator, charging → click "Engine" (under charging components)
  - Transmission, shift solenoids, TCM → click "Transmission"
  - Camera, collision alert, park assist → click "Driver Aids / ADAS"

CRITICAL - WHEN YOU'RE STUCK (MOST IMPORTANT!):
- Look at YOUR CLICKS THIS SESSION at the top of each message
- If you see the SAME element clicked 2+ times, THAT PATH ISN'T WORKING
- go_back() to the main page and try a COMPLETELY DIFFERENT section
- Example: If "Component Locations" isn't finding your connector, try "Wiring Diagrams" instead
- Connectors can be found in MULTIPLE places: Component Locations, Wiring Diagrams → OEM CONNECTOR END VIEWS INDEX
- Don't keep drilling into the same section - EXPLORE other top-level options!

KEY RULES:
1. ⚡ For SPECIFIC items (C102A, P0300, part#), use search() FIRST - it's faster than browsing!
2. MODAL = popup dialog. When one opens, pick from MODAL CONTENT list
3. INDEX pages list all connectors - find yours in PAGE TEXT and use click_text()
4. COMPONENT connectors = modules (radio, ECM). INLINE HARNESS = wire-to-wire (X200, X310)
5. For diagrams: DON'T click "Fig..." images - use capture_diagram() to save them
6. For connectors with "image": extract the spec text AND capture_diagram for the image
7. Duplicate elements labeled [BREADCRUMB] show where you ARE - don't click those
8. EXTRACT SPECS, NOT TITLES: For connectors, extract "Description: 20-Way F..." not the connector name

ALWAYS call a tool. Match your goal to a navigation path above and follow it."""


def build_user_message(
    page_state: PageState, 
    page_text: str, 
    modal_open: bool = False,
    path_taken: list = None,
    goal: str = "",
    click_history: list = None,
    collected_data: list = None,
) -> str:
    """
    Build the user message showing current page state and path taken.
    
    Args:
        collected_data: List of items already collected (persists across context resets)
    """
    lines = []
    
    # Show what's already collected (survives context resets)
    if collected_data:
        lines.append("✅ ITEMS ALREADY COLLECTED:")
        for item in collected_data:
            label = item.get('label', 'Unknown')
            lines.append(f"  • {label}")
        lines.append("")
        lines.append("Find the NEXT item from your goal, then call done() when ALL items collected.")
        lines.append("")
    
    # CLICK HISTORY: Show all clicks this session so AI can see patterns
    if click_history and len(click_history) > 3:
        lines.append("YOUR CLICKS THIS SESSION:")
        for i, click_text in enumerate(click_history, 1):
            lines.append(f"  {i}. {click_text}")
        lines.append("")
    
    # SHORT-TERM MEMORY: Show the journey so far WITH RESULTS
    if path_taken:
        lines.append("YOUR PATH SO FAR:")
        for i, step in enumerate(path_taken, 1):
            tool = step["tool"]
            args = step["args"]
            result = step.get("result_hint", "")  # What happened after this action
            
            if tool == "click" or tool == "click_text":
                elem_text = args.get("clicked_text", args.get("text", "?"))[:80]
                if result:
                    lines.append(f"  {i}. CLICK '{elem_text}' → {result}")
                else:
                    lines.append(f"  {i}. CLICK '{elem_text}'")
            elif tool == "go_back":
                lines.append(f"  {i}. GO BACK → {result or 'closed modal'}")
            elif tool == "prior_page":
                lines.append(f"  {i}. PRIOR PAGE → {result or 'went back one page'}")
            elif tool == "search":
                lines.append(f"  {i}. SEARCH '{args.get('text', '')}'")
            elif tool == "collect":
                label = args.get("label", "data")
                lines.append(f"  {i}. COLLECT '{label}' → {result or 'stored'}")
            elif tool == "done":
                lines.append(f"  {i}. DONE → {result or 'finished'}")
        lines.append(f"")
        # Calculate depth: clicks forward, minus prior_pages back
        clicks_forward = len([p for p in path_taken if p['tool'] in ('click', 'click_text')])
        pages_back = len([p for p in path_taken if p['tool'] == 'prior_page'])
        effective_depth = max(0, clicks_forward - pages_back)
        lines.append(f"DEPTH: {effective_depth} clicks deep (clicked {clicks_forward}x, went back {pages_back}x)")
        
        # Track which numbered sections have been tried
        sections_tried = set()
        for step in path_taken:
            clicked = step.get("args", {}).get("clicked_text", "").lower()
            if "1 of 3" in clicked:
                sections_tried.add(1)
            elif "2 of 3" in clicked:
                sections_tried.add(2)
            elif "3 of 3" in clicked:
                sections_tried.add(3)
        if sections_tried:
            tried_str = ", ".join(str(s) for s in sorted(sections_tried))
            remaining = [s for s in [1, 2, 3] if s not in sections_tried]
            if remaining:
                remain_str = ", ".join(str(s) for s in remaining)
                lines.append(f"⚠️ SECTIONS ALREADY TRIED: {tried_str}. TRY SECTION {remain_str} NEXT!")
            else:
                lines.append(f"⚠️ ALL SECTIONS (1, 2, 3) TRIED - item may not exist for this vehicle!")
        lines.append("")
    
    lines.append("CURRENT PAGE:")
    lines.append(f"URL: {page_state.url}")
    
    # Critical: Tell AI if modal is open - but encourage exploration
    if modal_open:
        lines.append("")
        lines.append("📋 MODAL DIALOG IS OPEN - You're inside a content section!")
        lines.append("Click elements inside the modal to drill deeper, or use collect() + done() if you found data.")
        lines.append("Only use go_back() if this is the WRONG section for your goal.")
    
    # Get clickable elements with meaningful text
    meaningful_elements = [el for el in page_state.elements if el.text and len(el.text.strip()) > 2]
    
    # When modal is open, ONLY show modal elements - filter out sidebar noise
    if modal_open:
        modal_elements = [el for el in meaningful_elements if el.in_modal]
        
        # Detect if we're at section selector (1 OF 3, 2 OF 3, etc.)
        section_elements = [el for el in modal_elements if "OF 3" in el.text.upper() or "OF 2" in el.text.upper()]
        if section_elements:
            lines.extend([
                "",
                "⚠️ SECTION SELECTOR - Multiple sections to search through:",
                ""
            ])
            # Deduplicate sections by text (same link may appear multiple times)
            seen_section_texts = set()
            for el in section_elements:
                text = el.text.strip().replace('\n', ' ')
                if text not in seen_section_texts:
                    seen_section_texts.add(text)
                    lines.append(f"  [{el.id}] {text}")
            lines.append("")
            lines.append("PICK A SECTION TO SEARCH. If not found, use prior_page() then try next section.")
            lines.append("")
            lines.append("OTHER OPTIONS IN MODAL:")
        else:
            lines.extend([
                "",
                "MODAL CONTENT (pick from these options!):",
                ""
            ])
        
        # Detect duplicates and label them (same text appearing multiple times)
        seen_texts = {}
        for el in modal_elements:
            text = el.text.strip().replace('\n', ' ')
            text_lower = text.lower()
            if text_lower in seen_texts:
                seen_texts[text_lower].append(el.id)
            else:
                seen_texts[text_lower] = [el.id]
        
        # Render with labels for duplicates
        for el in modal_elements:
            text = el.text.strip().replace('\n', ' ')
            text_lower = text.lower()
            
            # Label duplicates so AI knows which is which
            label = ""
            if len(seen_texts.get(text_lower, [])) > 1:
                ids = seen_texts[text_lower]
                if el.id == ids[0]:
                    label = " [BREADCRUMB - where you ARE]"
                else:
                    label = " [CLICKABLE]"
            
            lines.append(f"  [{el.id}] {text}{label}")
        
        # All elements shown - no truncation
    else:
        # Show clean list - just the choices
        lines.extend([
            "",
            "CLICKABLE OPTIONS (pick the one that matches your goal!):",
            ""
        ])
        
        for el in meaningful_elements:
            text = el.text.strip().replace('\n', ' ')
            lines.append(f"  [{el.id}] {text}")
    
    # Only include PAGE TEXT when in a modal (content page) - skip on landing page
    # Landing page just needs CLICKABLE OPTIONS to navigate; PAGE TEXT there is noise
    if modal_open:
        lines.append("")
        lines.append("PAGE TEXT (COPY exact text from here for collect!):")
        
        # For DTC/code searches, try to find and highlight the target
        code_match = re.search(r'[PBCUpbcu]\d{4}', goal)
        if code_match:
            target_code = code_match.group().upper()
            # Find all lines containing the code
            matching_lines = [line for line in page_text.split('\n') if target_code in line.upper()]
            if matching_lines:
                lines.append(f"\n*** FOUND {target_code}! Copy this EXACT text into collect(): ***")
                for ml in matching_lines[:3]:
                    clean = ml.strip()
                    if clean:
                        lines.append(f'"{clean}"')
                lines.append("")
        
        lines.append(page_text)
    
    return "\n".join(lines)
