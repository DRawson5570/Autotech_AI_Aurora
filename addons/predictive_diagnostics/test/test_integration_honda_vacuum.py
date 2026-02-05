from addons.predictive_diagnostics.integration.api import DiagnosticEngine, SensorReading


def test_honda_vacuum_diagnosis_high_confidence():
    engine = DiagnosticEngine(confidence_threshold=0.6)

    sensors = [
        SensorReading(name="engine_rpm", value=650),
        SensorReading(name="short_term_fuel_trim_b1", value=18),
        SensorReading(name="long_term_fuel_trim_b1", value=15),
        SensorReading(name="maf", value=3.2),
        SensorReading(name="intake_air_temp", value=75),
        SensorReading(name="coolant_temp", value=90),
        SensorReading(name="throttle_position", value=2),
        SensorReading(name="o2_b1s1", value=0.1),
    ]

    dtcs = ["P0300", "P0171"]
    symptoms = ["engine running rough at idle", "hesitation on acceleration"]

    result = engine.diagnose(sensors=sensors, dtcs=dtcs, symptoms=symptoms)

    assert result is not None
    assert result.primary_failure == "vacuum_leak", f"Unexpected primary failure: {result.primary_failure}"
    assert result.confidence >= 0.6, f"Expected at least 60% confidence, got {result.confidence}"
