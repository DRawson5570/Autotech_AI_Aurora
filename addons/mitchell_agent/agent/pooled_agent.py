"""
Pooled Mitchell Agent
=====================
Agent service that uses worker pool for parallel request processing.

Supports three scaling modes:
- single: One worker, queue requests (classic behavior)
- pool: Fixed pool of N workers with auto-scaling
- ondemand: Create/destroy workers per request (cold start penalty)

Usage:
    python -m addons.mitchell_agent.agent.pooled_agent

Environment:
    MITCHELL_SCALING_MODE=single|pool|ondemand
    MITCHELL_POOL_MIN_WORKERS=1
    MITCHELL_POOL_MAX_WORKERS=3
    MITCHELL_POOL_IDLE_TIMEOUT=300
    MITCHELL_POOL_BASE_PORT=9222
"""

import asyncio
import os
import sys
import time
import logging
import signal
from typing import Optional
from pathlib import Path

import httpx

from .config import AgentConfig, load_config
from .worker_pool import WorkerPool, ScalingMode

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mitchell-pooled-agent")


class PooledMitchellAgent:
    """
    Pooled polling agent that uses worker pool for parallel processing.
    
    This is the new architecture that supports multiple concurrent Chrome
    instances for higher throughput.
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self._pool: Optional[WorkerPool] = None
        self._running = False
        self._http_clients: dict = {}  # Map of server_url -> httpx.AsyncClient
        
        # Track request processing
        self._active_requests: set = set()
        self._request_semaphore: Optional[asyncio.Semaphore] = None
    
    async def start(self):
        """Start the pooled agent."""
        logger.info("=" * 60)
        logger.info("🚀 Starting Pooled Mitchell Agent")
        logger.info(f"   Shop ID: {self.config.shop_id}")
        logger.info(f"   Server URLs: {self.config.server_urls}")
        logger.info(f"   Scaling Mode: {self.config.scaling_mode}")
        if self.config.scaling_mode in ("pool", "ondemand"):
            logger.info(f"   Min Workers: {self.config.pool_min_workers}")
            logger.info(f"   Max Workers: {self.config.pool_max_workers}")
            logger.info(f"   Idle Timeout: {self.config.pool_idle_timeout}s")
            logger.info(f"   Base Port: {self.config.pool_base_port}")
        logger.info("=" * 60)
        
        # Initialize worker pool
        self._pool = WorkerPool(self.config)
        await self._pool.start()
        
        # Initialize HTTP clients for each server
        self._http_clients = {}
        for server_url in self.config.server_urls:
            self._http_clients[server_url] = httpx.AsyncClient(
                base_url=server_url,
                timeout=30.0
            )
            logger.info(f"  HTTP client initialized for: {server_url}")
        
        # Semaphore to limit concurrent request processing
        max_concurrent = self.config.pool_max_workers
        self._request_semaphore = asyncio.Semaphore(max_concurrent)
        
        self._running = True
        
        # Start polling
        await self._poll_loop()
        
        return True
    
    async def stop(self):
        """Stop the agent and all workers."""
        logger.info("Stopping pooled agent...")
        self._running = False
        
        # Wait for active requests to complete (with timeout)
        if self._active_requests:
            logger.info(f"Waiting for {len(self._active_requests)} active requests...")
            for _ in range(30):  # 30 second timeout
                if not self._active_requests:
                    break
                await asyncio.sleep(1)
        
        # Stop worker pool
        if self._pool:
            await self._pool.stop()
        
        # Close HTTP clients
        for server_url, client in self._http_clients.items():
            await client.aclose()
        
        logger.info("Pooled agent stopped")
    
    async def _poll_loop(self):
        """Main polling loop that dispatches requests to workers."""
        consecutive_errors = 0
        max_consecutive_errors = 10
        
        logger.info("🔄 Pooled agent ready and polling for requests...")
        
        while self._running:
            try:
                # Poll ALL servers for pending requests
                found_work = False
                tasks = []
                
                for server_url in self.config.server_urls:
                    pending = await self._get_pending_requests(server_url)
                    
                    if pending:
                        logger.info(f"Got {len(pending)} pending request(s) from {server_url}")
                        for request in pending:
                            # Tag request with source server
                            request['_source_server'] = server_url
                            
                            # Dispatch to worker (async, don't wait)
                            task = asyncio.create_task(
                                self._process_request_with_worker(request)
                            )
                            tasks.append(task)
                        found_work = True
                        consecutive_errors = 0
                
                if not found_work:
                    # No work, sleep before next poll
                    await asyncio.sleep(self.config.poll_interval)
                    consecutive_errors = 0
                else:
                    # Don't wait for tasks to complete, let them run in background
                    # This allows parallel processing
                    pass
                    
            except httpx.HTTPError as e:
                consecutive_errors += 1
                logger.warning(f"HTTP error polling server: {e}")
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("Too many consecutive errors, stopping agent")
                    self._running = False
                else:
                    await asyncio.sleep(self.config.error_backoff)
                    
            except Exception as e:
                consecutive_errors += 1
                logger.exception(f"Error in poll loop: {e}")
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("Too many consecutive errors, stopping agent")
                    self._running = False
                else:
                    await asyncio.sleep(self.config.error_backoff)
    
    async def _get_pending_requests(self, server_url: str) -> list:
        """Get pending requests from a specific server."""
        client = self._http_clients.get(server_url)
        if not client:
            logger.warning(f"No HTTP client for {server_url}")
            return []
        
        response = await client.get(
            f"/api/mitchell/pending/{self.config.shop_id}"
        )
        response.raise_for_status()
        
        # Handle empty response
        if not response.content or response.content == b'':
            return []
        
        try:
            data = response.json()
            return data.get("requests", [])
        except Exception:
            return []
    
    async def _claim_request(self, request_id: str, server_url: str) -> bool:
        """Claim a request before processing."""
        client = self._http_clients.get(server_url)
        if not client:
            return False
        
        try:
            response = await client.post(
                f"/api/mitchell/claim/{request_id}"
            )
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Request {request_id} already claimed")
                return False
            raise
    
    async def _submit_result(self, request_id: str, result: dict, server_url: str):
        """Submit result to the originating server."""
        client = self._http_clients.get(server_url)
        if not client:
            logger.warning(f"No HTTP client for {server_url}")
            return
        
        tokens_used = result.get("tokens_used")
        logger.info(f"[SUBMIT] tokens_used from result: {tokens_used}")
        
        payload = {
            "success": result.get("success", False),
            "data": result.get("data"),
            "error": result.get("error"),
            "tool_used": result.get("tool_used"),
            "execution_time_ms": result.get("execution_time_ms"),
            "images": result.get("images"),
            "tokens_used": tokens_used,
        }
        
        try:
            response = await client.post(
                f"/api/mitchell/result/{request_id}",
                json=payload
            )
            response.raise_for_status()
            logger.info(f"[SUBMIT] Result submitted to {server_url} for {request_id}")
        except Exception as e:
            logger.error(f"Failed to submit result: {e}")
            raise
            raise
    
    async def _process_request_with_worker(self, request: dict):
        """Process a request using a worker from the pool."""
        request_id = request["id"]
        
        # Use semaphore to limit concurrent processing
        async with self._request_semaphore:
            self._active_requests.add(request_id)
            
            try:
                await self._do_process_request(request)
            finally:
                self._active_requests.discard(request_id)
    
    async def _do_process_request(self, request: dict):
        """Actually process the request with a worker."""
        request_id = request["id"]
        tool = request["tool"]
        vehicle = request["vehicle"]
        params = request.get("params", {})
        source_server = request.get("_source_server", self.config.server_urls[0])
        
        logger.info(f"[{request_id}] Processing: {tool} for {vehicle.get('year')} {vehicle.get('make')} {vehicle.get('model')}")
        
        # Claim the request
        if not await self._claim_request(request_id, source_server):
            return
        
        start_time = time.time()
        
        try:
            # Acquire a worker from the pool
            async with self._pool.acquire() as worker:
                logger.info(f"[{request_id}] Using Worker-{worker.worker_id}")
                
                # Execute the request
                result = await worker.execute(tool, vehicle, params)
                
                execution_time = int((time.time() - start_time) * 1000)
                
                # Submit result
                await self._submit_result(request_id, {
                    "success": result.get("success", False),
                    "data": result.get("data"),
                    "error": result.get("error"),
                    "tool_used": tool,
                    "execution_time_ms": execution_time,
                    "images": result.get("images"),
                    "tokens_used": result.get("tokens_used"),
                }, source_server)
                
                logger.info(f"[{request_id}] Completed in {execution_time}ms")
                
        except Exception as e:
            logger.exception(f"[{request_id}] Error: {e}")
            execution_time = int((time.time() - start_time) * 1000)
            
            await self._submit_result(request_id, {
                "success": False,
                "error": str(e),
                "tool_used": tool,
                "execution_time_ms": execution_time
            }, source_server)
    
    def get_stats(self) -> dict:
        """Get agent and pool statistics."""
        pool_stats = self._pool.get_stats() if self._pool else {}
        return {
            "shop_id": self.config.shop_id,
            "active_requests": len(self._active_requests),
            "pool": pool_stats,
        }


async def main():
    """Main entry point for pooled agent."""
    # Load environment from .env if present
    env_file = Path(__file__).parent.parent.parent.parent / ".env"
    if env_file.exists():
        logger.info(f"Loading environment from {env_file}")
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    # Don't override existing environment variables
                    if key not in os.environ:
                        os.environ[key] = value.strip('"').strip("'")
    
    # Load configuration
    config = load_config()
    
    # Validate scaling mode
    mode = config.scaling_mode.lower()
    if mode not in ("single", "pool", "ondemand"):
        logger.error(f"Invalid MITCHELL_SCALING_MODE: {mode}")
        logger.error("Valid modes: single, pool, ondemand")
        sys.exit(1)
    
    # If single mode, use the original agent (has full navigation support)
    if mode == "single":
        logger.info("Single mode - using original MitchellAgent")
        from .service import MitchellAgent
        agent = MitchellAgent(config)
    else:
        logger.info(f"Pool mode ({mode}) - using PooledMitchellAgent")
        agent = PooledMitchellAgent(config)
    
    # Setup signal handlers
    loop = asyncio.get_event_loop()
    
    async def shutdown(sig):
        logger.info(f"Received signal {sig.name}, shutting down...")
        await agent.stop()
        loop.stop()
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(shutdown(s))
        )
    
    # Start agent
    try:
        await agent.start()
    except KeyboardInterrupt:
        logger.info("Interrupted")
    finally:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
