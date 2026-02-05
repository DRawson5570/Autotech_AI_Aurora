"""
Centralized logging configuration for Mitchell AI Navigator.

Log Levels (progressively more verbose):
- ERROR (40)   - Failures only (navigation failed, tool crashed)
- WARNING (30) - Unexpected situations (retries, fallbacks, element not found)
- INFO (20)    - Operation milestones ("Navigation started", "Collected 2 items", "Complete")
- DEBUG (10)   - Step-by-step flow (step numbers, tool names, brief results)
- TRACE (5)    - Full prompts and responses (entire system prompt, user message, raw AI output)

Usage:
    from .logging_config import get_logger, log_trace
    
    logger = get_logger(__name__)
    logger.info("Navigation started")
    logger.debug("Step 1: clicking element 22")
    log_trace("SYSTEM_PROMPT", system_prompt)
    log_trace("AI_RESPONSE", response_text)

Environment Variables:
    MITCHELL_LOG_LEVEL - Set log level (ERROR, WARNING, INFO, DEBUG, TRACE)
                         Default: INFO for production, DEBUG for development
    MITCHELL_LOG_DIR   - Directory for log files (default: /tmp/mitchell_logs)
"""

import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from datetime import datetime

# Custom TRACE level (more verbose than DEBUG)
TRACE = 5
logging.addLevelName(TRACE, "TRACE")

def trace(self, message, *args, **kwargs):
    """Log at TRACE level (most verbose - full prompts/responses)."""
    if self.isEnabledFor(TRACE):
        self._log(TRACE, message, args, **kwargs)

# Add trace method to Logger class
logging.Logger.trace = trace

# Singleton state
_initialized = False
_main_logger = None
_trace_logger = None
_log_dir = None

def _detect_environment() -> str:
    """Detect if we're in dev or prod environment."""
    # Check for common dev indicators
    if os.environ.get('MITCHELL_ENV') == 'development':
        return 'development'
    if os.environ.get('MITCHELL_ENV') == 'production':
        return 'production'
    
    # Check hostname
    hostname = os.uname().nodename.lower()
    if 'hp6' in hostname or 'prod' in hostname:
        return 'production'
    
    # Check if running from common dev paths
    cwd = os.getcwd()
    if '/home/' in cwd and 'autotech_ai' in cwd:
        return 'development'
    
    # Default to production (safer)
    return 'production'

def _get_default_level() -> int:
    """Get default log level based on environment."""
    env = _detect_environment()
    if env == 'development':
        return logging.DEBUG
    return logging.INFO

def _parse_level(level_str: str) -> int:
    """Parse log level string to int."""
    level_map = {
        'TRACE': TRACE,
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
    }
    return level_map.get(level_str.upper(), logging.INFO)

def _setup_logging():
    """Initialize logging configuration. Called once."""
    global _initialized, _main_logger, _trace_logger, _log_dir
    
    if _initialized:
        return
    
    # Get log directory
    _log_dir = Path(os.environ.get('MITCHELL_LOG_DIR', '/tmp/mitchell_logs'))
    _log_dir.mkdir(parents=True, exist_ok=True)
    
    # Get log level
    level_str = os.environ.get('MITCHELL_LOG_LEVEL', '')
    if level_str:
        level = _parse_level(level_str)
    else:
        level = _get_default_level()
    
    # Common format
    detailed_fmt = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    simple_fmt = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # === Main Logger (navigator.log) ===
    # Operations, steps, results - rotates daily, keeps 7 days
    _main_logger = logging.getLogger('mitchell.navigator')
    _main_logger.setLevel(level)
    _main_logger.handlers.clear()
    _main_logger.propagate = False
    
    main_handler = TimedRotatingFileHandler(
        _log_dir / 'navigator.log',
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )
    main_handler.setLevel(level)
    main_handler.setFormatter(detailed_fmt)
    _main_logger.addHandler(main_handler)
    
    # === Trace Logger (ai_trace.log) ===
    # Full prompts and responses - rotates daily, keeps 3 days (large files)
    # Only logs when main level is TRACE or DEBUG
    _trace_logger = logging.getLogger('mitchell.trace')
    _trace_logger.setLevel(level)  # Respect main log level
    _trace_logger.handlers.clear()
    _trace_logger.propagate = False
    
    trace_handler = TimedRotatingFileHandler(
        _log_dir / 'ai_trace.log',
        when='midnight',
        interval=1,
        backupCount=3,
        encoding='utf-8'
    )
    trace_handler.setLevel(TRACE)
    trace_handler.setFormatter(detailed_fmt)
    _trace_logger.addHandler(trace_handler)
    
    # Log startup info
    env = _detect_environment()
    _main_logger.info(f"=== Mitchell Navigator Logging Initialized ===")
    _main_logger.info(f"Environment: {env}, Level: {logging.getLevelName(level)}")
    _main_logger.info(f"Log directory: {_log_dir}")
    
    _initialized = True

def get_logger(name: str = None) -> logging.Logger:
    """
    Get a logger for the given module name.
    
    All loggers are children of 'mitchell.navigator' and inherit its config.
    
    Args:
        name: Module name (typically __name__). If None, returns root navigator logger.
    
    Returns:
        Configured logger instance
    """
    _setup_logging()
    
    if name is None:
        return _main_logger
    
    # Create child logger
    # Convert 'addons.mitchell_agent.ai_navigator.an_tools' -> 'mitchell.navigator.an_tools'
    short_name = name.split('.')[-1] if '.' in name else name
    child_logger = logging.getLogger(f'mitchell.navigator.{short_name}')
    
    return child_logger

def log_trace(category: str, content: str, truncate: bool = False):
    """
    Log full content to trace log (prompts, responses, page states).
    
    Only logs if TRACE level is enabled. Use for:
    - SYSTEM_PROMPT: Full system prompt sent to AI
    - USER_MESSAGE: Full user message with page state
    - AI_RESPONSE: Raw AI response text
    - PAGE_STATE: Full page element list
    - TOOL_RESULT: Detailed tool execution result
    
    Args:
        category: Label for the content (e.g., 'SYSTEM_PROMPT', 'AI_RESPONSE')
        content: The full content to log
        truncate: If True, truncate to 10000 chars (for massive content)
    """
    _setup_logging()
    
    if not _trace_logger.isEnabledFor(TRACE):
        return
    
    if truncate and len(content) > 10000:
        content = content[:10000] + f"\n... [TRUNCATED - {len(content)} total chars]"
    
    separator = "=" * 60
    _trace_logger.log(TRACE, f"\n{separator}\n[{category}]\n{separator}\n{content}\n{separator}")

def log_step(step: int, max_steps: int, action: str, details: str = ""):
    """
    Log a navigation step with consistent formatting.
    
    Args:
        step: Current step number (1-based)
        max_steps: Maximum steps allowed
        action: What action is being taken (e.g., "CLICK", "EXTRACT")
        details: Additional details about the action
    """
    _setup_logging()
    _main_logger.info(f"[Step {step}/{max_steps}] {action}: {details}")

def log_navigation_start(goal: str, vehicle: dict):
    """Log the start of a navigation session."""
    _setup_logging()
    vehicle_str = f"{vehicle.get('year', '?')} {vehicle.get('make', '?')} {vehicle.get('model', '?')}"
    _main_logger.info(f"{'='*60}")
    _main_logger.info(f"NAVIGATION START: {goal}")
    _main_logger.info(f"Vehicle: {vehicle_str}")
    _main_logger.info(f"{'='*60}")

def log_navigation_end(success: bool, steps: int, items_collected: int = 0, images: int = 0):
    """Log the end of a navigation session."""
    _setup_logging()
    status = "SUCCESS" if success else "FAILED"
    _main_logger.info(f"{'='*60}")
    _main_logger.info(f"NAVIGATION {status}: {steps} steps, {items_collected} items, {images} images")
    _main_logger.info(f"{'='*60}")

def get_log_dir() -> Path:
    """Get the current log directory path."""
    _setup_logging()
    return _log_dir
