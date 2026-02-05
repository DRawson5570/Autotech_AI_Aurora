"""
AutoDB Site Indexer.

Crawls Operation CHARM and builds a searchable text index per vehicle.
AI can egrep the index to find exactly where data lives.
"""

import asyncio
import aiohttp
import re
import json
import logging
from pathlib import Path
from typing import Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote

log = logging.getLogger("autodb_agent.indexer")

# Index storage location
INDEX_DIR = Path("/tmp/autodb_indexes")


class SiteIndexer:
    """Crawls and indexes Operation CHARM vehicle pages."""
    
    def __init__(self, base_url: str = "http://automotive.aurora-sentient.net/autodb"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    def _get_index_path(self, vehicle_key: str) -> Path:
        """Get path to index file for a vehicle."""
        INDEX_DIR.mkdir(exist_ok=True)
        safe_key = re.sub(r'[^\w\-]', '_', vehicle_key)
        return INDEX_DIR / f"{safe_key}.idx"
    
    async def fetch_page(self, url: str) -> tuple[str, str]:
        """Fetch page and return (html, final_url)."""
        session = await self._get_session()
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            html = await resp.text()
            return html, str(resp.url)
    
    def extract_content(self, html: str) -> tuple[str, list[dict]]:
        """Extract text content and links from HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Get main content div
        main = soup.find('div', class_='main')
        if not main:
            main = soup.body or soup
        
        # Extract text (cleaned)
        text = main.get_text(separator=' ', strip=True)
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Extract links
        links = []
        for a in main.find_all('a', href=True):
            href = a.get('href', '')
            if href and not href.startswith(('#', 'javascript:', 'mailto:')):
                links.append({
                    'text': a.get_text(strip=True),
                    'href': href,
                })
        
        return text, links
    
    async def crawl_vehicle(self, vehicle_url: str, max_pages: int = 2000) -> list[dict]:
        """
        Crawl all pages under a vehicle URL.
        
        Returns list of {path, title, content} dicts.
        """
        pages = []
        visited = set()
        queue = [vehicle_url]
        
        log.info(f"Starting crawl from {vehicle_url}")
        
        while queue and len(visited) < max_pages:
            url = queue.pop(0)
            
            # Normalize URL
            if not url.startswith('http'):
                url = urljoin(vehicle_url, url)
            
            # Skip if already visited or outside vehicle scope
            if url in visited:
                continue
            if not url.startswith(vehicle_url):
                continue
                
            visited.add(url)
            
            try:
                html, final_url = await self.fetch_page(url)
                text, links = self.extract_content(html)
                
                # Get relative path from vehicle URL
                rel_path = url[len(vehicle_url):].lstrip('/')
                rel_path = unquote(rel_path)
                
                # Get title
                soup = BeautifulSoup(html, 'html.parser')
                title_tag = soup.find('h1')
                title = title_tag.get_text(strip=True) if title_tag else rel_path
                
                pages.append({
                    'path': rel_path or '(root)',
                    'title': title,
                    'content': text[:2000],  # Cap content per page
                })
                
                # Add child links to queue
                for link in links:
                    href = link['href']
                    if not href.startswith('http'):
                        href = urljoin(url + '/', href)
                    if href not in visited and href.startswith(vehicle_url):
                        queue.append(href)
                
                if len(visited) % 50 == 0:
                    log.info(f"Crawled {len(visited)} pages, {len(queue)} in queue")
                    
            except Exception as e:
                log.warning(f"Error crawling {url}: {e}")
                continue
        
        log.info(f"Crawl complete: {len(pages)} pages indexed")
        return pages
    
    async def build_index(self, year: int, make: str, model: str, engine: str = "") -> Path:
        """
        Build searchable index for a vehicle.
        
        Returns path to index file.
        """
        # Find vehicle URL
        vehicle_key = f"{year}_{make}_{model}_{engine}" if engine else f"{year}_{make}_{model}"
        index_path = self._get_index_path(vehicle_key)
        
        # Construct vehicle URL (try common patterns)
        # e.g., /autodb/Jeep%20Truck/2012/Liberty%204WD%20V6-3.7L/
        make_slug = make.replace(' ', '%20')
        
        # Try to find the vehicle listing
        makes_url = f"{self.base_url}/"
        html, _ = await self.fetch_page(makes_url)
        
        # Find make link
        soup = BeautifulSoup(html, 'html.parser')
        make_link = None
        for a in soup.find_all('a', href=True):
            link_text = a.get_text(strip=True).lower()
            if make.lower() in link_text or f"{make.lower()} truck" in link_text:
                make_link = urljoin(makes_url, a['href'])
                break
        
        if not make_link:
            raise ValueError(f"Could not find make: {make}")
        
        # Find year
        html, _ = await self.fetch_page(make_link)
        soup = BeautifulSoup(html, 'html.parser')
        year_link = None
        for a in soup.find_all('a', href=True):
            if a.get_text(strip=True) == str(year):
                year_link = urljoin(make_link, a['href'])
                break
        
        if not year_link:
            raise ValueError(f"Could not find year: {year}")
        
        # Find model (fuzzy match)
        html, _ = await self.fetch_page(year_link)
        soup = BeautifulSoup(html, 'html.parser')
        model_link = None
        model_lower = model.lower()
        engine_lower = (engine or "").lower().replace('.', '').replace('l', '')

        for a in soup.find_all('a', href=True):
            link_text = a.get_text(strip=True).lower()
            if model_lower in link_text:
                # Check engine too if specified
                if engine_lower and engine_lower in link_text.replace('.', '').replace('l', ''):
                    model_link = urljoin(year_link, a['href'])
                    break
                elif not engine_lower:
                    model_link = urljoin(year_link, a['href'])
                    break
        
        if not model_link:
            # Take first model match without engine check
            for a in soup.find_all('a', href=True):
                if model_lower in a.get_text(strip=True).lower():
                    model_link = urljoin(year_link, a['href'])
                    break
        
        if not model_link:
            raise ValueError(f"Could not find model: {model}")
        
        log.info(f"Found vehicle at: {model_link}")
        
        # Crawl the vehicle
        pages = await self.crawl_vehicle(model_link)
        
        # Build index file (grep-friendly format)
        lines = []
        for page in pages:
            # Format: PATH\tTITLE\tCONTENT
            path = page['path']
            title = page['title'].replace('\t', ' ').replace('\n', ' ')
            content = page['content'].replace('\t', ' ').replace('\n', ' ')
            lines.append(f"{path}\t{title}\t{content}")
        
        # Write index
        index_path.write_text('\n'.join(lines), encoding='utf-8')
        log.info(f"Index written to {index_path} ({len(lines)} entries)")
        
        return index_path
    
    def index_exists(self, year: int, make: str, model: str, engine: str) -> bool:
        """Check if index already exists for vehicle."""
        vehicle_key = f"{year}_{make}_{model}_{engine}"
        return self._get_index_path(vehicle_key).exists()
    
    def get_index_path(self, year: int, make: str, model: str, engine: str) -> Optional[Path]:
        """Get index path if it exists."""
        vehicle_key = f"{year}_{make}_{model}_{engine}"
        path = self._get_index_path(vehicle_key)
        return path if path.exists() else None


def egrep_index(index_path: Path, pattern: str, max_results: int = 20) -> list[dict]:
    """
    Search index with extended regex.
    
    Returns list of {path, title, match} dicts.
    """
    results = []
    
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return [{"error": f"Invalid regex: {e}"}]
    
    with open(index_path, 'r', encoding='utf-8') as f:
        for line in f:
            if regex.search(line):
                parts = line.strip().split('\t', 2)
                if len(parts) >= 2:
                    path, title = parts[0], parts[1]
                    content = parts[2] if len(parts) > 2 else ""
                    
                    # Find the actual match with context
                    match = regex.search(content) or regex.search(title)
                    if match:
                        start = max(0, match.start() - 50)
                        end = min(len(content), match.end() + 50)
                        context = content[start:end]
                        if start > 0:
                            context = "..." + context
                        if end < len(content):
                            context = context + "..."
                    else:
                        context = content[:100] + "..." if len(content) > 100 else content
                    
                    results.append({
                        'path': path,
                        'title': title,
                        'match': context,
                    })
                    
                    if len(results) >= max_results:
                        break
    
    return results


async def main():
    """Test indexing."""
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    indexer = SiteIndexer()
    try:
        # Build index for test vehicle
        path = await indexer.build_index(
            year=2012,
            make="Jeep",
            model="Liberty",
            engine="3.7L"
        )
        print(f"Index built: {path}")
        
        # Test egrep
        print("\n=== Testing egrep 'radio|amplifier' ===")
        results = egrep_index(path, r"radio|amplifier")
        for r in results[:5]:
            print(f"  {r['path']}")
            print(f"    {r['match'][:80]}...")
            
    finally:
        await indexer.close()


if __name__ == "__main__":
    asyncio.run(main())
