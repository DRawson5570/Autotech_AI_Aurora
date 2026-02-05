"""
Selector Utilities
==================
Helpers for working with ShopKeyPro UI selectors and modals.
"""

import asyncio
from typing import Optional, Dict, List, Any

from .browser import wait_for_selector, safe_click, element_exists


# Basic selectors needed by utility functions
# (Legacy tools that used the full selector set have been archived)
VEHICLE_SELECTOR = {
    "select_vehicle_button": "#vehicleSelectorButton",
    "cancel_button": "input[data-action='Cancel']",
}

VEHICLE_OPTIONS = {}

MODULE_SELECTOR = {}

QUICK_ACCESS = {}

MODALS = {
    "modal_dialog": ".modalDialogView",
    "modal_close": ".modalDialogView .close",
}


def get_selector(category: str, key: str, default: str = "") -> str:
    """Get a selector by category and key."""
    categories = {
        "vehicle_selector": VEHICLE_SELECTOR,
        "vehicle_options": VEHICLE_OPTIONS,
        "module_selector": MODULE_SELECTOR,
        "quick_access": QUICK_ACCESS,
        "modals": MODALS,
    }
    cat = categories.get(category, {})
    return cat.get(key, default)


def get_selectors(category: str) -> Dict[str, str]:
    """
    Get a dictionary of selectors by category.
    
    Args:
        category: Category name (e.g., "vehicle_selector", "quick_access")
        
    Returns:
        Dictionary of selectors
    """
    categories = {
        "vehicle_selector": VEHICLE_SELECTOR,
        "vehicle_options": VEHICLE_OPTIONS,
        "module_selector": MODULE_SELECTOR,
        "quick_access": QUICK_ACCESS,
        "modals": MODALS,
    }
    return categories.get(category, {})


async def is_modal_open(page) -> bool:
    """
    Check if a modal dialog is currently open.
    
    Args:
        page: Playwright Page instance
        
    Returns:
        True if modal is open
    """
    return await element_exists(page, ".modalDialogView", timeout=500)


async def close_modal(page, timeout: int = 3000) -> bool:
    """
    Close any open modal dialog.
    
    Args:
        page: Playwright Page instance
        timeout: Max wait time in milliseconds
        
    Returns:
        True if modal was closed (or no modal was open)
    """
    if not await is_modal_open(page):
        return True
    
    # Try different close methods
    close_selectors = [
        ".modalDialogView .close",
        ".modalDialogView button:has-text('Close')",
        ".modalDialogView input[data-action='Cancel']",
        ".modalDialogView .modal-close",
    ]
    
    for selector in close_selectors:
        if await safe_click(page, selector, timeout=1000, delay_after=0.3):
            await asyncio.sleep(0.3)
            if not await is_modal_open(page):
                return True
    
    # Try pressing Escape
    try:
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.3)
        return not await is_modal_open(page)
    except Exception:
        return False


async def get_modal_content(page) -> Optional[str]:
    """
    Get the text content of the current modal.
    
    Args:
        page: Playwright Page instance
        
    Returns:
        Modal text content or None if no modal
    """
    if not await is_modal_open(page):
        return None
    
    try:
        locator = page.locator(".modalDialogView")
        return await locator.text_content()
    except Exception:
        return None


async def wait_for_modal(page, timeout: int = 10000) -> bool:
    """
    Wait for a modal to appear.
    
    Args:
        page: Playwright Page instance
        timeout: Max wait time in milliseconds
        
    Returns:
        True if modal appeared
    """
    locator = await wait_for_selector(page, ".modalDialogView", timeout=timeout)
    return locator is not None


async def click_in_modal(page, selector: str, timeout: int = 5000) -> bool:
    """
    Click an element inside the current modal.
    
    Args:
        page: Playwright Page instance
        selector: Selector relative to modal content
        timeout: Max wait time in milliseconds
        
    Returns:
        True if click succeeded
    """
    full_selector = f".modalDialogView {selector}"
    return await safe_click(page, full_selector, timeout=timeout)


def build_text_selector(text: str, tag: str = "*", exact: bool = False) -> str:
    """
    Build a Playwright text selector.
    
    Args:
        text: Text to match
        tag: HTML tag to match (default: any)
        exact: Whether to match exactly
        
    Returns:
        Playwright selector string
        
    Example:
        >>> build_text_selector("Login", "button")
        "button:has-text('Login')"
    """
    if exact:
        return f"{tag}:text-is('{text}')"
    return f"{tag}:has-text('{text}')"


async def get_options_list(page, container_selector: str) -> List[str]:
    """
    Get list of option text values from a container.
    
    Args:
        page: Playwright Page instance
        container_selector: Selector for the options container
        
    Returns:
        List of option text values
    """
    try:
        options = []
        locator = page.locator(f"{container_selector} li")
        count = await locator.count()
        
        for i in range(count):
            text = await locator.nth(i).text_content()
            if text:
                options.append(text.strip())
        
        return options
    except Exception:
        return []
