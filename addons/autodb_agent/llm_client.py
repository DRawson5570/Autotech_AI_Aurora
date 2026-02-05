"""
AutoDB LLM Client.

Handles calls to Gemini and Ollama with retry logic for rate limiting.
"""

import asyncio
import json
import logging
import re
from typing import Optional

import httpx

from .config import config, get_gemini_api_key
from .models import LLMResponse

log = logging.getLogger("autodb_agent.llm")


class LLMClient:
    """Client for LLM API calls with retry logic."""
    
    def __init__(self, model: str = None):
        self.model = model or config.model
        self.client = httpx.AsyncClient(timeout=60)
        self._total_tokens = 0
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    @property
    def total_tokens_used(self) -> int:
        """Total tokens used across all calls."""
        return self._total_tokens
    
    async def call(
        self,
        system_prompt: str,
        user_message: str,
        max_retries: int = None,
    ) -> LLMResponse:
        """
        Call the LLM with retry logic for rate limiting.
        
        Returns LLMResponse with content and usage stats.
        """
        max_retries = max_retries or config.llm_max_retries
        
        # Proactive delay between calls
        await asyncio.sleep(config.llm_delay_between_calls)
        
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                if self.model.startswith("gemini"):
                    response = await self._call_gemini(system_prompt, user_message)
                else:
                    response = await self._call_ollama(system_prompt, user_message)
                
                self._total_tokens += response.total_tokens
                return response
                
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status in (429, 503) and attempt < max_retries:
                    delay = config.llm_retry_base_delay * (2 ** attempt)
                    log.warning(
                        f"LLM rate limited (status {status}), retry {attempt + 1}/{max_retries} in {delay}s"
                    )
                    await asyncio.sleep(delay)
                    last_error = e
                    continue
                raise
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    delay = config.llm_retry_base_delay * (2 ** attempt)
                    log.warning(f"LLM error: {e}, retry {attempt + 1}/{max_retries} in {delay}s")
                    await asyncio.sleep(delay)
                    continue
                raise
        
        raise last_error or Exception("LLM call failed after retries")
    
    async def _call_gemini(self, system_prompt: str, user_message: str) -> LLMResponse:
        """Call Gemini API."""
        api_key = get_gemini_api_key()
        if not api_key:
            raise RuntimeError("Gemini API key not found")
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={api_key}"
        
        # Combine system + user into single prompt (Gemini style)
        combined_prompt = f"{system_prompt}\n\n{user_message}"
        
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": combined_prompt}]}
            ],
            "generationConfig": {
                "temperature": config.llm_temperature,
                "maxOutputTokens": config.llm_max_tokens,
            }
        }
        
        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        
        # Extract text
        text = ""
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                text = parts[0].get("text", "")
        
        # Extract usage
        usage = {}
        usage_meta = data.get("usageMetadata", {})
        if usage_meta:
            usage = {
                "prompt_tokens": usage_meta.get("promptTokenCount", 0),
                "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
                "total_tokens": usage_meta.get("totalTokenCount", 0),
            }
        
        return LLMResponse(content=text, usage=usage)
    
    async def _call_ollama(self, system_prompt: str, user_message: str) -> LLMResponse:
        """Call Ollama API."""
        url = f"{config.ollama_url}/api/chat"
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
            "keep_alive": -1,  # Keep model loaded indefinitely
            "options": {
                "temperature": config.llm_temperature,
                "num_predict": config.ollama_num_predict,
                "num_ctx": config.ollama_num_ctx,
            },
        }
        
        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        
        # Extract text
        text = data.get("message", {}).get("content", "")
        
        # Extract usage
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
        
        return LLMResponse(content=text, usage=usage)


def parse_llm_action(content: str) -> dict:
    """
    Parse LLM response to extract tool action.
    
    Expected format: {"tool": "click", "link_text": "..."}
    """
    log.debug(f"Parsing LLM response: {content[:200]}...")
    
    # First try to directly extract link_text if present - more reliable than JSON parsing
    # The link text might contain brackets [] which breaks JSON regex
    link_match = re.search(r'"link_text"\s*:\s*"([^"]+)"?', content)
    if link_match:
        link_text = link_match.group(1)
        log.debug(f"Extracted link_text: {link_text}")
        return {"tool": "click", "link_text": link_text}
    
    # Try to find JSON in response (for extract/go_back which have no link_text)
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}', content, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            log.debug(f"Parsed action: {parsed}")
            return parsed
        except json.JSONDecodeError as e:
            log.warning(f"JSON parse error: {e}")
    
    # Fallback: look for tool keywords
    content_lower = content.lower()
    if "extract" in content_lower:
        return {"tool": "extract"}
    if "go_back" in content_lower or "go back" in content_lower:
        return {"tool": "go_back"}
    
    # Default to extract if we can't parse
    log.warning(f"Could not parse action from: {content[:100]}")
    return {"tool": "extract"}
