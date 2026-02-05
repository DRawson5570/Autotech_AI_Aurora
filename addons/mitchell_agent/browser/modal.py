"""
Modal Handler
=============
Handles modal dialogs in ShopKeyPro.
"""

import asyncio
import logging
from typing import Optional, Callable, Any

from playwright.async_api import Page, Locator

log = logging.getLogger(__name__)


class ModalHandler:
    """
    Handles modal dialogs in ShopKeyPro.
    
    ShopKeyPro uses modals for:
    - Wiring diagrams
    - TSB lists
    - DTC info
    - Reset procedures
    - Many other data views
    
    Usage:
        handler = ModalHandler(page)
        await handler.wait_for_modal()
        content = await handler.get_modal_content()
        await handler.close_modal()
    """
    
    MODAL_SELECTOR = ".modalDialogView"
    CLOSE_BUTTON_SELECTOR = ".modalDialogView .close"
    
    def __init__(self, page: Page):
        """
        Initialize modal handler.
        
        Args:
            page: Playwright Page instance
        """
        self.page = page
    
    async def is_modal_open(self) -> bool:
        """
        Check if a modal is currently open.
        
        Returns:
            True if modal is visible
        """
        try:
            modal = self.page.locator(self.MODAL_SELECTOR)
            return await modal.is_visible(timeout=1000)
        except Exception:
            return False
    
    async def wait_for_modal(self, timeout: int = 10000) -> bool:
        """
        Wait for a modal to appear.
        
        Args:
            timeout: Maximum wait time in milliseconds
            
        Returns:
            True if modal appeared
        """
        try:
            modal = self.page.locator(self.MODAL_SELECTOR)
            await modal.wait_for(timeout=timeout, state="visible")
            log.debug("Modal opened")
            return True
        except Exception as e:
            log.warning(f"Modal did not appear within timeout: {e}")
            return False
    
    async def close_modal(self) -> bool:
        """
        Close the current modal.
        
        Returns:
            True if modal was closed
        """
        try:
            if not await self.is_modal_open():
                return True  # Already closed
            
            close_btn = self.page.locator(self.CLOSE_BUTTON_SELECTOR)
            
            if await close_btn.is_visible(timeout=2000):
                await close_btn.click()
                await asyncio.sleep(0.3)
                
                # Wait for modal to disappear
                await self.page.locator(self.MODAL_SELECTOR).wait_for(
                    state="hidden",
                    timeout=3000
                )
                log.debug("Modal closed")
                return True
            else:
                log.warning("Close button not found")
                return False
                
        except Exception as e:
            log.error(f"Error closing modal: {e}")
            return False
    
    async def click_in_modal(
        self,
        text: str,
        element_type: str = "a",
        timeout: int = 5000,
    ) -> bool:
        """
        Click an element inside the modal by text.
        
        Args:
            text: Text to match
            element_type: HTML element type (a, button, li, etc.)
            timeout: Wait timeout in milliseconds
            
        Returns:
            True if click successful
        """
        try:
            selector = f"{self.MODAL_SELECTOR} {element_type}:has-text('{text}')"
            loc = self.page.locator(selector).first
            
            if await loc.is_visible(timeout=timeout):
                await loc.click()
                await asyncio.sleep(0.5)
                return True
            else:
                log.warning(f"Element not found in modal: {text}")
                return False
                
        except Exception as e:
            log.error(f"Error clicking in modal: {e}")
            return False
    
    async def get_modal_content(self) -> Optional[str]:
        """
        Get the text content of the modal.
        
        Returns:
            Modal text content or None
        """
        try:
            modal = self.page.locator(self.MODAL_SELECTOR)
            return await modal.text_content()
        except Exception as e:
            log.error(f"Error getting modal content: {e}")
            return None
    
    async def get_modal_html(self) -> Optional[str]:
        """
        Get the HTML content of the modal.
        
        Returns:
            Modal HTML or None
        """
        try:
            modal = self.page.locator(self.MODAL_SELECTOR)
            return await modal.inner_html()
        except Exception as e:
            log.error(f"Error getting modal HTML: {e}")
            return None
    
    async def get_modal_links(self) -> list:
        """
        Get all links inside the modal.
        
        Returns:
            List of dicts with 'text' and 'href'
        """
        links = []
        try:
            link_locs = await self.page.locator(f"{self.MODAL_SELECTOR} a").all()
            
            for loc in link_locs:
                text = await loc.text_content()
                href = await loc.get_attribute("href")
                if text:
                    links.append({
                        "text": text.strip(),
                        "href": href,
                    })
                    
        except Exception as e:
            log.error(f"Error getting modal links: {e}")
        
        return links
    
    async def find_in_modal(
        self,
        selector: str,
        timeout: int = 5000,
    ) -> Optional[Locator]:
        """
        Find an element inside the modal.
        
        Args:
            selector: CSS selector (relative to modal)
            timeout: Wait timeout
            
        Returns:
            Locator or None
        """
        try:
            full_selector = f"{self.MODAL_SELECTOR} {selector}"
            loc = self.page.locator(full_selector).first
            
            if await loc.is_visible(timeout=timeout):
                return loc
        except Exception:
            pass
        
        return None
    
    async def wait_for_modal_content(
        self,
        content_selector: str,
        timeout: int = 10000,
    ) -> bool:
        """
        Wait for specific content to appear in modal.
        
        Args:
            content_selector: Selector for expected content
            timeout: Wait timeout
            
        Returns:
            True if content appeared
        """
        try:
            full_selector = f"{self.MODAL_SELECTOR} {content_selector}"
            await self.page.locator(full_selector).wait_for(
                timeout=timeout,
                state="visible"
            )
            return True
        except Exception:
            return False
    
    async def scroll_modal(self, direction: str = "down", pixels: int = 300):
        """
        Scroll inside the modal.
        
        Args:
            direction: "up" or "down"
            pixels: Number of pixels to scroll
        """
        try:
            modal = self.page.locator(self.MODAL_SELECTOR)
            delta = pixels if direction == "down" else -pixels
            
            await modal.evaluate(f"el => el.scrollBy(0, {delta})")
            await asyncio.sleep(0.2)
            
        except Exception as e:
            log.error(f"Error scrolling modal: {e}")
    
    async def execute_in_modal(
        self,
        callback: Callable[[Locator], Any],
    ) -> Any:
        """
        Execute a callback function with the modal locator.
        
        Useful for custom modal interactions.
        
        Args:
            callback: Async function that receives modal Locator
            
        Returns:
            Result from callback
        """
        try:
            modal = self.page.locator(self.MODAL_SELECTOR)
            if await modal.is_visible(timeout=2000):
                return await callback(modal)
        except Exception as e:
            log.error(f"Error executing in modal: {e}")
        
        return None
    
    async def get_table_data(self) -> list:
        """
        Extract table data from modal.
        
        Returns:
            List of row dicts with column data
        """
        rows = []
        
        try:
            # Get headers
            headers = []
            header_locs = await self.page.locator(
                f"{self.MODAL_SELECTOR} table thead th"
            ).all()
            
            for h in header_locs:
                text = await h.text_content()
                headers.append(text.strip() if text else "")
            
            # Get rows
            row_locs = await self.page.locator(
                f"{self.MODAL_SELECTOR} table tbody tr"
            ).all()
            
            for row_loc in row_locs:
                cells = await row_loc.locator("td").all()
                row_data = {}
                
                for i, cell in enumerate(cells):
                    header = headers[i] if i < len(headers) else f"col_{i}"
                    text = await cell.text_content()
                    row_data[header] = text.strip() if text else ""
                
                if row_data:
                    rows.append(row_data)
                    
        except Exception as e:
            log.error(f"Error extracting table data: {e}")
        
        return rows
    
    async def get_tree_items(self) -> list:
        """
        Extract tree/list items from modal.
        
        Returns:
            List of item dicts with text and optional children
        """
        items = []
        
        try:
            item_locs = await self.page.locator(
                f"{self.MODAL_SELECTOR} li.node, {self.MODAL_SELECTOR} li.usercontrol"
            ).all()
            
            for loc in item_locs:
                text_el = loc.locator("a, span").first
                text = await text_el.text_content()
                
                if text:
                    item = {"text": text.strip()}
                    
                    # Check if it has children
                    children = await loc.locator("ul li").all()
                    if children:
                        item["has_children"] = True
                        item["child_count"] = len(children)
                    
                    items.append(item)
                    
        except Exception as e:
            log.error(f"Error extracting tree items: {e}")
        
        return items
