"""
Session Management
==================
Handles ShopKeyPro login/logout and session timeout.
"""

import asyncio
import logging
import time
from typing import Optional

log = logging.getLogger(__name__)

# Session timeout - if no activity for this long, logout
SESSION_TIMEOUT_SECONDS = 300  # 5 minutes


class SessionManager:
    """
    Manages ShopKeyPro session lifecycle.
    
    Features:
    - Automatic login when needed
    - Session reuse for consecutive requests
    - Timeout-based automatic logout
    - Safe cleanup on errors
    
    Usage:
        session = SessionManager(api)
        await session.ensure_logged_in()
        # ... do work ...
        await session.logout()
    """
    
    def __init__(self, api):
        """
        Initialize session manager.
        
        Args:
            api: MitchellAPI instance
        """
        self._api = api
        self._logged_in = False
        self._last_activity: Optional[float] = None
        self._timeout_task: Optional[asyncio.Task] = None
    
    @property
    def is_logged_in(self) -> bool:
        """Check if session is active."""
        return self._logged_in
    
    def update_activity(self):
        """Update last activity timestamp."""
        self._last_activity = time.time()
    
    async def ensure_logged_in(self) -> bool:
        """
        Ensure logged into ShopKeyPro.
        
        Returns:
            True if logged in successfully
        """
        if self._logged_in:
            log.info("Reusing existing ShopKeyPro session")
            self.update_activity()
            return True
        
        log.info("Logging in to ShopKeyPro...")
        connected = await self._api.connect()
        if connected:
            self._logged_in = True
            self.update_activity()
            log.info("✅ Logged in to ShopKeyPro")
            return True
        else:
            log.error("Failed to connect to ShopKeyPro")
            return False
    
    async def logout(self):
        """
        Logout from ShopKeyPro.
        
        Safe to call multiple times.
        """
        if not self._logged_in:
            return
        
        try:
            if self._api:
                # Close any modals first
                await self._close_modals()
                await self._api.logout()
                log.info("✅ Logged out of ShopKeyPro")
        except Exception as e:
            log.error(f"Error during logout: {e}")
        finally:
            self._logged_in = False
            self._last_activity = None
    
    async def _close_modals(self):
        """Close any open modals before logout."""
        if not self._api or not self._api._page:
            return
        
        try:
            await self._api._page.evaluate('''() => {
                document.querySelector("input[data-action='Cancel']")?.click();
                document.querySelector(".modalDialogView .close")?.click();
            }''')
            await asyncio.sleep(0.3)
        except Exception:
            pass
    
    async def start_timeout_watcher(self):
        """Start background task to logout on inactivity."""
        self._timeout_task = asyncio.create_task(self._timeout_watcher())
    
    async def stop_timeout_watcher(self):
        """Stop the timeout watcher task."""
        if self._timeout_task:
            self._timeout_task.cancel()
            try:
                await self._timeout_task
            except asyncio.CancelledError:
                pass
            self._timeout_task = None
    
    async def _timeout_watcher(self):
        """Background task that logs out after inactivity."""
        while True:
            await asyncio.sleep(10)  # Check every 10 seconds
            
            if self._logged_in and self._last_activity:
                idle_time = time.time() - self._last_activity
                if idle_time > SESSION_TIMEOUT_SECONDS:
                    log.info(f"Session timeout ({idle_time:.0f}s idle) - logging out")
                    await self.logout()
