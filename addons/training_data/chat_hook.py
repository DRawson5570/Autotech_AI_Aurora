"""
Chat Pipeline Hook for Training Data Collection

This module hooks into the Open WebUI chat pipeline to automatically
collect training examples from automotive diagnostic conversations.
"""

import re
import logging
from typing import Optional, Dict, Any

from .collector import (
    get_collector,
    VehicleContext,
    ScanToolData,
    DataCategory,
)

logger = logging.getLogger(__name__)

# Patterns to detect automotive content
DTC_PATTERN = re.compile(r'\b[PBCU][0-9]{4}\b', re.IGNORECASE)

# Known car makes for better vehicle extraction
CAR_MAKES = [
    'acura', 'alfa', 'aston', 'audi', 'bentley', 'bmw', 'buick', 'cadillac',
    'chevrolet', 'chevy', 'chrysler', 'dodge', 'ferrari', 'fiat', 'ford',
    'genesis', 'gmc', 'honda', 'hyundai', 'infiniti', 'jaguar', 'jeep',
    'kia', 'lamborghini', 'land rover', 'lexus', 'lincoln', 'maserati',
    'mazda', 'mclaren', 'mercedes', 'mini', 'mitsubishi', 'nissan',
    'porsche', 'ram', 'rivian', 'rolls', 'subaru', 'suzuki', 'tesla',
    'toyota', 'volkswagen', 'vw', 'volvo'
]

# Pattern for vehicle: 4-digit year (1990-2030) + known make + model
VEHICLE_PATTERN = re.compile(
    r'\b(19[9][0-9]|20[0-3][0-9])\s+(' + '|'.join(CAR_MAKES) + r')\s+(\w+(?:[-\s]\w+)?)',
    re.IGNORECASE
)

FUEL_TRIM_PATTERN = re.compile(
    r'(stft|ltft|short.?term|long.?term).*?([+-]?\d+\.?\d*)\s*%',
    re.IGNORECASE
)

# Keywords that indicate automotive diagnostic content
DIAGNOSTIC_KEYWORDS = [
    'diagnostic', 'dtc', 'code', 'check engine', 'mil', 'obd',
    'misfire', 'lean', 'rich', 'vacuum leak', 'fuel trim',
    'torque spec', 'fluid capacity', 'oil', 'coolant', 'transmission',
    'sensor', 'actuator', 'solenoid', 'relay', 'fuse',
    'wiring', 'connector', 'harness', 'ground', 'voltage',
    'tsb', 'recall', 'bulletin', 'procedure', 'reset',
]


def is_automotive_query(text: str) -> bool:
    """Check if text appears to be automotive-related"""
    text_lower = text.lower()
    
    # Check for DTC codes
    if DTC_PATTERN.search(text):
        return True
    
    # Check for vehicle mentions
    if VEHICLE_PATTERN.search(text):
        return True
    
    # Check for diagnostic keywords
    for keyword in DIAGNOSTIC_KEYWORDS:
        if keyword in text_lower:
            return True
    
    return False


def extract_vehicle_context(text: str) -> Optional[VehicleContext]:
    """Extract vehicle information from text"""
    match = VEHICLE_PATTERN.search(text)
    if match:
        return VehicleContext(
            year=int(match.group(1)),
            make=match.group(2),
            model=match.group(3)
        )
    return None


def extract_dtc_codes(text: str) -> list:
    """Extract DTC codes from text"""
    return DTC_PATTERN.findall(text.upper())


def extract_fuel_trims(text: str) -> Dict[str, float]:
    """Extract fuel trim values from text"""
    trims = {}
    for match in FUEL_TRIM_PATTERN.finditer(text):
        trim_type = match.group(1).lower()
        value = float(match.group(2))
        
        if 'short' in trim_type or 'stft' in trim_type:
            trims['stft1'] = value
        elif 'long' in trim_type or 'ltft' in trim_type:
            trims['ltft1'] = value
    
    return trims


def categorize_query(text: str) -> DataCategory:
    """Determine the category of an automotive query"""
    text_lower = text.lower()
    
    # Check for DTC-related queries
    if DTC_PATTERN.search(text):
        return DataCategory.DTC_DIAGNOSIS
    
    # Check for symptom descriptions
    symptom_words = ['symptom', 'problem', 'issue', 'noise', 'vibration', 
                     'smell', 'leak', 'won\'t start', 'stall', 'rough idle']
    if any(word in text_lower for word in symptom_words):
        return DataCategory.SYMPTOM_DIAGNOSIS
    
    # Check for scan data analysis
    if FUEL_TRIM_PATTERN.search(text) or 'pid' in text_lower or 'scan' in text_lower:
        return DataCategory.SCAN_DATA_ANALYSIS
    
    # Check for spec lookups
    spec_words = ['torque', 'capacity', 'specification', 'spec', 'how much']
    if any(word in text_lower for word in spec_words):
        return DataCategory.SPEC_LOOKUP
    
    # Check for procedures
    procedure_words = ['how to', 'procedure', 'steps', 'reset', 'relearn', 'calibrate']
    if any(word in text_lower for word in procedure_words):
        return DataCategory.PROCEDURE
    
    # Check for TSB lookups
    if 'tsb' in text_lower or 'bulletin' in text_lower or 'recall' in text_lower:
        return DataCategory.TSB_LOOKUP
    
    # Check for wiring
    if 'wiring' in text_lower or 'diagram' in text_lower or 'connector' in text_lower:
        return DataCategory.WIRING
    
    return DataCategory.GENERAL


def collect_from_chat(
    user_message: str,
    assistant_response: str,
    model_id: str = None,
    chat_id: str = None,
    conversation_history: list = None
) -> bool:
    """
    Collect training data from a chat exchange.
    
    Called after each assistant response to potentially collect training data.
    Captures ALL automotive conversations - filter/curate during export.
    
    Args:
        user_message: The user's message
        assistant_response: The assistant's response
        model_id: The model that generated the response
        chat_id: The chat session ID
        conversation_history: Full list of messages for vehicle context extraction
    
    Returns:
        True if data was collected, False otherwise
    """
    
    # Capture all conversations - filter/curate during export
    # If it's going through an automotive model, it's relevant
    
    # Skip very short responses (likely errors)
    if len(assistant_response) < 50:
        return False
    
    # Extract vehicle context - scan entire conversation history
    vehicle = None
    if conversation_history:
        # Build full conversation text to search for vehicle mentions
        full_text = ""
        for msg in conversation_history:
            content = msg.get("content", "")
            if isinstance(content, str):
                full_text += " " + content
        vehicle = extract_vehicle_context(full_text)
    
    # Fallback: try current exchange only
    if not vehicle:
        vehicle = extract_vehicle_context(user_message + " " + assistant_response)
    
    category = categorize_query(user_message)
    
    # Extract scan data if present
    scan_data = None
    dtcs = extract_dtc_codes(user_message)
    fuel_trims = extract_fuel_trims(user_message)
    if dtcs or fuel_trims:
        scan_data = ScanToolData(
            dtcs=[{"code": dtc, "status": "unknown"} for dtc in dtcs],
            pids=fuel_trims if fuel_trims else None
        )
    
    # Collect the example
    try:
        collector = get_collector()
        collector.collect(
            input_text=user_message,
            output_text=assistant_response,
            category=category,
            vehicle=vehicle,
            scan_data=scan_data,
            source="user_chat"
        )
        logger.info(f"Collected training example from chat [{category.value}]")
        return True
    except Exception as e:
        logger.error(f"Failed to collect training data: {e}")
        return False


def collect_from_mitchell_tool(
    query: str,
    vehicle: Dict[str, Any],
    tool_name: str,
    result: Dict[str, Any],
    formatted_response: str
) -> bool:
    """
    Collect training data from Mitchell tool usage.
    
    Called when Mitchell tool returns data to collect high-quality examples.
    
    Args:
        query: The original user query
        vehicle: Vehicle info dict
        tool_name: Which Mitchell tool was used
        result: Raw tool result
        formatted_response: The formatted response shown to user
    
    Returns:
        True if data was collected
    """
    
    try:
        collector = get_collector()
        
        # Map tool names to categories
        tool_category_map = {
            "get_dtc_info": DataCategory.DTC_DIAGNOSIS,
            "get_fluid_capacities": DataCategory.SPEC_LOOKUP,
            "get_torque_specs": DataCategory.SPEC_LOOKUP,
            "get_tsb_list": DataCategory.TSB_LOOKUP,
            "get_wiring_diagram": DataCategory.WIRING,
            "get_reset_procedure": DataCategory.PROCEDURE,
        }
        
        category = tool_category_map.get(tool_name, DataCategory.GENERAL)
        
        # Build vehicle context
        vehicle_ctx = VehicleContext(
            year=vehicle.get("year"),
            make=vehicle.get("make"),
            model=vehicle.get("model"),
            engine=vehicle.get("engine")
        )
        
        collector.collect(
            input_text=query,
            output_text=formatted_response,
            category=category,
            vehicle=vehicle_ctx,
            mitchell_data=result,
            source="mitchell_tool",
            quality_score=0.9  # Mitchell data is high quality
        )
        
        logger.info(f"Collected Mitchell training example [{tool_name}]")
        return True
        
    except Exception as e:
        logger.error(f"Failed to collect Mitchell training data: {e}")
        return False


def collect_from_scan_tool(
    vehicle: Dict[str, Any],
    scan_data: Dict[str, Any],
    diagnosis: str
) -> bool:
    """
    Collect training data from scan tool diagnosis.
    
    Args:
        vehicle: Vehicle info dict
        scan_data: Scan tool data (DTCs, PIDs)
        diagnosis: The AI-generated diagnosis
    
    Returns:
        True if data was collected
    """
    
    try:
        collector = get_collector()
        
        vehicle_ctx = VehicleContext(
            year=vehicle.get("year"),
            make=vehicle.get("make"),
            model=vehicle.get("model"),
            engine=vehicle.get("engine")
        )
        
        scan_ctx = ScanToolData(
            dtcs=scan_data.get("dtcs", []),
            pids=scan_data.get("live_pids", {}),
            freeze_frame=scan_data.get("freeze_frame", {})
        )
        
        collector.collect_scan_analysis(
            vehicle=vehicle_ctx,
            scan_data=scan_ctx,
            analysis=diagnosis
        )
        
        logger.info("Collected scan tool training example")
        return True
        
    except Exception as e:
        logger.error(f"Failed to collect scan tool training data: {e}")
        return False
