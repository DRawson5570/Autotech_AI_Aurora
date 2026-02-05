#!/usr/bin/env python3
"""
Test the Diagnostic Agent

This tests the agent logic without requiring a real ELM327 connection.
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from addons.scan_tool.agent.diagnostic_agent import DiagnosticAgent, DiagnosticResult


class MockELM327Service:
    """Mock ELM327 service for testing."""
    
    def __init__(self):
        self.connected = False
        self.vin = "1J4GL48K82W123456"
    
    async def connect(self, conn_type: str, address: str) -> bool:
        print(f"  [MOCK] Connecting via {conn_type} to {address}")
        self.connected = True
        return True
    
    async def disconnect(self):
        print("  [MOCK] Disconnecting")
        self.connected = False
    
    async def read_vin(self) -> str:
        return self.vin
    
    async def read_all_dtcs(self):
        """Return mock DTCs."""
        from dataclasses import dataclass
        
        @dataclass
        class MockDTC:
            code: str
            status: str
            description: str = ""
        
        return {
            'stored': [
                MockDTC("P0217", "confirmed", "Engine Coolant Over Temperature"),
                MockDTC("P0128", "confirmed", "Coolant Thermostat Below Regulating Temperature"),
            ],
            'pending': [],
            'permanent': [],
        }
    
    async def read_pids(self, pid_list):
        """Return mock PID readings."""
        from dataclasses import dataclass
        from datetime import datetime
        
        @dataclass
        class MockReading:
            pid: int
            name: str
            value: float
            unit: str
            timestamp: datetime = None
        
        mock_data = {
            'RPM': (850, 'rpm'),
            'COOLANT_TEMP': (235, '°F'),  # Overheating!
            'LOAD': (22, '%'),
            'THROTTLE_POS': (15, '%'),
            'STFT_B1': (2.5, '%'),
            'LTFT_B1': (4.2, '%'),
            'STFT_B2': (1.8, '%'),
            'LTFT_B2': (3.9, '%'),
            'MAF': (12.5, 'g/s'),
            'MAP': (35, 'kPa'),
            'IAT': (95, '°F'),
            'SPEED': (0, 'km/h'),
            'TIMING_ADV': (12, '°'),
        }
        
        result = {}
        for pid_name in pid_list:
            if pid_name.upper() in mock_data:
                val, unit = mock_data[pid_name.upper()]
                result[pid_name.upper()] = MockReading(
                    pid=0, name=pid_name.upper(), value=val, unit=unit, timestamp=datetime.now()
                )
        return result
    
    async def monitor_pids(self, pid_list, duration=10, interval=1):
        """Return mock monitoring data."""
        samples = []
        num_samples = int(duration / interval)
        
        for i in range(num_samples):
            sample = await self.read_pids(pid_list)
            # Simulate temperature rising
            if 'COOLANT_TEMP' in sample:
                sample['COOLANT_TEMP'].value = 235 + i * 2
            samples.append(sample)
        
        return samples


async def test_agent():
    """Test the diagnostic agent with mock data."""
    print("=" * 60)
    print("DIAGNOSTIC AGENT TEST")
    print("=" * 60)
    
    messages = []
    
    async def mock_callback(message: str) -> str:
        print(f"\n📱 {message}")
        messages.append(message)
        
        # Auto-respond based on message type
        if "Please perform" in message:
            print("  [AUTO-RESPONSE] OK")
            return "OK"
        return ""
    
    # Create agent with mock service
    agent = DiagnosticAgent(
        elm_service=MockELM327Service(),
        technician_callback=mock_callback,
    )
    
    # Run diagnosis
    result = await agent.run_diagnosis(
        vehicle_description="2012 Jeep Liberty Sport 3.7",
        connection_type="bluetooth",
        connection_address="/dev/rfcomm0",
        symptoms=["overheating", "temperature warning light"],
    )
    
    print("\n" + "=" * 60)
    print("FINAL RESULT")
    print("=" * 60)
    print(f"Primary Diagnosis: {result.primary_diagnosis}")
    print(f"Confidence: {result.confidence * 100:.0f}%")
    print(f"\nSupporting Evidence:")
    for ev in result.supporting_evidence:
        print(f"  • {ev}")
    print(f"\nDifferential Diagnoses:")
    for diag, conf in result.differential_diagnoses:
        print(f"  • {diag} ({conf * 100:.0f}%)")
    print(f"\nRecommended Repairs:")
    for repair in result.recommended_repairs:
        print(f"  • {repair}")
    if result.estimated_cost:
        print(f"\nEstimated Cost: {result.estimated_cost}")
    print(f"\nTests Performed: {len(result.tests_performed)}")
    
    return result


if __name__ == "__main__":
    result = asyncio.run(test_agent())
    print("\n✅ Test completed successfully!")
