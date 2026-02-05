"""
ShopKeyPro Selectors
====================

All UI selectors for ShopKeyPro navigation, consolidated in one place.
These are hardcoded because:
1. They rarely change (ShopKeyPro's DOM is stable)
2. When they do change, we want to update code, not config files
3. Simpler than maintaining a 1000-line JSON config

The AI Navigator (ai_navigator/) uses its own selectors in common_sense.py
for Quick Access buttons. This module is for the legacy scripted tools.
"""

# =============================================================================
# URLs
# =============================================================================

URLS = {
    "landing_page": "https://www1.shopkeypro.com",
    "login_page": "https://aui.mitchell1.com/Login",
    "main_app": "https://www1.shopkeypro.com/Main/Index",
}

# =============================================================================
# Login Selectors
# =============================================================================

LOGIN = {
    "username_input": "#username",
    "password_input": "#password",
    "login_button": "#loginButton",
    "cancel_button": "#cancelButton",
    "remember_me_checkbox": "#rememberMeCheckbox",
    "logged_in_check": "#logout, nav >> text=Logout",
}

# =============================================================================
# Vehicle Selector Selectors
# =============================================================================

VEHICLE_SELECTOR = {
    "container": "#VehicleSelectorContainer",
    "select_vehicle_button": "#vehicleSelectorButton",
    "accordion_header": "h1:has-text('Vehicle Selection')",
    "qualifier_type_selector": "#qualifierTypeSelector",
    "qualifier_value_selector": "#qualifierValueSelector",
    "qualifier_item": "#qualifierValueSelector li.qualifier",
    "year_tab": "#qualifierTypeSelector li.year",
    "make_tab": "#qualifierTypeSelector li.make",
    "model_tab": "#qualifierTypeSelector li.model",
    "engine_tab": "#qualifierTypeSelector li.engine",
    "submodel_tab": "#qualifierTypeSelector li.submodel",
    "options_tab": "#qualifierTypeSelector li.options",
    "odometer_tab": "#qualifierTypeSelector li.odometer",
    "use_vehicle_button": "input[data-action='SelectComplete']",
    "cancel_button": "input[data-action='Cancel']",
    "reset_options_button": "input[data-action='ResetOptions']",
}

# Template for selecting a value - use .format(value=xxx)
VEHICLE_VALUE_TEMPLATE = "#qualifierValueSelector li.qualifier:has-text('{value}')"

# =============================================================================
# Vehicle Options Selectors (Drive Type, Body Style, etc.)
# =============================================================================

VEHICLE_OPTIONS = {
    "panel_container": "#qualifierValueSelector div.options",
    "required_message": "div.requiredMessage",
    "option_group": "div.optionGroup",
    "option_group_selected": "div.optionGroup.selected",
    "option_group_heading": "div.optionGroup div.heading",
    "option_group_title": "div.optionGroup div.heading h1",
    "option_group_value": "div.optionGroup div.heading h2",
    "option_item": "div.optionGroup ul li.qualifier",
    "option_item_selected": "div.optionGroup ul li.qualifier.selected",
}

# =============================================================================
# Module Selector (Left Navigation)
# =============================================================================

MODULE_SELECTOR = {
    "container": "#moduleSelectorContainer",
    "home": "li.home a",
    "one_search": "li.oneView a",
    "estimate_guide": "li.partsAndLabor a",
    "quotes": "li.quotes a",
    "maintenance": "li.maintenance a",
    "suretrack": "li.community a",
    "service_manual": "li.serviceManual a",
    "shop_reports": "li.shopReports a",
}

# =============================================================================
# Quick Access Panel Selectors
# =============================================================================

QUICK_ACCESS = {
    "panel": "#quickAccessPanel",
    "technical_bulletins": "#tsbQuickAccess",
    "common_specs": "#commonSpecsAccess",
    "adas": "#adasCalibrationAccess",
    "fluid_capacities": "#fluidsQuickAccess",
    "tire_info": "#tpmsTireFitmentQuickAccess",
    "reset_procedures": "#resetProceduresAccess",
    "dtc_index": "#dtcIndexAccess",
    "wiring_diagrams": "#wiringDiagramsAccess",
    "component_locations": "#componentLocationsAccess",
    "component_tests": "#ctmQuickAccess",
    "service_manual": "#serviceManualQuickAccess",
}

# =============================================================================
# Search Selectors (1Search)
# =============================================================================

SEARCH = {
    "search_input": "input.searchBox[placeholder*='Enter Codes']",
    "search_submit": "button.submit",
    "search_clear": "button.clear",
    "region_select": "#selectRegion",
    "results_container": ".search-results",
}

# =============================================================================
# Content Area Selectors
# =============================================================================

CONTENT = {
    "tech_content_root": "#ContentRegion",
    "application_region": "#ApplicationRegion",
    "breadcrumb": "#mainBreadCrumb",
    "page_title": "h1",
}

# =============================================================================
# Modal / Popup Selectors
# =============================================================================

MODALS = {
    "modal_dialog": ".modalDialogView",
    "modal_close": ".modalDialogView .close",
    "session_limit_modal": "[class*='session'], .modal:has-text('session')",
    "session_commit_button": "button:has-text('Commit'), button:has-text('Continue')",
    "cookie_banner": "#onetrust-consent-sdk",
    "cookie_accept": "#accept-recommended-btn-handler",
}

# =============================================================================
# Profile / Logout Selectors
# =============================================================================

PROFILE = {
    "menu": "#profileMenu",
    "logout": "#logout",
}

# =============================================================================
# VIN / Plate Lookup Selectors
# =============================================================================

VIN_PLATE_LOOKUP = {
    "accordion_header": "h1:has-text('VIN or Plate')",
    "accordion_content": "#vinPlateAccordion",
    "vin_input": "#vinInput",
    "plate_input": "#plateInput",
    "state_dropdown": "#stateSelect",
    "lookup_button": "#vinPlateLookupButton",
    "results_container": "#vinPlateResults",
}

# =============================================================================
# Wiring Diagram Semantic Search Mapping
# =============================================================================
# Maps common search terms to wiring diagram categories

WIRING_SEMANTIC_MAP = {
    # Starting/Charging
    "alternator": "STARTING/CHARGING",
    "generator": "STARTING/CHARGING",
    "charging": "STARTING/CHARGING",
    "battery": "STARTING/CHARGING",
    "starter": "STARTING/CHARGING",
    "crank": "STARTING/CHARGING",
    "no start": "STARTING/CHARGING",
    # Air Conditioning
    "a/c": "AIR CONDITIONING",
    "ac": "AIR CONDITIONING",
    "air conditioning": "AIR CONDITIONING",
    "compressor": "AIR CONDITIONING",
    "blower": "AIR CONDITIONING",
    "hvac": "AIR CONDITIONING",
    # Brakes
    "abs": "ANTI-LOCK BRAKES",
    "anti-lock": "ANTI-LOCK BRAKES",
    "wheel speed": "ANTI-LOCK BRAKES",
    "brake": "ANTI-LOCK BRAKES",
    # Lights
    "headlight": "HEADLIGHTS",
    "headlamp": "HEADLIGHTS",
    "high beam": "HEADLIGHTS",
    "low beam": "HEADLIGHTS",
    "drl": "HEADLIGHTS",
    "tail light": "EXTERIOR LIGHTS",
    "brake light": "EXTERIOR LIGHTS",
    "turn signal": "EXTERIOR LIGHTS",
    "blinker": "EXTERIOR LIGHTS",
    "backup": "EXTERIOR LIGHTS",
    "reverse light": "EXTERIOR LIGHTS",
    # Other systems
    "horn": "HORN",
    "cruise": "CRUISE CONTROL",
    "speed control": "CRUISE CONTROL",
    "power steering": "ELECTRONIC POWER STEERING",
    "eps": "ELECTRONIC POWER STEERING",
    "wiper": "WIPER/WASHER",
    "washer": "WIPER/WASHER",
    "window": "POWER WINDOWS",
    "door lock": "POWER DOOR LOCKS",
    "lock": "POWER DOOR LOCKS",
    "mirror": "POWER MIRRORS",
    "seat": "POWER SEATS",
    "sunroof": "POWER TOP/SUNROOF",
    "moonroof": "POWER TOP/SUNROOF",
    "radio": "RADIO",
    "speaker": "RADIO",
    "amplifier": "RADIO",
    "cluster": "INSTRUMENT CLUSTER",
    "gauge": "INSTRUMENT CLUSTER",
    "speedometer": "INSTRUMENT CLUSTER",
    "fuel gauge": "INSTRUMENT CLUSTER",
    "fuel pump": "FUEL PUMP",
    "fuel level": "FUEL PUMP",
    "airbag": "AIR BAG",
    "srs": "AIR BAG",
    "restraint": "AIR BAG",
    "network": "DATA LINK CONNECTOR",
    "can": "DATA LINK CONNECTOR",
    "obd": "DATA LINK CONNECTOR",
    "dlc": "DATA LINK CONNECTOR",
    "connector": "INLINE HARNESS CONNECTORS",
    "harness": "INLINE HARNESS CONNECTORS",
    "pinout": "INLINE HARNESS CONNECTORS",
    "ground": "GROUND DISTRIBUTION",
    "grounds": "GROUND DISTRIBUTION",
    "power distribution": "POWER DISTRIBUTION",
    "fuse": "POWER DISTRIBUTION",
}


# =============================================================================
# Helper Functions
# =============================================================================

def get_selector(category: str, key: str, default: str = "") -> str:
    """
    Get a selector by category and key.
    
    Args:
        category: One of: login, vehicle_selector, vehicle_options, 
                  module_selector, quick_access, search, content, modals, profile
        key: The selector key within that category
        default: Default value if not found
        
    Returns:
        Selector string
        
    Example:
        >>> get_selector("vehicle_selector", "year_tab")
        "#qualifierTypeSelector li.year"
    """
    categories = {
        "login": LOGIN,
        "vehicle_selector": VEHICLE_SELECTOR,
        "vehicle_options": VEHICLE_OPTIONS,
        "module_selector": MODULE_SELECTOR,
        "quick_access": QUICK_ACCESS,
        "search": SEARCH,
        "content": CONTENT,
        "modals": MODALS,
        "profile": PROFILE,
        "vin_plate_lookup": VIN_PLATE_LOOKUP,
    }
    
    cat = categories.get(category, {})
    return cat.get(key, default)


def vehicle_value_selector(value: str) -> str:
    """
    Get selector for a vehicle value (year, make, model, engine).
    
    Args:
        value: The value to select (e.g., "2018", "Ford", "F-150")
        
    Returns:
        Selector string
    """
    return VEHICLE_VALUE_TEMPLATE.format(value=value)
