import importlib.util, pathlib

from open_webui.models.chats import Chats


def test_upsert_triggers_compute(monkeypatch):
    calls = {}

    # Fake chat model returned by get_chat_by_id
    class FakeChat:
        def __init__(self):
            self.user_id = "user123"
            self.chat = {"history": {"messages": {}}}

    def fake_get_chat(self, id):
        return FakeChat()

    # Replace the bound method on the singleton instance to avoid DB access
    chats = Chats
    chats.get_chat_by_id = lambda id: FakeChat()

    def fake_compute(user_id, chat_id, message_id, content, model_name=None):
        calls['compute'] = (user_id, chat_id, message_id, content, model_name)

    monkeypatch.setattr('open_webui.socket.main.compute_tokens_and_record_message', fake_compute)

    # Call upsert which should trigger the compute helper for content without tokens
    chats.upsert_message_to_chat_by_id_and_message_id('chat-1', 'msg-1', {'content': 'hello there'})

    assert 'compute' in calls
    assert calls['compute'][0] == 'user123'
    assert calls['compute'][1] == 'chat-1'
    assert calls['compute'][2] == 'msg-1'