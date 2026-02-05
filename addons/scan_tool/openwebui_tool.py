"""
ELM327 Open WebUI Tool - Agentic Vehicle Diagnostics

AI-accessible tool for OBD-II diagnostics via ELM327 adapter.

IMPORTANT FOR LLM CONTEXT MANAGEMENT:
=====================================
This tool maintains a DIAGNOSTIC SESSION that persists across calls.
Always call `diagnostic_session_status()` to see:
  - What data has been collected
  - Current diagnostic hypotheses
  - What tests have been performed  
  - Recommended next steps

The session prevents the LLM from "forgetting" previous findings.

Key Functions:
- diagnostic_session_status() - GET THIS FIRST to see current state
- diagnostic_new_session() - Start fresh diagnosis
- elm327_connect() - Connect to vehicle
- elm327_read_dtcs() - Read trouble codes
- elm327_read_pids() - Read live sensor data
- elm327_monitor_pids() - Monitor PIDs over time
- elm327_capture_plot() - Record PIDs and return a visual chart
- diagnostic_analyze() - ML-powered analysis
- diagnostic_add_symptom() - Record customer complaints
- diagnostic_add_observation() - Record tech findings

Workflow:
1. diagnostic_new_session() - Start fresh
2. elm327_connect() - Connect to adapter
3. elm327_read_dtcs() - Get trouble codes
4. elm327_read_pids() - Get initial sensor data
5. diagnostic_analyze() - Get preliminary diagnosis
6. elm327_monitor_pids() - Gather more data if needed
7. diagnostic_session_status() - Review findings
8. elm327_disconnect() - Always disconnect when done

Usage in Open WebUI:
    The AI can call these functions to interact with the vehicle's
    OBD-II system through an ELM327 adapter.
"""

import asyncio
import base64
import io
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

# Pydantic for Open WebUI tool definition
try:
    from pydantic import BaseModel, Field
except ImportError:
    # Fallback for environments without pydantic
    class BaseModel:
        pass
    def Field(*args, **kwargs):
        return None

from .service import ELM327Service, DiagnosticSnapshot
from .protocol import DTC, get_dtc_description
from .pids import PIDRegistry
from .bidirectional import ActuatorType, ActuatorState
from .session import (
    DiagnosticSession, DiagnosticPhase, 
    get_session, reset_session, get_session_summary
)

logger = logging.getLogger(__name__)

# Global service instance (persists across tool calls)
_elm_service: Optional[ELM327Service] = None


class Tools:
    """
    ELM327 OBD-II Diagnostic Tools
    
    Provides AI-accessible functions for vehicle diagnostics through
    an ELM327-compatible OBD-II adapter.
    
    Sessions are scoped per user - each technician has their own
    diagnostic session that won't interfere with others.
    """
    
    class Valves(BaseModel):
        """Configuration options for the ELM327 tool."""
        default_connection_type: str = Field(
            default="wifi",
            description="Default connection type: wifi, bluetooth, usb"
        )
        default_address: str = Field(
            default="192.168.0.10:35000",
            description="Default adapter address"
        )
        enable_actuator_control: bool = Field(
            default=False,
            description="Enable bidirectional actuator control (use with caution)"
        )
        enable_dtc_clear: bool = Field(
            default=False,
            description="Enable DTC clearing (use with caution)"
        )
    
    def __init__(self):
        """Initialize the tool."""
        self.valves = self.Valves()
    
    def _get_user_id(self, __user__: dict = None) -> str:
        """Extract user ID from Open WebUI's __user__ dict."""
        if __user__ and isinstance(__user__, dict):
            # Open WebUI passes user info - use email or id
            return __user__.get("id") or __user__.get("email") or "default"
        return "default"
    
    # =========================================================================
    # SESSION MANAGEMENT - CRITICAL FOR LLM CONTEXT
    # =========================================================================
    
    async def diagnostic_session_status(self, __user__: dict = None) -> str:
        """
        Get the current diagnostic session status and context.
        
        ⚠️ CALL THIS FIRST when starting a diagnostic conversation!
        
        This provides:
        - Vehicle information
        - DTCs already found
        - PIDs already read
        - Current diagnostic hypotheses
        - Tests already performed
        - Recommended next steps
        
        The session persists across tool calls so you don't lose context.
        Each user has their own isolated session.
        
        Returns:
            Complete session summary with all collected data and analysis
        """
        user_id = self._get_user_id(__user__)
        session = get_session(user_id)
        summary = session.get_summary()
        
        # Add recommendation
        next_step = session.get_next_step_recommendation()
        summary += f"\n\n💡 **Recommended Next Step:** {next_step}"
        
        return summary
    
    async def diagnostic_new_session(
        self,
        vehicle_year: str = "",
        vehicle_make: str = "",
        vehicle_model: str = "",
        vehicle_engine: str = "",
        symptoms: str = "",
        __user__: dict = None
    ) -> str:
        """
        Start a new diagnostic session (clears previous session data).
        
        Call this at the START of a new diagnosis to reset the session.
        
        Args:
            vehicle_year: e.g., "2012"
            vehicle_make: e.g., "Jeep"
            vehicle_model: e.g., "Liberty Sport"
            vehicle_engine: e.g., "3.7L V6"
            symptoms: Comma-separated symptoms e.g., "overheating, check engine light"
        
        Returns:
            Confirmation and session status
        """
        user_id = self._get_user_id(__user__)
        session = reset_session(user_id)
        
        # Set vehicle info
        session.set_vehicle(
            year=vehicle_year or None,
            make=vehicle_make or None,
            model=vehicle_model or None,
            engine=vehicle_engine or None
        )
        
        # Add symptoms
        if symptoms:
            for s in symptoms.split(','):
                session.add_symptom(s.strip())
        
        session.log_action(f"Started new diagnostic session for {session.get_vehicle_description()}")
        
        return f"""✅ **New Diagnostic Session Started**

🚗 Vehicle: {session.get_vehicle_description()}
🩺 Symptoms: {', '.join(session.symptoms) if session.symptoms else 'None reported'}

**Next Steps:**
1. Connect to the vehicle with elm327_connect()
2. Read DTCs with elm327_read_dtcs()
3. Read live data with elm327_read_pids()

💡 Call diagnostic_session_status() anytime to see current progress."""
    
    async def diagnostic_add_symptom(self, symptom: str, __user__: dict = None) -> str:
        """
        Add a reported symptom to the diagnostic session.
        
        Args:
            symptom: Description of symptom (e.g., "rough idle when cold")
        
        Returns:
            Confirmation
        """
        user_id = self._get_user_id(__user__)
        session = get_session(user_id)
        session.add_symptom(symptom)
        session.log_action(f"Added symptom: {symptom}")
        
        return f"✅ Added symptom: '{symptom}'\nTotal symptoms: {len(session.symptoms)}"
    
    async def diagnostic_add_observation(self, observation: str, __user__: dict = None) -> str:
        """
        Add a technician observation to the diagnostic session.
        
        Args:
            observation: What the tech observed (e.g., "oil cap has milky residue")
        
        Returns:
            Confirmation
        """
        user_id = self._get_user_id(__user__)
        session = get_session(user_id)
        session.add_observation(observation)
        session.log_action(f"Observation: {observation}")
        
        return f"✅ Added observation: '{observation}'"
    
    async def diagnostic_set_hypothesis(
        self,
        diagnosis: str,
        confidence: float,
        evidence: str,
        tests_to_confirm: str = "",
        __user__: dict = None
    ) -> str:
        """
        Add or update a diagnostic hypothesis.
        
        Call this to record your current working theory.
        
        Args:
            diagnosis: The suspected issue (e.g., "thermostat stuck closed")
            confidence: Confidence level 0.0-1.0 (e.g., 0.7 for 70%)
            evidence: Comma-separated evidence supporting this hypothesis
            tests_to_confirm: Comma-separated tests that would confirm/deny this
        
        Returns:
            Confirmation and updated hypotheses list
        """
        user_id = self._get_user_id(__user__)
        session = get_session(user_id)
        
        evidence_list = [e.strip() for e in evidence.split(',') if e.strip()]
        tests_list = [t.strip() for t in tests_to_confirm.split(',') if t.strip()] if tests_to_confirm else []
        
        # Determine system from diagnosis
        system = "unknown"
        diag_lower = diagnosis.lower()
        if any(w in diag_lower for w in ['thermostat', 'coolant', 'radiator', 'water pump', 'cooling']):
            system = "cooling"
        elif any(w in diag_lower for w in ['fuel', 'injector', 'pump', 'lean', 'rich', 'trim']):
            system = "fuel"
        elif any(w in diag_lower for w in ['spark', 'coil', 'ignition', 'misfire']):
            system = "ignition"
        elif any(w in diag_lower for w in ['o2', 'cat', 'egr', 'evap', 'emission']):
            system = "emissions"
        
        session.add_hypothesis(
            diagnosis=diagnosis,
            system=system,
            confidence=confidence,
            evidence=evidence_list,
            tests_to_confirm=tests_list
        )
        session.log_action(f"Hypothesis: {diagnosis} ({confidence*100:.0f}%)")
        
        # Format output
        output = [f"✅ Hypothesis recorded: **{diagnosis}** ({confidence*100:.0f}% confidence)"]
        output.append(f"   System: {system}")
        output.append(f"   Evidence: {', '.join(evidence_list)}")
        
        if tests_list:
            output.append(f"   Tests to confirm: {', '.join(tests_list)}")
        
        output.append(f"\n**Current Hypotheses ({len(session.hypotheses)}):**")
        for h in sorted(session.hypotheses, key=lambda x: -x.confidence):
            output.append(f"   • {h.diagnosis}: {h.confidence*100:.0f}%")
        
        return '\n'.join(output)
    
    async def diagnostic_rule_out(self, diagnosis: str, reason: str, __user__: dict = None) -> str:
        """
        Rule out a diagnosis and record why.
        
        Args:
            diagnosis: The diagnosis being ruled out
            reason: Why it's being ruled out (e.g., "fuel trims normal")
        
        Returns:
            Confirmation
        """
        user_id = self._get_user_id(__user__)
        session = get_session(user_id)
        session.rule_out(diagnosis, reason)
        session.log_action(f"Ruled out: {diagnosis} - {reason}")
        
        return f"❌ Ruled out: **{diagnosis}**\n   Reason: {reason}"
    
    async def diagnostic_set_next_steps(self, steps: str, __user__: dict = None) -> str:
        """
        Set the recommended next steps for the diagnostic.
        
        Call this to record what should be done next.
        
        Args:
            steps: Comma-separated list of next steps
        
        Returns:
            Confirmation
        """
        user_id = self._get_user_id(__user__)
        session = get_session(user_id)
        session.next_steps = [s.strip() for s in steps.split(',') if s.strip()]
        session.log_action(f"Set {len(session.next_steps)} next steps")
        
        return f"✅ Set {len(session.next_steps)} next steps:\n" + '\n'.join(
            f"   {i}. {s}" for i, s in enumerate(session.next_steps, 1)
        )
    
    # =========================================================================
    # CONNECTION FUNCTIONS
    # =========================================================================
    
    async def elm327_connect(
        self,
        connection_type: str = None,
        address: str = None,
        __user__: dict = None
    ) -> str:
        """
        Connect to an ELM327 OBD-II adapter.
        
        Args:
            connection_type: Connection type - 'wifi', 'bluetooth', or 'usb'
            address: Device address. For WiFi: IP:port (e.g., '192.168.0.10:35000').
                    For Bluetooth/USB: device path (e.g., '/dev/rfcomm0')
        
        Returns:
            Connection status message with VIN if available
        """
        global _elm_service
        
        conn_type = connection_type or self.valves.default_connection_type
        user_id = self._get_user_id(__user__)
        addr = address or self.valves.default_address
        session = get_session(user_id)
        
        try:
            # Disconnect existing connection
            if _elm_service and _elm_service.connected:
                await _elm_service.disconnect()
            
            # Create new service and connect
            _elm_service = ELM327Service()
            success = await _elm_service.connect(conn_type, addr)
            
            if success:
                vin = _elm_service.vin
                supported = await _elm_service.get_supported_pids()
                
                msg = f"✅ Connected to ELM327 via {conn_type}"
                
                # Update session
                session.phase = DiagnosticPhase.CONNECTED
                session.log_action(f"Connected via {conn_type} to {addr}")
                
                if vin:
                    msg += f"\n📋 VIN: {vin}"
                    session.set_vehicle(vin=vin)
                    
                msg += f"\n📊 Vehicle supports {len(supported)} PIDs"
                msg += "\n\n💡 **Next:** Call elm327_read_dtcs() to check for trouble codes"
                return msg
            else:
                return f"❌ Failed to connect to ELM327 at {addr}"
                
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return f"❌ Connection error: {str(e)}"
    
    async def elm327_disconnect(self, __user__: dict = None) -> str:
        """
        Disconnect from the ELM327 adapter.
        
        ⚠️ ALWAYS call this when done with diagnostics!
        
        Returns:
            Disconnection status message and session summary
        """
        global _elm_service
        
        user_id = self._get_user_id(__user__)
        session = get_session(user_id)
        
        if _elm_service:
            await _elm_service.disconnect()
            _elm_service = None
            session.log_action("Disconnected from ELM327")
            
            # Provide summary
            summary = session.get_summary()
            return f"✅ Disconnected from ELM327\n\n{summary}"
        else:
            return "ℹ️ Not connected"
    
    async def elm327_read_vin(self, __user__: dict = None) -> str:
        """
        Read the Vehicle Identification Number (VIN).
        
        Returns:
            The 17-character VIN or error message
        """
        if not _elm_service or not _elm_service.connected:
            return "❌ Not connected. Use elm327_connect first."
        
        user_id = self._get_user_id(__user__)
        session = get_session(user_id)
        
        try:
            vin = await _elm_service.read_vin()
            if vin:
                session.set_vehicle(vin=vin)
                session.log_action(f"Read VIN: {vin}")
                return f"📋 VIN: {vin}"
            else:
                return "⚠️ Could not read VIN (vehicle may not support it)"
        except Exception as e:
            return f"❌ Error reading VIN: {str(e)}"
    
    async def elm327_read_dtcs(self, __user__: dict = None) -> str:
        """
        Read all Diagnostic Trouble Codes (DTCs).
        
        Reads stored, pending, and permanent DTCs from the vehicle's
        ECU and provides descriptions for each code.
        
        Results are saved to the diagnostic session for later analysis.
        
        Returns:
            List of DTCs with descriptions, or "No DTCs found"
        """
        if not _elm_service or not _elm_service.connected:
            return "❌ Not connected. Use elm327_connect first."
        
        user_id = self._get_user_id(__user__)
        session = get_session(user_id)
        
        try:
            all_dtcs = await _elm_service.read_all_dtcs()
            
            result = []
            dtc_count = 0
            
            # Stored DTCs
            stored = all_dtcs['stored']
            if stored:
                result.append("🔴 **Stored DTCs (Check Engine Light):**")
                for dtc in stored:
                    result.append(f"  • {dtc.code}: {dtc.description}")
                    session.add_dtc(dtc.code, dtc.description, "stored")
                    dtc_count += 1
            
            # Pending DTCs  
            pending = all_dtcs['pending']
            if pending:
                result.append("\n🟡 **Pending DTCs (Current Drive Cycle):**")
                for dtc in pending:
                    result.append(f"  • {dtc.code}: {dtc.description}")
                    session.add_dtc(dtc.code, dtc.description, "pending")
                    dtc_count += 1
            
            # Permanent DTCs
            permanent = all_dtcs['permanent']
            if permanent:
                result.append("\n🟠 **Permanent DTCs (Survive Clear):**")
                for dtc in permanent:
                    result.append(f"  • {dtc.code}: {dtc.description}")
                    session.add_dtc(dtc.code, dtc.description, "permanent")
                    dtc_count += 1
            
            # Update session phase
            session.phase = DiagnosticPhase.INITIAL_SCAN
            session.log_action(f"Read DTCs: found {dtc_count} codes")
            
            if not result:
                result.append("✅ No DTCs found - no active trouble codes")
                result.append("\n💡 **Next:** Read live PIDs with elm327_read_pids('RPM, COOLANT_TEMP, STFT_B1, LTFT_B1')")
            else:
                result.append("\n💡 **Next:** Read related PIDs to gather more diagnostic data")
            
            return '\n'.join(result)
            
        except Exception as e:
            return f"❌ Error reading DTCs: {str(e)}"
    
    async def elm327_clear_dtcs(self, __user__: dict = None) -> str:
        """
        Clear all DTCs and the Check Engine Light.
        
        ⚠️ WARNING: Only use this after repairs have been completed.
        Clearing DTCs without fixing the problem will cause the light
        to return.
        
        Returns:
            Success or error message
        """
        if not self.valves.enable_dtc_clear:
            return "❌ DTC clearing is disabled. Enable in tool settings if needed."
        
        if not _elm_service or not _elm_service.connected:
            return "❌ Not connected. Use elm327_connect first."
        
        user_id = self._get_user_id(__user__)
        session = get_session(user_id)
        
        try:
            success = await _elm_service.clear_dtcs()
            if success:
                session.log_action("Cleared DTCs")
                return "✅ DTCs cleared. Check Engine Light should turn off after a few drive cycles."
            else:
                return "⚠️ Clear command sent but response unclear"
        except Exception as e:
            return f"❌ Error clearing DTCs: {str(e)}"
    
    async def elm327_read_pids(
        self,
        pids: str,
        context: str = "",
        __user__: dict = None
    ) -> str:
        """
        Read specific OBD-II PIDs (live sensor data).
        
        Results are saved to the diagnostic session for later analysis.
        
        Args:
            pids: Comma-separated list of PID names or numbers.
                  Common PIDs: RPM, COOLANT_TEMP, SPEED, THROTTLE_POS,
                  STFT_B1, LTFT_B1, STFT_B2, LTFT_B2, MAF, MAP, IAT,
                  O2_B1S1, O2_B1S2, TIMING_ADV, LOAD, VOLTAGE
            context: Optional context for the reading (e.g., "at idle", "during warmup")
        
        Returns:
            Current values for requested PIDs
        """
        if not _elm_service or not _elm_service.connected:
            return "❌ Not connected. Use elm327_connect first."
        
        user_id = self._get_user_id(__user__)
        session = get_session(user_id)
        
        try:
            # Parse PID list
            pid_list = [p.strip() for p in pids.split(',')]
            
            readings = await _elm_service.read_pids(pid_list)
            
            if not readings:
                return "⚠️ No PIDs could be read (may not be supported)"
            
            result = ["📊 **Live PID Data:**"]
            if context:
                result.append(f"   _(Context: {context})_")
            
            for name, reading in readings.items():
                result.append(f"  • {name}: {reading.value:.2f} {reading.unit}")
                # Save to session
                session.add_pid(name, reading.value, reading.unit, context)
            
            session.phase = DiagnosticPhase.GATHERING_DATA
            session.log_action(f"Read {len(readings)} PIDs" + (f" ({context})" if context else ""))
            
            return '\n'.join(result)
            
        except Exception as e:
            return f"❌ Error reading PIDs: {str(e)}"
    
    async def elm327_read_fuel_trims(self, __user__: dict = None) -> str:
        """
        Read fuel trim values (short-term and long-term).
        
        Fuel trims indicate how much the ECU is adjusting fuel delivery:
        - Positive values: ECU adding fuel (lean condition)
        - Negative values: ECU removing fuel (rich condition)
        - Normal range: -10% to +10%
        
        Results are saved to the diagnostic session.
        
        Returns:
            Fuel trim percentages for both banks
        """
        if not _elm_service or not _elm_service.connected:
            return "❌ Not connected. Use elm327_connect first."
        
        user_id = self._get_user_id(__user__)
        session = get_session(user_id)
        
        try:
            trims = await _elm_service.read_fuel_trims()
            
            if not trims:
                return "⚠️ Fuel trim PIDs not supported"
            
            result = ["⛽ **Fuel Trims:**"]
            
            for name, reading in trims.items():
                val = reading.value
                status = "✅" if -10 <= val <= 10 else "⚠️"
                direction = "adding fuel (lean)" if val > 0 else "removing fuel (rich)" if val < 0 else "neutral"
                result.append(f"  {status} {name}: {val:+.1f}% ({direction})")
                # Save to session
                session.add_pid(name, val, "%", "fuel trim reading")
            
            session.log_action("Read fuel trims")
            
            # Interpretation
            if 'LTFT_B1' in trims and 'LTFT_B2' in trims:
                ltft1 = trims['LTFT_B1'].value
                ltft2 = trims['LTFT_B2'].value
                
                if ltft1 > 15 and ltft2 > 15:
                    result.append("\n💡 Both banks positive: Check for vacuum leak or MAF issue")
                elif ltft1 > 15 and abs(ltft2) < 5:
                    result.append("\n💡 Bank 1 only lean: Check Bank 1 injectors or intake leak")
                elif ltft1 < -15 and ltft2 < -15:
                    result.append("\n💡 Both banks rich: Check fuel pressure or O2 sensors")
            
            return '\n'.join(result)
            
        except Exception as e:
            return f"❌ Error reading fuel trims: {str(e)}"
    
    async def elm327_monitor_pids(
        self,
        pids: str,
        duration: float = 10.0,
        interval: float = 1.0,
        context: str = "",
        __user__: dict = None
    ) -> str:
        """
        Monitor PIDs over time and report min/max/average.
        
        Use this for tests like "monitor coolant temp during warmup".
        Results are saved to the diagnostic session.
        
        Args:
            pids: Comma-separated list of PID names
            duration: Monitoring duration in seconds (default: 10)
            interval: Sample interval in seconds (default: 1)
            context: What's happening during monitoring (e.g., "during warmup", "at 2500 RPM")
        
        Returns:
            Statistics for each monitored PID
        """
        if not _elm_service or not _elm_service.connected:
            return "❌ Not connected. Use elm327_connect first."
        
        user_id = self._get_user_id(__user__)
        session = get_session(user_id)
        
        try:
            pid_list = [p.strip() for p in pids.split(',')]
            
            # Collect samples
            samples = await _elm_service.monitor_pids(
                pid_list,
                duration=duration,
                interval=interval
            )
            
            if not samples:
                return "⚠️ No data collected"
            
            # Calculate statistics
            stats = {}
            for sample in samples:
                for name, reading in sample.items():
                    if name not in stats:
                        stats[name] = {'values': [], 'unit': reading.unit}
                    stats[name]['values'].append(reading.value)
            
            result = [f"📈 **Monitored {len(samples)} samples over {duration}s:**"]
            if context:
                result.append(f"   _(Context: {context})_")
            
            for name, data in stats.items():
                values = data['values']
                unit = data['unit']
                min_val = min(values)
                max_val = max(values)
                avg_val = sum(values)/len(values)
                
                result.append(f"\n  **{name}** ({unit}):")
                result.append(f"    Min: {min_val:.2f}")
                result.append(f"    Max: {max_val:.2f}")
                result.append(f"    Avg: {avg_val:.2f}")
                
                # Save final reading to session
                session.add_pid(name, values[-1], unit, f"monitored {duration}s: min={min_val:.1f}, max={max_val:.1f}" + (f" ({context})" if context else ""))
            
            session.phase = DiagnosticPhase.TESTING
            session.log_action(f"Monitored {', '.join(pid_list)} for {duration}s" + (f" ({context})" if context else ""))
            
            return '\n'.join(result)
            
        except Exception as e:
            return f"❌ Error monitoring PIDs: {str(e)}"
    
    async def elm327_capture_plot(
        self,
        pids: str,
        duration: float = 30.0,
        title: str = "",
        __user__: dict = None
    ) -> str:
        """
        Capture PID data over time and return a plot image.
        
        Use this to visualize sensor behavior over time - great for seeing
        O2 sensor switching, throttle response, fuel trim changes, etc.
        
        Args:
            pids: Comma-separated list of PIDs to plot (e.g., "RPM,MAP,O2_B1S1")
            duration: Capture duration in seconds (default: 30, max: 120)
            title: Optional title for the plot
        
        Returns:
            A plot image showing the sensor data over time
        """
        if not _elm_service or not _elm_service.connected:
            return "❌ Not connected. Use elm327_connect first."
        
        # Import matplotlib here to avoid startup cost
        try:
            import matplotlib
            matplotlib.use('Agg')  # Non-interactive backend
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
        except ImportError:
            return "❌ matplotlib not installed. Run: pip install matplotlib"
        
        user_id = self._get_user_id(__user__)
        session = get_session(user_id)
        
        try:
            pid_list = [p.strip().upper() for p in pids.split(',')]
            duration = min(duration, 120.0)  # Cap at 2 minutes
            
            # Collect data
            data = {pid: {'times': [], 'values': [], 'unit': ''} for pid in pid_list}
            start_time = datetime.now()
            
            sample_interval = 0.2  # 5Hz sampling
            samples_collected = 0
            
            while (datetime.now() - start_time).total_seconds() < duration:
                timestamp = (datetime.now() - start_time).total_seconds()
                
                readings = await _elm_service.read_pids(pid_list)
                if readings:
                    for name, reading in readings.items():
                        if name in data:
                            data[name]['times'].append(timestamp)
                            data[name]['values'].append(reading.value)
                            data[name]['unit'] = reading.unit
                    samples_collected += 1
                
                await asyncio.sleep(sample_interval)
            
            if samples_collected < 2:
                return "⚠️ Insufficient data collected. Check connection."
            
            # Create plot
            fig, axes = plt.subplots(len(pid_list), 1, figsize=(10, 3 * len(pid_list)), sharex=True)
            if len(pid_list) == 1:
                axes = [axes]
            
            colors = ['#00d4ff', '#ff6b6b', '#4ecdc4', '#ffe66d', '#95e1d3']
            
            for i, (pid, ax) in enumerate(zip(pid_list, axes)):
                pid_data = data[pid]
                if pid_data['times']:
                    color = colors[i % len(colors)]
                    ax.plot(pid_data['times'], pid_data['values'], color=color, linewidth=1.5)
                    ax.fill_between(pid_data['times'], pid_data['values'], alpha=0.3, color=color)
                    ax.set_ylabel(f"{pid}\n({pid_data['unit']})", fontsize=10)
                    ax.grid(True, alpha=0.3)
                    ax.set_facecolor('#1a1a2e')
                    
                    # Add min/max/avg annotations
                    vals = pid_data['values']
                    if vals:
                        ax.axhline(y=sum(vals)/len(vals), color=color, linestyle='--', alpha=0.5, label=f'avg: {sum(vals)/len(vals):.1f}')
                        ax.legend(loc='upper right', fontsize=8)
            
            axes[-1].set_xlabel('Time (seconds)', fontsize=10)
            
            plot_title = title if title else f"PID Capture - {', '.join(pid_list)}"
            fig.suptitle(plot_title, fontsize=12, fontweight='bold')
            
            fig.patch.set_facecolor('#0f0f23')
            plt.tight_layout()
            
            # Convert to base64 image
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=100, facecolor='#0f0f23', edgecolor='none')
            buf.seek(0)
            img_base64 = base64.b64encode(buf.read()).decode('utf-8')
            plt.close(fig)
            
            # Log to session
            session.log_action(f"Captured plot of {', '.join(pid_list)} for {duration}s ({samples_collected} samples)")
            
            # Return markdown image
            return f"📊 **PID Data Capture** ({samples_collected} samples over {duration:.0f}s)\n\n![{plot_title}](data:image/png;base64,{img_base64})"
            
        except Exception as e:
            logger.exception("Error in elm327_capture_plot")
            return f"❌ Error capturing data: {str(e)}"
    
    async def elm327_diagnostic_snapshot(self, __user__: dict = None) -> str:
        """
        Capture a complete diagnostic snapshot.
        
        Reads all available information including:
        - VIN
        - All DTCs (stored, pending, permanent)
        - Common diagnostic PIDs
        - Fuel trims
        - Temperatures
        
        Returns:
            Comprehensive diagnostic report
        """
        if not _elm_service or not _elm_service.connected:
            return "❌ Not connected. Use elm327_connect first."
        
        try:
            snapshot = await _elm_service.capture_diagnostic_snapshot()
            
            result = ["📋 **DIAGNOSTIC SNAPSHOT**"]
            result.append(f"🕐 Timestamp: {snapshot.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            
            if snapshot.vin:
                result.append(f"🚗 VIN: {snapshot.vin}")
            
            # DTCs
            result.append(f"\n🔍 **Trouble Codes:**")
            if snapshot.dtcs:
                for dtc in snapshot.dtcs:
                    result.append(f"  🔴 {dtc.code}: {dtc.description}")
            else:
                result.append("  ✅ No stored DTCs")
            
            if snapshot.pending_dtcs:
                result.append("  Pending:")
                for dtc in snapshot.pending_dtcs:
                    result.append(f"  🟡 {dtc.code}: {dtc.description}")
            
            # PIDs
            result.append(f"\n📊 **Live Data ({len(snapshot.pids)} PIDs):**")
            for name, reading in snapshot.pids.items():
                result.append(f"  • {name}: {reading.value:.2f} {reading.unit}")
            
            return '\n'.join(result)
            
        except Exception as e:
            return f"❌ Error capturing snapshot: {str(e)}"
    
    async def elm327_actuator_test(
        self,
        actuator: str,
        state: str = "on",
        duration: float = 5.0,
        __user__: dict = None
    ) -> str:
        """
        Test an actuator (bidirectional control).
        
        ⚠️ WARNING: Use with caution. This directly controls vehicle components.
        
        Args:
            actuator: Actuator to test - 'cooling_fan', 'evap_purge', 
                     'evap_vent', 'ac_clutch', 'fuel_pump'
            state: 'on', 'off', or 'default'
            duration: How long to run test in seconds (auto-releases after)
        
        Returns:
            Test result message
        """
        if not self.valves.enable_actuator_control:
            return "❌ Actuator control is disabled. Enable in tool settings if needed."
        
        if not _elm_service or not _elm_service.connected:
            return "❌ Not connected. Use elm327_connect first."
        
        try:
            success = await _elm_service.actuator_test(actuator, state, duration)
            
            if success:
                return f"✅ {actuator} commanded {state.upper()} for {duration}s\n⚠️ Verify actuator operation physically"
            else:
                return f"⚠️ Actuator test not supported or failed (Mode $08 may not be available on this vehicle)"
                
        except Exception as e:
            return f"❌ Actuator test error: {str(e)}"
    
    async def elm327_wait_for_condition(
        self,
        pid: str,
        operator: str,
        value: float,
        timeout: float = 30.0,
        tolerance: float = None,
        __user__: dict = None
    ) -> str:
        """
        Wait for a PID to meet a condition before continuing.
        
        Useful for AI-directed tests where the AI needs to wait for the
        user to bring the vehicle to a specific state before capturing data.
        
        Examples:
        - "Hold RPM at 2500" → pid="RPM", operator="equals", value=2500, tolerance=200
        - "Wait for engine to warm up" → pid="COOLANT_TEMP", operator=">=", value=180
        - "Rev above 3000" → pid="RPM", operator=">", value=3000
        - "Let it idle down" → pid="RPM", operator="<", value=1000
        
        Args:
            pid: PID to monitor (RPM, COOLANT_TEMP, THROTTLE_POS, MAF, etc.)
            operator: Comparison operator - '>', '<', '>=', '<=', '==', 'equals'
            value: Target value to compare against
            timeout: Maximum wait time in seconds (default 30)
            tolerance: For 'equals' operator, acceptable ± range (default: 10% of value)
        
        Returns:
            Success message with actual value, or timeout message
        """
        if not _elm_service or not _elm_service.connected:
            return "❌ Not connected. Use elm327_connect first."
        
        # Build condition function based on operator
        op = operator.lower().strip()
        
        if op in ('==', 'equals', 'eq', '='):
            tol = tolerance if tolerance is not None else abs(value * 0.1)  # 10% default
            condition = lambda v: abs(v - value) <= tol
            op_desc = f"≈ {value} (±{tol:.1f})"
        elif op in ('>', 'gt', 'above', 'greater'):
            condition = lambda v: v > value
            op_desc = f"> {value}"
        elif op in ('<', 'lt', 'below', 'less'):
            condition = lambda v: v < value
            op_desc = f"< {value}"
        elif op in ('>=', 'gte', 'atleast'):
            condition = lambda v: v >= value
            op_desc = f"≥ {value}"
        elif op in ('<=', 'lte', 'atmost'):
            condition = lambda v: v <= value
            op_desc = f"≤ {value}"
        else:
            return f"❌ Unknown operator '{operator}'. Use: >, <, >=, <=, ==, equals"
        
        try:
            result = await _elm_service.wait_for_condition(
                pid,
                condition,
                timeout=timeout
            )
            
            if result:
                return f"✅ Condition met! {pid}: {result.value:.1f} {result.unit}"
            else:
                return f"⏱️ Timeout - {pid} did not reach {op_desc} within {timeout}s"
                
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    async def elm327_available_pids(self, __user__: dict = None) -> str:
        """
        List all available PID names that can be read.
        
        Returns:
            List of PID names organized by category
        """
        result = ["📊 **Available PIDs:**\n"]
        
        result.append("**Engine:**")
        result.append("  RPM, LOAD, THROTTLE_POS, TIMING_ADV, RUN_TIME")
        
        result.append("\n**Fuel:**")
        result.append("  STFT_B1, LTFT_B1, STFT_B2, LTFT_B2, FUEL_PRESSURE, FUEL_LEVEL")
        
        result.append("\n**Temperature:**")
        result.append("  COOLANT_TEMP, IAT, OIL_TEMP, AMBIENT_TEMP")
        
        result.append("\n**Air Flow:**")
        result.append("  MAF, MAP, BARO")
        
        result.append("\n**Speed:**")
        result.append("  SPEED")
        
        result.append("\n**Oxygen Sensors:**")
        result.append("  O2_B1S1, O2_B1S2, O2_B2S1, O2_B2S2")
        
        result.append("\n**Other:**")
        result.append("  VOLTAGE, EVAP_PURGE")
        
        result.append("\n💡 Note: Not all PIDs are supported by all vehicles")
        
        return '\n'.join(result)

    async def diagnostic_analyze(
        self,
        dtcs: str = "",
        symptoms: str = "",
        coolant_temp: float = None,
        rpm: float = None,
        stft_b1: float = None,
        ltft_b1: float = None,
        stft_b2: float = None,
        ltft_b2: float = None,
        maf: float = None,
        map_kpa: float = None,
        temp_rise_rate: float = None,
        use_session_data: bool = True,
        __user__: dict = None
    ) -> str:
        """
        Analyze diagnostic data using ML inference.
        
        Call this after gathering DTCs, PIDs, and observations to get
        AI-assisted diagnosis with confidence scores.
        
        If use_session_data=True (default), will automatically include
        data already collected in the session. You can also pass additional
        data to override or supplement session data.
        
        Diagnoses are saved to the session as hypotheses.
        
        Args:
            dtcs: Comma-separated DTCs, e.g., "P0217, P0128"
            symptoms: Comma-separated symptoms, e.g., "overheating, rough idle"
            coolant_temp: Coolant temperature in °F
            rpm: Engine RPM
            stft_b1: Short-term fuel trim bank 1 (%)
            ltft_b1: Long-term fuel trim bank 1 (%)
            stft_b2: Short-term fuel trim bank 2 (%)
            ltft_b2: Long-term fuel trim bank 2 (%)
            maf: Mass airflow (g/s)
            map_kpa: Manifold pressure (kPa)
            temp_rise_rate: Temperature rise rate (°F/min) from monitoring
            use_session_data: Include data from session (default True)
        
        Returns:
            Ranked list of possible diagnoses with confidence scores
        """
        user_id = self._get_user_id(__user__)
        session = get_session(user_id)
        
        # Start with session data if requested
        if use_session_data:
            # Get DTCs from session
            session_dtcs = [d.code for d in session.dtcs]
            session_symptoms = session.symptoms.copy()
            
            # Get latest PID values from session
            session_pids = {}
            for pid_name in ['COOLANT_TEMP', 'RPM', 'STFT_B1', 'LTFT_B1', 'STFT_B2', 'LTFT_B2', 'MAF', 'MAP']:
                latest = session.get_latest_pid(pid_name)
                if latest:
                    session_pids[pid_name.lower()] = latest.value
        else:
            session_dtcs = []
            session_symptoms = []
            session_pids = {}
        
        # Merge with passed-in data (passed-in takes precedence)
        dtc_list = session_dtcs + [d.strip() for d in dtcs.split(',') if d.strip()]
        dtc_list = list(set(dtc_list))  # Dedupe
        
        symptom_list = session_symptoms + [s.strip().lower() for s in symptoms.split(',') if s.strip()]
        symptom_list = list(set(symptom_list))  # Dedupe
        
        # Build PID dict (passed-in values override session)
        pids = session_pids.copy()
        if coolant_temp is not None: pids['coolant_temp'] = coolant_temp
        if rpm is not None: pids['rpm'] = rpm
        if stft_b1 is not None: pids['stft_b1'] = stft_b1
        if ltft_b1 is not None: pids['ltft_b1'] = ltft_b1
        if stft_b2 is not None: pids['stft_b2'] = stft_b2
        if ltft_b2 is not None: pids['ltft_b2'] = ltft_b2
        if maf is not None: pids['maf'] = maf
        if map_kpa is not None: pids['map'] = map_kpa
        if temp_rise_rate is not None: pids['temp_rise_rate'] = temp_rise_rate
        
        # Try ML inference first
        diagnoses = []
        
        try:
            from addons.predictive_diagnostics.integration import DiagnosticEngine, SensorReading
            engine = DiagnosticEngine()
            
            # Convert PID dict to SensorReading list
            sensor_readings = []
            for name, value in pids.items():
                sensor_readings.append(SensorReading(name=name, value=value))
            
            result = engine.diagnose(
                sensors=sensor_readings if sensor_readings else None,
                dtcs=dtc_list if dtc_list else None, 
                symptoms=symptom_list if symptom_list else None
            )
            
            if result and hasattr(result, 'diagnoses') and result.diagnoses:
                for d in result.diagnoses[:5]:
                    diagnoses.append({
                        'diagnosis': d.failure_mode if hasattr(d, 'failure_mode') else str(d),
                        'confidence': d.confidence if hasattr(d, 'confidence') else 0.5,
                        'system': d.system if hasattr(d, 'system') else 'unknown',
                    })
        except Exception as e:
            logger.warning(f"ML inference not available: {e}")
        
        # Fallback to rule-based if ML didn't produce results
        if not diagnoses:
            diagnoses = self._rule_based_analyze(dtc_list, pids, symptom_list)
        
        # Save diagnoses to session as hypotheses
        session.phase = DiagnosticPhase.ANALYZING
        for d in diagnoses[:5]:  # Top 5
            evidence = []
            if dtc_list:
                evidence.append(f"DTCs: {', '.join(dtc_list[:3])}")
            if pids.get('coolant_temp'):
                evidence.append(f"Coolant: {pids['coolant_temp']:.0f}°F")
            if pids.get('ltft_b1'):
                evidence.append(f"LTFT B1: {pids['ltft_b1']:+.1f}%")
            
            session.add_hypothesis(
                diagnosis=d['diagnosis'],
                system=d['system'],
                confidence=d['confidence'],
                evidence=evidence
            )
        
        session.log_action(f"Analyzed data: top diagnosis = {diagnoses[0]['diagnosis']} ({diagnoses[0]['confidence']*100:.0f}%)")
        
        # Format output
        if not diagnoses:
            return "⚠️ Insufficient data for analysis. Gather more DTCs and PID readings."
        
        output = ["🧠 **Diagnostic Analysis:**\n"]
        
        # Show what data was used
        output.append(f"_Analyzed: {len(dtc_list)} DTCs, {len(pids)} PIDs, {len(symptom_list)} symptoms_\n")
        
        for i, d in enumerate(diagnoses, 1):
            conf = d['confidence'] * 100
            emoji = "🔴" if conf >= 70 else "🟡" if conf >= 40 else "⚪"
            output.append(f"{emoji} **{i}. {self._format_diagnosis(d['diagnosis'])}**")
            output.append(f"   Confidence: {conf:.0f}%")
            output.append(f"   System: {d['system'].title()}")
            output.append("")
        
        # Add reasoning hints
        output.append("💡 **Reasoning:**")
        ct = pids.get('coolant_temp', 0)
        lt1 = pids.get('ltft_b1', 0)
        tr = pids.get('temp_rise_rate', 0)
        
        if ct and ct > 220:
            output.append(f"  • Coolant temp {ct:.0f}°F is above normal (195-220°F)")
        if lt1 and abs(lt1) > 10:
            direction = "lean" if lt1 > 0 else "rich"
            output.append(f"  • LTFT B1 at {lt1:+.1f}% indicates {direction} condition")
        if tr and tr > 30:
            output.append(f"  • Rapid temp rise ({tr:.0f}°F/min) suggests restricted flow")
        if 'P0217' in dtc_list:
            output.append("  • P0217 confirms ECU detected overtemperature")
        if 'P0128' in dtc_list:
            output.append("  • P0128 indicates thermostat not regulating properly")
        
        output.append("\n⚠️ Confirm with physical inspection before repair.")
        output.append("\n💡 **Tip:** Call diagnostic_session_status() to see full session context")
        
        return '\n'.join(output)
    
    def _rule_based_analyze(
        self, 
        dtcs: list, 
        pids: dict, 
        symptoms: list
    ) -> list:
        """Rule-based fallback analysis."""
        diagnoses = []
        
        coolant_temp = pids.get('coolant_temp', 0)
        ltft_b1 = pids.get('ltft_b1', 0)
        ltft_b2 = pids.get('ltft_b2', 0)
        stft_b1 = pids.get('stft_b1', 0)
        stft_b2 = pids.get('stft_b2', 0)
        temp_rise_rate = pids.get('temp_rise_rate', 0)
        maf = pids.get('maf', 0)
        map_kpa = pids.get('map', 0)
        rpm = pids.get('rpm', 0)
        
        # Cooling system analysis
        if 'P0217' in dtcs or coolant_temp > 230:
            if temp_rise_rate and temp_rise_rate > 30:
                diagnoses.append({
                    'diagnosis': 'thermostat_stuck_closed',
                    'confidence': 0.80,
                    'system': 'cooling'
                })
            else:
                diagnoses.append({
                    'diagnosis': 'thermostat_stuck_closed',
                    'confidence': 0.55,
                    'system': 'cooling'
                })
            diagnoses.append({
                'diagnosis': 'water_pump_failure',
                'confidence': 0.25,
                'system': 'cooling'
            })
            diagnoses.append({
                'diagnosis': 'radiator_blocked',
                'confidence': 0.20,
                'system': 'cooling'
            })
            diagnoses.append({
                'diagnosis': 'coolant_leak',
                'confidence': 0.15,
                'system': 'cooling'
            })
        
        elif 'P0128' in dtcs or ('overheating' not in symptoms and coolant_temp and coolant_temp < 160):
            diagnoses.append({
                'diagnosis': 'thermostat_stuck_open',
                'confidence': 0.65,
                'system': 'cooling'
            })
        
        # O2 Sensor analysis
        if 'P0130' in dtcs or 'P0131' in dtcs:  # O2 sensor B1S1 issues
            diagnoses.append({
                'diagnosis': 'o2_sensor_stuck_lean',
                'confidence': 0.55,
                'system': 'fuel'
            })
        elif 'P0132' in dtcs:  # O2 sensor high voltage
            diagnoses.append({
                'diagnosis': 'o2_sensor_stuck_rich',
                'confidence': 0.55,
                'system': 'fuel'
            })
        elif 'P0133' in dtcs:  # O2 sensor slow response
            diagnoses.append({
                'diagnosis': 'o2_sensor_lazy',
                'confidence': 0.60,
                'system': 'fuel'
            })
        
        # Catalytic converter analysis
        if 'P0420' in dtcs or 'P0430' in dtcs:
            diagnoses.append({
                'diagnosis': 'catalytic_converter_degraded',
                'confidence': 0.65,
                'system': 'emissions'
            })
            diagnoses.append({
                'diagnosis': 'o2_sensor_lazy',
                'confidence': 0.25,
                'system': 'fuel'
            })
        
        # EGR analysis
        if 'P0401' in dtcs:  # EGR insufficient flow
            diagnoses.append({
                'diagnosis': 'egr_stuck_closed',
                'confidence': 0.60,
                'system': 'emissions'
            })
        elif 'P0402' in dtcs:  # EGR excessive flow
            diagnoses.append({
                'diagnosis': 'egr_stuck_open',
                'confidence': 0.65,
                'system': 'emissions'
            })
        
        # EVAP system analysis  
        if any(d in dtcs for d in ['P0440', 'P0442', 'P0455', 'P0456']):
            diagnoses.append({
                'diagnosis': 'evap_leak_small',
                'confidence': 0.55,
                'system': 'emissions'
            })
        elif 'P0441' in dtcs:  # EVAP incorrect purge flow
            diagnoses.append({
                'diagnosis': 'evap_purge_stuck_open',
                'confidence': 0.50,
                'system': 'emissions'
            })
        
        # Fuel system analysis - lean conditions
        if any(d in dtcs for d in ['P0171', 'P0174']) or (ltft_b1 > 15 and ltft_b2 > 15):
            diagnoses.append({
                'diagnosis': 'vacuum_leak',
                'confidence': 0.55,
                'system': 'fuel'
            })
            diagnoses.append({
                'diagnosis': 'maf_sensor_contaminated',
                'confidence': 0.40,
                'system': 'fuel'
            })
            diagnoses.append({
                'diagnosis': 'intake_gasket_leak',
                'confidence': 0.30,
                'system': 'fuel'
            })
            diagnoses.append({
                'diagnosis': 'exhaust_leak_pre_cat',
                'confidence': 0.20,
                'system': 'exhaust'
            })
        
        # Fuel system - rich conditions
        elif any(d in dtcs for d in ['P0172', 'P0175']) or (ltft_b1 < -15 and ltft_b2 < -15):
            diagnoses.append({
                'diagnosis': 'fuel_pressure_high',
                'confidence': 0.45,
                'system': 'fuel'
            })
            diagnoses.append({
                'diagnosis': 'injector_leaking',
                'confidence': 0.35,
                'system': 'fuel'
            })
            diagnoses.append({
                'diagnosis': 'o2_sensor_stuck_lean',
                'confidence': 0.30,
                'system': 'fuel'
            })
        
        # MAF/MAP sensor analysis
        if 'P0101' in dtcs or 'P0102' in dtcs or 'P0103' in dtcs:
            diagnoses.append({
                'diagnosis': 'maf_sensor_contaminated',
                'confidence': 0.65,
                'system': 'fuel'
            })
            diagnoses.append({
                'diagnosis': 'air_filter_clogged',
                'confidence': 0.25,
                'system': 'fuel'
            })
        
        if 'P0106' in dtcs or 'P0107' in dtcs or 'P0108' in dtcs:
            diagnoses.append({
                'diagnosis': 'map_sensor_drift',
                'confidence': 0.60,
                'system': 'fuel'
            })
        
        # Knock sensor analysis
        if 'P0325' in dtcs or 'P0330' in dtcs:
            diagnoses.append({
                'diagnosis': 'knock_sensor_failed',
                'confidence': 0.70,
                'system': 'ignition'
            })
        
        # Misfire analysis
        misfire_codes = [d for d in dtcs if d.startswith('P030')]
        if misfire_codes:
            if 'P0300' in misfire_codes:  # Random/multiple misfire
                diagnoses.append({
                    'diagnosis': 'vacuum_leak',
                    'confidence': 0.40,
                    'system': 'fuel'
                })
                diagnoses.append({
                    'diagnosis': 'low_compression_cylinder',
                    'confidence': 0.25,
                    'system': 'engine'
                })
            else:  # Specific cylinder misfire P0301-P0308
                diagnoses.append({
                    'diagnosis': 'spark_plug_worn',
                    'confidence': 0.50,
                    'system': 'ignition'
                })
                diagnoses.append({
                    'diagnosis': 'ignition_coil_failing',
                    'confidence': 0.35,
                    'system': 'ignition'
                })
                diagnoses.append({
                    'diagnosis': 'clogged_injector',
                    'confidence': 0.25,
                    'system': 'fuel'
                })
                diagnoses.append({
                    'diagnosis': 'low_compression_cylinder',
                    'confidence': 0.20,
                    'system': 'engine'
                })
        
        return sorted(diagnoses, key=lambda x: -x['confidence'])
    
    def _format_diagnosis(self, diagnosis: str) -> str:
        """Format diagnosis ID to readable text."""
        return diagnosis.replace('_', ' ').title()


# For direct script usage
if __name__ == "__main__":
    async def main():
        tools = Tools()
        print(await tools.elm327_connect('wifi', '192.168.0.10:35000'))
        print(await tools.elm327_read_dtcs())
        print(await tools.elm327_read_fuel_trims())
        print(await tools.elm327_disconnect())
    
    asyncio.run(main())
