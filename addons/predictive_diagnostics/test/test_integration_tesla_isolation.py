from addons.predictive_diagnostics.integration.api import DiagnosticEngine, SensorReading


def test_engine_detects_tesla_isolation_from_sensor_and_dtc():
    engine = DiagnosticEngine(confidence_threshold=0.7)

    sensors = [SensorReading(name="isolation_resistance", value=0.05, unit="MOhm")]
    dtcs = ["BMS_F035"]
    symptoms = ["Isolation fault, vehicle will not enter READY"]

    result = engine.diagnose(sensors=sensors, dtcs=dtcs, symptoms=symptoms)

    assert result is not None
    assert result.primary_failure in ("tesla_hv_isolation_fault", "hv_isolation_fault"), f"Unexpected primary failure: {result.primary_failure}"
    assert result.confidence >= 0.7, f"Expected high confidence but got {result.confidence}"
