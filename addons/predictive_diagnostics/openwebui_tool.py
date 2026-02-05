"""
Open WebUI Tool for Predictive Diagnostics.

This tool provides AI-powered automotive diagnostic reasoning.
Give it symptoms, DTCs, and sensor readings - it tells you
the most likely causes with confidence scores.

"Cut 1-2 hour diagnostic to 5 minutes"
"""

import logging
import time
from typing import Optional, Any, Callable, Awaitable, List

from pydantic import BaseModel, Field

# Configure logger for predictive diagnostics
log = logging.getLogger("predictive_diagnostics")

# Ensure we have at least INFO level logging
if not log.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    log.addHandler(handler)
    log.setLevel(logging.INFO)


class Tools:
    """Open WebUI tool for predictive diagnostics."""
    
    class Valves(BaseModel):
        """Configuration for the tool."""
        CONFIDENCE_THRESHOLD: float = Field(
            default=0.7,
            description="Confidence level to consider diagnosis conclusive"
        )
        MAX_ALTERNATIVES: int = Field(
            default=3,
            description="Maximum number of alternative diagnoses to show"
        )
    
    def __init__(self):
        self.valves = self.Valves()
        self._engine = None
    
    def _get_engine(self):
        """Lazy-load the diagnostic engine."""
        if self._engine is None:
            log.info("Initializing DiagnosticEngine (first use)")
            from addons.predictive_diagnostics.integration import DiagnosticEngine
            self._engine = DiagnosticEngine(
                confidence_threshold=self.valves.CONFIDENCE_THRESHOLD
            )
            log.info(f"DiagnosticEngine initialized with confidence_threshold={self.valves.CONFIDENCE_THRESHOLD}")
        return self._engine
    
    async def diagnose(
        self,
        symptoms: str,
        dtcs: str = "",
        sensor_readings: str = "",
        __user__: dict = None,
        __event_emitter__: Optional[Callable[[dict], Awaitable[None]]] = None,
    ) -> str:
        """
        Diagnose automotive problems using AI-powered reasoning.
        
        This tool uses Bayesian inference to identify the most likely
        cause of automotive issues. Give it what you know and it will:
        - Identify the most probable failure
        - Show confidence levels
        - Suggest the next diagnostic test
        - Recommend repair actions
        
        Best for: Cooling system issues (overheating, no heat, temp problems)
        
        Args:
            symptoms: Customer complaints or observations, comma-separated
                      Examples: "overheating", "no heat", "running cold",
                      "fan not running", "coolant leak", "steam from hood"
            dtcs: Diagnostic trouble codes, comma-separated (optional)
                  Examples: "P0217" (overtemp), "P0128" (thermostat),
                  "P0480" (fan circuit), "P0117/P0118" (ECT sensor)
            sensor_readings: ALL sensor values as "name:value" pairs, comma-separated.
                            IMPORTANT: Pass ALL sensor readings from the user query exactly as provided.
                            Do NOT omit any sensor values. Include every name:value pair.
                            Examples: "engine_rpm:650, short_term_fuel_trim_b1:18, maf:3.2, coolant_temp:90"
        
        Returns:
            Diagnostic report with probable causes and recommendations
        """
        from addons.predictive_diagnostics.integration import SensorReading
        
        # Log incoming request
        user_id = __user__.get("id", "unknown") if __user__ else "unknown"
        user_name = __user__.get("name", "unknown") if __user__ else "unknown"
        log.info(f"=== DIAGNOSE REQUEST ===")
        log.info(f"User: {user_name} ({user_id})")
        log.info(f"Symptoms: {symptoms}")
        log.info(f"DTCs: {dtcs}")
        log.info(f"Sensor readings: {sensor_readings}")
        
        start_time = time.time()
        
        # Emit status
        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {
                    "description": "Analyzing symptoms...",
                    "done": False
                }
            })
        
        try:
            engine = self._get_engine()
            
            import re

            # If the user pasted a combined prompt into the symptoms field (e.g.,
            # "DTCs: P0300,P0171. Sensor readings: engine_rpm:650, short_term_fuel_trim_b1:18,..."),
            # try to extract dtcs and sensor readings automatically so the diagnosis uses them.

            text = symptoms.strip()

            # Extract DTCs from symptoms text when dtcs parameter is blank
            dtc_list = [d.strip().upper() for d in dtcs.split(",") if d.strip()]
            if not dtc_list:
                m = re.search(r"dtcs?:\s*([A-Z0-9_,\s]+)", text, re.I)
                if m:
                    dtc_list = [d.strip().upper() for d in m.group(1).split(",") if d.strip()]
                    # remove dtc segment from text so it doesn't pollute symptoms
                    text = text[:m.start()] + text[m.end():]

            # Extract sensors from both the sensor_readings parameter AND the symptoms text
            # (LLM may only extract partial sensors, so we merge both sources)
            sensors = []
            seen_sensors = set()
            
            # First, parse from explicit sensor_readings parameter if provided
            if sensor_readings:
                for reading in sensor_readings.split(","):
                    if ":" in reading:
                        name, value = reading.split(":", 1)
                        name = name.strip().lower()
                        try:
                            if name not in seen_sensors:
                                sensors.append(SensorReading(
                                    name=name,
                                    value=float(value.strip())
                                ))
                                seen_sensors.add(name)
                        except ValueError:
                            pass  # Skip invalid readings
            
            # Also look for 'sensor readings' block in the text and merge
            # (The LLM sometimes only extracts partial sensors)
            m2 = re.search(r"sensor\s*readings?:\s*(.+?)(?:\.\s+[A-Z]|\n|$)", text, re.I)
            if m2:
                block = m2.group(1)
                # remove the block from symptoms text
                text = text[:m2.start()] + text[m2.end():]
                
                # parse name:value pairs from block
                for match in re.finditer(r"([a-zA-Z0-9_]+)\s*:\s*([0-9]*\.?[0-9]+)", block):
                    name = match.group(1).strip().lower()
                    val = match.group(2)
                    try:
                        if name not in seen_sensors:
                            sensors.append(SensorReading(name=name, value=float(val)))
                            seen_sensors.add(name)
                    except ValueError:
                        continue

            # Build symptom list from the cleaned text (remove trailing punctuation and split by commas)
            symptom_list = [s.strip() for s in re.split(r"[,;]\s*", text) if s.strip()]

            
            # Run diagnosis
            log.debug(f"Running diagnosis with {len(symptom_list)} symptoms, {len(dtc_list)} DTCs, {len(sensors)} sensors")
            result = engine.diagnose(
                symptoms=symptom_list,
                dtcs=dtc_list,
                sensors=sensors if sensors else None
            )
            
            # Log results
            elapsed = time.time() - start_time
            log.info(f"=== DIAGNOSIS RESULT ===")
            log.info(f"Primary: {result.primary_failure} ({result.confidence*100:.1f}% confidence)")
            log.info(f"Alternatives: {[(f, f'{c*100:.1f}%') for f, c in result.alternatives[:3]]}")
            log.info(f"Phase: {result.phase.value}")
            log.info(f"Elapsed: {elapsed*1000:.0f}ms")
            
            # Format response
            response = self._format_diagnosis(result, symptom_list, dtc_list, sensors)
            
            if __event_emitter__:
                status_msg = f"Diagnosis: {result.primary_failure.replace('_', ' ').title()} ({result.confidence*100:.0f}% confidence)"
                await __event_emitter__({
                    "type": "status",
                    "data": {"description": status_msg, "done": True}
                })
            
            return response
            
        except Exception as e:
            elapsed = time.time() - start_time
            log.exception(f"Diagnostic error after {elapsed*1000:.0f}ms: {str(e)}")
            error_msg = f"Diagnostic error: {str(e)}"
            if __event_emitter__:
                await __event_emitter__({
                    "type": "status",
                    "data": {"description": error_msg, "done": True}
                })
            return error_msg
    
    async def diagnose_interactive(
        self,
        action: str,
        data: str = "",
        __user__: dict = None,
        __event_emitter__: Optional[Callable[[dict], Awaitable[None]]] = None,
    ) -> str:
        """
        Interactive diagnostic session with step-by-step guidance.
        
        Use this for a more thorough diagnosis with test recommendations.
        The system will guide you through the diagnostic process.
        
        Args:
            action: What to do - one of:
                    "start" - Begin new session with initial symptoms
                    "add" - Add observation/test result
                    "test" - Get recommended next test
                    "conclude" - Get final diagnosis
            data: Data for the action:
                  For "start": comma-separated symptoms (e.g., "overheating, steam")
                  For "add": observation (e.g., "fan_running" or "P0217")
        
        Returns:
            Session status and recommendations
        """
        try:
            user_id = __user__.get('id', 'unknown') if __user__ else 'unknown'
            user_name = __user__.get('name', 'unknown') if __user__ else 'unknown'
            log.info(f"Interactive session: action='{action}' data='{data}' user={user_name} ({user_id})")
            
            engine = self._get_engine()
            
            # Get or create session (stored in user context)
            session_key = f"diag_session_{__user__.get('id', 'default')}" if __user__ else "diag_session_default"
            
            if action == "start":
                # Start new session
                session = engine.start_session()
                
                # Add initial symptoms
                symptoms = [s.strip() for s in data.split(",") if s.strip()]
                for symptom in symptoms:
                    session.add_symptom(symptom)
                
                # Store session (using class attribute as simple storage)
                if not hasattr(self, '_sessions'):
                    self._sessions = {}
                self._sessions[session_key] = session
                
                # Get initial assessment
                suspects = session.get_top_suspects(5)
                test_rec = session.recommend_test()
                
                response = "# 🔧 Diagnostic Session Started\n\n"
                response += f"**Symptoms:** {', '.join(symptoms)}\n\n"
                response += "## Initial Assessment\n\n"
                response += "| Suspect | Probability |\n|---------|-------------|\n"
                for failure, prob in suspects:
                    response += f"| {failure.replace('_', ' ').title()} | {prob*100:.1f}% |\n"
                
                if test_rec:
                    response += f"\n## 🔍 Recommended Test\n\n"
                    response += f"**{test_rec[2]}**\n\n"
                    response += f"_Information gain: {test_rec[1]:.3f} bits_\n\n"
                    response += "Use `diagnose_interactive(action='add', data='result')` to record the test result."
                
                log.info(f"Session started: symptoms={symptoms} top_suspect={suspects[0][0]}@{suspects[0][1]*100:.1f}%")
                return response
                
            elif action == "add":
                # Add observation to existing session
                if not hasattr(self, '_sessions') or session_key not in self._sessions:
                    return "No active session. Use `action='start'` to begin."
                
                session = self._sessions[session_key]
                
                # Check if it's a DTC
                if data.upper().startswith("P"):
                    session.add_dtc(data)
                else:
                    session.add_observation(data)
                
                # Get updated assessment
                suspects = session.get_top_suspects(5)
                test_rec = session.recommend_test()
                uncertainty = session.get_uncertainty()
                
                response = f"# 📝 Added: {data}\n\n"
                response += f"**Uncertainty:** {uncertainty:.2f} bits\n\n"
                response += "## Updated Assessment\n\n"
                response += "| Suspect | Probability |\n|---------|-------------|\n"
                for failure, prob in suspects:
                    response += f"| {failure.replace('_', ' ').title()} | {prob*100:.1f}% |\n"
                
                if suspects[0][1] >= self.valves.CONFIDENCE_THRESHOLD:
                    response += f"\n✅ **High confidence reached!** Use `action='conclude'` for final diagnosis."
                elif test_rec:
                    response += f"\n## 🔍 Next Recommended Test\n\n"
                    response += f"**{test_rec[2]}**\n"
                
                return response
                
            elif action == "test":
                # Get test recommendation
                if not hasattr(self, '_sessions') or session_key not in self._sessions:
                    return "No active session. Use `action='start'` to begin."
                
                session = self._sessions[session_key]
                test_rec = session.recommend_test()
                
                if test_rec:
                    return f"## 🔍 Recommended Test\n\n**{test_rec[2]}**\n\n_Information gain: {test_rec[1]:.3f} bits_"
                else:
                    return "No further tests recommended. Use `action='conclude'` for final diagnosis."
                
            elif action == "conclude":
                # Get final diagnosis
                if not hasattr(self, '_sessions') or session_key not in self._sessions:
                    return "No active session. Use `action='start'` to begin."
                
                session = self._sessions[session_key]
                result = session.conclude()
                
                # Clear session
                del self._sessions[session_key]
                
                log.info(f"Session concluded: primary={result.primary_failure} confidence={result.confidence*100:.1f}%")
                return self._format_diagnosis(result, [], [], [])
                
            else:
                return f"Unknown action: {action}. Use 'start', 'add', 'test', or 'conclude'."
                
        except Exception as e:
            log.exception("Interactive diagnostic error")
            return f"Error: {str(e)}"
    
    def _format_diagnosis(self, result, symptoms: list, dtcs: list, sensors: list) -> str:
        """Format diagnostic result as markdown."""
        
        # Confidence emoji
        if result.confidence >= 0.8:
            conf_emoji = "🟢"
        elif result.confidence >= 0.5:
            conf_emoji = "🟡"
        else:
            conf_emoji = "🔴"
        
        # Build response
        response = "# 🔧 Diagnostic Report\n\n"
        
        # Input summary
        if symptoms or dtcs or sensors:
            response += "## Input\n"
            if symptoms:
                response += f"- **Symptoms:** {', '.join(symptoms)}\n"
            if dtcs:
                response += f"- **DTCs:** {', '.join(dtcs)}\n"
            if sensors:
                response += f"- **Sensors:** {', '.join(f'{s.name}={s.value}' for s in sensors)}\n"
            response += "\n"
        
        # Primary diagnosis with ML confidence
        response += "## Diagnosis\n\n"
        
        # If confidence is very low, indicate the model doesn't have a good match
        if result.confidence < 0.10:
            response += "⚪ **No Strong Match Found**\n\n"
            response += "**Confidence:** Too low for reliable diagnosis\n\n"
            response += "_The diagnostic model doesn't have a strong match for this combination of symptoms/DTCs. This may indicate an issue not yet in the knowledge base, or insufficient input data._\n\n"
        else:
            response += f"{conf_emoji} **{result.primary_failure.replace('_', ' ').title()}**\n\n"
            response += f"**Confidence:** {result.confidence*100:.1f}%\n\n"
        
        # ML scores breakdown (if available)
        if hasattr(result, 'ml_failure_scores') and result.ml_failure_scores:
            response += "<details>\n<summary>📊 ML Confidence Breakdown</summary>\n\n"
            response += "| Failure Mode | ML Score |\n|-------------|----------|\n"
            sorted_scores = sorted(result.ml_failure_scores.items(), key=lambda x: -x[1])
            for failure, score in sorted_scores[:5]:
                response += f"| {failure.replace('_', ' ').title()} | {score*100:.1f}% |\n"
            response += "\n</details>\n\n"
        
        # Alternatives - only show if they have meaningful probability
        if result.alternatives:
            # Filter to alternatives with at least 10% probability
            meaningful_alternatives = [
                (failure, prob) for failure, prob in result.alternatives[:self.valves.MAX_ALTERNATIVES]
                if prob >= 0.10
            ]
            if meaningful_alternatives:
                response += "### Also Consider\n\n"
                for failure, prob in meaningful_alternatives:
                    response += f"- {failure.replace('_', ' ').title()}: {prob*100:.1f}%\n"
                response += "\n"
        
        # Discriminating tests to confirm
        if hasattr(result, 'discriminating_tests') and result.discriminating_tests:
            response += "## ✅ Confirm Diagnosis\n\n"
            response += "Perform these tests to verify:\n\n"
            for i, test in enumerate(result.discriminating_tests[:3], 1):
                response += f"{i}. {test}\n"
            response += "\n"
        
        # Repair actions - always start with visual inspection
        response += "## 🔧 Recommended Actions\n\n"
        response += "1. **Visual Inspection** - Check for obvious issues: loose connections, damaged hoses, leaks, corrosion, burnt wires, or physical damage in the affected area\n"
        if result.repair_actions:
            for i, action in enumerate(result.repair_actions, 2):
                response += f"{i}. {action}\n"
        response += "\n"
        
        # Repair estimate
        if hasattr(result, 'repair_estimate') and result.repair_estimate:
            response += f"### 💰 Estimated Cost\n\n"
            response += f"**{result.repair_estimate}**\n\n"
            response += "_Note: Actual costs vary by location and vehicle._\n\n"
        
        # Next test (if not confident)
        if result.recommended_test:
            response += "## 🔍 Need More Certainty?\n\n"
            response += f"**Recommended test:** {result.recommended_test.replace('_', ' ').title()}\n\n"
            if result.test_reason:
                response += f"_{result.test_reason}_\n\n"
        
        # Confidence interpretation
        response += "---\n\n"
        if result.confidence >= 0.8:
            response += "_High confidence diagnosis. Proceed with repair._"
        elif result.confidence >= 0.5:
            response += "_Moderate confidence. Consider additional testing to confirm._"
        else:
            response += "_Low confidence. Additional diagnostic tests recommended._"
        
        return response
