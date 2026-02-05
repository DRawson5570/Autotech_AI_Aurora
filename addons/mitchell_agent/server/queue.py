"""
Mitchell Request Queue
======================
In-memory queue for request/result management.
For production, swap with Redis or database-backed implementation.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from .models import (
    MitchellRequest,
    MitchellResult,
    RequestStatus,
    CreateRequestPayload,
    SubmitResultPayload,
    ClarificationRequest,
    ClarificationStatus,
    SubmitClarificationPayload,
)


class RequestQueue:
    """
    In-memory request queue.
    
    In production, consider:
    - Redis for distributed systems
    - PostgreSQL for persistence
    - RabbitMQ/Celery for robust queuing
    """
    
    def __init__(self, default_ttl_seconds: int = 300):
        self._requests: Dict[str, MitchellRequest] = {}
        self._results: Dict[str, MitchellResult] = {}
        self._clarifications: Dict[str, ClarificationRequest] = {}
        self._lock = asyncio.Lock()
        self._default_ttl = default_ttl_seconds
        self._result_events: Dict[str, asyncio.Event] = {}
        self._clarification_events: Dict[str, asyncio.Event] = {}
    
    async def create_request(self, payload: CreateRequestPayload) -> MitchellRequest:
        """Create a new request and add to queue."""
        async with self._lock:
            request = MitchellRequest(
                shop_id=payload.shop_id,
                user_id=payload.user_id,  # For billing when using server-side navigation
                tool=payload.tool,
                vehicle=payload.vehicle,
                params=payload.params,
                status=RequestStatus.PENDING,
                expires_at=datetime.utcnow() + timedelta(seconds=payload.timeout_seconds or self._default_ttl)
            )
            self._requests[request.id] = request
            self._result_events[request.id] = asyncio.Event()
            return request
    
    async def get_pending_requests(self, shop_id: str, limit: int = 10) -> List[MitchellRequest]:
        """Get pending requests for a shop."""
        async with self._lock:
            now = datetime.utcnow()
            pending = []
            
            for req in self._requests.values():
                # Check if belongs to shop and is pending
                if req.shop_id != shop_id:
                    continue
                if req.status != RequestStatus.PENDING:
                    continue
                    
                # Check expiration
                if req.expires_at and req.expires_at < now:
                    req.status = RequestStatus.EXPIRED
                    req.updated_at = now
                    continue
                
                pending.append(req)
                if len(pending) >= limit:
                    break
            
            return pending
    
    async def claim_request(self, request_id: str) -> Optional[MitchellRequest]:
        """Mark a request as being processed."""
        async with self._lock:
            request = self._requests.get(request_id)
            if not request:
                return None
            if request.status != RequestStatus.PENDING:
                return None
            
            request.status = RequestStatus.PROCESSING
            request.updated_at = datetime.utcnow()
            return request
    
    async def submit_result(self, request_id: str, payload: SubmitResultPayload) -> Optional[MitchellResult]:
        """Submit result for a request."""
        async with self._lock:
            request = self._requests.get(request_id)
            if not request:
                return None
            
            result = MitchellResult(
                request_id=request_id,
                success=payload.success,
                data=payload.data,
                error=payload.error,
                tool_used=payload.tool_used,
                execution_time_ms=payload.execution_time_ms,
                images=payload.images,
                tokens_used=payload.tokens_used,
            )
            
            self._results[request_id] = result
            request.status = RequestStatus.COMPLETED if payload.success else RequestStatus.FAILED
            request.updated_at = datetime.utcnow()
            
            # Signal waiters
            if request_id in self._result_events:
                self._result_events[request_id].set()
            
            return result
    
    async def get_result(self, request_id: str) -> Optional[MitchellResult]:
        """Get result for a request (non-blocking)."""
        return self._results.get(request_id)
    
    async def wait_for_result(self, request_id: str, timeout: float = 60.0) -> Optional[MitchellResult]:
        """Wait for a result with timeout."""
        event = self._result_events.get(request_id)
        if not event:
            return None
        
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return self._results.get(request_id)
        except asyncio.TimeoutError:
            # Mark as expired
            async with self._lock:
                request = self._requests.get(request_id)
                if request and request.status == RequestStatus.PENDING:
                    request.status = RequestStatus.EXPIRED
                    request.updated_at = datetime.utcnow()
            return None
    
    async def get_request_status(self, request_id: str) -> Optional[MitchellRequest]:
        """Get current status of a request."""
        return self._requests.get(request_id)
    
    async def cleanup_expired(self, max_age_seconds: int = 3600) -> int:
        """Remove old requests and results."""
        async with self._lock:
            now = datetime.utcnow()
            cutoff = now - timedelta(seconds=max_age_seconds)
            
            to_remove = [
                rid for rid, req in self._requests.items()
                if req.updated_at < cutoff
            ]
            
            for rid in to_remove:
                del self._requests[rid]
                self._results.pop(rid, None)
                self._result_events.pop(rid, None)
            
            return len(to_remove)
    
    # =========================================================================
    # Clarification Methods (AI Employee request_info flow)
    # =========================================================================
    
    async def create_clarification(self, payload: SubmitClarificationPayload) -> ClarificationRequest:
        """Create a new clarification request."""
        async with self._lock:
            clarification = ClarificationRequest(
                request_id=payload.request_id,
                shop_id=payload.shop_id,
                option_name=payload.option_name,
                available_values=payload.available_values,
                message=payload.message,
                status=ClarificationStatus.PENDING
            )
            self._clarifications[clarification.id] = clarification
            self._clarification_events[clarification.id] = asyncio.Event()
            return clarification
    
    async def get_clarification(self, clarification_id: str) -> Optional[ClarificationRequest]:
        """Get a clarification by ID."""
        return self._clarifications.get(clarification_id)
    
    async def get_pending_clarifications(self, request_id: str) -> List[ClarificationRequest]:
        """Get pending clarifications for a request."""
        async with self._lock:
            return [
                c for c in self._clarifications.values()
                if c.request_id == request_id and c.status == ClarificationStatus.PENDING
            ]
    
    async def answer_clarification(self, clarification_id: str, answer: str) -> Optional[ClarificationRequest]:
        """Answer a clarification request."""
        async with self._lock:
            clarification = self._clarifications.get(clarification_id)
            if not clarification:
                return None
            if clarification.status != ClarificationStatus.PENDING:
                return None
            
            clarification.answer = answer
            clarification.status = ClarificationStatus.ANSWERED
            clarification.answered_at = datetime.utcnow()
            
            # Signal waiters
            if clarification_id in self._clarification_events:
                self._clarification_events[clarification_id].set()
            
            return clarification
    
    async def wait_for_clarification(self, clarification_id: str, timeout: float = 60.0) -> Optional[ClarificationRequest]:
        """Wait for a clarification to be answered."""
        clarification = self._clarifications.get(clarification_id)
        if not clarification:
            return None
        
        # Already answered?
        if clarification.status == ClarificationStatus.ANSWERED:
            return clarification
        
        event = self._clarification_events.get(clarification_id)
        if not event:
            return None
        
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return self._clarifications.get(clarification_id)
        except asyncio.TimeoutError:
            # Mark as expired
            async with self._lock:
                if clarification.status == ClarificationStatus.PENDING:
                    clarification.status = ClarificationStatus.EXPIRED
            return clarification


# Global queue instance
_queue: Optional[RequestQueue] = None


def get_queue() -> RequestQueue:
    """Get or create the global queue instance."""
    global _queue
    if _queue is None:
        _queue = RequestQueue()
    return _queue
