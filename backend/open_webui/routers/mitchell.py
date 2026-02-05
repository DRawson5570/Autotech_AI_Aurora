"""Mitchell Agent Integration Router

This router handles communication between Autotech AI (hp6) and 
Mitchell agents running on client machines.

Endpoints:
- POST /api/v1/mitchell/agents/register - Register a new agent
- POST /api/v1/mitchell/agents/heartbeat - Agent heartbeat
- GET  /api/v1/mitchell/queries/pending - Get pending query for agent
- POST /api/v1/mitchell/queries/{query_id}/result - Submit query result
- POST /api/v1/mitchell/queries - Create a new query (from Autotech AI chat)
- GET  /api/v1/mitchell/agents - List registered agents
- POST /api/v1/mitchell/save - Save query result to user's Knowledge base
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from open_webui.models.users import Users
from open_webui.models.files import Files, FileForm
from open_webui.models.knowledge import Knowledges, KnowledgeForm
from open_webui.storage.provider import Storage
from open_webui.utils.auth import get_verified_user, get_admin_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/mitchell", tags=["mitchell"])

# Legal notice returned to user on save (NOT stored in file)
SAVE_LEGAL_NOTICE = (
    "This saves automotive data for your personal reference. "
    "Use requires a valid subscription to the original data source. "
    "Do not redistribute."
)

# Name for the auto-created Knowledge base
SAVED_KNOWLEDGE_NAME = "Saved Automotive Data"


# ============================================================================
# In-Memory Storage (replace with database in production)
# ============================================================================

# Registered agents: {agent_id: AgentInfo}
_agents: dict[str, "AgentInfo"] = {}

# Pending queries: {query_id: QueryInfo}
_pending_queries: dict[str, "QueryInfo"] = {}

# Completed queries: {query_id: QueryResult}
_completed_queries: dict[str, "QueryResultInfo"] = {}

# Agent assignments: {agent_id: query_id} - tracks which agent is working on which query
_agent_assignments: dict[str, str] = {}


# ============================================================================
# Data Models
# ============================================================================

class AgentInfo(BaseModel):
    agent_id: str
    agent_name: str
    agent_version: str = "1.0.0"
    capabilities: list[str] = Field(default_factory=list)
    hostname: str = ""
    registered_at: datetime = Field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow)
    status: str = "ready"  # ready, busy, offline
    current_job_id: Optional[str] = None


class AgentRegistrationRequest(BaseModel):
    agent_id: str
    agent_name: str
    agent_version: str = "1.0.0"
    capabilities: list[str] = Field(default_factory=list)
    hostname: str = ""
    registered_at: Optional[str] = None


class HeartbeatRequest(BaseModel):
    agent_id: str
    status: str = "ready"
    current_job_id: Optional[str] = None
    last_job_completed_at: Optional[str] = None


class QueryInfo(BaseModel):
    query_id: str
    vehicle: dict  # {year, make, model, engine}
    question: str
    priority: int = 0
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None  # user_id
    assigned_agent_id: Optional[str] = None
    assigned_at: Optional[datetime] = None


class QueryResultInfo(BaseModel):
    query_id: str
    agent_id: str
    status: str  # ok, error
    vehicle: dict
    question: str
    answer: Optional[str] = None
    source_url: Optional[str] = None
    page_title: Optional[str] = None
    breadcrumb: Optional[str] = None
    error: Optional[str] = None
    processing_time_ms: int = 0
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    ingested_to_rag: bool = False


class CreateQueryRequest(BaseModel):
    vehicle: dict  # {year, make, model, engine}
    question: str
    priority: int = 0
    metadata: dict = Field(default_factory=dict)


class QueryResponse(BaseModel):
    query_id: str
    status: str
    message: str = ""


# ============================================================================
# RAG Ingestion Helper
# ============================================================================

async def ingest_to_rag(request: Request, result: QueryResultInfo) -> bool:
    """Ingest the Q&A pair into the RAG system.
    
    This creates a document containing:
    - Vehicle information
    - Original question
    - Answer (extracted content)
    - Source metadata
    """
    try:
        from open_webui.routers.retrieval import save_docs_to_vector_db
        from langchain_core.documents import Document
        
        # Skip if there's no answer content
        if not result.answer:
            log.warning(f"No answer content to ingest for query {result.query_id}")
            return False
        
        # Create a unique collection name for Mitchell data
        collection_name = "mitchell_automotive_qa"
        
        # Build the document content
        vehicle = result.vehicle
        vehicle_str = f"{vehicle.get('year', '')} {vehicle.get('make', '')} {vehicle.get('model', '')} {vehicle.get('engine', '')}".strip()
        
        # Clean the HTML content for better RAG retrieval
        # (In production, you might want to parse and extract text)
        content = f"""
Vehicle: {vehicle_str}

Question: {result.question}

Answer Source: {result.page_title or 'Mitchell/ShopKeyPro'}
Breadcrumb: {result.breadcrumb or 'N/A'}
Source URL: {result.source_url or 'N/A'}

Content:
{result.answer[:50000] if result.answer else 'No content'}
"""
        
        # Create metadata for filtering/retrieval
        metadata = {
            "source": "mitchell_agent",
            "query_id": result.query_id,
            "vehicle_year": vehicle.get("year", ""),
            "vehicle_make": vehicle.get("make", ""),
            "vehicle_model": vehicle.get("model", ""),
            "vehicle_engine": vehicle.get("engine", ""),
            "question": result.question,
            "page_title": result.page_title or "",
            "source_url": result.source_url or "",
            "processed_at": result.processed_at.isoformat() if isinstance(result.processed_at, datetime) else str(result.processed_at),
        }
        
        # Create Document
        doc = Document(
            page_content=content,
            metadata=metadata,
        )
        
        # Save to vector DB
        success = await run_in_threadpool(
            save_docs_to_vector_db,
            request,
            [doc],
            collection_name,
            metadata={"source": "mitchell_agent"},
            add=True,  # Add to existing collection
        )
        
        if success:
            log.info(f"Ingested query {result.query_id} to RAG collection {collection_name}")
            return True
        else:
            log.warning(f"Failed to ingest query {result.query_id} to RAG")
            return False
            
    except Exception as e:
        log.exception(f"Error ingesting to RAG: {e}")
        return False


# ============================================================================
# Agent Management Endpoints
# ============================================================================

@router.post("/agents/register")
async def register_agent(
    request: Request,
    payload: AgentRegistrationRequest,
) -> dict:
    """Register a Mitchell agent."""
    agent_id = payload.agent_id
    
    agent = AgentInfo(
        agent_id=agent_id,
        agent_name=payload.agent_name,
        agent_version=payload.agent_version,
        capabilities=payload.capabilities,
        hostname=payload.hostname,
        status="ready",
    )
    
    _agents[agent_id] = agent
    log.info(f"Agent registered: {agent_id} ({payload.agent_name})")
    
    return {
        "status": "ok",
        "agent_id": agent_id,
        "message": "Agent registered successfully",
    }


@router.post("/agents/heartbeat")
async def agent_heartbeat(
    request: Request,
    payload: HeartbeatRequest,
) -> dict:
    """Receive heartbeat from agent."""
    agent_id = payload.agent_id
    
    if agent_id not in _agents:
        # Auto-register unknown agents
        _agents[agent_id] = AgentInfo(
            agent_id=agent_id,
            agent_name=f"Agent-{agent_id[:8]}",
            status=payload.status,
        )
    
    agent = _agents[agent_id]
    agent.last_heartbeat = datetime.utcnow()
    agent.status = payload.status
    agent.current_job_id = payload.current_job_id
    
    return {"status": "ok"}


@router.get("/agents")
async def list_agents(
    request: Request,
    user=Depends(get_verified_user),
) -> list[dict]:
    """List all registered agents."""
    now = datetime.utcnow()
    agents = []
    
    for agent in _agents.values():
        # Mark agents as offline if no heartbeat in 60 seconds
        if (now - agent.last_heartbeat).total_seconds() > 60:
            agent.status = "offline"
        
        agents.append({
            "agent_id": agent.agent_id,
            "agent_name": agent.agent_name,
            "status": agent.status,
            "hostname": agent.hostname,
            "last_heartbeat": agent.last_heartbeat.isoformat(),
            "current_job_id": agent.current_job_id,
        })
    
    return agents


# ============================================================================
# Query Management Endpoints
# ============================================================================

@router.post("/queries")
async def create_query(
    request: Request,
    payload: CreateQueryRequest,
    user=Depends(get_verified_user),
) -> QueryResponse:
    """Create a new query to be processed by a Mitchell agent.
    
    Called by Autotech AI when a user asks a question that requires
    Mitchell/ShopKeyPro data.
    """
    query_id = str(uuid.uuid4())
    
    query = QueryInfo(
        query_id=query_id,
        vehicle=payload.vehicle,
        question=payload.question,
        priority=payload.priority,
        metadata=payload.metadata,
        created_by=user.id,
    )
    
    _pending_queries[query_id] = query
    log.info(f"Query created: {query_id} - {payload.question[:50]}...")
    
    return QueryResponse(
        query_id=query_id,
        status="pending",
        message="Query queued for processing",
    )


@router.get("/queries/pending")
async def get_pending_query(
    request: Request,
    agent_id: str,
) -> Optional[dict]:
    """Get a pending query for an agent to process.
    
    Returns the highest priority unassigned query, or None if no work is available.
    """
    if agent_id not in _agents:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agent not registered",
        )
    
    # Check if agent is already assigned to a query
    if agent_id in _agent_assignments:
        existing_query_id = _agent_assignments[agent_id]
        if existing_query_id in _pending_queries:
            # Return the already-assigned query
            query = _pending_queries[existing_query_id]
            return {
                "query_id": query.query_id,
                "vehicle": query.vehicle,
                "question": query.question,
                "priority": query.priority,
                "metadata": query.metadata,
            }
    
    # Find highest priority unassigned query
    unassigned = [
        q for q in _pending_queries.values()
        if q.assigned_agent_id is None
    ]
    
    if not unassigned:
        return None  # No work available
    
    # Sort by priority (higher first), then by creation time (older first)
    unassigned.sort(key=lambda q: (-q.priority, q.created_at))
    
    query = unassigned[0]
    
    # Assign to this agent
    query.assigned_agent_id = agent_id
    query.assigned_at = datetime.utcnow()
    _agent_assignments[agent_id] = query.query_id
    
    log.info(f"Query {query.query_id} assigned to agent {agent_id}")
    
    return {
        "query_id": query.query_id,
        "vehicle": query.vehicle,
        "question": query.question,
        "priority": query.priority,
        "metadata": query.metadata,
    }


@router.post("/queries/{query_id}/result")
async def submit_query_result(
    request: Request,
    query_id: str,
    payload: dict,
) -> dict:
    """Submit query result from agent.
    
    This endpoint:
    1. Stores the result
    2. Ingests the Q&A into the RAG system
    3. Notifies any waiting clients (if implementing real-time)
    """
    agent_id = payload.get("agent_id", "")
    
    # Validate query exists
    if query_id not in _pending_queries:
        # Check if already completed
        if query_id in _completed_queries:
            return {"status": "ok", "message": "Query already completed"}
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query not found",
        )
    
    query = _pending_queries[query_id]
    
    # Create result
    result = QueryResultInfo(
        query_id=query_id,
        agent_id=agent_id,
        status=payload.get("status", "error"),
        vehicle=payload.get("vehicle", query.vehicle),
        question=payload.get("question", query.question),
        answer=payload.get("answer"),
        source_url=payload.get("source_url"),
        page_title=payload.get("page_title"),
        breadcrumb=payload.get("breadcrumb"),
        error=payload.get("error"),
        processing_time_ms=payload.get("processing_time_ms", 0),
    )
    
    # Move from pending to completed
    del _pending_queries[query_id]
    _completed_queries[query_id] = result
    
    # Clear agent assignment
    if agent_id in _agent_assignments:
        del _agent_assignments[agent_id]
    
    log.info(f"Query {query_id} completed with status {result.status}")
    
    # Ingest to RAG if successful
    if result.status == "ok" and result.answer:
        try:
            ingested = await ingest_to_rag(request, result)
            result.ingested_to_rag = ingested
        except Exception as e:
            log.exception(f"RAG ingestion error: {e}")
    
    return {
        "status": "ok",
        "query_id": query_id,
        "ingested_to_rag": result.ingested_to_rag,
    }


@router.get("/queries/{query_id}")
async def get_query_status(
    request: Request,
    query_id: str,
    user=Depends(get_verified_user),
) -> dict:
    """Get the status and result of a query."""
    # Check pending
    if query_id in _pending_queries:
        query = _pending_queries[query_id]
        return {
            "query_id": query_id,
            "status": "pending",
            "assigned_agent_id": query.assigned_agent_id,
            "created_at": query.created_at.isoformat(),
        }
    
    # Check completed
    if query_id in _completed_queries:
        result = _completed_queries[query_id]
        return {
            "query_id": query_id,
            "status": result.status,
            "vehicle": result.vehicle,
            "question": result.question,
            "answer": result.answer,
            "source_url": result.source_url,
            "page_title": result.page_title,
            "breadcrumb": result.breadcrumb,
            "error": result.error,
            "processing_time_ms": result.processing_time_ms,
            "processed_at": result.processed_at.isoformat() if isinstance(result.processed_at, datetime) else str(result.processed_at),
            "ingested_to_rag": result.ingested_to_rag,
        }
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Query not found",
    )


@router.get("/queries")
async def list_queries(
    request: Request,
    user=Depends(get_verified_user),
    status_filter: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """List queries (pending and completed)."""
    queries = []
    
    # Add pending queries
    if status_filter in (None, "pending"):
        for query in list(_pending_queries.values())[:limit]:
            queries.append({
                "query_id": query.query_id,
                "status": "pending",
                "vehicle": query.vehicle,
                "question": query.question[:100],
                "created_at": query.created_at.isoformat(),
                "assigned_agent_id": query.assigned_agent_id,
            })
    
    # Add completed queries
    if status_filter in (None, "completed", "ok", "error"):
        for result in list(_completed_queries.values())[:limit]:
            if status_filter in (None, "completed") or result.status == status_filter:
                queries.append({
                    "query_id": result.query_id,
                    "status": result.status,
                    "vehicle": result.vehicle,
                    "question": result.question[:100],
                    "processed_at": result.processed_at.isoformat() if isinstance(result.processed_at, datetime) else str(result.processed_at),
                    "processing_time_ms": result.processing_time_ms,
                    "ingested_to_rag": result.ingested_to_rag,
                })
    
    return queries[:limit]


# ============================================================================
# Token Tracking & Billing
# ============================================================================

class TokenUsageReport(BaseModel):
    """Token usage from Mitchell agent."""
    user_id: str
    job_id: str = ""
    usage: dict  # {prompt_tokens, completion_tokens, total_tokens, llm_calls}
    source: str = "mitchell_agent"


class TokenDeductResponse(BaseModel):
    status: str
    tokens_deducted: int = 0
    remaining_balance: int = 0
    message: str = ""



@router.post("/tokens/deduct", response_model=TokenDeductResponse)
async def deduct_tokens(
    request: Request,
    report: TokenUsageReport,
) -> TokenDeductResponse:
    """Deduct tokens from user's balance based on Mitchell agent usage.
    
    This is called by the Mitchell agent after completing a query to
    report token usage and deduct from the user's token bank.
    """
    try:
        total_tokens = report.usage.get("total_tokens", 0)
        prompt_tokens = report.usage.get("prompt_tokens", 0)
        completion_tokens = report.usage.get("completion_tokens", 0)
        
        if total_tokens <= 0:
            return TokenDeductResponse(
                status="ok",
                tokens_deducted=0,
                message="No tokens to deduct"
            )
        
        # Record usage and deduct from user's token balance
        from open_webui.models.billing import record_usage_event, Billing, check_and_trigger_auto_renew
        
        record_usage_event(
            user_id=report.user_id,
            chat_id=report.job_id or None,
            message_id=None,
            tokens_prompt=prompt_tokens,
            tokens_completion=completion_tokens,
            tokens_total=total_tokens,
            token_source=report.source or "mitchell_agent",
        )
        
        # Check for auto-renew (non-blocking)
        try:
            check_and_trigger_auto_renew(report.user_id)
        except Exception:
            pass
        
        # Get updated balance
        remaining = Billing.get_user_balance(report.user_id)
        
        log.info(
            "Token deduction completed: user=%s, job=%s, tokens=%d (prompt=%d, completion=%d), remaining=%d",
            report.user_id,
            report.job_id,
            total_tokens,
            prompt_tokens,
            completion_tokens,
            remaining,
        )
        
        return TokenDeductResponse(
            status="ok",
            tokens_deducted=total_tokens,
            remaining_balance=remaining,
            message=f"Deducted {total_tokens} tokens for job {report.job_id}"
        )
        
    except Exception as e:
        log.error("Token deduction failed: %s", e)
        return TokenDeductResponse(
            status="error",
            message=str(e)
        )


# ============================================================================
# Save to Knowledge Base
# ============================================================================

class SaveResultRequest(BaseModel):
    """Request to save automotive data to user's Knowledge base."""
    vehicle: dict  # {year, make, model, engine}
    query: str  # The original query/question
    content: str  # The result content to save
    source: Optional[str] = None  # Data source (e.g., "mitchell", "alldata")
    tool: Optional[str] = None  # Which tool produced this (e.g., "get_fluid_capacities")


class SaveResultResponse(BaseModel):
    """Response after saving to Knowledge base."""
    status: str  # "ok" or "error"
    message: str
    file_id: Optional[str] = None
    knowledge_id: Optional[str] = None
    notice: str = SAVE_LEGAL_NOTICE


def _get_or_create_saved_knowledge(user_id: str) -> str:
    """Get or create the 'Saved Automotive Data' Knowledge base for a user.
    
    Returns the knowledge_id.
    """
    # Search for existing Knowledge base owned by this user with matching name
    user_knowledge_bases = Knowledges.get_knowledge_bases_by_user_id(user_id, permission="write")
    
    for kb in user_knowledge_bases:
        if kb.name == SAVED_KNOWLEDGE_NAME and kb.user_id == user_id:
            return kb.id
    
    # Create new Knowledge base for this user (private by default)
    knowledge = Knowledges.insert_new_knowledge(
        user_id=user_id,
        form_data=KnowledgeForm(
            name=SAVED_KNOWLEDGE_NAME,
            description="Saved automotive data for quick retrieval.",
            access_control={},  # Empty dict = private to owner only
        )
    )
    
    if not knowledge:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create Knowledge base for saved results."
        )
    
    log.info(f"Created Mitchell Knowledge base {knowledge.id} for user {user_id}")
    return knowledge.id


def _create_save_file_content(
    vehicle: dict,
    query: str,
    content: str,
    source: Optional[str] = None,
    tool: Optional[str] = None,
) -> str:
    """Format the content for the saved file."""
    vehicle_str = f"{vehicle.get('year', '')} {vehicle.get('make', '')} {vehicle.get('model', '')}".strip()
    if vehicle.get('engine'):
        vehicle_str += f" ({vehicle.get('engine')})"
    
    # Title based on source if provided
    title = f"{source.title()} Data" if source else "Automotive Data"
    
    lines = [
        f"# {title}: {vehicle_str}",
        "",
        f"**Vehicle:** {vehicle_str}",
        f"**Query:** {query}",
    ]
    
    if source:
        lines.append(f"**Source:** {source}")
    if tool:
        lines.append(f"**Tool:** {tool}")
    
    lines.extend([
        f"**Saved:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        "---",
        "",
        content,
    ])
    
    return "\n".join(lines)


def _generate_filename(vehicle: dict, query: str) -> str:
    """Generate a descriptive filename for the saved result."""
    vehicle_str = f"{vehicle.get('year', '')}_{vehicle.get('make', '')}_{vehicle.get('model', '')}".strip("_")
    # Sanitize: replace spaces and special chars
    vehicle_str = vehicle_str.replace(" ", "_").replace("/", "-")
    
    # Truncate query to first few words
    query_words = query.split()[:4]
    query_slug = "_".join(query_words).replace("/", "-")[:30]
    
    # Add timestamp for uniqueness
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    return f"mitchell_{vehicle_str}_{query_slug}_{timestamp}.md"


@router.post("/save", response_model=SaveResultResponse)
def save_result_to_knowledge(
    request: Request,
    form_data: SaveResultRequest,
    user=Depends(get_verified_user),
) -> SaveResultResponse:
    """Save a Mitchell query result to the user's Knowledge base.
    
    This creates a markdown file with the query result and adds it to
    a Knowledge base named "Mitchell Saved Data" owned by the user.
    The Knowledge base is created automatically if it doesn't exist.
    
    The file is then automatically indexed for RAG retrieval.
    """
    from open_webui.routers.retrieval import ProcessFileForm, process_file
    from io import BytesIO
    
    try:
        # 1. Get or create the user's saved automotive data Knowledge base
        knowledge_id = _get_or_create_saved_knowledge(user.id)
        
        # 2. Generate file content and name
        file_content = _create_save_file_content(
            vehicle=form_data.vehicle,
            query=form_data.query,
            content=form_data.content,
            source=form_data.source,
            tool=form_data.tool,
        )
        filename = _generate_filename(form_data.vehicle, form_data.query)
        file_id = str(uuid.uuid4())
        
        # 3. Write file to storage
        contents = file_content.encode("utf-8")
        storage_filename = f"{file_id}_{filename}"
        
        file_stream = BytesIO(contents)
        _, file_path = Storage.upload_file(
            file_stream,
            storage_filename,
            {
                "OpenWebUI-User-Email": user.email,
                "OpenWebUI-User-Id": user.id,
                "OpenWebUI-User-Name": user.name,
                "OpenWebUI-File-Id": file_id,
            },
        )
        
        # 4. Create File record in database
        file_item = Files.insert_new_file(
            user.id,
            FileForm(
                id=file_id,
                filename=filename,
                path=file_path,
                data={"content": file_content, "status": "completed"},
                meta={
                    "name": filename,
                    "content_type": "text/markdown",
                    "size": len(contents),
                    "source": form_data.source or "automotive",
                    "vehicle": form_data.vehicle,
                    "query": form_data.query,
                    "tool": form_data.tool,
                },
            ),
        )
        
        if not file_item:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create file record."
            )
        
        # 5. Process file into vector DB and add to Knowledge base
        # This indexes the content for RAG retrieval
        process_file(
            request,
            ProcessFileForm(file_id=file_id, collection_name=knowledge_id),
            user=user,
        )
        
        # 6. Link file to Knowledge base
        Knowledges.add_file_to_knowledge_by_id(
            knowledge_id=knowledge_id,
            file_id=file_id,
            user_id=user.id,
        )
        
        log.info(
            f"Saved automotive data for user {user.id}: file={file_id}, "
            f"knowledge={knowledge_id}, vehicle={form_data.vehicle}, source={form_data.source}"
        )
        
        return SaveResultResponse(
            status="ok",
            message=f"Saved to '{SAVED_KNOWLEDGE_NAME}'",
            file_id=file_id,
            knowledge_id=knowledge_id,
            notice=SAVE_LEGAL_NOTICE,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception(f"Failed to save automotive data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save result: {str(e)}"
        )
