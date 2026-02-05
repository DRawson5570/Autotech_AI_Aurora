from datetime import datetime

from addons.predictive_diagnostics.reasoner import DiagnosticReasoner, SymptomReport
from addons.predictive_diagnostics.models import Vehicle, ScannerData, DTCCode


def test_isolation_detection_from_symptom_text():
    reasoner = DiagnosticReasoner()

    vehicle = Vehicle(year=2020, make="Tesla", model="Model 3")

    # No PIDs provided; DTC present; insulation value embedded in symptom text
    dtc = DTCCode(code="BMS_f035", description="Isolation fault detected")
    scanner = ScannerData(vehicle=vehicle, pids=[], dtcs=[dtc])

    symptoms = SymptomReport(descriptions=["Isolation fault, vehicle will not enter READY, HV+ to chassis insulation 0.05 MΩ"])

    result = reasoner.diagnose(vehicle=vehicle, scanner_data=scanner, symptoms=symptoms, system="hv_system", top_k=5)

    assert result is not None
    assert result.most_likely_fault is not None
    top = result.most_likely_fault
    assert top.fault_node_id in ("tesla_hv_isolation_fault", "hv_isolation_fault")
    assert top.probability > 0.7
    assert result.confidence_level == "high"
