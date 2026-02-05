"""
AutoDB Agent Configuration.

Centralized configuration for timing, limits, and URLs.
Load from environment variables with sensible defaults.
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

# Load .env from the autodb_agent directory
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)
        print(f"[AutoDB Config] Loaded .env from {env_path}", file=sys.stderr)
    else:
        print(f"[AutoDB Config] No .env at {env_path}", file=sys.stderr)
except ImportError:
    print("[AutoDB Config] dotenv not installed", file=sys.stderr)

# Initialize logging (after env is loaded so LOG_PATH can be overridden)
try:
    from .logging_config import setup_logging
    setup_logging()
except Exception as e:
    print(f"[AutoDB Config] Logging setup failed: {e}", file=sys.stderr)


@dataclass
class AutodbConfig:
    """Configuration for AutoDB Agent."""
    
    # Base URLs
    base_url: str = os.environ.get(
        "AUTODB_BASE_URL", 
        "http://automotive.aurora-sentient.net/autodb"
    )
    
    # LLM Settings
    model: str = os.environ.get("AUTODB_MODEL", "gemini-2.0-flash-lite")
    llm_temperature: float = float(os.environ.get("AUTODB_LLM_TEMPERATURE", "0.1"))
    llm_max_tokens: int = int(os.environ.get("AUTODB_LLM_MAX_TOKENS", "1024"))
    
    # LLM Rate Limiting (Gemini still has quotas)
    llm_max_retries: int = int(os.environ.get("AUTODB_LLM_MAX_RETRIES", "3"))
    llm_retry_base_delay: float = float(os.environ.get("AUTODB_LLM_RETRY_BASE_DELAY", "2.0"))
    llm_delay_between_calls: float = float(os.environ.get("AUTODB_LLM_DELAY", "0.2"))  # Small delay between calls
    
    # Navigation
    max_steps: int = int(os.environ.get("AUTODB_MAX_STEPS", "15"))
    max_links_shown: int = int(os.environ.get("AUTODB_MAX_LINKS", "50"))
    max_content_chars: int = int(os.environ.get("AUTODB_MAX_CONTENT", "4000"))
    max_path_history: int = int(os.environ.get("AUTODB_MAX_PATH_HISTORY", "10"))
    
    # Timeouts (generous - it's our server)
    http_timeout: int = int(os.environ.get("AUTODB_HTTP_TIMEOUT", "60"))
    
    # Ollama settings
    ollama_url: str = os.environ.get("AUTODB_OLLAMA_URL", "http://localhost:11434")
    ollama_num_ctx: int = int(os.environ.get("AUTODB_OLLAMA_NUM_CTX", "12000"))
    ollama_num_predict: int = int(os.environ.get("AUTODB_OLLAMA_NUM_PREDICT", "1024"))


# Global config instance
config = AutodbConfig()


def get_gemini_api_key() -> str | None:
    """Load Gemini API key from environment or file."""
    # Try environment variable first
    key = os.environ.get("GOOGLE_API_KEY")
    if key:
        return key
    
    # Try file fallback
    for path in [
        os.path.expanduser("~/gary_gemini_api_key"),
        os.path.expanduser("~/.config/gemini/api_key.txt"),
    ]:
        try:
            with open(path, 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            continue
    
    return None
