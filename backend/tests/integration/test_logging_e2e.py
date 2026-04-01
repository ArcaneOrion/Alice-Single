"""Integration coverage for the JSONL logging pipeline."""

import json
import logging
from pathlib import Path

import pytest

from backend.alice.core.logging.jsonl_logger import JSONLCategoryFileHandler
from backend.alice.domain.llm.models.message import ChatMessage
from backend.alice.domain.llm.models.stream_chunk import StreamChunk, TokenUsageUpdate, ToolCallDelta
from backend.alice.domain.llm.providers.base import BaseLLMProvider
from backend.alice.domain.llm.services.stream_service import StreamService


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

    def __init__(self) -> None:
        super().__init__("test-model")
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


def _build_stream_service(log_dir: Path, provider: BaseLLMProvider) -> tuple[logging.Logger, JSONLCategoryFileHandler, StreamService]:
    handler = JSONLCategoryFileHandler(
        log_dir=log_dir,
        category_mapping={"llm.stream": "tasks"},
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
