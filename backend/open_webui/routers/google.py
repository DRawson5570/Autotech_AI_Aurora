import asyncio
import base64
import json
import logging
import mimetypes
import re
import time
from typing import Optional

import aiohttp
from aiocache import cached
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

from open_webui.utils.auth import get_admin_user
from open_webui.models.users import UserModel
from open_webui.models.models import Models
from open_webui.constants import ERROR_MESSAGES
from open_webui.env import (
    AIOHTTP_CLIENT_SESSION_SSL,
    AIOHTTP_CLIENT_TIMEOUT,
    AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST,
    GOOGLE_API_MAX_RETRIES,
    GOOGLE_API_RETRY_DELAY,
    GOOGLE_API_FAILOVER_TIMEOUT,
    GOOGLE_MODEL_FAILOVER,
)
from open_webui.config import GEMINI_THINKING_LEVEL, GEMINI_25_THINKING_BUDGET
from open_webui.utils.oauth import encrypt_data, decrypt_data
from open_webui.utils.misc import openai_chat_chunk_message_template
from open_webui.utils.payload import apply_model_params_to_body_openai, apply_system_prompt_to_body

log = logging.getLogger(__name__)
router = APIRouter()

# Retry settings for transient Google errors (configurable via env)
GOOGLE_MAX_RETRIES = GOOGLE_API_MAX_RETRIES  # default: 6
GOOGLE_RETRY_BASE_DELAY = GOOGLE_API_RETRY_DELAY  # seconds, doubles each retry
GOOGLE_FAILOVER_TIMEOUT = GOOGLE_API_FAILOVER_TIMEOUT  # seconds, trigger failover if total time exceeds this
GOOGLE_RETRYABLE_STATUS_CODES = {429, 500, 503, 502, 504}  # Rate limit, server errors, bad gateway, timeout


def _get_failover_model(model_name: str) -> Optional[str]:
    """Get the failover model for a given model name, if configured."""
    if not model_name:
        return None
    # Normalize model name - strip 'models/' prefix if present
    clean_name = model_name.split("/")[-1] if "/" in model_name else model_name
    # Try exact match first, then lowercase
    return GOOGLE_MODEL_FAILOVER.get(clean_name) or GOOGLE_MODEL_FAILOVER.get(clean_name.lower())


def _is_retryable_google_error(status_code: int, error_json: dict = None) -> bool:
    """Check if a Google error is retryable (transient)."""
    if status_code in GOOGLE_RETRYABLE_STATUS_CODES:
        return True
    # Check for RESOURCE_EXHAUSTED in error body (can come with various status codes)
    if error_json and isinstance(error_json, dict):
        error = error_json.get("error", {})
        if isinstance(error, dict):
            status = error.get("status", "")
            message = error.get("message", "")
            if "RESOURCE_EXHAUSTED" in status or "RESOURCE_EXHAUSTED" in message:
                return True
            if "overloaded" in message.lower() or "try again" in message.lower():
                return True
    return False


async def _sleep_for_retry(attempt: int, reason: str = "rate limit") -> None:
    """Sleep with exponential backoff for retry."""
    if attempt > 0:
        delay = GOOGLE_RETRY_BASE_DELAY * (2 ** (attempt - 1))
        log.warning(f"Google API {reason}, retry {attempt}/{GOOGLE_MAX_RETRIES} after {delay:.1f}s delay")
        await asyncio.sleep(delay)


def _extract_api_key_from_encrypted(google_creds: dict) -> Optional[str]:
    """Return the api_key from a stored encrypted credential.
    Handles both dict and double-encoded string payloads for backwards compatibility.
    """
    if not google_creds or not google_creds.get("api_key_encrypted"):
        return None
    try:
        decrypted = decrypt_data(google_creds.get("api_key_encrypted"))
        # decrypt_data may return a dict or a JSON-encoded string (double-encoded). Handle both and nested string values.
        if isinstance(decrypted, dict):
            return decrypted.get("api_key")
        if isinstance(decrypted, str):
            try:
                parsed = json.loads(decrypted)
                # Sometimes the decrypted string contains another JSON-encoded string (double-encoded), try again
                if isinstance(parsed, str):
                    try:
                        parsed = json.loads(parsed)
                    except Exception:
                        pass
                if isinstance(parsed, dict):
                    return parsed.get("api_key")
            except Exception:
                return None
    except Exception as e:
        log.debug(f"Failed to decrypt google api key: {e}")
    return None


async def send_get_request(url, key=None, user: UserModel = None):
    """Send a GET request to the Google API. Prefer using query param for API keys (e.g., keys starting with 'AIza'),
    otherwise prefer Authorization: Bearer for OAuth tokens. On non-200 responses, try a sensible fallback.
    """
    timeout = aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST)
    try:
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            headers = {"Content-Type": "application/json"}

            # If the key looks like a Google API key (starts with 'AIza'), prefer the ?key= query param.
            use_query = False
            if key and isinstance(key, str) and key.startswith("AIza"):
                use_query = True

            if key and not use_query:
                # Treat key as a bearer token first (likely OAuth access token)
                headers["Authorization"] = f"Bearer {key}"
                async with session.get(url, headers=headers, ssl=AIOHTTP_CLIENT_SESSION_SSL) as response:
                    if response.status == 200:
                        return await response.json()

                    # Fallback: try using the key as a query parameter
                    if key:
                        async with session.get(f"{url}?key={key}", ssl=AIOHTTP_CLIENT_SESSION_SSL) as r2:
                            if r2.status == 200:
                                return await r2.json()
                            else:
                                log.error(f"Google API returned status {r2.status} for {url}")
                                return None

                    log.error(f"Google API returned status {response.status} for {url}")
                    return None

            else:
                # Use query param (either because key looks like API key or no Authorization token was provided)
                target = f"{url}?key={key}" if key else url
                async with session.get(target, headers=headers, ssl=AIOHTTP_CLIENT_SESSION_SSL) as response:
                    if response.status == 200:
                        return await response.json()

                    # Fallback: try Authorization header if query param fails
                    if key:
                        headers2 = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
                        async with session.get(url, headers=headers2, ssl=AIOHTTP_CLIENT_SESSION_SSL) as r2:
                            if r2.status == 200:
                                return await r2.json()
                            else:
                                log.error(f"Google API returned status {r2.status} for {url}")
                                return None

                    log.error(f"Google API returned status {response.status} for {url}")
                    return None
    except Exception as e:
        log.exception(e)
        return None


# @cached(ttl=60, key=lambda _, user: f"google_all_models_{user.id}" if user else "google_all_models")
async def get_all_models(request: Request, user: UserModel = None) -> list:
    log.info("google.get_all_models() - CACHE DISABLED FOR DEBUG")
    log.info(f"DEBUG: ENABLE_GOOGLE_API = {request.app.state.config.ENABLE_GOOGLE_API}")
    log.info(f"DEBUG: GOOGLE_API_BASE_URLS = {getattr(request.app.state.config, 'GOOGLE_API_BASE_URLS', [])}")
    log.info(f"DEBUG: GOOGLE_API_KEYS = {['***' if k else '' for k in (getattr(request.app.state.config, 'GOOGLE_API_KEYS', []) or [])]}")
    if not request.app.state.config.ENABLE_GOOGLE_API:
        return []

    request_tasks = []
    # Try to read key from model provider credentials (encrypted) first
    creds = getattr(request.app.state.config, "MODEL_PROVIDER_CREDENTIALS", None) or {}
    google_creds = creds.get("google", {})

    for idx, url in enumerate(getattr(request.app.state.config, "GOOGLE_API_BASE_URLS", []) or []):
        # Determine key to use
        key = None
        # Try encrypted provider-level credential first (handles several legacy encodings)
        key = _extract_api_key_from_encrypted(google_creds) or key
        # Fallback to plaintext config if set (legacy)
        if not key:
            keys = getattr(request.app.state.config, "GOOGLE_API_KEYS", []) or []
            if len(keys) > idx:
                key = keys[idx]

        request_tasks.append(send_get_request(f"{url}/models", key, user=user))

    responses = await asyncio.gather(*request_tasks)
    log.info(f"DEBUG: Got {len(responses)} responses from Google API")

    models = []
    for idx, response in enumerate(responses):
        if not response:
            log.info(f"DEBUG: Response {idx} is empty/None")
            continue
        log.info(f"DEBUG: Response {idx} has {len(response.get('models', []))} models")
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
                    "connection_type": m.get("connection_type", "external"),
                    "urlIdx": idx,
                }
            )

    log.info(f"DEBUG: Returning {len(models)} Google models")
    return models


class GoogleConfigForm(BaseModel):
    ENABLE_GOOGLE_API: Optional[bool] = None
    GOOGLE_API_BASE_URLS: Optional[list[str]] = None
    GOOGLE_API_KEYS: Optional[list[str]] = None


@router.post("/config/update")
async def update_config(request: Request, form_data: GoogleConfigForm, user=Depends(get_admin_user)):
    """Update Google config with defensive validation and helpful error messages.

    Only update values that are explicitly provided in the request payload. Omitting a field will preserve
    the currently saved value.
    """
    try:
        # Determine enable flag; if omitted, preserve current value
        if form_data.ENABLE_GOOGLE_API is None:
            enable = request.app.state.config.ENABLE_GOOGLE_API
        else:
            enable = bool(form_data.ENABLE_GOOGLE_API)

        # Only normalize urls/keys when they are provided (None means do not change)
        base_urls = None if form_data.GOOGLE_API_BASE_URLS is None else (form_data.GOOGLE_API_BASE_URLS or [])
        keys = None if form_data.GOOGLE_API_KEYS is None else (form_data.GOOGLE_API_KEYS or [])

        if base_urls is not None:
            # Normalize base_urls to remove trailing slashes
            base_urls = [u.rstrip('/') for u in base_urls]

            # Deduplicate while preserving order to avoid creating multiple identical connections
            seen = set()
            deduped = []
            for u in base_urls:
                if u not in seen:
                    seen.add(u)
                    deduped.append(u)
            base_urls = deduped

            # Ensure keys list length matches urls list length
            if keys is None:
                keys = []
            if len(keys) < len(base_urls):
                keys = keys + [""] * (len(base_urls) - len(keys))
            elif len(keys) > len(base_urls):
                keys = keys[: len(base_urls)]

        # Apply changes only when provided
        if form_data.ENABLE_GOOGLE_API is not None:
            request.app.state.config.ENABLE_GOOGLE_API = enable
        if base_urls is not None:
            request.app.state.config.GOOGLE_API_BASE_URLS = base_urls
            request.app.state.config.GOOGLE_API_KEYS = keys

        # Clear model caches only if something changed
        try:
            if form_data.ENABLE_GOOGLE_API is not None or base_urls is not None or form_data.GOOGLE_API_KEYS is not None:
                request.app.state.BASE_MODELS = []
                request.app.state.MODELS = {}
                request.app.state.OPENAI_MODELS = {}
                request.app.state.GOOGLE_MODELS = {}
        except Exception:
            pass

        return {
            "ENABLE_GOOGLE_API": request.app.state.config.ENABLE_GOOGLE_API,
            "GOOGLE_API_BASE_URLS": request.app.state.config.GOOGLE_API_BASE_URLS,
            "GOOGLE_API_KEYS": request.app.state.config.GOOGLE_API_KEYS,
        }
    except Exception as e:
        log.exception(f"Failed to update Google config: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid Google config: {e}")



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


@router.get("/config")
async def get_config(request: Request, user=Depends(get_admin_user)):
    # Return current Google configuration. If encrypted provider credentials exist, do not include plaintext API keys.
    creds = getattr(request.app.state.config, "MODEL_PROVIDER_CREDENTIALS", None) or {}
    google_creds = creds.get("google", {})

    # Do not expose plaintext keys if encrypted creds exist
    if google_creds.get("api_key_encrypted"):
        keys = []
    else:
        keys = getattr(request.app.state.config, "GOOGLE_API_KEYS", []) or []

    return {
        "ENABLE_GOOGLE_API": request.app.state.config.ENABLE_GOOGLE_API,
        "GOOGLE_API_BASE_URLS": request.app.state.config.GOOGLE_API_BASE_URLS,
        "GOOGLE_API_KEYS": keys,
        "MODEL_PROVIDER_CREDENTIALS": creds,
    }


class ProviderCredentialsForm(BaseModel):
    provider: str
    api_key: Optional[str] = None


@router.post("/credentials/set")
async def set_credentials(request: Request, form_data: ProviderCredentialsForm, user=Depends(get_admin_user)):
    # Store encrypted provider API key in persistent config under MODEL_PROVIDER_CREDENTIALS
    creds = getattr(request.app.state.config, "MODEL_PROVIDER_CREDENTIALS", None) or {}
    if form_data.api_key:
        # Store as JSON object to avoid double-encoding confusion later
        encrypted = encrypt_data({"api_key": form_data.api_key})
        creds[form_data.provider] = {"api_key_encrypted": encrypted}
    else:
        # remove
        if form_data.provider in creds:
            del creds[form_data.provider]

    request.app.state.config.MODEL_PROVIDER_CREDENTIALS = creds

    # Clear model caches to ensure new credentials are picked up immediately
    try:
        request.app.state.BASE_MODELS = []
        request.app.state.MODELS = {}
        request.app.state.OPENAI_MODELS = {}
        request.app.state.GOOGLE_MODELS = {}
    except Exception:
        pass

    return {"status": True}


@router.get("/credentials/get")
async def get_credentials(request: Request, provider: str, user=Depends(get_admin_user)):
    creds = getattr(request.app.state.config, "MODEL_PROVIDER_CREDENTIALS", None) or {}
    provider_creds = creds.get(provider, {})
    if provider_creds.get("api_key_encrypted"):
        # return masked
        return {"masked": True, "value": "****"}
    return {"masked": False, "value": None}




async def generate_chat_completion(request: Request, form_data: dict, user: UserModel, bypass_filter: bool = False):
    """Generate a chat completion using the configured Google Generative API for a given model."""
    # Ensure google models are loaded
    await get_all_models(request, user=user)

    model_id = form_data.get("model")
    if not model_id:
        raise HTTPException(status_code=400, detail="Model not specified")

    # Check if this is a custom model preset and resolve the base model
    model_info = Models.get_model_by_id(model_id)
    if model_info and model_info.base_model_id:
        base_model_id = (
            request.base_model_id
            if hasattr(request, "base_model_id")
            else model_info.base_model_id
        )
        form_data["model"] = base_model_id
        model_id = base_model_id
        log.info(f"Resolved custom model preset to base model: {base_model_id}")

        # Apply model params (system prompt, etc.) from the custom preset
        params = model_info.params.model_dump() if model_info.params else {}
        if params:
            system = params.pop("system", None)
            metadata = form_data.pop("metadata", None)
            form_data = apply_model_params_to_body_openai(params, form_data)
            log.warning(f"DEBUG google.py: user={user}, user.name={getattr(user, 'name', 'NO_NAME_ATTR')}")
            form_data = apply_system_prompt_to_body(system, form_data, metadata, user)

    google_models = getattr(request.app.state, "GOOGLE_MODELS", {}) or {}
    if model_id not in google_models:
        raise HTTPException(status_code=404, detail="Model not found")

    google_model = google_models[model_id]
    idx = google_model.get("urlIdx", 0)

    base_urls = getattr(request.app.state.config, "GOOGLE_API_BASE_URLS", []) or []
    if idx >= len(base_urls):
        raise HTTPException(status_code=500, detail="Google API base URL not configured for model")

    base_url = base_urls[idx]

    # Resolve API key from encrypted credentials or plaintext config
    creds = getattr(request.app.state.config, "MODEL_PROVIDER_CREDENTIALS", None) or {}
    google_creds = creds.get("google", {})
    api_key = None

    # Prefer encrypted provider credentials (handles legacy double-encoding)
    api_key = _extract_api_key_from_encrypted(google_creds) or api_key

    if not api_key:
        keys = getattr(request.app.state.config, "GOOGLE_API_KEYS", []) or []
        if len(keys) > idx:
            api_key = keys[idx]

    if not api_key:
        raise HTTPException(status_code=500, detail="Google API key not configured")

    DATA_IMAGE_URL_RE = re.compile(
        r"^data:(?P<mime>[^;]+);base64,(?P<data>.+)$",
        re.IGNORECASE | re.DOTALL,
    )
    FILE_ID_FROM_URL_RE = re.compile(r"/api/v\d+/files/(?P<id>[^/]+)")

    def _get_inline_part_from_image_url(url: str) -> Optional[dict]:
        if not url or not isinstance(url, str):
            return None

        # Already a data URL
        m = DATA_IMAGE_URL_RE.match(url)
        if m:
            mime_type = (m.group("mime") or "").strip() or "image/png"
            data = (m.group("data") or "").strip()
            if not data:
                return None
            return {"inline_data": {"mime_type": mime_type, "data": data}}

        # Try to extract a file id from common internal URLs (/api/v1/files/{id}/...)
        file_id: Optional[str] = None
        m2 = FILE_ID_FROM_URL_RE.search(url)
        if m2:
            file_id = m2.group("id")
        elif not url.startswith("http"):
            # Many call sites pass a bare file id
            file_id = url

        if not file_id:
            return None

        try:
            from open_webui.utils.files import get_image_base64_from_file_id

            b64_url = get_image_base64_from_file_id(file_id)
            if not b64_url:
                return None
            m3 = DATA_IMAGE_URL_RE.match(b64_url)
            if not m3:
                return None
            mime_type = (m3.group("mime") or "").strip() or "image/png"
            data = (m3.group("data") or "").strip()
            if not data:
                return None
            return {"inline_data": {"mime_type": mime_type, "data": data}}
        except Exception:
            return None

    def _collect_inline_image_parts(messages: list[dict]) -> list[dict]:
        parts: list[dict] = []
        for msg in messages or []:
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") != "image_url":
                    continue

                image_url_obj = part.get("image_url")
                url = None
                if isinstance(image_url_obj, dict):
                    url = image_url_obj.get("url")
                elif isinstance(image_url_obj, str):
                    url = image_url_obj

                inline_part = _get_inline_part_from_image_url(url)
                if inline_part:
                    parts.append(inline_part)
                else:
                    log.debug("Unable to convert image_url to inline_data (url=%s)", url)
        return parts

    # Compose a simple prompt from messages (system + conversation)
    messages = form_data.get("messages", [])
    composed = ""
    try:
        for msg in messages:
            role = msg.get("role", "user")
            content = ""
            if isinstance(msg.get("content"), list):
                # openai style content list
                for part in msg.get("content"):
                    if isinstance(part, dict) and part.get("type") == "text":
                        content += part.get("text", "")
                    elif isinstance(part, str):
                        content += part
            elif isinstance(msg.get("content"), str):
                content = msg.get("content")

            composed += f"{role.upper()}: {content}\n"
    except Exception:
        composed = ""

    # Map some params
    google_payload = {"prompt": {"text": composed or form_data.get("prompt", "")}}
    if form_data.get("temperature") is not None:
        google_payload["temperature"] = form_data.get("temperature")
    if form_data.get("max_completion_tokens") is not None:
        google_payload["max_output_tokens"] = form_data.get("max_completion_tokens")
    elif form_data.get("max_tokens") is not None:
        google_payload["max_output_tokens"] = form_data.get("max_tokens")

    async def _stream_google_generate_content(
        *,
        session: aiohttp.ClientSession,
        response: aiohttp.ClientResponse,
        model_for_template: str,
        failover_notice: str = "",
    ):
        from open_webui.routers.openai import _extract_text_from_google_response

        accumulated = ""
        buffer = ""
        sent_notice = False

        event_lines: list[str] = []
        async for chunk in response.content.iter_any():
            if not chunk:
                continue
            
            # Send failover notice as first chunk if applicable and not yet sent
            if failover_notice and not sent_notice:
                notice_msg = openai_chat_chunk_message_template(model_for_template, failover_notice)
                yield f"data: {json.dumps(notice_msg)}\n\n"
                sent_notice = True

            try:
                buffer += chunk.decode("utf-8", errors="ignore")
            except Exception:
                continue

            # The stream may be SSE (multiple "data:" lines per event) or NDJSON.
            # Accumulate lines into an event buffer until an empty line (event separator) is seen.
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                stripped = line.strip()

                # Event boundary (empty line) => process accumulated event_lines
                if stripped == "":
                    if not event_lines:
                        continue

                    # Merge data: lines into a single payload (preserve newlines between parts)
                    payload_parts: list[str] = []
                    for ev in event_lines:
                        if ev.startswith("data:"):
                            payload_parts.append(ev[len("data:") :].strip())
                        else:
                            payload_parts.append(ev)

                    event_lines = []
                    event_text = "\n".join(payload_parts)

                    if not event_text:
                        continue

                    if event_text == "[DONE]":
                        # End of stream
                        buffer = ""
                        break

                    # Try to parse JSON first, fall back to raw text when parsing fails
                    obj = None
                    text_piece = None
                    try:
                        obj = json.loads(event_text)
                        text_piece = _extract_text_from_google_response(obj)
                    except Exception:
                        # Not JSON; treat as plain text chunk
                        text_piece = event_text

                    if not text_piece:
                        continue

                    # Convert cumulative -> delta to avoid duplication
                    delta = ""
                    if text_piece.startswith(accumulated):
                        delta = text_piece[len(accumulated) :]
                    elif accumulated.startswith(text_piece):
                        delta = ""
                    else:
                        delta = text_piece

                    if not delta:
                        continue

                    accumulated += delta
                    message = openai_chat_chunk_message_template(model_for_template, delta)
                    yield f"data: {json.dumps(message)}\n\n"

                    continue

                # Not an event boundary, collect line
                event_lines.append(stripped)

            # end while

        # If there are leftover event_lines after the stream ends, process them
        if event_lines:
            payload_parts = []
            for ev in event_lines:
                if ev.startswith("data:"):
                    payload_parts.append(ev[len("data:") :].strip())
                else:
                    payload_parts.append(ev)
            event_text = "\n".join(payload_parts)
            try:
                obj = json.loads(event_text)
                text_piece = _extract_text_from_google_response(obj)
            except Exception:
                text_piece = event_text

            if text_piece:
                delta = ""
                if text_piece.startswith(accumulated):
                    delta = text_piece[len(accumulated) :]
                elif accumulated.startswith(text_piece):
                    delta = ""
                else:
                    delta = text_piece
                if delta:
                    accumulated += delta
                    message = openai_chat_chunk_message_template(model_for_template, delta)
                    log.debug("Google stream final chunk delta length=%s", len(delta))
                    yield f"data: {json.dumps(message)}\n\n"
        finish_message = openai_chat_chunk_message_template(model_for_template, "")
        finish_message["choices"][0]["finish_reason"] = "stop"
        log.debug("Google stream finished, sending final chunk")
        yield f"data: {json.dumps(finish_message)}\n\n"
        log.debug("Google stream finished, sending [DONE]")
        yield "data: [DONE]\n\n"


    def _build_thinking_config(model_name_str: str) -> Optional[dict]:
        """Build thinking config based on model type.
        
        Gemini 3: uses thinkingLevel ("minimal", "low", "medium", "high")
                  Default is "high" which causes very slow responses.
                  We default to "low" for faster responses.
        Gemini 2.5: uses thinkingBudget (0 to disable, -1 for dynamic)
        
        Config goes inside generationConfig.thinkingConfig
        """
        if not model_name_str:
            return None
        
        model_lower = model_name_str.lower()
        
        # Gemini 3 models use thinkingLevel
        # Default "high" causes 10+ minute delays, so we use "low"
        if "gemini-3" in model_lower:
            level = GEMINI_THINKING_LEVEL  # Default: "low"
            # Flash supports "minimal", Pro only supports "low" or "high"
            if "pro" in model_lower and level == "minimal":
                level = "low"
            return {"generationConfig": {"thinkingConfig": {"thinkingLevel": level.upper()}}}
        
        # Gemini 2.5 models use thinkingBudget
        if "gemini-2.5" in model_lower or "gemini-2" in model_lower:
            # 2.5 Pro cannot disable thinking, but we can set a low budget
            # 2.5 Flash can disable with budget=0
            budget = GEMINI_25_THINKING_BUDGET
            if "pro" in model_lower and budget == 0:
                # Pro cannot disable, use minimum budget instead
                budget = 128
            return {"generationConfig": {"thinkingConfig": {"thinkingBudget": budget}}}
        
        return None

    def _build_google_candidate_payloads(text_payload: str, inline_image_parts: Optional[list[dict]] = None) -> list[dict]:
        candidate_payloads: list[dict] = []
        parts: list[dict] = [{"text": text_payload}]
        if inline_image_parts:
            parts.extend(inline_image_parts)

        # Gemini multimodal uses contents[].parts[] with inline_data.
        p_contents = {"contents": [{"parts": parts}]}
        p3 = {"input": {"text": text_payload}}
        p2 = {"input": [{"text": text_payload}]}
        p1 = {"prompt": {"text": text_payload}}

        # Get thinking config based on model
        thinking_config = _build_thinking_config(model_name)

        for p in [p_contents, p3, p2, p1]:
            p = p.copy()
            if form_data.get("temperature") is not None:
                p["temperature"] = form_data.get("temperature")
            # Add thinking config to payloads that support it (contents-based)
            if thinking_config and "contents" in p:
                p.update(thinking_config)
            candidate_payloads.append(p)

        return candidate_payloads


    try:
        timeout = aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT)
        overall_start = time.monotonic()

        use_key_param = isinstance(api_key, str) and api_key.startswith("AIza")
        headers = {"Content-Type": "application/json"}
        if not use_key_param:
            headers["Authorization"] = f"Bearer {api_key}"

        model_name = google_model.get("google", {}).get("name") or google_model.get("id")
        if isinstance(model_name, str) and model_name.startswith("models/"):
            model_name = model_name.split("/", 1)[1]

        # Prefer generateContent (works for many Gemini models), try generate as fallback
        streaming_requested = bool(form_data.get("stream"))

        if streaming_requested:
            stream_endpoints = []
            if isinstance(model_name, str) and "/" in model_name:
                stream_endpoints.append(f"{base_url}/{model_name}:streamGenerateContent")
            else:
                stream_endpoints.append(f"{base_url}/models/{model_name}:streamGenerateContent")

            text_payload = composed or form_data.get("prompt", "") or ""
            inline_image_parts = _collect_inline_image_parts(messages)
            candidate_payloads = _build_google_candidate_payloads(text_payload, inline_image_parts)
            log.info("Built %d candidate payloads, first has generationConfig: %s", 
                     len(candidate_payloads), 
                     candidate_payloads[0].get("generationConfig") if candidate_payloads else None)

            stream_session = aiohttp.ClientSession(trust_env=True, timeout=timeout)
            stream_started = False
            try:
                last_error: dict | None = None
                for endpoint in stream_endpoints:
                    for body_candidate in candidate_payloads:
                        # Gemini REST streaming uses SSE when alt=sse is set.
                        # Use ?alt=sse for bearer-token auth and &alt=sse when using ?key=.
                        url = f"{endpoint}?alt=sse" if not use_key_param else f"{endpoint}?key={api_key}&alt=sse"
                        safe_url = endpoint
                        
                        # Retry loop for transient errors on this specific request
                        for retry_attempt in range(GOOGLE_MAX_RETRIES + 1):
                            await _sleep_for_retry(retry_attempt, "transient error")
                            attempt_start = time.monotonic()
                            try:
                                log.info(
                                    "Trying Google streaming endpoint %s with payload keys: %s",
                                    safe_url,
                                    list(body_candidate.keys()),
                                )
                                r = await stream_session.post(
                                    url,
                                    json=body_candidate,
                                    headers={**headers, "Accept": "text/event-stream"}
                                    if not use_key_param
                                    else {"Content-Type": "application/json"},
                                    ssl=AIOHTTP_CLIENT_SESSION_SSL,
                                )

                                attempt_ms = int((time.monotonic() - attempt_start) * 1000)

                                if r.status >= 400:
                                    try:
                                        err_json = await r.json()
                                    except Exception:
                                        err_json = None
                                    try:
                                        err_text = await r.text()
                                    except Exception:
                                        err_text = None

                                    log.warning(
                                        "Google streaming API returned status %s for %s duration_ms=%s",
                                        r.status,
                                        safe_url,
                                        attempt_ms,
                                    )
                                    last_error = {
                                        "status": r.status,
                                        "url": safe_url,
                                        "duration_ms": attempt_ms,
                                        "json": err_json,
                                        "text": err_text,
                                    }
                                    r.release()
                                    # On retryable errors (429, 500, 503, etc.), retry this request
                                    if _is_retryable_google_error(r.status, err_json) and retry_attempt < GOOGLE_MAX_RETRIES:
                                        continue  # Retry same request
                                    break  # Try next payload candidate

                                log.info(
                                    "Google streaming call started: %s status=%s duration_ms=%s",
                                    safe_url,
                                    r.status,
                                    attempt_ms,
                                )

                                overall_ms = int((time.monotonic() - overall_start) * 1000)
                                log.info(
                                    "Google streaming generation started duration_ms=%s",
                                    overall_ms,
                                )

                                stream_started = True
                                
                                # Check if this is a failover response
                                failover_model_used = getattr(request.state, "_failover_model", None)
                                stream_failover_notice = ""
                                if failover_model_used:
                                    stream_failover_notice = f"*[Note: Response from {failover_model_used} due to primary model unavailability]*\n\n"
                                    log.info(f"Failover successful (streaming): using {failover_model_used}")
                                
                                return StreamingResponse(
                                    _stream_google_generate_content(
                                        session=stream_session,
                                        response=r,
                                        model_for_template=form_data.get("model") or str(model_name),
                                        failover_notice=stream_failover_notice,
                                    ),
                                    media_type="text/event-stream",
                                    background=BackgroundTask(
                                        _cleanup_google_streaming, response=r, session=stream_session
                                    ),
                                )
                            except Exception as e:
                                log.exception(e)
                                last_error = {
                                    "status": None,
                                    "url": safe_url,
                                    "duration_ms": None,
                                    "json": None,
                                    "text": str(e),
                                }
                                break  # Don't retry on other exceptions

                # If streaming couldn't be established, fall back to non-streaming generation
                log.warning(
                    "Google streaming unavailable; falling back to non-stream response. last_error=%s",
                    last_error,
                )
            finally:
                if not stream_started:
                    await stream_session.close()

        async with aiohttp.ClientSession(trust_env=True, timeout=timeout) as session:
            endpoints = []
            if isinstance(model_name, str) and "/" in model_name:
                endpoints.append(f"{base_url}/{model_name}:generateContent")
                endpoints.append(f"{base_url}/{model_name}:generate")
            else:
                endpoints.append(f"{base_url}/models/{model_name}:generateContent")
                endpoints.append(f"{base_url}/models/{model_name}:generate")

            # Candidate payload shapes (prioritize contents and input object; remove 'instances' which some endpoints reject)
            text_payload = composed or form_data.get("prompt", "") or ""
            inline_image_parts = _collect_inline_image_parts(messages)
            candidate_payloads = _build_google_candidate_payloads(text_payload, inline_image_parts)

            errors = []
            res = None

            for endpoint in endpoints:
                for body_candidate in candidate_payloads:
                    # Retry loop for transient errors on this specific request
                    for retry_attempt in range(GOOGLE_MAX_RETRIES + 1):
                        await _sleep_for_retry(retry_attempt, "transient error")
                        try:
                            url = endpoint if not use_key_param else f"{endpoint}?key={api_key}"
                            safe_url = endpoint
                            attempt_start = time.monotonic()
                            log.info(
                                "Trying Google endpoint %s with payload keys: %s",
                                safe_url,
                                list(body_candidate.keys()),
                            )

                            async with session.post(
                                url,
                                json=body_candidate,
                                headers=headers
                                if not use_key_param
                                else {"Content-Type": "application/json"},
                                ssl=AIOHTTP_CLIENT_SESSION_SSL,
                            ) as r:
                                body_text = None
                                body_json = None
                                try:
                                    body_json = await r.json()
                                except Exception:
                                    try:
                                        body_text = await r.text()
                                    except Exception:
                                        body_text = None

                                attempt_ms = int((time.monotonic() - attempt_start) * 1000)

                                if r.status < 400:
                                    res = body_json if body_json is not None else (body_text or {})
                                    log.info(
                                        "Google call succeeded: %s status=%s duration_ms=%s",
                                        safe_url,
                                        r.status,
                                        attempt_ms,
                                    )
                                    break
                                else:
                                    log.warning(
                                        "Google API returned status %s for %s duration_ms=%s",
                                        r.status,
                                        safe_url,
                                        attempt_ms,
                                    )
                                    errors.append(
                                        {
                                            "status": r.status,
                                            "url": safe_url,
                                            "duration_ms": attempt_ms,
                                            "json": body_json,
                                            "text": body_text,
                                        }
                                    )
                                    # On retryable errors (429, 500, 503, etc.), retry this request
                                    if _is_retryable_google_error(r.status, body_json) and retry_attempt < GOOGLE_MAX_RETRIES:
                                        continue  # Retry same request
                                    break  # Try next payload candidate
                        except Exception as e:
                            log.exception(e)
                            errors.append(
                                {
                                    "status": None,
                                    "url": endpoint,
                                    "duration_ms": None,
                                    "json": None,
                                    "text": str(e),
                                }
                            )
                            break  # Don't retry on other exceptions
                    if res is not None:
                        break
                if res is not None:
                    break

            overall_ms = int((time.monotonic() - overall_start) * 1000)
            log.info(
                "Google generation finished duration_ms=%s attempts=%s",
                overall_ms,
                len(errors) + (1 if res is not None else 0),
            )

            if res is None:
                # Prefer the first structured JSON error that contains an 'error' key
                status_code = 500
                body = "No response from Google"
                preferred_error = None
                for e in errors:
                    if e.get("json") and isinstance(e.get("json"), dict) and "error" in e.get("json"):
                        preferred_error = e
                        break
                if preferred_error:
                    status_code = preferred_error.get("status")
                    body = preferred_error.get("json")
                else:
                    # fallback to the first non-empty text response
                    for e in errors:
                        if e.get("text"):
                            status_code = e.get("status")
                            body = e.get("text")
                            break
                    else:
                        if errors:
                            status_code = errors[-1].get("status")
                            body = ""

                # If Google returned a structured error with fieldViolations, extract meaningful messages
                try:
                    if isinstance(body, dict) and "error" in body:
                        err = body.get("error", {})
                        details = err.get("details") or []
                        messages = []
                        for d in details:
                            # fieldViolations often appear in 'details'
                            if isinstance(d, dict) and d.get("fieldViolations"):
                                for fv in d.get("fieldViolations", []):
                                    if fv.get("description"):
                                        messages.append(fv.get("description"))
                            # Some responses include 'message' at this level
                            if isinstance(d, dict) and d.get("message"):
                                messages.append(d.get("message"))
                        if messages:
                            body = {"google_error": ", ".join(messages)}
                        elif err.get("message"):
                            body = {"google_error": err.get("message")}
                except Exception:
                    pass

                # Include per-endpoint errors in the log for debugging
                log.warning(f"Google generation failed: chosen_status={status_code} chosen_body={body} attempts={errors}")

                # If we got a 404, attempt to fetch the model list for the configured base_url to provide hints
                available_models = None
                try:
                    if status_code == 404 and base_url:
                        models_resp = await send_get_request(f"{base_url}/models", api_key, user=user)
                        if isinstance(models_resp, dict):
                            # collect a small sample of model names to include as a hint
                            mm = [m.get('name') or m.get('id') or m.get('model') for m in models_resp.get('models', [])[:10]]
                            available_models = mm
                except Exception:
                    pass

                # Return a clean error message to user (full details already logged above)
                # Check if we should attempt failover to a different model
                elapsed_seconds = (time.monotonic() - overall_start)
                original_model = form_data.get("model", model_name)
                failover_model = _get_failover_model(original_model)
                failover_attempted = getattr(request.state, "_failover_attempted", False)
                
                # Trigger failover on any error OR if total time exceeded threshold
                should_failover = (
                    failover_model
                    and not failover_attempted
                    and original_model != failover_model
                    and (errors or elapsed_seconds > GOOGLE_FAILOVER_TIMEOUT)
                )
                
                if should_failover:
                    log.info(
                        f"Primary model {original_model} failed (errors={len(errors)}, elapsed={elapsed_seconds:.1f}s), "
                        f"attempting failover to {failover_model}"
                    )
                    request.state._failover_attempted = True
                    request.state._failover_model = failover_model  # Track which model we fell back to
                    form_data["model"] = failover_model
                    try:
                        return await generate_chat_completion(request, form_data, user, bypass_filter)
                    except HTTPException as fallback_err:
                        log.warning(f"Failover to {failover_model} also failed: {fallback_err.detail}")
                        # Continue to raise original error
                    except Exception as fallback_err:
                        log.warning(f"Failover to {failover_model} failed with exception: {fallback_err}")

                if status_code == 503:
                    detail = "The model is currently overloaded. Please try again in a moment, or use a different model."
                elif status_code == 404:
                    detail = f"Model not found: {model_name}"
                    if available_models:
                        detail += f". Available models include: {', '.join(available_models[:5])}"
                elif status_code == 429:
                    detail = "Rate limit exceeded. Please wait a moment before trying again."
                elif isinstance(body, dict) and body.get("google_error"):
                    detail = body.get("google_error")
                else:
                    detail = f"Google API error ({status_code})"
                raise HTTPException(status_code=status_code or 500, detail=detail)

            from open_webui.routers.openai import _extract_text_from_google_response
            text_out = _extract_text_from_google_response(res)
            
            # Add subtle notice if we used a failover model
            failover_model_used = getattr(request.state, "_failover_model", None)
            failover_notice = ""
            if failover_model_used:
                failover_notice = f"*[Note: Response from {failover_model_used} due to primary model unavailability]*\n\n"
                log.info(f"Failover successful: using {failover_model_used}")

            if form_data.get("stream"):
                async def _stream_single_message():
                    # Send failover notice as first chunk if applicable
                    if failover_notice:
                        notice_msg = openai_chat_chunk_message_template(form_data.get("model") or str(model_name), failover_notice)
                        yield f"data: {json.dumps(notice_msg)}\n\n"
                    msg = openai_chat_chunk_message_template(form_data.get("model") or str(model_name), text_out)
                    yield f"data: {json.dumps(msg)}\n\n"
                    finish_message = openai_chat_chunk_message_template(form_data.get("model") or str(model_name), "")
                    finish_message["choices"][0]["finish_reason"] = "stop"
                    log.debug("Streaming fallback: sending final chunk and [DONE]")
                    yield f"data: {json.dumps(finish_message)}\n\n"
                    yield "data: [DONE]\n\n"

                return StreamingResponse(_stream_single_message(), media_type="text/event-stream")

            return {
                "id": f"google-{model_name}",
                "object": "chat.completion",
                "choices": [
                    {"message": {"role": "assistant", "content": failover_notice + text_out}, "finish_reason": "stop"}
                ],
            }
    except HTTPException:
        raise
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=500, detail="Failed to call Google Generative API")


async def _cleanup_google_streaming(
    response: Optional[aiohttp.ClientResponse],
    session: Optional[aiohttp.ClientSession],
):
    try:
        if response:
            response.close()
    finally:
        if session:
            await session.close()


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
