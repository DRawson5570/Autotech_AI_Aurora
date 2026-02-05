import importlib.util, pathlib


def _load_main():
    main_path = pathlib.Path(__file__).resolve().parents[1] / 'socket' / 'main.py'
    spec = importlib.util.spec_from_file_location('open_webui.socket.main', str(main_path))
    main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main)
    return main


def test_compute_tokens_no_content_does_nothing(monkeypatch):
    main = _load_main()

    # Monkeypatch upsert to raise if it gets called; empty content should not cause an upsert
    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("Chats.upsert_message_to_chat_by_id_and_message_id should not be called for empty content")

    monkeypatch.setattr('open_webui.socket.main.Chats.upsert_message_to_chat_by_id_and_message_id', _should_not_be_called)

    # Should return without exception
    main.compute_tokens_and_record_message('u1', 'c1', 'm-empty', '', 'gpt-3.5-turbo')


def test_compute_tokens_logs_info(monkeypatch, caplog):
    main = _load_main()

    calls = {}

    def fake_upsert(cid, mid, message):
        calls['upsert'] = (cid, mid, message)

    def fake_record_usage(user_id, chat_id, message_id, tokens_prompt, tokens_completion, tokens_total, token_source=None, ts=None):
        calls['record'] = {
            'user_id': user_id,
            'chat_id': chat_id,
            'message_id': message_id,
            'tokens_total': tokens_total,
            'token_source': token_source,
        }

    monkeypatch.setattr('open_webui.socket.main.Chats.upsert_message_to_chat_by_id_and_message_id', lambda cid, mid, m: fake_upsert(cid, mid, m))
    import importlib
    billing = importlib.import_module('open_webui.models.billing')
    monkeypatch.setattr(billing, 'record_usage_event', fake_record_usage)

    caplog.clear()
    caplog.set_level('INFO')

    main.compute_tokens_and_record_message('u2', 'c2', 'm2', 'hello world', 'gpt-3.5-turbo')

    assert 'upsert' in calls
    assert 'record' in calls
    assert any('Computed tokens (total=' in rec.message for rec in caplog.records)
