import uuid
import time
from open_webui.models.users import Users
from open_webui.models.chats import Chats
# Import billing module dynamically to ensure latest file is loaded when tests run
import importlib.util, pathlib
billing_path = pathlib.Path(__file__).resolve().parents[3] / 'models' / 'billing.py'
spec = importlib.util.spec_from_file_location('open_webui.models.billing', str(billing_path))
billing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(billing)
UsageEvent = billing.UsageEvent
UserTokenUsage = billing.UserTokenUsage
record_usage_event = billing.record_usage_event
from test.util.abstract_integration_test import AbstractPostgresTest
from test.util.mock_user import mock_webui_user


def _get_usage_events_by_user(db, user_id):
    return list(db.query(UsageEvent).filter_by(user_id=user_id))


class TestBillingUsage(AbstractPostgresTest):
    def setup_method(self):
        super().setup_method()
        # create a user and a chat
        self.uid = f"billing_user_{uuid.uuid4().hex[:8]}"
        Users.insert_new_user(self.uid, "Billing User", f"{self.uid}@example.com")
        self.user = Users.get_user_by_email(f"{self.uid}@example.com")
        # create a chat
        chat = Chats.insert_new_chat(self.user.id, Chats.ChatForm(chat={"title": "Billing Chat", "history": {"messages": {}, "currentId": None}}))
        self.chat_id = chat.id

    def test_record_usage_event_via_socket_emitter(self):
        # simulate the emitter recording; call record_usage_event directly for unit behavior
        ts = int(time.time())
        record_usage_event(self.user.id, self.chat_id, "m1", 5, 10, 15, token_source="openai", ts=ts)

        # verify usage_event exists
        with self.postgres_engine.connect() as conn:
            res = conn.execute("SELECT * FROM usage_event WHERE user_id = %s", (self.user.id,))
            rows = list(res)
            assert len(rows) >= 1

        # verify aggregate exists
        with self.postgres_engine.connect() as conn:
            res2 = conn.execute("SELECT * FROM user_token_usage WHERE user_id = %s", (self.user.id,))
            rows2 = list(res2)
            assert len(rows2) == 1
            assert int(rows2[0]["tokens_total"]) >= 15

    def test_compute_and_record_tokens_when_missing(self):
        # Simulate a provider that does not return usage; the emitter should compute tokens from content
        content = "This is a short generated response to be tokenized."
        msg_id = "m2"
        Chats.upsert_message_to_chat_by_id_and_message_id(self.chat_id, msg_id, {"content": content})

        # Dynamically import the socket main to access the helper without import-time side-effects
        import importlib.util, pathlib
        main_path = pathlib.Path(__file__).resolve().parents[3] / 'socket' / 'main.py'
        main_spec = importlib.util.spec_from_file_location('open_webui.socket.main', str(main_path))
        main = importlib.util.module_from_spec(main_spec)
        main_spec.loader.exec_module(main)

        # Call the helper which should compute tokens, persist to message, and record a usage_event
        main.compute_tokens_and_record_message(self.user.id, self.chat_id, msg_id, content, "gpt-3.5-turbo")

        # verify a usage_event exists for the user
        with self.postgres_engine.connect() as conn:
            res = conn.execute("SELECT * FROM usage_event WHERE user_id = %s ORDER BY ts DESC", (self.user.id,))
            rows = list(res)
            assert len(rows) >= 1
            assert int(rows[0]["tokens_total"]) >= 1

        # verify the message contains token fields
        msg = Chats.get_message_by_id_and_message_id(self.chat_id, msg_id)
        assert int(msg.get("tokens_total", 0)) >= 1

    def test_emitter_computes_and_records_usage_end_to_end(self):
        # Create an empty message, then emit a message event with content but no usage; emitter should compute tokens
        msg_id = "m-emitter"
        Chats.upsert_message_to_chat_by_id_and_message_id(self.chat_id, msg_id, {"content": ""})

        request_info = {
            "user_id": self.user.id,
            "chat_id": self.chat_id,
            "message_id": msg_id,
            "session_id": "test-session",
        }

        from open_webui.socket.main import get_event_emitter
        emitter = get_event_emitter(request_info, update_db=True)
        assert emitter is not None

        import asyncio
        event_data = {"type": "message", "data": {"content": "Generated response from provider without usage."}}

        # run emitter
        asyncio.run(emitter(event_data))

        # verify usage_event exists
        with self.postgres_engine.connect() as conn:
            res = conn.execute("SELECT * FROM usage_event WHERE user_id = %s ORDER BY created_at DESC", (self.user.id,))
            rows = list(res)
            assert len(rows) >= 1
            assert int(rows[0]["tokens_total"]) >= 1

        # verify the message contains token fields
        msg = Chats.get_message_by_id_and_message_id(self.chat_id, msg_id)
        assert int(msg.get("tokens_total", 0)) >= 1
