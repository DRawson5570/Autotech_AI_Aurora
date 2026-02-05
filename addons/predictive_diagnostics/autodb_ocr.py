"""
AutoDB OCR Module - Extract specs from Operation CHARM images.

AutoDB stores specifications as images (scanned service manual pages).
This module:
1. Fetches spec pages from AutoDB
2. Extracts image URLs
3. OCRs images using Tesseract
4. Parses extracted text for specific values

Usage:
    from autodb_ocr import AutoDBOCR
    
    ocr = AutoDBOCR()
    specs = await ocr.get_cooling_specs(2010, "Toyota", "Camry", "L4-2.5L (2AR-FE)")
    # Returns: {"thermostat_opens_f": 176, "thermostat_opens_max_f": 183, ...}
"""

from __future__ import annotations

import re
import io
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

# Lazy imports for OCR
pytesseract = None
Image = None

logger = logging.getLogger(__name__)


def _ensure_ocr_imports():
    """Lazy import OCR dependencies."""
    global pytesseract, Image
    if pytesseract is None:
        import pytesseract as _pytesseract
        from PIL import Image as _Image
        pytesseract = _pytesseract
        Image = _Image


# =============================================================================
# URL BUILDING
# =============================================================================

AUTODB_BASE = "http://automotive.aurora-sentient.net/autodb"

# Known spec paths in AutoDB
SPEC_PATHS = {
    "cooling_temp": "Repair%20and%20Diagnosis/Specifications/Pressure%2C%20Vacuum%20and%20Temperature%20Specifications/Cooling%20System/",
    "cooling_electrical": "Repair%20and%20Diagnosis/Specifications/Electrical%20Specifications/Cooling%20System/",
    "fuel_pressure": "Repair%20and%20Diagnosis/Specifications/Pressure%2C%20Vacuum%20and%20Temperature%20Specifications/Fuel%20Delivery%20and%20Air%20Induction/Fuel%20Pressure/",
    "fuel_electrical": "Repair%20and%20Diagnosis/Specifications/Electrical%20Specifications/Fuel%20Delivery%20and%20Air%20Induction/Fuel/",
    "engine_specs": "Repair%20and%20Diagnosis/Specifications/Mechanical%20Specifications/Engine/System%20Specifications/Service%20Data/",
    "ignition_specs": "Repair%20and%20Diagnosis/Specifications/Electrical%20Specifications/Ignition%20System/",
    "ignition_mech": "Repair%20and%20Diagnosis/Specifications/Mechanical%20Specifications/Ignition%20System/System%20Specifications/Service%20Data/",
    "charging_specs": "Repair%20and%20Diagnosis/Specifications/Electrical%20Specifications/Charging%20System/",
    "oil_pressure": "Repair%20and%20Diagnosis/Specifications/Pressure%2C%20Vacuum%20and%20Temperature%20Specifications/Engine/Engine%20Lubrication/Engine%20Oil%20Pressure/",
    "computers": "Repair%20and%20Diagnosis/Specifications/Electrical%20Specifications/Computers%20and%20Control%20Systems/",
}


def build_vehicle_url(year: int, make: str, model: str, engine: str = None) -> str:
    """Build AutoDB URL for a vehicle."""
    # AutoDB format: /autodb/Make/Year/Model Engine/
    # Example: /autodb/Toyota/2010/Camry L4-2.5L (2AR-FE)/
    make_encoded = quote(make)
    
    if engine:
        model_engine = f"{model} {engine}"
    else:
        model_engine = model
    model_encoded = quote(model_engine)
    
    return f"{AUTODB_BASE}/{make_encoded}/{year}/{model_encoded}/"


def build_spec_url(base_vehicle_url: str, spec_type: str) -> str:
    """Build URL for a specific spec page."""
    if spec_type not in SPEC_PATHS:
        raise ValueError(f"Unknown spec type: {spec_type}")
    return urljoin(base_vehicle_url, SPEC_PATHS[spec_type])


# =============================================================================
# IMAGE EXTRACTION
# =============================================================================

def extract_image_urls(html: str, base_url: str) -> List[str]:
    """Extract all image URLs from an AutoDB spec page."""
    soup = BeautifulSoup(html, "html.parser")
    images = []
    
    for img in soup.select("img.big-img"):
        src = img.get("src")
        if src:
            # Make absolute URL
            if src.startswith("/"):
                images.append(f"http://automotive.aurora-sentient.net{src}")
            elif not src.startswith("http"):
                images.append(urljoin(base_url, src))
            else:
                images.append(src)
    
    return images


# =============================================================================
# OCR PROCESSING
# =============================================================================

def ocr_image(image_url: str, session: requests.Session = None) -> str:
    """Download and OCR a single image."""
    _ensure_ocr_imports()
    
    sess = session or requests.Session()
    
    try:
        response = sess.get(image_url, timeout=30)
        response.raise_for_status()
        
        # Load image
        img = Image.open(io.BytesIO(response.content))
        
        # Convert to RGB if needed (some images are 1-bit)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # OCR with Tesseract
        text = pytesseract.image_to_string(img)
        
        return text.strip()
        
    except Exception as e:
        logger.warning(f"OCR failed for {image_url}: {e}")
        return ""


def ocr_spec_page(page_url: str, session: requests.Session = None) -> List[str]:
    """Fetch a spec page and OCR all images on it."""
    sess = session or requests.Session()
    
    try:
        response = sess.get(page_url, timeout=30)
        response.raise_for_status()
        
        image_urls = extract_image_urls(response.text, page_url)
        logger.info(f"Found {len(image_urls)} images on {page_url}")
        
        texts = []
        for img_url in image_urls:
            text = ocr_image(img_url, sess)
            if text:
                texts.append(text)
                logger.debug(f"OCR'd: {text[:100]}...")
        
        return texts
        
    except Exception as e:
        logger.warning(f"Failed to fetch spec page {page_url}: {e}")
        return []


# =============================================================================
# SPEC PARSING
# =============================================================================

@dataclass
class ExtractedSpecs:
    """Specs extracted from OCR'd text."""
    # Cooling
    thermostat_opens_f: Optional[float] = None
    thermostat_opens_max_f: Optional[float] = None
    thermostat_full_open_f: Optional[float] = None
    radiator_cap_psi: Optional[float] = None
    
    # Fuel
    fuel_pressure_kpa: Optional[float] = None
    fuel_pressure_psi: Optional[float] = None
    fuel_pressure_min_kpa: Optional[float] = None
    fuel_pressure_max_kpa: Optional[float] = None
    
    # Engine
    idle_rpm: Optional[float] = None
    idle_rpm_min: Optional[float] = None
    idle_rpm_max: Optional[float] = None
    compression_kpa: Optional[float] = None
    compression_psi: Optional[float] = None
    
    # Electrical
    charging_voltage_min: Optional[float] = None
    charging_voltage_max: Optional[float] = None
    
    # Oil
    oil_pressure_idle_kpa: Optional[float] = None
    oil_pressure_3000rpm_kpa: Optional[float] = None
    
    # Raw texts for debugging
    raw_texts: List[str] = field(default_factory=list)
    source: str = "autodb_ocr"


def parse_thermostat_specs(text: str) -> Dict[str, float]:
    """Parse thermostat opening temperature from OCR text."""
    specs = {}
    
    # Pattern: "80 to 84°C (176 to 183°F)"
    match = re.search(r'(\d+)\s*to\s*(\d+)\s*°?\s*[CF]\s*\((\d+)\s*to\s*(\d+)\s*°?\s*F\)', text, re.IGNORECASE)
    if match:
        specs["thermostat_opens_f"] = float(match.group(3))
        specs["thermostat_opens_max_f"] = float(match.group(4))
    
    # Pattern: "at 95°C (203°F)" for full open
    match = re.search(r'at\s*(\d+)\s*°?\s*C\s*\((\d+)\s*°?\s*F\)', text, re.IGNORECASE)
    if match:
        specs["thermostat_full_open_f"] = float(match.group(2))
    
    # Alternative: just Fahrenheit "opens at 180°F"
    if not specs:
        match = re.search(r'open[s]?\s+(?:at\s+)?(\d+)\s*(?:to|-)\s*(\d+)\s*°?\s*F', text, re.IGNORECASE)
        if match:
            specs["thermostat_opens_f"] = float(match.group(1))
            specs["thermostat_opens_max_f"] = float(match.group(2))
    
    return specs


def parse_radiator_cap_specs(text: str) -> Dict[str, float]:
    """Parse radiator cap pressure from OCR text."""
    specs = {}
    
    # Only parse if this looks like radiator cap section
    if not re.search(r'radiator|cap|reservoir', text, re.IGNORECASE):
        return specs
    
    # Pattern: "10.7 to 14.9 psi" or "10.7 ta 14.9 psi" (OCR error)
    # Radiator cap is typically 10-20 psi
    match = re.search(r'(\d+\.?\d*)\s*(?:to|ta|-)\s*(\d+\.?\d*)\s*psi', text, re.IGNORECASE)
    if match:
        low = float(match.group(1))
        high = float(match.group(2))
        # Radiator cap pressure is 8-20 psi range
        if 5 <= low <= 20 and 10 <= high <= 25:
            specs["radiator_cap_psi"] = low
    
    # Pattern: kPa "74 to 103 kPa" - radiator cap is typically 50-150 kPa
    match = re.search(r'(\d+\.?\d*)\s*(?:to|ta|-)\s*(\d+\.?\d*)\s*kPa', text, re.IGNORECASE)
    if match:
        low = float(match.group(1))
        high = float(match.group(2))
        if 50 <= low <= 150:
            specs["radiator_cap_kpa"] = low
    
    return specs


def parse_fuel_pressure_specs(text: str) -> Dict[str, float]:
    """Parse fuel pressure specs from OCR text."""
    specs = {}
    
    # Only parse if this looks like a fuel pressure section
    if not re.search(r'fuel\s*pressure', text, re.IGNORECASE):
        return specs
    
    # Pattern: "304 to 343 kPa" - fuel pressure is typically 200-400 kPa
    match = re.search(r'(\d{2,3})\s*(?:to|-)\s*(\d{2,3})\s*kPa', text, re.IGNORECASE)
    if match:
        low = float(match.group(1))
        high = float(match.group(2))
        # Fuel pressure is typically 200-500 kPa, not radiator cap range (94-122)
        if low > 150:
            specs["fuel_pressure_min_kpa"] = low
            specs["fuel_pressure_max_kpa"] = high
            specs["fuel_pressure_kpa"] = (low + high) / 2
    
    # Pattern: "44 to 50 psi" - fuel pressure in psi
    match = re.search(r'(\d+)\s*(?:to|-)\s*(\d+)\s*psi', text, re.IGNORECASE)
    if match:
        low = float(match.group(1))
        high = float(match.group(2))
        # Fuel pressure is typically 30-60 psi
        if low > 25:
            specs["fuel_pressure_psi"] = (low + high) / 2
    
    return specs


def parse_idle_rpm_specs(text: str) -> Dict[str, float]:
    """Parse idle RPM specs from OCR text."""
    specs = {}
    
    # Pattern: "650 to 750 rpm" or "650 to 750 rom" (OCR error)
    match = re.search(r'(\d{3,4})\s*(?:to|-)\s*(\d{3,4})\s*r[op]m', text, re.IGNORECASE)
    if match:
        specs["idle_rpm_min"] = float(match.group(1))
        specs["idle_rpm_max"] = float(match.group(2))
        specs["idle_rpm"] = (specs["idle_rpm_min"] + specs["idle_rpm_max"]) / 2
    
    # Pattern: "700 ± 50 rpm"
    match = re.search(r'(\d{3,4})\s*[±+-]\s*(\d+)\s*r[op]m', text, re.IGNORECASE)
    if match:
        center = float(match.group(1))
        tolerance = float(match.group(2))
        if "idle_rpm" not in specs:
            specs["idle_rpm"] = center
            specs["idle_rpm_min"] = center - tolerance
            specs["idle_rpm_max"] = center + tolerance
    
    return specs


def parse_charging_voltage_specs(text: str) -> Dict[str, float]:
    """Parse charging/alternator voltage specs from OCR text."""
    specs = {}
    
    # Find all voltage patterns in the text
    all_matches = re.findall(r'(\d+\.?\d*)\s*(?:to|-)\s*(\d+\.?\d*)\s*V(?:olts?)?', text, re.IGNORECASE)
    
    for match in all_matches:
        low = float(match[0])
        high = float(match[1])
        # Charging voltage is typically 13.2-14.8V
        # Battery static voltage is 12.6-12.8V
        if 13.0 <= low <= 14.0 and 14.0 <= high <= 15.0:
            specs["charging_voltage_min"] = low
            specs["charging_voltage_max"] = high
            break  # Use first match in charging range
    
    return specs


def parse_oil_pressure_specs(text: str) -> Dict[str, float]:
    """Parse oil pressure specs from OCR text."""
    specs = {}
    
    # Pattern: "at idle" followed by pressure
    match = re.search(r'idle[^0-9]*(\d+)\s*(?:to|-)\s*(\d+)\s*kPa', text, re.IGNORECASE)
    if match:
        specs["oil_pressure_idle_kpa"] = (float(match.group(1)) + float(match.group(2))) / 2
    
    # Pattern: "at 3000 rpm" or "at 3,000 rpm"
    match = re.search(r'3[,.]?000\s*rpm[^0-9]*(\d+)\s*(?:to|-)\s*(\d+)\s*kPa', text, re.IGNORECASE)
    if match:
        specs["oil_pressure_3000rpm_kpa"] = (float(match.group(1)) + float(match.group(2))) / 2
    
    return specs


def parse_compression_specs(text: str) -> Dict[str, float]:
    """Parse compression test specs from OCR text."""
    specs = {}
    
    # Pattern: "1450 kPa" or "1,450 kPa" - compression is typically 1000-1500 kPa
    match = re.search(r'(?:standard|compression)[^0-9]*(\d+[,.]?\d*)\s*kPa', text, re.IGNORECASE)
    if match:
        value = float(match.group(1).replace(",", ""))
        if value > 500:  # Compression is > 500 kPa
            specs["compression_kpa"] = value
    
    # Pattern: "210 psi" - compression is typically 100-220 psi
    match = re.search(r'(?:standard|compression)[^0-9]*(\d+)\s*psi', text, re.IGNORECASE)
    if match:
        value = float(match.group(1))
        if value > 80:  # Compression is > 80 psi
            specs["compression_psi"] = value
    
    return specs


# =============================================================================
# MAIN OCR CLASS
# =============================================================================

class AutoDBOCR:
    """OCR-based spec extractor for AutoDB."""
    
    def __init__(self, base_url: str = AUTODB_BASE):
        self.base_url = base_url
        self.session = requests.Session()
        self._cache: Dict[str, ExtractedSpecs] = {}
    
    def _cache_key(self, year: int, make: str, model: str, engine: str = None) -> str:
        return f"{year}_{make}_{model}_{engine or 'default'}"
    
    def get_all_specs(
        self,
        year: int,
        make: str,
        model: str,
        engine: str = None,
    ) -> ExtractedSpecs:
        """
        Get all available specs for a vehicle via OCR.
        
        This fetches multiple spec pages and extracts values from images.
        Results are cached per vehicle.
        """
        cache_key = self._cache_key(year, make, model, engine)
        if cache_key in self._cache:
            logger.info(f"Using cached specs for {year} {make} {model}")
            return self._cache[cache_key]
        
        vehicle_url = build_vehicle_url(year, make, model, engine)
        specs = ExtractedSpecs()
        all_texts = []
        
        # Fetch and OCR each spec page
        spec_types_to_fetch = [
            "cooling_electrical",  # Has thermostat, fan, radiator cap
            "fuel_pressure",
            "fuel_electrical",     # Has fuel pressure too sometimes
            "charging_specs",
            "oil_pressure",
            "engine_specs",
            "ignition_mech",       # Often has idle RPM, compression
            "computers",           # Sometimes has idle specs
        ]
        
        for spec_type in spec_types_to_fetch:
            try:
                spec_url = build_spec_url(vehicle_url, spec_type)
                logger.info(f"Fetching {spec_type} from {spec_url}")
                
                texts = ocr_spec_page(spec_url, self.session)
                all_texts.extend(texts)
                
                # Parse each text block
                for text in texts:
                    # Try all parsers
                    for parsed in [
                        parse_thermostat_specs(text),
                        parse_radiator_cap_specs(text),
                        parse_fuel_pressure_specs(text),
                        parse_idle_rpm_specs(text),
                        parse_charging_voltage_specs(text),
                        parse_oil_pressure_specs(text),
                        parse_compression_specs(text),
                    ]:
                        for key, value in parsed.items():
                            if hasattr(specs, key) and getattr(specs, key) is None:
                                setattr(specs, key, value)
                                logger.info(f"Extracted {key} = {value}")
            
            except Exception as e:
                logger.warning(f"Failed to get {spec_type}: {e}")
        
        specs.raw_texts = all_texts
        self._cache[cache_key] = specs
        
        return specs
    
    def get_cooling_specs(
        self,
        year: int,
        make: str,
        model: str,
        engine: str = None,
    ) -> Dict[str, Any]:
        """Get just cooling system specs."""
        vehicle_url = build_vehicle_url(year, make, model, engine)
        spec_url = build_spec_url(vehicle_url, "cooling_electrical")
        
        texts = ocr_spec_page(spec_url, self.session)
        
        result = {}
        for text in texts:
            result.update(parse_thermostat_specs(text))
            result.update(parse_radiator_cap_specs(text))
        
        return result
    
    def get_fuel_specs(
        self,
        year: int,
        make: str,
        model: str,
        engine: str = None,
    ) -> Dict[str, Any]:
        """Get just fuel system specs."""
        vehicle_url = build_vehicle_url(year, make, model, engine)
        spec_url = build_spec_url(vehicle_url, "fuel_pressure")
        
        texts = ocr_spec_page(spec_url, self.session)
        
        result = {}
        for text in texts:
            result.update(parse_fuel_pressure_specs(text))
        
        return result


# =============================================================================
# INTEGRATION WITH PID_SPECS
# =============================================================================

async def query_autodb_specs_via_ocr(
    year: int,
    make: str,
    model: str,
    engine: str = None,
) -> Dict[str, Any]:
    """
    Query AutoDB via OCR and return specs in format compatible with pid_specs.py.
    
    This is the function to call from pid_specs._query_autodb_specs()
    """
    ocr = AutoDBOCR()
    extracted = ocr.get_all_specs(year, make, model, engine)
    
    # Map to pid_specs format
    result = {}
    
    if extracted.thermostat_opens_f:
        result["operating_temp_min"] = extracted.thermostat_opens_f
    if extracted.thermostat_opens_max_f:
        result["operating_temp_max"] = extracted.thermostat_opens_max_f + 20  # Add headroom above thermostat
    if extracted.thermostat_opens_f:
        result["thermostat_opens_at"] = extracted.thermostat_opens_f
    
    if extracted.fuel_pressure_kpa:
        result["fuel_pressure_spec"] = extracted.fuel_pressure_kpa
        result["fuel_pressure_tolerance"] = 10  # ±10%
    
    if extracted.idle_rpm:
        result["idle_rpm_spec"] = extracted.idle_rpm
        if extracted.idle_rpm_min and extracted.idle_rpm_max:
            result["idle_rpm_tolerance"] = (extracted.idle_rpm_max - extracted.idle_rpm_min) / 2
    
    if extracted.charging_voltage_min:
        result["charging_voltage_min"] = extracted.charging_voltage_min
    if extracted.charging_voltage_max:
        result["charging_voltage_max"] = extracted.charging_voltage_max
    
    return result


# =============================================================================
# CLI FOR TESTING
# =============================================================================

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    # Default test vehicle
    year = 2010
    make = "Toyota"
    model = "Camry"
    engine = "L4-2.5L (2AR-FE)"
    
    if len(sys.argv) >= 4:
        year = int(sys.argv[1])
        make = sys.argv[2]
        model = sys.argv[3]
        engine = sys.argv[4] if len(sys.argv) > 4 else None
    
    print(f"\n=== OCR Specs for {year} {make} {model} {engine or ''} ===\n")
    
    ocr = AutoDBOCR()
    specs = ocr.get_all_specs(year, make, model, engine)
    
    print("Extracted Specs:")
    for field_name in [
        "thermostat_opens_f", "thermostat_opens_max_f", "thermostat_full_open_f",
        "radiator_cap_psi", "fuel_pressure_kpa", "fuel_pressure_psi",
        "idle_rpm", "idle_rpm_min", "idle_rpm_max",
        "charging_voltage_min", "charging_voltage_max",
        "oil_pressure_idle_kpa", "oil_pressure_3000rpm_kpa",
        "compression_kpa", "compression_psi",
    ]:
        value = getattr(specs, field_name, None)
        if value is not None:
            print(f"  {field_name}: {value}")
    
    print("\n--- Raw OCR Texts ---")
    for i, text in enumerate(specs.raw_texts):
        print(f"\n[Image {i+1}]")
        print(text[:500] + "..." if len(text) > 500 else text)
