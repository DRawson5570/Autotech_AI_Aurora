from open_webui.utils.payload import apply_system_prompt_to_body


def test_apply_system_prompt_with_missing_name():
    system = "Hello {{USER_FIRST_NAME}}! I'm Aurora."
    form_data = {"messages": []}
    user = {"id": "2", "name": None}

    out = apply_system_prompt_to_body(system, form_data, metadata=None, user=user)
    assert out["messages"][0]["content"] == "Hello! I'm Aurora."
