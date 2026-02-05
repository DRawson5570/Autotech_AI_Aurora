#!/usr/bin/env python3
"""
Integration test: Ensure ML model priors are used by Diagnostician
"""
import os
import sys
sys.path.insert(0, "/home/drawson/autotech_ai")

from addons.predictive_diagnostics.ml.run_phase3_quick import run_quick
from addons.predictive_diagnostics.ml.inference import DiagnosticInference
from addons.predictive_diagnostics.ml.model import SimpleDiagnosticModel
from addons.predictive_diagnostics.reasoning import Diagnostician


def test_ml_priors_used_by_diagnostician(tmp_path):
    # Run quick training to produce a small model
    metrics = run_quick()
    model_path = "/tmp/pd_quick_model.pt"
    assert os.path.exists(model_path), "Expected quick model to be saved"

    # Load model and perform inference on a cold-running scenario
    model = SimpleDiagnosticModel.load(model_path)
    inference = DiagnosticInference(model)

    observations = {"coolant_temp": 50}
    ml_result = inference.diagnose_from_observations(observations)
    assert ml_result.hypotheses, "ML inference produced no hypotheses"

    top_ml = ml_result.hypotheses[0]["failure_id"]

    # Start diagnostician session with ML model and same observations
    diag = Diagnostician(ml_model=model)
    session = diag.start_session(sensor_data=observations)
    state = diag.get_current_state(session)

    top_state = state.get_top_hypotheses(1)[0][0]

    assert top_ml == top_state, f"ML top '{top_ml}' should match Diagnostician top '{top_state}'"


if __name__ == '__main__':
    test_ml_priors_used_by_diagnostician(None)
    print("OK")
