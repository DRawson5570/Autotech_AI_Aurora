def test_compute_tokens_and_record_message_monkeypatched(monkeypatch):
    calls = {}

    def fake_upsert(chat_id, message_id, message):
        calls['upsert'] = (chat_id, message_id, message)

    def fake_record_usage(user_id, chat_id, message_id, tokens_prompt, tokens_completion, tokens_total, token_source=None, ts=None):
        calls['record'] = {
            'user_id': user_id,
            'chat_id': chat_id,
            'message_id': message_id,
            'tokens_prompt': tokens_prompt,
            'tokens_completion': tokens_completion,
            'tokens_total': tokens_total,
            'token_source': token_source,
        }

    import importlib.util, pathlib
    main_path = pathlib.Path(__file__).resolve().parents[1] / 'socket' / 'main.py'
    spec = importlib.util.spec_from_file_location('open_webui.socket.main', str(main_path))
    main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main)

    # Monkeypatch Chats.upsert_message_to_chat_by_id_and_message_id
    monkeypatch.setattr('open_webui.socket.main.Chats.upsert_message_to_chat_by_id_and_message_id', lambda cid, mid, m: fake_upsert(cid, mid, m))
    # Monkeypatch billing.record_usage_event
    import importlib
    billing = importlib.import_module('open_webui.models.billing')
    monkeypatch.setattr(billing, 'record_usage_event', fake_record_usage)

    # Call helper
    main.compute_tokens_and_record_message('user1', 'chat1', 'msg1', 'hello world, this is a test', 'gpt-3.5-turbo')

    assert 'upsert' in calls
    assert 'record' in calls
    assert int(calls['record']['tokens_total']) >= 1
    assert calls['record']['token_source'] == 'computed'