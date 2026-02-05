"""
Common Sense Mapping - AI Heuristics
=====================================

Maps data types to likely locations in ShopKeyPro.
This helps the AI rank candidates intelligently before exploring.

The AI uses this as "common sense" - it won't look for
fluid capacities in wiring diagrams.
"""

from typing import Dict, List, Tuple

# Quick Access button selectors on the landing page
# Use #quickLinkRegion prefix to avoid duplicate element issues
QUICK_ACCESS_BUTTONS = {
    "technical_bulletins": {
        "selector": "#quickLinkRegion #tsbQuickAccess",
        "name": "Technical Bulletins",
        "contains": [
            "tsb", "technical service bulletin", "recall", "campaign",
            "service bulletin", "manufacturer bulletin", "any tsb",
            "are there any tsb", "tsbs for", "bulletins for"
        ]
    },
    "common_specs": {
        "selector": "#quickLinkRegion #commonSpecsAccess",
        "name": "Common Specs",
        "contains": [
            "lug nut torque", "wheel torque", "torque specs", "specifications",
            "bolt torque", "fastener torque", "general specs"
        ]
    },
    "driver_assist": {
        "selector": "#quickLinkRegion #adasCalibrationAccess",
        "name": "Driver Assist ADAS",
        "contains": [
            "adas", "calibration", "camera calibration", "radar calibration",
            "lane departure", "collision avoidance", "blind spot",
            "forward collision", "adaptive cruise"
        ]
    },
    "fluid_capacities": {
        "selector": "#quickLinkRegion #fluidsQuickAccess",
        "name": "Fluid Capacities",
        "contains": [
            "oil capacity", "coolant capacity", "transmission fluid",
            "brake fluid", "power steering fluid", "differential fluid",
            "transfer case fluid", "oil drain plug torque", "drain plug",
            "fluid capacity", "oil type", "coolant type", "atf"
        ]
    },
    "tire_info": {
        "selector": "#quickLinkRegion #tpmsTireFitmentQuickAccess",
        "name": "Tire Information & Lifting Points",
        "contains": [
            "tire size", "tire pressure", "tpms", "tire sensor",
            "wheel size", "lifting points", "jack points",
            "tire specs", "wheel specs"
        ]
    },
    "reset_procedures": {
        "selector": "#quickLinkRegion #resetProceduresAccess",
        "name": "Reset Procedures",
        "contains": [
            "oil life reset", "maintenance reset", "tpms reset",
            "service reset", "oil reset", "reset procedure",
            "maintenance light", "service light"
        ]
    },
    "dtc_index": {
        "selector": "#quickLinkRegion #dtcIndexAccess",
        "name": "DTC Index",
        "contains": [
            "dtc", "diagnostic trouble code", "check engine",
            "fault code", "error code", "obd", "p0", "p1", "p2",
            "b0", "c0", "u0", "code meaning"
        ]
    },
    "wiring_diagrams": {
        "selector": "#quickLinkRegion #wiringDiagramsAccess",
        "name": "Wiring Diagrams",
        "contains": [
            "wiring diagram", "electrical diagram", "circuit",
            "connector", "wire color", "pinout", "electrical",
            "wiring", "harness", "schematic"
        ]
    },
    "component_locations": {
        "selector": "#quickLinkRegion #componentLocationsAccess",
        "name": "Component Locations",
        "contains": [
            "location", "where is", "component location",
            "sensor location", "relay location", "fuse location"
        ]
    },
    "component_tests": {
        "selector": "#quickLinkRegion #ctmQuickAccess",
        "name": "Component Tests",
        "contains": [
            "test procedure", "component test", "diagnostic test",
            "how to test", "testing", "multimeter", "pinout",
            "wheel speed sensor", "abs module", "alternator test"
        ]
    },
    "service_manual": {
        "selector": "#quickLinkRegion #serviceManualAccess",
        "name": "Service Manual",
        "contains": [
            "repair procedure", "how to replace", "removal",
            "installation", "service manual", "repair manual"
        ]
    }
}


def score_candidate(query: str, button_key: str) -> float:
    """
    Score how likely a button contains the requested data.
    
    Args:
        query: The search query (e.g., "oil drain plug torque")
        button_key: Key from QUICK_ACCESS_BUTTONS
        
    Returns:
        Score from 0.0 to 1.0 (higher = more likely)
    """
    if button_key not in QUICK_ACCESS_BUTTONS:
        return 0.0
    
    button = QUICK_ACCESS_BUTTONS[button_key]
    query_lower = query.lower()
    
    score = 0.0
    matches = 0
    
    # Check for keyword matches
    for keyword in button["contains"]:
        if keyword in query_lower:
            # Exact phrase match is best
            score += 1.0
            matches += 1
        else:
            # Check word-by-word overlap
            keyword_words = set(keyword.split())
            query_words = set(query_lower.split())
            overlap = len(keyword_words & query_words)
            if overlap > 0:
                score += 0.3 * overlap
                matches += 1
    
    # Normalize score
    if matches > 0:
        return min(score / 2.0, 1.0)  # Cap at 1.0
    
    return 0.0


def rank_candidates(query: str) -> List[Tuple[str, str, float]]:
    """
    Rank all Quick Access buttons by likelihood of containing the data.
    
    Args:
        query: The search query
        
    Returns:
        List of (selector, name, score) tuples, sorted by score descending
    """
    candidates = []
    
    for key, button in QUICK_ACCESS_BUTTONS.items():
        score = score_candidate(query, key)
        candidates.append((
            button["selector"],
            button["name"],
            score
        ))
    
    # Sort by score descending, but keep all candidates
    # (AI might need to try lower-scored ones if high ones fail)
    candidates.sort(key=lambda x: x[2], reverse=True)
    
    return candidates


def get_top_candidates(query: str, min_score: float = 0.1) -> List[Tuple[str, str, float]]:
    """
    Get candidates with score above threshold.
    
    Args:
        query: The search query
        min_score: Minimum score to include (default 0.1)
        
    Returns:
        List of (selector, name, score) tuples
    """
    all_candidates = rank_candidates(query)
    return [c for c in all_candidates if c[2] >= min_score]


def format_candidates_for_prompt(query: str) -> str:
    """
    Format ranked candidates for inclusion in AI prompt.
    
    Args:
        query: The search query
        
    Returns:
        Formatted string showing ranked options
    """
    candidates = rank_candidates(query)
    
    lines = ["## Candidate Paths (ranked by likelihood)"]
    
    for i, (selector, name, score) in enumerate(candidates, 1):
        if score > 0.5:
            indicator = "🟢 HIGH"
        elif score > 0.2:
            indicator = "🟡 MEDIUM"
        elif score > 0:
            indicator = "🟠 LOW"
        else:
            indicator = "⚪ UNLIKELY"
        
        lines.append(f"{i}. {name} ({selector}) - {indicator} ({score:.2f})")
    
    return "\n".join(lines)


def get_negative_candidates(query: str) -> List[str]:
    """
    Get buttons that are UNLIKELY to contain the data.
    
    Useful for telling the AI what NOT to try.
    
    Args:
        query: The search query
        
    Returns:
        List of button names that are unlikely
    """
    candidates = rank_candidates(query)
    return [name for selector, name, score in candidates if score == 0]
