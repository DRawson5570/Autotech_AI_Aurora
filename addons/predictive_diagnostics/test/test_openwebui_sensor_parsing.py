import asyncio

from addons.predictive_diagnostics.openwebui_tool import Tools


async def _call_diagnose():
    tool = Tools()
    resp = await tool.diagnose(
        "engine running rough at idle, hesitation on acceleration",
        dtcs="P0300,P0171",
        sensor_readings="engine_rpm:650, short_term_fuel_trim_b1:18, long_term_fuel_trim_b1:15, maf:3.2, intake_air_temp:75, coolant_temp:90, throttle_position:2, o2_b1s1:0.1",
        __user__={"id":"test","name":"tester"}
    )
    return resp


def test_openwebui_parses_all_sensors():
    resp = asyncio.run(_call_diagnose())
    # Ensure the response header lists the key sensors (not just coolant_temp)
    assert "short_term_fuel_trim_b1=18" in resp
    assert "long_term_fuel_trim_b1=15" in resp
    assert "maf=3.2" in resp
    assert "o2_b1s1=0.1" in resp
