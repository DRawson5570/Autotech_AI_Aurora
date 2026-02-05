"""Token counting utilities with fallbacks.

Provides a small wrapper that tries to use 'tiktoken' when available and falls
back to a simple BPE-like heuristic using the Python standard library when not.

Functions:
- count_tokens_for_model(text, model_name): returns estimated token count (int)

The implementation here is intentionally small and easy to review; for better
accuracy we can add a light-weight dependency like 'tiktoken' or 'huggingface/transformers'.
"""

from typing import Optional


def _simple_tokenizer(text: str) -> int:
    # Very small heuristic: split on whitespace and punctuation
    import re

    tokens = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
    return len(tokens)


def count_tokens_for_model(text: str, model_name: Optional[str] = None) -> int:
    """Return estimated token count for `text` targeting `model_name`.

    Attempts to use tiktoken if present for better accuracy; otherwise uses a
    simple heuristic that counts words and punctuation as tokens.
    """
    try:
        import tiktoken  # type: ignore

        # Map a model to a tiktoken encoding if possible; fall back to cl100k_base
        enc_name = None
        if model_name:
            if model_name.startswith("gpt-4"):
                enc_name = "cl100k_base"
            elif model_name.startswith("gpt-3.5"):
                enc_name = "cl100k_base"

        if not enc_name:
            enc_name = "cl100k_base"

        enc = tiktoken.get_encoding(enc_name)
        return len(enc.encode(text))
    except Exception:
        return _simple_tokenizer(text)
