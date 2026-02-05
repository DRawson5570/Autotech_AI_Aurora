"""
Open WebUI Tool for Physics-Based Diagnostics.

This tool uses first-principles physics models to diagnose automotive problems.
Instead of pattern matching, it simulates how faults affect system behavior
and matches observed symptoms to predicted outcomes.

"Diagnosis becomes natural because the AI thinks like the system itself."
"""

import logging
from typing import Optional, Any, Callable, Awaitable, List, Dict

from pydantic import BaseModel, Field

log = logging.getLogger("physics_diagnostics")


class Tools:
    """Open WebUI tool for physics-based diagnostics."""
    
    class Valves(BaseModel):
        """Configuration for the tool."""
        CONFIDENCE_THRESHOLD: float = Field(
            default=0.6,
            description="Minimum confidence to show a diagnosis candidate"
        )
        MAX_CANDIDATES: int = Field(
            default=5,
            description="Maximum number of diagnostic candidates to show"
        )
        SHOW_PHYSICS: bool = Field(
            default=True,
            description="Show physics explanation for each diagnosis"
        )
        USE_ML_MODEL: bool = Field(
            default=True,
            description="Use trained ML model for diagnosis (if available)"
        )
        ML_MODEL_PATH: str = Field(
            default="/tmp/pd_full_model.pt",
            description="Path to trained PyTorch model file"
        )
    
    def __init__(self):
        self.valves = self.Valves()
        self._engine = None
        self._ml_inference = None
    
    def _get_engine(self):
        """Lazy-load the diagnostic engine."""
        if self._engine is None:
            from addons.predictive_diagnostics.physics.diagnostic_engine import DiagnosticEngine
            self._engine = DiagnosticEngine()
        return self._engine
    
    def _get_ml_inference(self):
        """Lazy-load the ML inference engine."""
        if self._ml_inference is None and self.valves.USE_ML_MODEL:
            import os
            if os.path.exists(self.valves.ML_MODEL_PATH):
                try:
                    from addons.predictive_diagnostics.ml.inference import DiagnosticInference
                    self._ml_inference = DiagnosticInference.load(self.valves.ML_MODEL_PATH)
                    log.info(f"ML model loaded from {self.valves.ML_MODEL_PATH}")
                except Exception as e:
                    log.warning(f"Failed to load ML model: {e}")
                    self._ml_inference = None
        return self._ml_inference
    
    async def physics_diagnose(
        self,
        dtcs: str = "",
        complaints: str = "",
        coolant_temp_c: float = None,
        rpm: int = None,
        vehicle_speed_mph: float = None,
        battery_voltage: float = None,
        fuel_pressure_psi: float = None,
        stft_percent: float = None,
        ltft_percent: float = None,
        maf_gs: float = None,
        o2_voltage: float = None,
        __user__: dict = None,
        __event_emitter__: Optional[Callable[[dict], Awaitable[None]]] = None,
    ) -> str:
        """
        Diagnose automotive problems using physics-based simulation.
        
        This tool uses first-principles physics models of automotive systems
        (cooling, fuel, ignition, charging) to diagnose problems. It simulates
        how each potential fault would affect the system and compares to
        your observations.
        
        **Supported Systems:**
        - 🌡️ Cooling: Overheating, no heat, temp sensor issues
        - ⛽ Fuel: Rough idle, poor fuel economy, hard starts
        - ⚡ Ignition: Misfires, no start, weak spark
        - 🔋 Charging: Dead battery, dim lights, slow crank
        
        Args:
            dtcs: Diagnostic trouble codes, comma-separated
                  Examples: "P0217, P0128" (cooling), "P0171, P0174" (fuel lean),
                  "P0300, P0301" (misfire), "P0562" (low voltage)
            complaints: Customer complaints, comma-separated
                        Examples: "overheating", "rough idle", "hard start",
                        "poor fuel economy", "engine dies", "misfire"
            coolant_temp_c: Coolant temperature in Celsius (normal: 85-95°C)
            rpm: Engine RPM (idle: 600-900, cruise: 1500-3000)
            vehicle_speed_mph: Vehicle speed in MPH
            battery_voltage: System voltage (normal: 13.5-14.5V running)
            fuel_pressure_psi: Fuel rail pressure (typical: 35-65 psi)
            stft_percent: Short-term fuel trim % (-10 to +10 normal)
            ltft_percent: Long-term fuel trim % (-10 to +10 normal)
            maf_gs: Mass airflow in grams/second
            o2_voltage: Upstream O2 sensor voltage (0.1-0.9V cycling)
        
        Returns:
            Diagnostic report with ranked causes, physics explanation,
            verification tests, and repair recommendations
        """
        # Emit status
        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {
                    "description": "🔬 Running physics simulation...",
                    "done": False
                }
            })
        
        try:
            engine = self._get_engine()
            
            # Parse DTCs
            dtc_list = [d.strip().upper() for d in dtcs.split(",") if d.strip()] if dtcs else []
            
            # Parse complaints
            complaint_list = [c.strip().lower() for c in complaints.split(",") if c.strip()] if complaints else []
            
            # Build PID dictionary
            pids = {}
            if coolant_temp_c is not None:
                pids["coolant_temp_c"] = coolant_temp_c
            if rpm is not None:
                pids["rpm"] = rpm
            if vehicle_speed_mph is not None:
                pids["vehicle_speed_mph"] = vehicle_speed_mph
            if battery_voltage is not None:
                pids["battery_voltage"] = battery_voltage
            if fuel_pressure_psi is not None:
                pids["fuel_pressure_psi"] = fuel_pressure_psi
            if stft_percent is not None:
                pids["stft_percent"] = stft_percent
            if ltft_percent is not None:
                pids["ltft_percent"] = ltft_percent
            if maf_gs is not None:
                pids["maf_gs"] = maf_gs
            if o2_voltage is not None:
                pids["o2_voltage"] = o2_voltage
            
            # Validate we have something to diagnose
            if not dtc_list and not complaint_list:
                return (
                    "## ⚠️ No Input Provided\n\n"
                    "Please provide at least one of:\n"
                    "- **DTCs**: Diagnostic trouble codes (e.g., P0217, P0171)\n"
                    "- **Complaints**: Customer concerns (e.g., overheating, rough idle)\n\n"
                    "**Example:**\n"
                    "```\n"
                    "dtcs: P0217\n"
                    "complaints: overheating, steam from hood\n"
                    "coolant_temp_c: 115\n"
                    "```"
                )
            
            # Run diagnosis
            result = engine.diagnose(
                dtcs=dtc_list,
                pids=pids,
                complaints=complaint_list
            )
            
            # Get candidates from result
            candidates = result.candidates
            
            # Try ML model for additional insights
            ml_result = None
            ml_inference = self._get_ml_inference()
            if ml_inference:
                try:
                    # Build observations for ML
                    observations = dict(pids)  # Copy PIDs
                    if dtc_list:
                        observations["dtcs"] = dtc_list
                    if complaint_list:
                        observations["symptoms"] = complaint_list
                    
                    ml_result = ml_inference.diagnose_from_observations(
                        observations, top_k=self.valves.MAX_CANDIDATES
                    )
                    log.info(f"ML diagnosis: {ml_result.hypotheses[0]['failure_id']} ({ml_result.confidence:.1%})")
                except Exception as e:
                    log.warning(f"ML inference failed: {e}")
            
            # Filter by confidence threshold
            candidates = [c for c in candidates if c.confidence >= self.valves.CONFIDENCE_THRESHOLD]
            candidates = candidates[:self.valves.MAX_CANDIDATES]
            
            if not candidates:
                return (
                    "## 🤔 No Strong Diagnosis\n\n"
                    f"No diagnosis candidates found above {self.valves.CONFIDENCE_THRESHOLD*100:.0f}% confidence.\n\n"
                    "**Suggestions:**\n"
                    "- Provide more sensor readings (PIDs)\n"
                    "- Check for additional DTCs\n"
                    "- Describe symptoms in more detail\n"
                )
            
            # Format response
            response = self._format_diagnosis(
                candidates, dtc_list, complaint_list, pids, ml_result
            )
            
            if __event_emitter__:
                top = candidates[0]
                status_msg = f"✅ Top diagnosis: {top.fault_type.replace('_', ' ').title()} ({top.confidence*100:.0f}%)"
                await __event_emitter__({
                    "type": "status",
                    "data": {"description": status_msg, "done": True}
                })
            
            return response
            
        except Exception as e:
            log.exception("Physics diagnostic error")
            error_msg = f"❌ Diagnostic error: {str(e)}"
            if __event_emitter__:
                await __event_emitter__({
                    "type": "status",
                    "data": {"description": error_msg, "done": True}
                })
            return error_msg
    
    def _format_diagnosis(
        self,
        candidates: List,
        dtcs: List[str],
        complaints: List[str],
        pids: Dict[str, float],
        ml_result = None
    ) -> str:
        """Format diagnostic results as markdown."""
        
        # Header
        lines = ["# 🔧 Physics-Based Diagnostic Report\n"]
        
        # Input summary
        lines.append("## Input")
        if dtcs:
            lines.append(f"**DTCs:** {', '.join(dtcs)}")
        if complaints:
            lines.append(f"**Complaints:** {', '.join(complaints)}")
        if pids:
            pid_str = ", ".join(f"{k}={v}" for k, v in pids.items())
            lines.append(f"**Readings:** {pid_str}")
        lines.append("")
        
        # Top diagnosis
        top = candidates[0]
        confidence_bar = self._confidence_bar(top.confidence)
        
        # Handle system being either string or enum
        system_name = top.system.value if hasattr(top.system, 'value') else str(top.system)
        
        lines.append("## 🎯 Most Likely Cause\n")
        lines.append(f"### {top.fault_id.replace('_', ' ').title()}")
        lines.append(f"**Confidence:** {confidence_bar} {top.confidence*100:.0f}%\n")
        lines.append(f"**System:** {system_name.title()}\n")
        lines.append(f"**Description:** {top.description}\n")
        
        # Physics explanation - predicted_state instead of physics_trace
        if self.valves.SHOW_PHYSICS and top.predicted_state:
            lines.append("### 🔬 Predicted State (if this fault)")
            lines.append("```")
            if isinstance(top.predicted_state, dict):
                for key, value in top.predicted_state.items():
                    if isinstance(value, float):
                        lines.append(f"{key}: {value:.2f}")
                    else:
                        lines.append(f"{key}: {value}")
            else:
                lines.append(str(top.predicted_state))
            lines.append("```\n")
        
        # Verification tests
        if top.verification_tests:
            lines.append("### ✅ Verification Tests")
            for test in top.verification_tests[:3]:
                lines.append(f"> {test}\n")
        
        # Repair actions
        if top.repair_actions:
            lines.append("### 🔧 Repair Recommendations")
            for action in top.repair_actions:
                lines.append(f"- {action}")
            if top.estimated_repair_cost:
                lines.append(f"\n**Estimated Cost:** {top.estimated_repair_cost}\n")
        
        # Alternative diagnoses
        if len(candidates) > 1:
            lines.append("\n## 📋 Other Possibilities\n")
            lines.append("| Rank | Fault | Confidence | System |")
            lines.append("|------|-------|------------|--------|")
            for i, cand in enumerate(candidates[1:], 2):
                fault_name = cand.fault_id.replace('_', ' ').title()
                conf = f"{cand.confidence*100:.0f}%"
                sys_name = cand.system.value if hasattr(cand.system, 'value') else str(cand.system)
                lines.append(f"| {i} | {fault_name} | {conf} | {sys_name.title()} |")
            lines.append("")
            
            # Show verification tests for alternatives
            lines.append("### Differential Tests")
            for i, cand in enumerate(candidates[1:], 2):
                if cand.verification_tests:
                    fault_name = cand.fault_id.replace('_', ' ').title()
                    lines.append(f"- **{fault_name}:** {cand.verification_tests[0]}")
        
        # ML Model insights (if available)
        if ml_result and ml_result.hypotheses:
            lines.append("\n## 🤖 ML Model Analysis\n")
            lines.append("*Pattern-based diagnosis from trained neural network*\n")
            lines.append("| Rank | Fault | Probability |")
            lines.append("|------|-------|-------------|")
            for i, hyp in enumerate(ml_result.hypotheses[:5], 1):
                fault_name = hyp['failure_id'].replace('_', ' ').title()
                prob = f"{hyp['probability']*100:.1f}%"
                lines.append(f"| {i} | {fault_name} | {prob} |")
            
            if ml_result.is_ambiguous:
                lines.append("\n⚠️ **Note:** ML model shows uncertainty - multiple failures are possible.")
            
            if ml_result.recommended_tests:
                lines.append("\n**ML-Recommended Discriminating Tests:**")
                for test in ml_result.recommended_tests[:3]:
                    lines.append(f"- {test}")
        
        lines.append("\n---")
        lines.append("*Diagnosis generated by physics-based simulation engine*")
        if ml_result:
            lines.append("*with ML model enhancement*")
        
        return "\n".join(lines)
    
    def _confidence_bar(self, confidence: float) -> str:
        """Create a visual confidence bar."""
        filled = int(confidence * 10)
        empty = 10 - filled
        return "█" * filled + "░" * empty
    
    async def get_supported_dtcs(
        self,
        system: str = "",
        __user__: dict = None,
        __event_emitter__: Optional[Callable[[dict], Awaitable[None]]] = None,
    ) -> str:
        """
        List DTCs supported by the physics diagnostic engine.
        
        Use this to see what diagnostic trouble codes the physics
        engine can analyze.
        
        Args:
            system: Filter by system (optional)
                    Options: "cooling", "fuel", "ignition", "charging"
        
        Returns:
            Table of supported DTCs with descriptions
        """
        from addons.predictive_diagnostics.physics.diagnostic_engine import DTC_FAULT_MAP
        
        lines = ["# 📋 Supported DTCs\n"]
        
        # Group by system
        by_system: Dict[str, List[tuple]] = {}
        for dtc, info in DTC_FAULT_MAP.items():
            sys = info["system"]
            if system and sys != system.lower():
                continue
            if sys not in by_system:
                by_system[sys] = []
            by_system[sys].append((dtc, info))
        
        system_icons = {
            "cooling": "🌡️",
            "fuel": "⛽",
            "ignition": "⚡",
            "charging": "🔋",
        }
        
        for sys, dtcs in sorted(by_system.items()):
            icon = system_icons.get(sys, "🔧")
            lines.append(f"## {icon} {sys.title()} System\n")
            lines.append("| DTC | Description | Possible Faults |")
            lines.append("|-----|-------------|-----------------|")
            for dtc, info in sorted(dtcs):
                desc = info.get("description", "")
                faults = ", ".join(f.replace("_", " ").title() for f in info.get("faults", []))
                lines.append(f"| {dtc} | {desc} | {faults} |")
            lines.append("")
        
        if not by_system:
            lines.append("No DTCs found for the specified system.\n")
            lines.append("Available systems: cooling, fuel, ignition, charging")
        
        return "\n".join(lines)
    
    async def explain_fault(
        self,
        fault: str,
        __user__: dict = None,
        __event_emitter__: Optional[Callable[[dict], Awaitable[None]]] = None,
    ) -> str:
        """
        Get detailed explanation of a fault type.
        
        Explains what causes a fault, how to verify it, and how to repair it.
        
        Args:
            fault: Fault name (e.g., "thermostat_stuck_closed", "fuel_pump_weak")
                   Use underscores or spaces between words.
        
        Returns:
            Detailed fault explanation with verification and repair steps
        """
        from addons.predictive_diagnostics.physics.diagnostic_engine import FAULT_DETAILS
        
        # Normalize fault name
        fault_key = fault.lower().replace(" ", "_")
        
        if fault_key not in FAULT_DETAILS:
            # Try to find partial match
            matches = [k for k in FAULT_DETAILS.keys() if fault_key in k or k in fault_key]
            if matches:
                lines = [f"## ❓ Fault '{fault}' not found\n"]
                lines.append("Did you mean one of these?")
                for m in matches[:5]:
                    lines.append(f"- `{m}`")
                return "\n".join(lines)
            else:
                all_faults = list(FAULT_DETAILS.keys())
                lines = [f"## ❓ Fault '{fault}' not found\n"]
                lines.append("Available faults:")
                for f in sorted(all_faults)[:20]:
                    lines.append(f"- `{f}`")
                if len(all_faults) > 20:
                    lines.append(f"- ... and {len(all_faults)-20} more")
                return "\n".join(lines)
        
        details = FAULT_DETAILS[fault_key]
        
        lines = [f"# 🔧 {fault_key.replace('_', ' ').title()}\n"]
        lines.append(f"**Description:** {details.get('description', 'N/A')}\n")
        lines.append("## ✅ Verification Test")
        lines.append(f"{details.get('verification', 'N/A')}\n")
        lines.append("## 🔧 Repair Action")
        lines.append(f"{details.get('repair', 'N/A')}\n")
        if details.get("cost"):
            lines.append(f"**Estimated Cost:** {details['cost']}")
        
        return "\n".join(lines)
