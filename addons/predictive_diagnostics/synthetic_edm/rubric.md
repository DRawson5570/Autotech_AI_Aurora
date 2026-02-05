# Evaluation Rubric

This document describes the scoring rubric for the EDM diagnosis experiment.

Metrics
- Top-1 Accuracy: fraction of scenarios where the model's top prediction matches ground truth.
- Top-3 Accuracy: fraction where ground truth appears in top-3 predictions.
- Diagnostic Test Usefulness: SME-rated 1–5 (optional/human-in-the-loop).
- Repair Correctness: binary (1 if recommended fix matches expected repair, 0 otherwise), partial credit for correct step sequencing.
- Confidence Calibration: compare predicted probabilities vs empirical accuracy across bins.
- Explanation Quality: SME-rated 1–5 for clarity and traceability.

Scoring Example (per scenario)
- Top-1 correct: 3 points
- Top-3 correct: 2 points
- Each actionable diagnostic test: 1 point (SME-rated)
- Explanation clarity bonus: 1 point if SME > 3

Automated vs Human
- Top-1 / Top-3 are automated and deterministic.
- Test usefulness and explanation clarity require human rating.

Use this rubric to guide automated scoring and to produce aggregated reports for experiments.