"""
ELM327 Scan Tool for Open WebUI - Standalone Version

This tool communicates with the ELM327 Gateway service via HTTP.
No relative imports - works in Open WebUI's isolated execution environment.

Prerequisites:
    1. Start the ELM327 gateway: python -m addons.scan_tool.gateway.server
    2. Or start the simulator: python -m addons.scan_tool.simulator --port 35000
    
The gateway provides REST API access to the ELM327 adapter.
"""

import json
import requests
from typing import Optional
from pydantic import BaseModel, Field


class Tools:
    """
    ELM327 OBD-II Diagnostic Tools
    
    Connects to vehicles via ELM327 adapter for reading DTCs,
    live sensor data, and performing diagnostics.
    """
    
    class Valves(BaseModel):
        """Configuration for the ELM327 tool."""
        gateway_url: str = Field(
            default="http://localhost:8327",
            description="URL of the ELM327 gateway service"
        )
        elm327_address: str = Field(
            default="localhost:35000",
            description="ELM327 adapter address (for WiFi: host:port)"
        )
        connection_type: str = Field(
            default="wifi",
            description="Connection type: wifi, bluetooth, usb"
        )
    
    def __init__(self):
        self.valves = self.Valves()
        self._session_data = {}
    
    def _api(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Make API call to gateway."""
        url = f"{self.valves.gateway_url}{endpoint}"
        try:
            if method == "GET":
                resp = requests.get(url, timeout=30)
            elif method == "POST":
                resp = requests.post(url, json=data, timeout=30)
            elif method == "DELETE":
                resp = requests.delete(url, timeout=30)
            else:
                return {"error": f"Unknown method: {method}"}
            
            if resp.status_code == 200:
                return resp.json()
            else:
                return {"error": f"HTTP {resp.status_code}: {resp.text}"}
        except requests.exceptions.ConnectionError:
            return {"error": "Cannot connect to gateway. Start it with: python -m addons.scan_tool.gateway.server"}
        except Exception as e:
            return {"error": str(e)}
    
    async def elm327_connect(
        self,
        connection_type: str = "",
        address: str = "",
        __user__: dict = None
    ) -> str:
        """
        Connect to vehicle via ELM327 adapter.
        
        Args:
            connection_type: wifi, bluetooth, or usb (default: wifi)
            address: Adapter address - for WiFi use host:port (default: localhost:35000)
        
        Returns:
            Connection status and vehicle info
        """
        conn_type = connection_type or self.valves.connection_type
        addr = address or self.valves.elm327_address
        
        result = self._api("POST", "/connect", {
            "connection_type": conn_type,
            "address": addr
        })
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        if result.get("status") == "connected":
            vin = result.get("vin", "Unknown")
            return f"""✅ Connected to ELM327 via {conn_type}
📋 VIN: {vin}

💡 **Next:** Call elm327_read_dtcs() to check for trouble codes"""
        else:
            return f"❌ Failed to connect: {result.get('status', 'Unknown error')}"
    
    async def elm327_disconnect(self, __user__: dict = None) -> str:
        """
        Disconnect from ELM327 adapter.
        
        Always disconnect when done to free the adapter for other users.
        """
        result = self._api("POST", "/disconnect")
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        return "✅ Disconnected from ELM327"
    
    async def elm327_status(self, __user__: dict = None) -> str:
        """
        Check current connection status.
        
        Returns:
            Connection status and vehicle info if connected
        """
        result = self._api("GET", "/")
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        if result.get("connected"):
            vin = result.get("vin", "Unknown")
            protocol = result.get("protocol", "Unknown")
            return f"""✅ Connected
📋 VIN: {vin}
🔌 Protocol: {protocol}"""
        else:
            return "❌ Not connected. Use elm327_connect() first."
    
    async def elm327_read_dtcs(self, __user__: dict = None) -> str:
        """
        Read Diagnostic Trouble Codes from vehicle.
        
        Reads stored, pending, and permanent DTCs.
        
        Returns:
            List of DTCs with descriptions
        """
        result = self._api("GET", "/dtcs")
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        output = []
        
        # Stored DTCs (CEL on)
        stored = result.get("stored", [])
        if stored:
            output.append("🔴 **Stored DTCs (Check Engine Light):**")
            for dtc in stored:
                code = dtc.get("code", "Unknown")
                desc = dtc.get("description", "")
                output.append(f"  • {code}: {desc}")
        else:
            output.append("✅ No stored DTCs")
        
        # Pending DTCs
        pending = result.get("pending", [])
        if pending:
            output.append("\n🟡 **Pending DTCs (Current drive cycle):**")
            for dtc in pending:
                code = dtc.get("code", "Unknown")
                desc = dtc.get("description", "")
                output.append(f"  • {code}: {desc}")
        
        # Permanent DTCs
        permanent = result.get("permanent", [])
        if permanent:
            output.append("\n🔒 **Permanent DTCs (Cannot be cleared):**")
            for dtc in permanent:
                code = dtc.get("code", "Unknown")
                output.append(f"  • {code}")
        
        if stored:
            output.append("\n💡 **Next:** Read related PIDs to gather more diagnostic data")
        
        return "\n".join(output)
    
    async def elm327_clear_dtcs(self, __user__: dict = None) -> str:
        """
        Clear DTCs and turn off Check Engine Light.
        
        ⚠️ WARNING: This clears freeze frame data and resets monitors.
        Only clear codes after diagnosing the root cause.
        
        Returns:
            Success or failure message
        """
        result = self._api("POST", "/clear-dtcs")
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        if result.get("status") == "cleared":
            return """✅ DTCs cleared successfully
⚠️ Check Engine Light should turn off
📊 Emission monitors have been reset - vehicle needs drive cycle to complete"""
        else:
            return f"❌ Failed to clear DTCs: {result.get('status', 'Unknown error')}"
    
    async def elm327_read_pids(
        self,
        pids: str = "RPM,COOLANT_TEMP,SPEED,THROTTLE_POS",
        __user__: dict = None
    ) -> str:
        """
        Read live sensor data from vehicle.
        
        Args:
            pids: Comma-separated list of PID names to read.
                  Common PIDs: RPM, COOLANT_TEMP, SPEED, THROTTLE_POS, MAP, MAF,
                  STFT_B1, LTFT_B1, O2_B1S1, TIMING_ADV, LOAD, IAT
        
        Returns:
            Current sensor values
        """
        # Normalize and send as comma-separated string
        pid_list = [p.strip().upper() for p in pids.split(",")]
        pids_str = ",".join(pid_list)
        
        result = self._api("POST", "/pids", {"pids": pids_str})
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        readings = result.get("pids", {})
        if not readings:
            return "⚠️ No data returned. Vehicle may not support requested PIDs."
        
        output = ["📊 **Live Sensor Data:**"]
        for name, data in readings.items():
            value = data.get("value", "N/A")
            unit = data.get("unit", "")
            output.append(f"  • {name}: {value} {unit}")
        
        return "\n".join(output)
    
    async def elm327_read_fuel_trims(self, __user__: dict = None) -> str:
        """
        Read fuel trim values from vehicle.
        
        Fuel trims indicate how much the ECU is adjusting fuel delivery.
        Positive = adding fuel (lean condition)
        Negative = removing fuel (rich condition)
        Normal range: -10% to +10%
        
        Returns:
            Fuel trim values with interpretation
        """
        result = self._api("GET", "/fuel_trims")
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        trims = result.get("fuel_trims", {})
        if not trims:
            return "⚠️ Could not read fuel trims"
        
        output = ["⛽ **Fuel Trims:**"]
        
        all_positive = True
        all_negative = True
        
        for name, data in trims.items():
            value = data.get("value", 0)
            
            if value > 10:
                status = "⚠️ HIGH (adding fuel - lean)"
            elif value < -10:
                status = "⚠️ HIGH (removing fuel - rich)"
            else:
                status = "✓ normal"
            
            if value <= 0:
                all_positive = False
            if value >= 0:
                all_negative = False
            
            output.append(f"  {name}: {value:+.1f}% ({status})")
        
        # Add interpretation
        if all_positive and any(abs(trims[t].get("value", 0)) > 10 for t in trims):
            output.append("\n💡 Both banks positive: Check for vacuum leak or MAF issue")
        elif all_negative and any(abs(trims[t].get("value", 0)) > 10 for t in trims):
            output.append("\n💡 Both banks negative: Check for fuel pressure or leaking injector")
        
        return "\n".join(output)
    
    async def elm327_read_vin(self, __user__: dict = None) -> str:
        """
        Read Vehicle Identification Number.
        
        Returns:
            17-character VIN with decoded information
        """
        result = self._api("GET", "/vin")
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        vin = result.get("vin")
        if not vin:
            return "⚠️ Could not read VIN"
        
        return f"""📋 **Vehicle Identification Number:**
VIN: {vin}

Use this VIN to look up:
• Vehicle specifications
• Recall information
• Service history"""
    
    async def elm327_monitor(
        self,
        pids: str = "RPM,COOLANT_TEMP",
        duration: int = 10,
        __user__: dict = None
    ) -> str:
        """
        Monitor PIDs over time and report statistics.
        
        Args:
            pids: Comma-separated list of PIDs to monitor
            duration: Monitoring duration in seconds (default: 10)
        
        Returns:
            Min/max/average for each PID over the monitoring period
        """
        # Normalize and send as comma-separated string
        pid_list = [p.strip().upper() for p in pids.split(",")]
        pids_str = ",".join(pid_list)
        
        result = self._api("POST", "/monitor", {
            "pids": pids_str,
            "duration": duration
        })
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        stats = result.get("stats", {})
        if not stats:
            return "⚠️ No data collected"
        
        output = [f"📈 **Monitored {duration} seconds:**"]
        
        for name, data in stats.items():
            unit = data.get("unit", "")
            output.append(f"\n  **{name}** ({unit}):")
            output.append(f"    Min: {data.get('min', 'N/A')}")
            output.append(f"    Max: {data.get('max', 'N/A')}")
            output.append(f"    Avg: {data.get('avg', 'N/A')}")
        
        return "\n".join(output)
    
    async def scan_tool_help(self, __user__: dict = None) -> str:
        """
        Show available scan tool functions and usage.
        
        Returns:
            List of available functions with descriptions
        """
        return """🔧 **ELM327 Scan Tool Functions:**

**Connection:**
• `elm327_connect()` - Connect to ELM327 adapter
• `elm327_disconnect()` - Disconnect from adapter
• `elm327_status()` - Check connection status

**Diagnostics:**
• `elm327_read_dtcs()` - Read trouble codes
• `elm327_clear_dtcs()` - Clear trouble codes (use with caution!)
• `elm327_read_vin()` - Read vehicle VIN

**Live Data:**
• `elm327_read_pids(pids)` - Read sensor values
• `elm327_read_fuel_trims()` - Read fuel trim data
• `elm327_monitor(pids, duration)` - Monitor PIDs over time

**Common PIDs:**
RPM, COOLANT_TEMP, SPEED, THROTTLE_POS, MAP, MAF, STFT_B1, LTFT_B1,
STFT_B2, LTFT_B2, O2_B1S1, O2_B1S2, TIMING_ADV, LOAD, IAT, VOLTAGE

**Typical Workflow:**
1. `elm327_connect()` - Connect to vehicle
2. `elm327_read_dtcs()` - Check for codes
3. `elm327_read_fuel_trims()` - Check fuel system
4. `elm327_read_pids("RPM,MAP,MAF")` - Read related sensors
5. `elm327_disconnect()` - Always disconnect when done"""
