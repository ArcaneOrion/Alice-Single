from __future__ import annotations

import pytest

from backend.alice.domain.llm.models.message import ChatMessage
from backend.alice.domain.llm.models.stream_chunk import StreamChunk, TokenUsageUpdate, ToolCallDelta
from backend.alice.domain.llm.providers.base import BaseLLMProvider
from backend.alice.domain.llm.services.stream_service import StreamService


class _RuntimeStreamProvider(BaseLLMProvider):
    def __init__(self) -> None:
        super().__init__("gpt-4o-mini")
        self._chunks = [
            StreamChunk(
                content="```python\nprint(1)\n```",
                tool_calls=[
                    ToolCallDelta(index=0, id="call_1", type="function", function_name="run_python"),
                ],
            ),
            StreamChunk(
                thinking="native reasoning",
                tool_calls=[
                    ToolCallDelta(index=0, function_arguments='{"code": "print(1)'),
                ],
            ),
            StreamChunk(
                tool_calls=[
                    ToolCallDelta(index=0, function_arguments='"}'),
                ],
                usage=TokenUsageUpdate(prompt_tokens=2, completion_tokens=3, total_tokens=5),
                is_complete=True,
            ),
        ]

    def _make_chat_request(self, messages, stream: bool = False, **kwargs):
        _ = messages, stream, kwargs
        return None

    def _extract_stream_chunks(self, response):
        _ = response
        yield from self._chunks


@pytest.mark.unit
def test_stream_runtime_keeps_content_as_content_without_parser_heuristics() -> None:
    service = StreamService(provider=_RuntimeStreamProvider())

    events = list(service.stream_runtime([ChatMessage.user("run something")]))
    event_types = [event["event_type"] for event in events]

    assert event_types == [
        "tool_call_started",
        "content_delta",
        "tool_call_argument_delta",
        "reasoning_delta",
        "usage_updated",
        "tool_call_argument_delta",
        "tool_call_completed",
        "message_completed",
    ]

    assert events[0]["payload"]["function"]["name"] == "run_python"
    assert events[1] == {
        "event_type": "content_delta",
        "payload": {"content": "```python\nprint(1)\n```"},
    }
    assert events[2]["payload"]["delta"] == '{"code": "print(1)'
    assert events[3] == {
        "event_type": "reasoning_delta",
        "payload": {"content": "native reasoning"},
    }
    assert events[4]["payload"]["usage"]["total_tokens"] == 5
    assert events[5]["payload"]["delta"] == '"}'
    assert events[6]["payload"]["function"]["arguments"] == '{"code": "print(1)"}'
    assert events[7]["payload"] == {
        "content": "```python\nprint(1)\n```",
        "reasoning": "native reasoning",
        "usage": {
            "prompt_tokens": 2,
            "completion_tokens": 3,
            "total_tokens": 5,
        },
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "index": 0,
                "function": {
                    "name": "run_python",
                    "arguments": '{"code": "print(1)"}',
                },
            }
        ],
    }
