"""
Mitchell Request/Result Models
==============================
Pydantic models for the request queue system.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field
import uuid


class RequestStatus(str, Enum):
    """Status of a Mitchell request."""
    PENDING = "pending"      # Waiting for agent to pick up
    PROCESSING = "processing"  # Agent is working on it
    COMPLETED = "completed"   # Result available
    FAILED = "failed"        # Agent reported failure
    EXPIRED = "expired"      # Timed out waiting for agent


class ToolType(str, Enum):
    """Available tool types."""
    # Unified autonomous tool (primary)
    QUERY_AUTONOMOUS = "query_autonomous"
    
    # Legacy tools (kept for backward compatibility)
    FLUID_CAPACITIES = "get_fluid_capacities"
    DTC_INFO = "get_dtc_info"
    TORQUE_SPECS = "get_torque_specs"
    RESET_PROCEDURE = "get_reset_procedure"
    TSB_LIST = "get_tsb_list"
    ADAS_CALIBRATION = "get_adas_calibration"
    TIRE_SPECS = "get_tire_specs"
    WIRING_DIAGRAM = "get_wiring_diagram"
    SPECS_PROCEDURES = "get_specs_procedures"
    COMPONENT_LOCATION = "get_component_location"
    COMPONENT_TESTS = "get_component_tests"
    VIN_PLATE_LOOKUP = "lookup_vehicle"
    QUERY_BY_PLATE = "query_by_plate"
    SEARCH = "search_mitchell"
    QUERY = "query_mitchell"


class VehicleInfo(BaseModel):
    """Vehicle specification."""
    year: int
    make: str
    model: str
    engine: Optional[str] = None
    submodel: Optional[str] = None
    body_style: Optional[str] = None
    drive_type: Optional[str] = None


class MitchellRequest(BaseModel):
    """A request for Mitchell data."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    shop_id: str = Field(..., description="Identifier for the shop/agent")
    user_id: Optional[str] = Field(None, description="User ID for billing")
    tool: ToolType = Field(..., description="Which tool to execute")
    vehicle: VehicleInfo = Field(..., description="Vehicle information")
    params: Dict[str, Any] = Field(default_factory=dict, description="Additional parameters")
    status: RequestStatus = Field(default=RequestStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True


class MitchellResult(BaseModel):
    """Result from a Mitchell request."""
    request_id: str = Field(..., description="ID of the original request")
    success: bool = Field(..., description="Whether the request succeeded")
    data: Optional[Any] = Field(default=None, description="Result data (dict or list)")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    tool_used: Optional[str] = Field(default=None, description="Tool that was executed")
    images: Optional[List[Dict[str, str]]] = Field(default=None, description="Base64-encoded images")
    execution_time_ms: Optional[int] = Field(default=None, description="Execution time in milliseconds")
    tokens_used: Optional[Dict[str, int]] = Field(default=None, description="Token usage for billing {prompt_tokens, completion_tokens, total_tokens}")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CreateRequestPayload(BaseModel):
    """Payload for creating a new request."""
    shop_id: str
    user_id: Optional[str] = Field(None, description="User ID for billing (server-side navigation)")
    tool: ToolType
    vehicle: VehicleInfo
    params: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=60, description="How long to wait for result")


class SubmitResultPayload(BaseModel):
    """Payload for submitting a result."""
    success: bool
    data: Optional[Any] = None  # Can be dict, list, or any JSON-serializable data
    error: Optional[str] = None
    tool_used: Optional[str] = None
    images: Optional[List[Dict[str, str]]] = None  # Base64-encoded images
    execution_time_ms: Optional[int] = None
    tokens_used: Optional[Dict[str, int]] = None  # Token usage for billing


class PendingRequestsResponse(BaseModel):
    """Response containing pending requests for a shop."""
    shop_id: str
    requests: List[MitchellRequest]
    count: int


class RequestStatusResponse(BaseModel):
    """Response for request status check."""
    request_id: str
    status: RequestStatus
    result: Optional[MitchellResult] = None


# ============================================================================
# Clarification Models (for AI Employee request_info flow)
# ============================================================================

class ClarificationStatus(str, Enum):
    """Status of a clarification request."""
    PENDING = "pending"      # Waiting for Autotech AI to answer
    ANSWERED = "answered"    # User provided answer
    EXPIRED = "expired"      # Timed out waiting


class ClarificationRequest(BaseModel):
    """
    Request for clarification when navigator needs info not in the goal.
    
    Flow:
    1. Agent calls POST /clarify with option_name and available_values
    2. Server stores request, returns clarification_id
    3. Autotech AI shows options to user
    4. User answers, tool calls POST /answer/{clarification_id}
    5. Agent polls GET /answer/{clarification_id} and gets the answer
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str = Field(..., description="ID of the parent MitchellRequest")
    shop_id: str = Field(..., description="Shop that needs clarification")
    option_name: str = Field(..., description="What option is needed, e.g. 'Drive Type'")
    available_values: List[str] = Field(..., description="Available options to choose from")
    message: str = Field(..., description="Helpful message for the user")
    status: ClarificationStatus = Field(default=ClarificationStatus.PENDING)
    answer: Optional[str] = Field(default=None, description="User's answer")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    answered_at: Optional[datetime] = Field(default=None)
    
    class Config:
        use_enum_values = True


class SubmitClarificationPayload(BaseModel):
    """Payload for agent submitting a clarification request."""
    request_id: str = Field(..., description="ID of the parent MitchellRequest")
    shop_id: str
    option_name: str
    available_values: List[str]
    message: str


class AnswerClarificationPayload(BaseModel):
    """Payload for Open WebUI tool answering a clarification."""
    answer: str = Field(..., description="The user's selected value")


class ClarificationResponse(BaseModel):
    """Response for clarification status."""
    clarification_id: str
    request_id: str = Field(..., description="ID of the parent MitchellRequest")
    status: ClarificationStatus
    option_name: str
    available_values: List[str]
    message: str
    answer: Optional[str] = None


# ============================================================================
# Navigation Models (Server-side navigation for clients without GPU)
# ============================================================================

class PageState(BaseModel):
    """Current state of the vehicle selector page."""
    current_tab: Optional[str] = Field(None, description="Active tab: Year, Make, Model, etc.")
    values: List[str] = Field(default_factory=list, description="Available values to select")
    options: List[Dict[str, Any]] = Field(default_factory=list, description="Option groups with values")


class NavigationRequest(BaseModel):
    """Request for server to decide next navigation action."""
    request_id: str = Field(..., description="Original Mitchell request ID for billing lookup")
    shop_id: str = Field(..., description="Shop identifier")
    goal: str = Field(..., description="Vehicle selection goal, e.g. '2018 Ford F-150 5.0L XLT'")
    state: PageState = Field(..., description="Current page state")
    step: int = Field(default=1, description="Current step number")


class NavigationAction(BaseModel):
    """Server's recommended navigation action."""
    tool: str = Field(..., description="Tool to call: select_year, select_make, request_info, etc.")
    args: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool")
    reasoning: Optional[str] = Field(None, description="Why this action was chosen")


class TokenUsage(BaseModel):
    """Token usage from server-side Ollama call."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class NavigationResponse(BaseModel):
    """Response from server navigation endpoint."""
    action: NavigationAction
    done: bool = Field(default=False, description="Whether navigation is complete")
    needs_clarification: bool = Field(default=False, description="Whether user input is needed")
    tokens_used: Optional[TokenUsage] = Field(None, description="Tokens used for this navigation step (billable)")

