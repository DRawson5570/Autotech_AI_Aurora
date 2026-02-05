"""Autodb Tool Router - Operation CHARM Integration

This router provides an API for querying the Operation CHARM automotive
repair database (autodb). Unlike Mitchell, autodb is a static site with
free data, so no authentication or agent infrastructure is needed.

Endpoints:
- POST /api/v1/autodb/query - Query autodb for automotive info
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from open_webui.utils.auth import get_verified_user

log = logging.getLogger(__name__)

router = APIRouter(tags=["autodb"])


# ============================================================================
# Data Models
# ============================================================================

class VehicleInfo(BaseModel):
    """Vehicle information for the query."""
    year: str = Field(..., description="Vehicle year (e.g., '2012')")
    make: str = Field(..., description="Vehicle make (e.g., 'Jeep')")
    model: str = Field(..., description="Vehicle model with engine (e.g., 'Liberty 4WD V6-3.7L')")


class QueryRequest(BaseModel):
    """Request to query autodb."""
    goal: str = Field(..., description="What to look up (e.g., 'oil capacity', 'coolant type')")
    vehicle: VehicleInfo = Field(..., description="Vehicle information")


class QueryResponse(BaseModel):
    """Response from autodb query."""
    success: bool = Field(..., description="Whether the query succeeded")
    content: str = Field(default="", description="The extracted content from autodb")
    url: str = Field(default="", description="URL of the page where content was found")
    breadcrumb: str = Field(default="", description="Navigation breadcrumb path")
    path: str = Field(default="", description="Navigation path taken")
    error: Optional[str] = Field(default=None, description="Error message if failed")


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/query", response_model=QueryResponse)
async def query_autodb(
    request: QueryRequest,
    user=Depends(get_verified_user)
):
    """
    Query the Operation CHARM (autodb) database for automotive information.
    
    This is a free resource - no subscription required.
    
    Common queries:
    - "oil capacity" - Engine oil capacity and type
    - "coolant capacity" - Coolant capacity and type
    - "transmission fluid" - ATF capacity and type
    - "differential fluid" - Differential/axle fluid specs
    - "lug nut torque" - Wheel torque specs
    - "spark plug" - Spark plug specifications
    - "firing order" - Engine firing order
    """
    try:
        # Import here to avoid circular imports
        from addons.autodb_tool.navigator import AutodbNavigator
        
        # Create navigator with default settings
        navigator = AutodbNavigator()
        
        # Convert vehicle to dict format expected by navigator
        vehicle = {
            "year": request.vehicle.year,
            "make": request.vehicle.make,
            "model": request.vehicle.model,
        }
        
        # Navigate to find the information
        result = await navigator.navigate(request.goal, vehicle)
        
        # Check for 404 pages in content
        is_404 = "Page Not Found" in result.content or "Error 404" in result.content
        
        if is_404:
            return QueryResponse(
                success=False,
                content="",
                url="",
                breadcrumb="",
                path=" -> ".join(result.path_taken) if result.path_taken else "",
                error=f"Vehicle not found in Operation CHARM database: {request.vehicle.year} {request.vehicle.make} {request.vehicle.model}"
            )
        
        return QueryResponse(
            success=result.success,
            content=result.content,
            url=result.url,
            breadcrumb=result.breadcrumb,
            path=" -> ".join(result.path_taken) if result.path_taken else "",
            error=None if result.success else "Could not find the requested information"
        )
        
    except Exception as e:
        log.exception(f"Error querying autodb: {e}")
        return QueryResponse(
            success=False,
            content="",
            url="",
            breadcrumb="",
            path="",
            error=str(e)
        )
