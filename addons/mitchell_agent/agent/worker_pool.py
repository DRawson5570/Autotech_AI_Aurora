"""
Mitchell Agent Worker Pool
==========================
Manages multiple Chrome browser workers for parallel request processing.

Scaling Modes:
- single: One Chrome instance, one request at a time (current behavior)
- pool: Fixed pool of workers, requests queued when all busy
- ondemand: Spawn Chrome per request, kill when done (cold start penalty)

Usage:
    pool = WorkerPool(config)
    await pool.start()
    
    # Get a worker (blocks until one available)
    async with pool.acquire() as worker:
        result = await worker.execute(request)
    
    await pool.stop()
"""

import asyncio
import logging
import time
import socket
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List, Any
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class WorkerState(Enum):
    """Worker lifecycle states."""
    STARTING = "starting"      # Chrome launching
    IDLE = "idle"              # Ready for work
    BUSY = "busy"              # Processing request
    STOPPING = "stopping"      # Shutting down
    ERROR = "error"            # Failed state


class ScalingMode(Enum):
    """Agent scaling modes."""
    SINGLE = "single"          # One worker, classic behavior
    POOL = "pool"              # Fixed pool with queue
    ONDEMAND = "ondemand"      # Spawn per request


@dataclass
class WorkerStats:
    """Statistics for a worker."""
    requests_completed: int = 0
    requests_failed: int = 0
    total_processing_time: float = 0.0
    last_active: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    
    @property
    def avg_processing_time(self) -> float:
        if self.requests_completed == 0:
            return 0.0
        return self.total_processing_time / self.requests_completed
    
    @property
    def idle_time(self) -> float:
        return time.time() - self.last_active


class Worker:
    """
    A single Chrome browser worker.
    
    Each worker manages its own:
    - Chrome process (via CDP)
    - Playwright connection
    - Login state
    - Navigator for vehicle selection
    - Tool execution
    
    Note: Each worker has its own complete MitchellAPI and Navigator,
    so it can handle any tool independently. Workers don't share state.
    """
    
    def __init__(
        self,
        worker_id: int,
        config: Any,
        cdp_port: int,
    ):
        self.worker_id = worker_id
        self.config = config
        self.cdp_port = cdp_port
        self.state = WorkerState.STARTING
        self.stats = WorkerStats()
        
        # Browser and navigation objects (set during start)
        self._api = None
        self._navigator = None
        self._logged_in = False
        
        # Lock for this worker
        self._lock = asyncio.Lock()
        
        logger.info(f"Worker-{worker_id} created on port {cdp_port}")
    
    async def start(self) -> bool:
        """Start Chrome and connect via CDP."""
        try:
            self.state = WorkerState.STARTING
            
            # Import here to avoid circular imports
            from ..api import MitchellAPI
            
            # Create API instance for this worker
            self._api = MitchellAPI(
                headless=self.config.headless,
                debug_screenshots=getattr(self.config, 'debug_screenshots', False)
            )
            
            # CRITICAL: Set port BEFORE connect() is called
            # This prevents _launch_chrome from finding its own port
            self._api._cdp_port = self.cdp_port
            
            # CRITICAL: Each worker needs its own Chrome profile directory
            # Set explicit override so workers don't share profiles and stomp on each other
            self._api._user_data_override = f"/tmp/mitchell-chrome-worker-{self.worker_id}"
            
            self.state = WorkerState.IDLE
            self.stats.last_active = time.time()
            
            logger.info(f"Worker-{self.worker_id} initialized: port={self.cdp_port}, profile=/tmp/mitchell-chrome-worker-{self.worker_id}")
            return True
            
        except Exception as e:
            logger.error(f"Worker-{self.worker_id} failed to start: {e}")
            self.state = WorkerState.ERROR
            return False
    
    async def stop(self):
        """Stop Chrome and cleanup."""
        self.state = WorkerState.STOPPING
        
        try:
            if self._api and self._logged_in:
                await self._api.logout()
            if self._api:
                await self._api.disconnect()
        except Exception as e:
            logger.warning(f"Worker-{self.worker_id} cleanup error: {e}")
        
        self._logged_in = False
        self.state = WorkerState.IDLE  # Mark as stopped
        logger.info(f"Worker-{self.worker_id} stopped")
    
    async def _ensure_connected(self) -> bool:
        """Ensure worker is connected and logged in to ShopKeyPro."""
        if self._logged_in:
            return True
        
        try:
            # Connect to Chrome
            connected = await self._api.connect()
            if not connected:
                logger.error(f"Worker-{self.worker_id} failed to connect")
                return False
            
            self._logged_in = True
            return True
        except Exception as e:
            logger.error(f"Worker-{self.worker_id} connection failed: {e}")
            return False
    
    async def execute(self, tool: str, vehicle: dict, params: dict) -> dict:
        """Execute a request on this worker.
        
        All requests are routed through the AI Navigator (query_autonomous).
        The 'tool' parameter is now just used to build the question/goal.
        
        Flow:
        1. Ensure connected and logged in
        2. Navigate to vehicle (open selector, select year/make/model/engine)
        3. Run AI Navigator to find and extract data
        4. Logout
        """
        start_time = time.time()
        self.state = WorkerState.BUSY
        self.stats.last_active = time.time()
        
        try:
            # Ensure connected and logged in
            if not await self._ensure_connected():
                return {"success": False, "error": "Failed to connect to ShopKeyPro"}
            
            # Step 1: Navigate to vehicle FIRST
            # The AI Navigator expects to start from Quick Lookups page with vehicle selected
            nav_result = await self._navigate_to_vehicle(vehicle)
            if not nav_result.get("success"):
                return {
                    "success": False,
                    "error": nav_result.get("error", "Vehicle navigation failed"),
                    "data": nav_result.get("missing_info"),
                }
            
            # Step 2: Now run the AI Navigator to find the data
            from ..ai_navigator.autonomous_navigator import query_mitchell_autonomous
            
            # Build goal from tool name and params
            goal = self._build_goal(tool, params)
            context = params.get("context", "")
            
            logger.info(f"Worker-{self.worker_id} executing query: {goal}")
            
            result = await query_mitchell_autonomous(
                page=self._api._page,
                goal=goal,
                vehicle=vehicle,
                context=context,
            )
            
            # Update stats
            elapsed = time.time() - start_time
            self.stats.requests_completed += 1
            self.stats.total_processing_time += elapsed
            
            return result
            
        except Exception as e:
            self.stats.requests_failed += 1
            logger.error(f"Worker-{self.worker_id} execution error: {e}")
            return {"success": False, "error": str(e)}
            
        finally:
            self.state = WorkerState.IDLE
            self.stats.last_active = time.time()
            
            # Logout after request (clean state for next request)
            try:
                if self._api and self._logged_in:
                    await self._api.logout()
                    self._logged_in = False
            except Exception as e:
                logger.warning(f"Worker-{self.worker_id} logout error: {e}")
    
    async def _create_navigator(self):
        """Create a Navigator for vehicle selection."""
        import os
        from .navigator import Navigator, NavigatorBackend
        
        # Get backend config (same as main service)
        backend_str = os.environ.get('NAVIGATOR_BACKEND', 
                                     getattr(self.config, 'navigator_backend', 'gemini'))
        try:
            backend = NavigatorBackend(backend_str.lower())
        except ValueError:
            backend = NavigatorBackend.GEMINI
        
        return Navigator(
            page=self._api._page,
            backend=backend,
            gemini_api_key=os.environ.get('GEMINI_API_KEY', ''),
            gemini_model=os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash'),
            ollama_url=getattr(self.config, 'ollama_url', 'http://localhost:11434'),
            ollama_model=getattr(self.config, 'ollama_model', 'qwen3:8b'),
            server_url=self.config.server_url,
            shop_id=self.config.shop_id,
        )
    
    async def _navigate_to_vehicle(self, vehicle: dict) -> dict:
        """
        Navigate to a vehicle using the Navigator.
        
        Opens the vehicle selector and selects year/make/model/engine.
        Must complete BEFORE running AI Navigator queries.
        """
        import re
        import asyncio
        
        # Try to extract drive_type from any field if not explicitly provided
        drive_type = vehicle.get("drive_type")
        
        if not drive_type:
            # Look for drive type patterns in submodel, body_style, or engine fields
            all_text = " ".join([
                str(vehicle.get("submodel", "")),
                str(vehicle.get("body_style", "")),
                str(vehicle.get("engine", ""))
            ])
            drive_match = re.search(r'\b(4WD|AWD|RWD|FWD|2WD|4x4|4X4)\b', all_text, re.IGNORECASE)
            if drive_match:
                drive_type = drive_match.group(1).upper()
                logger.info(f"Worker-{self.worker_id} extracted drive_type '{drive_type}' from vehicle fields")
        
        # Build goal from vehicle info
        goal_parts = [str(vehicle["year"]), vehicle["make"], vehicle["model"]]
        if vehicle.get("engine"):
            goal_parts.append(vehicle["engine"])
        if vehicle.get("submodel"):
            goal_parts.append(vehicle["submodel"])
        if vehicle.get("body_style"):
            goal_parts.append(vehicle["body_style"])
        if drive_type:
            goal_parts.append(drive_type)
        
        goal = " ".join(goal_parts)
        logger.info(f"Worker-{self.worker_id} selecting vehicle: {goal}")
        
        # Simple clarification handler - just record what's needed and abort
        missing_info = []
        
        async def handle_clarification(option_name: str, available_values: list, message: str):
            """Record missing info and return None to abort navigation."""
            logger.info(f"Worker-{self.worker_id} missing info: {option_name} - options: {available_values}")
            missing_info.append({
                "option": option_name,
                "values": available_values,
                "message": message
            })
            return None  # Signal navigation should abort
        
        # Create navigator and set up clarification handler
        navigator = await self._create_navigator()
        navigator.on_clarification_needed = handle_clarification
        
        # Navigate!
        result = await navigator.navigate(goal)
        
        # If we collected missing info, close the selector and return helpful error
        if missing_info:
            # Close the vehicle selector dialog before returning
            try:
                cancel_btn = navigator.page.locator("input[data-action='Cancel']")
                if await cancel_btn.count() > 0:
                    await cancel_btn.click(timeout=3000)
                    logger.info(f"Worker-{self.worker_id} closed vehicle selector after clarification needed")
                    await asyncio.sleep(0.5)
            except Exception as e:
                logger.debug(f"Worker-{self.worker_id} could not close vehicle selector: {e}")
            
            info = missing_info[0]  # Usually just one thing missing
            options_str = ", ".join(info["values"][:6])  # Show first 6 options
            if len(info["values"]) > 6:
                options_str += f", ... ({len(info['values'])} total)"
            
            error_msg = (
                f"Additional information needed: {info['option']}. "
                f"Please include one of these in your request: {options_str}. "
                f"Example: '2018 Ford F-150 XLT with 5.0L engine'"
            )
            return {
                "success": False,
                "error": error_msg,
                "missing_info": missing_info
            }
        
        return {
            "success": result.success,
            "error": result.error,
            "auto_selected": result.auto_selected,
        }
    
    def _build_goal(self, tool: str, params: dict) -> str:
        """
        Build a natural language goal from tool name and params.
        
        The AI Navigator will interpret this to find the right data.
        """
        # If there's already a question/query, use it directly
        if params.get("question"):
            return params["question"]
        if params.get("query"):
            return params["query"]
        
        # Map legacy tool names to natural language goals
        goal_templates = {
            "get_fluid_capacities": "fluid capacities" + (f" for {params.get('fluid_type')}" if params.get('fluid_type') else ""),
            "get_dtc_info": f"DTC code {params.get('dtc_code', '')} information",
            "get_torque_specs": "torque specifications" + (f" for {params.get('component')}" if params.get('component') else ""),
            "get_reset_procedure": f"{params.get('procedure', 'oil life')} reset procedure",
            "get_tsb_list": "technical service bulletins" + (f" for {params.get('category')}" if params.get('category') else ""),
            "get_adas_calibration": "ADAS calibration" + (f" for {params.get('component')}" if params.get('component') else ""),
            "get_tire_specs": "tire and TPMS specifications",
            "get_wiring_diagram": f"wiring diagram for {params.get('system', params.get('component', 'electrical'))}",
            "query_autonomous": params.get("question", params.get("query", "general information")),
        }
        
        return goal_templates.get(tool, f"information about {tool}")
    
    def __repr__(self):
        return f"Worker(id={self.worker_id}, port={self.cdp_port}, state={self.state.value})"


class WorkerPool:
    """
    Manages a pool of Chrome workers for parallel processing.
    
    Supports three scaling modes:
    - single: One worker, queue requests (current behavior)
    - pool: Fixed pool of N workers with auto-scaling
    - ondemand: Create/destroy workers per request
    """
    
    def __init__(self, config: Any):
        """
        Initialize worker pool.
        
        Config should have:
        - scaling_mode: single, pool, or ondemand
        - pool_min_workers: Minimum workers to keep running
        - pool_max_workers: Maximum workers allowed
        - pool_idle_timeout: Seconds before killing idle worker
        - pool_base_port: Starting CDP port number
        """
        self.config = config
        self.mode = ScalingMode(getattr(config, 'scaling_mode', 'single'))
        
        # Pool settings
        self.min_workers = getattr(config, 'pool_min_workers', 1)
        self.max_workers = getattr(config, 'pool_max_workers', 3)
        self.idle_timeout = getattr(config, 'pool_idle_timeout', 300)  # 5 min
        self.base_port = getattr(config, 'pool_base_port', 9222)
        
        # Worker management
        self._workers: Dict[int, Worker] = {}
        self._worker_id_counter = 0
        self._available_ports: List[int] = []
        self._request_queue: asyncio.Queue = asyncio.Queue()
        
        # Locks
        self._pool_lock = asyncio.Lock()
        self._acquire_semaphore: Optional[asyncio.Semaphore] = None
        
        # Background tasks
        self._scaler_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info(f"WorkerPool initialized: mode={self.mode.value}, "
                   f"min={self.min_workers}, max={self.max_workers}")
    
    def _find_free_port(self, start_port: int = None) -> int:
        """Find a free port starting from start_port."""
        port = start_port or self.base_port
        while port < port + 100:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    return port
            except OSError:
                port += 1
        raise RuntimeError(f"Could not find free port in range {self.base_port}-{self.base_port + 100}")
    
    async def start(self):
        """Start the worker pool."""
        self._running = True
        
        if self.mode == ScalingMode.SINGLE:
            # Single worker mode - create one worker
            self._acquire_semaphore = asyncio.Semaphore(1)
            await self._spawn_worker()
            
        elif self.mode == ScalingMode.POOL:
            # Pool mode - create min_workers, start scaler
            self._acquire_semaphore = asyncio.Semaphore(self.max_workers)
            for _ in range(self.min_workers):
                await self._spawn_worker()
            
            # Start auto-scaler task
            self._scaler_task = asyncio.create_task(self._scaler_loop())
            
        elif self.mode == ScalingMode.ONDEMAND:
            # On-demand mode - no workers started initially
            self._acquire_semaphore = asyncio.Semaphore(self.max_workers)
        
        logger.info(f"WorkerPool started with {len(self._workers)} workers")
    
    async def stop(self):
        """Stop all workers and cleanup."""
        self._running = False
        
        # Cancel scaler
        if self._scaler_task:
            self._scaler_task.cancel()
            try:
                await self._scaler_task
            except asyncio.CancelledError:
                pass
        
        # Stop all workers
        async with self._pool_lock:
            for worker in list(self._workers.values()):
                await worker.stop()
            self._workers.clear()
        
        logger.info("WorkerPool stopped")
    
    async def _spawn_worker(self) -> Optional[Worker]:
        """Create and start a new worker."""
        async with self._pool_lock:
            if len(self._workers) >= self.max_workers:
                logger.warning("Cannot spawn worker: max workers reached")
                return None
            
            # Find free port
            port = self._find_free_port(self.base_port + len(self._workers))
            
            # Create worker
            self._worker_id_counter += 1
            worker = Worker(
                worker_id=self._worker_id_counter,
                config=self.config,
                cdp_port=port
            )
            
            # Start it
            if await worker.start():
                self._workers[worker.worker_id] = worker
                logger.info(f"Spawned Worker-{worker.worker_id} on port {port}")
                return worker
            else:
                logger.error(f"Failed to spawn worker on port {port}")
                return None
    
    async def _kill_worker(self, worker_id: int):
        """Stop and remove a worker."""
        async with self._pool_lock:
            if worker_id in self._workers:
                worker = self._workers[worker_id]
                await worker.stop()
                del self._workers[worker_id]
                logger.info(f"Killed Worker-{worker_id}")
    
    async def _get_idle_worker(self) -> Optional[Worker]:
        """Get an idle worker from the pool."""
        async with self._pool_lock:
            for worker in self._workers.values():
                if worker.state == WorkerState.IDLE:
                    return worker
        return None
    
    async def _scaler_loop(self):
        """Background task that manages pool size."""
        while self._running:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                
                async with self._pool_lock:
                    idle_workers = [w for w in self._workers.values() 
                                   if w.state == WorkerState.IDLE]
                    busy_workers = [w for w in self._workers.values() 
                                   if w.state == WorkerState.BUSY]
                
                # Scale up: If all workers busy and under max
                if len(idle_workers) == 0 and len(self._workers) < self.max_workers:
                    logger.info("All workers busy, scaling up...")
                    await self._spawn_worker()
                
                # Scale down: Kill idle workers over min (respecting idle_timeout)
                if len(self._workers) > self.min_workers:
                    for worker in idle_workers:
                        if worker.stats.idle_time > self.idle_timeout:
                            logger.info(f"Worker-{worker.worker_id} idle for "
                                       f"{worker.stats.idle_time:.0f}s, scaling down...")
                            await self._kill_worker(worker.worker_id)
                            break  # Kill one at a time
                            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scaler error: {e}")
    
    @asynccontextmanager
    async def acquire(self):
        """
        Acquire a worker for processing.
        
        Usage:
            async with pool.acquire() as worker:
                result = await worker.execute(...)
        """
        await self._acquire_semaphore.acquire()
        worker = None
        
        try:
            if self.mode == ScalingMode.ONDEMAND:
                # On-demand: spawn new worker
                worker = await self._spawn_worker()
                if not worker:
                    raise RuntimeError("Failed to spawn on-demand worker")
                    
            else:
                # Single/Pool: get existing idle worker, or wait
                for _ in range(30):  # Wait up to 30 seconds
                    worker = await self._get_idle_worker()
                    if worker:
                        break
                    await asyncio.sleep(1)
                
                if not worker:
                    # Try to spawn if under max
                    worker = await self._spawn_worker()
                    
                if not worker:
                    raise RuntimeError("No workers available")
            
            yield worker
            
        finally:
            if self.mode == ScalingMode.ONDEMAND and worker:
                # On-demand: kill worker after use
                await self._kill_worker(worker.worker_id)
            
            self._acquire_semaphore.release()
    
    def get_stats(self) -> dict:
        """Get pool statistics."""
        workers_info = []
        for w in self._workers.values():
            workers_info.append({
                "id": w.worker_id,
                "port": w.cdp_port,
                "state": w.state.value,
                "requests_completed": w.stats.requests_completed,
                "requests_failed": w.stats.requests_failed,
                "avg_time": round(w.stats.avg_processing_time, 2),
                "idle_time": round(w.stats.idle_time, 1),
            })
        
        return {
            "mode": self.mode.value,
            "total_workers": len(self._workers),
            "idle_workers": len([w for w in self._workers.values() if w.state == WorkerState.IDLE]),
            "busy_workers": len([w for w in self._workers.values() if w.state == WorkerState.BUSY]),
            "workers": workers_info,
        }
    
    def __repr__(self):
        return f"WorkerPool(mode={self.mode.value}, workers={len(self._workers)})"
