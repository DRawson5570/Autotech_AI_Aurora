"""
PyTest-friendly quick test for Phase 3 ML pipeline.
Runs a short training run and asserts the validation accuracy exceeds a low threshold.
"""

import os
import tempfile

from addons.predictive_diagnostics.ml.run_phase3_quick import run_quick


def test_quick_training_runs():
    metrics = run_quick()
    final_val_acc = metrics.get('final_val_acc', 0.0)
    assert final_val_acc >= 0.12, f"Validation accuracy too low: {final_val_acc:.2f}"


if __name__ == '__main__':
    print(run_quick())
