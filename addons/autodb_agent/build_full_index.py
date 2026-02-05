#!/usr/bin/env python3
"""
Build full site index for Operation CHARM.

Creates a single unified index file that can be grepped across all vehicles.

Usage:
    # Test batch (5 makes)
    python -m addons.autodb_agent.build_full_index --test
    
    # Full site (all makes)
    python -m addons.autodb_agent.build_full_index --full
    
    # Resume interrupted build
    python -m addons.autodb_agent.build_full_index --resume
    
    # Specific makes
    python -m addons.autodb_agent.build_full_index --makes "Jeep Truck,Ford,Toyota"
"""

import argparse
import asyncio
import aiohttp
import logging
import os
import re
import time
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote, quote
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("full_indexer")

# Default paths
DEFAULT_BASE_URL = "http://automotive.aurora-sentient.net/autodb"
DEFAULT_INDEX_PATH = Path("/tmp/autodb_full_index.tsv")  # For testing
PROD_INDEX_PATH = Path("/prod/autotech_ai/data/autodb_index.tsv")

# Test makes (popular brands, good coverage)
TEST_MAKES = [
    "Jeep Truck",
    "Ford",
    "Ford Truck",
    "Chevrolet",
    "Toyota",
]


class FullSiteIndexer:
    """Crawls entire Operation CHARM site and builds unified index."""
    
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        index_path: Path = DEFAULT_INDEX_PATH,
        max_pages_per_vehicle: int = 2000,
        max_concurrent: int = 50,
        title_only: bool = False,
    ):
        self.base_url = base_url.rstrip('/')
        self.index_path = Path(index_path)
        self.max_pages_per_vehicle = max_pages_per_vehicle
        self.max_concurrent = max_concurrent
        self.title_only = title_only
        self.session: aiohttp.ClientSession = None
        self._write_lock = asyncio.Lock()  # For thread-safe file writes
        
        # Progress tracking
        self.progress_file = self.index_path.with_suffix('.progress')
        self.completed_vehicles = set()
        self.stats = {
            'vehicles_done': 0,
            'vehicles_total': 0,
            'pages_indexed': 0,
            'errors': 0,
            'start_time': None,
        }
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            connector = aiohttp.TCPConnector(limit=self.max_concurrent)
            self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return self.session
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def fetch_page(self, url: str) -> str:
        """Fetch a page, return HTML."""
        session = await self._get_session()
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.text()
                else:
                    log.warning(f"HTTP {resp.status} for {url}")
                    return ""
        except Exception as e:
            log.warning(f"Error fetching {url}: {e}")
            return ""
    
    def extract_links(self, html: str, base_url: str) -> list[dict]:
        """Extract links from HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        for a in soup.find_all('a', href=True):
            href = a.get('href', '')
            text = a.get_text(strip=True)
            if href and not href.startswith(('#', 'javascript:', 'mailto:')):
                full_url = urljoin(base_url + '/', href)
                links.append({'text': text, 'url': full_url})
        return links
    
    def extract_content(self, html: str) -> tuple[str, str]:
        """Extract title and content from HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Title
        h1 = soup.find('h1')
        title = h1.get_text(strip=True) if h1 else ""
        
        # Content
        main = soup.find('div', class_='main')
        if not main:
            main = soup.body or soup
        
        text = main.get_text(separator=' ', strip=True)
        text = re.sub(r'\s+', ' ', text)  # Collapse whitespace
        
        return title, text[:2000]  # Cap content length
    
    async def get_all_makes(self) -> list[str]:
        """Get list of all makes from homepage."""
        html = await self.fetch_page(f"{self.base_url}/")
        links = self.extract_links(html, self.base_url)
        
        makes = []
        for link in links:
            text = link['text']
            # Skip non-make links
            if text.lower() in ('about operation charm', 'home'):
                continue
            if '/' in link['url'].replace(self.base_url, '').strip('/'):
                continue  # Not a top-level make
            makes.append(text)
        
        return makes
    
    async def get_years_for_make(self, make: str) -> list[str]:
        """Get list of years for a make."""
        make_url = f"{self.base_url}/{quote(make)}/"
        html = await self.fetch_page(make_url)
        links = self.extract_links(html, make_url)
        
        years = []
        for link in links:
            text = link['text']
            if text.isdigit() and 1980 <= int(text) <= 2030:
                years.append(text)
        
        return years
    
    async def get_models_for_year(self, make: str, year: str) -> list[dict]:
        """Get list of models for a make/year."""
        year_url = f"{self.base_url}/{quote(make)}/{year}/"
        html = await self.fetch_page(year_url)
        links = self.extract_links(html, year_url)
        
        models = []
        for link in links:
            text = link['text']
            url = link['url']
            # Skip navigation links
            if text.lower() in ('home', 'back', make.lower(), year):
                continue
            if url.rstrip('/').endswith(f"/{year}"):
                continue
            models.append({'name': text, 'url': url})
        
        return models
    
    async def crawl_vehicle(self, vehicle_url: str, vehicle_path: str) -> list[str]:
        """
        Crawl all pages under a vehicle URL.
        
        Returns list of index lines: "full_path\\ttitle\\tcontent"
        In title_only mode, crawls full tree but only extracts path+title (no content).
        """
        lines = []
        visited = set()
        queue = [vehicle_url]
        
        while queue and len(visited) < self.max_pages_per_vehicle:
            url = queue.pop(0)
            
            # Normalize
            if not url.startswith('http'):
                url = urljoin(vehicle_url, url)
            
            if url in visited:
                continue
            if not url.startswith(vehicle_url):
                continue
            
            visited.add(url)
            
            html = await self.fetch_page(url)
            if not html:
                continue
            
            # Build full path
            rel_path = url[len(vehicle_url):].strip('/')
            rel_path = unquote(rel_path)
            full_path = f"{vehicle_path}/{rel_path}" if rel_path else vehicle_path
            
            if self.title_only:
                # Title-only: just get page title from <title> or first <h1>
                soup = BeautifulSoup(html, 'html.parser')
                title_tag = soup.find('title')
                title = title_tag.get_text(strip=True) if title_tag else ''
                if not title:
                    h1 = soup.find('h1')
                    title = h1.get_text(strip=True) if h1 else rel_path
                title = title.replace('\t', ' ').replace('\n', ' ')
                lines.append(f"{full_path}\t{title}\t")
            else:
                # Full crawl: extract title + content
                title, content = self.extract_content(html)
                title = title.replace('\t', ' ').replace('\n', ' ')
                content = content.replace('\t', ' ').replace('\n', ' ')
                lines.append(f"{full_path}\t{title}\t{content}")
            
            # Queue child links (both modes need to discover children)
            links = self.extract_links(html, url)
            for link in links:
                child_url = link['url']
                if child_url not in visited and child_url.startswith(vehicle_url):
                    queue.append(child_url)
            
            # Small delay to be nice to server
            await asyncio.sleep(0.02)
        
        return lines
    
    def load_progress(self):
        """Load progress from file."""
        if self.progress_file.exists():
            self.completed_vehicles = set(
                self.progress_file.read_text().strip().split('\n')
            )
            log.info(f"Loaded progress: {len(self.completed_vehicles)} vehicles completed")
    
    def save_progress(self, vehicle_key: str):
        """Save completed vehicle to progress file."""
        with open(self.progress_file, 'a') as f:
            f.write(f"{vehicle_key}\n")
        self.completed_vehicles.add(vehicle_key)
    
    async def index_vehicle(self, make: str, year: str, model: dict) -> int:
        """Index a single vehicle, return page count."""
        vehicle_url = model['url'].rstrip('/') + '/'
        
        # Extract the full model name from URL (includes body style + engine)
        # URL like: .../Jeep%20Truck/1985/CJ-7%20L4-150%202.5L%20VIN%20U%201-bbl/
        # We want: CJ-7 L4-150 2.5L VIN U 1-bbl
        url_path = vehicle_url.replace(self.base_url, '').strip('/')
        model_from_url = unquote(url_path.split('/')[-1]) if '/' in url_path else model['name']
        
        vehicle_key = f"{make}/{year}/{model_from_url}"
        
        if vehicle_key in self.completed_vehicles:
            log.debug(f"Skipping {vehicle_key} (already done)")
            return 0
        
        vehicle_path = f"{make}/{year}/{model_from_url}"
        
        try:
            lines = await self.crawl_vehicle(vehicle_url, vehicle_path)
            
            if lines:
                # Append to index file (thread-safe)
                async with self._write_lock:
                    with open(self.index_path, 'a', encoding='utf-8') as f:
                        f.write('\n'.join(lines) + '\n')
                    self.save_progress(vehicle_key)
                    self.stats['pages_indexed'] += len(lines)
                    self.stats['vehicles_done'] += 1
            else:
                async with self._write_lock:
                    self.stats['vehicles_done'] += 1
            return len(lines)
            
        except Exception as e:
            log.error(f"Error indexing {vehicle_key}: {e}")
            async with self._write_lock:
                self.stats['errors'] += 1
            return 0
    
    async def build_index(self, makes: list[str] = None, resume: bool = True):
        """
        Build the full site index.
        
        Args:
            makes: List of makes to index (None = all)
            resume: Whether to resume from progress file
        """
        self.stats['start_time'] = time.time()
        
        # Ensure index directory exists
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load progress if resuming
        if resume:
            self.load_progress()
        else:
            # Start fresh
            if self.index_path.exists():
                self.index_path.unlink()
            if self.progress_file.exists():
                self.progress_file.unlink()
            self.completed_vehicles = set()
        
        # Get makes to process
        if makes is None:
            makes = await self.get_all_makes()
        
        log.info(f"Processing {len(makes)} makes: {makes[:5]}{'...' if len(makes) > 5 else ''}")
        
        # Count total vehicles for progress
        total_vehicles = 0
        vehicle_list = []
        
        for make in makes:
            years = await self.get_years_for_make(make)
            for year in years:
                models = await self.get_models_for_year(make, year)
                for model in models:
                    vehicle_list.append((make, year, model))
                    total_vehicles += 1
        
        self.stats['vehicles_total'] = total_vehicles
        log.info(f"Found {total_vehicles} vehicles to index")
        
        # Process vehicles in parallel batches
        batch_size = self.max_concurrent
        pending = [v for v in vehicle_list if f"{v[0]}/{v[1]}/{v[2]['name']}" not in self.completed_vehicles]
        log.info(f"Vehicles to process: {len(pending)} (skipping {total_vehicles - len(pending)} already done)")
        
        for batch_start in range(0, len(pending), batch_size):
            batch = pending[batch_start:batch_start + batch_size]
            
            # Run batch in parallel
            tasks = [self.index_vehicle(make, year, model) for make, year, model in batch]
            await asyncio.gather(*tasks)
            
            # Progress update
            elapsed = time.time() - self.stats['start_time']
            done = self.stats['vehicles_done']
            rate = done / (elapsed / 60) if elapsed > 0 else 0
            remaining = len(pending) - (batch_start + len(batch))
            eta = remaining / rate if rate > 0 else 0
            
            log.info(
                f"Progress: {done}/{total_vehicles} vehicles "
                f"({self.stats['pages_indexed']} pages) "
                f"- {rate:.1f} veh/min - ETA: {eta:.1f} min"
            )
        
        # Final stats
        elapsed = time.time() - self.stats['start_time']
        log.info(f"=== INDEXING COMPLETE ===")
        log.info(f"Vehicles: {self.stats['vehicles_done']}")
        log.info(f"Pages: {self.stats['pages_indexed']}")
        log.info(f"Errors: {self.stats['errors']}")
        log.info(f"Time: {elapsed/60:.1f} minutes")
        log.info(f"Index: {self.index_path}")
        
        if self.index_path.exists():
            size_mb = self.index_path.stat().st_size / 1024 / 1024
            log.info(f"Size: {size_mb:.1f} MB")


async def main():
    parser = argparse.ArgumentParser(description="Build full site index")
    parser.add_argument("--test", action="store_true", help="Index test batch (5 makes)")
    parser.add_argument("--full", action="store_true", help="Index full site (all makes)")
    parser.add_argument("--resume", action="store_true", help="Resume interrupted build")
    parser.add_argument("--makes", type=str, help="Comma-separated list of makes")
    parser.add_argument("--output", type=str, help="Output index file path")
    parser.add_argument("--prod", action="store_true", help="Use production path")
    parser.add_argument("--shallow", type=int, default=2000, 
                       help="Max pages per vehicle (default 2000, use 50 for quick test)")
    parser.add_argument("--concurrency", type=int, default=50,
                       help="Max concurrent HTTP requests (default 50)")
    parser.add_argument("--title-only", action="store_true",
                       help="Only index page titles, not content (much faster)")
    
    args = parser.parse_args()
    
    # Determine output path
    if args.output:
        index_path = Path(args.output)
    elif args.prod:
        index_path = PROD_INDEX_PATH
    else:
        index_path = DEFAULT_INDEX_PATH
    
    # Determine makes to process
    if args.makes:
        makes = [m.strip() for m in args.makes.split(',')]
    elif args.test:
        makes = TEST_MAKES
    elif args.full:
        makes = None  # All makes
    else:
        # Default to test batch
        makes = TEST_MAKES
    
    log.info(f"Output: {index_path}")
    log.info(f"Makes: {makes if makes else 'ALL'}")
    log.info(f"Max pages/vehicle: {args.shallow}")
    log.info(f"Concurrency: {args.concurrency}")
    log.info(f"Title-only: {args.title_only}")
    
    indexer = FullSiteIndexer(index_path=index_path, max_pages_per_vehicle=args.shallow, max_concurrent=args.concurrency, title_only=args.title_only)
    try:
        await indexer.build_index(makes=makes, resume=args.resume)
    finally:
        await indexer.close()


if __name__ == "__main__":
    asyncio.run(main())
