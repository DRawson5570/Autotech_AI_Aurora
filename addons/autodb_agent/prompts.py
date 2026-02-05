"""
AutoDB Agent Prompts.

System prompts for the AI navigator.
Enhanced with better navigation guidance and more tools.
"""

from .models import Vehicle, PathStep
from typing import List


def build_system_prompt(goal: str, vehicle: Vehicle) -> str:
    """Build the system prompt for navigation."""
    
    # Detect if query is for diagrams/images
    goal_lower = goal.lower()
    wants_diagram = any(word in goal_lower for word in ['diagram', 'wiring', 'schematic', 'image', 'picture'])
    
    diagram_guidance = ""
    if wants_diagram:
        diagram_guidance = """
=== FINDING DIAGRAMS ===
You're looking for a DIAGRAM. Diagrams are IMAGE files, not text.
- Path: Repair and Diagnosis → Diagrams → Electrical Diagrams → [System] → Left Hand Drive
- The page with the actual diagram will show "Has Images: True" or "IMAGES: X diagram(s)"
- If you find a page about the topic but NO images, GO BACK and try a different path!
- There may be multiple paths to similar content - find the one WITH the image.
"""
    
    return f"""You are navigating the Operation CHARM automotive service manual database.

=== YOUR GOAL ===
Find: {goal}
Vehicle: {vehicle}

=== CRITICAL: VEHICLE SELECTION ===
You MUST navigate to this EXACT vehicle first:
- Make: {vehicle.make}
- Year: {vehicle.year}
- Model: {vehicle.model}
- Engine: {vehicle.engine}

DO NOT click on any other make. ONLY click on "{vehicle.make}" or "{vehicle.make} Truck".
{diagram_guidance}
=== SITE STRUCTURE ===
Home → Make → Year → Model → Content Sections

Content sections under a vehicle:
- **Repair and Diagnosis** - Main section containing:
  - Specifications (capacities, torque, mechanical specs)
  - Diagrams (wiring, electrical, vacuum diagrams WITH IMAGES)
  - Procedures (repair steps, usually text)
  - DTCs (diagnostic trouble codes)
- **Parts and Labor** - Parts catalogs

=== FINDING SPECIFIC CONTENT ===

**Wiring Diagrams:** Repair and Diagnosis → Diagrams → Electrical Diagrams → [System Name] → Left Hand Drive
- The "Left Hand Drive" or final page has the actual diagram IMAGE
- Example: Charging System diagram is at Diagrams/Electrical Diagrams/Charging System/Left Hand Drive

**Specifications:** Repair and Diagnosis → Specifications → [Type]
- Capacity Specifications (oil, coolant, trans fluid)
- Mechanical Specifications (torque specs)
- Fluid Type Specifications (what fluids to use)

**Firing Order:** Multiple paths exist - if one doesn't have an image, try another:
- Specifications → Mechanical Specifications → Ignition System → Firing Order
- Powertrain Management → Ignition System → Firing Order
- Engine → Tune-up → Firing Order

**Fuse Box Diagram / Fuse Locations:** 
- Path: Repair and Diagnosis → Power and Ground Distribution → Fuse → **Locations**
- The "Locations" page contains the TIPM (Totally Integrated Power Module) diagram with fuse cavity tables
- This has IMAGES of the fuse box layout with fuse positions, amp ratings, and descriptions
- Do NOT look in the Diagrams folder for fuse boxes - they are under "Locations"!

=== TOOLS ===
Respond with JSON only. Available tools:

1. **click** - Navigate to a link:
   {{"tool": "click", "link_text": "Exact Link Text"}}

2. **extract** - Get content from current page (use when you see the data you need):
   {{"tool": "extract"}}

3. **go_back** - Return to previous page (use when current page isn't right):
   {{"tool": "go_back"}}

4. **grep** - Search current page for a pattern (case-insensitive):
   {{"tool": "grep", "pattern": "search term"}}
   Use this to find specific data like "Radio fuse", "40 Amp", or a torque value.

5. **cat** - Show full page content (when summary isn't enough):
   {{"tool": "cat"}}

6. **egrep** - Search the ENTIRE SITE for a pattern (regex supported):
   {{"tool": "egrep", "pattern": "radio|fuse"}}
   This searches ALL pages for the vehicle, returning paths where data is found.
   Use this FIRST to find exactly where data lives before clicking around!
   **IMPORTANT: After egrep finds results, use 'goto' with one of the returned PATH values!**

7. **goto** - Jump directly to a path (use IMMEDIATELY after egrep finds results):
   {{"tool": "goto", "path": "Repair and Diagnosis/Relays and Modules/..."}}
   The path should be from the egrep results - copy the PATH value from the result.
   Example workflow:
   - egrep finds: PATH: Repair and Diagnosis/Relays and Modules/Choke Relay
   - You then: {{"tool": "goto", "path": "Repair and Diagnosis/Relays and Modules/Choke Relay"}}

8. **where_am_i** - Check your current location and what's available:
   {{"tool": "where_am_i"}}

9. **how_did_i_get_here** - Review your full navigation path:
   {{"tool": "how_did_i_get_here"}}

10. **collect** - Store data and continue navigating (for multi-section data):
   {{"tool": "collect", "data": "the data", "label": "Section Name"}}

11. **done** - Combine all collected data and finish:
   {{"tool": "done"}}

=== NAVIGATION STRATEGY ===
1. **Start at home** - You'll see a list of vehicle makes
2. **Use egrep FIRST** to search the entire site for your goal term
3. **When egrep finds results**, immediately use **goto** with the most relevant PATH from results
4. **If goto takes you to the data**, use extract to get it
5. If the page doesn't have what you need, use go_back and try another path from egrep results
6. "Has Data: True" means extractable content exists
7. "IMAGES: X diagram(s)" means diagrams are present - that's your target for diagram queries!

=== CRITICAL: egrep → goto WORKFLOW ===
When you call egrep and get matches like:
  PATH: Jeep Truck/1985/L4-150/Repair and Diagnosis/Relays and Modules/Choke Relay
  TITLE: Choke Relay
  SNIPPET: ...
  
Your NEXT action MUST be goto with that path:
  {{"tool": "goto", "path": "Jeep Truck/1985/L4-150/Repair and Diagnosis/Relays and Modules/Choke Relay"}}

Do NOT call egrep again with the same or similar pattern!

=== IMPORTANT ===
- Click EXACTLY what's shown in the link list
- For diagrams, you MUST find a page with images - keep looking if the page has no images
- Use go_back() freely to try different paths - don't give up after one failed attempt"""


def build_user_message(
    page_text: str,
    path_taken: List[PathStep],
    max_path_history: int = 10,
) -> str:
    """Build the user message showing current page state."""
    
    # Format path taken
    if path_taken:
        path_lines = []
        # Show last N steps
        recent_path = path_taken[-max_path_history:]
        start_num = len(path_taken) - len(recent_path) + 1
        for i, step in enumerate(recent_path, start_num):
            path_lines.append(f"{i}. {step.action} {step.result_hint}")
        path_text = "\n".join(path_lines)
    else:
        path_text = "(start)"
    
    return f"""=== CURRENT PAGE ===
{page_text}

=== PATH TAKEN ===
{path_text}

What's your next action? Respond with JSON only."""
