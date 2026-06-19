"""Tests for the OpenAI-compatible backend adapter."""

import pytest
import responses

from command_line_assistant.daemon.http.openai import from_openai_response, to_openai_payload
from command_line_assistant.daemon.http import query


@pytest.fixture
def base_payload():
    return {
        "question": "How do I list open ports?",
        "context": {
            "systeminfo": {
                "os": "Arch Linux",
                "version": "rolling",
                "arch": "x86_64",
                "id": "arch",
            },
            "terminal": {"output": ""},
            "stdin": {"stdin": ""},
            "attachments": {"contents": "", "mimetype": ""},
        },
    }


@pytest.fixture
def payload_with_context():
    return {
        "question": "What is wrong?",
        "context": {
            "systeminfo": {
                "os": "Arch Linux",
                "version": "rolling",
                "arch": "x86_64",
                "id": "arch",
            },
            "terminal": {"output": "error: command not found"},
            "stdin": {"stdin": "ls /nonexistent"},
            "attachments": {"contents": "file content", "mimetype": "text/plain"},
        },
    }


class TestToOpenaiPayload:
    def test_basic_structure(self, base_payload, mock_config_openai):
        result = to_openai_payload(base_payload, mock_config_openai)
        assert result["model"] == "llama3"
        assert result["stream"] is False
        assert "messages" in result

    def test_user_message_content(self, base_payload, mock_config_openai):
        result = to_openai_payload(base_payload, mock_config_openai)
        user_msgs = [m for m in result["messages"] if m["role"] == "user"]
        assert len(user_msgs) == 1
        assert user_msgs[0]["content"] == "How do I list open ports?"

    def test_system_message_includes_os_info(self, base_payload, mock_config_openai):
        result = to_openai_payload(base_payload, mock_config_openai)
        system_msgs = [m for m in result["messages"] if m["role"] == "system"]
        assert len(system_msgs) == 1
        assert "Arch Linux" in system_msgs[0]["content"]
        assert "x86_64" in system_msgs[0]["content"]

    def test_terminal_output_in_system_message(self, payload_with_context, mock_config_openai):
        result = to_openai_payload(payload_with_context, mock_config_openai)
        system_msgs = [m for m in result["messages"] if m["role"] == "system"]
        assert "error: command not found" in system_msgs[0]["content"]

    def test_stdin_in_system_message(self, payload_with_context, mock_config_openai):
        result = to_openai_payload(payload_with_context, mock_config_openai)
        system_msgs = [m for m in result["messages"] if m["role"] == "system"]
        assert "ls /nonexistent" in system_msgs[0]["content"]

    def test_attachment_in_system_message(self, payload_with_context, mock_config_openai):
        result = to_openai_payload(payload_with_context, mock_config_openai)
        system_msgs = [m for m in result["messages"] if m["role"] == "system"]
        assert "file content" in system_msgs[0]["content"]

    def test_no_system_message_when_no_context(self, mock_config_openai):
        payload = {"question": "hello", "context": {}}
        result = to_openai_payload(payload, mock_config_openai)
        system_msgs = [m for m in result["messages"] if m["role"] == "system"]
        assert len(system_msgs) == 0

    def test_model_from_config(self, base_payload, mock_config_openai):
        mock_config_openai.backend.model = "mistral"
        result = to_openai_payload(base_payload, mock_config_openai)
        assert result["model"] == "mistral"


class TestFromOpenaiResponse:
    def test_extracts_content(self):
        response = {"choices": [{"message": {"content": "Use ss -tulnp"}}]}
        assert from_openai_response(response) == "Use ss -tulnp"

    def test_missing_choices_returns_empty(self):
        assert from_openai_response({}) == ""

    def test_empty_choices_returns_empty(self):
        assert from_openai_response({"choices": []}) == ""

    def test_missing_content_returns_empty(self):
        assert from_openai_response({"choices": [{"message": {}}]}) == ""


class TestQueryRouting:
    @responses.activate
    def test_openai_backend_routes_to_chat_completions(self, base_payload, mock_config_openai):
        responses.post(
            url="http://localhost:11434/v1/chat/completions",
            json={"choices": [{"message": {"content": "Use ss -tulnp"}}]},
        )
        result = query.submit(base_payload, mock_config_openai)
        assert result == "Use ss -tulnp"

    @responses.activate
    def test_rhsm_backend_routes_to_infer(self, base_payload, mock_config):
        responses.post(
            url="http://localhost/infer",
            json={"data": {"text": "Use ss -tulnp"}},
        )
        result = query.submit(base_payload, mock_config)
        assert result == "Use ss -tulnp"

    @responses.activate
    def test_openai_backend_error_response(self, base_payload, mock_config_openai):
        from command_line_assistant.dbus.exceptions import RequestFailedError
        responses.post(
            url="http://localhost:11434/v1/chat/completions",
            status=503,
            json={"detail": "Service temporarily unavailable"},
        )
        with pytest.raises(RequestFailedError):
            query.submit(base_payload, mock_config_openai)
