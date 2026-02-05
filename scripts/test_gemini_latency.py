#!/usr/bin/env python3

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import Any, Optional

import aiohttp


def _read_api_key(key_file: Path) -> str:
    key = key_file.expanduser().read_text(encoding="utf-8").strip()
    if not key:
        raise SystemExit(f"API key file is empty: {key_file}")
    return key


async def _get_json(session: aiohttp.ClientSession, url: str) -> Any:
    async with session.get(url) as resp:
        text = await resp.text()
        if resp.status >= 400:
            raise RuntimeError(f"GET {url} -> {resp.status}: {text[:500]}")
        try:
            return json.loads(text)
        except Exception as e:
            raise RuntimeError(f"Failed to parse JSON from GET {url}: {e}: {text[:500]}")


def _pick_model_id(models_json: Any, preferred_substring: str) -> Optional[str]:
    if not isinstance(models_json, dict):
        return None
    models = models_json.get("models")
    if not isinstance(models, list):
        return None

    # Each model often looks like {"name": "models/gemini-...", ...}
    candidates: list[str] = []
    for m in models:
        if not isinstance(m, dict):
            continue
        name = m.get("name") or m.get("id")
        if isinstance(name, str) and name:
            candidates.append(name)

    # Prefer exact-ish matches
    for name in candidates:
        short = name.split("/", 1)[1] if name.startswith("models/") else name
        if preferred_substring in short:
            return short

    return None


async def _post_json(session: aiohttp.ClientSession, url: str, payload: dict[str, Any]) -> tuple[int, Any, dict[str, str]]:
    async with session.post(url, json=payload) as resp:
        headers = {k.lower(): v for k, v in resp.headers.items()}
        text = await resp.text()
        if not text:
            return resp.status, None, headers
        try:
            return resp.status, json.loads(text), headers
        except Exception:
            return resp.status, text, headers


def _extract_text(result: Any) -> str:
    # v1beta generateContent usually returns: {"candidates": [{"content": {"parts": [{"text": "..."}]}}]}
    try:
        if not isinstance(result, dict):
            return ""
        candidates = result.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return ""
        content = candidates[0].get("content")
        if not isinstance(content, dict):
            return ""
        parts = content.get("parts")
        if not isinstance(parts, list) or not parts:
            return ""
        text = parts[0].get("text")
        return text if isinstance(text, str) else ""
    except Exception:
        return ""


async def main() -> None:
    parser = argparse.ArgumentParser(description="Measure Gemini (Google Generative Language API) latency.")
    parser.add_argument("--key-file", default="~/gary_gemini_api_key", help="Path to API key file")
    parser.add_argument(
        "--base-url",
        default="https://generativelanguage.googleapis.com/v1beta",
        help="API base URL (default: v1beta)",
    )
    parser.add_argument(
        "--model",
        default="gemini-2.5-pro",
        help="Preferred model id (script will try to auto-detect a matching deployed model)",
    )
    parser.add_argument("--runs", type=int, default=5, help="Number of timed calls")
    parser.add_argument("--timeout", type=float, default=60.0, help="Per-request timeout seconds")
    parser.add_argument("--prompt", default="Reply with the single word: pong", help="Prompt to send")

    args = parser.parse_args()

    key = _read_api_key(Path(args.key_file))
    base_url = args.base_url.rstrip("/")

    timeout = aiohttp.ClientTimeout(total=float(args.timeout))
    connector = aiohttp.TCPConnector(ssl=True)

    async with aiohttp.ClientSession(timeout=timeout, connector=connector, trust_env=True) as session:
        # 1) Discover model id (best-effort)
        models_url = f"{base_url}/models?key={key}"
        t0 = time.monotonic()
        models_json = await _get_json(session, models_url)
        models_ms = int((time.monotonic() - t0) * 1000)

        discovered = _pick_model_id(models_json, preferred_substring=args.model)
        model_id = discovered or args.model

        # 2) Time generateContent
        gen_endpoint = f"{base_url}/models/{model_id}:generateContent?key={key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": args.prompt}]}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 16},
        }

        print(f"Models list: {models_ms} ms")
        print(f"Model: {model_id}{' (auto-detected)' if discovered else ' (requested)'}")

        durations_ms: list[int] = []
        last_status: Optional[int] = None
        last_text: str = ""

        for i in range(args.runs):
            start = time.monotonic()
            status, result, headers = await _post_json(session, gen_endpoint, payload)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            durations_ms.append(elapsed_ms)
            last_status = status

            text_out = _extract_text(result)
            if not text_out and isinstance(result, dict) and "error" in result:
                text_out = f"ERROR: {result.get('error')}"
            elif not text_out and isinstance(result, str):
                text_out = result

            last_text = text_out
            req_id = headers.get("x-request-id") or headers.get("x-goog-request-id") or ""
            req_id_str = f" request_id={req_id}" if req_id else ""

            print(f"Run {i+1}/{args.runs}: status={status} {elapsed_ms} ms{req_id_str}")

        durations_ms_sorted = sorted(durations_ms)
        p95 = durations_ms_sorted[max(0, int(round(0.95 * (len(durations_ms_sorted) - 1))))]

        print(
            "Summary:",
            f"min={min(durations_ms)} ms",
            f"avg={int(statistics.mean(durations_ms))} ms",
            f"p95={p95} ms",
            f"max={max(durations_ms)} ms",
            f"last_status={last_status}",
        )
        if last_text:
            snippet = last_text.replace("\n", " ").strip()
            print(f"Last response text (snippet): {snippet[:160]}")


if __name__ == "__main__":
    asyncio.run(main())
