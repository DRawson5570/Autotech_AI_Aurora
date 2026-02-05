"""
Browser Context Manager
=======================
Handles browser context creation with anti-detection measures.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from playwright.async_api import Browser, BrowserContext

log = logging.getLogger(__name__)


# Default anti-detection script
STEALTH_SCRIPT = r"""
// Prevent webdriver flag
Object.defineProperty(navigator, 'webdriver', { get: () => false, configurable: true });
// Provide Chrome runtime stub
try { window.chrome = window.chrome || { runtime: {} }; } catch(e) {}
// Languages
try { Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] }); } catch(e) {}
// Permissions query override
try {
    const origQuery = navigator.permissions.query;
    navigator.permissions.query = (parameters) =>
        parameters && parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : origQuery(parameters);
} catch(e) {}
// Prevent headless detection via plugins
try { Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] }); } catch(e) {}
// Provide a stable platform and userAgent override if configured
try {
    Object.defineProperty(navigator, 'platform', { get: () => window.__pw_platform || navigator.platform });
    Object.defineProperty(navigator, 'userAgent', { get: () => window.__pw_user_agent || navigator.userAgent });
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => window.__pw_hwc || navigator.hardwareConcurrency || 8 });
} catch(e) {}
"""

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
)


class BrowserContextManager:
    """
    Manages browser context creation with anti-detection stealth.
    
    Usage:
        manager = BrowserContextManager(
            storage_state_path="/path/to/state.json",
            user_agent="...",
            viewport_width=1920,
            viewport_height=1080
        )
        context = await manager.create_context(browser)
    """
    
    def __init__(
        self,
        storage_state_path: Optional[str] = None,
        user_agent: Optional[str] = None,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
    ):
        """
        Initialize context manager.
        
        Args:
            storage_state_path: Path to save/load browser state
            user_agent: Custom user agent string
            viewport_width: Browser viewport width
            viewport_height: Browser viewport height
        """
        self.storage_state_path = storage_state_path
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
    
    async def create_context(self, browser: Browser) -> BrowserContext:
        """
        Create a new browser context with stealth settings.
        
        Args:
            browser: Playwright Browser instance
            
        Returns:
            Configured BrowserContext
        """
        # Ensure storage directory exists
        if self.storage_state_path:
            state_path = Path(self.storage_state_path)
            state_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Context options
        context_kwargs = {
            "user_agent": self.user_agent,
            "viewport": {"width": self.viewport_width, "height": self.viewport_height},
            "locale": "en-US",
            "timezone_id": "America/Los_Angeles",
            "extra_http_headers": {"accept-language": "en-US,en;q=0.9"},
        }
        
        # Load existing state if available
        if self.storage_state_path and Path(self.storage_state_path).exists():
            context = await browser.new_context(
                storage_state=self.storage_state_path,
                **context_kwargs
            )
            log.info("Created context with existing storage state")
        else:
            context = await browser.new_context(**context_kwargs)
            log.info("Created fresh browser context")
        
        # Apply anti-detection scripts
        await self._apply_stealth(context)
        
        return context
    
    async def _apply_stealth(self, context: BrowserContext):
        """Apply anti-detection measures to context."""
        # Main stealth script
        await context.add_init_script(STEALTH_SCRIPT)
        
        # Configure UA/platform based on user agent
        if self.user_agent:
            await context.add_init_script(f"window.__pw_user_agent = '{self.user_agent}';")
        
        # Platform based on UA
        if 'Windows' in self.user_agent:
            await context.add_init_script("window.__pw_platform = 'Win32';")
        else:
            await context.add_init_script("window.__pw_platform = navigator.platform || 'Linux x86_64';")
        
        # Hardware concurrency based on viewport
        hwc = max(2, min(16, self.viewport_width // 200))
        await context.add_init_script(f"window.__pw_hwc = {hwc};")
    
    async def save_state(self, context: BrowserContext):
        """
        Save browser state for future sessions.
        
        Args:
            context: Browser context to save
        """
        if not self.storage_state_path:
            return
        
        try:
            await context.storage_state(path=self.storage_state_path)
            log.info(f"Saved browser state to {self.storage_state_path}")
        except Exception as e:
            log.warning(f"Failed to save browser state: {e}")
