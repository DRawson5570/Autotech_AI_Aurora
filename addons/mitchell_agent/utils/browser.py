"""
Browser Utilities
=================
Common browser automation helpers for Playwright.
"""

import asyncio
from pathlib import Path
from typing import Optional, Union
from datetime import datetime

# Type hints for Playwright (avoid import for lighter module)
Page = "playwright.async_api.Page"
Locator = "playwright.async_api.Locator"


async def wait_for_selector(
    page,
    selector: str,
    timeout: int = 10000,
    state: str = "visible"
) -> Optional[any]:
    """
    Wait for a selector to appear on the page.
    
    Args:
        page: Playwright Page instance
        selector: CSS selector or text selector
        timeout: Max wait time in milliseconds
        state: Expected state (visible, attached, hidden, detached)
        
    Returns:
        Locator if found, None if timeout
    """
    try:
        locator = page.locator(selector)
        await locator.wait_for(timeout=timeout, state=state)
        return locator
    except Exception:
        return None


async def safe_click(
    page,
    selector: str,
    timeout: int = 5000,
    delay_before: float = 0.3,
    delay_after: float = 0.5
) -> bool:
    """
    Safely click an element with delays to mimic human behavior.
    
    Args:
        page: Playwright Page instance
        selector: CSS selector or text selector
        timeout: Max wait time in milliseconds
        delay_before: Seconds to wait before clicking
        delay_after: Seconds to wait after clicking
        
    Returns:
        True if click succeeded, False otherwise
    """
    try:
        await asyncio.sleep(delay_before)
        
        locator = page.locator(selector)
        await locator.wait_for(timeout=timeout, state="visible")
        await locator.click()
        
        await asyncio.sleep(delay_after)
        return True
    except Exception:
        return False


async def safe_fill(
    page,
    selector: str,
    value: str,
    timeout: int = 5000,
    clear_first: bool = True
) -> bool:
    """
    Safely fill an input field.
    
    Args:
        page: Playwright Page instance
        selector: CSS selector for input
        value: Value to fill
        timeout: Max wait time in milliseconds
        clear_first: Whether to clear existing value first
        
    Returns:
        True if fill succeeded, False otherwise
    """
    try:
        locator = page.locator(selector)
        await locator.wait_for(timeout=timeout, state="visible")
        
        if clear_first:
            await locator.clear()
        
        await locator.fill(value)
        return True
    except Exception:
        return False


async def take_screenshot(
    page,
    name: str,
    directory: str = "/tmp/mitchell_screenshots",
    full_page: bool = False
) -> Optional[str]:
    """
    Take a screenshot and save to file.
    
    Args:
        page: Playwright Page instance
        name: Screenshot name (without extension)
        directory: Directory to save screenshots
        full_page: Whether to capture full page
        
    Returns:
        Path to saved screenshot, or None if failed
    """
    try:
        Path(directory).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%H%M%S")
        filename = f"{name}_{timestamp}.png"
        filepath = Path(directory) / filename
        
        await page.screenshot(path=str(filepath), full_page=full_page)
        return str(filepath)
    except Exception:
        return None


async def wait_for_network_idle(
    page,
    timeout: int = 5000,
    idle_time: int = 500
) -> bool:
    """
    Wait for network activity to settle.
    
    Args:
        page: Playwright Page instance
        timeout: Max wait time in milliseconds
        idle_time: How long network must be idle
        
    Returns:
        True if network became idle, False if timeout
    """
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout)
        await asyncio.sleep(idle_time / 1000)
        return True
    except Exception:
        return False


async def scroll_into_view(page, selector: str) -> bool:
    """
    Scroll an element into view.
    
    Args:
        page: Playwright Page instance
        selector: CSS selector for element
        
    Returns:
        True if successful, False otherwise
    """
    try:
        await page.locator(selector).scroll_into_view_if_needed()
        return True
    except Exception:
        return False


async def get_text_content(page, selector: str, timeout: int = 5000) -> Optional[str]:
    """
    Get text content of an element.
    
    Args:
        page: Playwright Page instance
        selector: CSS selector
        timeout: Max wait time in milliseconds
        
    Returns:
        Text content or None if not found
    """
    try:
        locator = page.locator(selector)
        await locator.wait_for(timeout=timeout, state="visible")
        return await locator.text_content()
    except Exception:
        return None


async def element_exists(page, selector: str, timeout: int = 1000) -> bool:
    """
    Check if an element exists on the page.
    
    Args:
        page: Playwright Page instance
        selector: CSS selector
        timeout: Max wait time in milliseconds
        
    Returns:
        True if element exists, False otherwise
    """
    try:
        locator = page.locator(selector)
        await locator.wait_for(timeout=timeout, state="attached")
        return True
    except Exception:
        return False


async def get_element_count(page, selector: str) -> int:
    """
    Count elements matching a selector.
    
    Args:
        page: Playwright Page instance
        selector: CSS selector
        
    Returns:
        Number of matching elements
    """
    try:
        return await page.locator(selector).count()
    except Exception:
        return 0
