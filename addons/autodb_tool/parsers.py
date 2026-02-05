"""HTML parsers for the Autodb static site (Operation CHARM).
"""
from __future__ import annotations
from typing import List, Dict
from bs4 import BeautifulSoup


def absolute(base: str, url: str) -> str:
    if url.startswith("http"):
        return url
    return base.rstrip("/") + '/' + url.lstrip('/')


def parse_makes(html: str, base: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    # The site uses lists of links for makes
    for a in soup.select("a"):
        href = a.get('href')
        text = a.get_text(strip=True)
        if href and text:
            # Heuristic: top-level make links have simple text like 'Acura' and href contains '/autodb/Acura/'
            if '/autodb/' in href or href.startswith('autodb/') or href.endswith('/'):
                results.append({"name": text, "url": absolute(base, href)})
    return results


def parse_manual_list(html: str, base: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    # Manuals are linked; we return title and url
    for a in soup.select("a"):
        href = a.get('href')
        text = a.get_text(strip=True)
        if href and text:
            # Filter out header navigation links
            if 'autodb' in href or href.startswith('/') or href.startswith('http'):
                # Avoid re-adding make links to the list
                if text and len(text) > 1 and not text.lower().startswith('home'):
                    results.append({"title": text, "url": absolute(base, href)})
    return results


def parse_manual_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # Extract headings and paragraphs for a concise text
    parts = []
    for tag in soup.select('h1, h2, h3, p'):
        text = tag.get_text(separator=' ', strip=True)
        if text:
            parts.append(text)
    return '\n\n'.join(parts)
