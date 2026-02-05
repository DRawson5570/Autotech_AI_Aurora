import pytest
import sys
import os
import asyncio

sys.path.insert(0, os.path.abspath("backend"))

from open_webui.utils.middleware import ensure_system_greeting, process_chat_payload
from open_webui.models.users import Users
from open_webui.models.models import Models

MODEL_ID = "autotech-ai-expert---bullet-points"


def test_ensure_system_greeting_adds_greeting_for_gary():
    user = Users.get_user_by_email("wishaex@gmail.com")
    assert user is not None

    form_data = {"model": MODEL_ID, "messages": [{"role": "user", "content": "Please help"}]}
    out = ensure_system_greeting(form_data, metadata={}, user=user, request_id="deadbeef")

    from open_webui.utils.misc import get_system_message

    sys_msg = get_system_message(out.get("messages", []))
    assert sys_msg is not None
    assert "Hello Gary" in sys_msg.get("content")


def test_process_chat_payload_injects_greeting_when_missing():
    user = Users.get_user_by_email("wishaex@gmail.com")
    assert user is not None

    model_item = Models.get_model_by_id(MODEL_ID).model_dump()

    class FakeConfig:
        TASK_MODEL = None
        TASK_MODEL_EXTERNAL = None
        OPENAI_API_BASE_URLS = ["http://localhost"]
        OPENAI_API_KEYS = [""]
        VOICE_MODE_PROMPT_TEMPLATE = None

    class FakeAppState:
        def __init__(self, models):
            self.config = FakeConfig()
            self.MODELS = models

    class FakeApp:
        def __init__(self, models):
            self.state = FakeAppState(models)

    class FakeRequest:
        def __init__(self, models):
            self.app = FakeApp(models)
            self.cookies = {}
            self.state = type('S', (), {})()

    request = FakeRequest({MODEL_ID: model_item})
    form_data = {"model": MODEL_ID, "messages": [{"role": "user", "content": "Diagnose this"}], "metadata": {}}

    out = asyncio.run(process_chat_payload(request, form_data, user, metadata={}, model=model_item))
    # process_chat_payload returns (form_data, metadata, events) in some flows
    if isinstance(out, tuple):
        out = out[0]

    from open_webui.utils.misc import get_system_message

    assert get_system_message(out.get("messages", [])) is not None


if __name__ == "__main__":
    asyncio.run(test_process_chat_payload_injects_greeting_when_missing())
