"""
HTTP Polling
============
Handles HTTP communication with server(s) for request queue.
"""

import logging
from typing import Dict, List, Optional

import httpx

log = logging.getLogger(__name__)


class ServerClient:
    """
    HTTP client for a single server.
    
    Handles:
    - Getting pending requests
    - Claiming requests
    - Submitting results
    """
    
    def __init__(self, server_url: str, timeout: float = 30.0):
        """
        Initialize server client.
        
        Args:
            server_url: Server base URL
            timeout: Request timeout in seconds
        """
        self.server_url = server_url
        self._client = httpx.AsyncClient(
            base_url=server_url,
            timeout=timeout
        )
    
    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
    
    async def get_pending_requests(self, shop_id: str) -> List[dict]:
        """
        Get pending requests for a shop.
        
        Args:
            shop_id: Shop identifier
            
        Returns:
            List of pending request dicts
        """
        try:
            response = await self._client.get(
                f"/api/mitchell/pending/{shop_id}"
            )
            response.raise_for_status()
            
            # Handle empty response
            if not response.content or response.content == b'':
                return []
            
            data = response.json()
            return data.get("requests", [])
            
        except httpx.HTTPError as e:
            log.warning(f"HTTP error getting pending requests: {e}")
            return []
        except Exception as e:
            log.error(f"Error getting pending requests: {e}")
            return []
    
    async def claim_request(self, request_id: str) -> bool:
        """
        Claim a request before processing.
        
        Args:
            request_id: Request ID to claim
            
        Returns:
            True if claimed successfully
        """
        try:
            response = await self._client.post(
                f"/api/mitchell/claim/{request_id}"
            )
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                log.warning(f"Request {request_id} already claimed or not found")
                return False
            raise
        except Exception as e:
            log.error(f"Error claiming request: {e}")
            return False
    
    async def submit_result(self, request_id: str, result: dict):
        """
        Submit result for a request.
        
        Args:
            request_id: Request ID
            result: Result dict with success, data, error, etc.
        """
        # Ensure only valid fields are sent
        payload = {
            "success": result.get("success", False),
            "data": result.get("data"),
            "error": result.get("error"),
            "tool_used": result.get("tool_used"),
            "execution_time_ms": result.get("execution_time_ms"),
            "images": result.get("images"),
            "auto_selected": result.get("auto_selected"),
        }
        
        try:
            response = await self._client.post(
                f"/api/mitchell/result/{request_id}",
                json=payload
            )
            response.raise_for_status()
        except Exception as e:
            log.error(f"Failed to submit result: {e}")
            log.error(f"Payload was: {payload}")
            raise


class MultiServerPoller:
    """
    Polls multiple servers for pending requests.
    
    Routes results back to the originating server.
    
    Usage:
        poller = MultiServerPoller(server_urls, shop_id)
        await poller.start()
        
        # Get pending from all servers
        requests = await poller.get_all_pending()
        
        # Submit result to originating server
        await poller.submit_result(request)
        
        await poller.close()
    """
    
    def __init__(
        self,
        server_urls: List[str],
        shop_id: str,
        timeout: float = 30.0
    ):
        """
        Initialize multi-server poller.
        
        Args:
            server_urls: List of server URLs to poll
            shop_id: Shop identifier
            timeout: HTTP request timeout
        """
        self.server_urls = server_urls
        self.shop_id = shop_id
        self._clients: Dict[str, ServerClient] = {}
        
        for url in server_urls:
            self._clients[url] = ServerClient(url, timeout)
            log.info(f"  HTTP client initialized for: {url}")
    
    async def close(self):
        """Close all HTTP clients."""
        for client in self._clients.values():
            await client.close()
        self._clients.clear()
    
    async def get_all_pending(self) -> List[dict]:
        """
        Get pending requests from all servers.
        
        Tags each request with _source_server for routing.
        
        Returns:
            List of pending request dicts
        """
        all_pending = []
        
        for server_url, client in self._clients.items():
            requests = await client.get_pending_requests(self.shop_id)
            
            # Tag each request with source server
            for req in requests:
                req['_source_server'] = server_url
            
            all_pending.extend(requests)
            
            if requests:
                log.info(f"Got {len(requests)} pending request(s) from {server_url}")
        
        return all_pending
    
    async def claim_request(self, request: dict) -> bool:
        """
        Claim a request on its source server.
        
        Args:
            request: Request dict with _source_server tag
            
        Returns:
            True if claimed successfully
        """
        source = request.get('_source_server')
        if not source:
            log.warning("Request missing _source_server tag")
            return False
        
        client = self._clients.get(source)
        if not client:
            log.warning(f"No client for server: {source}")
            return False
        
        return await client.claim_request(request['id'])
    
    async def submit_result(self, request: dict, result: dict):
        """
        Submit result to the originating server.
        
        Args:
            request: Original request dict with _source_server
            result: Result dict
        """
        source = request.get('_source_server')
        if not source:
            # Fall back to first server
            source = self.server_urls[0]
            log.warning(f"Request missing _source_server, using default: {source}")
        
        client = self._clients.get(source)
        if not client:
            log.error(f"No client for server: {source}")
            return
        
        await client.submit_result(request['id'], result)
