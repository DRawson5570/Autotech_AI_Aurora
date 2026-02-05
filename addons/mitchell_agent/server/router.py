"""
Mitchell Agent API Router
=========================
FastAPI endpoints for request/result queue between Open WebUI tool and remote polling agents.

Endpoints:
    POST /api/mitchell/request          - Create new request (tool calls this)
    GET  /api/mitchell/pending/{shop_id} - Get pending requests (agent polls this)
    POST /api/mitchell/claim/{request_id} - Claim a request (agent calls this)
    POST /api/mitchell/result/{request_id} - Submit result (agent calls this)
    GET  /api/mitchell/status/{request_id} - Check status (tool polls this)
    GET  /api/mitchell/wait/{request_id}   - Wait for result (tool calls this)
    
Clarification Flow (AI Employee request_info):
    POST /api/mitchell/clarify           - Agent needs clarification (agent calls this)
    GET  /api/mitchell/clarify/{id}      - Check clarification status (agent polls this)
    POST /api/mitchell/answer/{id}       - Answer clarification (tool calls this)
    GET  /api/mitchell/clarify/pending/{request_id} - Get pending clarifications for a request
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from .models import (
    MitchellRequest,
    MitchellResult,
    RequestStatus,
    CreateRequestPayload,
    SubmitResultPayload,
    PendingRequestsResponse,
    RequestStatusResponse,
    ClarificationRequest,
    ClarificationStatus,
    SubmitClarificationPayload,
    AnswerClarificationPayload,
    ClarificationResponse,
    NavigationRequest,
    NavigationResponse,
    NavigationAction,
    TokenUsage,
)
from .queue import get_queue
from .navigation import get_navigation_decision

import logging

log = logging.getLogger("mitchell-router")


router = APIRouter(prefix="/api/mitchell", tags=["mitchell"])


@router.post("/request", response_model=MitchellRequest)
async def create_request(payload: CreateRequestPayload):
    """
    Create a new Mitchell data request.
    
    Called by the Open WebUI tool to queue a request for a remote agent.
    """
    log.info(f"[DEBUG] create_request payload: vehicle={payload.vehicle}")
    log.info(f"[DEBUG] drive_type in vehicle: {payload.vehicle.drive_type}")
    queue = get_queue()
    request = await queue.create_request(payload)
    log.info(f"[DEBUG] created request: vehicle={request.vehicle}")
    return request


@router.get("/pending/{shop_id}", response_model=PendingRequestsResponse)
async def get_pending_requests(
    shop_id: str,
    limit: int = Query(default=10, ge=1, le=100)
):
    """
    Get pending requests for a shop.
    
    Called by the remote polling agent to get work.
    """
    queue = get_queue()
    requests = await queue.get_pending_requests(shop_id, limit=limit)
    return PendingRequestsResponse(
        shop_id=shop_id,
        requests=requests,
        count=len(requests)
    )


@router.post("/claim/{request_id}", response_model=MitchellRequest)
async def claim_request(request_id: str):
    """
    Claim a request for processing.
    
    Called by the agent before starting work to prevent duplicate processing.
    """
    queue = get_queue()
    request = await queue.claim_request(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found or already claimed")
    return request


@router.post("/result/{request_id}", response_model=MitchellResult)
async def submit_result(request_id: str, payload: SubmitResultPayload):
    """
    Submit result for a request.
    
    Called by the agent after completing work.
    Also records token usage for billing if tokens_used is present.
    """
    queue = get_queue()
    
    # Get the original request to find user_id for billing
    request = await queue.get_request_status(request_id)
    
    result = await queue.submit_result(request_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="Request not found")
    
    # Record token usage for billing if we have both user_id and tokens
    if request and request.user_id and payload.tokens_used:
        try:
            from open_webui.models.billing import record_usage_event
            tokens = payload.tokens_used
            record_usage_event(
                user_id=request.user_id,
                chat_id=None,  # Mitchell tool doesn't have chat context here
                message_id=None,
                tokens_prompt=tokens.get("prompt_tokens", 0),
                tokens_completion=tokens.get("completion_tokens", 0),
                tokens_total=tokens.get("total_tokens", 0),
                token_source="mitchell_agent",
            )
            import logging
            logging.getLogger(__name__).info(
                f"[BILLING] Recorded {tokens.get('total_tokens', 0)} tokens for user {request.user_id}"
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[BILLING] Failed to record usage: {e}")
    
    return result


@router.get("/status/{request_id}", response_model=RequestStatusResponse)
async def get_request_status(request_id: str):
    """
    Check status of a request.
    
    Called by the tool to poll for completion.
    """
    queue = get_queue()
    request = await queue.get_request_status(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    result = None
    if request.status in (RequestStatus.COMPLETED, RequestStatus.FAILED):
        result = await queue.get_result(request_id)
    
    return RequestStatusResponse(
        request_id=request_id,
        status=request.status,
        result=result
    )


@router.get("/wait/{request_id}", response_model=RequestStatusResponse)
async def wait_for_result(
    request_id: str,
    timeout: float = Query(default=30.0, ge=1.0, le=600.0)
):
    """
    Wait for a request to complete.
    
    Long-polling endpoint - blocks until result is ready or timeout.
    """
    queue = get_queue()
    request = await queue.get_request_status(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    # If already completed, return immediately
    if request.status in (RequestStatus.COMPLETED, RequestStatus.FAILED, RequestStatus.EXPIRED):
        result = await queue.get_result(request_id)
        return RequestStatusResponse(
            request_id=request_id,
            status=request.status,
            result=result
        )
    
    # Wait for result
    result = await queue.wait_for_result(request_id, timeout=timeout)
    request = await queue.get_request_status(request_id)
    
    return RequestStatusResponse(
        request_id=request_id,
        status=request.status if request else RequestStatus.EXPIRED,
        result=result
    )


@router.delete("/cleanup")
async def cleanup_expired(max_age_seconds: int = Query(default=3600, ge=60)):
    """
    Cleanup expired requests.
    
    Admin endpoint - call periodically to free memory.
    """
    queue = get_queue()
    removed = await queue.cleanup_expired(max_age_seconds)
    return {"removed": removed}


# ============================================================================
# Clarification Endpoints (AI Employee request_info flow)
# ============================================================================

@router.post("/clarify", response_model=ClarificationResponse)
async def submit_clarification(payload: SubmitClarificationPayload):
    """
    Submit a clarification request.
    
    Called by the agent when the Ollama navigator needs info not in the goal.
    For example, when the vehicle requires Drive Type but user didn't specify it.
    
    The tool will poll for this and show options to the user.
    """
    queue = get_queue()
    clarification = await queue.create_clarification(payload)
    return ClarificationResponse(
        clarification_id=clarification.id,
        request_id=clarification.request_id,
        status=clarification.status,
        option_name=clarification.option_name,
        available_values=clarification.available_values,
        message=clarification.message,
        answer=clarification.answer
    )


@router.get("/clarify/{clarification_id}", response_model=ClarificationResponse)
async def get_clarification(clarification_id: str):
    """
    Get clarification status/answer.
    
    Called by the agent to check if user has answered.
    """
    queue = get_queue()
    clarification = await queue.get_clarification(clarification_id)
    if not clarification:
        raise HTTPException(status_code=404, detail="Clarification not found")
    
    return ClarificationResponse(
        clarification_id=clarification.id,
        request_id=clarification.request_id,
        status=clarification.status,
        option_name=clarification.option_name,
        available_values=clarification.available_values,
        message=clarification.message,
        answer=clarification.answer
    )


@router.get("/clarify/pending/{request_id}")
async def get_pending_clarifications(request_id: str):
    """
    Get pending clarifications for a request.
    
    Called by the tool when waiting for result - checks if agent needs clarification.
    """
    queue = get_queue()
    clarifications = await queue.get_pending_clarifications(request_id)
    return {
        "request_id": request_id,
        "clarifications": [
            ClarificationResponse(
                clarification_id=c.id,
                request_id=c.request_id,
                status=c.status,
                option_name=c.option_name,
                available_values=c.available_values,
                message=c.message,
                answer=c.answer
            ) for c in clarifications
        ],
        "count": len(clarifications)
    }


@router.post("/answer/{clarification_id}", response_model=ClarificationResponse)
async def answer_clarification(clarification_id: str, payload: AnswerClarificationPayload):
    """
    Answer a clarification request.
    
    Called by the Open WebUI tool after user selects an option.
    The agent will see this answer when it polls GET /clarify/{id}.
    """
    queue = get_queue()
    clarification = await queue.answer_clarification(clarification_id, payload.answer)
    if not clarification:
        raise HTTPException(status_code=404, detail="Clarification not found or already answered")
    
    return ClarificationResponse(
        clarification_id=clarification.id,
        request_id=clarification.request_id,
        status=clarification.status,
        option_name=clarification.option_name,
        available_values=clarification.available_values,
        message=clarification.message,
        answer=clarification.answer
    )


@router.get("/clarify/wait/{clarification_id}", response_model=ClarificationResponse)
async def wait_for_answer(
    clarification_id: str,
    timeout: float = Query(default=30.0, ge=1.0, le=180.0)
):
    """
    Wait for a clarification to be answered.
    
    Long-polling endpoint - blocks until answer is ready or timeout.
    Called by the agent instead of polling GET /clarify/{id}.
    """
    queue = get_queue()
    clarification = await queue.wait_for_clarification(clarification_id, timeout=timeout)
    if not clarification:
        raise HTTPException(status_code=404, detail="Clarification not found or timed out")
    
    return ClarificationResponse(
        clarification_id=clarification.id,
        request_id=clarification.request_id,
        status=clarification.status,
        option_name=clarification.option_name,
        available_values=clarification.available_values,
        message=clarification.message,
        answer=clarification.answer
    )


# ============================================================================
# Navigation Endpoints (Server-side navigation for clients without GPU)
# ============================================================================

@router.post("/navigate", response_model=NavigationResponse)
async def navigate_step(request: NavigationRequest):
    """
    Get the next navigation action for vehicle selection.
    
    Called by clients without local Ollama. The server uses its own 8B model
    to decide what action to take based on the current page state.
    
    Security & Billing:
    - Agent sends request_id (not user_id) to prevent spoofing
    - Server looks up the original user who created the request
    - Tokens are billed to that verified user
    - Token usage is returned in response for transparency
    """
    try:
        # Look up the original request to get user_id for billing
        queue = get_queue()
        original_request = await queue.get_request_status(request.request_id)
        
        if not original_request:
            raise HTTPException(status_code=404, detail=f"Request {request.request_id} not found")
        
        user_id = original_request.user_id
        
        decision = await get_navigation_decision(
            goal=request.goal,
            state=request.state.model_dump(),
            step=request.step
        )
        
        # Track token usage for billing
        tokens_used = None
        if decision.total_tokens > 0:
            tokens_used = TokenUsage(
                prompt_tokens=decision.prompt_tokens,
                completion_tokens=decision.completion_tokens,
                total_tokens=decision.total_tokens
            )
            
            if user_id:
                # Record usage to billing system
                try:
                    from open_webui.models.billing import record_usage_event
                    record_usage_event(
                        user_id=user_id,
                        chat_id=None,  # No chat - this is navigation
                        message_id=f"nav-{request.request_id}-step-{request.step}",
                        tokens_prompt=decision.prompt_tokens,
                        tokens_completion=decision.completion_tokens,
                        tokens_total=decision.total_tokens,
                        token_source="mitchell_navigation"
                    )
                    log.info(
                        "Billed %d tokens to user %s for request %s step %d",
                        decision.total_tokens, user_id, request.request_id, request.step
                    )
                except Exception as e:
                    # Don't fail the request if billing fails
                    log.error("Failed to record navigation billing: %s", e)
        
        return NavigationResponse(
            action=NavigationAction(
                tool=decision.tool,
                args=decision.args,
                reasoning=None
            ),
            done=decision.done,
            needs_clarification=decision.needs_clarification,
            tokens_used=tokens_used
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Navigation error: {str(e)}")