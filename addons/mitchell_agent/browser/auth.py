"""
ShopKeyPro Authentication
=========================
Login and logout handling for ShopKeyPro portal.
"""

import asyncio
import logging
import random
from pathlib import Path
from typing import Optional

from playwright.async_api import BrowserContext, Page

log = logging.getLogger(__name__)


async def human_delay(min_ms: int = 200, max_ms: int = 800) -> None:
    """Add a random delay to mimic human behavior."""
    delay = random.randint(min_ms, max_ms) / 1000.0
    await asyncio.sleep(delay)


class ShopKeyProAuth:
    """
    Handles ShopKeyPro login and logout.
    
    Usage:
        auth = ShopKeyProAuth(
            login_url="https://www1.shopkeypro.com/Login",
            base_url="https://www.shopkeypro.com/#||||||||||||||||||/Home",
            username="user",
            password="pass"
        )
        page = await auth.login(context)
        # ... do work ...
        await auth.logout(page)
    """
    
    # Default selectors for ShopKeyPro login
    SELECTORS = {
        "username": "input#username",
        "password": "input#password",
        "login_button": "#loginButton",
        "logged_in_sentinel": "#vehicleSelectorButton",
        "logout_button": "#btnLogout, button:has-text('Logout')",
    }
    
    def __init__(
        self,
        login_url: str,
        base_url: str,
        username: str,
        password: str,
        nav_timeout_ms: int = 30000,
    ):
        """
        Initialize authentication handler.
        
        Args:
            login_url: ShopKeyPro login page URL
            base_url: Main application URL
            username: ShopKeyPro username
            password: ShopKeyPro password
            nav_timeout_ms: Navigation timeout in milliseconds
        """
        self.login_url = login_url
        self.base_url = base_url
        self.username = username
        self.password = password
        self.nav_timeout_ms = nav_timeout_ms
    
    async def is_logged_in(self, page: Page) -> bool:
        """
        Check if currently logged in to ShopKeyPro.
        
        Args:
            page: Playwright Page instance
            
        Returns:
            True if logged in
        """
        try:
            selector = self.SELECTORS["logged_in_sentinel"]
            await page.locator(selector).wait_for(timeout=3000, state="visible")
            return True
        except Exception:
            return False
    
    async def find_logged_in_page(self, context: BrowserContext) -> Optional[Page]:
        """
        Find an existing logged-in page in the context.
        
        Args:
            context: Browser context to search
            
        Returns:
            Logged-in page or None
        """
        for page in context.pages:
            if 'shopkeypro.com' in page.url.lower():
                if await self.is_logged_in(page):
                    log.info(f"Found existing logged-in page: {page.url}")
                    return page
        return None
    
    async def login(self, context: BrowserContext) -> Page:
        """
        Ensure logged in and return the page.
        
        Args:
            context: Browser context
            
        Returns:
            Logged-in page
            
        Raises:
            Exception: If login fails
        """
        # Check for existing logged-in page
        existing = await self.find_logged_in_page(context)
        if existing:
            return existing
        
        # Create new page
        page = await context.new_page()
        page.set_default_timeout(self.nav_timeout_ms)
        
        try:
            # Try going to base URL first (might be already logged in via cookies)
            await page.goto(self.base_url, wait_until="domcontentloaded")
            
            if await self.is_logged_in(page):
                log.info("Already logged in (session restored)")
                return page
            
            # Need to login
            log.info("Not logged in, proceeding to login page")
            await page.goto(self.login_url, wait_until="domcontentloaded")
            
            # Enter credentials
            await self._enter_credentials(page)
            
            # Submit login
            await self._submit_login(page)
            
            # Wait for login to complete
            await self._wait_for_login(page)
            
            log.info("Login successful")
            return page
            
        except Exception as e:
            log.error(f"Login failed: {e}")
            await page.close()
            raise
    
    async def _enter_credentials(self, page: Page):
        """Enter username and password with human-like typing."""
        username_sel = self.SELECTORS["username"]
        password_sel = self.SELECTORS["password"]
        
        # Username
        log.info("Entering username")
        await human_delay(300, 800)
        username_loc = page.locator(username_sel)
        await username_loc.click()
        await human_delay(200, 500)
        await username_loc.fill("")
        await username_loc.type(self.username, delay=random.randint(30, 80))
        
        # Password
        log.info("Entering password")
        await human_delay(400, 1000)
        password_loc = page.locator(password_sel)
        await password_loc.click()
        await human_delay(200, 400)
        await password_loc.fill("")
        
        # Type password character by character
        for char in self.password:
            await password_loc.press(char)
            await asyncio.sleep(random.uniform(0.03, 0.08))
        
        log.info("Credentials entered")
        await human_delay(300, 700)
    
    async def _submit_login(self, page: Page):
        """Submit the login form."""
        button_sel = self.SELECTORS["login_button"]
        
        try:
            button = page.locator(button_sel)
            await button.wait_for(timeout=5000, state="visible")
            await button.click()
            log.info("Login button clicked")
        except Exception as e:
            log.warning(f"Could not click login button: {e}")
            # Try pressing Enter as fallback
            await page.keyboard.press("Enter")
    
    async def _wait_for_login(self, page: Page, timeout_ms: int = 30000):
        """Wait for login to complete."""
        sentinel_sel = self.SELECTORS["logged_in_sentinel"]
        
        try:
            await page.locator(sentinel_sel).wait_for(
                timeout=timeout_ms,
                state="visible"
            )
        except Exception:
            # Check if there's an error message
            error = await self._get_login_error(page)
            if error:
                raise Exception(f"Login failed: {error}")
            raise Exception("Login timed out waiting for sentinel")
    
    async def _get_login_error(self, page: Page) -> Optional[str]:
        """Check for login error messages."""
        error_selectors = [
            ".error-message",
            ".alert-danger",
            "#errorMessage",
            ".login-error",
        ]
        
        for sel in error_selectors:
            try:
                loc = page.locator(sel)
                if await loc.count() > 0:
                    return await loc.first.text_content()
            except Exception:
                pass
        
        return None
    
    async def logout(self, page: Page) -> bool:
        """
        Logout from ShopKeyPro.
        
        Args:
            page: Logged-in page
            
        Returns:
            True if logout successful
        """
        try:
            # Close any open modals first
            await self._close_modals(page)
            
            # Click logout button
            logout_sel = self.SELECTORS["logout_button"]
            logout_btn = page.locator(logout_sel).first
            
            if await logout_btn.is_visible(timeout=3000):
                await logout_btn.click()
                await asyncio.sleep(1)
                log.info("Logged out successfully")
                return True
            else:
                log.warning("Logout button not found")
                return False
                
        except Exception as e:
            log.error(f"Logout failed: {e}")
            return False
    
    async def _close_modals(self, page: Page):
        """Close any open modal dialogs."""
        try:
            await page.evaluate('''() => {
                document.querySelector("input[data-action='Cancel']")?.click();
                document.querySelector(".modalDialogView .close")?.click();
            }''')
            await asyncio.sleep(0.3)
        except Exception:
            pass
