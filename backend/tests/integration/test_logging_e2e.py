"""Integration coverage for the JSONL logging pipeline."""

import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.alice.core.logging.jsonl_logger import JSONLCategoryFileHandler
from backend.alice.domain.llm.models.message import ChatMessage
from backend.alice.domain.llm.models.stream_chunk import StreamChunk, TokenUsageUpdate, ToolCallDelta
from backend.alice.domain.llm.providers.base import BaseLLMProvider, ProviderCapability
from backend.alice.domain.llm.providers.openai_provider import OpenAIConfig, OpenAIProvider
from backend.alice.domain.llm.services.stream_service import StreamService, build_tool_kwargs
from backend.alice.infrastructure.bridge.canonical_bridge import CanonicalBridgeEvent, CanonicalEventType
from backend.alice.infrastructure.bridge.legacy_compatibility_serializer import serialize_canonical_event


REQUIRED_FIELDS = ("ts", "event_type", "level", "source")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _assert_required_fields(record: dict[str, object]) -> None:
    for field in REQUIRED_FIELDS:
        assert field in record, f"Missing {field} in {record}"


class _DummyStreamProvider(BaseLLMProvider):
    """简化的流式 provider，用于在集成测试中触发 llm 日志。"""

    def __init__(self, capabilities: ProviderCapability | None = None) -> None:
        super().__init__("test-model")
        if capabilities is not None:
            self._capabilities = capabilities
        self._chunks = [
            StreamChunk(
                content="payload chunk",
                thinking="analysis chunk",
                usage=TokenUsageUpdate(prompt_tokens=2, completion_tokens=3, total_tokens=5),
                is_complete=True,
            )
        ]

    def _make_chat_request(
        self,
        messages: list[ChatMessage],
        stream: bool = False,
        **kwargs,
    ):
        _ = messages, stream, kwargs
        return None

    def _extract_stream_chunks(self, response):
        _ = response
        yield from self._chunks


class _NoToolSupportProvider(_DummyStreamProvider):
    def __init__(self) -> None:
        super().__init__(capabilities=ProviderCapability(supports_tool_calling=False))


class _DummyToolCallStreamProvider(BaseLLMProvider):
    def __init__(self) -> None:
        super().__init__("test-model")
        self._chunks = [
            StreamChunk(
                tool_calls=[
                    ToolCallDelta(index=0, id="call_1", type="function", function_name="run_bash"),
                ]
            ),
            StreamChunk(
                tool_calls=[ToolCallDelta(index=0, function_arguments='{"command": "echo')],
            ),
            StreamChunk(
                tool_calls=[ToolCallDelta(index=0, function_arguments=' hi"}')],
                is_complete=True,
            ),
        ]

    def _make_chat_request(
        self,
        messages: list[ChatMessage],
        stream: bool = False,
        **kwargs,
    ):
        _ = messages, stream, kwargs
        return None

    def _extract_stream_chunks(self, response):
        _ = response
        yield from self._chunks


class _FakeRawResponse:
    def __init__(self, response, *, request_id: str = "req-openai-1", status_code: int = 200, retries_taken: int = 0) -> None:
        self._response = response
        self.status_code = status_code
        self.retries_taken = retries_taken
        self.headers = {"x-request-id": request_id}

    def parse(self):
        return self._response


class _FakeCompletions:
    def __init__(self, response) -> None:
        self._response = response
        self.captured_params = None
        self.with_raw_response = self

    def create(self, **params):
        self.captured_params = params
        return _FakeRawResponse(self._response)


class _FakeChat:
    def __init__(self, response) -> None:
        self.completions = _FakeCompletions(response)


class _FakeOpenAIClient:
    def __init__(self, response) -> None:
        self.chat = _FakeChat(response)


class _FakeOpenAIProvider(OpenAIProvider):
    def __init__(self, response) -> None:
        super().__init__(
            OpenAIConfig(
                api_key="test-key",
                base_url="https://example.test/v1",
                model_name="gpt-4o-mini",
            )
        )
        self._client = _FakeOpenAIClient(response)


def _build_openai_response(content: str):
    return SimpleNamespace(
        id="resp-openai-1",
        model="gpt-4o-mini",
        usage={"prompt_tokens": 7, "completion_tokens": 5, "total_tokens": 12},
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content=content),
            )
        ],
    )


def _build_stream_service(log_dir: Path, provider: BaseLLMProvider) -> tuple[logging.Logger, JSONLCategoryFileHandler, StreamService]:
    handler = JSONLCategoryFileHandler(
        log_dir=log_dir,
        category_mapping={
            "llm.stream": "tasks",
            "bridge.compatibility": "tasks",
        },
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)

    logger = logging.getLogger("alice.validation.e2e")
    logger.setLevel(logging.DEBUG)
    logger.propagate = True
    logger.handlers.clear()

    return logger, handler, StreamService(provider)


def _close_handler(handler: JSONLCategoryFileHandler) -> None:
    root_logger = logging.getLogger()
    handler.flush()
    handler.close()
    root_logger.removeHandler(handler)


def _api_records(tasks_records: list[dict]) -> list[dict]:
    return [
        record
        for record in tasks_records
        if record["event_type"].startswith("model.") or record["event_type"].startswith("api.")
    ]


def _assert_api_context(records: list[dict], *, task_id: str, trace_id: str) -> None:
    assert records, "Expected provider/api events to land in tasks.jsonl"
    for record in records:
        context = record.get("context", {})
        assert context.get("task_id") == task_id
        assert context.get("request_id") == trace_id
        assert context.get("trace_id") == trace_id


def _find_event(records: list[dict], event_type: str) -> dict:
    return next(record for record in records if record["event_type"] == event_type)


def _tool_call_arguments(record: dict) -> str:
    aggregated = record.get("data", {}).get("tool_calls_aggregated", [])
    assert aggregated
    return aggregated[0]["function_arguments"]


def _tool_call_delta_arguments(record: dict) -> list[str | None]:
    deltas = record.get("data", {}).get("tool_calls_delta", [])
    return [delta.get("function_arguments") for delta in deltas]


def _read_tasks_records(log_dir: Path) -> list[dict]:
    return _read_jsonl(log_dir / "tasks.jsonl")


def _bridge_records(tasks_records: list[dict]) -> list[dict]:
    return [record for record in tasks_records if record["event_type"].startswith("bridge.")]


def _binding_records(tasks_records: list[dict]) -> list[dict]:
    return [record for record in tasks_records if record["event_type"].startswith("binding.")]


def _run_stream_collect(service: StreamService, *, task_id: str, trace_id: str):
    return service.stream_collect(
        [ChatMessage.user("run validation flow")],
        metadata={
            "task_id": task_id,
            "trace_id": trace_id,
            "session_id": "session-llm",
        },
    )


def _assert_logging_pipeline(tasks_records: list[dict], *, task_id: str, trace_id: str) -> None:
    api_records = _api_records(tasks_records)
    _assert_api_context(api_records, task_id=task_id, trace_id=trace_id)
    for record in tasks_records[:4]:
        _assert_required_fields(record)
        assert record.get("task_id") == task_id


def _emit_manual_lifecycle_logs(logger: logging.Logger, *, task_id: str) -> None:
    logger.info(
        "Agent bootstrap",
        extra={"event_type": "system.start", "log_category": "system"},
    )
    logger.info(
        "Task queued",
        extra={
            "event_type": "task.created",
            "log_category": "tasks",
            "task_id": task_id,
            "data": {"intent": "validate logging"},
        },
    )
    logger.info(
        "Task starts exec",
        extra={
            "event_type": "task.started",
            "log_category": "tasks",
            "task_id": task_id,
            "span_id": "span-abc",
        },
    )
    logger.info(
        "Task progress update",
        extra={
            "event_type": "task.progress",
            "log_category": "tasks",
            "task_id": task_id,
            "data": {"phase": "logging"},
        },
    )
    logger.info(
        "Task finished",
        extra={
            "event_type": "task.completed",
            "log_category": "tasks",
            "task_id": task_id,
        },
    )
    logger.info(
        "Prompt file saved",
        extra={
            "event_type": "change.file_saved",
            "log_category": "changes",
            "data": {"file": "prompts/alice.md", "size": 512},
        },
    )


def _assert_core_log_files(log_dir: Path, *, task_id: str, trace_id: str) -> list[dict]:
    system_records = _read_jsonl(log_dir / "system.jsonl")
    assert len(system_records) == 1
    _assert_required_fields(system_records[0])
    assert system_records[0]["event_type"] == "system.start"

    tasks_records = _read_tasks_records(log_dir)
    expected_lifecycle = ["task.created", "task.started", "task.progress", "task.completed"]
    assert [record["event_type"] for record in tasks_records[:4]] == expected_lifecycle
    _assert_logging_pipeline(tasks_records, task_id=task_id, trace_id=trace_id)

    changes_records = _read_jsonl(log_dir / "changes.jsonl")
    assert len(changes_records) == 1
    _assert_required_fields(changes_records[0])
    assert changes_records[0]["event_type"] == "change.file_saved"

    return tasks_records


@pytest.mark.integration
def test_logging_e2e_creates_structured_jsonl_files(tmp_path: Path) -> None:
    """Validate the end-to-end logging pipeline for system, tasks, changes, and llm events."""

    log_dir = tmp_path / "logs" / "validation"
    logger, handler, service = _build_stream_service(log_dir, _DummyStreamProvider())

    task_id = "task-lifecycle-001"
    trace_id = "trace-llm-001"
    _emit_manual_lifecycle_logs(logger, task_id=task_id)
    _run_stream_collect(service, task_id=task_id, trace_id=trace_id)

    _close_handler(handler)

    assert log_dir.exists(), "Log directory should be created by the handler"

    tasks_records = _assert_core_log_files(log_dir, task_id=task_id, trace_id=trace_id)
    api_records = _api_records(tasks_records)
    assert [record["event_type"] for record in api_records] == [
        "model.stream_started",
        "model.prompt_built",
        "model.stream_chunk",
        "model.stream_completed",
    ]

    assert api_records[0]["data"]["operation"] == "stream_collect"
    assert api_records[1]["data"]["operation"] == "stream_chat"
    assert api_records[0]["context"]["component"] == "llm.stream_service"
    assert api_records[1]["context"]["component"] == "llm.provider.base"

    completed = _find_event(tasks_records, "model.stream_completed")
    assert completed["data"]["content"] == "payload chunk"
    assert completed["data"]["thinking"] == "analysis chunk"
    assert completed["data"]["usage"] == {
        "prompt_tokens": "*",
        "completion_tokens": "*",
        "total_tokens": "*",
    }


@pytest.mark.integration
def test_logging_e2e_tracks_typed_tool_call_aggregation(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs" / "tool-calls"
    _, handler, service = _build_stream_service(log_dir, _DummyToolCallStreamProvider())

    task_id = "task-tool-001"
    trace_id = "trace-tool-001"
    response = _run_stream_collect(service, task_id=task_id, trace_id=trace_id)

    _close_handler(handler)

    tasks_records = _read_tasks_records(log_dir)
    api_records = _api_records(tasks_records)
    _assert_api_context(api_records, task_id=task_id, trace_id=trace_id)

    for record in api_records:
        _assert_required_fields(record)
        assert record["source"]
        assert record["level"]
        assert isinstance(record.get("data", {}), dict)

    assert [record["event_type"] for record in api_records] == [
        "model.stream_started",
        "model.prompt_built",
        "model.stream_chunk",
        "model.tool_decision",
        "model.stream_chunk",
        "model.tool_decision",
        "model.stream_chunk",
        "model.tool_decision",
        "model.stream_completed",
    ]

    assert {record["event_type"] for record in api_records} == {
        "model.stream_started",
        "model.prompt_built",
        "model.stream_chunk",
        "model.tool_decision",
        "model.stream_completed",
    }

    assert all(
        record["data"].get("operation") in {"stream_collect", "stream_chat"}
        for record in api_records
    )
    assert all(
        record["context"].get("component") in {"llm.stream_service", "llm.provider.base"}
        for record in api_records
    )
    assert all(
        "latency_ms" in record.get("timing", {})
        for record in api_records
        if record["event_type"] not in {"model.stream_started", "model.prompt_built"}
    )

    stream_chunks = [record for record in tasks_records if record["event_type"] == "model.stream_chunk"]
    tool_decisions = [record for record in tasks_records if record["event_type"] == "model.tool_decision"]
    completed = _find_event(tasks_records, "model.stream_completed")
    started = _find_event(tasks_records, "model.stream_started")

    assert len(stream_chunks) == 3
    assert len(tool_decisions) == 3
    assert len([record for record in tasks_records if record["event_type"].startswith("model.")]) == 9
    assert completed["data"]["chunk_count"] == 3
    assert started["data"]["operation"] == "stream_collect"
    assert started["data"]["message_count"] == 1

    assert _tool_call_delta_arguments(stream_chunks[0]) == [None]
    assert _tool_call_delta_arguments(stream_chunks[1]) == ['{"command": "echo']
    assert _tool_call_delta_arguments(stream_chunks[2]) == [' hi"}']

    assert _tool_call_arguments(stream_chunks[0]) == ""
    assert _tool_call_arguments(stream_chunks[1]) == '{"command": "echo'
    assert _tool_call_arguments(stream_chunks[2]) == '{"command": "echo hi"}'
    assert _tool_call_arguments(tool_decisions[-1]) == '{"command": "echo hi"}'
    assert _tool_call_arguments(completed) == '{"command": "echo hi"}'

    assert all(record["data"].get("content_delta", "") == "" for record in stream_chunks)
    assert all(record["data"].get("thinking_delta", "") == "" for record in stream_chunks)
    assert all(record["data"].get("tool_calls_aggregated") for record in tool_decisions)

    assert completed["data"]["tool_calls_aggregated"] == [
        {
            "index": 0,
            "id": "call_1",
            "type": "function",
            "function_name": "run_bash",
            "function_arguments": '{"command": "echo hi"}',
        }
    ]
    assert completed["data"]["content"] == ""
    assert completed["data"]["thinking"] == ""
    assert completed["data"]["usage"] == {}

    assert response.tool_calls == [
        {
            "id": "call_1",
            "type": "function",
            "index": 0,
            "function": {
                "name": "run_bash",
                "arguments": '{"command": "echo hi"}',
            },
        }
    ]
    assert response.content == ""
    assert response.thinking == ""
    assert response.usage is None

    assert not _read_jsonl(log_dir / "system.jsonl")
    assert not _read_jsonl(log_dir / "changes.jsonl")


@pytest.mark.integration
def test_logging_e2e_tracks_binding_observability_events(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs" / "binding-observability"
    _, handler, _ = _build_stream_service(log_dir, _DummyStreamProvider())

    bound_kwargs = build_tool_kwargs(
        _DummyStreamProvider(),
        [{"type": "function", "function": {"name": "run_bash"}}],
        metadata={"task_id": "task-bind-1", "trace_id": "trace-bind-1", "request_id": "req-bind-1"},
    )

    with pytest.raises(ValueError, match="当前模型不支持结构化 tool calling"):
        build_tool_kwargs(
            _NoToolSupportProvider(),
            [{"type": "function", "function": {"name": "run_bash"}}],
            metadata={"task_id": "task-bind-2", "trace_id": "trace-bind-2", "request_id": "req-bind-2"},
        )

    _close_handler(handler)

    assert bound_kwargs["tool_choice"] == "auto"
    tasks_records = _read_tasks_records(log_dir)
    binding_records = _binding_records(tasks_records)
    assert [record["event_type"] for record in binding_records] == [
        "binding.tools_bound",
        "binding.capability_mismatch",
    ]

    tools_bound = _find_event(tasks_records, "binding.tools_bound")
    capability_mismatch = _find_event(tasks_records, "binding.capability_mismatch")

    assert tools_bound["context"]["task_id"] == "task-bind-1"
    assert tools_bound["data"] == {
        "model": "test-model",
        "tool_count": 1,
        "tool_names": ["run_bash"],
        "supports_tool_calling": True,
        "decision": "bound",
    }
    assert capability_mismatch["context"]["task_id"] == "task-bind-2"
    assert capability_mismatch["data"] == {
        "model": "test-model",
        "tool_count": 1,
        "tool_names": ["run_bash"],
        "supports_tool_calling": False,
        "decision": "rejected",
        "reason": "provider_does_not_support_tool_calling",
    }


@pytest.mark.integration
def test_logging_e2e_tracks_openai_api_request_observability(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs" / "openai-request"
    _, handler, _ = _build_stream_service(log_dir, _DummyStreamProvider())

    provider = _FakeOpenAIProvider(_build_openai_response("provider payload"))
    request_kwargs = {
        "metadata": {
            "task_id": "task-request-1",
            "trace_id": "trace-request-1",
            "request_id": "req-request-1",
            "session_id": "session-request-1",
            "span_id": "span-request-1",
        },
        "request_envelope": {
            "request_metadata": {
                "trace_id": "trace-envelope-1",
                "request_id": "req-envelope-1",
                "task_id": "task-envelope-1",
                "session_id": "session-envelope-1",
                "span_id": "span-envelope-1",
            }
        },
        "temperature": 0.2,
    }
    messages = [
        ChatMessage.system("<runtime_context>\ncurrent_question: where?\nrequest_metadata: {'trace_id': 'trace-request-1'}"),
        ChatMessage.user("hello provider"),
    ]

    response = provider.chat(messages, **request_kwargs)

    _close_handler(handler)

    assert response.content == "provider payload"
    tasks_records = _read_tasks_records(log_dir)
    api_request = _find_event(tasks_records, "api.request")
    api_response = _find_event(tasks_records, "api.response")
    prompt_built = _find_event(tasks_records, "model.prompt_built")

    for record in (prompt_built, api_request, api_response):
        _assert_required_fields(record)

    assert api_request["context"] == {
        "trace_id": "trace-envelope-1",
        "request_id": "req-envelope-1",
        "task_id": "task-envelope-1",
        "session_id": "session-envelope-1",
        "span_id": "span-envelope-1",
        "component": "llm.provider.openai",
        "phase": "request",
        "payload_kind": "chat.completions",
    }
    assert api_request["data"]["provider"] == "openai"
    assert api_request["data"]["base_url"] == "https://example.test/v1"
    assert api_request["data"]["request_path"] == "/chat/completions"
    assert api_request["data"]["model"] == "gpt-4o-mini"
    assert api_request["data"]["stream"] is False
    assert api_request["data"]["timeout"] == 120
    assert api_request["data"]["max_retries"] == 2
    assert api_request["data"]["request_count"] == 1
    assert api_request["data"]["extra_headers"]["User-Agent"] == "curl/8.0"
    assert api_request["data"]["request_params"]["temperature"] == 0.2
    assert api_request["data"]["request_params"]["stream"] is False
    assert api_request["data"]["request_params"]["model"] == "gpt-4o-mini"
    assert "request_envelope" not in api_request["data"]["request_params"]
    assert api_request["data"]["message_count"] == 2
    assert api_request["data"]["role_distribution"] == {"system": 1, "user": 1}
    assert api_request["data"]["messages"][0]["role"] == "system"
    assert "<runtime_context>" in api_request["data"]["messages"][0]["content"]
    assert "current_question" in api_request["data"]["messages"][0]["content"]
    assert "request_metadata" in api_request["data"]["messages"][0]["content"]
    assert api_request["data"]["payload"]["temperature"] == 0.2
    assert api_request["data"]["payload"]["messages"][1]["content"] == "hello provider"

    assert prompt_built["context"]["component"] == "llm.provider.base"
    assert prompt_built["context"]["phase"] == "prepare"
    assert prompt_built["context"]["payload_kind"] == "messages"
    assert prompt_built["context"]["trace_id"] == "trace-envelope-1"
    assert prompt_built["data"]["request_kwargs"]["metadata"]["trace_id"] == "trace-request-1"
    assert prompt_built["data"]["request_kwargs"]["request_envelope"]["request_metadata"]["trace_id"] == "trace-envelope-1"

    assert api_response["context"]["request_id"] == "req-envelope-1"
    assert api_response["data"]["provider"] == "openai"
    assert api_response["data"]["response_request_id"] == "req-openai-1"
    assert api_response["data"]["status_code"] == 200
    assert api_response["data"]["usage"] == {
        "prompt_tokens": "*",
        "completion_tokens": "*",
        "total_tokens": "**",
    }
    assert "latency_ms" in api_response.get("timing", {})

    assert not _read_jsonl(log_dir / "system.jsonl")
    assert not _read_jsonl(log_dir / "changes.jsonl")


@pytest.mark.integration
def test_logging_e2e_tracks_legacy_compatibility_projection_events(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs" / "bridge-compatibility"
    _, handler, _ = _build_stream_service(log_dir, _DummyStreamProvider())

    projected = serialize_canonical_event(
        CanonicalBridgeEvent(
            event_type=CanonicalEventType.TOOL_CALL_STARTED,
            payload={"tool_name": "run_bash"},
        )
    )
    dropped = serialize_canonical_event(
        CanonicalBridgeEvent(
            event_type=CanonicalEventType.TOOL_RESULT,
            payload={"tool_call_id": "call_1", "content": "ok"},
        )
    )

    _close_handler(handler)

    assert projected == {"type": "status", "content": "executing_tool"}
    assert dropped is None

    tasks_records = _read_tasks_records(log_dir)
    bridge_records = _bridge_records(tasks_records)
    assert [record["event_type"] for record in bridge_records] == [
        "bridge.compatibility_serializer_used",
        "bridge.event_dropped_by_legacy_projection",
    ]

    serializer_used = _find_event(tasks_records, "bridge.compatibility_serializer_used")
    dropped_record = _find_event(tasks_records, "bridge.event_dropped_by_legacy_projection")

    assert serializer_used["context"]["component"] == "legacy_compatibility_serializer"
    assert serializer_used["data"] == {
        "source_kind": "canonical_event",
        "canonical_event_type": "tool_call_started",
        "legacy_message_type": "status",
        "legacy_status": "executing_tool",
    }
    assert dropped_record["context"]["component"] == "legacy_compatibility_serializer"
    assert dropped_record["data"] == {
        "source_kind": "canonical_event",
        "dropped_event_type": "tool_result",
        "reason": "unsupported_canonical_event",
        "payload_keys": ["content", "tool_call_id"],
    }
