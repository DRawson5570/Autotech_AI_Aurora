"""Simple Autodb API client and helpers.
"""
from __future__ import annotations

import logging
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)


class AutodbAPI:
    def __init__(self, base_url: str = "http://automotive.aurora-sentient.net/autodb"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def get_makes(self) -> List[Dict[str, str]]:
        """Return list of makes available on the site as dicts with name and url."""
        r = self.session.get(self.base_url, timeout=10)
        r.raise_for_status()
        return parse_makes(r.text, self.base_url)

    def get_manual_list(self, make_path: str) -> List[Dict[str, str]]:
        """Return list of manuals for a make. make_path can be a relative path or full URL."""
        url = make_path if make_path.startswith("http") else f"{self.base_url}/{make_path.lstrip('/') }"
        r = self.session.get(url, timeout=10)
        r.raise_for_status()
        return parse_manual_list(r.text, url)

    def get_manual_text(self, manual_url: str) -> str:
        """Fetch manual page and return cleaned text (headings and paragraphs)."""
        url = manual_url if manual_url.startswith("http") else f"{self.base_url}/{manual_url.lstrip('/') }"
        r = self.session.get(url, timeout=10)
        r.raise_for_status()
        return parse_manual_content(r.text)


# Lightweight parser wrappings so application code can import from here
from .parsers import parse_makes, parse_manual_list, parse_manual_content  # noqa: E402, F401
