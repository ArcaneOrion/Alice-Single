from __future__ import annotations

import logging

import pytest

from backend.alice.domain.llm.models.message import ChatMessage
from backend.alice.domain.llm.models.stream_chunk import StreamChunk, TokenUsageUpdate, ToolCallDelta
from backend.alice.domain.llm.providers.base import BaseLLMProvider, ProviderCapability
from backend.alice.domain.llm.services.stream_service import StreamService, build_tool_kwargs


class _RuntimeStreamProvider(BaseLLMProvider):
    def __init__(self, capabilities: ProviderCapability | None = None) -> None:
        super().__init__("gpt-4o-mini")
        if capabilities is not None:
            self._capabilities = capabilities
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
def test_build_tool_kwargs_preserves_metadata_without_tools() -> None:
    provider = _RuntimeStreamProvider()

    kwargs = build_tool_kwargs(provider, [], metadata={"request_id": "req-1", "trace_id": "trace-1"})

    assert kwargs == {
        "metadata": {
            "request_id": "req-1",
            "trace_id": "trace-1",
        }
    }


@pytest.mark.unit
def test_build_tool_kwargs_preserves_request_envelope() -> None:
    provider = _RuntimeStreamProvider()

    kwargs = build_tool_kwargs(
        provider,
        [],
        metadata={"request_id": "req-1"},
        request_envelope={"request_metadata": {"trace_id": "trace-1", "span_id": "span-1"}},
    )

    assert kwargs == {
        "metadata": {"request_id": "req-1"},
        "request_envelope": {"request_metadata": {"trace_id": "trace-1", "span_id": "span-1"}},
    }
    assert "tools" not in kwargs
    assert "tool_choice" not in kwargs


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


@pytest.mark.unit
def test_build_tool_kwargs_logs_binding_snapshot_when_tools_bound(caplog) -> None:
    provider = _RuntimeStreamProvider()
    tools = [{"type": "function", "function": {"name": "run_bash"}}]

    with caplog.at_level(logging.INFO):
        kwargs = build_tool_kwargs(
            provider,
            tools,
            metadata={"request_id": "req-1", "trace_id": "trace-1", "task_id": "task-1"},
        )

    assert kwargs["tools"] == tools
    assert kwargs["tool_choice"] == "auto"
    snapshot = next(
        record
        for record in caplog.records
        if getattr(record, "event_type", "") == "binding.tools_bound"
    )
    assert snapshot.data == {
        "model": provider.model_name,
        "tool_count": 1,
        "tool_names": ["run_bash"],
        "supports_tool_calling": True,
        "decision": "bound",
    }


@pytest.mark.unit
def test_build_tool_kwargs_logs_binding_rejection_for_capability_mismatch(caplog) -> None:
    provider = _RuntimeStreamProvider(capabilities=ProviderCapability(supports_tool_calling=False))
    tools = [{"type": "function", "function": {"name": "run_bash"}}]

    with caplog.at_level(logging.WARNING):
        with pytest.raises(ValueError, match="当前模型不支持结构化 tool calling"):
            build_tool_kwargs(
                provider,
                tools,
                metadata={"request_id": "req-2", "trace_id": "trace-2", "task_id": "task-2"},
            )

    rejected = next(
        record
        for record in caplog.records
        if getattr(record, "event_type", "") == "binding.capability_mismatch"
    )
    assert rejected.data == {
        "model": provider.model_name,
        "tool_count": 1,
        "tool_names": ["run_bash"],
        "supports_tool_calling": False,
        "decision": "rejected",
        "reason": "provider_does_not_support_tool_calling",
    }


@pytest.mark.unit
def test_build_tool_kwargs_treats_metadata_and_request_envelope_as_separate_layers() -> None:
    provider = _RuntimeStreamProvider()

    kwargs = build_tool_kwargs(
        provider,
        [{"type": "function", "function": {"name": "run_bash"}}],
        metadata={"request_id": "req-1", "trace_id": "trace-1"},
        request_envelope={"request_metadata": {"trace_id": "trace-1"}},
    )

    assert kwargs == {
        "metadata": {"request_id": "req-1", "trace_id": "trace-1"},
        "request_envelope": {"request_metadata": {"trace_id": "trace-1"}},
        "tools": [{"type": "function", "function": {"name": "run_bash"}}],
        "tool_choice": "auto",
    }
    assert "request_metadata" not in kwargs["metadata"]
    assert "metadata" not in kwargs["request_envelope"]
    assert build_tool_kwargs(provider, [], metadata={"trace_id": "trace-2"}) == {
        "metadata": {"trace_id": "trace-2"}
    }
    assert build_tool_kwargs(provider, [], request_envelope={"request_metadata": {"trace_id": "trace-3"}}) == {
        "request_envelope": {"request_metadata": {"trace_id": "trace-3"}}
    }
    assert build_tool_kwargs(provider, []) == {}


__all__ = []
