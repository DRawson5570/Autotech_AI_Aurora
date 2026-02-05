# Prompt templates for diagnosis

## Base prompt
System documents: Attach scenario JSON (component list, interfaces, FMEA entries) and CSV log. Observations: provide textual symptom summary and optionally the time-series CSV.

Please perform the following:
1. List top-3 root cause hypotheses and give an estimated probability for each. Provide brief reasoning (2-4 bullets each). 
2. Propose diagnostic measurements/tests to confirm or deny each hypothesis, prioritized by cost/time. 
3. Recommend immediate mitigations (safe mode or limits) and full repairs.
4. State explicitly what additional data you'd request (if any).

Require the model to **show reasoning** for each hypothesis and include confidence values.

## Interactive protocol
Allow the model to request up to 5 follow-up measurements (e.g., "Measure pump current at t=240s", "Read CAN error count from ECU: last 5 minutes"). For each request, the experiment runner will either provide the simulated value from the CSV or reply "not available".

## Output format (expected)
Return a JSON object with:
- `predictions`: [ {"hypothesis":str, "prob":float, "reason": [str,...], "tests": [str,...], "mitigation": str } ]
- `requested_measurements`: [str,...]
- `explanation`: str

This structured format simplifies automated evaluation.
