"""Stress reproduction: call process_chat_payload concurrently as Gary to try to reproduce system message loss.

Usage: python3 scripts/stress_repro_pipeline.py
"""
import sys
import os
import asyncio
import logging
import json
from types import SimpleNamespace

# Ensure local 'backend' package is importable when running the script directly
sys.path.insert(0, os.path.abspath('backend'))

from open_webui.models.users import Users
from open_webui.models.models import Models
from open_webui.utils.middleware import process_chat_payload

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

MODEL_ID = "autotech-ai-expert---bullet-points"
NUM_TASKS = 50


class FakeConfig:
    def __init__(self):
        self.TASK_MODEL = None
        self.TASK_MODEL_EXTERNAL = None
        self.OPENAI_API_BASE_URLS = ["http://localhost"]
        self.OPENAI_API_KEYS = [""]
        self.VOICE_MODE_PROMPT_TEMPLATE = None


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
        self.state = SimpleNamespace(direct=False)


async def run_one(user_email, models):
    user = Users.get_user_by_email(user_email)
    if not user:
        log.error(f"User not found: {user_email}")
        return

    # minimal model dict
    model_item = Models.get_model_by_id(MODEL_ID)
    if not model_item:
        log.error(f"Model not found: {MODEL_ID}")
        return
    # Use dict form like runtime (ModelModel -> dict)
    model_item = model_item.model_dump()

    # Start with a system template that uses {{USER_FIRST_NAME}} to exercise replacement logic
    form_data = {"model": MODEL_ID, "messages": [{"role": "system", "content": "Hello {{USER_FIRST_NAME}}!"}]}
    metadata = {"chat_id": None}

    request = FakeRequest({MODEL_ID: model_item})

    try:
        out = await process_chat_payload(request, form_data, user, metadata, model_item)
        # process_chat_payload may return a tuple (form_data, metadata, events) or just form_data
        from open_webui.utils.misc import get_system_message

        form_out = out[0] if isinstance(out, tuple) else out

        sys_msg = get_system_message(form_out.get("messages", []))
        if sys_msg:
            preview = sys_msg.get("content")[:200]
            log.info(f"SUCCESS: user={user.email}, system_present=yes, preview={preview}")
            print(f"SUCCESS: user={user.email}, system_present=yes, preview={preview}")
        else:
            log.info(f"MISSING: user={user.email}, system_present=no")
            print(f"MISSING: user={user.email}, system_present=no")
    except Exception as e:
        log.exception(f"Error in run_one: {e}")


async def main():
    # Ensure models dict contains plain dict entries like the running app
    models = {MODEL_ID: Models.get_model_by_id(MODEL_ID).model_dump()}

    tasks = []
    for i in range(NUM_TASKS):
        tasks.append(run_one("wishaex@gmail.com", models))

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
