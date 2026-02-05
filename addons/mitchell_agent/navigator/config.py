"""
Navigator Configuration
=======================
Environment-based configuration for MitchellNavigator.
"""

import os
from dataclasses import dataclass


@dataclass
class NavigatorConfig:
    """
    Navigator configuration from environment.
    
    Environment variables:
        MITCHELL_USERNAME: ShopKeyPro username
        MITCHELL_PASSWORD: ShopKeyPro password
        CHROME_EXECUTABLE_PATH: Path to Chrome binary
        CHROME_USER_DATA_PATH: Chrome user data directory
        MITCHELL_CDP_PORT: CDP port for Chrome
        MITCHELL_HEADLESS: Run Chrome headless (true/false)
        GEMINI_API_KEY: Google Gemini API key
        GEMINI_MODEL: Gemini model name
        VIEWPORT_WIDTH: Browser viewport width
        VIEWPORT_HEIGHT: Browser viewport height
    """
    username: str
    password: str
    chrome_path: str
    chrome_user_data: str
    cdp_port: int
    headless: bool
    gemini_api_key: str
    gemini_model: str
    viewport_width: int
    viewport_height: int
    
    @classmethod
    def from_env(cls) -> "NavigatorConfig":
        """
        Create configuration from environment variables.
        
        Returns:
            NavigatorConfig instance
        """
        return cls(
            username=os.environ.get("MITCHELL_USERNAME", ""),
            password=os.environ.get("MITCHELL_PASSWORD", ""),
            chrome_path=os.environ.get("CHROME_EXECUTABLE_PATH", "/usr/bin/google-chrome"),
            chrome_user_data=os.environ.get("CHROME_USER_DATA_PATH", "/tmp/mitchell-chrome"),
            cdp_port=int(os.environ.get("MITCHELL_CDP_PORT", "9222")),
            headless=os.environ.get("MITCHELL_HEADLESS", "false").lower() == "true",
            gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
            gemini_model=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
            viewport_width=int(os.environ.get("VIEWPORT_WIDTH", "1920")),
            viewport_height=int(os.environ.get("VIEWPORT_HEIGHT", "1080")),
        )
    
    def validate(self) -> list:
        """
        Validate configuration.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if not self.username:
            errors.append("MITCHELL_USERNAME not set")
        if not self.password:
            errors.append("MITCHELL_PASSWORD not set")
        if not self.gemini_api_key:
            errors.append("GEMINI_API_KEY not set")
        
        return errors
