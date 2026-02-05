"""
HTTP Utilities
==============
HTTP client helpers for the Mitchell Agent.
"""

import asyncio
from typing import Optional, Dict, Any, List
import httpx

from .logging import get_logger

logger = get_logger("http")


class MultiServerClient:
    """
    HTTP client that can communicate with multiple servers.
    
    Used by the polling agent to serve both prod and dev servers
    from a single agent instance.
    """
    
    def __init__(self, server_urls: List[str], timeout: float = 30.0):
        """
        Initialize multi-server client.
        
        Args:
            server_urls: List of server base URLs
            timeout: Request timeout in seconds
        """
        self.server_urls = server_urls
        self.timeout = timeout
        self._clients: Dict[str, httpx.AsyncClient] = {}
    
    async def __aenter__(self):
        """Create HTTP clients for each server."""
        for url in self.server_urls:
            self._clients[url] = httpx.AsyncClient(
                base_url=url,
                timeout=self.timeout
            )
            logger.debug(f"Created HTTP client for: {url}")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close all HTTP clients."""
        for url, client in self._clients.items():
            await client.aclose()
            logger.debug(f"Closed HTTP client for: {url}")
        self._clients.clear()
    
    def get_client(self, server_url: str) -> Optional[httpx.AsyncClient]:
        """
        Get HTTP client for a specific server.
        
        Args:
            server_url: Server URL
            
        Returns:
            HTTP client or None if not found
        """
        return self._clients.get(server_url)
    
    async def get(self, server_url: str, path: str, **kwargs) -> Optional[httpx.Response]:
        """
        Make GET request to a specific server.
        
        Args:
            server_url: Server URL
            path: Request path
            **kwargs: Additional request arguments
            
        Returns:
            Response or None if failed
        """
        client = self.get_client(server_url)
        if not client:
            logger.warning(f"No client for server: {server_url}")
            return None
        
        try:
            return await client.get(path, **kwargs)
        except Exception as e:
            logger.error(f"GET {server_url}{path} failed: {e}")
            return None
    
    async def post(self, server_url: str, path: str, **kwargs) -> Optional[httpx.Response]:
        """
        Make POST request to a specific server.
        
        Args:
            server_url: Server URL
            path: Request path
            **kwargs: Additional request arguments
            
        Returns:
            Response or None if failed
        """
        client = self.get_client(server_url)
        if not client:
            logger.warning(f"No client for server: {server_url}")
            return None
        
        try:
            return await client.post(path, **kwargs)
        except Exception as e:
            logger.error(f"POST {server_url}{path} failed: {e}")
            return None


async def poll_all_servers(
    client: MultiServerClient,
    path: str,
    parse_response: callable = None
) -> List[tuple]:
    """
    Poll all servers and collect responses.
    
    Args:
        client: MultiServerClient instance
        path: API path to poll
        parse_response: Optional function to parse response JSON
        
    Returns:
        List of (server_url, data) tuples for successful responses
    """
    results = []
    
    for server_url in client.server_urls:
        response = await client.get(server_url, path)
        
        if response and response.status_code == 200:
            try:
                data = response.json()
                if parse_response:
                    data = parse_response(data)
                results.append((server_url, data))
            except Exception as e:
                logger.warning(f"Failed to parse response from {server_url}: {e}")
    
    return results


class RetryConfig:
    """Configuration for HTTP retry behavior."""
    
    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        retry_statuses: tuple = (500, 502, 503, 504)
    ):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.retry_statuses = retry_statuses


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    retry_config: Optional[RetryConfig] = None,
    **kwargs
) -> httpx.Response:
    """
    Make HTTP request with retry logic.
    
    Args:
        client: HTTP client
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        retry_config: Retry configuration
        **kwargs: Additional request arguments
        
    Returns:
        HTTP response
        
    Raises:
        httpx.HTTPError: If all retries failed
    """
    config = retry_config or RetryConfig()
    last_exception = None
    
    for attempt in range(config.max_retries + 1):
        try:
            response = await client.request(method, url, **kwargs)
            
            if response.status_code not in config.retry_statuses:
                return response
            
            logger.warning(
                f"Retry {attempt + 1}/{config.max_retries}: "
                f"{method} {url} returned {response.status_code}"
            )
            
        except httpx.HTTPError as e:
            last_exception = e
            logger.warning(f"Retry {attempt + 1}/{config.max_retries}: {e}")
        
        if attempt < config.max_retries:
            delay = config.backoff_factor * (2 ** attempt)
            await asyncio.sleep(delay)
    
    if last_exception:
        raise last_exception
    
    return response  # Return last response even if it was a retry status
