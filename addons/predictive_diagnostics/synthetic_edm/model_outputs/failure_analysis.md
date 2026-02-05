# Failure Mode Analysis

## EDM_004
Ground truth: ['CAN message loss / gateway fault']
Model top predictions: ['CAN gateway fault causing message loss'] (reasons preserved when available)
Significant CAN drops observed in logs — consistent with CAN/gateway fault.
Model considered a CAN/gateway issue.
Suggested tests: read gateway error counters, test bus voltages, try loopback diagnostics.
Model's hypothesis 'CAN gateway fault causing message loss' cites signals: ['thermal', 'can'] (reason snippet: 210 CAN drops recorded inverter status OK no voltage/temperature anomalies)

## EDM_008
Ground truth: ['CAN message loss / gateway fault']
Model top predictions: ['CAN gateway fault causing message loss'] (reasons preserved when available)
Significant CAN drops observed in logs — consistent with CAN/gateway fault.
Model considered a CAN/gateway issue.
Suggested tests: read gateway error counters, test bus voltages, try loopback diagnostics.
Model's hypothesis 'CAN gateway fault causing message loss' cites signals: ['can'] (reason snippet: high CAN_drops_total (210) inverter and power metrics normal root‑cause list includes CAN fault)
