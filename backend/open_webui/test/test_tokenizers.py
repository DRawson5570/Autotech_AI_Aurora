import pytest

from open_webui.local_tokenizers import count_tokens_for_model



def test_count_tokens_basic():
    text = "Hello, world! This is a test."
    n = count_tokens_for_model(text)
    assert isinstance(n, int)
    assert n > 0


def test_count_tokens_reproducible():
    text = "one two three four five"
    n1 = count_tokens_for_model(text)
    n2 = count_tokens_for_model(text)
    assert n1 == n2


@pytest.mark.parametrize("model", [None, "gpt-3.5-turbo", "gpt-4-mini"])
def test_count_tokens_for_models(model):
    text = "The quick brown fox jumps over the lazy dog"
    n = count_tokens_for_model(text, model)
    assert isinstance(n, int)
    assert n >= 1
