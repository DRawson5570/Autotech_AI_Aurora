"""
Quick Access Mapping
====================
Maps data types to ShopKeyPro Quick Access button selectors.
"""

from typing import Optional


# NOTE: Use #quickLinkRegion prefix because each ID exists twice in the DOM
# (once in #quickLinkRegion, once in #quickAccessPanel). The visible one is
# #quickLinkRegion.

QUICK_ACCESS_BUTTONS = {
    # Fluid Capacities
    "fluid capacities": "#quickLinkRegion #fluidsQuickAccess",
    "fluids": "#quickLinkRegion #fluidsQuickAccess",
    "oil capacity": "#quickLinkRegion #fluidsQuickAccess",
    "coolant capacity": "#quickLinkRegion #fluidsQuickAccess",
    
    # Common Specs (torque, general specs)
    "common specs": "#quickLinkRegion #commonSpecsAccess",
    "specifications": "#quickLinkRegion #commonSpecsAccess",
    "torque specs": "#quickLinkRegion #commonSpecsAccess",
    "torque specifications": "#quickLinkRegion #commonSpecsAccess",
    
    # Reset Procedures
    "reset procedures": "#quickLinkRegion #resetProceduresAccess",
    "oil reset": "#quickLinkRegion #resetProceduresAccess",
    "oil life reset": "#quickLinkRegion #resetProceduresAccess",
    "tpms reset": "#quickLinkRegion #resetProceduresAccess",
    "maintenance reset": "#quickLinkRegion #resetProceduresAccess",
    
    # Technical Bulletins / TSBs
    "technical bulletins": "#quickLinkRegion #technicalBulletinAccess",
    "tsb": "#quickLinkRegion #technicalBulletinAccess",
    "service bulletins": "#quickLinkRegion #technicalBulletinAccess",
    
    # DTC Index
    "dtc": "#quickLinkRegion #dtcIndexAccess",
    "dtc index": "#quickLinkRegion #dtcIndexAccess",
    "trouble codes": "#quickLinkRegion #dtcIndexAccess",
    "diagnostic codes": "#quickLinkRegion #dtcIndexAccess",
    
    # Tire Information (TPMS & Tire Fitment)
    "tire information": "#quickLinkRegion #tpmsTireFitmentQuickAccess",
    "tire specs": "#quickLinkRegion #tpmsTireFitmentQuickAccess",
    "tires": "#quickLinkRegion #tpmsTireFitmentQuickAccess",
    "tire pressure": "#quickLinkRegion #tpmsTireFitmentQuickAccess",
    "tpms": "#quickLinkRegion #tpmsTireFitmentQuickAccess",
    
    # ADAS Calibration
    "adas": "#quickLinkRegion #adasAccess",
    "driver assist": "#quickLinkRegion #adasAccess",
    "calibration": "#quickLinkRegion #adasAccess",
    "adas calibration": "#quickLinkRegion #adasAccess",
    
    # Wiring Diagrams
    "wiring diagrams": "#quickLinkRegion #wiringDiagramsAccess",
    "wiring": "#quickLinkRegion #wiringDiagramsAccess",
    "electrical diagrams": "#quickLinkRegion #wiringDiagramsAccess",
    
    # Component Locations
    "component locations": "#quickLinkRegion #electricalComponentLocationAccess",
    "electrical components": "#quickLinkRegion #electricalComponentLocationAccess",
    
    # Component Tests
    "component tests": "#quickLinkRegion #ctmQuickAccess",
    "tests": "#quickLinkRegion #ctmQuickAccess",
    
    # Service Manual
    "service manual": "#quickLinkRegion #serviceManualQuickAccess",
    "manual": "#quickLinkRegion #serviceManualQuickAccess",
}


def get_quick_access_selector(data_type: str) -> Optional[str]:
    """
    Map data type to Quick Access button selector.
    
    Args:
        data_type: Type of data requested (case-insensitive)
        
    Returns:
        CSS selector for Quick Access button, or None if not mapped
    
    Example:
        selector = get_quick_access_selector("fluid capacities")
        # Returns: "#quickLinkRegion #fluidsQuickAccess"
    """
    key = data_type.lower().strip()
    return QUICK_ACCESS_BUTTONS.get(key)


def get_all_data_types() -> list:
    """
    Get list of all supported data types.
    
    Returns:
        Sorted list of data type strings
    """
    return sorted(set(QUICK_ACCESS_BUTTONS.keys()))


def get_button_ids() -> list:
    """
    Get list of unique Quick Access button IDs.
    
    Returns:
        List of button ID strings (without prefix)
    """
    unique_ids = set()
    for selector in QUICK_ACCESS_BUTTONS.values():
        # Extract ID from selector like "#quickLinkRegion #fluidsQuickAccess"
        parts = selector.split()
        if len(parts) == 2:
            unique_ids.add(parts[1].lstrip("#"))
    return sorted(unique_ids)
