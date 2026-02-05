from datetime import datetime

from addons.predictive_diagnostics.reasoner import DiagnosticReasoner, SymptomReport
from addons.predictive_diagnostics.models import Vehicle, ScannerData, PIDReading, DTCCode


def test_isolation_detection_with_pid_and_dtc():
    reasoner = DiagnosticReasoner()

    vehicle = Vehicle(year=2020, make="Tesla", model="Model 3")

    pid = PIDReading(pid="INS_RES", name="insulation_resistance", value=0.05, unit="MOhm", timestamp=datetime.now())
    dtc = DTCCode(code="BMS_f035", description="Isolation fault detected")

    scanner = ScannerData(vehicle=vehicle, pids=[pid], dtcs=[dtc])
    symptoms = SymptomReport(descriptions=["Isolation fault, vehicle will not enter READY, cannot charge"])

    result = reasoner.diagnose(vehicle=vehicle, scanner_data=scanner, symptoms=symptoms, system="hv_system", top_k=5)

    assert result is not None
    assert result.most_likely_fault is not None, "Expected a most likely fault"
    top = result.most_likely_fault
    assert top.fault_node_id in ("tesla_hv_isolation_fault", "hv_isolation_fault"), f"Unexpected top fault: {top.fault_node_id}"
    assert top.probability > 0.7, f"Expected high probability but got {top.probability}"
    assert result.confidence_level == "high"