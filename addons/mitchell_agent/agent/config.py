"""
Mitchell Agent Configuration
============================
Configuration management for the polling agent.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
import json

# Load .env from the mitchell_agent directory
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # dotenv not installed, use environment only


class AgentConfig(BaseModel):
    """Configuration for the Mitchell polling agent."""
    
    # Identity
    shop_id: str = Field(..., description="Unique identifier for this shop")
    shop_name: str = Field(default="", description="Human-readable shop name")
    
    # Server connection
    server_url: str = Field(
        default="https://automotive.aurora-sentient.net",
        description="URL(s) of the Autotech AI server(s) - comma-separated for multiple"
    )
    
    @property
    def server_urls(self) -> list[str]:
        """Get list of server URLs to poll (supports comma-separated list)."""
        urls = [u.strip() for u in self.server_url.split(",") if u.strip()]
        return urls if urls else ["https://automotive.aurora-sentient.net"]
    
    # Mitchell credentials (for ShopKeyPro login)
    mitchell_username: str = Field(default="", description="ShopKeyPro username")
    mitchell_password: str = Field(default="", description="ShopKeyPro password")
    
    # Agent behavior
    poll_interval: float = Field(
        default=2.0,
        description="Seconds between polls when no work available"
    )
    error_backoff: float = Field(
        default=10.0,
        description="Seconds to wait after an error before retrying"
    )
    headless: bool = Field(
        default=True,
        description="Run browser in headless mode (true=invisible, false=visible)"
    )
    
    # Chrome settings
    chrome_executable_path: Optional[str] = Field(
        default=None,
        description="Path to Chrome/Chromium executable (auto-detected if not set)"
    )
    chrome_user_data_path: Optional[str] = Field(
        default=None,
        description="Chrome user data directory for session persistence"
    )
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: Optional[str] = Field(default=None, description="Optional log file path")
    
    # Debug settings
    debug_screenshots: bool = Field(
        default=False,
        description="Save screenshots at each tool step to /tmp/navigator_screenshots/"
    )
    
    # Navigator backend settings
    navigator_backend: str = Field(
        default="gemini",
        description="Navigator backend: gemini, ollama, or server"
    )
    
    # Ollama settings (for local AI navigation)
    ollama_url: str = Field(
        default="http://localhost:11434",
        description="URL of the local Ollama server"
    )
    ollama_model: str = Field(
        default="qwen3:8b",
        description="Ollama model for vehicle navigation (qwen3:8b recommended)"
    )
    
    # Scaling / Worker Pool settings
    scaling_mode: str = Field(
        default="single",
        description="Agent scaling mode: single, pool, or ondemand"
    )
    pool_min_workers: int = Field(
        default=1,
        description="Minimum number of workers to keep running (pool mode)"
    )
    pool_max_workers: int = Field(
        default=3,
        description="Maximum number of concurrent workers allowed"
    )
    pool_idle_timeout: int = Field(
        default=300,
        description="Seconds before killing an idle worker (pool mode)"
    )
    pool_base_port: int = Field(
        default=9222,
        description="Starting CDP port number for Chrome instances"
    )
    
    # Navigation timing settings (milliseconds)
    nav_delay_short: int = Field(
        default=300,
        description="Short delay for quick UI updates (ms)"
    )
    nav_delay_medium: int = Field(
        default=1000,
        description="Medium delay for page transitions (ms)"
    )
    nav_delay_long: int = Field(
        default=3000,
        description="Long delay for heavy content loads (ms)"
    )
    nav_delay_ajax: int = Field(
        default=600,
        description="Delay after AJAX requests (ms)"
    )
    nav_delay_step: float = Field(
        default=0.6,
        description="Delay between navigation steps (seconds)"
    )
    nav_delay_modal: float = Field(
        default=1.0,
        description="Delay after modal close (seconds)"
    )


def load_config(config_path: Optional[str] = None) -> AgentConfig:
    """
    Load configuration from file and/or environment variables.
    
    Priority (highest to lowest):
    1. Environment variables (MITCHELL_SHOP_ID, MITCHELL_USERNAME, etc.)
    2. Config file (config.json)
    3. Defaults
    """
    config_dict = {}
    
    # Try to load from config file
    if config_path is None:
        # Look in common locations
        candidates = [
            Path("config.json"),
            Path("mitchell_config.json"),
            Path.home() / ".mitchell-agent" / "config.json",
            Path("/etc/mitchell-agent/config.json"),
        ]
        for candidate in candidates:
            if candidate.exists():
                config_path = str(candidate)
                break
    
    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            config_dict = json.load(f)
    
    # Override with environment variables
    env_mappings = {
        "MITCHELL_SHOP_ID": "shop_id",
        "MITCHELL_SHOP_NAME": "shop_name",
        "MITCHELL_SERVER_URL": "server_url",
        "MITCHELL_USERNAME": "mitchell_username",
        "MITCHELL_PASSWORD": "mitchell_password",
        "MITCHELL_POLL_INTERVAL": "poll_interval",
        "MITCHELL_ERROR_BACKOFF": "error_backoff",
        "MITCHELL_HEADLESS": "headless",
        "MITCHELL_LOG_LEVEL": "log_level",
        "MITCHELL_LOG_FILE": "log_file",
        "CHROME_EXECUTABLE_PATH": "chrome_executable_path",
        "CHROME_USER_DATA_PATH": "chrome_user_data_path",
        "NAVIGATOR_BACKEND": "navigator_backend",
        "OLLAMA_URL": "ollama_url",
        "OLLAMA_MODEL": "ollama_model",
        "MITCHELL_DEBUG_SCREENSHOTS": "debug_screenshots",
        # Scaling options
        "MITCHELL_SCALING_MODE": "scaling_mode",
        "MITCHELL_POOL_MIN_WORKERS": "pool_min_workers",
        "MITCHELL_POOL_MAX_WORKERS": "pool_max_workers",
        "MITCHELL_POOL_IDLE_TIMEOUT": "pool_idle_timeout",
        "MITCHELL_POOL_BASE_PORT": "pool_base_port",
        # Navigation timing options
        "MITCHELL_NAV_DELAY_SHORT": "nav_delay_short",
        "MITCHELL_NAV_DELAY_MEDIUM": "nav_delay_medium",
        "MITCHELL_NAV_DELAY_LONG": "nav_delay_long",
        "MITCHELL_NAV_DELAY_AJAX": "nav_delay_ajax",
        "MITCHELL_NAV_DELAY_STEP": "nav_delay_step",
        "MITCHELL_NAV_DELAY_MODAL": "nav_delay_modal",
    }
    
    for env_var, config_key in env_mappings.items():
        value = os.environ.get(env_var)
        if value is not None:
            # Type conversion
            if config_key in ("poll_interval", "error_backoff", "nav_delay_step", "nav_delay_modal"):
                value = float(value)
            elif config_key in ("headless", "debug_screenshots"):
                # Support multiple truthy/falsy values for user-friendliness
                value = value.lower() in ("true", "1", "yes", "on", "headless")
            elif config_key in ("pool_min_workers", "pool_max_workers", "pool_idle_timeout", "pool_base_port", "nav_delay_short", "nav_delay_medium", "nav_delay_long", "nav_delay_ajax"):
                value = int(value)
            config_dict[config_key] = value
    
    return AgentConfig(**config_dict)


def save_config(config: AgentConfig, config_path: str = "config.json"):
    """Save configuration to file."""
    with open(config_path, "w") as f:
        json.dump(config.model_dump(), f, indent=2)
