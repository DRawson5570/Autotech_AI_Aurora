"""
Logging Utilities
=================
Consistent logging setup for Mitchell Agent components.
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    name: str = "mitchell-agent"
) -> logging.Logger:
    """
    Set up logging with consistent format.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional file path for logging
        name: Logger name
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        file_path = Path(log_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(console_format)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (will be prefixed with 'mitchell.')
        
    Returns:
        Logger instance
    """
    full_name = f"mitchell.{name}" if not name.startswith("mitchell") else name
    return logging.getLogger(full_name)


class ToolLogger:
    """
    Logger for individual tools with file output support.
    
    Usage:
        logger = ToolLogger("wiring_tool", "/tmp/wiring_tool.log")
        logger.info("Processing request")
        logger.debug("Detailed info")
    """
    
    def __init__(self, name: str, log_file: Optional[str] = None, enabled: bool = True):
        self.name = name
        self.log_file = log_file
        self.enabled = enabled
        self._logger = get_logger(name)
        
        if log_file and enabled:
            self._setup_file_handler()
    
    def _setup_file_handler(self):
        """Add file handler if not already present."""
        for handler in self._logger.handlers:
            if isinstance(handler, logging.FileHandler) and handler.baseFilename == self.log_file:
                return
        
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        self._logger.addHandler(file_handler)
    
    def _log(self, level: str, msg: str):
        """Write log message."""
        if not self.enabled:
            return
        getattr(self._logger, level)(msg)
    
    def debug(self, msg: str):
        self._log("debug", msg)
    
    def info(self, msg: str):
        self._log("info", msg)
    
    def warning(self, msg: str):
        self._log("warning", msg)
    
    def error(self, msg: str):
        self._log("error", msg)
    
    def exception(self, msg: str):
        self._log("exception", msg)
