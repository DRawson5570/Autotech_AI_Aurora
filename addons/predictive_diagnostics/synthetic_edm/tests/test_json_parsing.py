import sys
import os
import pytest
# allow tests to import package from repo root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from synthetic_edm.model_adapters import robust_parse_json


def test_plain_json():
    txt = 'Here is the answer:\n{"scenario_id":"EDM_001","predictions":[{"hypothesis":"Cooling pump failure","prob":0.7}]}'
    parsed = robust_parse_json(txt)
    assert parsed['scenario_id'] == 'EDM_001'
    assert parsed['predictions'][0]['hypothesis'] == 'Cooling pump failure'


def test_fenced_json_with_trailing_commas():
    txt = "```json\n{ 'scenario_id': 'EDM_002', 'predictions': [ {'hypothesis': 'Phase FET short',}, ], }\n```"
    parsed = robust_parse_json(txt)
    assert parsed['scenario_id'] == 'EDM_002'


def test_unquoted_keys_and_python_literals():
    txt = "{scenario_id: EDM_003, predictions: [{'hypothesis':'BMS cell imbalance','prob':0.6}], active: True}"
    parsed = robust_parse_json(txt)
    assert parsed['predictions'][0]['hypothesis'] == 'BMS cell imbalance'
    assert parsed['active'] is True or parsed.get('active') in (True, 'True', 'true')
