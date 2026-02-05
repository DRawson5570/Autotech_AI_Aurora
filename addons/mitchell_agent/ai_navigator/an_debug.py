"""
Debug logging for Autonomous Navigator.

Captures everything the AI sees and does for debugging.
"""

import json
import os
from datetime import datetime
from typing import Optional

from .an_config import is_debug_enabled, is_verbose

# Import PageState type if available
try:
    from .element_extractor import PageState
except ImportError:
    PageState = None


class ANDebugLogger:
    """
    Dedicated debug logger for autonomous navigator.
    Captures everything the AI sees and does for debugging.
    """
    
    def __init__(self):
        self.enabled = is_debug_enabled()
        self.verbose = is_verbose()
        self.log_file = os.environ.get("MITCHELL_DEBUG_LOG", "/tmp/an_debug.log")
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._file = None
        
        if self.enabled:
            self._file = open(self.log_file, "w")
            self._write_header()
    
    def _write_header(self):
        """Write session header."""
        if self._file:
            self._file.write("=" * 80 + "\n")
            self._file.write(f"AUTONOMOUS NAVIGATOR DEBUG LOG\n")
            self._file.write(f"Session: {self.session_id}\n")
            self._file.write(f"Verbose: {self.verbose}\n")
            self._file.write("=" * 80 + "\n\n")
            self._file.flush()
    
    def log(self, message: str, level: str = "INFO"):
        """Log a message if debug is enabled."""
        if not self.enabled or not self._file:
            return
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self._file.write(f"[{timestamp}] [{level}] {message}\n")
        self._file.flush()
    
    def log_step_start(self, step: int, max_steps: int, goal: str):
        """Log the start of a navigation step."""
        if not self.enabled:
            return
        self._file.write("\n" + "=" * 80 + "\n")
        self._file.write(f"STEP {step}/{max_steps} - Goal: {goal}\n")
        self._file.write("=" * 80 + "\n\n")
        self._file.flush()
    
    def log_page_state(self, page_state, modal_open: bool, page_text: str):
        """Log what we extracted from the page."""
        if not self.enabled:
            return
        
        self.log(f"URL: {page_state.url}")
        self.log(f"Modal Open: {modal_open}")
        self.log(f"Elements Found: {len(page_state.elements)}")
        
        # Log the elements the AI will see
        self._file.write("\n--- ELEMENTS SHOWN TO AI ---\n")
        meaningful = [el for el in page_state.elements if el.text and len(el.text.strip()) > 2]
        
        if modal_open:
            modal_els = [el for el in meaningful if el.in_modal]
            self._file.write(f"[MODAL ELEMENTS: {len(modal_els)} items]\n")
            for el in modal_els[:50]:
                text = el.text.strip().replace('\n', ' ')[:70]
                self._file.write(f"  [{el.id}] {text}\n")
        else:
            self._file.write(f"[PAGE ELEMENTS: {len(meaningful)} items]\n")
            for el in meaningful[:50]:
                text = el.text.strip().replace('\n', ' ')[:70]
                self._file.write(f"  [{el.id}] {text}\n")
        
        if self.verbose:
            self._file.write("\n--- PAGE TEXT ---\n")
            self._file.write(page_text + "\n")
        
        self._file.flush()
    
    def log_prompt(self, system_prompt: str, user_message: str):
        """Log the prompts sent to the AI."""
        if not self.enabled:
            return
        
        if self.verbose:
            self._file.write("\n--- SYSTEM PROMPT ---\n")
            self._file.write(system_prompt + "\n")
            self._file.write("\n--- USER MESSAGE ---\n")
            self._file.write(user_message + "\n")
        else:
            # Just log summary
            self._file.write(f"\n[Prompt: {len(system_prompt)} chars system, {len(user_message)} chars user]\n")
        
        self._file.flush()
    
    def log_ai_response(self, response: dict, tool_calls: list):
        """Log what the AI responded with."""
        if not self.enabled:
            return
        
        self._file.write("\n--- AI RESPONSE ---\n")
        
        # Log the tool call(s)
        if tool_calls:
            for tc in tool_calls:
                func = tc.get("function", {})
                name = func.get("name", "unknown")
                args = func.get("arguments", {})
                self._file.write(f"TOOL: {name}\n")
                self._file.write(f"ARGS: {json.dumps(args, indent=2)}\n")
        else:
            content = response.get("message", {}).get("content", "")
            self._file.write(f"TEXT RESPONSE: {content}\n")
        
        self._file.flush()
    
    def log_tool_result(self, tool_name: str, success: bool, result: str):
        """Log the result of executing a tool."""
        if not self.enabled:
            return
        
        status = "✓" if success else "✗"
        self._file.write(f"\n--- TOOL RESULT ---\n")
        self._file.write(f"{status} {tool_name}: {result}\n")
        self._file.flush()
    
    def log_navigation_complete(self, success: bool, steps: int, reason: str = None):
        """Log navigation completion."""
        if not self.enabled:
            return
        
        self._file.write("\n" + "=" * 80 + "\n")
        self._file.write("NAVIGATION COMPLETE\n")
        self._file.write("=" * 80 + "\n")
        self._file.write(f"Success: {success}\n")
        self._file.write(f"Steps: {steps}\n")
        if reason:
            self._file.write(f"Reason: {reason}\n")
        self._file.flush()
    
    def close(self):
        """Close the log file."""
        if self._file:
            self._file.close()
            self._file = None


# Global debug logger instance (lazy init)
_debug_logger: Optional[ANDebugLogger] = None


def get_debug_logger() -> ANDebugLogger:
    """Get or create the debug logger."""
    global _debug_logger
    if _debug_logger is None:
        _debug_logger = ANDebugLogger()
    return _debug_logger
