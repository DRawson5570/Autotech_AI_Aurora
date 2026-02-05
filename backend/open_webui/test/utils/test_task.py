import pytest
from open_webui.utils.task import prompt_template


def test_prompt_template_with_name():
    tpl = "Hello {{USER_FIRST_NAME}}! I'm Aurora."
    user = {"id": "1", "name": "Bryon Smith"}
    out = prompt_template(tpl, user)
    assert "Hello Bryon!" in out


def test_prompt_template_without_name():
    tpl = "Hello {{USER_FIRST_NAME}}! I'm Aurora."
    user = {"id": "2", "name": None}
    out = prompt_template(tpl, user)
    # Should not contain the stray space before punctuation
    assert "Hello! I'm Aurora." in out
