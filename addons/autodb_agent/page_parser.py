"""
AutoDB Page Parser.

Fetches and parses HTML pages from the Operation CHARM site.
Extracts links, content, tables, and determines if page has actual data.
"""

import logging
from typing import Optional
from urllib.parse import unquote, urljoin

import httpx
from bs4 import BeautifulSoup

from .config import config
from .models import PageState

log = logging.getLogger("autodb_agent.parser")


class PageParser:
    """Parses AutoDB HTML pages into PageState objects."""
    
    def __init__(self, base_url: str = None):
        # MUST keep trailing slash for urljoin to work correctly
        base = base_url or config.base_url
        self.base_url = base.rstrip("/") + "/"
        self.client = httpx.AsyncClient(
            timeout=config.http_timeout,
            follow_redirects=True
        )
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def fetch_page(self, url: str) -> tuple[str, str]:
        """Fetch HTML content from URL.
        
        Returns (html, final_url) where final_url may differ from input
        if there were redirects.
        """
        if not url.startswith("http"):
            url = f"{self.base_url}{url.lstrip('/')}"
        
        log.debug(f"Fetching: {url}")
        response = await self.client.get(url)
        response.raise_for_status()
        # Return the final URL after any redirects - important for urljoin
        return response.text, str(response.url)
    
    async def fetch_and_parse(self, url: str) -> PageState:
        """Fetch URL and parse into PageState."""
        html, final_url = await self.fetch_page(url)
        return self.parse_html(html, final_url)
    
    def parse_html(self, html: str, url: str) -> PageState:
        """Parse HTML into PageState."""
        # Use lxml parser - handles unclosed <li> tags correctly
        soup = BeautifulSoup(html, "lxml")
        
        # Extract title
        title = self._extract_title(soup)
        
        # Extract breadcrumb
        breadcrumb = self._extract_breadcrumb(soup)
        
        # Extract links
        links = self._extract_links(soup, url)
        
        # Extract content
        content_text = self._extract_content(soup)
        
        # Extract tables
        tables = self._extract_tables(soup)
        
        # Extract images
        images = self._extract_images(soup, url)
        
        # Detect if this is a data page (has specs/values, not just links)
        has_data = self._detect_data_page(soup, content_text, tables)
        
        return PageState(
            url=url,
            title=title,
            breadcrumb=breadcrumb,
            links=links,
            content_text=content_text,
            tables=tables,
            has_data=has_data,
            images=images,
        )
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title."""
        # Try h1 first
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        
        # Fall back to title tag
        title = soup.find("title")
        if title:
            return title.get_text(strip=True)
        
        return ""
    
    def _extract_breadcrumb(self, soup: BeautifulSoup) -> list:
        """Extract breadcrumb trail."""
        breadcrumb = []
        
        # Look for breadcrumb container
        bc_div = soup.select_one(".breadcrumbs, .breadcrumb, nav[aria-label='breadcrumb']")
        if bc_div:
            for a in bc_div.find_all("a"):
                text = a.get_text(strip=True)
                if text and text.lower() != "home":
                    breadcrumb.append(text)
        
        return breadcrumb
    
    def _extract_links(self, soup: BeautifulSoup, current_url: str) -> list:
        """Extract all clickable links from page.
        
        AutoDB structure:
        - Simple pages: flat <ul> with <li><a href=...> items
        - Complex pages: nested <ul> with folders and sub-items
        
        We extract ALL clickable links (those with href), regardless of nesting.
        For complex pages this might be many links, but we limit display in the model.
        
        Each link includes path context to help disambiguate duplicates.
        Path context comes from:
        1. Parent <li> folder text (for nested structures like vehicle models)
        2. Href path segments (for deep structures like Specifications/...)
        """
        links = []
        seen = set()
        
        # Find the main content area
        main_div = soup.select_one(".main")
        if not main_div:
            main_div = soup.body if soup.body else soup
        
        # Find all clickable links in main content area
        for a in main_div.select("a[href]"):
            href = a.get("href")
            
            # Skip non-navigable hrefs
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue
            
            # Skip breadcrumb links (they have specific class)
            if a.find_parent(class_=["breadcrumbs", "breadcrumb"]):
                continue
            
            text = a.get_text(strip=True)
            if not text:
                continue
            
            # Extract path context
            path_context = self._get_link_context(a, href)
            
            # Resolve relative URLs
            if not href.startswith("http"):
                href = urljoin(current_url, href)
            
            if href not in seen:
                seen.add(href)
                links.append({
                    "text": text,
                    "href": href,
                    "path": path_context,
                })
        
        return links
    
    def _get_link_context(self, a_tag, href: str) -> str:
        """Get context path for a link.
        
        Looks for:
        1. Parent <li> with class 'li-folder' or containing just text (model names)
        2. Href path segments
        """
        from urllib.parse import unquote
        
        # First try: look at parent <li> elements that are folders/categories
        context_parts = []
        parent = a_tag.find_parent("li")
        while parent:
            # Check if this li is a folder (has text before the nested ul)
            parent_li = parent.find_parent("li")
            if parent_li:
                # Get the direct text of parent_li (not nested elements)
                # Look for <a> with name= attribute (folder label) or direct text
                folder_label = parent_li.find("a", attrs={"name": True})
                if folder_label:
                    label_text = folder_label.get_text(strip=True)
                    if label_text and label_text not in context_parts:
                        context_parts.insert(0, label_text)
                else:
                    # Check for direct text content (like model names)
                    for content in parent_li.children:
                        if isinstance(content, str):
                            txt = content.strip()
                            if txt and txt not in context_parts:
                                context_parts.insert(0, txt)
                                break
            parent = parent.find_parent("li")
        
        if context_parts:
            return "/".join(context_parts)
        
        # Fallback: extract from href path
        if "/" in href:
            path_parts = unquote(href).split("/")
            if len(path_parts) > 2:
                return "/".join(path_parts[:-2])
        
        return ""
        
        return links
    
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Extract main content text."""
        content_parts = []
        
        # Look for main content area
        main = soup.select_one(".main, .content, main, article")
        if not main:
            main = soup.body if soup.body else soup
        
        # First try: get all text from main div (handles plain text + <br> layouts)
        main_text = main.get_text(separator="\n", strip=True)
        if main_text:
            # Clean up multiple newlines
            lines = [line.strip() for line in main_text.split('\n') if line.strip()]
            # Filter out very short lines (likely just navigation artifacts)
            lines = [line for line in lines if len(line) > 3]
            if lines:
                return "\n".join(lines[:30])  # Limit to 30 lines
        
        # Fallback: Extract from specific tags (p, h1-h4, li)
        for tag in main.select("h1, h2, h3, h4, p, li"):
            text = tag.get_text(separator=" ", strip=True)
            if text and len(text) > 10:
                content_parts.append(text)
        
        return "\n".join(content_parts[:20])  # Limit to 20 chunks
    
    def _extract_tables(self, soup: BeautifulSoup) -> list:
        """Extract tables as readable text."""
        tables = []
        
        for table in soup.select("table")[:5]:  # Max 5 tables
            rows = []
            for tr in table.select("tr"):
                cells = [td.get_text(strip=True) for td in tr.select("th, td")]
                if any(cells):
                    rows.append(" | ".join(cells))
            
            if rows:
                tables.append("\n".join(rows))
        
        return tables
    
    def _detect_data_page(self, soup: BeautifulSoup, content: str, tables: list) -> bool:
        """Detect if page has actual data (specs, values) vs just navigation links."""
        # Count links - if many links, probably navigation page
        link_count = len(soup.select("a[href]"))
        
        # Strong indicator: lots of links = navigation page
        if link_count > 20:
            return False
        
        # If we have tables with content, likely a data page
        if tables and any(len(t) > 50 for t in tables):
            return True
        
        # If page has diagrams/images, it's a data page
        image_count = len(soup.select("div.oxe-image img, img.big-img"))
        if image_count > 0:
            return True
        
        # Look for spec-like patterns in content
        spec_patterns = [
            " qt", " qts", " quart", " liter", " liters",
            " ft-lb", " ft.lb", " n.m", " n-m", " nm",
            " psi", " kpa", " bar",
            " in.", " mm", " inch",
            " ohm", " volt", " amp",
        ]
        content_lower = content.lower()
        if any(p in content_lower for p in spec_patterns):
            return True
        
        content_length = len(content)
        
        # If mostly links and little content, it's navigation
        if link_count > 10 and content_length < 500:
            return False
        
        # If decent content, probably data
        if content_length > 1000:
            return True
        
        return False
    
    def _extract_images(self, soup: BeautifulSoup, current_url: str) -> list:
        """Extract image URLs from page.
        
        AutoDB images are inside div.oxe-image containers.
        Images use relative paths like /autodb/images/...
        """
        images = []
        
        # Find main content area
        main = soup.select_one(".main, .content, main, article")
        if not main:
            main = soup.body if soup.body else soup
        
        # Look for images in oxe-image containers (AutoDB specific)
        for img_container in main.select("div.oxe-image img, img.big-img"):
            src = img_container.get("src")
            if src:
                # Convert relative to absolute URL
                if not src.startswith("http"):
                    src = urljoin(current_url, src)
                images.append(src)
        
        # Also look for any other images in content area
        for img in main.select("img"):
            src = img.get("src")
            if src and "/icons/" not in src and "/logo" not in src.lower():
                if not src.startswith("http"):
                    src = urljoin(current_url, src)
                if src not in images:
                    images.append(src)
        
        return images
