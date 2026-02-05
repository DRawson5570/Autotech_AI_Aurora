import sys
import types
import pytest

# Prevent optional deps (e.g., azure) from breaking imports in unit tests
sys.modules.setdefault('azure', types.ModuleType('azure'))
azure_identity = types.ModuleType('azure.identity')
azure_identity.DefaultAzureCredential = lambda *a, **k: None
azure_identity.get_bearer_token_provider = lambda *a, **k: (None, None)
sys.modules.setdefault('azure.identity', azure_identity)

from open_webui.routers import openai


def test_extract_from_candidates_content_parts():
    res = {
        "candidates": [
            {"content": {"parts": [{"text": "Hello!"}]}, "finishReason": "STOP"}
        ]
    }

    out = openai._extract_text_from_google_response(res)
    assert out.strip() == "Hello!"


def test_extract_from_output_list():
    res = {"output": [{"type": "text", "text": "Output text."}]}
    out = openai._extract_text_from_google_response(res)
    assert "Output text." in out


def test_extract_from_content_top():
    res = {"content": {"parts": [{"text": "Top content"}]}}
    out = openai._extract_text_from_google_response(res)
    assert out.strip() == "Top content"


def test_string_input_returns_itself():
    res = "just a string"
    out = openai._extract_text_from_google_response(res)
    assert out == "just a string"
