"""
Action Log - Clean transcript of agent actions.

Writes a simple, readable log of just the high-level actions taken.
Separate from verbose debug logs.
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional


# Configurable log path
ACTION_LOG_PATH = os.environ.get("MITCHELL_ACTION_LOG", "/tmp/mitchell_actions.log")

# Create a dedicated logger
_action_logger: Optional[logging.Logger] = None


def _get_action_logger() -> logging.Logger:
    """Get or create the action logger."""
    global _action_logger
    
    if _action_logger is None:
        _action_logger = logging.getLogger("mitchell.actions")
        _action_logger.setLevel(logging.INFO)
        _action_logger.propagate = False  # Don't send to root logger
        
        # Clear any existing handlers
        _action_logger.handlers.clear()
        
        # File handler
        log_path = Path(ACTION_LOG_PATH)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(str(log_path), mode='a')
        file_handler.setLevel(logging.INFO)
        
        # Simple format: timestamp and message
        formatter = logging.Formatter('%(asctime)s | %(message)s', datefmt='%H:%M:%S')
        file_handler.setFormatter(formatter)
        
        _action_logger.addHandler(file_handler)
    
    return _action_logger


def log_action(action: str) -> None:
    """Log a single action."""
    _get_action_logger().info(action)


def log_session_start(goal: str, vehicle: dict) -> None:
    """Log the start of a navigation session."""
    logger = _get_action_logger()
    logger.info("=" * 60)
    logger.info(f"NEW SESSION: {goal}")
    logger.info(f"Vehicle: {vehicle.get('year', '?')} {vehicle.get('make', '?')} {vehicle.get('model', '?')} {vehicle.get('engine', '?')}")
    logger.info("-" * 60)


def log_session_end(success: bool, result: Optional[str] = None, steps: int = 0) -> None:
    """Log the end of a navigation session."""
    logger = _get_action_logger()
    logger.info("-" * 60)
    status = "SUCCESS" if success else "FAILED"
    logger.info(f"SESSION {status} ({steps} steps)")
    if result:
        # Truncate very long results for the log
        result_preview = result[:200] + "..." if len(result) > 200 else result
        logger.info(f"Result: {result_preview}")
    logger.info("=" * 60)
    logger.info("")


def log_click(element_id: int, element_text: str, reason: str = "") -> None:
    """Log a click action."""
    text_preview = element_text[:50] if element_text else "?"
    msg = f"CLICK [{element_id}] '{text_preview}'"
    if reason:
        msg += f"  ({reason})"
    log_action(msg)


def log_click_text(text: str, reason: str = "") -> None:
    """Log a click-by-text action."""
    text_preview = text[:50] if text else "?"
    msg = f"CLICK TEXT '{text_preview}'"
    if reason:
        msg += f"  ({reason})"
    log_action(msg)


def log_extract(label: str, data_preview: str = "") -> None:
    """Log a data extraction."""
    msg = f"EXTRACT '{label}'"
    if data_preview:
        preview = data_preview[:80] if len(data_preview) > 80 else data_preview
        msg += f": {preview}"
    log_action(msg)


def log_capture_diagram(description: str, success: bool = True) -> None:
    """Log a diagram capture."""
    status = "✓" if success else "✗"
    log_action(f"CAPTURE DIAGRAM {status} '{description[:60]}'")


def log_capture_image(description: str, success: bool = True) -> None:
    """Log an image capture."""
    status = "✓" if success else "✗"
    log_action(f"CAPTURE IMAGE {status} '{description[:60]}'")


def log_go_back(reason: str = "") -> None:
    """Log a back navigation."""
    msg = "GO BACK"
    if reason:
        msg += f"  ({reason})"
    log_action(msg)


def log_close_modal(reason: str = "") -> None:
    """Log closing a modal."""
    msg = "CLOSE MODAL"
    if reason:
        msg += f"  ({reason})"
    log_action(msg)


def log_error(error: str) -> None:
    """Log an error."""
    log_action(f"ERROR: {error}")


def log_note(note: str) -> None:
    """Log a general note."""
    log_action(f"NOTE: {note}")


def clear_log() -> None:
    """Clear the action log file."""
    log_path = Path(ACTION_LOG_PATH)
    if log_path.exists():
        log_path.unlink()
    
    # Reset the logger so it recreates the file
    global _action_logger
    if _action_logger:
        _action_logger.handlers.clear()
        _action_logger = None
