"""
Scan Tool API Router

Provides endpoints for:
- Receiving scan data from mobile/web clients
- AI-powered diagnosis from scan data
- Vehicle identification from VIN
"""

import logging
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from open_webui.utils.auth import get_current_user
from open_webui.models.users import Users

logger = logging.getLogger("scan_api")

router = APIRouter(prefix="/scan", tags=["scan"])

# Path to the web interface
WEB_DIR = Path(__file__).parent.parent.parent.parent / "addons" / "scantool_tool" / "web"


# Request/Response Models

class DTCInput(BaseModel):
    """Diagnostic Trouble Code input."""
    code: str = Field(..., description="DTC code (e.g., P0300)")
    status: str = Field(default="current", description="current, pending, or permanent")


class FreezeFrameInput(BaseModel):
    """Freeze frame data captured when DTC was set."""
    coolant_temp: Optional[float] = Field(None, description="Coolant temp in °C")
    engine_rpm: Optional[float] = Field(None, description="Engine RPM")
    vehicle_speed: Optional[float] = Field(None, description="Speed in km/h")
    load: Optional[float] = Field(None, description="Engine load %")
    stft1: Optional[float] = Field(None, description="Short term fuel trim bank 1 %")
    ltft1: Optional[float] = Field(None, description="Long term fuel trim bank 1 %")


class LivePIDsInput(BaseModel):
    """Live PID data from vehicle."""
    stft1: Optional[float] = Field(None, description="Short term fuel trim bank 1 %")
    ltft1: Optional[float] = Field(None, description="Long term fuel trim bank 1 %")
    stft2: Optional[float] = Field(None, description="Short term fuel trim bank 2 %")
    ltft2: Optional[float] = Field(None, description="Long term fuel trim bank 2 %")
    maf: Optional[float] = Field(None, description="Mass air flow g/s")
    map_pressure: Optional[float] = Field(None, description="Manifold pressure kPa")
    coolant_temp: Optional[float] = Field(None, description="Coolant temp °C")
    intake_temp: Optional[float] = Field(None, description="Intake air temp °C")
    rpm: Optional[float] = Field(None, description="Engine RPM")
    load: Optional[float] = Field(None, description="Engine load %")
    throttle: Optional[float] = Field(None, description="Throttle position %")
    timing: Optional[float] = Field(None, description="Timing advance °")
    o2_b1s1: Optional[float] = Field(None, description="O2 sensor bank 1 sensor 1 V")
    o2_b1s2: Optional[float] = Field(None, description="O2 sensor bank 1 sensor 2 V")
    o2_b2s1: Optional[float] = Field(None, description="O2 sensor bank 2 sensor 1 V")
    o2_b2s2: Optional[float] = Field(None, description="O2 sensor bank 2 sensor 2 V")
    control_voltage: Optional[float] = Field(None, description="ECU voltage V")
    vehicle_speed: Optional[float] = Field(None, description="Speed km/h")
    fuel_level: Optional[float] = Field(None, description="Fuel level %")


class MonitorsInput(BaseModel):
    """Readiness monitor status."""
    catalyst: Optional[str] = Field(None, description="complete, incomplete, not_supported")
    evap: Optional[str] = Field(None, description="complete, incomplete, not_supported")
    o2_sensor: Optional[str] = Field(None, description="complete, incomplete, not_supported")
    o2_heater: Optional[str] = Field(None, description="complete, incomplete, not_supported")
    egr: Optional[str] = Field(None, description="complete, incomplete, not_supported")
    secondary_air: Optional[str] = Field(None, description="complete, incomplete, not_supported")
    misfire: Optional[str] = Field(None, description="complete, incomplete, not_supported")
    fuel_system: Optional[str] = Field(None, description="complete, incomplete, not_supported")


class VehicleInput(BaseModel):
    """Vehicle identification."""
    year: Optional[int] = Field(None, description="Vehicle year")
    make: Optional[str] = Field(None, description="Vehicle make")
    model: Optional[str] = Field(None, description="Vehicle model")
    engine: Optional[str] = Field(None, description="Engine specification")
    vin: Optional[str] = Field(None, description="VIN if available")


class DiagnoseRequest(BaseModel):
    """Full diagnostic request with all scan data."""
    vehicle: VehicleInput
    dtcs: List[DTCInput] = Field(default_factory=list)
    freeze_frame: Optional[FreezeFrameInput] = None
    live_pids: Optional[LivePIDsInput] = None
    monitors: Optional[MonitorsInput] = None
    symptoms: Optional[str] = Field(None, description="Additional symptoms described by tech")


class LikelyCause(BaseModel):
    """A likely cause with probability."""
    cause: str
    probability: str  # "high", "medium", "low"
    explanation: Optional[str] = None


class RecommendedTest(BaseModel):
    """A recommended diagnostic test."""
    test: str
    reason: Optional[str] = None
    expected_result: Optional[str] = None


class DiagnosisResponse(BaseModel):
    """AI diagnostic response."""
    summary: str
    confidence: str  # "high", "medium", "low"
    reasoning: str
    likely_causes: List[LikelyCause]
    recommended_tests: List[RecommendedTest]
    safety_notes: List[str] = Field(default_factory=list)
    additional_info: Optional[str] = None


class VINDecodeResponse(BaseModel):
    """VIN decode response."""
    vin: str
    year: int
    make: str
    model: str
    engine: Optional[str] = None
    transmission: Optional[str] = None
    drive_type: Optional[str] = None
    body_style: Optional[str] = None


# Helper functions

def build_diagnosis_prompt(request: DiagnoseRequest) -> str:
    """Build a prompt for the AI to diagnose from scan data."""
    
    parts = ["Analyze this vehicle scan data and provide a diagnosis:\n"]
    
    # Vehicle info
    v = request.vehicle
    if v.year or v.make or v.model:
        vehicle_str = " ".join(filter(None, [str(v.year) if v.year else None, v.make, v.model, v.engine]))
        parts.append(f"VEHICLE: {vehicle_str}")
    if v.vin:
        parts.append(f"VIN: {v.vin}")
    
    # DTCs
    if request.dtcs:
        parts.append("\nDIAGNOSTIC TROUBLE CODES:")
        for dtc in request.dtcs:
            parts.append(f"  - {dtc.code} ({dtc.status})")
    
    # Freeze frame
    if request.freeze_frame:
        parts.append("\nFREEZE FRAME (conditions when code set):")
        ff = request.freeze_frame
        if ff.coolant_temp is not None:
            parts.append(f"  Coolant Temp: {ff.coolant_temp}°C")
        if ff.engine_rpm is not None:
            parts.append(f"  RPM: {ff.engine_rpm}")
        if ff.vehicle_speed is not None:
            parts.append(f"  Speed: {ff.vehicle_speed} km/h")
        if ff.load is not None:
            parts.append(f"  Load: {ff.load}%")
        if ff.stft1 is not None:
            parts.append(f"  STFT1: {ff.stft1:+.1f}%")
        if ff.ltft1 is not None:
            parts.append(f"  LTFT1: {ff.ltft1:+.1f}%")
    
    # Live PIDs
    if request.live_pids:
        parts.append("\nLIVE DATA:")
        pids = request.live_pids
        
        # Fuel trims (most important)
        if pids.stft1 is not None or pids.ltft1 is not None:
            stft1 = pids.stft1 if pids.stft1 is not None else 0
            ltft1 = pids.ltft1 if pids.ltft1 is not None else 0
            total1 = stft1 + ltft1
            parts.append(f"  Bank 1 Fuel Trims: STFT {stft1:+.1f}%, LTFT {ltft1:+.1f}% (Total: {total1:+.1f}%)")
        
        if pids.stft2 is not None or pids.ltft2 is not None:
            stft2 = pids.stft2 if pids.stft2 is not None else 0
            ltft2 = pids.ltft2 if pids.ltft2 is not None else 0
            total2 = stft2 + ltft2
            parts.append(f"  Bank 2 Fuel Trims: STFT {stft2:+.1f}%, LTFT {ltft2:+.1f}% (Total: {total2:+.1f}%)")
        
        # Engine params
        if pids.rpm is not None:
            parts.append(f"  RPM: {pids.rpm:.0f}")
        if pids.load is not None:
            parts.append(f"  Load: {pids.load:.1f}%")
        if pids.coolant_temp is not None:
            parts.append(f"  Coolant Temp: {pids.coolant_temp:.0f}°C")
        if pids.intake_temp is not None:
            parts.append(f"  Intake Temp: {pids.intake_temp:.0f}°C")
        if pids.throttle is not None:
            parts.append(f"  Throttle: {pids.throttle:.1f}%")
        if pids.timing is not None:
            parts.append(f"  Timing Advance: {pids.timing:.1f}°")
        
        # Air metering
        if pids.maf is not None:
            parts.append(f"  MAF: {pids.maf:.2f} g/s")
        if pids.map_pressure is not None:
            parts.append(f"  MAP: {pids.map_pressure:.0f} kPa")
        
        # O2 sensors
        o2_data = []
        if pids.o2_b1s1 is not None:
            o2_data.append(f"B1S1: {pids.o2_b1s1:.3f}V")
        if pids.o2_b1s2 is not None:
            o2_data.append(f"B1S2: {pids.o2_b1s2:.3f}V")
        if pids.o2_b2s1 is not None:
            o2_data.append(f"B2S1: {pids.o2_b2s1:.3f}V")
        if pids.o2_b2s2 is not None:
            o2_data.append(f"B2S2: {pids.o2_b2s2:.3f}V")
        if o2_data:
            parts.append(f"  O2 Sensors: {', '.join(o2_data)}")
        
        # Electrical
        if pids.control_voltage is not None:
            parts.append(f"  System Voltage: {pids.control_voltage:.2f}V")
    
    # Monitors
    if request.monitors:
        parts.append("\nREADINESS MONITORS:")
        m = request.monitors
        for name in ["catalyst", "evap", "o2_sensor", "o2_heater", "egr", "misfire", "fuel_system"]:
            status = getattr(m, name, None)
            if status:
                parts.append(f"  {name.replace('_', ' ').title()}: {status}")
    
    # Additional symptoms
    if request.symptoms:
        parts.append(f"\nADDITIONAL SYMPTOMS: {request.symptoms}")
    
    parts.append("\n---")
    parts.append("Provide diagnosis with: summary, reasoning from the data, likely causes (ranked), and recommended tests.")
    
    return "\n".join(parts)


async def get_ai_diagnosis(request: Request, prompt: str, user) -> Optional[DiagnosisResponse]:
    """Get AI diagnosis from the prompt using the configured AI model."""
    from open_webui.utils.chat import generate_chat_completion
    from open_webui.utils.task import get_task_model_id
    
    system_prompt = """You are an expert automotive diagnostician analyzing scan tool data.

Analyze the provided data and respond with a JSON object containing:
{
    "summary": "One sentence summary of the issue",
    "confidence": "high/medium/low",
    "reasoning": "Detailed explanation of how the data leads to your conclusion",
    "likely_causes": [
        {"cause": "Description", "probability": "high/medium/low", "explanation": "Why this is likely"}
    ],
    "recommended_tests": [
        {"test": "What to test", "reason": "Why", "expected_result": "What to look for"}
    ],
    "safety_notes": ["Any safety concerns"]
}

Focus on:
1. Fuel trim analysis (±10% is normal, beyond that indicates issues)
2. Bank-to-bank comparison on V6/V8 engines
3. Correlation between DTCs and live data
4. Freeze frame conditions (was it at idle? driving?)
5. O2 sensor behavior (front should oscillate, rear should be steady ~0.7V)

IMPORTANT: Respond with ONLY the JSON object, no markdown code blocks or other text."""

    try:
        # Get task model for analysis
        models = request.app.state.MODELS
        task_model_id = get_task_model_id(
            request.app.state.config.TASK_MODEL,
            request.app.state.config.TASK_MODEL_EXTERNAL,
            models,
        )
        
        if not task_model_id:
            logger.warning("No task model configured for AI diagnosis")
            return None
            
        payload = {
            "model": task_model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "max_tokens": 2000,
        }
        
        response = await generate_chat_completion(request, form_data=payload, user=user)
        
        # Parse response
        if hasattr(response, 'body'):
            body = response.body
            if isinstance(body, bytes):
                body = body.decode('utf-8')
            data = json.loads(body)
        else:
            data = response
            
        # Extract content from response
        content = ""
        if "choices" in data and len(data["choices"]) > 0:
            content = data["choices"][0].get("message", {}).get("content", "")
        
        if not content:
            return None
            
        # Parse JSON from content (handle markdown code blocks)
        content = content.strip()
        if content.startswith("```"):
            # Remove markdown code blocks
            lines = content.split('\n')
            content = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])
        
        diagnosis_data = json.loads(content)
        
        return DiagnosisResponse(
            summary=diagnosis_data.get("summary", "AI analysis complete"),
            confidence=diagnosis_data.get("confidence", "medium"),
            reasoning=diagnosis_data.get("reasoning", ""),
            likely_causes=[
                LikelyCause(**c) for c in diagnosis_data.get("likely_causes", [])
            ],
            recommended_tests=[
                RecommendedTest(**t) for t in diagnosis_data.get("recommended_tests", [])
            ],
            safety_notes=diagnosis_data.get("safety_notes", [])
        )
        
    except Exception as e:
        logger.error(f"AI diagnosis failed: {e}")
        return None


# API Endpoints

@router.post("/diagnose", response_model=DiagnosisResponse)
async def diagnose_from_scan(
    req: Request,
    request: DiagnoseRequest,
    user=Depends(get_current_user)
):
    """
    Analyze scan tool data and provide AI diagnosis.
    
    Submit DTCs, live PIDs, freeze frame data and get an intelligent diagnosis
    with likely causes and recommended tests.
    """
    logger.info(f"Diagnosis request from user {user.id}")
    
    # Build the prompt
    prompt = build_diagnosis_prompt(request)
    logger.debug(f"Diagnosis prompt:\n{prompt}")
    
    # Try AI-powered diagnosis first
    ai_diagnosis = await get_ai_diagnosis(req, prompt, user)
    if ai_diagnosis:
        logger.info("AI diagnosis successful")
        
        # Collect training data
        try:
            from addons.training_data.chat_hook import collect_from_scan_tool
            vehicle_dict = {}
            if request.vehicle:
                vehicle_dict = {
                    "year": request.vehicle.year,
                    "make": request.vehicle.make,
                    "model": request.vehicle.model,
                    "engine": request.vehicle.engine
                }
            scan_dict = {
                "dtcs": [{"code": d.code, "status": d.status} for d in request.dtcs] if request.dtcs else [],
                "live_pids": request.live_pids.model_dump() if request.live_pids else {},
                "freeze_frame": request.freeze_frame.model_dump() if request.freeze_frame else {}
            }
            collect_from_scan_tool(
                vehicle=vehicle_dict,
                scan_data=scan_dict,
                diagnosis=ai_diagnosis.summary + " | " + ai_diagnosis.reasoning
            )
        except Exception as e:
            logger.debug(f"Training data collection skipped: {e}")
        
        return ai_diagnosis
    
    # Fallback to heuristic-based diagnosis
    logger.info("Falling back to heuristic diagnosis")
    
    # Quick fuel trim analysis
    quick_analysis = None
    if request.live_pids:
        pids = request.live_pids
        if pids.stft1 is not None and pids.ltft1 is not None:
            try:
                from addons.scan_tool.legacy.elm327 import analyze_fuel_trims
                quick_analysis = analyze_fuel_trims(
                    pids.stft1, pids.ltft1,
                    pids.stft2, pids.ltft2
                )
            except ImportError:
                pass
    
    # Heuristic-based diagnosis fallback
    likely_causes = []
    recommended_tests = []
    safety_notes = []
    reasoning_parts = []
    
    # Analyze DTCs
    if request.dtcs:
        dtc_codes = [d.code for d in request.dtcs]
        reasoning_parts.append(f"DTCs present: {', '.join(dtc_codes)}")
        
        # Check for common patterns
        if any("P030" in c for c in dtc_codes):
            # Misfire codes
            if "P0300" in dtc_codes:
                likely_causes.append(LikelyCause(
                    cause="Random/multiple cylinder misfire",
                    probability="high",
                    explanation="P0300 indicates misfires not isolated to one cylinder - often fuel or air delivery issue"
                ))
            
            # Check if specific cylinder
            specific_misfires = [c for c in dtc_codes if c.startswith("P030") and c != "P0300"]
            if specific_misfires:
                likely_causes.append(LikelyCause(
                    cause=f"Cylinder-specific misfire ({', '.join(specific_misfires)})",
                    probability="high",
                    explanation="Check ignition components (coil, plug, wire) on affected cylinders"
                ))
        
        if "P0171" in dtc_codes or "P0174" in dtc_codes:
            bank = "1" if "P0171" in dtc_codes else "2"
            likely_causes.append(LikelyCause(
                cause=f"System too lean - Bank {bank}",
                probability="high",
                explanation="Vacuum leak, weak fuel pump, or MAF sensor issue"
            ))
        
        if "P0172" in dtc_codes or "P0175" in dtc_codes:
            bank = "1" if "P0172" in dtc_codes else "2"
            likely_causes.append(LikelyCause(
                cause=f"System too rich - Bank {bank}",
                probability="high",
                explanation="Leaking injector, fuel pressure too high, or faulty O2 sensor"
            ))
    
    # Add fuel trim analysis
    if quick_analysis:
        if quick_analysis["issues"]:
            reasoning_parts.extend(quick_analysis["issues"])
        if quick_analysis["likely_causes"]:
            for cause in quick_analysis["likely_causes"]:
                likely_causes.append(LikelyCause(
                    cause=cause,
                    probability="medium",
                    explanation="Based on fuel trim analysis"
                ))
    
    # Add recommended tests based on issues found
    if any("lean" in str(c.cause).lower() or "vacuum" in str(c.cause).lower() for c in likely_causes):
        recommended_tests.append(RecommendedTest(
            test="Smoke test intake system",
            reason="Detect vacuum leaks",
            expected_result="Smoke visible at leak location"
        ))
        recommended_tests.append(RecommendedTest(
            test="Check fuel pressure",
            reason="Rule out fuel delivery issue",
            expected_result="Should be within spec (typically 55-65 psi for port injection)"
        ))
    
    if any("misfire" in str(c.cause).lower() for c in likely_causes):
        recommended_tests.append(RecommendedTest(
            test="Swap coil to different cylinder",
            reason="Determine if misfire follows coil",
            expected_result="If misfire moves, replace coil"
        ))
        recommended_tests.append(RecommendedTest(
            test="Inspect spark plugs",
            reason="Check condition and gap",
            expected_result="Should be clean, proper gap, no damage"
        ))
    
    # Safety notes
    if request.dtcs and any(d.status == "current" for d in request.dtcs):
        safety_notes.append("Vehicle has active DTCs - may affect drivability or emissions")
    
    if request.live_pids and request.live_pids.coolant_temp and request.live_pids.coolant_temp > 105:
        safety_notes.append("Coolant temperature elevated - check for overheating before driving")
    
    # Build summary
    if likely_causes:
        summary = f"Likely issue: {likely_causes[0].cause}"
    elif request.dtcs:
        summary = f"DTCs present: {', '.join(d.code for d in request.dtcs[:3])}"
    else:
        summary = "No obvious issues detected in scan data"
    
    # Build confidence
    confidence = "low"
    if request.dtcs and quick_analysis and quick_analysis["status"] != "normal":
        confidence = "high" if quick_analysis["status"] == "critical" else "medium"
    elif request.dtcs:
        confidence = "medium"
    
    response = DiagnosisResponse(
        summary=summary,
        confidence=confidence,
        reasoning=" | ".join(reasoning_parts) if reasoning_parts else "Insufficient data for detailed analysis",
        likely_causes=likely_causes,
        recommended_tests=recommended_tests,
        safety_notes=safety_notes
    )
    
    # Collect training data from scan tool diagnosis
    try:
        from addons.training_data.chat_hook import collect_from_scan_tool
        vehicle_dict = {}
        if request.vehicle:
            vehicle_dict = {
                "year": request.vehicle.year,
                "make": request.vehicle.make,
                "model": request.vehicle.model,
                "engine": request.vehicle.engine
            }
        scan_dict = {
            "dtcs": [{"code": d.code, "status": d.status} for d in request.dtcs] if request.dtcs else [],
            "live_pids": request.live_pids.model_dump() if request.live_pids else {},
            "freeze_frame": request.freeze_frame.model_dump() if request.freeze_frame else {}
        }
        collect_from_scan_tool(
            vehicle=vehicle_dict,
            scan_data=scan_dict,
            diagnosis=response.summary + " | " + response.reasoning
        )
    except Exception as e:
        logger.debug(f"Training data collection skipped: {e}")
    
    return response


@router.post("/vin/decode", response_model=VINDecodeResponse)
async def decode_vin(
    vin: str,
    user=Depends(get_current_user)
):
    """
    Decode a VIN to get vehicle information.
    
    Uses NHTSA API for decoding.
    """
    import httpx
    
    if len(vin) != 17:
        raise HTTPException(status_code=400, detail="VIN must be 17 characters")
    
    # Use NHTSA API
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/{vin}?format=json"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"VIN decode failed: {e}")
            raise HTTPException(status_code=500, detail="Failed to decode VIN")
    
    # Parse NHTSA response
    results = {r["Variable"]: r["Value"] for r in data.get("Results", []) if r.get("Value")}
    
    year = results.get("Model Year")
    make = results.get("Make")
    model = results.get("Model")
    
    if not year or not make or not model:
        raise HTTPException(status_code=400, detail="Could not decode VIN")
    
    return VINDecodeResponse(
        vin=vin.upper(),
        year=int(year),
        make=make,
        model=model,
        engine=results.get("Engine Model") or results.get("Displacement (L)"),
        transmission=results.get("Transmission Style"),
        drive_type=results.get("Drive Type"),
        body_style=results.get("Body Class")
    )


@router.get("/pids")
async def get_supported_pids(user=Depends(get_current_user)):
    """
    Get list of OBD2 PIDs we support with descriptions.
    """
    from addons.scantool_tool.obd2_pids import PIDS, ESSENTIAL_PIDS
    
    return {
        "essential_pids": [
            {
                "pid": f"0x{pid:02X}",
                "name": PIDS[pid].name,
                "description": PIDS[pid].description,
                "units": PIDS[pid].units,
                "diagnostic_value": PIDS[pid].diagnostic_value
            }
            for pid in ESSENTIAL_PIDS if pid in PIDS
        ],
        "all_pids": [
            {
                "pid": f"0x{pid:02X}",
                "name": defn.name,
                "description": defn.description,
                "units": defn.units,
            }
            for pid, defn in sorted(PIDS.items())
        ]
    }


@router.get("/", response_class=HTMLResponse)
async def get_scan_tool_ui():
    """
    Serve the scan tool web interface.
    
    Access at /api/v1/scan/
    """
    html_path = WEB_DIR / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Scan tool UI not found")
    
    return HTMLResponse(content=html_path.read_text())
