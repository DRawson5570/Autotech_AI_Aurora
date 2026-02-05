"""
AutoDB Agent Logging Configuration.

Sets up proper file logging for all AutoDB components.
Logs go to /tmp/autodb_agent.log by default.
"""

import logging
import os
import sys
from pathlib import Path

# Default log path
LOG_PATH = os.environ.get("AUTODB_LOG_PATH", "/tmp/autodb_agent.log")


def setup_logging(level: str = "DEBUG") -> None:
    """
    Configure logging for all AutoDB components.
    
    Creates file handler at LOG_PATH and configures all autodb_* loggers.
    """
    log_path = Path(LOG_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Common format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler
    file_handler = logging.FileHandler(log_path, mode='a')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Also log to stderr for service output
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Configure all autodb loggers
    logger_names = [
        "autodb_agent",
        "autodb_agent.navigator",
        "autodb_agent.llm",
        "autodb_agent.parser",
        "autodb_agent.tools",
        "autodb_tool",
    ]
    
    for name in logger_names:
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, level.upper(), logging.DEBUG))
        logger.handlers.clear()  # Remove any existing handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        logger.propagate = False  # Don't propagate to root logger
    
    # Log startup
    log = logging.getLogger("autodb_agent")
    log.info(f"AutoDB logging initialized - log file: {log_path}")


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for an AutoDB component."""
    full_name = f"autodb_agent.{name}" if not name.startswith("autodb") else name
    return logging.getLogger(full_name)
