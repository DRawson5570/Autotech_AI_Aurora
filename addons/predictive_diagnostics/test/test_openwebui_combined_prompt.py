import asyncio

from addons.predictive_diagnostics.openwebui_tool import Tools


async def _call_diagnose_combined():
    tool = Tools()
    combined = (
        "Diagnose vehicle issue: Vehicle: 2018 Honda Accord 2.0T. "
        "Symptoms: engine running rough at idle, hesitation on acceleration. "
        "DTCs: P0300,P0171. "
        "Sensor readings: engine_rpm:650, short_term_fuel_trim_b1:18, long_term_fuel_trim_b1:15, "
        "maf:3.2, intake_air_temp:75, coolant_temp:90, throttle_position:2, o2_b1s1:0.1"
    )
    resp = await tool.diagnose(
        combined,
        dtcs="",
        sensor_readings="",
        __user__={"id": "test", "name": "tester"}
    )
    return resp


def test_combined_prompt_parsed():
    resp = asyncio.run(_call_diagnose_combined())
    # Ensure the formatted response includes parsed sensor entries
    assert "short_term_fuel_trim_b1=18" in resp
    assert "long_term_fuel_trim_b1=15" in resp
    assert "maf=3.2" in resp
    # And that the diagnosis is confident for this input
    assert "Vacuum Leak" in resp or "vacuum leak" in resp
