from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Load .env file from addon directory if it exists
_addon_dir = Path(__file__).parent
_env_file = _addon_dir / ".env"
if _env_file.exists():
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                # Only set if not already in environment (env vars take precedence)
                if key and key not in os.environ:
                    os.environ[key] = value


def _env(key: str, default: str | None = None) -> str | None:
    value = os.getenv(key)
    if value is None:
        return default
    value = value.strip()
    return value if value != "" else default


def _env_bool(key: str, default: bool = False) -> bool:
    v = _env(key)
    if v is None:
        return default
    return v.lower() in {"1", "true", "yes", "y", "on"}


def _env_int(key: str, default: int) -> int:
    v = _env(key)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    aurora_base_url: str
    aurora_poll_path: str
    aurora_submit_path_template: str
    poll_interval_seconds: int

    mitchell_base_url: str
    mitchell_login_url: str
    mitchell_username: str
    mitchell_password: str

    playwright_browser: str
    playwright_headless: bool
    playwright_slow_mo_ms: int
    playwright_nav_timeout_ms: int
    storage_state_path: str

    # Stealth / anti-bot options
    playwright_stealth: bool
    playwright_user_agent: str | None
    playwright_viewport_width: int
    playwright_viewport_height: int

    # Persistent profile options
    playwright_use_persistent_profile: bool
    chrome_user_data_path: str
    chrome_executable_path: str  # Path to system Chrome/Chromium binary
    chrome_cdp_url: str  # CDP URL to connect to existing Chrome (e.g. http://localhost:9222)

    auto_discover_selectors: bool
    selectors_profile_path: str

    # ODA mode (Observe-Decide-Act)
    navigation_mode: str
    oda_max_steps: int
    oda_reasoning_provider: str  # ollama, openai, openrouter, anthropic, google, openai_compatible
    oda_reasoning_api_base_url: str
    oda_reasoning_api_key: str
    oda_reasoning_model: str
    oda_reasoning_max_tokens: int
    oda_reasoning_temperature: float
    
    # Vision model settings (optional, for visual understanding)
    oda_vision_enabled: bool
    oda_vision_model: str  # e.g., qwen3-vl:32b, llava:34b

    # Selectors
    sel_username_input: str
    sel_password_input: str
    sel_login_button: str
    sel_logged_in_sentinel: str

    sel_year_dropdown: str
    sel_make_dropdown: str
    sel_model_dropdown: str
    sel_engine_dropdown: str
    sel_vehicle_apply_button: str

    sel_search_input: str
    sel_search_submit: str
    sel_results_container: str
    sel_content_frame: str
    sel_breadcrumb: str
    sel_page_title: str
    sel_tech_content_root: str

    download_assets: bool
    asset_extensions: tuple[str, ...]
    autotech_api_url: str
    nav_config_refresh_interval_seconds: int


def load_config() -> Config:
    asset_ext = tuple(
        s.strip().lower()
        for s in (_env("ASSET_EXTENSIONS", ".svg,.svgz,.jpg,.jpeg,.png") or "").split(",")
        if s.strip()
    )

    return Config(
        aurora_base_url=_env("AURORA_BASE_URL", "http://automotive.aurora-sentient.net:8082") or "",
        aurora_poll_path=_env("AURORA_POLL_PATH", "/get_task") or "/get_task",
        aurora_submit_path_template=_env(
            "AURORA_SUBMIT_PATH_TEMPLATE", "/submit_gold/{Job_ID}"
        )
        or "/submit_gold/{Job_ID}",
        poll_interval_seconds=_env_int("POLL_INTERVAL_SECONDS", 5),
        mitchell_base_url=_env("MITCHELL_BASE_URL", "") or "",
        mitchell_login_url=_env("MITCHELL_LOGIN_URL", "") or "",
        mitchell_username=_env("MITCHELL_USERNAME", "") or "",
        mitchell_password=_env("MITCHELL_PASSWORD", "") or "",
        playwright_browser=_env("PLAYWRIGHT_BROWSER", "chromium") or "chromium",
        playwright_headless=_env_bool("PLAYWRIGHT_HEADLESS", True),
        playwright_slow_mo_ms=_env_int("PLAYWRIGHT_SLOW_MO_MS", 0),
        playwright_nav_timeout_ms=_env_int("PLAYWRIGHT_NAV_TIMEOUT_MS", 45000),
        storage_state_path=_env("STORAGE_STATE_PATH", "addons/mitchell_agent/storage_state.json")
        or "addons/mitchell_agent/storage_state.json",

        # Stealth / anti-bot options
        playwright_stealth=_env_bool("PLAYWRIGHT_STEALTH", True),
        playwright_user_agent=_env("PLAYWRIGHT_USER_AGENT", None),
        playwright_viewport_width=_env_int("PLAYWRIGHT_VIEWPORT_WIDTH", 1366),
        playwright_viewport_height=_env_int("PLAYWRIGHT_VIEWPORT_HEIGHT", 768),

        # Optional persistent profile to reduce fingerprinting
        playwright_use_persistent_profile=_env_bool("PLAYWRIGHT_USE_PERSISTENT_PROFILE", False),
        chrome_user_data_path=_env("CHROME_USER_DATA_PATH", "") or "",
        chrome_executable_path=_env("CHROME_EXECUTABLE_PATH", "") or "",
        chrome_cdp_url=_env("CHROME_CDP_URL", "") or "",

        auto_discover_selectors=_env_bool("AUTO_DISCOVER_SELECTORS", True),
        selectors_profile_path=_env(
            "SELECTORS_PROFILE_PATH", "addons/mitchell_agent/selectors_profile.json"
        )
        or "addons/mitchell_agent/selectors_profile.json",

        navigation_mode=_env("NAVIGATION_MODE", "scripted") or "scripted",
        oda_max_steps=_env_int("ODA_MAX_STEPS", 24),
        oda_reasoning_provider=_env("ODA_REASONING_PROVIDER", "openai_compatible") or "openai_compatible",
        oda_reasoning_api_base_url=_env("ODA_REASONING_API_BASE_URL", "") or "",
        oda_reasoning_api_key=_env("ODA_REASONING_API_KEY", "") or "",
        oda_reasoning_model=_env("ODA_REASONING_MODEL", "") or "",
        oda_reasoning_max_tokens=_env_int("ODA_REASONING_MAX_TOKENS", 4096),
        oda_reasoning_temperature=float(_env("ODA_REASONING_TEMPERATURE", "0.2") or "0.2"),
        
        # Vision settings
        oda_vision_enabled=_env_bool("ODA_VISION_ENABLED", False),
        oda_vision_model=_env("ODA_VISION_MODEL", "qwen3-vl:32b") or "qwen3-vl:32b",

        sel_username_input=_env("SEL_USERNAME_INPUT", "") or "",
        sel_password_input=_env("SEL_PASSWORD_INPUT", "") or "",
        sel_login_button=_env("SEL_LOGIN_BUTTON", "") or "",
        sel_logged_in_sentinel=_env("SEL_LOGGED_IN_SENTINEL", "") or "",
        sel_year_dropdown=_env("SEL_YEAR_DROPDOWN", "") or "",
        sel_make_dropdown=_env("SEL_MAKE_DROPDOWN", "") or "",
        sel_model_dropdown=_env("SEL_MODEL_DROPDOWN", "") or "",
        sel_engine_dropdown=_env("SEL_ENGINE_DROPDOWN", "") or "",
        sel_vehicle_apply_button=_env("SEL_VEHICLE_APPLY_BUTTON", "") or "",
        sel_search_input=_env("SEL_SEARCH_INPUT", "") or "",
        sel_search_submit=_env("SEL_SEARCH_SUBMIT", "") or "",
        sel_results_container=_env("SEL_RESULTS_CONTAINER", "") or "",
        sel_content_frame=_env("SEL_CONTENT_FRAME", "") or "",
        sel_breadcrumb=_env("SEL_BREADCRUMB", "") or "",
        sel_page_title=_env("SEL_PAGE_TITLE", "") or "",
        sel_tech_content_root=_env("SEL_TECH_CONTENT_ROOT", "") or "",
        download_assets=_env_bool("DOWNLOAD_ASSETS", True),
        asset_extensions=asset_ext,
        autotech_api_url=_env("AUTOTECH_API_URL", "https://automotive.aurora-sentient.net") or "",
        nav_config_refresh_interval_seconds=_env_int("NAV_CONFIG_REFRESH_INTERVAL_SECONDS", 300),
    )
