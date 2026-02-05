"""
Human-like Delays
=================
Delay functions to mimic human behavior and avoid bot detection.
"""

import asyncio
import random


async def human_delay(min_ms: int = 800, max_ms: int = 1300) -> None:
    """
    Add random delay to mimic human behavior.
    
    Helps avoid bot detection by adding natural timing variations.
    
    Args:
        min_ms: Minimum delay in milliseconds
        max_ms: Maximum delay in milliseconds
    """
    delay = random.randint(min_ms, max_ms) / 1000.0
    await asyncio.sleep(delay)


async def typing_delay() -> None:
    """Add delay appropriate for between keystrokes."""
    await human_delay(50, 150)


async def click_delay() -> None:
    """Add delay appropriate before clicking."""
    await human_delay(300, 600)


async def page_load_delay() -> None:
    """Add delay appropriate after page navigation."""
    await human_delay(1000, 2000)


async def form_submit_delay() -> None:
    """Add delay appropriate after form submission."""
    await human_delay(1500, 2500)
