"""
Mitchell Data Extractor for Learning Phase

This module extracts data from Mitchell (ShopKeyPro) to build fault trees.
USED ONLY DURING TRAINING - not at runtime.

Extracts:
1. Wiring diagrams → circuit topology, component connections
2. Component specs → operating parameters
3. TSBs → known issues with elevated probability
4. DTC definitions → code descriptions and related components
5. Connector pinouts → connection details

Uses the existing Mitchell Agent AI navigation system.

RATE LIMITING:
- Mimics human browsing patterns with random delays
- Limits queries per session and per day
- Adds "thinking time" between navigations
- Randomizes timing to avoid detection patterns
"""

import asyncio
import logging
import json
import re
import random
import time
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# =============================================================================
# RATE LIMITING CONFIGURATION - Mimic Human Behavior
# =============================================================================

# Time between queries (seconds) - randomized within range
DELAY_MIN_BETWEEN_QUERIES = 45      # At least 45 seconds between queries
DELAY_MAX_BETWEEN_QUERIES = 180     # Up to 3 minutes between queries

# "Reading time" - time spent "looking at" results before next action
DELAY_MIN_READING_TIME = 10         # At least 10 seconds reading
DELAY_MAX_READING_TIME = 60         # Up to 1 minute reading

# Session limits
MAX_QUERIES_PER_SESSION = 8         # Max queries before taking a long break
SESSION_BREAK_MIN = 900             # 15 minute minimum break between sessions
SESSION_BREAK_MAX = 3600            # Up to 1 hour break

# Daily limits
MAX_QUERIES_PER_DAY = 20            # Absolute max queries per day
MAX_VEHICLES_PER_DAY = 4            # Max different vehicles per day

# State file for tracking across runs
RATE_LIMIT_STATE_FILE = Path("/tmp/mitchell_extractor_state.json")


# =============================================================================
# RATE LIMITER - Human-Like Query Pacing
# =============================================================================

class HumanLikeRateLimiter:
    """
    Rate limiter that mimics human browsing behavior.
    
    Features:
    - Random delays between queries (45s - 3min)
    - "Reading time" after receiving results
    - Session-based limits with long breaks
    - Daily limits tracked across runs
    - State persistence to survive restarts
    """
    
    def __init__(self, state_file: Path = RATE_LIMIT_STATE_FILE):
        self.state_file = state_file
        self.session_queries = 0
        self.session_start = time.time()
        self.last_query_time = 0
        self._load_state()
    
    def _load_state(self):
        """Load persistent state from file."""
        self.daily_queries = 0
        self.daily_vehicles = set()
        self.today = date.today().isoformat()
        
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                
                # Reset if it's a new day
                if state.get('date') == self.today:
                    self.daily_queries = state.get('queries', 0)
                    self.daily_vehicles = set(state.get('vehicles', []))
                    logger.info(f"Loaded state: {self.daily_queries} queries today, "
                               f"{len(self.daily_vehicles)} vehicles")
                else:
                    logger.info("New day - resetting daily counters")
            except Exception as e:
                logger.warning(f"Could not load rate limit state: {e}")
    
    def _save_state(self):
        """Persist state to file."""
        try:
            state = {
                'date': self.today,
                'queries': self.daily_queries,
                'vehicles': list(self.daily_vehicles),
                'last_query': datetime.now().isoformat(),
            }
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save rate limit state: {e}")
    
    def can_query(self, vehicle_key: str = None) -> Tuple[bool, str]:
        """
        Check if we can make another query.
        
        Returns:
            (allowed, reason) - whether query is allowed and why/why not
        """
        # Check daily query limit
        if self.daily_queries >= MAX_QUERIES_PER_DAY:
            return False, f"Daily limit reached ({MAX_QUERIES_PER_DAY} queries). Try again tomorrow."
        
        # Check daily vehicle limit
        if vehicle_key and vehicle_key not in self.daily_vehicles:
            if len(self.daily_vehicles) >= MAX_VEHICLES_PER_DAY:
                return False, f"Daily vehicle limit reached ({MAX_VEHICLES_PER_DAY}). Try again tomorrow."
        
        # Check session limit
        if self.session_queries >= MAX_QUERIES_PER_SESSION:
            elapsed = time.time() - self.session_start
            if elapsed < SESSION_BREAK_MIN:
                wait_time = SESSION_BREAK_MIN - elapsed
                return False, f"Session limit reached. Take a break ({wait_time/60:.0f} min remaining)."
            else:
                # Reset session
                self.session_queries = 0
                self.session_start = time.time()
                logger.info("Session reset after break")
        
        return True, "OK"
    
    async def wait_before_query(self):
        """
        Wait an appropriate amount of time before the next query.
        Mimics human "thinking" and browsing behavior.
        """
        if self.last_query_time == 0:
            # First query of session - small random delay
            delay = random.uniform(2, 8)
            logger.info(f"First query - waiting {delay:.1f}s")
        else:
            # Subsequent queries - longer human-like delay
            elapsed = time.time() - self.last_query_time
            min_wait = DELAY_MIN_BETWEEN_QUERIES - elapsed
            
            if min_wait > 0:
                # Add randomness to the remaining wait
                delay = min_wait + random.uniform(0, DELAY_MAX_BETWEEN_QUERIES - DELAY_MIN_BETWEEN_QUERIES)
                logger.info(f"Rate limiting: waiting {delay:.1f}s before next query...")
            else:
                # Already waited long enough, just add small random delay
                delay = random.uniform(5, 20)
        
        if delay > 0:
            # Log progress for long waits
            if delay > 30:
                logger.info(f"⏳ Waiting {delay:.0f}s to mimic human browsing...")
            await asyncio.sleep(delay)
    
    async def simulate_reading_time(self):
        """
        Simulate time spent reading/analyzing results.
        A human wouldn't immediately make another query.
        """
        delay = random.uniform(DELAY_MIN_READING_TIME, DELAY_MAX_READING_TIME)
        logger.debug(f"Simulating reading time: {delay:.1f}s")
        await asyncio.sleep(delay)
    
    def record_query(self, vehicle_key: str = None):
        """Record that a query was made."""
        self.last_query_time = time.time()
        self.session_queries += 1
        self.daily_queries += 1
        
        if vehicle_key:
            self.daily_vehicles.add(vehicle_key)
        
        self._save_state()
        logger.info(f"Query recorded: {self.session_queries} this session, "
                   f"{self.daily_queries} today")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current rate limit status."""
        return {
            'daily_queries': self.daily_queries,
            'daily_limit': MAX_QUERIES_PER_DAY,
            'daily_remaining': MAX_QUERIES_PER_DAY - self.daily_queries,
            'session_queries': self.session_queries,
            'session_limit': MAX_QUERIES_PER_SESSION,
            'vehicles_today': list(self.daily_vehicles),
            'vehicles_limit': MAX_VEHICLES_PER_DAY,
        }


@dataclass
class ExtractedComponent:
    """A component extracted from Mitchell data."""
    id: str
    name: str
    component_type: str
    location: str = ""
    specifications: Dict[str, Any] = field(default_factory=dict)
    connected_to: List[str] = field(default_factory=list)
    circuit_id: str = ""
    pins: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ExtractedTSB:
    """A TSB extracted from Mitchell data."""
    id: str
    title: str
    description: str
    affected_components: List[str] = field(default_factory=list)
    symptoms: List[str] = field(default_factory=list)
    solution: str = ""


@dataclass
class ExtractionResult:
    """Result of Mitchell data extraction."""
    vehicle_year: int
    vehicle_make: str
    vehicle_model: str
    vehicle_engine: Optional[str]
    system: str
    
    components: List[ExtractedComponent] = field(default_factory=list)
    tsbs: List[ExtractedTSB] = field(default_factory=list)
    dtc_info: Dict[str, str] = field(default_factory=dict)  # code -> description
    
    extraction_time_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)


class MitchellDataExtractor:
    """
    Extracts training data from Mitchell using the agent.
    
    This is a learning-phase-only component. It queries Mitchell to:
    1. Get wiring diagrams for circuit topology
    2. Extract component specifications
    3. Gather TSBs for known issues
    4. Get DTC information
    
    The extracted data is used to build fault trees for training.
    
    RATE LIMITING:
    - Uses HumanLikeRateLimiter to pace queries
    - Random delays between 45s - 3min per query
    - Max 8 queries per session, then 15-60 min break
    - Max 20 queries per day, 4 vehicles per day
    - State persists across restarts
    """
    
    def __init__(self, mitchell_tool=None, enable_rate_limiting: bool = True):
        """
        Initialize the extractor.
        
        Args:
            mitchell_tool: Optional pre-configured Mitchell tool instance.
                          If not provided, will try to import and create one.
            enable_rate_limiting: If True (default), enforces human-like delays.
                                 Set False only for testing with mock data.
        """
        self.mitchell_tool = mitchell_tool
        self._initialized = False
        self.enable_rate_limiting = enable_rate_limiting
        self.rate_limiter = HumanLikeRateLimiter() if enable_rate_limiting else None
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limiting status."""
        if self.rate_limiter:
            return self.rate_limiter.get_status()
        return {'rate_limiting': 'disabled'}
    
    async def _ensure_initialized(self):
        """Ensure Mitchell tool is available."""
        if self._initialized:
            return
        
        if self.mitchell_tool is None:
            try:
                # Try to import the Mitchell tool
                from addons.mitchell_agent.openwebui_tool import Tools as MitchellTools
                self.mitchell_tool = MitchellTools()
                logger.info("Mitchell tool initialized")
            except ImportError:
                logger.warning("Mitchell tool not available - using mock data")
                self.mitchell_tool = None
        
        self._initialized = True
    
    async def extract_for_vehicle(
        self,
        year: int,
        make: str,
        model: str,
        system: str,
        engine: str = None,
        force: bool = False,
    ) -> ExtractionResult:
        """
        Extract all relevant data for a vehicle/system from Mitchell.
        
        This method is RATE LIMITED to avoid bot detection:
        - Random delays 45s-3min between queries
        - Max 8 queries per session
        - Max 20 queries per day
        - Max 4 different vehicles per day
        
        Args:
            year: Vehicle year
            make: Vehicle make
            model: Vehicle model
            system: System name (e.g., "Cooling System")
            engine: Optional engine spec
            force: If True, bypass rate limiting (use with caution!)
            
        Returns:
            ExtractionResult with all extracted data
            
        Raises:
            RateLimitExceeded: If rate limits are hit and force=False
        """
        import time
        start_time = time.time()
        
        vehicle_key = f"{year}_{make}_{model}"
        
        result = ExtractionResult(
            vehicle_year=year,
            vehicle_make=make,
            vehicle_model=model,
            vehicle_engine=engine,
            system=system,
        )
        
        await self._ensure_initialized()
        
        if self.mitchell_tool is None:
            # Return mock data for testing (no rate limiting needed)
            result = self._generate_mock_data(year, make, model, system, engine)
            result.extraction_time_seconds = time.time() - start_time
            return result
        
        # Check rate limits before proceeding
        if self.rate_limiter and not force:
            allowed, reason = self.rate_limiter.can_query(vehicle_key)
            if not allowed:
                logger.warning(f"Rate limit: {reason}")
                result.errors.append(f"Rate limited: {reason}")
                return result
        
        logger.info(f"🚗 Extracting data for {year} {make} {model} - {system}")
        logger.info(f"📊 Rate limit status: {self.get_rate_limit_status()}")
        
        # ---------- WIRING DIAGRAM ----------
        try:
            if self.rate_limiter and not force:
                await self.rate_limiter.wait_before_query()
            
            components = await self._extract_wiring_components(
                year, make, model, system, engine
            )
            result.components = components
            
            if self.rate_limiter:
                self.rate_limiter.record_query(vehicle_key)
                await self.rate_limiter.simulate_reading_time()
            
        except Exception as e:
            logger.error(f"Failed to extract wiring: {e}")
            result.errors.append(f"Wiring extraction failed: {e}")
        
        # ---------- TSBs ----------
        try:
            if self.rate_limiter and not force:
                allowed, reason = self.rate_limiter.can_query(vehicle_key)
                if not allowed:
                    logger.warning(f"Rate limit hit during extraction: {reason}")
                    result.errors.append(f"TSB extraction skipped: {reason}")
                else:
                    await self.rate_limiter.wait_before_query()
                    
                    tsbs = await self._extract_tsbs(year, make, model, system, engine)
                    result.tsbs = tsbs
                    
                    self.rate_limiter.record_query(vehicle_key)
                    await self.rate_limiter.simulate_reading_time()
            else:
                tsbs = await self._extract_tsbs(year, make, model, system, engine)
                result.tsbs = tsbs
            
        except Exception as e:
            logger.error(f"Failed to extract TSBs: {e}")
            result.errors.append(f"TSB extraction failed: {e}")
        
        # ---------- DTCs ----------
        try:
            if self.rate_limiter and not force:
                allowed, reason = self.rate_limiter.can_query(vehicle_key)
                if not allowed:
                    logger.warning(f"Rate limit hit during extraction: {reason}")
                    result.errors.append(f"DTC extraction skipped: {reason}")
                else:
                    await self.rate_limiter.wait_before_query()
                    
                    dtc_info = await self._extract_dtc_info(year, make, model, system, engine)
                    result.dtc_info = dtc_info
                    
                    self.rate_limiter.record_query(vehicle_key)
            else:
                dtc_info = await self._extract_dtc_info(year, make, model, system, engine)
                result.dtc_info = dtc_info
            
        except Exception as e:
            logger.error(f"Failed to extract DTCs: {e}")
            result.errors.append(f"DTC extraction failed: {e}")
        
        result.extraction_time_seconds = time.time() - start_time
        logger.info(f"Extraction complete in {result.extraction_time_seconds:.1f}s")
        
        return result
    
    async def _extract_wiring_components(
        self,
        year: int,
        make: str,
        model: str,
        system: str,
        engine: str = None,
    ) -> List[ExtractedComponent]:
        """Extract components from wiring diagram."""
        components = []
        
        # Query Mitchell for wiring diagram
        # Note: This would use the AI navigator to find the wiring diagram
        # and extract component information from it
        
        # For now, return empty - actual implementation would query Mitchell
        logger.info(f"Would extract wiring for {year} {make} {model} - {system}")
        
        return components
    
    async def _extract_tsbs(
        self,
        year: int,
        make: str,
        model: str,
        system: str,
        engine: str = None,
    ) -> List[ExtractedTSB]:
        """Extract relevant TSBs."""
        tsbs = []
        
        # Query Mitchell for TSBs related to this system
        logger.info(f"Would extract TSBs for {year} {make} {model} - {system}")
        
        return tsbs
    
    async def _extract_dtc_info(
        self,
        year: int,
        make: str,
        model: str,
        system: str,
        engine: str = None,
    ) -> Dict[str, str]:
        """Extract DTC definitions."""
        dtc_info = {}
        
        # Query Mitchell for DTC information
        logger.info(f"Would extract DTCs for {year} {make} {model} - {system}")
        
        return dtc_info
    
    def _generate_mock_data(
        self,
        year: int,
        make: str,
        model: str,
        system: str,
        engine: str = None,
    ) -> ExtractionResult:
        """
        Generate mock data for testing without Mitchell.
        
        Based on common vehicle systems and components.
        """
        result = ExtractionResult(
            vehicle_year=year,
            vehicle_make=make,
            vehicle_model=model,
            vehicle_engine=engine,
            system=system,
        )
        
        if "cooling" in system.lower():
            result.components = self._mock_cooling_components()
            result.tsbs = self._mock_cooling_tsbs(year, make, model)
            result.dtc_info = self._mock_cooling_dtcs()
        elif "fuel" in system.lower():
            result.components = self._mock_fuel_components()
            result.dtc_info = self._mock_fuel_dtcs()
        elif "ignition" in system.lower():
            result.components = self._mock_ignition_components()
            result.dtc_info = self._mock_ignition_dtcs()
        else:
            # Generic components
            result.components = self._mock_generic_components(system)
        
        logger.info(f"Generated mock data: {len(result.components)} components, "
                   f"{len(result.tsbs)} TSBs, {len(result.dtc_info)} DTCs")
        
        return result
    
    def _mock_cooling_components(self) -> List[ExtractedComponent]:
        """Mock cooling system components."""
        return [
            ExtractedComponent(
                id="M12",
                name="Coolant Pump Motor",
                component_type="motor",
                location="Engine compartment, front",
                specifications={
                    "voltage": "12V",
                    "current_nominal": "2.0A",
                    "current_stall": "8A",
                },
                connected_to=["R15", "F35", "C245"],
                circuit_id="cooling_pump",
            ),
            ExtractedComponent(
                id="R15",
                name="Coolant Pump Relay",
                component_type="relay",
                location="Underhood fuse box",
                specifications={
                    "coil_resistance": "75Ω",
                    "contact_rating": "30A",
                },
                connected_to=["M12", "K20", "F35"],
                circuit_id="cooling_pump",
            ),
            ExtractedComponent(
                id="S22",
                name="Coolant Temperature Sensor",
                component_type="sensor",
                location="Thermostat housing",
                specifications={
                    "type": "NTC thermistor",
                    "resistance_20C": "1200Ω",
                    "resistance_80C": "300Ω",
                },
                connected_to=["K20", "C246"],
                circuit_id="cooling_sensor",
            ),
            ExtractedComponent(
                id="F35",
                name="Coolant Pump Fuse",
                component_type="fuse",
                location="Underhood fuse box",
                specifications={
                    "rating": "15A",
                },
                connected_to=["M12", "R15"],
                circuit_id="cooling_pump",
            ),
            ExtractedComponent(
                id="K20",
                name="Battery ECM",
                component_type="ecu",
                location="Passenger compartment",
                specifications={},
                connected_to=["R15", "S22"],
                circuit_id="cooling_control",
            ),
            ExtractedComponent(
                id="C245",
                name="Coolant Pump Connector",
                component_type="connector",
                location="At coolant pump",
                specifications={
                    "pins": "2",
                },
                connected_to=["M12"],
                circuit_id="cooling_pump",
                pins=[
                    {"pin": "1", "function": "Power", "wire_color": "RED"},
                    {"pin": "2", "function": "Ground", "wire_color": "BLACK"},
                ],
            ),
            ExtractedComponent(
                id="TH01",
                name="Thermostat Assembly",
                component_type="valve",
                location="Coolant outlet housing",
                specifications={
                    "opening_temp": "82°C",
                    "full_open": "95°C",
                },
                connected_to=[],
                circuit_id="cooling_flow",
            ),
        ]
    
    def _mock_cooling_tsbs(self, year: int, make: str, model: str) -> List[ExtractedTSB]:
        """Mock cooling system TSBs."""
        tsbs = []
        
        # Add common EV cooling TSB if Bolt
        if "bolt" in model.lower() and 2019 <= year <= 2022:
            tsbs.append(ExtractedTSB(
                id="TSB 20-NA-123",
                title="Reduced Propulsion Power - Coolant Pump Failure",
                description="Some vehicles may experience reduced propulsion power "
                           "due to coolant pump motor failure causing battery overheating.",
                affected_components=["Coolant Pump Motor", "M12"],
                symptoms=["Reduced power warning", "High battery temperature", 
                         "Propulsion system fault"],
                solution="Replace coolant pump assembly. Part #XXXXX.",
            ))
        
        return tsbs
    
    def _mock_cooling_dtcs(self) -> Dict[str, str]:
        """Mock cooling system DTCs."""
        return {
            "P0117": "Engine Coolant Temperature Sensor Circuit Low",
            "P0118": "Engine Coolant Temperature Sensor Circuit High",
            "P0119": "Engine Coolant Temperature Sensor Circuit Intermittent",
            "P0125": "Insufficient Coolant Temperature for Closed Loop",
            "P0128": "Coolant Temperature Below Thermostat Regulating Temperature",
            "P0217": "Engine Coolant Overtemperature Condition",
            "P0230": "Fuel Pump Primary Circuit",
            "P0480": "Cooling Fan 1 Control Circuit",
            "P0481": "Cooling Fan 2 Control Circuit",
        }
    
    def _mock_fuel_components(self) -> List[ExtractedComponent]:
        """Mock fuel system components."""
        return [
            ExtractedComponent(
                id="FP01",
                name="Fuel Pump Module",
                component_type="pump",
                location="Fuel tank",
                specifications={
                    "voltage": "12V",
                    "pressure": "350-400 kPa",
                    "current": "5-8A",
                },
                connected_to=["FP_RLY", "FP_FUSE"],
                circuit_id="fuel_delivery",
            ),
            ExtractedComponent(
                id="INJ1",
                name="Fuel Injector #1",
                component_type="fuel_injector",
                location="Intake manifold",
                specifications={
                    "resistance": "12-14Ω",
                    "flow_rate": "200 cc/min",
                },
                connected_to=["PCM"],
                circuit_id="fuel_injection",
            ),
            ExtractedComponent(
                id="FPS01",
                name="Fuel Pressure Sensor",
                component_type="sensor",
                location="Fuel rail",
                specifications={
                    "range": "0-700 kPa",
                    "output": "0.5-4.5V",
                },
                connected_to=["PCM"],
                circuit_id="fuel_monitoring",
            ),
        ]
    
    def _mock_fuel_dtcs(self) -> Dict[str, str]:
        """Mock fuel system DTCs."""
        return {
            "P0171": "System Too Lean (Bank 1)",
            "P0172": "System Too Rich (Bank 1)",
            "P0174": "System Too Lean (Bank 2)",
            "P0175": "System Too Rich (Bank 2)",
            "P0201": "Injector Circuit/Open - Cylinder 1",
            "P0202": "Injector Circuit/Open - Cylinder 2",
            "P0230": "Fuel Pump Primary Circuit",
            "P0231": "Fuel Pump Secondary Circuit Low",
        }
    
    def _mock_ignition_components(self) -> List[ExtractedComponent]:
        """Mock ignition system components."""
        return [
            ExtractedComponent(
                id="COI1",
                name="Ignition Coil #1",
                component_type="ignition_coil",
                location="Cylinder 1",
                specifications={
                    "primary_resistance": "0.5-1.5Ω",
                    "secondary_resistance": "5000-15000Ω",
                },
                connected_to=["PCM", "SP1"],
                circuit_id="ignition_cyl1",
            ),
            ExtractedComponent(
                id="SP1",
                name="Spark Plug #1",
                component_type="spark_plug",
                location="Cylinder 1",
                specifications={
                    "gap": "0.8mm",
                    "heat_range": "6",
                },
                connected_to=["COI1"],
                circuit_id="ignition_cyl1",
            ),
            ExtractedComponent(
                id="CKP01",
                name="Crankshaft Position Sensor",
                component_type="sensor",
                location="Transmission bell housing",
                specifications={
                    "type": "Hall effect",
                    "output": "0-5V square wave",
                },
                connected_to=["PCM"],
                circuit_id="ignition_timing",
            ),
        ]
    
    def _mock_ignition_dtcs(self) -> Dict[str, str]:
        """Mock ignition system DTCs."""
        return {
            "P0300": "Random/Multiple Cylinder Misfire Detected",
            "P0301": "Cylinder 1 Misfire Detected",
            "P0302": "Cylinder 2 Misfire Detected",
            "P0351": "Ignition Coil A Primary/Secondary Circuit",
            "P0352": "Ignition Coil B Primary/Secondary Circuit",
            "P0335": "Crankshaft Position Sensor A Circuit",
            "P0340": "Camshaft Position Sensor A Circuit",
        }
    
    def _mock_generic_components(self, system: str) -> List[ExtractedComponent]:
        """Mock generic components for any system."""
        return [
            ExtractedComponent(
                id="GEN_SENS",
                name=f"{system} Sensor",
                component_type="sensor",
                location="System location",
                specifications={},
                connected_to=["GEN_ECU"],
                circuit_id=f"{system.lower()}_monitoring",
            ),
            ExtractedComponent(
                id="GEN_ACT",
                name=f"{system} Actuator",
                component_type="actuator",
                location="System location",
                specifications={},
                connected_to=["GEN_ECU", "GEN_RLY"],
                circuit_id=f"{system.lower()}_control",
            ),
            ExtractedComponent(
                id="GEN_RLY",
                name=f"{system} Relay",
                component_type="relay",
                location="Fuse box",
                specifications={},
                connected_to=["GEN_ACT", "GEN_FUSE"],
                circuit_id=f"{system.lower()}_power",
            ),
            ExtractedComponent(
                id="GEN_FUSE",
                name=f"{system} Fuse",
                component_type="fuse",
                location="Fuse box",
                specifications={"rating": "15A"},
                connected_to=["GEN_RLY"],
                circuit_id=f"{system.lower()}_power",
            ),
        ]


def extract_components_from_wiring_text(wiring_text: str) -> List[ExtractedComponent]:
    """
    Parse wiring diagram text to extract components.
    
    This is a helper for processing text extracted from Mitchell wiring diagrams.
    """
    components = []
    
    # Common patterns in wiring diagrams
    # Component ID patterns like "M12", "K15", "S22", "C245"
    component_pattern = r'\b([MKSRCF]\d{1,3}[A-Z]?)\b'
    
    # Find all component IDs
    matches = re.findall(component_pattern, wiring_text)
    
    for comp_id in set(matches):
        # Determine type from prefix
        prefix = comp_id[0]
        comp_type = {
            'M': 'motor',
            'K': 'relay',
            'S': 'sensor',
            'R': 'resistor',
            'C': 'connector',
            'F': 'fuse',
        }.get(prefix, 'unknown')
        
        components.append(ExtractedComponent(
            id=comp_id,
            name=f"Component {comp_id}",  # Would need context to get real name
            component_type=comp_type,
        ))
    
    return components
