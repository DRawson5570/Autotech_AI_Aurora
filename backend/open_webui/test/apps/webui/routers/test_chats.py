import uuid

from test.util.abstract_integration_test import AbstractPostgresTest
from test.util.mock_user import mock_webui_user


class TestChats(AbstractPostgresTest):
    BASE_PATH = "/api/v1/chats"

    def setup_class(cls):
        super().setup_class()

    def setup_method(self):
        super().setup_method()
        from open_webui.models.chats import ChatForm, Chats

        self.chats = Chats
        self.chats.insert_new_chat(
            "2",
            ChatForm(
                **{
                    "chat": {
                        "name": "chat1",
                        "description": "chat1 description",
                        "tags": ["tag1", "tag2"],
                        "history": {"currentId": "1", "messages": []},
                    }
                }
            ),
        )

    def test_get_session_user_chat_list(self):
        with mock_webui_user(id="2"):
            response = self.fast_api_client.get(self.create_url("/"))
        assert response.status_code == 200
        first_chat = response.json()[0]
        assert first_chat["id"] is not None
        assert first_chat["title"] == "New Chat"
        assert first_chat["created_at"] is not None
        assert first_chat["updated_at"] is not None

    def test_delete_all_user_chats(self):
        with mock_webui_user(id="2"):
            response = self.fast_api_client.delete(self.create_url("/"))
        assert response.status_code == 200
        assert len(self.chats.get_chats()) == 0

    def test_get_user_chat_list_by_user_id(self):
        with mock_webui_user(id="3"):
            response = self.fast_api_client.get(self.create_url("/list/user/2"))
        assert response.status_code == 200
        first_chat = response.json()[0]
        assert first_chat["id"] is not None
        assert first_chat["title"] == "New Chat"
        assert first_chat["created_at"] is not None
        assert first_chat["updated_at"] is not None

    def test_create_new_chat(self):
        with mock_webui_user(id="2"):
            response = self.fast_api_client.post(
                self.create_url("/new"),
                json={
                    "chat": {
                        "name": "chat2",
                        "description": "chat2 description",
                        "tags": ["tag1", "tag2"],
                    }
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["archived"] is False
        assert data["chat"] == {
            "name": "chat2",
            "description": "chat2 description",
            "tags": ["tag1", "tag2"],
        }
        assert data["user_id"] == "2"
        assert data["id"] is not None
        assert data["share_id"] is None
        assert data["title"] == "New Chat"
        assert data["updated_at"] is not None
        assert data["created_at"] is not None
        assert len(self.chats.get_chats()) == 2

    def test_get_user_chats(self):
        self.test_get_session_user_chat_list()

    def test_get_user_archived_chats(self):
        self.chats.archive_all_chats_by_user_id("2")
        from open_webui.internal.db import Session

        Session.commit()
        with mock_webui_user(id="2"):
            response = self.fast_api_client.get(self.create_url("/all/archived"))
        assert response.status_code == 200
        first_chat = response.json()[0]
        assert first_chat["id"] is not None
        assert first_chat["title"] == "New Chat"
        assert first_chat["created_at"] is not None
        assert first_chat["updated_at"] is not None

    def test_get_all_user_chats_in_db(self):
        with mock_webui_user(id="4"):
            response = self.fast_api_client.get(self.create_url("/all/db"))
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_get_archived_session_user_chat_list(self):
        self.test_get_user_archived_chats()

    def test_archive_all_chats(self):
        with mock_webui_user(id="2"):
            response = self.fast_api_client.post(self.create_url("/archive/all"))
        assert response.status_code == 200
        assert len(self.chats.get_archived_chats_by_user_id("2")) == 1

    def test_get_shared_chat_by_id(self):
        chat_id = self.chats.get_chats()[0].id
        self.chats.update_chat_share_id_by_id(chat_id, chat_id)

    def test_model_alias_applies_for_user_chat(self):
        # Ensure model_aliases is respected when fetching a chat for a non-admin user
        from open_webui.main import app

        # Set the alias on the running app state for the test
        app.state.MODEL_ALIASES = {"llama3.1:8b": "Aurora AI"}

        # Create a chat with one assistant message using the target model
        from open_webui.models.chats import ChatForm

        msg = {
            "id": "m1",
            "parentId": None,
            "childrenIds": [],
            "role": "assistant",
            "content": "Hello",
            "model": "llama3.1:8b",
            "timestamp": 1700000000,
        }

        chat_form = ChatForm(
            **{
                "chat": {
                    "name": "alias-test",
                    "history": {"currentId": "m1", "messages": {"m1": msg}},
                }
            }
        )

        chat = self.chats.insert_new_chat("2", chat_form)

        with mock_webui_user(id="2"):
            response = self.fast_api_client.get(self.create_url(f"/{chat.id}"))

        assert response.status_code == 200
        returned_chat = response.json()
        messages = returned_chat["chat"]["history"]["messages"]
        assert messages["m1"].get("model_display") == "Aurora AI"

    def test_model_alias_applies_for_models_array(self):
        # Ensure model_aliases is respected for messages that store available models as a list
        from open_webui.main import app

        app.state.MODEL_ALIASES = {"llama3.1:8b": "Aurora AI"}

        from open_webui.models.chats import ChatForm

        msg = {
            "id": "m2",
            "parentId": None,
            "childrenIds": [],
            "role": "assistant",
            "content": "Hello",
            "models": ["llama3.1:8b"],
            "timestamp": 1700000001,
        }

        chat_form = ChatForm(
            **{
                "chat": {
                    "name": "alias-test-2",
                    "history": {"currentId": "m2", "messages": {"m2": msg}},
                }
            }
        )

        chat = self.chats.insert_new_chat("2", chat_form)

        with mock_webui_user(id="2"):
            response = self.fast_api_client.get(self.create_url(f"/{chat.id}"))

        assert response.status_code == 200
        returned_chat = response.json()
        messages = returned_chat["chat"]["history"]["messages"]
        assert messages["m2"].get("model_display") == "Aurora AI"

    def test_model_aliass_from_env_are_used_when_app_state_missing(self):
        # If the running app didn't have MODEL_ALIASES at startup, parse the env var at runtime
        import os
        from open_webui.main import app

        os.environ["MODEL_ALIASES"] = '{"llama3.1:8b": "Aurora AI"}'
        # Simulate a process that didn't set app.state.MODEL_ALIASES at import time
        app.state.MODEL_ALIASES = None

        from open_webui.models.chats import ChatForm

        msg = {
            "id": "m3",
            "parentId": None,
            "childrenIds": [],
            "role": "assistant",
            "content": "Hello",
            "model": "llama3.1:8b",
            "timestamp": 1700000002,
        }

        chat_form = ChatForm(
            **{
                "chat": {
                    "name": "alias-test-3",
                    "history": {"currentId": "m3", "messages": {"m3": msg}},
                }
            }
        )

        chat = self.chats.insert_new_chat("2", chat_form)

        with mock_webui_user(id="2"):
            response = self.fast_api_client.get(self.create_url(f"/{chat.id}"))

        assert response.status_code == 200
        returned_chat = response.json()
        messages = returned_chat["chat"]["history"]["messages"]
        assert messages["m3"].get("model_display") == "Aurora AI"

        # cleanup
        del os.environ["MODEL_ALIASES"]
        with mock_webui_user(id="2"):
            response = self.fast_api_client.get(self.create_url(f"/share/{chat_id}"))
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == chat_id
        assert data["chat"] == {
            "name": "chat1",
            "description": "chat1 description",
            "tags": ["tag1", "tag2"],
            "history": {"currentId": "1", "messages": []},
        }
        assert data["id"] == chat_id
        assert data["share_id"] == chat_id
        assert data["title"] == "New Chat"

    def test_get_chat_by_id(self):
        chat_id = self.chats.get_chats()[0].id
        with mock_webui_user(id="2"):
            response = self.fast_api_client.get(self.create_url(f"/{chat_id}"))
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == chat_id
        assert data["chat"] == {
            "name": "chat1",
            "description": "chat1 description",
            "tags": ["tag1", "tag2"],
            "history": {"currentId": "1", "messages": []},
        }
        assert data["share_id"] is None
        assert data["title"] == "New Chat"
        assert data["user_id"] == "2"

    def test_update_chat_by_id(self):
        chat_id = self.chats.get_chats()[0].id
        with mock_webui_user(id="2"):
            response = self.fast_api_client.post(
                self.create_url(f"/{chat_id}"),
                json={
                    "chat": {
                        "name": "chat2",
                        "description": "chat2 description",
                        "tags": ["tag2", "tag4"],
                        "title": "Just another title",
                    }
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == chat_id
        assert data["chat"] == {
            "name": "chat2",
            "title": "Just another title",
            "description": "chat2 description",
            "tags": ["tag2", "tag4"],
            "history": {"currentId": "1", "messages": []},
        }
        assert data["share_id"] is None
        assert data["title"] == "Just another title"
        assert data["user_id"] == "2"

    def test_delete_chat_by_id(self):
        chat_id = self.chats.get_chats()[0].id
        with mock_webui_user(id="2"):
            response = self.fast_api_client.delete(self.create_url(f"/{chat_id}"))
        assert response.status_code == 200
        assert response.json() is True

    def test_clone_chat_by_id(self):
        chat_id = self.chats.get_chats()[0].id
        with mock_webui_user(id="2"):
            response = self.fast_api_client.get(self.create_url(f"/{chat_id}/clone"))

        assert response.status_code == 200
        data = response.json()
        assert data["id"] != chat_id
        assert data["chat"] == {
            "branchPointMessageId": "1",
            "description": "chat1 description",
            "history": {"currentId": "1", "messages": []},
            "name": "chat1",
            "originalChatId": chat_id,
            "tags": ["tag1", "tag2"],
            "title": "Clone of New Chat",
        }
        assert data["share_id"] is None
        assert data["title"] == "Clone of New Chat"
        assert data["user_id"] == "2"

    def test_archive_chat_by_id(self):
        chat_id = self.chats.get_chats()[0].id
        with mock_webui_user(id="2"):
            response = self.fast_api_client.get(self.create_url(f"/{chat_id}/archive"))
        assert response.status_code == 200

        chat = self.chats.get_chat_by_id(chat_id)
        assert chat.archived is True

    def test_share_chat_by_id(self):
        chat_id = self.chats.get_chats()[0].id
        with mock_webui_user(id="2"):
            response = self.fast_api_client.post(self.create_url(f"/{chat_id}/share"))
        assert response.status_code == 200

        chat = self.chats.get_chat_by_id(chat_id)
        assert chat.share_id is not None

    def test_delete_shared_chat_by_id(self):
        chat_id = self.chats.get_chats()[0].id
        share_id = str(uuid.uuid4())
        self.chats.update_chat_share_id_by_id(chat_id, share_id)
        with mock_webui_user(id="2"):
            response = self.fast_api_client.delete(self.create_url(f"/{chat_id}/share"))
        assert response.status_code

        chat = self.chats.get_chat_by_id(chat_id)
        assert chat.share_id is None
