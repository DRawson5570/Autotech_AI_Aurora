"""scripts/scrape_and_ingest.py

Simple CLI utility to scrape one or more URLs and ingest them into the app's RAG pipeline
by calling the backend endpoints:
 - POST /api/v1/retrieval/process/web  (body: {"url":..., "collection_name":...})
 - POST /api/v1/knowledge/create       (optional, to create a new knowledge base)

Usage examples:
  python scripts/scrape_and_ingest.py --url https://example.com --collection my-collection
  python scripts/scrape_and_ingest.py --urls urls.txt --create-knowledge "My KB" --concurrency 6

Auth:
 - If the server requires an API token, set OPENWEBUI_API_TOKEN env var or use --api-key

This script is intentionally simple and uses `requests` + ThreadPoolExecutor so it works
in most environments and is easy to test.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import logging
import os
import sys
import time
import xml.etree.ElementTree as ET
from typing import Iterable, List, Optional, Tuple
from urllib.parse import urlparse, urljoin
from html.parser import HTMLParser
from collections import deque
import threading

import requests

# Default retry/backoff settings
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 1.0
# Per-domain politeness tracking
_DOMAIN_NEXT_ALLOWED: dict = {}
# Lock for checkpoint file writes
_CHECKPOINT_LOCK = threading.Lock()

log = logging.getLogger("scrape_and_ingest")

DEFAULT_BASE_URL = "http://localhost:3000"


class HTTPError(Exception):
    pass


def _headers(api_key: Optional[str]) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def create_knowledge(base_url: str, api_key: Optional[str], name: str, description: str = "") -> dict:
    url = f"{base_url.rstrip('/')}/api/v1/knowledge/create"
    payload = {"name": name, "description": description}
    r = requests.post(url, json=payload, headers=_headers(api_key), timeout=30)
    if r.status_code != 200:
        raise HTTPError(f"Create knowledge failed: {r.status_code} {r.text}")
    return r.json()


def process_url(
    base_url: str,
    api_key: Optional[str],
    url_to_process: str,
    collection_name: Optional[str],
    timeout: int = 60,
    retries: int = DEFAULT_RETRIES,
    backoff_factor: float = DEFAULT_BACKOFF,
) -> Tuple[bool, str]:
    url = f"{base_url.rstrip('/')}/api/v1/retrieval/process/web"
    payload = {"url": url_to_process}
    if collection_name:
        payload["collection_name"] = collection_name

    attempt = 0
    while True:
        attempt += 1
        try:
            r = requests.post(url, json=payload, headers=_headers(api_key), timeout=timeout)
            # On 4xx errors, do not retry except maybe 429
            if r.status_code != 200:
                if attempt >= retries or (400 <= r.status_code < 500 and r.status_code != 429):
                    return False, f"HTTP {r.status_code}: {r.text}"
                # else retry
                time.sleep(backoff_factor * (2 ** (attempt - 1)))
                continue

            try:
                jr = r.json()
                if jr.get("status"):
                    return True, jr.get("collection_name") or "(none)"
                else:
                    # treat as failure but allow retry
                    if attempt >= retries:
                        return False, str(jr)
                    time.sleep(backoff_factor * (2 ** (attempt - 1)))
                    continue
            except Exception:
                if attempt >= retries:
                    return False, "Invalid JSON response"
                time.sleep(backoff_factor * (2 ** (attempt - 1)))
                continue
        except Exception as e:
            if attempt >= retries:
                return False, str(e)
            time.sleep(backoff_factor * (2 ** (attempt - 1)))
            continue


def _fetch_with_retries(url: str, timeout: int = 15, retries: int = DEFAULT_RETRIES, backoff_factor: float = DEFAULT_BACKOFF, domain_delay: float = 0.0):
    attempt = 0
    netloc = urlparse(url).netloc
    while True:
        attempt += 1
        try:
            # Respect per-domain politeness
            if domain_delay and netloc:
                now = time.time()
                next_allowed = _DOMAIN_NEXT_ALLOWED.get(netloc, 0)
                wait = next_allowed - now
                if wait > 0:
                    time.sleep(wait)

            r = requests.get(url, timeout=timeout)
            r.raise_for_status()

            # Mark next allowed time for domain
            if domain_delay and netloc:
                _DOMAIN_NEXT_ALLOWED[netloc] = time.time() + domain_delay

            return r
        except Exception as e:
            if attempt >= retries:
                raise
            time.sleep(backoff_factor * (2 ** (attempt - 1)))


def load_resume_file(path: str) -> set:
    processed = set()
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        processed.add(line.strip())
    except Exception:
        pass
    return processed


def append_to_resume_file(path: str, url: str) -> None:
    try:
        with _CHECKPOINT_LOCK:
            with open(path, "a", encoding="utf-8") as f:
                f.write(url + "\n")
    except Exception:
        pass


def fetch_sitemap_urls(sitemap_url: str, timeout: int = 15) -> List[str]:
    try:
        r = _fetch_with_retries(sitemap_url, timeout=timeout)
        root = ET.fromstring(r.content)
        urls: List[str] = []
        for elem in root.findall('.//{*}loc'):
            if elem.text:
                urls.append(elem.text.strip())
        return urls
    except Exception as e:
        raise HTTPError(f"Failed to fetch sitemap {sitemap_url}: {e}")


class LinkExtractor(HTMLParser):
    def __init__(self, base: str):
        super().__init__()
        self.base = base
        self.links: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            for k, v in attrs:
                if k.lower() == "href" and v:
                    try:
                        abs_url = urljoin(self.base, v)
                        self.links.append(abs_url)
                    except Exception:
                        pass


def _extract_links(base_url: str, html: str) -> List[str]:
    parser = LinkExtractor(base_url)
    try:
        parser.feed(html)
    except Exception:
        pass
    # Normalize: drop fragments and only keep http/https
    out = []
    for u in parser.links:
        p = urlparse(u)
        if p.scheme in ("http", "https"):
            normalized = p._replace(fragment="").geturl()
            out.append(normalized)
    return list(dict.fromkeys(out))  # preserve order, unique


def expand_urls_with_crawl(
    start_urls: Iterable[str],
    max_depth: int = 1,
    max_pages: Optional[int] = None,
    timeout: int = 15,
    retries: int = DEFAULT_RETRIES,
    backoff_factor: float = DEFAULT_BACKOFF,
    domain_delay: float = 0.0,
) -> List[str]:
    """Breadth-first crawl limited to same-domain URLs. Honours domain_delay politeness."""
    start_urls = list(start_urls)
    if not start_urls:
        return []

    visited = set()
    results: List[str] = []
    q = deque()

    # Start from each seed URL with depth 0
    for u in start_urls:
        q.append((u, 0))

    # Determine allowed domains (netlocs) - allow multiple if seeds are different
    allowed_netlocs = set()
    for u in start_urls:
        try:
            allowed_netlocs.add(urlparse(u).netloc)
        except Exception:
            pass

    while q:
        u, depth = q.popleft()
        if u in visited:
            continue
        visited.add(u)
        results.append(u)

        if max_pages is not None and len(results) >= max_pages:
            break

        if depth >= max_depth:
            continue

        # Fetch page and extract links
        try:
            r = _fetch_with_retries(u, timeout=timeout, retries=retries, backoff_factor=backoff_factor, domain_delay=domain_delay)
            html = r.text
            links = _extract_links(u, html)
            for link in links:
                nl = urlparse(link).netloc
                if nl not in allowed_netlocs:
                    continue
                if link not in visited:
                    q.append((link, depth + 1))
        except Exception as e:
            log.debug("Crawl: failed to fetch %s: %s", u, e)
            continue

    return results


def scrape_and_ingest(
    urls: Iterable[str],
    base_url: str = DEFAULT_BASE_URL,
    api_key: Optional[str] = None,
    collection_name: Optional[str] = None,
    create_knowledge_name: Optional[str] = None,
    concurrency: int = 4,
    timeout: int = 60,
    crawl: bool = False,
    max_depth: int = 1,
    max_pages: Optional[int] = None,
    retries: int = DEFAULT_RETRIES,
    backoff_factor: float = DEFAULT_BACKOFF,
    domain_delay: float = 0.0,
    resume_file: Optional[str] = None,
) -> dict:
    """Scrape and ingest a list of URLs. Returns a summary dict."""

    if create_knowledge_name and not collection_name:
        log.info("Creating knowledge base: %s", create_knowledge_name)
        resp = create_knowledge(base_url, api_key, create_knowledge_name)
        # Expecting a KnowledgeModel-ish response with an `id` field
        collection_name = resp.get("id") or collection_name
        log.info("Created knowledge id: %s", collection_name)

    urls = list(urls)
    if not urls:
        raise ValueError("No URLs provided")

    # Load resume file if provided
    processed_set = set()
    if resume_file:
        processed_set = load_resume_file(resume_file)
        log.info("Loaded %d URLs from resume file %s", len(processed_set), resume_file)

    # Expand if crawl requested
    if crawl:
        log.info("Crawling %d seed urls with max_depth=%d max_pages=%s", len(urls), max_depth, str(max_pages))
        try:
            expanded = expand_urls_with_crawl(urls, max_depth=max_depth, max_pages=max_pages, timeout=timeout, retries=retries, backoff_factor=backoff_factor, domain_delay=domain_delay)
            urls = [u for u in expanded if u not in processed_set]
            log.info("Crawl discovered %d urls (after resume filter)", len(urls))
        except Exception as e:
            log.exception("Crawl failed: %s", e)
    else:
        # Filter seeds by resume set
        urls = [u for u in urls if u not in processed_set]

    total = len(urls)
    successes = 0
    failures = 0
    results: List[Tuple[str, bool, str]] = []

    log.info("Processing %d urls with concurrency=%d", total, concurrency)

    def _worker(u: str) -> Tuple[str, bool, str]:
        ok, info = process_url(
            base_url,
            api_key,
            u,
            collection_name,
            timeout=timeout,
            retries=retries,
            backoff_factor=backoff_factor,
        )
        if ok and resume_file:
            try:
                append_to_resume_file(resume_file, u)
            except Exception:
                pass
        return (u, ok, info)

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = {ex.submit(_worker, u): u for u in urls}
        for fut in concurrent.futures.as_completed(futures):
            u = futures[fut]
            try:
                url, ok, info = fut.result()
                results.append((url, ok, info))
                if ok:
                    successes += 1
                    log.info("OK	%s	-> %s", url, info)
                else:
                    failures += 1
                    log.error("FAIL	%s	-> %s", url, info)
            except Exception as e:  # pragma: no cover - defensive
                failures += 1
                log.exception("Unhandled exception for %s: %s", u, e)
                results.append((u, False, str(e)))

    summary = {
        "total": total,
        "successes": successes,
        "failures": failures,
        "results": results,
        "collection_name": collection_name,
    }

    return summary


def _read_urls_from_file(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scrape and ingest web pages into Open WebUI RAG")
    p.add_argument("--base-url", default=os.getenv("OPENWEBUI_BASE_URL", DEFAULT_BASE_URL), help="Backend base URL")
    p.add_argument("--api-key", default=os.getenv("OPENWEBUI_API_TOKEN"), help="Bearer API token")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", action="append", help="Single URL to scrape and ingest. Can be repeated.")
    group.add_argument("--urls", help="Path to a file containing newline-separated URLs")
    group.add_argument("--sitemap", help="URL to a sitemap.xml to fetch and ingest")

    p.add_argument("--collection", help="Collection name or knowledge id to save docs into")
    p.add_argument("--create-knowledge", help="Create a new knowledge base with this name and use it as collection")
    p.add_argument("--concurrency", type=int, default=4, help="Max concurrent requests")
    p.add_argument("--timeout", type=int, default=60, help="Per-request timeout (seconds)")
    p.add_argument("--crawl", action="store_true", help="Enable crawling from each seed URL")
    p.add_argument("--max-depth", type=int, default=1, help="Max crawl depth (0 = only seeds)")
    p.add_argument("--max-pages", type=int, default=None, help="Max total pages to crawl/process")
    p.add_argument("--domain-delay", type=float, default=0.5, help="Minimum seconds between requests to the same domain")
    p.add_argument("--retries", type=int, default=DEFAULT_RETRIES, help="Retries for transient failures")
    p.add_argument("--backoff-factor", type=float, default=DEFAULT_BACKOFF, help="Base backoff factor in seconds (exponential)")
    p.add_argument("--resume-file", type=str, default=None, help="Path to resume/checkpoint file (one URL per line)")
    p.add_argument("--checkpoint-interval", type=int, default=1, help="Not used (kept for backward compatibility)")
    p.add_argument("--verbose", action="store_true", help="Verbose logging")

    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.url:
        urls = args.url
    elif args.urls:
        urls = _read_urls_from_file(args.urls)
    elif args.sitemap:
        urls = fetch_sitemap_urls(args.sitemap)
    else:
        urls = []

    start = time.time()
    try:
        summary = scrape_and_ingest(
            urls,
            base_url=args.base_url,
            api_key=args.api_key,
            collection_name=args.collection,
            create_knowledge_name=args.create_knowledge,
            concurrency=args.concurrency,
            timeout=args.timeout,
            crawl=args.crawl,
            max_depth=args.max_depth,
            max_pages=args.max_pages,
            retries=args.retries,
            backoff_factor=args.backoff_factor,
            domain_delay=args.domain_delay,
            resume_file=args.resume_file,
        )
    except Exception as e:
        log.exception("Error: %s", e)
        return 2

    dur = time.time() - start
    log.info("Finished in %.2fs - total=%d success=%d failures=%d", dur, summary["total"], summary["successes"], summary["failures"])

    if summary["failures"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
