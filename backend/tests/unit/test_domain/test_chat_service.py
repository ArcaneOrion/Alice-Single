from unittest.mock import MagicMock

import pytest
from backend.alice.domain.llm.models.message import ChatMessage
from backend.alice.domain.llm.services.chat_service import ChatService


class _EnvelopeLike:
    def __init__(self) -> None:
        self._payload = {
            "system": {"prompt": "You are Alice"},
            "messages": [ChatMessage.user("current question").to_dict()],
            "model_context": {
                "local_time": {
                    "iso": "2026-04-01T12:00:00+08:00",
                    "timezone": "CST",
                    "source": "local",
                },
                "memory_snapshot": {
                    "working": "working notes",
                    "short_term": "",
                    "long_term": "long term memory",
                },
                "skill_snapshot": {
                    "summary": "toolkit, memory",
                },
            },
            "tool_history": [
                {
                    "tool_name": "run_bash",
                    "status": "success",
                    "output": "hi",
                }
            ],
        }

    def to_dict(self) -> dict:
        return dict(self._payload)


@pytest.mark.unit
def test_chat_service_projects_only_model_visible_context_into_system_message() -> None:
    service = ChatService(provider=MagicMock(), system_prompt="You are Alice")

    request_messages = service.build_request_messages(
        request_envelope=_EnvelopeLike()
    )

    assert request_messages[0].role == "system"
    assert request_messages[0].content.startswith("You are Alice")
    assert "<runtime_context>" not in request_messages[0].content
    assert "working notes" in request_messages[0].content
    assert "long term memory" in request_messages[0].content
    assert "toolkit, memory" in request_messages[0].content
    assert "run_bash" in request_messages[0].content
    assert "short_term" not in request_messages[0].content
    assert request_messages[1] == ChatMessage.user("current question")
