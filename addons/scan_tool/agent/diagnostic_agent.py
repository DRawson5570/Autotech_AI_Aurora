"""
Agentic Diagnostic Agent

An AI agent that performs interactive vehicle diagnostics using:
- ELM327 scan tool for reading vehicle data
- Predictive diagnostics ML models for inference
- Interactive technician communication for tests

The agent follows a diagnostic workflow:
1. Connect to vehicle
2. Read initial data (DTCs, PIDs)
3. Run ML inference for preliminary diagnosis
4. Request discriminating tests from technician
5. Refine diagnosis based on new data
6. Present final diagnosis with confidence

Usage:
    agent = DiagnosticAgent()
    await agent.run_diagnosis("2012 Jeep Liberty Sport 3.7")
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """Current state of the diagnostic agent."""
    IDLE = "idle"
    CONNECTING = "connecting"
    READING_INITIAL = "reading_initial"
    ANALYZING = "analyzing"
    AWAITING_TECHNICIAN = "awaiting_technician"
    MONITORING = "monitoring"
    FINALIZING = "finalizing"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class DiagnosticResult:
    """Final diagnostic result."""
    primary_diagnosis: str
    confidence: float
    supporting_evidence: List[str]
    differential_diagnoses: List[Tuple[str, float]]  # (diagnosis, confidence)
    recommended_repairs: List[str]
    estimated_cost: Optional[str]
    tests_performed: List[str]
    raw_data: Dict[str, Any]


@dataclass
class TechnicianRequest:
    """A request for the technician to perform an action."""
    instruction: str
    reason: str
    expected_duration: int  # seconds
    data_to_capture: List[str]  # PIDs to monitor during the action


class DiagnosticAgent:
    """
    AI-powered diagnostic agent.
    
    Orchestrates the diagnostic process by:
    - Managing ELM327 communication
    - Running ML inference
    - Communicating with technician
    - Building diagnostic evidence
    """
    
    def __init__(
        self,
        elm_service=None,
        diagnostic_engine=None,
        technician_callback: Optional[Callable] = None,
    ):
        """
        Initialize the diagnostic agent.
        
        Args:
            elm_service: ELM327Service instance (will create if None)
            diagnostic_engine: DiagnosticEngine instance (will create if None)
            technician_callback: Async function to communicate with technician
                                 Signature: async def callback(message: str) -> str
        """
        self.elm_service = elm_service
        self.diagnostic_engine = diagnostic_engine
        self.technician_callback = technician_callback or self._default_callback
        
        self.state = AgentState.IDLE
        self.vehicle_info: Dict[str, Any] = {}
        self.collected_data: Dict[str, Any] = {}
        self.diagnostic_history: List[Dict] = []
        self.tests_performed: List[str] = []
        
    async def _default_callback(self, message: str) -> str:
        """Default callback - just prints and waits for input."""
        print(f"\n🔧 TECHNICIAN: {message}")
        return input("Response: ")
    
    async def _init_services(self):
        """Initialize services if not provided."""
        if self.elm_service is None:
            from ..service import ELM327Service
            self.elm_service = ELM327Service()
        
        if self.diagnostic_engine is None:
            try:
                from addons.predictive_diagnostics.reasoning.diagnostic_engine import DiagnosticEngine
                self.diagnostic_engine = DiagnosticEngine()
            except ImportError:
                logger.warning("DiagnosticEngine not available, using basic inference")
                self.diagnostic_engine = None
    
    async def run_diagnosis(
        self,
        vehicle_description: str,
        connection_type: str = "bluetooth",
        connection_address: str = "/dev/rfcomm0",
        symptoms: Optional[List[str]] = None,
    ) -> DiagnosticResult:
        """
        Run a complete diagnostic session.
        
        Args:
            vehicle_description: e.g., "2012 Jeep Liberty Sport 3.7"
            connection_type: "bluetooth", "wifi", or "usb"
            connection_address: Device address
            symptoms: Optional list of reported symptoms
        
        Returns:
            DiagnosticResult with diagnosis and recommendations
        """
        await self._init_services()
        
        self.vehicle_info = self._parse_vehicle(vehicle_description)
        self.collected_data = {
            'vehicle': self.vehicle_info,
            'symptoms': symptoms or [],
            'dtcs': [],
            'pids': {},
            'time_series': [],
            'freeze_frames': [],
        }
        
        try:
            # Step 1: Connect
            self.state = AgentState.CONNECTING
            await self._notify(f"🔌 Connecting to {vehicle_description}...")
            
            connected = await self.elm_service.connect(connection_type, connection_address)
            if not connected:
                raise ConnectionError("Failed to connect to ELM327 adapter")
            
            # Read VIN
            vin = await self.elm_service.read_vin()
            if vin:
                self.collected_data['vin'] = vin
                await self._notify(f"📋 VIN: {vin}")
            
            # Step 2: Read initial data
            self.state = AgentState.READING_INITIAL
            await self._read_initial_data()
            
            # Step 3: Initial analysis
            self.state = AgentState.ANALYZING
            initial_result = await self._run_inference("initial")
            
            # Step 4: Interactive diagnosis loop
            max_iterations = 5
            iteration = 0
            
            while iteration < max_iterations and initial_result['confidence'] < 0.80:
                iteration += 1
                
                # Determine what test would help most
                test = await self._determine_discriminating_test(initial_result)
                
                if test is None:
                    await self._notify("ℹ️ No further tests would significantly improve confidence")
                    break
                
                # Request technician action
                self.state = AgentState.AWAITING_TECHNICIAN
                response = await self._request_technician_action(test)
                
                if response.lower() in ['skip', 'cancel', 'done']:
                    break
                
                # Monitor during action
                self.state = AgentState.MONITORING
                await self._monitor_during_action(test)
                
                # Re-analyze
                self.state = AgentState.ANALYZING
                initial_result = await self._run_inference(f"iteration_{iteration}")
            
            # Step 5: Final diagnosis
            self.state = AgentState.FINALIZING
            result = await self._compile_final_result(initial_result)
            
            self.state = AgentState.COMPLETE
            return result
            
        except Exception as e:
            self.state = AgentState.ERROR
            logger.error(f"Diagnostic error: {e}")
            raise
        
        finally:
            # Always disconnect
            if self.elm_service and self.elm_service.connected:
                await self.elm_service.disconnect()
    
    def _parse_vehicle(self, description: str) -> Dict[str, str]:
        """Parse vehicle description into structured data."""
        parts = description.strip().split()
        
        result = {
            'year': None,
            'make': None,
            'model': None,
            'engine': None,
            'raw': description,
        }
        
        for part in parts:
            if part.isdigit() and len(part) == 4:
                result['year'] = part
            elif part.lower() in ['jeep', 'ford', 'chevy', 'chevrolet', 'toyota', 
                                   'honda', 'nissan', 'dodge', 'ram', 'gmc', 'bmw',
                                   'mercedes', 'audi', 'vw', 'volkswagen', 'hyundai',
                                   'kia', 'subaru', 'mazda', 'lexus', 'acura']:
                result['make'] = part.capitalize()
            elif '.' in part and any(c.isdigit() for c in part):
                result['engine'] = part
        
        # Whatever's left is likely the model
        remaining = [p for p in parts if p not in 
                    [result['year'], result['make'], result['engine']] 
                    and p.lower() != result.get('make', '').lower()]
        if remaining:
            result['model'] = ' '.join(remaining)
        
        return result
    
    async def _notify(self, message: str):
        """Send a notification to the technician."""
        await self.technician_callback(message)
    
    async def _read_initial_data(self):
        """Read initial diagnostic data from vehicle."""
        await self._notify("📊 Reading vehicle data...")
        
        # Read DTCs
        dtc_data = await self.elm_service.read_all_dtcs()
        
        stored = dtc_data.get('stored', [])
        pending = dtc_data.get('pending', [])
        permanent = dtc_data.get('permanent', [])
        
        self.collected_data['dtcs'] = [d.code for d in stored]
        self.collected_data['pending_dtcs'] = [d.code for d in pending]
        self.collected_data['permanent_dtcs'] = [d.code for d in permanent]
        
        if stored:
            dtc_list = ', '.join(d.code for d in stored)
            await self._notify(f"🔴 Found DTCs: {dtc_list}")
        else:
            await self._notify("✅ No stored DTCs")
        
        # Read common PIDs
        try:
            pids_to_read = [
                'RPM', 'COOLANT_TEMP', 'LOAD', 'THROTTLE_POS',
                'STFT_B1', 'LTFT_B1', 'STFT_B2', 'LTFT_B2',
                'MAF', 'MAP', 'IAT', 'SPEED', 'TIMING_ADV'
            ]
            
            readings = await self.elm_service.read_pids(pids_to_read)
            
            for name, reading in readings.items():
                self.collected_data['pids'][name.lower()] = reading.value
            
            await self._notify(f"📊 Read {len(readings)} PIDs")
            
        except Exception as e:
            logger.warning(f"Error reading PIDs: {e}")
        
        self.tests_performed.append("Initial scan (DTCs + PIDs)")
    
    async def _run_inference(self, phase: str) -> Dict[str, Any]:
        """Run ML inference on collected data."""
        await self._notify("🧠 Analyzing data...")
        
        # Convert to format expected by diagnostic engine
        dtcs = self.collected_data.get('dtcs', [])
        pids = self.collected_data.get('pids', {})
        symptoms = self.collected_data.get('symptoms', [])
        
        result = {
            'phase': phase,
            'timestamp': datetime.now().isoformat(),
            'diagnosis': None,
            'confidence': 0.0,
            'differentials': [],
        }
        
        if self.diagnostic_engine:
            try:
                # Use ML-powered inference
                diagnosis = self.diagnostic_engine.diagnose(
                    dtcs=dtcs,
                    pids=pids,
                    symptoms=symptoms
                )
                
                if diagnosis and diagnosis.get('diagnoses'):
                    top = diagnosis['diagnoses'][0]
                    result['diagnosis'] = top.get('failure_mode', 'Unknown')
                    result['confidence'] = top.get('confidence', 0.0)
                    result['differentials'] = [
                        (d['failure_mode'], d['confidence']) 
                        for d in diagnosis['diagnoses'][1:4]
                    ]
                    result['raw'] = diagnosis
                    
            except Exception as e:
                logger.warning(f"ML inference error: {e}")
        
        # Fallback to rule-based inference
        if not result['diagnosis']:
            result = self._rule_based_inference(dtcs, pids, symptoms)
            result['phase'] = phase
        
        self.diagnostic_history.append(result)
        
        diag = result['diagnosis'] or 'Unknown'
        conf = result['confidence'] * 100
        await self._notify(f"📋 Preliminary: {diag} ({conf:.0f}% confidence)")
        
        return result
    
    def _rule_based_inference(
        self, 
        dtcs: List[str], 
        pids: Dict[str, float],
        symptoms: List[str]
    ) -> Dict[str, Any]:
        """Simple rule-based inference as fallback."""
        result = {
            'diagnosis': None,
            'confidence': 0.0,
            'differentials': [],
        }
        
        coolant_temp = pids.get('coolant_temp', 0)
        ltft_b1 = pids.get('ltft_b1', 0)
        ltft_b2 = pids.get('ltft_b2', 0)
        
        # Check if we have time series data that supports the diagnosis
        time_series = self.collected_data.get('time_series', [])
        confidence_boost = min(0.25, len(time_series) * 0.001)  # Up to 25% boost for more data
        
        # Cooling system rules
        if 'P0217' in dtcs or 'P0128' in dtcs or coolant_temp > 230:
            # Check time series for temperature behavior
            if time_series:
                temps = [t.get('coolant_temp', 0) for t in time_series if 'coolant_temp' in t]
                if temps:
                    temp_rise = temps[-1] - temps[0] if len(temps) > 1 else 0
                    temp_max = max(temps)
                    
                    # Thermostat stuck closed: rapid rise, stays high
                    if temp_max > 230 and temp_rise > 20:
                        result['diagnosis'] = 'cooling.thermostat_stuck_closed'
                        result['confidence'] = 0.55 + confidence_boost
                        result['differentials'] = [
                            ('cooling.water_pump_failure', 0.25),
                            ('cooling.coolant_leak', 0.15),
                        ]
                    # Thermostat stuck open: slow rise, doesn't reach temp
                    elif 'P0128' in dtcs and temp_max < 180:
                        result['diagnosis'] = 'cooling.thermostat_stuck_open'
                        result['confidence'] = 0.60 + confidence_boost
                        result['differentials'] = [
                            ('cooling.ect_sensor_issue', 0.20),
                        ]
            
            # Default cooling diagnosis if no time series
            if not result['diagnosis']:
                if 'P0217' in dtcs:
                    result['diagnosis'] = 'cooling.thermostat_stuck_closed'
                    result['confidence'] = 0.55
                else:
                    result['diagnosis'] = 'cooling.thermostat_stuck_open'
                    result['confidence'] = 0.50
                result['differentials'] = [
                    ('cooling.water_pump_failure', 0.25),
                    ('cooling.coolant_leak', 0.15),
                ]
        
        # Fuel system rules
        elif any(dtc.startswith('P017') or dtc.startswith('P0171') for dtc in dtcs):
            if ltft_b1 > 15 and ltft_b2 > 15:
                result['diagnosis'] = 'fuel.vacuum_leak'
                result['confidence'] = 0.6 + confidence_boost
                result['differentials'] = [
                    ('fuel.maf_sensor_contaminated', 0.25),
                ]
            elif ltft_b1 > 15 and abs(ltft_b2) < 5:
                result['diagnosis'] = 'fuel.injector_bank1_issue'
                result['confidence'] = 0.5 + confidence_boost
        
        # Misfire rules
        elif any(dtc.startswith('P030') for dtc in dtcs):
            result['diagnosis'] = 'ignition.spark_plug_worn'
            result['confidence'] = 0.5 + confidence_boost
            result['differentials'] = [
                ('ignition.coil_pack_failing', 0.3),
            ]
        
        # Default
        if not result['diagnosis'] and dtcs:
            result['diagnosis'] = f'dtc_{dtcs[0]}_related'
            result['confidence'] = 0.3
        
        # Cap confidence at 95%
        result['confidence'] = min(0.95, result['confidence'])
        
        return result
    
    async def _determine_discriminating_test(
        self, 
        current_result: Dict[str, Any]
    ) -> Optional[TechnicianRequest]:
        """Determine the best test to discriminate between possibilities."""
        diagnosis = current_result.get('diagnosis', '')
        differentials = current_result.get('differentials', [])
        iteration = len(self.diagnostic_history)
        
        # Don't repeat the same test
        performed = set(t[:30] for t in self.tests_performed)
        
        # Cooling system tests
        if 'cooling' in diagnosis or any('cooling' in d[0] for d in differentials):
            if 'thermostat' in diagnosis and 'Start the engine cold' not in str(performed):
                return TechnicianRequest(
                    instruction="Start the engine cold and let it warm up to operating temperature. "
                                "DO NOT drive. Watch the temperature gauge.",
                    reason="Testing thermostat opening behavior",
                    expected_duration=300,  # 5 minutes
                    data_to_capture=['COOLANT_TEMP', 'RPM', 'SPEED']
                )
            elif ('water_pump' in diagnosis or iteration >= 1) and 'rev to 2500' not in str(performed).lower():
                return TechnicianRequest(
                    instruction="With engine at operating temp, rev to 2500 RPM and hold for 30 seconds.",
                    reason="Testing coolant circulation under load",
                    expected_duration=45,
                    data_to_capture=['COOLANT_TEMP', 'RPM', 'LOAD']
                )
        
        # Fuel system tests
        if 'fuel' in diagnosis or any('fuel' in d[0] for d in differentials):
            if 'rev to 2500' not in str(performed).lower():
                return TechnicianRequest(
                    instruction="Start engine, let idle for 1 minute, then rev to 2500 RPM and hold for 30 seconds.",
                    reason="Observing fuel trim adaptation under load",
                    expected_duration=120,
                    data_to_capture=['STFT_B1', 'LTFT_B1', 'STFT_B2', 'LTFT_B2', 'RPM', 'MAF', 'MAP']
                )
        
        # Ignition tests  
        if 'ignition' in diagnosis:
            if 'slowly increase' not in str(performed).lower():
                return TechnicianRequest(
                    instruction="Start engine, listen for misfires at idle, then slowly increase RPM to 3000.",
                    reason="Testing misfire behavior across RPM range",
                    expected_duration=60,
                    data_to_capture=['RPM', 'LOAD', 'TIMING_ADV']
                )
        
        return None
    
    async def _request_technician_action(self, test: TechnicianRequest) -> str:
        """Request the technician to perform an action."""
        message = f"""
🔧 **Please perform the following test:**

{test.instruction}

📝 Reason: {test.reason}
⏱️ Expected duration: {test.expected_duration} seconds

Type 'OK' when ready, or 'skip' to skip this test.
"""
        return await self.technician_callback(message)
    
    async def _monitor_during_action(self, test: TechnicianRequest):
        """Monitor PIDs while technician performs action."""
        await self._notify(f"📊 Monitoring: {', '.join(test.data_to_capture)}...")
        
        try:
            # Monitor for the expected duration
            samples = await self.elm_service.monitor_pids(
                test.data_to_capture,
                duration=test.expected_duration,
                interval=1.0
            )
            
            # Store time series data
            if samples:
                for sample in samples:
                    ts_entry = {'timestamp': datetime.now().isoformat()}
                    for name, reading in sample.items():
                        ts_entry[name.lower()] = reading.value
                    self.collected_data['time_series'].append(ts_entry)
                
                await self._notify(f"✅ Captured {len(samples)} data points")
                
        except Exception as e:
            logger.warning(f"Monitoring error: {e}")
            await self._notify(f"⚠️ Monitoring interrupted: {e}")
        
        self.tests_performed.append(test.instruction[:50] + "...")
    
    async def _compile_final_result(self, last_result: Dict[str, Any]) -> DiagnosticResult:
        """Compile the final diagnostic result."""
        diagnosis = last_result.get('diagnosis', 'Unknown')
        confidence = last_result.get('confidence', 0.0)
        differentials = last_result.get('differentials', [])
        
        # Build evidence list
        evidence = []
        
        dtcs = self.collected_data.get('dtcs', [])
        if dtcs:
            evidence.append(f"DTCs present: {', '.join(dtcs)}")
        
        pids = self.collected_data.get('pids', {})
        if pids.get('coolant_temp', 0) > 220:
            evidence.append(f"Elevated coolant temp: {pids['coolant_temp']:.0f}°F")
        
        ltft = pids.get('ltft_b1', 0)
        if abs(ltft) > 10:
            evidence.append(f"Abnormal fuel trim: LTFT B1 = {ltft:+.1f}%")
        
        # Get repair recommendations
        repairs, cost = self._get_repair_recommendations(diagnosis)
        
        return DiagnosticResult(
            primary_diagnosis=self._format_diagnosis(diagnosis),
            confidence=confidence,
            supporting_evidence=evidence,
            differential_diagnoses=[(self._format_diagnosis(d), c) for d, c in differentials],
            recommended_repairs=repairs,
            estimated_cost=cost,
            tests_performed=self.tests_performed,
            raw_data=self.collected_data,
        )
    
    def _format_diagnosis(self, diagnosis: str) -> str:
        """Format diagnosis code into readable text."""
        if not diagnosis:
            return "Unknown"
        
        # Convert cooling.thermostat_stuck_closed -> "Thermostat Stuck Closed (Cooling System)"
        parts = diagnosis.replace('_', ' ').split('.')
        if len(parts) == 2:
            system, issue = parts
            return f"{issue.title()} ({system.title()} System)"
        return diagnosis.replace('_', ' ').title()
    
    def _get_repair_recommendations(self, diagnosis: str) -> Tuple[List[str], Optional[str]]:
        """Get repair recommendations for a diagnosis."""
        repairs_db = {
            'cooling.thermostat_stuck_closed': (
                ['Replace thermostat', 'Flush cooling system', 'Check coolant level'],
                "$150-300 (parts: $25-50, labor: 1-2 hrs)"
            ),
            'cooling.thermostat_stuck_open': (
                ['Replace thermostat'],
                "$100-200 (parts: $25-50, labor: 1 hr)"
            ),
            'cooling.water_pump_failure': (
                ['Replace water pump', 'Replace timing belt if due', 'Flush cooling system'],
                "$400-800 (parts: $150-300, labor: 2-4 hrs)"
            ),
            'cooling.coolant_leak': (
                ['Pressure test cooling system', 'Locate and repair leak', 'Check hoses and clamps'],
                "$100-500 depending on leak location"
            ),
            'fuel.vacuum_leak': (
                ['Smoke test intake system', 'Replace leaking gaskets/hoses'],
                "$150-400 depending on location"
            ),
            'ignition.spark_plug_worn': (
                ['Replace spark plugs', 'Inspect ignition coils'],
                "$100-300 (parts: $50-150, labor: 1-2 hrs)"
            ),
        }
        
        return repairs_db.get(diagnosis, (['Perform further diagnosis'], None))


# Convenience function for Open WebUI integration
async def diagnose_vehicle(
    vehicle_description: str,
    connection_type: str = "bluetooth",
    connection_address: str = "/dev/rfcomm0",
    symptoms: List[str] = None,
    message_callback: Callable = None,
) -> str:
    """
    Run a diagnostic session and return formatted results.
    
    This is the main entry point for Open WebUI tool integration.
    """
    agent = DiagnosticAgent(technician_callback=message_callback)
    
    try:
        result = await agent.run_diagnosis(
            vehicle_description=vehicle_description,
            connection_type=connection_type,
            connection_address=connection_address,
            symptoms=symptoms,
        )
        
        # Format result for display
        output = [
            "=" * 60,
            "🔍 DIAGNOSTIC REPORT",
            "=" * 60,
            "",
            f"**Primary Diagnosis:** {result.primary_diagnosis}",
            f"**Confidence:** {result.confidence * 100:.0f}%",
            "",
        ]
        
        if result.supporting_evidence:
            output.append("**Supporting Evidence:**")
            for ev in result.supporting_evidence:
                output.append(f"  • {ev}")
            output.append("")
        
        if result.differential_diagnoses:
            output.append("**Other Possibilities:**")
            for diag, conf in result.differential_diagnoses:
                output.append(f"  • {diag} ({conf * 100:.0f}%)")
            output.append("")
        
        output.append("**Recommended Repairs:**")
        for repair in result.recommended_repairs:
            output.append(f"  • {repair}")
        
        if result.estimated_cost:
            output.append(f"\n**Estimated Cost:** {result.estimated_cost}")
        
        output.append("")
        output.append(f"**Tests Performed:** {len(result.tests_performed)}")
        for test in result.tests_performed:
            output.append(f"  • {test}")
        
        return '\n'.join(output)
        
    except Exception as e:
        return f"❌ Diagnostic error: {str(e)}"
