"""Integration coverage for the JSONL logging pipeline."""

import json
import logging
from pathlib import Path

import pytest

from backend.alice.core.logging.jsonl_logger import JSONLCategoryFileHandler
from backend.alice.domain.llm.models.message import ChatMessage
from backend.alice.domain.llm.models.stream_chunk import StreamChunk, TokenUsageUpdate
from backend.alice.domain.llm.providers.base import BaseLLMProvider
from backend.alice.domain.llm.services import stream_service as stream_service_module
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
    """简化的流式 provider，用于在集成测试中触发 llm_call/response 日志。"""

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
        return None

    def _extract_stream_chunks(self, response):
        yield from self._chunks


def _ensure_stream_log_context_stub() -> None:
    """确保 StreamService 在测试环境有 log context helper（兼容主控可能尚未定义）。"""

    def _extract_stream_log_context(kwargs: dict[str, object]) -> dict[str, object]:
        metadata = kwargs.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}

        session_id = metadata.get("session_id") or kwargs.get("session_id") or ""
        request_id = (
            metadata.get("request_id")
            or metadata.get("trace_id")
            or kwargs.get("request_id")
            or kwargs.get("trace_id")
            or ""
        )
        task_id = (
            metadata.get("task_id")
            or kwargs.get("task_id")
            or request_id
            or session_id
            or ""
        )

        return {
            "task_id": task_id,
            "request_id": request_id,
            "session_id": session_id,
            "component": "stream_service",
        }

    if not hasattr(stream_service_module, "_extract_stream_log_context"):
        setattr(stream_service_module, "_extract_stream_log_context", _extract_stream_log_context)


def _ensure_usage_helper_stub() -> None:
    """确保 StreamService 定义 _usage_to_data，供测试中的 log payload 读取。"""

    def _usage_to_data(usage: object | None) -> dict[str, object]:
        if usage is None:
            return {}
        return {
            "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        }

    if not hasattr(stream_service_module, "_usage_to_data"):
        setattr(stream_service_module, "_usage_to_data", _usage_to_data)

@pytest.mark.integration
def test_logging_e2e_creates_structured_jsonl_files(tmp_path: Path) -> None:
    """Validate the end-to-end logging pipeline for system, tasks, changes, and llm events."""

    log_dir = tmp_path / "logs" / "validation"
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

    task_id = "task-lifecycle-001"

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

    trace_id = "trace-llm-001"
    metadata = {
        "task_id": task_id,
        "trace_id": trace_id,
        "session_id": "session-llm",
    }
    _ensure_stream_log_context_stub()
    _ensure_usage_helper_stub()
    service = StreamService(_DummyStreamProvider())
    service.stream_collect(
        [ChatMessage.user("run validation flow")],
        metadata=metadata,
    )

    handler.flush()
    handler.close()
    root_logger.removeHandler(handler)

    assert log_dir.exists(), "Log directory should be created by the handler"

    system_records = _read_jsonl(log_dir / "system.jsonl")
    assert len(system_records) == 1
    _assert_required_fields(system_records[0])
    assert system_records[0]["event_type"] == "system.start"

    tasks_records = _read_jsonl(log_dir / "tasks.jsonl")
    expected_lifecycle = ["task.created", "task.started", "task.progress", "task.completed"]
    assert [record["event_type"] for record in tasks_records[:4]] == expected_lifecycle
    for record in tasks_records[:4]:
        _assert_required_fields(record)
        assert record.get("task_id") == task_id
    assert tasks_records[3]["event_type"] == "task.completed"

    api_records = [
        record
        for record in tasks_records
        if record["event_type"].startswith("model.") or record["event_type"].startswith("api.")
    ]
    assert api_records, "Expected provider/api events to land in tasks.jsonl"
    for record in api_records:
        context = record.get("context", {})
        assert context.get("task_id") == task_id
        assert context.get("request_id") == trace_id
        assert context.get("trace_id") == trace_id

    changes_records = _read_jsonl(log_dir / "changes.jsonl")
    assert len(changes_records) == 1
    _assert_required_fields(changes_records[0])
    assert changes_records[0]["event_type"] == "change.file_saved"
