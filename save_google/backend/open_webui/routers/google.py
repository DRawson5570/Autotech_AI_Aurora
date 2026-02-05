import asyncio
import json
import logging
from typing import Optional

import aiohttp
from aiocache import cached
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from open_webui.utils.auth import get_admin_user
from open_webui.models.users import UserModel
from open_webui.constants import ERROR_MESSAGES
from open_webui.env import (
    AIOHTTP_CLIENT_SESSION_SSL,
    AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST,
)
from open_webui.utils.oauth import encrypt_data, decrypt_data

log = logging.getLogger(__name__)
router = APIRouter()


async def send_get_request(url, key=None, user: UserModel = None):
    timeout = aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST)
    try:
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            headers = {"Content-Type": "application/json"}
            if key:
                # Prefer Authorization header with Bearer token
                headers["Authorization"] = f"Bearer {key}"

            async with session.get(url, headers=headers, ssl=AIOHTTP_CLIENT_SESSION_SSL) as response:
                if response.status != 200:
                    # try with key as query param if provided
                    if key:
                        async with session.get(f"{url}?key={key}", ssl=AIOHTTP_CLIENT_SESSION_SSL) as r2:
                            if r2.status == 200:
                                return await r2.json()
                            else:
                                log.error(f"Google API returned status {r2.status} for {url}")
                                return None
                    log.error(f"Google API returned status {response.status} for {url}")
                    return None
                return await response.json()
    except Exception as e:
        log.exception(e)
        return None


@cached(ttl=60, key=lambda _, user: f"google_all_models_{user.id}" if user else "google_all_models")
async def get_all_models(request: Request, user: UserModel = None) -> list:
    log.info("google.get_all_models()")
    if not request.app.state.config.ENABLE_GOOGLE_API:
        return []

    request_tasks = []
    # Try to read key from model provider credentials (encrypted) first
    creds = getattr(request.app.state.config, "MODEL_PROVIDER_CREDENTIALS", None) or {}
    google_creds = creds.get("google", {})

    for idx, url in enumerate(getattr(request.app.state.config, "GOOGLE_API_BASE_URLS", []) or []):
        # Determine key to use
        key = None
        if google_creds.get("api_key_encrypted"):
            try:
                decrypted = decrypt_data(google_creds.get("api_key_encrypted"))
                key = decrypted.get("api_key") if isinstance(decrypted, dict) else None
            except Exception as e:
                log.debug(f"Failed to decrypt google api key: {e}")
        # Fallback to plaintext config if set (legacy)
        if not key:
            keys = getattr(request.app.state.config, "GOOGLE_API_KEYS", []) or []
            if len(keys) > idx:
                key = keys[idx]

        request_tasks.append(send_get_request(f"{url}/models", key, user=user))

    responses = await asyncio.gather(*request_tasks)

    models = []
    for idx, response in enumerate(responses):
        if not response:
            continue
        # Google models list may be in different formats, attempt to normalize
        # Expecting response: {"models": [{"name": "models/gemini-...", "displayName": "Gemini"}, ...]}
        # Or {"models": [{"name": "...", "id": "..."}, ...]}
        for m in response.get("models", []) if isinstance(response, dict) else []:
            model_id = m.get("name") or m.get("id") or m.get("model")
            if model_id and model_id.startswith("models/"):
                # shorten to e.g., gemini-3.0
                model_id = model_id.split("/")[-1]

            model_name = m.get("displayName") or m.get("name") or model_id

            models.append(
                {
                    "id": model_id,
                    "name": model_name,
                    "object": "model",
                    "created": 0,
                    "owned_by": "google",
                    "google": m,
                }
            )

    return models


class GoogleConfigForm(BaseModel):
    ENABLE_GOOGLE_API: Optional[bool] = None
    GOOGLE_API_BASE_URLS: list[str]
    GOOGLE_API_KEYS: list[str]


@router.get("/config")
async def get_config(request: Request, user=Depends(get_admin_user)):
    return {
        "ENABLE_GOOGLE_API": request.app.state.config.ENABLE_GOOGLE_API,
        "GOOGLE_API_BASE_URLS": request.app.state.config.GOOGLE_API_BASE_URLS,
        # Do not return plaintext api keys if encrypted credentials exist
        "GOOGLE_API_KEYS": request.app.state.config.GOOGLE_API_KEYS,
        "MODEL_PROVIDER_CREDENTIALS": getattr(request.app.state.config, "MODEL_PROVIDER_CREDENTIALS", {}),
    }


@router.post("/config/update")
async def update_config(request: Request, form_data: GoogleConfigForm, user=Depends(get_admin_user)):
    request.app.state.config.ENABLE_GOOGLE_API = form_data.ENABLE_GOOGLE_API
    request.app.state.config.GOOGLE_API_BASE_URLS = form_data.GOOGLE_API_BASE_URLS
    # plaintext keys will be stored only for backward compatibility; recommend using encrypted model provider credentials
    request.app.state.config.GOOGLE_API_KEYS = form_data.GOOGLE_API_KEYS

    return {
        "ENABLE_GOOGLE_API": request.app.state.config.ENABLE_GOOGLE_API,
        "GOOGLE_API_BASE_URLS": request.app.state.config.GOOGLE_API_BASE_URLS,
        "GOOGLE_API_KEYS": request.app.state.config.GOOGLE_API_KEYS,
    }


class ConnectionVerificationForm(BaseModel):
    url: str
    key: Optional[str] = None


@router.post("/verify")
async def verify_connection(form_data: ConnectionVerificationForm, user=Depends(get_admin_user)):
    url = form_data.url
    key = form_data.key

    try:
        async with aiohttp.ClientSession(
            trust_env=True,
            timeout=aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST),
        ) as session:
            headers = {"Content-Type": "application/json"}
            if key:
                headers["Authorization"] = f"Bearer {key}"

            async with session.get(f"{url}/models", headers=headers, ssl=AIOHTTP_CLIENT_SESSION_SSL) as r:
                if r.status != 200:
                    # try with ?key= fallback
                    async with session.get(f"{url}/models?key={key}", ssl=AIOHTTP_CLIENT_SESSION_SSL) as r2:
                        if r2.status != 200:
                            raise Exception(f"HTTP Error: {r.status}")
                        return await r2.json()
                return await r.json()

    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=400, detail=f"Failed to connect to Google models endpoint: {e}")


class ProviderCredentialsForm(BaseModel):
    provider: str
    api_key: Optional[str] = None


@router.post("/credentials/set")
async def set_credentials(request: Request, form_data: ProviderCredentialsForm, user=Depends(get_admin_user)):
    # Store encrypted provider API key in persistent config under MODEL_PROVIDER_CREDENTIALS
    creds = getattr(request.app.state.config, "MODEL_PROVIDER_CREDENTIALS", None) or {}
    if form_data.api_key:
        encrypted = encrypt_data(json.dumps({"api_key": form_data.api_key}))
        creds[form_data.provider] = {"api_key_encrypted": encrypted}
    else:
        # remove
        if form_data.provider in creds:
            del creds[form_data.provider]

    request.app.state.config.MODEL_PROVIDER_CREDENTIALS = creds
    return {"status": True}


@router.get("/credentials/get")
async def get_credentials(request: Request, provider: str, user=Depends(get_admin_user)):
    creds = getattr(request.app.state.config, "MODEL_PROVIDER_CREDENTIALS", None) or {}
    provider_creds = creds.get(provider, {})
    if provider_creds.get("api_key_encrypted"):
        # return masked
        return {"masked": True, "value": "****"}
    return {"masked": False, "value": None}


@router.get("/admin/ui")
async def admin_ui(user=Depends(get_admin_user)):
    # Minimal admin UI to set Google API key and test connection
    html = '''<!doctype html>
<html><head><meta charset="utf-8"><title>Google Connection</title></head>
<body>
  <h1>Google Connection</h1>
  <div>
    <label>API Key: <input id="api_key" type="text" /></label>
    <button onclick="setKey()">Save</button>
    <button onclick="testKey()">Test</button>
  </div>
  <pre id="out"></pre>
  <script>
  async function setKey(){
    const api_key = document.getElementById('api_key').value;
    const res = await fetch('/api/v1/google/credentials/set',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body: JSON.stringify({provider:'google', api_key})
    });
    document.getElementById('out').innerText = await res.text();
  }
  async function testKey(){
    const url = document.getElementById('api_key').value ? '' : '';
    const api_key = document.getElementById('api_key').value;
    const res = await fetch('/api/v1/google/verify',{method:'POST',headers:{'Content-Type':'application/json'}, body: JSON.stringify({url:'https://generativelanguage.googleapis.com/v1', key: api_key})});
    document.getElementById('out').innerText = await res.text();
  }
  </script>
</body></html>'''
    return HTMLResponse(content=html, status_code=200)
