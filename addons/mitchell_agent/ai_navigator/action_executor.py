"""
Action Executor for AI-Driven Navigation
=========================================

Executes the actions decided by the AI navigator.
Handles clicks, typing, scrolling, back navigation, modal closing.
"""

import asyncio
import logging
import random
from typing import Optional

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from .ai_navigator import ActionType, NavigationAction
from .timing import TIMEOUT_ACTION, TIMEOUT_MODAL_CLOSE

log = logging.getLogger(__name__)


async def human_delay(min_ms: int = 200, max_ms: int = 600) -> None:
    """Add random delay to mimic human behavior."""
    delay = random.randint(min_ms, max_ms) / 1000.0
    await asyncio.sleep(delay)


class ActionExecutor:
    """
    Executes navigation actions on a Playwright page.
    
    Handles:
    - Click with retry and scroll-into-view
    - Type with human-like delays
    - Scroll up/down
    - Browser back
    - Modal close (tries multiple strategies)
    """
    
    def __init__(self, page: Page, action_timeout: float = None):
        """
        Initialize executor.
        
        Args:
            page: Playwright Page object
            action_timeout: Timeout for actions in seconds (default from config)
        """
        self.page = page
        timeout = action_timeout if action_timeout is not None else TIMEOUT_ACTION
        self.action_timeout = timeout * 1000  # Convert to ms
    
    async def execute(self, action: NavigationAction) -> bool:
        """
        Execute a navigation action.
        
        Args:
            action: The NavigationAction to execute
            
        Returns:
            True if action succeeded, False otherwise
        """
        try:
            if action.action_type == ActionType.CLICK:
                return await self._execute_click(action)
            
            elif action.action_type == ActionType.TYPE:
                return await self._execute_type(action)
            
            elif action.action_type == ActionType.SCROLL:
                return await self._execute_scroll(action)
            
            elif action.action_type == ActionType.BACK:
                return await self._execute_back(action)
            
            elif action.action_type == ActionType.CLOSE_MODAL:
                return await self._execute_close_modal(action)
            
            elif action.action_type == ActionType.WAIT:
                await asyncio.sleep(1)
                return True
            
            elif action.action_type in (ActionType.EXTRACT_DATA, ActionType.DONE, ActionType.FAIL):
                # These are terminal actions, no execution needed
                return True
            
            else:
                log.warning(f"Unknown action type: {action.action_type}")
                return False
                
        except Exception as e:
            log.error(f"Action execution failed: {e}")
            return False
    
    async def _execute_click(self, action: NavigationAction) -> bool:
        """Execute a click action."""
        selector = action.selector
        if not selector:
            log.error("Click action missing selector")
            return False
        
        log.info(f"Clicking: {selector}")
        
        try:
            # Add human delay before click
            await human_delay(100, 300)
            
            # Handle different selector types
            if ":has-text(" in selector:
                # Playwright text selector
                locator = self.page.locator(selector)
            else:
                # CSS selector
                locator = self.page.locator(selector)
            
            # Check if multiple elements match - use first visible one
            count = await locator.count()
            if count > 1:
                log.info(f"Multiple elements ({count}) match selector, using first visible")
                # Try to find a more specific visible one
                for i in range(count):
                    nth_locator = locator.nth(i)
                    if await nth_locator.is_visible():
                        locator = nth_locator
                        log.info(f"Using element {i} which is visible")
                        break
                else:
                    # If none visible, just use first
                    locator = locator.first
            
            # Wait for element to be visible
            await locator.wait_for(state="visible", timeout=self.action_timeout)
            
            # Scroll into view if needed
            await locator.scroll_into_view_if_needed()
            await human_delay(50, 150)
            
            # Click
            await locator.click(timeout=self.action_timeout)
            
            # Wait for any navigation or dynamic content
            await human_delay(300, 600)
            
            log.info(f"Click successful: {selector}")
            return True
            
        except PlaywrightTimeout:
            log.warning(f"Click timeout: {selector}")
            return False
        except Exception as e:
            log.error(f"Click failed: {selector} - {e}")
            return False
    
    async def _execute_type(self, action: NavigationAction) -> bool:
        """Execute a type action."""
        selector = action.selector
        text = action.text
        
        if not selector or not text:
            log.error("Type action missing selector or text")
            return False
        
        log.info(f"Typing into: {selector}")
        
        try:
            await human_delay(100, 200)
            
            locator = self.page.locator(selector)
            await locator.wait_for(state="visible", timeout=self.action_timeout)
            
            # Clear existing content
            await locator.clear()
            await human_delay(50, 100)
            
            # Type with human-like delay
            await locator.type(text, delay=random.randint(30, 80))
            
            log.info(f"Typed: {text[:20]}...")
            return True
            
        except Exception as e:
            log.error(f"Type failed: {e}")
            return False
    
    async def _execute_scroll(self, action: NavigationAction) -> bool:
        """Execute a scroll action."""
        direction = action.text or "down"
        
        log.info(f"Scrolling {direction}")
        
        try:
            if direction == "down":
                await self.page.evaluate("window.scrollBy(0, 500)")
            else:
                await self.page.evaluate("window.scrollBy(0, -500)")
            
            await human_delay(200, 400)
            return True
            
        except Exception as e:
            log.error(f"Scroll failed: {e}")
            return False
    
    async def _execute_back(self, action: NavigationAction) -> bool:
        """Execute browser back navigation - DISABLED for safety."""
        log.warning("go_back is disabled - browser back is too dangerous")
        # Don't actually do anything - browser back can navigate away from ShopKeyPro
        return False
    
    async def _execute_close_modal(self, action: NavigationAction) -> bool:
        """
        Close any open modal/dialog.
        
        Tries multiple strategies:
        1. Click close button (X)
        2. Click overlay/backdrop
        3. Press Escape
        """
        log.info("Closing modal")
        
        try:
            # Strategy 1: Look for close buttons (ShopKeyPro-specific first)
            close_selectors = [
                ".modalDialogView span.close",  # ShopKeyPro modal X button
                ".modalDialogView .close",
                "span.close",  # Generic ShopKeyPro close
                ".modal .close",
                "[aria-label='Close']",
                ".modal-close",
                ".dialog-close",
                "button.close",
                ".modal .btn-close",
                "[data-dismiss='modal']",
                "input[data-action='Cancel']",  # ShopKeyPro cancel button
            ]
            
            for sel in close_selectors:
                try:
                    locator = self.page.locator(sel).first
                    if await locator.is_visible():
                        await locator.click(timeout=TIMEOUT_MODAL_CLOSE)
                        await human_delay(200, 400)
                        log.info(f"Closed modal via: {sel}")
                        return True
                except:
                    continue
            
            # Strategy 2: Press Escape
            await self.page.keyboard.press("Escape")
            await human_delay(200, 400)
            
            # Check if modal is gone
            modal_selectors = [
                ".modalDialogView",
                ".modal:not(.hidden)",
                "[role='dialog']"
            ]
            
            for sel in modal_selectors:
                try:
                    if await self.page.locator(sel).is_visible():
                        # Modal still visible, Escape didn't work
                        log.warning("Modal still visible after Escape")
                        continue
                except:
                    pass
            
            log.info("Modal closed (or was not present)")
            return True
            
        except Exception as e:
            log.error(f"Close modal failed: {e}")
            return False
    
    async def take_screenshot(self, path: str) -> bool:
        """Take a screenshot for debugging."""
        try:
            await self.page.screenshot(path=path)
            log.info(f"Screenshot saved: {path}")
            return True
        except Exception as e:
            log.error(f"Screenshot failed: {e}")
            return False
